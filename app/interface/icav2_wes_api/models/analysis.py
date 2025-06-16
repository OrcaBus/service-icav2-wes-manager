#!/usr/bin/env python3

"""
Job model, used to for job management
"""

# Standard imports
import typing
from typing import List, Dict, Any
from os import environ
from typing import Optional, Self, ClassVar
import json

from dyntastic import Dyntastic
from fastapi.encoders import jsonable_encoder
from pydantic import Field, BaseModel, model_validator, ConfigDict
from datetime import datetime

from . import AnalysisStatus
from fastapi_tools import QueryPaginatedResponse

# Util imports
from ..utils import (
    to_camel, get_ulid,
    get_icav2_wes_analysis_endpoint_url
)
from ..globals import UUID4_REGEX_MATCH_STR, URI_MATCH_STR, ICAV2_WES_ANALYSIS_PREFIX


class EngineParameters(BaseModel):
    """
    The engine parameters for an ICAv2 WES analysis
    """
    model_config = ConfigDict(
        alias_generator=to_camel,
        validate_by_name=True,
        validate_by_alias=True
    )

    # Must be a valid pipeline id
    pipeline_id: str = Field(
        description="The ICAv2 pipeline id to use for the analysis",
        alias='pipelineId',
        pattern=UUID4_REGEX_MATCH_STR
    )
    # Must be a valid project id
    project_id: str = Field(
        description="The ICAv2 project id to use for the analysis",
        alias='projectId',
        pattern=UUID4_REGEX_MATCH_STR
    )
    # Must be a valid uri
    output_uri: str = Field(
        description="The output uri to use for the analysis, must start with s3:// or icav2://",
        alias='outputUri',
        pattern=URI_MATCH_STR
    )
    # Must be a valid uri
    logs_uri: str = Field(
        description="The logs uri to use for the analysis, must start with s3:// or icav2://",
        alias='logsUri',
        pattern=URI_MATCH_STR
    )


class Icav2WesAnalysisBase(BaseModel):
    name: str
    inputs: Dict[str, Any]
    engine_parameters: EngineParameters
    tags: Dict[str, Any]


class Icav2WesAnalysisOrcabusId(BaseModel):
    # fqr.ABCDEFGHIJKLMNOP
    # BCLConvert Metadata attributes
    id: str = Field(default_factory=lambda: f"{ICAV2_WES_ANALYSIS_PREFIX}.{get_ulid()}")


class Icav2WesAnalysisWithId(Icav2WesAnalysisBase, Icav2WesAnalysisOrcabusId):
    """
    Order class inheritance this way to ensure that the id field is set first
    """
    # We also have the steps execution id as an attribute to add
    status: AnalysisStatus = Field(default='PENDING')
    submission_time: datetime = Field(default_factory=datetime.now)
    steps_launch_execution_arn: Optional[str] = None
    icav2_analysis_id: Optional[str] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None


class Icav2WesAnalysisResponse(Icav2WesAnalysisWithId):
    model_config = ConfigDict(
        alias_generator=to_camel,
        validate_by_name=True,
        validate_by_alias=True,
    )

    # Set the model_dump method response
    if typing.TYPE_CHECKING:
        def model_dump(self, **kwargs) -> Self:
            pass


class Icav2WesAnalysisCreate(Icav2WesAnalysisBase):
    model_config = ConfigDict(
        alias_generator=to_camel,
        validate_by_name=True,
        validate_by_alias=True
    )

    def model_dump(self, **kwargs) -> 'Icav2WesAnalysisResponse':
        return (
            Icav2WesAnalysisResponse(**super().model_dump()).
            model_dump()
        )


class Icav2WesAnalysisPatch(BaseModel):
    icav2AnalysisId: Optional[str] = None
    status: AnalysisStatus


class Icav2WesAnalysisData(Icav2WesAnalysisWithId, Dyntastic):
    """
    The job data object
    """
    __table_name__ = environ['DYNAMODB_ICAV2_WES_ANALYSIS_TABLE_NAME']
    __table_host__ = environ['DYNAMODB_HOST']
    __hash_key__ = "id"

    inputs: str
    tags: str
    engine_parameters: str

    @classmethod
    def from_dict(cls, **kwargs: Dict[str, Any]) -> 'Icav2WesAnalysisData':
        """
        Convert a dictionary to an Icav2WesAnalysisData object
        :param data: The dictionary to convert
        :return: An Icav2WesAnalysisData object
        """
        return cls(
            inputs=json.dumps(jsonable_encoder(kwargs.pop('inputs'))),
            engine_parameters=json.dumps(jsonable_encoder(kwargs.pop('engine_parameters'))),
            tags=json.dumps(jsonable_encoder(kwargs.pop('tags'))),
            **kwargs
        )

    # To Dictionary
    def to_dict(self) -> 'Icav2WesAnalysisResponse':
        """
        Alternative serialization path to return objects by camel case
        :return:
        """
        # Load the inputs, tags and engine parameters from JSON strings
        inputs = json.loads(self.inputs) if self.inputs else {}
        tags = json.loads(self.tags) if self.tags else {}
        engine_parameters = json.loads(self.engine_parameters) if self.engine_parameters else {}

        # Initialise the model dump
        model_dump = self.model_dump(
            by_alias=True,
            exclude_none=True,
            exclude_unset=True
        )

        # Update the model dump with the inputs, tags and engine parameters
        model_dump.update({
            'inputs': inputs,
            'tags': tags,
            'engineParameters': engine_parameters
        })

        return jsonable_encoder(
            Icav2WesAnalysisResponse(
                **model_dump
            ).model_dump(by_alias=True)
        )


class Icav2WesAnalysisQueryPaginatedResponse(QueryPaginatedResponse):
    """
    ICAv2 Analysis Query Response, includes a list of analyses
    """
    url_placeholder: ClassVar[str] = get_icav2_wes_analysis_endpoint_url()
    results: List[Icav2WesAnalysisResponse]

    @classmethod
    def resolve_url_placeholder(cls, **kwargs) -> str:

        # Get the url placeholder
        return cls.url_placeholder.format()
