#!/usr/bin/env python3

"""
Given an analysis id, find the analysis id in the database and update the status on the ICAv2 wes api.
"""
# Standard imports
from tempfile import NamedTemporaryFile
from typing import Dict
from urllib.parse import urlunparse
import typing
import boto3
from os import environ
import logging
from datetime import datetime, timezone
from pathlib import Path

# Layer imports
from orcabus_api_tools.icav2_wes import (
    get_icav2_wes_analysis_by_name,
    update_icav2_wes_analysis_status
)

if typing.TYPE_CHECKING:
    from mypy_boto3_s3 import S3Client

# Globals
ICAV2_WES_ORCABUS_ID_TAG_NAME = 'icav2_wes_orcabus_id'

# Set up logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)


def handler(event, context) -> Dict:
    """
    Update the status of analysis on the ICAv2 WES API
    :param event:
    :param context:
    :return:
    """

    # Get the name from the event
    name = event.get("name")

    # Get the status from the event
    status = event.get("status")

    # Get the analysis id from the event
    icav2_analysis_id = event.get("icav2AnalysisId")

    # Get the errorMessage and errorType if they are present
    error_type = event.get("errorType")
    error_message = event.get("errorMessage")

    # We don't add the error message to the database, instead if the error message is present, we upload it to S3.
    # And then we add the S3 uri to the database.
    s3_payload_uri = None
    if error_message is not None:
        # Get the current date and upload path
        logger.info("Uploading the error logs to S3")
        now = datetime.now(timezone.utc)
        upload_path = str(
            Path(environ['S3_ANALYSIS_ERROR_LOGS_PREFIX']) /
            f"year={now.year}" /
            f"month={now.month:02d}" /
            f"day={now.day:02d}" /
            f"{icav2_analysis_id}.txt"
        )
        # Save the analysis object to a temporary file
        with (
            NamedTemporaryFile(suffix='.txt') as temp_error_message,
        ):
            # Write the error message to the temp file
            temp_error_message.write(error_message.encode('utf-8'))
            temp_error_message.flush()

            # Upload the analysis json to S3
            s3_client: 'S3Client' = boto3.client('s3')
            s3_client.upload_file(
                Filename=temp_error_message.name,
                Bucket=environ['S3_ANALYSIS_ARTEFACTS_BUCKET_NAME'],
                Key=upload_path
            )

        s3_payload_uri = str(urlunparse((
            's3',
            environ['S3_ANALYSIS_ARTEFACTS_BUCKET_NAME'],
            str(upload_path),
            None, None, None
        )))

    # Get the analysis object
    analysis_object = get_icav2_wes_analysis_by_name(
        analysis_name=name
    )

    # Update the status on the ICAv2 WES API
    update_response = update_icav2_wes_analysis_status(
        # Positional args in snake_case
        icav2_wes_orcabus_id=analysis_object['id'],
        # Keyword (packed) args in camelCase
        status=status,
        icav2AnalysisId=icav2_analysis_id,
        # Error messages
        errorType=error_type,
        errorMessageUri=s3_payload_uri
    )

    # Return the response payload (We don't actually need this, since updating the API generates the event)
    return dict(update_response)
