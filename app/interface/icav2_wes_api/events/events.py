#!/usr/bin/env python3
import json
import typing
from os import environ

import boto3

from ..globals import (
    EVENT_BUS_NAME_ENV_VAR,
    EVENT_SOURCE_ENV_VAR,
    AnalysisEventDetailTypeEnum
)
from ..models.analysis import Icav2WesAnalysisResponse

if typing.TYPE_CHECKING:
    from mypy_boto3_events import EventBridgeClient
    from mypy_boto3_events.type_defs import PutEventsRequestEntryTypeDef


def get_event_client() -> 'EventBridgeClient':
    """
    Get the event client for AWS EventBridge.
    """
    return boto3.client('events')


def put_event(event_detail_type, event_detail):
    # DEBUG
    if environ.get(EVENT_BUS_NAME_ENV_VAR) == 'local':
        return

    event_obj: PutEventsRequestEntryTypeDef = {
        'EventBusName': environ[EVENT_BUS_NAME_ENV_VAR],
        'Source': environ[EVENT_SOURCE_ENV_VAR],
        'DetailType': event_detail_type,
        'Detail': json.dumps(event_detail),
    }
    get_event_client().put_events(
        Entries=[
            event_obj,
        ]
    )


# Update events
def put_icav2_wes_analysis_update_event(icav2_wes_analysis_response_object: Icav2WesAnalysisResponse):
    """
    Put a update event to the event bus.
    """
    put_event(AnalysisEventDetailTypeEnum.STATE_CHANGE.value, icav2_wes_analysis_response_object)
