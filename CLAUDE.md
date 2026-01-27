# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Purpose

VoiceAttack profile generator - accessibility tool to reduce workload when creating VoiceAttack profiles. Converts simple JSON definitions to valid `.vap` files.

**Status:** Complete and tested. Profiles import and work in VoiceAttack (tested with Cyber Knights Flashpoint, Heart of the Machine).

## VAP File Format

- `.vap` files: either deflate-compressed binary OR uncompressed XML
- VoiceAttack accepts raw XML directly (no compression needed)
- Decode binary profiles: `zlib.decompress(data, -15)` (raw deflate, Python)

## XML Profile Structure

```xml
<Profile xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:xsd="http://www.w3.org/2001/XMLSchema">
  <Id>GUID</Id>
  <Name>Profile Name</Name>
  <Commands>
    <Command>
      <CommandString>[phrase; alternatives]</CommandString>
      <ActionSequence>
        <CommandAction>
          <ActionType>PressKey|MouseAction|Say|Launch|...</ActionType>
          <Context>action-specific data</Context>
        </CommandAction>
      </ActionSequence>
    </Command>
  </Commands>
</Profile>
```

## ActionTypes

| ActionType | Context | Key Fields |
|------------|---------|------------|
| `PressKey` | - | `KeyCodes/unsignedShort`, `Duration` (min 0.1s) |
| `KeyDown` | - | `KeyCodes/unsignedShort` |
| `KeyUp` | - | `KeyCodes/unsignedShort` |
| `MouseAction` | see codes below | `X` (scroll clicks) |
| `Say` | text to speak | `X` (volume 0-100), `Y` (rate) |
| `Launch` | executable path | `Context2` (args), `Context3` (working dir) |
| `Pause` | - | `Duration` |
| `ExecuteCommand` | command name | - |
| `SetClipboard` | text to copy | - |

**MouseAction Context Codes:** `LC` (left click), `RC` (right click), `MC` (middle click), `LDC` (double click - NOT `DC`), `SF` (scroll up), `SB` (scroll down)

## Command Phrase Syntax

- `[option1; option2]` - alternatives (either triggers command)
- `[word;]` - optional word (trailing semicolon)

## Windows Virtual Key Codes

```
A-Z: 65-90    0-9: 48-57    F1-F12: 112-123
Enter: 13     Escape: 27    Space: 32     Tab: 9
Left: 37      Up: 38        Right: 39     Down: 40
Shift: 16     Ctrl: 17      Alt: 18       Win: 91
```

## Project Files

**Skill (Claude Code plugin):**
- `skills/voiceattack-generator/scripts/vap_generator.py` - Main generator script
- `skills/voiceattack-generator/SKILL.md` - Skill instructions (includes screenshot workflow)
- `skills/voiceattack-generator/examples/` - Example JSON files

**Reference:**
- `sample_profile.json` - Example JSON with various action types
- `cyber_knights_flashpoint.json` - Real game profile (30 commands)
- `VAP_Binary_Schema_Analysis.md` - Full binary format documentation

## Profile Generator

**Usage:** `python3 skills/voiceattack-generator/scripts/vap_generator.py input.json output.vap`

**Note:** User-provided strings (trigger phrases, categories, profile names, Say text) are XML-escaped automatically.

### JSON Input Format
```json
{
  "name": "Profile Name",
  "commands": [
    {"_section": "=== KEYBOARD ==="},
    {"trigger": "[press;] alpha", "key": "a", "category": "keyboard"},
    {"trigger": "copy", "actions": [
      {"type": "KeyDown", "keys": ["ctrl"]},
      {"type": "PressKey", "keys": ["c"], "duration": 0.1},
      {"type": "KeyUp", "keys": ["ctrl"]}
    ]},
    {"_section": "=== MOUSE ==="},
    {"trigger": "left click", "mouse": "left_click", "category": "mouse"}
  ]
}
```

Use `{"_section": "..."}` entries to organize JSON - they're ignored by generator.

### Supported Actions
| Type | Parameters |
|------|------------|
| PressKey | keys, duration (default 0.1) |
| KeyDown | keys |
| KeyUp | keys |
| MouseAction | action (left_click/right_click/double_click/scroll_up/scroll_down), scroll_clicks |
| Pause | duration |
| Say | text, volume (0-100), rate |

### Key Names
Letters: a-z, Numbers: 0-9, F-keys: f1-f12
Special: enter, escape, space, tab, backspace, delete
Arrows: left, up, right, down
Modifiers: shift, ctrl, alt, win

## Decoding Existing VAP Files

To analyze existing binary .vap profiles for reference:
```python
import zlib
with open('profile.vap', 'rb') as f:
    data = f.read()
xml = zlib.decompress(data, -15).decode('utf-8')
```

## Testing Workflow

1. Generate: `python3 skills/voiceattack-generator/scripts/vap_generator.py input.json output.vap`
2. Validate XML: `xmllint --noout output.vap`
3. Import into VoiceAttack: File → Import Profile
4. Test commands execute proper actions

No automated tests - validation is manual import into VoiceAttack.

## Screenshot Workflow

See `skills/voiceattack-generator/SKILL.md` for instructions on extracting keybindings from game screenshots.

## External References

- [IDA Pro VoiceAttack](https://github.com/mandiant/IDA_Pro_VoiceAttack_profile) - ActionType examples
- [Edvard](https://github.com/schmidsven/edvard) - XML structure template
