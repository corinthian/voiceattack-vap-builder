---
name: voiceattack-decoder
description: Decode VoiceAttack .vap binary files to XML
status: standalone-tool
---

# VoiceAttack Profile Decoder

> **Note:** This is a standalone tool, not yet a Claude Code skill. Use via command line.

Decode VoiceAttack `.vap` binary files to readable XML for inspection and analysis.

## Usage

```bash
# Decode to stdout
python3 <tool-dir>/scripts/vap_decoder.py input.vap

# Decode to file
python3 <tool-dir>/scripts/vap_decoder.py input.vap output.xml
```

## What It Does

1. Reads binary `.vap` file
2. Detects compression (raw deflate or uncompressed)
3. Outputs formatted XML

## Use Cases

- Inspect existing VoiceAttack profiles
- Reverse-engineer command structures
- Debug profile generation issues
- Extract action sequences for reference

## Binary Format

See `docs/VAP_FORMAT.md` for detailed binary format documentation.

## Future Skill Integration

When promoted to a full skill, this decoder will:
- Accept `.vap` file uploads
- Display XML structure visually
- Extract command listings
- Support VAP → JSON conversion (reverse of generator)
