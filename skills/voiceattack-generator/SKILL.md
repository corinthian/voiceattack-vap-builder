---
name: voiceattack-generator
description: Generate VoiceAttack .vap profiles from JSON
argument-hint: [json-file] [output.vap]
allowed-tools:
  - Read
  - Write
  - "Bash(python3:*)"
---

# VoiceAttack Profile Generator

Generate valid VoiceAttack `.vap` profiles from simple JSON input.

## Usage

```
/voiceattack-generator <input.json> [output.vap]
```

If output file is omitted, uses input filename with `.vap` extension.

## Instructions

When the user invokes this skill:

1. Read the input JSON file
2. Run the generator script:
   ```bash
   python3 /path/to/scripts/vap_generator.py input.json output.vap
   ```
3. Report success with command count

## JSON Input Format

```json
{
  "name": "Profile Name",
  "commands": [
    {"trigger": "[spoken; phrase]", "key": "a", "category": "keyboard"},
    {"trigger": "click", "mouse": "left_click", "category": "mouse"},
    {"trigger": "copy", "actions": [...], "category": "keyboard"}
  ]
}
```

## Supported Action Types

| Type | Description | Parameters |
|------|-------------|------------|
| PressKey | Press and release key(s) | keys, duration (default 0.1) |
| KeyDown | Hold key down | keys |
| KeyUp | Release held key | keys |
| MouseAction | Mouse click/scroll | action, scroll_clicks |
| Pause | Wait | duration (seconds) |
| Say | Text-to-speech | text, volume (0-100), rate |

## Mouse Actions

| Action | Code |
|--------|------|
| left_click | LC |
| right_click | RC |
| middle_click | MC |
| double_click | LDC |
| scroll_up | SF |
| scroll_down | SB |

## Key Names

**Letters:** a-z
**Numbers:** 0-9
**Function:** f1-f12
**Special:** enter, escape, space, tab, backspace, delete, insert, home, end, pageup, pagedown
**Arrows:** left, up, right, down
**Modifiers:** shift, ctrl, alt, win
**Punctuation:** comma, period, slash, semicolon, quote, minus, equals

## Command Phrase Syntax

- `[word1; word2]` - Alternatives (either triggers command)
- `[word;]` - Optional word (trailing semicolon)

Examples:
- `"[press;] alpha"` matches "press alpha" or "alpha"
- `"[open; show] map"` matches "open map" or "show map"
- `"zoom [in;]"` matches "zoom" or "zoom in"

## Section Markers

Use `{"_section": "..."}` entries to organize your JSON. They're ignored by the generator:

```json
{"_section": "=== MOVEMENT ==="},
{"trigger": "forward", "key": "w"},
{"trigger": "back", "key": "s"},
{"_section": "=== COMBAT ==="},
{"trigger": "fire", "key": "space"}
```
