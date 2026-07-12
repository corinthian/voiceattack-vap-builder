# VAP Decoder v2 — Preliminary Specification

Status: PRELIMINARY draft for review, 2026-07-08. Defines the successor to `vap_decoder.py` (v1). v2 replaces v1's flat pattern scan with a tree walk over the verified object model. Normative basis: **only claims independently re-verified in `VAP_Format_Specification_Review.md`** (§1 Confirmed, §2 corrections as corrected, §3 new findings), each within its verified scope. Spec-tagged-[SOLID]-but-unreviewed claims are NOT a basis. This is a specification; no implementation is authorized by this document.

## 1. Design rules

1. **Solid-only decoding.** A field is decoded if and only if the review confirmed its location, width, and meaning. No inference at decode time, no enum guessing, no heuristic pattern matching in the action path.
2. **Explicit unknowns, never silence.** Anything outside solid ground is emitted as a typed unknown marker carrying enough raw material (member table, offsets, lengths) to be re-decoded later without re-running the tool. Nothing is silently dropped; nothing is guessed.
3. **Comprehensive within the solid set.** Every review-confirmed field is emitted: full condition records, chorded key lists, durations, pairing links, block ordinals, action GUIDs, Set-action fields where verified.
4. **Provenance everywhere.** Every command and action carries its absolute byte offsets so any output value can be checked against the binary by hand.

## 2. Normative basis (what "solid" means here)

In scope (review-confirmed): container decompression; header fields @0/@4/0x170/0x180; command envelope with actionCount; the 34-member object envelope (head = length = sibling pointer, base = array start, heap at +140, all slots are offsets requiring typed dereference); the member map of §4; ActionType codes {0, 2, 17, 19, 20, 21, 22, 23, 29, 30, 31, 36, 37, 38, 63}; all four operator enums; value-type codes 0–4; value slots m[7]/m[21]/m[25] with per-type absence semantics; KeyCodes list with chords; pairing semantics including closers, Else, and Loop links; the block-open ordinal.

Out of scope (unverified — emitted as unknowns, never decoded): mouse actions (spec §9.3 was not re-verified), ActionType 16 and every unlisted code, Launch/Say/SetClipboard/plugin-payload layouts, Set-Boolean value location, compound sub-condition list format (m[31] interior), KeyDown/KeyUp/KeyToggle subtype discrimination, the ~24 unmapped member slots, the command-list index, the trailing-region structure (category — see §7).

## 3. Architecture

```
decompress (zlib -15)
→ read profile header (@0 size check, @4 0x59 check, GUID @0x170, name @0x180)
→ command discovery: structural signature scan          [interim — see below]
→ per command: read GUID, phrase, actionCount
→ walk actionCount objects: head → 34 member offsets → typed dereference by slot
→ emit JSON (normative) / XML (secondary, gated — §8)
```

**Command discovery stays a structural signature scan** (GUID validity + phrase length/printability + count sanity) because the command-list indexing mechanism is still open — this is a documented interim mechanism, not a verified format feature. Required adjustments over v1: (a) the profile-header record at the profile-Id position (0x170) matches the command signature and MUST be excluded as a pseudo-command; (b) the count read at phrase_end is the true actionCount — v1's offset-table truncation logic is deleted (the "35-entry table" was `[head][m0..m33]`; corinthian set-fire's raw count 37 chains 37 objects cleanly). Validation evidence: 201 corinthian commands found = the profile header's own count field; all 1,601 actions across the five reference profiles chain within bounds. The scan's residual risk (a phrase byte-pattern aliasing a command signature) is accepted and documented; the walk's chain-integrity check (each head lands before the next discovered command) is a mandatory runtime assertion, and any violation is emitted as a command-level unknown marker, not repaired.

## 4. Member field map (all reads are `deref(arrayStart + m[i])`)

| slot | type | field | gate / scope |
|------|------|-------|--------------|
| m[0] | u32 | constant 32 | sanity check only; ≠32 → object-level unknown flag |
| m[1] | GUID (16 B) | action object Id | always (m[1]==140 is a mandatory envelope assertion) |
| m[2] | u32 | ActionType | always; codes outside the verified set → unknown action |
| m[3] | double | Duration (seconds) | key actions (m[2]=0); elsewhere emitted raw-if-nonzero as unknown-field |
| m[5] | u32 count + count × u16 | KeyCodes list (chords) | m[2]=0 |
| m[6] | string | Set-action target variable name | m[2] ∈ {21, 36} ONLY (verified on Set Text / Set Boolean); other Set types → unknown-field |
| m[7] | string | Text condition value; Set Text value | compares with m[24]=1 (`''` = valueless operator); m[2]=21. Non-Text compares read 0xFFFFFFFF here — never a value |
| m[11] | u32 | Set-Integer literal | m[2]=37 ONLY |
| m[17] | u32 | ConditionPairing (next branch point / End; closers → their Begin; Else and Loop carry links) | block actions {19, 20, 29, 30, 31, 63} |
| m[18] | u32 | block-open ordinal (emitted as `blockOrdinal` — NOT ConditionGroup; semantics unproven for grouping) | block actions |
| m[19] | string | left operand (inline token or pool variable name) | m[2] ∈ {19, 63, 30} |
| m[20] | u32 | operator (per-type enum via m[24]) | enum-decoded ONLY when m[2] ∈ {19, 63, 30}; on m[2] ∈ {36, 37, 38, 21} emitted as raw `setOpCode` with no enum (shared slot; CSV wording does not map 1:1) |
| m[21] | i32 | numeric/boolean right operand | compares with m[24] ∈ {0, 2, 3}; see §5 for the −1/sentinel rule |
| m[24] | u32 | ConditionStartValueType: 0 SmallInt, 1 Text, 2 Bool, 3 Int, 4 Decimal | compares only (0 aliases unset — meaningful only under the m[2] gate) |
| m[25] | .NET Decimal (16 B: flags, hi, lo, mid) | Decimal compare value; Set-Decimal value | m[24]=4 compares; m[2]=38 |
| m[31] | u32 | compound sub-condition count | m[2] ∈ {19, 63, 30}; scalar only — interior NOT decoded (§6) |

All other slots: undecoded; their offsets are preserved in the raw member table of every action (§6 provenance), and a deref'd value of 0 / 0xFFFFFFFF is not reported as meaning anything.

## 5. Condition records

Emitted for every action with m[2] ∈ {19 Begin, 63 Else If, 30 Begin Loop While}: `{ leftOperand, operator (code + name), valueType (code + name), value, pairing, blockOrdinal }`.

- Operator enums (0-indexed dropdown order, per value type): Text (10): Equals, Does Not Equal, Starts With, Does Not Start With, Ends With, Does Not End With, Contains, Does Not Contain, Has Been Set, Has Not Been Set. Integer/Decimal/Small Integer (8): Equals, Does Not Equal, Is Less Than, Is Less Than Or Equals, Is Greater Than, Is Greater Than Or Equals, Has Been Set, Has Not Been Set. Boolean (4): Equals, Does Not Equal, Has Been Set, Has Not Been Set.
- Value slot by m[24]: 1 → m[7] string; 0/3 → m[21] i32; 2 → m[21] (0=False, 1=True); 4 → m[25] .NET Decimal rendered as exact decimal string (never a float round-trip).
- **Valueless operators** (Has Been Set / Has Not Been Set — codes {8,9} Text, {6,7} numeric, {2,3} Bool): no `value` key is emitted. This rule, not the sentinel, decides absence — because i32 −1 is byte-identical to 0xFFFFFFFF and is a legitimate value (corinthian reverse-throttle compares read −1..−4). Text valueless operators read `''` in m[7]; that empty string is likewise suppressed by the operator rule, not by inspection.
- Compound blocks: the first compare decodes fully (verified); when m[31] ≥ 2 the record gains `subConditions: { decoded: false, count: <m31 scalar>, note: "AND/OR sub-compare list format unverified" }`. No attempt to locate or split the interior.

## 6. Unknown-marker schema

- **Unknown action** (m[2] outside the verified set, or envelope assertion failure): `{ "decoded": false, "actionTypeCode": <u32>, "offset": <abs>, "head": <len>, "guid": "...", "members": [34 u32], "reason": "..." }`. With `--raw`, adds the object's full heap as hex.
- **Unknown field** (inside an otherwise decoded action — e.g. nonzero unexplained slot, m[6] on an unverified Set type, compound interior): `{ "decoded": false, "slot": <i or region>, "rawOffset": <abs>, "rawLength": <n> }` attached under the action's `unknownFields` list.
- **Key-action subtype**: m[2]=0 with Duration exactly 0.0 is a down/up/toggle event whose subtype is not recoverable from solid data — emitted as `{ "type": "key", "keyCodes": [...], "duration": 0.0, "subtype": { "decoded": false, "note": "down/up/toggle indistinguishable" } }`. Nonzero duration → `subtype: "press"` (verified press-and-release semantics).
- Every action, decoded or not, carries `offset` and `head`; every command carries `guidOffset`, `phrase`, `actionCount`, `chainEnd`. This is the re-decode lifeline for future research.

## 7. Category

v1's category extraction is heuristic string selection in a structurally unverified trailing region, and the review documented in-sample failures (VK-aliased fallbacks). v2 keeps it — deleting it would regress the CSV-oracle category parity bar — but demotes it honestly: emitted as `category: { "value": "...", "provenance": "heuristic", "regionOffset": <chainEnd>, "regionLength": <n> }`, never as a bare decoded field. The trailing region's raw span is recorded so the research track can close it; when it does, the heuristic is replaced, not patched.

## 8. Output

- **JSON (normative, lossless):** profile header, command list, per-action records per §4–§6, unknown markers inline. This is the only output that represents the full decode result.
- **XML (secondary, gated):** retained for VoiceAttack-import utility, but a command containing ANY unknown-marked action is excluded from `<Commands>` and listed in a manifest comment at the top of the file (`excluded: <phrase> — <n> undecoded actions`). Partial ActionSequences are never emitted; a silently lossy import file is a workaround by another name.

## 9. Verification bar (all mandatory before v2 replaces v1)

1. corinthian CSV oracle: 479/479 expanded rows matched; category parity ≥ v1 (≤1 mismatch); key and duration parity with v1 on all commands v1 decodes correctly.
2. Close the v1 gaps the review exposed: chorded keypresses decoded (v1's flat `01 00 00 00` marker misses every count≠1 chord — corinthian contains verified 2- and 3-key chords); zero phantom keypresses and zero VK-alias artifacts by construction (no pattern scan exists to alias).
3. Envelope invariants across all five reference profiles: every action m[0]=32 and m[1]=140, every chain ends before the next command, corinthian command count equals the header count field (201).
4. Unknown accounting: the decoder reports per-profile totals (actions decoded / unknown-marked, by ActionType code) so coverage is a measured number, not an impression.
5. Regression harness: checked in with a skip-if-missing guard, since the reference profiles and CSVs are gitignored and local-only (resolves the open decision in `Project_Status.md` in favor of check-in).

## 10. Non-goals

No generator changes; no writing or round-tripping VAP files; no decoding of unverified action types or member slots; no enum extrapolation (e.g. assuming unseen set-op codes); no category re-engineering beyond the provenance tagging of §7; no attempt to parse the compound sub-condition interior, the command-list index, or the trailing region. Those belong to the research plan, and v2 gains them only when they reach review-confirmed status.

## 11. Open items this spec is blocked on (none) and deferred to research

Nothing blocks drafting or implementing v2 as specified — the solid set is self-sufficient. Deferred to the research track: mouse/Launch/Say/plugin layouts, Set-Boolean value, KeyDown/Up/Toggle subtype, compound interior, m[18] grouping semantics, trailing-region structure (category), command-list indexing, remaining member slots, remaining ActionType codes.
