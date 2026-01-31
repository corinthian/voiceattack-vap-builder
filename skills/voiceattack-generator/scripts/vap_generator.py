#!/usr/bin/env python3
"""
VoiceAttack Profile Generator
Generates valid .vap XML files from simple JSON input.

Supports: PressKey, MouseAction, Pause, KeyDown, KeyUp, KeyToggle, Say

Usage: python3 vap_generator.py <input.json> [output.vap]
"""

import json
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


def new_guid():
    return str(uuid.uuid4())


def action_xml(action, ordinal=0):
    """Generate XML for a single action."""
    action_type = action.get("type", "PressKey")

    # Common fields
    action_id = new_guid()
    duration = action.get("duration", 0.1 if action_type == "PressKey" else 0)
    delay = action.get("delay", 0)
    context = ""
    x, y, z = 0, 0, 0
    scroll_clicks = 0
    key_codes_xml = "<KeyCodes/>"

    if action_type in ("PressKey", "KeyDown", "KeyUp", "KeyToggle"):
        keys = action.get("keys", [])
        if isinstance(keys, str):
            keys = [keys]
        codes = []
        for k in keys:
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
            warn(f"Unknown mouse action '{mouse_action}' - defaulting to left_click")
        context = MOUSE_CODES.get(mouse_action, "LC")
        # scroll_clicks for scroll actions - try Duration field (appears before Context)
        scroll_clicks = action.get("scroll_clicks", 1 if context in ("SF", "SB", "SL", "SR") else 0)
        if context in ("SF", "SB", "SL", "SR"):
            duration = scroll_clicks  # Try Duration for scroll clicks
        x = scroll_clicks  # Also set X
        # Duration for click actions (click duration in seconds)
        if "duration" in action and context not in ("SF", "SB", "SL", "SR"):
            duration = action["duration"]

    elif action_type == "Pause":
        duration = action.get("duration", 0.5)

    elif action_type == "Say":
        context = escape(action.get("text", ""))
        x = action.get("volume", 100)
        y = action.get("rate", 0)

    return f"""        <CommandAction>
          <PairingSet>false</PairingSet>
          <PairingSetElse>false</PairingSetElse>
          <Ordinal>{ordinal}</Ordinal>
          <ConditionMet xsi:nil="true"/>
          <IndentLevel>0</IndentLevel>
          <ConditionSkip>false</ConditionSkip>
          <IsSuffixAction>false</IsSuffixAction>
          <DecimalTransient1>0</DecimalTransient1>
          <Id>{action_id}</Id>
          <ActionType>{action_type}</ActionType>
          <Duration>{duration}</Duration>
          <Delay>{delay}</Delay>
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
          <DecimalContext1>{scroll_clicks}</DecimalContext1>
          <DecimalContext2>0</DecimalContext2>
          <DateContext1>0001-01-01T00:00:00</DateContext1>
          <DateContext2>0001-01-01T00:00:00</DateContext2>
          <Disabled>false</Disabled>
          <RandomSounds/>
          <ConditionExpressions/>
        </CommandAction>"""


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
            if key.lower() not in KEY_CODES and not key.isdigit():
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

    actions_xml = "\n".join(action_xml(a, i) for i, a in enumerate(actions))

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

Usage: python3 vap_generator.py <input.json> [output.vap]

Arguments:
  input.json    JSON file with profile definition
  output.vap    Output file (default: input filename with .vap extension)

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

Key Names:
  Letters: a-z
  Numbers: 0-9
  F-keys: f1-f12
  Special: enter, escape, space, tab, backspace, delete
  Arrows: left, up, right, down
  Modifiers: shift, ctrl, alt, win
""")


def main():
    if len(sys.argv) < 2 or sys.argv[1] in ("-h", "--help"):
        print_help()
        sys.exit(0 if sys.argv[1:] else 1)

    input_file = sys.argv[1]
    output_file = (
        sys.argv[2] if len(sys.argv) > 2 else input_file.replace(".json", ".vap")
    )

    with open(input_file, "r") as f:
        profile_data = json.load(f)

    xml = generate_profile(profile_data)

    with open(output_file, "w", encoding="utf-8") as f:
        f.write(xml)

    # Count actual commands (excluding section markers)
    cmd_count = len(
        [c for c in profile_data.get("commands", []) if "_section" not in c]
    )

    print(f"Generated: {output_file}")
    print(f"Commands: {cmd_count}")
    if _warnings:
        print(f"Warnings: {len(_warnings)}")


if __name__ == "__main__":
    main()
