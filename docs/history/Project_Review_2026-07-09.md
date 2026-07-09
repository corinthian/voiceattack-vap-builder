# VoiceAttack Schema — PM Review

_Reviewer: Claude (PM role) · Date: 2026-07-09 · Branch reviewed: `feature/decode-conditional-actions` @ `6f2a294`_

Method: four parallel read-only audits (git/branches, decoder code + live oracle re-run, docs corpus, generator skill), reconciled against the root meta-docs. Nothing was edited, committed, or pushed. Claims tagged **[verified]** were re-run empirically; **[read]** were confirmed by reading; **[faith]** are taken from existing docs and not independently reproduced.

> **⚑ AUDIT (engineering re-review, 2026-07-09):** Four independent agents re-verified this review empirically — git (including an actual trial merge in a throwaway worktree, repo restored byte-identical), decoder re-run against the oracle profiles, generator exercised with edge-case inputs, full docs sweep. Comments marked ⚑ AUDIT below. Headline: the local-repo facts and the §4 docs catalog hold up almost everywhere, but the push-state story is refuted (the review read stale remote refs — 1.2.0 IS on GitHub), and both tools carry real defects the review missed, two of them data-destroying. Details inline.

---

## Executive summary

**The work is good. The *state* is confused. The gap is bookkeeping, not substance.**

The decoder's four accuracy bugs are genuinely fixed in the source and the fixes hold under an independent re-run (201 commands, phantom keypresses gone, 48 durations, category vocabulary matches the CSV oracle). The binary-format understanding is well-earned and triple-confirmed (spec → independent review of a 1,601-action walk → uncertainty-closure walk of 1,603). The generator produces well-formed profiles for its documented scope.

What makes the project feel confused is a single structural fault repeated across git, docs, and meta-files: **the current truth is uncommitted while the committed material is stale, and the front-door docs route a reader to the oldest, most-superseded content.** Layered on top: 13 commits of solid work are stranded unmerged and unpushed, the branch list is a graveyard, and two headline meta-claims ("Complete and tested", "bank Contains=1") are contradicted by the project's own newer work.

**Bottom line:** almost nothing here needs new research to become commit-ready. It needs consolidation, a reconciliation pass on stale docs, and a decision on how to integrate/push. Roughly a bookkeeping afternoon, not a build — with one genuinely non-trivial item inside it: writing the consolidated spec **v0.2** (§5.2 #3) is real spec-authoring, not clerical, since it means reconciling five refuted facts plus the closure results into the base doc.

> **⚑ AUDIT:** "Bookkeeping afternoon" undersells it. The accuracy fixes are real, but the audits surfaced roughly ten code defects this review missed (see §3 comments): worst are a generator path bug that silently overwrites the user's input JSON, and a decoder bound bug that miscategorizes the last command of *every* profile (the actual root cause of Finding 5, which this review treats as an unexplained anomaly). Budget a bug-fix day alongside the consolidation pass. Also, decision §5.2 #1 is moot as framed — see the §2.1 comment.

---

## 1. The crux: truth is untracked, committed docs are stale

This one fault explains most of the "confused" feeling. Everything else is a symptom.

| Layer | Current truth lives in… | …but the committed/front-door state says |
|---|---|---|
| Docs | `VAP_Uncertainty_Closure_Table.md`, `VAP_Decoder_V2_Preliminary_Spec.md`, `VAP_Uncertainty_Research_Plan.md`, `VAP_Probe_Specs_A_B.md` — **all 4 untracked** | Committed set still carries stale `Project_Status.md` + **superseded** `Conditionals_Probe_2_{Spec,Execution_Plan}.md` |
| Spec of record | Corrections live in `VAP_Format_Specification_Review.md` (overrides) + the Closure Table (extends) | `VAP_Format_Specification.md` — the self-declared "authoritative" base — still asserts **5 refuted facts in its own body** |
| Entry points | The object-model spec + review + conditionals work | `CLAUDE.md` and `SKILL.md` point **only** to `VAP_FORMAT.md`, the oldest flat-scan-era doc |

Committing the tree as-is would **enshrine the stale version and leave the truth on the floor.** The keystone that would fix this — a consolidated `VAP_Format_Specification.md` **v0.2** folding the Review + Closure corrections into the base — is called for by the research plan's Phase 6 but **does not exist yet.** It is the single highest-leverage missing artifact.

> **⚑ AUDIT:** Crux confirmed, one extension: the enshrine-the-stale risk already exists inside the *committed* set — `VAP_Binary_Schema_Analysis.md` (committed) still teaches the refuted offset-table model with no in-place annotation; its correction lives only in the newer spec. So "committing as-is enshrines the stale version" is already partly true today, independent of the untracked docs.

Authoritative reading order today (stated only inside the untracked Research Plan, nowhere a newcomer would look): **Spec (base) → Review (overrides on conflict) → Closure Table (extends).**

> **⚑ AUDIT:** Substance confirmed (no entry point mentions any of these docs), but no doc literally states this three-step chain. The Research Plan (:14-18) orders Spec → Review → *Conditional Analysis*; the Closure Table's place is implied only by its own header. The v0.2 author shouldn't treat this ordering as written-down anywhere.

---

## 2. Git & branch state

### 2.1 Nothing is pushed — on either line
- **HEAD** (`feature/decode-conditional-actions`): 13 commits ahead / 2 behind `main`. **No remote at all** — 13 commits entirely unpushed. [verified]
- **Local `main`**: 3 commits ahead of `origin/main`, unpushed — including the **1.2.0 version bump and the numpad feature**. The 1.2.0 "release" never reached GitHub. [verified]
- Remote: `git@github.com:corinthian/voiceattack-vap-builder.git`.

> **⚑ AUDIT — partly REFUTED; biggest miss in the review.** These numbers were read from stale remote-tracking refs; the review never fetched. Live `origin/main` is `a541840` (`git ls-remote`), which contains merged PRs #13 and #14 — and those contain **all three** "unpushed" local-main commits, including the 1.2.0 bump and the numpad work. **The 1.2.0 release DID reach GitHub.** Against the live remote, local main is 0 ahead / 2 behind (missing only the two GitHub merge commits). The genuinely unpushed work is exactly the 13 feature-branch commits — that half of the claim stands. First action before any push decision: `git fetch --prune`. Two related misses: there is no 1.2.0 tag despite the bump (pushed tags are `Version-1.1.1` and `VAP-export-Plugin`), and PR #14's merge subject implies a `fix/numpad-separator-docs` branch existed on GitHub that this clone has never seen — more evidence work flowed through GitHub after the last local fetch.

### 2.2 The stranded 13 — mostly docs, 2 real code commits
11 `docs:` + 2 `fix:`. Only two commits touch `*.py`, both `vap_decoder.py`:
- **`4233a0e`** — structural command detection replaces the category whitelist; fixes an off-by-4 profile-record read (byte 368 vs 364); removes dead `find_all_strings`.
- **`3f94d6e`** — the four CSV-oracle accuracy fixes (categories / phantom keys / dropped command / durations) + mouse-ordering determinism.

The other 11 are the reverse-engineering docs corpus. HEAD's file set is **disjoint** from main's 2 divergent commits (HEAD = decoder side; main's 2 = generator/manifest side), so integration **should be clean — no expected content or manifest conflict** (HEAD never touches `manifest.json`). This is *predicted* from the disjoint file sets, **not trial-merged** — no merge/rebase was run against the working tree. If you want certainty before relying on it, authorize a throwaway trial merge. [verified: file sets disjoint / predicted: clean merge]

> **⚑ AUDIT — prediction upgraded to verified.** The trial merge was run in a throwaway detached worktree (then discarded; repo confirmed byte-identical before/after): merging the feature branch into main completes conflict-free, 9 files changed +1383/−127, merged `manifest.json` = 1.2.0. The 11-docs/2-fix split, both code commits touching only `vap_decoder.py`, and the disjoint file sets all check out. Minor forensic note: `3f94d6e` was amended once (reflog) — harmless.

### 2.3 Branch graveyard — 8 of 10 are deletable
Keep only `feature/decode-conditional-actions` (active) and `main`. Safe to delete: `caps-lock`, `decoder`, `feature/vap-decoder`, `gallant-ride`, `multikey` (all fully merged into main), `feature/numeric-keypad-pr` (identical to main's tip), `fix/decoder-category-whitelist` (subsumed by HEAD), and `feature/numeric-keypad` (patch-equivalent to main via rebased `1dd5c1a` — *confirm you don't need its exact commits before deleting*). Three locals track `[gone]` upstreams (their PRs were merged and remote branches deleted). Stale remote PR branches `origin/caps-lock` and `origin/feature/numeric-keypad-pr` are prunable.

> **⚑ AUDIT — deletions all check out; one correction.** `git cherry` shows `feature/numeric-keypad` fully patch-equivalent to main (*both* its commits, numpad + 1.1.1 bump), so the "confirm before deleting" hedge can drop. `fix/decoder-category-whitelist` is a plain ancestor of HEAD — its tip is literally HEAD's first commit; deletion is provably lossless. Correction: `origin/caps-lock` and `origin/feature/numeric-keypad-pr` are already deleted server-side (GitHub removed them at PR merge) — they survive only as stale local tracking refs. After `git fetch --prune`, five locals (not three) would show `[gone]`.

### 2.4 The version fork — real but harmless
HEAD's `manifest.json` = **1.1.1**; main = **1.2.0** (bump `fa72978`). HEAD predates the bump. A merge resolves to 1.2.0 automatically. Minor forensic oddity: `fa72978` carries an old author-date (2026-04-04, `rlarsen@slab.maximillian`) sitting atop July work — a cherry-pick/rebase artifact, not a problem. [verified]

> **⚑ AUDIT — explanation refuted.** Not a cherry-pick/rebase artifact: the *committer* date is also 2026-04-04, on all three main-side commits — a July rebase would carry July committer dates. These commits were genuinely authored April 4 on another machine (`slab.maximillian`) and reached this clone by fetch; the numpad/1.2.0 line simply predates the July decoder work. Consistent with §2.1: that line was merged on GitHub long before this review.

### 2.5 Cruft — clean
No tracked junk. `.gitignore` fully covers `.DS_Store`, `__pycache__/`, `output files/`, `reference profiles/`, `Screenshots/`; nothing matching is in the index. The `vap_generator_temp.cpython-314.pyc` ghost has **no source in history** — a deleted dev-intermediate inside an ignored `__pycache__/`, invisible to git. Not distributed. [verified]

> **⚑ AUDIT — "clean" misses two things.** (1) A forgotten stash: `stash@{0}` "WIP on feature/vap-decoder", dated 2026-01-28, modifying CLAUDE.md +19/−6 — five-month-old uncommitted CLAUDE.md edits, exactly the class of untracked truth this review's §1 thesis is about, and absent from its catalog of uncommitted material. (2) `.claude/settings.local.json` is untracked but invisible in `git status` only because of a *global* gitignore rule (`~/.config/git/ignore`), not the repo's — worth knowing before any "commit everything" sweep.

---

## 3. Code readiness

### 3.1 Decoder — ready, with documented (not hidden) caveats
**All four documented bugs are genuinely fixed, and bug #2 uses the *corrected* marker−12 Duration-slot approach with the `0.001 ≤ d ≤ 60` floor — not the older suffix method the docs disavow.** Both extra fixes (0.0-Duration KeyDown/KeyUp gate; mouse position-sort) are present; determinism confirmed byte-identical across 5 runs under randomized hash seed. Code is clean: no TODO/FIXME, no dead code, typed error handling (no bare `except`). [verified]

Independent re-run against the local oracle: 201 commands (= the profile header's own count field, read independently), category vocabulary exactly matches the CSV's 10 names, phantoms gone on named cases *and* the conditions-heavy profile, 48 durations (0.01–12.0s), set-fire command recovered. The one unreproduced headline is the exact **"479/479 rows"** — the phrase-expander oracle is scratchpad-only, so that count is **[faith]** (strongly corroborated, not reproduced).

> **⚑ AUDIT:** Independent re-run reproduces all of it: 201 commands, exact 10-name category match, phantoms gone on the named cases, 48 non-default durations (0.01–12.0s), set-fire present, byte-identical output across 5 randomized-hash-seed runs, and xmllint/jq clean on all five reference profiles. One precision fix: the 201 count field lives in the *profile record* (offset 400), not the top-level header (whose @4 field reads 89) — the check holds, the phrasing is loose.

Caveats (all known, none are hidden regressions):
- **Category extractor is a heuristic last-link and still leaks off-corinthian.** The `/`-fix cleaned corinthian, but the fallback is unchanged elsewhere: conditionals get the condition *variable name* (`boo`/`smal`), numkeys get VK-aliased letters (`m/j/n/o/k/i`), and a base-profile command grabs a window title (`NVIDIA GeForce Overlay`). [verified]
- **Conditional commands are flattened lossily with no in-code warning.** The decoder emits accurate keypresses but discards branch structure and condition semantics. The docs say conditional decoding is an open research problem; a source-only reader gets no signal that this output is lossy. [verified]
- **Finding 5 (the zoom-out category anomaly, the surviving "1" of 37→1) is not flagged in the source.** [verified]
- Minor: `run_application` detection `break`s after the first `.exe`/`*` per command (a two-launch command drops the second). No test exercises it.

> **⚑ AUDIT — all four caveats reproduce, but this list is materially incomplete.** Extra category leaks beyond those named: `vampire` (2 cmds), `hold right mouse`, and three conditionals commands whose category is a single space. What the review missed entirely:
> - **Finding 5 is root-causable, not an anomaly.** The last command's scan bound is `len(data)` (vap_decoder.py:428), so it swallows the trailing profile-level region and `_extract_category` grabs the profile's own category list. This bites the *last command of every profile* — base profile's last command comes back as `dictation`. An afternoon fix; belongs on the §6 list, not in "parked anomalies."
> - **Cross-type action order is scrambled.** All keys are emitted, then all mouse actions appended (:436-437). Verified against byte order on `alt [left; right;] click`: true order LALT, RC, LC, LALT; decoder emits LALT, LALT, RC, LC. Deterministic but wrong — determinism was checked, order correctness wasn't.
> - **KeyDown/KeyUp decode as PressKey** — hold-tab becomes press-twice. Acknowledged in the Findings doc but absent here, and it corrupts round-trips worse than the §3.2 numpad naming issue.
> - **The decoder crashes (raw zlib traceback) on uncompressed-XML .vap** — a format CLAUDE.md documents as valid and the *only* format this repo's own generator writes. The documented decode→edit→regenerate loop can't open a generator-made file at step one.
> - **Decoder-side silent action drops:** Say, Pause, ExecuteCommand, SetClipboard, KeyToggle, and non-`.exe` Launch produce nothing, unwarned — §3.2 frames this as generator-only; it's both sides. Corinthian's events commands decode with zero actions though the CSV shows dozens of Say/Execute/Pause steps.
> - **Default output writes next to the input** (:613-615) — the documented bare invocation on a file in `reference profiles/` writes into the directory CLAUDE.md declares read-only.
> - Wording nits: "no dead code" — the `profile_name` param (:395) is unused; and the 0.0-duration gate *accepts* verified KeyDown/KeyUp records rather than skipping them.

### 3.2 Generator — works for its scope; "Complete and tested" overstates
All three example JSONs generate and pass `xmllint`; chording, full key/mouse tables, sections, and XML-escaping all work empirically. But:
- **Silent no-op trap.** `Launch` / `ExecuteCommand` / `SetClipboard` are decoder-only concepts the generator does **not** implement — yet feeding one emits a structurally-valid but empty `<ActionType>` with **no warning**, producing a broken profile. (Unknown *keys* warn; unknown *types* don't.) [verified]
- **Same-repo decoder↔generator numpad mismatch.** The decoder emits `subtract/multiply/decimal/divide/add`; the generator only knows `numpad_subtract`/`num_subtract`, so a documented decode→edit→regenerate round-trip **silently drops all numpad-operator keys.** This contradicts the round-trip-editing premise. [verified]
- **"Tested" = well-formed + structurally matches real decoded profiles.** Actual VoiceAttack import/execution is asserted by CLAUDE.md, never demonstrated in-repo (CLAUDE.md itself admits "No automated tests"). [read/faith]
- `scroll_clicks` is written to Duration, X, **and** DecimalContext1 simultaneously — the author was unsure which field VoiceAttack reads; correctness unverified. [read]

> **⚑ AUDIT — all four claims stand; two framing fixes and two bigger misses.** Framing: the numpad round-trip drop is **not silent** — the generator prints five explicit "Unknown key … ignored" warnings and "Warnings: 5" on stdout (exit code stays 0, so a pipeline ignoring stderr still gets burned, but "silently drops" is wrong). The genuinely silent trap is the unknown-ActionType one, and it's *worse* than stated: a typo'd type like `PresKey` also passes silently, and because the keys branch never runs, its keys drop without even the unknown-key warning. Missed defects:
> - **Input-file clobbering — worst code defect in the repo.** `output_file = input_file.replace(".json", ".vap")` (vap_generator.py:542). An input filename without `.json` makes output == input: the generator **silently overwrites the user's JSON with XML** (verified destructively in scratchpad). Replace-all also corrupts paths with `.json` elsewhere in them.
> - **The round-trip gap is much wider than numpad.** The decoder also emits `separator`, `backtick`, `lbracket`/`rbracket`, `printscreen`, `pause` (the key), and seven media keys — none exist in the generator's table; all drop on round-trip.
> - Smaller, all verified: tiny durations serialize as scientific notation (`1e-05`), which .NET decimal parsing likely rejects; no duration floor (0 and −1 pass through; CLAUDE.md claims a 0.1s minimum that is only a *default*); JSON-numeric keys (`"key": 5`) crash with a raw AttributeError; an unknown *mouse* action warns but then substitutes a real `left_click` into the profile; `scroll_clicks` leaks X/DecimalContext1 into non-scroll mouse actions; missing input file and malformed JSON dump raw tracebacks.

---

## 4. Internal inconsistencies (catalog)

Ranked roughly by how misleading each is to a reader.

1. **`Project_Status.md` contradicts itself on Contains=1.** Line 35 says "Contains=1 is refuted"; line 53 says "bank Contains=1 + the diff technique and stop." Same file, opposite claims. [read]
2. **`CLAUDE.md`: "Status: Complete and tested"** while the entire recent workstream is decoder bug-fixes plus an explicitly *open* conditional-decoding research problem. The headline status is stale. [read]
3. **The "authoritative" spec asserts 5 refuted facts in its own body.** `VAP_Format_Specification.md` still states: Decimal = IEEE-754 double (actually 16-byte .NET Decimal at m[25]); m[7] holds all right-operands (actually Text-only; numeric = m[21]); m[5] = keypress marker (actually KeyCodes list — flat read misses every chord); separator = `0xF1886E09` (off-by-one; actual `0x886E0900`); three GUIDs per command (actually 1 + actionCount). Corrections live in the *Review*, a separate file. [read]

   > **⚑ AUDIT:** All five asserted-and-refuted pairs verified at file:line. One softening: the spec tags the Decimal=double claim `[INFERRED]`, so "asserts" is mildly strong for that one; the other four carry `[SOLID]`.
4. **`VAP_FORMAT.md` is stale and self-contradictory** — yet it's the doc CLAUDE.md and SKILL.md point to. Wrong key-action byte layout (says `00 00 01 00`; actual `01 00 00 00`), doesn't document the Duration-at-marker−12 slot that both decoder fixes depend on, describes a clean category field the code never uses, and contradicts itself on the scroll offset (−24 in one place, −20 in another; code uses −20). [verified]

   > **⚑ AUDIT — confirmed except the scroll diagnosis.** The "−24" (:132) and "−20" (:163) lines describe the *same byte* under different anchors (context code vs 4-byte length prefix) — not a contradiction. The genuine defect is the offset table (:165-170), which anchors 0 at the string bytes yet still writes −20. Code uses pos−20 from the prefix (vap_decoder.py:252), matching :163. Byte-layout, marker−12 absence, phantom category field, and entry-point-pointer claims all verified.
5. **`main` bumped to 1.2.0 but this branch's `manifest.json` says 1.1.1**, and the branch's *code* already supports `numpad_separator` while its generator-facing docs and version don't mention it — **code ahead of docs ahead of nothing pushed.** [verified]
6. **Docs cite pre-fix line numbers** (175/299/351) that have since drifted in `vap_decoder.py`; anyone following the docs to a line lands in the wrong place. [verified]

   > **⚑ AUDIT:** Two of three drifted (299, 351); line 175 still lands exactly on `pattern_prefix` — that citation is fine, so "anyone… lands in the wrong place" overreaches. Also missed: `Decoder_Category_Anchor_Fix_Plan.md` cites four more dead line numbers (261/267/272/294) from the deleted whitelist era, mitigated by being marked "already executed."
7. **`README.md` under-documents its own product** — omits chording, numpad, L/R modifiers, and mouse back/forward/triple/toggle/scroll-L-R, several of which its *own shipped examples* use (numpad example, pageup/pagedown in the heart example). Its Quick Start step 2 ("Generate the profile") is followed by an **empty code block** — the command is missing. Install URL references repo `voiceattack-vap-builder` while the package is named `voiceattack-tools`. [read]

   > **⚑ AUDIT:** Confirmed with two nits: the gap after "Generate the profile" is blank lines, not an empty code block, and it sits in the *Manual Method* section, not Quick Start. All omissions and the repo-vs-package name mismatch verified; the shipped examples do use the undocumented features.
8. **`Project_Status.md`'s "Open" list is fully closed elsewhere** — it still lists Integer/Decimal/Boolean enums, value-type field, ConditionPairing, IndentLevel, and token−4 as open; the Closure Table resolves all of them. It also calls the action-graph walk "not yet attempted" when it has since been done and confirmed. [read]

   > **⚑ AUDIT — confirmed except one error:** **ConditionPairing is not in the Open list** — Project_Status.md:36 presents it as cracked. Attribution is also loose: several closures live in the committed conditional-analysis updates and the untracked Spec/Review, not solely the Closure Table. Worth noting: the "not yet attempted" walk contradiction sits entirely within the *committed* file set — it isn't explained by the untracked-truth crux.
9. **Stale residual "Contains=1"** also survives in `VAP_Conditional_Command_Analysis.md` (corinthian session-update still-open list), though later sections in the same file refute it. [read]

> **⚑ AUDIT — catalog verdict: 7 confirmed clean, 3 confirmed-with-overstatement, 0 refuted. But it's missing four entries of comparable rank:**
> 1. `VAP_Conditional_Command_Analysis.md` contradicts itself *within its final session update*: :377 declares m[2]=ActionType `[SOLID]` resolved (Begin/ElseIf/Else/End = 19/63/29/20); :379, two paragraphs later, lists "the subtype code (m[2])" as genuinely open. Same class as item 1 above.
> 2. `Project_Status.md` has a *second* self-contradiction, on git state: :9 "Three files from this session are uncommitted" vs :48 "Working tree clean after the decoder-fix commit."
> 3. The decoder `SKILL.md` misdocuments its own CLI: bare invocation is labeled "Decode to stdout" but actually writes `input_decoded.xml/.json` (stdout needs `--stdout`), and it describes XML-only output when the decoder always emits XML + JSON.
> 4. Cross-doc numeric conflicts and broken references: corinthian decompressed size 545,814 (`VAP_Binary_Schema_Analysis.md`) vs 545,818 (spec; the Review verified the spec's number); base-profile command count ~112 vs 103 in the same file vs header 101 elsewhere; `VAP_Binary_Schema_Analysis.md:239-240` lists two "Generated Artifacts" JSONs that exist nowhere in the repo. Plus `numlock` and `numpad_separator` are generator-supported but documented nowhere, though the shipped numpad example uses `numlock`.

---

## 5. Unanswered questions

### 5.1 Open research (genuinely not yet known)
- **Probe B targets** (only live probe; specced, not built, gated on the user hand-building an `actions` export): unsampled ActionTypes 50/51 (start/stop listening) + field layouts for Say/Launch/SetClipboard/mouse; the Set-op operator enum (contradictory samples: climb=4 vs jumped=0); Set-Boolean value-vs-order confound; Set-SmallInt/Decimal layouts; mouse context enum + X/Y.
- **Compound AND/OR conditions** — deliberately **de-scoped to decode-only** (Probe A dropped). Support is scoped to nested single-condition blocks.
- **Header @8 command-list index** — the trailing ~size−530 region is undecoded; command discovery stays scan-based even in the V2 design.
- **~24 unmapped member slots** — parked; a few known-dead (m10≡FFFF, m22/26/32/33≡0), m23 a binary flag of unknown meaning.

### 5.2 Open decisions (yours to make — these are the real blockers)
1. **Push or keep local?** The 1.2.0 release + numpad work sit only on local `main`; all decoder work is unpushed. Is a 1.2.0 release intended?

   > **⚑ AUDIT — moot as framed.** 1.2.0 is already on GitHub via merged PRs #13/#14 (see §2.1 comment). The live decisions are: run `git fetch --prune`; whether to push the 13 decoder commits; whether to tag 1.2.0 (no tag exists); and what to do with the forgotten 2026-01 stash of CLAUDE.md edits.
2. **Commit the untracked truth-docs, or start a decoder-V2 branch for them?** They post-date every committed doc and are newer than HEAD's tip.
3. **Write the consolidated `VAP_Format_Specification.md` v0.2** (the missing keystone) before or after committing?
4. **Fund the V2 decoder build** (tree-walk over the confirmed object model, replacing the flat scan + category heuristic) — or bank the current decoder and stop? This is the path that would fix the category leak and the lossy-conditional flattening.
5. **Regression harness.** Verification scripts are scratchpad-only, so the whole thing is **not reproducible from committed state** (the research plan literally says "rebuild the walker first thing"). The reference profiles are gitignored (local-only), so a committed harness can't run elsewhere. Decide: check in a harness with a skip-if-missing guard, or keep verification manual. (V2 §9.5 leans toward check-in; not done.)
6. **Branch cleanup** — delete the 8 dead branches now, or later?

---

## 6. Loose ends — actionable checklist

Prioritized. None require new research; all are consolidation/hygiene.

**High (removes the "confused" state):**
- [ ] Commit or explicitly branch the 4 untracked truth-docs (§1).
- [ ] Write `VAP_Format_Specification.md` v0.2 folding in Review §2 + Closure closures; retire or annotate the old spec (§1, §4.3).
- [ ] Fix `Project_Status.md`'s Contains=1 self-contradiction and stale Open-list, or replace the file with a fresh status (§4.1, §4.8).
- [ ] Update `CLAUDE.md` status line off "Complete and tested" to reflect decoder-in-progress + open conditional work (§4.2).
- [ ] Repoint `CLAUDE.md` / `SKILL.md` from `VAP_FORMAT.md` to the current spec, or fix `VAP_FORMAT.md` (§1, §4.4).

**Medium (correctness / honesty):**
- [ ] Decide integration path for HEAD → main (clean; §2.2) and whether to push (§5.2).
- [ ] Add a generator warning for unrecognized ActionType (kill the silent no-op trap) (§3.2).
- [ ] Reconcile the decoder↔generator numpad-operator naming so round-trips don't drop keys (§3.2).
- [ ] Fix README: add missing command in Quick Start, document chording/numpad/L-R modifiers/full mouse set, reconcile the repo-vs-package name (§4.7).
- [ ] Refresh doc line-number citations to match current `vap_decoder.py` (§4.6).

**Low (hygiene):**
- [ ] Delete the 8 dead branches; prune stale remote PR branches (§2.3).
- [ ] Flag Finding 5 and the lossy-conditional flattening in the decoder source (comments), so source-only readers are warned (§3.1).
- [ ] Purge the residual "Contains=1" in `VAP_Conditional_Command_Analysis.md` (§4.9).
- [ ] Decide the regression-harness question (§5.2 #5).

> **⚑ AUDIT — additions the checklist needs (from the code audits; "none require new research" no longer holds — these are bug fixes):**
> - [ ] **High:** fix the generator output-path derivation (input-file clobbering, vap_generator.py:542) — active data-loss bug.
> - [ ] **High:** `git fetch --prune` before acting on any §2 push/branch items; reframe §5.2 #1 per the audit comment there.
> - [ ] **Medium:** decoder — accept uncompressed-XML .vap (its own generator's output format); cap the last-command scan bound (root cause of Finding 5); fix cross-type key/mouse ordering; warn on decoder-side dropped action types.
> - [ ] **Medium:** generator — warn on unknown ActionType (already listed above) *and* return nonzero exit when warnings fired; fix scientific-notation duration serialization; validate durations.
> - [ ] **Low:** inspect then drop or apply `stash@{0}` (2026-01-28 CLAUDE.md edits); decide whether to tag 1.2.0.

---

## 7. What's ready to commit right now

| Item | Ready? | Blocker |
|---|---|---|
| Decoder code (`vap_decoder.py`, the 2 fix commits) | **Yes** — verified, clean, already committed on HEAD | Just needs merge/push decision |
| HEAD → main integration | **Yes** — disjoint file set, clean | Decision only |
| The 4 untracked truth-docs | **Almost** — coherent, current | Decide commit vs V2 branch |
| `VAP_Format_Specification.md` as "the spec" | **No** | Asserts refuted facts; needs v0.2 consolidation |
| `Project_Status.md` | **No** | Self-contradictory + stale; refresh or retire |
| `CLAUDE.md` / `README.md` / `SKILL.md` | **No** | Stale status, wrong doc pointers, under-documented, broken code block |
| Generator | **Ships already** (it's the plugin) | Silent-no-op + numpad round-trip are real defects, not commit-blockers |
| Branch list | **N/A** | 8 deletable |

> **⚑ AUDIT — two rows need edits.** Decoder "Yes — verified, clean": the four documented fixes are real and reproduce, but "clean" is too strong given the last-command category bug, the cross-type ordering bug, KeyDown/KeyUp mistyped as PressKey, and the crash on uncompressed XML (§3.1 comment). Still committable — the fix commits are strict improvements — but not defect-free. Generator "ships already": true, and it ships with an input-clobbering path bug that deserves fixing regardless of any commit decision.

**One-line verdict:** the engine runs and the measurements are trustworthy; the dashboard is wired to last week's readings. Fix the dashboard (consolidate the spec, refresh the status/meta-docs, commit the truth, decide push/merge) and this is in clean shape without touching the research frontier.

> **⚑ AUDIT — overall verdict on this review.** Its honesty discipline held: every [verified] tag we re-checked reproduced against *local* state, and the §4 docs catalog is accurate. Two systematic weaknesses: it audited git without fetching, which inverted the release story (1.2.0 is published; only the 13 decoder commits are unpushed), and it stopped code inspection at the documented-bug level, calling both tools ready while ~10 undocumented defects — two data-destroying — sat within reach of the same empirical method it used elsewhere. Corrected one-liner: the dashboard is wired to last week's readings *and* the engine has a couple of real leaks — one consolidation pass plus one bug-fix day, not just a bookkeeping afternoon.

---

_Note: this review file is itself a new **untracked** file in the repo root — a 6th uncommitted item on top of the 4 untracked docs plus the ghost `__pycache__`. Per its own §1 thesis (truth shouldn't sit untracked), decide whether to commit it as a project artifact, gitignore it, or keep it outside the eventual commit. It was placed here for visibility, not silently added to the tree._
