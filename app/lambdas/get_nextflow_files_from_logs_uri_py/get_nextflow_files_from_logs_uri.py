#!/usr/bin/env python3

"""
Given a logs uri, find the following files to copy over to the output directory:

* timeline-report.html
* execution-report.html
* dag-report.dot


"""
from icav2_tools import set_icav2_env_vars
# Wrapica imports
from wrapica.project_data import (
    convert_uri_to_project_data_obj,
    find_project_data_bulk,
    convert_project_data_obj_to_icav2_uri
)

# Globals
# Filenames to look for
FILE_NAMES_LIST = [
    'timeline-report.html',
    'execution-report.html',
    'dag-report.dot'
]


def handler(event, context):
    """
    Get nextflow files from logs uri

    :param event:
    :param context:
    :return:
    """
    # Set the icav2 env vars
    set_icav2_env_vars()

    # Get the logs uri and project id
    logs_uri = event.get("logsUri")

    logs_folder = convert_uri_to_project_data_obj(
        logs_uri
    )

    # Find the timeline-report.html, execution-report.html, and dag-report.dot files
    project_data = list(filter(
        lambda project_data_iter_: project_data_iter_.data.details.name in FILE_NAMES_LIST,
        find_project_data_bulk(
            project_id=logs_folder.project_id,
            parent_folder_id=logs_folder.data.id,
            data_type='FILE'
        )
    ))

    # Return the files list
    project_data_uris = list(map(
        lambda project_data_iter_: convert_project_data_obj_to_icav2_uri(project_data_iter_),
        project_data
    ))

    return {
        "filesUriList": project_data_uris
    }
