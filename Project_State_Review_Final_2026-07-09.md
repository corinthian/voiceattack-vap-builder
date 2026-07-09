# VoiceAttack Schema — Project State Review (Final)

_Reviewer: Claude (PM role) · Date: 2026-07-09 · Branch: `feature/decode-conditional-actions` @ `6f2a294`_

**Provenance.** v1 of this review ran four parallel read-only audits. It was then stress-tested by an independent engineering re-review (four more agents: a trial merge in a throwaway worktree, a live `git ls-remote`, destructive generator tests, a full docs sweep). This final version folds the corrections in, after I **independently re-verified every conclusion-changing or data-loss claim myself** rather than relaying them. Where the re-review overreached, I say so and correct it.

**Verification legend:** **[verified]** = I re-ran/re-read it this pass · **[inspection]** = confirmed by reading the code path · **[read]** = confirmed in a doc, not executed · **[faith]** = carried from a prior audit, not independently reproduced.

---

## 0. What changed from v1, and my rulings on the stress-test

The stress-test was mostly right and materially improved the picture. Two of its corrections are important; a few of its severity labels overreach.

| Stress-test claim | My ruling | Basis |
|---|---|---|
| **1.2.0 IS on GitHub; v1's "never pushed" was read off stale refs** | **CONCEDED — v1 was wrong.** Biggest correction. Now **proven**, not inferred. | [verified] `git fetch --prune` then `git merge-base --is-ancestor fa72978 origin/main` → true; live `origin/main`=`a541840`; local main 0-ahead/2-behind |
| Generator silently **overwrites input JSON** (path bug) | **CONFIRMED, real data-loss** | [inspection] vap_generator.py:542 |
| Decoder **last command of every profile over-scans** into profile-level bytes (root cause of Finding 5) | **CONFIRMED — attribution now proven by controlled test** | [verified] "zoom out" is corinthian's last command (idx 200/201) → wrong cat `combat & targeting`; adjacent non-last "zoom in" → correct `Interface`; only position differs. + [inspection] vap_decoder.py:428 |
| Cross-type action order scrambled (keys then mouse) | **CONFIRMED** | [inspection] vap_decoder.py:436-437 |
| Forgotten `stash@{0}` (Jan CLAUDE.md edits) missed by v1 | **CONFIRMED — good catch** | [verified] `git stash list` |
| v1's "numpad drops **silently**" | **CONCEDED — generator DOES warn** ("Unknown key… ignored", "Warnings: 5"). The truly silent trap is unknown-*ActionType*. | [read] audit, consistent with generator code |
| v1 item 8 listed **ConditionPairing** as still-open | **CONCEDED — v1 error.** Project_Status.md:36 presents it as cracked. | [read] |
| v1 item 4: −24/−20 scroll offset is a "contradiction" | **CONCEDED — same byte, different anchor.** Real defect is the offset-table example. | [read] |
| v1 item 6: doc line-refs drifted → reader "lands wrong" | **Softened — 2 of 3 drifted; line 175 still lands on `pattern_prefix`.** | [read] |
| **"Two data-destroying bugs"** | **CHALLENGED — only ONE destroys data** (generator clobber). The decoder last-command bug is an *accuracy* defect: the decoder is read-only; a wrong category destroys nothing. | reasoning + [inspection] |
| Clobber is **"worst defect in the repo"** | **CHALLENGED — calibrate.** Real data-loss, but only fires on a non-`.json`-named input with no explicit output arg; the documented workflow never triggers it. High priority (data-loss class), but latent. | [inspection] :542 |
| Decoder crash on uncompressed-XML `.vap` **"breaks the documented round-trip at step one"** | **CHALLENGED — real gap, wrong framing.** CLAUDE.md does list XML `.vap` as valid, so the decoder should handle it — a genuine robustness gap. But the documented loop is real-`.vap` → decode → edit → generate → *import*; it never re-decodes generator output. "Round-trip broken" overreaches. | [inspection] + prior audits |

Net effect on the headline: **the release story inverts** (1.2.0 shipped; the clone is stale), and **the effort estimate rises** from "a bookkeeping afternoon" to **a consolidation pass plus a bug-fix day.** Everything else in v1 held.

---

## 1. Executive summary (corrected)

**The work is good and independently verified. The *state* is confused — and the confusion is bookkeeping plus a handful of real, mostly-latent code defects, not a broken research effort.**

The decoder's four documented accuracy fixes are genuinely in the source and reproduce under re-run (201 commands, phantoms gone, 48 durations, category vocabulary matching the CSV oracle). The binary-format understanding is well-earned and triple-confirmed. But the tools carry ~10 undocumented defects the first pass missed — one of them destroys user data (generator input-clobber), several corrupt decoder output (last-command miscategorization, scrambled key/mouse order, KeyDown/KeyUp mistyped as PressKey), and the decoder can't open the uncompressed-XML `.vap` variant its own docs call valid.

The dominant *organizational* fault is unchanged: **the current truth is uncommitted while the committed material is stale, and the front-door docs route a reader to the oldest, most-superseded content.** The release picture, corrected, is healthier than v1 claimed — 1.2.0 is on GitHub — but the clone is stale and the 13-commit decoder line is genuinely unpushed.

**Bottom line:** one consolidation pass (docs) + one bug-fix day (tools) + a `git fetch` and a few decisions. No research frontier needs touching to reach a clean, committable state.

---

## 2. Git & release state (corrected — the biggest change)

**v1 audited git without fetching and inverted the release story. I ran `git fetch --prune` this pass (tracking refs only — no working tree, branches, or commits touched) and proved the corrected picture:**

- **The clone was stale.** Before the fetch, local `origin/main` tracking ref = `f0e0862` (the `Version-1.1.1` tag); the live `origin/main` = `a541840`, which the clone had never seen. [verified]
- **1.2.0 is published — proven.** `git merge-base --is-ancestor fa72978 origin/main` → true: the 1.2.0 bump (and `7d66971` numpad_separator) are ancestors of live `origin/main`. The numpad feature + 1.2.0 release reached GitHub via merged PRs #13/#14. [verified]
- **Local `main` is behind, not ahead:** `git rev-list --left-right --count main...origin/main` → `0  2` (0 ahead / 2 behind — the two GitHub merge commits). v1's "3 ahead, unpushed" was the stale-ref artifact. [verified]
- **What is genuinely unpushed:** exactly the **13 decoder commits** on `feature/decode-conditional-actions`, which has no remote at all. That half of v1's claim stands. [verified]
- **No `1.2.0` tag exists** — only `Version-1.1.1` and `VAP-export-Plugin`. If 1.2.0 is a real release, it's untagged. [verified]
- **Post-fetch:** the fetch pruned `origin/caps-lock` and `origin/feature/numeric-keypad-pr` (GitHub deleted them server-side at PR merge); **five** local branches now show `[gone]` upstreams. [verified]

**Integration (HEAD → main): clean — now verified, not predicted.** The stress-test ran the merge in a throwaway detached worktree (repo restored byte-identical): conflict-free, 9 files +1383/−127, merged `manifest.json` = 1.2.0. The 11-docs/2-code split holds; both code commits (`4233a0e`, `3f94d6e`) touch only `vap_decoder.py`. [verified by stress-test worktree merge]

**Branch graveyard: 8 of 10 deletable** (keep `feature/decode-conditional-actions` + `main`). `feature/numeric-keypad` is fully patch-equivalent to main (drop v1's "confirm first" hedge); `fix/decoder-category-whitelist` is a plain ancestor of HEAD (provably lossless). [verified]

**Cruft, corrected:** the tree is clean of *tracked* junk, but two pieces of uncommitted state escaped v1's catalog — the **forgotten `stash@{0}`** (Jan 2026 WIP, CLAUDE.md +19/−6) and an untracked `.claude/settings.local.json` (hidden only by a *global* gitignore). Both matter before any "commit everything" sweep. [verified stash; read settings]

**Forensic note:** the numpad/1.2.0 commits carry April-4 author *and committer* dates (not a July rebase artifact as v1 guessed) — genuinely authored earlier on another machine and merged to GitHub before the July decoder work. [read]

---

## 3. Code readiness & the real defect list

The four documented fixes are real and reproduce. But "ready/clean" was too generous — here is the corrected defect inventory. **None block committing the existing fix commits (they are strict improvements), but the tools are not defect-free.**

### 3.1 Decoder
Confirmed solid: the four bug-fixes (bug #2 uses the corrected marker−12 Duration approach, not the disavowed suffix method), both extra fixes, byte-identical determinism, 201 commands (count field lives in the *profile record* at offset ~400, not the top-level header — v1's phrasing was loose), category vocabulary matching the oracle. [verified / inspection]

Defects (severity-ordered):
1. **Last command of every profile over-scans.** `bound = … else n` (vap_decoder.py:428) lets the final command's byte range run to end-of-buffer, so `_extract_category` grabs profile-level strings. **Confirmed root cause of Finding 5 by controlled test:** corinthian's last command (idx 200/201) is "zoom out" → wrong category `combat & targeting`; the adjacent, *non-last* "zoom in" (idx 199, bounded by the next hit) → correct `Interface`. Same family, only position differs. Mis-tags the last command of *every* profile. Accuracy bug, not data-loss. Afternoon fix. [verified]
2. **Cross-type action order scrambled.** All keys emitted, then all mouse appended (:436-437). `alt [left;right;] click` decodes LALT, LALT, RC, LC instead of true byte order. Deterministic but wrong — v1 checked determinism, not order correctness. [inspection]
3. **KeyDown/KeyUp decode as PressKey** — hold-tab becomes press-twice; corrupts round-trips. Noted in the Findings doc, absent from v1. [read]
4. **Crashes on uncompressed-XML `.vap`** — raw-inflate only, no XML fallback, though CLAUDE.md lists XML `.vap` as a valid variant. Real robustness gap. (But not the "round-trip break" the stress-test called it — see §0.) [inspection]
5. **Silent decoder-side action drops** — Say/Pause/ExecuteCommand/SetClipboard/KeyToggle/non-`.exe` Launch produce nothing, unwarned; corinthian's events commands decode with zero actions despite the CSV showing many. (v1 framed this as generator-only; it's both sides.) [read]
6. **Category extractor still leaks off-corinthian** beyond v1's list: also `vampire`, `hold right mouse`, and single-space categories on conditionals. The `/`-fix cleaned corinthian; the fallback is unchanged elsewhere. [verified]
7. Minor: default bare invocation writes `input_decoded.*` next to the input (into the read-only `reference profiles/`); `run_application` stops after the first hit; unused `profile_name` param. [read]

**Conditional commands remain flattened lossily with no in-code warning** — accurate keypresses, but branch structure and condition semantics discarded (the open research problem, §5).

### 3.2 Generator
Works for its documented scope (all three examples generate + pass `xmllint`; chording, key/mouse tables, escaping verified). Defects:
1. **Input-file clobbering — the one genuine data-loss bug in the repo.** `input_file.replace(".json", ".vap")` (vap_generator.py:542) returns the input unchanged when the name lacks `.json`, then line 550 opens it for **write** — silently overwriting the user's file. Also `.replace` is replace-all, so paths with `.json` elsewhere corrupt. **Real and destructive, but latent:** only fires on a non-`.json`-named input with no explicit output arg. High priority regardless. [inspection]
2. **Silent unknown-ActionType trap.** A typo'd type (`PresKey`) or a decoder-only type (`Launch`/`ExecuteCommand`/`SetClipboard`) emits an empty `<ActionType>` with no warning — and because the keys branch never runs, its keys vanish without even the unknown-*key* warning. This is the actually-silent one (unlike numpad, which does warn). [read/inspection]
3. **Round-trip gap is wider than numpad.** The decoder emits `separator`, `backtick`, `lbracket`/`rbracket`, `printscreen`, `pause`, and seven media keys — none in the generator's table; all drop on round-trip. [read]
4. Smaller, all reported: tiny durations serialize as `1e-05` (likely rejected by .NET decimal parsing); no duration floor (0/−1 pass through; the "0.1s minimum" is only a default); numeric-JSON keys crash; unknown *mouse* action warns then substitutes a real `left_click`; `scroll_clicks` leaks into non-scroll actions; exit code stays 0 even with warnings. [read]

**"Complete and tested" is still an overstatement** — actual VoiceAttack import is asserted (CLAUDE.md admits "No automated tests"), and the tool ships with the clobber bug and the silent trap.

---

## 4. Docs: truth untracked, committed stale (holds; extended)

The core organizational fault stands and the stress-test sharpened it.

- **The crux:** current truth (Closure Table, V2 Spec, Research Plan, Probe Specs) is **untracked**; the committed set carries a stale `Project_Status.md` + superseded `Conditionals_Probe_2_*`; entry points (`CLAUDE.md`, `SKILL.md`) point only to the oldest doc (`VAP_FORMAT.md`). [read]
- **Staleness already lives inside the committed set** — `VAP_Binary_Schema_Analysis.md` still teaches the refuted offset-table model with no in-place annotation. So "committing as-is enshrines stale content" is partly true *today*, independent of the untracked docs. [read]
- **The missing keystone:** a consolidated `VAP_Format_Specification.md` **v0.2** (Research Plan Phase 6) folding the Review + Closure corrections into the base — does not exist. Highest-leverage missing artifact. Note: no doc actually writes down the Spec→Review→Closure precedence order; the v0.2 author shouldn't assume it's recorded anywhere. [read]

The format *understanding* itself is solid and triple-confirmed; the problem is trust-routing and packaging, not content.

---

## 5. Internal inconsistencies (consolidated catalog)

v1's catalog: 7 clean, 3 overstated (corrected in §0), 0 refuted. Merged with the stress-test's additions and de-duplicated:

1. `Project_Status.md` self-contradicts on **Contains=1** (L35 "refuted" vs L53 "bank Contains=1") **and** on **git state** (L9 "three files uncommitted" vs L48 "working tree clean"). [read/verified]
2. `CLAUDE.md` "**Status: Complete and tested**" vs an in-progress decoder + open conditional research. [read]
3. `VAP_Format_Specification.md` asserts **5 refuted facts in its own body** (Decimal-as-double [tagged INFERRED], m[7]-all, m[5]-marker, `0xF1886E09`, three-GUIDs); corrections live only in the separate Review. [read]
4. `VAP_FORMAT.md` stale (wrong key-action byte layout `00 00 01 00` vs actual `01 00 00 00`; undocumented Duration-at-marker−12 slot; phantom clean-category field) — and it's the doc the entry points cite. (The −24/−20 "contradiction" is withdrawn: same byte, different anchor; the real defect is the offset-table example.) [verified/read]
5. `manifest.json` = 1.1.1 on this branch while code supports `numpad_separator` undocumented — code ahead of docs. [verified]
6. Doc line-number citations partly drifted (299, 351 dead; 175 fine); `Decoder_Category_Anchor_Fix_Plan.md` cites four more dead line numbers from the deleted-whitelist era. [read]
7. `README.md` under-documents its own product (omits chording/numpad/L-R modifiers/extended mouse — several used by its own examples), has a missing command in the Manual-Method steps, and a repo-vs-package name mismatch (`voiceattack-vap-builder` vs `voiceattack-tools`). [read]
8. `Project_Status.md` "Open" list is closed elsewhere (enums, value-type, IndentLevel, token−4 — **not** ConditionPairing, which it shows as cracked); calls the action-graph walk "not yet attempted" when it's since done — a contradiction *within the committed set*. [read]
9. `VAP_Conditional_Command_Analysis.md` self-contradicts in its final update: m[2]=ActionType `[SOLID]` resolved (:377) vs "subtype code (m[2])" listed open (:379); also a stale residual "Contains=1". [read]
10. Decoder `SKILL.md` misdocuments its own CLI (bare invocation labeled "Decode to stdout" but writes `input_decoded.*`; claims XML-only when it emits XML+JSON). [read]
11. Cross-doc numeric conflicts: corinthian decompressed size 545,814 vs 545,818; base-profile command count 112/103/101 across docs; `VAP_Binary_Schema_Analysis.md:239-240` lists two artifact JSONs that exist nowhere. [read]

---

## 6. Open questions & decisions

### 6.1 Open research (genuinely unknown)
- **Probe B targets** (only live probe; specced, unbuilt, gated on a hand-built `actions` export): ActionTypes 50/51 + Say/Launch/SetClipboard/mouse field layouts; Set-op operator enum (contradictory samples); Set-Boolean value-vs-order; Set-SmallInt/Decimal layouts; mouse context enum + X/Y.
- **Compound AND/OR conditions** — deliberately de-scoped to decode-only (Probe A dropped).
- **Header @8 command-list index** — trailing region undecoded; discovery stays scan-based even in V2.
- **~24 unmapped member slots** — parked.

### 6.2 Open decisions (corrected)
1. **`git fetch --prune` first**, then decide: push the 13 decoder commits? Tag 1.2.0 (no tag exists)? (v1's "push 1.2.0" is moot — it's already on GitHub.)
2. Inspect then drop-or-apply the forgotten `stash@{0}` (Jan CLAUDE.md edits).
3. Commit the 4 untracked truth-docs, or open a decoder-V2 branch for them?
4. Write the consolidated Spec **v0.2** (the keystone) — before or after committing?
5. Fund the **V2 decoder build** (tree-walk over the confirmed object model, replacing flat-scan + category heuristic — fixes the category leak and lossy conditionals) or bank the current decoder?
6. **Regression harness** — verification is scratchpad-only, so not reproducible from committed state; reference profiles are gitignored. Check in a harness with a skip-if-missing guard, or keep manual?
7. Branch cleanup — delete the 8 dead branches now?

---

## 7. Prioritized action list (corrected — now includes bug fixes)

"None require new research" no longer holds; the code fixes are real work. Still no research frontier.

**High — data-loss & release hygiene:**
- [ ] Fix generator output-path derivation (input-clobber, vap_generator.py:542). Active data-loss bug.
- [ ] `git fetch --prune` before any git decision; reconcile the stale-ref picture (§2).
- [ ] Commit or explicitly branch the 4 untracked truth-docs (§4).
- [ ] Write `VAP_Format_Specification.md` v0.2; retire/annotate the old spec and `VAP_Binary_Schema_Analysis.md` (§4).
- [ ] Fix `Project_Status.md`'s two self-contradictions + stale Open-list, or replace it (§5.1, §5.8).
- [ ] Update `CLAUDE.md` off "Complete and tested"; repoint `CLAUDE.md`/`SKILL.md` from `VAP_FORMAT.md` to the current spec (§5.2, §4).

**Medium — correctness & honesty:**
- [ ] Decoder: cap the last-command scan bound (Finding 5 root cause); fix cross-type key/mouse ordering; accept uncompressed-XML `.vap`; warn on dropped action types (§3.1).
- [ ] Generator: warn on unknown ActionType + return nonzero on warnings; fix scientific-notation durations; validate durations (§3.2).
- [ ] Reconcile decoder↔generator key-naming so round-trips don't drop keys (numpad + the wider gap) (§3.2).
- [ ] Fix README (missing command, undocumented features, repo-vs-package name); refresh drifted doc line-refs (§5.6-7).

**Low — hygiene:**
- [ ] Inspect then drop/apply `stash@{0}`; decide whether to tag 1.2.0.
- [ ] Delete the 8 dead branches (post-fetch); fix `SKILL.md` CLI docs; flag Finding 5 + lossy conditionals in source; purge residual "Contains=1"; decide the regression-harness question (§5, §6.2).

---

## 8. Ready-to-commit matrix (corrected)

| Item | Ready? | Note |
|---|---|---|
| Decoder fix commits (`4233a0e`, `3f94d6e`) | **Yes** — strict improvements | but `vap_decoder.py` still has the §3.1 defects; "clean" withdrawn |
| HEAD → main integration | **Yes** — merge verified conflict-free in a worktree | decision only |
| The 4 untracked truth-docs | **Almost** — coherent, current | commit vs V2 branch |
| `VAP_Format_Specification.md` as "the spec" | **No** | needs v0.2 consolidation |
| `Project_Status.md` | **No** | two self-contradictions + stale; refresh or retire |
| `CLAUDE.md` / `README.md` / `SKILL.md` | **No** | stale status, wrong pointers, under-documented, CLI mis-docs |
| Generator | **Ships already** | ships with a data-loss path bug (§3.2 #1) that deserves fixing regardless |
| Branch list / stash / settings | **Cleanup pending** | 8 branches deletable; stash + settings to resolve |

---

## One-line verdict (corrected)

The engine runs and the measurements are trustworthy, but the engine has a few real leaks and the dashboard is wired to last week's readings. The release actually shipped (1.2.0 is on GitHub — the clone was just stale); the genuinely stranded work is the 13-commit decoder line. **One consolidation pass (docs) plus one bug-fix day (tools) plus a `git fetch` and a handful of decisions** — no research frontier required — puts this in clean, honest, committable shape.

---

_**Canonical file.** This document (`Project_State_Review_Final_2026-07-09.md`) supersedes both `Project_Review_2026-07-09.md` (v1 + the inline stress-test annotations — keep as the working/audit trail) and the stale in-repo `Project_Status.md` (which §5 flags for refresh-or-retire). If only one review survives, this is it._

_**Untracked, by its own thesis.** This file is a new untracked item in the repo root — now one of several review docs there, exactly the proliferation §4 critiques. Decide deliberately: commit it as the project's status-of-record (and retire the other two), gitignore it, or keep it outside the eventual commit. It was placed here for visibility, not silently added to the tree._
