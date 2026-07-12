# VAP Uncertainty Research — Phase 0–2 Closure Table (2026-07-08)

> **HISTORICAL (2026-07-09).** All closures and the ActionType table are folded into `VAP_Format_Specification.md` v0.2, which alone is authoritative. This file is retained as the evidence trail; Probe B targets and parked items are tracked in spec §12.
>
> **UPDATE (2026-07-11).** Probe B executed and closed — see `VAP_Probe_Specs_A_B.md`'s banner and `VAP_Format_Specification.md` v0.3. The row-3 (mouse, PARTIAL) and row-4 (Set-Boolean, PLAUSIBLE) verdicts below are now CLOSED in v0.3; row-7 (compound m[31], PARTIAL) stays PARTIAL/decode-only by design. This file is not updated in place — v0.3 is authoritative for all current verdicts; `VAP_Parked_Uncertainties.md` is authoritative for everything still open.

Session run of `VAP_Uncertainty_Research_Plan.md`, Phases 0→2, stopped at the closure
gate per user direction. Analysis-only; scripts in scratchpad; no project docs edited.
Verdict rule (user ruling): "holds-where-it-appears = CLOSED" (a feature consistent in
every profile that contains it is CLOSED even if some profiles lack it).

## Phase 0 — harness sanity: PASS
Command scanner ported from vap_decoder v1 (signature + offset-table sanity + @368
profile-record exclusion); walk uses the RAW actionCount at phrase_end and chains by head.
Per-profile actions: zoom 5, numkeys 16, conditionals 111, base 303 — all exact vs review.
corinthian: 201 commands (= profile-record count field), 1168 actions vs review's 1166.
1168 is AUTHORITATIVE: walk is count-driven (count=actionCount, anchored by set-fire=37
and header=201, both reproduced); all 1168 objects pass m[0]=32, m[1]=140, clean in-bounds
chaining (chain_overrun=0). A phantom would need m0/m1 to coincide at arbitrary offsets and
would trip chain_overrun — neither happens. Delta cause unknown; does not affect any slot
semantics. (set-fire trailing 587 B vs review's "1,364" — second harmless harness mismatch.)

## Phase 1 — 34-slot census (1603 objects, 5 profiles)
- Fixed-offset heap header: m[0]=off 32 (const struct), m[1]=off 140 (heap start / GUID),
  m[2]=off 156, m[3]=off 160, m[4]=off 168, m[5]=off 176. Slots 6+ have variable offsets.
- m[1] deref = 1603 distinct GUIDs (per-action Id). m[2] deref = 40 distinct ActionType codes.
- Dead/constant: m[10]≡0xFFFFFFFF, m[22]≡0, m[26]≡0, m[32]≡0, m[33]≡0.
- m[27]≡m[28]≡0x886e0900 (review §2.7 exact — const sits at deref, NOT 0xF1886E09).
- NEW: m[23] is a binary FFFF/0 flag (1359 FF / 244 zero) — meaning unmapped.
- ~24 slots near-constant (mostly 0 or FFFF) — confirms prediction P4.

## Phase 2 — closures

| # | item | verdict | evidence |
|---|------|---------|----------|
| 1 | ActionType inventory | **CLOSED** (23 codes) | corinthian CSV single-action + aligned multi-action |
| 2 | KeyDown/Up/Toggle discriminator | **CLOSED** | distinct ActionTypes 8/9/67, not a subtype member |
| 3 | Mouse member layout | PARTIAL | m2=12; context m[6], param m[7]; enum+XY → Probe B |
| 4 | Set-Boolean value | PLAUSIBLE | m[14] 0=True/1=False, NO surviving counterexample; value-vs-order confound → Probe B |
| 5 | Set field map | **CLOSED** | value Text→m7 / Int→m11 / Dec→m25; target Text&Bool→m6 / Int&Dec→m15; Set-Int 58/58 |
| 6 | Pause duration | **CLOSED** | m[3] double = 1.125 (CSV "Pause 1.125 s"); durations all sane |
| 7 | Compound m[31] interior | PARTIAL | m[31]=subcount scalar confirmed; record format → Probe A |
| 8 | Local-var pool | PARTIAL | names length-prefixed UTF-8 where used; no single pool region |
| 9 | Trailing region / category | PARTIAL | category heuristic (v1); structure not mapped this session |
| 10 | Header @8 + cmd index | PARTIAL/OPEN | @8 = top-level offset table (0/1/2 → profile rec/name/count); entries 3+ point into a trailing ~size−530 region that likely holds a per-command index — UNDECODED; detection stays scan-based |
| 11 | Constants + 2.1.8 | **CLOSED** | m0=32, m27/28=0x886e0900; 2.1.8 optional (3/5, newer exports) |
| 12 | IndentLevel storage | **CLOSED** | not stored; derived from Begin/End nesting; m[18]=ordinal 1..8 |

### ActionType (m[2]) code table — CSV-confirmed
0 PressKey · 2 Pause · 8 KeyDown · 9 KeyUp · 12 MouseAction · 16 ExecuteCommand ·
17 KillCommand · 18 SetSmallInt · 19 BeginCondition · 20 EndCondition · 21 SetText ·
22 ExecuteExternalPlugin · 23 Write · 29 Else · 30 BeginLoopWhile · 31 EndLoop ·
32 Marker · 33 JumpToMarker · 35 PlaySound · 36 SetBoolean · 37 SetInteger ·
38 SetDecimal · 40 QuickInput · 62 PauseVariable · 63 ElseIf · 64 ExitCommand · 67 KeyToggle
PLAUSIBLE (single-action command name = its sole action): 24 paste dictation ·
25 dictation mode · 26 stop dictation · 27 Clear dictation buffer.
32/33 aligned in `clear planet…`: obj21 "Marker: Begin jump"→32, obj10/17 "Jump to Marker"→33.
Still UNLABELED (→ Probe B): 50, 51 (start/stop listening).

### Key corrections / new facts
- ActionType 62 = Pause-variable ("Pause a variable number of seconds [{DEC:x}]"),
  distinct from fixed Pause=2.
- m[6] is polymorphic: Set-target name (Text/Bool) AND mouse context code ('SPECIAL').
- Set-Integer target is m[15] (not m[6]); m[11]=integer literal. Set semantics per-type.
- m[14] Set-Boolean value uses positional dropdown coding (True=0) IF confirmed — matches
  the operator-enum principle; resolves what review left "unresolved," pending Probe B.

### Carried to Phase 3 (scope decision 2026-07-08)
- **Probe A DROPPED.** Support scoped to nested single-condition blocks, already fully decoded
  (IndentLevel/pairing/ordinal on `nested + decimal`). Multi-conditioned AND/OR compounds
  (m[18] grouping, m[31] interior) are now **decode-only** — emitted as `unknown` for
  third-party profiles, not authored or probed. Items 2 & 7 close as "decode-only / de-scoped".
- **Probe B (actions):** unlabeled ActionTypes 50/51; Say/Launch/SetClipboard codes + layouts;
  mouse context-code enum + X/Y; Set-Boolean m[14] value-vs-order; Set-op m[20] dropdown sweep;
  Set-SmallInt layout. (24/25/26/27 PLAUSIBLE, 32/33 closed as Marker/JumpToMarker.)
