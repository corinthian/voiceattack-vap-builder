# VAP Uncertainty Research Plan

Run-book for a fresh Opus session to close every remaining open in the VAP format. Written 2026-07-08 against `VAP_Format_Specification.md` v0.1 and `VAP_Format_Specification_Review.md`. Execute phases in order; each ends in a gate. Analysis on existing data comes first; new probe profiles are specced only for what existing data cannot reach, because the user builds and exports every probe by hand.

## Ground rules (non-negotiable)

1. **Analysis and documents only.** Do NOT edit `vap_decoder.py` or any source file without explicit user authorization in the current conversation. Scripts go in the session scratchpad.
2. Branch is `feature/decode-conditional-actions`. Commit only when the user says commit. Never push.
3. Reference profiles and CSVs are gitignored and stay local.
4. State every prediction BEFORE reading the bytes that test it; record refutations as prominently as confirmations.
5. Cross-validation gate: no claim is CLOSED until it holds across all five reference profiles. Anything less is PLAUSIBLE — say so.
6. Terse reporting. No hard line wrapping in prose written to docs.

## Required reading (in order)

1. `VAP_Format_Specification.md` — the object model. Treat §6 (envelope), §8.1–8.4 (conditions), §9.1 (ActionType) as verified foundation; do not re-derive.
2. `VAP_Format_Specification_Review.md` — corrections that OVERRIDE the spec where they conflict: member slots are always offsets requiring dereference; Decimal values are 16-byte .NET Decimals at m[25] (flags,hi,lo,mid); numeric/boolean condition operands are i32 at m[21]; m[5] is the KeyCodes list `[u32 count][count × u16]`; m[7] is Text-only.
3. `VAP_Conditional_Command_Analysis.md` — history; skim the session-update sections only.

**Superseded:** `Conditionals_Probe_2_Spec.md` and `Conditionals_Probe_2_Execution_Plan.md`. The rebuilt conditionals profile (2026-07-08 export) plus the object walk closed their targets: all four operator enums, value-type codes m[24] 0–4, ConditionPairing semantics, pool-referenced operand/operator layout, and Begin/ElseIf/Else/End codes (ActionTypes 19/63/29/20). Do not build that probe. Two of its questions remain live and are carried here: whether IndentLevel is stored anywhere (item 12) and what m[18] means (item 2).

## Evidence base

Five binaries in `reference profiles/` (zoom-if-else, numkeys, conditionals, corinthian-4, base profile) + CSV oracles for corinthian, conditionals, and Cities Skylines II. Note: base profile and numkeys have NO CSV — findings there lack an oracle and cap at PLAUSIBLE unless cross-confirmed. The review's harness (`spec_verify1–6.py` in that session's scratchpad, reproducible from the review doc) walks every command; rebuild the walker first thing.

## Phase 0 — harness + sanity gate

Rebuild the object walker (command scan via decoder signature matcher excluding the profile-header pseudo-command @368; walk actionCount objects via head; deref members by index). Gate: reproduce the review's headline numbers — 1,601 actions, all m[1]=140, set-fire chains 37/37, zoom landmarks per spec §13.

## Phase 1 — slot census (existing data, do this before anything else)

For all 1,601 objects, tabulate per member slot: deref'd u32 value distribution, split by ActionType. Output: one table, 34 rows — which slots are constant (value + where), which vary and with what, which are 0xFFFFFFFF-always. This single artifact scopes every downstream item: unmapped slots that never vary get parked; slots that vary get correlated against CSV action text. Predictions to state first: m[0]=32 constant everywhere; m[27]/m[28] deref to `[00][F1886E09][FFFFFFFF]` everywhere; ~24 slots near-constant.

## Phase 2 — existing-data closures

Each item: technique + data source. State the prediction, read the bytes, record verdict.

1. **ActionType 16 = Execute Command.** corinthian CSV has `Execute command` rows; correlate walk m[2] against them. Also inventory every distinct m[2] across all profiles vs the 16 known codes — unknown codes become probe targets.
2. **KeyDown / KeyUp / KeyToggle distinguishing member.** corinthian has `Press down X` / `Release X` pairs (incl. chords) and `Toggle F12 key`. Diff a down/up/toggle object trio against a plain PressKey twin; all share Duration 0.0. The differing slot is the subtype field.
3. **Mouse-action layout.** corinthian has `hold down/Release middle mouse button` and `Move mouse cursor to …` with CSV oracle. Walk those objects: find the context-code string member, the scroll/click-count member, X/Y for cursor moves. The flat-scan claims (§9.3: string `{button}{action}`, double at −20) have never been object-walk verified — verify or correct them. Full context-code sweep goes to the probe.
4. **Set-Boolean value location.** corinthian CSV has `Set Boolean [ads] to True` AND `to False` — diff the pair; the differing byte/slot is the value (predicted: a 1-byte field, since no u32 slot held True in the conditionals profile).
5. **Set-action field map.** Verify m[6]=target-name and m[11]=Set-Integer literal across ALL corinthian Set actions (many samples); check whether m[11]/m[7]/m[25] generalize per type. The Set-op m[20] discrepancy (climb "converted value"=4 vs jumped "converted value"=0) — collect every Set-Integer in corinthian with CSV wording and tabulate; if the enum doesn't resolve from wording, it goes to the probe (dropdown sweep).
6. **Pause duration slot.** 171 corinthian Pause rows; predicted m[3] double (same slot as keypress Duration).
7. **m[31] compound sub-condition format.** Existing samples: `(return to main screen)` (2 sub-compares, OR) and set-fire's three `… 'one' OR … 'two'` blocks. Parse m[31]'s region: expect a count scalar (=2 observed) then packed sub-condition records; map operand/operator/value fields inside by matching known literals. m[18] on compounds vs simple blocks is the first ConditionGroup test — a compound is ONE action, so if m[18] enumerates sub-groups anywhere it would show here.
8. **Local-variable declaration pool.** conditionals profile declares `[i]`, `[pie]`, `boo`, `bbq`, `smal` — locate each `[01][len][name][01]` wrapper, establish where the pool lives (command trailing region? profile level?), its record shape, and whether Set actions reference it or embed names.
9. **Command trailing region.** Between chain end and next command: zoom shows `01 01 FF×8 [len]camera …`. Diff trailing regions across numkeys commands (same actions, same category) and corinthian commands with CSV-known distinct categories; map category string position, description, and flag bytes. IndentLevel search: nested+decimal has depths 0/1/2 — scan its full command region (not just member tables) for the 0,1,2 pattern; verdict on item 12.
10. **Header @8 + command-list indexing.** Diff bytes @8..@0x170 across all five profiles (sizes differ, command counts differ — correlate). Test: does anything at the head point to the first command or enumerate command offsets, or is detection necessarily scan-based?
11. **Constants.** m[0]=32: check whether it's a count (32 of something), a version, or a fixed tag — vary against anything (member count? object class?). m[27]/m[28] 9-byte structure; the optional `2.1.8` string (present zoom/conditionals/corinthian, absent numkeys/base — correlate with what those profiles contain/lack, e.g. export version or a feature flag).

Gate: publish the closure table — CLOSED / PLAUSIBLE / NEEDS-PROBE per item, with evidence lines.

## Phase 3 — probe specs (only for what Phase 2 left open)

Consolidate into at most TWO profile builds to minimize the user's burden. Design rules (proven in probes 1–2): one variable per contrast; self-labeling operands (literals name their block, numeric values k×11); nonzero anchors (avoid Equals=0-only blocks); a duplicate control block where order/code confounds are possible; screenshot every dropdown swept; export VAP + CSV together.

**Probe A — `groups` (m[18]/ConditionGroup + compound format).** One command: `(A AND B) OR (C AND D)` with four self-labeling text compares; one command: same four compares all-AND; one command: all-OR; one command: two sequential simple Begin blocks as control. Predictions: if m[18] is a block-open ordinal only, values follow serialization order and AND/OR leaves them untouched; the AND/OR distinction then must live inside m[31]'s sub-records or another slot. Yield: m[18] verdict, m[31] record format with 4 subs, AND-vs-OR encoding.

**Probe B — `actions` (ActionType + layout sweep).** One command per unsampled action, each with distinctive self-labeling parameters: Say (text 'say-test', volume 43, rate 7 — no Say exists in ANY current CSV), Launch (path + args + workdir strings), SetClipboard ('clip-test'), Write vs Say contrast, dictation start/stop if available, Set Integer swept across its full value-source dropdown in order (value / converted value / plus / minus / …, screenshot — settles the m[20] set-op enum), Set Decimal and Set Small Int variants, and a mouse command sweeping context codes (LC, LDC, RC, SF with 5 clicks, cursor-move to X,Y) if Phase 2 left mouse gaps. Yield: ActionType codes, per-type member layouts, set-op enum.

Gate: probe specs reviewed by the user before building; STOP and wait for exports.

## Phase 4 — probe analysis

Phase 0 sanity on the new exports (CSV is the oracle for what was actually built; log every deviation). Then per-probe: predictions, member dumps, closures.

## Phase 5 — cross-validation gate (mandatory)

Re-read all five original profiles with every new field definition; each must hold everywhere it applies. corinthian is the stress test (1,166 actions, every condition style). Any inconsistency downgrades to PLAUSIBLE — write it that way.

## Phase 6 — write-up, then stop

Amend `VAP_Format_Specification.md` to v0.2: apply the review's §2 corrections, add closures with confidence tags, update §12. Append a dated session update to `VAP_Conditional_Command_Analysis.md`. Update `Project_Status.md`. Report closed / refuted / still-open to the user. STOP — decoder changes are a separate, explicit authorization.

## Open inventory (summary)

| # | open | current state | path |
|---|------|---------------|------|
| 1 | header @8, command-list indexing | OPEN | Phase 2.10 |
| 2 | m[18] ConditionGroup vs ordinal | ordinal-consistent, untested vs AND/OR | Phase 2.7 → Probe A |
| 3 | m[31] sub-condition record format | count=2 observed, format unknown | Phase 2.7 → Probe A |
| 4 | ActionType completeness (16, Say, Launch, SetClipboard, dictation, mouse) | 16 codes known | Phase 2.1/2.3 → Probe B |
| 5 | mouse member layout | flat-scan claims unverified | Phase 2.3 → Probe B |
| 6 | Set-Boolean value location | not in any u32 slot | Phase 2.4 |
| 7 | Set-op m[20] enum | contradictory samples | Phase 2.5 → Probe B |
| 8 | m[6]/m[11] scope across Set types | single-sample each | Phase 2.5 |
| 9 | KeyDown/KeyUp/KeyToggle subtype member | shared marker, Duration 0.0 | Phase 2.2 |
| 10 | ~24 unmapped member slots | unknown | Phase 1 census |
| 11 | m[0]=32, m[27]/m[28] structure, `2.1.8` optionality | constants, meaning unknown | Phase 2.11 |
| 12 | IndentLevel storage (or derived-only) | not in member table | Phase 2.9 |
| 13 | command trailing region (category, description, flags) | category string located only | Phase 2.9 |
| 14 | local-var declaration pool structure | wrapper known, pool anchor unknown | Phase 2.8 |
