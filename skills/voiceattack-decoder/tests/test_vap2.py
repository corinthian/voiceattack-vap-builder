"""vap2 regression harness (plan W6).

Checked-in per the verification bar (prelim §9). The reference profiles and CSVs are
gitignored local-only assets, so every test that needs one is guarded by skip-if-missing —
the suite runs green (with skips) on a fresh checkout and fully where the assets are present.

Run:  python3 -m unittest discover -s skills/voiceattack-decoder/tests -v
  or:  python3 skills/voiceattack-decoder/tests/test_vap2.py
"""

import csv
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
SCRIPTS = os.path.join(ROOT, "skills", "voiceattack-decoder", "scripts")
PROFILES = os.path.join(ROOT, "reference profiles")
sys.path.insert(0, SCRIPTS)

import vap2  # noqa: E402
import vap2.names as names  # noqa: E402
import vap2.container as container  # noqa: E402
import vap2.walker as walker  # noqa: E402
import vap2.primitives as P  # noqa: E402

DICT = names.load()


def profile_path(fname):
    return os.path.join(PROFILES, fname)


def have(fname):
    return os.path.exists(profile_path(fname))


def decode(fname):
    return vap2.decode_file(profile_path(fname), DICT)


def require(fname):
    if not have(fname):
        raise unittest.SkipTest("missing local asset: %s" % fname)


# Expected structural totals (spec §2 evidence base; corinthian anchored by header count).
CENSUS = {
    "zoom-if-else.vap": {"commands": 1, "actions": 5},
    "numkeys-Profile.vap": {"actions": 16},
    "conditionals-Profile.vap": {"actions": 111},
    "corinthian-4-Profile.vap": {"commands": 201, "actions": 1168},
    "base profile-Profile.vap": {"actions": 303},
    "Probe B-Profile.vap": {"commands": 10, "actions": 32},
}


class LandmarkTest(unittest.TestCase):
    """The tightest constraint in the spec — zoom §13 exact offsets and derefs."""

    def test_zoom_landmarks(self):
        require("zoom-if-else.vap")
        with open(profile_path("zoom-if-else.vap"), "rb") as f:
            buf = container.decompress(f.read())
        self.assertEqual(len(buf), 3111)
        cands = walker.discover_commands(buf)
        self.assertEqual(len(cands), 1)
        z = cands[0]
        self.assertEqual(z["pos"], 750)
        self.assertEqual(z["action_count"], 5)
        self.assertEqual(z["actions_start"], 788)
        head, m = walker.read_members(buf, 788)
        self.assertEqual(head, 347)
        self.assertEqual((m[0], m[1]), (32, 140))
        self.assertEqual(P.u32(buf, 788 + m[2]), 19)   # Begin
        self.assertEqual(P.u32(buf, 788 + m[20]), 6)   # Contains
        self.assertEqual(P.string(buf, 788 + m[19]), "{LASTSPOKENCMD}")
        self.assertEqual(P.string(buf, 788 + m[7]), "out")


class CensusGateTest(unittest.TestCase):
    """Envelope invariants + counts across every reference profile (prelim §9.3)."""

    def test_counts_and_chain_integrity(self):
        for fname, exp in CENSUS.items():
            with self.subTest(profile=fname):
                require(fname)
                prof = decode(fname)
                c = prof["census"]
                if "commands" in exp:
                    self.assertEqual(prof["profile"]["commandCount"], exp["commands"])
                self.assertEqual(c["totalActions"], exp["actions"])
                self.assertEqual(c["chainBreaks"], 0, "chain break in %s" % fname)

    def test_unknown_accounting_consistent(self):
        # Coverage is a measured number, and the R3 tripwire budget must equal the
        # unknown-marked count on the CSV-oracle profile (corinthian): all codes attributed.
        require("corinthian-4-Profile.vap")
        c = decode("corinthian-4-Profile.vap")["census"]
        self.assertEqual(c["unknownMarked"], 0)
        self.assertEqual(c["unknownBudgetFromHistogram"], 0)
        self.assertEqual(c["decoded"], 1168)


class ProbeBOracleTest(unittest.TestCase):
    """By-construction oracle: 32/32 decoded, every self-labeling marker reproduced (§9.1)."""

    def setUp(self):
        require("Probe B-Profile.vap")
        self.prof = decode("Probe B-Profile.vap")
        self.actions = [a for cmd in self.prof["commands"] for a in cmd["actions"]]

    def _find(self, atype_name, **kv):
        for a in self.actions:
            if a["actionType"]["name"] == atype_name and all(a.get(k) == v for k, v in kv.items()):
                return a
        return None

    def test_zero_unknown(self):
        self.assertEqual(self.prof["census"]["unknownMarked"], 0)
        self.assertEqual(self.prof["census"]["totalActions"], 32)

    def test_say_markers(self):
        say = self._find("Say")
        self.assertEqual(say["volume"], 43)
        self.assertEqual(say["rate"], 7)
        self.assertEqual(say["text"], "say-marker")

    def test_set_integer_and_decimal_and_smallint(self):
        self.assertEqual(self._find("SetInteger", targetVariable="ssi")["value"], 33)
        self.assertEqual(self._find("SetDecimal", targetVariable="sd")["value"], "4.44")

    def test_mouse_move_and_scroll(self):
        move = self._find("MouseAction", contextCode="Move")
        self.assertEqual((move["x"], move["y"]), (333, 444))
        sf = self._find("MouseAction", contextCode="SF")
        self.assertEqual(sf["scroll_clicks"], 5.0)
        self.assertEqual(sf["action"], "scroll_up")

    def test_boolean_value_not_order(self):
        # bfa=False built FIRST, btr=True built SECOND — value tracks the dropdown, not order.
        self.assertIs(self._find("SetBoolean", targetVariable="bfa")["value"], False)
        self.assertIs(self._find("SetBoolean", targetVariable="btr")["value"], True)

    def test_set_integer_mode_gating(self):
        siv1 = self._find("SetInteger", targetVariable="siv1")
        self.assertEqual((siv1["source"], siv1["min"], siv1["max"]), ("random", "0", "9"))
        siv6 = self._find("SetInteger", targetVariable="siv6")
        self.assertEqual(siv6["operation"]["name"], "plus")

    def test_categories_survive_descriptions(self):
        # Probe B commands carry author descriptions in the trailing region; the category
        # heuristic must still recover each command's real category (stop-at-version bound).
        csv_path = profile_path("Probe B-Profile.csv")
        if not os.path.exists(csv_path):
            self.skipTest("missing Probe B CSV oracle")
        with open(csv_path, newline="") as f:
            want = {r[0]: r[4] for r in csv.reader(f) if len(r) > 4}
        got = {c["phrase"]: c["category"]["value"] for c in self.prof["commands"]}
        for phrase, cat in want.items():
            self.assertEqual(got.get(phrase), cat, "category for %r" % phrase)

    def test_pastedictation_refuted(self):
        # The dictation sweep records a SetClipboard, not a PasteDictation action (§9.1).
        clip = self._find("SetClipboard", text="No such action as 'Paste dictation'")
        self.assertIsNotNone(clip)


class ConditionsOracleTest(unittest.TestCase):
    """Authored operator/type sweeps; valueless suppression; no false compounds."""

    def setUp(self):
        require("conditionals-Profile.vap")
        self.prof = decode("conditionals-Profile.vap")

    def _compares(self):
        return [a["condition"] for cmd in self.prof["commands"] for a in cmd["actions"]
                if a.get("condition")]

    def test_no_false_compounds(self):
        self.assertFalse(any("compound" in c for c in self._compares()))

    def test_valueless_operators_suppress_value(self):
        for c in self._compares():
            if c["operator"]["name"] in ("Has Been Set", "Has Not Been Set"):
                self.assertNotIn("value", c)
            elif c["operator"]["name"]:
                self.assertIn("value", c)

    def test_all_value_types_present(self):
        names_seen = {c["valueType"]["name"] for c in self._compares()}
        for vt in ("Text", "Integer", "Boolean", "Decimal", "SmallInteger"):
            self.assertIn(vt, names_seen, "value type %s not exercised" % vt)


class CompoundDecodeOnlyTest(unittest.TestCase):
    def test_corinthian_compounds_marked_not_dropped(self):
        require("corinthian-4-Profile.vap")
        prof = decode("corinthian-4-Profile.vap")
        comps = [a["condition"]["compound"] for cmd in prof["commands"]
                 for a in cmd["actions"] if a.get("condition", {}).get("compound")]
        self.assertTrue(comps, "expected real compound blocks in corinthian")
        for cm in comps:
            self.assertFalse(cm["decoded"])
            self.assertGreaterEqual(cm["subConditions"], 2)


class DeterminismTest(unittest.TestCase):
    def test_decode_is_deterministic(self):
        from vap2.emit_json import to_json
        for fname in ("conditionals-Profile.vap", "Probe B-Profile.vap"):
            with self.subTest(profile=fname):
                require(fname)
                self.assertEqual(to_json(decode(fname)), to_json(decode(fname)))


class CorinthianCsvCategoryTest(unittest.TestCase):
    """Category parity against the corinthian CSV, scoped to the commands the CSV covers
    (plan §7 scope note). Coverage is reported, never silently capped."""

    def test_category_parity_on_covered_commands(self):
        require("corinthian-4-Profile.vap")
        csv_path = profile_path("corinthian-4-Profile.csv")
        if not os.path.exists(csv_path):
            self.skipTest("missing corinthian CSV oracle")
        with open(csv_path, newline="") as f:
            csv_cat = {r[0]: r[4] for r in csv.reader(f) if len(r) > 4}
        prof = decode("corinthian-4-Profile.vap")
        matched = mismatches = 0
        bad = []
        for cmd in prof["commands"]:
            if cmd["phrase"] in csv_cat:
                matched += 1
                if cmd["category"]["value"] != csv_cat[cmd["phrase"]]:
                    mismatches += 1
                    bad.append((cmd["phrase"], cmd["category"]["value"], csv_cat[cmd["phrase"]]))
        sys.stderr.write(
            "\n[corinthian CSV category oracle] exact-phrase matched=%d mismatches=%d "
            "(V2 %d cmds; CSV expands phrases so unmatched = expanded/absent, per R2 scope)\n"
            % (matched, mismatches, len(prof["commands"])))
        self.assertGreater(matched, 0, "no exact-phrase matches — oracle wiring broken")
        self.assertEqual(mismatches, 0, "category mismatches: %s" % bad[:5])


class KeyDurationParityTest(unittest.TestCase):
    """prelim §9 #1: key/duration parity with v1 on every command v1 decodes correctly.
    v1 lumps KeyDown/Up/Toggle and PressKey all as 'keypress', so compare against v2's full
    set of key-bearing actions. v2 must MATCH v1 where v1 is right and may only add keys v1
    missed (its documented chord gap) — never disagree on a (vk, duration) pair."""

    KEY_ACTS = {"PressKey", "KeyDown", "KeyUp", "KeyToggle"}

    def _v1(self):
        import importlib.util
        path = os.path.join(SCRIPTS, "vap_decoder.py")
        spec = importlib.util.spec_from_file_location("vap_decoder_v1", path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod

    def _v2_keys(self, cmd):
        out = []
        for a in cmd["actions"]:
            if a["actionType"]["name"] in self.KEY_ACTS:
                for kc in a.get("keyCodes", []):
                    if isinstance(kc, dict):
                        out.append((kc["vk"], round(a.get("duration", 0.0), 4)))
        return sorted(out)

    def _v1_keys(self, cmd):
        return sorted((a["vk_code"], round(a.get("duration", 0.0), 4))
                      for a in cmd["actions"] if a.get("type") == "keypress")

    def test_key_duration_parity(self):
        if not any(have(f) for f in CENSUS):
            self.skipTest("no local reference profiles — parity needs at least one")
        v1 = self._v1()
        compared = mismatches = 0
        bad = []
        for fname in CENSUS:
            if not have(fname):
                continue
            data = v1.decompress_vap(profile_path(fname))
            v1cmds = {c["phrase"]: c for c in v1.find_commands(data)}
            for c2 in decode(fname)["commands"]:
                if c2["phrase"] not in v1cmds:
                    continue
                k1 = self._v1_keys(v1cmds[c2["phrase"]])
                k2 = self._v2_keys(c2)
                if not k1 and not k2:
                    continue
                compared += 1
                v1set = {vk for vk, _ in k1}
                v2set = {vk for vk, _ in k2}
                if k1 == k2 or v1set < v2set:  # equal, or v2 a strict superset (chord gap)
                    continue
                mismatches += 1
                bad.append((c2["phrase"], k1, k2))
        self.assertGreater(compared, 0, "no commands compared — v1 harness broken")
        self.assertEqual(mismatches, 0, "key/duration disagreements: %s" % bad[:5])


XML_CONDITIONAL_FIXTURE = """<?xml version="1.0" encoding="utf-8"?>
<Profile xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:xsd="http://www.w3.org/2001/XMLSchema">
  <Id>d38fb3f1-b55c-4d76-957e-fd0addd3f7b8</Id>
  <Name>XML Conditional Fixture</Name>
  <Commands>
    <Command>
      <Id>7e38f126-2a11-4418-b0e3-1e064917e1d6</Id>
      <CommandString>zoom [out; in]</CommandString>
      <ActionSequence>
        <CommandAction>
          <Ordinal>0</Ordinal>
          <IndentLevel>0</IndentLevel>
          <ActionType>ConditionStart</ActionType>
          <Duration>0</Duration>
          <Delay>0</Delay>
          <KeyCodes />
          <Context2 xml:space="preserve">out</Context2>
          <X>0</X>
          <Y>0</Y>
          <Z>1</Z>
          <ConditionPairing>2</ConditionPairing>
          <ConditionGroup>1</ConditionGroup>
          <ConditionStartNameFrom>{LASTSPOKENCMD}</ConditionStartNameFrom>
          <ConditionStartOperator>4</ConditionStartOperator>
          <ConditionStartValue>0</ConditionStartValue>
          <ConditionStartValueType>0</ConditionStartValueType>
          <ConditionStartCompareToCondtion />
          <ConditionStartType>1</ConditionStartType>
        </CommandAction>
        <CommandAction>
          <Ordinal>1</Ordinal>
          <IndentLevel>1</IndentLevel>
          <ActionType>PressKey</ActionType>
          <Duration>1.5</Duration>
          <Delay>0</Delay>
          <KeyCodes>
            <unsignedShort>70</unsignedShort>
          </KeyCodes>
          <Context />
          <X>0</X>
          <Y>0</Y>
          <Z>0</Z>
          <ConditionPairing>0</ConditionPairing>
          <ConditionGroup>0</ConditionGroup>
        </CommandAction>
        <CommandAction>
          <Ordinal>2</Ordinal>
          <IndentLevel>0</IndentLevel>
          <ActionType>ConditionElseIf</ActionType>
          <Duration>0</Duration>
          <Delay>0</Delay>
          <KeyCodes />
          <Context2 xml:space="preserve">in</Context2>
          <X>0</X>
          <Y>0</Y>
          <Z>1</Z>
          <ConditionPairing>4</ConditionPairing>
          <ConditionGroup>1</ConditionGroup>
          <ConditionStartNameFrom>{LASTSPOKENCMD}</ConditionStartNameFrom>
          <ConditionStartOperator>4</ConditionStartOperator>
          <ConditionStartValue>0</ConditionStartValue>
          <ConditionStartValueType>0</ConditionStartValueType>
          <ConditionStartCompareToCondtion />
          <ConditionStartType>1</ConditionStartType>
        </CommandAction>
        <CommandAction>
          <Ordinal>3</Ordinal>
          <IndentLevel>1</IndentLevel>
          <ActionType>PressKey</ActionType>
          <Duration>1.5</Duration>
          <Delay>0</Delay>
          <KeyCodes>
            <unsignedShort>82</unsignedShort>
          </KeyCodes>
          <Context />
          <X>0</X>
          <Y>0</Y>
          <Z>0</Z>
          <ConditionPairing>0</ConditionPairing>
          <ConditionGroup>0</ConditionGroup>
        </CommandAction>
        <CommandAction>
          <Ordinal>4</Ordinal>
          <IndentLevel>0</IndentLevel>
          <ActionType>ConditionEnd</ActionType>
          <Duration>0</Duration>
          <Delay>0</Delay>
          <KeyCodes />
          <X>0</X>
          <Y>0</Y>
          <Z>0</Z>
          <ConditionPairing>0</ConditionPairing>
          <ConditionGroup>1</ConditionGroup>
        </CommandAction>
      </ActionSequence>
    </Command>
  </Commands>
</Profile>
"""


class XmlConditionalFixtureTest(unittest.TestCase):
    """Ground-truth-shaped inline XML: Text 'Ends With' Begin/ElseIf/End block (build spec
    WP-B #3). Exercises the XML-input rebind: ConditionStartType is the type carrier (not
    ConditionStartValueType, vestigial); ConditionStartValue is the SmallInt/Bool right value
    (not leftOperand); operator/valueType are integer codes resolved to names via the
    dictionary, not read as literal name text; codes 19/63/29/20 resolve via xml_action_type."""

    def setUp(self):
        self.prof = vap2.decode_bytes(XML_CONDITIONAL_FIXTURE.encode("utf-8"), DICT)
        self.actions = self.prof["commands"][0]["actions"]

    def test_action_type_codes_resolve(self):
        codes = [a["actionType"]["code"] for a in self.actions]
        self.assertEqual(codes, [19, 0, 63, 0, 20])
        names = [a["actionType"]["name"] for a in self.actions]
        self.assertEqual(names, ["BeginCondition", "PressKey", "ElseIf", "PressKey", "EndCondition"])

    def test_derived_indent(self):
        self.assertEqual([a["indentLevel"] for a in self.actions], [0, 1, 0, 1, 0])

    def test_begin_condition_fields(self):
        cond = self.actions[0]["condition"]
        self.assertEqual(cond["valueType"], {"code": 1, "name": "Text"})
        self.assertEqual(cond["operator"], {"code": 4, "name": "Ends With"})
        self.assertEqual(cond["leftOperand"], "{LASTSPOKENCMD}")
        self.assertEqual(cond["value"], "out")
        self.assertEqual(cond["pairing"], 2)
        self.assertEqual(cond["blockOrdinal"], 1)

    def test_elseif_condition_fields(self):
        cond = self.actions[2]["condition"]
        self.assertEqual(cond["valueType"], {"code": 1, "name": "Text"})
        self.assertEqual(cond["operator"], {"code": 4, "name": "Ends With"})
        self.assertEqual(cond["leftOperand"], "{LASTSPOKENCMD}")
        self.assertEqual(cond["value"], "in")
        self.assertEqual(cond["pairing"], 4)
        self.assertEqual(cond["blockOrdinal"], 1)

    def test_body_and_end_carry_no_condition(self):
        # Body actions: neither key. End: no condition, but the binary path's block record.
        self.assertNotIn("condition", self.actions[1])
        self.assertNotIn("condition", self.actions[3])
        self.assertNotIn("condition", self.actions[4])
        self.assertNotIn("block", self.actions[1])
        self.assertNotIn("block", self.actions[3])
        self.assertEqual(self.actions[4]["block"], {"pairing": 0})


# Else branch + valueless operator + present-but-empty Context2, per ground-truth sample 2d
# (Else carries no ConditionStartNameFrom) and the binary path's valueless-value suppression.
XML_ELSE_FIXTURE = """<?xml version="1.0" encoding="utf-8"?>
<Profile xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:xsd="http://www.w3.org/2001/XMLSchema">
  <Id>b8e1c2d3-0000-4000-8000-000000000001</Id>
  <Name>XML Else Fixture</Name>
  <Commands>
    <Command>
      <Id>b8e1c2d3-0000-4000-8000-000000000002</Id>
      <CommandString>branch test</CommandString>
      <ActionSequence>
        <CommandAction>
          <Ordinal>0</Ordinal>
          <ActionType>ConditionStart</ActionType>
          <Duration>0</Duration>
          <KeyCodes />
          <Z>1</Z>
          <ConditionPairing>1</ConditionPairing>
          <ConditionGroup>1</ConditionGroup>
          <ConditionStartNameFrom>{TXT:probe}</ConditionStartNameFrom>
          <ConditionStartOperator>8</ConditionStartOperator>
          <ConditionStartValue>0</ConditionStartValue>
          <ConditionStartValueType>0</ConditionStartValueType>
          <ConditionStartCompareToCondtion />
          <ConditionStartType>1</ConditionStartType>
        </CommandAction>
        <CommandAction>
          <Ordinal>1</Ordinal>
          <ActionType>ConditionElseIf</ActionType>
          <Duration>0</Duration>
          <KeyCodes />
          <Context2 xml:space="preserve"></Context2>
          <Z>1</Z>
          <ConditionPairing>2</ConditionPairing>
          <ConditionGroup>1</ConditionGroup>
          <ConditionStartNameFrom>{TXT:probe}</ConditionStartNameFrom>
          <ConditionStartOperator>0</ConditionStartOperator>
          <ConditionStartValue>0</ConditionStartValue>
          <ConditionStartValueType>0</ConditionStartValueType>
          <ConditionStartCompareToCondtion />
          <ConditionStartType>1</ConditionStartType>
        </CommandAction>
        <CommandAction>
          <Ordinal>2</Ordinal>
          <ActionType>ConditionElse</ActionType>
          <Duration>0</Duration>
          <KeyCodes />
          <Z>0</Z>
          <ConditionPairing>3</ConditionPairing>
          <ConditionGroup>1</ConditionGroup>
          <ConditionStartOperator>0</ConditionStartOperator>
          <ConditionStartValue>0</ConditionStartValue>
          <ConditionStartValueType>0</ConditionStartValueType>
          <ConditionStartType>0</ConditionStartType>
        </CommandAction>
        <CommandAction>
          <Ordinal>3</Ordinal>
          <ActionType>ConditionEnd</ActionType>
          <Duration>0</Duration>
          <KeyCodes />
          <Z>0</Z>
          <ConditionPairing>0</ConditionPairing>
          <ConditionGroup>1</ConditionGroup>
          <ConditionStartOperator>0</ConditionStartOperator>
          <ConditionStartValue>0</ConditionStartValue>
          <ConditionStartValueType>0</ConditionStartValueType>
          <ConditionStartType>0</ConditionStartType>
        </CommandAction>
      </ActionSequence>
    </Command>
  </Commands>
</Profile>
"""


class XmlElseAndValuelessTest(unittest.TestCase):
    """Shape parity with the binary path on the three verification findings: Else/End carry
    the block record {pairing}, present-but-empty Context2 binds as "" not None, and
    valueless Text operators (Has Been Set) omit the value key entirely."""

    def setUp(self):
        self.prof = vap2.decode_bytes(XML_ELSE_FIXTURE.encode("utf-8"), DICT)
        self.actions = self.prof["commands"][0]["actions"]

    def test_valueless_operator_omits_value_key(self):
        cond = self.actions[0]["condition"]
        self.assertEqual(cond["operator"], {"code": 8, "name": "Has Been Set"})
        self.assertNotIn("value", cond)

    def test_empty_string_value_binds_as_empty_not_none(self):
        cond = self.actions[1]["condition"]
        self.assertEqual(cond["operator"], {"code": 0, "name": "Equals"})
        self.assertEqual(cond["value"], "")

    def test_else_and_end_carry_block_record(self):
        self.assertEqual(self.actions[2]["block"], {"pairing": 3})
        self.assertEqual(self.actions[3]["block"], {"pairing": 0})
        self.assertNotIn("condition", self.actions[2])
        self.assertNotIn("condition", self.actions[3])


# WriteToLog from ground-truth sample 4.8 (Antaniserse/VAExtensions, verbatim fields) plus a
# present-but-empty Context variant; DecimalSet from the INFERRED template — target in
# ConditionSetName, value in DecimalContext1 by IntSet analogy, NO public sample exists
# (dictionary 0.4.0 marks the carrier plausible pending the VA import probe).
XML_SET_WRITE_FIXTURE = """<?xml version="1.0" encoding="utf-8"?>
<Profile xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:xsd="http://www.w3.org/2001/XMLSchema">
  <Id>c9f2d4e5-0000-4000-8000-000000000001</Id>
  <Name>XML Set Write Fixture</Name>
  <Commands>
    <Command>
      <Id>c9f2d4e5-0000-4000-8000-000000000002</Id>
      <CommandString>set and write</CommandString>
      <ActionSequence>
        <CommandAction>
          <Ordinal>0</Ordinal>
          <ActionType>WriteToLog</ActionType>
          <Duration>0</Duration>
          <Delay>0</Delay>
          <KeyCodes />
          <Context>{TXT:VxResult}</Context>
          <X>3</X>
          <Y>0</Y>
          <Z>0</Z>
          <InputMode>0</InputMode>
          <ConditionPairing>0</ConditionPairing>
          <ConditionGroup>0</ConditionGroup>
          <DecimalContext1>0</DecimalContext1>
        </CommandAction>
        <CommandAction>
          <Ordinal>1</Ordinal>
          <ActionType>WriteToLog</ActionType>
          <Duration>0</Duration>
          <Delay>0</Delay>
          <KeyCodes />
          <Context></Context>
          <X>0</X>
          <Y>0</Y>
          <Z>0</Z>
          <InputMode>0</InputMode>
          <ConditionPairing>0</ConditionPairing>
          <ConditionGroup>0</ConditionGroup>
          <DecimalContext1>0</DecimalContext1>
        </CommandAction>
        <CommandAction>
          <Ordinal>2</Ordinal>
          <ActionType>DecimalSet</ActionType>
          <Duration>0</Duration>
          <Delay>0</Delay>
          <KeyCodes />
          <X>0</X>
          <Y>0</Y>
          <Z>0</Z>
          <InputMode>0</InputMode>
          <ConditionSetName xml:space="preserve">bbq</ConditionSetName>
          <ConditionSetCondition />
          <ConditionPairing>0</ConditionPairing>
          <ConditionGroup>0</ConditionGroup>
          <DecimalContext1>2.25</DecimalContext1>
        </CommandAction>
      </ActionSequence>
    </Command>
  </Commands>
</Profile>
"""


class XmlSetWriteTest(unittest.TestCase):
    """Wave-2 payload bindings: WriteToLog (23) text←Context with the present-empty vs
    absent distinction, DecimalSet (38, INFERRED carrier) targetVariable←ConditionSetName /
    value←DecimalContext1 in string form — record keys match the binary path exactly."""

    def setUp(self):
        self.prof = vap2.decode_bytes(XML_SET_WRITE_FIXTURE.encode("utf-8"), DICT)
        self.actions = self.prof["commands"][0]["actions"]

    def test_writetolog_code_and_text(self):
        a = self.actions[0]
        self.assertEqual(a["actionType"], {"code": 23, "name": "Write"})
        self.assertEqual(a["text"], "{TXT:VxResult}")
        self.assertNotIn("context", a)  # rebound as text, no duplicate generic key

    def test_writetolog_empty_context_binds_empty_string(self):
        self.assertEqual(self.actions[1]["text"], "")

    def test_decimalset_code_and_bindings(self):
        a = self.actions[2]
        self.assertEqual(a["actionType"], {"code": 38, "name": "SetDecimal"})
        self.assertEqual(a["targetVariable"], "bbq")
        self.assertEqual(a["value"], "2.25")


# Row-1 payload bindings on the XML path (build spec WP-B / plan W2.5): Say volume/rate,
# MouseAction context-gated fields, Pause duration, Launch Context/Context2/Context3, and
# the presence rules the binary path enforces (duration key per family, keyCodes always on
# key actions, truthiness gates on clickDuration/scroll_clicks). Carriers per dictionary
# 0.4.1 xml notes and the generator's ground-truth templates.
XML_ROW1_PAYLOAD_FIXTURE = """<?xml version="1.0" encoding="utf-8"?>
<Profile xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:xsd="http://www.w3.org/2001/XMLSchema">
  <Id>a1b2c3d4-0000-4000-8000-000000000001</Id>
  <Name>XML Row1 Payload Fixture</Name>
  <Commands>
    <Command>
      <Id>a1b2c3d4-0000-4000-8000-000000000002</Id>
      <CommandString>row one sweep</CommandString>
      <ActionSequence>
        <CommandAction>
          <Ordinal>0</Ordinal>
          <ActionType>Say</ActionType>
          <Duration>0</Duration>
          <Delay>0</Delay>
          <KeyCodes />
          <Context>say-marker</Context>
          <X>43</X>
          <Y>7</Y>
          <Z>0</Z>
          <ConditionPairing>0</ConditionPairing>
          <ConditionGroup>0</ConditionGroup>
        </CommandAction>
        <CommandAction>
          <Ordinal>1</Ordinal>
          <ActionType>MouseAction</ActionType>
          <Duration>0.1</Duration>
          <Delay>0</Delay>
          <KeyCodes />
          <Context>LC</Context>
          <X>0</X>
          <Y>0</Y>
          <Z>0</Z>
          <ConditionPairing>0</ConditionPairing>
          <ConditionGroup>0</ConditionGroup>
        </CommandAction>
        <CommandAction>
          <Ordinal>2</Ordinal>
          <ActionType>MouseAction</ActionType>
          <Duration>0</Duration>
          <Delay>0</Delay>
          <KeyCodes />
          <Context>RC</Context>
          <X>0</X>
          <Y>0</Y>
          <Z>0</Z>
          <ConditionPairing>0</ConditionPairing>
          <ConditionGroup>0</ConditionGroup>
        </CommandAction>
        <CommandAction>
          <Ordinal>3</Ordinal>
          <ActionType>MouseAction</ActionType>
          <Duration>5</Duration>
          <Delay>0</Delay>
          <KeyCodes />
          <Context>SF</Context>
          <X>5</X>
          <Y>0</Y>
          <Z>0</Z>
          <ConditionPairing>0</ConditionPairing>
          <ConditionGroup>0</ConditionGroup>
        </CommandAction>
        <CommandAction>
          <Ordinal>4</Ordinal>
          <ActionType>MouseAction</ActionType>
          <Duration>0</Duration>
          <Delay>0</Delay>
          <KeyCodes />
          <Context>Move</Context>
          <X>333</X>
          <Y>444</Y>
          <Z>0</Z>
          <ConditionPairing>0</ConditionPairing>
          <ConditionGroup>0</ConditionGroup>
        </CommandAction>
        <CommandAction>
          <Ordinal>5</Ordinal>
          <ActionType>Pause</ActionType>
          <Duration>1.125</Duration>
          <Delay>0</Delay>
          <KeyCodes />
          <Context />
          <X>0</X>
          <Y>0</Y>
          <Z>0</Z>
          <ConditionPairing>0</ConditionPairing>
          <ConditionGroup>0</ConditionGroup>
        </CommandAction>
        <CommandAction>
          <Ordinal>6</Ordinal>
          <ActionType>Pause</ActionType>
          <Duration>0</Duration>
          <Delay>0</Delay>
          <KeyCodes />
          <Context />
          <X>0</X>
          <Y>0</Y>
          <Z>0</Z>
          <ConditionPairing>0</ConditionPairing>
          <ConditionGroup>0</ConditionGroup>
        </CommandAction>
        <CommandAction>
          <Ordinal>7</Ordinal>
          <ActionType>Launch</ActionType>
          <Duration>0</Duration>
          <Delay>0</Delay>
          <KeyCodes />
          <Context>C:\\probe\\launch-test.exe</Context>
          <Context2>--a1 --a2</Context2>
          <Context3>C:\\probe\\wd</Context3>
          <X>0</X>
          <Y>0</Y>
          <Z>0</Z>
          <ConditionPairing>0</ConditionPairing>
          <ConditionGroup>0</ConditionGroup>
        </CommandAction>
        <CommandAction>
          <Ordinal>8</Ordinal>
          <ActionType>Launch</ActionType>
          <Duration>0</Duration>
          <Delay>0</Delay>
          <KeyCodes />
          <Context>C:\\probe\\bare.exe</Context>
          <X>0</X>
          <Y>0</Y>
          <Z>0</Z>
          <ConditionPairing>0</ConditionPairing>
          <ConditionGroup>0</ConditionGroup>
        </CommandAction>
        <CommandAction>
          <Ordinal>9</Ordinal>
          <ActionType>KeyDown</ActionType>
          <Duration>0</Duration>
          <Delay>0</Delay>
          <KeyCodes>
            <unsignedShort>162</unsignedShort>
          </KeyCodes>
          <Context />
          <X>0</X>
          <Y>0</Y>
          <Z>0</Z>
          <ConditionPairing>0</ConditionPairing>
          <ConditionGroup>0</ConditionGroup>
        </CommandAction>
        <CommandAction>
          <Ordinal>10</Ordinal>
          <ActionType>PressKey</ActionType>
          <Duration>0</Duration>
          <Delay>0</Delay>
          <KeyCodes>
            <unsignedShort>67</unsignedShort>
          </KeyCodes>
          <Context />
          <X>0</X>
          <Y>0</Y>
          <Z>0</Z>
          <ConditionPairing>0</ConditionPairing>
          <ConditionGroup>0</ConditionGroup>
        </CommandAction>
        <CommandAction>
          <Ordinal>11</Ordinal>
          <ActionType>WriteToLog</ActionType>
          <Duration>0</Duration>
          <Delay>0</Delay>
          <KeyCodes />
          <Context>log line</Context>
          <X>0</X>
          <Y>0</Y>
          <Z>0</Z>
          <ConditionPairing>0</ConditionPairing>
          <ConditionGroup>0</ConditionGroup>
        </CommandAction>
      </ActionSequence>
    </Command>
  </Commands>
</Profile>
"""


class XmlRow1PayloadTest(unittest.TestCase):
    """W2.5 parity closeout: every new XML binding carries the binary path's exact record
    keys, value types, and presence rules (actions.py is the contract)."""

    def setUp(self):
        self.prof = vap2.decode_bytes(XML_ROW1_PAYLOAD_FIXTURE.encode("utf-8"), DICT)
        self.actions = self.prof["commands"][0]["actions"]

    def test_say_bindings(self):
        a = self.actions[0]
        self.assertEqual(a["actionType"], {"code": 13, "name": "Say"})
        self.assertEqual(a["text"], "say-marker")
        self.assertEqual(a["volume"], 43)
        self.assertEqual(a["rate"], 7)
        # Binary _say assigns all five keys unconditionally; XML has no voice carrier.
        self.assertIn("voiceGuid", a)
        self.assertIn("voiceName", a)
        self.assertIsNone(a["voiceGuid"])
        self.assertIsNone(a["voiceName"])
        self.assertNotIn("context", a)
        self.assertNotIn("duration", a)

    def test_mouse_click_duration(self):
        a = self.actions[1]
        self.assertEqual(a["contextCode"], "LC")
        self.assertEqual(a["action"], "left_click")
        self.assertEqual(a["clickDuration"], 0.1)
        self.assertNotIn("scroll_clicks", a)
        self.assertNotIn("duration", a)
        self.assertNotIn("context", a)

    def test_mouse_zero_duration_omits_key(self):
        # Binary _mouse gates clickDuration on truthiness — 0.0 emits no key.
        a = self.actions[2]
        self.assertEqual(a["contextCode"], "RC")
        self.assertNotIn("clickDuration", a)
        self.assertNotIn("scroll_clicks", a)
        self.assertNotIn("duration", a)

    def test_mouse_scroll_clicks(self):
        a = self.actions[3]
        self.assertEqual(a["contextCode"], "SF")
        self.assertEqual(a["action"], "scroll_up")
        self.assertEqual(a["scroll_clicks"], 5.0)
        self.assertNotIn("clickDuration", a)
        self.assertNotIn("duration", a)

    def test_mouse_move_xy(self):
        a = self.actions[4]
        self.assertEqual(a["contextCode"], "Move")
        self.assertEqual(a["action"], "cursor_move")
        self.assertEqual((a["x"], a["y"]), (333, 444))
        self.assertNotIn("clickDuration", a)
        self.assertNotIn("scroll_clicks", a)

    def test_pause_duration(self):
        a = self.actions[5]
        self.assertEqual(a["actionType"], {"code": 2, "name": "Pause"})
        self.assertEqual(a["duration"], 1.125)
        self.assertNotIn("context", a)

    def test_pause_zero_duration_key_present(self):
        # Binary _pause: `_opt_double or 0.0` — the key is ALWAYS present on Pause.
        a = self.actions[6]
        self.assertEqual(a["duration"], 0.0)

    def test_launch_bindings(self):
        a = self.actions[7]
        self.assertEqual(a["actionType"], {"code": 3, "name": "Launch"})
        self.assertEqual(a["executablePath"], "C:\\probe\\launch-test.exe")
        self.assertEqual(a["arguments"], "--a1 --a2")
        self.assertEqual(a["workingDirectory"], "C:\\probe\\wd")
        self.assertNotIn("context", a)
        self.assertNotIn("duration", a)

    def test_launch_absent_fields_omitted(self):
        # Binary SIMPLE_STRING_FIELDS binds only present slots — missing Context2/3
        # elements must omit the keys, not bind None.
        a = self.actions[8]
        self.assertEqual(a["executablePath"], "C:\\probe\\bare.exe")
        self.assertNotIn("arguments", a)
        self.assertNotIn("workingDirectory", a)

    def test_keydown_has_no_duration_key(self):
        # Binary _keys_no_duration: KeyDown/Up/Toggle records never carry duration.
        a = self.actions[9]
        self.assertEqual(a["actionType"], {"code": 8, "name": "KeyDown"})
        self.assertEqual(a["keyCodes"], [{"vk": 162, "name": "lctrl"}])
        self.assertNotIn("duration", a)

    def test_presskey_zero_duration_key_present(self):
        # Binary _keys: duration ALWAYS present on PressKey, 0.0 included.
        a = self.actions[10]
        self.assertEqual(a["duration"], 0.0)
        self.assertEqual(a["keyCodes"], [{"vk": 67, "name": "c"}])

    def test_writetolog_has_no_duration_key(self):
        a = self.actions[11]
        self.assertEqual(a["text"], "log line")
        self.assertNotIn("duration", a)


class Cs2BinaryXmlParityTest(unittest.TestCase):
    """W2.5 gate: binary decode of the CS2 reference profile vs XML decode of the profile
    the CURRENT generator emits from cities_skylines_2_conditional.json — field-identical
    action records for every row-1 type present, matched per command phrase. GUIDs and
    profile/command-level metadata (offsets, category provenance) are excluded; the action
    record is the contract."""

    BINARY = "Cities Skylines II-Profile.vap"
    SOURCE_JSON = os.path.join(ROOT, "cities_skylines_2_conditional.json")
    GENERATOR = os.path.join(ROOT, "skills", "voiceattack-generator", "scripts",
                             "vap_generator.py")

    # Provenance keys, per source: binary carries offset/head/guid + a confidence tag,
    # XML carries source. Neither is action payload.
    _STRIP = {"offset", "head", "guid", "source"}

    @classmethod
    def _normalize(cls, action):
        out = {k: v for k, v in action.items() if k not in cls._STRIP}
        at = dict(out["actionType"])
        at.pop("confidence", None)
        out["actionType"] = at
        return out

    def test_row1_field_parity(self):
        require(self.BINARY)
        if not (os.path.exists(self.SOURCE_JSON) and os.path.exists(self.GENERATOR)):
            self.skipTest("generator or cities_skylines_2_conditional.json missing")
        import subprocess
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            out_vap = os.path.join(tmp, "cs2_generated.vap")
            proc = subprocess.run(
                [sys.executable, self.GENERATOR, self.SOURCE_JSON, out_vap],
                capture_output=True, text=True)
            self.assertEqual(proc.returncode, 0, proc.stderr or proc.stdout)
            xml_prof = vap2.decode_file(out_vap, DICT)
        bin_prof = decode(self.BINARY)

        bin_cmds = {c["phrase"]: c for c in bin_prof["commands"]}
        xml_cmds = {c["phrase"]: c for c in xml_prof["commands"]}
        common = sorted(set(bin_cmds) & set(xml_cmds))
        self.assertGreater(len(common), 0, "no phrase-matched commands — pair broken")

        covered = {}
        mismatches = []
        for phrase in common:
            b_acts = [self._normalize(a) for a in bin_cmds[phrase]["actions"]]
            x_acts = [self._normalize(a) for a in xml_cmds[phrase]["actions"]]
            self.assertEqual(len(b_acts), len(x_acts), "action count differs on %r" % phrase)
            for b, x in zip(b_acts, x_acts):
                name = b["actionType"]["name"]
                covered[name] = covered.get(name, 0) + 1
                if b != x:
                    mismatches.append((phrase, b["index"], name, b, x))
        sys.stderr.write(
            "\n[CS2 binary-vs-XML parity] commands=%d actions-per-type=%s mismatches=%d\n"
            % (len(common), sorted(covered.items()), len(mismatches)))
        self.assertEqual(mismatches, [], "field mismatches: %s" % mismatches[:3])
        # The pair must actually exercise the conditional row-1 core, or the gate is hollow.
        for must in ("PressKey", "BeginCondition", "ElseIf", "EndCondition"):
            self.assertIn(must, covered, "CS2 pair no longer exercises %s" % must)


class AuditGateTest(unittest.TestCase):
    """Round-trip contract: dictionary_tools audit must report zero orphans against V2."""

    def test_names_audit_zero_orphans(self):
        import importlib.util
        tools_path = os.path.join(ROOT, "schema", "dictionary_tools.py")
        gen_path = os.path.join(ROOT, "skills", "voiceattack-generator", "scripts", "vap_generator.py")
        if not (os.path.exists(tools_path) and os.path.exists(gen_path)):
            self.skipTest("audit tooling or generator missing")
        spec = importlib.util.spec_from_file_location("dictionary_tools", tools_path)
        tools = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(tools)
        d = tools.load_dict()
        decoder_mod = tools.load_tool_module(__import__("pathlib").Path(
            os.path.join(SCRIPTS, "vap2", "names.py")))
        gen_mod = tools.load_tool_module(__import__("pathlib").Path(gen_path))
        with open(gen_path) as f:
            gen_src = f.read()
        report = tools.audit(d, decoder_mod, gen_mod, gen_src)
        self.assertEqual(report["fail_count"], 0, report)


if __name__ == "__main__":
    unittest.main(verbosity=2)
