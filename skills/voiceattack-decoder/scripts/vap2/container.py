"""Container layer (spec sec 3): a .vap is EITHER raw-deflate binary OR uncompressed XML.

sniff() decides which; decompress() returns the decompressed binary buffer. The XML
form is the logical model the binary serializes (spec sec 5); it is handed to the XML
path in walker, not decompressed here.
"""

import zlib


class ContainerError(Exception):
    """Unrecognized or corrupt container."""


def sniff(data):
    """Return 'xml' or 'binary' by leading bytes (spec sec 3.2)."""
    head = data.lstrip()[:16].lower()
    if head.startswith(b"<?xml") or head.startswith(b"<profile"):
        return "xml"
    return "binary"


def decompress(data):
    """Raw deflate, no zlib header (wbits=-15). Spec sec 3.1."""
    try:
        return zlib.decompress(data, -15)
    except zlib.error as e:
        raise ContainerError(f"raw-deflate decompression failed: {e}") from e


def load(path):
    """Read a .vap and return (kind, payload): ('binary', decompressed bytes) or
    ('xml', raw bytes). Raises ContainerError on an unreadable container."""
    with open(path, "rb") as f:
        data = f.read()
    if not data:
        raise ContainerError("empty file")
    kind = sniff(data)
    if kind == "xml":
        return "xml", data
    return "binary", decompress(data)
