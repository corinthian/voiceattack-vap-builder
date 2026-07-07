# VoiceAttack Schema — Project Status

_Last updated: 2026-07-07_

## Where we are

The decoder now detects commands structurally (no category whitelist) and reads the profile header correctly. As of this session it has, for the first time, been measured against **ground truth** — a VoiceAttack CSV export of the corinthian profile — which both validated the structural rewrite and surfaced four accuracy bugs plus real progress on decoding conditional (variable) commands.

Active branch: `feature/decode-conditional-actions`. Nothing pushed. Three files from this session are uncommitted (see Git state).

## The ground-truth breakthrough

VoiceAttack cannot export XML, but its **CSV export** lists every command's category and full English action sequence. Paired with the binary `.vap`, it is a validation oracle and a semi-matched pair for reverse-engineering. Local, gitignored pair:
`reference profiles/corinthian-4-Profile.vap` + `…-Profile.csv`.

The CSV expands VoiceAttack's dynamic-phrase syntax (`[select;target] wing target`, `inch forward [1..4;]`) into one row per spoken permutation, so 200 raw decoder commands ↔ 479 CSV rows. A phrase-expander reproduces the expansion and matches **443/479 rows, 0 ambiguous**.

## Decoder accuracy — 4 bugs found, all PARKED (documented, unfixed)

Full writeup: `skills/voiceattack-decoder/docs/Decoder_Accuracy_Findings_corinthian_CSV.md`. No decoder code has been touched — fixes await explicit authorization. Reviewed against the binaries 2026-07-07: all four bugs confirmed exactly, but the drafted fix directions for #1 (categories) and #2 (phantom keys) were flawed and are corrected in the findings doc, which also gains Finding 6 (numkeys VK-aliased fallback categories — the category fallback fails even with no slash involved).

1. **Categories wrong for 36/192 (~19%)** — of the 200 decoded commands, 8 are absent from the CSV export (it's a filtered subset), leaving ~192 comparable. `_extract_category` line 351 discards any string containing `/`, so the real category `flight/navigation` is thrown away and the fallback returns action text, a key letter, or a command-GUID. First bulk test of the shipped category-anchor fix; it fails on every slash-category. *(Highest priority; ~one-line fix.)*
2. **Phantom keypresses in ~19 conditional commands** — `find_key_actions` line 175 matches the `00000000 01000000` prefix and never validates what follows, so condition bytes read as keypresses with mouse-button VKs (1/2/4/256). Real key survives; the phantoms are extra (before or after it). *(Fix corrected on review: NOT the docstring-suffix check — real keys have two suffix shapes and a phantom passes it. Use the Duration-slot check at marker−12 with a floor; see findings doc.)*
3. **One command silently dropped** — `set [weapon;hardpoint;…] … fire` (36 spoken forms). `_match_command_signature` line 299 (`any(o >= n)`) nukes it because `count` (37) overruns the true 35-entry offset table into a child GUID. Fix: truncate the table at the first out-of-range offset, keep the command.
4. **Hold durations dropped entirely** — every "press and hold 1.5s" flattens to a bare press; `find_key_actions` never reads the Duration double.

## Condition (variable command) decoding — progress

Full writeup: `skills/voiceattack-decoder/docs/VAP_Conditional_Command_Analysis.md` (session update section).

**Cracked**
- **Near-twin diff is the working technique.** Diffing `throttle 25/50/75/100` (identical but for key + literal) pinpoints, relative to `phrase_end`: **+184 = keypress VK** (F1–F4) and **+580 = ConditionStartValue** (integer literal 1/2/3/4). Structure is byte-stable within a command family.
- **Contains = ConditionStartOperator code 1** — confirmed from **zoom** ground truth only. The corinthian `{LASTSPOKENCMD}`→1 correlation is confounded (that token is ~97% Contains) and is not cited as proof.
- **Two operand mechanisms.** Global tokens (`{LASTSPOKENCMD}`, `{TXT:}`, `{BOOL:}`) stored inline; local vars (`[throt]`, `[i]`) live in a declaration pool and are referenced via wrapper `[01][len][name][01]`.
- **Token-adjacency model is dead** — the `token−8` "subtype" slot takes 2,3,4,5,6,9,15,21 across corinthian; operator/subtype are object members at member-table offsets, not adjacent fields.

**Open** — the full operator enum (Equals, Starts With, Does Not Equal, Is Greater/Less Than, Has Not Been Set, Equals True/False), value-type, subtype codes, IndentLevel. Every clean route to a second operator's value hits the same wall: the variable-name anchor lands on the declaration pool, not the compare object. Stopped here per the stop-after-two-ambiguous-contrasts rule.

**The unlock (not yet attempted — a research build)**: dereference the shared command-member offsets (`[32,140,156,160]`, constant across zoom `[347,…]` and throttle `[331,…]`) to **walk action objects in order**, read each ActionType, match throttle's known 5-action sequence to fix the BeginCompare ActionType code, then read operator/type/subtype at consistent member offsets. Finds every condition across all commands and yields the full enum.

## Git state

- Branch: `feature/decode-conditional-actions`
- Commit stack: `4233a0e` (decoder fix + plan) → `01c9bbb` → `ca3a5c9` → `11986c6` → `c60647e` → `8148b07` (all docs)
- **Uncommitted this session:**
  - `M  skills/voiceattack-decoder/docs/VAP_Conditional_Command_Analysis.md` (session findings appended)
  - `?? skills/voiceattack-decoder/docs/Decoder_Accuracy_Findings_corinthian_CSV.md` (new bug report)
  - `?? Project_Status.md` (this doc, repo root)
- Reference profiles + CSV are gitignored (local only), consistent with keeping binaries out of Git.

## Open decisions

1. **Fund the action-graph walk** (path to the full condition enum) or bank Contains=1 + the diff technique and stop.
2. **Authorize the 4 decoder fixes** — recommended path is prototype + verify in scratchpad against all reference profiles (recovery AND no new false-positive commands) before editing `vap_decoder.py`. Priority: categories → phantom keys → dropped command → durations.
3. **Commit** the three uncommitted files on this branch.

## Key artifacts

- Decoder: `skills/voiceattack-decoder/scripts/vap_decoder.py`
- Bug report: `skills/voiceattack-decoder/docs/Decoder_Accuracy_Findings_corinthian_CSV.md`
- Condition analysis: `skills/voiceattack-decoder/docs/VAP_Conditional_Command_Analysis.md`
- Fix plan (already executed): `skills/voiceattack-decoder/docs/Decoder_Category_Anchor_Fix_Plan.md`
- Ground-truth pair (gitignored): `reference profiles/corinthian-4-Profile.{vap,csv}`, `reference profiles/zoom-if-else.vap` (anchors Contains=1), `reference profiles/Cities Skylines II-Profile.csv` + zoom screenshot
- Scratchpad prototypes (session): `expand_match.py`, `sweep.py`/`sweep2.py`, `crack_operator.py`/`crack_op2.py`, twin-diff + dump scripts under the session scratchpad dir
