#!/usr/bin/env python3

"""
Given a list of ingest ids, this function performs the following steps:

1. Performs a batch query over the ingest ids and returns all file objects
2. Filters the ingest ids to match those that are divisible by 65536
  ( the 64 KB boundary which seems to be causing some issues in ICAv2 )
3. We select files with the following suffixes (and allow for *.gz) as well
bed
cnv
csv
err
html
json
log
maf
pcf
seg
sf
tsv
txt
vcf
xml

We also accept bam files to check as well since we can use samtools validation for these
"""

# Standard Imports
import re
from typing import List, Dict, Union, cast
import math
import logging

# Layer imports
from orcabus_api_tools.filemanager import get_s3_objs_from_ingest_ids_map
from orcabus_api_tools.filemanager.models import FileObject

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
    "vcf",
    "xml",
    # Add bam files
    # Since these are important
    # And we can use tools to check their integrity
    "bam"
]

# noinspection RegExpUnnecessaryNonCapturingGroup
SUFFIX_REGEX_OBJ = re.compile(
    rf".*(?:{"|".join(SUFFIX_LIST)})(?:.gz)?$"
)

# We want files that are a multiple of the block size of 1024
# Since these are the ones most likely to be corrupted
FILESIZE_DENOMINATOR = math.pow(2, 10)  # 1024

# Set logging
logging.basicConfig()
logger = logging.getLogger(__name__)


def handler(event, context):
    """
    Given a list of ingest ids,
    Pull in all objects

    """

    # Get inputs
    ingest_id_list = event.get("ingestIdList")

    # Set outputs
    matched_ingest_id_list = []

    # Set files as objects
    file_objects_dict_list: List[Dict[str, Union[FileObject | str]]] = get_s3_objs_from_ingest_ids_map(
        ingest_ids=ingest_id_list
    )

    # Filter by filesizes
    for file_object_iter_ in file_objects_dict_list:
        # Get file object size
        file_object_size = file_object_iter_.get("fileObject", {}).get("size")

        # Check if file object size to None
        if file_object_size is None:
            logger.warning("Didn't expect to get none for file object size")
            continue

        # Check if file object size is divisible by 65536
        if (
                # Not divisible by 65536, file not of interest
                not divmod(file_object_size, FILESIZE_DENOMINATOR)[-1] == 0 or
                # File empty, also not of interest
                file_object_size == 0
        ):
            continue

        # Check if file key endswith text or text.gz
        file_object_key = file_object_iter_.get("fileObject", {}).get("key")
        if file_object_key is None:
            logger.warning("Didn't expect to get none for file object key")
            continue

        # Check file object key
        if not SUFFIX_REGEX_OBJ.match(cast(str, file_object_key)):
            # Not a file of interest
            continue

        # If we get to here, this is an ingest id of interest
        matched_ingest_id_list.append(
            file_object_iter_['ingestId']
        )

    # Return response
    return {
        "matchingIngestIds": matched_ingest_id_list
    }
