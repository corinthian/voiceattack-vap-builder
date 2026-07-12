"""Low-level binary readers and the member-offset deref rule (spec sec 4, sec 6.3-6.4).

Every read is little-endian. Member slots hold OFFSETS, never values: a field is
`value = deref(arrayStart + m[i])` read at the slot's own data type (spec sec 6.4).
All readers are bounds-checked and raise ReadError rather than reading past the buffer,
so a malformed object degrades to a typed unknown instead of crashing the walk.
"""

import struct


class ReadError(Exception):
    """A read that would fall outside the buffer, or a malformed length prefix."""


def u32(buf, pos):
    if pos < 0 or pos + 4 > len(buf):
        raise ReadError(f"u32 @{pos} out of bounds")
    return struct.unpack_from("<I", buf, pos)[0]


def i32(buf, pos):
    if pos < 0 or pos + 4 > len(buf):
        raise ReadError(f"i32 @{pos} out of bounds")
    return struct.unpack_from("<i", buf, pos)[0]


def u16(buf, pos):
    if pos < 0 or pos + 2 > len(buf):
        raise ReadError(f"u16 @{pos} out of bounds")
    return struct.unpack_from("<H", buf, pos)[0]


def double(buf, pos):
    if pos < 0 or pos + 8 > len(buf):
        raise ReadError(f"double @{pos} out of bounds")
    return struct.unpack_from("<d", buf, pos)[0]


def guid(buf, pos):
    """.NET mixed-endian GUID (spec sec 4): u32 LE, u16 LE, u16 LE, then 8 raw bytes."""
    if pos < 0 or pos + 16 > len(buf):
        raise ReadError(f"guid @{pos} out of bounds")
    a = struct.unpack_from("<I", buf, pos)[0]
    b = struct.unpack_from("<H", buf, pos + 4)[0]
    c = struct.unpack_from("<H", buf, pos + 6)[0]
    tail = buf[pos + 8:pos + 16]
    return "%08x-%04x-%04x-%02x%02x-%02x%02x%02x%02x%02x%02x" % (
        a, b, c, tail[0], tail[1], tail[2], tail[3], tail[4], tail[5], tail[6], tail[7]
    )


def string(buf, pos):
    """Length-prefixed UTF-8 (spec sec 4): [u32 length][UTF-8 bytes]. Returns the str."""
    length = u32(buf, pos)
    if length > len(buf):
        raise ReadError(f"string len {length} @{pos} implausible")
    end = pos + 4 + length
    if end > len(buf):
        raise ReadError(f"string body @{pos} out of bounds")
    return buf[pos + 4:end].decode("utf-8")


def decimal16(buf, pos):
    """.NET Decimal, CLR layout [flags u32][hi u32][lo u32][mid u32] (spec sec 4).

    Rendered as an EXACT decimal string, never via IEEE float (round-trip contract).
    5.43 -> flags 0x00020000 (scale 2), lo 543.
    """
    if pos < 0 or pos + 16 > len(buf):
        raise ReadError(f"decimal16 @{pos} out of bounds")
    flags, hi, lo, mid = struct.unpack_from("<IIII", buf, pos)
    negative = bool(flags & 0x80000000)
    scale = (flags >> 16) & 0xFF
    mantissa = (hi << 64) | (mid << 32) | lo
    digits = str(mantissa)
    if scale == 0:
        body = digits
    else:
        if len(digits) <= scale:
            digits = "0" * (scale - len(digits) + 1) + digits
        body = digits[:-scale] + "." + digits[-scale:]
    return ("-" + body) if (negative and mantissa != 0) else body


# Sentinels (spec sec 4). Both alias real values in a flat scan; type-gate before use.
ABSENT = 0xFFFFFFFF


class Deref:
    """Bound (buf, arrayStart, members) reader. `d.at(i, kind)` derefs member slot i.

    kind is one of the module functions above. Missing/out-of-bounds reads raise
    ReadError so the caller can degrade the field or the whole action to an unknown.
    """

    __slots__ = ("buf", "array_start", "members")

    def __init__(self, buf, array_start, members):
        self.buf = buf
        self.array_start = array_start
        self.members = members

    def raw(self, i):
        """The stored offset in slot i (not dereferenced)."""
        return self.members[i]

    def at(self, i, kind):
        return kind(self.buf, self.array_start + self.members[i])
