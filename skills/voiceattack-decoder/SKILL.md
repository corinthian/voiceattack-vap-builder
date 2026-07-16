---
name: voiceattack-decoder
description: Decode VoiceAttack .vap binary files to XML
status: standalone-tool
---

# VoiceAttack Profile Decoder

> **Note:** This is a standalone tool, not yet a Claude Code skill. Use via command line.

Decode VoiceAttack `.vap` files to structured JSON (normative) + gated XML for inspection.

## Usage — V2 (`vap2`, current)

V2 walks the binary object model (spec v0.3), emitting canonical names from the capability
dictionary and explicit typed unknowns for anything outside the SOLID set. Run from the
`scripts/` directory so the package resolves:

```bash
cd <tool-dir>/scripts
python3 -m vap2 input.vap                 # writes input_decoded.json
python3 -m vap2 input.vap output_base     # writes output_base.json
python3 -m vap2 input.vap --stdout        # JSON to stdout
python3 -m vap2 input.vap --stdout --xml  # gated secondary XML (prelim §8)
```

Output schema is frozen in `docs/V2_JSON_Schema.md`. Both containers are handled: raw-deflate
binary via the object walk, and uncompressed `<Profile>` XML input (v1 crashed on this).

Decoded JSON/XML is a verbatim transcription of the profile — it can contain launch paths,
command-line arguments, clipboard text, and typed text. Treat decoded output with the same
care as the profile itself before sharing or committing it. `output files/` is gitignored
for this reason.

## What It Does (V2)

1. Sniffs the container (raw-deflate binary or `<Profile>` XML).
2. Walks the profile → commands → 34-slot `CommandAction` objects, dereferencing each member
   slot by type per family (keys, mouse, Say, Launch, Set-*, conditions).
3. Emits normative JSON with per-action provenance and unknown markers; category is a
   provenance-tagged heuristic. Regression harness in `tests/`.

> **Legacy:** `scripts/vap_decoder.py` (v1, flat pattern scan) stays in-tree during soak.

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
