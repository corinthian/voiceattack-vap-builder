"""vap2 — VoiceAttack .vap decoder V2.

Tree walk over the verified object model (spec v0.3), replacing v1's flat pattern scan.
Public entry points: decode_bytes() and decode_file(). Both containers are handled: raw
-deflate binary via the object walk, and uncompressed `<Profile>` XML via xml_input.
"""

from . import container, names, walker, xml_input


def decode_bytes(data, dictionary=None):
    """Decode a raw .vap file's bytes. Returns the normative profile dict."""
    dictionary = dictionary or names.load()
    kind = container.sniff(data)
    if kind == "xml":
        return xml_input.parse(data, dictionary)
    return walker.decode_profile(container.decompress(data), dictionary)


def decode_file(path, dictionary=None):
    dictionary = dictionary or names.load()
    kind, payload = container.load(path)
    if kind == "xml":
        return xml_input.parse(payload, dictionary)
    return walker.decode_profile(payload, dictionary)
