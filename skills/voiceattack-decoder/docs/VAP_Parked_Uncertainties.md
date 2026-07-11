# VAP Parked Uncertainties Register

Status: committed 2026-07-11, Phase 2 exit criteria (`Execution_Plan_2026-07-09.md`). Every item below is the resume-cold writeup for an OPEN item routed to PARKED in `VAP_Format_Specification.md` v0.3 §12. Nothing here blocks decoder V2 or the encoder — each item is either invisible to a correct decode (a decoder that ignores it produces identical output for every profile in evidence) or explicitly contracted as a decode-only/opaque marker. This register exists so a future session can pick any one item up without re-reading the whole research history.

Format per item: what it is, what's known, what evidence exists, what would close it.

---

## 1. Compound condition `m[31]` interior record format

**What it is.** A compound `Begin Condition` (`(A AND B) OR (C AND D)`) is a single action object holding multiple sub-compares. The normal single-compare member map (m[19]/m[20]/m[21]/m[7]/m[25] for the first sub-compare) undercounts anything beyond that first sub-condition; the rest live in a region m[31] points at.

**What's known.** m[31] derefs to a scalar = sub-condition count (2 observed on corinthian's `(return to main screen)` command, one object @29797, head=579 vs ~340 for a simple compare). A second literal (`'station services'`) was located inside the inflated heap region past the normal slots, consistent with a second sub-compare living there, but its field layout (operator, value-type, operand slots, AND/OR conjunction marker) is undecoded.

**Evidence.** `VAP_Format_Specification.md` §8.6; corinthian-4-Profile.vap, command `(return to main screen)` @29797.

**Decode contract (already in force, not blocked by this item).** Emit the first sub-compare using the normal member map, plus an explicit `compound: n sub-conditions, undecoded` marker. Never silently drop the extra sub-conditions.

**What would close it.** A profile with a single compound Begin Condition, 2 sub-conditions, both self-labeling and maximally distinct (different value-types, different operators, one AND one OR variant built separately) — then a byte-diff between the compound object and an equivalent pair of nested simple Begins to isolate exactly which bytes encode the second sub-compare and the conjunction operator. Scoped out of Probe B by the 2026-07-08 ruling (Probe A dropped); would need a dedicated Probe C if ever prioritized. Not required for V2 acceptance — compound support stays decode-only by design (§8.6).

---

## 2. Header `@8` offset-table entries 3+ / command-list index

**What it is.** The file header's top-level offset table at `@0x0008` has entries 0/1/2 resolved (profile record, profile name, command count). Entries 3+ point into a trailing region roughly `size − 530` bytes from the end of the file, which likely holds a per-command index (offsets to each command envelope) but the record format there is undecoded.

**What's known.** Entries 0–2 are SOLID (§6.1). The trailing region's existence and rough size are known; its internal structure is not.

**Evidence.** `VAP_Format_Specification.md` §6.1; observed across all six evidence-base profiles including Probe B's `u32s after profile name: [10, 1281, 82, 340, 356, 375, 1043, 1044]` (10 = command count, the rest are unresolved offset-table entries).

**Why it doesn't block anything.** Command discovery works today via the scan-based walk (§13): find the profile record, then scan for command-envelope signatures (GUID + phrase + actionCount) rather than following an index. This is slower and has one known hazard (the profile record itself matches the command-envelope signature and must be excluded, §11.5) but is otherwise reliable — 1,635 objects across six profiles, zero structural exceptions.

**What would close it.** Take a profile with a known, small, exact command count and byte-diff the trailing region against the command list's actual byte offsets, looking for a table of u32 offsets whose count matches the command count. Low priority — closing it would only be a performance/robustness improvement to discovery, not a new capability.

---

## 3. ~24 unmapped near-constant member slots (incl. `m[23]`'s flag meaning outside Set-Integer)

**What it is.** Of the 34 member slots in the `CommandAction` envelope, roughly 24 are near-constant (0x00000000 or 0xFFFFFFFF) across the full census and have no established semantic meaning. `m[23]` is the most\-investigated: outside Set-Integer it's a binary flag, ≡0xFFFFFFFF on 1,359 objects and ≡0 on 244 (v0.2 census), with no established meaning; Probe B found a THIRD reading — on Set-Integer's random value-source mode, m[23] is a length-prefixed string holding the max bound (`'9'`).

**What's known.** The dead/constant slots: `m[10]≡0xFFFFFFFF`; `m[22]`, `m[26]`, `m[32]`, `m[33]≡0` across the census — these look like genuinely unused padding, not encoding anything. `m[23]`'s FFFF/0 split (outside Set-Integer) is NOT yet correlated with anything — not ActionType, not value-type, not command position. `m[12]` also picked up a new open thread from Probe B: on Set-Integer arithmetic modes (8/9) it reads `=1` alongside the operand in m[11], a secondary flag whose meaning wasn't isolated (§6.4).

**Evidence.** `VAP_Format_Specification.md` §6.4 (dead-slot row), §12 item 8; Phase 1 census in `VAP_Uncertainty_Closure_Table.md`.

**What would close it.** A per-slot correlation pass across a much larger, more structurally diverse profile corpus (corinthian-scale or larger) looking for any slot whose FFFF/0 (or nonzero) pattern lines up with a feature not yet modeled — e.g. IsSuffixAction, a per-command flag, or a UI-only setting that doesn't affect execution. Given 1,635 census objects have not surfaced a correlation, this is a low-yield, low-priority item; most likely outcome is these slots are genuinely inert (reserved/padding) and this item closes by exhaustion rather than a positive finding.

---

## 4. Command trailing region: category string, description, flag bytes

**What it is.** After a command's action-object chain ends, a trailing region holds at minimum the category string (used by decoder v1's category heuristic) and, per Probe B, command description text (e.g. `"Smallint merged with Int in VA 2"`, `"Runs 'Write a value tthe event log'"`) and the optional `2.1.8` version string. The full record structure (field order, length prefixes, flag bytes between strings) is not mapped.

**What's known.** The category string is locatable by a walk-bounded scan of the region between the end of the last action object and the start of the next command envelope (V2's approach — §12 item 9 note). Probe B reconfirmed this pattern on all 10 of its commands: each command's distinct category (`say`, `write`, `launch`, `clip`, `boolOrder`, `setIntSweep`, `setSmall`, `setDec`, `mouse`, `dictation`) was found in the trailing region, plus description strings where the user set them, plus the version string on the last command only.

**Evidence.** `VAP_Format_Specification.md` §6.2, §12 item 9; Probe B walk (all 10 trailing-region string dumps).

**Why it doesn't block V2.** Walk-bounded category extraction already works without knowing the full record structure — decoder V2 can keep using scan-within-bounds rather than a byte-exact field map.

**What would close it.** Byte-diff the trailing region across several commands with deliberately varied category-string length, description presence/absence, and version-string presence/absence, to isolate length prefixes and any flag bytes between the fields. Not required for any planned V2 or encoder feature; low priority.

---

## 5. Local-variable declaration pool anchor

**What it is.** Pool-local variables (declared once, referenced by name from multiple compares/Set actions) are wrapped as `[01 00 00 00][u32 len][name][01 00 00 00]` — this wrapper is shared between the pool declaration itself and any compare/Set action that references the name, so a naive string search can't distinguish "this is where the variable is declared" from "this is where it's used." Where the pool record itself lives (per-command trailing region vs. profile-level) is unresolved.

**What's known.** The wrapper format is SOLID. The object walk sidesteps the ambiguity entirely: every compare or Set action resolves its own operand/target name from within its own action object (m[19], m[6], m[15], m[16]) via the offset-deref rule, without ever needing to find the pool's anchor. This is why the item is parked rather than blocking — it doesn't matter where the pool lives if nothing in the decode path needs to visit it.

**Evidence.** `VAP_Format_Specification.md` §8.3 (wrapper), §12 item 10.

**What would close it.** Only relevant if a future feature needs a manifest of all declared variables independent of where they're used (e.g. an encoder that wants to declare unused variables, or a decoder feature that reports "variables never referenced"). If that need arises: search a profile for all instances of the wrapper pattern, cross-reference against every m[19]/m[6]/m[15]/m[16] resolved name across the whole profile, and see which wrapper instances are NOT reachable from any action object — those are the pool declarations. Not currently on any roadmap.

---

## 6. Write action color/shape parameters

**What it is.** VoiceAttack's Write UI exposes color and shape options (e.g. `[Blue]`, `[Square]`) alongside the text. Whether/where these are encoded in the binary is unknown.

**What's known.** Probe B's `write test` command (ActionType 23, ActionType confirmed SOLID) used UI defaults for color and shape. A full raw dump of all 34 member slots on that action found nothing populated beyond `m[6]` (the text, `'write-marker'`) and the universal `m[27]`/`m[28]` structural constants — every other slot read its usual dead/default value. With one sample at default settings, this is indistinguishable between "color/shape isn't stored at all (always derived/default at render time)" and "color/shape is stored but happens to default to the zero/FFFF pattern already accounted for by other fields."

**Evidence.** `VAP_Format_Specification.md` §9.4 (Write); Probe B walk, `write test` @16874, full 34-slot raw dump.

**What would close it.** One Write action built with a NON-default color and shape (e.g. `[Red]`, `[Circle]`), object-walked and diffed against the default-build's slot values. Minor priority — doesn't block V2 (Write text decodes cleanly regardless; color/shape would be an additive field if found).

---

## 7. Set-Integer value-source modes 2 and 3

**What it is.** The Set-Integer `m[14]` value-source-mode enum (§9.4) has confirmed codes 0, 1, 4, 5, 6, 7, 8, 9. Codes 2 and 3 were never built in Probe B's `set int sweep` command and remain unobserved.

**What's known.** The dropdown almost certainly has entries at those positions (the screenshotted order wasn't captured for Set-Integer the way it was for Set-Boolean — only the resulting m[14] values were read back from the 12 built actions, which skipped positions 2 and 3). Best guess based on the VoiceAttack UI's typical Set-Integer dropdown ordering (Value, Random, [Increment/Decrement?], [Toggle-adjacent?], Another Variable, Not Set, Converted Text, Saved Value, Arithmetic-Literal, Arithmetic-Variable) is speculative and NOT recorded as a spec claim.

**Evidence.** `VAP_Format_Specification.md` §9.4 (value-source-mode table, "2, 3 unobserved"); Probe B `set int sweep`, actions `siv0`..`siv11`.

**What would close it.** Two more Set-Integer actions built at the skipped dropdown positions, screenshotted for the exact labels, self-labeling target vars, object-walked. Cheap to close whenever another VoiceAttack session is available — bundle with item 6 (Write color/shape) if a Probe C is ever opened, since both are single cheap builds.

---

## 8. Set-Integer stale-operand-slot hazard (modes 5/6/7)

**What it is.** In the `set int sweep` walk, the mode-5 ("Not Set") action still had m[19]='0'/m[23]='9' populated (the random-bounds strings from mode 1), and mode-6 and mode-7 actions both had m[16]='[integer_text]' populated identically, even though mode 7 ("saved value") shouldn't need a text-var reference the way mode 6 ("converted value of a text var") does.

**What's known.** The leading hypothesis is that VoiceAttack's UI does not clear a field's stored value when the user switches the value-source dropdown away from the option that used it — so these are leftover bytes from whichever dropdown position was visited earlier during the same UI session, not meaningful at the action's final m[14] mode. This is PLAUSIBLE only: it rests on a single build sequence, not an A/B test that deliberately visits and reverts dropdown positions on the same variable to confirm staleness vs. a real (if redundant) encoding.

**Evidence.** `VAP_Format_Specification.md` §6.4 ("Decoder hazard — stale secondary-operand slots"); Probe B `set int sweep`, actions `siv3` (mode 5), `siv4`/`siv5` (modes 6/7).

**Decode contract (already in force).** Every Set-Integer operand read MUST gate on m[14] (the mode); a decoder must never infer the mode from which operand slots happen to be populated, and must never surface m[16]/m[19]/m[23] as meaningful when m[14] doesn't call for them.

**What would close it.** Build one Set-Integer action, set it to mode 1 (random, populating m[19]/m[23]), then in the SAME UI session switch it to mode 5 ("Not Set") before saving, and check whether the exported bytes still carry the mode-1 strings. If yes, staleness confirmed as a genuine UI behavior (not export-order artifact). Low priority — the decode contract already treats this safely regardless of the underlying cause.

---

## 9. Mouse `SPECIAL` context and the untested button×action combinations

**What it is.** The mouse context-code scheme (5 buttons × 6 actions + 4 scrolls = 34 derivable codes, `schema/vap_capability_dictionary.json` `mouse` block) is SOLID by construction of the naming scheme itself, and Probe B spot-checked 4 of the 34 plus the new `Move` context — all matched. A cross-check walk of `corinthian-4-Profile.vap`'s 9 real-world mouse actions turned up a context string NOT in the 34-code scheme at all: `SPECIAL`, carrying a populated `m[7]` parameter (`'Application Center'`, apparently a window/element target name).

**What's known.** `SPECIAL` exists as a real context code in at least one production profile. Its full semantics — what UI action produces it, what other parameter strings it can carry, whether there are other non-click/scroll/move context codes beyond `SPECIAL` and `Move` — are unexplored. The other 30 of the 34 derived button×action codes (everything except `LC`, `LDC`, `RC`, `SF`) were not individually re-walked in Probe B; they're accepted on the strength of the naming scheme's internal consistency, not independent per-code verification.

**Evidence.** `VAP_Format_Specification.md` §9.3; Probe B mouse sweep (`LC`, `LDC`, `RC`, `SF`, `Move`); corinthian-4-Profile.vap mouse-action cross-check (contexts observed: `LC`×3, `Move`×3, `MD`, `MU`, `SPECIAL`×1).

**What would close it.** (a) For the 30 untested button×action combinations: low priority, the naming scheme is regular and mechanical enough that spot-checking 4/34 plus Move gives reasonable confidence — only worth closing exhaustively if a decode ever produces a code from that set that doesn't match expectations. (b) For `SPECIAL`: identify which VoiceAttack UI mouse action produces it (candidate: "Move mouse to a specific window/control" or similar targeting action, distinct from the X/Y coordinate `Move`) and build 2-3 samples with different self-labeling target strings to confirm the m[7] parameter's role and check for any other populated slots.

---

## Closed by Probe B (2026-07-11) — reference only, not open

For completeness, everything Probe B DID close (see `VAP_Format_Specification.md` v0.3 for the authoritative writeups; not reproduced here): ActionTypes 3 (Launch), 13 (Say), 24 (SetClipboard, refuting the old PasteDictation attribution), 25/26/27 (dictation mode, promoted to SOLID), 50/51 (Start/Stop Listening); the Set-action value-source-mode model (m[14]) and arithmetic-operator enum (m[20], modes 8/9 only); the Set-Boolean value-vs-order confound (m[14] is the value: 0=True/1=False); Set-Small-Int's mootness in VoiceAttack 2 (merges into Set Integer, code 18 kept legacy/decode-only); mouse click duration (m[4]), scroll click count (m[3], superseding the old "-20 from length prefix" claim), and the cursor-Move context (m[11]/m[12]).
