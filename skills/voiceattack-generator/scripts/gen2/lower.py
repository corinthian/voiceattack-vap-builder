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

import re


class LoweringError(Exception):
    """Authoring defect in the simple format (legacy hard-fail class, incl. idiom token
    collisions that ordering cannot resolve). Exit 1, no output file."""


# Condition-object shape (mirrors vap_generator.py CONDITION_KEYS).
_CONDITION_KEYS = {"valueType", "operator", "leftOperand", "value"}
_CONDITION_TYPES = {"BeginCondition", "ElseIf", "Else", "EndCondition"}
_KEY_TYPES = {"PressKey", "KeyDown", "KeyUp", "KeyToggle"}
_SIMPLE_TYPES = _KEY_TYPES | _CONDITION_TYPES | {
    "MouseAction", "Pause", "Say", "SetDecimal", "Write"}

_GROUP_RE = re.compile(r"\[([^\[\]]*)\]")
_DISPATCH_OPERAND = "{LASTSPOKENCMD}"


def lower_profile(profile_data, dictionary, no_idiom=False):
    """Simple-format document -> (schema model, info lines, warning lines).

    The model is the same shape schema_input.parse returns; infos are the idiom
    compiler's visibility lines (they do NOT count as warnings — auto-lowering is the
    D2 default, not a defect); warnings mirror legacy warn() texts."""
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

    if _idiom_fires(cmd, actions, trigger, no_idiom):
        actions = _compile_idiom(cmd, actions, trigger, info)

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

def _alternative_groups(trigger):
    """Bracket groups with >=2 non-empty tokens and NO empty token (a trailing empty
    token is the optional-word syntax `[word;]`, never a dispatch alternative).
    Returns [(tokens, chars_after_group)] in trigger order."""
    out = []
    for m in _GROUP_RE.finditer(trigger):
        tokens = [t.strip() for t in m.group(1).split(";")]
        if len(tokens) >= 2 and all(tokens):
            out.append((tokens, trigger[m.end():]))
    return out


def _idiom_fires(cmd, actions, trigger, no_idiom):
    """The conservative detection predicate (build spec W4): fire ONLY when the command
    has an explicit actions list of length N>=2, the trigger has exactly ONE alternative
    bracket group and it has exactly N alternatives, every action has the SAME type (a
    KeyDown/PressKey/KeyUp chord must never be split), none is a condition marker, and
    the command is not opted out (`"idiom": false`, or the global --no-idiom).
    Anything else passes through untouched."""
    if no_idiom or cmd.get("idiom") is False:
        return False
    if not isinstance(cmd.get("actions"), list) or len(actions) < 2:
        return False
    if not all(isinstance(a, dict) for a in actions):
        return False
    types = {a.get("type", "PressKey") for a in actions}
    if len(types) != 1 or types & _CONDITION_TYPES:
        return False
    groups = _alternative_groups(trigger)
    if len(groups) != 1 or len(groups[0][0]) != len(actions):
        return False
    return True


def _compile_idiom(cmd, actions, trigger, info):
    """Lower N alternatives x N parallel actions into a {LASTSPOKENCMD} dispatch chain
    (contract ruling + amendment): final group -> Ends With; a group followed by
    anything -> ordered Contains with substring-shadow handling."""
    tokens, after = _alternative_groups(trigger)[0]
    final = after.strip() == ""
    operator = "Ends With" if final else "Contains"
    branches = _order_branches(list(zip(tokens, actions)), suffix_mode=final,
                               trigger=trigger, operator=operator)

    lowered = []
    for i, (token, action) in enumerate(branches):
        lowered.append({
            "type": "BeginCondition" if i == 0 else "ElseIf",
            "condition": {"valueType": "Text", "operator": operator,
                          "leftOperand": _DISPATCH_OPERAND, "value": token}})
        lowered.append(action)
    lowered.append({"type": "EndCondition"})

    info("Command '%s': overloaded-trigger idiom lowered to a %s dispatch chain: %s"
         % (trigger, operator,
            "; ".join("'%s' -> %s" % (t, _describe(a)) for t, a in branches)))
    return lowered


def _order_branches(pairs, suffix_mode, trigger, operator):
    """Branch order follows input order EXCEPT where a token shadows another (contract):
    under Ends With only a suffix shadows; under Contains any substring shadows. A
    shadowing pair reorders longest-first (minimal disturbance: the longer token moves
    just ahead of the token it shadows); identical tokens cannot be resolved by ordering
    and hard-refuse naming the collision."""
    lowered_tokens = [t.lower() for t, _ in pairs]
    dupes = sorted({t for t in lowered_tokens if lowered_tokens.count(t) > 1})
    if dupes:
        raise LoweringError(
            "Command '%s': overloaded-trigger idiom cannot dispatch - duplicate "
            "alternative token(s) %s collide under %s and no branch order can resolve "
            "them" % (trigger, dupes, operator))

    ordered = []
    for token, action in pairs:  # input order, minimally disturbed
        tok = token.lower()
        insert_at = None
        for i, (placed_token, _) in enumerate(ordered):
            p = placed_token.lower()
            shadowed = tok.endswith(p) if suffix_mode else (p in tok)
            if shadowed:  # the longer token must be tested before its shadow
                insert_at = i
                break
        if insert_at is None:
            ordered.append((token, action))
        else:
            ordered.insert(insert_at, (token, action))
    return ordered


def _describe(action):
    a_type = action.get("type", "PressKey")
    if a_type in _KEY_TYPES:
        keys = action.get("keys", [])
        return "%s[%s]" % (a_type, ", ".join(str(k) for k in
                                             (keys if isinstance(keys, list) else [keys])))
    if a_type == "MouseAction":
        return "MouseAction[%s]" % action.get("action", "left_click")
    return a_type
