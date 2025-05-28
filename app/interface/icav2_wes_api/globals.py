#!/usr/bin/env python3

import re
from enum import Enum
from os import environ

import typing

if typing.TYPE_CHECKING:
    from .models.analysis import Icav2WesAnalysisPatch

# Add context prefix - ICAv2 WES Analysis
ICAV2_WES_ANALYSIS_PREFIX = "iwa"  # ICAv2 WES Analysis

# https://regex101.com/r/zJRC62/1
ORCABUS_ULID_REGEX_MATCH = re.compile(r'^[a-z0-9]{3}\.[A-Z0-9]{26}$')

# Validate pydantic fields
UUID4_REGEX_MATCH_STR = r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'
URI_MATCH_STR = r'^(?:s3|icav2)://[^\s]+$'

# Envs
EVENT_BUS_NAME_ENV_VAR = "EVENT_BUS_NAME"
EVENT_SOURCE_ENV_VAR = "EVENT_SOURCE"
EVENT_DETAIL_TYPE_ANALYSIS_STATE_CHANGE_ENV_VAR = "EVENT_DETAIL_TYPE_ANALYSIS_STATE_CHANGE"

DYNAMODB_ICAV2_WES_ANALYSIS_TABLE_NAME_ENV_VAR = "DYNAMODB_ICAV2_WES_ANALYSIS_TABLE_NAME"
DYNAMODB_HOST_ENV_VAR = "DYNAMODB_HOST"

# SFN Env vars
ICAV2_WES_LAUNCH_STATE_MACHINE_ARN_ENV_VAR = "ICAV2_WES_LAUNCH_STATE_MACHINE_ARN"
ICAV2_WES_ABORT_MACHINE_ARN_ENV_VAR = "ICAV2_WES_ABORT_STATE_MACHINE_ARN"


# Event enums
class AnalysisEventDetailTypeEnum(Enum):
    STATE_CHANGE = environ[EVENT_DETAIL_TYPE_ANALYSIS_STATE_CHANGE_ENV_VAR]


def get_default_job_patch_entry() -> 'Icav2WesAnalysisPatch':
    from .models.analysis import Icav2WesAnalysisPatch
    return Icav2WesAnalysisPatch(**dict({"status": 'SUBMITTED'}))
