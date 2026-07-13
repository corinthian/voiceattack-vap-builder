"""XML-variant input (spec sec 3, sec 5).

A .vap may be an uncompressed `<Profile>` document instead of raw-deflate binary;
VoiceAttack imports both. v1 crashed on this documented-valid form; V2 parses it via
ElementTree into the SAME normative model the binary walker produces (output contract),
so downstream JSON is uniform regardless of container. Malformed XML raises a clean
XmlInputError, never an uncaught stack trace.

The XML form already stores the logical field set by NAME (ActionType text, Context,
KeyCodes, Condition* fields), so no member-slot deref is involved; this is a straight
field map. Fields the XML doesn't carry are simply absent, mirroring the binary path.
"""

import xml.etree.ElementTree as ET

from . import conditions


class XmlInputError(Exception):
    pass


def parse(data, dictionary):
    """Parse `<Profile>` XML bytes into the normative profile model."""
    try:
        root = ET.fromstring(data)
    except ET.ParseError as e:
        raise XmlInputError("malformed profile XML: %s" % e) from e

    tag = root.tag.split("}")[-1]  # tolerate a default namespace
    if tag != "Profile":
        raise XmlInputError("root element is <%s>, expected <Profile>" % tag)

    commands = []
    commands_el = _find_local(root, "Commands")
    if commands_el is not None:
        for cmd_el in _iter_local(commands_el, "Command"):
            commands.append(_parse_command(cmd_el, dictionary))

    return {
        "schema_version": 2,
        "decoder": "vap2",
        "source": "xml",
        "dictionary_version": dictionary.version,
        "profile": {
            "id": _local_text(root, "Id"),
            "name": _local_text(root, "Name"),
            "commandCount": len(commands),
        },
        "commands": commands,
        "census": _census(commands),
    }


def _parse_command(cmd_el, dictionary):
    actions = []
    seq = _find_local(cmd_el, "ActionSequence")
    if seq is not None:
        for i, act_el in enumerate(_iter_local(seq, "CommandAction")):
            actions.append(_parse_action(act_el, i, dictionary))
    conditions.derive_indent(actions)
    return {
        "id": _local_text(cmd_el, "Id"),
        "phrase": _local_text(cmd_el, "CommandString"),
        "category": {"value": _local_text(cmd_el, "Category") or None,
                     "provenance": "xml"},
        "actionCount": len(actions),
        "actions": actions,
    }


def _parse_action(act_el, index, dictionary):
    """Per-type field binding, mirroring the binary path's records to the field (build
    spec W2.5: the record is the contract — key names, value types, and presence rules
    must match actions.py exactly, because the fixpoint's second decode reads emitted
    XML and its records are compared field-for-field against the binary decode)."""
    xml_type = _local_text(act_el, "ActionType")
    code = dictionary.code_for_xml_type(xml_type) if xml_type else None
    base = {
        "index": index,
        "actionType": {"code": code, "name": dictionary.action_type(code) if code is not None else xml_type},
        "source": "xml",
    }

    # PressKey (0): duration ALWAYS present, absent/zero binds 0.0 (binary _keys:
    # `_opt_double or 0.0`); keyCodes ALWAYS present, even empty. KeyDown/Up/Toggle
    # (8/9/67): keyCodes only — Duration reads 0.0 by definition and the binary record
    # carries NO duration key (actions.py _keys_no_duration; spec sec 9.2).
    if code == 0:
        base["duration"] = _local_float(act_el, "Duration") or 0.0
        base["keyCodes"] = _parse_keycodes(act_el, dictionary)
        return base
    if code in (8, 9, 67):
        base["keyCodes"] = _parse_keycodes(act_el, dictionary)
        return base

    # Pause (2): duration ALWAYS present, absent/zero binds 0.0 (binary _pause).
    if code == 2:
        base["duration"] = _local_float(act_el, "Duration") or 0.0
        return base

    # Say (13): Context=text, X=volume, Y=rate (dictionary xml note, Probe B). All five
    # binary record keys are ALWAYS present (binary _say assigns unconditionally); the
    # XML form carries NO voice fields, so voiceGuid/voiceName bind None — the same
    # value the binary path yields when its slots are absent.
    if code == 13:
        base["text"] = _local_text_or_empty(act_el, "Context")
        base["voiceGuid"] = None
        base["voiceName"] = None
        base["volume"] = _local_int(act_el, "X")
        base["rate"] = _local_int(act_el, "Y")
        return base

    # MouseAction (12): Context=context code; Duration is the shared carrier for the
    # binary m[3]/m[4] pair — scroll clicks on scroll contexts (spec sec 9.3: the
    # generator "already writes scroll clicks to <Duration>"), click duration on the
    # rest; X/Y = cursor Move coordinates (m[11]/m[12]). Presence rules mirror binary
    # _mouse: contextCode/action always, clickDuration/scroll_clicks only when truthy,
    # x/y only on the Move context. The m[7] `parameter` slot (SPECIAL context) has no
    # verified XML carrier — never bound here; matches the binary record whenever that
    # slot is absent (all click/scroll/Move contexts).
    if code == 12:
        context = _local_text(act_el, "Context")
        mouse_name = dictionary.mouse_name(context) if context is not None else None
        base["contextCode"] = context
        base["action"] = mouse_name
        duration = _local_float(act_el, "Duration")
        if mouse_name in ("scroll_up", "scroll_down", "scroll_left", "scroll_right"):
            if duration:
                base["scroll_clicks"] = duration
        elif duration:
            # Non-scroll contexts INCLUDING Move: binary _mouse binds clickDuration from
            # m[4] regardless of context (truthy-gated), so a Move action with a truthy
            # Duration binds it here too. Duration-as-click-duration on Move is INFERRED
            # (Probe B's Move sample has m[4]=0.0; no export pairs them) — pending W5
            # export confirmation (verifier finding 3, wave 1).
            base["clickDuration"] = duration
        if context == "Move":
            base["x"] = _local_int(act_el, "X")
            base["y"] = _local_int(act_el, "Y")
        return base

    # Launch (3): Context=path, Context2=args, Context3=workdir (dictionary xml note).
    # Binary SIMPLE_STRING_FIELDS binds each key only when the slot is present — mirror
    # with the present-vs-absent idiom (present-but-empty "", missing element omitted).
    if code == 3:
        for field, el_name in (("executablePath", "Context"),
                               ("arguments", "Context2"),
                               ("workingDirectory", "Context3")):
            val = _local_text_or_empty(act_el, el_name)
            if val is not None:
                base[field] = val
        return base

    # Conditions are fields on the action (spec sec 5), carried on Begin/ElseIf (codes
    # 19/63) only — Else/End (29/20) are block-structure markers with no compare (ground
    # -truth samples 2d/2e: no ConditionStartNameFrom element at all on those two types).
    # Both records mirror the binary path's shape exactly (actions.py / conditions.py):
    # no duration key, no keyCodes key, no generic context key.
    if code in (19, 63):
        base["condition"] = _parse_condition(act_el, dictionary)
        return base
    if code in conditions.BLOCK_STRUCTURE_TYPES:
        base["block"] = {"pairing": _local_int(act_el, "ConditionPairing")}
        return base

    # Write (23): text carrier is Context; present-but-empty binds "" (ground truth
    # 4.8/4.9), missing element omits the key (binary _opt_string absence rule).
    if code == 23:
        text = _local_text_or_empty(act_el, "Context")
        if text is not None:
            base["text"] = text
        return base

    # SetDecimal (38): target ConditionSetName, value DecimalContext1 (string form,
    # matching the binary path's SetDecimal record keys) — carriers inferred by IntSet
    # analogy, then CONFIRMED by the VA import probe (dictionary 0.4.1 note). Both keys
    # always present, mirroring binary _set_decimal's exact rules (verifier finding 4):
    # targetVariable = _opt_string(m[15]) — None when the slot is absent, "" when
    # present-but-empty; value = decimal16(m[25]) with ReadError -> None — the binary
    # value domain is a decimal string or None, NEVER "", so a present-but-empty
    # DecimalContext1 (a state no binary profile can encode) binds None.
    if code == 38:
        base["targetVariable"] = _local_text_or_empty(act_el, "ConditionSetName")
        raw_value = _local_text_or_empty(act_el, "DecimalContext1")
        base["value"] = raw_value if raw_value else None
        return base

    # --- W5 row 2: Set family + FreeType. Carriers per the banked verbatim export
    # samples (s4_textset/boolset/intset/condset/freetype, 2.0.0 ground-truth mining)
    # and dictionary 0.4.1 xml notes; presence rules mirror actions.py where a binary
    # record exists. ---------------------------------------------------------------

    # SetText (21): target Context, value Context2 xml:space=preserve (10+ export
    # samples). Binary SIMPLE_STRING_FIELDS rule: each key bound only when its slot is
    # present — present-but-empty "", missing element omitted.
    if code == 21:
        for field, el_name in (("targetVariable", "Context"), ("value", "Context2")):
            val = _local_text_or_empty(act_el, el_name)
            if val is not None:
                base[field] = val
        return base

    # SetBoolean (36): target Context, mode InputMode — matches the binary m[14] enum
    # exactly (dictionary note; both polarities sampled: True=0, False=1). Dispatch
    # mirrors binary _set_boolean to the field: 0 -> True, 1 -> False, any other
    # non-None mode -> the same honest valueSource marker (modes 2-6 inferred from
    # dropdown order, unsampled on BOTH paths), absent mode -> no value key at all.
    if code == 36:
        base["targetVariable"] = _local_text_or_empty(act_el, "Context")
        mode = _local_int(act_el, "InputMode")
        if mode == 0:
            base["value"] = True
        elif mode == 1:
            base["value"] = False
        elif mode is not None:
            base["valueSource"] = {
                "mode": mode, "decoded": False,
                "note": "Set-Boolean value-source mode 2-6 inferred, unsampled (spec sec 9.4)",
            }
        return base

    # SetInteger (37): target ConditionSetName, literal value X int text node — the
    # ONLY carriers the export samples prove (s4_intset; dictionary note). The binary
    # record's valueSourceMode has NO evidenced XML carrier: the IntSet sample reads
    # InputMode=0 on a literal-value action, but FreeType samples read InputMode=1, so
    # InputMode-as-m[14] is NOT established for this type — key not bound, pending the
    # W5 export probe. Non-literal-mode operands (random min/max, sourceVariable,
    # arithmetic operand/operation) are likewise carrier-unevidenced and unbound.
    # Stale-slot hazard recurs at the XML layer: Context/Context2 carry leftover author
    # strings on real IntSet exports — never read them as operands.
    if code == 37:
        base["targetVariable"] = _local_text_or_empty(act_el, "ConditionSetName")
        base["value"] = _local_int(act_el, "X")
        return base

    # SetSmallInt (18, XML ConditionSet — legacy VA1 "condition"): target
    # ConditionSetName, value X int text node (s4_condset; mandiant/Antaniserse
    # exports). The binary path cannot decode this code (layout unmapped — VA2 merged
    # Small Int into Integer; FIELDS_UNDECODED marker), so the XML record is richer
    # than the binary one by construction; keys follow the IntSet convention.
    if code == 18:
        base["targetVariable"] = _local_text_or_empty(act_el, "ConditionSetName")
        base["value"] = _local_int(act_el, "X")
        return base

    # QuickInput (40, XML FreeType): text Context (variable tokens legal), Duration =
    # per-keystroke delay seconds (0.05 observed, s4_freetype). Binary path leaves this
    # code FIELDS_UNDECODED — no binary record to mirror; the per-key delay gets a
    # name-level split from the generic duration key (output contract sec 5 precedent,
    # like scroll_clicks) with a truthy gate (0 = no delay, key omitted). InputMode
    # reads 1 on both banked samples — semantics unverified, not bound.
    if code == 40:
        text = _local_text_or_empty(act_el, "Context")
        if text is not None:
            base["text"] = text
        delay = _local_float(act_el, "Duration")
        if delay:
            base["perKeyDelay"] = delay
        return base

    # Remaining codes: name resolution + the legacy generic bindings (wave 2 scope,
    # spec sec 9.4 XML note). Payload parity for these codes is future work.
    duration = _local_float(act_el, "Duration")
    if duration is not None:
        base["duration"] = duration
    context = _local_text(act_el, "Context")
    if context is not None:
        base["context"] = context
    keycodes = _parse_keycodes(act_el, dictionary)
    if keycodes:
        base["keyCodes"] = keycodes
    return base


def _parse_condition(act_el, dictionary):
    """Bind the same shape the binary path emits (conditions.decode_compare): valueType
    /operator as {code, name} pairs resolved through the dictionary, leftOperand/value
    split by value type, value key OMITTED for valueless operators (gated by the operator,
    matching the binary path). ConditionStartType is the real type carrier —
    ConditionStartValueType is vestigial (always 0 in real exports); ConditionStartValue is
    the SmallInt/Bool right-hand value, never the left operand (ConditionStartNameFrom)."""
    vtype_code = _local_int(act_el, "ConditionStartType")
    vtype_name = dictionary.value_type(vtype_code) if vtype_code is not None else None
    op_code = _local_int(act_el, "ConditionStartOperator")
    op_name = dictionary.operator(vtype_name, op_code) if (vtype_name and op_code is not None) else None

    rec = {
        "valueType": {"code": vtype_code, "name": vtype_name},
        "operator": {"code": op_code, "name": op_name},
        "leftOperand": _local_text(act_el, "ConditionStartNameFrom"),
        "pairing": _local_int(act_el, "ConditionPairing"),
        "blockOrdinal": _local_int(act_el, "ConditionGroup"),
    }
    if op_name is not None and dictionary.operator_is_valueless(op_name):
        return rec  # Has/Has-Not-Been-Set: no value key (spec sec 8.3), by operator not slot

    if vtype_name == "Text":
        # Present-but-empty Context2 round-trips as "", never None.
        rec["value"] = _local_text_or_empty(act_el, "Context2")
    else:
        # SmallInteger/Boolean carrier (spec addendum; Integer/Decimal XML carriers unverified).
        raw = _local_text_or_empty(act_el, "ConditionStartValue")
        value = None
        if raw:
            try:
                value = int(raw)
            except ValueError:
                value = None
        if vtype_name == "Boolean" and value is not None:
            value = bool(value == 1)  # True=1, matches conditions.py's binary-path read
        rec["value"] = value
    return rec


def _parse_keycodes(act_el, dictionary):
    kc = _find_local(act_el, "KeyCodes")
    if kc is None:
        return []
    out = []
    for us in _iter_local(kc, "unsignedShort"):
        if us.text is None:
            continue
        try:
            vk = int(us.text)
        except ValueError:
            continue
        out.append({"vk": vk, "name": dictionary.key_name(vk)})
    return out


def _census(commands):
    total = sum(len(c["actions"]) for c in commands)
    return {"totalActions": total, "decoded": total, "unknownMarked": 0, "source": "xml"}


# --- namespace-tolerant element helpers ----------------------------------------

def _local_name(el):
    return el.tag.split("}")[-1]


def _find_local(parent, name):
    for child in parent:
        if _local_name(child) == name:
            return child
    return None


def _iter_local(parent, name):
    for child in parent:
        if _local_name(child) == name:
            yield child


def _local_text(parent, name):
    el = _find_local(parent, name)
    return el.text if (el is not None and el.text is not None) else None


def _local_text_or_empty(parent, name):
    """Present-vs-absent text: an element that EXISTS with empty text (ElementTree .text
    is None) returns "", a missing element returns None. The row-1 payload idiom
    (condition values, Say/Write text, Launch fields, SetDecimal carriers) — remaining
    generic fields depend on _local_text's absent-on-empty behavior."""
    el = _find_local(parent, name)
    if el is None:
        return None
    return el.text if el.text is not None else ""


def _local_int(parent, name):
    t = _local_text(parent, name)
    try:
        return int(t) if t is not None else None
    except ValueError:
        return None


def _local_float(parent, name):
    t = _local_text(parent, name)
    try:
        return float(t) if t is not None else None
    except ValueError:
        return None
