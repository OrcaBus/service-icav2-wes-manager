#!/usr/bin/env python3

"""
Given an analysis id, find the analysis id in the database and update the status on the ICAv2 wes api.
"""

# Standard imports
from typing import Dict

# Layer imports
from orcabus_api_tools.icav2_wes import (
    get_icav2_wes_analysis_by_name,
    update_icav2_wes_analysis_status
)

# Globals
ICAV2_WES_ORCABUS_ID_TAG_NAME = 'icav2_wes_orcabus_id'


def handler(event, context) -> Dict:
    """
    Update the status of analysis on the ICAv2 WES API
    :param event:
    :param context:
    :return:
    """

    # Get the name from the event
    name = event.get("name")

    # Get the status from the event
    status = event.get("status")

    # Get the analysis id from the event
    icav2_analysis_id = event.get("icav2AnalysisId")

    # Get the analysis object
    analysis_object = get_icav2_wes_analysis_by_name(
        analysis_name=name
    )

    # Update the status on the ICAv2 WES API
    update_response = update_icav2_wes_analysis_status(
        # Positional args in snake_case
        icav2_wes_orcabus_id=analysis_object['id'],
        # Keyword (packed) args in camelCase
        status=status,
        icav2AnalysisId=icav2_analysis_id,
    )

    # Return the response payload (We don't actually need this, since updating the API generates the event)
    return dict(update_response)
