# VoiceAttack Profile Tools

Claude Code plugin for generating VoiceAttack voice command profiles from JSON.

## Installation

```bash
/plugin install https://github.com/corinthian/voiceattack-vap-builder
```

## Quick Start: Screenshot Method

The fastest way to create a profile - no manual JSON editing required.

1. Take a screenshot of your game's keybinding/controls screen
2. Provide the screenshot to Claude Code: "Create a VoiceAttack profile from this screenshot"
3. Claude extracts keybindings and generates both the JSON and VAP files
4. Import the `.vap` file into VoiceAttack (File > Import Profile)

## Manual Method: JSON Definition

1. Create a JSON file with your commands:

```json
{
  "name": "My Game Profile",
  "commands": [
    {"trigger": "fire", "key": "space", "category": "combat"},
    {"trigger": "reload", "key": "r", "category": "combat"},
    {"trigger": "left click", "mouse": "left_click", "category": "mouse"}
  ]
}
```

2. Generate the VoiceAttack profile:

```
/voiceattack-generator my_profile.json output.vap
```

3. Import `output.vap` into VoiceAttack (File > Import Profile)

## JSON Format

See `skills/voiceattack-generator/examples/` for complete examples.

### Simple Key Press
```json
{"trigger": "[press;] alpha", "key": "a", "category": "keyboard"}
```

### Mouse Action
```json
{"trigger": "left click", "mouse": "left_click", "category": "mouse"}
```

### Multi-Action Sequence (e.g., Ctrl+C)
```json
{
  "trigger": "copy",
  "actions": [
    {"type": "KeyDown", "keys": ["ctrl"]},
    {"type": "PressKey", "keys": ["c"], "duration": 0.1},
    {"type": "KeyUp", "keys": ["ctrl"]}
  ],
  "category": "keyboard"
}
```

### Section Markers (ignored by generator)
```json
{"_section": "=== COMBAT ==="}
```

## Supported Actions

This generator covers basic input simulation - suitable for gaming and simple automation. Special characters (`&`, `<`, `>`) in trigger phrases are automatically XML-escaped.

| Action | Description |
|--------|-------------|
| PressKey | Press and release a key |
| KeyDown / KeyUp | Hold or release a key (for combos like Ctrl+C) |
| KeyToggle | Toggle key state (press once = down, again = up) |
| MouseAction | Clicks (left, right, middle, double) and scroll (up, down) |
| Pause | Wait between actions |
| Say | Text-to-speech output |

**Not supported:** Variables, conditionals, loops, launching applications, clipboard operations, executing other commands, or any advanced VoiceAttack logic. For those features, edit the profile directly in VoiceAttack after import.

## Command Phrase Syntax

- `[word1; word2]` - alternatives (either triggers the command)
- `[word;]` - optional word (trailing semicolon)

Examples:
- `"[press;] alpha"` - "press alpha" or "alpha" both work
- `"[open; show] map"` - "open map" or "show map" both work

## Supported Keys

Letters: a-z | Numbers: 0-9 | F-keys: f1-f12
Special: enter, escape, space, tab, backspace, delete
Arrows: left, up, right, down
Modifiers: shift, ctrl, alt, win

## VoiceAttack

[VoiceAttack](https://voiceattack.com/) is a Windows application that executes commands in response to spoken phrases. It's commonly used for:
- Gaming accessibility
- Hands-free PC control
- Voice macros

## License

MIT
