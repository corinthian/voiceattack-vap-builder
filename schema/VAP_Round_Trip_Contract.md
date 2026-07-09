# VAP Round-Trip Contract

Version 0.1.0 · 2026-07-09 · Binds decoder V2 and the encoder module to `vap_capability_dictionary.json` (the dictionary). The dictionary is the single name authority: every key, mouse, and action name either tool emits or accepts lives there, and nowhere else. Execution plan Phase 4 deliverable; the fixpoint test lands in the Phase 5 harness.

## The contract

1. **Solid entries** (`confidence: solid`): decoder V2 MUST emit the canonical name; the encoder MUST accept the canonical name and every listed alias, and MUST produce a VoiceAttack-importable action for it. These entries define the fixpoint set.
2. **Plausible / inferred entries**: both tools handle them exactly like solid entries, but each emission or consumption prints a warning naming the entry and its confidence. They round-trip; they are not yet trusted.
3. **Parked entries** (`round_trip: opaque`, e.g. binary codes 50/51): the decoder emits an explicit opaque marker — `{"type": "unknown", "binary_code": N}` in JSON, a comment in XML — never silence. The encoder, on meeting one, warns and emits nothing for it. No parked entry may be silently dropped by either tool.
4. **Compound conditions** (parked by scope ruling 2026-07-08): decoder emits the first sub-compare plus `{"compound": n_subs}`; the encoder refuses compound input with a warning until the m[31] format is decoded.

## Fixpoint acceptance test

For every reference profile `x`: `decode(encode(decode(x))) == decode(x)`, compared on the solid subset of fields (canonical names, key codes, durations, action order, condition structure). Warnings are permitted; differences are failures. This test is the encoder's definition of done and a decoder-V2 regression gate (Phase 5 harness, `tests/`).

## Name-evolution rules

- Aliases are accepted forever once published; adding an alias is a MINOR dictionary bump.
- Changing or removing a canonical name is a MAJOR bump and requires a migration note.
- Decoder-v1 legacy names (bare `subtract`, `backtick`, `lbracket`, media-key names, …) are aliases precisely so JSON decoded before this contract keeps regenerating.
- New discoveries (Probe B) enter as new entries with honest confidence tags; promotion to `solid` requires the cross-validation gate of the research plan (holds across all five reference profiles).

## Tool obligations

- Both tools load their name tables from the dictionary (or from a build step that generates their tables from it, verified identical by the audit tool). Hand-edited name tables in tool source are a contract violation.
- `schema/dictionary_tools.py audit` must report zero orphans: no name emitted by the decoder or accepted by the encoder that is absent from the dictionary, and no solid dictionary entry unsupported by either tool. CI-equivalent: run it in the Phase 5 harness.
- The generated view `VAP_Capability_Dictionary.md` and any README/SKILL tables regenerate from the dictionary (`dictionary_tools.py render`); they carry a GENERATED header and are never hand-edited.
