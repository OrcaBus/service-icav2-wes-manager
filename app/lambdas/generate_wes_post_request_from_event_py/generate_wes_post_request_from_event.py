#!/usr/bin/env python3

"""
Generate a WES POST request from a WES event.
"""

# Standard library imports
import json

from aws_durable_execution_sdk_python.retries import create_retry_strategy
from aws_durable_execution_sdk_python.types import WaitForCallbackContext
from requests import HTTPError
from datetime import datetime, UTC
from os import environ
import boto3
import typing
from typing import Dict, Any, Optional

# Durable context imports
from aws_durable_execution_sdk_python import (
    DurableContext,
    durable_execution, StepContext, durable_step
)
from aws_durable_execution_sdk_python.config import (
    Duration, WaitForCallbackConfig
)

# Layer imports
from orcabus_api_tools.icav2_wes import (
    create_icav2_wes_analysis,
    WESPostRequest, get_icav2_wes_analysis_by_name,
)
from orcabus_api_tools.icav2_wes.models import WESResponse

if typing.TYPE_CHECKING:
    from mypy_boto3_dynamodb.client import DynamoDBClient

# Globals
CALLBACK_DATABASE_NAME_ENV_VAR = "CALLBACK_DATABASE_NAME"
SECONDS_PER_DAY = (60 * 60 * 24)  # 60 seconds per min * 60 minutes per hour * 24 hours per day


def get_dynamodb_client() -> 'DynamoDBClient':
    return boto3.client('dynamodb')


@durable_step
def create_icav2_wes_analysis_durable_step(ctx: StepContext, record_body: Dict[str, Any]) -> Optional[WESResponse]:
    # Create the WES POST request
    wes_post_request: WESPostRequest = {
        "name": record_body['name'],
        "inputs": record_body['inputs'],
        "engineParameters": record_body['engineParameters'],
        "tags": record_body['tags']
    }

    # Check if we haven't already tried to create this analysis
    try:
        get_icav2_wes_analysis_by_name(record_body['name'])
    except ValueError:
        pass
    else:
        ctx.logger.info(f"WES analysis with name '{record_body['name']}' already exists. Skipping creation.")
        return None

    # Get the ICAv2 WES analysis response
    try:
        icav2_wes_analysis_response = create_icav2_wes_analysis(
            **wes_post_request
        )
    except HTTPError as e:
        ctx.logger.error(f"Request '{wes_post_request}' failed with error: {e}")
        raise e

    return icav2_wes_analysis_response


def map_and_wait(icav2_wes_analysis_id: str, context: DurableContext):
    def submitter(callback_id: str, callback_context: WaitForCallbackContext):
        # Step 2: Add the callback to the DynamoDb database
        callback_context.logger.info("WES analysis submitted, mapping WES Id to callback ID so we can be unlocked")
        get_dynamodb_client().put_item(
            Item={
                "id": {
                    "S": icav2_wes_analysis_id,
                },
                "id_type": {
                    "S": "LAUNCH_REQUEST"
                },
                "callback_id": {
                    "S": callback_id
                },
                "ttl": {
                    # Add 24 hours to current epoch timestamp
                    "N": str(
                        int(datetime.now(UTC).timestamp()) +
                        SECONDS_PER_DAY
                    )
                }
            },
            TableName=environ[CALLBACK_DATABASE_NAME_ENV_VAR]
        )

    # Step 3: Wait here for the callback to be invoked
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


@durable_execution
def handler(event, context: DurableContext):
    """
    Expect the following inputs from the event object:
      * inputs
      * engineParameters
      * tags

    :param event:
    :param context:
    :return:
    """

    # Not sure what this will look like from the sqs event source
    for record in event.get("Records", []):
        record_body = json.loads(record.get("body", {}))
        # Check if the event contains the required keys
        required_keys = ['name', 'inputs', 'engineParameters', 'tags']
        for key in required_keys:
            if key not in record_body:
                raise ValueError(f"Missing required key: {key}")

        # 1. Submit the external request
        icav2_wes_analysis_response = context.step(create_icav2_wes_analysis_durable_step(record_body))

        if icav2_wes_analysis_response is None:
            continue

        # 2. Register in db and wait for callback
        map_and_wait(icav2_wes_analysis_response['id'], context)
