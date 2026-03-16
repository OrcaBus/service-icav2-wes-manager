#!/usr/bin/env python3

"""
Given an ingest id, this function performs the following steps:

1. Queries the file object associated with the ingest id
2. Checks if the file is a BAM file by looking at the file extension

3. Returns the json payload 'isBamFile' with a boolean value indicating whether the file is a BAM file or not.
"""

# Standard imports
from typing import Dict

# Layer imports
from orcabus_api_tools.filemanager import get_file_object_from_ingest_id
from orcabus_api_tools.filemanager.models import FileObject

# Globals
BAM_SUFFIX = ".bam"


def handler(event, context) -> Dict[str, bool]:
    """
    Check if we have a bam file from an ingest id
    """

    # Get inputs
    file_object: FileObject = get_file_object_from_ingest_id(event.get("ingestId"))

    return {
        "isBamFile": file_object["key"].endswith(BAM_SUFFIX)
    }
