# VoiceAttack Schema — Execution Plan

_Author: Claude (engineering) · Date: 2026-07-09 · Basis: `Project_State_Review_Final_2026-07-09.md` (status-of-record) + v1 review with audit annotations_

## Goal

Close out the current research program, roll every confirmed discovery into a **decoder V2**, formally park what remains unknown, and **release**. Produce a **canonical capability dictionary** — the single machine-readable statement of everything the decoder understands — as the contract the encoder module will be built against. The encoder must round-trip every function the decoder understands. Alongside: repo cleanup, full documentation reconciliation, branch rationalization, and the bookkeeping backlog from the reviews.

## Decisions this plan assumes (from the brief; confirm before Phase 0 executes)

| Review decision (§6.2) | Assumed answer |
|---|---|
| Fund V2 decoder build? | **Yes** — it is the vehicle for "discoveries rolled into a new version" |
| Commit untracked truth-docs or V2 branch? | **V2 branch** (`feature/decoder-v2`), folded to main at release |
| Write Spec v0.2 before or after committing? | **Before** — it gates the dictionary and V2 acceptance |
| Regression harness checked in? | **Yes**, with skip-if-missing guard for the gitignored reference profiles |
| Branch cleanup now? | **Yes** |
| Tag 1.2.0 retroactively? | **Recommend yes** (cheap, makes release history honest); release itself becomes **2.0.0** |
| Push decisions | Per standing workflow: nothing is pushed or merged to main without explicit approval at each gate |

## Status — updated 2026-07-09

| Phase | Status |
|---|---|
| 0 — Stabilize the repo | **Complete** (2026-07-09). Deviation: GitHub branch protection blocks direct pushes to main, so all main changes route via PR — the 13-commit decoder line landed as PR #15, doc consolidation as PR #16. `Version-1.2.0` tagged on `fa72978` and pushed. 9 branches deleted (the 8 dead + the merged feature branch). Stash dropped after review (superseded content). Truth docs committed on `feature/decoder-v2` (local, unpushed per plan). Backups: git bundle + untracked-docs tarball in `~/Projects`. |
| 1 — Generator hotfixes | **Complete** (2026-07-09, PR #17). All six fixes in. Lane B (Sonnet) implementation; Lane A review passed (diff read, adversarial cases independently re-run). All three examples byte-identical to pre-fix output modulo random GUIDs. Exit codes now 0 clean / 1 error / 2 warnings. |
| 2 — Research completion | **Blocked on human gate** — Probe B profile build + export requested from Richard 2026-07-09. |
| 3 — Spec consolidation | **3.1 complete** (2026-07-09): `VAP_Format_Specification.md` v0.2 authored on `feature/decoder-v2` — all nine review corrections + all Phase 0–2 closures folded, precedence rule stated, §13 reference algorithm fixed (deref rule + per-slot types), every open item routed to Probe B or PARKED in §12. Review + Closure Table marked historical. Independent transcription-fidelity check ran against all three sources; caught 3 defects (m[0] offset-vs-deref contradiction, m[23] shorthand, correction undercount), all fixed before commit. 3.2 (fold Probe B → v0.3) awaits the export. **3.3–3.4 complete** (2026-07-09, on `feature/decoder-v2`): HISTORICAL banners + in-place corrections on `VAP_FORMAT.md` (byte layout, scroll anchor, category list) and `VAP_Binary_Schema_Analysis.md` (offset-table refutation, stale numbers, phantom artifacts); all 11 catalog items resolved — CLAUDE.md status + pointers, decoder SKILL.md CLI docs, README missing command + decoder section, Conditional-Analysis history banner + two stale-open annotations, pinned-line-ref banners on Findings + Fix-Plan docs (items 1/3/5/8 were already resolved by Phase 0 / spec v0.2). Verification sweep: no refuted claim asserted outside bannered historical context. Deferred to Phase 6 per plan: dictionary-generated README/SKILL feature tables, line-ref refresh against frozen V2, repo-vs-package naming. Note: main's front door keeps the stale status line until the V2 fold — say the word to cherry-pick the CLAUDE.md/README fixes to main early. |
| 4 — Capability dictionary | **Complete** (2026-07-09, on `feature/decoder-v2`, commit `995abdd`). `schema/vap_capability_dictionary.json` (36 action types, 110 keys with canonical+alias resolution of the decoder↔generator naming gap, 34 mouse codes + 5 legacy aliases, full condition system) + `schema/VAP_Round_Trip_Contract.md` (fixpoint test, name-evolution rules) + `schema/dictionary_tools.py` (validate/render/audit, stdlib-only) + generated `VAP_Capability_Dictionary.md`. Lane A authored, Lane B built tooling + audited against live tool tables (caught 5 unmodeled generator mouse aliases — fixed). Audit exit 0: zero orphans, zero VK/code mismatches, render byte-stable. Pending-adoption lists from the audit define V2/encoder key-name scope. Dictionary amendment after Probe B remains open (Phase 4 step 4). |
| 5–8 | Pending. Phase 5 (decoder V2) is now unblocked on the dictionary side; its acceptance still wants Probe B closures (Phase 2, human-gated). |

## Out of scope — the parked-uncertainty register (Phase 2 formalizes this)

Compound AND/OR condition *encoding* (decode-only stays); header @8 command-list index (discovery remains walk/scan-based); the ~24 unmapped member slots; anything Probe B cannot close with one profile-export round. These go into a committed `VAP_Parked_Uncertainties.md` with enough context that a future session can resume any of them cold.

## Delegation model

Three lanes. Every delegated task names its lane; anything produced in Lane C or B that feeds the spec, dictionary, or release gets a Lane A review gate before it merges.

- **Lane A — frontier model (Fable/Opus):** spec authoring, V2 architecture and walker core, Probe B analysis, dictionary schema design, round-trip contract, all review gates.
- **Lane B — mid model (Sonnet):** generator hotfixes, regression harness, V2 non-core modules (output writers, CLI), doc rewrites from an approved outline, dictionary population from existing tables.
- **Lane C — small model (Haiku):** mechanical sweeps — branch deletion, stale-string purges, line-ref refreshes, README table generation from the dictionary, xmllint/jq verification runs, checklist audits.

**Human-gated steps (Richard):** build + export the Probe B profile in VoiceAttack; import-test V2 outputs and encoder-contract samples in VoiceAttack; approve each push/merge/tag; final release sign-off.

---

## Phase 0 — Stabilize the repo (Lane C, review Lane B) — ✅ COMPLETE 2026-07-09

Prereq: none. The fetch/prune already ran during the final review; state below assumes it.

1. Merge `feature/decode-conditional-actions` → `main` (verified conflict-free; manifest resolves 1.2.0). **Gate: approval to merge.**
2. Push main; push nothing else yet. **Gate: approval to push.**
3. Tag `1.2.0` on `fa72978`'s merge point if approved; push tag.
4. Delete the 8 dead branches (all verified merged/ancestor/patch-equivalent); local prune already done.
5. Stash: produce a diff report of `stash@{0}` (Jan CLAUDE.md WIP) for a keep/drop decision; then drop or apply. **Gate: Richard decides on sight of the diff.**
6. Review-doc consolidation: commit `Project_State_Review_Final_2026-07-09.md` as status-of-record; move `Project_Review_2026-07-09.md` (v1 + audit annotations) to `docs/history/`; retire `Project_Status.md` (its replacement is the final review + this plan). Commit this plan.
7. Delete the ghost `__pycache__` files; leave `.claude/settings.local.json` untracked (it is machine-local, correctly globally ignored).

Exit criteria: main == origin/main, one working branch (`feature/decoder-v2` created from main), zero stale branches, zero stashes, review docs deduplicated to one canonical + one archived.

## Phase 1 — Generator hotfixes (Lane B, review Lane A) — ✅ COMPLETE 2026-07-09 (PR #17)

The generator ships today and is NOT replaced by V2, so it gets fixed now. Decoder V1 defects are deliberately **not** hotfixed — every one of them is cured structurally by V2 (Phase 5 acceptance criteria); patching the flat-scan twice is waste.

1. Output-path derivation: replace the `.replace(".json", ".vap")` clobber path with proper suffix handling + refuse to write over the input. (The one data-loss bug.)
2. Unknown-ActionType: warn loudly, and exit nonzero when any warning fired.
3. Duration handling: decimal serialization (no scientific notation), floor/validation.
4. Unknown mouse action: warn and *skip*, never substitute `left_click`.
5. Accept JSON-numeric key codes or fail with a clear message (no raw tracebacks anywhere: missing file, bad JSON).
6. `scroll_clicks` leak into non-scroll actions: stop writing X/DecimalContext1 outside scroll.

Key-name gaps (numpad + the wider list) are NOT patched piecemeal here — Phase 4's dictionary becomes the generator's key table, fixing the whole class at once.

Exit criteria: all three examples still generate + xmllint clean; a small adversarial input set (from the audit scratchpad scenarios) runs without silence or tracebacks.

## Phase 2 — Complete the research (Lane A analysis; Lane C bookkeeping) — gated on export

1. **Kick off the human-gated step first:** Richard hand-builds the Probe B profile per `VAP_Probe_Specs_A_B.md` in VoiceAttack and exports it. Everything else in this phase queues behind that file.
2. Analyze the export: ActionTypes 50/51; Say/Launch/SetClipboard/mouse field layouts; Set-op operator enum (resolve climb=4 vs jumped=0); Set-Boolean value-vs-order confound; Set-SmallInt/Decimal layouts; mouse context enum + X/Y. Include the `scroll_clicks` field question (which of Duration/X/DecimalContext1 VoiceAttack actually reads) if the probe profile can carry a scroll command — closes a generator unknown for free.
3. Update the Uncertainty Closure Table with results; anything Probe B cannot close moves to `VAP_Parked_Uncertainties.md` (Lane C drafts from the closure table; Lane A reviews).
4. Formally retire the superseded probe docs (`Conditionals_Probe_2_*`) with in-file supersession notices (Lane C).

Exit criteria: every open item in the research plan is either CLOSED in the closure table or PARKED in the register with a resume-cold writeup. No third state.

## Phase 3 — Spec consolidation (Lane A) — ~1 day, can start immediately

1. Draft `VAP_Format_Specification.md` **v0.2** now: fold the Review's overrides and the existing Closure Table into the base; delete the five refuted assertions from the body; state the precedence rule explicitly (it is written down nowhere today). This does not wait for Probe B.
2. When Phase 2 lands, fold Probe B results → **v0.3**. That is the release spec.
3. Annotate-or-retire the stale layer: `VAP_FORMAT.md` (rewrite header to "historical; superseded by the Specification" + fix the byte-layout error), `VAP_Binary_Schema_Analysis.md` (in-place supersession banner over the refuted offset-table sections).
4. Purge the contradiction catalog (final review §5, all 11 items) across the docs corpus — Lane C sweep from an explicit item list, Lane A spot-review.

Exit criteria: one authoritative spec, zero refuted facts in any live doc body, every retired doc says so in its own first lines.

## Phase 4 — Canonical capability dictionary (Lane A schema; Lane B population) — ~1 day, after v0.2 draft

The deliverable the encoder is built against. One machine-readable file, one generated human view.

1. `schema/vap_capability_dictionary.json` — schema designed Lane A. Contents: every ActionType the decoder understands (id, name, fields, field encodings, context semantics); the full canonical key-name table (VK code ↔ one canonical name ↔ accepted aliases — resolves decoder `subtract` vs generator `numpad_subtract` by construction); mouse action/context codes; enums (operators, value-types, condition subtypes 19/63/29/20); duration semantics; conditional block structure as V2 will emit it. Each entry carries a confidence tag (`solid` / `inferred` / `parked`) traceable to the spec section that earns it.
2. Generated views: human-readable `VAP_Capability_Dictionary.md` plus the README/SKILL key tables, all generated from the JSON (Lane C runs generation; nothing hand-maintained twice).
3. **Round-trip contract (Lane A, short doc):** for every dictionary entry with confidence `solid`, decoder V2 MUST emit it in canonical form and the encoder MUST consume it; the acceptance test is the fixpoint `decode(encode(decode(x))) == decode(x)` over the reference profiles. `inferred` entries round-trip with a warning; `parked` entries are preserved as opaque blobs where feasible, never silently dropped.
4. Amend the dictionary after Probe B closes (new ActionTypes/layouts).

Exit criteria: dictionary validates against its schema; every name the decoder emits and every name the generator accepts appears in it; zero orphan names on either side (Lane C audit script).

## Phase 5 — Decoder V2 (Lane A core; Lane B periphery) — the build, ~3–5 days

Per `VAP_Decoder_V2_Preliminary_Spec.md`: tree-walk over the confirmed object model, replacing the flat scan and the category heuristic.

Acceptance criteria absorb the entire V1 defect list — these are requirements, not aspirations:
1. Category from the object graph, not last-string heuristic (kills the leak class: `boo`/`smal`, VK-alias letters, window titles, `vampire`, single-space).
2. Command bounds from the walk (kills the last-command over-scan — Finding 5's root cause).
3. Actions emitted in true byte/sequence order across types (kills key/mouse scrambling).
4. KeyDown/KeyUp/KeyToggle preserved as themselves (no PressKey flattening).
5. Conditionals decoded structurally — nested single-condition blocks with condition semantics, per the closed research (kills the lossy flattening; compound AND/OR stays parked, emitted with an explicit `parked` marker, never silently).
6. Say/Pause/ExecuteCommand/SetClipboard/Launch decoded per Probe B layouts; anything undecodable emits a warning, never silence.
7. Accepts uncompressed-XML `.vap`; clean errors on empty/truncated input; never writes into the input's directory by default; `--stdout` covers JSON too.
8. All names emitted in dictionary-canonical form.
9. **Regression harness checked in** (`tests/`): oracle comparisons (corinthian CSV, conditionals CSV), determinism run, fixpoint stubs for Phase 8; skip-if-missing guard on the gitignored profiles. Harness is Lane B; the walker core and the conditional emitter are Lane A; CLI/writers Lane B.

Exit criteria: harness green including all oracle checks V1 passed (no regressions) plus the nine criteria above; V1 kept in-tree during soak, deleted at release.

## Phase 6 — Documentation overhaul (Lane B from Lane A outline; Lane C sweeps) — ~1 day

1. `CLAUDE.md`: status line honest ("decoder V2 + research complete; encoder next"); repoint format docs to the Specification; document XML-variant handling; key/mouse tables replaced by dictionary-generated versions.
2. `README.md`: missing generate command; full feature documentation (chording, numpad, L/R modifiers, extended mouse) generated from the dictionary; fix repo-vs-package naming.
3. Both `SKILL.md`s: correct CLI behavior (decoder default output, `--stdout`, XML+JSON), dictionary-generated tables, V2 usage.
4. Line-ref refresh across docs (Lane C, against frozen V2 source).
5. `Project_Status.md` is already retired in Phase 0; confirm nothing still links to it.

Exit criteria: Lane C cross-reference audit finds zero broken doc pointers, zero stale line-refs, zero claims contradicting the spec or the dictionary.

## Phase 7 — Release (Lane B mechanics; human gates)

1. Version: **2.0.0** (output format changes: structured conditionals, canonical names). Manifest bump; changelog (info-level per preference).
2. Richard import-tests: a V2-decoded → generator-rebuilt profile, plus the three examples, in VoiceAttack. This is the only "tested" claim the docs will make, and it will be true.
3. Merge `feature/decoder-v2` → main, push, tag `2.0.0`. **Gates: approval at merge, push, and tag.**

## Phase 8 — Encoder kickoff (next project; Lane A design doc only)

Deliverable here is a design brief, not code: the encoder consumes decoder-V2 JSON and emits VoiceAttack-importable profiles covering every `solid` dictionary entry, with the fixpoint test as its definition of done. Open design question to settle in the brief: emit XML (VoiceAttack accepts it natively — recommended, evolves the generator) vs binary. The dictionary + round-trip contract from Phase 4 are its spec; the harness from Phase 5 is its test bed.

---

## Dependencies and parallelism

Phases 0, 1, and 3.1 start immediately and in parallel. Phase 2 starts now but blocks on the human export — request it on day one. Phase 4 follows the v0.2 draft; Phase 5 core design can start against v0.2 + the V2 preliminary spec while Probe B is pending, but V2 acceptance waits on Phases 2–4. Phases 6–7 are strictly last. Rough critical path: export turnaround + spec v0.3 + V2 build ≈ **6–8 working days** of agent time, thinly spread around the human gates.

## Standing rules for all phases

No pushes, merges to main, or tags without explicit approval at that gate. No writes ever into `reference profiles/` or `Screenshots/`. Every Lane B/C artifact feeding spec, dictionary, or release passes a Lane A review. Backup (git + a dated tarball of the untracked docs) before Phase 0 step 6 touches the review files.
