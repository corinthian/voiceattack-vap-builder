# VoiceAttack `.vap` Format — Specification

Status: reverse-engineered, consolidated. **Version 0.3, 2026-07-11.** Author: analysis sessions over the profiles in §2. This version folds Probe B (executed 2026-07-11, `VAP_Probe_Specs_A_B.md`) into v0.2: ActionTypes 3 (Launch), 13 (Say), and the SetClipboard correction; ActionTypes 25/26/27 promoted to SOLID; ActionTypes 50/51 labeled; the Set-action value-source-mode and arithmetic-operator model resolved; Set-Boolean's value-vs-order confound broken; mouse click-duration, scroll-click-count, and cursor-Move slots closed. v0.2 (2026-07-09) folded three documents into one authoritative spec: v0.1 (2026-07-08), the independent verification review (`VAP_Format_Specification_Review.md` — 1,601-object walk, nine corrections §2.1–2.9 applied here), and the Phase 0–2 uncertainty closures (`VAP_Uncertainty_Closure_Table.md` — 1,603-object slot census, 12 verdicts). It is not derived from VoiceAttack source; every non-trivial claim cites the bytes or the evidence doc it rests on.

**Precedence.** This document alone is authoritative. The Review, Closure Table, and Probe Specs are folded in and retained as the historical evidence trail; where any document conflicts with this one, this one wins. `VAP_FORMAT.md` and `VAP_Binary_Schema_Analysis.md` are superseded flat-scan-era notes; `VAP_Conditional_Command_Analysis.md` is the session history. v0.1's five refuted claims (Decimal-as-double, m[7]-as-universal-right-operand, m[5]-as-marker, m[27]/m[28]=0xF1886E09, three-GUIDs-per-command) are corrected in place in v0.2. v0.2's "24 = paste dictation" attribution is refuted in this version (§9.1) — "Paste Dictation" does not exist as a VoiceAttack 2 action.

## 1. Confidence legend

Each claim is tagged. Treat only [SOLID] as safe to implement against without re-verification.

- **[SOLID]** — object-walk-verified across every profile that exhibits the feature (closure rule: holds-where-it-appears = CLOSED), or cross-checked against VoiceAttack's own UI / CSV export.
- **[PLAUSIBLE]** — consistent with all observed bytes, one confound not yet eliminated; named as such.
- **[INFERRED]** — consistent with the bytes and a plausible model, but not independently proven.
- **[OPEN]** — location or meaning not established. §12 routes every OPEN item to a probe or parks it.

Byte offsets are positions in the **decompressed** buffer for the named profile. "rel" offsets are relative to an object's own array start (§6.3). **Member slots hold OFFSETS, never values: every field read is `value = deref(arrayStart + m[i])` at the slot's data type (§6.4).** Prior-doc citations use `File.md:Lnn`.

## 2. Evidence base

Reference profiles (all decode identically):

| Profile | Decompressed size | Commands / actions | Role in this spec |
|---------|-------------------|--------------------|-------------------|
| `zoom-if-else.vap` | 3111 B | 1 / 5 | Primary landmark set; if/else-if/end ground truth |
| `numkeys-Profile.vap` | 10289 B | — / 16 | 5 single-key commands; object-template triangulation |
| `conditionals-Profile.vap` | 40744 B | — / 111 | Authored operator/type sweeps (Text, Integer, Boolean, Decimal, Small-Int) |
| `corinthian-4-Profile.vap` | 545818 B | 201 / 1168 | Real-world stress test; pool-referenced + compound + loop conditions |
| `base profile-Profile.vap` | 164274 B | — / 303 | Profile-header sample |
| `Probe B-Profile.vap` | 17888 B | 10 / 32 | Authored-to-spec oracle (Probe B, `VAP_Probe_Specs_A_B.md`, executed 2026-07-11): one command per unsampled action, self-labeling markers, distinct category per command; oracle is construction (Richard hand-built each command to the spec in VoiceAttack 2), cross-checked against `Probe B-Profile.csv` and 4 screenshots (Set-Integer value-source dropdown, mouse-action dropdown, Say volume/rate, Set-Boolean True/False dropdown) |

Census totals: 1,603 action objects across the five v0.2 profiles; every one chains cleanly with m[0]=32 and m[1]=140, zero structural exceptions. [SOLID] (The review's 1,601 / corinthian-1,166 differs by a two-object harness mismatch; the count-driven walk's 1,168 is authoritative — anchored by set-fire=37 and the profile-record command count=201, both reproduced.) Probe B adds 32 more action objects (10 commands, all envelope-clean, m[0]=32/m[1]=140 throughout, zero violations) — census now 1,635 across six profiles. [SOLID]

Ground-truth oracles: VoiceAttack "Edit a Command" UI screenshots; CSV exports (`corinthian-4-Profile.csv`, `Cities Skylines II-Profile.csv`, `conditionals-Profile.csv`); Edvard `defaultcommand.xml` (the XML field set, §5). numkeys and base profile have no CSV — findings unique to them cap at [PLAUSIBLE].

A version string `2.1.8` appears in zoom, conditionals, and corinthian but NOT in numkeys or base profile: the field is optional (newer exports) and must not be used as a format-version anchor. [SOLID]

## 3. Container layer

A `.vap` file is EITHER raw-deflate-compressed binary OR uncompressed XML; VoiceAttack imports both. [SOLID]

- Binary: `zlib.decompress(data, -15)` — raw deflate, no zlib header (`wbits = -15`). All five profiles decompress to exactly the §2 sizes. [SOLID]
- XML: a `<Profile>` document (§5) accepted verbatim. Detect by leading `<?xml` / `<Profile`.

The rest of this spec describes the decompressed BINARY. The XML form (§5) is the logical model the binary serializes.

## 4. Primitive data types

[SOLID unless noted]

- **u32 / i32** — little-endian 32-bit. u32 is the width of every member-offset-table entry (§6.3); i32 is the read for numeric compare operands (m[21] — negative values are real, see §8.3 hazard).
- **u16** — little-endian; Virtual Key Codes (§9.2).
- **double** — IEEE-754 little-endian 8-byte; `Duration` (keypress m[3], Pause m[3]).
- **.NET Decimal (16 B)** — CLR internal layout, field order flags, hi, lo, mid; e.g. 5.43 = flags 0x00020000 (scale 2), lo 543. Used for Decimal compare values and Set-Decimal (m[25]). [SOLID — review §2.1]
- **GUID (16 B)** — .NET mixed-endian: u32 LE, u16 LE, u16 LE, then 8 raw bytes big-endian. Example: `zoom` command Id at @750 is `26 f1 38 7e 11 2a 18 44 b0 e3 1e 06 49 17 e1 d6` → `7e38f126-2a11-4418-b0e3-1e064917e1d6`. [SOLID]
- **Length-prefixed string** — `[u32 length][UTF-8 bytes]`. Phrases, category, string operands, variable names.
- **Sentinels** — `0xFFFFFFFF` marks an absent/optional field; `0x00000000` marks empty/default. Both alias real values in a flat scan (§11), and "absent" encodes differently per value type (§8.3).

## 5. Logical model (XML) — the field set the binary encodes

Source of truth for field names: Edvard `defaultcommand.xml`, VoiceAttack's own `CommandAction` serialization. [SOLID]

```
Profile
  Id (GUID), Name (string)
  Commands: Command[]
    Command
      Id (GUID), CommandString (phrase), Category (string)
      ActionSequence: CommandAction[]
```

**Conditions are not a separate action type — they are FIELDS on each `CommandAction`.** [SOLID] The full `CommandAction` field set: `Ordinal`, `IndentLevel`, `ConditionMet`, `ConditionPairing`, `ConditionGroup`, `ConditionStartOperator`, `ConditionStartValue`, `ConditionStartValueType`, plus `ActionType`, `Duration`, `Delay`, `KeyCodes`, `Context`, `X`, `Y`, `InputMode`, `IsSuffixAction`. The binary stores integer CODES, not names: `corinthian` contains zero occurrences of `PressKey`/`BeginCondition`/etc. as strings. [SOLID]

**XML-input naming hazard [SOLID, real VoiceAttack XML exports: mandiant/IDA_Pro_VoiceAttack_profile, Penecruz/VAICOM-Community; 2026-07-11].** The real on-disk `<CommandAction>` XML uses `ConditionStartType` as the value-type carrier (0=Small Integer, 1=Text, 2=Boolean, 3=Integer, 4=Decimal — same enum as m[24] in §8.1); `ConditionStartValueType` is a DIFFERENT, vestigial element that reads `0` in every real sample and must not be read as the type. `ConditionStartValue` is the SmallInteger/Boolean right-hand comparison value (an integer text node), never the left operand — the left operand is `ConditionStartNameFrom`. For Text-typed compares the right-hand value is carried in a separate `<Context2 xml:space="preserve">` element, not `ConditionStartValue`. `ConditionStartOperator` and `ConditionStartType` are integers (dropdown index / enum code, §8.1-8.2), not name strings, on the wire. `<ActionType>` carries the string `ConditionStart` / `ConditionElseIf` / `ConditionElse` / `ConditionEnd` for binary codes 19 / 63 / 29 / 20 respectively (§9.1). `ConditionPairing`/`ConditionGroup` map 1:1 to m[17]/m[18] (§8.4-8.5). Integer/Decimal XML right-hand carriers are unverified — out of scope.

**Set-family / Write / loop XML names [SOLID except as tagged; real XML exports: Antaniserse/VAExtensions, SavageCore/EDDB_Scraper, mandiant/IDA_Pro_VoiceAttack_profile, Penecruz/VAICOM-Community; 2026-07-12].** The Set family splits exactly like the binary layer (Text/Bool targets in `Context` ≈ m[6], Int/SmallInt targets in `ConditionSetName` ≈ m[15]): code 18 = `ConditionSet` (legacy VA1 "condition" = small int; target `ConditionSetName`, value `X`), 37 = `IntSet` (target `ConditionSetName`, literal value `X`), 21 = `TextSet` (target `Context`, value `Context2` xml:space=preserve), 36 = `BooleanSet` (target `Context`, value `InputMode` 0=True/1=False — the binary m[14] enum verbatim, both polarities sampled). The binary stale-slot hazard recurs at the XML layer: IntSet actions were observed carrying leftover author strings in `Context`/`Context2` — never read those as IntSet operands. Code 23 = `WriteToLog` (text in `Context`, variable tokens legal; `X` = color code, 0/1/3/6 observed, name mapping unverified), 40 = `FreeType` (text in `Context`; `Duration` = per-keystroke delay seconds), and the loop pair 30/31 = `WhileStart`/`WhileEnd`. Code 38 = `DecimalSet` is INFERRED-PLAUSIBLE only (target `ConditionSetName`, value `DecimalContext1` by IntSet analogy — zero public XML samples; pending the VA import probe). XML-input decode binds payloads only for 23 (`text`) and 38 (`targetVariable`/`value`) as of dictionary 0.4.0; the other codes in this paragraph are name-resolution-only.

## 6. Binary object model (core of this spec)

The decompressed buffer is a nested tree of serialized objects. Three envelope shapes are established, one per level.

### 6.1 File / Profile header  [SOLID for the fields below; command-list index OPEN]

```
@0x0000  u32  total decompressed size      — all five profiles [SOLID]
@0x0004  u32  0x59 (89)                    — constant across all five; meaning unknown [SOLID observation]
@0x0008  u32… top-level offset table        — entries 0/1/2 resolve to the profile record, profile name,
                                              and command count; entries 3+ point into a trailing
                                              ~size−530 region, undecoded [SOLID for 0-2 / OPEN for 3+]
@0x0170  GUID profile Id                   — profile record @368 [SOLID]
@0x0180  u32  profile name length
@0x0184  string profile name
```

The profile record @368 also carries the profile's **command count** (corinthian = 201, matching the CSV). How the command LIST is indexed remains [OPEN] — the trailing region likely holds a per-command index, but it is undecoded; command discovery stays scan-based (§13). Hazard: the profile record itself matches the command-envelope signature and will walk as a pseudo-command if not excluded (§11.5).

### 6.2 Command envelope  [SOLID — verified in all five profiles]

```
[GUID (16 B)]            command Id
[u32 phraseLen]
[UTF-8 phrase]           CommandString, e.g. "zoom [out; in]"
[u32 actionCount]        number of CommandAction objects that follow
[action object 0][action object 1]…[action object N-1]   (§6.3, chained)
… trailing: Category string, description, flag bytes — structure only partly mapped [OPEN §12]
```

zoom evidence: GUID @750, phraseLen @766 (=14), phrase @770 `zoom [out; in]`, actionCount @784 (=5), first action object @788. [SOLID]

**Correction to flat-scan-era docs.** `VAP_FORMAT.md:L30-33` and `VAP_Binary_Schema_Analysis.md:L32-35` read the u32 after `actionCount` as "number of offset entries" followed by a "command-property offset table." That is a MISREAD: the array at @788 is the FIRST ACTION OBJECT'S member-offset table (§6.3), and the u32 at @784 is the action COUNT. Decisive evidence: corinthian set-fire's raw actionCount is 37 and exactly 37 objects chain cleanly to the next command; the CSV confirms 37 actions. [SOLID]

### 6.3 `CommandAction` object envelope  [SOLID — the central result]

Every action is serialized as:

```
[u32 head][u32 m[0]][u32 m[1]]…[u32 m[33]]   ← offset array (35 u32 total)
[member-data heap]
```

Rules, all verified across the full 1,603-object census:

1. **Member count is FIXED at 34.** A decoder MUST read exactly 34 and MUST NOT infer the count by "read while ascending" — an interned/shared heap slot can emit a backward offset and silently truncate the array. [SOLID]
2. **Base = the array's own start; slots are offsets requiring deref.** `m[i]`'s data is at `arrayStart + m[i]`, read at that slot's data type (§6.4 table). zoom action[0] (array @788): `m[20]` = 254 → @1042 derefs to 6 (the operator); `m[19]` = 235 → @1023 = the token operand; `m[7]` = 184 → @972 = the literal `out`. [SOLID]
3. **`head` = the object's total byte length = pointer to the next sibling.** zoom action[0] head = 347 → next array @ 788+347 = 1135, exactly action[1]'s array. Walking `start → start + head` chains the actions; chain length = `actionCount`. A single-key keypress object is a fixed 331-byte template (head = 331, numkeys). [SOLID]
4. **Fixed heap-header offsets.** In every object of every profile: m[0] holds offset 32 (a constant structure), m[1] = 140 (= 4 + 34×4, the heap start — the per-action GUID), m[2] = 156, m[3] = 160, m[4] = 168, m[5] = 176. Slots 6+ have variable offsets (the heap shifts with string lengths). The member INDEX is the stable schema position: read by index, never by absolute byte position. [SOLID]

Chain validated on the hardest real commands: set-fire (37 actions), `corinthian ((EDDI jumped))` (15, two nested compares), `Climb` (17, if/else-if/else + nested Integer block + Loop While). [SOLID]

### 6.4 `CommandAction` member index map

**Member semantics are ActionType-polymorphic** — the same slot means different things on different action families (m[6], m[7], m[20] proven polymorphic). Apply each row only to the action families listed. Deref type given per slot. [SOLID unless tagged]

| idx | deref type | field (family) | value/meaning | confidence |
|-----|-----------|----------------|---------------|------------|
| m[0] | — | — (all) | slot holds the constant OFFSET 32 in every object (same series as m[1]=140); what it addresses is unresolved — the offset lands inside the offset array itself | [SOLID observation] |
| m[1] | GUID | action Id (all) | per-action GUID at heap start; 1,635 distinct across census (incl. Probe B) | [SOLID] |
| m[2] | u32 | **`ActionType`** (all) | integer code; full enum §9.1; v0.2's five-profile census saw 40 distinct codes; Probe B's 32 actions used 14 codes, all now attributed (§9.1) | [SOLID] |
| m[3] | double | `Duration` (keypress, Pause); scroll click count (mouse) | keypress hold time; Pause seconds (CSV: 1.125 reproduced); mouse scroll clicks as IEEE double (5.0 observed on Scroll Forward, §9.3) — same slot reused, not a separate field | [SOLID — Probe B for the mouse reuse] |
| m[4] | double | click duration (mouse) | 0.1 observed on Left Click / Left Double Click / Right Click (CSV: "duration 0.1 seconds"); absent (0.0) on scroll and Move | [SOLID — Probe B] |
| m[5] | list | **`KeyCodes`** (key actions) | `[u32 count][count × u16 VK]`; chords read count 2–3 ([162,164,69] = LCtrl+LAlt+E) | [SOLID — review §2.4] |
| m[6] | string | polymorphic | Set-action target variable name (Text `m[6]='integer_text'`, Boolean `m[6]='bfa'/'btr'`); mouse context code (§9.3, `LC`/`LDC`/`RC`/`SF`/`Move` observed); Launch executable path (`C:\probe\launch-test.exe`); Say text (`'say-marker'`); SetClipboard text (`'clip-marker'`); Write text (`'write-marker'`) | [SOLID — Probe B closes Launch/Say/SetClipboard/Write] |
| m[7] | string | polymorphic | `ConditionStartValue` for **Text compares only** (`out`=3, `in`=2); Set-Text value (`'2'`); Launch arguments (`'--a1 --a2'`); mouse parameter — absent (0xFFFFFFFF) on the five Probe B mouse variants (LC/LDC/RC/SF/Move, none of which need a parameter) but POPULATED on corinthian's `SPECIAL` mouse context (`m[7]='Application Center'`, a window/element target name) — the slot is real, just unexercised by Probe B's sample set | [SOLID] |
| m[8] | string | polymorphic | Say voice GUID as a string (`'00000000-0000-0000-0000-000000000000'` for the Default voice); Launch working directory (`'C:\probe\wd'`) | [SOLID — Probe B] |
| m[9] | string | Say voice display name | `'Default'` observed | [SOLID — Probe B] |
| m[11] | i32/u32 | polymorphic | Set-Integer literal value-source-mode-0 operand AND arithmetic literal operand in modes 8 (climb's 99; 58/58 corinthian Set-Integers verified pre-Probe-B; siv6–siv10 in the arithmetic sweep); Say volume (43 observed); mouse Move X (333 observed) | [SOLID — Probe B extends to Say/mouse] |
| m[12] | u32 | polymorphic | Say rate (7 observed); mouse Move Y (444 observed); also nonzero (=1) alongside m[11] on Set-Integer arithmetic-mode actions (siv6–siv11) — meaning of that secondary flag not isolated, park as minor open item | [SOLID for Say/Move; OPEN for the Set-Integer arithmetic flag] |
| m[14] | u32 | Set-action value-source-mode selector (Boolean, Integer) | On Set Boolean: 0=True / 1=False (the two literal-value positions); positions 2–6 (Toggle, Another Boolean variable's value, Random true/false, Retrieve saved value, Clear value — per screenshot dropdown order) are unsampled, positional-INFERRED. On Set Integer: full enum §9.4 (0/1/4/5/6/7/8/9 observed, 2/3 unobserved) — same slot number, same "which source populates the value" concept, but a DIFFERENT per-type ordering (§9.4 table) — do not conflate the two dropdowns | [SOLID for Boolean 0/1 and Integer's 8 observed codes — Probe B; INFERRED for Boolean 2–6] |
| m[15] | string | Set target name (Integer, Decimal) | disjoint from m[6]'s Text/Bool targets; Probe B: `'siv0'`..`'siv11'`, `'ssi'`, `'sd'` | [SOLID] |
| m[16] | string | Set-Integer source-variable / text-var reference | value-source mode 4 ("another variable's value"): source var name (`m[16]='siv0'`); mode 9 (arithmetic w/ variable operand): variable name; modes 6/7 (converted value of a text var / saved value): `m[16]='[integer_text]'` on both — see the mode-5/6/7 stale-slot hazard below | [SOLID — Probe B] |
| m[17] | u32 | `ConditionPairing` (block actions) | 0-based index of the paired action (§8.4) | [SOLID] |
| m[18] | u32 | block-open ordinal | 1-based, increments per Begin; AND/OR grouping de-scoped (§8.5) | [SOLID as ordinal] |
| m[19] | string | polymorphic | left operand (compares): inline token (`{LASTSPOKENCMD}`, `{TXT:bbq}`) OR pool-local variable name — same slot both ways; Set-Integer value-source mode 1 (random): minimum bound AS A STRING (`'0'` observed) | [SOLID] |
| m[20] | u32 | polymorphic | `ConditionStartOperator` on compares (§8.2); Set-action arithmetic operation code, ONLY meaningful in value-source modes 8/9 — 0=plus · 1=minus · 2=times · 3=divide (integer division) · 4=mod (Probe B swept siv6–siv11: plus/minus/times/divide/mod/mod in order) | [SOLID — Probe B resolves the set-op enum] |
| m[21] | i32 | numeric/boolean right operand (compares) | Integer/Small-Int/Boolean compare value; True=1; negatives real (−1..−4 observed) | [SOLID — review §2.2] |
| m[23] | u32/string | polymorphic | on most actions: binary flag, ≡0xFFFFFFFF (1,359 objects) or 0 (244); meaning unmapped [OPEN]; on Set-Integer value-source mode 1 (random): maximum bound AS A STRING (`'9'` observed) — same slot, different type per context, consistent with the m[7]/m[19] polymorphism pattern | [SOLID for the Set-Integer random-max reading — Probe B; OPEN elsewhere] |
| m[24] | u32 | `ConditionStartValueType` | 0=Small Int, 1=Text, 2=Bool, 3=Int, 4=Decimal (§8.1) | [SOLID] |
| m[25] | Decimal 16 B | Decimal value | Decimal compare value AND Set-Decimal value (.NET layout, §4); Probe B cross-check: `m[15]='sd'`, `m[25]`=4.44 (flags 0x00020000, scale 2) | [SOLID — review §2.1, reconfirmed Probe B] |
| m[27], m[28] | u32 | structural constant | deref = **0x886E0900**; byte layout `[00][09 6E 88 F1][FF FF FF FF]` — the recurring 4-byte constant 0xF1886E09 sits at deref+1. An equality test against 0xF1886E09 at deref FAILS | [SOLID — review §2.7, reconfirmed on all 32 Probe B objects] |
| m[31] | region | compound sub-condition list | scalar = sub-condition count (2 observed); record format undecoded, decode-only (§8.6) | [SOLID scalar / OPEN format] |
| dead | — | — | m[10]≡0xFFFFFFFF; m[22], m[26], m[32], m[33]≡0 across the census | [SOLID observation] |

~24 slots are near-constant (0 or 0xFFFFFFFF) and unmapped — parked (§12).

Gate operator reads on the ActionType, m[2]: treat an action as a compare only when m[2] ∈ {19 Begin, 63 Else If, 30 Begin Loop While}. Do NOT gate on m[24] — Small-Integer conditions AND every non-condition action read m[24]=0, so it filters nothing; m[24] is DESCRIPTIVE (the value-type), not a condition flag. [SOLID]

**Decoder hazard — stale secondary-operand slots on Set-Integer.** Probe B's value-source-mode sweep shows m[19]/m[23] (the random-bounds strings `'0'`/`'9'`) still populated on the mode-5 ("Not Set") action, and m[16] (`'[integer_text]'`) populated identically on BOTH mode-6 and mode-7 actions. The simplest reading is that VoiceAttack's UI does not clear a field when the user switches the value-source dropdown away from a position that used it — the byte is left over from an earlier UI state, not meaningful at the current mode. This is PLAUSIBLE, not verified (single build, no A/B on the same var across dropdown switches) — a decoder MUST gate every Set-Integer operand read on m[14] and MUST NOT infer mode from which operand slots happen to be populated. [PLAUSIBLE — Probe B, single-sample]

## 8. Condition encoding

### 8.1 `ConditionStartValueType` — m[24]  [SOLID, complete]

Authored one-compare-per-type sweep in `conditionals-Profile.vap`; m[24] is the ONLY member separating all five types:

| code | value-type | evidence (command @offset) |
|------|-----------|----------------------------|
| 0 | Small Integer | `small int` @34124 |
| 1 | Text | `New Command` @23108, `zoom` |
| 2 | Boolean | `boolean` @764 |
| 3 | Integer | `integer compare` @4677 |
| 4 | Decimal | `nested + decimal ` @13551 |

**Caveat.** Small Integer reads 0, identical to the value non-condition actions carry; 0-as-Small-Int and 0-as-unset are indistinguishable by this field alone. Identify a Small-Int compare structurally (m[2]=19 + operand m[19] + operator m[20]), never by m[24]. Inline non-Text tokens carry their declared type (corinthian `((EDDI entered signal source))` inline `[{INT:…}]` reads m[24]=3), so value-type applies to inline tokens as well as pool locals. [SOLID]

### 8.2 `ConditionStartOperator` — m[20]  [SOLID]

**The operator code is the 0-indexed position of the operator in THAT value-type's dropdown.** Because the dropdowns differ in length, the same operator has different codes per type — e.g. "Has Not Been Set" is 3 (Boolean) / 7 (Integer, Decimal, Small Int) / 9 (Text).

| value-type | operators (index = code) | evidence |
|-----------|--------------------------|----------|
| Text (10) | 0 Equals · 1 Does Not Equal · 2 Starts With · 3 Does Not Start With · 4 Ends With · 5 Does Not End With · 6 Contains · 7 Does Not Contain · 8 Has Been Set · 9 Has Not Been Set | self-labeling sweep, m[7] literals match dropdown order |
| Integer / Decimal / Small Integer (8) | 0 Equals · 1 Does Not Equal · 2 Is Less Than · 3 Is Less Than Or Equals · 4 Is Greater Than · 5 Is Greater Than Or Equals · 6 Has Been Set · 7 Has Not Been Set | sweeps + corinthian CSV anchors (`Does Not Equal ±1..±4`→1, `Is Less Than 2`→2, `Is Greater Than 0` Loop While→4, Small-Int `Is Greater Than 2/3`→4) |
| Boolean (4) | 0 Equals · 1 Does Not Equal · 2 Has Been Set · 3 Has Not Been Set | `boolean` @764 sweep |

Cross-profile anchor: zoom's two `Contains` branches read m[20]=6 at @1042 / @1719; corinthian's Text `Does Not Equal` reads 1 — exact CSV correlation. [SOLID]

### 8.3 Operands and value encodings  [SOLID — review §2.2 correction applied]

- **Left operand — m[19].** The evaluated side. Length-prefixed string: either an inline token (`{LASTSPOKENCMD}`, `{TXT:name}`, `{INT:name}`) or a pool-local variable name (`i`, `count`, `throt`). [SOLID]
- **Right operand — split by value type:**
  - Text → length-prefixed string at **m[7]**. [SOLID]
  - Integer / Small Integer / Boolean → **i32 at m[21]** (throttle compares read 1/2/3/4; reverse compares −1/−2/−3/−4; Small-Int 2/3; `[submit] Equals True` reads 1). m[7] derefs to 0xFFFFFFFF on every non-Text compare. [SOLID]
  - Decimal → **16-byte .NET Decimal at m[25]** (flags, hi, lo, mid; 5.43 = scale-2 flags + lo 543). NOT an IEEE double — no double of the compare values exists anywhere in those objects. [SOLID]
- **Absent-value hazards.** (a) Integer −1 in m[21] is byte-identical to the absent sentinel 0xFFFFFFFF — type-gate on m[24] before deciding a field is unset. (b) Text Has/Has-Not-Been-Set reads m[7]='' (empty string), not 0xFFFFFFFF — "absent" encodes differently per type. [SOLID]
- **Local-variable declaration pool.** Pool-local variables are referenced by a `[01 00 00 00][u32 len][name][01 00 00 00]` wrapper; the pool record and the condition record share this wrapper, so a naive name search lands on the pool, not the compare. The object walk sidesteps this: m[19] resolves the operand from within the action object. Where the pool itself lives (command trailing region vs profile level) is unresolved [OPEN §12]. [SOLID for the wrapper]

### 8.4 `ConditionPairing` — m[17]  [SOLID]

The 0-based index (within the command's action sequence) of the action that closes this block's current segment, and the reverse link on closing actions. **All block actions carry pairing links** — Begin, Else If, Else, End, Begin/End Loop:

- A `Begin`/`Else If` points to the NEXT branch point or the block's `End` — NOT straight to the final `End`. zoom: Begin @action0 → 2 (its Else If), Else If @action2 → 4 (the End). climb: Begin → 3 (Else If), Else If → 8 (Else), Else @8 → 10.
- Loop While → End Loop and back (climb a11→16, 16→11).
- With real nesting (corinthian `((EDDI jumped))`): outer Begin (action 9) → 14 (outer End), inner Begin (10) → 13 (inner End); the End records point back to their Begins (14→9, 13→10).
- In an Else-If chain the End points back to the ORIGINAL Begin (boolean a9→1), not the last Else If.

This settles the old "branch vs. final End" question: the model is "next branch point." [SOLID]

### 8.5 m[18] — block-open ordinal  [SOLID as ordinal; grouping de-scoped]

A 1-based counter that increments once per `Begin`-condition in serialized order; `Else If` inherits its `Begin`'s number; nested `Begin`s take the next number. Evidence: `nested + decimal` reads 1,2,3,3,4,5,6,7,8; the Text sweep reads 1..10; zoom 1,1; `boolean` 1,1,1,1 — the latter two are single Begin/Else-If chains, which is WHY flat sequences support the model. Edge: corinthian `Climb`'s Loop While reads 1, not a fresh number. Whether m[18] doubles as `ConditionGroup` (AND/OR grouping) was Probe A's question; **Probe A is dropped and compound grouping is de-scoped to decode-only** (2026-07-08 ruling) — do not implement m[18] as `ConditionGroup`. [SOLID for the ordinal behavior]

### 8.6 Compound conditions — `(A AND B) OR (C AND D)`  [SOLID observation; format OPEN, de-scoped]

A compound `Begin Condition` is a SINGLE action object holding multiple sub-compares. corinthian `(return to main screen)`: one object @29797, head=579 (inflated vs ~340 simple), m[2]=19, first sub-compare in the normal slots (m[7]='none', m[20]=0), second literal `station services` @30324 inside m[31]'s data region; m[31]'s scalar reads 2 = sub-condition count. [SOLID observation]

Decoder contract: the single-compare member map UNDERCOUNTS sub-conditions on compound blocks. Support is scoped to **nested single-condition blocks**; multi-conditioned AND/OR compounds are decode-only — emit the first sub-compare plus an explicit `compound: n sub-conditions, undecoded` marker, never silence. The m[31] record format is parked [OPEN §12].

### 8.7 `IndentLevel` — CLOSED: not stored, derived  [SOLID]

No member of the 34-slot table encodes nesting depth (per-slot u32 diff on `nested + decimal`, depths 0/1/2: a depth-0 and depth-1 `Begin` differ only in {m[1] GUID, m[17], m[18], m[20]}). Nesting is fully reconstructable from `ConditionPairing` (m[17]) plus the m[18] ordinal; a decoder derives `IndentLevel` from Begin/End nesting. [SOLID]

## 9. Action encoding

### 9.1 `ActionType` — m[2]  [SOLID for the CSV-confirmed codes]

The ActionType is member m[2] — an integer code per action type, mapped by correlating walks against CSV/UI action names. v0.2's census observed **40 distinct codes** across the five profiles in §2's original table; Probe B's 32 actions (10 commands) use 14 distinct codes, every one of them now attributed — 8 by Probe B itself (3, 13, 24, 25, 26, 27, 50, 51), the other 6 (12, 21, 23, 36, 37, 38) reconfirming codes already attributed in v0.2. Whether 3 and 13 are new values not present in the original five-profile byte census, or were already present there unattributed, was not independently re-verified in this pass — the ad-hoc scan attempted for that cross-check was unreliable on the larger profiles (a heuristic reused from the Probe B script, not the validated walker) and its output is discarded rather than asserted. The attributed table:

| code | ActionType | code | ActionType |
|------|-----------|------|-----------|
| 0 | PressKey | 27 | Clear Dictation Buffer |
| 2 | Pause | 29 | Else |
| 3 | Launch / Run Application | 30 | Begin Loop While (compare) |
| 8 | KeyDown | 31 | End Loop |
| 9 | KeyUp | 32 | Marker |
| 12 | MouseAction | 33 | Jump to Marker |
| 13 | Say | 35 | Play Sound |
| 16 | Execute Command | 36 | Set Boolean |
| 17 | Kill Command | 37 | Set Integer |
| 18 | Set Small Int (legacy — §9.4) | 38 | Set Decimal |
| 19 | Begin Condition (compare) | 40 | Quick Input |
| 20 | End Condition | 50 | Start VoiceAttack Listening |
| 21 | Set Text | 51 | Stop VoiceAttack Listening |
| 22 | Execute External Plugin | 62 | Pause Variable |
| 23 | Write | 63 | Else If (compare) |
| 24 | SetClipboard | 64 | Exit Command |
| 25 | Start Dictation Mode | 67 | KeyToggle |
| 26 | Stop Dictation Mode | | |

All CSV-confirmed or Probe-B-confirmed [SOLID] (3, 13, 24, 25, 26, 27, 50, 51 are Probe B closures, all self-labeling and object-walk verified — see §9.4). Codes 19 / 63 / 30 carry a compare (read operator m[20], type m[24], operands); 20 / 29 / 31 are block-structure actions with no operand. **XML `<ActionType>` strings for 19 / 63 / 29 / 20** [SOLID, real VoiceAttack XML exports: mandiant/IDA_Pro_VoiceAttack_profile, Penecruz/VAICOM-Community; 2026-07-11]: `ConditionStart` / `ConditionElseIf` / `ConditionElse` / `ConditionEnd` (see §5 XML-input naming hazard for the accompanying field-name corrections). 62 (Pause Variable, `[{DEC:x}]` seconds) is distinct from fixed Pause 2. **KeyDown / KeyUp / KeyToggle are distinct ActionTypes (8 / 9 / 67), not a subtype member** — closure item 2. This SUPERSEDES the flat-scan note that "`01 00 00 00` = ActionType 1 = PressKey": that `01` is m[5]'s KeyCodes count=1; PressKey's code is 0. [SOLID]

**24 = SetClipboard, not "paste dictation."** v0.2's PLAUSIBLE attribution of code 24 to a "paste dictation" action is REFUTED by Probe B: 24's only observed field is m[6] (text — `'clip-marker'` on the `clip test` command). "Paste Dictation" does not exist as an action in VoiceAttack 2 — confirmed in-profile: when the Probe B dictation sweep attempted to build it, VoiceAttack recorded a SetClipboard action (code 24) whose m[6] text reads `"No such action as 'Paste dictation'"` (a manual annotation Richard left when the UI offered no such action), NOT an actual PasteDictation action. Any decoder/dictionary reference to a PasteDictation ActionType is stale. [SOLID — Probe B]

25/26/27 are Start Dictation Mode / Stop Dictation Mode / Clear Dictation Buffer, promoted from v0.2's PLAUSIBLE to SOLID: Probe B's `dictation set` command built all three (plus 50/51) in sequence and every code lines up with its command-phrase intent. 25 additionally carries a flag: `m[11]=1` on the probe's "Start Dictation Mode (Clearing Dictation Buffer)" build — read as a clear-buffer-first flag, single sample. [SOLID for the code; PLAUSIBLE for the m[11] flag meaning — single sample]

50/51 = Start / Stop VoiceAttack Listening, the last previously-unlabeled census codes, closed by Probe B's `dictation set` command (built first in the sequence, before the dictation-mode actions). Neither carries any populated field beyond the shared envelope constants — no operand layout to decode. [SOLID]

### 9.2 Keypress record  [SOLID — restated in member-slot terms]

- **`Duration` = m[3]** (double): zoom keys 1.5 s, numkeys 0.5 s; KeyDown/KeyUp/KeyToggle read exactly 0.0.
- **`KeyCodes` = m[5]**: `[u32 count][count × u16 VK]` (F = 0x46, R = 0x52; chords count 2–3 with full VK list).
- The flat scan's `00 00 00 00 | 01 00 00 00` "marker" is m[4]'s zero tail + m[5]'s count=1 — the single-key special case. **Any matcher keyed on that 8-byte pattern silently misses every chorded keypress** (count ≠ 1) — a proven live gap in flat-scan decoding (§11.6).
- Flat-scan legacy facts, still true where a flat reader is unavoidable: Duration double sits 12 bytes before that marker; VK u16 at marker+8; validity floor `0.001 ≤ d ≤ 60` (phantom slots hold positive denormals ~1e-304). Command-relative positions like "VK at rel 209" are accidents of phrase length (20 + len + heap layout) — only array-relative positions are stable. [SOLID]

### 9.3 Mouse actions  [SOLID — Probe B closes the context enum sample, click duration, scroll count, and cursor Move]

MouseAction = m[2] code 12. The context-code string lives at **m[6]** and the action parameter at **m[7]** (walk-verified; the polymorphism warning in §6.4 applies). Context code is `{button}{action}` (e.g. `LC`, `RDC`, `SF`). Probe B built and walk-verified `LC`, `LDC`, `RC`, `SF`, and a new context `Move` — all five match the m[6]/m[7] slot model. [SOLID]

- **Click duration — m[4] double.** 0.1 observed on `LC`, `LDC`, `RC` (matches CSV "duration 0.1 seconds"); 0.0 (unused) on scroll and Move. This is a NEW slot assignment — m[4] previously appeared in §6.4 only as a fixed heap-header offset, not a semantic field. [SOLID — Probe B]
- **Scroll click count — m[3] double.** `SF` (Scroll Forward, 5 clicks requested) reads m[3]=5.0 as an IEEE double — the SAME slot as keypress/Pause `Duration` (§6.4), reused rather than a distinct field. This SUPERSEDES the flat-scan-era claim of "a double at −20 from the context-code length prefix": that claim was never object-walk verified and is retired as [INFERRED, superseded]. The corrected reading also validates the generator's XML side, which already writes scroll clicks to `<Duration>`. [SOLID — Probe B]
- **Cursor Move — new context `Move`.** X = **m[11]** u32 (333 observed), Y = **m[12]** u32 (444 observed). No click-duration (m[4]=0) or scroll-count (m[3]=0) on this context — consistent with Move using its own operand pair. [SOLID — Probe B]
- **m[7] parameter slot — reconfirmed, not exercised by Probe B's five variants.** All five Probe B mouse samples (LC/LDC/RC/SF/Move) leave m[7]=0xFFFFFFFF (absent) — none of those five contexts needs a parameter. Independently re-walking `corinthian-4-Profile.vap`'s 9 mouse actions (contexts: `LC`×3, `Move`×3, `MD`, `MU`, `SPECIAL`) finds the `SPECIAL` context WITH m[7] populated: `m[7]='Application Center'` (a window/element target name). The m[7] parameter slot is real and in active use by at least one context outside Probe B's sample — Probe B narrows which contexts leave it empty but does not retire the slot. [SOLID — corinthian cross-check]
- **Full context-code enum.** The button×action derivation scheme (5 buttons × 6 actions + 4 scrolls = 34 codes, `schema/vap_capability_dictionary.json` `mouse` block) was already SOLID pre-Probe-B by construction of the code scheme itself; Probe B spot-samples 4 of the 34 plus the new `Move` context and all match. The remaining 30 combinations and the `SPECIAL` context's full semantics (does every non-click/scroll/move context populate m[7]? what other context strings exist?) are not individually re-verified — treat the scheme as SOLID, individual untested combinations as INFERRED-by-pattern.

### 9.4 Set actions and others

**Set-action value-source-mode model (m[14]) — this RESOLVES the v0.2 m[20] set-op contradiction.** [SOLID for observed codes — Probe B] `m[14]` is a value-source-mode selector present on Set Boolean and Set Integer (the two types Probe B swept); it answers "where does this Set action get its value from," and its meaning is PER-TYPE (a different dropdown, like §8.2's condition operators) even though the slot number is shared:

| Set Integer m[14] | meaning | operand location |
|---|---|---|
| 0 | literal value | m[11] i32 |
| 1 | random | bounds as STRINGS: m[19]=min (`'0'`), m[23]=max (`'9'`) |
| 2, 3 | unobserved (dropdown positions not built by Probe B) | — |
| 4 | another variable's value | source var name string in m[16] (`'siv0'`) |
| 5 | Not Set | — (m[19]/m[23] may hold stale values — see §6.4 hazard) |
| 6 | converted value of a text var | m[16]=`'[integer_text]'` |
| 7 | saved value | — (m[16] may hold a stale value from mode 6 — see §6.4 hazard) |
| 8 | arithmetic, literal operand | operand m[11], operation m[20] (0=plus·1=minus·2=times·3=divide·4=mod) |
| 9 | arithmetic, variable operand | variable m[16], operation m[20] |

Probe B built one Set Integer per dropdown position (`siv0`..`siv11`, `set int sweep` command) — codes 2 and 3 were not built (dropdown positions skipped in the sweep) and remain unobserved. The v0.2 contradiction ("climb's 'converted value' read m[20]=4, jumped's read m[20]=0") dissolves: **m[20] was never the value-source code — m[14] is.** m[20] on a Set-Integer action is ONLY meaningful when m[14]∈{8,9}, where it is the arithmetic operator. [SOLID]

**Set Boolean (36) m[14]** is the SAME concept (value-source mode) with a DIFFERENT dropdown: positions 0=True, 1=False are the two literal values Probe B swept and are [SOLID] — the value-vs-order confound from v0.2 is broken: the probe built `Set Boolean [bfa] to False` FIRST (m[14]=1) then `Set Boolean [btr] to True` SECOND (m[14]=0); if m[14] tracked serialization order it would read 0 then 1, not 1 then 0. The full Boolean dropdown, screenshotted, is: True, False, Toggle, Another Boolean variable's value, Random true or false, Retrieve saved value, Clear value — so positions 2–6 are presumed the analogous other-source modes, but unsampled (INFERRED, positional only). Target name: m[6] (`'bfa'`, `'btr'`). [SOLID for 0/1; INFERRED for 2–6]

**Set-action field map — disjoint from the condition map, per-type** [SOLID, closure item 5, extended by Probe B]:

| Set type (m[2]) | value slot | target-name slot | value-source mode |
|-----------------|-----------|------------------|--------------------|
| Set Text (21) | m[7] string | m[6] | not swept — Probe B reconfirmed m[6]=`'integer_text'`/m[7]=`'2'` only |
| Set Boolean (36) | m[14] u32 (0=True/1=False) | m[6] | m[14] itself (see above) |
| Set Integer (37) | mode-dependent (m[11]/m[16]/m[19]+m[23], see table) | m[15] | m[14] (see above) |
| Set Decimal (38) | m[25] .NET Decimal | m[15] | not swept — Probe B cross-check: m[15]=`'sd'`, m[25]=4.44 |
| Set Small Int (18) | legacy/decode-only — see below | — | — |

**Set Small Int is MOOT in VoiceAttack 2.** VoiceAttack 2 merged Small Int into Integer (Richard's in-profile command description on the probe's `set smallint test` command: "Smallint merged with Int in VA 2"). Building "Set Small Int [ssi] to 33" in the VoiceAttack 2 UI serializes as ActionType **37** (Set Integer), value-source mode 0, m[11]=33, m[15]='ssi' — indistinguishable from a native Set Integer action. ActionType code **18** is retained in the enum as legacy/decode-only for pre-VA2 profiles that may still contain it; its own field layout was not and cannot be re-sampled from a VA2 build and stays [OPEN]. [SOLID for the VA2 merge finding — Probe B]

**Say (13)** [SOLID — Probe B]: m[6]=text (`'say-marker'`), m[8]=voice GUID as a string (`'00000000-0000-0000-0000-000000000000'` for the Default voice), m[9]=voice display name (`'Default'`), m[11]=volume u32 (43), m[12]=rate u32 (7). XML side (already emitted by the generator): `Context`=text, `X`=volume 0–100, `Y`=rate.

**Launch / Run Application (3)** [SOLID — Probe B]: m[6]=executable path (`'C:\probe\launch-test.exe'`), m[7]=arguments (`'--a1 --a2'`), m[8]=working directory (`'C:\probe\wd'`). The `*`-prefix-for-window-title-match convention noted in the dictionary is a decoder-v1/XML-side inference, not independently re-verified by Probe B (the probe built a plain path, no `*` variant).

**SetClipboard (24)** [SOLID — Probe B]: m[6]=text (`'clip-marker'`). See §9.1 for the refutation of the old "24 = paste dictation" attribution.

**Write (23)** [SOLID for m[6]; PARKED for color/shape — Probe B]: m[6]=text (`'write-marker'`), reconfirming v0.2. VoiceAttack's Write UI also exposes color and shape parameters (e.g. `[Blue]`, `[Square]`); Probe B's `write test` command used the defaults for both, and a full raw dump of every one of the action's 34 slots found nothing populated beyond m[6] and the m[27]/m[28] structural constants — color/shape did NOT appear in any nonzero slot. With only one sample at default values, a color/shape field is indistinguishable from "doesn't exist" or "defaults to zero" — parked as a minor open item (§12) rather than concluded either way.

## 10. Structural constants

- **m[0] slot ≡ 32** (the stored offset, constant) in every object of every profile — do NOT deref it as a value; its meaning is unknown. [SOLID observation]
- **m[27]/m[28] deref ≡ 0x886E0900**; byte layout `[00][09 6E 88 F1][FF FF FF FF]`. The 4-byte constant `0xF1886E09` recurs throughout the action region at deref+1 — it is a generic separator, NOT a per-type tag, and NOT the u32 you get by dereffing the slot. [SOLID — review §2.7]
- **GUID count per command = 1 + actionCount** (at least): the command Id plus one m[1] GUID per action (1,603 distinct action GUIDs in the census). v0.1's "three GUIDs per command" is deleted — it described nothing observed. [SOLID]
- The optional `2.1.8` string: present in 3/5 profiles (§2) — do not anchor on it.

## 11. Decoding hazards (why a flat scan fails)

All are byproducts of pattern-scanning a flat byte range instead of walking the object tree. [SOLID]

1. **Aliased `'F'`/`'R'` label strings** — the keypress count `01 00 00 00` reads as a length-1 string whose "content" is the next byte, the VK itself. One physical byte, two readings.
2. **Phantom keypresses** — VK=0x00 inside condition padding and VK=0xFFFF at the `FF`-run terminator fire a flat keypress matcher; their Duration slots are 0.0 / NaN. Filter with the Duration floor (§9.2).
3. **`Equals` = 0 and Small Integer type = 0** — both alias zero padding; a flat scan cannot tell an `Equals`/`Small-Int` condition from a Say-text token or padding. Only the object walk is reliable.
4. **Pool var-ref vs. compare** — the shared `[01][len][name][01]` wrapper (§8.3) means a global name search lands on the declaration pool, not the compare.
5. **Profile-record pseudo-command** — the profile record @368 matches the command-envelope signature and walks as a fake command unless explicitly excluded (85 apparent envelope violations in base profile all traced to this).
6. **Chord miss** — matchers keyed on the 8-byte single-key marker miss every chorded keypress (m[5] count ≠ 1).
7. **Sentinel aliasing on operands** — integer −1 ≡ 0xFFFFFFFF and Text-absent ≡ '' (§8.3); type-gate before declaring a field unset.

## 12. Confidence summary & open questions

Closed [SOLID]: container/compression; primitives incl. GUID endianness and the 16-byte .NET Decimal; header fields @0/@4/@0x170+ and offset-table entries 0–2; command envelope and actionCount; the action-object envelope (fixed 34 members, offset-deref rule, head chaining, fixed heap-header offsets, m[0]=32, m[1]=GUID); 35 ActionType codes incl. KeyDown/Up/Toggle as distinct types, Launch/Say/SetClipboard/dictation/listening (Probe B); the condition system (value-type codes, all four operator dropdowns, per-type operand slots m[7]/m[21]/m[25], pairing semantics generalized to all block actions, m[18] ordinal, IndentLevel derived-not-stored); Set-action field map incl. the value-source-mode model (m[14]) and arithmetic-operator enum (m[20], modes 8/9 only) (Text/Bool/Int/Dec + targets); Set-Boolean value-vs-order confound (Probe B: value, not order); Set-Small-Int MOOT in VA2 (merges into Set Integer; code 18 legacy/decode-only); mouse click duration (m[4]), scroll click count (m[3], superseding the old −20 claim), cursor Move (m[11]/m[12]); Pause duration m[3]; keypress Duration/KeyCodes slots; the structural constants; all seven hazards.

Open, routed:

| # | item | state | route |
|---|------|-------|-------|
| 6 | Compound m[31] record format; m[18]-as-ConditionGroup | de-scoped 2026-07-08 | **PARKED** (decode-only contract §8.6) |
| 7 | Header @8 offset-table entries 3+ / command-list index (trailing ~size−530 region) | undecoded | **PARKED** (discovery stays scan-based) |
| 8 | ~24 near-constant member slots; m[23] FFFF/0 flag outside Set-Integer; m[0]=32 meaning; m[27..28] 9-byte structure; m[12]'s secondary =1 flag on Set-Integer arithmetic modes | unmapped constants | **PARKED** |
| 9 | Command trailing region: category string, description, flag bytes | category located, structure unmapped | **PARKED** (V2 uses walk-bounded category read) |
| 10 | Local-var declaration pool anchor | wrapper known | **PARKED** |
| 11 | Unattributed census ActionType codes | Probe B's named targets are all closed (3, 13, 24, 25, 26, 27, 50, 51 — see §9.1); v0.2's five-profile census saw 40 distinct m[2] values against which 35 are now attributed by name (§9.1's table), leaving residue whose exact count is unconfirmed (§9.1 flags that Probe B's 3/13 may or may not overlap that original 40 — not independently re-verified) | **PARKED** (residue — no further probe planned) |
| 12 | Set-Integer value-source modes 2, 3 | dropdown positions not built in Probe B's sweep | **PARKED** |
| 13 | Set Small Int (code 18) own field layout | cannot be re-sampled from a VA2 build (VA2 UI no longer emits it) | **PARKED** (decode-only if an old profile is ever seen) |
| 14 | Write color/shape parameters | one sample at UI defaults; no nonzero slot found beyond m[6] | **PARKED** (minor) |
| 15 | Set-Integer m[19]/m[23]/m[16] "stale operand" hazard on modes 5/6/7 | PLAUSIBLE, single-sample, not independently confirmed by an A/B rebuild | **PARKED** |
| 16 | Mouse `SPECIAL` context and the other 30 unswept button×action code combinations | scheme SOLID by construction; individual combinations beyond LC/LDC/RC/SF/Move/SPECIAL untested | **PARKED** |

## 13. Reference decoder algorithm  [corrected — review §2.3 applied]

Do NOT flat-scan. Walk the tree, and DEREF every member slot:

```
buf = raw_deflate_decompress(file)                      # zlib -15
profile = read_profile_header(buf)                      # §6.1; exclude the @368 pseudo-command (§11.5)
for each command:                                        # §6.2 (discovery scan-based, §12 #7)
    read GUID, phraseLen, phrase, actionCount
    arr = position after actionCount
    for k in range(actionCount):                         # §6.3
        head = u32(arr)
        m    = [u32(arr + 4 + 4*i) for i in 0..33]       # FIXED 34 — offsets, not values
        deref = lambda i, ty: read(ty, arr + m[i])       # per-slot type from §6.4
        atype = deref(2, u32)                            # ActionType code
        if atype in {19, 63, 30}:                        # Begin / Else If / Begin Loop While = a compare
            vtype = deref(24, u32)                       # gate operand slot on vtype (§8.3)
            op    = deref(20, u32)
            left  = deref(19, string)
            right = deref(7, string) if vtype == 1 else \
                    deref(25, decimal16) if vtype == 4 else deref(21, i32)
            # compound: if sub-count at m[31] > 1, emit decode-only marker (§8.6)
        else:
            decode_action(atype, deref)                  # §9 — 0=PressKey (m[3] duration, m[5] keycodes), …
        arr = arr + head                                 # next sibling
```

Landmark self-test (zoom-if-else, decompressed 3111 B): profile Id @368; command Id @750; phrase `zoom [out; in]` @770; actionCount 5 @784; action[0] array @788, head 347 → action[1] @1135; deref m[20] → @1042 = 6 (`Contains`), deref m[19] → @1023 = `{LASTSPOKENCMD}`, deref m[7] → @972 = `out`. Census gate: 1,603 objects across the five profiles, every one m[0]=32 and m[1]=140, set-fire chains 37/37. A correct implementation reproduces every one of these. [SOLID]
