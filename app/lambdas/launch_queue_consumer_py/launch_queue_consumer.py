#!/usr/bin/env python3

"""
Launch Queue Consumer Lambda.

This Lambda consumes messages from the Launch_Analysis_Queue (SQS) and invokes
the Launch_Analysis_SFN with the analysis payload plus its own durable execution
callback token. It holds its concurrency slot via the wait_for_callback pattern
until the SFN completes and unlocks the token, enforcing rate-limiting on ICA API requests.

Behavior:
1. Parse SQS record body → extract id, name, inputs, engineParameters, tags
2. Validate required keys; if malformed → log error, delete message, complete successfully
3. Start Launch_Analysis_SFN execution with payload + own callback token
4. Wait for callback (max 15 min timeout)
5. On SFN invocation failure → log error, delete message from queue, complete successfully
"""

# Standard library imports
import json
import logging
from os import environ

import boto3

# Durable execution SDK imports
from aws_durable_execution_sdk_python import (
    DurableContext,
    durable_execution,
)
from aws_durable_execution_sdk_python.config import (
    Duration,
    WaitForCallbackConfig,
)
from aws_durable_execution_sdk_python.retries import create_retry_strategy
from aws_durable_execution_sdk_python.types import WaitForCallbackContext

# Environment variables
LAUNCH_ANALYSIS_SFN_ARN_ENV_VAR = "LAUNCH_ANALYSIS_SFN_ARN"

# Logger
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Required keys in the SQS message body
REQUIRED_MESSAGE_KEYS = ["id", "name", "inputs", "engineParameters", "tags"]


def get_sfn_client():
    """Get the Step Functions client."""
    return boto3.client("stepfunctions")


def get_sqs_client():
    """Get the SQS client."""
    return boto3.client("sqs")


def get_queue_url_from_event_source_arn(event_source_arn: str) -> str:
    """
    Derive the queue URL from the event source ARN.

    ARN format: arn:aws:sqs:<region>:<account-id>:<queue-name>
    URL format: https://sqs.<region>.amazonaws.com/<account-id>/<queue-name>
    """
    # Parse the ARN
    arn_parts = event_source_arn.split(":")
    region = arn_parts[3]
    account_id = arn_parts[4]
    queue_name = arn_parts[5]
    return f"https://sqs.{region}.amazonaws.com/{account_id}/{queue_name}"


def delete_message_from_queue(queue_url: str, receipt_handle: str) -> None:
    """Delete a message from the SQS queue."""
    sqs_client = get_sqs_client()
    sqs_client.delete_message(
        QueueUrl=queue_url,
        ReceiptHandle=receipt_handle,
    )


@durable_execution
def handler(event, context: DurableContext):
    """
    Lambda handler for the Launch Queue Consumer.

    Processes SQS messages from the Launch_Analysis_Queue:
    - Extracts analysis payload from the message body
    - Starts the Launch_Analysis_SFN with the payload and its own callback token
    - Waits for the SFN to unlock the callback token before completing

    :param event: SQS event containing Records
    :param context: DurableContext from the durable execution SDK
    """
    launch_analysis_sfn_arn = environ[LAUNCH_ANALYSIS_SFN_ARN_ENV_VAR]

    for record in event.get("Records", []):
        receipt_handle = record.get("receiptHandle")
        event_source_arn = record.get("eventSourceARN")
        queue_url = get_queue_url_from_event_source_arn(event_source_arn)

        # Parse the message body
        try:
            record_body = json.loads(record.get("body", "{}"))
        except (json.JSONDecodeError, TypeError) as e:
            context.logger.error(
                f"Malformed message body, cannot parse JSON: {e}"
            )
            delete_message_from_queue(queue_url, receipt_handle)
            continue

        # Validate required keys
        missing_keys = [
            key for key in REQUIRED_MESSAGE_KEYS if key not in record_body
        ]
        if missing_keys:
            context.logger.error(
                f"Malformed message: missing required keys {missing_keys}. "
                f"Deleting message to prevent poison pill."
            )
            delete_message_from_queue(queue_url, receipt_handle)
            continue

        # Build the SFN input payload
        sfn_payload = {
            "id": record_body["id"],
            "name": record_body["name"],
            "inputs": record_body["inputs"],
            "engineParameters": record_body["engineParameters"],
            "tags": record_body["tags"],
        }

        def submitter(callback_id: str, callback_context: WaitForCallbackContext):
            """
            Start the Launch_Analysis_SFN execution with the analysis payload
            and the consumer's own callback token.

            On SFN invocation failure: raise so wait_for_callback fails immediately
            and does not hold a concurrency slot.
            """
            # Add the callback token to the SFN input
            execution_input = {
                **sfn_payload,
                "callbackToken": callback_id,
            }

            callback_context.logger.info(
                f"Starting Launch_Analysis_SFN execution for analysis '{sfn_payload['id']}' "
                f"with name '{sfn_payload['name']}'"
            )

            sfn_client = get_sfn_client()
            sfn_client.start_execution(
                stateMachineArn=launch_analysis_sfn_arn,
                input=json.dumps(execution_input),
            )

        # Wait for the callback to be unlocked by the Launch_Analysis_SFN
        # The SFN will invoke the unlock_callback_id Lambda with our token
        # upon completion (both success and failure paths)
        try:
            context.wait_for_callback(
                submitter=submitter,
                name=None,
                config=WaitForCallbackConfig(
                    timeout=Duration.from_minutes(15),
                    retry_strategy=create_retry_strategy(
                        config=None
                    ),
                ),
            )
        except Exception as e:
            context.logger.error(
                f"wait_for_callback failed for analysis '{sfn_payload['id']}': {e}. "
                f"Deleting message from queue to prevent retry loop."
            )
            delete_message_from_queue(queue_url, receipt_handle)
