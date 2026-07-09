# Conditionals Probe 2 — Execution Plan

Run-book for analyzing the probe-2 exports defined in `Conditionals_Probe_2_Spec.md`. Written for a fresh Opus session with no prior context. Execute phases in order; each has a gate.

> **Review disposition (2026-07-07).** An external review of this plan was received, verified against the binaries, and actioned as needed. Applied to the spec: duplicate-Equals control block in command 1 (kills the operator/counter confound in-profile); Does Not Equal replaces Equals in commands 2 and 3 (Equals codes 0 and aliases zero padding); command 3 renumbered 0-based with the IndentLevel prediction corrected to 0,1,2,1,0,1,0,1,0 (an earlier draft omitted the branch Press Spaces). Applied here: Phase 2's cross-check now cites corinthian's five known-operator integer compares; Phase 3 gains token-forward field reads and the inline-vs-pool grouping rule; Phase 4 states the corrected IndentLevel pattern; Phase 5 gains Small Integer / Loop While cross-checks and an optional object-walk sanity check. Declined with reason: a VA-version gate (the identical `2.1.8` version string appears in all three reference binaries — same exporter throughout, and model offsets are relative anchors re-derived per profile, not absolute constants) and a k×11-gap caveat (probe 1 ground truth puts Has/Has Not Been Set last in the dropdown, codes 8/9, and the build-time screenshot settles the Integer order regardless). Already covered by existing text: the screenshot checklist (spec export item 4), input gating, token−4 expectations.

## Ground rules (non-negotiable)

1. **Analysis only.** Do NOT edit `vap_decoder.py` or any source file without explicit user authorization in the current conversation. All scripts go in the session scratchpad.
2. Branch is `feature/decode-conditional-actions`. Commit only when the user says commit. Never push.
3. Reference profiles are gitignored and stay local.
4. State every prediction BEFORE reading the bytes that test it; record refutations as prominently as confirmations.
5. Terse reporting. No hard line wrapping in prose written to docs.

## Required inputs (stop and ask if missing)

- `reference profiles/conditionals2-Profile.vap` and `.csv`
- `Screenshots/` — action lists + operator dropdowns (Text, Integer, Decimal, Boolean, Small Integer if present)
- Read first: `VAP_Conditional_Command_Analysis.md` (session-update sections), `Decoder_Accuracy_Findings_corinthian_CSV.md`, `Project_Status.md`

## Verified model (build on this, don't re-derive)

- Decompress: `zlib.decompress(data, -15)` — raw deflate.
- Command record: `[16B GUID][u32 len][phrase][u32 action-count][count × u32 offsets]`.
- Inline-token conditions: **operator = u32 at token_end**, coded as 0-indexed dropdown position (Text enum confirmed 0–9, Contains=6). **token−8 = ConditionPairing** (0-based index of the block's closing action). **token−4 = unidentified counter.** Equals=0 aliases zero padding — never trust a flat-scan Equals without an independent anchor.
- Local vars live in a declaration pool, referenced via `[01][len][name][01]` wrappers.
- Prior probe pair for cross-reference: `reference profiles/conditionals-Profile.{vap,csv}` (Text enum ground truth).

## Phase 0 — sanity gate

1. Decode the VAP with `skills/voiceattack-decoder/scripts/vap_decoder.py`. Expect exactly 3 commands: `integer ops`, `type test`, `nest test`.
2. Parse the CSV and compare its English action sequences against the spec. **The CSV is the oracle for what the user actually built** — where it differs from the spec (missing operators, different values, UI substitutions), follow the CSV and log every deviation before proceeding.
3. Transcribe each dropdown screenshot into an ordered list. These are the predicted enums. Write them down before touching bytes.

## Phase 1 — anchor the blocks (command 1)

1. Find the k×11 self-labels (11, 22, 33, …) and the control block's 999. Scan for BOTH encodings: little-endian u32/u64 AND length-prefixed ASCII ("11", "22") — the binary encoding of integer compare values is unconfirmed. The encoding that yields all values in ascending byte order is real; record it.
2. Find the `[01][len]"i"[01]` wrappers (one per block, plus the Set action's own reference).
3. For each block anchor, dump ±64 bytes and columnize across blocks. Fields identify themselves by variance pattern.

## Phase 2 — Integer operator enum + local-var layout (command 1)

- Candidate operator = the field matching 0-indexed dropdown positions across all value-bearing blocks.
- **Confound protocol** (pairing ≈ 3,6,9,… and the counter ≈ 1,2,3,… both co-increment with block order):
  a. The duplicate-Equals control block (value 999, in the spec): the operator field drops back to 0 on the final block while every per-block counter keeps climbing — decisive on its own.
  b. Cross-check corinthian: its CSV lists pool-referenced integer compares across five operators, mostly nonzero codes — `Does Not Equal ±1..±4`, `Is Less Than 2`, `Equals 0`, `Has Not Been Set` (93 rows), plus `Is Greater Than` in Small Integer Compare and Loop While records. Reading the proposed operator offset on those must reproduce the dropdown positions.
  c. Has Been Set / Has Not Been Set blocks carry an operator but no value — the field present there is not the value.
- Deliverables: Integer operator enum table; operator/value offsets relative to the var-ref wrapper (the pool-referenced layout the flat scan can't reach today).

## Phase 3 — value-type field (command 2)

- Anchor each of the five blocks by its literal ('type-text', 111, 1.25, the Boolean encoding, the small-int value). Blocks are built with Does Not Equal (spec default), so a predicted token_end = 1 is a second anchor; if the export shows Equals anyway, use literal anchors only (zero-alias).
- The five records are NOT near-twins — token names and value encodings differ in length, so whole-record alignment drifts. Anchor block LOCATION on the literal, but READ candidate fields forward from the TOKEN start (in zoom and probe 1 the literal precedes its token by ~50 bytes; the variable-length value must never sit between anchor and field).
- If any type fell back to a local var (the spec allows it when the UI refuses a token), that block is pool-referenced and shaped differently — analyze inline-token and pool blocks as separate groups; never diff across the two.
- Diff the five condition records. The field that varies with compare type is `ConditionStartValueType` — record its code per type. If nothing varies near the condition, the type lives in the action subtype instead; that is also an answer.
- Record each type's value encoding (string / u32 / double / bool byte). This closes the value-encoding question independently of Phase 1.

## Phase 4 — structure fields (command 3)

- Read ConditionPairing for 'outer' (action 0), 'inner' (1), 'branch-two' (4). Verdict: outer→4 means "next branch point" (zoom-consistent); outer→8 means "final End". State it explicitly and update the ConditionPairing definition if refuted.
- IndentLevel: the field reading 0,1,2,1,0,1,0,1,0 across actions 0–8 (the spec's corrected prediction).
- Subtype codes: diff the Else (6) and End (3, 8) records against command 1's flat Begin/End records; isolate what distinguishes Begin / Else If / Else / End.

## Phase 5 — cross-validation gate (mandatory before conclusions)

- Re-read conditionals-1, zoom, and corinthian with every new field definition. Each must hold there too: zoom's pairing 2/4 must fit the Phase 4 verdict; corinthian's `{BOOL:}` pairing spread (2,3,4,5,6,9,15,21) must make structural sense; conditionals-1's counter values (1..10) should be explainable if token−4 is cracked.
- Corinthian also carries Small Integer Compare (`[i] Is Greater Than 2/3`) and Loop While (`[count] Is Greater Than 0`) records with CSV-known operators — free extra targets for the Integer/Small-Integer layouts.
- Optional: use conditionals2 as a fully-known controlled input to sanity-check the member-table offsets (`[32,140,156,160]`) from the analysis doc — the cheapest possible test of the object-walk model. Cross-check only; do not expand scope.
- Any inconsistency downgrades the finding to PLAUSIBLE. Say so in the docs — do not round up to confirmed.

## Phase 6 — write-up (docs only, then stop)

- Append a dated session-update section to `VAP_Conditional_Command_Analysis.md`: enum tables, layouts, verdicts, refutations, remaining opens (Decimal/Boolean enums are screenshot-predicted only; the member-table base still needs the action-graph walk; token−4 if unexplained).
- Update `Project_Status.md`: condition section, Open list, key artifacts (add the conditionals2 pair).
- Report to the user: closed / refuted / still open. Then STOP. Applying anything to the decoder is a separate, explicit authorization.

## Failure modes

- Fields not at predicted offsets → fall back to near-twin whole-record diffing; the probe's blocks are near-twins by construction.
- Dropdown order differs from assumptions → screenshots win; restate predictions before concluding.
- VA reordered or collapsed actions relative to the spec → analyze what the CSV says was built, not what the spec asked for.
