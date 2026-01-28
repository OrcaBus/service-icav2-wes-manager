#!/usr/bin/env python3

"""
Generate a WES POST request from a WES event.
"""
# Standard library imports
from requests import HTTPError
import logging
from os import environ
import boto3
import typing

# Durable context imports
from aws_durable_execution_sdk_python import (
    DurableContext,
    durable_execution
)
from aws_durable_execution_sdk_python.config import (
    CallbackConfig, Duration
)

# Layer imports
from orcabus_api_tools.icav2_wes import (
    create_icav2_wes_analysis,
    WESPostRequest
)

if typing.TYPE_CHECKING:
    from mypy_boto3_dynamodb.client import DynamoDBClient

# Globals
CALLBACK_DATABASE_NAME_ENV_VAR = "CALLBACK_DATABASE_NAME"


def get_dynamodb_client() -> 'DynamoDBClient':
    return boto3.client('dynamodb')


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

    # Check if the event contains the required keys
    required_keys = ['name', 'inputs', 'engineParameters', 'tags']
    for key in required_keys:
        if key not in event:
            raise ValueError(f"Missing required key: {key}")

    # Create the WES POST request
    wes_post_request: WESPostRequest = {
        "name": event['name'],
        "inputs": event['inputs'],
        "engineParameters": event['engineParameters'],
        "tags": event['tags']
    }

    # Get the ICAv2 WES analysis response
    try:
        icav2_wes_analysis_response = create_icav2_wes_analysis(
            **wes_post_request
        )
    except HTTPError as e:
        logging.error(f"Request '{wes_post_request}' failed with error: {e}")
        raise e

    # Run the durable execution callback configuration
    # Step 1: Create the callback
    callback = context.create_callback(
        name="WESRequestCallback",
        config=CallbackConfig(timeout=Duration.from_minutes(30)),
    )

    # Step 2: Add the callback to the DynamoDb database
    get_dynamodb_client().put_item(
        Item={
            "id": icav2_wes_analysis_response['id'],
            "callback_id": callback.callback_id,
        },
        TableName=environ[CALLBACK_DATABASE_NAME_ENV_VAR]
    )

    callback.result()
