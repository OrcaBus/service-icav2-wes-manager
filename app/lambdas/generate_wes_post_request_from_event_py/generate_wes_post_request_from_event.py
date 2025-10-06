#!/usr/bin/env python3

"""
Generate a WES POST request from a WES event.
"""

# Standard library imports
from requests import HTTPError
import logging


# Layer imports
from orcabus_api_tools.icav2_wes import (
    create_icav2_wes_analysis,
    WESPostRequest
)


def handler(event, context):
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

    try:
        create_icav2_wes_analysis(
            **wes_post_request
        )
    except HTTPError as e:
        logging.error(f"Request '{wes_post_request}' failed with error: {e}")
        raise e
