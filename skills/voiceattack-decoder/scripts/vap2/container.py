"""Container layer (spec sec 3): a .vap is EITHER raw-deflate binary OR uncompressed XML.

sniff() decides which; decompress() returns the decompressed binary buffer. The XML
form is the logical model the binary serializes (spec sec 5); it is handed to the XML
path in walker, not decompressed here.
"""

import zlib

# Largest real reference profile is ~80 KB compressed / ~550 KB decompressed
# (largest XML-form profile ~90 KB); these caps give ~100x headroom (SECURITY_REVIEW finding 2).
MAX_FILE_BYTES = 16 * 1024 * 1024
MAX_DECOMPRESSED_BYTES = 64 * 1024 * 1024


class ContainerError(Exception):
    """Unrecognized or corrupt container."""


def sniff(data):
    """Return 'xml' or 'binary' by leading bytes (spec sec 3.2)."""
    head = data.lstrip()[:16].lower()
    if head.startswith(b"<?xml") or head.startswith(b"<profile"):
        return "xml"
    return "binary"


def decompress(data):
    """Raw deflate, no zlib header (wbits=-15). Spec sec 3.1.

    Uses decompressobj with a max_length budget so a decompression bomb can't blow
    memory. decompressobj does not raise on a truncated stream the way one-shot
    zlib.decompress does, so eof is checked explicitly to preserve corrupt-file detection.
    """
    d = zlib.decompressobj(-15)
    try:
        out = d.decompress(data, MAX_DECOMPRESSED_BYTES)
    except zlib.error as e:
        raise ContainerError(f"raw-deflate decompression failed: {e}") from e
    if d.unconsumed_tail:
        raise ContainerError("decompressed output exceeds max size")
    if not d.eof:
        raise ContainerError("raw-deflate decompression failed: truncated stream")
    if d.unused_data:
        raise ContainerError("raw-deflate decompression failed: trailing garbage after stream")
    return out


def load(path):
    """Read a .vap and return (kind, payload): ('binary', decompressed bytes) or
    ('xml', raw bytes). Raises ContainerError on an unreadable container."""
    with open(path, "rb") as f:
        data = f.read()
    if not data:
        raise ContainerError("empty file")
    if len(data) > MAX_FILE_BYTES:
        raise ContainerError("file exceeds max size")
    kind = sniff(data)
    if kind == "xml":
        return "xml", data
    return "binary", decompress(data)
