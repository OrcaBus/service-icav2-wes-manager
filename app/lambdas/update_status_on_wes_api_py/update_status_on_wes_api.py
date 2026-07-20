#!/usr/bin/env python3

"""
Given an orcabus id, update the status on the ICAv2 wes api.
Uses the icav2WesOrcabusId directly for hash key lookup, avoiding GSI queries.
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
    update_icav2_wes_analysis_status
)

if typing.TYPE_CHECKING:
    from mypy_boto3_s3 import S3Client

# Set up logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Globals
S3_ANALYSIS_ERROR_LOGS_PREFIX_ENV_VAR = 'S3_ANALYSIS_ERROR_LOGS_PREFIX'
S3_ANALYSIS_ARTEFACTS_BUCKET_NAME_ENV_VAR = 'S3_ANALYSIS_ARTEFACTS_BUCKET_NAME'


def handler(event, context) -> Dict:
    """
    Update the status of analysis on the ICAv2 WES API.
    Uses icav2WesOrcabusId for direct DynamoDB hash key lookup.
    :param event:
    :param context:
    :return:
    """

    # Get the orcabus id from the event (direct hash key — no GSI query needed)
    icav2_wes_orcabus_id = event.get("icav2WesOrcabusId")

    if not icav2_wes_orcabus_id:
        raise ValueError("No icav2WesOrcabusId provided")

    # Get the status from the event
    status = event.get("status")

    # Get the analysis id from the event
    icav2_analysis_id = event.get("icav2AnalysisId")

    # Get the steps execution arn if present
    steps_execution_arn = event.get("stepsLaunchExecutionArn")

    # Get the errorMessage and errorType if they are present
    error_type = event.get("errorType")
    error_message = event.get("errorMessage")

    # We don't add the error message to the database, instead if the error message is present, we upload it to S3.
    # And then we add the S3 uri to the database.
    s3_payload_uri = None
    if error_message is not None:
        # Use icav2_analysis_id for the error log path, fall back to orcabus id
        error_log_id = icav2_analysis_id if icav2_analysis_id is not None else icav2_wes_orcabus_id
        # Get the current date and upload path
        logger.info("Uploading the error logs to S3")
        now = datetime.now(timezone.utc)
        upload_path = str(
            Path(environ[S3_ANALYSIS_ERROR_LOGS_PREFIX_ENV_VAR]) /
            f"year={now.year}" /
            f"month={now.month:02d}" /
            f"day={now.day:02d}" /
            f"{error_log_id}.txt"
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
                Bucket=environ[S3_ANALYSIS_ARTEFACTS_BUCKET_NAME_ENV_VAR],
                Key=upload_path
            )

        s3_payload_uri = str(urlunparse((
            's3',
            environ[S3_ANALYSIS_ARTEFACTS_BUCKET_NAME_ENV_VAR],
            str(upload_path),
            None, None, None
        )))

    # Update the status on the ICAv2 WES API directly using the orcabus id
    update_response = update_icav2_wes_analysis_status(
        icav2_wes_orcabus_id,
        **dict(filter(
            lambda kv_iter_: kv_iter_[1] is not None,
            {
                # Keyword (packed) args in camelCase
                "status": status,
                "icav2AnalysisId": icav2_analysis_id,
                # Steps execution arn (not yet implemented)
                "stepsLaunchExecutionArn": steps_execution_arn,
                # Error messages
                "errorType": error_type,
                "errorMessageUri": s3_payload_uri,
            }.items()
        ))
    )

    # Return the response payload (We don't actually need this, since updating the API generates the event)
    return dict(update_response)
