# VAP Decoder V2 — JSON Output Schema (FROZEN)

Version 1.1 · frozen 2026-07-11 at W5 exit (plan §5 freeze gate); amended same day in review, before any consumer existed. This document, not the code, is the contract the generator/encoder refactor is authored against (plan §9). JSON is the normative, lossless decode output; `schema_version` is `2`. Changing or removing a field here is a MAJOR bump requiring a migration note; adding an optional field is MINOR.

**v1.0 → v1.1 migration note (category null).** `category.value` is now `<str>|null`; `null` means the command has no category (VoiceAttack's empty-category state). v1.0's synthetic `"uncategorized"` placeholder is no longer emitted — an encoder writing it back would invent a category the profile never had. No consumer existed at v1.0, so this amendment predates all readers.

One rule governs every field: **no value depends on a byte offset to be interpretable.**
Offsets (`offset`, `head`, `regionOffset`) are provenance annotations only. Everything an
encoder needs to rebuild an action is a name, a code, or a self-contained value (output
contract §5).

## Top level

```
{
  "schema_version": 2,
  "decoder": "vap2",
  "dictionary_version": "0.2.0",   // dictionary the names were emitted from
  "source": "xml",                 // present ONLY when the input was XML (else binary)
  "profile": { … },
  "commands": [ … ],
  "census": { … }
}
```

## profile

```
{ "id": "<guid>", "name": "<str>",
  "declaredSize": <int>, "actualSize": <int>,   // binary only
  "commandCount": <int> }
```

## census (measured coverage, plan §7)

```
{ "totalActions": <int>, "decoded": <int>, "unknownMarked": <int>,
  "chainBreaks": <int>,
  "unknownBudgetFromHistogram": <int>,          // R3 tripwire budget = actions whose m[2]
                                                //   code is not in the dictionary
  "histogram": { "<code>": { "count": <int>, "attributed": <bool> }, … } }
```

`unknownMarked` counts actions emitted with `"decoded": false`. The R3 abort tripwire
(plan §7) compares `unknownMarked` against `unknownBudgetFromHistogram`: any *attributed*
code landing unknown means a slot map is wrong.

## command

```
{ "id": "<guid>", "phrase": "<CommandString>", "guidOffset": <int>,
  "actionCount": <int>, "chainEnd": <int>, "chainOk": <bool>,
  "category": { "value": "<str>|null", "provenance": "heuristic",
                "regionOffset": <int>, "regionLength": <int> },
  "actions": [ <action>, … ] }
```

`category.provenance` is always `"heuristic"` (binary) or `"xml"` — never a bare decoded
field (prelim §7); it is the weakest link and honestly tagged. `category.value` is `null`
when the command has no category — never a synthetic placeholder (v1.1 migration note).

## action — common fields

Every action carries provenance (the re-decode lifeline, prelim §6):

```
{ "index": <int>,
  "actionType": { "code": <int|null>, "name": "<canonical>|null", "confidence": "<str>" },
  "offset": <int>, "head": <int>, "guid": "<guid>",
  "indentLevel": <int>,        // derived from Begin/End nesting (spec §8.7), NOT stored
  … family-specific fields … }
```

### Unknown action (`decoded: false`)

Emitted when an ActionType code is not in the dictionary, an envelope assertion fails, or
the chain breaks. Carries the raw 34-slot member table so it can be re-decoded or passed
through opaquely by the encoder (round-trip contract §3):

```
{ "decoded": false, "index": <int>, "actionTypeCode": <int|null>,
  "offset": <int>, "head": <int|null>, "guid": "<guid>|null",
  "members": [<u32>×34] | null, "reason": "<str>" }
```

### Family fields (all reads gated per spec §9; absent fields omitted)

| Family (code) | Fields |
|---|---|
| PressKey (0) | `duration` (s), `keyCodes: [{vk,name}]` |
| KeyDown/Up/Toggle (8/9/67) | `keyCodes` (duration is 0 by definition) |
| Pause (2) | `duration` |
| Say (13) | `text`, `voiceGuid`, `voiceName`, `volume`, `rate` |
| MouseAction (12) | `contextCode`, `action` (name), `clickDuration`?, `scroll_clicks`?, `x`/`y` (Move), `parameter`? (SPECIAL) |
| Launch (3) | `executablePath`, `arguments`, `workingDirectory` |
| SetClipboard (24), Write (23) | `text` |
| Set Text (21) | `targetVariable`, `value` |
| Set Boolean (36) | `targetVariable`, `value` (bool) or `valueSource` marker for modes 2–6 |
| Set Integer (37) | `targetVariable`, `valueSourceMode`, then mode-gated: `value` / `source`+operands / `operation` |
| Set Decimal (38) | `targetVariable`, `value` (exact decimal string) |
| Dictation Start (25) | `clearBufferFlag`? (plausible) |
| Recognized, operands undecoded (16/17/18/22/32/33/35/40/62/64) | `fieldsDecoded: false`, `note`, `members` |

> **Known passthrough gap (encoder-facing).** For the `fieldsDecoded: false` families, `members`
> holds the 34 raw member *offsets*, not the dereferenced values — so an encoder cannot yet pass
> these actions through byte-for-byte from JSON alone (round-trip contract #4). Most visible case:
> **ExecuteCommand (16)**, the 2nd-commonest action in corinthian (201×), whose target-command
> **GUID sits in m[6]** but is left undecoded because code 16 has no SOLID slot map (spec §9.1;
> plan §3 out-of-scope). Promoting it is a cheap spec follow-up (read m[6] as the target GUID); until
> then these actions round-trip only if the encoder is handed the source bytes, not just this JSON.

`scroll_clicks` is a name-level split from the shared Duration slot m[3] so the encoder
never guesses which semantic applies (output contract §5). `Set Integer` operands are read
ONLY per `valueSourceMode` (m[14]); stale operand slots for other modes are never surfaced
(spec §6.4 hazard).

## condition (a field on the action, spec §5 — not a separate action type)

Present on Begin (19), Else If (63), Begin Loop While (30):

```
"condition": {
  "valueType": { "code": <int>, "name": "<Text|Integer|…>" },
  "operator":  { "code": <int>, "name": "<Equals|…>" },
  "leftOperand": "<token or var name>",
  "value": <int|bool|"decimal string"|"text">,   // OMITTED for valueless operators
  "pairing": <int>,          // 0-based index of the paired action (authorable, not a byte offset)
  "blockOrdinal": <int>,
  "compound": { "subConditions": <n>, "decoded": false, "note": "…" }   // only if compound
}
```

Block-structure actions End (20), Else (29), End Loop (31) carry only:

```
"block": { "pairing": <int> }
```

The **value key is suppressed by the operator** (Has Been Set / Has Not Been Set), never by
inspecting the slot — i32 −1 is byte-identical to the absent sentinel (spec §8.3). Compound
blocks emit the first sub-compare plus the `compound` marker; the remaining sub-conditions
are decode-only until the m[31] interior is decoded (parked #1).

When the **left operand (m[19]) is absent**, the compare is not identifiable — m[24]=0
(SmallInteger) and m[20]=0 (Equals) are byte-identical to unset (spec §8.1), so the decoder
does NOT assert those defaults. It emits `valueType.name` and `operator.name` as `null` plus:

```
"unresolved": { "decoded": false, "reason": "left operand (m[19]) absent; …" }
```

Seen on Begin Loop While and compound Begins whose sub-compares live off the normal slots
(11 of corinthian's 153 compares). `pairing`, `blockOrdinal`, and `compound` remain valid.
