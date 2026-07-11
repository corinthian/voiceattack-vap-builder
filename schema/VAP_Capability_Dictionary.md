GENERATED from vap_capability_dictionary.json v0.2.0 — do not hand-edit; regenerate with dictionary_tools.py render

# VAP Capability Dictionary

- Name: vap_capability_dictionary
- Version: 0.2.0
- Date: 2026-07-11
- Spec: skills/voiceattack-decoder/docs/VAP_Format_Specification.md v0.3
- Purpose: Single machine-readable statement of everything the VAP decoder understands. Contract for decoder V2 output and the encoder module's input. All key/mouse/action names in both tools derive from this file; nothing is hand-maintained twice.
- Canonical rule: Tools EMIT canonical names only and ACCEPT canonical + all listed aliases. Adding an alias is non-breaking; changing a canonical name is breaking (bump major). Decoder-v1 legacy names are preserved as aliases so previously decoded JSON keeps regenerating.

## Confidence Legend

- **solid**: object-walk or oracle verified per spec v0.2; round-trips canonically
- **plausible**: single-source or confound not eliminated; round-trips with a warning
- **inferred**: standard/documented value never verified in an imported profile; round-trips with a warning
- **parked**: location/meaning open (spec sec 12); preserved as opaque marker, never silently dropped

## Action Types

| Code | Canonical | XML Name | Confidence | Round-Trip | Notes |
|---|---|---|---|---|---|
| 0 | PressKey | PressKey | solid | canonical |  |
| 2 | Pause | Pause | solid | canonical |  |
| 3 | Launch | Launch | solid | canonical | Binary code + layout closed by Probe B (path 'C:\probe\launch-test.exe', args '--a1 --a2', workdir 'C:\probe\wd'). Decoder v1 emits run_application - name reconciliation is V2/encoder scope. |
| 8 | KeyDown | KeyDown | solid | canonical |  |
| 9 | KeyUp | KeyUp | solid | canonical |  |
| 12 | MouseAction | MouseAction | solid | canonical | Context enum sweep, click duration, scroll count, and cursor Move closed by Probe B. |
| 13 | Say | Say | solid | canonical | Binary code + full layout closed by Probe B (self-labeling: text 'say-marker', volume 43, rate 7). |
| 16 | ExecuteCommand | ExecuteCommand | solid | warn | Binary code CSV-confirmed; member layout unmapped; XML name from external reference |
| 17 | KillCommand | — | solid | warn |  |
| 18 | SetSmallInt | — | parked | opaque | MOOT in VoiceAttack 2: Small Int merged into Integer (Probe B, user-confirmed in-profile). Building 'Set Small Int' in VA2 serializes as ActionType 37 (SetInteger) mode 0, not this code. Code 18 retained legacy/decode-only for pre-VA2 profiles; its own layout cannot be re-sampled from a VA2 build and stays unmapped. |
| 19 | BeginCondition | — | solid | canonical | Compare gate: m[2] in {19,63,30}. Compound (multi-sub-condition) blocks are decode-only: emit first sub-compare + explicit compound marker |
| 20 | EndCondition | — | solid | canonical |  |
| 21 | SetText | — | solid | warn |  |
| 22 | ExecuteExternalPlugin | — | solid | warn |  |
| 23 | Write | — | solid | warn | Write-to-log/screen; distinct from Say (13). Text field reconfirmed by Probe B ('write-marker'); color/shape UI parameters found in no nonzero slot with one default-value sample - parked, see VAP_Parked_Uncertainties.md item 6. |
| 24 | SetClipboard | SetClipboard | solid | canonical | Binary code + layout closed by Probe B (text 'clip-marker'). REFUTES the removed 'PasteDictation' entry (was binary_code 24, confidence plausible): 'Paste Dictation' does not exist as a VoiceAttack 2 action - confirmed in-profile (Probe B's dictation sweep recorded a SetClipboard action whose text field reads "No such action as 'Paste dictation'", not a distinct action type). |
| 25 | DictationMode | — | solid | warn | Start Dictation Mode. Promoted solid by Probe B (self-labeling command-phrase build). |
| 26 | StopDictation | — | solid | warn | Stop Dictation Mode. Promoted solid by Probe B. |
| 27 | ClearDictationBuffer | — | solid | warn | Promoted solid by Probe B. |
| 29 | Else | — | solid | canonical |  |
| 30 | BeginLoopWhile | — | solid | canonical |  |
| 31 | EndLoop | — | solid | canonical |  |
| 32 | Marker | — | solid | warn |  |
| 33 | JumpToMarker | — | solid | warn |  |
| 35 | PlaySound | — | solid | warn |  |
| 36 | SetBoolean | — | solid | warn | m[14] is the same value-source-mode concept as SetInteger's m[14] but a DIFFERENT per-type dropdown ordering - do not conflate |
| 37 | SetInteger | — | solid | warn | Set Small Int (code 18) is legacy/decode-only in VA2 - see that entry. Decoder hazard: m[16]/m[19]/m[23] may hold stale values from a previously-selected mode; gate every read on m[14], never infer mode from which slots are populated (plausible, single-sample). |
| 38 | SetDecimal | — | solid | warn |  |
| 40 | QuickInput | — | solid | warn |  |
| 50 | StartListening | — | solid | warn | Start VoiceAttack Listening. Closed by Probe B; no fields observed beyond the shared envelope - layout is empty, not unknown. |
| 51 | StopListening | — | solid | warn | Stop VoiceAttack Listening. Closed by Probe B; no fields observed beyond the shared envelope - layout is empty, not unknown. |
| 62 | PauseVariable | — | solid | warn | Pause a variable number of seconds; distinct from fixed Pause (2) |
| 63 | ElseIf | — | solid | canonical |  |
| 64 | ExitCommand | — | solid | warn |  |
| 67 | KeyToggle | KeyToggle | solid | canonical |  |

## Keys

### letters

| Canonical | VK (dec) | VK (hex) | Aliases | Confidence |
|---|---|---|---|---|
| a | 65 | 0x41 | — | solid |
| b | 66 | 0x42 | — | solid |
| c | 67 | 0x43 | — | solid |
| d | 68 | 0x44 | — | solid |
| e | 69 | 0x45 | — | solid |
| f | 70 | 0x46 | — | solid |
| g | 71 | 0x47 | — | solid |
| h | 72 | 0x48 | — | solid |
| i | 73 | 0x49 | — | solid |
| j | 74 | 0x4A | — | solid |
| k | 75 | 0x4B | — | solid |
| l | 76 | 0x4C | — | solid |
| m | 77 | 0x4D | — | solid |
| n | 78 | 0x4E | — | solid |
| o | 79 | 0x4F | — | solid |
| p | 80 | 0x50 | — | solid |
| q | 81 | 0x51 | — | solid |
| r | 82 | 0x52 | — | solid |
| s | 83 | 0x53 | — | solid |
| t | 84 | 0x54 | — | solid |
| u | 85 | 0x55 | — | solid |
| v | 86 | 0x56 | — | solid |
| w | 87 | 0x57 | — | solid |
| x | 88 | 0x58 | — | solid |
| y | 89 | 0x59 | — | solid |
| z | 90 | 0x5A | — | solid |

### digits

| Canonical | VK (dec) | VK (hex) | Aliases | Confidence |
|---|---|---|---|---|
| 0 | 48 | 0x30 | — | solid |
| 1 | 49 | 0x31 | — | solid |
| 2 | 50 | 0x32 | — | solid |
| 3 | 51 | 0x33 | — | solid |
| 4 | 52 | 0x34 | — | solid |
| 5 | 53 | 0x35 | — | solid |
| 6 | 54 | 0x36 | — | solid |
| 7 | 55 | 0x37 | — | solid |
| 8 | 56 | 0x38 | — | solid |
| 9 | 57 | 0x39 | — | solid |

### function

| Canonical | VK (dec) | VK (hex) | Aliases | Confidence |
|---|---|---|---|---|
| f1 | 112 | 0x70 | — | solid |
| f10 | 121 | 0x79 | — | solid |
| f11 | 122 | 0x7A | — | solid |
| f12 | 123 | 0x7B | — | solid |
| f2 | 113 | 0x71 | — | solid |
| f3 | 114 | 0x72 | — | solid |
| f4 | 115 | 0x73 | — | solid |
| f5 | 116 | 0x74 | — | solid |
| f6 | 117 | 0x75 | — | solid |
| f7 | 118 | 0x76 | — | solid |
| f8 | 119 | 0x77 | — | solid |
| f9 | 120 | 0x78 | — | solid |

### special

| Canonical | VK (dec) | VK (hex) | Aliases | Confidence |
|---|---|---|---|---|
| backspace | 8 | 0x08 | — | solid |
| delete | 46 | 0x2E | — | solid |
| end | 35 | 0x23 | — | solid |
| enter | 13 | 0x0D | return | solid |
| escape | 27 | 0x1B | esc | solid |
| home | 36 | 0x24 | — | solid |
| insert | 45 | 0x2D | — | solid |
| pagedown | 34 | 0x22 | — | solid |
| pageup | 33 | 0x21 | — | solid |
| pause | 19 | 0x13 | pause_break | inferred |
| printscreen | 44 | 0x2C | — | inferred |
| space | 32 | 0x20 | — | solid |
| tab | 9 | 0x09 | — | solid |

### arrows

| Canonical | VK (dec) | VK (hex) | Aliases | Confidence |
|---|---|---|---|---|
| down | 40 | 0x28 | — | solid |
| left | 37 | 0x25 | — | solid |
| right | 39 | 0x27 | — | solid |
| up | 38 | 0x26 | — | solid |

### modifiers

| Canonical | VK (dec) | VK (hex) | Aliases | Confidence |
|---|---|---|---|---|
| alt | 18 | 0x12 | — | solid |
| ctrl | 17 | 0x11 | control | solid |
| lalt | 164 | 0xA4 | — | solid |
| lctrl | 162 | 0xA2 | lcontrol | solid |
| lshift | 160 | 0xA0 | — | solid |
| lwin | 91 | 0x5B | win, windows | solid |
| ralt | 165 | 0xA5 | — | solid |
| rctrl | 163 | 0xA3 | rcontrol | solid |
| rshift | 161 | 0xA1 | — | solid |
| rwin | 92 | 0x5C | — | solid |
| shift | 16 | 0x10 | — | solid |

### punctuation

| Canonical | VK (dec) | VK (hex) | Aliases | Confidence |
|---|---|---|---|---|
| backslash | 220 | 0xDC | — | solid |
| bracket_left | 219 | 0xDB | lbracket | solid |
| bracket_right | 221 | 0xDD | rbracket | solid |
| comma | 188 | 0xBC | — | solid |
| equals | 187 | 0xBB | — | solid |
| grave | 192 | 0xC0 | backtick | solid |
| minus | 189 | 0xBD | — | solid |
| period | 190 | 0xBE | — | solid |
| quote | 222 | 0xDE | — | solid |
| semicolon | 186 | 0xBA | — | solid |
| slash | 191 | 0xBF | — | solid |

### locks

| Canonical | VK (dec) | VK (hex) | Aliases | Confidence |
|---|---|---|---|---|
| capslock | 20 | 0x14 | caps | solid |
| numlock | 144 | 0x90 | — | solid |
| scrolllock | 145 | 0x91 | — | solid |

### numpad

| Canonical | VK (dec) | VK (hex) | Aliases | Confidence |
|---|---|---|---|---|
| numpad0 | 96 | 0x60 | num0 | solid |
| numpad1 | 97 | 0x61 | num1 | solid |
| numpad2 | 98 | 0x62 | num2 | solid |
| numpad3 | 99 | 0x63 | num3 | solid |
| numpad4 | 100 | 0x64 | num4 | solid |
| numpad5 | 101 | 0x65 | num5 | solid |
| numpad6 | 102 | 0x66 | num6 | solid |
| numpad7 | 103 | 0x67 | num7 | solid |
| numpad8 | 104 | 0x68 | num8 | solid |
| numpad9 | 105 | 0x69 | num9 | solid |
| numpad_add | 107 | 0x6B | num_add, add | solid |
| numpad_decimal | 110 | 0x6E | num_decimal, decimal | solid |
| numpad_divide | 111 | 0x6F | num_divide, divide | solid |
| numpad_multiply | 106 | 0x6A | num_multiply, multiply | solid |
| numpad_separator | 108 | 0x6C | num_separator, separator | inferred |
| numpad_subtract | 109 | 0x6D | num_subtract, subtract | solid |

### media

| Canonical | VK (dec) | VK (hex) | Aliases | Confidence |
|---|---|---|---|---|
| media_stop | 178 | 0xB2 | stop | inferred |
| mute | 173 | 0xAD | — | inferred |
| next_track | 176 | 0xB0 | nexttrack | inferred |
| play_pause | 179 | 0xB3 | playpause | inferred |
| prev_track | 177 | 0xB1 | prevtrack | inferred |
| volume_down | 174 | 0xAE | volumedown | inferred |
| volume_up | 175 | 0xAF | volumeup | inferred |

## Mouse

Rule: {button}_{action} maps to {button-code}{action-code}; scroll names map directly. 34 codes total. Both tools use these names; the generator additionally accepts the legacy aliases below, preserved per the contract's alias rule.

| Name | Code |
|---|---|
| back_click | 4C |
| back_double_click | 4DC |
| back_down | 4D |
| back_toggle | 4T |
| back_triple_click | 4TC |
| back_up | 4U |
| cursor_move | Move |
| forward_click | 5C |
| forward_double_click | 5DC |
| forward_down | 5D |
| forward_toggle | 5T |
| forward_triple_click | 5TC |
| forward_up | 5U |
| left_click | LC |
| left_double_click | LDC |
| left_down | LD |
| left_toggle | LT |
| left_triple_click | LTC |
| left_up | LU |
| middle_click | MC |
| middle_double_click | MDC |
| middle_down | MD |
| middle_toggle | MT |
| middle_triple_click | MTC |
| middle_up | MU |
| right_click | RC |
| right_double_click | RDC |
| right_down | RD |
| right_toggle | RT |
| right_triple_click | RTC |
| right_up | RU |
| scroll_down | SB |
| scroll_left | SL |
| scroll_right | SR |
| scroll_up | SF |

Aliases: double_click = left_double_click, lc = left_click, mc = middle_click, rc = right_click, triple_click = left_triple_click

## Conditions

### Value Types

| Code | Name | Right-Operand Slot | Confidence | Notes |
|---|---|---|---|---|
| 0 | SmallInteger | m[21] i32 | solid | 0 aliases unset - identify compares structurally by m[2], never by m[24] |
| 1 | Text | m[7] string | solid |  |
| 2 | Boolean | m[21] i32 (True=1) | solid |  |
| 3 | Integer | m[21] i32 | solid |  |
| 4 | Decimal | m[25] .NET Decimal 16B | solid |  |

### Operators

Coding rule: 0-indexed position in that value-type's dropdown (spec sec 8.2)

- **Text** (10): Equals, Does Not Equal, Starts With, Does Not Start With, Ends With, Does Not End With, Contains, Does Not Contain, Has Been Set, Has Not Been Set
- **Integer** (8): Equals, Does Not Equal, Is Less Than, Is Less Than Or Equals, Is Greater Than, Is Greater Than Or Equals, Has Been Set, Has Not Been Set
- **Decimal** (8): Equals, Does Not Equal, Is Less Than, Is Less Than Or Equals, Is Greater Than, Is Greater Than Or Equals, Has Been Set, Has Not Been Set
- **SmallInteger** (8): Equals, Does Not Equal, Is Less Than, Is Less Than Or Equals, Is Greater Than, Is Greater Than Or Equals, Has Been Set, Has Not Been Set
- **Boolean** (4): Equals, Does Not Equal, Has Been Set, Has Not Been Set

### Block Structure

- **pairing**: m[17] = 0-based index of the action closing this segment (next branch point, not final End); closers point back; End of an Else-If chain points to the ORIGINAL Begin. All block actions carry pairing (Begin/ElseIf/Else/End/Loop).
- **block_ordinal**: m[18] = 1-based, increments per Begin; ElseIf inherits
- **indent_level**: NOT stored; derive from Begin/End nesting
- **confidence**: solid

- **compound**: status=parked — Multi-sub-condition (AND/OR) blocks are decode-only: emit the first sub-compare plus an explicit marker {compound: n_subs} - never silence. m[31] record format undecoded (spec sec 12 item 6).

### Operand Hazards

- i32 -1 in m[21] is byte-identical to the absent sentinel - type-gate on m[24]
- Text Has/Has-Not-Been-Set reads m[7]='' not 0xFFFFFFFF

## Durations

- **binary**: m[3] IEEE-754 double, seconds; KeyDown/KeyUp/KeyToggle read exactly 0.0; sanity floor 0.001 <= d <= 60 for flat-scan legacy paths
- **json_default**: 0.1
- **serialization**: plain decimal string, never scientific notation
- **confidence**: solid

## Parked Registry Pointer

Probe B (2026-07-11) closed its targets: ActionTypes 3/13/24/25/26/27/50/51, mouse click-duration/scroll-count/Move, Set-action value-source-mode + arithmetic-op model, Set-Boolean confound, Set-SmallInt-is-moot. Spec sec 12 and skills/voiceattack-decoder/docs/VAP_Parked_Uncertainties.md route everything still open: compound m[31] interior, header @8 command-list index, ~24 unmapped near-constant slots, trailing-region structure, local-var pool anchor, Write color/shape, Set-Integer value-source modes 2/3, Set-Integer stale-operand-slot hazard, mouse SPECIAL context + untested button/action combinations.

