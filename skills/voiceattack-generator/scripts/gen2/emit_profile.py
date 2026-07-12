"""XML profile emission (plan W1) — schema-JSON records -> VoiceAttack-importable XML.

The CommandAction templates are EXTRACTED VERBATIM from vap_generator.py 2.0.0, the
proven-importable ground truth (two VoiceAttack import probes at 100%). Element order,
whitespace conventions, and xml:space handling are not changed here (build spec standing
rule). The Launch template extends the ordinary one with Context2 (args) / Context3
(working dir) after Context, per the dictionary's Launch xml carriers (xml_confidence
"inferred" — emission warns, contract §2).

Two-phase per the build spec: materialize (route contract-§3 refusals) -> validate
(hard-fail BEFORE any output) -> compute Ordinal/IndentLevel/ConditionPairing/
ConditionGroup -> render. Hard-fail vs warn split mirrors vap_generator.py: malformed
condition STRUCTURE and malformed SetDecimal/Write payloads raise EmitError (exit 1, no
output file); unknown or unrepresentable action types are refused with a LOUD warning and
emit nothing (contract §3, never silently) — action-level for non-structural types,
whole-command for condition-family actions and `decoded: false` unknown markers, whose
partial loss would corrupt every downstream pairing index (the exact failure the
hard-fail ruling exists to prevent).

Pairing/blockOrdinal/indentLevel on input records are IGNORED and recomputed from the
emitted sequence — they are derived layout, and recomputation keeps them consistent when
a non-structural action in the block was refused.
"""

import math
import re
import uuid
from xml.sax.saxutils import escape


class EmitError(Exception):
    """Hard-fail defect (malformed condition structure, malformed SetDecimal/Write
    payload). Aborts the entire generation run: exit 1, no output file."""


# Wired coverage this wave (plan coverage row 1). Canonical dictionary names — a SCOPE
# statement only; every code/name/index below resolves through the dictionary at runtime.
WIRED = {
    "PressKey", "KeyDown", "KeyUp", "KeyToggle", "MouseAction", "Pause", "Say",
    "Launch", "Write", "SetDecimal",
    "BeginCondition", "ElseIf", "Else", "EndCondition",
}
# Key-list family (shared template, Duration 0 by definition for the last three).
_KEY_FAMILY = {"PressKey", "KeyDown", "KeyUp", "KeyToggle"}
# Condition-family (block-structural): refusal granularity is the whole command.
_STRUCTURAL = {"BeginCondition", "ElseIf", "Else", "EndCondition", "BeginLoopWhile", "EndLoop"}
_COMPARES = {"BeginCondition", "ElseIf"}
_BRANCHES = {"ElseIf", "Else"}

_PLAIN_DECIMAL = re.compile(r"^-?\d+(\.\d+)?$")


def new_guid():
    return str(uuid.uuid4())


def emit(model, dictionary):
    """Render a schema_input model to profile XML. Returns (xml_text, warnings).
    Raises EmitError on any hard-fail defect — the caller must not have written output."""
    warnings = []
    command_chunks = []
    for cmd in model["commands"]:
        chunk = _command_xml(cmd, dictionary, warnings.append)
        if chunk is not None:
            command_chunks.append(chunk)

    profile = model["profile"]
    profile_id = profile.get("id") or new_guid()
    name = escape(profile.get("name") or "")
    return _profile_xml(profile_id, name, "\n".join(command_chunks)), warnings


# --- phase 1: refusal routing (contract §3 — loud, never silent) -------------------

def route_actions(cmd, dictionary, warn):
    """Classify a command's actions. Returns the representable plans
    [(canonical, record), ...], or None when the whole command is refused."""
    phrase = cmd["phrase"]
    kept = []
    for idx, rec in enumerate(cmd["actions"]):
        if rec.get("decoded") is False:
            warn("Command '%s': action %d is an unknown marker (ActionType code %s: %s) - "
                 "cannot be proven non-structural; refusing the whole command (contract §3)"
                 % (phrase, idx, rec.get("actionTypeCode"), rec.get("reason", "no reason recorded")))
            return None

        canonical = _resolve_canonical(rec.get("actionType") or {}, dictionary)
        if canonical is None:
            at = rec.get("actionType") or {}
            warn("Command '%s': action %d type (code %r, name %r) is not in the dictionary - "
                 "cannot be proven non-structural; refusing the whole command (contract §3)"
                 % (phrase, idx, at.get("code"), at.get("name")))
            return None

        if canonical in _STRUCTURAL:
            if canonical not in WIRED:
                warn("Command '%s': action %d '%s' emission is parked (While pair, plan D4) - "
                     "refusing the whole command" % (phrase, idx, canonical))
                return None
            if canonical in _COMPARES:
                reason = _condition_refusal(rec.get("condition"), dictionary)
                if reason is not None:
                    warn("Command '%s': action %d (%s) %s - refusing the whole command"
                         % (phrase, idx, canonical, reason))
                    return None
            kept.append((canonical, rec))
            continue

        if canonical not in WIRED:
            warn("Command '%s': action %d '%s' is not emit-wired this wave - "
                 "emitting nothing for it (contract §3)" % (phrase, idx, canonical))
            continue

        if canonical == "MouseAction" and _mouse_context(rec, dictionary) is None:
            warn("Command '%s': action %d MouseAction context %r / action %r is not in the "
                 "dictionary - emitting nothing for it" % (phrase, idx,
                 rec.get("contextCode"), rec.get("action")))
            continue

        if canonical == "Say" and _nondefault_voice(rec):
            # The XML voice carrier is unknown; the selection cannot be represented.
            # Emit the action with the Default voice, but never drop the field silently.
            warn("Command '%s': action %d Say voice %r is not representable (XML voice "
                 "carrier unknown) - emitting with the Default voice" % (phrase, idx,
                 rec.get("voiceName") or rec.get("voiceGuid")))

        if canonical in _KEY_FAMILY and not isinstance(rec.get("keyCodes", []), list):
            warn("Command '%s': action %d %s key-code list did not decode - "
                 "emitting nothing for it" % (phrase, idx, canonical))
            continue

        code = dictionary.code_for_name(canonical)
        xml_conf = dictionary.xml_confidence(code)
        if xml_conf not in (None, "solid"):
            # Plausible/inferred entries round-trip WITH a warning naming the entry and
            # its confidence (contract §2).
            warn("Command '%s': action %d '%s' XML carrier confidence is '%s' - emitted "
                 "with a warning (contract §2)" % (phrase, idx, canonical, xml_conf))
        kept.append((canonical, rec))
    return kept


def _resolve_canonical(action_type, dictionary):
    """Record {code, name} -> canonical dictionary name, or None (refuse, never guess).
    Names are the authority (contract §1); a code/name mismatch resolves to None."""
    code = action_type.get("code")
    name = action_type.get("name")
    if code is not None and dictionary.action_entry(code) is not None:
        canonical = dictionary.canonical(code)
        if name is not None and name != canonical:
            return None
        return canonical
    if name is not None and dictionary.code_for_name(name) is not None:
        return name
    return None


def _condition_refusal(cond, dictionary):
    """Unrepresentable-but-well-formed compare -> refusal reason string, else None.
    (A MISSING condition object is malformed structure — the hard-fail path, not here.)"""
    if not isinstance(cond, dict):
        return None
    if "unresolved" in cond:
        return "carries an unresolved compare (left operand absent at decode)"
    if "compound" in cond:
        return ("carries a compound (AND/OR) condition - the encoder refuses compound "
                "input until the m[31] format is decoded (contract §4)")
    vtype = cond.get("valueType") or {}
    vtype_name = vtype.get("name") if isinstance(vtype, dict) else None
    if vtype_name != "Text":
        return ("has valueType %r - wave 1 emits Text compares only (coverage row 1)"
                % (vtype_name,))
    op = cond.get("operator") or {}
    op_name = op.get("name") if isinstance(op, dict) else None
    if dictionary.operator_index("Text", op_name) is None:
        return "has operator %r, not in the dictionary's Text operator table" % (op_name,)
    return None


_ZERO_GUID = "00000000-0000-0000-0000-000000000000"


def _nondefault_voice(rec):
    """True when a Say record selects a specific TTS voice (all-zero GUID = Default,
    dictionary Say fields note)."""
    guid = rec.get("voiceGuid")
    name = rec.get("voiceName")
    if guid is not None and guid != _ZERO_GUID:
        return True
    return name is not None and name != "Default"


def _mouse_context(rec, dictionary):
    """Resolve a MouseAction record to its context code: the record's own contextCode if
    it is dictionary-valid, else the canonical/alias action name. None = refuse."""
    ctx = rec.get("contextCode")
    if ctx is not None:
        return ctx if ctx in dictionary.mouse_context_codes else None
    action = rec.get("action")
    if isinstance(action, str):
        return dictionary.mouse_context(action.lower())
    return None


# --- phase 2: hard-fail validation (structure + SetDecimal/Write payloads) ---------

def _validate(plans, phrase, dictionary):
    def fail(msg):
        raise EmitError("Command '%s': %s" % (phrase, msg))

    stack = []  # one frame per open block: {"seen_else": bool}
    for canonical, rec in plans:
        if canonical == "SetDecimal":
            variable = rec.get("targetVariable")
            if not isinstance(variable, str) or not variable:
                fail("'SetDecimal' requires a non-empty string 'targetVariable'")
            _validate_decimal_value(rec.get("value"), fail)
            continue
        if canonical == "Write":
            if not isinstance(rec.get("text"), str):
                fail("'Write' requires a string 'text' (empty string is legal)")
            continue
        if canonical not in _STRUCTURAL:
            continue

        cond = rec.get("condition")
        if canonical in _COMPARES:
            if not isinstance(cond, dict):
                fail("'%s' is missing a required 'condition' object" % canonical)
            left = cond.get("leftOperand")
            if not isinstance(left, str) or not left:
                fail("'%s' condition is missing a non-empty 'leftOperand'" % canonical)
            op_name = (cond.get("operator") or {}).get("name")
            if not dictionary.operator_is_valueless(op_name) and "value" not in cond:
                fail("'%s' condition is missing a 'value' key (only Has Been Set / "
                     "Has Not Been Set omit it)" % canonical)

        if canonical == "BeginCondition":
            stack.append({"seen_else": False})
        elif canonical == "ElseIf":
            if not stack:
                fail("'ElseIf' found outside any open condition block")
            if stack[-1]["seen_else"]:
                fail("'ElseIf' follows 'Else' in the same condition block")
        elif canonical == "Else":
            if cond is not None:
                fail("'Else' must not carry a 'condition' object")
            if not stack:
                fail("'Else' found outside any open condition block")
            if stack[-1]["seen_else"]:
                fail("duplicate 'Else' in the same condition block")
            stack[-1]["seen_else"] = True
        elif canonical == "EndCondition":
            if cond is not None:
                fail("'EndCondition' must not carry a 'condition' object")
            if not stack:
                fail("'EndCondition' found without a matching 'BeginCondition'")
            stack.pop()

    if stack:
        raise EmitError(
            "Command '%s': %d condition block(s) opened with 'BeginCondition' but never "
            "closed with 'EndCondition'" % (phrase, len(stack)))


def _validate_decimal_value(value, fail):
    """SetDecimal value: schema JSON carries the exact decimal STRING the binary decode
    produced (plain form, never scientific); bare numbers are accepted too. .NET decimal
    has no NaN/Inf, so a non-finite value would silently break VoiceAttack import."""
    if isinstance(value, bool):
        fail("'SetDecimal' requires a numeric 'value' (got %r)" % (value,))
    elif isinstance(value, (int, float)):
        if not math.isfinite(value):
            fail("'SetDecimal' requires a finite 'value' (got %r)" % (value,))
    elif isinstance(value, str):
        if not _PLAIN_DECIMAL.match(value):
            fail("'SetDecimal' requires a plain decimal string 'value' (got %r)" % (value,))
    else:
        fail("'SetDecimal' requires a numeric 'value' (got %r)" % (value,))


# --- phase 3: layout (Ordinal / IndentLevel / ConditionPairing / ConditionGroup) ----

def _compute_layout(plans):
    """[(canonical, rec)] -> [(canonical, rec, ordinal, indent, pairing, group)].

    Same derivation as vap_generator.py's command_xml pass: Ordinal is the emitted index;
    IndentLevel from Begin/End nesting (branch markers dedent one); ConditionGroup counts
    Begins 1-based with branches/End inheriting; ConditionPairing chains forward
    Begin -> ElseIf -> ... -> Else -> End, with End pointing back to its Begin."""
    out = []
    depth = 0
    group_counter = 0
    stack = []      # open blocks: {"group": int, "ordinals": [int, ...]}
    finished = []   # per block, marker ordinals in Begin..End order
    for canonical, rec in plans:
        ordinal = len(out)
        if canonical == "BeginCondition":
            group_counter += 1
            stack.append({"group": group_counter, "ordinals": [ordinal]})
            out.append([canonical, rec, ordinal, depth, 0, group_counter])
            depth += 1
        elif canonical in _BRANCHES:
            frame = stack[-1]
            frame["ordinals"].append(ordinal)
            out.append([canonical, rec, ordinal, max(0, depth - 1), 0, frame["group"]])
        elif canonical == "EndCondition":
            frame = stack.pop()
            frame["ordinals"].append(ordinal)
            depth = max(0, depth - 1)
            out.append([canonical, rec, ordinal, depth, 0, frame["group"]])
            finished.append(frame["ordinals"])
        else:
            out.append([canonical, rec, ordinal, depth, 0, 0])

    pairing = {}
    for ordinals in finished:
        for src, dst in zip(ordinals, ordinals[1:]):
            pairing[src] = dst
        pairing[ordinals[-1]] = ordinals[0]
    for plan in out:
        if plan[0] in _STRUCTURAL:
            plan[4] = pairing[plan[2]]
    return [tuple(p) for p in out]


# --- phase 4: render ----------------------------------------------------------------

def _command_xml(cmd, dictionary, warn):
    plans = route_actions(cmd, dictionary, warn)
    if plans is None:
        return None
    _validate(plans, cmd["phrase"], dictionary)
    chunks = [_action_xml(p, dictionary, warn) for p in _compute_layout(plans)]
    return _command_envelope(cmd, "\n".join(chunks))


def _action_xml(plan, dictionary, warn):
    canonical, rec, ordinal, indent, pairing, group = plan
    xml_type = dictionary.xml_action_type(dictionary.code_for_name(canonical))

    if canonical in _COMPARES:
        return _compare_xml(xml_type, rec["condition"], ordinal, indent, pairing, group,
                            dictionary)
    if canonical in ("Else", "EndCondition"):
        return _block_close_xml(xml_type, ordinal, indent, pairing, group)
    if canonical == "SetDecimal":
        return _decimal_set_xml(rec, ordinal, indent)
    if canonical == "Launch":
        return _launch_xml(rec, ordinal, indent, warn)

    duration_str = "0"
    context = ""
    x = y = z = "0"
    dc1 = "0"
    key_codes_xml = "<KeyCodes/>"

    if canonical in _KEY_FAMILY:
        key_codes_xml = _key_codes_xml(rec.get("keyCodes", []), warn)
        if canonical == "PressKey":
            duration_str = _format_duration(rec.get("duration", 0), warn)
        # KeyDown/KeyUp/KeyToggle: Duration is 0 by definition (dictionary fields note).
    elif canonical == "Pause":
        duration_str = _format_duration(rec.get("duration", 0), warn)
    elif canonical == "Say":
        context = escape(rec.get("text") or "")
        x = _int_str(rec.get("volume"), 100, "Say volume", warn)
        y = _int_str(rec.get("rate"), 0, "Say rate", warn)
    elif canonical == "Write":
        context = escape(rec["text"])
    elif canonical == "MouseAction":
        context = _mouse_context(rec, dictionary)
        if context in dictionary.scroll_context_codes:
            clicks = _format_duration(rec.get("scroll_clicks", 1), warn)
            duration_str = clicks
            x = clicks
            dc1 = clicks
        elif context == dictionary.cursor_move_code:
            x = _int_str(rec.get("x"), 0, "MouseAction x", warn)
            y = _int_str(rec.get("y"), 0, "MouseAction y", warn)
        elif rec.get("clickDuration") is not None:
            duration_str = _format_duration(rec["clickDuration"], warn)

    return _ordinary_xml(xml_type, ordinal, indent, duration_str, key_codes_xml,
                         context, x, y, z, dc1)


def _key_codes_xml(key_codes, warn):
    codes = []
    for entry in key_codes:
        vk = entry.get("vk") if isinstance(entry, dict) else entry
        if isinstance(vk, int) and not isinstance(vk, bool):
            codes.append(vk)
        else:
            warn("Unknown key entry %r - ignored" % (entry,))
    if not codes:
        return "<KeyCodes/>"
    return (
        "<KeyCodes>\n"
        + "\n".join(f"            <unsignedShort>{c}</unsignedShort>" for c in codes)
        + "\n          </KeyCodes>"
    )


# --- number rendering ---------------------------------------------------------------

def _format_duration(value, warn):
    """Validate a duration/count and format it as a plain decimal string (never
    scientific notation). Invalid (non-numeric, negative, non-finite) values fall back
    to 0.1 with a warning, mirroring vap_generator.format_duration. Explicit zero is
    legal and passes through unclamped (build spec input-mapping note)."""
    if (isinstance(value, bool) or not isinstance(value, (int, float))
            or not math.isfinite(value) or value < 0):
        warn("Invalid duration %r - using default 0.1" % (value,))
        return "0.1"
    return _plain_number(value)


def _plain_number(value):
    """Plain decimal string, never scientific notation. json.load erases the int/float
    authoring distinction (vap_generator's '0' decodes back as 0.0), so integral floats
    render as ints — reproducing the old emitter's output for every decoded value."""
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    if isinstance(value, int):
        return str(value)
    s = repr(value)
    if "e" in s or "E" in s:
        s = f"{value:.10f}".rstrip("0").rstrip(".")
    return s


def _format_decimal(value):
    """SetDecimal value as plain decimal text: exact strings pass through untouched
    (the binary decode's lossless .NET-decimal rendering), numbers like the old
    generator's _format_decimal."""
    if isinstance(value, str):
        return value
    if isinstance(value, int):
        return str(value)
    s = repr(float(value))
    if "e" in s or "E" in s:
        s = f"{float(value):.10f}".rstrip("0").rstrip(".")
    return s


def _int_str(value, default, label, warn):
    if value is None:
        return str(default)
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        warn("Invalid %s %r - using default %d" % (label, value, default))
        return str(default)
    return str(int(value))


# --- templates (verbatim from vap_generator.py 2.0.0 — ground truth, do not edit) ----

def _ordinary_xml(action_type, ordinal, indent_level, duration_str, key_codes_xml,
                  context, x, y, z, decimal_context1):
    action_id = new_guid()
    return f"""        <CommandAction>
          <PairingSet>false</PairingSet>
          <PairingSetElse>false</PairingSetElse>
          <Ordinal>{ordinal}</Ordinal>
          <ConditionMet xsi:nil="true"/>
          <IndentLevel>{indent_level}</IndentLevel>
          <ConditionSkip>false</ConditionSkip>
          <IsSuffixAction>false</IsSuffixAction>
          <DecimalTransient1>0</DecimalTransient1>
          <Id>{action_id}</Id>
          <ActionType>{action_type}</ActionType>
          <Duration>{duration_str}</Duration>
          <Delay>0</Delay>
          {key_codes_xml}
          <Context>{context}</Context>
          <X>{x}</X>
          <Y>{y}</Y>
          <Z>{z}</Z>
          <InputMode>0</InputMode>
          <ConditionPairing>0</ConditionPairing>
          <ConditionGroup>0</ConditionGroup>
          <ConditionStartOperator>0</ConditionStartOperator>
          <ConditionStartValue>0</ConditionStartValue>
          <ConditionStartValueType>0</ConditionStartValueType>
          <ConditionStartType>0</ConditionStartType>
          <DecimalContext1>{decimal_context1}</DecimalContext1>
          <DecimalContext2>0</DecimalContext2>
          <DateContext1>0001-01-01T00:00:00</DateContext1>
          <DateContext2>0001-01-01T00:00:00</DateContext2>
          <Disabled>false</Disabled>
          <RandomSounds/>
          <ConditionExpressions/>
        </CommandAction>"""


def _launch_xml(rec, ordinal, indent_level, warn):
    """Ordinary template + Context2 (args) / Context3 (working dir) after Context, per
    the dictionary's Launch xml carriers. Context2/Context3 are emitted only when the
    record carries the field, with xml:space="preserve" (the serializer's convention on
    Context2, per the ground-truth condition template). Not producible by
    vap_generator.py 2.0.0 — Launch is v1-era, import-proven since 1.x (plan §4)."""
    action_id = new_guid()
    context = escape(rec.get("executablePath") or "")
    extra = ""
    if rec.get("arguments") is not None:
        extra += f"\n          <Context2 xml:space=\"preserve\">{escape(rec['arguments'])}</Context2>"
    if rec.get("workingDirectory") is not None:
        extra += f"\n          <Context3 xml:space=\"preserve\">{escape(rec['workingDirectory'])}</Context3>"
    return f"""        <CommandAction>
          <PairingSet>false</PairingSet>
          <PairingSetElse>false</PairingSetElse>
          <Ordinal>{ordinal}</Ordinal>
          <ConditionMet xsi:nil="true"/>
          <IndentLevel>{indent_level}</IndentLevel>
          <ConditionSkip>false</ConditionSkip>
          <IsSuffixAction>false</IsSuffixAction>
          <DecimalTransient1>0</DecimalTransient1>
          <Id>{action_id}</Id>
          <ActionType>Launch</ActionType>
          <Duration>0</Duration>
          <Delay>0</Delay>
          <KeyCodes/>
          <Context>{context}</Context>{extra}
          <X>0</X>
          <Y>0</Y>
          <Z>0</Z>
          <InputMode>0</InputMode>
          <ConditionPairing>0</ConditionPairing>
          <ConditionGroup>0</ConditionGroup>
          <ConditionStartOperator>0</ConditionStartOperator>
          <ConditionStartValue>0</ConditionStartValue>
          <ConditionStartValueType>0</ConditionStartValueType>
          <ConditionStartType>0</ConditionStartType>
          <DecimalContext1>0</DecimalContext1>
          <DecimalContext2>0</DecimalContext2>
          <DateContext1>0001-01-01T00:00:00</DateContext1>
          <DateContext2>0001-01-01T00:00:00</DateContext2>
          <Disabled>false</Disabled>
          <RandomSounds/>
          <ConditionExpressions/>
        </CommandAction>"""


def _compare_xml(action_type, condition, ordinal, indent_level, pairing, group, dictionary):
    """Begin/ElseIf marker: value in Context2 (xml:space=preserve), left operand in
    ConditionStartNameFrom, operator as the Text dropdown index, ConditionStartType as
    the value-type code — all dictionary-resolved."""
    action_id = new_guid()
    operator_code = dictionary.operator_index("Text", condition["operator"]["name"])
    vtype_code = dictionary.value_type_code("Text")
    left_operand = escape(condition["leftOperand"])
    value = escape(str(condition.get("value", "")))
    return f"""        <CommandAction>
          <PairingSet>false</PairingSet>
          <PairingSetElse>false</PairingSetElse>
          <Ordinal>{ordinal}</Ordinal>
          <ConditionMet xsi:nil="true"/>
          <IndentLevel>{indent_level}</IndentLevel>
          <ConditionSkip>false</ConditionSkip>
          <IsSuffixAction>false</IsSuffixAction>
          <DecimalTransient1>0</DecimalTransient1>
          <Id>{action_id}</Id>
          <ActionType>{action_type}</ActionType>
          <Duration>0</Duration>
          <Delay>0</Delay>
          <KeyCodes/>
          <Context2 xml:space="preserve">{value}</Context2>
          <X>0</X>
          <Y>0</Y>
          <Z>1</Z>
          <InputMode>0</InputMode>
          <ConditionPairing>{pairing}</ConditionPairing>
          <ConditionGroup>{group}</ConditionGroup>
          <ConditionStartNameFrom>{left_operand}</ConditionStartNameFrom>
          <ConditionStartOperator>{operator_code}</ConditionStartOperator>
          <ConditionStartValue>0</ConditionStartValue>
          <ConditionStartValueType>0</ConditionStartValueType>
          <ConditionStartCompareToCondtion/>
          <ConditionStartType>{vtype_code}</ConditionStartType>
          <DecimalContext1>0</DecimalContext1>
          <DecimalContext2>0</DecimalContext2>
          <DateContext1>0001-01-01T00:00:00</DateContext1>
          <DateContext2>0001-01-01T00:00:00</DateContext2>
          <Disabled>false</Disabled>
          <RandomSounds/>
          <ConditionExpressions/>
        </CommandAction>"""


def _block_close_xml(action_type, ordinal, indent_level, pairing, group):
    """Else / EndCondition: structural only, no compare fields carried."""
    action_id = new_guid()
    return f"""        <CommandAction>
          <PairingSet>false</PairingSet>
          <PairingSetElse>false</PairingSetElse>
          <Ordinal>{ordinal}</Ordinal>
          <ConditionMet xsi:nil="true"/>
          <IndentLevel>{indent_level}</IndentLevel>
          <ConditionSkip>false</ConditionSkip>
          <IsSuffixAction>false</IsSuffixAction>
          <DecimalTransient1>0</DecimalTransient1>
          <Id>{action_id}</Id>
          <ActionType>{action_type}</ActionType>
          <Duration>0</Duration>
          <Delay>0</Delay>
          <KeyCodes/>
          <X>0</X>
          <Y>0</Y>
          <Z>0</Z>
          <InputMode>0</InputMode>
          <ConditionPairing>{pairing}</ConditionPairing>
          <ConditionGroup>{group}</ConditionGroup>
          <ConditionStartOperator>0</ConditionStartOperator>
          <ConditionStartValue>0</ConditionStartValue>
          <ConditionStartValueType>0</ConditionStartValueType>
          <ConditionStartType>0</ConditionStartType>
          <DecimalContext1>0</DecimalContext1>
          <DecimalContext2>0</DecimalContext2>
          <DateContext1>0001-01-01T00:00:00</DateContext1>
          <DateContext2>0001-01-01T00:00:00</DateContext2>
          <Disabled>false</Disabled>
          <RandomSounds/>
          <ConditionExpressions/>
        </CommandAction>"""


def _decimal_set_xml(rec, ordinal, indent_level):
    """DecimalSet: target variable in ConditionSetName, value in DecimalContext1, no
    <Context> element. Carriers CONFIRMED by the 2026-07-12 VoiceAttack import probe
    (dictionary 0.4.1 SetDecimal note)."""
    action_id = new_guid()
    variable = escape(rec["targetVariable"])
    value = _format_decimal(rec["value"])
    return f"""        <CommandAction>
          <PairingSet>false</PairingSet>
          <PairingSetElse>false</PairingSetElse>
          <Ordinal>{ordinal}</Ordinal>
          <ConditionMet xsi:nil="true"/>
          <IndentLevel>{indent_level}</IndentLevel>
          <ConditionSkip>false</ConditionSkip>
          <IsSuffixAction>false</IsSuffixAction>
          <DecimalTransient1>0</DecimalTransient1>
          <Id>{action_id}</Id>
          <ActionType>DecimalSet</ActionType>
          <Duration>0</Duration>
          <Delay>0</Delay>
          <KeyCodes/>
          <X>0</X>
          <Y>0</Y>
          <Z>0</Z>
          <InputMode>0</InputMode>
          <ConditionSetName xml:space="preserve">{variable}</ConditionSetName>
          <ConditionPairing>0</ConditionPairing>
          <ConditionGroup>0</ConditionGroup>
          <ConditionStartOperator>0</ConditionStartOperator>
          <ConditionStartValue>0</ConditionStartValue>
          <ConditionStartValueType>0</ConditionStartValueType>
          <ConditionStartType>0</ConditionStartType>
          <DecimalContext1>{value}</DecimalContext1>
          <DecimalContext2>0</DecimalContext2>
          <DateContext1>0001-01-01T00:00:00</DateContext1>
          <DateContext2>0001-01-01T00:00:00</DateContext2>
          <Disabled>false</Disabled>
          <RandomSounds/>
          <ConditionExpressions/>
        </CommandAction>"""


def _command_envelope(cmd, actions_xml):
    cmd_id = new_guid()
    base_id = new_guid()
    trigger = escape(cmd["phrase"])
    category = escape(cmd["category"] or "")
    return f"""    <Command>
      <Referrer xsi:nil="true"/>
      <ExecType>3</ExecType>
      <Confidence>0</Confidence>
      <PrefixActionCount>0</PrefixActionCount>
      <IsDynamicallyCreated>false</IsDynamicallyCreated>
      <TargetProcessSet>false</TargetProcessSet>
      <TargetProcessType>0</TargetProcessType>
      <TargetProcessLevel>0</TargetProcessLevel>
      <CompareType>0</CompareType>
      <ExecFromWildcard>false</ExecFromWildcard>
      <IsSubCommand>false</IsSubCommand>
      <IsOverride>false</IsOverride>
      <BaseId>{base_id}</BaseId>
      <OriginId>00000000-0000-0000-0000-000000000000</OriginId>
      <SessionEnabled>true</SessionEnabled>
      <Id>{cmd_id}</Id>
      <CommandString>{trigger}</CommandString>
      <ActionSequence>
{actions_xml}
      </ActionSequence>
      <Async>true</Async>
      <Enabled>true</Enabled>
      <Category>{category}</Category>
      <UseShortcut>false</UseShortcut>
      <keyValue>0</keyValue>
      <keyShift>0</keyShift>
      <keyAlt>0</keyAlt>
      <keyCtrl>0</keyCtrl>
      <keyWin>0</keyWin>
      <keyPassthru>true</keyPassthru>
      <UseSpokenPhrase>true</UseSpokenPhrase>
      <onlyKeyUp>false</onlyKeyUp>
      <RepeatNumber>2</RepeatNumber>
      <RepeatType>0</RepeatType>
      <CommandType>0</CommandType>
      <SourceProfile>00000000-0000-0000-0000-000000000000</SourceProfile>
      <UseConfidence>false</UseConfidence>
      <minimumConfidenceLevel>0</minimumConfidenceLevel>
      <UseJoystick>false</UseJoystick>
      <joystickNumber>0</joystickNumber>
      <joystickButton>0</joystickButton>
      <joystickNumber2>0</joystickNumber2>
      <joystickButton2>0</joystickButton2>
      <joystickUp>false</joystickUp>
      <KeepRepeating>false</KeepRepeating>
      <UseProcessOverride>false</UseProcessOverride>
      <ProcessOverrideActiveWindow>true</ProcessOverrideActiveWindow>
      <LostFocusStop>false</LostFocusStop>
      <PauseLostFocus>false</PauseLostFocus>
      <LostFocusBackCompat>true</LostFocusBackCompat>
      <UseMouse>false</UseMouse>
      <Mouse1>false</Mouse1>
      <Mouse2>false</Mouse2>
      <Mouse3>false</Mouse3>
      <Mouse4>false</Mouse4>
      <Mouse5>false</Mouse5>
      <Mouse6>false</Mouse6>
      <Mouse7>false</Mouse7>
      <Mouse8>false</Mouse8>
      <Mouse9>false</Mouse9>
      <MouseUpOnly>false</MouseUpOnly>
      <MousePassThru>true</MousePassThru>
      <joystickExclusive>false</joystickExclusive>
      <UseProfileProcessOverride>false</UseProfileProcessOverride>
      <ProfileProcessOverrideActiveWindow>false</ProfileProcessOverrideActiveWindow>
      <RepeatIfKeysDown>false</RepeatIfKeysDown>
      <RepeatIfMouseDown>false</RepeatIfMouseDown>
      <RepeatIfJoystickDown>false</RepeatIfJoystickDown>
      <AH>0</AH>
      <CL>0</CL>
      <HasMB>false</HasMB>
      <UseVariableHotkey>false</UseVariableHotkey>
      <CLE>0</CLE>
      <EX1>false</EX1>
      <EX2>false</EX2>
      <InternalId xsi:nil="true"/>
      <HasInput>true</HasInput>
    </Command>"""


def _profile_xml(profile_id, name, commands_xml):
    return f"""<?xml version="1.0" encoding="utf-8"?>
<Profile xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:xsd="http://www.w3.org/2001/XMLSchema">
  <Id>{profile_id}</Id>
  <Name>{name}</Name>
  <Commands>
{commands_xml}
  </Commands>
  <OverrideGlobal>false</OverrideGlobal>
  <GlobalHotkeyIndex>0</GlobalHotkeyIndex>
  <GlobalHotkeyEnabled>false</GlobalHotkeyEnabled>
  <GlobalHotkeyValue>0</GlobalHotkeyValue>
  <GlobalHotkeyShift>0</GlobalHotkeyShift>
  <GlobalHotkeyAlt>0</GlobalHotkeyAlt>
  <GlobalHotkeyCtrl>0</GlobalHotkeyCtrl>
  <GlobalHotkeyWin>0</GlobalHotkeyWin>
  <GlobalHotkeyPassThru>false</GlobalHotkeyPassThru>
  <OverrideMouse>false</OverrideMouse>
  <MouseIndex>0</MouseIndex>
  <OverrideStop>false</OverrideStop>
  <StopCommandHotkeyEnabled>false</StopCommandHotkeyEnabled>
  <StopCommandHotkeyValue>0</StopCommandHotkeyValue>
  <StopCommandHotkeyShift>0</StopCommandHotkeyShift>
  <StopCommandHotkeyAlt>0</StopCommandHotkeyAlt>
  <StopCommandHotkeyCtrl>0</StopCommandHotkeyCtrl>
  <StopCommandHotkeyWin>0</StopCommandHotkeyWin>
  <StopCommandHotkeyPassThru>false</StopCommandHotkeyPassThru>
  <DisableShortcuts>false</DisableShortcuts>
  <UseOverrideListening>false</UseOverrideListening>
  <OverrideJoystickGlobal>false</OverrideJoystickGlobal>
  <GlobalJoystickIndex>0</GlobalJoystickIndex>
  <GlobalJoystickButton>0</GlobalJoystickButton>
  <GlobalJoystickNumber>0</GlobalJoystickNumber>
  <GlobalJoystickButton2>0</GlobalJoystickButton2>
  <GlobalJoystickNumber2>0</GlobalJoystickNumber2>
  <ReferencedProfile xsi:nil="true"/>
  <ExportVAVersion>1.10.0</ExportVAVersion>
  <ExportOSVersionMajor>10</ExportOSVersionMajor>
  <ExportOSVersionMinor>0</ExportOSVersionMinor>
  <OverrideConfidence>false</OverrideConfidence>
  <Confidence>0</Confidence>
  <CatchAllEnabled>false</CatchAllEnabled>
  <CatchAllId xsi:nil="true"/>
  <InitializeCommandEnabled>false</InitializeCommandEnabled>
  <InitializeCommandId xsi:nil="true"/>
  <UseProcessOverride>false</UseProcessOverride>
  <HasMB>false</HasMB>
</Profile>"""
