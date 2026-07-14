---
name: voiceattack-generator
description: Generate VoiceAttack .vap profiles from JSON
---

# VoiceAttack Profile Generator

Generate valid VoiceAttack `.vap` profiles from simple JSON input.

## Instructions

When the user wants to generate a VoiceAttack profile:

1. Read their JSON input file (or extract from screenshot - see below)
2. Present command summary and offer review (see "Review Before Generation")
3. Run the generator (from `<skill-dir>/scripts`): `python3 -m gen2 <input.json> <output.vap>`
4. Report the output file location and command count

The generator auto-detects its input: the simple authoring format below, or normative
schema-v1.1 JSON (a decoder output). Run with `-h` for full usage; `--no-idiom` disables
overloaded-trigger auto-lowering. Exit codes: 0 clean, 1 hard-fail (no file written),
2 written with warnings.

> The legacy `scripts/vap_generator.py` is retained in-tree during soak but is no longer
> the entry point — it cannot emit the newer action types (dictation/listening, clipboard,
> the Set family). Always invoke `gen2`.

## Screenshot Extraction

When the user provides a screenshot of game keybindings:

1. **Analyse the image** - Identify the keybinding UI layout (list, grid, or categorised sections)

2. **Extract mappings** - For each visible binding, capture:
   - The action name (convert to natural speech for the voice trigger)
   - The assigned key/button
   - The category (if the game groups bindings)

3. **Handle ambiguity:**
   - If a key is unreadable, ask the user
   - If an action name is unclear, use the game's terminology and add alternatives: `"[dock; docking]"`
   - Skip unbound actions unless the user wants placeholders

4. **Generate JSON** - Write to a file:
   ```json
   {
     "name": "<Game Name>",
     "commands": [
       {"_section": "=== CATEGORY ==="},
       {"trigger": "<natural phrase>", "key": "<key>", "category": "<category>"}
     ]
   }
   ```

5. **Review step** - See "Review Before Generation" section below

6. **Run generator** - Convert JSON to VAP

7. **Report to user** - State command count and list any skipped/unclear bindings

## Review Before Generation

After generating JSON (either from user-provided file or screenshot extraction), allow the user to review and edit before creating the VAP file.

### 1. Present Command Summary

Show commands in a readable table format:

```
Trigger Phrase      | Key/Action   | Category
--------------------|--------------|----------
fire weapon         | space        | combat
reload              | r            | combat
left click          | mouse L      | mouse
open inventory      | i            | interface
```

### 2. Ask User

"Would you like to make any changes before generating the profile?"

Options:
- **Generate now** - Proceed directly to VAP generation
- **Make changes** - Describe edits in plain English
- **Download JSON** - Get the JSON file for external editing

### 3. Handle Edit Requests

If user wants to make changes, accept natural language requests:

- "Change 'fire weapon' to 'shoot'"
- "Remove the reload command"
- "Change all combat triggers to start with 'combat'"
- "Add a command for 'jump' on spacebar"
- "Make 'press alpha' just 'alpha'"

Apply edits to the JSON, show updated summary table, and ask again. Repeat until user is satisfied.

### 4. Handle JSON Download/Upload

If user wants to edit externally:

1. Provide JSON file for download
2. User edits in their preferred editor (bulk find/replace, etc.)
3. User uploads edited JSON back
4. Validate JSON structure and show updated summary
5. Return to step 2 (ask about further changes)

### 5. Generate VAP

Once user confirms, run the generator with the final JSON.

## JSON Input Format

```json
{
  "name": "Profile Name",
  "commands": [
    {"trigger": "[spoken; phrase]", "key": "a", "category": "keyboard"},
    {"trigger": "click", "mouse": "left_click", "category": "mouse"},
    {"trigger": "copy", "actions": [
      {"type": "KeyDown", "keys": ["ctrl"]},
      {"type": "PressKey", "keys": ["c"], "duration": 0.1},
      {"type": "KeyUp", "keys": ["ctrl"]}
    ], "category": "keyboard"}
  ]
}
```

## Action Types

| Type | Parameters |
|------|------------|
| PressKey | keys, duration (default 0.1) |
| KeyDown | keys |
| KeyUp | keys |
| KeyToggle | keys (press once = down, again = up) |
| MouseAction | action, scroll_clicks; cursor_move takes x, y (a move `duration`/animation is deferred to a future release - a plain move is emitted and the timing dropped with a warning) |
| Pause | duration (seconds) |
| Say | text, volume (0-100), rate |
| SetDecimal | variable, value (number) - sets a decimal variable (carrier VoiceAttack-import confirmed) |
| SetText | variable, value (string) - sets a text variable |
| SetBoolean | variable, value (true/false) - sets a boolean variable |
| SetInteger | variable, value (integer, Int32 range) - sets an integer variable |
| QuickInput | text - types text into the focused field (variable tokens work) |
| SetClipboard | text - copies text to the Windows clipboard |
| Write | text - writes to the VoiceAttack event LOG, not keystrokes; variable tokens like {DEC:var} work |
| DictationMode / StopDictation / ClearDictationBuffer | (no parameters) - start / stop / clear VoiceAttack dictation |
| StartListening / StopListening | (no parameters) - start / stop VoiceAttack listening (note: StopListening stops VA hearing further speech) |
| BeginCondition | condition (required) - opens an if block |
| ElseIf | condition (required) - else-if branch |
| Else | (no parameters) - else branch |
| EndCondition | (no parameters) - closes the block |

## Condition Blocks

Interleave condition actions with ordinary actions to branch inside a command. `BeginCondition`/`ElseIf` require a `condition` object: `{"valueType": "Text", "operator": "<name>", "leftOperand": "<string>", "value": "<string>"}`. Text operators: Equals, Does Not Equal, Starts With, Does Not Start With, Ends With, Does Not End With, Contains, Does Not Contain, Has Been Set, Has Not Been Set. Nesting and `Else` are supported.

```json
{"trigger": "zoom [out; in]", "actions": [
  {"type": "BeginCondition", "condition": {"valueType": "Text", "operator": "Ends With", "leftOperand": "{LASTSPOKENCMD}", "value": "out"}},
  {"type": "PressKey", "keys": ["f"], "duration": 1.5},
  {"type": "ElseIf", "condition": {"valueType": "Text", "operator": "Ends With", "leftOperand": "{LASTSPOKENCMD}", "value": "in"}},
  {"type": "PressKey", "keys": ["r"], "duration": 1.5},
  {"type": "EndCondition"}
]}
```

**Scope:** `valueType` must be `"Text"` - other value types (SmallInteger/Boolean/Integer/Decimal) are rejected because their XML carriers are unverified.

**Validation:** unlike other generator defects (warn-and-drop), any malformed condition structure aborts generation with exit 1 and no output file - a dropped condition action would corrupt the block's pairing indexes and produce an importable-but-broken profile. Malformed `SetDecimal` (missing/empty `variable`, non-numeric `value`) and `Write` (missing/non-string `text`) hard-fail the same way.

## Mouse Actions

**Buttons:** left, middle, right, back, forward
**Actions:** click, double_click, triple_click, down, up, toggle
**Scroll:** scroll_up, scroll_down, scroll_left, scroll_right

Format: `{button}_{action}` (e.g., `left_click`, `right_double_click`, `back_toggle`)

## Key Names

**Letters:** a-z | **Numbers:** 0-9 | **F-keys:** f1-f12
**Special:** enter, escape, space, tab, backspace, delete, insert, home, end, pageup, pagedown
**Arrows:** left, up, right, down
**Modifiers (generic):** shift, ctrl, alt, win
**Modifiers (left/right):** lshift, rshift, lctrl, rctrl, lalt, ralt, lwin, rwin
**Numpad:** numpad0-numpad9, numpad_add, numpad_subtract, numpad_multiply, numpad_divide, numpad_decimal, numpad_separator

## Key Chording

To press multiple keys simultaneously (e.g., Ctrl+V), use a single PressKey action with multiple keys. Use left/right specific modifiers for reliable chording:

```json
{"trigger": "paste", "actions": [
  {"type": "PressKey", "keys": ["lctrl", "v"], "duration": 0.1}
]}
```

## Command Phrase Syntax

- `[word1; word2]` - Alternatives (either triggers command)
- `[word;]` - Optional word (trailing semicolon)

## Overloaded-Trigger Idiom (auto-lowering)

When a trigger has exactly one alternative group with N options **and** the command has N
parallel same-type actions, the generator auto-lowers it to a `{LASTSPOKENCMD}` conditional
dispatch chain — each spoken alternative fires its matching action. So this:

```json
{"trigger": "zoom [out; in]", "actions": [
  {"type": "PressKey", "keys": ["f"]},
  {"type": "PressKey", "keys": ["r"]}]}
```

means "zoom out" presses `f` and "zoom in" presses `r`. The mapping is proven safe by
simulating dispatch over every utterance the trigger produces; if two alternatives would
collide, generation hard-fails rather than emit an ambiguous chain. Disable with
`--no-idiom` or per-command `"idiom": false`.
