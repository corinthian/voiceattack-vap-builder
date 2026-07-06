# Decoder Fix Plan: Remove Category-Whitelist Dependency from Command Recognition

## Problem

`vap_decoder.py` fails to decode any commands from profiles whose category is not one of six hardcoded words. `zoom-if-else.vap` (category `camera`) decodes to `<Commands/>` — zero commands.

## Root Cause

`find_commands` (vap_decoder.py:261) does not parse the binary structurally. It detects commands heuristically: a string is treated as a command phrase **only if a known category string appears within ~800 bytes after it**. The category list is hardcoded at line 267:

```python
categories = {'keyboard', 'applications', 'interface', 'system', 'navigation', 'mouse'}
```

The category string is the anchor the entire detection scheme hangs on. When `category_positions` is empty (line 272), the inner loop at line 294 never runs, no phrase is accepted, and the command list comes back empty. Any profile using a category outside those six words — `camera`, `combat`, `flight`, anything a user names — decodes to nothing. This is general fragility, not specific to one file.

Confirmed empirically: adding `'camera'` to the set (source untouched, scratchpad copy) took `zoom-if-else.vap` from 0 commands to 1.

## Design Principle

Command **detection** must be decoupled from category **content**. Detection anchors on structure that is intrinsic to every command; the category becomes a plain field that is *read*, never a gate. Delete the whitelist — do not soften it to a "hint." The requirement is literal: recognition must never require a whitelisted category name.

## Required Prerequisite: Fix Profile Header Parsing

Before replacing command detection, fix `parse_profile`. The current parser skips to byte `364` by assuming:

```python
pos = 8 + item_count * 4
```

That is four bytes early for the reference profiles. The first top-level offset table entry points to the profile record at byte `368`; parsing at `364` produces a wrong profile GUID and only recovers the profile name later by fallback string search.

Implementation requirement:

1. Read `total_size` at byte `0`.
2. Read the top-level member count at byte `4`.
3. Read the top-level offset table beginning at byte `8`.
4. Use the first offset table entry as `profile_start`.
5. Read the profile GUID at `profile_start`.
6. Read the profile name immediately after the GUID.

Observed reference-profile values after this correction:

| Profile | Profile start | Correct profile name | Command count field |
|---------|---------------|----------------------|---------------------|
| base profile | 368 | `base profile` | 101 |
| corinthian-4 | 368 | `corinthian-4` | 201 |
| numkeys | 368 | `numkeys` | 7 |
| zoom-if-else | 368 | `Cities Skylines II` | 1 |

This prerequisite matters because the profile header can look like a command header. The self-match filter must compare against the correct profile GUID and/or the exact profile record start.

## The Anchor: Per-Command Signature

Every command record in the decompressed binary begins with the same structural signature:

```
[16-byte GUID][uint32 length][UTF-8 phrase][uint32 count][count × uint32 property-offset table]
```

This is documented in `VAP_Binary_Schema_Analysis.md` ("Number of offset entries; uint32[] offset table for command properties") and confirmed by inspection: `zoom [out; in]` sits at a GUID + length-prefixed phrase + `05 00 00 00` count + five offsets. An action's inner `Id` GUID is **not** followed by phrase-then-count-then-offset-table, so this combination distinguishes a command header from the GUIDs and strings buried inside actions.

The GUID must be validated as a real GUID, not padding. VoiceAttack pads and terminates fields with `FF FF FF FF` and `00 00 00 00`; leaf values (categories, Say text, mouse contexts) are preceded by that padding, while command headers are preceded by a random GUID. Rejecting 16-byte prefixes that contain a `0xFFFFFFFF` run, are mostly zero, or have a zero/`0xFFFFFFFF` first word cleanly separates the two.

### Detection algorithm (replaces the category-proximity heuristic)

1. Fix profile parsing first, then call `find_commands` with the correct profile GUID, profile name, and `profile_start`.
2. Walk the decompressed buffer. At each position, test the signature: 16 candidate GUID bytes, then a sane length prefix (1–500), then a cleanly-decoding printable UTF-8 phrase, then a plausible property count, then that many uint32 property offsets.
3. Reject the candidate unless the candidate GUID bytes pass the GUID-validity check: no `FFFFFFFF` run, not mostly zero, and first uint32 word is neither `0` nor `0xFFFFFFFF`.
4. Reject the candidate if it is the profile record: candidate start equals `profile_start`, candidate GUID equals the profile GUID, or candidate phrase equals the profile name and the candidate is before the first real command.
5. Validate the property-offset table before accepting the hit:
   - `1 <= count <= 128` for the initial implementation. Raise only if a real profile proves this too low.
   - The table must fit inside the buffer.
   - Every offset must be non-negative and less than the remaining buffer length.
   - Offsets should not all be identical.
   - Offset `32` is common and valid; do not reject it solely for being small.
6. On a hit, record the command start, phrase, GUID, property count, and offset table; skip past the offset table and continue scanning.
7. Derive command bounds from the next accepted command start, or from the end of the decompressed data for the last accepted command. If the profile command count and/or command-size table is confidently parsed, prefer those bounds.
8. Read the category as a free-form field inside the command bounds, with no membership check. See the category extraction rule below.

### Category extraction rule

The phrase is not the only length-prefixed string inside a command. Action branches may contain strings such as `out`, `{LASTSPOKENCMD}`, executable paths, script names, mouse contexts, and other operands. Therefore, "nearest string after the phrase" is not a valid category rule.

Initial implementation rule:

1. Collect all printable length-prefixed UTF-8 strings between the end of the command header and the command bound.
2. Exclude known action operands and metadata:
   - mouse context codes (`LC`, `RDC`, `SF`, etc.)
   - token operands beginning with `{` and ending with `}`
   - executable/window/path-like strings containing `\`, `/`, `.exe`, `.wav`, or starting with `*`
   - version-like strings matching `N.N...`, such as `2.1.8`
3. Prefer the last remaining printable string in the command bound.
4. If no candidate remains, set `category` to `uncategorized`.

This is still a heuristic, but it is scoped to category **extraction**, not command **detection**. The decoder must accept the command even when category extraction fails.

**Caveat — this rule is the weakest link.** "Prefer the last remaining printable string" is not guaranteed to select the category. It is not a structural slot; it is a positional guess, and it is the part of this plan most likely to break on a profile outside the four reference samples. The failure mode is visible even in the samples: trailing profile-level fields (for example the `2.1.8` version string after the final command) leak into the last command's bound, and the version/token/path exclusions above are patches over that leakage rather than a principled selection. Treat the exclusion list as provisional and expect to extend it. The durable fix is to locate the category's actual structural position within the command record — which is what the deferred container-walk (full member-table enumeration) provides. If category extraction proves noisy in practice, prefer promoting the container walk over piling on more content-based exclusion rules.

### Evidence this works

Signature scan + GUID-validity filter, run against all four reference profiles (source untouched):

| Profile | Whitelist result | New result | Real commands recovered |
|---------|------------------|------------|-------------------------|
| zoom-if-else (`camera`) | **0** | 2 hits → 1 command | `zoom [out; in]` ✓ |
| base profile | 43 in current checkout | 101 structural hits | `[press; hold] alpha` … ✓ |
| numkeys | **0** in current checkout | 8 hits → 7 commands | `num -`, `num 0-9` … ✓ |
| corinthian-4 | 105 in current checkout | 200 structural hits | `((EDDI docked))` … ✓ |

The whitelist's total failure on `camera` is gone; the real phrase decodes (not the `{LASTSPOKENCMD}` mis-read the old path produced when forced).

## Edge Cases and Mitigations

**Profile-name self-match.** Some profile headers can match the command signature (`Cities Skylines II`, `numkeys`, ...). Exclude this using the corrected `profile_start`, profile GUID, and profile name. Do not rely on the current `parse_profile` output until the prerequisite header fix is complete.

**Residual leaf-value false positives on complex profiles.** corinthian-4 can surface non-commands (a `.wav` sound path, a `Script` name, a `signal_source` context var) whose bytes coincidentally satisfy the signature. Use the concrete property-offset validation above. If false positives remain, parse and use command bounds from the profile command table instead of broad next-hit bounds.

**Profile command table ambiguity.** The profile record contains a command count, but the following integers are not always a simple list of command byte lengths across all reference profiles. `numkeys` and `zoom-if-else` behave like simple command-size tables; larger profiles include additional member-table data. Do not implement a blind `sum(lengths)` parser. Use the count as a cross-check first; only use table-derived bounds once the exact member-table structure is verified.

**No false negatives observed.** Every real command in every sample profile appears in the scan. The failure mode of the new approach is occasional over-matching on complex profiles, which is a strictly better failure than the whitelist's silent total loss — and it is filterable.

## Regression Bar

- Add an automated regression harness for the four checked-in profiles under `reference profiles/`.
- Header parsing returns the correct profile GUID and name for all four reference profiles.
- `zoom-if-else.vap` decodes exactly one command with phrase `zoom [out; in]` and category `camera`.
- `numkeys-Profile.vap` decodes seven commands, including `num -`, `num *`, `num .`, `num /`, `num +`, `num 0-9`, and `num lock`.
- `base profile-Profile.vap` decodes around 101 structural commands and includes `[press; hold] alpha`.
- `corinthian-4-Profile.vap` decodes around 200 structural commands and includes `((EDDI docked))`.
- Command detection must not depend on category content. Category extraction may be heuristic, but command acceptance cannot require a known category string.
- No category name appears anywhere in the detection path — grep the diff to confirm the whitelist set is deleted, not relocated.

## Explicitly Out of Scope

This fixes **detection**. It does not fix **action decoding**. Even once `zoom-if-else.vap` is detected, its actions decode wrong — the conditional / `{LASTSPOKENCMD}` branch is flattened to a single `R` keypress, because the string-and-pattern action parser was never built for condition blocks or token operands. That is a separate second failure (the `if/else` technique) and a separate piece of work. Keep it out of this change so the category fix stays small and verifiable.

## Effort and Risk

Moderately contained: the main behavior change is still localized to `find_commands`, but `parse_profile` must be fixed first so GUID/name parsing and profile-header self-match filtering are correct. No new dependencies are needed. Primary risk is tuning the GUID-validity, offset-table validation, and category extraction rules across profiles beyond the four samples.

The nested-container walk (full structural enumeration via the member table) remains the stronger long-term foundation. It is not required to remove the category-whitelist dependency, but if the scanner cannot eliminate false positives cleanly, the next step should be parsing command bounds structurally rather than adding more content-based filters.
