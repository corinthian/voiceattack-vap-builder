#!/usr/bin/env python3
"""
VoiceAttack .VAP Profile Decoder

Decodes VoiceAttack .vap profile files from compressed binary format to human-readable XML.

Usage:
    python vap_decoder.py <input.vap> [output.xml]

If output is not specified, prints XML to stdout.
"""

import struct
import sys
import zlib
import xml.etree.ElementTree as ET
from xml.dom import minidom
from pathlib import Path
from typing import Optional


# Virtual Key Code mappings
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


def find_all_strings(data: bytes, min_length: int = 4) -> list[tuple[int, str]]:
    """Find all readable strings in binary data."""
    strings = []
    i = 0
    while i < len(data) - 4:
        length, _ = read_uint32(data, i)
        if min_length <= length <= 500:
            try:
                s = data[i+4:i+4+length].decode('utf-8')
                if s.isprintable() and len(s) >= min_length:
                    strings.append((i, s))
            except (UnicodeDecodeError, IndexError):
                pass
        i += 1
    return strings


def find_key_actions(data: bytes, start: int, end: int) -> list[dict]:
    """
    Find all key actions in a data range by pattern matching.

    Key action pattern:
    - 4 bytes: 00 00 00 00 (zeros)
    - 4 bytes: 01 00 00 00 (action type = 1)
    - 4 bytes: VK code (little-endian)
    - 2 bytes: 00 00
    - 6 bytes: FF FF FF FF FF FF (padding)
    """
    actions = []
    # Pattern: 00 00 00 00 01 00 00 00 XX 00 00 00 00 00 FF FF
    pattern_prefix = b'\x00\x00\x00\x00\x01\x00\x00\x00'

    i = start
    while i < end - 16:
        if data[i:i+8] == pattern_prefix:
            vk_code = struct.unpack('<H', data[i+8:i+10])[0]
            if 0 < vk_code < 0x200:  # Valid VK code range
                key_name = VK_CODES.get(vk_code, f"VK_0x{vk_code:02X}")
                actions.append({
                    'type': 'keypress',
                    'vk_code': vk_code,
                    'key': key_name
                })
                i += 16  # Skip past this action
                continue
        i += 1
    return actions


def find_commands(data: bytes) -> list[dict]:
    """Find and parse all commands in the decompressed data."""
    commands = []
    strings = find_all_strings(data, 4)

    # Find command phrases (start with '[')
    phrase_positions = [(pos, s) for pos, s in strings if s.startswith('[')]

    # Known categories
    categories = {'keyboard', 'applications', 'Interface', 'system', 'navigation'}

    for phrase_pos, phrase in phrase_positions:
        # GUID should be 20 bytes before string (16 GUID + 4 length prefix)
        guid_pos = phrase_pos - 20
        if guid_pos < 0:
            continue

        guid, _ = read_guid(data, guid_pos)

        # Find category after the phrase
        category = None
        search_start = phrase_pos + len(phrase) + 4
        search_end = min(search_start + 2000, len(data))

        for cat_pos, cat_str in strings:
            if search_start < cat_pos < search_end and cat_str.lower() in [c.lower() for c in categories]:
                category = cat_str
                break

        # Find actions in the range after phrase
        actions = []
        action_search_start = phrase_pos + len(phrase) + 4
        action_search_end = min(action_search_start + 800, len(data))

        # Find key press actions
        key_actions = find_key_actions(data, action_search_start, action_search_end)
        actions.extend(key_actions)

        # Check for app launch (look for executable paths)
        for str_pos, s in strings:
            if action_search_start < str_pos < action_search_end:
                if '.exe' in s.lower() or s.startswith('*'):
                    actions.append({
                        'type': 'run_application',
                        'path': s
                    })
                    break

        commands.append({
            'guid': guid,
            'phrase': phrase,
            'category': category or 'uncategorized',
            'actions': actions
        })

    return commands


def parse_profile(data: bytes) -> dict:
    """Parse the profile header and commands."""
    # Read header
    total_size, pos = read_uint32(data, 0)
    item_count, pos = read_uint32(data, pos)

    # Skip offset table
    pos += item_count * 4

    # Read profile GUID
    profile_guid, pos = read_guid(data, pos)

    # Read profile name
    profile_name, pos = read_string(data, pos)

    # If name not found at expected position, search for it
    if not profile_name:
        strings = find_all_strings(data, 4)
        # Look for "profile" in string names
        for str_pos, s in strings:
            if 'profile' in s.lower() and len(s) < 50:
                profile_name = s
                break

    # Find commands
    commands = find_commands(data)

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
                elif action['type'] == 'run_application':
                    ET.SubElement(action_elem, 'Path').text = action['path']

    # Pretty print
    xml_str = ET.tostring(root, encoding='unicode')
    dom = minidom.parseString(xml_str)
    return dom.toprettyxml(indent='  ', encoding=None)


def decode_vap(input_path: str, output_path: Optional[str] = None) -> str:
    """Main decoder function."""
    # Decompress
    data = decompress_vap(input_path)

    # Parse
    profile = parse_profile(data)

    # Convert to XML
    xml_output = to_xml(profile)

    # Write or return
    if output_path:
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(xml_output)
        print(f"Decoded {len(profile['commands'])} commands to {output_path}")

    return xml_output


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        print("\nError: Input file required")
        sys.exit(1)

    input_path = sys.argv[1]
    output_path = sys.argv[2] if len(sys.argv) > 2 else None

    if not Path(input_path).exists():
        print(f"Error: File not found: {input_path}")
        sys.exit(1)

    xml_output = decode_vap(input_path, output_path)

    if not output_path:
        print(xml_output)


if __name__ == '__main__':
    main()
