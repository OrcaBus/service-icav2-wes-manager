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
chunks.

Whether a stream is gzip-compressed is decided by inspecting the *actual*
leading bytes of the body (the gzip magic bytes 0x1f 0x8b), not by the key
suffix. This matters because an S3 object stored with Content-Encoding: gzip is
transparently decoded by requests/urllib3, so a ``.json.gz`` body can reach us
as already-decompressed plaintext. Deciding on the real bytes handles both the
already-decompressed case and the genuinely-gzipped case, while a stream that
begins with the gzip magic but is corrupt mid-stream still raises and is
reported as corrupted. As a defensive secondary measure we also set
``response.raw.decode_content = False`` so requests does not transparently
gunzip Content-Encoding on our behalf.

Multi-member / concatenated gzip streams (e.g. bgzip or streamed gzip, as
produced by DRAGEN) are fully decompressed: every concatenated member is
decoded, not just the first. A single ``zlib.decompressobj`` only decodes the
first member and silently stops, so we loop over ``unused_data`` to continue
with each subsequent member while still streaming low-memory and still raising
on genuinely corrupt data.

Per content type we then:

  * gzip files      -> feed each chunk through an incremental decompressor and
                       discard the output; concatenated gzip members are each
                       decoded in turn; a corrupt stream raises while
                       decompressing.
  * json files      -> stream (decompressed if needed) to a temp file on disk,
                       then parse from disk.
  * html files      -> keep only the trailing bytes to confirm the closing tag.
  * everything else -> remember only the final byte to confirm a trailing
                       newline.
"""
# Standard imports
import logging
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

# Leading bytes that identify a gzip stream.
_GZIP_MAGIC = b"\x1f\x8b"

# Number of trailing bytes we retain to validate the HTML closing tag.
# Kept comfortably larger than "</html>" plus any trailing whitespace.
_HTML_TAIL_BYTES = 1024
_HTML_CLOSING_TAG = b"</html>"

# Module logger. In Lambda the root handler is already configured, so this
# emits to CloudWatch at INFO without extra setup; locally, configure logging
# in the caller (see scratch/debug_is_file_corrupted.py).
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def _iter_response_chunks(presigned_url: str):
    """
    Stream the response body in fixed-size byte chunks without buffering the
    whole payload in memory.

    We disable requests' transparent content decoding so the raw stored bytes
    reach us; the real disambiguation is the gzip magic-byte check performed by
    the caller.
    """
    with requests.get(presigned_url, stream=True) as response:
        logger.info(
            "GET presigned url -> status=%s content-length=%s content-type=%s content-encoding=%s",
            response.status_code,
            response.headers.get("Content-Length"),
            response.headers.get("Content-Type"),
            response.headers.get("Content-Encoding"),
        )
        response.raise_for_status()
        response.raw.decode_content = False
        total = 0
        for chunk in response.iter_content(chunk_size=CHUNK_SIZE):
            if chunk:
                total += len(chunk)
                yield chunk
        logger.info("finished reading response body: %d raw bytes", total)


def _iter_decoded_chunks(presigned_url: str):
    """
    Stream the body and yield plaintext bytes. If the stream actually begins
    with the gzip magic bytes (0x1f 0x8b) we gunzip it with an incremental
    decompressor; otherwise the bytes are already plaintext (e.g. requests/S3
    transparently decoded a Content-Encoding: gzip object) and we pass them
    through unchanged. Detection is on the real bytes, so it is independent of
    the key suffix and response headers.

    A stream that starts with the gzip magic but is corrupt mid-stream still
    raises zlib.error, which callers map to "corrupted".
    """
    chunks = _iter_response_chunks(presigned_url)

    first = b""
    for first in chunks:
        break  # first non-empty chunk (iterator already skips empties)

    if not first:
        logger.info("empty response body: no bytes to decode")
        return  # empty body -> no bytes to yield

    logger.info("first chunk leading bytes (hex): %s", first[:4].hex())

    if first[:2] != _GZIP_MAGIC:
        # Already plaintext (or non-gzip) -> pass through unchanged.
        logger.info("stream is NOT gzip (no magic bytes) -> passing through as plaintext")
        yield first
        for chunk in chunks:
            yield chunk
        return

    logger.info("stream IS gzip (magic bytes present) -> decompressing")
    decompressor = zlib.decompressobj(_GZIP_WBITS)
    produced = 0
    members = 1

    def _feed(compressed: bytes):
        # Feed one compressed chunk into the current decompressor, draining any
        # member boundaries that complete within it. When a member ends,
        # ``unused_data`` holds the start of the next member(s): flush the
        # finished member, start a fresh decompressor seeded with the leftover
        # bytes, and keep going until the chunk is fully consumed.
        nonlocal decompressor, produced, members
        data = decompressor.decompress(compressed)
        while True:
            if data:
                produced += len(data)
                yield data
            leftover = decompressor.unused_data
            if not leftover:
                break
            tail = decompressor.flush()
            if tail:
                produced += len(tail)
                yield tail
            members += 1
            decompressor = zlib.decompressobj(_GZIP_WBITS)
            data = decompressor.decompress(leftover)

    yield from _feed(first)
    for chunk in chunks:
        yield from _feed(chunk)

    # Final drain: flush the last member, then keep consuming any trailing
    # members whose boundary fell exactly at end-of-stream.
    data = decompressor.flush()
    if data:
        produced += len(data)
        yield data
    while decompressor.unused_data:
        leftover = decompressor.unused_data
        members += 1
        decompressor = zlib.decompressobj(_GZIP_WBITS)
        data = decompressor.decompress(leftover)
        if data:
            produced += len(data)
            yield data
        data = decompressor.flush()
        if data:
            produced += len(data)
            yield data

    logger.info(
        "gzip decompression complete: %d decompressed bytes produced across %d member(s)",
        produced,
        members,
    )


def handler(event, context):
    """
    Given an ingest id, this function performs the following steps:
    """
    # Get inputs
    ingest_id = event.get("ingestId")
    logger.info("handler invoked with ingestId=%s", ingest_id)

    # Get the file object
    file_object: FileObject = get_file_object_from_ingest_id(ingest_id)
    logger.info(
        "resolved file object: s3ObjectId=%s storageClass=%s bucket=%s key=%s",
        file_object.get("s3ObjectId"),
        file_object.get("storageClass"),
        file_object.get("bucket"),
        file_object.get("key"),
    )

    # Get the presigned url
    presigned_url = get_presigned_url_from_ingest_id(ingest_id)
    logger.info("presigned url resolved (type=%s)", type(presigned_url).__name__)

    key = file_object["key"]
    is_json = key.endswith(".json.gz") or key.endswith("json")
    is_html = key.endswith(".html")
    logger.info("content type flags: is_json=%s is_html=%s", is_json, is_html)

    corrupted = {"corruptedS3Uri": get_s3_uri_from_ingest_id(ingest_id)}
    not_corrupted = {"corruptedS3Uri": None}

    # ------------------------------------------------------------------
    # JSON: we need the full (decompressed) document to validate it, so we
    # stream it to disk first and then parse it from disk. We never hold the
    # entire download in memory at once.
    # ------------------------------------------------------------------
    if is_json:
        logger.info("taking JSON branch: streaming to temp file then json_load")
        with NamedTemporaryFile(suffix=".json") as tmp:
            try:
                written = 0
                for chunk in _iter_decoded_chunks(presigned_url):
                    written += len(chunk)
                    tmp.write(chunk)
                logger.info("wrote %d bytes to temp file %s", written, tmp.name)
            except (zlib.error, EOFError) as e:
                logger.warning("CORRUPTED verdict: gzip stream error while reading: %r", e)
                return corrupted

            tmp.flush()
            tmp.seek(0)
            try:
                json_load(tmp)
            except (JSONDecodeError, UnicodeDecodeError) as e:
                logger.warning("CORRUPTED verdict: json parse error: %r", e)
                return corrupted
        logger.info("NOT corrupted: JSON parsed successfully")
        return not_corrupted

    # ------------------------------------------------------------------
    # Non-JSON: we only ever need the trailing bytes of the (decompressed)
    # content, so we stream through and retain just the tail.
    # ------------------------------------------------------------------
    logger.info("taking non-JSON branch (is_html=%s): checking trailing bytes", is_html)
    tail = b""
    tail_limit = _HTML_TAIL_BYTES if is_html else 1

    try:
        for data in _iter_decoded_chunks(presigned_url):
            if data:
                tail = (tail + data)[-tail_limit:]
    except (zlib.error, EOFError) as e:
        logger.warning("CORRUPTED verdict: gzip stream error while reading: %r", e)
        return corrupted

    logger.info("trailing bytes (repr): %r", tail[-64:])

    # HTML files may not have a line ending; confirm they end in '</html>'.
    if is_html:
        if tail.rstrip().endswith(_HTML_CLOSING_TAG):
            logger.info("NOT corrupted: HTML ends with closing tag")
            return not_corrupted
        logger.warning("CORRUPTED verdict: HTML missing closing tag")
        return corrupted

    # Everything else: the final character must be a newline.
    if not tail.endswith(b"\n"):
        logger.warning("CORRUPTED verdict: file does not end with a newline")
        return corrupted

    logger.info("NOT corrupted: trailing newline present")
    return not_corrupted
