#!/usr/bin/env python3

"""
Get the ICAv2 WES Object
"""

# Standard Library Imports
from typing import Dict, Any

# Layer imports
from orcabus_api_tools.icav2_wes import get_icav2_wes_request
from orcabus_api_tools.icav2_wes.globals import ANALYSES_ENDPOINT


def handler(event, context) -> Dict[str, Any]:
    """
    Get the ICAv2 WES Object by its orcabus ID (direct hash key lookup).
    Falls back to name-based lookup for backwards compatibility.
    """
    # Prefer icav2WesOrcabusId for direct lookup by DynamoDB hash key
    icav2_wes_orcabus_id = event.get("icav2WesOrcabusId")

    if not icav2_wes_orcabus_id:
        raise ValueError("No icav2WesOrcabusId provided")

    # Direct GET by ID — uses DynamoDB hash key, avoids GSI query
    icav2_wes_object = get_icav2_wes_request(
        f"{ANALYSES_ENDPOINT}/{icav2_wes_orcabus_id}"
    )

    return {
        "icav2WesObject": icav2_wes_object,
    }
