# VAP Conditional (Variable) Command Structure — Analysis

> **HISTORY DOCUMENT (2026-07-09).** Session-by-session research log, superseded by `VAP_Format_Specification.md` v0.2 (authoritative). Earlier sections record claims that later sections refute — read chronologically or not at all. Known residual contradictions are annotated in place below.

Reverse-engineering notes for the **if/else + `{LASTSPOKENCMD}`** command in
`reference profiles/zoom-if-else.vap`. This is the "second failure" parked by the
category-whitelist fix: even once the command is *detected*, its conditional actions
decode wrong. This document records how the structure actually decodes.

It advances the "Next Steps → Extract condition/loop structures" item in
`VAP_Binary_Schema_Analysis.md`. It is analysis only — no decoder code is proposed here.

Every offset below is a byte position in the **decompressed** buffer
(`zlib.decompress(data, -15)`, length 3111).

## Claim confidence

Each finding is tagged: **[SOLID]** = read directly and cross-checked; **[INFERRED]** =
consistent with the bytes but not proven; **[OPEN]** = not yet cracked.

## What the command is  [SOLID — ground truth]

Confirmed against VoiceAttack's own "Edit a Command" UI and its CSV export
(`reference profiles/Cities Skylines II-Profile.csv`). The action sequence is a single
**if / else-if / end** block — five `CommandAction`s:

```
Command "zoom [out; in]"                       category: camera
  1. Begin Text Compare : [{LASTSPOKENCMD}] Contains 'out'
  2.     PressKey F (VK 0x46), hold 1.5s
  3. Else If Text Compare : [{LASTSPOKENCMD}] Contains 'in'
  4.     PressKey R (VK 0x52), hold 1.5s
  5. End Condition
```

This corrects an earlier draft that read it as *two independent `if`s*. It is one condition
block: `Begin` + `Else If` + `End`. Operator = **Contains**, comparison type = **Text**,
left operand = the token `{LASTSPOKENCMD}`, right operand = the literal. The keypresses
"hold for 1.5 seconds" — matching the Duration double found in the bytes.

## Command header  [SOLID]

| Offset | Bytes | Meaning |
|--------|-------|---------|
| 750 | `7e38f126-2a11-4418-b0e3-1e064917e1d6` | command GUID (Id) |
| 766 | `0e 00 00 00` | phrase length = 14 |
| 770 | `zoom [out; in]` | phrase (UTF-8) |
| 784 | `05 00 00 00` | **action count = 5** (the five CommandActions above) |
| 788 | `347, 32, 140, 156, 160` | per-action offset table (5 × uint32) |

**Count = number of actions** [SOLID — ground truth resolves the earlier puzzle]. The `5`
is the ActionSequence length: Begin / PressF / ElseIf / PressR / End. Cross-checks: numkeys
single-key commands are count = 1 (one keypress); `num 0-9` is count = 10 (ten keypresses).
The `[347, 32, 140, 156, 160]` are the per-action offsets; the longer ascending run that
follows belongs to the first action object's own member table (see *Object envelope*), not
the command's table.

## Condition operand encoding — "out" branch  [mixed]

Bytes 968–1042:

| Offset | Bytes | Meaning | Confidence |
|--------|-------|---------|------------|
| 968 | `ff ff ff ff` | prior-field terminator | SOLID |
| 972 | `03 00 00 00` + `out` | length-prefixed literal operand | SOLID |
| 979–1014 | `ff…` / `00…` runs | empty/optional members, null-padded | SOLID |
| 1015 | `02 00 00 00` | 0-based index of the paired closing action (the Else If @ index 2 closes this Begin) — earlier misread as "subtype 2 = Begin" | CORRECTED 2026-07-07 |
| 1019 | `01 00 00 00` | unknown member (reads 1 in both zoom branches; counts 1..10 in the conditionals probe) — earlier misread as "operator, Contains = 1" | OPEN |
| 1023 | `0f 00 00 00` + `{LASTSPOKENCMD}` | length-prefixed token operand (the left/evaluated value) | SOLID |
| 1042 | `06 00 00 00` | **`ConditionStartOperator` = 6 = Contains** — 0-indexed dropdown position, sits immediately after the token operand; earlier misread as a token-type code | GROUND-TRUTH 2026-07-07 |

The "Else If" branch repeats this shape (literal `in` @1650, token `{LASTSPOKENCMD}` @1700) with token−8 reading **4** instead of **2** — the 0-based index of the action that closes each block (branch 1 is closed by the Else If at index 2, branch 2 by the End at index 4), i.e. `ConditionPairing`, not a subtype. Both branches read operator **6 = Contains** at token_end (@1042 / @1719). An earlier draft read token−8 as a Begin/Else-If subtype and token−4 as the operator; the 2026-07-07 conditionals probe refuted both — see that session update.

## Keypress action record  [SOLID]

Verified across the zoom branches and all seven numkeys commands:

```
[ double Duration @ i-12 ] … 00 00 00 00 | 01 00 00 00 | VK (uint16) …
```

- The 8-byte IEEE-754 double **12 bytes before** the `00000000 01000000` marker is the
  key-hold Duration: **1.5** for both zoom keys, **0.5** for every numkeys key.
- `VK` is a uint16 at marker+8. F = 0x46, R = 0x52.

This duration doubles as a validity check: a real keypress has a sane double in that slot (0.03–1.5 observed across zoom / numkeys / corinthian); false-hits do not — but corinthian phantom slots hold positive **denormals** (~1e-304), so the test needs a floor (e.g. `0.001 <= d <= 60`), not just `d > 0` (floor added on review 2026-07-07; see next section).

## Two decoding traps that mislead the current decoder  [SOLID]

1. **The `'F'` / `'R'` "label strings" do not exist.** They are the string-scanner
   aliasing the keypress's own VK byte: `u32 @ marker+4 = 01 00 00 00` reads as a length-1
   string, and the next byte (`0x46 = 'F'`) is the VK code itself. One physical byte,
   two readings. Each branch action is cleanly just `PressKey VK` — nothing trails it.

2. **The `VK=0x00` and `VK=0xFFFF` "keypresses" are artifacts.** The flat pattern matcher
   fires on `00`-padding inside the condition object (VK=0x00 at 1054, 1731) and on the
   `FF`-run terminator before the category (VK=0xFFFF at 2367). Their Duration slots are
   all-zero (0.0) and all-FF (NaN) respectively — i.e. not real actions.

Both traps are byproducts of **pattern-scanning a flat byte range**. They are the concrete
argument for why a conditional decoder must **walk the object tree**, not scan: the flat
scanner cannot tell a real action from aliased condition/padding bytes.

## Object envelope hypothesis  [INFERRED] / [OPEN]

Every serialized object appears to follow:

```
[16-byte GUID Id][uint32 memberCount][memberCount × uint32 member-offset table][member data]
```

recursively (a Command contains an action sequence, which contains action objects, each
with its own GUID + offset table). Evidence: the action objects' offset tables are
**byte-identical in their tail** (`…32,140,156,160,168…` at both 788 and 1136), differing
only in a per-instance head value (347 vs 331) — i.e. a shared type-level member layout
emitted per instance.

## Triangulation results (numkeys, five single-key commands)  [SOLID]

Method: `numkeys-Profile.vap` has five near-identical single-key commands
(`num -`, `num *`, `num .`, `num /`, `num +`). Each record spans 929 bytes (GUID-to-GUID).
Aligning all five at their GUID start and computing a constant-vs-variable byte mask
isolates the type **schema** (constant) from **instance** data (variable).

**Finding 1 — member offsets are object-relative, not absolute.** All five commands are
`count = 1`, and the single stored property value is **331 in every record**, despite each
record sitting 929 bytes farther into the file. An absolute file offset would increase by
929 each time; a constant value proves the offset is intrinsic/relative. (What exact base
331 is measured from is still **[OPEN]** — no tested base lands on a clean landmark.)

**Finding 2 — the single-key command template.** The 929-byte record is byte-constant
except for these positions (offsets relative to the command GUID):

| rel | size | varies as | meaning |
|-----|------|-----------|---------|
| 0 | 16 | unique GUID | command Id |
| 24 | 1 | `2d/2a/2e/2f/2b` | the phrase's trailing char (inside `num X`) |
| 169 | 16 | unique GUID | nested sub-object Id |
| 209 | 1 | `6D/6A/6E/6F/6B` | **keypress VK code** (SUBTRACT/MULTIPLY/DECIMAL/DIVIDE/ADD) |
| 479 | 16 | unique GUID | nested sub-object Id |

Everything else in the front of the record is fixed schema. So the VK lives at a fixed
offset **inside the keypress object's template** — no scanning needed once the object is
located. (This is the numkeys template specifically; offsets differ per command shape.)

**Finding 3 — three GUID-tagged objects per command.** Each command carries three distinct
Id GUIDs (rel 0, 169, 479), and each occurs exactly once in the file. They are unique
object Ids, not cross-references. This confirms the recursive envelope: a command nests
sub-objects (action-sequence / action), each with its own Id.

**Finding 4 — `0xF1886E09` is a generic separator, not a type tag.** The constant uint32
`0xF1886E09` (bytes `09 6e 88 f1`) recurs throughout the action region of numkeys, zoom
*and* corinthian, next to every kind of action and field — so it is a structural marker,
not a per-type discriminator. (An earlier draft treated it as a candidate type tag; the
corinthian frequency rules that out.)

## Schema map (VoiceAttack XML ↔ binary)

Source of truth: Edvard `defaultcommand.xml` — VoiceAttack's own `CommandAction`
serialization. **Conditions are not a separate action type; they are fields on each
action:** `Ordinal`, `IndentLevel`, `ConditionMet`, `ConditionPairing`, `ConditionGroup`,
`ConditionStartOperator`, `ConditionStartValue`, `ConditionStartValueType` — alongside
`ActionType`, `Duration`, `Delay`, `KeyCodes`, `Context`, `X`, `Y`, `InputMode`,
`IsSuffixAction`. `IndentLevel` is what nests actions inside a condition block.

**The binary stores integer codes, not names.**  [SOLID] corinthian contains zero
occurrences of `PressKey`/`Say`/`BeginCondition`/etc. as strings; `ActionType` and the
condition fields are serialized as integers (the `01 00 00 00` in the keypress pattern =
ActionType 1 = PressKey). A name-level decode therefore needs the int↔name enums.

**Condition operand block, mapped across zoom + corinthian, anchored by ground truth.**
VoiceAttack's UI reports zoom's condition as **`{LASTSPOKENCMD}` contains "out"** (and the
other branch `… contains "in"`). In the bytes, the token operand is preceded by two uint32
fields:

```
… [uint32 A] [uint32 B = ConditionStartOperator] [uint32 len]["{TOKEN}"] …
```

- **The token−4 / token−8 pair is NOT operator/subtype — both readings REFUTED (2026-07-07, conditionals probe).** An earlier draft argued B (token−4) = operator with contains = 1, anchored on both zoom branches reading B = 1 — but both branches share the operator AND the value type, so invariance could not separate the candidates. The conditionals probe (ten Text operators, one per block) shows token−4 counting 1..10 while the real operator sits at **token_end**; see that session update for the full enum. The corinthian B-value statistics (1×82, 2×8… for `{TXT:}`; 2/3 for `{BOOL:}`) and the "boolean operators = 2/3 (is-true / is-false)" reading — including the same-day CSV cross-check note that endorsed it — were artifacts of the same misassignment: boolean token compares use the shared Text enum (Equals = 0 / Does Not Equal = 1) against quoted 'True'/'False' literals, and the binary matches the CSV exactly (the profile's single cargo-scoop Does Not Equal is the single token_end = 1). What token−4 actually is remains OPEN (1, 1 in zoom; 1..10 in conditionals; mostly 1 in corinthian).
- **Token−8 = `ConditionPairing`, the 0-based index of the block's closing action — INFERRED, strong.** zoom: Begin reads 2 (its Else If's index), Else If reads 4 (the End's index). conditionals: the ten Begins read 3, 6, …, 30 — each block's own End. This also explains the corinthian token−8 spread (2,3,4,5,6,9,15,21) that killed the "subtype" reading. Begin / Else If / Else / End subtype codes are therefore still unlocated.
- **Value-type location still open.** Neither token−4 nor token_end tracks Text/Boolean/Integer. In the conditionals probe every nearby slot is constant across the ten blocks — expected, since all ten are Text compares; a mixed-type probe is the discriminator (probe 2).
- **B = 0 is the noise floor.**  [SOLID] A token embedded in `Say` text has zero-padding
  before it, so it reads B = 0 — which is why scanning cannot tell condition operands from
  Say-text tokens. Only an object-tree walk can. Same lesson as the keypress aliasing.

**Operand order** (from zoom): the `A,B` pair precedes the **token** operand specifically.
The *literal* side of the comparison (`out`) has no such prefix — it is `FF`-padded then
`03 00 00 00 "out"` — and the pair sits *between* the literal and the token. So the pair is
a property of the token operand, not of every operand.

## Still open — all gated on one input

Remaining unknowns (updated 2026-07-07): the **Text-compare operator enum is now fully known** — 0-indexed dropdown order, `Contains = 6`, see the conditionals-probe session update. Still open: the Integer / Decimal / Boolean-variable dropdown enums; the operator field position for pool-referenced local-var conditions; **where the value type is stored** and its codes; the byte position of `IndentLevel` / `Ordinal` / the Begin-ElseIf-Else-End subtype within a `CommandAction`; the object type-code enum; and the member-table base (rel offset like 331).

Every one is resolved cheaply by a **matched pair** — the *same* profile exported from
VoiceAttack in both binary `.vap` and uncompressed XML. The XML names every field the
binary encodes as an integer, so one aligned read replaces all further byte-staring.
Producing that pair needs VoiceAttack itself; it cannot be reconstructed from the binaries
alone. The semantic decode and record layout above already explain *how it decodes* — the
matched pair is what a generic decoder *implementation* would require.

## Reference offsets (zoom-if-else, decompressed)

| Item | Offset |
|------|--------|
| Profile record (GUID) | 368 |
| Command GUID | 750 |
| Phrase `zoom [out; in]` | 770 |
| Property count / table | 784 / 788 |
| Literal `out` | 972 |
| Token `{LASTSPOKENCMD}` (branch 1) | 1023 |
| Keypress F (VK 0x46, dur 1.5) marker | 1307 |
| Literal `in` | 1650 |
| Token `{LASTSPOKENCMD}` (branch 2) | 1700 |
| Keypress R (VK 0x52, dur 1.5) marker | 1984 |
| Terminator false-hit (VK 0xFFFF) | 2367 |
| Category `camera` | 2482 |
| Version `2.1.8` | 2802 |

---

## Session update — corinthian CSV matched pair (2026-07-07)

Ground truth this round: `reference profiles/corinthian-4-Profile.{vap,csv}` (both gitignored, local). The CSV lists every command's category + full English action sequence, including **882 compare-conditions across the 479 rows** (111 across the 193 unique action sequences; compound `Begin Condition : (…)` blocks not counted). An earlier draft said "258 conditions" — not reproducible under any counting rule tried on review (2026-07-07); superseded by the figures above. Operator vocabulary observed, by compare type: **Text** — Contains, Equals, Starts With, Does Not Equal; **Boolean (local vars)** — Equals True only (the operator "Equals False" never occurs); **{BOOL:} tokens** — serialized as compares against quoted literals: Equals 'True', Equals 'False', Does Not Equal 'True'; **Integer** — Has Not Been Set, Is Greater Than, Is Less Than, Equals, Does Not Equal.

### Confirmed
- ~~Contains = ConditionStartOperator code 1~~ — **REFUTED 2026-07-07** by the conditionals probe: the token−4 field that read 1 is not the operator. The operator sits at **token_end** and **Contains = 6** (full enum in the conditionals-probe session update below). The caution recorded here about the corinthian correlation being confounded was warranted — about this bullet's own anchor.
- **The token-adjacency model is dead.** The operator/subtype are NOT at fixed offsets before the operand string. Proof: across corinthian conditions the byte at `token−8` (the zoom "subtype" slot) takes values 2,3,4,5,6,9,15,21 — no Begin=2/ElseIf=4 pattern. Operator/subtype are object members at member-table offsets, not adjacent fields.
- **Near-twin diff works; structure is byte-stable relative to `phrase_end` within a command family.** Diffing `throttle 25/50/75/100` (identical except key + literal) pinpoints, relative to `phrase_end`:
  - **+184 = keypress VK code** — `[112,115,113,114]` = F1,F4,F2,F3 (matches 25/100/50/75).
  - **+580 = ConditionStartValue** (integer literal) — `[1,4,2,3]` = "Does Not Equal 1/4/2/3".
  Everything else identical → the operator ("Does Not Equal", constant across the four) lives in the non-differing bytes.
- **Two operand-storage mechanisms.** Global tokens (`{LASTSPOKENCMD}`, `{TXT:}`, `{BOOL:}`, `{INT:}`) are stored inline in the condition. Local condition vars (`[throt]`, `[i]`, `[count]`, `[System_visits]`) live in a variable **declaration pool** and are referenced; the var-ref wrapper is `[01 00 00 00][len][name][01 00 00 00]`. The pool record and the condition record share this wrapper, so a global name-search lands on the pool, not the compare — a trap (mistook the pool's `01`/`fc ff ff ff` for the compare value).
- **KeyDown/KeyUp records share the PressKey marker (fix-verification finding, 2026-07-07).** "Press down X key" / "Release X key" actions match the same `00 00 00 00 01 00 00 00` marker as PressKey, with the Duration slot **exactly 0.0** (all-zero bytes) instead of a hold time — so the `01` either covers all three key actions or is not the ActionType field. Down vs up vs toggle is not distinguishable from the flat record; needs the object walk. (This is why the decoder's phantom filter accepts d==0.0 with a suffix check rather than requiring a positive duration.)

### Still open (needs the action-graph walk — a research investment)

(Annotation 2026-07-09: this section is fully superseded — every item below closed. The walk was run (1,603 objects); all operator enums are in spec §8.2 — and "Contains=1" in the first bullet was itself refuted, Contains=6. See the session updates below and spec v0.2.)

- Operator codes beyond Contains=1 (Equals, Starts With, Does Not Equal, Is Greater/Less Than, Has Not Been Set, Equals True/False). The cross-operator contrast is ambiguous because the compare value can only be reached reliably by walking the action objects (the var-name anchor hits the pool). 
- ConditionStartValueType, ConditionPairing/Group, IndentLevel, Begin/ElseIf/Else/End subtype codes.
- **The unlock:** dereference the shared command-member offsets (`[32,140,156,160]` constant across zoom `[347,…]` and throttle `[331,…]`) to walk actions in order, read each ActionType, match a known sequence (throttle = PressKey, BeginIntegerCompare, SetSmallInt, EndCondition, SetInteger) to fix the BeginCompare ActionType code, then read operator/type/subtype at consistent object-relative member offsets. This finds ALL conditions (inline and by-ref) across every command. Not attempted this round (higher-cost, previously ambiguous) — fund explicitly.

---

## Session update — conditionals probe (2026-07-07): Text operator enum cracked

Ground truth: `reference profiles/conditionals-Profile.{vap,csv}` + VA UI screenshot (authored probe, gitignored/local). One command ("New Command", action-count field 31 = 1 SetText + 10 × Begin/PressSpace/End — fifth profile confirming count = actions), sweeping all ten Text-compare operators in dropdown order, each literal operand naming its own operator (`Equals 'equals'`, `Contains 'contains'`, …) — the binary is self-labeling.

**Design confound and its resolution.** Operator order = block order, so any per-block counter mimics the enum: token−8 steps 3,6,…,30; token−4 counts 1..10; token_end counts 0..9. Cross-profile tiebreak: zoom's two Contains branches read **token_end = 6** (while token−4 reads 1, 1), and corinthian's `{BOOL:}` conditions read token_end = 0 everywhere except the profile's single Does Not Equal (cargo scoop), which reads 1 — exact CSV correlation. token_end is the operator.

**[GROUND-TRUTH] `ConditionStartOperator` sits immediately after the inline token operand (token_end), coded as the 0-indexed dropdown position:**

| code | operator |
|------|----------|
| 0 | Equals |
| 1 | Does Not Equal |
| 2 | Starts With |
| 3 | Does Not Start With |
| 4 | Ends With |
| 5 | Does Not End With |
| 6 | Contains |
| 7 | Does Not Contain |
| 8 | Has Been Set |
| 9 | Has Not Been Set |

Boolean token compares (`{BOOL:…}`) share this enum, comparing against quoted 'True'/'False' literals (Equals = 0 and Does Not Equal = 1 observed in corinthian).

**Refuted by this probe** (all previously recorded as confirmed/inferred): Contains = 1 (zoom token−4 misread); token−8 = Begin/Else-If subtype (it is `ConditionPairing` — the 0-based index of the block's closing action: zoom 2/4, conditionals 3,6,…,30, corinthian's 2,3,4,5,6,9,15,21 spread); B = 2/3 = boolean is-true/is-false operators.

**Noise floor, again.** Equals = 0 aliases zero padding: a token in a non-condition context (Say / Write / Set-text operand) can read token_end = 0 or FF-run. Only nonzero, non-FF token_end values are trustworthy from a flat scan — reading Equals conditions reliably still needs the object walk. Same lesson as the keypress aliasing.

**Still open after this probe:** what token−4 is (1, 1 in zoom; 1..10 in conditionals; mostly 1 in corinthian); the value-type field and codes; Integer / Decimal / Boolean-variable dropdown enums; operator position for pool-referenced local-var conditions; Begin/Else If/Else/End subtype codes and IndentLevel. Probe profile #2 is specified in `Conditionals_Probe_2_Spec.md`.

---

## Session update — object-tree walk: member layout + base found (2026-07-07)

Ground truth this round: an object-tree walk over profiles already in hand — `zoom-if-else.vap`, `numkeys-Profile.vap`, conditionals-1 (`conditionals-Profile.vap`), and `corinthian-4-Profile.vap` (all four already used above). Pre-vap analysis on existing data, no new export needed — this is the "action-graph walk" the corinthian session update flagged above as a research investment.

**[SOLID] Object-envelope base found — this answers the doc's long-open "what base is 331 measured from."** Every serialized CommandAction is `[u32 head][u32 member[0]]...[u32 member[N-1]]` — an offset array, ascending after head — followed by a member-data heap, and every member offset is relative to the array's own start address: the position of `head` itself. `head` is not a member offset — it is the object's total byte length, which doubles as a pointer to the next sibling object (347 for zoom's Begin, 331 for every keypress object). So 331 was never measured from an external landmark; it is the keypress action object's own byte length, and it recurs because every keypress object is the same size. Walking `start -> start+head -> ...` chains the action objects in order, and chain length = action count: zoom (count=5) and numkeys (count=1 each) both check out, and on corinthian `((EDDI jumped))` (count=15, including two nested compares) and `Climb` (count=17, if/elseif/else + a nested Integer block + Loop While) both chain to their full counts.

**[SOLID] Fixed 34-member CommandAction layout, identical across zoom and numkeys.** `nmembers=34` holds for every action in both profiles, confirmed by data_start arithmetic (zoom: 928 = 788 + 4 + 34×4) rather than by rediscovering the count per object — rediscovery is unsafe, since a shared/interned heap slot can emit a backward offset, truncate the array early, and silently shift every downstream index.

Member index table (only the slots resolved this round; enum tables follow separately):

| idx | field | confidence |
|-----|-------|------------|
| m[17] | ConditionPairing — index of the next branch-point-or-End | [SOLID], validated with real nesting + a loop on corinthian |
| m[18] | counter, reads 1..10 across conditionals-1's ten blocks, 1 in zoom, 1 for Climb's Loop While | [OPEN] — not a simple global block counter, not nesting depth; candidate ConditionGroup/Ordinal |
| m[19] | left operand — inline token OR pool-local variable NAME (`System_visits`, `ads`, `count`, `c`), same slot both ways | [SOLID] |
| m[20] | ConditionStartOperator — read as the full Text 0–9 enum, correctly, on conditionals-1's ten self-labeling blocks (table already in this doc, above) | [SOLID] on Text; [PARTIAL, sample-backed] on Integer, see below |
| m[24] | ConditionStartValueType — Text=1, Bool=2, Int=3 | [SOLID] on Text/Int; single-sample on Bool |

**[SOLID] ConditionPairing (m[17]) confirmed with real nesting and a loop — this settles the branch-vs-End ambiguity probe-2 command 3 was designed to test.** A Begin/Else-If points to the next branch-point-or-End, not straight through to the block's final End: on corinthian's `jumped`, O9 (outer) → 14 and O10 (inner) → 13, and both closing actions point back (14→9, 13→10); on `Climb`, O1 → 3 (ElseIf), O3 → 8 (Else), O11 (LoopWhile) → 16 (End Loop).

**[SOLID] Pool-referenced left operand and operator confirmed on corinthian — this was the walk's own open extrapolation, and it is now closed.** m[19] reads the pool var name directly (`System_visits`, `ads`, `count`) with no inline token present at all; m[20] reads the operator by member index regardless of whether the left operand is inline or pool-referenced. Gotcha, carried over: m[20] is a shared slot — on Set-integer actions it holds the set-op code (4=converted, 1=minus), not a comparison operator, so any condition read must gate on m[24] ∈ {1,2,3}.

**[SOLID] ConditionStartValueType (m[24]) cracked — probe-2 command 2's target.** Text=1, Bool=2, Int=3, read directly off the object: conditionals-1's ten Text blocks all read m[24]=1, constant — which is exactly what separates m[24] from m[18] (see reconciliation below). An inline non-Text token carries its declared type rather than collapsing to Text: corinthian's `((EDDI entered signal source))` inline `{INT:...}` compare reads m[24]=3, not 1. [PARTIAL, sample-backed] Bool=2 rests on a single sample (`[ads]`) — thinner than Text or Int. Decimal and Small-Int codes are still unknown; no sample yet.

**[PARTIAL, sample-backed] Integer operator enum, incomplete:**

| code | operator | evidence |
|------|----------|----------|
| 0 | Equals | corinthian, `[c] Equals 0` |
| 1 | Does Not Equal | corinthian, `[throt] Does Not Equal -1` |
| 2 | Is Less Than | corinthian, CSV-matched |
| 4 | Is Greater Than | corinthian, CSV-matched |
| 7 | Has Not Been Set | corinthian, CSV-matched |

Corinthian is now exhausted — it contains only these five Integer operators (codes 0, 1, 2, 4, 7); codes 3, 5, 6 and Has Been Set / ≤ / ≥ never occur in it. Still missing therefore: Has Been Set, Is Less Than or Equal To, Is Greater Than or Equal To. [INFERRED] the observed spacing (Is Less Than=2, Is Greater Than=4) fits VoiceAttack's Integer dropdown order and predicts 3 = Is Less Than or Equal To, 5 = Is Greater Than or Equal To, 6 = Has Been Set — but only the probe-2 command-1 sweep + dropdown screenshot confirms the gaps. Confirmed NOT the same enum as Text above: Has Not Been Set is code 7 for Integer vs code 9 for Text.

**[OPEN] m[18] — the real "token−4" counter, not resolved this round.** Reads 1..10 across conditionals-1's ten self-labeling blocks, 1 in both of zoom's branches, and 1 for Climb's Loop While rather than a fresh number — so it tracks neither a simple global block count nor nesting depth. Candidate ConditionGroup or Ordinal; unresolved.

**Reconciliation with the flat-scan model above.** The flat rules already recorded in this doc — operator at `token_end`, `ConditionPairing` at `token−8` — remain correct for inline-token conditions; the object walk does not contradict them, it explains them: `token_end` is member m[20], `token−8` is member m[17], and the token itself sits at member m[19] (`token_end` falls right after m[19]'s data). The object walk supersedes the flat scan by giving fixed member indices that ALSO resolve pool-referenced conditions — no inline token, so no `token` anchor to count offsets from — which the flat scan cannot reach at all. Correction to this doc's own open item: the flat "token−4 counter" is member m[18], and `ConditionStartValueType` is the separate member m[24]. Conditionals-1 settled this: m[24] reads 1, constant, for all ten Text blocks, while m[18] reads 1..10 across those same ten blocks.

**What this closes, pre-vap, against `Conditionals_Probe_2_Spec.md`'s targets:**
- Command 1's local-var operator-position target — closed: m[19]/m[20] read pool-referenced operands and operators by member index, confirmed on corinthian.
- Command 1's Integer enum target — not closed: 5 codes now known (0, 1, 2, 4, 7) and corinthian exhausted; still needs Has Been Set, ≤, ≥ (the 3/5/6 gaps, predicted but unconfirmed).
- Command 2's value-type-field target — closed for Text/Bool/Int; Decimal and Small-Int codes still unknown.
- Command 3's ConditionPairing (branch-vs-End) target — closed: the "next branch-point-or-End" model is confirmed against the rival "always points to the block's final End" model, using real nesting (`jumped`) and a loop (`Climb`).
- Command 3's IndentLevel and Begin/ElseIf/Else/End subtype targets — not closed: no candidate member identified this round (m[2], per the walk's own working notes, remains an unresolved pointer/length-shaped read, not yet a clean subtype code).

Net effect for probe 2: command-2's value-type target and command-3's pairing question are largely answered pre-vap; command-1 reduces to completing the Integer operator enum plus the Decimal/Boolean/Small-Int value-type codes — more samples are still needed for those, but not a VoiceAttack export/XML matched pair, since the object walk already reaches them on data in hand.

---

## Session update — Integer operator enum confirmed (2026-07-07)

**[SOLID] The full 8-operator Integer enum is confirmed — closing the [INFERRED] gaps (3/5/6) left open in the object-walk update above.** Ground truth: an `integer compare` command authored into `conditionals-Profile.vap` this round (alongside the existing text sweep), sweeping all eight Integer-compare operators in dropdown order against `[i]` (a pool-referenced local var), read via the object walk (operator = member m[20]). All eight blocks read m[24]=3 (Int) and m[19]=`[i]`; m[20] returns the 0-indexed dropdown position exactly:

| code | operator |
|------|----------|
| 0 | Equals |
| 1 | Does Not Equal |
| 2 | Is Less Than |
| 3 | Is Less Than Or Equals |
| 4 | Is Greater Than |
| 5 | Is Greater Than Or Equals |
| 6 | Has Been Set |
| 7 | Has Not Been Set |

This matches the prior update's [INFERRED] predictions exactly (3 = Is Less Than Or Equals, 5 = Is Greater Than Or Equals, 6 = Has Been Set), and is a third independent object-walk confirmation (after zoom/numkeys and corinthian) — on a freshly authored profile, with the pool-referenced operand/operator read holding again. Same coding scheme as Text (0-indexed dropdown position); the enum itself differs (Has Not Been Set is 7 for Integer vs 9 for Text).

**Probe-2 status:** command-1's Integer operator enum is now fully closed pre-`conditionals2`. Still open for probe 2: the Decimal / Boolean / Small-Int value-type codes (m[24]) and their operator enums; IndentLevel; and the Begin/Else If/Else/End subtype (m[2]).

---

## Session update — value-type enum complete + Boolean/Decimal/Small-Int operators (2026-07-08)

Ground truth: three more sweeps authored into `conditionals-Profile.vap` — `boolean` ([boo] vs False), `nested + decimal` ([pie] vs 5.43, with two nested blocks), `small int` ([smal] vs 0) — each sweeping one compare type's dropdown in order, read via the object walk (value-type m[24], operator m[20]).

**[SOLID] ConditionStartValueType (m[24]) — complete, all five types. This fully closes probe-2 command 2's target.** A cross-type member dump (one compare per type) confirms m[24] is the only member that separates all five:

| code | value-type |
|------|-----------|
| 0 | Small Integer |
| 1 | Text |
| 2 | Boolean |
| 3 | Integer |
| 4 | Decimal |

Caveat: Small Integer reads 0, the same value non-condition actions carry (Set/Press/Pause), so 0-as-Small-Int and 0-as-unset are indistinguishable by this field alone — identify a Small-Int compare structurally (Begin marker m[2]=19 + operand m[19] + operator m[20]), never by m[24].

**[SOLID] Operator enum (m[20]) = 0-indexed position in that type's own dropdown.** The generative point: Has [Not] Been Set lands at a different code per type purely because the dropdowns differ in length.

| value-type | operators (code = order) |
|-----------|--------------------------|
| Boolean (4) | 0 Equals · 1 Does Not Equal · 2 Has Been Set · 3 Has Not Been Set |
| Integer / Decimal / Small Integer (8) | 0 Equals · 1 Does Not Equal · 2 Is Less Than · 3 Is Less Than Or Equals · 4 Is Greater Than · 5 Is Greater Than Or Equals · 6 Has Been Set · 7 Has Not Been Set |
| Text (10) | as in this doc's existing table (0–9) |

So Has Not Been Set = 3 (Bool) / 7 (Int, Decimal, Small Int) / 9 (Text) — all the same field, just the positional index. Decimal and Small Integer share Integer's exact 8-operator order.

**[INFERRED] m[18] is a 1-based block-open ordinal — a candidate for ConditionGroup, but NOT confirmed as such.** It increments once per Begin-Condition in serialized order (Else If inherits its Begin's number; nested Begins take the next number): decimal reads 1,2,3,3,4,5,6,7,8; conditionals-1 1..10; zoom 1,1; boolean 1,1,1,1. That behavior is fully explained as an ordinal — no ConditionGroup (AND/OR grouping) semantics have actually been observed. This supersedes the earlier update's tentative reading of m[18] and does NOT rename the doc's open "token−4"/counter item to ConditionGroup yet; the distinguishing test is a compound condition (below).

**[SOLID observation] Compound conditions expose a walker gap — and locate where the extra sub-compares live.** `(return to main screen)`'s opening `Begin Condition : [gui focus] Equals 'none' OR [gui focus] Equals 'station services'` is a single action object, inflated (head=579 vs ~340 for a simple compare). The flat 34-member read surfaces only the FIRST sub-compare; the second literal ('station services') sits inside the object at member m[31]'s data region (m[31] spans object-offsets 343→571, scalar reads 2 — a candidate sub-condition count). So additional AND/OR sub-compares are packed into a member the current single-compare reader does not descend into: the walk undercounts sub-conditions on compound blocks, and settling the ConditionGroup question requires decoding that nested region.

**[SOLID] IndentLevel is not present in the 34-slot member table.** In the nested decimal command (depths 0/1/2), no member reads the 0/1/2 depth pattern — a depth-0 Begin and a depth-1 Begin differ only in GUID / pairing / m[18] / operator, and the depth-2 keypress has no member reading 2. Nesting is reconstructable from ConditionPairing (m[17]) plus the m[18] ordinal, so an IndentLevel value can be derived even if it is not stored here; whether VA stores it elsewhere or recomputes it at load is not shown by the bytes.

**[SOLID] m[2] = ActionType (resolved same day).** m[2] is a per-action-type integer, consistent across jumped / climb / boolean: 0 PressKey · 2 Pause · 16 Execute Command · 17 Kill Command · 19 Begin Condition · 20 End Condition · 23 Write/Say · 29 Else · 30 Begin Loop While · 31 End Loop · 36 Set Boolean · 37 Set Integer · 63 Else If. Codes 19/63/30 carry a compare; no non-compare action reads any of them, so m[2] is the reliable condition detector (m[24] is NOT — it reads 0 for both Small-Integer compares and every non-condition action, filtering nothing). This corrects the earlier reading of "`01 00 00 00` = ActionType 1 = PressKey" above: that `01` is the m[5] keypress marker, and PressKey's ActionType is 0. Enum not exhaustive (Launch/Mouse/SetText etc. unsampled).

**Probe-2 status after this round:** command 2 (value-type field + all five codes) is closed pre-`conditionals2`; command 3's ConditionPairing branch-vs-End model is closed, its IndentLevel is reframed (not a stored member; derivable from pairing + ordinal), and its subtype (m[2]) stays open. Remaining genuinely-open items: whether m[18] is ConditionGroup (needs the compound decode), the subtype code (m[2]), and compound-condition handling in the walker.

(Correction 2026-07-09: the two "m[2] stays open" mentions above are stale — they contradict the [SOLID] resolution two paragraphs up (m[2]=ActionType, Begin/ElseIf/Else/End = 19/63/29/20). m[2] is closed; see spec §9.1. The m[18]-as-ConditionGroup question was subsequently de-scoped to decode-only (Probe A dropped, 2026-07-08), and compound handling is a V2 requirement — spec §8.5/§8.6.)
