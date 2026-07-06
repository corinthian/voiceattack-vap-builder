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

## What the command is  [SOLID]

```
Command "zoom [out; in]"          category: camera
  ├─ if  {LASTSPOKENCMD} ~ "out"  →  PressKey F (VK 0x46), duration 1.5s
  └─ if  {LASTSPOKENCMD} ~ "in"   →  PressKey R (VK 0x52), duration 1.5s
```

Two conditional branches, each comparing the token `{LASTSPOKENCMD}` against a string
literal, then executing one keypress. The keypress `F` (byte 1315) lies between the two
`{LASTSPOKENCMD}` tokens (1023 and 1700), so it provably belongs to the "out" branch;
`R` follows the second token, so it belongs to the "in" branch. The comparison direction
(which operand is left/right) and the exact match semantics ("contains" vs "equals") are
**[INFERRED]**, not proven.

## Command header  [SOLID]

| Offset | Bytes | Meaning |
|--------|-------|---------|
| 750 | `7e38f126-2a11-4418-b0e3-1e064917e1d6` | command GUID (Id) |
| 766 | `0e 00 00 00` | phrase length = 14 |
| 770 | `zoom [out; in]` | phrase (UTF-8) |
| 784 | `05 00 00 00` | property count = 5 |
| 788 | `347, 32, 140, 156, 160` | property offset table (5 × uint32) |

Note: the uint32 series does **not** stop after 5 entries — an ascending run
(`32,140,156,160,168,176,180,…`) continues to ~912, followed by a 16-byte GUID at 928.
So "count = 5" is not "5 raw byte offsets into the action data." See *Object envelope*.

## Condition operand encoding — "out" branch  [mixed]

Bytes 968–1042:

| Offset | Bytes | Meaning | Confidence |
|--------|-------|---------|------------|
| 968 | `ff ff ff ff` | prior-field terminator | SOLID |
| 972 | `03 00 00 00` + `out` | length-prefixed literal operand | SOLID |
| 979–1014 | `ff…` / `00…` runs | empty/optional members, null-padded | SOLID |
| 1015 | `02 00 00 00` | operator / comparison-type code | INFERRED |
| 1019 | `01 00 00 00` | operand-kind code | INFERRED |
| 1023 | `0f 00 00 00` + `{LASTSPOKENCMD}` | length-prefixed token operand | SOLID |
| 1042 | `06 00 00 00` | token-type code (not a string length — followed by zeros) | INFERRED |

The "in" branch repeats this exact shape (literal `in` @1650, token `{LASTSPOKENCMD}`
@1700), confirming a fixed per-condition layout.

## Keypress action record  [SOLID]

Verified across the zoom branches and all seven numkeys commands:

```
[ double Duration @ i-12 ] … 00 00 00 00 | 01 00 00 00 | VK (uint16) …
```

- The 8-byte IEEE-754 double **12 bytes before** the `00000000 01000000` marker is the
  key-hold Duration: **1.5** for both zoom keys, **0.5** for every numkeys key.
- `VK` is a uint16 at marker+8. F = 0x46, R = 0x52.

This duration doubles as a validity check: a real keypress has a small positive double in
that slot; padding/marker false-hits do not (see next section).

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

**Finding 4 [INFERRED] — candidate type tag.** The constant uint32 `0xF1886E09`
(bytes `09 6e 88 f1`) appears in the action region of *both* numkeys and zoom, near the
keypress data. It is a plausible class/type identifier, but its role is unconfirmed.

### Still open after triangulation
- The exact base the relative offset (331) is measured from.
- Confirming the object **type tag** (candidate: `0xF1886E09`) and enumerating type codes
  (PressKey vs BeginCondition vs token-compare).
- The ascending 2-byte table in the record tail (rel ~589+), likely a container-level
  offset table rather than keypress payload.

These remaining items are what a *generic* conditional decoder (code) would need. The
semantic decode and the record layout above are sufficient to explain "how it decodes."

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
