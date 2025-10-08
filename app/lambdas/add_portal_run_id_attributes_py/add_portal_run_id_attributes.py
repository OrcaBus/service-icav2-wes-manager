#!/usr/bin/env python3

"""
Add portal run id attributes from the filemanager
"""

# Standard imports
from urllib.parse import urlparse
from pathlib import Path

# Layer imports
from orcabus_api_tools.filemanager import file_manager_patch_request
from orcabus_api_tools.filemanager.globals import S3_LIST_ENDPOINT


def handler(event, context):
    """
    Add the portal run id attributes for the output uri
    :param event:
    :param context:
    :return:
    """

    output_uri = event.get("outputUri")
    portal_run_id = event.get("portalRunId")

    # Get the output uri and key
    output_uri_parsed = urlparse(output_uri)
    output_bucket = output_uri_parsed.netloc
    output_key = output_uri_parsed.path.lstrip('/')

    # Confirm that the output uri endswith the portal run id
    if not Path(output_key).name == portal_run_id:
        raise ValueError(f"The output uri {output_uri} does not end with the portal run id {portal_run_id}")

    # Add the portal run id attribute to the output uri
    file_manager_patch_request(
        endpoint=S3_LIST_ENDPOINT,
        params={
            "bucket": output_bucket,
            "key": f"{output_key.rstrip('/')}/*",
        },
        json_data=[
            {
                'op': 'add',
                'path': '/portalRunId',
                'value': portal_run_id
            }
        ]
    )
