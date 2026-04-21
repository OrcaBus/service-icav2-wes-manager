#!/usr/bin/env python3

"""
Given a logs uri, find the following files to copy over to the output directory:

* timeline-report.html
* execution-report.html
* dag-report.dot


"""
# Standard imports
from subprocess import run
from tempfile import NamedTemporaryFile
from textwrap import dedent
from typing import List

from libica.openapi.v3 import ProjectData

# Wrapica imports
from wrapica.project_data import (
    convert_uri_to_project_data_obj,
    find_project_data_bulk,
    create_file_with_upload_url,
    create_download_url
)

# Layer imports
from icav2_tools import set_icav2_env_vars

# Globals
# Filenames to look for
FILE_NAMES_LIST = [
    'timeline-report.html',
    'execution-report.html',
    'dag-report.dot'
]

# Globals
POST_DELETION_WAIT_TIME = 5  # seconds


def get_shell_script_template() -> str:
    return dedent(
        """
        #!/usr/bin/env bash

        set -euo pipefail

        curl --location \
         "__DOWNLOAD_PRESIGNED_URL__" | \
        curl --location \
          --request PUT \
          --header 'Content-Type: application/octet-stream' \
          --data-binary "@-" \
          "__UPLOAD_PRESIGNED_URL__"
        """
    )


def generate_shell_script(
        source_file_download_url: str,
        destination_file_upload_url: str,
):
    # Create a temp file
    temp_file_path = NamedTemporaryFile(
        delete=False,
        suffix=".sh"
    ).name

    # Write the shell script to the temp file
    with open(temp_file_path, "w") as temp_file_h:
        temp_file_h.write(
            get_shell_script_template().replace(
                "__DOWNLOAD_PRESIGNED_URL__", source_file_download_url
            ).replace(
                "__UPLOAD_PRESIGNED_URL__", destination_file_upload_url
            ) + "\n"
        )

    return temp_file_path


def run_shell_script(
        shell_script_path: str,
):
    """
    Run the shell script with the following environment variables set
    :param shell_script_path:
    :return:
    """
    proc = run(
        [
            "bash", shell_script_path
        ],
        capture_output=True
    )

    if not proc.returncode == 0:
        raise RuntimeError(
            f"Failed to run shell script {shell_script_path} with return code {proc.returncode}. "
            f"Stdout was {proc.stdout.decode()}"
            f"Stderr was {proc.stderr.decode()}"
        )

    return


def handler(event, context):
    """
    Get nextflow files from logs uri

    :param event:
    :param context:
    :return:
    """
    # Set the icav2 env vars
    set_icav2_env_vars()

    # Get the logs uri and the output uri
    logs_uri = event.get("logsUri")
    output_uri = event.get("outputUri")

    logs_folder = convert_uri_to_project_data_obj(
        logs_uri
    )
    output_folder = convert_uri_to_project_data_obj(
        output_uri + "pipeline_info/",
        create_data_if_not_found=True
    )

    # Find the timeline-report.html, execution-report.html, and dag-report.dot files
    logs_project_data: List[ProjectData] = list(filter(
        lambda project_data_iter_: project_data_iter_.data.details.name in FILE_NAMES_LIST,
        find_project_data_bulk(
            project_id=logs_folder.project_id,
            parent_folder_id=logs_folder.data.id,
            data_type='FILE'
        )
    ))

    # For each file, copy it to the output folder
    for log_data in logs_project_data:
        # Create the destination file object
        # Get the shell script
        shell_script_path = generate_shell_script(
            source_file_download_url=create_download_url(
                project_id=log_data.project_id,
                file_id=log_data.data.id,
            ),
            destination_file_upload_url=create_file_with_upload_url(
                project_id=output_folder.project_id,
                folder_id=output_folder.data.id,
                file_name=log_data.data.details.name
            )
        )

        # Run the shell script
        run_shell_script(
            shell_script_path=shell_script_path,
        )

    return {}
