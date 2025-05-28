#!/usr/bin/env python3

"""
Given the analysis object, find where ICAv2 has actually put the logs
(since we can't actually specify this while using the analysis output mapping),

We will use this to then copy the logs to the correct location (and delete the old ones).

Logs are placed in the top directory of the project under the following structure:

/<analysis-user-reference>-<analysis-id>/ica_logs/
"""
from pathlib import Path

from wrapica.enums import DataType
from wrapica.project_analysis import (
    get_analysis_obj_from_analysis_id,
)
from wrapica.project_data import (
    get_project_data_obj_from_project_id_and_path,
    convert_project_data_obj_to_uri
)
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
    project_id = event.get('projectId')
    analysis_id = event.get('analysisId')

    # Get the analysis object
    analysis_obj = get_analysis_obj_from_analysis_id(
        project_id=project_id,
        analysis_id=analysis_id
    )

    # Get the project data object, will fail if this doesn't exist
    ica_logs_folder_object = get_project_data_obj_from_project_id_and_path(
        project_id=project_id,
        data_path=Path("/") / f"{analysis_obj.user_reference}-{analysis_obj.id}" / 'ica_logs',
        data_type=DataType.FOLDER
    )

    return {
        "icaLogsDirUri": convert_project_data_obj_to_uri(ica_logs_folder_object)
    }
