#!/usr/bin/env python3

"""
Get the icav2 analysis object from the workflow orcabus id
"""

# Standard Library Imports
from typing import Dict, Any

# Wrapica imports
from wrapica.project_analysis import get_analysis_obj_from_analysis_id

# Layer imports
from icav2_tools import set_icav2_env_vars
from orcabus_api_tools.icav2_wes import get_icav2_wes_request
from orcabus_api_tools.icav2_wes.globals import ANALYSES_ENDPOINT


def handler(event, context) -> Dict[str, Any]:
    """
    Get the ICAv2 WES Object and determine the pipeline language
    """
    # Set the environment variables for icav2
    set_icav2_env_vars()

    # Prefer icav2WesOrcabusId for direct lookup by DynamoDB hash key
    icav2_wes_orcabus_id = event.get("icav2WesOrcabusId")

    if not icav2_wes_orcabus_id:
        raise ValueError("No icav2WesOrcabusId provided")

    # Direct GET by ID — uses DynamoDB hash key, avoids GSI query
    icav2_wes_object = get_icav2_wes_request(
        f"{ANALYSES_ENDPOINT}/{icav2_wes_orcabus_id}"
    )

    # Get the pipeline id
    project_id = icav2_wes_object.get("engineParameters", {}).get("projectId")
    analysis_id = icav2_wes_object.get("icav2AnalysisId")

    # Get analysis object
    analysis_obj = get_analysis_obj_from_analysis_id(
        project_id=project_id,
        analysis_id=analysis_id
    )

    return {
        "language": analysis_obj.pipeline.language
    }
