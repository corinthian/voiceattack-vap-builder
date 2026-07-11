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


class FixpointStubTest(unittest.TestCase):
    """decode(encode(decode(x))) == decode(x) — the encoder's definition of done
    (round-trip contract). The encoder is out of V2 scope (plan §9); this stub documents
    the gate and activates when an encoder module appears."""

    def test_fixpoint_placeholder(self):
        try:
            import vap2.encoder  # noqa: F401
        except Exception:
            self.skipTest("encoder not yet built (plan §9 mirror refactor) — fixpoint deferred")


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
