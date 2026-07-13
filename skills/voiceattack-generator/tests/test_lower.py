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

import csv
import json
import os
import re
import subprocess
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPTS = os.path.join(os.path.dirname(HERE), "scripts")
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
PROFILES = os.path.join(ROOT, "reference profiles")
sys.path.insert(0, SCRIPTS)

import vap_generator  # noqa: E402  (same skill: the legacy oracle)
from gen2 import names  # noqa: E402
from gen2.emit_profile import emit  # noqa: E402
from gen2 import lower as gen2_lower  # noqa: E402
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


class Row2AuthoringVerbTest(unittest.TestCase):
    """W5 authoring verbs: SetText/SetBoolean/SetInteger/QuickInput lower to the same
    schema records the decoder produces, with SetDecimal/Write-pattern hard-fail
    validation. NO SetSmallInt verb: legacy-in, never authored-out."""

    def test_settext_lowering(self):
        cmd, _, warnings = one_command({"trigger": "t", "actions": [
            {"type": "SetText", "variable": "Script", "value": "hello {TXT:x}"}]})
        self.assertEqual(warnings, [])
        r = cmd["actions"][0]
        self.assertEqual(r["actionType"], {"code": 21, "name": "SetText"})
        self.assertEqual((r["targetVariable"], r["value"]),
                         ("Script", "hello {TXT:x}"))

    def test_setboolean_lowering(self):
        cmd, _, _ = one_command({"trigger": "t", "actions": [
            {"type": "SetBoolean", "variable": "submit", "value": False}]})
        r = cmd["actions"][0]
        self.assertEqual(r["actionType"]["code"], 36)
        self.assertIs(r["value"], False)

    def test_setinteger_lowering(self):
        cmd, _, _ = one_command({"trigger": "t", "actions": [
            {"type": "SetInteger", "variable": "c", "value": 4}]})
        r = cmd["actions"][0]
        self.assertEqual(r["actionType"]["code"], 37)
        self.assertEqual((r["targetVariable"], r["value"]), ("c", 4))

    def test_quickinput_lowering(self):
        cmd, _, _ = one_command({"trigger": "t", "actions": [
            {"type": "QuickInput", "text": "{TXT:System1}", "per_key_delay": 0.05}]})
        r = cmd["actions"][0]
        self.assertEqual(r["actionType"]["code"], 40)
        self.assertEqual((r["text"], r["perKeyDelay"]), ("{TXT:System1}", 0.05))

    def test_quickinput_delay_optional(self):
        cmd, _, _ = one_command({"trigger": "t", "actions": [
            {"type": "QuickInput", "text": "abc"}]})
        self.assertNotIn("perKeyDelay", cmd["actions"][0])

    def test_no_setsmallint_authoring_verb(self):
        _, _, warnings = one_command({"trigger": "t", "actions": [
            {"type": "SetSmallInt", "variable": "v", "value": 1}]})
        self.assertIn("Unknown action type 'SetSmallInt' - skipped", warnings)

    def test_authored_int32_bounds_hard_fail(self):
        # W5 fix wave finding 3, authored door: exit-1 class, value named.
        for value in (2147483648, -2147483649):
            with self.subTest(value=value):
                with self.assertRaisesRegex(LoweringError,
                                            r"%d.*outside Int32" % value):
                    lower({"commands": [{"trigger": "t", "actions": [
                        {"type": "SetInteger", "variable": "v", "value": value}]}]})

    def test_authored_int32_boundaries_accepted(self):
        cmd, _, warnings = one_command({"trigger": "t", "actions": [
            {"type": "SetInteger", "variable": "v", "value": 2147483647},
            {"type": "SetInteger", "variable": "w", "value": -2147483648}]})
        self.assertEqual(warnings, [])
        self.assertEqual([a["value"] for a in cmd["actions"]],
                         [2147483647, -2147483648])

    def test_authored_control_chars_hard_fail(self):
        # W5 door split: an AUTHOR typing a control character still gets exit 1.
        cases = [
            {"type": "Say", "text": "hi\x08"},
            {"type": "Write", "text": "a\x00b"},
            {"type": "SetDecimal", "variable": "v\x02", "value": 1},
            {"type": "SetText", "variable": "v", "value": "x\x1b"},
            {"type": "SetBoolean", "variable": "v\x0b", "value": True},
            {"type": "SetInteger", "variable": "v\x7f", "value": 1},
            {"type": "QuickInput", "text": "a\x01b"},
        ]
        for action in cases:
            with self.subTest(type=action["type"]):
                with self.assertRaisesRegex(LoweringError,
                                            r"control character U\+00"):
                    lower({"commands": [{"trigger": "t", "actions": [action]}]})

    def test_authored_setdecimal_value_hard_fails(self):
        # Moved from the emit side by the W5 door split: authored SetDecimal values
        # validate at lowering time now.
        for value, pattern in ((float("nan"), "finite"),
                               ("abc", "numeric 'value'"),
                               (True, "numeric 'value'"),
                               (None, "numeric 'value'")):
            with self.subTest(value=repr(value)):
                with self.assertRaisesRegex(LoweringError, pattern):
                    lower({"commands": [{"trigger": "t", "actions": [
                        {"type": "SetDecimal", "variable": "v", "value": value}]}]})

    def test_row2_authoring_hard_fails(self):
        cases = [
            ({"type": "SetText", "value": "x"}, "non-empty string 'variable'"),
            ({"type": "SetText", "variable": "v", "value": 5}, "string 'value'"),
            ({"type": "SetBoolean", "variable": "v", "value": "yes"},
             "boolean 'value'"),
            ({"type": "SetBoolean", "variable": "v", "value": 1},
             "boolean 'value'"),
            ({"type": "SetInteger", "variable": "v", "value": 1.5},
             "integer 'value'"),
            ({"type": "SetInteger", "variable": "v", "value": True},
             "integer 'value'"),
            ({"type": "QuickInput", "per_key_delay": 0.05}, "string 'text'"),
            ({"type": "QuickInput", "text": "a", "per_key_delay": -1},
             "non-negative"),
            ({"type": "QuickInput", "text": "a", "per_key_delay": True},
             "non-negative"),
        ]
        for action, pattern in cases:
            with self.subTest(pattern=pattern):
                with self.assertRaisesRegex(LoweringError, pattern):
                    lower({"commands": [{"trigger": "t", "actions": [action]}]})


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


class IdiomDispatchSimulationTest(unittest.TestCase):
    """W4 fix-wave finding 1: collision analysis IS a dispatch simulation over every
    utterance the trigger grammar produces — VA matches {LASTSPOKENCMD} against the
    FULL spoken phrase, so tokens collide with the fixed prefix/tail, optional-group
    text, and across word boundaries. The verifier's five silently-misdispatching
    constructions (A/B/C/D/M) are pinned here as named regressions, plus the general
    property: every ACCEPTED lowering dispatches every utterance to its own branch."""

    def assert_refuses(self, trigger, n=2):
        cmd = idiom_cmd(trigger=trigger, keys=[str(i + 1) for i in range(n)])
        with self.assertRaisesRegex(LoweringError, "cannot dispatch safely"):
            one_command(cmd)

    def assert_verified(self, trigger, n=2):
        """Lower, then independently re-simulate the emitted chain over the trigger's
        utterances — the acceptance property, reusing the compiler's own simulator."""
        cmd = idiom_cmd(trigger=trigger, keys=[str(i + 1) for i in range(n)])
        lowered, infos, _ = one_command(cmd)
        self.assertEqual(len(infos), 1, "idiom must fire for this construction")
        branches = []
        acts = lowered["actions"]
        suffix_mode = None
        for i, a in enumerate(acts):
            if a["actionType"]["name"] in ("BeginCondition", "ElseIf"):
                cond = a["condition"]
                suffix_mode = cond["operator"]["name"] == "Ends With"
                branches.append((cond["value"], acts[i + 1]))
        segments, problem = gen2_lower._parse_trigger(cmd["trigger"])
        self.assertIsNone(problem)
        utterances, _ = gen2_lower._trigger_utterances(segments)
        tagged = [(u, t) for u, t in utterances if t is not None]
        self.assertGreater(len(tagged), 0)
        failure = gen2_lower._simulate_dispatch(branches, suffix_mode, tagged)
        self.assertIsNone(failure, "accepted lowering misdispatches: %r" % (failure,))
        return [t for t, _ in branches]

    def test_verifier_A_prefix_boundary_suffix_refuses(self):
        # spoken "camera pan up" ends with "n up" (the n comes from "pan").
        self.assert_refuses("camera pan [n up; up]")

    def test_verifier_B_fixed_prefix_contains_refuses(self):
        # token 'down' sits in the fixed prefix of every utterance.
        self.assert_refuses("scroll down [down; up] [fast;]")

    def test_verifier_C_fixed_tail_reorders_correctly(self):
        # 'no' hides inside the fixed-tail word 'now'; testing 'yes' first resolves it.
        order = self.assert_verified("zoom [no; yes] now")
        self.assertEqual(order, ["yes", "no"])

    def test_verifier_D_optional_group_text_refuses(self):
        # 'right' hides inside the optional group's own text "right now".
        self.assert_refuses("pan [right; left] [right now;]")

    def test_verifier_M_optional_head_refuses(self):
        # with the optional head omitted, the short utterance EQUALS the long token.
        self.assert_refuses("[press;] pan [an; pan an]")

    def test_property_on_all_accepted_constructions(self):
        for trigger, n in (("pan [up; down]", 2),
                           ("[press;] pan [up; down]", 2),
                           ("zoom [out; in] [more;]", 2),
                           ("game [normal; fast; fastest]", 3),
                           ("go [fast; very fast]", 2),
                           ("turn [key one; one]", 2),
                           ("pan [a; b a; c b a]", 3),
                           ("game [fast; fastest] [now;]", 2),
                           ("do [la; plan]", 2)):
            with self.subTest(trigger=trigger):
                self.assert_verified(trigger, n)

    def test_refusal_names_utterance_and_token(self):
        with self.assertRaisesRegex(
                LoweringError, r"'camera pan up'.*meant for alternative 'up'.*'n up'"):
            one_command(idiom_cmd(trigger="camera pan [n up; up]"))

    def test_identical_actions_do_not_fire(self):
        # Finding 3: an overload with identical branches is meaningless (double-tap).
        cmd = {"trigger": "pan [up; down]", "actions": [
            {"type": "PressKey", "keys": ["w"]}, {"type": "PressKey", "keys": ["w"]}]}
        lowered, infos, _ = one_command(cmd)
        self.assertEqual(infos, [])
        self.assertEqual(types_of(lowered), ["PressKey", "PressKey"])

    def test_all_refused_types_do_not_fire(self):
        # Finding 5: no empty Begin/ElseIf/End shell around refused actions.
        cmd = {"trigger": "warp [in; out]", "actions": [
            {"type": "Teleport", "which": 1}, {"type": "Teleport", "which": 2}]}
        lowered, infos, warnings = one_command(cmd)
        self.assertEqual(infos, [])
        self.assertEqual(lowered["actions"], [])
        self.assertEqual(warnings.count("Unknown action type 'Teleport' - skipped"), 2)

    def test_utterance_cap_passes_through_with_warning(self):
        opt = " ".join("[w%d;]" % i for i in range(10))  # 2^10 optional combos
        cmd = idiom_cmd(trigger="go [a; b] " + opt)
        lowered, infos, warnings = one_command(cmd)
        self.assertEqual(infos, [])
        self.assertEqual(types_of(lowered), ["PressKey", "PressKey"])
        self.assertTrue(any("cap" in w and "passing the command through" in w
                            for w in warnings), warnings)

    def test_wrong_door_schema_json_refused(self):
        # Finding 4: decoded schema JSON must be routed to python3 -m gen2.
        with self.assertRaisesRegex(LoweringError, r"schema_version.*-m gen2"):
            lower({"schema_version": 2, "profile": {"name": "X"}, "commands": []})


class RangeAndGrammarTest(unittest.TestCase):
    """W4 closure wave: the enumerator models VA's `N..M` numeric-range wildcard
    exactly as the CSV oracle shows; unmodelable trigger grammar (nested/unmatched
    brackets, unverified range forms) vetoes the idiom — warn + pass through, never a
    chain verified against garbage utterances."""

    def assert_vetoed(self, trigger, reason_fragment):
        cmd = idiom_cmd(trigger=trigger)
        lowered, infos, warnings = one_command(cmd)
        self.assertEqual(infos, [])
        self.assertEqual(types_of(lowered), ["PressKey", "PressKey"])
        self.assertTrue(any(reason_fragment in w and
                            "passing the command through untouched" in w
                            for w in warnings), warnings)

    def test_range_expansion_matches_oracle_shape(self):
        # corinthian's `[inch;] Climb [1..4;] [continuous;]` per the VA CSV export.
        segments, problem = gen2_lower._parse_trigger(
            "[inch;] Climb [1..4;] [continuous;]")
        self.assertIsNone(problem)
        utts, count = gen2_lower._trigger_utterances(segments)
        self.assertEqual(count, 20)  # [inch;]=2 x [1..4;]=5 x [continuous;]=2
        spoken = {s for s, _ in utts}
        self.assertIn("Climb", spoken)             # everything optional omitted
        self.assertIn("Climb 1", spoken)
        self.assertIn("inch Climb 4 continuous", spoken)
        self.assertIn("Climb continuous", spoken)
        self.assertNotIn("Climb 1..4", spoken)     # the literal must never survive
        self.assertEqual(len(spoken), 20)

    def test_live_range_repro_refuses_over_real_expansion(self):
        # The verifier's live repro: token '5' captures VA's real "select 6 5"
        # utterance (range expanded), so the idiom must refuse — before this wave the
        # INFO line falsely claimed "verified over 4 utterances".
        with self.assertRaisesRegex(LoweringError,
                                    r"'select 6 5'.*captured by token '5'"):
            one_command(idiom_cmd(trigger="select [5; 6] [1..12;]"))

    def test_range_in_dispatch_group_counts_expanded(self):
        # [1..3] IS the dispatch group: 3 alternatives after expansion.
        cmd = {"trigger": "select [1..3]", "actions": [
            {"type": "PressKey", "keys": [k]} for k in ("a", "b", "c")]}
        lowered, infos, _ = one_command(cmd)
        self.assertEqual(len(infos), 1)
        values = [a["condition"]["value"] for a in lowered["actions"]
                  if "condition" in a]
        self.assertEqual(values, ["1", "2", "3"])

    def test_range_in_dispatch_group_never_miscounts(self):
        # Two actions against three expanded alternatives: silent no-fire, no veto.
        cmd = {"trigger": "select [1..3]", "actions": [
            {"type": "PressKey", "keys": ["a"]}, {"type": "PressKey", "keys": ["b"]}]}
        lowered, infos, warnings = one_command(cmd)
        self.assertEqual((infos, warnings), ([], []))
        self.assertEqual(types_of(lowered), ["PressKey", "PressKey"])

    def test_nested_brackets_vetoed(self):
        self.assert_vetoed("pan [up; [down]]", "nested brackets")

    def test_unmatched_open_bracket_vetoed(self):
        self.assert_vetoed("pan [up; down", "unmatched '['")

    def test_unmatched_close_bracket_vetoed(self):
        self.assert_vetoed("pan up; down]", "unmatched ']'")

    def test_zero_padded_range_vetoed(self):
        self.assert_vetoed("pan [01..04]", "zero-padded")

    def test_descending_range_vetoed(self):
        self.assert_vetoed("pan [4..1]", "descending")

    def test_oversize_range_vetoed(self):
        self.assert_vetoed("pan [1..9999]", "cap")

    def test_range_like_token_vetoed(self):
        self.assert_vetoed("go [ready 1..2; other]", "range-like")

    def test_authored_trailing_space_preserved(self):
        # VA's CSV keeps an authored trailing space ('set decimal test ') — the
        # enumerator must reproduce the oracle text exactly (closure item 4).
        segments, _ = gen2_lower._parse_trigger("set decimal test ")
        utts, _ = gen2_lower._trigger_utterances(segments)
        self.assertEqual(utts, [("set decimal test ", None)])

    def test_empty_tagged_set_refuses(self):
        # Hard guard (closure item 3): a vacuous simulation pass must be impossible —
        # unreachable while parser and detector share one parse, so SIMULATE the
        # drift: an enumerator that comes back with no tagged utterances.
        real = gen2_lower._trigger_utterances
        gen2_lower._trigger_utterances = lambda segments: ([("pan up", None)], 1)
        try:
            with self.assertRaisesRegex(LoweringError, "no dispatch-tagged utterances"):
                gen2_lower._compile_idiom(
                    {}, [{"type": "PressKey", "keys": ["a"]},
                         {"type": "PressKey", "keys": ["b"]}], "pan [up; down]",
                    lambda m: self.fail("INFO printed for unverified chain: %s" % m),
                    lambda m: None)
        finally:
            gen2_lower._trigger_utterances = real


class TriggerExpansionOracleTest(unittest.TestCase):
    """THE ORACLE (closure item 5): VA's own CSV exports are the only independent
    check on the enumerator — the trust anchor of every dispatch proof. Differential:
    for every command in each reference profile, _trigger_utterances must reproduce
    the CSV's expanded phrase set EXACTLY (text-exact, ranges included), with only the
    known exclusions: commands VA omits from the CSV wholly (corinthian's 8 dictation/
    listening/system commands). Reference profiles and CSVs are gitignored local
    assets — skip-if-missing; the decoder is driven as a SUBPROCESS because this suite
    never imports vap2 (architecture ruling)."""

    PAIRS = [("corinthian-4-Profile.vap", "corinthian-4-Profile.csv", 8),
             ("Probe B-Profile.vap", "Probe B-Profile.csv", 0),
             ("conditionals-Profile.vap", "conditionals-Profile.csv", 0)]

    def triggers_of(self, vap_path):
        decoder_scripts = os.path.join(ROOT, "skills", "voiceattack-decoder",
                                       "scripts")
        if not os.path.isdir(os.path.join(decoder_scripts, "vap2")):
            self.skipTest("decoder skill not present")
        r = subprocess.run([sys.executable, "-m", "vap2", vap_path, "--stdout"],
                           capture_output=True, text=True, cwd=decoder_scripts)
        if r.returncode != 0:
            self.skipTest("decoder subprocess failed: %s" % r.stderr[:200])
        return [c["phrase"] for c in json.loads(r.stdout)["commands"]]

    def test_csv_expansion_differential(self):
        ran_any = False
        for vap_name, csv_name, expected_absent in self.PAIRS:
            vap_path = os.path.join(PROFILES, vap_name)
            csv_path = os.path.join(PROFILES, csv_name)
            if not (os.path.exists(vap_path) and os.path.exists(csv_path)):
                continue
            ran_any = True
            with self.subTest(profile=vap_name):
                triggers = self.triggers_of(vap_path)
                with open(csv_path, newline="", encoding="utf-8-sig") as f:
                    csv_set = {row[0] for row in csv.reader(f) if row}
                self.assertGreater(len(csv_set), 0)

                enum = {}
                for trigger in triggers:
                    segments, problem = gen2_lower._parse_trigger(trigger)
                    self.assertIsNone(
                        problem, "unmodelable real-world trigger %r: %s"
                        % (trigger, problem))
                    utts, count = gen2_lower._trigger_utterances(segments)
                    self.assertIsNotNone(
                        utts, "real-world trigger %r blew the cap (%d)"
                        % (trigger, count))
                    enum[trigger] = {s for s, _ in utts}

                absent = sorted(t for t, us in enum.items() if not (us & csv_set))
                self.assertEqual(
                    len(absent), expected_absent,
                    "wholly-absent command set changed: %r" % absent)
                union_all = set().union(*enum.values())
                self.assertEqual(
                    sorted(csv_set - union_all), [],
                    "CSV phrases the enumerator never produces")
                covered = set().union(*(us for t, us in enum.items()
                                        if t not in absent))
                self.assertEqual(
                    sorted(covered - csv_set), [],
                    "enumerated utterances VA's oracle does not list")
        if not ran_any:
            self.skipTest("no local CSV oracle pairs present")


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
