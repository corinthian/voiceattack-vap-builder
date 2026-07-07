#!/usr/bin/env python3
"""
VoiceAttack .VAP Profile Decoder

Decodes VoiceAttack .vap profile files from compressed binary format to:
- XML: Human-readable decoded structure
- JSON: Generator-compatible format for round-trip editing

Usage:
    python vap_decoder.py <input.vap> [output_base]

Output:
    If output_base is specified: output_base.xml and output_base.json
    If not specified: input_decoded.xml and input_decoded.json
    Use --stdout to print XML to stdout without writing files
"""

import json
import re
import struct
import sys
import zlib
import xml.etree.ElementTree as ET
from xml.dom import minidom
from pathlib import Path
from typing import Optional


# Virtual Key Code mappings
# Mouse context code to generator-compatible name mapping
CONTEXT_TO_GENERATOR = {
    # Left button
    'LC': 'left_click',
    'LDC': 'left_double_click',
    'LTC': 'left_triple_click',
    'LD': 'left_down',
    'LU': 'left_up',
    'LT': 'left_toggle',
    # Middle button
    'MC': 'middle_click',
    'MDC': 'middle_double_click',
    'MTC': 'middle_triple_click',
    'MD': 'middle_down',
    'MU': 'middle_up',
    'MT': 'middle_toggle',
    # Right button
    'RC': 'right_click',
    'RDC': 'right_double_click',
    'RTC': 'right_triple_click',
    'RD': 'right_down',
    'RU': 'right_up',
    'RT': 'right_toggle',
    # Back button (X1)
    '4C': 'back_click',
    '4DC': 'back_double_click',
    '4TC': 'back_triple_click',
    '4D': 'back_down',
    '4U': 'back_up',
    '4T': 'back_toggle',
    # Forward button (X2)
    '5C': 'forward_click',
    '5DC': 'forward_double_click',
    '5TC': 'forward_triple_click',
    '5D': 'forward_down',
    '5U': 'forward_up',
    '5T': 'forward_toggle',
    # Scroll
    'SF': 'scroll_up',
    'SB': 'scroll_down',
    'SL': 'scroll_left',
    'SR': 'scroll_right',
}

# All known mouse context codes (for pattern matching)
MOUSE_CONTEXT_CODES = set(CONTEXT_TO_GENERATOR.keys())

VK_CODES = {
    # Letters A-Z
    0x41: 'A', 0x42: 'B', 0x43: 'C', 0x44: 'D', 0x45: 'E',
    0x46: 'F', 0x47: 'G', 0x48: 'H', 0x49: 'I', 0x4A: 'J',
    0x4B: 'K', 0x4C: 'L', 0x4D: 'M', 0x4E: 'N', 0x4F: 'O',
    0x50: 'P', 0x51: 'Q', 0x52: 'R', 0x53: 'S', 0x54: 'T',
    0x55: 'U', 0x56: 'V', 0x57: 'W', 0x58: 'X', 0x59: 'Y',
    0x5A: 'Z',
    # Numbers 0-9
    0x30: '0', 0x31: '1', 0x32: '2', 0x33: '3', 0x34: '4',
    0x35: '5', 0x36: '6', 0x37: '7', 0x38: '8', 0x39: '9',
    # Function keys
    0x70: 'F1', 0x71: 'F2', 0x72: 'F3', 0x73: 'F4',
    0x74: 'F5', 0x75: 'F6', 0x76: 'F7', 0x77: 'F8',
    0x78: 'F9', 0x79: 'F10', 0x7A: 'F11', 0x7B: 'F12',
    # Modifiers
    0xA0: 'LSHIFT', 0xA1: 'RSHIFT',
    0xA2: 'LCTRL', 0xA3: 'RCTRL',
    0xA4: 'LALT', 0xA5: 'RALT',
    0x5B: 'LWIN', 0x5C: 'RWIN',
    0x10: 'SHIFT', 0x11: 'CTRL', 0x12: 'ALT',
    # Navigation
    0x25: 'LEFT', 0x26: 'UP', 0x27: 'RIGHT', 0x28: 'DOWN',
    0x21: 'PAGEUP', 0x22: 'PAGEDOWN',
    0x23: 'END', 0x24: 'HOME',
    0x2D: 'INSERT', 0x2E: 'DELETE',
    # Common keys
    0x08: 'BACKSPACE', 0x09: 'TAB', 0x0D: 'ENTER', 0x1B: 'ESCAPE',
    0x20: 'SPACE', 0x14: 'CAPSLOCK', 0x90: 'NUMLOCK', 0x91: 'SCROLLLOCK',
    0x2C: 'PRINTSCREEN', 0x13: 'PAUSE',
    # Punctuation
    0xBA: 'SEMICOLON', 0xBB: 'EQUALS', 0xBC: 'COMMA', 0xBD: 'MINUS',
    0xBE: 'PERIOD', 0xBF: 'SLASH', 0xC0: 'BACKTICK',
    0xDB: 'LBRACKET', 0xDC: 'BACKSLASH', 0xDD: 'RBRACKET', 0xDE: 'QUOTE',
    # Numpad
    0x60: 'NUMPAD0', 0x61: 'NUMPAD1', 0x62: 'NUMPAD2', 0x63: 'NUMPAD3',
    0x64: 'NUMPAD4', 0x65: 'NUMPAD5', 0x66: 'NUMPAD6', 0x67: 'NUMPAD7',
    0x68: 'NUMPAD8', 0x69: 'NUMPAD9',
    0x6A: 'MULTIPLY', 0x6B: 'ADD', 0x6C: 'SEPARATOR',
    0x6D: 'SUBTRACT', 0x6E: 'DECIMAL', 0x6F: 'DIVIDE',
    # Media keys
    0xAD: 'MUTE', 0xAE: 'VOLUMEDOWN', 0xAF: 'VOLUMEUP',
    0xB0: 'NEXTTRACK', 0xB1: 'PREVTRACK', 0xB2: 'STOP', 0xB3: 'PLAYPAUSE',
}


def decompress_vap(filepath: str) -> bytes:
    """Decompress a .vap file using raw deflate."""
    with open(filepath, 'rb') as f:
        compressed = f.read()
    return zlib.decompress(compressed, -15)  # raw deflate (wbits=-15)


def read_uint32(data: bytes, pos: int) -> tuple[int, int]:
    """Read uint32 little-endian, return (value, new_position)."""
    return struct.unpack('<I', data[pos:pos+4])[0], pos + 4


def read_guid(data: bytes, pos: int) -> tuple[str, int]:
    """Read .NET GUID format, return (guid_string, new_position)."""
    guid_bytes = data[pos:pos+16]
    a = struct.unpack('<I', guid_bytes[0:4])[0]
    b = struct.unpack('<H', guid_bytes[4:6])[0]
    c = struct.unpack('<H', guid_bytes[6:8])[0]
    d = guid_bytes[8:16].hex()
    guid_str = f"{a:08x}-{b:04x}-{c:04x}-{d[:4]}-{d[4:]}"
    return guid_str, pos + 16


def read_string(data: bytes, pos: int) -> tuple[Optional[str], int]:
    """Read length-prefixed UTF-8 string, return (string, new_position)."""
    length, pos = read_uint32(data, pos)
    if length == 0 or length > 10000:  # sanity check
        return None, pos
    try:
        string = data[pos:pos+length].decode('utf-8')
        return string, pos + length
    except UnicodeDecodeError:
        return None, pos + length


def find_key_actions(data: bytes, start: int, end: int) -> list[dict]:
    """
    Find all key actions in a data range by pattern matching.

    Key action record:
    - 8 bytes at marker-12: IEEE-754 double key-hold Duration
    - marker: 00 00 00 00 (zeros) + 01 00 00 00 (action type 1 = PressKey)
    - 2 bytes at marker+8: VK code (little-endian uint16)
    - suffix varies by profile (zero padding and/or FF run) and is NOT validated;
      the Duration sanity check is the phantom filter instead. Condition objects
      alias the 01 00 00 00 marker with garbage in the Duration slot (FF-runs,
      denormals ~1e-304), while real records hold either a sane press time
      (0.001-60s; observed 0.03-1.5) or exactly 0.0 (KeyDown/KeyUp-style
      "press down X" / "release X" records - all-zero slot, no hold time).
      See Decoder_Accuracy_Findings_corinthian_CSV.md Findings 3 and 4.
    """
    actions = []
    pattern_prefix = b'\x00\x00\x00\x00\x01\x00\x00\x00'

    i = start
    while i < end - 16:
        if data[i:i+8] == pattern_prefix:
            vk_code = struct.unpack('<H', data[i+8:i+10])[0]
            dur_ok = False
            duration = None
            if i >= 12:
                d = struct.unpack('<d', data[i-12:i-4])[0]
                if d == 0.0:
                    # KeyDown/KeyUp-style record: no hold time. Condition operands
                    # can also alias an all-zero slot, so additionally require the
                    # record suffix: VK zero-padded then FF-terminated within 6 bytes
                    # (both observed real shapes; operand strings fail this).
                    tail = data[i+10:i+16]
                    dur_ok = tail[:2] == b'\xff\xff' or tail == b'\x00\x00\x00\x00\xff\xff'
                elif 0.001 <= d <= 60:  # NaN/denormal/FF-run garbage all fail
                    dur_ok = True
                    duration = round(d, 4)
            if 0 < vk_code < 0x200 and dur_ok:
                key_name = VK_CODES.get(vk_code, f"VK_0x{vk_code:02X}")
                action = {
                    'type': 'keypress',
                    'vk_code': vk_code,
                    'key': key_name
                }
                if duration is not None:
                    action['duration'] = duration
                actions.append(action)
                i += 16  # Skip past this action
                continue
        i += 1
    return actions


def find_mouse_actions(data: bytes, start: int, end: int) -> list[dict]:
    """
    Find all mouse actions in a data range by pattern matching.

    Mouse action pattern:
    - Length-prefixed string containing context code (e.g., 02 00 00 00 4C 43 = "LC")
    - Followed by FF FF FF FF FF FF FF FF... padding

    Scroll actions have click count as IEEE 754 double at offset -20 from length prefix.

    Hits are collected per context code, then sorted by byte position: set iteration
    order is hash-randomized per process, so without the sort the action order of a
    multi-mouse-action command changes from run to run.
    """
    hits = []

    # Look for each known context code
    for context_code in MOUSE_CONTEXT_CODES:
        code_bytes = context_code.encode('ascii')
        code_len = len(code_bytes)
        # Pattern: length (4 bytes) + code bytes
        length_bytes = struct.pack('<I', code_len)
        pattern = length_bytes + code_bytes

        i = start
        while i < end - len(pattern):
            pos = data.find(pattern, i, end)
            if pos == -1:
                break

            # Verify this is likely a mouse action (check for FF padding after)
            after_pos = pos + len(pattern)
            if after_pos + 4 <= end and data[after_pos:after_pos+4] == b'\xff\xff\xff\xff':
                action = {
                    'type': 'mouse',
                    'context_code': context_code,
                    'generator_name': CONTEXT_TO_GENERATOR[context_code]
                }

                # For scroll actions, extract click count from offset -20
                if context_code in ('SF', 'SB', 'SL', 'SR'):
                    click_offset = pos - 20
                    if click_offset >= start and click_offset + 8 <= end:
                        try:
                            click_count = struct.unpack('<d', data[click_offset:click_offset+8])[0]
                            # Sanity check: should be a reasonable number
                            if 0 < click_count < 1000:
                                action['scroll_clicks'] = int(click_count)
                        except struct.error:
                            pass

                hits.append((pos, action))
                i = pos + len(pattern)
            else:
                i = pos + 1

    return [action for _pos, action in sorted(hits, key=lambda h: h[0])]


def _guid_is_valid(guid_bytes: bytes) -> bool:
    """Distinguish a real (random) command GUID from field padding / leaf values.

    VoiceAttack pads and terminates leaf fields with 0xFFFFFFFF and 0x00000000 runs,
    so those bytes precede categories, Say text and mouse contexts - never a command.
    """
    if len(guid_bytes) < 16:
        return False
    words = struct.unpack('<4I', guid_bytes[:16])
    if words[0] == 0 or words[0] == 0xFFFFFFFF:
        return False
    if any(w == 0xFFFFFFFF for w in words):
        return False
    if guid_bytes.count(0) >= 8:
        return False
    if b'\xff\xff\xff\xff' in guid_bytes:
        return False
    return True


def _match_command_signature(data: bytes, pos: int) -> Optional[dict]:
    """Test the per-command signature at pos, the structural anchor for detection:

        [16-byte GUID][uint32 length][UTF-8 phrase][uint32 count][count x uint32 offsets]

    Returns a candidate dict, or None if the signature does not hold. No category or
    other content is consulted - detection is purely structural.
    """
    n = len(data)
    if pos + 20 > n:
        return None
    guid_bytes = data[pos:pos+16]
    if not _guid_is_valid(guid_bytes):
        return None
    length = struct.unpack('<I', data[pos+16:pos+20])[0]
    if not (1 <= length <= 500):
        return None
    phrase_end = pos + 20 + length
    if phrase_end + 4 > n:
        return None
    try:
        phrase = data[pos+20:phrase_end].decode('utf-8')
    except UnicodeDecodeError:
        return None
    if not phrase.isprintable():
        return None
    count = struct.unpack('<I', data[phrase_end:phrase_end+4])[0]
    if not (1 <= count <= 128):
        return None
    table_start = phrase_end + 4
    table_end = table_start + count * 4
    if table_end > n:
        return None
    offsets = struct.unpack('<%dI' % count, data[table_start:table_end])
    bad_idx = next((i for i, o in enumerate(offsets) if o >= n), None)
    if bad_idx == 0:
        return None
    if bad_idx is not None:
        # count can overrun the true table length (corinthian 'set ... fire':
        # count 37, 35 real entries, then child-GUID bytes read as offsets).
        # Truncate at the first out-of-range entry and keep the command;
        # detection does not depend on the table. Finding 1 in
        # Decoder_Accuracy_Findings_corinthian_CSV.md.
        offsets = offsets[:bad_idx]
        count = bad_idx
        table_end = table_start + count * 4
    # A run of identical offsets signals garbage; a single offset is legitimate.
    if count >= 2 and len(set(offsets)) == 1:
        return None
    return {
        'pos': pos,
        'guid_bytes': guid_bytes,
        'phrase': phrase,
        'phrase_end': phrase_end,  # also the count position / start of action data
        'count': count,
        'table_end': table_end,
    }


# A version-like string (e.g. "2.1.8") is a profile-level field, never a category.
_VERSION_RE = re.compile(r'\d+(\.\d+)+$')


def _strings_in_range(data: bytes, start: int, end: int,
                      min_length: int = 1, max_length: int = 500) -> list[tuple[int, str]]:
    """Return (pos, string) for every length-prefixed printable UTF-8 string in [start, end)."""
    out = []
    i = max(0, start)
    limit = min(end, len(data) - 4)
    while i < limit:
        length = struct.unpack('<I', data[i:i+4])[0]
        if min_length <= length <= max_length and i + 4 + length <= len(data):
            try:
                s = data[i+4:i+4+length].decode('utf-8')
                if s.isprintable():
                    out.append((i, s))
            except (UnicodeDecodeError, IndexError):
                pass
        i += 1
    return out


def _extract_category(data: bytes, start: int, end: int) -> str:
    """Read the category as a free-form field within the command bound - no whitelist.

    Heuristic (category extraction only; command detection never depends on this):
    skip known non-category operands, then prefer the last remaining printable string.
    See Decoder_Category_Anchor_Fix_Plan.md for why this is the weak link.
    """
    candidate = None
    for _pos, s in _strings_in_range(data, start, end, min_length=1):
        if s in MOUSE_CONTEXT_CODES:
            continue
        if s.startswith('{') and s.endswith('}'):  # token operand, e.g. {LASTSPOKENCMD}
            continue
        low = s.lower()
        if '\\' in s or '.exe' in low or '.wav' in low or s.startswith('*'):
            continue  # path / window / sound operand (a bare '/' is NOT a path
            # indicator: 'flight/navigation' is a real category - Finding 2)
        if _VERSION_RE.match(s):
            continue  # version string
        candidate = s
    return candidate or 'uncategorized'


def find_commands(data: bytes, profile_name: Optional[str] = None,
                  profile_start: Optional[int] = None,
                  profile_guid_bytes: Optional[bytes] = None) -> list[dict]:
    """Detect and parse commands structurally, with no category whitelist.

    Every command begins with the per-command signature (GUID + length-prefixed phrase +
    property-offset table). Detection anchors on that structure; the category is read as a
    plain field, never used as a gate. Recognition never requires a known category name.
    """
    n = len(data)

    # Pass 1: collect structural command hits.
    hits = []
    pos = 0
    while pos < n - 20:
        cand = _match_command_signature(data, pos)
        if cand is None:
            pos += 1
            continue
        # The profile's own header record matches the same signature - skip it.
        is_profile = (
            (profile_start is not None and cand['pos'] == profile_start)
            or (profile_guid_bytes is not None and cand['guid_bytes'] == profile_guid_bytes)
        )
        if is_profile:
            pos = cand['table_end']
            continue
        hits.append(cand)
        pos = cand['table_end']

    # Pass 2: turn each hit into a command, bounded by the next hit (or end of buffer).
    commands = []
    for i, h in enumerate(hits):
        bound = hits[i+1]['pos'] if i + 1 < len(hits) else n
        guid, _ = read_guid(data, h['pos'])
        category = _extract_category(data, h['table_end'], bound)

        # Action decoding is unchanged and out of scope for this fix; reuse the existing
        # pattern matchers over the command's precise byte range.
        action_start = h['phrase_end']
        actions = []
        actions.extend(find_key_actions(data, action_start, bound))
        actions.extend(find_mouse_actions(data, action_start, bound))
        for _str_pos, s in _strings_in_range(data, action_start, bound, min_length=2):
            if '.exe' in s.lower() or s.startswith('*'):
                actions.append({'type': 'run_application', 'path': s})
                break

        commands.append({
            'guid': guid,
            'phrase': h['phrase'],
            'category': category,
            'actions': actions,
        })

    return commands


def parse_profile(data: bytes) -> dict:
    """Parse the profile header and commands.

    Header layout: total_size @0, member count @4, top-level offset table @8. The first
    offset table entry points at the profile record (GUID + length-prefixed name). The
    old parser used 8 + item_count*4, which is four bytes early and corrupts the GUID.
    """
    profile_start, _ = read_uint32(data, 8)  # first top-level offset table entry

    profile_guid_bytes = data[profile_start:profile_start+16]
    profile_guid, pos = read_guid(data, profile_start)
    profile_name, pos = read_string(data, pos)

    # Fallback: if the name did not read cleanly, take the first plausible string.
    if not profile_name:
        for _str_pos, s in _strings_in_range(data, 0, len(data), min_length=4):
            if s not in MOUSE_CONTEXT_CODES:
                profile_name = s
                break

    # Detection is structural and profile-header aware (self-match filtering).
    commands = find_commands(data, profile_name, profile_start, profile_guid_bytes)

    return {
        'guid': profile_guid,
        'name': profile_name or 'Unknown Profile',
        'commands': commands
    }


def to_xml(profile: dict) -> str:
    """Convert profile dict to XML string."""
    root = ET.Element('Profile')

    ET.SubElement(root, 'Id').text = profile['guid']
    ET.SubElement(root, 'Name').text = profile['name']

    commands_elem = ET.SubElement(root, 'Commands')

    for cmd in profile['commands']:
        cmd_elem = ET.SubElement(commands_elem, 'Command')
        ET.SubElement(cmd_elem, 'Id').text = cmd['guid']
        ET.SubElement(cmd_elem, 'Phrase').text = cmd['phrase']
        ET.SubElement(cmd_elem, 'Category').text = cmd['category']

        if cmd['actions']:
            actions_elem = ET.SubElement(cmd_elem, 'Actions')
            for action in cmd['actions']:
                action_elem = ET.SubElement(actions_elem, 'Action')
                ET.SubElement(action_elem, 'Type').text = action['type']

                if action['type'] == 'keypress':
                    ET.SubElement(action_elem, 'Key').text = action['key']
                    ET.SubElement(action_elem, 'VKCode').text = f"0x{action['vk_code']:02X}"
                    if 'duration' in action:
                        ET.SubElement(action_elem, 'Duration').text = str(action['duration'])
                elif action['type'] == 'mouse':
                    ET.SubElement(action_elem, 'ContextCode').text = action['context_code']
                    ET.SubElement(action_elem, 'GeneratorName').text = action['generator_name']
                    if 'scroll_clicks' in action:
                        ET.SubElement(action_elem, 'ScrollClicks').text = str(action['scroll_clicks'])
                elif action['type'] == 'run_application':
                    ET.SubElement(action_elem, 'Path').text = action['path']

    # Pretty print
    xml_str = ET.tostring(root, encoding='unicode')
    dom = minidom.parseString(xml_str)
    return dom.toprettyxml(indent='  ', encoding=None)


def to_json(profile: dict) -> str:
    """Convert profile dict to generator-compatible JSON."""
    commands = []

    for cmd in profile['commands']:
        json_cmd = {
            "trigger": cmd["phrase"],
            "category": cmd.get("category", "")
        }

        actions = cmd.get('actions', [])
        if len(actions) == 1:
            action = actions[0]
            if action['type'] == 'keypress':
                dur = action.get('duration')
                if dur is not None and abs(dur - 0.1) > 1e-9:
                    # Non-default hold time - the 'key' shorthand can't carry it
                    json_cmd['actions'] = [{"type": "PressKey",
                                            "keys": [action['key'].lower()],
                                            "duration": dur}]
                else:
                    # Single key press - use simplified format
                    json_cmd['key'] = action['key'].lower()
            elif action['type'] == 'mouse':
                # Single mouse action - use simplified format
                json_cmd['mouse'] = action['generator_name']
                if 'scroll_clicks' in action:
                    json_cmd['scroll_clicks'] = action['scroll_clicks']
            elif action['type'] == 'run_application':
                json_cmd['actions'] = [{"type": "Launch", "path": action['path']}]
        elif len(actions) > 1:
            # Multiple actions - use full action list
            json_actions = []
            for action in actions:
                if action['type'] == 'keypress':
                    ja = {
                        "type": "PressKey",
                        "keys": [action['key'].lower()]
                    }
                    dur = action.get('duration')
                    if dur is not None and abs(dur - 0.1) > 1e-9:
                        ja["duration"] = dur
                    json_actions.append(ja)
                elif action['type'] == 'mouse':
                    mouse_action = {
                        "type": "MouseAction",
                        "action": action['generator_name']
                    }
                    if 'scroll_clicks' in action:
                        mouse_action['scroll_clicks'] = action['scroll_clicks']
                    json_actions.append(mouse_action)
                elif action['type'] == 'run_application':
                    json_actions.append({"type": "Launch", "path": action['path']})
            json_cmd['actions'] = json_actions

        commands.append(json_cmd)

    output = {
        "name": profile['name'],
        "commands": commands
    }

    return json.dumps(output, indent=2)


def decode_vap(input_path: str, output_base: Optional[str] = None, stdout: bool = False) -> tuple[str, str]:
    """
    Main decoder function.

    Args:
        input_path: Path to input .vap file
        output_base: Base path for output files (without extension)
        stdout: If True, only return output without writing files

    Returns:
        Tuple of (xml_output, json_output)
    """
    # Decompress
    data = decompress_vap(input_path)

    # Parse
    profile = parse_profile(data)

    # Convert to both formats
    xml_output = to_xml(profile)
    json_output = to_json(profile)

    # Write files if not stdout mode
    if not stdout:
        if output_base is None:
            # Default: input_decoded.xml and input_decoded.json
            input_stem = Path(input_path).stem
            output_base = str(Path(input_path).parent / f"{input_stem}_decoded")

        # Handle if output_base already has extension
        output_base_path = Path(output_base)
        if output_base_path.suffix in ('.xml', '.json'):
            output_base = str(output_base_path.with_suffix(''))

        xml_path = f"{output_base}.xml"
        json_path = f"{output_base}.json"

        with open(xml_path, 'w', encoding='utf-8') as f:
            f.write(xml_output)

        with open(json_path, 'w', encoding='utf-8') as f:
            f.write(json_output)

        print(f"Decoded {len(profile['commands'])} commands")
        print(f"  XML:  {xml_path}")
        print(f"  JSON: {json_path}")

    return xml_output, json_output


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        print("\nError: Input file required")
        sys.exit(1)

    # Handle --stdout flag
    args = sys.argv[1:]
    stdout_mode = '--stdout' in args
    if stdout_mode:
        args.remove('--stdout')

    if not args:
        print(__doc__)
        print("\nError: Input file required")
        sys.exit(1)

    input_path = args[0]
    output_base = args[1] if len(args) > 1 else None

    if not Path(input_path).exists():
        print(f"Error: File not found: {input_path}")
        sys.exit(1)

    xml_output, json_output = decode_vap(input_path, output_base, stdout=stdout_mode)

    if stdout_mode:
        print(xml_output)


if __name__ == '__main__':
    main()
