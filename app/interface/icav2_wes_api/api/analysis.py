#!/usr/bin/env python3

"""

Routes for the API V1 Fastq endpoint

This is the list of routes available
-

"""

# Standard imports
from datetime import datetime, timezone
from os import environ
from textwrap import dedent
from typing import Annotated

from fastapi import Depends, Query, Body
from fastapi.routing import APIRouter, HTTPException
from dyntastic import A, DoesNotExist

from fastapi_tools import QueryPagination

# Model imports
from ..models.analysis import (
    Icav2WesAnalysisData,
    Icav2WesAnalysisQueryPaginatedResponse,
    Icav2WesAnalysisCreate,
    Icav2WesAnalysisResponse,
    Icav2WesAnalysisPatch
)
from ..models.analysis_query import AnalysisQueryParameters
from ..globals import (
    ICAV2_WES_LAUNCH_STATE_MACHINE_ARN_ENV_VAR,
    ICAV2_WES_ABORT_MACHINE_ARN_ENV_VAR,
    get_default_job_patch_entry,
)
from ..utils import (
    sanitise_icav2_wes_analysis_orcabus_id,
    launch_sfn
)
from ..events.events import put_icav2_wes_analysis_update_event

router = APIRouter()


# Define a dependency function that returns the pagination parameters
def get_pagination_params(
    # page must be greater than or equal to 1
    page: int = Query(1, gt=0),
    # rowsPerPage must be greater than 0
    rows_per_page: int = Query(100, gt=0, alias='rowsPerPage')
) -> QueryPagination:
    return {"page": page, "rowsPerPage": rows_per_page}


## Query options
# - Get /analysis endpoint for a given fastq list row id
@router.get(
    "/",
    tags=["query"]
)
async def get_icav2_wes_analysis_list(
        analysis_query_parameters: AnalysisQueryParameters = Depends(),
        # Pagination options
        pagination: QueryPagination = Depends(get_pagination_params),
) -> Icav2WesAnalysisQueryPaginatedResponse:
    # Job Query Parameters include start time, end time and status
    # We also include the fastq id as a parameter however this is not indexed and so needs to be filtered manually
    # As such we will first filter by the indexed parameters and then filter by the fastq id
    # If no indexed parameters are provided, we will perform a scan and then filter by the fastq id

    # Let's try and generate the filter expression
    # We have the following indexed keys in the database (tied to status),
    filter_expression = None
    # FIXME - skipping time queries for now
    # if job_query_parameters.created_before is not None:
    #     filter_expression = filter_expression & (A.start_time <= job_query_parameters.created_before)
    # if job_query_parameters.created_after is not None:
    #     filter_expression = filter_expression & (A.start_time >= job_query_parameters.created_after)
    # if job_query_parameters.completed_before is not None:
    #     filter_expression = filter_expression & (A.end_time <= job_query_parameters.completed_before)
    # if job_query_parameters.completed_after is not None:
    #     filter_expression = filter_expression & (A.end_time >= job_query_parameters.completed_after)

    # To query or to scan, depends on if the status is provided
    # Since the status is indexed to the jobs
    if analysis_query_parameters.status_list is not None:
        # - start_time
        # - end_time
        # With the following query parameters
        # - created_before
        # - created_after
        # - completed_before
        # - completed_after
        icav2_wes_analysis_list = []
        for status_iter in analysis_query_parameters.status_list:
            icav2_wes_analysis_list += list(Icav2WesAnalysisData.query(
                A.status == status_iter,
                filter_condition=filter_expression,
                index="status-index",
                load_full_item=True
            ))
    else:
        icav2_wes_analysis_list = list(Icav2WesAnalysisData.scan(
            filter_condition=filter_expression,
            load_full_item=True
        ))

    # Now check if the fastq_id_list is in the query parameters
    if analysis_query_parameters.name_list is not None:
        icav2_wes_analysis_list = list(filter(
            lambda analysis_iter_: analysis_iter_.name in analysis_query_parameters.name_list,
            icav2_wes_analysis_list
        ))

    return Icav2WesAnalysisQueryPaginatedResponse.from_results_list(
        results=list(map(
            lambda icav2_wes_analysis_iter_: icav2_wes_analysis_iter_.to_dict(),
            icav2_wes_analysis_list,
        )),
        query_pagination=pagination,
        params_response=dict(filter(
            lambda kv: kv[1] is not None,
            dict(
                **analysis_query_parameters.to_params_dict(),
                **pagination
            ).items()
        )),
    )


# Get a job from orcabus id
@router.get(
    "/{analysis_id}",
    tags=["query"],
    description="Get an analysis object"
)
async def get_jobs(job_id: str = Depends(sanitise_icav2_wes_analysis_orcabus_id)) -> Icav2WesAnalysisResponse:
    try:
        return Icav2WesAnalysisData.get(job_id).to_dict()
    except DoesNotExist as e:
        raise HTTPException(status_code=404, detail=str(e))


# Create a job object
@router.post(
    "/",
    tags=["icav2 wes create"],
    description=dedent("""
    Create a new ICAv2 WES Analysis.
    Given a list of fastq list row orcabus ids, create a new unarchiving job.
    This will create a new job object and return the job object as a response.
    """)
)
async def create_job(analysis_obj: Icav2WesAnalysisCreate) -> Icav2WesAnalysisResponse:
    # First convert the CreateFastqListRow to a FastqListRow
    analysis_obj = Icav2WesAnalysisData(**dict(analysis_obj.model_dump(by_alias=True)))

    if (
            # Check if the analysis name already exists in the database
            len(list(Icav2WesAnalysisData.query(
                A.name == analysis_obj.name,
                index="name-index",
                load_full_item=True
            ))) > 0
    ):
        raise HTTPException(
        status_code=409,
        detail=f"Analysis with name '{analysis_obj.name}' already exists"
    )


    # Can't solve every race condition, but this is pretty close to immediate
    analysis_obj.save()

    # Now launch the job - we skip the 'PENDING' phase for now
    # Instead we go straight to 'SUBMITTED'
    analysis_obj.start_time = datetime.now(timezone.utc)
    analysis_obj.steps_launch_execution_arn = launch_sfn(
        sfn_name=environ[ICAV2_WES_LAUNCH_STATE_MACHINE_ARN_ENV_VAR],
        sfn_input=dict(analysis_obj.to_dict())
    )

    # Save the analysis (so two events dont get created)
    analysis_obj.status = 'SUBMITTED'

    # Re-save the object
    analysis_obj.save()

    # Create the dictionary
    analysis_dict = analysis_obj.to_dict()

    # Generate a create event
    put_icav2_wes_analysis_update_event(analysis_dict)

    # Return the fastq as a dictionary
    return analysis_dict


@router.patch(
    "/{analysis_id}",
    tags=["job update"],
    description=dedent("""
    Update the status of a job, internal-use only
    """)
)
async def update_job(analysis_id: str = Depends(sanitise_icav2_wes_analysis_orcabus_id), analysis_change_object: Annotated[Icav2WesAnalysisPatch, Body()] = get_default_job_patch_entry()) -> Icav2WesAnalysisResponse:
    if analysis_change_object.status not in ['RUNNABLE', 'STARTING', 'RUNNING', 'SUCCEEDED', 'FAILED', 'ABORTED']:
        raise HTTPException(
            status_code=400,
            detail="Invalid status provided, "
                   "must be one of RUNNING, STARTING, RUNNING, SUCCEEDED, FAILED or ABORTED")
    try:
        analysis_obj = Icav2WesAnalysisData.get(analysis_id)
        analysis_obj.status = analysis_change_object.status
        # Add in end time if the job is in a terminal state
        if analysis_obj.status in ['SUCCEEDED', 'FAILED', 'ABORTED']:
            analysis_obj.end_time = datetime.now(timezone.utc)
        if (
                analysis_obj.icav2_analysis_id is None and
                analysis_change_object.icav2AnalysisId is not None
        ):
            analysis_obj.icav2_analysis_id = analysis_change_object.icav2AnalysisId

        # Save the object
        analysis_obj.save()

        # Create the response, and event
        analysis_dict = analysis_obj.to_dict()
        put_icav2_wes_analysis_update_event(analysis_dict)
        return analysis_dict
    except DoesNotExist as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.patch(
    "/{analysis_id}:abort",
    tags=["job abort"],
    description=dedent("""
    Abort a job. This will abort a job and set the status to ABORTED
    """)
)
async def abort_job(analysis_id: str = Depends(sanitise_icav2_wes_analysis_orcabus_id)) -> str:
    try:
        analysis_obj = Icav2WesAnalysisData.get(analysis_id)

        if not analysis_obj.status in ['STARTING', 'RUNNING']:
            raise AssertionError("Job is not in a state that can be aborted")

        # Abort the execution arn
        # We do not set the status just yet, as we wait for the ICAv2 WES event to come
        # In and set the status to ABORTED then
        launch_sfn(
            sfn_name=environ[ICAV2_WES_ABORT_MACHINE_ARN_ENV_VAR],
            sfn_input=dict(analysis_obj.to_dict())
        )

        analysis_obj.save()
        return f"Aborting analysis {analysis_obj.icav2_analysis_id}"
    except DoesNotExist as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
