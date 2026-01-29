# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Purpose

VoiceAttack profile tools - accessibility utilities for creating and analyzing VoiceAttack profiles. Two main workflows:

1. **Generator**: JSON → VAP (create profiles from simple definitions)
2. **Decoder**: Binary VAP → XML + JSON (reverse-engineer existing profiles)

**Status:** Complete and tested. Profiles import and work in VoiceAttack.

## Commands

```bash
# Generate VAP from JSON
python3 skills/voiceattack-generator/scripts/vap_generator.py input.json output.vap

# Decode binary VAP to XML + JSON (dual output)
python3 skills/voiceattack-decoder/scripts/vap_decoder.py input.vap [output_base]
# Produces: output_base.xml and output_base.json (or input_decoded.* if no output specified)

# Validate generated XML
xmllint --noout output.vap

# Quick inspect binary VAP (hex dump of decompressed data)
python3 -c "import zlib; d=zlib.decompress(open('file.vap','rb').read(),-15); print(f'Size: {len(d)} bytes'); print(d[:500])"
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
| `KeyToggle` | - | `KeyCodes/unsignedShort` (toggle key state) |
| `MouseAction` | see codes below | `Duration` (scroll clicks) |
| `Say` | text to speak | `X` (volume 0-100), `Y` (rate) |
| `Launch` | executable path | `Context2` (args), `Context3` (working dir) |
| `Pause` | - | `Duration` |
| `ExecuteCommand` | command name | - |
| `SetClipboard` | text to copy | - |

**MouseAction Context Codes:**

| Button | Click | Double | Triple | Down | Up | Toggle |
|--------|-------|--------|--------|------|-----|--------|
| Left | LC | LDC | LTC | LD | LU | LT |
| Middle | MC | MDC | MTC | MD | MU | MT |
| Right | RC | RDC | RTC | RD | RU | RT |
| Back | 4C | 4DC | 4TC | 4D | 4U | 4T |
| Forward | 5C | 5DC | 5TC | 5D | 5U | 5T |

**Scroll:** `SF` (up), `SB` (down), `SL` (left), `SR` (right)

## Command Phrase Syntax

- `[option1; option2]` - alternatives (either triggers command)
- `[word;]` - optional word (trailing semicolon)

## Windows Virtual Key Codes

```
A-Z: 65-90    0-9: 48-57    F1-F12: 112-123
Enter: 13     Escape: 27    Space: 32     Tab: 9
Left: 37      Up: 38        Right: 39     Down: 40
Shift: 16     Ctrl: 17      Alt: 18       Win: 91

Left/Right modifiers (for chording):
LShift: 160   RShift: 161   LCtrl: 162    RCtrl: 163
LAlt: 164     RAlt: 165     LWin: 91      RWin: 92
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

## Directory Structure

| Directory | Purpose | Access |
|-----------|---------|--------|
| `reference profiles/` | VAP files for extracting reference data | Read-only |
| `Screenshots/` | Game keybinding screenshots | Read-only |
| `output files/` | Test output (generated VAP and intermediate JSON) | Write |

**Rules:**
- Never write generated profiles to `reference profiles/` - that's for source VAPs only
- All screenshots go in `Screenshots/`
- All test/generated output goes in `output files/`

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
| KeyToggle | keys (press once = down, again = up) |
| MouseAction | action (see mouse actions below), scroll_clicks (for scroll actions) |
| Pause | duration |
| Say | text, volume (0-100), rate |

### Key Names

Letters: a-z, Numbers: 0-9, F-keys: f1-f12
Special: enter, escape, space, tab, backspace, delete
Arrows: left, up, right, down
Modifiers (generic): shift, ctrl, alt, win
Modifiers (left/right): lshift, rshift, lctrl, rctrl, lalt, ralt, lwin, rwin

### Mouse Actions

**Buttons:** left, middle, right, back, forward
**Actions:** click, double_click, triple_click, down, up, toggle
**Scroll:** scroll_up, scroll_down, scroll_left, scroll_right

Format: `{button}_{action}` (e.g., `left_click`, `right_double_click`, `back_toggle`)

```json
{"trigger": "scroll left", "actions": [{"type": "MouseAction", "action": "scroll_left", "scroll_clicks": 5}]}
{"trigger": "back toggle", "mouse": "back_toggle"}
```

### Key Chording

Press multiple keys simultaneously using a single PressKey with left/right modifiers:
```json
{"trigger": "paste", "actions": [{"type": "PressKey", "keys": ["lctrl", "v"]}]}
```

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
