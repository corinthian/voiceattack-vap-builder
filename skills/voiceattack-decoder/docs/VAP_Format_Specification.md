# VoiceAttack `.vap` Format — Specification (Draft for External Review)

Status: DRAFT, reverse-engineered. Version 0.1, 2026-07-08. Author: analysis session over the profiles listed in §2. This document consolidates and, where noted, CORRECTS the three prior working notes in this folder — `VAP_FORMAT.md`, `VAP_Binary_Schema_Analysis.md`, and `VAP_Conditional_Command_Analysis.md` — into one reviewable specification. It is not derived from VoiceAttack source; every non-trivial claim cites the bytes or the prior-doc line it rests on.

## 1. Confidence legend

Each claim is tagged. A reviewer should treat only [SOLID] as safe to implement against without re-verification.

- **[SOLID]** — read directly from ≥2 independent profiles, or cross-checked against VoiceAttack's own UI / CSV export.
- **[INFERRED]** — consistent with the bytes and with a plausible model, but not independently proven.
- **[OPEN]** — location or meaning not established.

Byte offsets are positions in the **decompressed** buffer for the named profile. "rel" offsets are relative to an object's own array start (see §6). Prior-doc citations use `File.md:Lnn`.

## 2. Evidence base

Reference profiles (all decode identically; VoiceAttack version string `2.1.8` appears in each):

| Profile | Decompressed size | Role in this spec |
|---------|-------------------|-------------------|
| `zoom-if-else.vap` | 3111 B | Primary landmark set; if/else-if/end ground truth |
| `numkeys-Profile.vap` | 10289 B | 5 single-key commands; object-template triangulation |
| `conditionals-Profile.vap` | 40744 B | Authored operator/type sweeps (Text, Integer, Boolean, Decimal, Small-Int) |
| `corinthian-4-Profile.vap` | 545818 B | 479 real commands; pool-referenced + compound + loop conditions |
| `base profile-Profile.vap` | 164274 B | Profile-header sample (per `VAP_Binary_Schema_Analysis.md:L41-43`) |

Ground-truth oracles: VoiceAttack "Edit a Command" UI screenshots; CSV exports (`corinthian-4-Profile.csv`, `Cities Skylines II-Profile.csv`, `conditionals-Profile.csv`); Edvard `defaultcommand.xml` (the XML field set, §5).

## 3. Container layer

A `.vap` file is EITHER raw-deflate-compressed binary OR uncompressed XML; VoiceAttack imports both. [SOLID — `VAP_FORMAT.md:L7-12`, `VAP_Binary_Schema_Analysis.md:L9-12`]

- Binary: `zlib.decompress(data, -15)` — raw deflate, no zlib header (`wbits = -15`). [SOLID]
- XML: a `<Profile>` document (§5) accepted verbatim. Detect by leading `<?xml` / `<Profile`.

The rest of this spec describes the decompressed BINARY. The XML form (§5) is the logical model the binary serializes.

## 4. Primitive data types

[SOLID unless noted — `VAP_FORMAT.md:L42-77`]

- **u32** — little-endian unsigned 32-bit. Also the width of every member-offset-table entry (§6).
- **u16** — little-endian; used for Virtual Key Codes (§9.2).
- **double** — IEEE-754 little-endian 8-byte; used for `Duration` and Decimal compare values.
- **GUID (16 B)** — .NET mixed-endian: u32 LE, u16 LE, u16 LE, then 8 raw bytes big-endian. Example: `zoom` command Id at @750 is `26 f1 38 7e 11 2a 18 44 b0 e3 1e 06 49 17 e1 d6` → `7e38f126-2a11-4418-b0e3-1e064917e1d6`. [SOLID]
- **Length-prefixed string** — `[u32 length][UTF-8 bytes]`. Used for phrases, category, string operands, variable names.
- **Sentinels** — `0xFFFFFFFF` marks an absent/optional field; `0x00000000` marks empty/default. Both alias real values in a flat scan (§11).

## 5. Logical model (XML) — the field set the binary encodes

Source of truth for field names: Edvard `defaultcommand.xml`, VoiceAttack's own `CommandAction` serialization. [SOLID — `VAP_Conditional_Command_Analysis.md:L155-162`]

```
Profile
  Id (GUID), Name (string)
  Commands: Command[]
    Command
      Id (GUID), CommandString (phrase), Category (string)
      ActionSequence: CommandAction[]
```

**Conditions are not a separate action type — they are FIELDS on each `CommandAction`.** [SOLID — `VAP_Conditional_Command_Analysis.md:L157-162`] The full `CommandAction` field set: `Ordinal`, `IndentLevel`, `ConditionMet`, `ConditionPairing`, `ConditionGroup`, `ConditionStartOperator`, `ConditionStartValue`, `ConditionStartValueType`, plus `ActionType`, `Duration`, `Delay`, `KeyCodes`, `Context`, `X`, `Y`, `InputMode`, `IsSuffixAction`. The binary stores integer CODES, not names: `corinthian` contains zero occurrences of `PressKey`/`BeginCondition`/etc. as strings. [SOLID — `VAP_Conditional_Command_Analysis.md:L164-167`]

## 6. Binary object model (core of this spec)

The decompressed buffer is a nested tree of serialized objects. Three envelope shapes are established, one per level.

### 6.1 File / Profile header  [INFERRED — from prior docs, not re-verified this session]

Per `VAP_FORMAT.md:L22-33` and `VAP_Binary_Schema_Analysis.md:L16-27`:

```
@0x0000  u32  total decompressed size
@0x0004  u32  0x59 (89)         — meaning uncertain: item count OR offset to first data
@0x0008  u32… offset table / pointer to profile metadata
@0x0170  GUID profile Id        — VERIFIED in zoom (@368 = 0x170) [SOLID]
@0x0180  u32  profile name length
@0x0184  string profile name
```

Only the profile-Id position @0x170 is re-verified this session (zoom "Profile record @368", `VAP_Conditional_Command_Analysis.md:L204`). The @0 / @4 / @8 header and how the command LIST is indexed (offset table vs. chained) remain [OPEN] — see §12.

### 6.2 Command envelope  [SOLID — verified in zoom, numkeys, conditionals, corinthian]

```
[GUID (16 B)]            command Id
[u32 phraseLen]
[UTF-8 phrase]           CommandString, e.g. "zoom [out; in]"
[u32 actionCount]        number of CommandAction objects that follow
[action object 0][action object 1]…[action object N-1]   (§6.3, chained)
… trailing: Category string, etc.
```

zoom evidence: GUID @750, phraseLen @766 (=14), phrase @770 `zoom [out; in]`, actionCount @784 (=5), first action object @788. [SOLID]

**Correction to prior docs.** `VAP_FORMAT.md:L30-33` and `VAP_Binary_Schema_Analysis.md:L32-35` read the u32 after `actionCount` as "number of offset entries" followed by a "command-property offset table." That is a MISREAD: the array at @788 is the FIRST ACTION OBJECT'S member-offset table (§6.3), and the u32 at @784 is the action COUNT (zoom=5, and exactly 5 action objects chain from @788; numkeys single-key commands read count=1). The "5" cannot be an offset-entry count because the array holds 34 entries, not 5. [SOLID]

`actionCount` = number of actions was cross-checked earlier: numkeys single-key = 1, `num 0-9` = 10 keypresses = 10. [SOLID — `VAP_Conditional_Command_Analysis.md:L49-54`]

### 6.3 `CommandAction` object envelope  [SOLID — the central result]

Every action is serialized as:

```
[u32 head][u32 member[0]][u32 member[1]]…[u32 member[33]]   ← offset array (35 u32 total)
[member-data heap]
```

Rules, all verified:

1. **Member count is FIXED at 34.** Same `nmembers = 34` in every action of zoom and numkeys, and across all five compare types in conditionals. Verified by arithmetic, not by scanning: zoom action[0] data heap starts at 928 = 788 + 4 (head) + 34×4. [SOLID] A decoder MUST read exactly 34 and MUST NOT infer the count by "read while ascending" — an interned/shared heap slot can emit a backward offset and silently truncate the array. [SOLID — observed risk]
2. **Base = the array's own start.** `member[i]`'s data is at `arrayStart + member[i]`. zoom action[0] (array @788): `member[20]` = 254 → @1042 = the operator; `member[19]` = 235 → @1023 = the token operand; `member[7]` = 184 → @972 = the literal `out`. [SOLID] This answers the prior docs' long-standing "what base is offset 331 measured from" [OPEN] (`VAP_Conditional_Command_Analysis.md:L127`): it is measured from the object's own array start.
3. **`head` = the object's total byte length = pointer to the next sibling.** zoom action[0] head = 347 → next array @ 788+347 = 1135, which is exactly where action[1]'s array begins. Walking `start → start + head` chains the actions; chain length = `actionCount`. zoom: 5 objects then the chain runs into the category tail. numkeys: every single-key action object has head = 331 (a keypress object is a fixed 331-byte template; this is the "331" the prior docs could not anchor). [SOLID]
4. Member OFFSETS vary per object (the heap shifts with string lengths); the member INDEX is the stable schema position. Read by index, never by absolute byte position. [SOLID]

Chain validated on complex real commands: `corinthian ((EDDI jumped))` actionCount=15 chains to 15 objects including two nested compares; `Climb` (`[inch;] Climb [1..4;] [continuous;]`, @106380) actionCount=17 chains through if/else-if/else + a nested Integer block + a Loop While. [SOLID]

### 6.4 `CommandAction` member index map

Slots identified so far (of 34). Unlisted slots read 0 or `0xFFFFFFFF` (empty/optional) in the samples seen.

| idx | field | value/meaning | confidence |
|-----|-------|---------------|------------|
| m[1] | nested sub-object Id | pointer to a 16-B GUID in the heap (reads as garbage u32) | [INFERRED] |
| m[2] | **`ActionType`** | per-action-type code (full enum §9.1); 19 Begin / 63 Else If / 30 Begin Loop While carry a compare | [SOLID] (multi-profile) |
| m[5] | keypress marker | 1 for PressKey actions (all numkeys + zoom keypresses), else 0 | [SOLID] |
| m[7] | `ConditionStartValue` | right operand; length-prefixed string for Text (`out`=3, `in`=2); `0xFFFFFFFF` if none | [SOLID] |
| m[17] | `ConditionPairing` | 0-based index of the paired action (§8.4) | [SOLID] |
| m[18] | block-open ordinal | candidate `ConditionGroup` (§8.5) | [INFERRED] |
| m[19] | left operand (evaluated value) | inline token (`{LASTSPOKENCMD}`, `{TXT:bbq}`) OR pool-local variable name (`System_visits`, `count`, `[i]`) — same slot both ways | [SOLID] |
| m[20] | `ConditionStartOperator` | per-type 0-indexed dropdown position (§8.2) | [SOLID] |
| m[24] | `ConditionStartValueType` | 0=Small Int, 1=Text, 2=Bool, 3=Int, 4=Decimal (§8.1) | [SOLID] |
| m[27], m[28] | structural separator | constant `0xF1886E09` (§10) | [SOLID] |
| m[31] | compound sub-condition list | on compound blocks, holds the extra AND/OR sub-compares (§8.6) | [SOLID observation] |

Gotcha: m[20] is a SHARED slot — on a `Set integer` action it reads the set-operation code (4 = "to converted value", 1 = "minus"), not an operator. **Gate operator reads on the ActionType, m[2] (§9.1): treat an action as a compare only when m[2] ∈ {19 Begin, 63 Else If, 30 Begin Loop While}.** Do NOT gate on m[24] — Small-Integer conditions AND every non-condition action read m[24]=0, so it filters nothing; m[24] is DESCRIPTIVE (the value-type), not a condition flag. Across the jumped / climb / boolean walks, no non-compare action reads m[2] ∈ {19,63,30}. [SOLID]

## 8. Condition encoding

### 8.1 `ConditionStartValueType` — m[24]  [SOLID, complete]

Authored one-compare-per-type sweep in `conditionals-Profile.vap`; a cross-type member dump shows m[24] is the ONLY member separating all five types:

| code | value-type | evidence (command @offset) |
|------|-----------|----------------------------|
| 0 | Small Integer | `small int` @34124 |
| 1 | Text | `New Command` @23108, `zoom` |
| 2 | Boolean | `boolean` @764 |
| 3 | Integer | `integer compare` @4677 |
| 4 | Decimal | `nested + decimal ` @13551 |

**Caveat.** Small Integer reads 0, identical to the value non-condition actions carry; 0-as-Small-Int and 0-as-unset are indistinguishable by this field alone. Identify a Small-Int compare structurally (m[2]=19 + operand m[19] + operator m[20]), never by m[24]. [SOLID] An inline non-Text token carries its declared type (corinthian `((EDDI entered signal source))` inline `[{INT:…}]` reads m[24]=3, not 1), so value-type applies to inline tokens as well as pool locals. [SOLID]

### 8.2 `ConditionStartOperator` — m[20]  [SOLID]

**The operator code is the 0-indexed position of the operator in THAT value-type's dropdown.** Because the dropdowns differ in length, the same operator has different codes per type — e.g. "Has Not Been Set" is 3 (Boolean) / 7 (Integer, Decimal, Small Int) / 9 (Text).

| value-type | operators (index = code) | evidence |
|-----------|--------------------------|----------|
| Text (10) | 0 Equals · 1 Does Not Equal · 2 Starts With · 3 Does Not Start With · 4 Ends With · 5 Does Not End With · 6 Contains · 7 Does Not Contain · 8 Has Been Set · 9 Has Not Been Set | `New Command` self-labeling sweep; `VAP_Conditional_Command_Analysis.md:L248-263` |
| Integer / Decimal / Small Integer (8) | 0 Equals · 1 Does Not Equal · 2 Is Less Than · 3 Is Less Than Or Equals · 4 Is Greater Than · 5 Is Greater Than Or Equals · 6 Has Been Set · 7 Has Not Been Set | `integer compare` / `nested + decimal ` / `small int` sweeps; corinthian CSV-matched (`[c] Equals 0`, `[throt] Does Not Equal -1`, `[System_visits] Is Less Than 2`, `[count] Is Greater Than 0`, `Has Not Been Set`) |
| Boolean (4) | 0 Equals · 1 Does Not Equal · 2 Has Been Set · 3 Has Not Been Set | `boolean` @764 sweep |

Cross-profile anchor: zoom's two `Contains` branches read m[20]=6 at @1042 / @1719; corinthian's single `Does Not Equal` (Text) reads 1 — exact CSV correlation. [SOLID — `VAP_Conditional_Command_Analysis.md:L246`]

### 8.3 Operands and value encodings

- **Left operand — m[19].** The evaluated side. Stored as a length-prefixed string that is either an inline token (`{LASTSPOKENCMD}`, `{TXT:name}`, `{INT:name}`) or a pool-local variable name (`i`, `count`, `throt`). [SOLID]
- **Right operand / `ConditionStartValue` — m[7]** and value encoding by type:
  - Text → length-prefixed string (m[7]). [SOLID]
  - Integer / Small Integer → raw integer; corinthian `throttle` family stores the compare value as a u32 at a fixed command-relative offset (+580 in that family). [SOLID — `VAP_Conditional_Command_Analysis.md:L230`]
  - Decimal → IEEE-754 double (matches the `Duration` encoding; not byte-pinned this session). [INFERRED]
  - Boolean → the `True`/`False` value; for `{BOOL:}` token compares VoiceAttack stores a quoted `'True'`/`'False'` string operand, so a Boolean-typed compare likely stores a bool byte or the same quoted form. [INFERRED / OPEN]
- **Local-variable declaration pool.** Pool-local variables live in a declaration pool and are referenced by a `[01 00 00 00][u32 len][name][01 00 00 00]` wrapper; the pool record and the condition record share this wrapper, so a naive name search lands on the pool, not the compare. [SOLID — `VAP_Conditional_Command_Analysis.md:L232`] The object walk sidesteps this: m[19] resolves the operand from within the action object regardless.

### 8.4 `ConditionPairing` — m[17]  [SOLID]

The 0-based index (within the command's action sequence) of the action that closes this block's current segment, and the reverse link on closing actions.

- A `Begin`/`Else If` points to the NEXT branch point or the block's `End` — NOT straight to the final `End`. zoom: Begin @action0 → 2 (its Else If), Else If @action2 → 4 (the End). climb: Begin → 3 (Else If), Else If → 8 (Else). [SOLID]
- With real nesting (corinthian `((EDDI jumped))`): outer Begin (action 9) → 14 (outer End), inner Begin (action 10) → 13 (inner End); the End records point back to their Begins (14→9, 13→10). [SOLID]

This settles the "branch vs. final End" question the conditionals-2 probe was designed to test: the model is "next branch point," confirmed against the rival "always the final End."

### 8.5 m[18] — block-open ordinal / candidate `ConditionGroup`  [INFERRED]

A 1-based counter that increments once per `Begin`-condition in serialized order; `Else If` inherits its `Begin`'s number; nested `Begin`s take the next number. Evidence: `nested + decimal` reads 1,2,3,3,4,5,6,7,8; `New Command` reads 1..10; zoom 1,1; `boolean` 1,1,1,1. This is fully explained as a block-open ORDINAL; no `ConditionGroup` (AND/OR grouping) BEHAVIOR has been observed. The distinguishing test is a compound condition (§8.6), not yet decoded. Do not implement this as `ConditionGroup` without that test. [INFERRED] The old "token−4 counter" [OPEN] item is this slot. Edge: corinthian `Climb`'s Loop While reads 1, not a fresh number.

### 8.6 Compound conditions — `(A AND B) OR (C AND D)`  [SOLID observation, partial]

A compound `Begin Condition` is a SINGLE action object holding multiple sub-compares. corinthian `(return to main screen)` opens with `Begin Condition : [gui focus] Equals 'none' OR [gui focus] Equals 'station services'`: one object at @29797, head=579 (inflated vs. ~340 for a simple compare). The flat 34-member read surfaces only the FIRST sub-compare (m[7]=`none`, m[19]=operand, m[20]=0); the second literal `station services` (@30324) lives inside the object in member m[31]'s data region (m[31] spans object-rel 343→571; its scalar reads 2 — candidate sub-condition count). [SOLID observation]

Implication for a decoder: the single-compare member map (§6.4) UNDERCOUNTS sub-conditions on compound blocks. Full support requires recursively parsing m[31]'s packed sub-condition list. This is the same region that must be decoded to resolve whether m[18] is `ConditionGroup` (§8.5). [OPEN — sub-condition list format not yet specified]

### 8.7 `IndentLevel`  [SOLID that it is not in the member table]

In the `nested + decimal` command (nesting depths 0/1/2) no member of the 34-slot table reads the 0/1/2 depth pattern: a depth-0 `Begin` and a depth-1 `Begin` differ only in GUID / m[17] / m[18] / m[20], and the depth-2 keypress has no member reading 2. Nesting is fully reconstructable from `ConditionPairing` (m[17]) plus the m[18] ordinal, so an `IndentLevel` value is DERIVABLE even though it is not stored in this table. Whether VoiceAttack stores it elsewhere or recomputes it at load is not shown by the bytes. [SOLID / the "derives at load" gloss is INFERRED]

## 9. Action encoding

### 9.1 `ActionType` — m[2]  [SOLID for the multi-profile codes]

The ActionType is member m[2] — an integer code per action type (mapped by correlating the walk against the UI/CSV action names). Observed enum:

| code | ActionType | evidence |
|------|-----------|----------|
| 0 | PressKey | numkeys, zoom, climb, boolean — [SOLID] |
| 2 | Pause | jumped, climb — [SOLID] |
| 16 | Execute Command | jumped — [INFERRED] |
| 17 | Kill Command | climb — [INFERRED] |
| 19 | Begin Condition (compare) | jumped, climb, boolean — [SOLID] |
| 20 | End Condition | jumped, climb, boolean — [SOLID] |
| 23 | Write / Say | jumped, climb — [INFERRED] |
| 29 | Else | climb — [INFERRED] |
| 30 | Begin Loop While (compare) | climb — [INFERRED] |
| 31 | End Loop | climb — [INFERRED] |
| 36 | Set Boolean | boolean — [INFERRED] |
| 37 | Set Integer | jumped, climb — [SOLID] |
| 63 | Else If (compare) | climb, boolean — [SOLID] |

Codes 19 / 63 / 30 carry a compare (read operator m[20], type m[24], operands); 20 / 29 / 31 are block-structure actions with no operand. This SUPERSEDES the prior note that "`01 00 00 00` = ActionType 1 = PressKey" (`VAP_Conditional_Command_Analysis.md:L167`): that `01` is the m[5] keypress marker; the ActionType lives in m[2] and PressKey's code is 0. [SOLID] The enum is not exhaustive — Launch, MouseAction, Say-vs-Write, SetText, SetClipboard codes are not yet sampled.

### 9.2 Keypress record  [SOLID — `VAP_Conditional_Command_Analysis.md:L73-84`]

Inside a keypress action object's heap:

```
[ double Duration @ marker-12 ] … 00 00 00 00 | 01 00 00 00 (marker) | VK (u16) @ marker+8 …
```

- `Duration` = IEEE-754 double 12 bytes before the `00000000 01000000` marker (zoom keys = 1.5 s; numkeys = 0.5 s). Doubles as a validity check with a floor `0.001 ≤ d ≤ 60` (corinthian phantom slots hold positive denormals ~1e-304). [SOLID]
- `VK` = u16 at marker+8 (F = 0x46, R = 0x52). numkeys template: VK at command-rel 209. [SOLID]
- KeyDown / KeyUp / KeyToggle share the SAME marker with `Duration` exactly 0.0; down/up/toggle are not distinguishable from the flat record. [SOLID — `VAP_Conditional_Command_Analysis.md:L233`] The prior "56-byte key action" template (`VAP_FORMAT.md:L79-91`) is the recognizable core of this heap region, not a standalone record.

### 9.3 Mouse actions  [SOLID — `VAP_FORMAT.md:L130-172`]

Context code is a length-prefixed string `{button}{action}` (e.g. `LC`, `RDC`, `SF`). Scroll-click count is an IEEE-754 double at offset −20 from the context-code length prefix. In XML the scroll count is the `<Duration>` field.

### 9.4 Other actions

`Launch` (executable path, `*` prefix = window-title match), `Say`, `Pause` (Duration), `ExecuteCommand`, `SetClipboard`, `MouseAction` per §5 / `VAP_Binary_Schema_Analysis.md:L120-132`. Their binary member layouts are [OPEN] beyond the shared envelope.

## 10. Structural constants

- **`0xF1886E09`** (bytes `09 6e 88 f1`) — a generic separator that recurs throughout the action region next to every kind of field (members m[27]/m[28]); it is NOT a per-type tag. [SOLID — `VAP_Conditional_Command_Analysis.md:L149-153`]
- **Three GUIDs per command** — each command carries three unique object Ids (command, plus two nested sub-object Ids), each occurring once; confirms the recursive envelope. [SOLID — `VAP_Conditional_Command_Analysis.md:L144-147`]

## 11. Decoding hazards (why a flat scan fails)

All are byproducts of pattern-scanning a flat byte range instead of walking the object tree. [SOLID — `VAP_Conditional_Command_Analysis.md:L86-100`]

1. **Aliased `'F'`/`'R'` label strings** — the keypress `01 00 00 00` reads as a length-1 string whose "content" is the next byte, the VK itself. One physical byte, two readings.
2. **Phantom keypresses** — VK=0x00 inside condition padding and VK=0xFFFF at the `FF`-run terminator fire a flat keypress matcher; their Duration slots are 0.0 / NaN. Filter with the Duration floor (§9.2).
3. **`Equals` = 0 and Small Integer type = 0** — both alias zero padding; a flat scan cannot tell an `Equals`/`Small-Int` condition from a Say-text token or padding. Only the object walk is reliable.
4. **Pool var-ref vs. compare** — the shared `[01][len][name][01]` wrapper (§8.3) means a global name search lands on the declaration pool, not the compare.

## 12. Confidence summary & open questions

Closed [SOLID]: container/compression; primitives incl. GUID endianness; command envelope (§6.2) and the action-object envelope (§6.3) incl. base and chaining; the identified member slots incl. `ActionType` m[2] (13 codes); `ConditionStartValueType` (all 5 codes); `ConditionStartOperator` (all four dropdown enums, positional coding); `ConditionPairing` semantics; operand reading for inline AND pool-referenced conditions; keypress record; the flat-scan hazards.

Open [OPEN] / [INFERRED], recommended review targets:
1. File/Profile header @0..@0x170 and how the command LIST is indexed (offset table vs. chained) — §6.1, not re-verified this session.
2. Compound sub-condition list format inside m[31] — §8.6 — and, with it, whether m[18] is `ConditionGroup` — §8.5.
3. `ActionType` enum COMPLETENESS — m[2] is the field (§9.1) with 13 codes mapped; Launch / MouseAction / Say-vs-Write / SetText / SetClipboard codes not yet sampled.
4. Decimal and Boolean `ConditionStartValue` encodings — §8.3.
5. The remaining ~24 unmapped member slots.

## 13. Reference decoder algorithm (recommended)

Do NOT flat-scan. Walk the tree:

```
buf = raw_deflate_decompress(file)                     # zlib -15
profile = read_profile_header(buf)                     # §6.1 (partly open)
for each command:                                       # §6.2
    read GUID, phraseLen, phrase, actionCount
    arr = position after actionCount
    for k in range(actionCount):                        # §6.3
        head    = u32(arr)
        members = [u32(arr + 4 + 4*i) for i in 0..33]   # FIXED 34
        heap    = arr + 4 + 34*4
        # resolve fields by index: actiontype=members[2], operator=members[20],
        # type=members[24], pairing=members[17], left=members[19], value=members[7] …
        if members[2] in {19, 63, 30}:                  # Begin / Else If / Begin Loop While = a compare
            decode_condition(members)                   # §8; value-type=members[24]; recurse m[31] if compound
        else:
            decode_action(members[2], members)          # §9 — 0=PressKey, 2=Pause, 37=SetInt, …
        arr = arr + head                                # next sibling
```

Landmark self-test (zoom-if-else, decompressed 3111 B): profile Id @368; command Id @750; phrase `zoom [out; in]` @770; actionCount 5 @784; action[0] array @788, head 347 → action[1] @1135; action[0] m[20] → @1042 = 6 (`Contains`), m[19] → @1023 = `{LASTSPOKENCMD}`, m[7] → @972 = `out`. A correct implementation reproduces every one of these. [SOLID]
