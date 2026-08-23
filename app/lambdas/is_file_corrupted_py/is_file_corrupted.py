#!/usr/bin/env python3

"""
Is a text file corrupted?

We perform the following checks:

1. If the file endswith .gz, we just check if the gzip can complete
2. If the file is a json, we actually just see if the json can load,
   json files don't necessarily have a new line ending
3. If the file is anything else, we check if the last char is a newline char

If the file is corrupted we return with the s3 uri with the key corruptedS3Uri

Implementation note
-------------------
Files may be arbitrarily large, so we never hold the full (compressed or
decompressed) contents in memory. Instead we stream the download in fixed-size
chunks and:

  * gzip files      -> feed each chunk through an incremental decompressor and
                       discard the output; a corrupt stream raises while
                       decompressing.
  * json files      -> stream (decompressed if needed) to a temp file on disk,
                       then parse from disk.
  * html files      -> keep only the trailing bytes to confirm the closing tag.
  * everything else -> remember only the final byte to confirm a trailing
                       newline.
"""
# Standard imports
import zlib
from json import JSONDecodeError, load as json_load
from tempfile import NamedTemporaryFile
import requests

# Layer imports
from orcabus_api_tools.filemanager import (
    get_presigned_url_from_ingest_id,
    get_file_object_from_ingest_id,
    get_s3_uri_from_ingest_id,
)
from orcabus_api_tools.filemanager.models import FileObject

# How many bytes we read from the network at a time.
CHUNK_SIZE = 1024 * 1024  # 1 MiB

# gzip streams use a zlib window with the gzip header (16 + MAX_WBITS).
_GZIP_WBITS = 16 + zlib.MAX_WBITS

# Number of trailing bytes we retain to validate the HTML closing tag.
# Kept comfortably larger than "</html>" plus any trailing whitespace.
_HTML_TAIL_BYTES = 1024
_HTML_CLOSING_TAG = b"</html>"


def _iter_response_chunks(presigned_url: str):
    """
    Stream the response body in fixed-size byte chunks without buffering the
    whole payload in memory.
    """
    with requests.get(presigned_url, stream=True) as response:
        response.raise_for_status()
        for chunk in response.iter_content(chunk_size=CHUNK_SIZE):
            if chunk:
                yield chunk


def handler(event, context):
    """
    Given an ingest id, this function performs the following steps:
    """
    # Get inputs
    ingest_id = event.get("ingestId")

    # Get the file object
    file_object: FileObject = get_file_object_from_ingest_id(ingest_id)

    # Get the presigned url
    presigned_url = get_presigned_url_from_ingest_id(ingest_id)

    key = file_object["key"]
    is_gzipped = key.endswith(".gz")
    is_json = key.endswith(".json.gz") or key.endswith("json")
    is_html = key.endswith(".html")

    corrupted = {"corruptedS3Uri": get_s3_uri_from_ingest_id(ingest_id)}
    not_corrupted = {"corruptedS3Uri": None}

    # ------------------------------------------------------------------
    # JSON: we need the full (decompressed) document to validate it, so we
    # stream it to disk first and then parse it from disk. We never hold the
    # entire download in memory at once.
    # ------------------------------------------------------------------
    if is_json:
        decompressor = zlib.decompressobj(_GZIP_WBITS) if is_gzipped else None
        with NamedTemporaryFile(suffix=".json") as tmp:
            try:
                for chunk in _iter_response_chunks(presigned_url):
                    if decompressor is not None:
                        tmp.write(decompressor.decompress(chunk))
                    else:
                        tmp.write(chunk)
                if decompressor is not None:
                    tmp.write(decompressor.flush())
            except (zlib.error, EOFError):
                # Corrupt gzip stream
                return corrupted

            tmp.flush()
            tmp.seek(0)
            try:
                json_load(tmp)
            except (JSONDecodeError, UnicodeDecodeError):
                return corrupted
        return not_corrupted

    # ------------------------------------------------------------------
    # Non-JSON: we only ever need the trailing bytes of the (decompressed)
    # content, so we stream through and retain just the tail.
    # ------------------------------------------------------------------
    decompressor = zlib.decompressobj(_GZIP_WBITS) if is_gzipped else None
    tail = b""
    tail_limit = _HTML_TAIL_BYTES if is_html else 1

    try:
        for chunk in _iter_response_chunks(presigned_url):
            data = decompressor.decompress(chunk) if decompressor is not None else chunk
            if data:
                tail = (tail + data)[-tail_limit:]
        if decompressor is not None:
            data = decompressor.flush()
            if data:
                tail = (tail + data)[-tail_limit:]
    except (zlib.error, EOFError):
        # Corrupt gzip stream
        return corrupted

    # HTML files may not have a line ending; confirm they end in '</html>'.
    if is_html:
        if tail.rstrip().endswith(_HTML_CLOSING_TAG):
            return not_corrupted
        return corrupted

    # Everything else: the final character must be a newline.
    if not tail.endswith(b"\n"):
        return corrupted

    return not_corrupted
