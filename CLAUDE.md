# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Purpose

VoiceAttack profile tools - accessibility utilities for creating and analyzing VoiceAttack profiles. Two main workflows:

1. **Generator**: JSON → VAP (create profiles from simple definitions)
2. **Decoder**: Binary VAP → XML (reverse-engineer existing profiles)

**Status:** Complete and tested. Profiles import and work in VoiceAttack.

## Commands

```bash
# Generate VAP from JSON
python3 skills/voiceattack-generator/scripts/vap_generator.py input.json output.vap

# Decode binary VAP to XML
python3 skills/voiceattack-decoder/scripts/vap_decoder.py input.vap [output.xml]

# Validate generated XML
xmllint --noout output.vap

# Quick decode for inspection (Python one-liner)
python3 -c "import zlib; print(zlib.decompress(open('file.vap','rb').read(),-15).decode())"
```

## VAP File Format

- `.vap` files: either deflate-compressed binary OR uncompressed XML
- VoiceAttack accepts raw XML directly (no compression needed)
- Binary compression: `zlib.decompress(data, -15)` (raw deflate)
- See `skills/voiceattack-decoder/docs/VAP_FORMAT.md` for binary structure details

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

**Skills:**
- `skills/voiceattack-generator/` - JSON to VAP generator (registered in manifest.json)
- `skills/voiceattack-decoder/` - Binary VAP to XML decoder (standalone tool, NOT in manifest)

**Key Files:**
- `skills/voiceattack-generator/scripts/vap_generator.py` - Generator script
- `skills/voiceattack-generator/SKILL.md` - Skill instructions (includes screenshot workflow)
- `skills/voiceattack-decoder/scripts/vap_decoder.py` - Decoder script
- `skills/voiceattack-decoder/docs/VAP_FORMAT.md` - Binary format documentation

## Generator JSON Format

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

## Testing Workflow

1. Generate: `python3 skills/voiceattack-generator/scripts/vap_generator.py input.json output.vap`
2. Validate XML: `xmllint --noout output.vap`
3. Import into VoiceAttack: File → Import Profile
4. Test commands execute proper actions

No automated tests - validation is manual import into VoiceAttack.

## Screenshot Workflow

See `skills/voiceattack-generator/SKILL.md` for extracting keybindings from game screenshots.

## External References

- [IDA Pro VoiceAttack](https://github.com/mandiant/IDA_Pro_VoiceAttack_profile) - ActionType examples
- [Edvard](https://github.com/schmidsven/edvard) - XML structure template
