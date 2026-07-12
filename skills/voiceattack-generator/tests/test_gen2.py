"""gen2 unit tests (encoder refactor plan W1/W2; build spec WP-A test home 1).

NO vap2 imports here — the generator skill's suite stands alone (architecture ruling
2026-07-12); the cross-tool equivalence gates live at repo-level tests/integration/.

Expected XML fragments are VERBATIM vap_generator.py 2.0.0 output (captured 2026-07-12
from a probe input covering every wired type), with <Id> GUIDs masked. The Launch
fragment is the one exception: vap_generator 2.0.0 cannot emit Launch, so it is authored
from the dictionary's Launch xml carriers on the ground-truth template (see
emit_profile._launch_xml's docstring).

Run:  python3 -m unittest discover -s skills/voiceattack-generator/tests -t . -v
  or:  python3 skills/voiceattack-generator/tests/test_gen2.py
"""

import contextlib
import io
import json
import os
import re
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPTS = os.path.join(os.path.dirname(HERE), "scripts")
sys.path.insert(0, SCRIPTS)

from gen2 import names, schema_input  # noqa: E402
from gen2.cli import main as cli_main  # noqa: E402
from gen2.emit_profile import EmitError, emit  # noqa: E402
from gen2.schema_input import SchemaError  # noqa: E402

DICT = names.load()
GUID_RE = re.compile(r"<Id>[0-9a-f\-]{36}</Id>")
CHUNK_RE = re.compile(r" {8}<CommandAction>.*?</CommandAction>", re.S)


def mask(chunk):
    return GUID_RE.sub("<Id>GUID</Id>", chunk)


def model_for(actions, phrase="t", category="general"):
    return {"profile": {"id": None, "name": "T"},
            "commands": [{"phrase": phrase, "category": category, "actions": actions}]}


def emit_chunks(actions, **kw):
    xml, warnings = emit(model_for(actions, **kw), DICT)
    return [mask(c) for c in CHUNK_RE.findall(xml)], warnings


def rec(code, name, **fields):
    r = {"actionType": {"code": code, "name": name}}
    r.update(fields)
    return r


def doc_for(actions, phrase="t", category="general"):
    """A full schema-v1.1 document (for schema_input / CLI tests)."""
    return {"schema_version": 2, "decoder": "vap2", "dictionary_version": DICT.version,
            "profile": {"id": "11111111-2222-3333-4444-555555555555", "name": "T",
                        "commandCount": 1},
            "commands": [{"id": "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee", "phrase": phrase,
                          "category": {"value": category, "provenance": "xml"},
                          "actionCount": len(actions), "actions": actions}],
            "census": {"totalActions": len(actions), "decoded": len(actions),
                       "unknownMarked": 0}}


# --- verbatim expected fragments (vap_generator.py 2.0.0 output, GUIDs masked) -------

PRESSKEY_CHORD = """        <CommandAction>
          <PairingSet>false</PairingSet>
          <PairingSetElse>false</PairingSetElse>
          <Ordinal>0</Ordinal>
          <ConditionMet xsi:nil="true"/>
          <IndentLevel>0</IndentLevel>
          <ConditionSkip>false</ConditionSkip>
          <IsSuffixAction>false</IsSuffixAction>
          <DecimalTransient1>0</DecimalTransient1>
          <Id>GUID</Id>
          <ActionType>PressKey</ActionType>
          <Duration>0.25</Duration>
          <Delay>0</Delay>
          <KeyCodes>
            <unsignedShort>162</unsignedShort>
            <unsignedShort>86</unsignedShort>
          </KeyCodes>
          <Context></Context>
          <X>0</X>
          <Y>0</Y>
          <Z>0</Z>
          <InputMode>0</InputMode>
          <ConditionPairing>0</ConditionPairing>
          <ConditionGroup>0</ConditionGroup>
          <ConditionStartOperator>0</ConditionStartOperator>
          <ConditionStartValue>0</ConditionStartValue>
          <ConditionStartValueType>0</ConditionStartValueType>
          <ConditionStartType>0</ConditionStartType>
          <DecimalContext1>0</DecimalContext1>
          <DecimalContext2>0</DecimalContext2>
          <DateContext1>0001-01-01T00:00:00</DateContext1>
          <DateContext2>0001-01-01T00:00:00</DateContext2>
          <Disabled>false</Disabled>
          <RandomSounds/>
          <ConditionExpressions/>
        </CommandAction>"""

KEYDOWN_CTRL = PRESSKEY_CHORD.replace(
    "<ActionType>PressKey</ActionType>", "<ActionType>KeyDown</ActionType>"
).replace("<Duration>0.25</Duration>", "<Duration>0</Duration>").replace(
    """<KeyCodes>
            <unsignedShort>162</unsignedShort>
            <unsignedShort>86</unsignedShort>
          </KeyCodes>""",
    """<KeyCodes>
            <unsignedShort>17</unsignedShort>
          </KeyCodes>""")

SAY_FRAGMENT = """        <CommandAction>
          <PairingSet>false</PairingSet>
          <PairingSetElse>false</PairingSetElse>
          <Ordinal>0</Ordinal>
          <ConditionMet xsi:nil="true"/>
          <IndentLevel>0</IndentLevel>
          <ConditionSkip>false</ConditionSkip>
          <IsSuffixAction>false</IsSuffixAction>
          <DecimalTransient1>0</DecimalTransient1>
          <Id>GUID</Id>
          <ActionType>Say</ActionType>
          <Duration>0</Duration>
          <Delay>0</Delay>
          <KeyCodes/>
          <Context>hello world</Context>
          <X>75</X>
          <Y>2</Y>
          <Z>0</Z>
          <InputMode>0</InputMode>
          <ConditionPairing>0</ConditionPairing>
          <ConditionGroup>0</ConditionGroup>
          <ConditionStartOperator>0</ConditionStartOperator>
          <ConditionStartValue>0</ConditionStartValue>
          <ConditionStartValueType>0</ConditionStartValueType>
          <ConditionStartType>0</ConditionStartType>
          <DecimalContext1>0</DecimalContext1>
          <DecimalContext2>0</DecimalContext2>
          <DateContext1>0001-01-01T00:00:00</DateContext1>
          <DateContext2>0001-01-01T00:00:00</DateContext2>
          <Disabled>false</Disabled>
          <RandomSounds/>
          <ConditionExpressions/>
        </CommandAction>"""

PAUSE_FRAGMENT = SAY_FRAGMENT.replace(
    "<ActionType>Say</ActionType>", "<ActionType>Pause</ActionType>"
).replace("<Duration>0</Duration>", "<Duration>1.5</Duration>").replace(
    "<Context>hello world</Context>", "<Context></Context>"
).replace("<X>75</X>", "<X>0</X>").replace("<Y>2</Y>", "<Y>0</Y>")

MOUSE_CLICK_FRAGMENT = SAY_FRAGMENT.replace(
    "<ActionType>Say</ActionType>", "<ActionType>MouseAction</ActionType>"
).replace("<Context>hello world</Context>", "<Context>LC</Context>").replace(
    "<X>75</X>", "<X>0</X>").replace("<Y>2</Y>", "<Y>0</Y>")

MOUSE_SCROLL_FRAGMENT = SAY_FRAGMENT.replace(
    "<ActionType>Say</ActionType>", "<ActionType>MouseAction</ActionType>"
).replace("<Duration>0</Duration>", "<Duration>7</Duration>").replace(
    "<Context>hello world</Context>", "<Context>SF</Context>"
).replace("<X>75</X>", "<X>7</X>").replace("<Y>2</Y>", "<Y>0</Y>").replace(
    "<DecimalContext1>0</DecimalContext1>", "<DecimalContext1>7</DecimalContext1>")

WRITE_FRAGMENT = SAY_FRAGMENT.replace(
    "<ActionType>Say</ActionType>", "<ActionType>WriteToLog</ActionType>"
).replace("<Context>hello world</Context>", "<Context>hello {DEC:myvar}</Context>").replace(
    "<X>75</X>", "<X>0</X>").replace("<Y>2</Y>", "<Y>0</Y>")

DECIMALSET_FRAGMENT = """        <CommandAction>
          <PairingSet>false</PairingSet>
          <PairingSetElse>false</PairingSetElse>
          <Ordinal>0</Ordinal>
          <ConditionMet xsi:nil="true"/>
          <IndentLevel>0</IndentLevel>
          <ConditionSkip>false</ConditionSkip>
          <IsSuffixAction>false</IsSuffixAction>
          <DecimalTransient1>0</DecimalTransient1>
          <Id>GUID</Id>
          <ActionType>DecimalSet</ActionType>
          <Duration>0</Duration>
          <Delay>0</Delay>
          <KeyCodes/>
          <X>0</X>
          <Y>0</Y>
          <Z>0</Z>
          <InputMode>0</InputMode>
          <ConditionSetName xml:space="preserve">myvar</ConditionSetName>
          <ConditionPairing>0</ConditionPairing>
          <ConditionGroup>0</ConditionGroup>
          <ConditionStartOperator>0</ConditionStartOperator>
          <ConditionStartValue>0</ConditionStartValue>
          <ConditionStartValueType>0</ConditionStartValueType>
          <ConditionStartType>0</ConditionStartType>
          <DecimalContext1>3.5</DecimalContext1>
          <DecimalContext2>0</DecimalContext2>
          <DateContext1>0001-01-01T00:00:00</DateContext1>
          <DateContext2>0001-01-01T00:00:00</DateContext2>
          <Disabled>false</Disabled>
          <RandomSounds/>
          <ConditionExpressions/>
        </CommandAction>"""

BEGIN_HASBEENSET_FRAGMENT = """        <CommandAction>
          <PairingSet>false</PairingSet>
          <PairingSetElse>false</PairingSetElse>
          <Ordinal>0</Ordinal>
          <ConditionMet xsi:nil="true"/>
          <IndentLevel>0</IndentLevel>
          <ConditionSkip>false</ConditionSkip>
          <IsSuffixAction>false</IsSuffixAction>
          <DecimalTransient1>0</DecimalTransient1>
          <Id>GUID</Id>
          <ActionType>ConditionStart</ActionType>
          <Duration>0</Duration>
          <Delay>0</Delay>
          <KeyCodes/>
          <Context2 xml:space="preserve"></Context2>
          <X>0</X>
          <Y>0</Y>
          <Z>1</Z>
          <InputMode>0</InputMode>
          <ConditionPairing>2</ConditionPairing>
          <ConditionGroup>1</ConditionGroup>
          <ConditionStartNameFrom>{TXT:foo}</ConditionStartNameFrom>
          <ConditionStartOperator>8</ConditionStartOperator>
          <ConditionStartValue>0</ConditionStartValue>
          <ConditionStartValueType>0</ConditionStartValueType>
          <ConditionStartCompareToCondtion/>
          <ConditionStartType>1</ConditionStartType>
          <DecimalContext1>0</DecimalContext1>
          <DecimalContext2>0</DecimalContext2>
          <DateContext1>0001-01-01T00:00:00</DateContext1>
          <DateContext2>0001-01-01T00:00:00</DateContext2>
          <Disabled>false</Disabled>
          <RandomSounds/>
          <ConditionExpressions/>
        </CommandAction>"""

ELSE_FRAGMENT = """        <CommandAction>
          <PairingSet>false</PairingSet>
          <PairingSetElse>false</PairingSetElse>
          <Ordinal>2</Ordinal>
          <ConditionMet xsi:nil="true"/>
          <IndentLevel>0</IndentLevel>
          <ConditionSkip>false</ConditionSkip>
          <IsSuffixAction>false</IsSuffixAction>
          <DecimalTransient1>0</DecimalTransient1>
          <Id>GUID</Id>
          <ActionType>ConditionElse</ActionType>
          <Duration>0</Duration>
          <Delay>0</Delay>
          <KeyCodes/>
          <X>0</X>
          <Y>0</Y>
          <Z>0</Z>
          <InputMode>0</InputMode>
          <ConditionPairing>4</ConditionPairing>
          <ConditionGroup>1</ConditionGroup>
          <ConditionStartOperator>0</ConditionStartOperator>
          <ConditionStartValue>0</ConditionStartValue>
          <ConditionStartValueType>0</ConditionStartValueType>
          <ConditionStartType>0</ConditionStartType>
          <DecimalContext1>0</DecimalContext1>
          <DecimalContext2>0</DecimalContext2>
          <DateContext1>0001-01-01T00:00:00</DateContext1>
          <DateContext2>0001-01-01T00:00:00</DateContext2>
          <Disabled>false</Disabled>
          <RandomSounds/>
          <ConditionExpressions/>
        </CommandAction>"""

END_FRAGMENT = ELSE_FRAGMENT.replace(
    "<ActionType>ConditionElse</ActionType>", "<ActionType>ConditionEnd</ActionType>"
).replace("<Ordinal>2</Ordinal>", "<Ordinal>4</Ordinal>").replace(
    "<ConditionPairing>4</ConditionPairing>", "<ConditionPairing>0</ConditionPairing>")

# Hand-authored (see module docstring): dictionary Launch carriers on the ground-truth
# template — Context=path, Context2=args, Context3=workdir after Context.
LAUNCH_FRAGMENT = SAY_FRAGMENT.replace(
    "<ActionType>Say</ActionType>", "<ActionType>Launch</ActionType>"
).replace(
    "<Context>hello world</Context>",
    "<Context>C:\\probe\\launch-test.exe</Context>\n"
    "          <Context2 xml:space=\"preserve\">--a1 --a2</Context2>\n"
    "          <Context3 xml:space=\"preserve\">C:\\probe\\wd</Context3>"
).replace("<X>75</X>", "<X>0</X>").replace("<Y>2</Y>", "<Y>0</Y>")


def begin_text(operator, value=None, left="{LASTSPOKENCMD}", code=19, name="BeginCondition"):
    cond = {"valueType": {"code": 1, "name": "Text"},
            "operator": {"code": DICT.operator_index("Text", operator), "name": operator},
            "leftOperand": left, "pairing": 0, "blockOrdinal": 1}
    if value is not None:
        cond["value"] = value
    return rec(code, name, condition=cond)


def presskey(vk="a", vknum=65, duration=0.1):
    return rec(0, "PressKey", duration=duration, keyCodes=[{"vk": vknum, "name": vk}])


class PerActionEquivalenceTest(unittest.TestCase):
    """Hand-built schema records render byte-identically to vap_generator.py 2.0.0."""

    def assert_single(self, record, expected):
        chunks, warnings = emit_chunks([record])
        self.assertEqual(len(chunks), 1)
        self.assertEqual(chunks[0], expected)

    def test_presskey_chord(self):
        self.assert_single(
            rec(0, "PressKey", duration=0.25,
                keyCodes=[{"vk": 162, "name": "lctrl"}, {"vk": 86, "name": "v"}]),
            PRESSKEY_CHORD)

    def test_presskey_zero_duration(self):
        # Explicit zero is legal and passes through unclamped; decoded 0.0 renders "0".
        chunks, _ = emit_chunks([presskey(duration=0.0)])
        self.assertIn("<Duration>0</Duration>", chunks[0])

    def test_keydown(self):
        self.assert_single(rec(8, "KeyDown", keyCodes=[{"vk": 17, "name": "ctrl"}]),
                           KEYDOWN_CTRL)

    def test_keyup(self):
        self.assert_single(
            rec(9, "KeyUp", keyCodes=[{"vk": 17, "name": "ctrl"}]),
            KEYDOWN_CTRL.replace("<ActionType>KeyDown</ActionType>",
                                 "<ActionType>KeyUp</ActionType>"))

    def test_keytoggle(self):
        self.assert_single(
            rec(67, "KeyToggle", keyCodes=[{"vk": 20, "name": "capslock"}]),
            KEYDOWN_CTRL.replace("<ActionType>KeyDown</ActionType>",
                                 "<ActionType>KeyToggle</ActionType>")
                        .replace("<unsignedShort>17</unsignedShort>",
                                 "<unsignedShort>20</unsignedShort>"))

    def test_say(self):
        self.assert_single(rec(13, "Say", text="hello world", volume=75, rate=2),
                           SAY_FRAGMENT)

    def test_pause(self):
        self.assert_single(rec(2, "Pause", duration=1.5), PAUSE_FRAGMENT)

    def test_mouse_click(self):
        self.assert_single(rec(12, "MouseAction", contextCode="LC", action="left_click"),
                           MOUSE_CLICK_FRAGMENT)

    def test_mouse_click_by_action_name_alias(self):
        # No contextCode: canonical/alias action names resolve through the dictionary.
        chunks, _ = emit_chunks([rec(12, "MouseAction", action="lc")])
        self.assertEqual(chunks[0], MOUSE_CLICK_FRAGMENT)

    def test_mouse_scroll(self):
        self.assert_single(
            rec(12, "MouseAction", contextCode="SF", action="scroll_up", scroll_clicks=7),
            MOUSE_SCROLL_FRAGMENT)

    def test_mouse_scroll_clicks_float_integral(self):
        # Binary decode carries scroll_clicks as a double; 7.0 renders "7".
        chunks, _ = emit_chunks([rec(12, "MouseAction", contextCode="SF",
                                     scroll_clicks=7.0)])
        self.assertEqual(chunks[0], MOUSE_SCROLL_FRAGMENT)

    def test_mouse_move(self):
        chunks, _ = emit_chunks([rec(12, "MouseAction", contextCode="Move", x=333, y=444)])
        self.assertIn("<Context>Move</Context>", chunks[0])
        self.assertIn("<X>333</X>", chunks[0])
        self.assertIn("<Y>444</Y>", chunks[0])

    def test_mouse_click_duration(self):
        chunks, _ = emit_chunks([rec(12, "MouseAction", contextCode="LC",
                                     clickDuration=0.1)])
        self.assertIn("<Duration>0.1</Duration>", chunks[0])

    def test_write(self):
        self.assert_single(rec(23, "Write", text="hello {DEC:myvar}"), WRITE_FRAGMENT)

    def test_setdecimal_number(self):
        self.assert_single(rec(38, "SetDecimal", targetVariable="myvar", value=3.5),
                           DECIMALSET_FRAGMENT)

    def test_setdecimal_exact_string_passthrough(self):
        # The binary decode's exact .NET-decimal string is emitted untouched.
        chunks, _ = emit_chunks([rec(38, "SetDecimal", targetVariable="myvar",
                                     value="2.25")])
        self.assertIn("<DecimalContext1>2.25</DecimalContext1>", chunks[0])

    def test_launch(self):
        chunks, warnings = emit_chunks([
            rec(3, "Launch", executablePath="C:\\probe\\launch-test.exe",
                arguments="--a1 --a2", workingDirectory="C:\\probe\\wd")])
        self.assertEqual(chunks[0], LAUNCH_FRAGMENT)
        # Inferred XML carrier: emitted WITH a warning (contract §2).
        self.assertTrue(any("inferred" in w for w in warnings), warnings)

    def test_launch_omits_absent_context23(self):
        chunks, _ = emit_chunks([rec(3, "Launch", executablePath="C:\\x.exe")])
        self.assertNotIn("<Context2", chunks[0])
        self.assertNotIn("<Context3", chunks[0])

    def test_escaping(self):
        chunks, _ = emit_chunks([rec(23, "Write", text="a < b & c > d")])
        self.assertIn("<Context>a &lt; b &amp; c &gt; d</Context>", chunks[0])


class ConditionBlockTest(unittest.TestCase):
    """Block markers: verbatim fragments plus recomputed pairing/group/indent."""

    def test_hasbeenset_else_block_verbatim(self):
        chunks, warnings = emit_chunks([
            begin_text("Has Been Set", left="{TXT:foo}"),
            presskey("a", 65),
            rec(29, "Else", block={"pairing": 4}),
            presskey("b", 66),
            rec(20, "EndCondition", block={"pairing": 0}),
        ])
        self.assertEqual(warnings, [])
        self.assertEqual(len(chunks), 5)
        self.assertEqual(chunks[0], BEGIN_HASBEENSET_FRAGMENT)
        self.assertEqual(chunks[2], ELSE_FRAGMENT)
        self.assertEqual(chunks[4], END_FRAGMENT)

    def test_pairing_chain_and_groups(self):
        # Two sequential blocks: pairing chains forward, End points back to its Begin,
        # ConditionGroup counts Begins 1-based. Input pairing values are IGNORED and
        # recomputed (deliberately wrong here).
        chunks, warnings = emit_chunks([
            begin_text("Ends With", "more"),
            rec(38, "SetDecimal", targetVariable="bbq", value="2.25"),
            rec(29, "Else", block={"pairing": 99}),
            rec(38, "SetDecimal", targetVariable="bbq", value="0.75"),
            rec(20, "EndCondition", block={"pairing": 99}),
            begin_text("Contains", "out"),
            presskey("f", 70, 0.0),
            rec(63, "ElseIf", condition=begin_text("Contains", "in")["condition"]),
            presskey("r", 82, 0.0),
            rec(20, "EndCondition", block={"pairing": 99}),
        ])
        self.assertEqual(warnings, [])

        def field(i, tag):
            return re.search(r"<%s>(.*?)</%s>" % (tag, tag), chunks[i]).group(1)

        self.assertEqual([field(i, "Ordinal") for i in range(10)],
                         [str(i) for i in range(10)])
        self.assertEqual(field(0, "ConditionPairing"), "2")   # Begin -> Else
        self.assertEqual(field(2, "ConditionPairing"), "4")   # Else -> End
        self.assertEqual(field(4, "ConditionPairing"), "0")   # End -> Begin
        self.assertEqual(field(5, "ConditionPairing"), "7")   # Begin2 -> ElseIf
        self.assertEqual(field(7, "ConditionPairing"), "9")   # ElseIf -> End2
        self.assertEqual(field(9, "ConditionPairing"), "5")   # End2 -> Begin2
        self.assertEqual(field(0, "ConditionGroup"), "1")
        self.assertEqual(field(5, "ConditionGroup"), "2")
        self.assertEqual(field(7, "ConditionGroup"), "2")
        # Actions inside a block indent one level; markers sit at block level.
        self.assertEqual(field(1, "IndentLevel"), "1")
        self.assertEqual(field(6, "IndentLevel"), "1")
        self.assertEqual(field(5, "IndentLevel"), "0")

    def test_all_ten_text_operators(self):
        for op in DICT.operators["Text"]:
            valueless = DICT.operator_is_valueless(op)
            chunks, warnings = emit_chunks([
                begin_text(op, None if valueless else "x"),
                presskey(),
                rec(20, "EndCondition", block={"pairing": 0}),
            ])
            self.assertEqual(warnings, [], op)
            self.assertIn("<ConditionStartOperator>%d</ConditionStartOperator>"
                          % DICT.operator_index("Text", op), chunks[0])


class HardFailTest(unittest.TestCase):
    """Malformed condition structure / SetDecimal / Write payloads: EmitError, no output."""

    def assert_fails(self, actions, pattern):
        with self.assertRaisesRegex(EmitError, pattern):
            emit(model_for(actions), DICT)

    def test_elseif_outside_block(self):
        self.assert_fails([rec(63, "ElseIf",
                               condition=begin_text("Equals", "x")["condition"])],
                          "outside any open condition block")

    def test_duplicate_else(self):
        self.assert_fails([begin_text("Equals", "x"),
                           rec(29, "Else"), rec(29, "Else"),
                           rec(20, "EndCondition")],
                          "duplicate 'Else'")

    def test_elseif_after_else(self):
        self.assert_fails([begin_text("Equals", "x"), rec(29, "Else"),
                           rec(63, "ElseIf",
                               condition=begin_text("Equals", "y")["condition"]),
                           rec(20, "EndCondition")],
                          "follows 'Else'")

    def test_unclosed_begin(self):
        self.assert_fails([begin_text("Equals", "x")], "never closed")

    def test_end_without_begin(self):
        self.assert_fails([rec(20, "EndCondition")], "without a matching")

    def test_begin_missing_condition(self):
        self.assert_fails([rec(19, "BeginCondition"), rec(20, "EndCondition")],
                          "missing a required 'condition'")

    def test_else_carrying_condition(self):
        self.assert_fails([begin_text("Equals", "x"),
                           rec(29, "Else",
                               condition=begin_text("Equals", "y")["condition"]),
                           rec(20, "EndCondition")],
                          "must not carry")

    def test_begin_missing_left_operand(self):
        bad = begin_text("Equals", "x")
        del bad["condition"]["leftOperand"]
        self.assert_fails([bad, rec(20, "EndCondition")], "leftOperand")

    def test_begin_missing_value_for_valued_operator(self):
        self.assert_fails([begin_text("Equals"), rec(20, "EndCondition")],
                          "missing a 'value'")

    def test_setdecimal_empty_variable(self):
        self.assert_fails([rec(38, "SetDecimal", targetVariable="", value=1)],
                          "non-empty string 'targetVariable'")

    def test_setdecimal_non_numeric_value(self):
        self.assert_fails([rec(38, "SetDecimal", targetVariable="v", value="abc")],
                          "plain decimal string")

    def test_setdecimal_scientific_string(self):
        self.assert_fails([rec(38, "SetDecimal", targetVariable="v", value="1e5")],
                          "plain decimal string")

    def test_setdecimal_nan(self):
        self.assert_fails([rec(38, "SetDecimal", targetVariable="v",
                               value=float("nan"))], "finite")

    def test_setdecimal_bool(self):
        self.assert_fails([rec(38, "SetDecimal", targetVariable="v", value=True)],
                          "numeric 'value'")

    def test_write_missing_text(self):
        self.assert_fails([rec(23, "Write")], "requires a string 'text'")


class RefusalTest(unittest.TestCase):
    """Contract §3: unknown/unrepresentable input is refused LOUDLY, never silently —
    action-level for non-structural types, whole-command for condition-family actions
    and unknown markers."""

    def emit_model(self, actions):
        xml, warnings = emit(model_for(actions), DICT)
        return xml.count("<Command>"), len(CHUNK_RE.findall(xml)), warnings

    def test_unwired_type_drops_action_only(self):
        n_cmds, n_actions, warnings = self.emit_model(
            [rec(21, "SetText", targetVariable="x", value="y"), presskey()])
        self.assertEqual((n_cmds, n_actions), (1, 1))
        self.assertEqual(len(warnings), 1)
        self.assertIn("not emit-wired", warnings[0])

    def test_unknown_marker_refuses_command(self):
        n_cmds, n_actions, warnings = self.emit_model(
            [{"decoded": False, "index": 0, "actionTypeCode": 99,
              "members": None, "reason": "test fixture"}, presskey()])
        self.assertEqual((n_cmds, n_actions), (0, 0))
        self.assertEqual(len(warnings), 1)
        self.assertIn("refusing the whole command", warnings[0])

    def test_non_text_compare_refuses_command(self):
        begin = begin_text("Equals", 5)
        begin["condition"]["valueType"] = {"code": 3, "name": "Integer"}
        n_cmds, _, warnings = self.emit_model(
            [begin, presskey(), rec(20, "EndCondition")])
        self.assertEqual(n_cmds, 0)
        self.assertIn("Text compares only", warnings[0])

    def test_compound_condition_refuses_command(self):
        begin = begin_text("Equals", "x")
        begin["condition"]["compound"] = {"subConditions": 2, "decoded": False}
        n_cmds, _, warnings = self.emit_model(
            [begin, presskey(), rec(20, "EndCondition")])
        self.assertEqual(n_cmds, 0)
        self.assertIn("compound", warnings[0])

    def test_unresolved_compare_refuses_command(self):
        begin = rec(19, "BeginCondition", condition={
            "valueType": {"code": 0, "name": None},
            "operator": {"code": 0, "name": None}, "leftOperand": None,
            "unresolved": {"decoded": False, "reason": "left operand absent"},
            "pairing": 2, "blockOrdinal": 1})
        n_cmds, _, warnings = self.emit_model(
            [begin, presskey(), rec(20, "EndCondition")])
        self.assertEqual(n_cmds, 0)
        self.assertIn("unresolved", warnings[0])

    def test_while_pair_parked_refuses_command(self):
        n_cmds, _, warnings = self.emit_model(
            [rec(30, "BeginLoopWhile",
                 condition=begin_text("Equals", "x")["condition"]),
             presskey(), rec(31, "EndLoop", block={"pairing": 0})])
        self.assertEqual(n_cmds, 0)
        self.assertIn("parked", warnings[0])

    def test_unknown_mouse_context_drops_action(self):
        n_cmds, n_actions, warnings = self.emit_model(
            [rec(12, "MouseAction", contextCode="XX"), presskey()])
        self.assertEqual((n_cmds, n_actions), (1, 1))
        self.assertIn("MouseAction context", warnings[0])

    def test_code_name_mismatch_refuses_command(self):
        n_cmds, _, warnings = self.emit_model([rec(0, "Pause", duration=1.0)])
        self.assertEqual(n_cmds, 0)
        self.assertIn("not in the dictionary", warnings[0])

    def test_nondefault_say_voice_warns_but_emits(self):
        n_cmds, n_actions, warnings = self.emit_model(
            [rec(13, "Say", text="hi", volume=100, rate=0, voiceName="Karen",
                 voiceGuid="12345678-1234-1234-1234-123456789012")])
        self.assertEqual((n_cmds, n_actions), (1, 1))
        self.assertTrue(any("voice" in w for w in warnings), warnings)

    def test_default_say_voice_is_silent(self):
        _, _, warnings = self.emit_model(
            [rec(13, "Say", text="hi", volume=100, rate=0, voiceName="Default",
                 voiceGuid="00000000-0000-0000-0000-000000000000")])
        self.assertEqual(warnings, [])


class SchemaInputTest(unittest.TestCase):
    """Strict v1.1 reader: accepts the frozen shape (annotations tolerated), rejects
    unknown top-level shapes, maps nulls to empties."""

    def test_accepts_normative_doc(self):
        model = schema_input.parse(doc_for([presskey()]))
        self.assertEqual(model["profile"]["name"], "T")
        self.assertEqual(len(model["commands"]), 1)
        self.assertEqual(model["commands"][0]["category"], "general")

    def test_tolerates_provenance_annotations(self):
        doc = doc_for([dict(presskey(), offset=788, head=347,
                            guid="11111111-2222-3333-4444-555555555555",
                            indentLevel=0, source="xml")])
        doc["commands"][0]["guidOffset"] = 750
        doc["commands"][0]["chainEnd"] = 3111
        doc["commands"][0]["chainOk"] = True
        doc["future_annotation"] = {"anything": 1}
        model = schema_input.parse(doc)  # must not raise
        self.assertEqual(model["commands"][0]["actions"][0]["offset"], 788)

    def test_rejects_simple_authoring_format(self):
        with self.assertRaisesRegex(SchemaError, "schema_version"):
            schema_input.parse({"name": "My Profile", "commands": [
                {"trigger": "alpha", "key": "a"}]})

    def test_rejects_wrong_schema_version(self):
        doc = doc_for([])
        doc["schema_version"] = 3
        with self.assertRaisesRegex(SchemaError, "not supported"):
            schema_input.parse(doc)

    def test_rejects_non_object_top_level(self):
        with self.assertRaises(SchemaError):
            schema_input.parse([1, 2, 3])

    def test_rejects_missing_profile(self):
        doc = doc_for([])
        del doc["profile"]
        with self.assertRaisesRegex(SchemaError, "profile"):
            schema_input.parse(doc)

    def test_rejects_non_list_commands(self):
        doc = doc_for([])
        doc["commands"] = {"0": {}}
        with self.assertRaisesRegex(SchemaError, "commands"):
            schema_input.parse(doc)

    def test_rejects_action_without_actiontype(self):
        with self.assertRaisesRegex(SchemaError, "actionType"):
            schema_input.parse(doc_for([{"duration": 0.1}]))

    def test_accepts_unknown_marker_action(self):
        doc = doc_for([{"decoded": False, "index": 0, "actionTypeCode": 99,
                        "members": None, "reason": "chain break"}])
        model = schema_input.parse(doc)
        self.assertFalse(model["commands"][0]["actions"][0]["decoded"])

    def test_category_null_maps_to_none(self):
        doc = doc_for([])
        doc["commands"][0]["category"] = {"value": None, "provenance": "heuristic"}
        self.assertIsNone(schema_input.parse(doc)["commands"][0]["category"])

    def test_category_absent_maps_to_none(self):
        doc = doc_for([])
        del doc["commands"][0]["category"]
        self.assertIsNone(schema_input.parse(doc)["commands"][0]["category"])

    def test_null_category_renders_empty_element(self):
        doc = doc_for([presskey()])
        doc["commands"][0]["category"] = {"value": None, "provenance": "heuristic"}
        xml, _ = emit(schema_input.parse(doc), DICT)
        self.assertIn("<Category></Category>", xml)

    def test_null_phrase_maps_to_empty(self):
        doc = doc_for([])
        doc["commands"][0]["phrase"] = None
        self.assertEqual(schema_input.parse(doc)["commands"][0]["phrase"], "")


class NumberFormatTest(unittest.TestCase):
    """Durations render as the old emitter's plain-decimal strings; json.load erases
    the int/float distinction, so integral floats render as ints."""

    def duration_of(self, value):
        chunks, warnings = emit_chunks([rec(2, "Pause", duration=value)])
        return re.search(r"<Duration>(.*?)</Duration>", chunks[0]).group(1), warnings

    def test_zero_float(self):
        self.assertEqual(self.duration_of(0.0), ("0", []))

    def test_tenth(self):
        self.assertEqual(self.duration_of(0.1), ("0.1", []))

    def test_one_point_five(self):
        self.assertEqual(self.duration_of(1.5), ("1.5", []))

    def test_negative_warns_and_defaults(self):
        d, warnings = self.duration_of(-2)
        self.assertEqual(d, "0.1")
        self.assertEqual(len(warnings), 1)

    def test_non_finite_warns_and_defaults(self):
        d, warnings = self.duration_of(float("inf"))
        self.assertEqual(d, "0.1")
        self.assertEqual(len(warnings), 1)

    def test_tiny_never_scientific(self):
        d, _ = self.duration_of(0.0000001)
        self.assertNotIn("e", d.lower())


class CliSmokeTest(unittest.TestCase):
    """Exit codes mirror vap_generator.py: 0 clean, 1 hard fail (no file), 2 warnings."""

    def run_cli(self, doc, name="in.json"):
        with tempfile.TemporaryDirectory() as td:
            inp = os.path.join(td, name)
            out = os.path.join(td, "out.vap")
            with open(inp, "w", encoding="utf-8") as f:
                json.dump(doc, f)
            buf_out, buf_err = io.StringIO(), io.StringIO()
            with contextlib.redirect_stdout(buf_out), contextlib.redirect_stderr(buf_err):
                code = cli_main([inp, out])
            return code, os.path.exists(out), buf_err.getvalue()

    def test_clean_run(self):
        code, wrote, _ = self.run_cli(doc_for([presskey()]))
        self.assertEqual((code, wrote), (0, True))

    def test_schema_error_exits_1_no_output(self):
        code, wrote, err = self.run_cli({"name": "simple", "commands": []})
        self.assertEqual((code, wrote), (1, False))
        self.assertIn("ERROR", err)

    def test_hard_fail_exits_1_no_output(self):
        code, wrote, err = self.run_cli(doc_for([rec(20, "EndCondition")]))
        self.assertEqual((code, wrote), (1, False))
        self.assertIn("ERROR", err)

    def test_warnings_exit_2_with_output(self):
        code, wrote, err = self.run_cli(
            doc_for([rec(21, "SetText", targetVariable="x", value="y"), presskey()]))
        self.assertEqual((code, wrote), (2, True))
        self.assertIn("WARNING", err)


if __name__ == "__main__":
    unittest.main(verbosity=2)
