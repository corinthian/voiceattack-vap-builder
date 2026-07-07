# VAP Conditional (Variable) Command Structure — Analysis

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
| 1015 | `02 00 00 00` | field A = condition subtype: **2 = Begin** (the "in" branch reads 4 = Else-If) | INFERRED |
| 1019 | `01 00 00 00` | `ConditionStartOperator` = 1 = **Contains** (confirmed in VA UI) | GROUND-TRUTH |
| 1023 | `0f 00 00 00` + `{LASTSPOKENCMD}` | length-prefixed token operand (the left/evaluated value) | SOLID |
| 1042 | `06 00 00 00` | token-type code (not a string length — followed by zeros) | INFERRED |

The "Else If" branch repeats this shape (literal `in` @1650, token `{LASTSPOKENCMD}` @1700)
with **one** difference: field A = **4** instead of **2**. Since branch 1 is `Begin` and
branch 2 is `Else If`, A encodes the condition subtype, while the operator field B stays
**1** (Contains) for both.

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

- **B (immediately before the value) = `ConditionStartOperator`.**  Ground-truth anchored:
  both zoom branches read "contains" and both have **B = 1**, while A differs (2 vs 4). An
  operator shared by both branches must be the *invariant* field — so B is the operator and
  **contains = 1**. Cross-checks: for a *fixed* operand type (`{TXT:…}`) B is not constant
  (1×82, 2×8, 3×1, 5×1), so it cannot be the value *type* — it tracks the comparison. And
  `{BOOL:…}` shows exactly two values, **B = 2 (7×) / 3 (5×)** — the two boolean operators
  (is-true / is-false), not noise. (Review 2026-07-07, CSV cross-check: {BOOL:} conditions serialize as Equals 'True' / Equals 'False' / Does Not Equal 'True'; the ten distinct combos split ~5 semantically-true / ~5 semantically-false — consistent with is-true/is-false for 2/3, inconsistent with an Equals/Does-Not-Equal split, which would be ~9/1.)
  - Named so far: **contains = 1**; boolean operators = **2 / 3** (which is which still
    needs the pair). `equals`, `greater-than`, etc. remain unnamed.
- **A (before B) = condition subtype (Begin / Else-If / …).**  Ground truth: branch 1 is
  `Begin` (A = 2), branch 2 is `Else If` (A = 4) — so A marks the condition-action kind,
  which is why it varies across a fixed operand type. The compare *type* (Text / Boolean /
  Numeric) may be folded into this same code — "Begin **Text** Compare" vs "Begin **Boolean**
  Compare" are distinct action kinds — which would mean value type is not a separate field.
  Unconfirmed; needs a Boolean-condition A value to test.
- **Value-type location is reopened.**  An earlier draft read B as `ConditionStartValueType`
  with Text = 1. The ground-truth "contains" shows that "1" was the *operator*, not the
  type. Where the value type is stored, and its codes, are now unknown.
- **B = 0 is the noise floor.**  [SOLID] A token embedded in `Say` text has zero-padding
  before it, so it reads B = 0 — which is why scanning cannot tell condition operands from
  Say-text tokens. Only an object-tree walk can. Same lesson as the keypress aliasing.

**Operand order** (from zoom): the `A,B` pair precedes the **token** operand specifically.
The *literal* side of the comparison (`out`) has no such prefix — it is `FF`-padded then
`03 00 00 00 "out"` — and the pair sits *between* the literal and the token. So the pair is
a property of the token operand, not of every operand.

## Still open — all gated on one input

Remaining unknowns: the rest of the `ConditionStartOperator` names (`contains = 1` and the
two boolean operators `2/3` are known; `equals`, `greater-than`, … are not, and 2-vs-3
is not yet assigned to is-true/is-false); **where the value type is stored** and its codes
(reopened — "1" turned out to be the operator); the byte position of `IndentLevel` /
`Ordinal` within a `CommandAction`; the object type-code enum; and the member-table base
(rel offset like 331).

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
- **Contains = ConditionStartOperator code 1** — from the **zoom** ground truth only. The corinthian `{LASTSPOKENCMD}`→i4=1 correlation is **confounded** (that token is ~97% Contains, so "1 precedes it" may track the token, not the operator). Do not cite the correlation as proof.
- **The token-adjacency model is dead.** The operator/subtype are NOT at fixed offsets before the operand string. Proof: across corinthian conditions the byte at `token−8` (the zoom "subtype" slot) takes values 2,3,4,5,6,9,15,21 — no Begin=2/ElseIf=4 pattern. Operator/subtype are object members at member-table offsets, not adjacent fields.
- **Near-twin diff works; structure is byte-stable relative to `phrase_end` within a command family.** Diffing `throttle 25/50/75/100` (identical except key + literal) pinpoints, relative to `phrase_end`:
  - **+184 = keypress VK code** — `[112,115,113,114]` = F1,F4,F2,F3 (matches 25/100/50/75).
  - **+580 = ConditionStartValue** (integer literal) — `[1,4,2,3]` = "Does Not Equal 1/4/2/3".
  Everything else identical → the operator ("Does Not Equal", constant across the four) lives in the non-differing bytes.
- **Two operand-storage mechanisms.** Global tokens (`{LASTSPOKENCMD}`, `{TXT:}`, `{BOOL:}`, `{INT:}`) are stored inline in the condition. Local condition vars (`[throt]`, `[i]`, `[count]`, `[System_visits]`) live in a variable **declaration pool** and are referenced; the var-ref wrapper is `[01 00 00 00][len][name][01 00 00 00]`. The pool record and the condition record share this wrapper, so a global name-search lands on the pool, not the compare — a trap (mistook the pool's `01`/`fc ff ff ff` for the compare value).
- **KeyDown/KeyUp records share the PressKey marker (fix-verification finding, 2026-07-07).** "Press down X key" / "Release X key" actions match the same `00 00 00 00 01 00 00 00` marker as PressKey, with the Duration slot **exactly 0.0** (all-zero bytes) instead of a hold time — so the `01` either covers all three key actions or is not the ActionType field. Down vs up vs toggle is not distinguishable from the flat record; needs the object walk. (This is why the decoder's phantom filter accepts d==0.0 with a suffix check rather than requiring a positive duration.)

### Still open (needs the action-graph walk — a research investment)
- Operator codes beyond Contains=1 (Equals, Starts With, Does Not Equal, Is Greater/Less Than, Has Not Been Set, Equals True/False). The cross-operator contrast is ambiguous because the compare value can only be reached reliably by walking the action objects (the var-name anchor hits the pool). 
- ConditionStartValueType, ConditionPairing/Group, IndentLevel, Begin/ElseIf/Else/End subtype codes.
- **The unlock:** dereference the shared command-member offsets (`[32,140,156,160]` constant across zoom `[347,…]` and throttle `[331,…]`) to walk actions in order, read each ActionType, match a known sequence (throttle = PressKey, BeginIntegerCompare, SetSmallInt, EndCondition, SetInteger) to fix the BeginCompare ActionType code, then read operator/type/subtype at consistent object-relative member offsets. This finds ALL conditions (inline and by-ref) across every command. Not attempted this round (higher-cost, previously ambiguous) — fund explicitly.
