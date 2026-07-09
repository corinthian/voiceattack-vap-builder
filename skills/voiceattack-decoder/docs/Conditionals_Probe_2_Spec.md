# Conditionals Probe 2 — Spec

Targets everything the first probe left open: Integer/Decimal/Boolean-variable operator enums, the operator field position for pool-referenced local vars, the value-type field, Begin/Else If/Else/End subtype codes, IndentLevel, and token−4's meaning. One VoiceAttack profile, three commands, built the same way as probe 1.

_Amended 2026-07-07 after review: control block added to command 1; Does Not Equal replaces Equals in commands 2 and 3; command 3 renumbered 0-based with the IndentLevel prediction corrected._

## Design rules (carried over from probe 1)

1. **One variable per contrast.** Within a command, every block is identical except the one field under test.
2. **Self-label every operand.** Text literals name their operator; numeric literals use a distinctive per-block value (block k compares against k×11: 11, 22, 33, …) so blocks are identifiable in the bytes.
3. **Sweep in dropdown order** and screenshot each operator dropdown — the menu order is the predicted code order (probe 1: codes = 0-indexed dropdown position).
4. Same action inside every block: Press Space, hold 0.1s. Begin + End only, no Else If, except in command 3.

## Command 1 — `integer ops` (Integer enum + local-var operator position)

- First action: Set integer `[i]` value to 0.
- Then one `Begin Integer Compare` block per dropdown entry, in dropdown order: `[i] <operator> <k×11>`, Press Space, End Condition. (Has Been Set / Has Not Been Set take no value — that's fine, they're identified by position, same as probe 1.)
- **Control block (last):** one extra block repeating the FIRST dropdown entry (Equals) with value 999. This breaks the operator-equals-block-order confound inside the profile itself: on the control block the operator field drops back to 0 while every per-block counter keeps climbing.
- `[i]` is a local var, so it routes through the declaration pool — this command is the ground truth for reading operator/value on pool-referenced conditions, the case the flat scan can't reach today.

**Prediction:** operator codes = 0-indexed Integer-dropdown positions. The k×11 values locate each block; the field that counts 0,1,2,… across blocks near each var-ref wrapper AND drops back to 0 on the control block is the operator.

## Command 2 — `type test` (value-type field)

- Five Does-Not-Equal compares, one per compare type, all with inline tokens where the UI allows: Text `[{TXT:t}] Does Not Equal 'type-text'`; Integer `[{INT:i}] Does Not Equal 111`; Decimal `[{DEC:d}] Does Not Equal 1.25`; Boolean `[{BOOL:b}] Does Not Equal True`; plus Small Integer if the dialog offers it. (Does Not Equal, not Equals: Equals codes 0, which aliases zero padding and is invisible to the flat scan; a nonzero operator doubles as a per-block anchor.)
- If the UI refuses a token for some type, use a local var for that block and note which in the CSV filename or a comment command.

**Prediction:** token_end operator = 1 for every block (Does Not Equal is position 1 in each dropdown — verify against the screenshots). The field that VARIES across the five blocks is `ConditionStartValueType`. If nothing varies near the condition, the type is folded into the action subtype instead — also an answer.

## Command 3 — `nest test` (subtype, IndentLevel, pairing)

Action sequence, all Text compares on `[{TXT:t}]` using Does Not Equal (same nonzero-anchor rationale as command 2), distinct self-naming literals. Indices are 0-based and used consistently below:

```
0. Begin ... Does Not Equal 'outer'
1.     Begin ... Does Not Equal 'inner'
2.         Press Space 0.1s
3.     End Condition            (inner)
4. Else If ... Does Not Equal 'branch-two'
5.     Press Space 0.1s
6. Else
7.     Press Space 0.1s
8. End Condition                (outer)
```

**Falsifiable predictions** (0-based indices as listed):
- ConditionPairing (token−8 in probe-1 layout): zoom paired a Begin to its Else If, so the "pairing = next branch point" model predicts 'outer' → 4 and 'branch-two' → 6; the rival "pairing = final End" model predicts 'outer' → 8 and 'branch-two' → 8. 'inner' → 3 under both (its block has no branches). The three read values decide between the models — settling that ambiguity is what this command is for.
- IndentLevel: expected values across actions 0–8 are **0,1,2,1,0,1,0,1,0** (corrected 2026-07-07 — an earlier draft omitted the branch Press Spaces at indices 5 and 7, which sit at indent 1). The field taking exactly that pattern is IndentLevel.
- Else (6) and End (3, 8) have no operand — their subtype/ActionType codes surface by diffing these actions against command 1's flat Begin/End blocks.

## Export checklist

1. Profile name `conditionals2`, nothing in it but these three commands.
2. Export profile → `reference profiles/conditionals2-Profile.vap`
3. CSV export → `reference profiles/conditionals2-Profile.csv`
4. Screenshots → `Screenshots/`: each command's action list, plus the operator dropdown open for each compare type (Text, Integer, Decimal, Boolean, Small Integer if present).

## Expected yield

| unknown | closed by |
|---------|-----------|
| Integer operator enum | command 1 sweep + control block + dropdown screenshot |
| local-var operator/value position | command 1 (k×11 values anchor the blocks) |
| ConditionStartValueType field + codes | command 2 |
| Begin/Else If/Else/End subtype codes | command 3 vs command 1 diff |
| IndentLevel position | command 3 (0/1/2 pattern) |
| ConditionPairing semantics (branch vs End) | command 3 predictions |
| token−4 meaning | more samples from all three commands may expose the pattern |

Not covered: the member-table base / object envelope (that's the action-graph walk, a pure-analysis job on existing data) and Decimal/Boolean full enums if their dropdowns hold operators command 1 doesn't reach — the screenshots cover those by giving the predicted order anyway.
