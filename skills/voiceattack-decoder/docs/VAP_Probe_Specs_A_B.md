# VAP Probe Spec — Probe B (draft, 2026-07-08)

Phase-3 probe spec for `VAP_Uncertainty_Research_Plan.md`, refined against the Phase-0–2
closure table. **One** hand-built profile. Export VAP **and** CSV together.

## Scope decision (2026-07-08) — Probe A dropped
The condition UI supports both nested and multi-conditioned (AND/OR compound) tests. We are
scoping our support to **nested single-condition** blocks (one comparison per Begin; e.g.
"if Boolean is X", "if text does not equal Y"). That form is ALREADY fully decoded from existing
data — the `nested + decimal` command (conditionals profile, depths 0/1/2) confirmed:
IndentLevel not stored (derived from Begin/End), m[17] pairing holds across depths, m[18] is the
running block ordinal. With no multi-conditioned Begins in scope, the m[18]-as-ConditionGroup
question dissolves. So the original **Probe A (`groups`) is unnecessary and is dropped.**

Consequence: multi-conditioned AND/OR compounds (m[31] interior) are **decode-only** — a decoder
reading a third-party compound-heavy profile (e.g. corinthian, m[31]≥2) emits the extra
sub-conditions as `unknown` per the V2 spec, rather than parsing them. Not a build target.

## Design rules
One variable per contrast; self-labeling operands (distinctive markers/values); nonzero anchors;
a duplicate control where order/code could confound; screenshot every dropdown swept.

## What Probe B must close (everything else is CLOSED on existing data)
Unlabeled ActionTypes **50/51** (start/stop listening) + Say/Launch/SetClipboard codes (item 1);
mouse context enum + X/Y (item 3); Set-Boolean m[14] value-vs-order (item 4); Set-op m[20] enum
and Set-SmallInt layout (item 5). (32/33 already closed = Marker / JumpToMarker; 24–27 dictation
already PLAUSIBLE.)

**Oracle:** alignment is by construction — you built it to this spec, and the swept dropdowns are
screenshotted. We do NOT rely on splitting multi-action CSV clauses (they don't split cleanly).
CSV is a secondary cross-check only.

---

## PROBE B — `actions`

Purpose: ActionType codes + member layouts for unsampled actions; Set-op m[20] enum; break the
Set-Boolean m[14] value-vs-order confound.

Build — one command per action, self-labeling params, each a **distinct category**:

| cmd phrase | action(s) | self-labeling params |
|---|---|---|
| `say test` | Say | text 'say-marker', volume **43**, rate **7** |
| `write test` | Write | text 'write-marker' (Say/Write code contrast) |
| `launch test` | Launch/Run application | path `C:\probe\launch-test.exe`, args `--a1 --a2`, workdir `C:\probe\wd` |
| `clip test` | Set Clipboard | 'clip-marker' |
| `bool order test` | **Set Boolean [bfa] to False**, then **Set Boolean [btr] to True** (no conditions, this exact order) | breaks value-vs-order |
| `set int sweep` | one Set Integer per value-source dropdown position, IN ORDER, each to a distinct target var siv0,siv1,siv2,… | each position takes whatever operand it needs (literal / another var / arithmetic operand) — do NOT force a fixed value; identify positions by the target var. Screenshot the full ordered dropdown |
| `set smallint test` | Set Small Int [ssi] to **33** | layout of AT=18 |
| `set decimal test` | Set Decimal [sd] to **4.44** | cross-check m[25]/m[15] |
| `mouse sweep` | Left Click; Left Double Click; Right Click; Scroll Forward **5** clicks; Move cursor to X=**333**,Y=**444** | screenshot mouse dropdown |
| `dictation set` | Start Listening; Stop Listening; Start Dictation; Stop Dictation; Clear Dictation Buffer; Paste Dictation (whichever exist) | closes 50/51, confirms 24–27 |

Give each command a **distinct category** (say / write / launch / clip / boolOrder / setIntSweep /
setSmall / setDec / mouse / dictation) — free data for the item-9 trailing region.

Screenshots required: Set-Integer value-source dropdown (full ordered list), mouse-action
dropdown, Say volume/rate fields, Set-Boolean True/False dropdown.

Predictions (state before reading bytes):
- P-B1: Set-op m[20] = dropdown index 0,1,2,… in listed order (positional coding, like operators).
- P-B2: `bool order test` — if m[14] is the VALUE, [bfa]→1 and [btr]→0 despite False-first order;
  if m[14] tracks serialization ORDER, [bfa]→0 and [btr]→1. (Decisive for item 4.)
- P-B3: Say volume 43 lands in a numeric slot — prime candidate m[14] (census showed m[14]=100
  on 16 objects, likely a default volume) with rate 7 in an adjacent slot; Say gets a new AT code.
- P-B4: Launch's three strings occupy three string slots (path/args/workdir); new AT code.
- P-B5: mouse context codes (LC/LDC/RC/SF) are strings in m[6]; scroll count 5 and X=333/Y=444
  land in numeric slots to be identified (fixed-header doubles m[3]/m[4] or heap slots).
- P-B6: dictation Start/Stop Listening resolve codes 50/51; the others reconfirm 24–27.

Analysis: walk each command; dump m[2] + every non-trivial slot; map the self-labeling markers
(43,7,33,4.44,5,333,444, and the *-marker strings) to slots to fix each layout.

Gate: user reviews this spec before building; STOP and wait for the export.
