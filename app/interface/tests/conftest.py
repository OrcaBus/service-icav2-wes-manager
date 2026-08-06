#!/usr/bin/env python3
"""
Shared test configuration and fixtures for the ICAv2 WES API tests.

Sets up environment variables required by the application modules before they are imported.
Also adds required Lambda layer paths to sys.path.
"""
import os
import sys
from pathlib import Path

# Set required environment variables BEFORE any app modules are imported
os.environ.setdefault("DYNAMODB_ICAV2_WES_ANALYSIS_TABLE_NAME", "test-icav2-wes-analysis-table")
os.environ.setdefault("DYNAMODB_HOST", "http://localhost:8000")
os.environ.setdefault("EVENT_BUS_NAME", "test-event-bus")
os.environ.setdefault("EVENT_SOURCE", "test-source")
os.environ.setdefault("EVENT_DETAIL_TYPE_ANALYSIS_STATE_CHANGE", "Icav2WesAnalysisStateChange")
os.environ.setdefault("ICAV2_WES_LAUNCH_STATE_MACHINE_ARN", "arn:aws:states:us-east-1:123456789012:stateMachine:test-launch")
os.environ.setdefault("ICAV2_WES_ABORT_STATE_MACHINE_ARN", "arn:aws:states:us-east-1:123456789012:stateMachine:test-abort")
os.environ.setdefault("ICAV2_WES_UNLOCK_CALLBACK_STATE_MACHINE_ARN", "arn:aws:states:us-east-1:123456789012:stateMachine:test-unlock")
os.environ.setdefault("LAUNCH_ANALYSIS_QUEUE_NAME", "test-launch-analysis-queue")
os.environ.setdefault("ICAV2_WES_BASE_URL", "http://localhost:8080")

# Add Lambda layer source paths so that `fastapi_tools` is importable
_REPO_ROOT = Path(__file__).resolve().parents[3]
_FASTAPI_TOOLS_LAYER = (
    _REPO_ROOT
    / "node_modules"
    / ".pnpm"
    / "@orcabus+platform-cdk-constructs@1.7.2_@aws-cdk+aws-lambda-python-alpha@2.252.0-alpha.0_8fee2bdc3465848c2a9c9a168e0838ea"
    / "node_modules"
    / "@orcabus"
    / "platform-cdk-constructs"
    / "lambda"
    / "layers"
    / "fastapi_tools"
    / "src"
)
if _FASTAPI_TOOLS_LAYER.exists() and str(_FASTAPI_TOOLS_LAYER) not in sys.path:
    sys.path.insert(0, str(_FASTAPI_TOOLS_LAYER))
