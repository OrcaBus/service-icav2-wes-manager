#!/usr/bin/env python3

"""
Filemanager sync script

Check if the filemanager has the same number of files as the aws s3 api command returns
"""

# Standard imports
from urllib.parse import urlparse
import logging

# Wrapica imports
from wrapica.project_data import find_project_data_bulk, convert_uri_to_project_data_obj

# Layer imports
from icav2_tools import set_icav2_env_vars
from orcabus_api_tools.filemanager import get_file_manager_request_response_results

# Setup logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def handler(event, context):
    """
    List the files in the filemanager recursively
    :param event:
    :param context:
    :return:
    """
    # Set icav2 env vars
    set_icav2_env_vars()

    # Get the bucket, key from the event
    output_uri = event['outputUri']
    portal_run_id = event['portalRunId']
    icav2_project_data_obj = convert_uri_to_project_data_obj(output_uri)

    # Parse the s3 uri
    s3_bucket = urlparse(output_uri).netloc
    s3_key_prefix = urlparse(output_uri).path.lstrip('/')

    # Filemanager files (via attributes)
    filemanager_files = list(filter(
        # Remove iap temporary test files
        lambda file_obj_iter_: (
            # Not the iap temp copy test file
            ( not file_obj_iter_['key'].endswith('.iap_xaccount_test.tmp') ) and
            # Match the bucket and key prefix
            file_obj_iter_['bucket'] == s3_bucket and
            file_obj_iter_['key'].startswith(s3_key_prefix)
        ),
        # Get the files from the filemanager
        get_file_manager_request_response_results(
            endpoint="api/v1/s3/attributes",
            params={
                # Portal run id attributes
                "portalRunId": portal_run_id,
            }
        )
    ))

    # List files via icav2
    icav2_project_data_list = find_project_data_bulk(
        project_id=icav2_project_data_obj.project_id,
        parent_folder_id=icav2_project_data_obj.data.id,
        data_type='FILE'
    )

    # We try again in a few minutes
    if len(filemanager_files) != len(icav2_project_data_list):
        logger.info(
            f"Filemanager has {len(filemanager_files)} files, "
            f"ICAv2 has {len(icav2_project_data_list)} files"
        )
        return {
            "isSynced": False,
        }

    # If the number of files is the same, we pass the check
    else:
        return {
            "isSynced": True,
        }
