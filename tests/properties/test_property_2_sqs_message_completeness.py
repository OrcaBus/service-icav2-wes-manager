"""
Property 2: SQS message completeness

For any valid analysis creation request processed by the Create_Job_API, the message
enqueued to the Launch_Analysis_Queue SHALL be a JSON object containing the fields
`id`, `name`, `inputs`, `engineParameters`, and `tags`, where each field matches
the corresponding value from the created analysis record.

**Validates: Requirements 2.2, 2.3**

Feature: api-rate-limiting-and-async-callback, Property 2: SQS message completeness
"""

import json
import os
import sys
import uuid
from unittest.mock import patch, MagicMock

import pytest
from hypothesis import given, settings, HealthCheck
from hypothesis import strategies as st

# Set required environment variables before importing application modules
os.environ.setdefault("DYNAMODB_ICAV2_WES_ANALYSIS_TABLE_NAME", "test-table")
os.environ.setdefault("DYNAMODB_HOST", "http://localhost:8000")
os.environ.setdefault("EVENT_BUS_NAME", "local")
os.environ.setdefault("EVENT_SOURCE", "test-source")
os.environ.setdefault("EVENT_DETAIL_TYPE_ANALYSIS_STATE_CHANGE", "ICAv2WesAnalysisStateChange")
os.environ.setdefault("ICAV2_WES_LAUNCH_STATE_MACHINE_ARN", "arn:aws:states:us-east-1:123456789:stateMachine:test-launch")
os.environ.setdefault("ICAV2_WES_ABORT_STATE_MACHINE_ARN", "arn:aws:states:us-east-1:123456789:stateMachine:test-abort")
os.environ.setdefault("ICAV2_WES_UNLOCK_CALLBACK_STATE_MACHINE_ARN", "arn:aws:states:us-east-1:123456789:stateMachine:test-unlock")
os.environ.setdefault("LAUNCH_ANALYSIS_QUEUE_NAME", "test-launch-queue")
os.environ.setdefault("ICAV2_WES_BASE_URL", "http://localhost:8080")

# Add app/interface to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'app', 'interface'))

from httpx import AsyncClient, ASGITransport
from handler import app


# --- Hypothesis strategies for valid analysis payloads ---

def uuid4_str():
    """Generate a valid UUID4 string."""
    return st.from_regex(r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}', fullmatch=True)


def uri_str():
    """Generate a valid S3 or ICAv2 URI."""
    return st.one_of(
        st.from_regex(r's3://[a-z][a-z0-9\-]{2,20}/[a-z0-9/\-]+', fullmatch=True),
        st.from_regex(r'icav2://[a-z][a-z0-9\-]{2,20}/[a-z0-9/\-]+', fullmatch=True),
    )


analysis_storage_sizes = st.sampled_from(['Small', 'Medium', 'Large', 'XLarge', '2XLarge', '3XLarge'])


@st.composite
def engine_parameters_strategy(draw):
    """Generate valid engine parameters."""
    return {
        "pipelineId": draw(uuid4_str()),
        "projectId": draw(uuid4_str()),
        "outputUri": draw(uri_str()),
        "logsUri": draw(uri_str()),
    }


@st.composite
def analysis_name_strategy(draw):
    """Generate a unique analysis name."""
    prefix = draw(st.from_regex(r'[a-z][a-z0-9\-]{3,20}', fullmatch=True))
    suffix = uuid.uuid4().hex[:8]
    return f"{prefix}-{suffix}"


@st.composite
def inputs_strategy(draw):
    """Generate valid inputs dict."""
    num_inputs = draw(st.integers(min_value=0, max_value=3))
    inputs = {}
    for i in range(num_inputs):
        key = draw(st.from_regex(r'[a-z][a-z0-9_]{1,10}', fullmatch=True))
        value = draw(st.text(min_size=1, max_size=20, alphabet=st.characters(whitelist_categories=('L', 'N'))))
        inputs[key] = value
    return inputs


@st.composite
def tags_strategy(draw):
    """Generate valid tags dict."""
    num_tags = draw(st.integers(min_value=0, max_value=3))
    tags = {}
    for i in range(num_tags):
        key = draw(st.from_regex(r'[a-zA-Z][a-zA-Z0-9_]{1,10}', fullmatch=True))
        value = draw(st.text(min_size=1, max_size=20, alphabet=st.characters(whitelist_categories=('L', 'N'))))
        tags[key] = value
    return tags


@st.composite
def valid_analysis_payload(draw):
    """Generate a complete valid analysis creation payload."""
    return {
        "name": draw(analysis_name_strategy()),
        "inputs": draw(inputs_strategy()),
        "engineParameters": draw(engine_parameters_strategy()),
        "tags": draw(tags_strategy()),
    }


@pytest.mark.asyncio
@settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(payload=valid_analysis_payload())
async def test_sqs_message_contains_all_required_fields_with_correct_values(payload):
    """
    Property 2: SQS message completeness

    For any valid analysis creation request processed by the Create_Job_API,
    the message enqueued to the Launch_Analysis_Queue SHALL be a JSON object
    containing the fields `id`, `name`, `inputs`, `engineParameters`, and `tags`,
    where each field matches the corresponding value from the created analysis record.

    **Validates: Requirements 2.2, 2.3**
    """
    captured_sqs_calls = []

    def mock_put_sqs_message(queue_name, message_body):
        """Capture calls to put_sqs_message."""
        captured_sqs_calls.append({
            "queue_name": queue_name,
            "message_body": message_body
        })
        return "mock-message-id"

    mock_query_result = MagicMock()
    mock_query_result.__iter__ = MagicMock(return_value=iter([]))
    mock_query_result.__len__ = MagicMock(return_value=0)

    with patch(
        'icav2_wes_api.api.analysis.put_sqs_message',
        side_effect=mock_put_sqs_message
    ), patch(
        'icav2_wes_api.api.analysis.launch_sfn',
        return_value="mock-execution-arn"
    ), patch(
        'icav2_wes_api.models.analysis.Icav2WesAnalysisData.query',
        return_value=[]
    ), patch(
        'icav2_wes_api.models.analysis.Icav2WesAnalysisData.save',
        return_value=None
    ), patch(
        'icav2_wes_api.api.analysis.put_icav2_wes_analysis_update_event',
        return_value=None
    ):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post("/api/v1/analysis/", json=payload)

        # The endpoint should succeed
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"

        # Verify put_sqs_message was called exactly once
        assert len(captured_sqs_calls) == 1, (
            f"Expected put_sqs_message to be called once, was called {len(captured_sqs_calls)} times"
        )

        sqs_call = captured_sqs_calls[0]
        message_body = sqs_call["message_body"]

        # Verify queue name
        assert sqs_call["queue_name"] == os.environ["LAUNCH_ANALYSIS_QUEUE_NAME"]

        # Verify all 5 required fields are present
        required_fields = {"id", "name", "inputs", "engineParameters", "tags"}
        assert required_fields.issubset(set(message_body.keys())), (
            f"Missing required fields: {required_fields - set(message_body.keys())}"
        )

        # Verify `id` is a valid orcabus ULID (iwa.<ULID>)
        assert message_body["id"].startswith("iwa."), (
            f"Expected id to start with 'iwa.', got: {message_body['id']}"
        )

        # Verify `name` matches the input payload
        assert message_body["name"] == payload["name"], (
            f"Expected name '{payload['name']}', got '{message_body['name']}'"
        )

        # Verify `inputs` matches the input payload
        assert message_body["inputs"] == payload["inputs"], (
            f"Expected inputs {payload['inputs']}, got {message_body['inputs']}"
        )

        # Verify `engineParameters` matches the input payload
        assert message_body["engineParameters"] == payload["engineParameters"], (
            f"Expected engineParameters {payload['engineParameters']}, got {message_body['engineParameters']}"
        )

        # Verify `tags` matches the input payload
        assert message_body["tags"] == payload["tags"], (
            f"Expected tags {payload['tags']}, got {message_body['tags']}"
        )
