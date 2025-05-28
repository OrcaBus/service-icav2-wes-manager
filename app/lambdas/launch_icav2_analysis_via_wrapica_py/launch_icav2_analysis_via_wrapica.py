#!/usr/bin/env python3

"""
Launch the ICAv2 analysis.

Given the name, inputs, engine parameters, launch the analysis on ICAv2!
"""
# Standard imports
import json
import logging
from copy import copy
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Dict

# Wrapica imports
from wrapica.enums import AnalysisStorageSize
from wrapica.pipelines import get_pipeline_obj_from_pipeline_id
from wrapica.project_pipelines import (
    get_analysis_storage_from_analysis_storage_size,
    ICAv2PipelineAnalysisTags, Analysis
)
from wrapica.utils import recursively_build_open_api_body_from_libica_item

# Layer imports
from icav2_tools import set_icav2_env_vars


def camel_case_to_snake_case(camel_case_str: str) -> str:
    # Convert fastqListRowId to fastq_list_row_id
    return ''.join(['_' + i.lower() if i.isupper() else i for i in camel_case_str]).lstrip('_')


def flatten_user_tags(user_tags: Dict) -> Dict:
    user_tags = dict(
        map(
            lambda kv: (camel_case_to_snake_case(kv[0]), kv[1]),
            user_tags.items()
        )
    )

    for key, value in copy(user_tags).items():
        if isinstance(value, list):
            for iter_, value_iter in enumerate(value):
                user_tags[f"{key}.{iter_}"] = value_iter
            del user_tags[key]

    return user_tags


def handler(event, context):
    """
    We expect the following event attributes
      * name
      * inputs
      * engineParameters
      * tags
    :param event:
    :param context:
    :return:
    """

    # Set icav2 env vars
    set_icav2_env_vars()

    # Check if the event has the required attributes
    if not all(key in event for key in ['name', 'inputs', 'engineParameters', 'tags']):
        raise ValueError("Event must contain 'name', 'inputs', 'engineParameters', and 'tags' attributes")

    # Extract the WES attributes from the event
    id = event['id']
    name = event['name']
    inputs = event['inputs']
    engine_parameters = event['engineParameters']
    user_tags = event.get('tags', {})
    technical_tags = event.get('technicalTags', None)

    # Get the analysis storage size
    # FIXME

    # Get the pipeline id from the engine parameters
    pipeline_id = engine_parameters['pipelineId']

    # Get the project id from the engine parameters
    project_id = engine_parameters['projectId']

    # Get the analysis output uri and ica logs uri from the engine parameters
    analysis_output_uri = engine_parameters['outputUri']
    ica_logs_uri = engine_parameters['logsUri']

    # Get the pipeline object (to get the workflow language type)
    pipeline_obj = get_pipeline_obj_from_pipeline_id(pipeline_id)

    # Get the workflow type, one of CWL or NEXTFLOW
    workflow_type = pipeline_obj.language

    # Not sure if wrapica / libica can handle this yet
    # Assume all is XML
    # if pipeline_obj.input_form_type:
    #     input_form_type = pipeline_obj.input_form_type
    # else:
    #     input_form_type = 'XML'

    # Imports based on workflow type
    if workflow_type.lower() == 'cwl':
        from wrapica.project_pipelines import (
            ICAv2CwlAnalysisJsonInput as ICAv2AnalysisInput,
            ICAv2CWLPipelineAnalysis as ICAv2PipelineAnalysis,
        )
        # Collect the input json
        icav2_analysis_input_obj = ICAv2AnalysisInput(
            input_json=inputs
        )
    elif workflow_type.lower() == 'nextflow':
        from wrapica.project_pipelines import (
            ICAv2NextflowAnalysisInput as ICAv2AnalysisInput,
            ICAv2NextflowPipelineAnalysis as ICAv2PipelineAnalysis,
        )
        # Collect the input json
        icav2_analysis_input_obj = ICAv2AnalysisInput(
            input_json=inputs,
            project_id=project_id,
            pipeline_id=pipeline_id
        )
    else:
        raise ValueError(f"workflow_type should be one of 'nextflow' or 'cwl' got {workflow_type} instead")

    # Get the analysis storage size from the event
    # FIXME - need to directly use analysis storage size while
    # FIXME - https://github.com/umccr/wrapica/issues/115
    analysis_storage_size_event_val = event.get("analysis_storage_size")
    if analysis_storage_size_event_val is not None and not analysis_storage_size_event_val in AnalysisStorageSize.__members__.keys():
        logging.error(
            "Error: analysis_storage_size must be a string representing the AnalysisStorageSize enum value"
        )
        raise ValueError()
    if analysis_storage_size_event_val is not None:
        analysis_storage_size: AnalysisStorageSize = AnalysisStorageSize(analysis_storage_size_event_val)
    else:
        # Get the default analysis storage size from the pipeline object
        pipeline_obj = get_pipeline_obj_from_pipeline_id(pipeline_id)
        analysis_storage_size = AnalysisStorageSize(pipeline_obj.analysis_storage.name)

    # Initialise an ICAv2CWLPipeline Analysis object
    analysis_obj = ICAv2PipelineAnalysis(
        user_reference=name,
        project_id=project_id,
        pipeline_id=pipeline_id,
        analysis_input=icav2_analysis_input_obj.create_analysis_input(),
        # FIXME - https://github.com/umccr/wrapica/issues/115
        analysis_storage_id=get_analysis_storage_from_analysis_storage_size(analysis_storage_size).id,
        analysis_output_uri=analysis_output_uri,
        ica_logs_uri=ica_logs_uri,
        tags=ICAv2PipelineAnalysisTags(
            technical_tags=technical_tags,
            user_tags=user_tags,
            reference_tags=[]
        )
    )

    # Generate the inputs and analysis object
    # Call the object to launch it
    analysis_launch_obj: Analysis = analysis_obj(
        idempotency_key=id
    )

    # Save the analysis
    with NamedTemporaryFile(suffix='.json') as temp_file:
        analysis_obj.save_analysis(Path(temp_file.name))

        with open(Path(temp_file.name), 'r') as tmp_file_h:
            analysis_launch_payload = json.load(tmp_file_h)

    return {
        "analysisId": analysis_launch_obj.id,
        "analysisStatus": analysis_launch_obj.status,
        "analysisResponsePayload": recursively_build_open_api_body_from_libica_item(analysis_launch_obj),
        "analysisLaunchPayload": analysis_launch_payload
    }
