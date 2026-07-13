"""Lowering layer (plan W4): simple authoring format -> schema-v1.1 model.

One pipeline, two doors (plan §3): simple JSON enters here and lowers to the same model
`schema_input.parse` produces from decoded JSON; `emit_profile` is the single dumb
emitter behind both. Lowering owns ALL authoring conveniences — key-name/mouse tables
(dictionary-resolved), `key`/`mouse` shorthand, `_section` markers, defaults (PressKey
duration 0.1, Pause 0.5, category "general"), and the overloaded-trigger idiom compiler.

Authorities: CLAUDE.md "Generator JSON Format" (documentation) and vap_generator.py
2.0.0's parsing code (behavioral ground truth — its warning texts and hard-fail rules
are mirrored here so the wrapper CLI is drop-in). Authoring defects that legacy
hard-failed (malformed condition objects, SetDecimal/Write shapes) raise LoweringError:
exit-1 class, no output file.

The idiom compiler implements the contract's Ends With ruling + 2026-07-12 multi-group
amendment (schema/VAP_Round_Trip_Contract.md): the trigger's FINAL bracket group anchors
with Ends With; a dispatch group followed by anything lowers with ordered Contains.
Token-collision detection is mandatory — shadowed tokens reorder longest-first when that
resolves the shadow, duplicates hard-refuse naming the tokens. Detection is deliberately
conservative (build spec W4): false positives are worse than misses. Every firing is
reported on the INFO channel with the full alternative->action mapping — never silent.
"""

import itertools
import re


class LoweringError(Exception):
    """Authoring defect in the simple format (legacy hard-fail class, incl. idiom token
    collisions that ordering cannot resolve). Exit 1, no output file."""


# Condition-object shape (mirrors vap_generator.py CONDITION_KEYS).
_CONDITION_KEYS = {"valueType", "operator", "leftOperand", "value"}
_CONDITION_TYPES = {"BeginCondition", "ElseIf", "Else", "EndCondition"}
_KEY_TYPES = {"PressKey", "KeyDown", "KeyUp", "KeyToggle"}
_SIMPLE_TYPES = _KEY_TYPES | _CONDITION_TYPES | {
    "MouseAction", "Pause", "Say", "SetDecimal", "Write",
    # W5 row-2 authoring verbs. NO SetSmallInt here: it is legacy-in (decoded
    # profiles), never authored-out — VA2 merged Small Int into Integer.
    "SetText", "SetBoolean", "SetInteger", "QuickInput"}

_GROUP_RE = re.compile(r"\[([^\[\]]*)\]")
_DISPATCH_OPERAND = "{LASTSPOKENCMD}"


def lower_profile(profile_data, dictionary, no_idiom=False):
    """Simple-format document -> (schema model, info lines, warning lines).

    The model is the same shape schema_input.parse returns; infos are the idiom
    compiler's visibility lines (they do NOT count as warnings — auto-lowering is the
    D2 default, not a defect); warnings mirror legacy warn() texts."""
    if isinstance(profile_data, dict) and "schema_version" in profile_data:
        # Wrong door (W4 fix-wave finding 4): schema_version marks a schema-JSON
        # (decoded) document — that input enters the pipeline at stage two.
        raise LoweringError(
            "input carries schema_version %r - this is a schema-JSON (decoded) "
            "document, not the simple authoring format; encode it with "
            "python3 -m gen2 <input.json> <output.vap> instead"
            % (profile_data.get("schema_version"),))
    infos = []
    warnings = []
    commands = []
    for cmd in profile_data.get("commands", []):
        if "_section" in cmd:
            continue
        commands.append(_lower_command(cmd, dictionary, no_idiom,
                                       infos.append, warnings.append))
    return ({"profile": {"id": profile_data.get("id"),
                         "name": profile_data.get("name", "Generated Profile")},
             "commands": commands},
            infos, warnings)


def _lower_command(cmd, dictionary, no_idiom, info, warn):
    trigger = cmd.get("trigger", "unnamed command")
    actions = cmd.get("actions", [])
    if not actions:
        actions = _shorthand_actions(cmd, dictionary, trigger, warn)

    fires, veto = _idiom_detect(cmd, actions, trigger, no_idiom)
    if veto is not None:
        # Unmodelable trigger grammar on an otherwise idiom-shaped command (closure
        # wave item 2): never emit a chain verified against garbage utterances.
        warn("Command '%s': overloaded-trigger idiom not applied - %s; passing the "
             "command through untouched" % (trigger, veto))
    elif fires:
        lowered = _compile_idiom(cmd, actions, trigger, info, warn)
        if lowered is not None:
            actions = lowered

    records = []
    for a in actions:
        rec = _lower_action(a, dictionary, trigger, warn)
        if rec is not None:
            records.append(rec)

    return {"phrase": trigger,
            "category": cmd.get("category", "general"),
            "actions": records}


def _shorthand_actions(cmd, dictionary, trigger, warn):
    """`key`/`mouse` shorthand expansion (vap_generator.py command_xml verbatim)."""
    if "key" in cmd:
        key = cmd["key"]
        if isinstance(key, int) and not isinstance(key, bool):
            pass  # raw VK code given as a JSON number - always valid
        elif not isinstance(key, str) or (
                key.lower() not in dictionary.key_vk_by_name and not key.isdigit()):
            warn("Command '%s': unknown key '%s' - command will have no action"
                 % (trigger, key))
        return [{"type": "PressKey", "keys": [key],
                 "duration": cmd.get("duration", 0.1)}]
    if "mouse" in cmd:
        return [{"type": "MouseAction", "action": cmd["mouse"]}]
    warn("Command '%s': no key, mouse, or actions defined" % trigger)
    return []


# --- per-action lowering -------------------------------------------------------------

def _lower_action(action, dictionary, trigger, warn):
    a_type = action.get("type", "PressKey")
    if a_type not in _SIMPLE_TYPES:
        # Mirrors legacy warn-and-skip; Launch et al. stay outside the simple format
        # this wave (schema-JSON input reaches them through the other door).
        warn("Unknown action type '%s' - skipped" % a_type)
        return None

    if "delay" in action and action.get("delay"):
        # Legacy rendered a stray nonzero "delay" into <Delay>; schema v1.1 has no
        # delay field, so the new pipeline cannot carry it (undocumented key).
        warn("Command '%s': action 'delay' %r is not part of the simple format contract "
             "and is dropped by the lowering pipeline (use --legacy-emit if you rely "
             "on it)" % (trigger, action["delay"]))

    rec = {"actionType": {"code": dictionary.code_for_name(_canonical(a_type)),
                          "name": _canonical(a_type)}}

    if a_type in _KEY_TYPES:
        rec["keyCodes"] = _lower_keys(action.get("keys", []), dictionary, warn)
        if a_type == "PressKey":
            rec["duration"] = action.get("duration", 0.1)
        return rec
    if a_type == "Pause":
        rec["duration"] = action.get("duration", 0.5)
        return rec
    if a_type == "Say":
        rec["text"] = action.get("text", "")
        rec["volume"] = action.get("volume", 100)
        rec["rate"] = action.get("rate", 0)
        return rec
    if a_type == "MouseAction":
        rec["action"] = str(action.get("action", "left_click")).lower()
        if "scroll_clicks" in action:
            rec["scroll_clicks"] = action["scroll_clicks"]
        if "duration" in action:
            rec["clickDuration"] = action["duration"]
        return rec
    if a_type == "SetDecimal":
        variable = action.get("variable")
        if not isinstance(variable, str) or not variable:
            _fail(trigger, "'SetDecimal' requires a non-empty string 'variable'")
        rec["targetVariable"] = variable
        rec["value"] = action.get("value")  # emit_profile hard-validates numeric/finite
        return rec
    if a_type == "Write":
        if not isinstance(action.get("text"), str):
            _fail(trigger, "'Write' requires a string 'text' (empty string is legal)")
        rec["text"] = action["text"]
        return rec
    if a_type == "SetText":
        variable = action.get("variable")
        if not isinstance(variable, str) or not variable:
            _fail(trigger, "'SetText' requires a non-empty string 'variable'")
        if not isinstance(action.get("value"), str):
            _fail(trigger, "'SetText' requires a string 'value' (empty string is legal)")
        rec["targetVariable"] = variable
        rec["value"] = action["value"]
        return rec
    if a_type == "SetBoolean":
        variable = action.get("variable")
        if not isinstance(variable, str) or not variable:
            _fail(trigger, "'SetBoolean' requires a non-empty string 'variable'")
        if not isinstance(action.get("value"), bool):
            _fail(trigger, "'SetBoolean' requires a boolean 'value' (true or false; "
                           "got %r)" % (action.get("value"),))
        rec["targetVariable"] = variable
        rec["value"] = action["value"]
        return rec
    if a_type == "SetInteger":
        variable = action.get("variable")
        if not isinstance(variable, str) or not variable:
            _fail(trigger, "'SetInteger' requires a non-empty string 'variable'")
        value = action.get("value")
        if isinstance(value, bool) or not isinstance(value, int):
            _fail(trigger, "'SetInteger' requires an integer 'value' (got %r)"
                  % (value,))
        rec["targetVariable"] = variable
        rec["value"] = value
        return rec
    if a_type == "QuickInput":
        if not isinstance(action.get("text"), str):
            _fail(trigger, "'QuickInput' requires a string 'text' (empty string is "
                           "legal)")
        rec["text"] = action["text"]
        if "per_key_delay" in action:
            delay = action["per_key_delay"]
            if (isinstance(delay, bool) or not isinstance(delay, (int, float))
                    or delay < 0):
                _fail(trigger, "'QuickInput' requires a non-negative numeric "
                               "'per_key_delay' (got %r)" % (delay,))
            rec["perKeyDelay"] = delay
        return rec

    # Condition markers.
    if a_type in ("BeginCondition", "ElseIf"):
        rec["condition"] = _lower_condition(action, a_type, dictionary, trigger)
    elif "condition" in action and action["condition"] is not None:
        _fail(trigger, "'%s' must not carry a 'condition' object" % a_type)
    return rec


def _canonical(a_type):
    # Simple-format type names equal the dictionary canonicals for every wired type.
    return a_type


def _lower_condition(action, a_type, dictionary, trigger):
    """Simple condition object -> schema condition record, with vap_generator.py's
    hard-fail validation (its _validate_actions wording preserved)."""
    condition = action.get("condition")
    if condition is None:
        _fail(trigger, "'%s' is missing a required 'condition' object" % a_type)
    if not isinstance(condition, dict):
        _fail(trigger, "'%s' condition must be an object" % a_type)
    unknown = set(condition) - _CONDITION_KEYS
    if unknown:
        _fail(trigger, "'%s' condition has unknown key(s): %s" % (a_type, sorted(unknown)))
    value_type = condition.get("valueType")
    if value_type != "Text":
        _fail(trigger,
              "'%s' condition valueType '%s' is not supported - v1 supports Text only "
              "(Integer/Decimal XML carriers are unverified)" % (a_type, value_type))
    left_operand = condition.get("leftOperand")
    if not isinstance(left_operand, str) or not left_operand:
        _fail(trigger, "'%s' condition is missing a non-empty 'leftOperand'" % a_type)
    if "value" not in condition:
        _fail(trigger, "'%s' condition is missing a 'value' key (use \"\" for an empty "
                       "compare value)" % a_type)
    operator = condition.get("operator")
    op_index = dictionary.operator_index("Text", operator)
    if op_index is None:
        _fail(trigger, "'%s' condition has unknown operator '%s' - Text operators are: %s"
              % (a_type, operator, ", ".join(dictionary.operators["Text"])))
    return {"valueType": {"code": dictionary.value_type_code("Text"), "name": "Text"},
            "operator": {"code": op_index, "name": operator},
            "leftOperand": left_operand,
            "value": condition["value"]}


def _lower_keys(keys, dictionary, warn):
    if isinstance(keys, str):
        keys = [keys]
    out = []
    for k in keys:
        if isinstance(k, int) and not isinstance(k, bool):
            out.append({"vk": k, "name": dictionary.key_name_by_vk.get(k, "VK_%d" % k)})
            continue
        k_lower = k.lower() if isinstance(k, str) else k
        vk = dictionary.key_vk_by_name.get(k_lower) if isinstance(k_lower, str) else None
        if vk is not None:
            out.append({"vk": vk, "name": dictionary.key_name_by_vk.get(vk, k_lower)})
        elif isinstance(k, str) and k.isdigit():
            out.append({"vk": int(k), "name": dictionary.key_name_by_vk.get(int(k), k)})
        else:
            warn("Unknown key '%s' - ignored" % (k,))
    return out


def _fail(trigger, msg):
    raise LoweringError("Command '%s': %s" % (trigger, msg))


# --- the idiom compiler ----------------------------------------------------------------

_RANGE_RE = re.compile(r"^(\d+)\.\.(\d+)$")


def _parse_trigger(trigger):
    """Shared trigger-grammar parser for detection AND enumeration — one reading of
    the trigger, so the two can never drift (closure wave item 3's root concern).

    Returns (segments, problem). segments alternate ("text", str) and ("group",
    {"tokens": [...], "has_empty": bool}) in trigger order; group tokens are stripped,
    non-empty, and have VA's `N..M` numeric-range wildcard EXPANDED (corinthian CSV
    oracle: `[1..4;]` -> 1,2,3,4 plus omission). problem is a reason string when the
    grammar cannot be modeled — nested/unmatched brackets, range forms VA's behavior
    is unverified for — and the idiom must be vetoed (warn + pass through untouched,
    closure wave items 1-2)."""
    depth = 0
    for ch in trigger:
        if ch == "[":
            depth += 1
            if depth > 1:
                return None, "trigger has nested brackets (VA legality unknown)"
        elif ch == "]":
            depth -= 1
            if depth < 0:
                return None, "trigger has an unmatched ']'"
    if depth != 0:
        return None, "trigger has an unmatched '['"

    segments = []
    pos = 0
    for m in _GROUP_RE.finditer(trigger):
        if trigger[pos:m.start()]:
            segments.append(("text", trigger[pos:m.start()]))
        raw = [t.strip() for t in m.group(1).split(";")]
        tokens = []
        for t in raw:
            if not t:
                continue
            rm = _RANGE_RE.match(t)
            if rm:
                lo, hi = rm.group(1), rm.group(2)
                if str(int(lo)) != lo or str(int(hi)) != hi:
                    return None, ("zero-padded numeric range '%s' (VA behavior "
                                  "unverified)" % t)
                if int(lo) > int(hi):
                    return None, ("descending numeric range '%s' (VA behavior "
                                  "unverified)" % t)
                if int(hi) - int(lo) + 1 > _UTTERANCE_CAP:
                    return None, ("numeric range '%s' expands past the %d-utterance "
                                  "cap" % (t, _UTTERANCE_CAP))
                tokens.extend(str(v) for v in range(int(lo), int(hi) + 1))
            elif ".." in t:
                return None, ("range-like token '%s' is not plain N..M (VA behavior "
                              "unverified)" % t)
            else:
                tokens.append(t)
        segments.append(("group", {"tokens": tokens,
                                   # from RAW tokens: range expansion grows `tokens`,
                                   # so a length comparison would mask the omission
                                   "has_empty": any(not t for t in raw)}))
        pos = m.end()
    if trigger[pos:]:
        segments.append(("text", trigger[pos:]))
    return segments, None


def _is_dispatch_group(group):
    """An alternative (dispatch-capable) group: >=2 tokens after range expansion and
    NO empty token (a trailing empty token is the optional-word syntax `[word;]`)."""
    return len(group["tokens"]) >= 2 and not group["has_empty"]


def _alternative_groups(segments):
    """[(tokens, is_final)] for every dispatch-capable group. is_final: nothing but
    whitespace follows the group — the amendment's Ends With / Contains switch."""
    out = []
    for i, (kind, payload) in enumerate(segments):
        if kind != "group" or not _is_dispatch_group(payload):
            continue
        rest = segments[i + 1:]
        is_final = all(k == "text" and not t.strip() for k, t in rest)
        out.append((payload["tokens"], is_final))
    return out


def _idiom_detect(cmd, actions, trigger, no_idiom):
    """The conservative detection predicate (build spec W4): fire ONLY when the command
    has an explicit actions list of length N>=2, the trigger has exactly ONE alternative
    bracket group and it has exactly N alternatives AFTER range expansion (a range in
    the dispatch group changes the count and the exact-N match sees the expanded count
    — never a miscount), every action has the SAME type (a KeyDown/PressKey/KeyUp chord
    must never be split), none is a condition marker, and the command is not opted out
    (`"idiom": false`, or the global --no-idiom).

    Returns (fires, veto_reason): (True, None) to compile; (False, None) to pass
    through silently; (False, reason) when the command is idiom-shaped but the trigger
    grammar cannot be modeled — the caller warns and passes through untouched."""
    if no_idiom or cmd.get("idiom") is False:
        return False, None
    if not isinstance(cmd.get("actions"), list) or len(actions) < 2:
        return False, None
    if not all(isinstance(a, dict) for a in actions):
        return False, None
    types = {a.get("type", "PressKey") for a in actions}
    if len(types) != 1 or types & _CONDITION_TYPES:
        return False, None
    if next(iter(types)) not in _SIMPLE_TYPES:
        # Every branch action would be refused downstream — an empty Begin/ElseIf/End
        # shell helps nobody; pass through so the refusals land as plain warnings
        # (W4 fix-wave finding 5).
        return False, None
    if all(a == actions[0] for a in actions[1:]):
        # An overload whose branches are IDENTICAL is meaningless (the double-tap
        # case) — the same action fires either way; leave the command alone
        # (W4 fix-wave finding 3; the chord-split hazard stays on the W7 ruling list).
        return False, None
    segments, problem = _parse_trigger(trigger)
    if problem is not None:
        return False, problem
    groups = _alternative_groups(segments)
    if len(groups) != 1 or len(groups[0][0]) != len(actions):
        return False, None
    return True, None


def _compile_idiom(cmd, actions, trigger, info, warn):
    """Lower N alternatives x N parallel actions into a {LASTSPOKENCMD} dispatch chain
    (contract ruling + amendment): final group -> Ends With; a group followed by
    anything -> ordered Contains. The branch order is PROVEN by dispatch simulation
    before anything is emitted (W4 fix-wave ruling, finding 1). Returns the lowered
    action list, or None when the idiom must not apply (utterance-cap veto) — the
    caller then passes the command through untouched, which honestly restores exactly
    what the author wrote."""
    segments, problem = _parse_trigger(trigger)
    assert problem is None, "unmodelable trigger reached compile: %s" % problem
    tokens, final = _alternative_groups(segments)[0]
    operator = "Ends With" if final else "Contains"

    utterances, count = _trigger_utterances(segments)
    if utterances is None:
        warn("Command '%s': overloaded-trigger idiom not applied - the trigger expands "
             "to %d utterances (cap %d), too many to verify dispatch; passing the "
             "command through untouched" % (trigger, count, _UTTERANCE_CAP))
        return None
    tagged = [(spoken, token) for spoken, token in utterances if token is not None]
    if not tagged:
        # Hard guard (closure wave item 3): a vacuous simulation must be impossible —
        # "verified over 0 utterances" is unprintable by construction. Tripping this
        # means the parser/detector disagreed about which group dispatches.
        raise LoweringError(
            "Command '%s': overloaded-trigger idiom produced no dispatch-tagged "
            "utterances (enumerator/detector drift) - refusing rather than emit an "
            "unverified chain" % trigger)

    branches = _order_branches(list(zip(tokens, actions)), suffix_mode=final,
                               trigger=trigger, operator=operator,
                               utterances=tagged)

    lowered = []
    for i, (token, action) in enumerate(branches):
        lowered.append({
            "type": "BeginCondition" if i == 0 else "ElseIf",
            "condition": {"valueType": "Text", "operator": operator,
                          "leftOperand": _DISPATCH_OPERAND, "value": token}})
        lowered.append(action)
    lowered.append({"type": "EndCondition"})

    # Printable ONLY for a simulation-proven chain: _order_branches has already raised
    # on any order the simulation could not verify (finding 1 sub-rule 5).
    info("Command '%s': overloaded-trigger idiom lowered to a %s dispatch chain "
         "(verified over %d utterances): %s"
         % (trigger, operator, len(tagged),
            "; ".join("'%s' -> %s" % (t, _describe(a)) for t, a in branches)))
    return lowered


# Static-enumeration cap (W4 fix-wave ruling): a trigger whose grammar expands beyond
# this is not verifiable at sane cost — the idiom does NOT fire (warn + pass through).
_UTTERANCE_CAP = 512


def _trigger_utterances(segments):
    """Statically enumerate every spoken phrase the parsed trigger grammar produces,
    tagged with the dispatch-group token each one chose (None on non-dispatch
    segments). Returns (utterances, count); (None, count) past _UTTERANCE_CAP.

    Text fidelity matches VA's own CSV expansion oracle EXACTLY (closure wave items
    4-5): authored spacing — including a trailing space — is preserved verbatim; an
    OMITTED optional group absorbs exactly one adjacent space (right first, then
    left, skipping other omissions), which is how VA prints `[inch;] Climb [1..4;]`
    as "Climb", "Climb 1", "inch Climb 1", ...

    VA matches {LASTSPOKENCMD} against the FULL recognized phrase, so a token can
    collide with the fixed prefix, the fixed tail, optional-group text, and across
    word boundaries — which is exactly why collision analysis must happen at the
    utterance level, never token-vs-token (verifier findings A/B/C/D/M)."""
    option_lists = []
    group_positions = []
    for kind, payload in segments:
        if kind == "text":
            option_lists.append([(payload, None)])
            continue
        group_positions.append(len(option_lists))
        dispatch = _is_dispatch_group(payload)
        options = [(t, t if dispatch else None) for t in payload["tokens"]]
        if payload["has_empty"] or not options:
            options.append(("", None))
        option_lists.append(options)

    count = 1
    for options in option_lists:
        count *= len(options)
    if count > _UTTERANCE_CAP:
        return None, count

    out = []
    for combo in itertools.product(*option_lists):
        spoken = _join_spoken([text for text, _ in combo], group_positions)
        chosen = [token for _, token in combo if token is not None]
        out.append((spoken, chosen[0] if chosen else None))
    return out, count


def _join_spoken(pieces, group_positions):
    """Join utterance pieces the way VA prints them: each OMITTED group (empty piece)
    absorbs one adjacent space — the one following it if present, else the one ending
    the nearest non-empty piece to its left. Nothing else is normalized: authored
    spacing (runs, trailing space) survives verbatim, per the CSV oracle."""
    pieces = list(pieces)
    for i in group_positions:
        if pieces[i] != "":
            continue
        j = i + 1
        while j < len(pieces) and pieces[j] == "":
            j += 1
        if j < len(pieces) and pieces[j][:1] == " ":
            pieces[j] = pieces[j][1:]
            continue
        j = i - 1
        while j >= 0 and pieces[j] == "":
            j -= 1
        if j >= 0 and pieces[j][-1:] == " ":
            pieces[j] = pieces[j][:-1]
    return "".join(pieces)


def _order_branches(pairs, suffix_mode, trigger, operator, utterances):
    """Deterministic candidate orders per the W4 fix-wave ruling: input order first,
    then longest-token-first (stable); EACH candidate is verified by simulating the
    compiled chain over every utterance the trigger produces. The first candidate the
    simulation proves is used; if none survives, HARD-REFUSE naming the colliding
    token and the utterance that breaks it. Identical tokens are refused up front
    (no order can ever separate them)."""
    lowered_tokens = [t.lower() for t, _ in pairs]
    dupes = sorted({t for t in lowered_tokens if lowered_tokens.count(t) > 1})
    if dupes:
        raise LoweringError(
            "Command '%s': overloaded-trigger idiom cannot dispatch - duplicate "
            "alternative token(s) %s collide under %s and no branch order can resolve "
            "them" % (trigger, dupes, operator))

    candidates = [list(pairs),
                  sorted(pairs, key=lambda p: -len(p[0]))]  # stable: ties keep input order
    failure = None
    for candidate in candidates:
        failure = _simulate_dispatch(candidate, suffix_mode, utterances)
        if failure is None:
            return candidate

    spoken, intended, captured = failure
    raise LoweringError(
        "Command '%s': overloaded-trigger idiom cannot dispatch safely - spoken phrase "
        "'%s' (meant for alternative '%s') is captured by token %s under %s in every "
        "candidate branch order; write the conditional explicitly or rename the "
        "alternatives" % (trigger, spoken, intended,
                          "'%s'" % captured if captured is not None else "no branch",
                          operator))


def _simulate_dispatch(branches, suffix_mode, utterances):
    """VA-runtime dispatch model: {LASTSPOKENCMD} is the full spoken phrase; Ends With
    is str.endswith, Contains is substring; branches are tested in order and the first
    match fires (case-insensitive, VA's text-compare default). Returns None when every
    utterance fires its OWN branch, else (spoken, intended_token, captured_token)."""
    for spoken, intended in utterances:
        s = spoken.lower()
        fired = None
        for token, _ in branches:
            t = token.lower()
            if (s.endswith(t) if suffix_mode else t in s):
                fired = token
                break
        if fired is None or fired.lower() != intended.lower():
            return (spoken, intended, fired)
    return None


def _describe(action):
    a_type = action.get("type", "PressKey")
    if a_type in _KEY_TYPES:
        keys = action.get("keys", [])
        return "%s[%s]" % (a_type, ", ".join(str(k) for k in
                                             (keys if isinstance(keys, list) else [keys])))
    if a_type == "MouseAction":
        return "MouseAction[%s]" % action.get("action", "left_click")
    return a_type
