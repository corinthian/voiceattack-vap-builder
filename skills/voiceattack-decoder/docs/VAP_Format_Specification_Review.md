# VAP Format Specification v0.1 — Verification Review

> **HISTORICAL (2026-07-09).** All corrections and findings in this review are folded into `VAP_Format_Specification.md` v0.2, which alone is authoritative. This file is retained as the evidence trail for the v0.1→v0.2 corrections.

Response paper to `VAP_Format_Specification.md` (draft 0.1, 2026-07-08). Every byte-testable claim was re-executed against the five reference binaries and the CSV oracles by an independent harness (scratchpad `spec_verify1–6.py`), not by re-reading the prior docs. Walk coverage: 1,601 action objects across all commands of all five profiles (zoom 5, numkeys 16, conditionals 111, corinthian 1,166, base profile 303) — every object chained cleanly, every one read m[1]=140, none had a backward member offset.

**Overall verdict: the core of the spec is correct and strongly confirmed.** The object model (§6) — fixed 34-member offset array, array-start base, head-as-length chaining, actionCount as chain length — survives every test, including the two hardest cases (set-fire's 37-action chain, the compound-condition object). The operator enums, value-type codes, pairing semantics, and block ordinal all reproduce exactly. But the review found one refuted claim, one materially incomplete section, a broken reference algorithm, and several imprecise [SOLID] tags. Fix §8.3 and §13 before anyone implements against this document.

## 1. Confirmed — safe to implement (re-verified independently)

- **§3 container + §2 sizes.** All five profiles decompress with `zlib.decompress(data, -15)` to exactly the stated sizes.
- **§6.1 header — stronger than its [INFERRED] tag.** In ALL five profiles: u32@0 = total decompressed size, u32@4 = 0x59, profile name length@0x180 + name@0x184. The spec verified this only in zoom; it holds everywhere sampled and can be promoted (the @8 field and command-list indexing stay [OPEN]).
- **§6.2 command envelope + the actionCount correction.** zoom landmarks reproduce byte-for-byte (GUID @750 = `7e38f126-2a11-4418-b0e3-1e064917e1d6`, phraseLen 14 @766, actionCount 5 @784, action[0] @788). Decisive new evidence for the "offset table was a misread" correction: corinthian set-fire's raw actionCount is 37 and **37 objects chain cleanly** to 1,364 bytes before the next command (`spec_verify4.py`). The old "35-entry offset table" was `[head][m0..m33]` = 35 u32s, and the "child GUID read as offsets ≥ n" was action[0]'s own m[1] sub-object GUID at heap start. The correction fully dissolves the decoder's Finding-1 anomaly; the CSV confirms 37 actions.
- **§6.3 object envelope.** head = length = next-sibling pointer: all 1,601 objects across all profiles chain within bounds and land before the next command. Fixed 34 members: m[1] = 140 (= 4 + 34×4 = heap start) with zero exceptions. Keypress template head = 331 confirmed (numkeys). Caveat: 85 apparent m[1]≠140 objects in base profile all traced to the profile-header record @368 matching the command signature and being walked as a pseudo-command — a detection artifact worth a §11 hazard note, not an envelope failure.
- **§8.2 operator enums — all four, closed.** The rebuilt conditionals profile sweeps read m[20] in exact dropdown order: Text 0–9 (self-labeling literals in m[7] match), Integer 0–7, Boolean 0–3, Small Integer 0–7 as Else-If chain. Cross-profile CSV anchors: corinthian `[throt] Does Not Equal ±1..±4` → 1, `Is Less Than 2` → 2, `Is Greater Than 0` (Loop While) → 4, Small-Int `[i] Is Greater Than 2/3` → 4, zoom Contains → 6.
- **§8.1 value-type m[24].** 0=Small-Int, 1=Text, 2=Bool, 3=Int, 4=Decimal all reproduce at the cited commands; inline non-Text token typing confirmed (`{EDDI entered signal source threat}` compare reads m[24]=3); the Small-Int-reads-0 caveat is real and correctly stated.
- **§8.4 pairing m[17].** Every cited value reproduces: zoom 2/4; jumped 9→14, 10→13, closers 14→9, 13→10; climb Begin→3, ElseIf→8. New supporting data: Else also carries pairing (climb a8→10), Loop While→End Loop and back (a11→16, 16→11), and in an Else-If chain the End points back to the ORIGINAL Begin (boolean a9→1), not the last Else If.
- **§8.5 m[18] ordinal.** Sequences reproduce exactly (nested+decimal 1,2,3,3,4,5,6,7,8; Text sweep 1..10; boolean 1,1,1,1). One gap in the write-up: the boolean and small-int evidence only fits because those commands are single Begin/Else-If chains — the spec never says so, and a reader can't tell 1,1,1,1 supports the model rather than contradicting it. State the build structure with the evidence. The "don't implement as ConditionGroup yet" restraint is correct.
- **§8.6 compound conditions.** Every number verified: single object @29797, head 579, m[2]=19, m[7]='none', m[20]=0, m[31] offset 343 with scalar 2, second literal `station services` at abs 30324 inside the object. The undercount warning is right.
- **§8.7 IndentLevel not in the table.** Independently reproduced with a per-slot u32 diff: outer Begin vs nested Begin differ in exactly {m[1] GUID, m[17], m[18], m[20]} — the spec's list, precisely. No member encodes depth.
- **§6.4 gate rule.** m[2] ∈ {19, 63, 30} as the compare gate is consistent across all walks; the m[20]-is-shared gotcha is real (Set-integer actions read set-op codes there — climb: "value to 99"→0, "converted value of {CMDSEGMENT:2}"→4, "minus 1"→1).
- **§9.1 ActionType codes.** Climb's 17-action m[2] sequence [17,19,37,63,37,19,37,20,29,37,20,30,23,0,37,2,31] matches its CSV action list position-for-position, upgrading 17 Kill, 23 Write, 2 Pause, 29 Else, 30/31 Loop to CSV-confirmed. 0 PressKey, 19/20/63, 36/37 all reconfirmed.
- **§9.2 keypress.** Duration double at marker−12 (=1.5 zoom), VK at marker+8, head 331, d==0.0 for KeyDown/KeyUp — all hold. Better: the flat facts collapse into member slots — **Duration is m[3]** (double), and the "marker" is m[4]'s trailing zeros + m[5]'s value (see §2.4 below).
- **§11 hazards.** All four reproduce mechanically; the phantom-VK and Equals-0 aliasing behaviors are as described.

## 2. Errors and corrections (ranked)

### 2.1 §8.3 Decimal encoding — REFUTED
The [INFERRED] claim "Decimal → IEEE-754 double (matches the Duration encoding)" is wrong. No IEEE double of 5.43/4.32/3.14 exists anywhere in the compare objects. The value is a **16-byte .NET System.Decimal at m[25]**, field order flags, hi, lo, mid (the CLR's internal layout): 5.43 = flags 0x00020000 (scale 2), lo 543; 4.32 = lo 432; Set-Decimal's 3.14 = lo 314 in the same slot (`spec_verify5.py`). This is exactly the trap the confidence legend exists for — the [INFERRED] tag did its job, but the "matches Duration" rationale was reasoning by analogy, not bytes.

### 2.2 §8.3 / §6.4 right operand — materially incomplete
"m[7] = ConditionStartValue (right operand)" holds for **Text only**. On every Integer, Small-Integer, Boolean, and Decimal compare in the sweep profile, m[7] derefs to 0xFFFFFFFF. The numeric/boolean right operand is **m[21] as i32**: throttle compares read 1/2/3/4, reverse compares read −1/−2/−3/−4 (0xFFFFFFFF..0xFFFFFFFC), Small-Int reads 2/3, corinthian `[submit] Equals True` reads 1. The spec's own flat-scan citation ("+580 in the throttle family") is this slot. Two follow-on hazards the spec must state: (a) integer value −1 in m[21] is byte-identical to the absent sentinel — type-gate on m[24] before deciding a field is unset; (b) Text Has/Has-Not-Been-Set reads m[7]='' (empty string), not 0xFFFFFFFF, so "absent" encodes differently per type.

### 2.3 §13 reference algorithm — broken as written
Member slots are offsets, always; every field read requires `value = deref(arrayStart + members[i])`. The pseudocode reads slots as immediate values — `if members[2] in {19, 63, 30}` compares an offset (~156) against ActionType codes and never fires; `operator=members[20]` yields ~254, not 0–9. §6.3 rule 2 states the base correctly and the landmark table derefs correctly, but §6.4's table talks in value-language ("m[5]: 1 for PressKey") without saying deref, and the algorithm codifies the confusion. A conforming implementation also needs per-slot width/type (u32 vs i32 vs double vs 16-byte decimal vs length-prefixed string vs GUID), which the spec nowhere tabulates.

### 2.4 §6.4 m[5] — not a marker, the KeyCodes list
m[5] is `[u32 count][count × u16 VK]`. Chorded corinthian keypresses read count 2–3 with the full VK list ([162,164,69] = LCtrl+LAlt+E; [161,70] = RShift+F). "1 for PressKey actions" is the single-key special case; the flat scan's `00000000 01000000` marker is m[4]'s zero tail + count=1. Decoder implication the spec should flag: any matcher keyed on that 8-byte pattern **silently misses every chorded keypress** (count ≠ 1) — a live gap in `vap_decoder.py`'s CSV-validated output, since key comparison passed on single-key commands.

### 2.5 §2 evidence base — version-string claim false for 2 of 5 profiles
"`2.1.8` appears in each" — it appears in zoom, conditionals, and corinthian only; numkeys and base profile contain no such string. Whatever the field is, it is optional, which weakens any use of it as a format-version anchor.

### 2.6 §10 "three GUIDs per command" — wrong as stated
zoom's single command carries its command GUID plus **five distinct per-action m[1] GUIDs**. GUID count scales as 1 + actionCount (at least); "three per command, each occurring once" describes nothing observed and cites a prior-doc claim that the object walk has since superseded. Delete or restate.

### 2.7 §6.4 / §10 m[27]/m[28] — off by one
Deref of m[27]/m[28] yields 0x886E0900, not 0xF1886E09: the slot's data begins with a 0x00 byte and the constant sits at deref+1 (`[00][09 6e 88 f1][ff ff ff ff]`). The constant's recurrence is real; the claim "m[27], m[28] = constant" is not literally true and will fail an equality test in code.

### 2.8 §9.2 "VK at command-rel 209" — accidental constant
Verified for numkeys — but only because every simple numkeys phrase is 5 characters. The command-relative offset is phrase-length-dependent (20 + len + 4 + 4 + 136 + 45 of heap); the array-relative position is what's stable. Presenting 209 as a template fact invites breakage on any other profile.

### 2.9 §6.4 gotcha gloss — set-op codes don't track CSV wording
climb's "value to the converted value of {CMDSEGMENT:2}" reads m[20]=4, but jumped's "value to the converted value of {INT:System visits}" reads m[20]=0. The shared-slot warning stands; the parenthetical code glosses ("4 = to converted value") should not be trusted as an enum until the Set-Integer value-source dropdown is swept.

## 3. New findings from this review (candidate spec additions)

- **ActionType codes:** 21 = Set Text (set-fire + Text-sweep Set actions), 22 = Execute External Plugin (set-fire a36), 38 = Set Decimal. All CSV-positional.
- **Set-action field map is disjoint from the condition map:** Set-Integer stores its literal in **m[11]** (climb's 99), not m[21]; Set-Decimal uses m[25]; Set-Text uses m[7]; Set-Boolean's True/False is none of the u32 slots (unresolved). **m[6] = Set-action target variable name** ('boo', 'bbq' both pointed to by m[6]). General lesson for §6.4: member semantics are ActionType-polymorphic — the table should be labeled "compare/keypress actions" until other types are swept.
- **m[0] = 32 in every object of every profile** — constant, meaning unknown; worth recording next to head/nmembers.
- Else and Loop actions carry pairing links too (§8.4 can generalize from "Begin/Else If" to all block actions).

## 4. Untested by this review

§9.3 mouse actions (flat-scan legacy, no re-verification here); §6.1's @8 field; the XML container branch; ActionType 16 (Execute Command); Launch/Say/SetClipboard layouts; the ~24 unmapped slots beyond the additions above. These keep their existing tags.

## 5. Methodological notes

The confidence legend is honest and mostly well-applied; both refutations landed on [INFERRED]/[OPEN] items, which is the system working. Three process weaknesses: (1) [SOLID] was occasionally granted to restatements of prior-doc flat-scan claims without object-walk re-verification (§10 GUIDs, §9.2's 209, §2's version string) — "read directly from ≥2 profiles" should mean re-read, not re-cited; (2) offset conventions are mixed silently (§6.2 cites GUID start, §8.1 cites phrase start = GUID+20) — one command-position convention should be declared; (3) evidence rows sometimes omit the build structure that makes them evidence (§8.5's boolean 1,1,1,1 is only confirmatory because that command is one Else-If chain).

**Recommendation:** apply §2.1–§2.4 before any implementation work; the rest are wording-level. With those fixes, §6 + §8 + §9.1/9.2 are a sound basis for rewriting `vap_decoder.py` as a tree walker — which this review's harness effectively prototyped: the walk decoded all 201 corinthian commands, both compound conditions, and every sweep without a single structural exception.
