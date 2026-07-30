"""
Feature: api-rate-limiting-and-async-callback, Property 1: Callback token conditional unlock

Property 1: Callback token conditional unlock
For any valid analysis creation request, the Create_Job_API SHALL invoke the
Unlock_Callback_SFN if and only if the `callbackToken` field is present and non-null
in the request body. When invoked, the SFN input SHALL contain the exact callback token
from the request.

Validates: Requirements 1.4, 1.5
"""

import json
import os
import uuid
from unittest.mock import patch, MagicMock

import pytest
from hypothesis import given, settings, HealthCheck
from hypothesis import strategies as st
from httpx import AsyncClient, ASGITransport

from handler import app


# --- Strategies ---

# Generate valid UUID4 strings for pipeline/project IDs
uuid4_strategy = st.builds(lambda: str(uuid.uuid4()))

# Generate valid URI strings
uri_strategy = st.one_of(
    st.text(
        min_size=1, max_size=50,
        alphabet=st.characters(whitelist_categories=("L", "N"), whitelist_characters="-_/.")
    ).map(lambda s: f"s3://bucket/{s}"),
    st.text(
        min_size=1, max_size=50,
        alphabet=st.characters(whitelist_categories=("L", "N"), whitelist_characters="-_/.")
    ).map(lambda s: f"icav2://project/{s}"),
)

# Generate valid engine parameters
engine_parameters_strategy = st.fixed_dictionaries({
    "pipelineId": uuid4_strategy,
    "projectId": uuid4_strategy,
    "outputUri": uri_strategy,
    "logsUri": uri_strategy,
})

# Generate valid analysis names (non-empty, alphanumeric with dashes)
name_strategy = st.text(
    min_size=1,
    max_size=100,
    alphabet=st.characters(whitelist_categories=("L", "N"), whitelist_characters="-_")
)

# Generate valid inputs (arbitrary JSON-serializable dicts)
inputs_strategy = st.dictionaries(
    keys=st.text(min_size=1, max_size=20, alphabet=st.characters(whitelist_categories=("L", "N"))),
    values=st.text(min_size=0, max_size=50),
    max_size=5,
)

# Generate valid tags (arbitrary JSON-serializable dicts)
tags_strategy = st.dictionaries(
    keys=st.text(min_size=1, max_size=20, alphabet=st.characters(whitelist_categories=("L", "N"))),
    values=st.text(min_size=0, max_size=50),
    max_size=5,
)

# Generate callback tokens: either None or a random non-empty string
callback_token_strategy = st.one_of(
    st.none(),
    st.text(
        min_size=1, max_size=200,
        alphabet=st.characters(whitelist_categories=("L", "N"), whitelist_characters="-_:/.")
    ),
)

# Full request payload strategy
analysis_request_strategy = st.fixed_dictionaries({
    "name": name_strategy,
    "inputs": inputs_strategy,
    "engineParameters": engine_parameters_strategy,
    "tags": tags_strategy,
    "callbackToken": callback_token_strategy,
})


UNLOCK_SFN_ARN = os.environ["ICAV2_WES_UNLOCK_CALLBACK_STATE_MACHINE_ARN"]


@pytest.mark.asyncio
class TestProperty1CallbackTokenConditionalUnlock:
    """
    Feature: api-rate-limiting-and-async-callback, Property 1: Callback token conditional unlock

    **Validates: Requirements 1.4, 1.5**
    """

    @given(request_payload=analysis_request_strategy)
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    async def test_callback_token_conditional_unlock(self, request_payload):
        """
        **Validates: Requirements 1.4, 1.5**

        Property: Unlock_Callback_SFN is called if and only if callbackToken is present
        and non-null in the request. When called, it receives the exact token value.
        """
        callback_token = request_payload["callbackToken"]

        # Build the JSON payload, omitting callbackToken if None
        payload = {k: v for k, v in request_payload.items() if v is not None}

        with (
            patch("icav2_wes_api.api.analysis.put_sqs_message") as mock_sqs,
            patch("icav2_wes_api.api.analysis.launch_sfn") as mock_launch_sfn,
            patch("icav2_wes_api.api.analysis.put_icav2_wes_analysis_update_event"),
            patch("icav2_wes_api.api.analysis.Icav2WesAnalysisData") as mock_data_cls,
        ):
            # Mock SQS to succeed
            mock_sqs.return_value = "mock-message-id"

            # Mock the database model instance
            mock_instance = MagicMock()
            mock_instance.id = "iwa.01ABCDEFGHIJKLMNOP01234567"
            mock_instance.name = request_payload["name"]
            mock_instance.inputs = json.dumps(request_payload["inputs"])
            mock_instance.engine_parameters = json.dumps(request_payload["engineParameters"])
            mock_instance.tags = json.dumps(request_payload["tags"])
            mock_instance.status = "SUBMITTED"
            mock_instance.to_dict.return_value = {
                "id": mock_instance.id,
                "name": mock_instance.name,
                "inputs": request_payload["inputs"],
                "engineParameters": request_payload["engineParameters"],
                "tags": request_payload["tags"],
                "status": "SUBMITTED",
            }

            # Mock from_dict to return our mock instance
            mock_data_cls.from_dict.return_value = mock_instance

            # Mock query to return empty list (no duplicate name)
            mock_data_cls.query.return_value = []

            # Make the API call
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.post("/api/v1/analysis/", json=payload)

            # The request should succeed (status 200)
            assert response.status_code == 200, (
                f"Expected 200, got {response.status_code}: {response.text}"
            )

            # Verify Property 1: callback token conditional unlock
            if callback_token is not None:
                # Requirement 1.4: WHEN callbackToken is present, SHALL invoke Unlock_Callback_SFN
                mock_launch_sfn.assert_called_once()
                call_args = mock_launch_sfn.call_args

                # Extract positional and keyword arguments
                args, kwargs = call_args

                # launch_sfn is called as launch_sfn(sfn_name=..., sfn_input=...)
                sfn_name = kwargs.get("sfn_name", args[0] if args else None)
                sfn_input = kwargs.get("sfn_input", args[1] if len(args) > 1 else None)

                # Verify it was called with the Unlock_Callback_SFN ARN
                assert sfn_name == UNLOCK_SFN_ARN, (
                    f"Expected SFN ARN '{UNLOCK_SFN_ARN}', got '{sfn_name}'"
                )

                # Verify it was called with the exact callback token value
                assert sfn_input == {"callbackToken": callback_token}, (
                    f"Expected SFN input {{'callbackToken': '{callback_token}'}}, "
                    f"got {sfn_input}"
                )
            else:
                # Requirement 1.5: WHEN no callbackToken, SHALL NOT invoke Unlock_Callback_SFN
                mock_launch_sfn.assert_not_called()
