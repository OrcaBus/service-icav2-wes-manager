#!/usr/bin/env python3

"""
Given a portal run id, this function performs the following steps:

* Finds any files using the portal run id as a tag
* Returns all ingest ids
"""

# Standard imports

# Orcabus imports
from orcabus_api_tools.filemanager import list_files_from_portal_run_id

def handler(event, context):
    """
    Given a portal run id, return all ingest ids
    """

    # Set inputs
    portal_run_id = event.get("portalRunId")

    return {
        "ingestIdList": list(map(
            lambda file_object_iter_: file_object_iter_.get("ingestId"),
            list_files_from_portal_run_id(portal_run_id)
        ))
    }
