# VoiceAttack .VAP Binary Schema Analysis

## Overview

VoiceAttack profile files (`.vap`) use a custom binary format with raw deflate compression. This document describes the internal structure discovered through reverse engineering.

## File Format

### Compression
- **Algorithm:** Raw deflate (zlib without headers)
- **Decode:** `zlib.decompress(data, -15)` in Python
- **Note:** VoiceAttack also accepts uncompressed XML

### Binary Structure

```
[Header]
  +0x0000: uint32 - Total decompressed size
  +0x0004: uint32 - Offset to first data section (typically 0x59)
  +0x0008: uint32 - Offset to profile metadata
  ...      Offset table continues (4 bytes each)

[Profile Metadata]
  +0x0170: GUID (16 bytes, little-endian) - Profile ID
  +0x0180: uint32 - Profile name length
  +0x0184: string - Profile name (ASCII)

[Command Entries]
  Each command:
    GUID (16 bytes) - Command unique ID
    uint32 - Trigger phrase length
    string - Trigger phrase (e.g., "[mute; unmute] sound")
    uint32 - Number of offset entries
    uint32[] - Offset table for command properties
    [Action data follows]
```

## Analyzed Profiles

### Base Profile
- **GUID:** `99ef6cf1-b182-4318-94d5-e7e8b393c3ba`
- **Name:** `base profile`
- **Decompressed size:** 164,274 bytes
- **Commands:** ~112 unique triggers
- **Categories:** Interface, keyboard, applications, mouse, dictation

### Corinthian-4 Profile
- **Name:** `corinthian-4`
- **Decompressed size:** 545,814 bytes
- **Commands:** ~470 unique triggers
- **Purpose:** Elite Dangerous voice control
- **Integration:** EDDI (Elite Dangerous Data Interface)

## Command Trigger Syntax

| Pattern | Meaning | Example |
|---------|---------|---------|
| `[opt1; opt2]` | Alternative words | `[mute; unmute] sound` |
| `[word;]` | Optional word | `[landing;] gear` |
| `[1..4;]` | Numeric range | `down [1..4;]` |
| `word` | Literal match | `fire one` |

## Variable Tokens

### Text Variables
- `{TXT:varname}` - Text variable
- Examples: `{TXT:Environment}`, `{TXT:Ship model}`, `{TXT:System name}`

### Numeric Variables
- `{INT:varname}` - Integer variable
- `{DEC:varname}` - Decimal variable
- Examples: `{INT:count}`, `{DEC:l}`, `{INT:System visits}`

### Boolean Variables
- `{BOOL:varname}` - Boolean variable
- Examples: `{BOOL:Status lights on}`, `{BOOL:submit}`

### Special Tokens
- `{LASTSPOKENCMD}` - The last spoken command phrase
- `{CMDSEGMENT:n}` - Nth segment of spoken command

## Command Categories

Categories observed in profiles:

| Category | Description |
|----------|-------------|
| Interface | UI interactions, scrolling, zoom |
| keyboard | Key press actions |
| applications | App launching/switching |
| mouse | Mouse clicks, movement |
| dictation | Voice dictation control |
| flight/navigation | Ship movement (ED) |
| combat & targeting | Weapons/targeting (ED) |
| takeoff & landing | Launch/dock (ED) |
| power management | Ship power (ED) |
| events | Event-driven commands |

## EDDI Integration (Elite Dangerous)

Event triggers use double-parenthesis syntax:
```
((EDDI docked))
((EDDI entered normal space))
((EDDI entered supercruise))
((EDDI jumped))
((EDDI undocked))
((EDDI fighter rebuilt))
```

EDDI-specific variables:
```
{TXT:EDDI location bodytype}
{TXT:EDDI entered signal source source}
{INT:EDDI entered signal source threat}
{INT:EDDI fighter rebuilt id}
{BOOL:EDDI near surface approaching_surface}
```

## Action Types (from XML reference)

| ActionType | Purpose | Key Fields |
|------------|---------|------------|
| PressKey | Press and release | KeyCodes, Duration |
| KeyDown | Hold key down | KeyCodes |
| KeyUp | Release key | KeyCodes |
| MouseAction | Mouse operations | Context (LC/RC/MC/LDC/SF/SB) |
| Say | Text-to-speech | Context (text), X (volume), Y (rate) |
| Pause | Wait/delay | Duration |
| ExecuteCommand | Run another command | Context (command name) |
| Launch | Launch application | Context (path) |
| SetClipboard | Set clipboard text | Context (text) |

## Key Code Reference

Windows Virtual Key Codes stored as uint16:
```
A-Z:     65-90
0-9:     48-57
F1-F12:  112-123
Enter:   13
Escape:  27
Space:   32
Tab:     9
Left:    37
Up:      38
Right:   39
Down:    40
Shift:   16
Ctrl:    17
Alt:     18
Win:     91
```

## Files Analyzed

| File | Size | Decompressed | Commands |
|------|------|--------------|----------|
| base profile-Profile.vap | 21,624 | 164,274 | ~112 |
| corinthian-4-Profile.vap | 82,501 | 545,814 | ~470 |

## Sample Command JSON Schema

```json
{
  "profile": {
    "guid": "99ef6cf1-b182-4318-94d5-e7e8b393c3ba",
    "name": "base profile"
  },
  "commands": [
    {
      "guid": "bbc0274d-d800-49cf-a83b-cd427c85454a",
      "trigger": "[mute; unmute] sound",
      "category": "Interface",
      "actions": [
        {
          "type": "PressKey",
          "keyCodes": [77],
          "duration": 0.1
        }
      ]
    }
  ]
}
```

## Complete Command Lists

### Base Profile Commands (103 total)

**Application Switching:**
- `[open; switch to] chrome` - Switch to Google Chrome
- `[open; switch to] discord` - Launch Discord
- `[open; switch to] voiceattack` - Switch to VoiceAttack

**Keyboard (NATO Phonetic):**
- `[press; hold] alpha` through `[press; hold] zulu` - A-Z keys
- `[press; hold] control/shift/alt` - Modifier keys
- `[press; hold] up/down/left/right` - Arrow keys

**Mouse:**
- `left click`, `right click`, `middle click`
- `scroll up`, `scroll down`
- `centre mouse`, `unlock mouse`

**Interface:**
- `[mute; unmute] sound`
- `zoom in [more;]`, `zoom out [more;]`
- `select all`, `copy`, `paste`

### Corinthian-4 Commands (219 total)

**Flight/Navigation:**
- `throttle [full;max;maximum;100%]`
- `throttle [25%;one-quarter]`
- `all stop`, `engines [max; maximum]`
- `flight assist` toggle

**Combat & Targeting:**
- `fire one`, `fire two`, `cease fire`
- `[target;] next enemy`, `[target;] nearest enemy`
- `cycle [enemy;hostile] targets`
- `[deploy; ready; retract] [weapons; hard points]`

**Ship Systems:**
- `[deploy; lower; raise; retract;] [landing;] gear [down; up;]`
- `[deploy;] heat sink`, `[deploy;fire] chaff`
- `[flood;spot;] lights [on; off;]`

**EDDI Events:**
- `((EDDI docked))` - Triggered on station dock
- `((EDDI jumped))` - Triggered on hyperspace jump
- `((EDDI entered supercruise))` - Supercruise entry

## Generated Artifacts

| File | Description |
|------|-------------|
| `base_profile_export.json` | Complete JSON export of base profile |
| `corinthian4_export.json` | Complete JSON export of Corinthian-4 |
| `VAP_Binary_Schema_Analysis.md` | This document |

## Next Steps

1. Parse action sequences from binary data
2. Map all ActionType binary encodings
3. Extract condition/loop structures
4. Build complete JSON exporter with actions
5. Create profile generator from JSON
