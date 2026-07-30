#!/usr/bin/env python3

"""
Generate a WES POST request from a WES event.

This Lambda consumes WES request events from the WES_Request_Event_Queue,
calls the Create_Job_API passing its durable execution callback token in the request body,
and waits for the callback to be unlocked (max 15 min).

The callback token is passed directly to the API - no DynamoDB registration needed.
The API invokes the Unlock_Callback_SFN with the token after setting status to SUBMITTED.
"""

# Standard library imports
import json

from aws_durable_execution_sdk_python.retries import create_retry_strategy
from aws_durable_execution_sdk_python.types import WaitForCallbackContext
from requests import HTTPError

# Durable context imports
from aws_durable_execution_sdk_python import (
    DurableContext,
    durable_execution,
)
from aws_durable_execution_sdk_python.config import (
    Duration, WaitForCallbackConfig
)

# Layer imports
from orcabus_api_tools.icav2_wes import (
    icav2_wes_post_request,
    get_icav2_wes_analysis_by_name,
)
from orcabus_api_tools.icav2_wes.globals import ANALYSES_ENDPOINT


@durable_execution
def handler(event, context: DurableContext):
    """
    Expect the following inputs from the event object (SQS record body):
      * name
      * inputs
      * engineParameters
      * tags

    The handler uses wait_for_callback with a submitter that:
    1. Calls create_icav2_wes_analysis() passing callbackToken in the request body
    2. The API invokes the unlock chain on its side
    3. Waits for callback to be unlocked (max 15 min)

    On API call failure, raises exception so the message stays in queue for retry.

    :param event:
    :param context:
    :return:
    """

    # Process each SQS record
    for record in event.get("Records", []):
        record_body = json.loads(record.get("body", {}))
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
            context.logger.info(
                f"WES analysis with name '{record_body['name']}' already exists. Skipping creation."
            )
            continue

        def submitter(callback_id: str, callback_context: WaitForCallbackContext):
            """
            Submit the WES analysis creation request with the callback token.
            The API will invoke the Unlock_Callback_SFN with this token after
            setting the analysis status to SUBMITTED.
            """
            # Build the request body including the callbackToken
            wes_post_request_body = {
                "name": record_body['name'],
                "inputs": record_body['inputs'],
                "engineParameters": record_body['engineParameters'],
                "tags": record_body['tags'],
                "callbackToken": callback_id,
            }

            callback_context.logger.info(
                f"Submitting WES analysis '{record_body['name']}' with callback token"
            )

            # Call the Create_Job_API with callbackToken in the request body
            # Using icav2_wes_post_request directly since the helper function
            # doesn't support the callbackToken field in its TypedDict validation
            try:
                icav2_wes_post_request(
                    endpoint=ANALYSES_ENDPOINT,
                    json_data=wes_post_request_body,
                )
            except HTTPError as e:
                callback_context.logger.error(
                    f"API call failed for '{record_body['name']}': {e}"
                )
                # Raise exception so message stays in queue for retry
                raise e

        # Wait for the callback to be unlocked (max 15 min)
        # The API will invoke the Unlock_Callback_SFN which sends the task success signal
        context.wait_for_callback(
            submitter=submitter,
            name=None,
            config=WaitForCallbackConfig(
                timeout=Duration.from_minutes(15),
                retry_strategy=create_retry_strategy(
                    config=None
                )
            ),
        )
