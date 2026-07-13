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
    "Launch", "Write", "SetClipboard", "SetDecimal",
    # Coverage row 2 (plan W5; carriers per WP-B's decode bindings + the verbatim s4
    # export samples): SetText->TextSet, SetBoolean->BooleanSet (literal modes only),
    # SetInteger->IntSet (LITERAL VALUE MODE ONLY), QuickInput->FreeType, and
    # SetSmallInt normalized to IntSet (VA2 merge ruling — see _action_xml).
    "SetText", "SetBoolean", "SetInteger", "SetSmallInt", "QuickInput",
    "BeginCondition", "ElseIf", "Else", "EndCondition",
    # Parameterless dark types (W5 close, plan D3 branch 0): XML ActionType strings
    # oracle-verified by the W5 Export (dictionary 0.5.0); no carriers, so each emits
    # via the default _ordinary_xml skeleton (all-default fields) with only its
    # xml_action_type varying. ExecuteCommand/KillCommand (by-GUID cross-ref),
    # PauseVariable/ExitCommand (decoder-parked operands), and SoundFile (single
    # sample) are ground-truthed in the dictionary but DEFERRED — deliberately absent.
    "DictationMode", "StopDictation", "ClearDictationBuffer",
    "StartListening", "StopListening",
}

# Canonicals that emit AS another canonical's XML string (audit truth, plan W6).
# SetSmallInt is WIRED but normalizes to IntSet on emit (VA2 merge — see _action_xml);
# it never emits its own "ConditionSet" string. The audit resolves emitted XML through
# this map so ConditionSet is not falsely credited as emitted.
EMIT_NORMALIZED = {"SetSmallInt": "SetInteger"}

# XML ActionType strings the dictionary knows but gen2 deliberately does NOT emit, each
# with a standing reason (audit parked-awareness, plan W6). This is DISTINCT from pending:
# a pending entry is emit-ready and should be adopted; a DEFERRED entry is parked by
# design. SetClipboard is deliberately absent — it is emit-ready, so the audit surfaces
# it as pending until it is wired or explicitly parked (a ruling, not a silent bury).
DEFERRED_XML = {
    "ExecuteCommand": "by-GUID cross-reference (name->GUID resolution) - future release",
    "KillCommand": "by-GUID cross-reference (name->GUID resolution) - future release",
    "WhileStart": "While-loop emission parked (plan D4) - future release",
    "WhileEnd": "While-loop emission parked (plan D4) - future release",
    "PauseVariable": "decoder parks operands (no round-trip coverage) - future release",
    "ExitCommand": "decoder parks operands (no round-trip coverage) - future release",
    "ConditionSet": "legacy VA1 Small-Int set; SetSmallInt normalizes to IntSet on emit "
                    "(VA2 merge) - decode-only, never emitted",
}

# Key-list family (shared template, Duration 0 by definition for the last three).
_KEY_FAMILY = {"PressKey", "KeyDown", "KeyUp", "KeyToggle"}
# Condition-family (block-structural): refusal granularity is the whole command.
_STRUCTURAL = {"BeginCondition", "ElseIf", "Else", "EndCondition", "BeginLoopWhile", "EndLoop"}
_COMPARES = {"BeginCondition", "ElseIf"}
_BRANCHES = {"ElseIf", "Else"}

_PLAIN_DECIMAL = re.compile(r"^-?\d+(\.\d+)?$")

# Control characters the XML 1.0 Char production cannot represent in ANY form
# (0x00-0x08, 0x0B, 0x0C, 0x0E-0x1F, plus 0x7F per the verify-wave-1 ruling); tab/LF/CR
# are legal and pass. escape() passes these through, so a permissive emit would produce
# an unimportable .vap while exiting 0 — unrepresentable input hard-fails instead
# (contract §3; verify wave 1 finding 1).
_XML_ILLEGAL = re.compile(r"[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]")


def new_guid():
    return str(uuid.uuid4())


def _xml_defect(value):
    """'U+00XX' codepoint label when a string carries a control character illegal in
    XML 1.0, else None (verify wave 1 finding 1)."""
    if isinstance(value, str):
        m = _XML_ILLEGAL.search(value)
        if m is not None:
            return "U+%04X" % ord(m.group(0))
    return None


def _check_xml_text(value, where):
    """Hard-fail when a string field carries a control character illegal in XML 1.0.
    Since the W5 fix-wave door split (finding 4 ruling), this hard-fail form guards
    profile name, phrases, categories, and condition fields; per-action PAYLOAD
    fields go through _payload_defect's lenient warn-and-drop instead."""
    cp = _xml_defect(value)
    if cp is not None:
        raise EmitError(
            "%s contains control character %s - illegal in XML 1.0, "
            "unrepresentable (hard-fail, no output file)" % (where, cp))


def emit(model, dictionary, warn=None):
    """Render a schema_input model to profile XML. Returns (xml_text, warnings).
    Raises EmitError on any hard-fail defect — the caller must not have written
    output. `warn`, when given, is called with each warning AS IT OCCURS, so a CLI
    can surface everything accumulated before a hard-fail (W5 fix wave, finding 4)."""
    warnings = []

    def _warn(msg):
        warnings.append(msg)
        if warn is not None:
            warn(msg)

    _check_xml_text(model["profile"].get("name"), "Profile name")
    command_chunks = []
    for cmd in model["commands"]:
        chunk = _command_xml(cmd, dictionary, _warn)
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

        canonical, type_problem = _resolve_canonical(rec.get("actionType") or {}, dictionary)
        if canonical is None:
            warn("Command '%s': action %d %s - cannot be proven non-structural; "
                 "refusing the whole command (contract §3)" % (phrase, idx, type_problem))
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

        if rec.get("fieldsDecoded") is False:
            # Recognized type, operands undecoded (binary parked layouts, e.g. every
            # binary SetSmallInt/QuickInput record) — nothing to rebuild from.
            warn("Command '%s': action %d '%s' decoded without operands "
                 "(fieldsDecoded: false) - emitting nothing for it (contract §3)"
                 % (phrase, idx, canonical))
            continue

        if canonical == "SetBoolean" and "valueSource" in rec:
            # Binary modes 2-6 (toggle/copy/random/saved/clear): no proven XML emit
            # carrier for non-literal sources (W5 tasking item 2).
            warn("Command '%s': action %d SetBoolean value-source mode %r has no "
                 "evidenced XML carrier (modes 2-6 unsampled) - emitting nothing for "
                 "it (contract §3; W5 export probe)" % (phrase, idx,
                 (rec.get("valueSource") or {}).get("mode")))
            continue

        if canonical == "SetInteger":
            unevidenced = [k for k in ("sourceVariable", "min", "max",
                                       "operation", "valueSource") if k in rec]
            # NAME COLLISION GUARD: "source" is BOTH the XML-path provenance
            # annotation ("xml") and the binary record's semantic value-source label
            # ("random"/"arithmetic"/...). Only the semantic form marks a mode.
            if rec.get("source") not in (None, "xml"):
                unevidenced.append("source")
            mode = rec.get("valueSourceMode")
            if unevidenced or mode not in (None, 0):
                # LITERAL VALUE MODE ONLY (W5 tasking item 3): the s4 IntSet sample
                # proves ConditionSetName/X for a literal value and nothing else;
                # random/variable/arithmetic operand carriers are unevidenced.
                warn("Command '%s': action %d SetInteger value-source mode %r "
                     "(record keys %s) has no evidenced XML carrier - literal value "
                     "mode only; emitting nothing for it (contract §3; pending the "
                     "W5 export probe)" % (phrase, idx, mode,
                                           unevidenced or ["valueSourceMode"]))
                continue

        if canonical in ("SetText", "QuickInput") and "valueSource" in rec:
            # Defense-in-depth (W5 fix wave, finding 2): no decode path emits a
            # value-source marker on these types today, but a record carrying one
            # alongside a plausible literal must NOT emit the literal and silently
            # drop the marker.
            warn("Command '%s': action %d %s carries a value-source marker (mode %r) "
                 "- no evidenced non-literal carrier; emitting nothing for it "
                 "(contract §3; W5 export probe)" % (phrase, idx, canonical,
                 (rec.get("valueSource") or {}).get("mode")))
            continue

        defect = _payload_defect(canonical, rec)
        if defect is not None:
            # Decoded-input degeneracy (W5 fix wave, finding 4 — XO ruling
            # 2026-07-13): non-structural payload defects on DECODED records drop
            # loudly and the rest of the profile survives (exit 2). Authored input
            # reaches emit only through lower.py, whose own validation hard-fails
            # the same defects (exit 1) — the door split.
            warn("Command '%s': action %d %s payload defect: %s - emitting nothing "
                 "for it (decoded-input degeneracy ruling 2026-07-13, contract §3)"
                 % (phrase, idx, canonical, defect))
            continue

        if canonical == "SetSmallInt":
            # SANCTIONED NORMALIZATION (plan row-2 note): VA2 merged Small Int into
            # Integer — this record re-emits as IntSet and will re-decode as
            # SetInteger. Loud by design; the name change is ruling, not drift.
            warn("Command '%s': action %d SetSmallInt re-emitted as IntSet per the "
                 "VA2 Small-Int/Integer merge (sanctioned normalization) - it will "
                 "re-decode as SetInteger" % (phrase, idx))

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
    """Record {code, name} -> (canonical dictionary name, None), or (None, reason) when
    the type must be refused. Names are the authority (contract §1); a code/name
    mismatch and an unknown code get DISTINCT refusal reasons (verify wave 1 finding 6)
    — neither is guessed around."""
    code = action_type.get("code")
    name = action_type.get("name")
    if code is not None and dictionary.action_entry(code) is not None:
        canonical = dictionary.canonical(code)
        if name is not None and name != canonical:
            return None, ("type code %r is dictionary type %r but the record names it %r "
                          "- code/name mismatch" % (code, canonical, name))
        return canonical, None
    if name is not None and dictionary.code_for_name(name) is not None:
        return name, None
    return None, "type (code %r, name %r) is not in the dictionary" % (code, name)


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


# --- phase 2: hard-fail validation (condition structure + command-level fields) ----

_I32_MIN, _I32_MAX = -(2 ** 31), 2 ** 31 - 1


def _payload_defect(canonical, rec):
    """Non-structural payload validation, lenient side of the W5 door split (finding
    4 ruling 2026-07-13): a defective payload on a DECODED record is a decoded-input
    degeneracy, not an authoring error — the router warns and drops the action so
    every healthy command still emits. The simple authoring door reaches emit only
    through lower.py, whose own validation hard-fails these same defects (exit 1).
    Returns a human-readable defect, or None when the payload is emittable."""
    def clean(value, field):
        cp = _xml_defect(value)
        if cp is not None:
            return "%s contains control character %s, illegal in XML 1.0" % (field, cp)
        return None

    if canonical == "SetDecimal":
        variable = rec.get("targetVariable")
        if not isinstance(variable, str) or not variable:
            return "requires a non-empty string 'targetVariable' (got %r)" % (variable,)
        value = rec.get("value")
        if isinstance(value, bool):
            return "requires a numeric 'value' (got %r)" % (value,)
        if isinstance(value, (int, float)):
            if not math.isfinite(value):
                return "requires a finite 'value' (got %r)" % (value,)
        elif isinstance(value, str):
            if not _PLAIN_DECIMAL.match(value):
                return "requires a plain decimal string 'value' (got %r)" % (value,)
        else:
            return "requires a numeric 'value' (got %r)" % (value,)
        return clean(variable, "'targetVariable'")
    if canonical in ("Write", "SetClipboard"):
        if not isinstance(rec.get("text"), str):
            return "requires a string 'text' (got %r)" % (rec.get("text"),)
        return clean(rec["text"], "'text'")
    if canonical == "Say":
        return clean(rec.get("text"), "'text'")
    if canonical == "Launch":
        for field in ("executablePath", "arguments", "workingDirectory"):
            defect = clean(rec.get(field), "'%s'" % field)
            if defect is not None:
                return defect
        return None
    if canonical == "SetText":
        variable = rec.get("targetVariable")
        if not isinstance(variable, str) or not variable:
            return "requires a non-empty string 'targetVariable' (got %r)" % (variable,)
        if "value" in rec and not isinstance(rec["value"], str):
            return "requires a string 'value' when present (got %r)" % (rec["value"],)
        return clean(variable, "'targetVariable'") or clean(rec.get("value"), "'value'")
    if canonical == "SetBoolean":
        variable = rec.get("targetVariable")
        if not isinstance(variable, str) or not variable:
            return "requires a non-empty string 'targetVariable' (got %r)" % (variable,)
        if not isinstance(rec.get("value"), bool):
            return "requires a boolean 'value' (got %r)" % (rec.get("value"),)
        return clean(variable, "'targetVariable'")
    if canonical in ("SetInteger", "SetSmallInt"):
        variable = rec.get("targetVariable")
        if not isinstance(variable, str) or not variable:
            return "requires a non-empty string 'targetVariable' (got %r)" % (variable,)
        value = rec.get("value")
        if isinstance(value, bool) or not isinstance(value, int):
            return "requires an integer 'value' (got %r)" % (value,)
        if not (_I32_MIN <= value <= _I32_MAX):
            # <X> is Int32 on both the serializer and the binary slot (W5 fix wave,
            # finding 3) — an out-of-range emit would pass xmllint and fail VA import.
            return ("'value' %d is outside Int32 [%d, %d] - VA's serializer would "
                    "reject the import" % (value, _I32_MIN, _I32_MAX))
        return clean(variable, "'targetVariable'")
    if canonical == "QuickInput":
        if not isinstance(rec.get("text"), str):
            return "requires a string 'text' (got %r)" % (rec.get("text"),)
        return clean(rec["text"], "'text'")
    return None


def _validate(plans, phrase, dictionary):
    def fail(msg):
        raise EmitError("Command '%s': %s" % (phrase, msg))

    def check_clean(value, action_name, field):
        _check_xml_text(value, "Command '%s': %s '%s'" % (phrase, action_name, field))

    stack = []  # one frame per open block: {"seen_else": bool}
    for canonical, rec in plans:
        if canonical not in _STRUCTURAL:
            # Per-action payload validation moved to routing's lenient
            # _payload_defect path (W5 fix wave, finding 4 door split); by the time
            # a non-structural plan reaches here its payload is emittable.
            continue

        cond = rec.get("condition")
        if canonical in _COMPARES:
            if not isinstance(cond, dict):
                fail("'%s' is missing a required 'condition' object" % canonical)
            left = cond.get("leftOperand")
            if not isinstance(left, str) or not left:
                fail("'%s' condition is missing a non-empty 'leftOperand'" % canonical)
            check_clean(left, canonical, "condition leftOperand")
            op_name = (cond.get("operator") or {}).get("name")
            if not dictionary.operator_is_valueless(op_name) and "value" not in cond:
                fail("'%s' condition is missing a 'value' key (only Has Been Set / "
                     "Has Not Been Set omit it)" % canonical)
            if "value" in cond:
                # The renderer coerces via str(); check the coerced form it will emit.
                check_clean(str(cond["value"]), canonical, "condition value")

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
    _check_xml_text(cmd["phrase"], "Command %r: phrase" % (cmd["phrase"],))
    _check_xml_text(cmd["category"], "Command '%s': category" % (cmd["phrase"],))
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
    if canonical == "SetText":
        return _text_set_xml(rec, ordinal, indent)
    if canonical in ("SetInteger", "SetSmallInt"):
        # SANCTIONED NORMALIZATION (plan row-2 note / W5 tasking item 4): VA2 merged
        # Small Int into Integer, so a decoded SetSmallInt record re-emits with the
        # IntSet carriers and re-decodes as SetInteger. This canonical-name change
        # across the round trip is by ruling, not drift — fixpoint comparisons over
        # SmallInt-bearing profiles must treat it as sanctioned when those profiles
        # graduate to the fixture set.
        xml_type = dictionary.xml_action_type(dictionary.code_for_name("SetInteger"))
        return _int_set_xml(xml_type, rec, ordinal, indent)

    duration_str = "0"
    context = ""
    x = y = z = "0"
    dc1 = "0"
    input_mode = "0"
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
    elif canonical == "SetClipboard":
        # SetClipboard (24): text carrier is Context, identical to Write (dictionary
        # note; binary code + layout closed by Probe B). No other field.
        context = escape(rec["text"])
    elif canonical == "SetBoolean":
        # BooleanSet (s4 samples, both polarities): target Context, value InputMode
        # (0=True, 1=False — the binary m[14] enum exactly). Non-literal modes were
        # refused in routing.
        context = escape(rec["targetVariable"])
        input_mode = "0" if rec["value"] else "1"
    elif canonical == "QuickInput":
        # FreeType (s4 sample): text Context (variable tokens legal), Duration =
        # perKeyDelay seconds (WP-B's coined name; W7 docs list). InputMode reads 1
        # on both banked samples — semantics unverified, mirrored verbatim.
        # W7 docs note: perKeyDelay 0 emits Duration 0 and re-decodes with the key
        # ABSENT (the decode's truthy gate) — sanctioned normalization, same family
        # as clickDuration.
        context = escape(rec["text"])
        duration_str = _format_duration(rec.get("perKeyDelay", 0), warn)
        input_mode = "1"
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
            if rec.get("clickDuration"):
                # Binary m[4] is read unconditionally, so a Move record can carry a
                # click duration; emit it alongside X/Y rather than dropping it silently
                # (verify wave 1 finding 3). The Move+Duration XML carrier is INFERRED
                # pending the W5 export confirmation.
                duration_str = _format_duration(rec["clickDuration"], warn)
        elif rec.get("clickDuration") is not None:
            duration_str = _format_duration(rec["clickDuration"], warn)

    return _ordinary_xml(xml_type, ordinal, indent, duration_str, key_codes_xml,
                         context, x, y, z, dc1, input_mode)


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
                  context, x, y, z, decimal_context1, input_mode="0"):
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
          <InputMode>{input_mode}</InputMode>
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


def _text_set_xml(rec, ordinal, indent_level):
    """TextSet (s4_textset sample carriers): target variable in Context, value in
    Context2 (xml:space=preserve). Present-vs-absent honored both directions: the
    Context2 element is emitted only when the record carries a value key (a decoded
    present-but-empty value emits an EMPTY Context2), mirroring the decode binding."""
    action_id = new_guid()
    context = escape(rec["targetVariable"])
    extra = ""
    if "value" in rec:
        extra = f"\n          <Context2 xml:space=\"preserve\">{escape(rec['value'])}</Context2>"
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
          <ActionType>TextSet</ActionType>
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


def _int_set_xml(xml_type, rec, ordinal, indent_level):
    """IntSet (s4_intset sample carriers): target variable in ConditionSetName
    (xml:space=preserve), literal value in X — literal mode only (routing refused the
    rest). The real-world sample carries STALE author strings in Context/Context2 (the
    dictionary's stale-slot hazard); this template emits clean elements — no Context,
    no Context2 — on the proven DecimalSet skeleton, never mirroring stale slots.
    Serves SetInteger AND SetSmallInt (sanctioned normalization, see _action_xml)."""
    action_id = new_guid()
    variable = escape(rec["targetVariable"])
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
          <ActionType>{xml_type}</ActionType>
          <Duration>0</Duration>
          <Delay>0</Delay>
          <KeyCodes/>
          <X>{rec["value"]}</X>
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
