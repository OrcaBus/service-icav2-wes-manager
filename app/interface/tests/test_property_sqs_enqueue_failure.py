#!/usr/bin/env python3
"""
Property 3: SQS enqueue failure prevents SUBMITTED status

For any valid analysis creation request where the SQS enqueue operation fails,
the Create_Job_API SHALL return an error response (HTTP 5xx) and the analysis
record in the database SHALL NOT have status SUBMITTED.

**Validates: Requirements 2.6**

Feature: api-rate-limiting-and-async-callback, Property 3: SQS enqueue failure prevents SUBMITTED status
"""

import uuid
from unittest.mock import patch, MagicMock

import pytest
from botocore.exceptions import ClientError
from hypothesis import given, settings, HealthCheck
from hypothesis import strategies as st
from httpx import AsyncClient, ASGITransport

# Import the FastAPI app (env vars are set by conftest.py)
from handler import app


# --- Hypothesis Strategies ---

uuid_strategy = st.from_regex(
    r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}",
    fullmatch=True
)

uri_strategy = st.from_regex(r"s3://[a-z0-9][a-z0-9\-]{2,62}/[a-zA-Z0-9/_\-]+", fullmatch=True)

analysis_storage_size_strategy = st.sampled_from([
    "SMALL", "MEDIUM", "LARGE", "XLARGE", "2XLARGE", "3XLARGE"
])

engine_parameters_strategy = st.fixed_dictionaries({
    "pipelineId": uuid_strategy,
    "projectId": uuid_strategy,
    "outputUri": uri_strategy,
    "logsUri": uri_strategy,
}).map(lambda d: {**d, "analysisStorageSize": "SMALL"})

# Generate valid analysis names (unique enough for each test)
analysis_name_strategy = st.text(
    alphabet=st.characters(whitelist_categories=("L", "N"), whitelist_characters="-_"),
    min_size=3,
    max_size=50
).map(lambda s: f"test-analysis-{s}")

# Generate random inputs dict
inputs_strategy = st.dictionaries(
    keys=st.text(
        alphabet=st.characters(whitelist_categories=("L", "N"), whitelist_characters="_"),
        min_size=1,
        max_size=20
    ),
    values=st.text(min_size=0, max_size=100),
    min_size=0,
    max_size=5
)

# Generate random tags dict
tags_strategy = st.dictionaries(
    keys=st.text(
        alphabet=st.characters(whitelist_categories=("L", "N"), whitelist_characters="_"),
        min_size=1,
        max_size=20
    ),
    values=st.text(min_size=0, max_size=50),
    min_size=0,
    max_size=5
)

# Optional callback token strategy
callback_token_strategy = st.one_of(
    st.none(),
    st.text(
        alphabet=st.characters(whitelist_categories=("L", "N"), whitelist_characters="-_:/"),
        min_size=10,
        max_size=100
    )
)

# Full analysis creation payload strategy
analysis_payload_strategy = st.fixed_dictionaries({
    "name": analysis_name_strategy,
    "inputs": inputs_strategy,
    "engineParameters": engine_parameters_strategy,
    "tags": tags_strategy,
    "callbackToken": callback_token_strategy,
})


# --- SQS ClientError strategies ---

sqs_error_code_strategy = st.sampled_from([
    "AWS.SimpleQueueService.NonExistentQueue",
    "InvalidMessageContents",
    "ServiceUnavailable",
    "InternalError",
    "RequestThrottled",
])


def make_client_error(error_code: str) -> ClientError:
    """Create a botocore ClientError with the given error code."""
    return ClientError(
        error_response={
            "Error": {
                "Code": error_code,
                "Message": f"Simulated {error_code} error",
            }
        },
        operation_name="SendMessage",
    )


# --- Property Test ---


@pytest.mark.asyncio
class TestSQSEnqueueFailurePreventsSubmitted:
    """
    Feature: api-rate-limiting-and-async-callback, Property 3: SQS enqueue failure prevents SUBMITTED status
    """

    @given(
        payload=analysis_payload_strategy,
        error_code=sqs_error_code_strategy,
    )
    @settings(
        max_examples=100,
        suppress_health_check=[HealthCheck.function_scoped_fixture],
        deadline=None,
    )
    @pytest.mark.asyncio
    async def test_sqs_failure_returns_5xx_and_no_submitted_status(
        self,
        payload: dict,
        error_code: str,
    ):
        """
        **Validates: Requirements 2.6**

        For any valid analysis payload, when put_sqs_message raises a ClientError,
        the API must return HTTP 5xx and must NOT save the record with SUBMITTED status.
        """
        # Track if .save() was called on any analysis data object
        save_called = False
        original_save = None

        def mock_save(self_obj):
            nonlocal save_called
            save_called = True

        # Mock put_sqs_message to raise ClientError
        sqs_error = make_client_error(error_code)

        with (
            patch(
                "icav2_wes_api.api.analysis.put_sqs_message",
                side_effect=sqs_error,
            ),
            # Mock the database query for name uniqueness check (return empty = no conflict)
            patch(
                "icav2_wes_api.api.analysis.Icav2WesAnalysisData.query",
                return_value=[],
            ),
            # Mock .save() to track whether it's called
            patch(
                "icav2_wes_api.api.analysis.Icav2WesAnalysisData.save",
                new=mock_save,
            ),
            # Mock launch_sfn to prevent any real SFN calls
            patch(
                "icav2_wes_api.api.analysis.launch_sfn",
                return_value="arn:aws:states:us-east-1:123456789012:execution:test",
            ),
            # Mock the event bus call
            patch(
                "icav2_wes_api.api.analysis.put_icav2_wes_analysis_update_event",
            ),
        ):
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.post("/api/v1/analysis/", json=payload)

            # ASSERTION 1: API returns HTTP 5xx
            assert 500 <= response.status_code < 600, (
                f"Expected HTTP 5xx when SQS enqueue fails, got {response.status_code}. "
                f"Error code: {error_code}, payload name: {payload['name']}"
            )

            # ASSERTION 2: .save() was NOT called (so record is NOT saved with SUBMITTED status)
            assert not save_called, (
                f"Expected .save() NOT to be called when SQS enqueue fails, "
                f"but it was called. Error code: {error_code}, payload name: {payload['name']}"
            )
