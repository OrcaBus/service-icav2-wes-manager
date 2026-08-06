#!/usr/bin/env python3

"""
Generate a WES POST request from a WES event.

This Lambda consumes WES request events from the WES_Request_Event_Queue,
calls the Create_Job_API, and completes. The SQS event source mapping is configured
with maxConcurrency=1 to prevent overloading the API server.

On success, the Lambda completes normally (SQS message is deleted).
On failure, the Lambda raises an exception (SQS message stays for retry).
"""

# Standard library imports
import json
import logging

from requests import HTTPError

# Layer imports
from orcabus_api_tools.icav2_wes import (
    icav2_wes_post_request,
    get_icav2_wes_analysis_by_name,
)
from orcabus_api_tools.icav2_wes.globals import ANALYSES_ENDPOINT

# Logger
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def handler(event, context):
    """
    Expect the following inputs from the event object (SQS record body):
      * name
      * inputs
      * engineParameters
      * tags

    The handler:
    1. Parses the SQS record body
    2. Checks idempotency (analysis name doesn't already exist)
    3. Calls the Create_Job_API
    4. On success, completes (message deleted by Lambda service)
    5. On failure, raises (message stays in queue for retry)

    :param event:
    :param context:
    :return:
    """

    # Process each SQS record
    for record in event.get("Records", []):
        record_body = json.loads(record.get("body", "{}"))

        # Check if the event contains the required keys
        required_keys = ['name', 'inputs', 'engineParameters', 'tags']
        for key in required_keys:
            if key not in record_body:
                raise ValueError(f"Missing required key: {key}")

        # Check if we haven't already tried to create this analysis (idempotency)
        try:
            get_icav2_wes_analysis_by_name(record_body['name'])
        except ValueError:
            pass
        else:
            logger.info(
                f"WES analysis with name '{record_body['name']}' already exists. Skipping creation."
            )
            continue

        # Build the request body
        wes_post_request_body = {
            "name": record_body['name'],
            "inputs": record_body['inputs'],
            "engineParameters": record_body['engineParameters'],
            "tags": record_body['tags'],
        }

        logger.info(
            f"Submitting WES analysis '{record_body['name']}'"
        )

        # Call the Create_Job_API
        # On failure, raise so message stays in queue for retry
        try:
            icav2_wes_post_request(
                endpoint=ANALYSES_ENDPOINT,
                json_data=wes_post_request_body,
            )
        except HTTPError as e:
            logger.error(
                f"API call failed for '{record_body['name']}': {e}"
            )
            raise e

        logger.info(
            f"Successfully submitted WES analysis '{record_body['name']}'"
        )
