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

## Out of round-trip scope: profile references (documented limitation, not a fidelity bug)

VoiceAttack profiles can include commands from other profiles ("referenced profiles" — the maintainer's `base profile` is referenced by every working and test profile). That linkage lives in VoiceAttack's internal database and is **not present in `.vap` exports in any form**: a byte-level search of all five referencing reference profiles for the base profile's GUID (raw .NET-endian bytes AND string form) and its name found zero occurrences (verified 2026-07-11). Consequently:

1. **What the decoder sees:** only the profile's OWN commands — corinthian's 201 equals its own header count; no referenced commands are embedded, and nothing in the bytes identifies which profiles it references. Decoder output that contains no reference information is a faithful decode, not a gap.
2. **References cannot survive the translation process.** decode → encode → import necessarily loses the linkage, because the export it starts from never had it (confirmed by the maintainer: the reference does not survive VoiceAttack's own export/import either). After importing any generated or round-tripped profile, referenced profiles must be re-attached by hand in VoiceAttack's profile options. Neither tool can fix this; neither tool should be blamed for it; the fixpoint test does not and cannot cover it.

## Voice-alternative dispatch — encoder lowering rule (ruling 2026-07-11)

Generator/encoder input may use the overloaded-trigger idiom: a trigger whose trailing bracket group lists N alternatives, paired with exactly N actions in matching order (`"pan [up; down; left; right]"` + four PressKey actions). The encoder MUST lower this to a conditional dispatch chain, not a flat action sequence: `Begin Text Compare : [{LASTSPOKENCMD}] Ends With '<alternative 1>'` → action 1, `Else If … Ends With '<alternative 2>'` → action 2, …, `End Condition`.

The operator is **Ends With** (Text operator code 4, dictionary-enumerated, SOLID) — not Equals, not Contains. The alternative token is by construction the suffix of the spoken phrase, so a suffix-anchored compare tests exactly the segment that varies: prefix collisions cannot fire ('fast' is not a suffix of 'fastest'), and the match is invariant to everything before the token (optional words like `[press;]`, future re-phrasings of the command head). Equals breaks under optional-word triggers (combinatorial full-phrase branches); Contains breaks under substring collisions. Branch order follows input order, except when one alternative is a suffix of another (`[fast; very fast]`) — then longest-suffix-first is mandatory. Hand-built profiles predating this ruling use Contains/Starts With for the same job; the decoder preserves them faithfully, but the encoder emits Ends With.

**Amendment (2026-07-12) — scope: the Ends With rule applies only to the trigger's FINAL bracket group.** The suffix argument presumes the alternatives end the spoken phrase. A group followed by anything optional breaks it: in `zoom [out; in] [more;]`, "zoom out more" ends with 'more', not 'out'. For multi-group triggers the lowering is per-group, from the tail inward: the final group's tokens keep Ends With; alternatives in earlier groups are no longer suffixes and use ordered **Contains** instead. Contains reintroduces the substring-collision hazard the base rule exists to avoid ('fast'/'fastest' as inner-group tokens would shadow each other), so when lowering an inner group the encoder MUST detect token collisions — any token that is a substring of another token in the same phrase family — and either order branches longest-token-first when that resolves the shadow, or refuse the command with an error naming the colliding tokens. Evidence this decomposition is the real-world pattern: the maintainer's hand-built VA edit in the 2026-07-12 Cities Skylines II re-export lowers exactly this trigger as two sequential blocks — `Ends With 'more'` (setting a decimal) followed by `Contains 'out'` / Else If `Contains 'in'` — and V2 decodes it losslessly (first in-evidence Else, sequential blockOrdinals 1/2, SetDecimal, Write with a `{DEC:z}` token). The same export round-tripped the 40 untouched generator-built commands through VoiceAttack import→export byte-equivalently, including operator code 4 — VA-level confirmation of the base ruling's emitted form.

- Both tools load their name tables from the dictionary (or from a build step that generates their tables from it, verified identical by the audit tool). Hand-edited name tables in tool source are a contract violation.
- `schema/dictionary_tools.py audit` must report zero orphans: no name emitted by the decoder or accepted by the encoder that is absent from the dictionary, and no solid dictionary entry unsupported by either tool. CI-equivalent: run it in the Phase 5 harness.
- The generated view `VAP_Capability_Dictionary.md` and any README/SKILL tables regenerate from the dictionary (`dictionary_tools.py render`); they carry a GENERATED header and are never hand-edited.
