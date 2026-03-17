#!/usr/bin/env python3

"""
Get file uri from ingest id
"""

# Layer imports
from orcabus_api_tools.filemanager import get_s3_uri_from_ingest_id

def handler(event, context):
    """
    Given an ingest id, return the s3 uri

    Input: ingestId
    Output: outputFileUri
    """

    return {
        "outputFileUri": get_s3_uri_from_ingest_id(event.get("ingestId"))
    }
