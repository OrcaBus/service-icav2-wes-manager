# Implementation Plan — Fix false-positive corruption in `is_file_corrupted` lambda

## Context (discovered during exploration)

- **File to fix:** `app/lambdas/is_file_corrupted_py/is_file_corrupted.py` (handler `handler(event, context)`).
- **Python:** 3.14 (repo `.venv` is `uv`-managed, `cpython-3.14.2`). Package manager is `uv`.
- **Test deps available in `.venv`:** `pytest 9.1.1`, `hypothesis 6.159.0`, `requests 2.34.2`.
- **`orcabus_api_tools` is NOT importable in the dev `.venv`** (it is a Lambda layer). The regression test injects a stub `orcabus_api_tools` package into `sys.modules` before importing the lambda, so the test runs fully offline and is decoupled from the layer path. `FileObject` is a `TypedDict` and the lambda only does `file_object["key"]`, so a plain `dict` satisfies it.
- **Test layout precedent:** the only Python tests live in `app/interface/tests/` (pytest + hypothesis, heavy use of `unittest.mock.patch`). There are no existing tests under `app/lambdas/` and no `__init__.py` next to the lambda. There is no root `pyproject.toml`/`pytest.ini`; `make test` runs only the TypeScript/Jest suite, so Python lambda tests are run directly via pytest.
- **Decision on test location:** place the new test next to the lambda at `app/lambdas/is_file_corrupted_py/test_is_file_corrupted.py`. The test loads the module by file path via `importlib.util` (after installing the `orcabus_api_tools` stub into `sys.modules`). This keeps the test self-contained and needs no conftest.

## Root cause (confirmed by reading the code)

In both the JSON branch and the non-JSON branch the code decided whether to gzip-decompress purely from the key suffix: `is_gzipped = key.endswith(".gz")`. For a `.json.gz` object stored with `Content-Encoding: gzip`, `requests`/`urllib3` transparently decode the body during `iter_content()`, so the chunks are already plaintext JSON. Feeding plaintext into `zlib.decompressobj(16 + zlib.MAX_WBITS)` raises `zlib.error` immediately (no gzip header), so the handler wrongly returned `corrupted` for a valid file.

## Steps

- [x] 1. Add gzip magic-byte detection and make `_iter_response_chunks` disable transparent content decoding. Added `_GZIP_MAGIC = b"\x1f\x8b"` and set `response.raw.decode_content = False` after `raise_for_status()`.
- [x] 2. Replace suffix-driven decompression with actual-bytes detection in both branches via a new `_iter_decoded_chunks` streaming helper that gunzips only when the first two bytes are the gzip magic. Removed `is_gzipped`.
- [x] 3. Update the module docstring to describe magic-byte detection and `decode_content = False`.
- [x] 4. Add the regression test `test_is_file_corrupted.py` next to the lambda (offline, layer stubbed, `requests.get` patched).
- [x] 5. Full verification of the changed module.

## Verification record (actually run)

Command (from repo root):

    .venv/bin/python -m pytest app/lambdas/is_file_corrupted_py/test_is_file_corrupted.py -v

Result: **10 passed in 0.19s** (Python 3.14.2, pytest 9.1.1, hypothesis 6.159.0), fully offline (orcabus_api_tools stubbed into sys.modules, requests.get patched). Tests cover:

- `test_json_gz_already_decompressed_plaintext_returns_not_corrupted` — the exact production bug (plaintext JSON reaching us for a `.json.gz` key) → `{"corruptedS3Uri": None}`.
- `test_json_gz_real_gzip_valid_json_returns_not_corrupted` — real gzip, chunked → not corrupted.
- `test_json_gz_corrupt_gzip_returns_corrupted` — gzip magic + garbage → corrupted.
- `test_json_invalid_json_returns_corrupted` — plaintext non-JSON → corrupted.
- `test_plain_json_key_valid_returns_not_corrupted` — `.json` key.
- plain-text trailing-newline (pos/neg), html closing-tag (pos/neg), real-gzip `.txt.gz` → regression guards for the non-JSON branch.

Syntax check: `.venv/bin/python -c "import ast; ast.parse(open('app/lambdas/is_file_corrupted_py/is_file_corrupted.py').read())"` → exit 0.

## Notes / assumptions

- Output contract (`{"corruptedS3Uri": <uri>}` / `{"corruptedS3Uri": None}`) and the `handler(event, context)` signature are unchanged.
- `response.raw.decode_content = False` is a defensive secondary measure; the magic-byte check on the real first bytes is the primary, header-independent fix. It handles both the already-decompressed case and the genuinely-gzipped case, while still surfacing truly corrupt gzip streams as `zlib.error`.
- Did not run CDK deploy / `make deploy`, did not push or open a PR. `make test` runs only the TypeScript suite, so it is not the verification path for this Python fix.
