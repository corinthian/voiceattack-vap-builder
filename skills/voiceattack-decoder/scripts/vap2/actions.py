"""Action decoding (spec sec 9) — dispatch on ActionType m[2], per-family slot maps.

Slot maps are DATA (the tables below), applied by a small dispatcher, so adding a family
is a table edit, not new control flow. Families whose operand layout is not in spec v0.3's
SOLID set (Execute Command, markers, plugins, …) are emitted as recognized actions with an
honest `fieldsDecoded: false` note plus the raw member table — never silently bare, never
mis-counted as an unknown action (their ActionType code IS attributed). Reads are gated on
the mode/type slots the spec names; stale-slot hazards (spec sec 6.4) are respected.
"""

from . import primitives as P
from .primitives import ReadError, ABSENT
from . import conditions

# Families whose operands are plain length-prefixed strings (spec sec 9.4 / 9.3).
# code -> [(json_field, member_slot), ...]
SIMPLE_STRING_FIELDS = {
    3:  [("executablePath", 6), ("arguments", 7), ("workingDirectory", 8)],  # Launch
    24: [("text", 6)],                                                        # SetClipboard
    23: [("text", 6)],                                                        # Write (color/shape parked)
    21: [("targetVariable", 6), ("value", 7)],                               # Set Text
}

# Recognized ActionTypes whose operand layout is OPEN/parked or out of V2 scope
# (spec sec 9.1 attributions without a solid slot map; plan sec 3 out-of-scope list).
FIELDS_UNDECODED = {16, 17, 18, 22, 32, 33, 35, 40, 62, 64}

# Set-Integer arithmetic operator codes, meaningful only in value-source modes 8/9 (spec sec 9.4).
ARITHMETIC_OPS = {0: "plus", 1: "minus", 2: "times", 3: "divide", 4: "mod"}


def make_action_decoder(dictionary):
    """Return decode_action(buf, index, array_start, head, members) bound to `dictionary`,
    matching walker.walk_actions' callback signature."""

    def decode_action(buf, index, array_start, head, members):
        d = P.Deref(buf, array_start, members)
        atype = members and P.u32(buf, array_start + members[2])
        name = dictionary.action_type(atype)

        base = {
            "index": index,
            "actionType": {
                "code": atype,
                "name": name,
                "confidence": dictionary.action_type_confidence.get(atype),
            },
            "offset": array_start,
            "head": head,
            "guid": _guid(buf, array_start, members),
        }

        if name is None:
            # Envelope valid but code not attributed — an unknown action (spec sec 6.6 /
            # prelim sec 6). Counts toward the R3 tripwire's unknown budget.
            base["decoded"] = False
            base["actionTypeCode"] = atype
            base["members"] = list(members)
            base["reason"] = "ActionType code %s not in dictionary" % atype
            return base

        # Conditions are fields on the action (spec sec 5), dispatched by ActionType.
        if atype in conditions.COMPARE_TYPES:
            base["condition"] = conditions.decode_compare(d, atype, dictionary)
            return base
        if atype in conditions.BLOCK_STRUCTURE_TYPES:
            base["block"] = conditions.decode_block_structure(d, atype, dictionary)
            return base

        handler = _FAMILY.get(atype)
        if handler is not None:
            handler(d, base, dictionary)
            return base

        if atype in SIMPLE_STRING_FIELDS:
            for field, slot in SIMPLE_STRING_FIELDS[atype]:
                val = _opt_string(d, slot)
                if val is not None:
                    base[field] = val
            return base

        if atype in FIELDS_UNDECODED:
            base["fieldsDecoded"] = False
            base["note"] = "operand layout not in spec v0.3 solid set (parked / out of scope)"
            base["members"] = list(members)
            return base

        # Attributed name but no handler wired (e.g. 50/51 no-operand actions).
        base["fieldsDecoded"] = True
        return base

    return decode_action


# --- per-family handlers (mutate `base`) ----------------------------------------

def _keys(d, base, dictionary):
    base["duration"] = _opt_double(d, 3) or 0.0
    base["keyCodes"] = _read_keycodes(d, dictionary)


def _keys_no_duration(d, base, dictionary):
    # KeyDown/KeyUp/KeyToggle are distinct ActionTypes; Duration reads 0.0 (spec sec 9.2).
    base["keyCodes"] = _read_keycodes(d, dictionary)


def _pause(d, base, dictionary):
    base["duration"] = _opt_double(d, 3) or 0.0


def _say(d, base, dictionary):
    base["text"] = _opt_string(d, 6)
    base["voiceGuid"] = _opt_string(d, 8)
    base["voiceName"] = _opt_string(d, 9)
    base["volume"] = _opt_u32(d, 11)   # 0-100 (spec sec 9.4)
    base["rate"] = _opt_u32(d, 12)


def _mouse(d, base, dictionary):
    context = _opt_string(d, 6)
    base["contextCode"] = context
    base["action"] = dictionary.mouse_name(context) if context is not None else None
    click_dur = _opt_double(d, 4)
    if click_dur:
        base["clickDuration"] = click_dur
    scroll = _opt_double(d, 3)
    if scroll:
        base["scroll_clicks"] = scroll  # name-level split from Duration (output contract sec 5)
    if context == "Move":
        base["x"] = _opt_u32(d, 11)
        base["y"] = _opt_u32(d, 12)
    param = _opt_string(d, 7)  # populated on SPECIAL (spec sec 9.3); absent on Probe B's five
    if param is not None:
        base["parameter"] = param


def _set_boolean(d, base, dictionary):
    base["targetVariable"] = _opt_string(d, 6)
    mode = _opt_u32(d, 14)
    if mode == 0:
        base["value"] = True
    elif mode == 1:
        base["value"] = False
    elif mode is not None:
        base["valueSource"] = {
            "mode": mode, "decoded": False,
            "note": "Set-Boolean value-source mode 2-6 inferred, unsampled (spec sec 9.4)",
        }


def _set_integer(d, base, dictionary):
    base["targetVariable"] = _opt_string(d, 15)
    mode = _opt_u32(d, 14)
    base["valueSourceMode"] = mode
    # Gate every operand read on m[14]; never infer mode from populated slots, never read
    # stale operand slots for other modes (spec sec 6.4 hazard / parked #8).
    if mode == 0:
        base["value"] = _opt_i32(d, 11)
    elif mode == 1:
        base["source"] = "random"
        base["min"] = _opt_string(d, 19)
        base["max"] = _opt_string(d, 23)
    elif mode == 4:
        base["source"] = "another_variable"
        base["sourceVariable"] = _opt_string(d, 16)
    elif mode == 5:
        base["source"] = "not_set"
    elif mode == 6:
        base["source"] = "converted_text_variable"
        base["sourceVariable"] = _opt_string(d, 16)
    elif mode == 7:
        base["source"] = "saved_value"
    elif mode in (8, 9):
        base["source"] = "arithmetic"
        base["operand"] = (_opt_i32(d, 11) if mode == 8 else _opt_string(d, 16))
        op = _opt_u32(d, 20)
        base["operation"] = {"code": op, "name": ARITHMETIC_OPS.get(op)}
    elif mode in (2, 3):
        base["valueSource"] = {
            "mode": mode, "decoded": False,
            "note": "Set-Integer value-source modes 2/3 unobserved (spec sec 9.4, parked #7)",
        }


def _set_decimal(d, base, dictionary):
    base["targetVariable"] = _opt_string(d, 15)
    try:
        base["value"] = d.at(25, P.decimal16)
    except ReadError:
        base["value"] = None


def _dictation_start(d, base, dictionary):
    # ActionType 25; m[11]=1 read as clear-buffer flag (PLAUSIBLE, single sample; parked #10).
    flag = _opt_u32(d, 11)
    if flag:
        base["clearBufferFlag"] = {"value": flag, "confidence": "plausible"}


_FAMILY = {
    0: _keys,
    8: _keys_no_duration,
    9: _keys_no_duration,
    67: _keys_no_duration,
    2: _pause,
    13: _say,
    12: _mouse,
    36: _set_boolean,
    37: _set_integer,
    38: _set_decimal,
    25: _dictation_start,
}


# --- slot readers (absence-aware) -----------------------------------------------

def _read_keycodes(d, dictionary):
    """m[5] = [u32 count][count x u16 VK] (spec sec 9.2). Chords read count 2-3."""
    if d.raw(5) == ABSENT:
        return []
    try:
        base = d.array_start + d.members[5]
        count = P.u32(d.buf, base)
        if count > 64:
            return {"decoded": False, "reason": "implausible keycode count %d" % count}
        out = []
        for j in range(count):
            vk = P.u16(d.buf, base + 4 + 2 * j)
            out.append({"vk": vk, "name": dictionary.key_name(vk)})
        return out
    except ReadError:
        return {"decoded": False, "reason": "keycode list unreadable"}


def _opt_string(d, i):
    if d.raw(i) == ABSENT:
        return None
    try:
        return d.at(i, P.string)
    except ReadError:
        return None


def _opt_u32(d, i):
    if d.raw(i) == ABSENT:
        return None
    try:
        v = d.at(i, P.u32)
        return None if v == ABSENT else v
    except ReadError:
        return None


def _opt_i32(d, i):
    try:
        return d.at(i, P.i32)
    except ReadError:
        return None


def _opt_double(d, i):
    try:
        v = d.at(i, P.double)
        return v
    except ReadError:
        return None


def _guid(buf, array_start, members):
    try:
        return P.guid(buf, array_start + members[1])
    except ReadError:
        return None
