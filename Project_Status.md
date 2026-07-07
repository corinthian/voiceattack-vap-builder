# VoiceAttack Schema — Project Status

_Last updated: 2026-07-07_

## Where we are

The decoder now detects commands structurally (no category whitelist) and reads the profile header correctly. As of this session it has, for the first time, been measured against **ground truth** — a VoiceAttack CSV export of the corinthian profile — which both validated the structural rewrite and surfaced four accuracy bugs plus real progress on decoding conditional (variable) commands.

Active branch: `feature/decode-conditional-actions`. Nothing pushed. Three files from this session are uncommitted (see Git state).

## The ground-truth breakthrough

VoiceAttack cannot export XML, but its **CSV export** lists every command's category and full English action sequence. Paired with the binary `.vap`, it is a validation oracle and a semi-matched pair for reverse-engineering. Local, gitignored pair:
`reference profiles/corinthian-4-Profile.vap` + `…-Profile.csv`.

The CSV expands VoiceAttack's dynamic-phrase syntax (`[select;target] wing target`, `inch forward [1..4;]`) into one row per spoken permutation, so 200 raw decoder commands ↔ 479 CSV rows. A phrase-expander reproduces the expansion and matches **443/479 rows, 0 ambiguous**.

## Decoder accuracy — 4 bugs found, all FIXED (2026-07-07)

Full writeup: `skills/voiceattack-decoder/docs/Decoder_Accuracy_Findings_corinthian_CSV.md`. Reviewed against the binaries 2026-07-07: all four bugs confirmed exactly, but the drafted fix directions for #1 (categories) and #2 (phantom keys) were flawed and are corrected in the findings doc, which also gains Finding 6 (numkeys VK-aliased fallback categories — the category fallback fails even with no slash involved).

All four fixes then implemented in `vap_decoder.py` and verified (scratchpad prototype → all four reference profiles → CSV oracle): **479/479 CSV rows matched** (was 443), category mismatches 37→1 (the zoom-out anomaly, finding 5), phantom keypresses 19→0, 48 hold durations now decoded, the set-fire command recovered (corinthian 200→201 commands = the profile header's own count field). Two extra findings from verification: **KeyDown/KeyUp records ("press down X" / "release X") share the keypress marker with an exactly-0.0 Duration slot** — the phantom filter accepts d==0.0 only with a verified record suffix; and **`find_mouse_actions` iterated a set, making multi-mouse-action order nondeterministic across runs** — fixed by sorting hits by byte position.

1. **Categories wrong for 36/192 (~19%)** — of the 200 decoded commands, 8 are absent from the CSV export (it's a filtered subset), leaving ~192 comparable. `_extract_category` line 351 discards any string containing `/`, so the real category `flight/navigation` is thrown away and the fallback returns action text, a key letter, or a command-GUID. First bulk test of the shipped category-anchor fix; it fails on every slash-category. *(Highest priority; ~one-line fix.)*
2. **Phantom keypresses in ~19 conditional commands** — `find_key_actions` line 175 matches the `00000000 01000000` prefix and never validates what follows, so condition bytes read as keypresses with mouse-button VKs (1/2/4/256). Real key survives; the phantoms are extra (before or after it). *(Fix corrected on review: NOT the docstring-suffix check — real keys have two suffix shapes and a phantom passes it. Use the Duration-slot check at marker−12 with a floor; see findings doc.)*
3. **One command silently dropped** — `set [weapon;hardpoint;…] … fire` (36 spoken forms). `_match_command_signature` line 299 (`any(o >= n)`) nukes it because `count` (37) overruns the true 35-entry offset table into a child GUID. Fix: truncate the table at the first out-of-range offset, keep the command.
4. **Hold durations dropped entirely** — every "press and hold 1.5s" flattens to a bare press; `find_key_actions` never reads the Duration double.

## Condition (variable command) decoding — progress

Full writeup: `skills/voiceattack-decoder/docs/VAP_Conditional_Command_Analysis.md` (session update section).

**Cracked**
- **Near-twin diff is the working technique.** Diffing `throttle 25/50/75/100` (identical but for key + literal) pinpoints, relative to `phrase_end`: **+184 = keypress VK** (F1–F4) and **+580 = ConditionStartValue** (integer literal 1/2/3/4). Structure is byte-stable within a command family.
- **Full Text-compare operator enum (2026-07-07, authored conditionals probe).** `ConditionStartOperator` sits at **token_end** (immediately after the inline token operand), coded as the 0-indexed dropdown position: Equals=0 … **Contains=6** … Has Not Been Set=9. Confirmed across conditionals (10/10 sequential), zoom (Contains=6 in both branches), and corinthian `{BOOL:}` conditions (exact CSV correlation, incl. the single Does Not Equal=1). The earlier **Contains=1 is refuted** — that field (token−4) is an unidentified counter.
- **token−8 = ConditionPairing** (0-based index of the block's closing action) — explains zoom's 2/4 (previously misread as Begin/ElseIf subtype, now refuted) and corinthian's 2,3,4,5,6,9,15,21 spread.
- **Two operand mechanisms.** Global tokens (`{LASTSPOKENCMD}`, `{TXT:}`, `{BOOL:}`) stored inline; local vars (`[throt]`, `[i]`) live in a declaration pool and are referenced via wrapper `[01][len][name][01]`.
- **Noise floor caveat:** Equals=0 aliases zero padding for tokens in non-condition contexts, so flat-scan reads of Equals are unreliable; the object walk is still the clean route.

**Open** — Integer/Decimal/Boolean-variable dropdown enums, operator position for pool-referenced local-var conditions, value-type field, Begin/ElseIf/Else/End subtype codes, IndentLevel, token−4's meaning. Probe #2 (spec: `skills/voiceattack-decoder/docs/Conditionals_Probe_2_Spec.md`) targets all of these except the member-table base.

**The unlock (not yet attempted — a research build)**: dereference the shared command-member offsets (`[32,140,156,160]`, constant across zoom `[347,…]` and throttle `[331,…]`) to **walk action objects in order**, read each ActionType, match throttle's known 5-action sequence to fix the BeginCompare ActionType code, then read operator/type/subtype at consistent member offsets. Finds every condition across all commands and yields the full enum.

## Git state

- Branch: `feature/decode-conditional-actions`
- Commit stack: `4233a0e` (decoder fix + plan) → `01c9bbb` → `ca3a5c9` → `11986c6` → `c60647e` → `8148b07` (all docs) → `383408b` (status + findings + review corrections) → decoder-fix commit (this session; 4 bugs + mouse determinism)
- Working tree clean after the decoder-fix commit; nothing pushed.
- Reference profiles + CSV are gitignored (local only), consistent with keeping binaries out of Git.

## Open decisions

1. **Fund the action-graph walk** (path to the full condition enum) or bank Contains=1 + the diff technique and stop.
2. ~~Authorize the 4 decoder fixes~~ — DONE 2026-07-07, all four fixed and verified (see Decoder accuracy above).
3. ~~Commit the uncommitted docs~~ — DONE 2026-07-07 (`383408b` docs, decoder fix commit follows).
4. **Regression harness** — the verification scripts live in the session scratchpad only. The fix plan's regression bar calls for a checked-in harness, but the reference profiles are gitignored (local-only), so a committed harness can't run elsewhere. Decide: check in the harness with a skip-if-missing guard, or keep verification manual.

## Key artifacts

- Decoder: `skills/voiceattack-decoder/scripts/vap_decoder.py`
- Bug report: `skills/voiceattack-decoder/docs/Decoder_Accuracy_Findings_corinthian_CSV.md`
- Condition analysis: `skills/voiceattack-decoder/docs/VAP_Conditional_Command_Analysis.md`
- Fix plan (already executed): `skills/voiceattack-decoder/docs/Decoder_Category_Anchor_Fix_Plan.md`
- Ground-truth pairs (gitignored): `reference profiles/corinthian-4-Profile.{vap,csv}`, `reference profiles/conditionals-Profile.{vap,csv}` (authored operator probe — cracked the Text enum), `reference profiles/zoom-if-else.vap`, `reference profiles/Cities Skylines II-Profile.csv` + screenshots
- Scratchpad prototypes (session): `expand_match.py`, `sweep.py`/`sweep2.py`, `crack_operator.py`/`crack_op2.py`, twin-diff + dump scripts under the session scratchpad dir
