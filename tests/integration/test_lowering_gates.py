"""W4 lowering gates (encoder refactor plan §5 W4; build spec Wave 2).

Gate (a) — BYTE-IDENTITY modulo GUIDs, legacy emission vs the new lower+emit pipeline,
on both committed fixtures. Interpretation (build spec): this leg proves the PLUMBING is
lossless independent of the idiom compiler — `cities_skylines_2_conditional.json` runs
with defaults and the idiom detector MUST NOT fire on it (it has explicit condition
actions; a firing is a detector bug), while `cities_skylines_2.json` runs with the idiom
opted out (--no-idiom). Gate (b) proves the COMPILER.

Gate (b) — THE TRAP GATE: the original naive `cities_skylines_2.json`, lowered with
DEFAULT settings (idiom ON, D2 ruling), emitted, and decoded via vap2, must be
semantically identical to the decode of the LEGACY emission of
`cities_skylines_2_conditional.json`: same phrases in order, same action sequences, same
condition records (operators, operands, values, pairing, blockOrdinal), same keys and
durations, same categories — modulo GUIDs only. The two-week-old trap is now the
permanent regression fixture.

Both gates drive vap_generator.py as a subprocess (the real CLI, both paths); .vap
artifacts go to a tempdir, never the repo.

Run:  python3 -m unittest discover -s tests/integration -t . -v
"""

import os
import re
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "skills", "voiceattack-decoder", "scripts"))
sys.path.insert(0, os.path.join(ROOT, "skills", "voiceattack-generator", "scripts"))

import vap2  # noqa: E402

GENERATOR = os.path.join(ROOT, "skills", "voiceattack-generator", "scripts",
                         "vap_generator.py")
NAIVE = os.path.join(ROOT, "cities_skylines_2.json")
CONDITIONAL = os.path.join(ROOT, "cities_skylines_2_conditional.json")

GUID_RE = re.compile(r"<(Id|BaseId)>[0-9a-f\-]{36}</(Id|BaseId)>")
_DURATION_FIELDS = ("duration", "clickDuration", "scroll_clicks")

# Provenance-only normalization — the fixpoint test's exact set (test_fixpoint._STRIP
# + actionType.confidence), duplicated here so this file stays runnable standalone.
_STRIP = {"offset", "head", "guid", "source"}


def _normalize(action):
    out = {k: v for k, v in action.items() if k not in _STRIP}
    at = out.get("actionType")
    if isinstance(at, dict):
        out["actionType"] = {k: v for k, v in at.items() if k != "confidence"}
    return out


def require(path):
    if not os.path.exists(path):
        raise unittest.SkipTest("missing fixture: %s" % os.path.basename(path))


def generate(fixture, out_path, *flags):
    r = subprocess.run([sys.executable, GENERATOR, fixture, out_path, *flags],
                       capture_output=True, text=True)
    if r.returncode not in (0, 2):
        raise AssertionError("generator failed (%d): %s" % (r.returncode, r.stderr))
    with open(out_path, "r", encoding="utf-8") as f:
        return f.read(), r.stderr


def mask(xml):
    return GUID_RE.sub(r"<\1>GUID</\2>", xml)


class ByteIdentityGateTest(unittest.TestCase):
    """Gate (a): the new pipeline reproduces the legacy emission byte-for-byte modulo
    GUIDs when the idiom compiler is out of the picture (absent or opted out)."""

    def assert_byte_identical(self, fixture, new_flags, forbid_idiom_fire):
        require(fixture)
        with tempfile.TemporaryDirectory() as td:
            legacy_xml, _ = generate(fixture, os.path.join(td, "legacy.vap"),
                                     "--legacy-emit")
            new_xml, stderr = generate(fixture, os.path.join(td, "new.vap"), *new_flags)
        if forbid_idiom_fire:
            self.assertNotIn("INFO:", stderr,
                             "idiom detector fired where it must not (detector bug)")
        self.assertEqual(mask(legacy_xml), mask(new_xml))

    def test_conditional_fixture_default_pipeline(self):
        # Explicit condition actions present -> the detector must stay silent.
        self.assert_byte_identical(CONDITIONAL, (), forbid_idiom_fire=True)

    def test_naive_fixture_idiom_opted_out(self):
        self.assert_byte_identical(NAIVE, ("--no-idiom",), forbid_idiom_fire=True)


class TrapGateTest(unittest.TestCase):
    """Gate (b): naive fixture + default lowering == conditional fixture + legacy
    emission, compared on the decoded semantics (fixpoint dimensions, full precision)."""

    def test_naive_lowered_equals_conditional_legacy(self):
        require(NAIVE)
        require(CONDITIONAL)
        with tempfile.TemporaryDirectory() as td:
            new_path = os.path.join(td, "naive_lowered.vap")
            legacy_path = os.path.join(td, "conditional_legacy.vap")
            _, stderr = generate(NAIVE, new_path)  # DEFAULT settings: idiom ON
            generate(CONDITIONAL, legacy_path, "--legacy-emit")
            self.assertEqual(stderr.count("INFO:"), 5,
                             "the naive fixture's five overloaded triggers must all "
                             "lower, loudly: %s" % stderr)
            j_new = vap2.decode_file(new_path)
            j_leg = vap2.decode_file(legacy_path)

        self.assertEqual([c["phrase"] for c in j_new["commands"]],
                         [c["phrase"] for c in j_leg["commands"]])
        self.assertEqual([c["category"]["value"] for c in j_new["commands"]],
                         [c["category"]["value"] for c in j_leg["commands"]])

        condition_count = 0
        for ci, (c_new, c_leg) in enumerate(zip(j_new["commands"], j_leg["commands"])):
            where = "command %d (%r)" % (ci, c_new["phrase"])
            self.assertEqual(len(c_new["actions"]), len(c_leg["actions"]),
                             "%s: action count" % where)
            self.assertEqual(
                [a["actionType"]["name"] for a in c_new["actions"]],
                [a["actionType"]["name"] for a in c_leg["actions"]],
                "%s: action sequence" % where)
            for ai, (a_new, a_leg) in enumerate(zip(c_new["actions"],
                                                    c_leg["actions"])):
                loc = "%s action %d" % (where, ai)
                if "keyCodes" in a_new or "keyCodes" in a_leg:
                    self.assertEqual([k["vk"] for k in a_new.get("keyCodes", [])],
                                     [k["vk"] for k in a_leg.get("keyCodes", [])],
                                     "%s: keys" % loc)
                for f in _DURATION_FIELDS:
                    if f in a_new or f in a_leg:
                        self.assertEqual(a_new.get(f), a_leg.get(f),
                                         "%s: %s" % (loc, f))
                if "condition" in a_new or "condition" in a_leg:
                    cd_new, cd_leg = a_new.get("condition"), a_leg.get("condition")
                    self.assertIsNotNone(cd_new, "%s: condition missing (new)" % loc)
                    self.assertIsNotNone(cd_leg, "%s: condition missing (legacy)" % loc)
                    for key in ("valueType", "operator"):
                        self.assertEqual(cd_new[key]["name"], cd_leg[key]["name"],
                                         "%s: condition %s" % (loc, key))
                    for key in ("leftOperand", "pairing", "blockOrdinal"):
                        self.assertEqual(cd_new.get(key), cd_leg.get(key),
                                         "%s: condition %s" % (loc, key))
                    self.assertEqual(("value" in cd_new, cd_new.get("value")),
                                     ("value" in cd_leg, cd_leg.get("value")),
                                     "%s: condition value" % loc)
                    condition_count += 1
                if "block" in a_new or "block" in a_leg:
                    self.assertEqual(a_new.get("block"), a_leg.get("block"),
                                     "%s: block pairing" % loc)
                    condition_count += 1
                # Full normalized records (W4 fix-wave finding 2a): Say/Write/
                # SetDecimal/Mouse/Launch payloads must not pass through this gate
                # blind — the per-dimension asserts above name the frozen fields, this
                # one closes over everything but provenance.
                self.assertEqual(_normalize(a_new), _normalize(a_leg),
                                 "%s: full-record parity" % loc)

        # The gate is about the compiled chains: the comparison must have seen them.
        self.assertGreater(condition_count, 0,
                           "no condition records compared - gate compared nothing")


class PayloadIdiomTwinTest(unittest.TestCase):
    """W4 fix-wave finding 2b: the trap-gate fixtures are PressKey-only, so the FIRED
    idiom path never exercised payload comparison. Here an idiom profile whose branch
    actions carry payloads (Say, Write, SetDecimal, MouseAction) must lower+emit+decode
    semantically identical to its hand-written explicit-conditional twin — full
    normalized records, provenance-only stripping."""

    IDIOM_DOC = {"name": "PayloadTwin", "commands": [
        {"trigger": "announce [one; two]", "category": "t", "actions": [
            {"type": "Say", "text": "first thing", "volume": 60, "rate": 1},
            {"type": "Say", "text": "second thing", "volume": 80, "rate": -1}]},
        {"trigger": "log [alpha; beta]", "category": "t", "actions": [
            {"type": "Write", "text": "took alpha {DEC:v}"},
            {"type": "Write", "text": "took beta {DEC:v}"}]},
        {"trigger": "level [high; low]", "category": "t", "actions": [
            {"type": "SetDecimal", "variable": "lvl", "value": 2.5},
            {"type": "SetDecimal", "variable": "lvl", "value": 0.5}]},
        {"trigger": "wheel [in; out]", "category": "t", "actions": [
            {"type": "MouseAction", "action": "scroll_up", "scroll_clicks": 3},
            {"type": "MouseAction", "action": "scroll_down", "scroll_clicks": 5}]},
    ]}

    @staticmethod
    def twin_of(doc):
        """The hand-written explicit-conditional equivalent (Ends With chain in the
        idiom compiler's verified order — none of these triggers needs a reorder)."""
        twin = {"name": doc["name"], "commands": []}
        for cmd in doc["commands"]:
            tokens = re.search(r"\[([^\]]*)\]", cmd["trigger"]).group(1).split(";")
            tokens = [t.strip() for t in tokens]
            actions = []
            for i, (token, action) in enumerate(zip(tokens, cmd["actions"])):
                actions.append({
                    "type": "BeginCondition" if i == 0 else "ElseIf",
                    "condition": {"valueType": "Text", "operator": "Ends With",
                                  "leftOperand": "{LASTSPOKENCMD}", "value": token}})
                actions.append(dict(action))
            actions.append({"type": "EndCondition"})
            twin["commands"].append({"trigger": cmd["trigger"],
                                     "category": cmd["category"], "actions": actions})
        return twin

    def test_payload_idiom_matches_explicit_twin(self):
        from gen2 import names as gen2_names
        from gen2.emit_profile import emit
        from gen2.lower import lower_profile
        dictionary = gen2_names.load()

        model_a, infos_a, warns_a = lower_profile(self.IDIOM_DOC, dictionary)
        model_b, infos_b, warns_b = lower_profile(self.twin_of(self.IDIOM_DOC),
                                                  dictionary)
        self.assertEqual(len(infos_a), 4, "all four idiom commands must fire")
        self.assertEqual(infos_b, [], "explicit conditionals must not re-fire")
        self.assertEqual(warns_a + warns_b, [])

        xml_a, _ = emit(model_a, dictionary)
        xml_b, _ = emit(model_b, dictionary)
        j_a = vap2.decode_bytes(xml_a.encode("utf-8"))
        j_b = vap2.decode_bytes(xml_b.encode("utf-8"))

        self.assertEqual([c["phrase"] for c in j_a["commands"]],
                         [c["phrase"] for c in j_b["commands"]])
        payload_keys_seen = set()
        for c_a, c_b in zip(j_a["commands"], j_b["commands"]):
            acts_a = [_normalize(a) for a in c_a["actions"]]
            acts_b = [_normalize(a) for a in c_b["actions"]]
            self.assertEqual(acts_a, acts_b, c_a["phrase"])
            for a in acts_a:
                payload_keys_seen |= set(a) & {"text", "volume", "rate",
                                               "targetVariable", "value",
                                               "scroll_clicks", "contextCode"}
        # Tripwire: the payload fields must actually have been part of the comparison.
        self.assertEqual(payload_keys_seen,
                         {"text", "volume", "rate", "targetVariable", "value",
                          "scroll_clicks", "contextCode"})


if __name__ == "__main__":
    unittest.main(verbosity=2)
