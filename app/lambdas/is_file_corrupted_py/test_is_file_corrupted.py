#!/usr/bin/env python3

"""
Offline regression tests for the ``is_file_corrupted`` lambda.

These tests run fully offline: no AWS, no network. The ``orcabus_api_tools``
layer is not importable in the dev environment, so we inject a stub package
into ``sys.modules`` before loading the lambda, and we patch
``requests.get`` to drive a fake streamed response body.
"""
# Standard imports
import gzip
import importlib.util
import sys
from pathlib import Path
from types import ModuleType
from unittest.mock import MagicMock
from contextlib import contextmanager

import pytest


# ----------------------------------------------------------------------
# Stub the orcabus_api_tools layer BEFORE importing the lambda module.
# ----------------------------------------------------------------------
def _install_orcabus_stub():
    pkg = ModuleType("orcabus_api_tools")
    pkg.__path__ = []  # mark as a package

    filemanager = ModuleType("orcabus_api_tools.filemanager")
    filemanager.get_presigned_url_from_ingest_id = MagicMock(name="get_presigned_url_from_ingest_id")
    filemanager.get_file_object_from_ingest_id = MagicMock(name="get_file_object_from_ingest_id")
    filemanager.get_s3_uri_from_ingest_id = MagicMock(name="get_s3_uri_from_ingest_id")

    models = ModuleType("orcabus_api_tools.filemanager.models")
    models.FileObject = dict

    pkg.filemanager = filemanager
    filemanager.models = models

    sys.modules["orcabus_api_tools"] = pkg
    sys.modules["orcabus_api_tools.filemanager"] = filemanager
    sys.modules["orcabus_api_tools.filemanager.models"] = models
    return filemanager


_FILEMANAGER_STUB = _install_orcabus_stub()


# ----------------------------------------------------------------------
# Load the lambda module by file path (the folder is not a package).
# ----------------------------------------------------------------------
def _load_lambda_module():
    module_path = Path(__file__).parent / "is_file_corrupted.py"
    spec = importlib.util.spec_from_file_location("is_file_corrupted", module_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


is_file_corrupted = _load_lambda_module()

S3_URI = "s3://pipeline-prod-cache/analysis/output.json.gz"


def _chunk(data: bytes, size: int):
    """Split a byte string into chunks of at most ``size`` bytes."""
    return [data[i : i + size] for i in range(0, len(data), size)] or [b""]


@contextmanager
def _fake_requests_get(body_chunks):
    """
    Patch ``is_file_corrupted.requests.get`` with a context-manager mock whose
    ``iter_content`` yields the supplied chunks.
    """
    response = MagicMock(name="response")
    response.raise_for_status.return_value = None
    response.raw = MagicMock(name="raw")
    response.iter_content.return_value = iter(body_chunks)

    cm = MagicMock(name="requests.get")
    cm.return_value.__enter__.return_value = response
    cm.return_value.__exit__.return_value = False

    original = is_file_corrupted.requests.get
    is_file_corrupted.requests.get = cm
    try:
        yield cm
    finally:
        is_file_corrupted.requests.get = original


def _run(key: str, body_chunks):
    """Configure the filemanager stub for ``key`` and run the handler."""
    _FILEMANAGER_STUB.get_file_object_from_ingest_id.return_value = {"key": key}
    _FILEMANAGER_STUB.get_presigned_url_from_ingest_id.return_value = "https://example.test/presigned"
    _FILEMANAGER_STUB.get_s3_uri_from_ingest_id.return_value = S3_URI

    with _fake_requests_get(body_chunks):
        return is_file_corrupted.handler({"ingestId": "iwa.TEST"}, None)


# ----------------------------------------------------------------------
# JSON tests
# ----------------------------------------------------------------------
def test_json_gz_already_decompressed_plaintext_returns_not_corrupted():
    """
    The exact production bug: a .json.gz object whose body reaches us as
    already-decompressed plaintext JSON (Content-Encoding gunzipped by
    requests) must NOT be reported corrupted.
    """
    body = b'{"a": 1, "b": [1, 2, 3]}'
    result = _run("path/to/output.json.gz", _chunk(body, 8))
    assert result == {"corruptedS3Uri": None}


def test_json_gz_real_gzip_valid_json_returns_not_corrupted():
    """A genuinely gzip-compressed .json.gz with valid JSON is not corrupted."""
    body = gzip.compress(b'{"a": 1, "b": [1, 2, 3]}')
    # Split across multiple chunks to exercise the streaming path.
    result = _run("path/to/output.json.gz", _chunk(body, 4))
    assert result == {"corruptedS3Uri": None}


def test_json_gz_corrupt_gzip_returns_corrupted():
    """A stream that starts with gzip magic but is garbage is corrupted."""
    body = b"\x1f\x8b" + b"\x00" * 20
    result = _run("path/to/output.json.gz", _chunk(body, 4))
    assert result == {"corruptedS3Uri": S3_URI}


def test_json_invalid_json_returns_corrupted():
    """Plaintext body that is not valid JSON is corrupted."""
    body = b"{not json"
    result = _run("path/to/output.json.gz", _chunk(body, 4))
    assert result == {"corruptedS3Uri": S3_URI}


def test_plain_json_key_valid_returns_not_corrupted():
    """A plain .json key with valid JSON is not corrupted."""
    body = b'{"ok": true}'
    result = _run("path/to/output.json", _chunk(body, 8))
    assert result == {"corruptedS3Uri": None}


# ----------------------------------------------------------------------
# Non-JSON branch regression guards
# ----------------------------------------------------------------------
def test_plain_text_trailing_newline_not_corrupted():
    body = b"line one\nline two\n"
    result = _run("path/to/foo.txt", _chunk(body, 4))
    assert result == {"corruptedS3Uri": None}


def test_plain_text_no_trailing_newline_corrupted():
    body = b"line one\nline two"
    result = _run("path/to/foo.txt", _chunk(body, 4))
    assert result == {"corruptedS3Uri": S3_URI}


def test_html_closing_tag_not_corrupted():
    body = b"<html><body>hi</body></html>\n"
    result = _run("path/to/report.html", _chunk(body, 4))
    assert result == {"corruptedS3Uri": None}


def test_html_missing_closing_tag_corrupted():
    body = b"<html><body>hi</body>"
    result = _run("path/to/report.html", _chunk(body, 4))
    assert result == {"corruptedS3Uri": S3_URI}


def test_gzipped_plain_text_real_gzip_not_corrupted():
    """A real gzip .txt.gz ending in a newline is not corrupted."""
    body = gzip.compress(b"some log line\n")
    result = _run("path/to/foo.txt.gz", _chunk(body, 4))
    assert result == {"corruptedS3Uri": None}


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
