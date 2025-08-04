#!/usr/bin/env python3

"""
Given an icav2 analysis id, abort the analysis
"""

# Wrapica imports
from wrapica.project_analysis import (
    get_analysis_obj_from_analysis_id,
    abort_analysis
)

# Layer imports
from icav2_tools import set_icav2_env_vars


def handler(event, context):
    """
    Lambda function to abort an icav2 analysis
    :param event:
    :param context:
    :return:
    """

    # Set the environment variables for icav2
    set_icav2_env_vars()

    # Get the project id + analysis id from the event payload
    project_id = event.get('projectId')
    analysis_id = event.get('analysisId')

    # Get the analysis / checks that the analysis is valid
    analysis_obj = get_analysis_obj_from_analysis_id(
        project_id=project_id,
        analysis_id=analysis_id
    )

    # Abort the analysis
    abort_analysis(
        project_id=project_id,
        analysis_id=analysis_obj.id
    )

    return {}
