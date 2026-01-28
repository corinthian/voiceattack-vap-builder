# VoiceAttack .VAP File Format

Technical documentation for VoiceAttack profile files (.vap).

## Overview

VoiceAttack stores voice command profiles in `.vap` files using:
- **Compression**: Raw deflate (zlib with wbits=-15)
- **Binary format**: Little-endian integers, .NET-style GUIDs, length-prefixed strings

## File Structure

### Compression Layer

```
Raw file → zlib.decompress(data, -15) → Decompressed binary
```

### Decompressed Binary Structure

```
+------------------+
| Header           |
|  offset 0:  uint32 total_size
|  offset 4:  uint32 item_count
|  offset 8:  uint32[item_count] offset_table
+------------------+
| Profile Info     |
|  - GUID (16 bytes)
|  - Length-prefixed string: profile_name
|  - uint32: command_count
|  - uint32[]: command_offset_table
+------------------+
| Commands[]       |
|  - GUID (16 bytes)
|  - Length-prefixed string: phrase
|  - Action data (variable)
|  - Length-prefixed string: category
+------------------+
```

## Data Types

### uint32 (4 bytes)
Little-endian unsigned 32-bit integer.

```python
value = struct.unpack('<I', data[offset:offset+4])[0]
```

### GUID (16 bytes)
.NET binary format with mixed endianness:

| Bytes | Format | Component |
|-------|--------|-----------|
| 0-3   | Little-endian uint32 | Part A |
| 4-5   | Little-endian uint16 | Part B |
| 6-7   | Little-endian uint16 | Part C |
| 8-15  | Big-endian bytes | Part D |

```python
def read_guid(data, pos):
    a = struct.unpack('<I', data[pos:pos+4])[0]
    b = struct.unpack('<H', data[pos+4:pos+6])[0]
    c = struct.unpack('<H', data[pos+6:pos+8])[0]
    d = data[pos+8:pos+16].hex()
    return f"{a:08x}-{b:04x}-{c:04x}-{d[:4]}-{d[4:]}"
```

### Length-Prefixed String
- uint32 length prefix
- UTF-8 encoded bytes

```python
length = struct.unpack('<I', data[pos:pos+4])[0]
string = data[pos+4:pos+4+length].decode('utf-8')
```

## Key Action Structure

Key press actions follow this 56-byte pattern:

| Offset | Size | Description |
|--------|------|-------------|
| 0      | 4    | Zeros (padding) |
| 4      | 4    | `0x00010000` (action type flag) |
| 8      | 4    | Virtual Key Code |
| 12     | 4    | Zeros |
| 16     | 16   | `0xFFFFFFFF` padding |
| 32     | 16   | Zeros |
| 48     | 8    | `0xFFFFFFFF` terminator |

### Virtual Key Codes

Common codes used in VoiceAttack profiles:

| Code | Key | Code | Key |
|------|-----|------|-----|
| 0x41-0x5A | A-Z | 0x30-0x39 | 0-9 |
| 0xA0 | LSHIFT | 0xA1 | RSHIFT |
| 0xA2 | LCTRL | 0xA3 | RCTRL |
| 0xA4 | LALT | 0xA5 | RALT |
| 0x5B | LWIN | 0x5C | RWIN |
| 0x25 | LEFT | 0x26 | UP |
| 0x27 | RIGHT | 0x28 | DOWN |
| 0x08 | BACKSPACE | 0x09 | TAB |
| 0x0D | ENTER | 0x1B | ESCAPE |
| 0x20 | SPACE | 0x2E | DELETE |

Full reference: [Microsoft Virtual-Key Codes](https://docs.microsoft.com/en-us/windows/win32/inputdev/virtual-key-codes)

## Command Structure

Each command contains:

1. **GUID** (16 bytes) - Unique identifier
2. **Phrase** (length-prefixed string) - Voice trigger, often with alternatives:
   - `[press; hold] alpha` → "press alpha" or "hold alpha"
   - `[open; switch to] chrome` → "open chrome" or "switch to chrome"
3. **Actions** - Key presses, application launches, etc.
4. **Category** (length-prefixed string) - Organizational grouping

### Known Categories
- `keyboard` - Key press commands
- `applications` - App launch commands
- `Interface` - UI control commands
- `system` - System commands
- `navigation` - Navigation commands

## Mouse Action Structure

Mouse actions use a context code stored as a length-prefixed string, with scroll clicks stored as a double 24 bytes before the context code.

### Mouse Action Context Codes

Format: `{button}{action}`

| Button | Code | Button | Code |
|--------|------|--------|------|
| Left | L | Back | 4 |
| Middle | M | Forward | 5 |
| Right | R | | |

| Action | Code | Action | Code |
|--------|------|--------|------|
| Click | C | Down (press) | D |
| Double Click | DC | Up (release) | U |
| Triple Click | TC | Toggle | T |

**Examples:** `LC` (left click), `RDC` (right double click), `MTC` (middle triple click), `4D` (back down), `5T` (forward toggle)

### Scroll Codes

| Code | Direction |
|------|-----------|
| SF | Scroll Forward (up) |
| SB | Scroll Back (down) |
| SL | Scroll Left |
| SR | Scroll Right |

### Scroll Click Count (Binary)

Scroll clicks are stored as an IEEE 754 double at offset -24 from the context code:

```
Offset -24: double (scroll clicks)  e.g., 0x3ff0... = 1.0, 0x4024... = 10.0
Offset -16: zeros
Offset -8:  zeros
Offset -2:  uint32 length prefix (2 for "SF", "SB", etc.)
Offset 0:   context string
```

### Scroll Click Count (XML)

In XML format, scroll clicks are stored in the `<Duration>` field:

```xml
<ActionType>MouseAction</ActionType>
<Duration>5</Duration>  <!-- 5 scroll clicks -->
<Context>SL</Context>   <!-- scroll left -->
```

## Application Launch Actions

App launch commands contain:
- Executable path as length-prefixed string
- Path may start with `*` for window title matching

Example: `*Google Chrome` matches windows with "Google Chrome" in title.

## Example Data

### Sample Profile Header
```
Offset 0x0000: F2 81 02 00  (total_size = 164,274)
Offset 0x0004: 59 00 00 00  (item_count = 89)
```

### Sample Command Phrase
```
Offset 0x1234: 13 00 00 00  (length = 19)
Offset 0x1238: "[press; hold] alpha"
```

### Sample Key Action
```
00 00 00 00  // padding
00 00 01 00  // action type (0x00010000)
41 00 00 00  // VK_A (0x41 = 'A')
00 00 00 00  // padding
FF FF FF FF FF FF FF FF FF FF FF FF FF FF FF FF  // padding
00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00  // zeros
FF FF FF FF FF FF FF FF  // terminator
```

## Decompression Code

```python
import zlib

with open('profile.vap', 'rb') as f:
    compressed = f.read()

decompressed = zlib.decompress(compressed, -15)  # raw deflate
```

## Known Limitations

- Action types beyond key presses not fully documented
- Some binary sections contain unknown data
- Modifier key combinations may have additional encoding

## Tools

- `vap_decoder.py` - Python decoder script
- Hex editor for manual inspection
- zlib utilities for decompression testing

## References

- VoiceAttack official site: https://voiceattack.com/
- Microsoft Virtual-Key Codes: https://docs.microsoft.com/en-us/windows/win32/inputdev/virtual-key-codes
- .NET GUID binary format: https://docs.microsoft.com/en-us/dotnet/api/system.guid
