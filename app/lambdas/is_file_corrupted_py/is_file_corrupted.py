#!/usr/bin/env python3

"""
Is a text file corrupted?

We perform the following checks:

1. If the file endswith .gz, we just check if the gzip can complete
2. If the file is a json, we actually just see if the json can load,
   json files don't necessarily have a new line ending
3. If the file is anything else, we check if the last char is a newline char

If the file is corrupted we return with the s3 uri with the key corruptedS3Uri
"""
# Standard imports
from json import JSONDecodeError
from tempfile import NamedTemporaryFile
import requests
from gzip import decompress, BadGzipFile
import json

# Layer imports
from orcabus_api_tools.filemanager import (
    get_presigned_url_from_ingest_id,
    get_file_object_from_ingest_id, get_s3_uri_from_ingest_id
)
from orcabus_api_tools.filemanager.models import FileObject

def handler(event, context):
    """
    Given an ingest id, this function performs the following steps:
    """
    # Get inputs
    ingest_id = event.get("ingestId")

    # Get the file object
    file_object: FileObject = get_file_object_from_ingest_id(ingest_id)

    # Get the file object
    presigned_url = get_presigned_url_from_ingest_id(ingest_id)

    # Download the file
    local_file_obj = NamedTemporaryFile()
    with open(local_file_obj.name, 'w') as tmp_h:
        if file_object["key"].endswith(".gz"):
            try:
                tmp_h.write(
                    decompress(
                        requests.get(
                            presigned_url
                        ).content
                    ).decode()
                )
            except BadGzipFile:
                return {
                    "corruptedS3Uri": get_s3_uri_from_ingest_id(ingest_id)
                }
        else:
            tmp_h.write(
                requests.get(
                    presigned_url
                ).text
            )

    # If the file is a JSON file, we try to load it
    if (
            file_object["key"].endswith(".json.gz") or
            file_object["key"].endswith("json")
    ):
        with open(local_file_obj.name, 'r') as json_h:
            try:
                json.load(json_h)
            except JSONDecodeError:
                return {
                    "corruptedS3Uri": get_s3_uri_from_ingest_id(ingest_id)
                }

    # Check if the file's last file character is a new line
    with open(local_file_obj.name, 'r') as file_h:
        file_str = file_h.read()
        if not file_str.endswith("\n"):
            return {
                "corruptedS3Uri": get_s3_uri_from_ingest_id(ingest_id)
            }

    return None
