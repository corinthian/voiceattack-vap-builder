"""gen2.lower unit tests (encoder refactor plan W4) — NO vap2 imports.

Covers the lowering of the simple authoring format (shorthand, key/mouse tables,
defaults, hard-fail validation mirrored from vap_generator.py) and the idiom compiler
(the contract's Ends With ruling + multi-group amendment): detection positives and
negatives against the deliberately conservative predicate, collision resolution and
refusal, opt-out syntax, and the INFO visibility channel. Legacy byte-parity on the
committed fixture pair lives in tests/integration/test_lowering_gates.py; a small
in-process parity check against vap_generator.generate_profile (same skill — allowed)
is included here.

Run:  python3 -m unittest discover -s skills/voiceattack-generator/tests -v
"""

import os
import re
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPTS = os.path.join(os.path.dirname(HERE), "scripts")
sys.path.insert(0, SCRIPTS)

import vap_generator  # noqa: E402  (same skill: the legacy oracle)
from gen2 import names  # noqa: E402
from gen2.emit_profile import emit  # noqa: E402
from gen2.lower import LoweringError, lower_profile  # noqa: E402

DICT = names.load()
GUID_RE = re.compile(r"<(Id|BaseId)>[0-9a-f\-]{36}</(Id|BaseId)>")


def lower(doc, no_idiom=False):
    return lower_profile(doc, DICT, no_idiom=no_idiom)


def one_command(cmd, no_idiom=False):
    model, infos, warnings = lower({"name": "T", "commands": [cmd]}, no_idiom=no_idiom)
    return model["commands"][0], infos, warnings


def types_of(command):
    return [a["actionType"]["name"] for a in command["actions"]]


def idiom_cmd(trigger="pan [up; down]", keys=("w", "s"), extra=None):
    cmd = {"trigger": trigger, "category": "camera",
           "actions": [{"type": "PressKey", "keys": [k]} for k in keys]}
    if extra:
        cmd.update(extra)
    return cmd


class ShorthandAndDefaultsTest(unittest.TestCase):
    def test_key_shorthand(self):
        cmd, _, warnings = one_command({"trigger": "go back", "key": "escape",
                                        "category": "tools"})
        self.assertEqual(warnings, [])
        self.assertEqual(types_of(cmd), ["PressKey"])
        rec = cmd["actions"][0]
        self.assertEqual(rec["keyCodes"], [{"vk": 27, "name": "escape"}])
        self.assertEqual(rec["duration"], 0.1)  # shorthand default

    def test_key_shorthand_with_duration(self):
        cmd, _, _ = one_command({"trigger": "t", "key": "a", "duration": 1.5})
        self.assertEqual(cmd["actions"][0]["duration"], 1.5)

    def test_key_shorthand_unknown_key_warns(self):
        cmd, _, warnings = one_command({"trigger": "t", "key": "hyperspace"})
        self.assertTrue(any("unknown key 'hyperspace'" in w for w in warnings))
        self.assertEqual(cmd["actions"][0]["keyCodes"], [])  # second warn: ignored key

    def test_mouse_shorthand(self):
        cmd, _, _ = one_command({"trigger": "t", "mouse": "back_toggle"})
        self.assertEqual(cmd["actions"][0]["action"], "back_toggle")

    def test_no_action_warns(self):
        cmd, _, warnings = one_command({"trigger": "t"})
        self.assertEqual(cmd["actions"], [])
        self.assertTrue(any("no key, mouse, or actions defined" in w for w in warnings))

    def test_section_markers_skipped(self):
        model, _, _ = lower({"commands": [{"_section": "=== X ==="},
                                          {"trigger": "t", "key": "a"}]})
        self.assertEqual(len(model["commands"]), 1)

    def test_profile_defaults(self):
        model, _, _ = lower({"commands": []})
        self.assertEqual(model["profile"]["name"], "Generated Profile")
        self.assertIsNone(model["profile"]["id"])

    def test_trigger_and_category_defaults(self):
        cmd, _, _ = one_command({"key": "a"})
        self.assertEqual(cmd["phrase"], "unnamed command")
        self.assertEqual(cmd["category"], "general")

    def test_pause_default(self):
        cmd, _, _ = one_command({"trigger": "t", "actions": [{"type": "Pause"}]})
        self.assertEqual(cmd["actions"][0]["duration"], 0.5)

    def test_key_aliases_and_raw_codes(self):
        cmd, _, warnings = one_command({"trigger": "t", "actions": [
            {"type": "PressKey", "keys": ["esc", "control", "num5", 33, "45"]}]})
        self.assertEqual(warnings, [])
        self.assertEqual([k["vk"] for k in cmd["actions"][0]["keyCodes"]],
                         [27, 17, 101, 33, 45])

    def test_keys_string_form(self):
        cmd, _, _ = one_command({"trigger": "t",
                                 "actions": [{"type": "KeyDown", "keys": "ctrl"}]})
        self.assertEqual(cmd["actions"][0]["keyCodes"], [{"vk": 17, "name": "ctrl"}])

    def test_unknown_key_ignored_with_warning(self):
        cmd, _, warnings = one_command({"trigger": "t", "actions": [
            {"type": "PressKey", "keys": ["a", "warp"]}]})
        self.assertEqual([k["vk"] for k in cmd["actions"][0]["keyCodes"]], [65])
        self.assertIn("Unknown key 'warp' - ignored", warnings)

    def test_unknown_action_type_skipped(self):
        cmd, _, warnings = one_command({"trigger": "t", "actions": [
            {"type": "Teleport"}, {"type": "PressKey", "keys": ["a"]}]})
        self.assertEqual(types_of(cmd), ["PressKey"])
        self.assertIn("Unknown action type 'Teleport' - skipped", warnings)

    def test_setdecimal_and_write_lowering(self):
        cmd, _, _ = one_command({"trigger": "t", "actions": [
            {"type": "SetDecimal", "variable": "v", "value": 2.25},
            {"type": "Write", "text": "{DEC:v}"}]})
        self.assertEqual(cmd["actions"][0]["targetVariable"], "v")
        self.assertEqual(cmd["actions"][0]["value"], 2.25)
        self.assertEqual(cmd["actions"][1]["text"], "{DEC:v}")

    def test_mouse_action_lowering(self):
        cmd, _, _ = one_command({"trigger": "t", "actions": [
            {"type": "MouseAction", "action": "scroll_up", "scroll_clicks": 5},
            {"type": "MouseAction", "action": "LEFT_CLICK", "duration": 0.25},
            {"type": "MouseAction"}]})
        a = cmd["actions"]
        self.assertEqual(a[0]["scroll_clicks"], 5)
        self.assertEqual(a[1]["action"], "left_click")   # lowercased
        self.assertEqual(a[1]["clickDuration"], 0.25)    # duration -> clickDuration
        self.assertEqual(a[2]["action"], "left_click")   # legacy default

    def test_delay_warns_and_drops(self):
        _, _, warnings = one_command({"trigger": "t", "actions": [
            {"type": "PressKey", "keys": ["a"], "delay": 2}]})
        self.assertTrue(any("delay" in w for w in warnings))


class HardFailValidationTest(unittest.TestCase):
    """Legacy _validate_actions semantics preserved: authoring defects exit-1 class."""

    def assert_fails(self, actions, pattern):
        with self.assertRaisesRegex(LoweringError, pattern):
            lower({"commands": [{"trigger": "t", "actions": actions}]})

    def test_non_text_value_type(self):
        self.assert_fails([{"type": "BeginCondition", "condition": {
            "valueType": "Integer", "operator": "Equals",
            "leftOperand": "{X}", "value": 1}}], "Text only")

    def test_unknown_operator(self):
        self.assert_fails([{"type": "BeginCondition", "condition": {
            "valueType": "Text", "operator": "Sounds Like",
            "leftOperand": "{X}", "value": "a"}}], "unknown operator")

    def test_unknown_condition_key(self):
        self.assert_fails([{"type": "BeginCondition", "condition": {
            "valueType": "Text", "operator": "Equals", "leftOperand": "{X}",
            "value": "a", "fuzz": 1}}], "unknown key")

    def test_missing_value_key(self):
        self.assert_fails([{"type": "BeginCondition", "condition": {
            "valueType": "Text", "operator": "Equals", "leftOperand": "{X}"}}],
            "missing a 'value' key")

    def test_missing_left_operand(self):
        self.assert_fails([{"type": "BeginCondition", "condition": {
            "valueType": "Text", "operator": "Equals", "value": "a"}}],
            "leftOperand")

    def test_missing_condition(self):
        self.assert_fails([{"type": "ElseIf"}], "missing a required 'condition'")

    def test_else_with_condition(self):
        self.assert_fails([{"type": "Else", "condition": {
            "valueType": "Text", "operator": "Equals", "leftOperand": "{X}",
            "value": "a"}}], "must not carry")

    def test_setdecimal_missing_variable(self):
        self.assert_fails([{"type": "SetDecimal", "value": 1}],
                          "non-empty string 'variable'")

    def test_write_missing_text(self):
        self.assert_fails([{"type": "Write"}], "requires a string 'text'")


class IdiomDetectionTest(unittest.TestCase):
    """The conservative predicate: fires ONLY on the parallel-overload shape."""

    def fires(self, cmd, no_idiom=False):
        lowered, infos, _ = one_command(cmd, no_idiom=no_idiom)
        return len(infos) > 0, lowered

    def test_fires_on_parallel_overload(self):
        fired, cmd = self.fires(idiom_cmd())
        self.assertTrue(fired)
        self.assertEqual(types_of(cmd), ["BeginCondition", "PressKey", "ElseIf",
                                         "PressKey", "EndCondition"])
        begin = cmd["actions"][0]["condition"]
        self.assertEqual(begin["operator"]["name"], "Ends With")
        self.assertEqual(begin["leftOperand"], "{LASTSPOKENCMD}")
        self.assertEqual(begin["value"], "up")
        self.assertEqual(cmd["actions"][2]["condition"]["value"], "down")

    def test_optional_group_does_not_block(self):
        # "[press;] pan [up; down]" — optional group plus one final alternative group.
        fired, cmd = self.fires(idiom_cmd(trigger="[press;] pan [up; down]"))
        self.assertTrue(fired)
        self.assertEqual(cmd["actions"][0]["condition"]["operator"]["name"], "Ends With")

    def test_non_final_group_uses_contains(self):
        # Amendment: a dispatch group followed by anything lowers with ordered Contains.
        fired, cmd = self.fires(idiom_cmd(trigger="zoom [out; in] [more;]",
                                          keys=("f", "r")))
        self.assertTrue(fired)
        self.assertEqual(cmd["actions"][0]["condition"]["operator"]["name"], "Contains")

    def test_no_fire_single_action(self):
        fired, _ = self.fires({"trigger": "go [now;]", "actions": [
            {"type": "PressKey", "keys": ["a"]}]})
        self.assertFalse(fired)

    def test_no_fire_count_mismatch(self):
        fired, cmd = self.fires(idiom_cmd(trigger="pan [up; down; left]"))
        self.assertFalse(fired)
        self.assertEqual(types_of(cmd), ["PressKey", "PressKey"])

    def test_no_fire_mixed_action_types(self):
        # A KeyDown/KeyUp chord must never be split across branches.
        fired, _ = self.fires({"trigger": "hold [x; y]", "actions": [
            {"type": "KeyDown", "keys": ["x"]}, {"type": "KeyUp", "keys": ["y"]}]})
        self.assertFalse(fired)

    def test_no_fire_existing_conditions(self):
        fired, _ = self.fires({"trigger": "zoom [out; in]", "actions": [
            {"type": "BeginCondition", "condition": {
                "valueType": "Text", "operator": "Ends With",
                "leftOperand": "{LASTSPOKENCMD}", "value": "out"}},
            {"type": "PressKey", "keys": ["f"]},
            {"type": "EndCondition"}]})
        self.assertFalse(fired)

    def test_no_fire_two_alternative_groups(self):
        fired, _ = self.fires(idiom_cmd(trigger="pan [up; down] [fast; slow]"))
        self.assertFalse(fired)

    def test_no_fire_no_group(self):
        fired, _ = self.fires(idiom_cmd(trigger="pan around"))
        self.assertFalse(fired)

    def test_no_fire_shorthand_command(self):
        fired, _ = self.fires({"trigger": "go [back; forth]", "key": "a"})
        self.assertFalse(fired)

    def test_per_command_opt_out(self):
        fired, cmd = self.fires(idiom_cmd(extra={"idiom": False}))
        self.assertFalse(fired)
        self.assertEqual(types_of(cmd), ["PressKey", "PressKey"])

    def test_global_opt_out(self):
        fired, _ = self.fires(idiom_cmd(), no_idiom=True)
        self.assertFalse(fired)

    def test_info_names_command_and_mapping(self):
        _, infos, _ = one_command(idiom_cmd())
        self.assertEqual(len(infos), 1)
        self.assertIn("pan [up; down]", infos[0])
        self.assertIn("'up' -> PressKey[w]", infos[0])
        self.assertIn("Ends With", infos[0])


class IdiomCollisionTest(unittest.TestCase):
    def test_input_order_when_no_collision(self):
        # The contract's own example: 'fast' is NOT a suffix of 'fastest'.
        _, infos, _ = one_command(idiom_cmd(trigger="game [normal; fast; fastest]",
                                            keys=("1", "2", "3")))
        self.assertIn("'normal' -> PressKey[1]; 'fast' -> PressKey[2]; "
                      "'fastest' -> PressKey[3]", infos[0])

    def test_suffix_collision_reorders_longest_first(self):
        cmd, infos, _ = one_command(idiom_cmd(trigger="go [fast; very fast]",
                                              keys=("1", "2")))
        self.assertEqual(cmd["actions"][0]["condition"]["value"], "very fast")
        self.assertEqual(cmd["actions"][2]["condition"]["value"], "fast")
        # Action pairing follows the token, not the slot.
        self.assertEqual(cmd["actions"][1]["keyCodes"][0]["vk"], 50)  # '2'
        self.assertEqual(cmd["actions"][3]["keyCodes"][0]["vk"], 49)  # '1'

    def test_contains_substring_collision_reorders(self):
        # Inner-group (Contains) shadow: 'fast' is a substring of 'fastest'.
        cmd, _, _ = one_command(idiom_cmd(trigger="game [fast; fastest] [now;]",
                                          keys=("1", "2")))
        self.assertEqual(cmd["actions"][0]["condition"]["operator"]["name"], "Contains")
        self.assertEqual(cmd["actions"][0]["condition"]["value"], "fastest")
        self.assertEqual(cmd["actions"][2]["condition"]["value"], "fast")

    def test_ends_with_ignores_non_suffix_substring(self):
        # 'an' is a substring of 'plan' but not a suffix relation that Ends With can
        # confuse... it IS a suffix of 'plan'. Use a true non-suffix substring: 'la'.
        cmd, _, _ = one_command(idiom_cmd(trigger="do [la; plan]", keys=("1", "2")))
        self.assertEqual(cmd["actions"][0]["condition"]["value"], "la")  # input order

    def test_duplicate_tokens_hard_refuse(self):
        with self.assertRaisesRegex(LoweringError, r"duplicate.*'up'"):
            one_command(idiom_cmd(trigger="pan [up; up]"))

    def test_duplicate_tokens_case_insensitive(self):
        with self.assertRaisesRegex(LoweringError, "duplicate"):
            one_command(idiom_cmd(trigger="pan [Up; up]"))


class LegacyParityTest(unittest.TestCase):
    """In-process byte parity, small corpus: legacy generate_profile vs lower+emit
    (idiom-neutral input). The committed-fixture gates live in tests/integration/."""

    DOC = {"name": "Parity", "commands": [
        {"_section": "=== A ==="},
        {"trigger": "alpha", "key": "a", "category": "kb"},
        {"trigger": "click", "mouse": "left_click"},
        {"trigger": "scroll", "actions": [
            {"type": "MouseAction", "action": "scroll_down", "scroll_clicks": 3}]},
        {"trigger": "chord", "actions": [
            {"type": "KeyDown", "keys": ["ctrl"]},
            {"type": "PressKey", "keys": ["c"], "duration": 0},
            {"type": "KeyUp", "keys": ["ctrl"]}]},
        {"trigger": "speak", "actions": [
            {"type": "Say", "text": "hi & <bye>", "volume": 60, "rate": -1}]},
        {"trigger": "wait", "actions": [{"type": "Pause", "duration": 2.5}]},
        {"trigger": "zoom [out; in]", "idiom": False, "actions": [
            {"type": "BeginCondition", "condition": {
                "valueType": "Text", "operator": "Ends With",
                "leftOperand": "{LASTSPOKENCMD}", "value": "out"}},
            {"type": "SetDecimal", "variable": "z", "value": 2.25},
            {"type": "Else"},
            {"type": "SetDecimal", "variable": "z", "value": 0.75},
            {"type": "EndCondition"},
            {"type": "Write", "text": "{DEC:z}"}]},
    ]}

    def test_byte_identity_modulo_guids(self):
        legacy = GUID_RE.sub("<GUID/>", vap_generator.generate_profile(self.DOC))
        model, infos, warnings = lower(self.DOC)
        self.assertEqual(infos, [])
        new_xml, emit_warnings = emit(model, DICT)
        self.assertEqual(warnings + emit_warnings, [])
        new = GUID_RE.sub("<GUID/>", new_xml)
        self.assertEqual(legacy, new)


if __name__ == "__main__":
    unittest.main(verbosity=2)
