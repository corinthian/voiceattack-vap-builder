"""Tree walk over the object model (spec sec 6, sec 13) — the V2 core.

Replaces v1's flat pattern scan. Pipeline: profile header -> scan-based command
discovery (interim, spec sec 12 #7) with the @368 pseudo-command excluded -> count-driven
envelope walk of exactly 34 fixed member slots, chaining start -> start+head. Every
object is asserted (m[0]=32, m[1]=140, in-bounds chain); any failure becomes a loud
command- or action-level unknown, never silent corruption (spec sec 11).
"""

import re
import struct

from . import primitives as P
from .primitives import ReadError
from . import actions as actions_mod
from . import conditions

# Fixed envelope constants (spec sec 6.3 rule 4).
MEMBER_COUNT = 34
ENVELOPE_M0 = 32
ENVELOPE_M1 = 140

# Profile header offsets (spec sec 6.1).
OFF_TOTAL_SIZE = 0x0000
OFF_CONST_59 = 0x0004
OFF_PROFILE_ID = 0x0170  # 368 — also the pseudo-command position to exclude (sec 11.5)
OFF_PROFILE_NAME_LEN = 0x0180
PROFILE_RECORD_POS = 0x0170


class WalkError(Exception):
    pass


# --- profile header -------------------------------------------------------------

def read_profile_header(buf):
    """Spec sec 6.1. Returns {size, const59, id, name}. Fields beyond these are OPEN."""
    header = {}
    try:
        header["declared_size"] = P.u32(buf, OFF_TOTAL_SIZE)
    except ReadError:
        header["declared_size"] = None
    header["actual_size"] = len(buf)
    try:
        header["const_at_4"] = P.u32(buf, OFF_CONST_59)
    except ReadError:
        header["const_at_4"] = None
    try:
        header["id"] = P.guid(buf, OFF_PROFILE_ID)
    except ReadError:
        header["id"] = None
    try:
        header["name"] = P.string(buf, OFF_PROFILE_NAME_LEN)
    except ReadError:
        header["name"] = None
    return header


# --- command discovery (scan-based, interim; ported from v1's proven matcher) ----

def _guid_is_valid(guid_bytes):
    """Distinguish a real command GUID from field padding / leaf values (v1 heuristic).

    VoiceAttack pads and terminates leaf fields with 0xFFFFFFFF / 0x00000000 runs, so
    those bytes precede categories, Say text and mouse contexts — never a command.
    """
    if len(guid_bytes) < 16:
        return False
    words = struct.unpack("<4I", guid_bytes[:16])
    if words[0] == 0 or words[0] == 0xFFFFFFFF:
        return False
    if any(w == 0xFFFFFFFF for w in words):
        return False
    if guid_bytes.count(0) >= 8:
        return False
    if b"\xff\xff\xff\xff" in guid_bytes:
        return False
    return True


def _match_command_signature(buf, pos):
    """Structural per-command signature test (spec sec 6.2): [GUID][u32 len][phrase]
    [u32 actionCount]. Returns a candidate dict or None. Content is never consulted."""
    n = len(buf)
    if pos + 20 > n:
        return None
    guid_bytes = buf[pos:pos + 16]
    if not _guid_is_valid(guid_bytes):
        return None
    length = struct.unpack_from("<I", buf, pos + 16)[0]
    if not (1 <= length <= 500):
        return None
    phrase_end = pos + 20 + length
    if phrase_end + 4 > n:
        return None
    try:
        phrase = buf[pos + 20:phrase_end].decode("utf-8")
    except UnicodeDecodeError:
        return None
    if not phrase.isprintable():
        return None
    count = struct.unpack_from("<I", buf, phrase_end)[0]
    if not (1 <= count <= 128):
        return None
    return {
        "pos": pos,
        "guid": P.guid(buf, pos),
        "phrase": phrase,
        "action_count": count,
        "actions_start": phrase_end + 4,  # first action object array (spec sec 6.2)
    }


def _scan_chain_end(buf, actions_start, count):
    """Sum `head` over `count` objects (spec sec 6.3), asserting each envelope. Returns
    (chain_end, ok). Used by discovery to skip a command's whole action chain so that
    action-interior GUIDs cannot alias as commands (spec sec 11.6 chord/interior hazard)."""
    arr = actions_start
    n = len(buf)
    for _ in range(count):
        if arr + 4 + 4 * MEMBER_COUNT > n:
            return arr, False
        head = P.u32(buf, arr)
        m0 = P.u32(buf, arr + 4)
        m1 = P.u32(buf, arr + 8)
        if m0 != ENVELOPE_M0 or m1 != ENVELOPE_M1:
            return arr, False
        if head <= 0 or arr + head > n:
            return arr, False
        arr += head
    return arr, True


def discover_commands(buf):
    """Chain-aware sequential discovery (spec sec 12 #7 + sec 13). Scan for a command
    signature; validate it by its first action's envelope (m[0]=32, m[1]=140 — a real
    command's chain always starts with a valid object); then skip the entire chain so no
    interior byte is ever rescanned. Excludes the @368 profile pseudo-command (sec 11.5).
    """
    candidates = []
    n = len(buf)
    pos = 0
    while pos < n - 20:
        cand = _match_command_signature(buf, pos)
        if cand is None:
            pos += 1
            continue
        if cand["pos"] == PROFILE_RECORD_POS:
            pos = cand["actions_start"]  # skip the profile record (sec 11.5)
            continue
        # First-action envelope check — the decisive filter against interior aliasing.
        astart = cand["actions_start"]
        try:
            if P.u32(buf, astart + 4) != ENVELOPE_M0 or P.u32(buf, astart + 8) != ENVELOPE_M1:
                pos += 1
                continue
        except ReadError:
            pos += 1
            continue
        chain_end, ok = _scan_chain_end(buf, astart, cand["action_count"])
        candidates.append(cand)
        pos = chain_end if (ok and chain_end > pos) else astart + 1
    return candidates


# --- envelope walk --------------------------------------------------------------

def read_members(buf, array_start):
    """Read head + exactly 34 member offsets (spec sec 6.3 rule 1: FIXED 34, never
    read-while-ascending). Raises ReadError if the offset array is out of bounds."""
    head = P.u32(buf, array_start)
    members = [P.u32(buf, array_start + 4 + 4 * i) for i in range(MEMBER_COUNT)]
    return head, members


def walk_actions(buf, command, next_command_pos, decode_action):
    """Count-driven walk of one command's action chain (spec sec 6.3).

    Returns (actions, chain_end, chain_ok). Each action dict carries at minimum offset,
    head and the raw member table (the re-decode lifeline, prelim sec 6). Envelope or
    chain-integrity failures produce unknown-action markers, not exceptions.
    """
    actions = []
    arr = command["actions_start"]
    count = command["action_count"]
    chain_ok = True
    bound = next_command_pos if next_command_pos is not None else len(buf)

    for k in range(count):
        # Chain-integrity assertion (spec sec 6.3 rule 3 / sec 12 #7): the object must
        # start before the next command and its declared length must stay in bounds.
        if arr < 0 or arr + 4 > len(buf) or arr >= bound:
            actions.append(_chain_break_marker(k, arr, "action start out of chain bounds"))
            chain_ok = False
            break
        try:
            head, members = read_members(buf, arr)
        except ReadError as e:
            actions.append(_chain_break_marker(k, arr, "member table unreadable: %s" % e))
            chain_ok = False
            break

        if head <= 0 or arr + head > len(buf):
            actions.append(_unknown_action(buf, k, arr, head, members,
                                            "head %d overruns buffer" % head))
            chain_ok = False
            break

        if members[0] != ENVELOPE_M0 or members[1] != ENVELOPE_M1:
            actions.append(_unknown_action(
                buf, k, arr, head, members,
                "envelope assertion failed: m[0]=%d m[1]=%d (want 32/140)"
                % (members[0], members[1])))
        else:
            actions.append(decode_action(buf, k, arr, head, members))
        arr += head

    return actions, arr, chain_ok


def _guid_from_members(buf, array_start, members):
    try:
        return P.guid(buf, array_start + members[1])
    except ReadError:
        return None


def _unknown_action(buf, index, array_start, head, members, reason):
    """Prelim sec 6 unknown-action marker: enough raw material to re-decode later."""
    try:
        atype = P.u32(buf, array_start + members[2])
    except ReadError:
        atype = None
    return {
        "decoded": False,
        "index": index,
        "actionTypeCode": atype,
        "offset": array_start,
        "head": head,
        "guid": _guid_from_members(buf, array_start, members),
        "members": list(members),
        "reason": reason,
    }


def _chain_break_marker(index, array_start, reason):
    return {
        "decoded": False,
        "index": index,
        "actionTypeCode": None,
        "offset": array_start,
        "head": None,
        "guid": None,
        "members": None,
        "reason": reason,
    }


# --- category (walk-bounded heuristic, spec sec 12 #9 / prelim sec 7) ------------

_VERSION_RE = re.compile(r"\d+(\.\d+)+$")


def _strings_in_range(buf, start, end, min_length=1, max_length=500):
    out = []
    i = max(0, start)
    limit = min(end, len(buf) - 4)
    while i < limit:
        length = struct.unpack_from("<I", buf, i)[0]
        if min_length <= length <= max_length and i + 4 + length <= len(buf):
            try:
                s = buf[i + 4:i + 4 + length].decode("utf-8")
                if s.isprintable():
                    out.append((i, s))
            except (UnicodeDecodeError, IndexError):
                pass
        i += 1
    return out


def extract_category(buf, start, end, mouse_context_codes):
    """Category as a walk-bounded heuristic over [start, end) — the region between this
    command's chain end and the next command (prelim sec 7). Bounded by construction, so
    v1's last-command over-scan cannot recur. Provenance-tagged, never a bare field."""
    region_len = max(0, end - start)
    # Last qualifying string, but STOP at the version string (e.g. 2.1.8). The version
    # string marks the boundary between a command's own trailing data and the profile's
    # trailing master-category list; scanning past it is exactly v1's last-command
    # over-scan (Finding 5). Bounding at it cures the over-scan while keeping last-wins,
    # so author descriptions that PRECEDE the category don't win either. Verified: this
    # gives 0 category mismatches on BOTH corinthian (CSV) and Probe B.
    candidate = None
    for _pos, s in _strings_in_range(buf, start, end, min_length=1):
        if _VERSION_RE.match(s):
            break  # profile trailing region begins here
        if s in mouse_context_codes:
            continue
        if s.startswith("{") and s.endswith("}"):
            continue  # token operand, e.g. {LASTSPOKENCMD}
        low = s.lower()
        if "\\" in s or ".exe" in low or ".wav" in low or s.startswith("*"):
            continue  # path / window / sound operand
        candidate = s
    return {
        # None = no category (VoiceAttack's empty-category state). Never a synthetic
        # placeholder: an encoder must not write a literal category the profile lacks
        # (schema v1.1 migration note).
        "value": candidate,
        "provenance": "heuristic",
        "regionOffset": start,
        "regionLength": region_len,
    }


# --- top-level orchestration ----------------------------------------------------

def decode_profile(buf, dictionary):
    """Full decode of a decompressed binary profile (spec sec 13). Returns the normative
    object model: header, commands with structured actions, and a census whose m[2]
    histogram is the R3 tripwire's unknown-budget source (plan sec 7)."""
    header = read_profile_header(buf)
    candidates = discover_commands(buf)
    decode_action = actions_mod.make_action_decoder(dictionary)
    mouse_codes = set(dictionary.mouse_name_by_code.keys())
    attributed = set(dictionary.action_type_by_code.keys())

    commands = []
    for i, cand in enumerate(candidates):
        next_pos = candidates[i + 1]["pos"] if i + 1 < len(candidates) else len(buf)
        actions, chain_end, chain_ok = walk_actions(buf, cand, next_pos, decode_action)
        conditions.derive_indent(actions)
        commands.append({
            "id": cand["guid"],
            "phrase": cand["phrase"],
            "guidOffset": cand["pos"],
            "actionCount": cand["action_count"],
            "chainEnd": chain_end,
            "chainOk": chain_ok,
            "category": extract_category(buf, chain_end, next_pos, mouse_codes),
            "actions": actions,
        })

    census = _census(commands, attributed)
    return {
        "schema_version": 2,
        "decoder": "vap2",
        "dictionary_version": dictionary.version,
        "profile": {
            "id": header["id"],
            "name": header["name"],
            "declaredSize": header["declared_size"],
            "actualSize": header["actual_size"],
            "commandCount": len(commands),
        },
        "commands": commands,
        "census": census,
    }


def _census(commands, attributed):
    """m[2] histogram + decoded/unknown tallies across every action (plan sec 7)."""
    by_code = {}
    decoded = unknown = chain_breaks = 0
    for cmd in commands:
        for a in cmd["actions"]:
            code = a.get("actionTypeCode")
            if code is None and isinstance(a.get("actionType"), dict):
                code = a["actionType"].get("code")
            is_unknown = a.get("decoded") is False
            if a.get("head") is None and is_unknown and code is None:
                chain_breaks += 1
            if code is not None:
                slot = by_code.setdefault(code, {"count": 0, "attributed": code in attributed})
                slot["count"] += 1
            if is_unknown:
                unknown += 1
            else:
                decoded += 1
    total = decoded + unknown
    unknown_budget = sum(v["count"] for c, v in by_code.items() if not v["attributed"])
    return {
        "totalActions": total,
        "decoded": decoded,
        "unknownMarked": unknown,
        "chainBreaks": chain_breaks,
        "unknownBudgetFromHistogram": unknown_budget,
        "histogram": {str(c): v for c, v in sorted(by_code.items())},
    }
