#!/usr/bin/env python3

"""
Generate a WES POST request from a WES event.
"""

# Standard library imports
import json
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
    WESPostRequest, get_icav2_wes_analysis_by_name
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

    # Not sure what this will look like from the sqs event source
    for record in event.get("Records", []):
        record_body = json.loads(record.get("body", {}))
        # Check if the event contains the required keys
        required_keys = ['name', 'inputs', 'engineParameters', 'tags']
        for key in required_keys:
            if key not in record_body:
                raise ValueError(f"Missing required key: {key}")

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
            logging.info(f"WES analysis with name '{record_body['name']}' already exists. Skipping creation.")
            continue

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
            config=CallbackConfig(timeout=Duration.from_minutes(15)),
        )

        # Step 2: Add the callback to the DynamoDb database
        get_dynamodb_client().put_item(
            Item={
                "id": {
                    "S": icav2_wes_analysis_response['id'],
                },
                "id_type": {
                    "S": "LAUNCH_REQUEST"
                },
                "callback_id": {
                    "S": callback.callback_id
                },
            },
            TableName=environ[CALLBACK_DATABASE_NAME_ENV_VAR]
        )

        # Step 3: Wait here for the callback to be invoked
        callback.result()
