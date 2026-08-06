"""
Feature: api-rate-limiting-and-async-callback, Property 4: Consumer Lambda forwards complete payload with callback token

Property 4: Consumer Lambda forwards complete payload with callback token
For any valid message consumed from the Launch_Analysis_Queue, the
Launch_Queue_Consumer_Lambda SHALL invoke the Launch_Analysis_SFN with a payload
containing the fields `id`, `name`, `inputs`, `engineParameters`, `tags` from the
message body, plus a `callbackToken` field containing the consumer Lambda's own
durable execution callback token.

**Validates: Requirements 3.2**
"""

import json
import os
import sys
from unittest.mock import patch, MagicMock

import pytest
from hypothesis import given, settings, HealthCheck
from hypothesis import strategies as st

# Add lambda directory to path for imports
sys.path.insert(
    0,
    os.path.join(
        os.path.dirname(__file__),
        "..",
        "..",
        "app",
        "lambdas",
        "launch_queue_consumer_py",
    ),
)

# Set required environment variables before importing the Lambda module
os.environ.setdefault(
    "LAUNCH_ANALYSIS_SFN_ARN",
    "arn:aws:states:ap-southeast-2:123456789012:stateMachine:launch-analysis-sfn",
)

# Import the module under test
import launch_queue_consumer


# --- Hypothesis strategies for valid queue message bodies ---


def orcabus_id_strategy():
    """Generate a valid orcabus ID (iwa.<ULID-like string>)."""
    return st.from_regex(r"iwa\.[0-9A-Z]{26}", fullmatch=True)


def analysis_name_strategy():
    """Generate a valid analysis name."""
    return st.from_regex(r"[a-z][a-z0-9\-]{3,30}", fullmatch=True)


def inputs_strategy():
    """Generate valid inputs dict (arbitrary JSON-serializable)."""
    return st.dictionaries(
        keys=st.from_regex(r"[a-z][a-z0-9_]{1,15}", fullmatch=True),
        values=st.one_of(
            st.text(
                min_size=1,
                max_size=30,
                alphabet=st.characters(whitelist_categories=("L", "N")),
            ),
            st.integers(min_value=0, max_value=1000),
            st.booleans(),
        ),
        min_size=0,
        max_size=5,
    )


def uuid4_str():
    """Generate a valid UUID4 string."""
    return st.from_regex(
        r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}",
        fullmatch=True,
    )


def uri_strategy():
    """Generate a valid S3 or ICAv2 URI."""
    return st.one_of(
        st.from_regex(r"s3://[a-z][a-z0-9\-]{2,15}/[a-z0-9/\-]+", fullmatch=True),
        st.from_regex(r"icav2://[a-z][a-z0-9\-]{2,15}/[a-z0-9/\-]+", fullmatch=True),
    )


@st.composite
def engine_parameters_strategy(draw):
    """Generate valid engine parameters."""
    return {
        "pipelineId": draw(uuid4_str()),
        "projectId": draw(uuid4_str()),
        "outputUri": draw(uri_strategy()),
        "logsUri": draw(uri_strategy()),
    }


def tags_strategy():
    """Generate valid tags dict."""
    return st.dictionaries(
        keys=st.from_regex(r"[a-zA-Z][a-zA-Z0-9_]{1,15}", fullmatch=True),
        values=st.text(
            min_size=1,
            max_size=20,
            alphabet=st.characters(whitelist_categories=("L", "N")),
        ),
        min_size=0,
        max_size=5,
    )


@st.composite
def valid_queue_message_body(draw):
    """Generate a valid queue message body with all required fields."""
    return {
        "id": draw(orcabus_id_strategy()),
        "name": draw(analysis_name_strategy()),
        "inputs": draw(inputs_strategy()),
        "engineParameters": draw(engine_parameters_strategy()),
        "tags": draw(tags_strategy()),
    }


def callback_id_strategy():
    """Generate a random callback ID (simulates durable execution SDK callback token)."""
    return st.from_regex(
        r"arn:aws:lambda:[a-z]{2}-[a-z]+-[0-9]:[0-9]{12}:durable-execution/token/[a-f0-9\-]{36}",
        fullmatch=True,
    )


LAUNCH_ANALYSIS_SFN_ARN = os.environ["LAUNCH_ANALYSIS_SFN_ARN"]


class TestProperty4ConsumerForwardsPayload:
    """
    Feature: api-rate-limiting-and-async-callback, Property 4: Consumer Lambda forwards complete payload with callback token

    **Validates: Requirements 3.2**
    """

    @given(
        message_body=valid_queue_message_body(),
        callback_id=callback_id_strategy(),
    )
    @settings(
        max_examples=100,
        suppress_health_check=[HealthCheck.function_scoped_fixture],
    )
    def test_consumer_lambda_forwards_complete_payload_with_callback_token(
        self, message_body, callback_id
    ):
        """
        **Validates: Requirements 3.2**

        Property: For any valid queue message, the consumer Lambda's submitter
        calls start_execution with all message fields (id, name, inputs,
        engineParameters, tags) plus a callbackToken containing the consumer's
        own durable execution callback token.
        """
        # Build SQS event structure
        sqs_event = {
            "Records": [
                {
                    "body": json.dumps(message_body),
                    "receiptHandle": "test-receipt-handle",
                    "eventSourceARN": "arn:aws:sqs:ap-southeast-2:123456789012:test-queue",
                }
            ]
        }

        # Track what the SFN client receives
        captured_sfn_calls = []
        mock_sfn_client = MagicMock()

        def capture_start_execution(**kwargs):
            captured_sfn_calls.append(kwargs)

        mock_sfn_client.start_execution.side_effect = capture_start_execution

        # Mock wait_for_callback to immediately invoke the submitter with our
        # generated callback_id, simulating the durable execution SDK behavior
        def mock_wait_for_callback(submitter, name=None, config=None):
            """Intercept wait_for_callback to immediately invoke the submitter."""
            mock_callback_context = MagicMock()
            mock_callback_context.logger = MagicMock()
            submitter(callback_id, mock_callback_context)

        # Create mock DurableContext
        mock_context = MagicMock()
        mock_context.wait_for_callback.side_effect = mock_wait_for_callback
        mock_context.logger = MagicMock()

        # Extract the original handler function from the decorator's closure
        # The @durable_execution decorator wraps the function; the original is
        # stored in the closure
        original_handler = None
        if launch_queue_consumer.handler.__closure__:
            for cell in launch_queue_consumer.handler.__closure__:
                obj = cell.cell_contents
                if callable(obj) and getattr(obj, "__name__", None) == "handler":
                    original_handler = obj
                    break

        assert original_handler is not None, (
            "Could not extract original handler from @durable_execution closure"
        )

        # Patch get_sfn_client to return our mock
        with patch.object(
            launch_queue_consumer,
            "get_sfn_client",
            return_value=mock_sfn_client,
        ):
            # Call the original handler with our mock context
            original_handler(sqs_event, mock_context)

        # --- Assertions ---

        # The submitter should have been called (via wait_for_callback)
        assert mock_context.wait_for_callback.called, (
            "Expected wait_for_callback to be called"
        )

        # start_execution should have been called exactly once
        assert len(captured_sfn_calls) == 1, (
            f"Expected start_execution to be called once, was called "
            f"{len(captured_sfn_calls)} times"
        )

        sfn_call = captured_sfn_calls[0]

        # Verify the state machine ARN
        assert sfn_call["stateMachineArn"] == LAUNCH_ANALYSIS_SFN_ARN, (
            f"Expected SFN ARN '{LAUNCH_ANALYSIS_SFN_ARN}', "
            f"got '{sfn_call['stateMachineArn']}'"
        )

        # Parse the input payload
        execution_input = json.loads(sfn_call["input"])

        # Verify all message body fields are present with correct values
        assert execution_input["id"] == message_body["id"], (
            f"Expected id '{message_body['id']}', got '{execution_input['id']}'"
        )
        assert execution_input["name"] == message_body["name"], (
            f"Expected name '{message_body['name']}', got '{execution_input['name']}'"
        )
        assert execution_input["inputs"] == message_body["inputs"], (
            f"Expected inputs {message_body['inputs']}, got {execution_input['inputs']}"
        )
        assert execution_input["engineParameters"] == message_body["engineParameters"], (
            f"Expected engineParameters {message_body['engineParameters']}, "
            f"got {execution_input['engineParameters']}"
        )
        assert execution_input["tags"] == message_body["tags"], (
            f"Expected tags {message_body['tags']}, got {execution_input['tags']}"
        )

        # Verify the callbackToken is present and matches the callback_id
        assert "callbackToken" in execution_input, (
            "Expected 'callbackToken' field in start_execution input"
        )
        assert execution_input["callbackToken"] == callback_id, (
            f"Expected callbackToken '{callback_id}', "
            f"got '{execution_input['callbackToken']}'"
        )

        # Verify callbackToken is a string
        assert isinstance(execution_input["callbackToken"], str), (
            f"Expected callbackToken to be a string, "
            f"got {type(execution_input['callbackToken'])}"
        )
