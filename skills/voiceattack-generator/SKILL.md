---
name: voiceattack-generator
description: Generate VoiceAttack .vap profiles from JSON
---

# VoiceAttack Profile Generator

Generate valid VoiceAttack `.vap` profiles from simple JSON input.

## Instructions

When the user wants to generate a VoiceAttack profile:

1. Read their JSON input file
2. Write the generator script (below) to `/tmp/vap_generator.py`
3. Run: `python3 /tmp/vap_generator.py <input.json> <output.vap>`
4. Report the output file location and command count

## Generator Script

Write this to `/tmp/vap_generator.py`:

```python
#!/usr/bin/env python3
import uuid, json, sys

KEY_CODES = {
    'a': 65, 'b': 66, 'c': 67, 'd': 68, 'e': 69, 'f': 70, 'g': 71, 'h': 72,
    'i': 73, 'j': 74, 'k': 75, 'l': 76, 'm': 77, 'n': 78, 'o': 79, 'p': 80,
    'q': 81, 'r': 82, 's': 83, 't': 84, 'u': 85, 'v': 86, 'w': 87, 'x': 88,
    'y': 89, 'z': 90, '0': 48, '1': 49, '2': 50, '3': 51, '4': 52, '5': 53,
    '6': 54, '7': 55, '8': 56, '9': 57, 'f1': 112, 'f2': 113, 'f3': 114,
    'f4': 115, 'f5': 116, 'f6': 117, 'f7': 118, 'f8': 119, 'f9': 120,
    'f10': 121, 'f11': 122, 'f12': 123, 'enter': 13, 'return': 13,
    'escape': 27, 'esc': 27, 'space': 32, 'tab': 9, 'backspace': 8,
    'delete': 46, 'insert': 45, 'home': 36, 'end': 35, 'pageup': 33,
    'pagedown': 34, 'left': 37, 'up': 38, 'right': 39, 'down': 40,
    'shift': 16, 'ctrl': 17, 'control': 17, 'alt': 18, 'win': 91,
    'comma': 188, 'period': 190, 'slash': 191, 'semicolon': 186,
    'quote': 222, 'minus': 189, 'equals': 187,
}
MOUSE_CODES = {'left_click': 'LC', 'right_click': 'RC', 'middle_click': 'MC',
               'double_click': 'LDC', 'scroll_up': 'SF', 'scroll_down': 'SB'}

def action_xml(action, ordinal=0):
    action_type = action.get('type', 'PressKey')
    aid = str(uuid.uuid4())
    dur = action.get('duration', 0.1 if action_type == 'PressKey' else 0)
    ctx, x, y = '', 0, 0
    kcxml = '<KeyCodes/>'
    if action_type in ('PressKey', 'KeyDown', 'KeyUp'):
        keys = action.get('keys', [])
        keys = [keys] if isinstance(keys, str) else keys
        codes = [KEY_CODES.get(k.lower()) for k in keys if KEY_CODES.get(k.lower())]
        if codes:
            kcxml = '<KeyCodes>\n' + '\n'.join(
                f'            <unsignedShort>{c}</unsignedShort>' for c in codes
            ) + '\n          </KeyCodes>'
    elif action_type == 'MouseAction':
        ctx = MOUSE_CODES.get(action.get('action', 'left_click').lower(), 'LC')
        x = action.get('scroll_clicks', 1 if ctx in ('SF', 'SB') else 0)
    elif action_type == 'Pause':
        dur = action.get('duration', 0.5)
    elif action_type == 'Say':
        ctx = action.get('text', '')
        x, y = action.get('volume', 100), action.get('rate', 0)
    return f'''        <CommandAction>
          <PairingSet>false</PairingSet>
          <PairingSetElse>false</PairingSetElse>
          <Ordinal>{ordinal}</Ordinal>
          <ConditionMet xsi:nil="true"/>
          <IndentLevel>0</IndentLevel>
          <ConditionSkip>false</ConditionSkip>
          <IsSuffixAction>false</IsSuffixAction>
          <DecimalTransient1>0</DecimalTransient1>
          <Id>{aid}</Id>
          <ActionType>{action_type}</ActionType>
          <Duration>{dur}</Duration>
          <Delay>0</Delay>
          {kcxml}
          <Context>{ctx}</Context>
          <X>{x}</X>
          <Y>{y}</Y>
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
        </CommandAction>'''

def command_xml(cmd):
    cid, bid = str(uuid.uuid4()), str(uuid.uuid4())
    trigger = cmd.get('trigger', 'unnamed')
    cat = cmd.get('category', 'general')
    actions = cmd.get('actions', [])
    if not actions:
        if 'key' in cmd:
            actions = [{'type': 'PressKey', 'keys': [cmd['key']], 'duration': cmd.get('duration', 0.1)}]
        elif 'mouse' in cmd:
            actions = [{'type': 'MouseAction', 'action': cmd['mouse']}]
    axml = '\n'.join(action_xml(a, i) for i, a in enumerate(actions))
    return f'''    <Command>
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
      <BaseId>{bid}</BaseId>
      <OriginId>00000000-0000-0000-0000-000000000000</OriginId>
      <SessionEnabled>true</SessionEnabled>
      <Id>{cid}</Id>
      <CommandString>{trigger}</CommandString>
      <ActionSequence>
{axml}
      </ActionSequence>
      <Async>true</Async>
      <Enabled>true</Enabled>
      <Category>{cat}</Category>
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
    </Command>'''

def generate_profile(data):
    pid = data.get('id', str(uuid.uuid4()))
    name = data.get('name', 'Generated Profile')
    cmds = [c for c in data.get('commands', []) if '_section' not in c]
    cxml = '\n'.join(command_xml(c) for c in cmds)
    return f'''<?xml version="1.0" encoding="utf-8"?>
<Profile xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:xsd="http://www.w3.org/2001/XMLSchema">
  <Id>{pid}</Id>
  <Name>{name}</Name>
  <Commands>
{cxml}
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
</Profile>'''

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: python3 vap_generator.py <input.json> [output.vap]")
        sys.exit(1)
    inp = sys.argv[1]
    out = sys.argv[2] if len(sys.argv) > 2 else inp.replace('.json', '.vap')
    with open(inp) as f:
        data = json.load(f)
    with open(out, 'w') as f:
        f.write(generate_profile(data))
    cmds = [c for c in data.get('commands', []) if '_section' not in c]
    print(f"Generated: {out}")
    print(f"Commands: {len(cmds)}")
```

## JSON Input Format

```json
{
  "name": "Profile Name",
  "commands": [
    {"trigger": "[spoken; phrase]", "key": "a", "category": "keyboard"},
    {"trigger": "click", "mouse": "left_click", "category": "mouse"},
    {"trigger": "copy", "actions": [
      {"type": "KeyDown", "keys": ["ctrl"]},
      {"type": "PressKey", "keys": ["c"], "duration": 0.1},
      {"type": "KeyUp", "keys": ["ctrl"]}
    ], "category": "keyboard"}
  ]
}
```

## Action Types

| Type | Parameters |
|------|------------|
| PressKey | keys, duration (default 0.1) |
| KeyDown | keys |
| KeyUp | keys |
| MouseAction | action, scroll_clicks |
| Pause | duration (seconds) |
| Say | text, volume (0-100), rate |

## Mouse Actions

left_click, right_click, middle_click, double_click, scroll_up, scroll_down

## Key Names

**Letters:** a-z | **Numbers:** 0-9 | **F-keys:** f1-f12
**Special:** enter, escape, space, tab, backspace, delete, insert, home, end, pageup, pagedown
**Arrows:** left, up, right, down | **Modifiers:** shift, ctrl, alt, win

## Command Phrase Syntax

- `[word1; word2]` - Alternatives (either triggers command)
- `[word;]` - Optional word (trailing semicolon)
