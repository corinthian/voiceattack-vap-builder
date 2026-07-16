# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Purpose

VoiceAttack profile tools - accessibility utilities for creating and analyzing VoiceAttack profiles. Two main workflows:

1. **Generator**: JSON → VAP (create profiles from simple definitions)
2. **Decoder**: Binary VAP → XML + JSON (reverse-engineer existing profiles)

**Status:** 2.0.0 shipped on `main` (`039b7aa`). The **2.1 encoder line** is complete on `feature/generator-v2` (W0–W7 done) and staged for release. `gen2` (`skills/voiceattack-generator/scripts/gen2/`, stdlib-only, dictionary-driven) is now the **active generator** — its CLI (`python3 -m gen2`) auto-detects the simple authoring format vs schema-v1.1 JSON and is one emission pipeline; the overloaded-trigger idiom auto-lowers to a `{LASTSPOKENCMD}` dispatch chain (collision-checked by exhaustive utterance simulation). `vap_generator.py` is deprecated (soak-only, fewer types; still backs the audit's key/mouse tables). Emit coverage: keys/mouse/Pause/Say, SetDecimal/Write/conditionals, row-2 (TextSet/BooleanSet/IntSet/QuickInput), SetClipboard, Launch (carriers VA-confirmed), and the five parameterless dark types (dictation/listening) — all VA-import-verified, zero inference. Deferred to a future release: ExecuteCommand/KillCommand (by-GUID), PauseVariable/ExitCommand (decoder-parked), SoundFile (code 14, corrects bogus PlaySound=35), While-loops (D4), animated mouse-move (DecimalContext2 timing + steps/ease flags — W7 ground truth, not the old wrong `Duration` inference). The `decode(encode(decode(x)))==decode(x)` fixpoint is a live repo-level gate (`tests/integration/`). Decoder V2 (`scripts/vap2/`, stdlib-only object-walk) decodes binary and XML-form profiles into normative JSON (schema v1.1, frozen). The dictionary audit is gen2-aware + parked-aware (W6). Harness: 25 integration + 60 decoder tests green; dictionary 0.5.0 validate OK + audit exit 0; manifest 2.1.1. 2.1.0 shipped and tagged; the 2.1.1 line (`fix/security-review`, PR #27) adds bounded container input/decompression, atomic output writes, and the decoder verbatim-transcription doc note.

## Commands

```bash
# Generate VAP from JSON (gen2 is the active generator as of 2.1; run from scripts/)
cd skills/voiceattack-generator/scripts && python3 -m gen2 input.json output.vap
# Auto-detects simple authoring format vs schema-v1.1 JSON; --no-idiom disables idiom lowering.
# Legacy (deprecated, soak-only, fewer action types): python3 skills/voiceattack-generator/scripts/vap_generator.py input.json output.vap

# Decode binary VAP — V2 (object-walk; normative JSON, gated XML with --xml)
python3 -m vap2 input.vap [output_base] [--stdout] [--xml]   # run from scripts/ dir
# V2 regression harness + soak sign-off
python3 -m unittest discover -s skills/voiceattack-decoder/tests
python3 skills/voiceattack-decoder/tests/soak.py

# Decode binary VAP — v1 (legacy, in-tree during soak): XML + JSON dual output
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
- See `skills/voiceattack-decoder/docs/VAP_Format_Specification.md` (v0.2, authoritative) for binary structure details

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

Numpad: Num0-9: 96-105  Multiply: 106  Add: 107
Separator: 108  Subtract: 109  Decimal: 110  Divide: 111
```

## Project Files

**Skills:**
- `skills/voiceattack-generator/` - JSON to VAP generator (registered in manifest.json)
- `skills/voiceattack-decoder/` - Binary VAP to XML decoder (standalone tool, NOT in manifest)

**Key Files:**
- `skills/voiceattack-generator/scripts/vap_generator.py` - Generator script
- `skills/voiceattack-generator/SKILL.md` - Skill instructions (includes screenshot workflow)
- `skills/voiceattack-decoder/scripts/vap_decoder.py` - Decoder script
- `skills/voiceattack-decoder/docs/VAP_Format_Specification.md` - Binary format specification (v0.2, authoritative)

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
| SetDecimal | variable, value (number) - sets a decimal variable; XML carrier inferred pending VoiceAttack import probe |
| Write | text - writes to the VoiceAttack event LOG, not keystrokes; variable tokens like {DEC:var} work |
| BeginCondition | condition (required) - opens an if block |
| ElseIf | condition (required) - else-if branch |
| Else | (no parameters) - else branch |
| EndCondition | (no parameters) - closes the block |

### Condition Blocks

Interleave condition actions with ordinary actions to branch inside a command. `BeginCondition`/`ElseIf` require a `condition` object: `{"valueType": "Text", "operator": "<name>", "leftOperand": "<string>", "value": "<string>"}`. Text operators: Equals, Does Not Equal, Starts With, Does Not Start With, Ends With, Does Not End With, Contains, Does Not Contain, Has Been Set, Has Not Been Set. Nesting and `Else` are supported.

```json
{"trigger": "zoom [out; in]", "actions": [
  {"type": "BeginCondition", "condition": {"valueType": "Text", "operator": "Ends With", "leftOperand": "{LASTSPOKENCMD}", "value": "out"}},
  {"type": "PressKey", "keys": ["f"], "duration": 1.5},
  {"type": "ElseIf", "condition": {"valueType": "Text", "operator": "Ends With", "leftOperand": "{LASTSPOKENCMD}", "value": "in"}},
  {"type": "PressKey", "keys": ["r"], "duration": 1.5},
  {"type": "EndCondition"}
]}
```

**Scope:** `valueType` must be `"Text"` - other value types (SmallInteger/Boolean/Integer/Decimal) are rejected because their XML carriers are unverified.

**Validation:** unlike other generator defects (warn-and-drop), any malformed condition structure aborts generation with exit 1 and no output file - a dropped condition action would corrupt the block's pairing indexes and produce an importable-but-broken profile. Malformed `SetDecimal` (missing/empty `variable`, non-numeric `value`) and `Write` (missing/non-string `text`) hard-fail the same way.

### Key Names

Letters: a-z, Numbers: 0-9, F-keys: f1-f12
Special: enter, escape, space, tab, backspace, delete
Arrows: left, up, right, down
Modifiers (generic): shift, ctrl, alt, win
Modifiers (left/right): lshift, rshift, lctrl, rctrl, lalt, ralt, lwin, rwin
Numpad: numpad0-numpad9, numpad_add, numpad_subtract, numpad_multiply, numpad_divide, numpad_decimal, numpad_separator

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
