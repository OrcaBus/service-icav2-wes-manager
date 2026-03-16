#!/usr/bin/env python3

"""
Generate a WES POST request from a WES event.
"""

# Standard library imports
import json
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


if typing.TYPE_CHECKING:
    from mypy_boto3_stepfunctions.client import SFNClient
    from mypy_boto3_dynamodb.client import DynamoDBClient

# Globals
CALLBACK_DATABASE_NAME_ENV_VAR = "CALLBACK_DATABASE_NAME"
HANDLE_ICA_ANALYSIS_STATE_CHANGE_SFN_ARN_ENV_VAR = "HANDLE_ICA_ANALYSIS_STATE_CHANGE_SFN_ARN"


# Helper functions
def get_dynamodb_client() -> 'DynamoDBClient':
    return boto3.client('dynamodb')


def get_sfn_client() -> 'SFNClient':
    return boto3.client('stepfunctions')


# Durable Lambda Handler
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
        # Check if the event contains the required keys
        record_body = json.loads(record.get("body", {}))
        required_keys = ['payload']
        for key in required_keys:
            if key not in record_body:
                raise ValueError(f"Missing required key: {key}")

        # Collect the payload
        payload = record_body.get("payload")

        # Get the following attributes
        icav2_analysis_id = payload.get("id")
        status = payload.get("status")
        name = payload.get("userReference")
        error_message = payload.get("summary")
        icav2_wes_orcabus_id = (
            next(filter(
                lambda technical_tag_iter_: technical_tag_iter_.startswith("icav2_wes_orcabus_id="),
                payload.get("tags", {}).get("technicalTags", [])
            ))
        ).split("=")[-1]
        message_receipt_handle_token = record.get("receiptHandle")

        # Run the durable execution callback configuration
        # Step 1: Create the callback
        callback = context.create_callback(
            name="WESRequestCallback",
            config=CallbackConfig(timeout=Duration.from_minutes(60)),
        )

        # Step 2: Add the callback to the DynamoDb database
        get_dynamodb_client().put_item(
            Item={
                "id": {
                    "S": icav2_wes_orcabus_id,
                },
                "id_type": {
                    "S": status
                },
                "callback_id": {
                    "S": callback.callback_id
                },
            },
            TableName=environ[CALLBACK_DATABASE_NAME_ENV_VAR]
        )

        # Step 3: Launch the step function (asynchronously)
        get_sfn_client().start_execution(
            stateMachineArn=environ[HANDLE_ICA_ANALYSIS_STATE_CHANGE_SFN_ARN_ENV_VAR],
            input=json.dumps(
                {
                    "icav2AnalysisId": icav2_analysis_id,
                    "status": status,
                    "name": name,
                    "errorMessage": error_message,
                    "icav2WesOrcabusId": icav2_wes_orcabus_id,
                    "messageReceiptHandleToken": message_receipt_handle_token
                },
                separators=(",", ":")
            )
        )

        # Step 4: Wait here for the callback to be invoked
        callback.result()
