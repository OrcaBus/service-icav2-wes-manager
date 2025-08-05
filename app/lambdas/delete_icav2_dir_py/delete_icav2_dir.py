#!/usr/bin/env python3

"""
Delete a directory on ICAv2
"""

# Standard library imports
import logging

# Wrapica imports
from wrapica.project_data import (
    coerce_data_id_or_uri_to_project_data_obj,
    delete_project_data
)
from wrapica.utils.globals import FOLDER_DATA_TYPE

# Layer imports
from icav2_tools import set_icav2_env_vars


def handler(event, context):
    """
    Lambda function to get the actual ica logs directory
    :param event:
    :param context:
    :return:
    """

    # Set the environment variables for icav2
    set_icav2_env_vars()

    # Get the project id + analysis id from the event payload
    directory_uri = event.get('directoryUri')

    # Get the analysis object
    try:
        directory_obj = coerce_data_id_or_uri_to_project_data_obj(directory_uri)
    except (NotADirectoryError, FileNotFoundError, ValueError) as e:
        logging.error("Could not get directory object from URI: %s", directory_uri)
        raise e

    # Get the project data object, will fail if this doesn't exist
    if not directory_obj.data.details.data_type == FOLDER_DATA_TYPE:
        logging.error("Not a folder")
        raise ValueError("Provided URI does not point to a folder")

    delete_project_data(
        project_id=directory_obj.project_id,
        data_id=directory_obj.data.id
    )

    return {
        "statusCode": 200,
    }
