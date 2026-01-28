#!/usr/bin/env python3

"""
Unlock the callback id used when generating a WES post request from the event

https://docs.aws.amazon.com/lambda/latest/api/API_SendDurableExecutionCallbackSuccess.html
"""

# Standard library imports
import boto3
import typing

# Types
if typing.TYPE_CHECKING:
    from mypy_boto3_lambda.client import LambdaClient


def get_lambda_client() -> 'LambdaClient':
    return boto3.client('lambda')


def handler(event, context):
    """
    Given a library callback id, unlock it
    :param event:
    :param context:
    :return:
    """

    lambda_client = get_lambda_client()

    try:
        lambda_client.send_durable_execution_callback_success(
            CallbackId=event['callbackId'],
            Result="SUCCESS"
        )
    except lambda_client.exceptions.InvalidParameterValueException as e:
        raise ValueError(f"Invalid callback id: {event['callbackId']}") from e
