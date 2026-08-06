"""
Test configuration for Python property-based tests.
Sets up environment variables and Python path for the FastAPI application.
"""

import os
import sys

# Add app/interface to the Python path so that 'icav2_wes_api' and 'handler' can be imported
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "app", "interface"))

# Set required environment variables before any app imports
os.environ.setdefault("DYNAMODB_ICAV2_WES_ANALYSIS_TABLE_NAME", "test-table")
os.environ.setdefault("DYNAMODB_HOST", "http://localhost:8000")
os.environ.setdefault("EVENT_BUS_NAME", "local")
os.environ.setdefault("EVENT_SOURCE", "test-source")
os.environ.setdefault("EVENT_DETAIL_TYPE_ANALYSIS_STATE_CHANGE", "AnalysisStateChange")
os.environ.setdefault("ICAV2_WES_LAUNCH_STATE_MACHINE_ARN", "arn:aws:states:us-east-1:123456789012:stateMachine:launch")
os.environ.setdefault("ICAV2_WES_ABORT_STATE_MACHINE_ARN", "arn:aws:states:us-east-1:123456789012:stateMachine:abort")
os.environ.setdefault("ICAV2_WES_UNLOCK_CALLBACK_STATE_MACHINE_ARN", "arn:aws:states:us-east-1:123456789012:stateMachine:unlock-callback")
os.environ.setdefault("LAUNCH_ANALYSIS_QUEUE_NAME", "test-launch-queue")
os.environ.setdefault("ICAV2_WES_BASE_URL", "http://localhost:8080")
