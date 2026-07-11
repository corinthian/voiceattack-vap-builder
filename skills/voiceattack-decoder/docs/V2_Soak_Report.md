# VAP Decoder V2 — Soak Report & Acceptance Sign-off (W7)

Date: 2026-07-11 · Branch: `feature/decoder-v2` · Regenerate: `python3 skills/voiceattack-decoder/tests/soak.py`

vap2 decoded all six reference profiles and was compared against the deployed v1 decoder.
All Phase-5 acceptance criteria pass. One decode decision (category bound) changed during
soak; it is documented below. Remaining gate before merge: the VoiceAttack **import test**
(human, Windows) — not performed here.

## Acceptance checklist — measured

| Criterion | Result | Measure |
|---|---|---|
| Category parity vs corinthian CSV (0 mismatch) | **PASS** | 106 matched, 0 mismatches |
| Probe B 32/32 actions, zero unknown | **PASS** | 32 actions, 0 unknown-marked |
| corinthian 201 cmds / 1168 actions | **PASS** | header-count anchored |
| R3 tripwire: unknownMarked == histogram budget | **PASS** | unknown=0, budget=0 |
| Zero chain breaks across all profiles | **PASS** | 0 breaks / 1,635 objects |
| Structural conditionals, KeyDown/Up/Toggle distinct, XML input | **PASS** | `test_vap2.py` (19 tests) |
| Probe B markers reproduced (43/7/33/4.44/5/333/444, sweeps, order) | **PASS** | `ProbeBOracleTest` |
| Chorded keys / zero phantoms (by construction, no pattern scan) | **PASS** | object walk only |
| Key/duration parity with v1 where v1 is correct (prelim §9 #1) | **PASS** | 226 cmds: 174 exact, 52 v2-superset (v1 chord gap), 0 disagreements |
| Regression harness checked in (skip-if-missing) | **PASS** | `tests/test_vap2.py` (20 tests) |
| Fixpoint `decode(encode(decode(x)))==decode(x)` | DEFERRED | encoder out of scope (plan §9); stub skips |

## v1 vs v2 — where v2 differs

**Command discovery.** v2 is chain-aware (skips each command's whole action chain, so
action-interior GUIDs can't alias as commands) and excludes the @368 profile pseudo-command
by construction. Called bare, v1 counts the pseudo-command as an extra command on most
profiles (e.g. zoom v1=2 / v2=1); corinthian matches at 201 (header count) for both.

**Category parity vs the CSV oracle** (the acceptance bar):

| Profile | v1 mismatches | v2 mismatches |
|---|---|---|
| corinthian | 1 | **0** |
| conditionals | 5 | **0** |
| Probe B | 0 | **0** |

v2 **fixes** v1's one corinthian category error and holds parity everywhere the CSV covers.
conditionals' five commands genuinely have no category (CSV column empty): v1's heuristic
leaked action-operand strings into the category field there; v2's walk-bounded region
correctly finds none and emits `null` (schema v1.1 — the v1.0 `"uncategorized"` placeholder
is no longer emitted, so an encoder cannot write back a category the profile never had).

## Decode decision changed during soak — category region bound

v1's category heuristic mis-tagged the **last** command by over-scanning into the profile's
trailing master-category list (the classic Finding-5 over-scan). Two naive selections each
failed one profile:

- "last qualifying string" → over-scans on the final command (corinthian `zoom out` → wrong).
- "first qualifying string" → loses to author **descriptions** that precede the category
  (Probe B commands → wrong).

The fix uses the **version string (`2.1.8`) as the region terminator**: it marks the boundary
between a command's own trailing data and the profile master list. Bounding the scan there and
keeping last-wins gives **0 category mismatches on both corinthian and Probe B**. This is a
bounds fix, not category re-engineering (prelim §10) — the field stays `provenance: "heuristic"`
and is still the weakest link until the trailing-region structure is decoded (parked #4).

## Content-diff findings (from adversarial double-check, not just structure)

- **Key/duration parity vs v1** (in-tree): 226 commands both decode; 174 exact, 52 where v2
  finds chord keys v1 missed (v1's documented chord gap, spec §11.6), **0 disagreements**.
- **11 of corinthian's 153 compares** are Begin Loop While / compound Begins with the left
  operand (m[19]) absent. m[24]=0/m[20]=0 there are byte-identical to unset, so the decoder
  emits `valueType.name`/`operator.name` as `null` + an `unresolved` marker rather than
  asserting the spec-forbidden SmallInteger/Equals default (spec §8.1). The 10 *genuine*
  SmallInteger compares (operand present) decode fully.
- **ExecuteCommand (16)** — target-command GUID is in m[6] but undecoded (no SOLID slot map);
  recorded as a known passthrough gap in `V2_JSON_Schema.md`, not merely "out of scope".

## Known limitations (unchanged from spec, honestly carried)

- Category remains heuristic/provenance-tagged; replaced only when the trailing region is
  decoded (parked #4).
- Compound conditions are decode-only: first sub-compare + `{compound: n}` marker (parked #1).
- base profile emits 14 unknown-marked actions — genuinely unattributed ActionType codes
  (no CSV oracle); correct warn-never-silence, not a defect.
- XML **input** parses to the same JSON model (v1's crash closed); it is a field map, not a
  byte-level re-derivation. XML **output** is the gated secondary view (prelim §8), not
  import-verified — that is the pending human gate.
