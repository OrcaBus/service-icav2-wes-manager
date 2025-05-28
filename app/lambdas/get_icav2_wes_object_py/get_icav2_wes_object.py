#!/usr/bin/env python3

"""
Get the ICAv2 WES Object
"""
from typing import Dict, Any

from orcabus_api_tools.icav2_wes import get_icav2_wes_analysis_by_name


def handler(event, context) -> Dict[str, Any]:
    """
    Get the ICAv2 WES Object
    """
    # Get the analysis name from the event
    name = event.get("name")
    if not name:
        raise ValueError("No analysis name provided")

    # Get the ICAv2 WES Object
    icav2_wes_object = get_icav2_wes_analysis_by_name(
        analysis_name=name
    )

    return {
        "icav2WesObject": icav2_wes_object,
    }
