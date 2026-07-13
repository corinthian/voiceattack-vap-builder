#!/usr/bin/env python3
"""
VoiceAttack Profile Generator
Generates valid .vap XML files from simple JSON input.

Supports: PressKey, MouseAction, Pause, KeyDown, KeyUp, KeyToggle, Say,
SetDecimal, Write (VoiceAttack log), and condition blocks (BeginCondition,
ElseIf, Else, EndCondition - Text compares only)

Usage: python3 vap_generator.py <input.json> [output.vap]
"""

import json
import math
import os
import sys
import uuid
from xml.sax.saxutils import escape

# Track warnings for summary
_warnings = []


def warn(msg):
    """Print warning to stderr and track it."""
    _warnings.append(msg)
    print(f"WARNING: {msg}", file=sys.stderr)


# Windows Virtual Key Codes
KEY_CODES = {
    # Letters
    "a": 65,
    "b": 66,
    "c": 67,
    "d": 68,
    "e": 69,
    "f": 70,
    "g": 71,
    "h": 72,
    "i": 73,
    "j": 74,
    "k": 75,
    "l": 76,
    "m": 77,
    "n": 78,
    "o": 79,
    "p": 80,
    "q": 81,
    "r": 82,
    "s": 83,
    "t": 84,
    "u": 85,
    "v": 86,
    "w": 87,
    "x": 88,
    "y": 89,
    "z": 90,
    # Numbers
    "0": 48,
    "1": 49,
    "2": 50,
    "3": 51,
    "4": 52,
    "5": 53,
    "6": 54,
    "7": 55,
    "8": 56,
    "9": 57,
    # Function keys
    "f1": 112,
    "f2": 113,
    "f3": 114,
    "f4": 115,
    "f5": 116,
    "f6": 117,
    "f7": 118,
    "f8": 119,
    "f9": 120,
    "f10": 121,
    "f11": 122,
    "f12": 123,
    # Special keys
    "enter": 13,
    "return": 13,
    "escape": 27,
    "esc": 27,
    "space": 32,
    "tab": 9,
    "backspace": 8,
    "delete": 46,
    "insert": 45,
    "home": 36,
    "end": 35,
    "pageup": 33,
    "pagedown": 34,
    # Arrow keys
    "left": 37,
    "up": 38,
    "right": 39,
    "down": 40,
    # Modifiers (generic)
    "shift": 16,
    "ctrl": 17,
    "control": 17,
    "alt": 18,
    "win": 91,
    "windows": 91,
    # Modifiers (left/right specific - for chording)
    "lshift": 160,
    "rshift": 161,
    "lctrl": 162,
    "lcontrol": 162,
    "rctrl": 163,
    "rcontrol": 163,
    "lalt": 164,
    "ralt": 165,
    "lwin": 91,
    "rwin": 92,
    # Punctuation
    "comma": 188,
    "period": 190,
    "slash": 191,
    "semicolon": 186,
    "quote": 222,
    "bracket_left": 219,
    "bracket_right": 221,
    "backslash": 220,
    "minus": 189,
    "equals": 187,
    "grave": 192,
    # Toggle keys
    "capslock": 20,
    "caps": 20,
    "numlock": 144,
    "scrolllock": 145,
    # Numpad keys
    "numpad0": 96,
    "numpad1": 97,
    "numpad2": 98,
    "numpad3": 99,
    "numpad4": 100,
    "numpad5": 101,
    "numpad6": 102,
    "numpad7": 103,
    "numpad8": 104,
    "numpad9": 105,
    "numpad_multiply": 106,
    "numpad_add": 107,
    "numpad_separator": 108,
    "numpad_subtract": 109,
    "numpad_decimal": 110,
    "numpad_divide": 111,
    # Numpad aliases
    "num0": 96,
    "num1": 97,
    "num2": 98,
    "num3": 99,
    "num4": 100,
    "num5": 101,
    "num6": 102,
    "num7": 103,
    "num8": 104,
    "num9": 105,
    "num_multiply": 106,
    "num_add": 107,
    "num_subtract": 109,
    "num_decimal": 110,
    "num_divide": 111,
}

# Mouse action codes
# Format: {button}_{action} -> CODE
# Buttons: left, middle, right, back (4), forward (5)
# Actions: click, double_click, triple_click, down, up, toggle
# Scroll: scroll_up (SF), scroll_down (SB)
MOUSE_CODES = {
    # Left button
    "left_click": "LC",
    "left_double_click": "LDC",
    "left_triple_click": "LTC",
    "left_down": "LD",
    "left_up": "LU",
    "left_toggle": "LT",
    # Middle button
    "middle_click": "MC",
    "middle_double_click": "MDC",
    "middle_triple_click": "MTC",
    "middle_down": "MD",
    "middle_up": "MU",
    "middle_toggle": "MT",
    # Right button
    "right_click": "RC",
    "right_double_click": "RDC",
    "right_triple_click": "RTC",
    "right_down": "RD",
    "right_up": "RU",
    "right_toggle": "RT",
    # Back button (button 4)
    "back_click": "4C",
    "back_double_click": "4DC",
    "back_triple_click": "4TC",
    "back_down": "4D",
    "back_up": "4U",
    "back_toggle": "4T",
    # Forward button (button 5)
    "forward_click": "5C",
    "forward_double_click": "5DC",
    "forward_triple_click": "5TC",
    "forward_down": "5D",
    "forward_up": "5U",
    "forward_toggle": "5T",
    # Scroll
    "scroll_up": "SF",
    "scroll_down": "SB",
    "scroll_left": "SL",
    "scroll_right": "SR",
    # Short aliases for common actions
    "lc": "LC",
    "rc": "RC",
    "mc": "MC",
    "double_click": "LDC",  # default to left
    "triple_click": "LTC",  # default to left
}


# Condition block action types (JSON "type" -> XML ActionType string). Codes 19/63/29/20
# per schema/vap_capability_dictionary.json 0.2.0 action_types (confirmed against real
# VoiceAttack XML exports, 2026-07-11 recon).
CONDITION_ACTION_TYPES = {
    "BeginCondition": "ConditionStart",
    "ElseIf": "ConditionElseIf",
    "Else": "ConditionElse",
    "EndCondition": "ConditionEnd",
}
# Marker kinds that open/continue/close a block, for validation and pairing/group derivation.
CONDITION_OPEN = "BeginCondition"
CONDITION_BRANCH = ("ElseIf", "Else")
CONDITION_CLOSE = "EndCondition"

# Value-type selector codes (ConditionStartType), dictionary 0.2.0 conditions.value_types.
# v1 only supports Text; the others are listed so an out-of-scope valueType can be named
# in the error message.
CONDITION_VALUE_TYPES = {
    "SmallInteger": 0,
    "Text": 1,
    "Boolean": 2,
    "Integer": 3,
    "Decimal": 4,
}

# Text operator dropdown order (0-based index == code), dictionary 0.2.0
# conditions.operators.Text. Only Text is in v1 scope.
TEXT_OPERATORS = {
    "Equals": 0,
    "Does Not Equal": 1,
    "Starts With": 2,
    "Does Not Start With": 3,
    "Ends With": 4,
    "Does Not End With": 5,
    "Contains": 6,
    "Does Not Contain": 7,
    "Has Been Set": 8,
    "Has Not Been Set": 9,
}

CONDITION_KEYS = {"valueType", "operator", "leftOperand", "value"}

# JSON-level action names whose XML ActionType differs (SetDecimal -> DecimalSet,
# Write -> WriteToLog). Kept as named constants, not quoted dispatch literals: the
# dictionary audit reads quoted literals in action_xml's dispatch chain as XML
# ActionType names.
SET_DECIMAL_JSON_TYPE = "SetDecimal"
WRITE_JSON_TYPE = "Write"


class ConditionValidationError(Exception):
    """A command's action list fails hard-fail validation (condition-block structure,
    SetDecimal/Write shape). Aborts the entire generation run (no output file is
    written) - dropping one condition action would corrupt every downstream pairing
    index and produce an importable-but-broken profile."""


def new_guid():
    return str(uuid.uuid4())


def format_duration(value):
    """Validate a duration and format it as a plain decimal string (never
    scientific notation). Invalid (non-numeric or negative) values fall back
    to 0.1 with a warning. Explicit zero is legal - real VoiceAttack exports
    carry PressKey Duration 0.0 (reference profile zoom command)."""
    try:
        d = float(value)
    except (TypeError, ValueError):
        warn(f"Invalid duration {value} - using default 0.1")
        return "0.1"
    if d < 0:
        warn(f"Invalid duration {value} - using default 0.1")
        return "0.1"
    if isinstance(value, int) and not isinstance(value, bool):
        return str(value)
    s = repr(d)
    if "e" in s or "E" in s:
        s = f"{d:.10f}".rstrip("0").rstrip(".")
    return s


def action_xml(action, ordinal=0, indent_level=0, condition_pairing=0, condition_group=0):
    """Generate XML for a single action. Returns None if the action should
    be skipped entirely (unknown action type or unknown mouse action).

    Condition markers (BeginCondition/ElseIf/Else/EndCondition) are rendered by a
    dedicated helper - they never enter the dispatch chain below, so they cannot be
    dropped by the "unknown action type" fallback."""
    action_type = action.get("type", "PressKey")
    if action_type in CONDITION_ACTION_TYPES:
        return _condition_action_xml(action, ordinal, indent_level, condition_pairing, condition_group)

    # Common fields
    action_id = new_guid()
    duration = action.get("duration", 0.1 if action_type == "PressKey" else 0)
    delay = action.get("delay", 0)
    context = ""
    x, y, z = 0, 0, 0
    scroll_clicks = 0
    key_codes_xml = "<KeyCodes/>"
    skip_duration_validation = False

    if action_type in ("PressKey", "KeyDown", "KeyUp", "KeyToggle"):
        keys = action.get("keys", [])
        if isinstance(keys, str):
            keys = [keys]
        codes = []
        for k in keys:
            if isinstance(k, int) and not isinstance(k, bool):
                # Raw VK code given as a JSON number - accept as-is
                codes.append(k)
                continue
            k_lower = k.lower()
            if k_lower in KEY_CODES:
                codes.append(KEY_CODES[k_lower])
            elif k.isdigit():
                codes.append(int(k))
            else:
                warn(f"Unknown key '{k}' - ignored")
        if codes:
            key_codes_xml = (
                "<KeyCodes>\n"
                + "\n".join(
                    f"            <unsignedShort>{c}</unsignedShort>" for c in codes
                )
                + "\n          </KeyCodes>"
            )

    elif action_type == "MouseAction":
        mouse_action = action.get("action", "left_click").lower()
        if mouse_action not in MOUSE_CODES:
            warn(f"Unknown mouse action '{mouse_action}' - skipped")
            return None
        context = MOUSE_CODES[mouse_action]
        if context in ("SF", "SB", "SL", "SR"):
            # scroll_clicks for scroll actions - try Duration field (appears before Context)
            scroll_clicks = action.get("scroll_clicks", 1)
            duration = scroll_clicks  # Try Duration for scroll clicks
            x = scroll_clicks  # Also set X
            skip_duration_validation = True
        else:
            # Duration for click actions (click duration in seconds).
            # scroll_clicks must never leak into non-scroll actions.
            if "duration" in action:
                duration = action["duration"]

    elif action_type == "Pause":
        duration = action.get("duration", 0.5)

    elif action_type == "Say":
        context = escape(action.get("text", ""))
        x = action.get("volume", 100)
        y = action.get("rate", 0)

    elif action_type == SET_DECIMAL_JSON_TYPE:
        # Own template: DecimalSet carries ConditionSetName + DecimalContext1 and no
        # <Context> element (ground truth sec 4.6 ConditionSet analogy).
        return _decimal_set_xml(action, ordinal, indent_level)

    elif action_type == WRITE_JSON_TYPE:
        # XML ActionType is WriteToLog (code 23) - writes to the VoiceAttack event log,
        # not keystrokes. Text in Context, X = color code (mapping unverified - emit 0).
        # Shape validated in _validate_actions (hard-fail).
        action_type = "WriteToLog"
        context = escape(action.get("text", ""))

    else:
        warn(f"Unknown action type '{action_type}' - skipped")
        return None

    # A duration of 0 that was never supplied by the user is an inapplicable
    # placeholder (e.g. KeyDown/KeyUp/plain mouse clicks) - not an error.
    if not skip_duration_validation and duration == 0 and "duration" not in action:
        skip_duration_validation = True
    duration_str = str(duration) if skip_duration_validation else format_duration(duration)

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
          <Delay>{delay}</Delay>
          {key_codes_xml}
          <Context>{context}</Context>
          <X>{x}</X>
          <Y>{y}</Y>
          <Z>{z}</Z>
          <InputMode>0</InputMode>
          <ConditionPairing>{condition_pairing}</ConditionPairing>
          <ConditionGroup>{condition_group}</ConditionGroup>
          <ConditionStartOperator>0</ConditionStartOperator>
          <ConditionStartValue>0</ConditionStartValue>
          <ConditionStartValueType>0</ConditionStartValueType>
          <ConditionStartType>0</ConditionStartType>
          <DecimalContext1>{scroll_clicks}</DecimalContext1>
          <DecimalContext2>0</DecimalContext2>
          <DateContext1>0001-01-01T00:00:00</DateContext1>
          <DateContext2>0001-01-01T00:00:00</DateContext2>
          <Disabled>false</Disabled>
          <RandomSounds/>
          <ConditionExpressions/>
        </CommandAction>"""


def _condition_action_xml(action, ordinal, indent_level, condition_pairing, condition_group):
    """Render a BeginCondition/ElseIf/Else/EndCondition marker. Element order and the
    absence/presence of fields follow the ground-truth XML samples exactly (see
    conditional_xml_ground_truth.md samples 1, 2c, 2d, 2e) - it is NOT the same template
    as ordinary actions: no <Context>, a Text compare's value lives in <Context2>, and
    Begin/ElseIf carry ConditionStartNameFrom + ConditionStartCompareToCondtion that
    Else/EndCondition omit entirely."""
    action_type = action["type"]
    xml_action_type = CONDITION_ACTION_TYPES[action_type]
    action_id = new_guid()

    if action_type in (CONDITION_OPEN, "ElseIf"):
        condition = action["condition"]  # presence already validated
        operator_code = TEXT_OPERATORS[condition["operator"]]
        left_operand = escape(condition["leftOperand"])
        value = escape(str(condition["value"]))
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
          <ActionType>{xml_action_type}</ActionType>
          <Duration>0</Duration>
          <Delay>0</Delay>
          <KeyCodes/>
          <Context2 xml:space="preserve">{value}</Context2>
          <X>0</X>
          <Y>0</Y>
          <Z>1</Z>
          <InputMode>0</InputMode>
          <ConditionPairing>{condition_pairing}</ConditionPairing>
          <ConditionGroup>{condition_group}</ConditionGroup>
          <ConditionStartNameFrom>{left_operand}</ConditionStartNameFrom>
          <ConditionStartOperator>{operator_code}</ConditionStartOperator>
          <ConditionStartValue>0</ConditionStartValue>
          <ConditionStartValueType>0</ConditionStartValueType>
          <ConditionStartCompareToCondtion/>
          <ConditionStartType>1</ConditionStartType>
          <DecimalContext1>0</DecimalContext1>
          <DecimalContext2>0</DecimalContext2>
          <DateContext1>0001-01-01T00:00:00</DateContext1>
          <DateContext2>0001-01-01T00:00:00</DateContext2>
          <Disabled>false</Disabled>
          <RandomSounds/>
          <ConditionExpressions/>
        </CommandAction>"""

    # Else / EndCondition: structural only, no compare fields carried.
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
          <ActionType>{xml_action_type}</ActionType>
          <Duration>0</Duration>
          <Delay>0</Delay>
          <KeyCodes/>
          <X>0</X>
          <Y>0</Y>
          <Z>0</Z>
          <InputMode>0</InputMode>
          <ConditionPairing>{condition_pairing}</ConditionPairing>
          <ConditionGroup>{condition_group}</ConditionGroup>
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


def _format_decimal(value):
    """Format a validated numeric value as plain decimal text (never scientific
    notation), matching the IntSet sample's plain-literal convention."""
    if isinstance(value, int) and not isinstance(value, bool):
        return str(value)
    d = float(value)
    s = repr(d)
    if "e" in s or "E" in s:
        s = f"{d:.10f}".rstrip("0").rstrip(".")
    return s


def _decimal_set_xml(action, ordinal, indent_level):
    """Render a SetDecimal action as XML ActionType DecimalSet. CARRIER INFERRED, not
    observed - no public XML export contains one (ground truth sec 4.1): target variable
    in ConditionSetName and value in DecimalContext1 by exact analogy to the SOLID
    IntSet/ConditionSet samples (secs 4.5/4.6); element order mirrors sec 4.6, the
    Mandiant-generation serializer this generator's template already follows. Pending
    the VoiceAttack import probe."""
    action_id = new_guid()
    variable = escape(action["variable"])  # shape validated in _validate_actions
    value = _format_decimal(action["value"])
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


def _validate_actions(actions, trigger_raw):
    """Structural + shape validation over a command's raw actions list (materialized
    order, before ordinal/pairing/group are computed). Any defect raises
    ConditionValidationError - see build spec WP-A validation ruling: a dropped or
    malformed condition action corrupts every downstream pairing index, so this hard-fails
    rather than warning. SetDecimal/Write shapes hard-fail here too (WP-A2 ruling)."""

    def fail(msg):
        raise ConditionValidationError(f"Command '{trigger_raw}': {msg}")

    stack = []  # one frame per open block: {"seen_else": bool}
    for a in actions:
        a_type = a.get("type")
        if a_type == SET_DECIMAL_JSON_TYPE:
            variable = a.get("variable")
            if not isinstance(variable, str) or not variable:
                fail("'SetDecimal' requires a non-empty string 'variable'")
            value = a.get("value")
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                fail(f"'SetDecimal' requires a numeric 'value' (got {value!r})")
            # json.load parses bare NaN/Infinity; .NET decimal has no NaN/Inf, so the
            # emitted DecimalContext1 would silently break VoiceAttack import.
            if not math.isfinite(value):
                fail(f"'SetDecimal' requires a finite 'value' (got {value!r})")
            continue
        if a_type == WRITE_JSON_TYPE:
            if not isinstance(a.get("text"), str):
                fail("'Write' requires a string 'text' (empty string is legal)")
            continue
        if a_type not in CONDITION_ACTION_TYPES:
            continue
        has_condition = "condition" in a and a["condition"] is not None

        if a_type == CONDITION_OPEN or a_type == "ElseIf":
            if not has_condition:
                fail(f"'{a_type}' is missing a required 'condition' object")
            condition = a["condition"]
            if not isinstance(condition, dict):
                fail(f"'{a_type}' condition must be an object")
            unknown = set(condition) - CONDITION_KEYS
            if unknown:
                fail(f"'{a_type}' condition has unknown key(s): {sorted(unknown)}")
            value_type = condition.get("valueType")
            if value_type != "Text":
                fail(
                    f"'{a_type}' condition valueType '{value_type}' is not supported - "
                    "v1 supports Text only (Integer/Decimal XML carriers are unverified)"
                )
            left_operand = condition.get("leftOperand")
            if not isinstance(left_operand, str) or not left_operand:
                fail(f"'{a_type}' condition is missing a non-empty 'leftOperand'")
            if "value" not in condition:
                fail(f"'{a_type}' condition is missing a 'value' key (use \"\" for an empty compare value)")
            operator = condition.get("operator")
            if operator not in TEXT_OPERATORS:
                fail(
                    f"'{a_type}' condition has unknown operator '{operator}' - "
                    f"Text operators are: {', '.join(TEXT_OPERATORS)}"
                )

        if a_type == CONDITION_OPEN:
            stack.append({"seen_else": False})
            continue

        if a_type == "ElseIf":
            if not stack:
                fail("'ElseIf' found outside any open condition block")
            if stack[-1]["seen_else"]:
                fail("'ElseIf' follows 'Else' in the same condition block")
        elif a_type == "Else":
            if has_condition:
                fail("'Else' must not carry a 'condition' object")
            if not stack:
                fail("'Else' found outside any open condition block")
            if stack[-1]["seen_else"]:
                fail("duplicate 'Else' in the same condition block")
            stack[-1]["seen_else"] = True
        elif a_type == CONDITION_CLOSE:
            if has_condition:
                fail("'EndCondition' must not carry a 'condition' object")
            if not stack:
                fail("'EndCondition' found without a matching 'BeginCondition'")
            stack.pop()

    if stack:
        fail(f"{len(stack)} condition block(s) opened with 'BeginCondition' but never closed with 'EndCondition'")


def command_xml(cmd):
    """Generate XML for a single command."""
    cmd_id = new_guid()
    base_id = new_guid()
    trigger_raw = cmd.get("trigger", "unnamed command")
    trigger = escape(trigger_raw)
    category = escape(cmd.get("category", "general"))

    actions = cmd.get("actions", [])
    if not actions:
        # Default: single key press if 'key' specified
        if "key" in cmd:
            key = cmd["key"]
            if isinstance(key, int) and not isinstance(key, bool):
                pass  # raw VK code given as a JSON number - always valid
            elif not isinstance(key, str) or (
                key.lower() not in KEY_CODES and not key.isdigit()
            ):
                warn(
                    f"Command '{trigger_raw}': unknown key '{key}' - command will have no action"
                )
            actions = [
                {
                    "type": "PressKey",
                    "keys": [key],
                    "duration": cmd.get("duration", 0.1),
                }
            ]
        elif "mouse" in cmd:
            actions = [{"type": "MouseAction", "action": cmd["mouse"]}]
        else:
            warn(f"Command '{trigger_raw}': no key, mouse, or actions defined")

    # (2) Validate condition-block structure and SetDecimal/Write shapes up front, on the
    # raw action list, before any rendering: a malformed block must abort generation,
    # never render a partial/corrupt chain (build spec WP-A/WP-A2 validation ruling).
    _validate_actions(actions, trigger_raw)

    # (1)+(3)+(4) materialize/compute/render collapsed into one pass so warn() output
    # stays in exact original left-to-right order (dropped-action and inner per-action
    # warnings must not be reordered relative to each other). Ordinal, IndentLevel and
    # ConditionGroup are all knowable the moment an action is reached (they never depend
    # on what comes later); ConditionPairing on a Begin/ElseIf/Else marker is the ordinal
    # of the NEXT marker in its block, which isn't known until that marker is reached - so
    # markers are rendered with a per-ordinal placeholder token that a second, non-
    # rendering pass over the finished chunks substitutes for the real value.
    action_chunks = []
    depth = 0
    group_counter = 0
    block_stack = []  # open blocks: {"group": int, "marker_ordinals": [ordinal, ...]}
    finished_blocks = []  # [[ordinal, ...], ...] each in Begin..End order

    def pairing_placeholder(ordinal):
        return f"__CONDITION_PAIRING_{ordinal}__"

    def resolve_pairing(chunk, ordinal, value):
        # Replace the whole element, not the bare token: user-supplied text is
        # angle-bracket-escaped, so the full element string cannot occur in content.
        return chunk.replace(
            f"<ConditionPairing>{pairing_placeholder(ordinal)}</ConditionPairing>",
            f"<ConditionPairing>{value}</ConditionPairing>",
        )

    for a in actions:
        a_type = a.get("type", "PressKey")
        if a_type in CONDITION_ACTION_TYPES:
            ordinal = len(action_chunks)
            if a_type == CONDITION_OPEN:
                group_counter += 1
                group = group_counter
                indent = depth
                depth += 1
                block_stack.append({"group": group, "marker_ordinals": [ordinal]})
            elif a_type in CONDITION_BRANCH:
                frame = block_stack[-1]
                group = frame["group"]
                indent = max(0, depth - 1)
                frame["marker_ordinals"].append(ordinal)
            else:  # CONDITION_CLOSE
                frame = block_stack.pop()
                group = frame["group"]
                depth = max(0, depth - 1)
                indent = depth
                frame["marker_ordinals"].append(ordinal)
                finished_blocks.append(frame["marker_ordinals"])
            chunk = action_xml(a, ordinal, indent, pairing_placeholder(ordinal), group)
            action_chunks.append(chunk)
        else:
            chunk = action_xml(a, len(action_chunks), depth, 0, 0)
            if chunk is not None:
                action_chunks.append(chunk)

    # ConditionPairing: forward chain Begin->ElseIf->...->Else->End; End points back to
    # its block's Begin (build spec Shared facts + ADDENDUM "no ElseIf/Else" case).
    for marker_ordinals in finished_blocks:
        for i in range(len(marker_ordinals) - 1):
            src, dst = marker_ordinals[i], marker_ordinals[i + 1]
            action_chunks[src] = resolve_pairing(action_chunks[src], src, dst)
        last, first = marker_ordinals[-1], marker_ordinals[0]
        action_chunks[last] = resolve_pairing(action_chunks[last], last, first)

    actions_xml = "\n".join(action_chunks)

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


def generate_profile(profile_data):
    """Generate complete profile XML."""
    profile_id = profile_data.get("id", new_guid())
    name = escape(profile_data.get("name", "Generated Profile"))
    commands = profile_data.get("commands", [])

    # Filter out section markers (entries with _section key)
    commands = [c for c in commands if "_section" not in c]

    commands_xml = "\n".join(command_xml(c) for c in commands)

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


def print_help():
    """Print usage information."""
    print("""VoiceAttack Profile Generator

Usage: python3 vap_generator.py <input.json> [output.vap] [--no-idiom] [--legacy-emit]

Arguments:
  input.json    JSON file with profile definition
  output.vap    Output file (default: input filename with .vap extension)

Flags:
  --no-idiom     Disable overloaded-trigger auto-lowering for the whole run
                 (per-command opt-out: "idiom": false on the command)
  --legacy-emit  Use this file's own 2.0.0 emission path instead of the gen2
                 pipeline (soak oracle; retires with it)

Example JSON format:
{
  "name": "My Profile",
  "commands": [
    {"trigger": "[press;] alpha", "key": "a", "category": "keyboard"},
    {"trigger": "left click", "mouse": "left_click", "category": "mouse"},
    {"trigger": "copy", "actions": [
      {"type": "KeyDown", "keys": ["ctrl"]},
      {"type": "PressKey", "keys": ["c"], "duration": 0.1},
      {"type": "KeyUp", "keys": ["ctrl"]}
    ], "category": "keyboard"}
  ]
}

Action Types:
  PressKey     - Press and release key(s)
  KeyDown      - Hold key down
  KeyUp        - Release held key
  KeyToggle    - Toggle key state (press once = down, press again = up)
  MouseAction  - Mouse click/scroll (left_click, right_click, double_click, scroll_up, scroll_down)
  Pause        - Wait (duration in seconds)
  Say          - Text-to-speech (text, volume, rate)
  SetDecimal   - Set a decimal variable (variable, value). XML carrier inferred
                 pending a VoiceAttack import probe.
  Write        - Write text to the VoiceAttack event log, NOT keystrokes (text;
                 variable tokens like {DEC:var} work)
  BeginCondition / ElseIf / Else / EndCondition
               - Condition block markers. BeginCondition/ElseIf require a
                 "condition" object: {"valueType": "Text", "operator": "<name>",
                 "leftOperand": "<string>", "value": "<string>"}. Text only;
                 malformed blocks abort generation (exit 1, no output file).

Key Names:
  Letters: a-z
  Numbers: 0-9
  F-keys: f1-f12
  Special: enter, escape, space, tab, backspace, delete
  Arrows: left, up, right, down
  Modifiers: shift, ctrl, alt, win
  Numpad: numpad0-numpad9, numpad_add, numpad_subtract, numpad_multiply, numpad_divide, numpad_decimal, numpad_separator
""")


def _run_gen2_pipeline(profile_data, no_idiom):
    """W4 default path: simple JSON -> gen2.lower -> gen2.emit_profile (one pipeline,
    two doors — refactor plan §3). This module's own emission path stays intact behind
    --legacy-emit as the byte-identity oracle through soak. Returns (xml, warning
    count); exits 1 on any hard-fail, before any output file exists."""
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from gen2 import names as gen2_names
    from gen2.emit_profile import EmitError, emit as gen2_emit
    from gen2.lower import LoweringError, lower_profile

    # INFO lines are idiom-compiler visibility (D2 ruling: auto-lowering is the
    # default, not a defect — they never count toward the warning exit code). Both
    # channels STREAM as they occur, so everything accumulated before a hard-fail is
    # already on stderr when the ERROR line lands (W5 fix wave, finding 4).
    print_info = lambda line: print(f"INFO: {line}", file=sys.stderr)  # noqa: E731
    print_warn = lambda line: print(f"WARNING: {line}", file=sys.stderr)  # noqa: E731
    try:
        dictionary = gen2_names.load()
        model, infos, lower_warnings = lower_profile(
            profile_data, dictionary, no_idiom=no_idiom,
            info=print_info, warn=print_warn)
        xml, emit_warnings = gen2_emit(model, dictionary, warn=print_warn)
    except (LoweringError, EmitError) as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)

    return xml, len(lower_warnings) + len(emit_warnings)


def main():
    argv = sys.argv[1:]
    legacy_emit = "--legacy-emit" in argv
    no_idiom = "--no-idiom" in argv
    args = [a for a in argv if a not in ("--legacy-emit", "--no-idiom")]

    if not args or args[0] in ("-h", "--help"):
        print_help()
        sys.exit(0 if args else 1)

    input_file = args[0]
    if len(args) > 1:
        output_file = args[1]
    else:
        base, ext = os.path.splitext(input_file)
        output_file = (base if ext.lower() == ".json" else input_file) + ".vap"

    if os.path.abspath(output_file) == os.path.abspath(input_file):
        print(
            f"ERROR: Output file would overwrite input file: {output_file}",
            file=sys.stderr,
        )
        sys.exit(1)

    try:
        with open(input_file, "r") as f:
            profile_data = json.load(f)
    except FileNotFoundError:
        print(f"ERROR: File not found: {input_file}", file=sys.stderr)
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"ERROR: Invalid JSON in {input_file}: {e}", file=sys.stderr)
        sys.exit(1)

    if legacy_emit:
        try:
            xml = generate_profile(profile_data)
        except ConditionValidationError as e:
            print(f"ERROR: {e}", file=sys.stderr)
            sys.exit(1)
        warning_count = len(_warnings)
    else:
        xml, warning_count = _run_gen2_pipeline(profile_data, no_idiom)

    with open(output_file, "w", encoding="utf-8") as f:
        f.write(xml)

    # Count actual commands (excluding section markers)
    cmd_count = len(
        [c for c in profile_data.get("commands", []) if "_section" not in c]
    )

    print(f"Generated: {output_file}")
    print(f"Commands: {cmd_count}")
    if warning_count:
        print(f"Warnings: {warning_count}")
        sys.exit(2)


if __name__ == "__main__":
    main()
