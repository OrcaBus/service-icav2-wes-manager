#!/usr/bin/env python3

"""
Generate a WES POST request from a WES event.
"""

# Standard library imports
import json
from os import environ
import boto3
import typing
from datetime import datetime

# Durable context imports
from aws_durable_execution_sdk_python import (
    DurableContext,
    durable_execution
)
from aws_durable_execution_sdk_python.config import (
    Duration, WaitForCallbackConfig
)
from aws_durable_execution_sdk_python.retries import create_retry_strategy
from aws_durable_execution_sdk_python.types import WaitForCallbackContext

# Type hints
if typing.TYPE_CHECKING:
    from mypy_boto3_stepfunctions.client import SFNClient
    from mypy_boto3_dynamodb.client import DynamoDBClient


# Globals
CALLBACK_DATABASE_NAME_ENV_VAR = "CALLBACK_DATABASE_NAME"
HANDLE_ICA_ANALYSIS_STATE_CHANGE_SFN_ARN_ENV_VAR = "HANDLE_ICA_ANALYSIS_STATE_CHANGE_SFN_ARN"
SECONDS_PER_DAY = (60 * 60 * 24)  # 60 seconds per min * 60 minutes per hour * 24 hours per day

# Helper functions
def get_dynamodb_client() -> 'DynamoDBClient':
    return boto3.client('dynamodb')


def get_sfn_client() -> 'SFNClient':
    return boto3.client('stepfunctions')


# Durable step to handle scaling
def handle_ica_execution(
        icav2_wes_orcabus_id: str,
        status: str,
        icav2_analysis_id: str,
        name: str,
        error_message: str,
        message_receipt_handle_token: str,
        context: DurableContext
):
    def submitter(callback_id: str, callback_context: WaitForCallbackContext):
        """
        Write callback to dynamodb and then start the execution
        """
        callback_context.logger.info("Writing callback id to dynamodb")
        get_dynamodb_client().put_item(
            Item={
                "id": {
                    "S": icav2_wes_orcabus_id,
                },
                "id_type": {
                    "S": status
                },
                "callback_id": {
                    "S": callback_id
                },
                "ttl": {
                    # Add 24 hours to current epoch timestamp
                    "N": str(int(datetime.now().timestamp()) + SECONDS_PER_DAY)
                }
            },
            TableName=environ[CALLBACK_DATABASE_NAME_ENV_VAR]
        )

        # Step 3: Launch the step function (asynchronously)
        callback_context.logger.info("Start sfn execution")
        execution = get_sfn_client().start_execution(
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
        callback_context.logger.info(f"Running sfn execution {execution['executionArn']}")

    # Wait here for the callback to be invoked by the step function
    context.wait_for_callback(
        submitter=submitter,
        name=None,
        config=WaitForCallbackConfig(
            timeout=Duration.from_minutes(60),
            retry_strategy=create_retry_strategy(
                config=None
            )
        ),
    )


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

        # Get the wes orcabus id
        try:
            icav2_wes_orcabus_id = (
                next(filter(
                    lambda technical_tag_iter_: technical_tag_iter_.startswith("icav2_wes_orcabus_id="),
                    payload.get("tags", {}).get("technicalTags", [])
                ))
            ).split("=")[-1]
        except StopIteration:
            raise ValueError("Missing icav2 wes orcabus id in technical tags")

        # Start handle ica execution with a callback step
        handle_ica_execution(
            icav2_wes_orcabus_id=icav2_wes_orcabus_id,
            status = payload.get("status"),
            icav2_analysis_id = payload.get("id"),
            name = payload.get("userReference"),
            error_message = payload.get("summary"),
            message_receipt_handle_token = record.get("receiptHandle"),
            context=context,
        )
