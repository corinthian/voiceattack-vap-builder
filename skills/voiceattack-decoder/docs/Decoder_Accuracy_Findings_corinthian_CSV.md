# Decoder Accuracy Findings — corinthian CSV Oracle

First measurement of the decoder against ground truth. VoiceAttack cannot export XML, but its **CSV export** lists every command's category and full action sequence in English. Paired with the binary `.vap`, it is a validation oracle. Source pair (both gitignored, local only): `reference profiles/corinthian-4-Profile.vap` + `reference profiles/corinthian-4-Profile.csv`.

## Method

The CSV expands VoiceAttack's dynamic-phrase syntax — `[select;target] wing target`, `inch forward [1..4;]` — into one row per spoken permutation. So 200 raw decoder commands ↔ 479 CSV rows. A phrase-expander (`scratchpad/expand_match.py`) reproduces the expansion and matches every CSV row to its owning command: **443/479 rows matched, 0 ambiguous**. The 36 unmatched all trace to one dropped command (Finding 1); 8 decoder commands are legit but absent from this CSV export (dictation/listening/course-home/`((EDDI docked))` — the export is a filtered subset), not bugs. On the ~192 matched commands, category (CSV field 5) and keypress key/duration were compared per-command.

## Findings (all CSV-confirmed)

### 1. One real command silently dropped — `_match_command_signature` line 299
`set [weapon; hardpoint; hardpoints; weapons] [one; two;] [single; long; continuous] fire` (36 spoken forms). Phrase present in binary @465836, valid GUID, 37 actions. Rejected by `if any(o >= n for o in offsets): return None`. Root cause: `count` (37) exceeds the true offset-table length (35). Reading `count×4` bytes overruns into the first child action-object's GUID; its high bytes (`0x14dadb95`, `0x4d9e4a42` — literally the child GUID `95 db da 14 42 4a 9e 4d…`) read as offsets ≥ n and nuke the whole command. `count ≠ table-length` is specific to this command (197 others have count == clean-table-length). Blast radius on corinthian: exactly 1 command.
**Fix direction:** truncate the offset table at the first out-of-range offset and keep the command, rather than discarding it. Detection does not depend on the table (actions decode from `phrase_end`); an overrun that lands on `<n` garbage never dropped a command, so the rule stays well-scoped. Must verify no false positives on all profiles.

### 2. Category wrong for 36/192 (~19%) — `_extract_category` line 351
`if '\\' in s or '/' in s … : continue` discards any string containing `/` as a "path operand." But `flight/navigation` is a real category and contains `/`. It gets skipped; the extractor's last-string fallback then returns action text (`count`, `throt`, `say`), a key letter (`Z`, `X`, `l`), or an ExecuteCommand target-GUID stored as ASCII. Every one of the 36 failures is a slash-category. This is the first bulk test of the shipped category-anchor fix (4233a0e) — previously only zoom's `camera` (an easy count==table-length case) was oracle-checked.
**Fix direction (corrected on review 2026-07-07):** stop treating `/` as a path indicator for categories. Filter only strings that are actually paths: contain `\`, end in a file extension, or start with `*`. An earlier draft added "a no-space token with a slash" to the filter — self-defeating: `flight/navigation` is itself a no-space token with a slash, so that rule re-discards the exact category this fix exists to save. A bare `/` must never disqualify. Re-measure against the CSV after.

### 3. Phantom keypresses in ~19 conditional commands — `find_key_actions` line 175
The matcher keys on the 8-byte prefix `00 00 00 00 01 00 00 00` and reads a VK, but never verifies the trailing `00 00 FF FF FF…` padding its own docstring (lines 162–167) specifies. In conditional commands the bytes `01 00 00 00` recur as ConditionStartOperator / ActionType fields, so they are misread as keypresses with VK = adjacent bytes — mouse-button codes 1/2/4 and out-of-range 256. Example: `jump to hyperspace` decodes `[256, 1, 4, J]` (only `J` is real); `request clearance` decodes `[2, 1, 4, 1, X]`. The real key survives; the phantoms are extra. (VK 8 = Backspace in `dismiss` is legitimate, not a phantom.)
**Fix direction (corrected on review 2026-07-07):** suffix verification is the wrong predicate. Real keypresses take two suffix shapes: zoom/numkeys read `VK 00 | 00 00 00 00 | FF FF…` (the docstring's pattern), but corinthian's real keys read `VK 00 | FF FF…` — the FF run starts immediately, no zero padding. Requiring `00 00` at +10 rejects real corinthian keys (`j` @47044, `num /` @52272), and phantom VK=4 @43796 (`04 00 00 00 ff ff ff ff`) passes an FF-run test. Use Finding 4's Duration slot instead: a real keypress carries a sane double at marker−12 (0.03–1.5 observed across all reference profiles); phantom slots carry garbage. The test needs a floor, not `> 0` — phantom garbage includes positive denormals (~1e-304). `0.001 <= d <= 60` separates every real key from every phantom in the reference set.

### 4. Hold durations dropped entirely — `find_key_actions` output
Keypress dicts carry `type / vk_code / key` only — no duration. CSV commands say "hold for 1.5 seconds"; the conditional analysis located the 8-byte IEEE-754 Duration double at `marker − 12`. The decoder never surfaces it, so every "press and hold" is flattened to a bare press.
**Fix direction:** read the Duration double relative to the matched keypress and add it to the action dict.

### 5. One category anomaly (low priority)
corinthian `zoom out`: decoder `combat & targeting` vs CSV `Interface`. Single case; possibly an expander mis-match or a genuine extraction error. Note separately.

### 6. numkeys fallback categories are VK-aliased junk (found on review 2026-07-07 — outside the CSV oracle)
Re-running the decoder on `numkeys-Profile.vap`: six of seven commands decode category `m/j/n/o/k/i` — the keypress VK byte (0x6D/0x6A/0x6E/0x6F/0x6B/0x69) aliased as a length-1 string, the same one-byte-two-readings trap `VAP_Conditional_Command_Analysis.md` documents for the phantom `F`/`R` label strings. (`num lock`'s VK 0x90 is unprintable, so it correctly falls through to `uncategorized` — the likely true value for all seven.) No slash involved: this failure is independent of Finding 2, and the `/`-filter fix will not touch it. It is the fix plan's "weakest link" caveat (last-remaining-string selection) failing in-sample. No clean content-based patch; the durable fix is the structural member walk. Low priority — track, don't patch.

## Priority
2 (categories, 19% of commands) > 3 (phantom keys, ~19 commands) > 1 (one dropped command) > 4 (durations, quality) > 5/6 (single anomaly; aliased fallback categories). An earlier draft claimed Findings 1 and 2 share the count>table-length mechanism — wrong. Finding 2's GUID categories are ExecuteCommand target GUIDs picked up by the last-string fallback; no table overrun is involved, and Finding 1's count≠table-length is specific to one command. Table truncation helps Finding 1 only.

## Scope note
This is analysis. Applying any fix to `vap_decoder.py` requires explicit authorization. Fix prototypes belong in scratchpad and must be verified against all reference profiles (recovery **and** no new false-positive commands) before proposing application.

## Outcome (2026-07-07 — fixes authorized, implemented, verified)

Findings 1–4 are fixed in `vap_decoder.py`, following the scope note's path: scratchpad prototype → verification against all four reference profiles → applied to source → re-verified. Results against the CSV oracle:

- **479/479 rows matched** (was 443/479) — the set-fire command recovered; corinthian decodes 201 commands, matching the profile header's own count field.
- **Category mismatches 37 → 1** — only the zoom-out anomaly (Finding 5) remains.
- **Phantom keypresses 19 → 0**, with no real key lost on any profile.
- **48 hold durations decoded** (0.01–12.0s observed); JSON emits `duration` only when it differs from the 0.1 default, XML always.

Two discoveries during verification:

1. **KeyDown/KeyUp records share the keypress marker.** "Press down X key" / "Release X key" actions (boost, cease fire, `[press; hold]` pairs) match the same `00 00 00 00 01 00 00 00` marker with the Duration slot **exactly 0.0** (all-zero bytes) — so "01 = ActionType PressKey" is not the whole story; down/up records either share the type or the field isn't ActionType. The phantom filter therefore accepts d==0.0 only when the record suffix verifies (VK zero-padded then FF-terminated within 6 bytes); one condition-operand phantom (`(return to main screen)`'s `[01][len]"none"` wrapper) also carries an all-zero slot and is rejected by the suffix rule. These records still decode as generic `keypress` — typing them as KeyDown/KeyUp needs the structural walk.
2. **`find_mouse_actions` was nondeterministic** — it iterated the `MOUSE_CONTEXT_CODES` set, whose order is hash-randomized per process, so multi-mouse-action commands changed action order between runs. Fixed by sorting hits by byte position (also the positionally correct order).

Still open: Finding 5 (zoom-out anomaly) and Finding 6 (numkeys VK-aliased categories — unchanged by these fixes, awaits the structural member walk).
