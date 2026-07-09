---
name: voiceattack-decoder
description: Decode VoiceAttack .vap binary files to XML
status: standalone-tool
---

# VoiceAttack Profile Decoder

> **Note:** This is a standalone tool, not yet a Claude Code skill. Use via command line.

Decode VoiceAttack `.vap` binary files to readable XML + JSON for inspection and analysis.

## Usage

```bash
# Decode to input_decoded.xml and input_decoded.json (written next to the input)
python3 <tool-dir>/scripts/vap_decoder.py input.vap

# Decode to custom output base (writes base.xml and base.json)
python3 <tool-dir>/scripts/vap_decoder.py input.vap output_base

# Print XML to stdout only (no files written)
python3 <tool-dir>/scripts/vap_decoder.py input.vap --stdout
```

## What It Does

1. Reads binary `.vap` file
2. Decompresses (raw deflate; uncompressed-XML input is NOT yet handled — planned for V2)
3. Outputs formatted XML (inspection) and JSON (generator-compatible)

## Use Cases

- Inspect existing VoiceAttack profiles
- Reverse-engineer command structures
- Debug profile generation issues
- Extract action sequences for reference

## Binary Format

See `docs/VAP_Format_Specification.md` (v0.2, authoritative) for the binary format. `docs/VAP_FORMAT.md` is the superseded flat-scan-era doc, retained as history.

## Future Skill Integration

When promoted to a full skill, this decoder will:
- Accept `.vap` file uploads
- Display XML structure visually
- Extract command listings
- Support VAP → JSON conversion (reverse of generator)
