#!/usr/bin/env python3

"""
Given a portal run id, this function performs the following steps:

* Finds any files using the portal run id as a tag
* Filters them to only those that are potentially corrupted:
  - File size is a multiple of 1024 bytes (except bam/vcf files which are always included)
  - File is not empty
  - File matches a known suffix list (text-based formats, vcf, bam)
  - Excludes known false positives (lilac fragments, log files)
* Returns the filtered ingest ids
"""

# Standard imports
import re
import math
import logging
from typing import cast

# Orcabus imports
from orcabus_api_tools.filemanager import list_files_from_portal_run_id

# Globals
SUFFIX_LIST = [
    "bed",
    "cnv",
    "csv",
    "err",
    "html",
    "json",
    "log",
    "maf",
    "pcf",
    "seg",
    "sf",
    "tsv",
    "txt",
    "xml",
    # Add bam/vcf files
    # Since these are important
    # And we can use tools to check their integrity
    "vcf",
    "bam",
]

# noinspection RegExpUnnecessaryNonCapturingGroup
SUFFIX_REGEX_OBJ = re.compile(rf".*(?:{"|".join(SUFFIX_LIST)})(?:.gz)?$")

# We want files that are a multiple of the block size of 1024
# Since these are the ones most likely to be corrupted
FILESIZE_DENOMINATOR = math.pow(2, 10)  # 1024

# Set logging
logging.basicConfig()
logger = logging.getLogger(__name__)


def handler(event, context):
    """
    Given a portal run id, return all ingest ids that match
    the corrupted file filtering criteria.
    """

    # Set inputs
    portal_run_id = event.get("portalRunId")

    # Get all files from the portal run id
    file_objects = list_files_from_portal_run_id(portal_run_id)

    # Set outputs
    matched_ingest_id_list = []

    # Filter by file size and suffix criteria
    for file_object_iter_ in file_objects:
        file_object_size = file_object_iter_.get("size")
        file_object_key = file_object_iter_.get("key", "")
        ingest_id = file_object_iter_.get("ingestId")

        # Check if file object size is None
        if file_object_size is None:
            logger.warning("Didn't expect to get none for file object size")
            continue

        # Check if file object size is divisible by 1024
        if (
            # Not divisible by 1024, file not of interest (unless a vcf / bam file)
            (
                not divmod(file_object_size, FILESIZE_DENOMINATOR)[-1] == 0
                and not (
                    file_object_key.endswith(".vcf.gz") or file_object_key.endswith(".bam")
                )
            )
            or
            # File empty, also not of interest
            file_object_size == 0
            or
            # Known bug for lilac fragments, we ignore these
            file_object_key.endswith(".lilac.hlay.fragments.tsv")
            or
            # And we ignore '/logs' for now too
            "/logs/" in file_object_key
        ):
            continue

        # Check if file key is None
        if file_object_key is None:
            logger.warning("Didn't expect to get none for file object key")
            continue

        # Check file object key matches our suffix list
        if not SUFFIX_REGEX_OBJ.match(cast(str, file_object_key)):
            # Not a file of interest
            continue

        # If we get to here, this is an ingest id of interest
        matched_ingest_id_list.append(ingest_id)

    # Return response
    return {"ingestIdList": matched_ingest_id_list}
