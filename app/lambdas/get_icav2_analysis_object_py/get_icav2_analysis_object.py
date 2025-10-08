#!/usr/bin/env python3

"""
Get the icav2 analysis object from the workflow name
"""

# Standard Library Imports
from typing import Dict, Any
from fastapi.encoders import jsonable_encoder

# Wrapica imports
from wrapica.project_analysis import get_analysis_obj_from_analysis_id

# Layer imports
from icav2_tools import set_icav2_env_vars
from orcabus_api_tools.icav2_wes import get_icav2_wes_analysis_by_name


def handler(event, context) -> Dict[str, Any]:
    """
    Get the ICAv2 WES Object
    """
    # Set the environment variables for icav2
    set_icav2_env_vars()

    # Get the analysis name from the event
    name = event.get("name")
    if not name:
        raise ValueError("No analysis name provided")

    # Get the ICAv2 WES Object
    icav2_wes_object = get_icav2_wes_analysis_by_name(
        analysis_name=name
    )

    # Get the pipeline id
    project_id = icav2_wes_object.get("engineParameters", {}).get("projectId")
    analysis_id = icav2_wes_object.get("icav2AnalysisId")

    return {
        "icav2AnalysisObject": jsonable_encoder(
            get_analysis_obj_from_analysis_id(
                project_id=project_id,
                analysis_id=analysis_id
            )
        ),
    }
