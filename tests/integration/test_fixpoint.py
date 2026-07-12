"""Fixpoint integration gate: decode(encode(decode(x))) == decode(x).

Repo-level home per the 2026-07-12 architecture ruling (Generator_Refactor_Plan §3):
the generator (gen2) is the top-tier component depending only on the dictionary; the
decoder (vap2) verifies its output from outside; the fixpoint test sits ABOVE both and
orchestrates the pair. Neither skill's own suite imports the other skill's code.

ACTIVE as of plan W3 (first blood) on exactly the three profiles gen2 can FULLY
represent: zoom-if-else, the Cities Skylines II VA re-export, and Zoom Zoom. Further
profiles graduate to this fixture set at W5 — do not add them early; presence of a
fixture is not passability.

The comparison dimensions are contractually frozen (VAP_Round_Trip_Contract.md, Fixpoint
section): canonical names, key codes, durations, action order, condition structure. Each
dimension is asserted EXPLICITLY and its compared items are COUNTED; a zero count on a
dimension the fixture contains fails the test — the R3 tripwire: a comparison that
passes because a dimension silently compared nothing is the exact failure mode this
guards against. A pass achieved by shrinking the compared subset is a stop-and-report,
not a pass.

Beyond the frozen dimensions, full normalized action records are compared, stripping
ONLY provenance (offset/head/guid/source + actionType.confidence — the same set the
decoder's binary-vs-XML parity test uses, no wider). A mismatch there is reported as a
DISTINCT failure so a frozen-dimension pass can never mask record drift; widening the
normalization to go green is a standing abort condition.

Run:  python3 -m unittest discover -s tests/integration -t . -v
"""

import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "skills", "voiceattack-decoder", "scripts"))
sys.path.insert(0, os.path.join(ROOT, "skills", "voiceattack-generator", "scripts"))

import vap2  # noqa: E402
from gen2 import names as gen2_names, schema_input  # noqa: E402
from gen2.emit_profile import emit  # noqa: E402

GEN2_DICT = gen2_names.load()

# The W3 fixture set — exactly these three (plan §5 W3; module docstring). Reference
# profiles are gitignored local assets, so every fixture is skip-if-missing.
FIXTURES = {
    "zoom-if-else": os.path.join(ROOT, "reference profiles", "zoom-if-else.vap"),
    "cs2-reexport": os.path.join(ROOT, "reference profiles",
                                 "Cities Skylines II-Profile.vap"),
    "zoom-zoom": os.path.join(ROOT, "output files", "Zoom Zoom.vap"),
}

# Provenance-only normalization (mirrors test_vap2's parity-test set — no wider).
_STRIP = {"offset", "head", "guid", "source"}
_DURATION_FIELDS = ("duration", "clickDuration", "scroll_clicks")
# The five contractually frozen dimensions. All three W3 fixtures contain all five
# (conditions included: Zoom Zoom carries two blocks, zoom-if-else and CS2 theirs),
# so every count must land nonzero on every fixture.
_DIMENSIONS = ("names", "keycodes", "durations", "order", "conditions")


def require(path):
    if not os.path.exists(path):
        raise unittest.SkipTest("missing local asset: %s" % os.path.basename(path))


def _normalize(action):
    out = {k: v for k, v in action.items() if k not in _STRIP}
    at = out.get("actionType")
    if isinstance(at, dict):
        out["actionType"] = {k: v for k, v in at.items() if k != "confidence"}
    return out


class FixpointTest(unittest.TestCase):
    """decode(encode(decode(x))) == decode(x) on the solid subset — the encoder's
    definition of done and a decoder-V2 regression gate (contract, Fixpoint section)."""

    maxDiff = None

    def assert_fixpoint(self, path):
        require(path)
        j1 = vap2.decode_file(path)
        model = schema_input.parse(j1)
        xml, warnings = emit(model, GEN2_DICT)
        # W3 gate: ZERO warnings — these fixtures are fully representable, so any
        # warning IS a refusal or a confidence regression, never noise.
        self.assertEqual(warnings, [], "encode must be warning- and refusal-free")
        j2 = vap2.decode_bytes(xml.encode("utf-8"))

        counts = {d: 0 for d in _DIMENSIONS}

        # Command level: order preserved, phrase lists equal (document order, which
        # also pairs any duplicate phrases positionally), category values equal.
        self.assertEqual([c["phrase"] for c in j1["commands"]],
                         [c["phrase"] for c in j2["commands"]],
                         "command order / phrase list")
        self.assertEqual([c["category"]["value"] for c in j1["commands"]],
                         [c["category"]["value"] for c in j2["commands"]],
                         "category values")

        for ci, (cmd1, cmd2) in enumerate(zip(j1["commands"], j2["commands"])):
            where = "command %d (%r)" % (ci, cmd1["phrase"])
            a1s, a2s = cmd1["actions"], cmd2["actions"]
            self.assertEqual(len(a1s), len(a2s), "%s: action count" % where)

            # Frozen dimensions: action order + canonical names (asserted together on
            # the ordered name sequence; each counted per action).
            names1 = [a.get("actionType", {}).get("name") for a in a1s]
            names2 = [a.get("actionType", {}).get("name") for a in a2s]
            self.assertEqual(names1, names2,
                             "%s: action order / canonical names" % where)
            counts["order"] += len(names1)
            counts["names"] += len(names1)

            for ai, (a1, a2) in enumerate(zip(a1s, a2s)):
                loc = "%s action %d (%s)" % (where, ai, names1[ai])

                # Frozen dimension: key codes.
                if "keyCodes" in a1 or "keyCodes" in a2:
                    vks1 = [k.get("vk") for k in a1.get("keyCodes", [])]
                    vks2 = [k.get("vk") for k in a2.get("keyCodes", [])]
                    self.assertEqual(vks1, vks2, "%s: key codes" % loc)
                    counts["keycodes"] += len(vks1)

                # Frozen dimension: durations (all three duration-family carriers,
                # compared on presence AND value — present-vs-absent is contract).
                for f in _DURATION_FIELDS:
                    if f in a1 or f in a2:
                        self.assertEqual(a1.get(f), a2.get(f), "%s: %s" % (loc, f))
                        counts["durations"] += 1

                # Frozen dimension: condition structure — compare records on
                # Begin/ElseIf and block records on Else/End, field by field. The
                # value is compared on presence AND content: the valueless-operator
                # suppression rule must survive the round trip.
                if "condition" in a1 or "condition" in a2:
                    c1, c2 = a1.get("condition"), a2.get("condition")
                    self.assertIsNotNone(c1, "%s: condition only in j2" % loc)
                    self.assertIsNotNone(c2, "%s: condition only in j1" % loc)
                    for label, get in (
                            ("valueType",
                             lambda c: (c.get("valueType") or {}).get("name")),
                            ("operator",
                             lambda c: (c.get("operator") or {}).get("name")),
                            ("leftOperand", lambda c: c.get("leftOperand")),
                            ("value", lambda c: ("value" in c, c.get("value"))),
                            ("pairing", lambda c: c.get("pairing")),
                            ("blockOrdinal", lambda c: c.get("blockOrdinal"))):
                        self.assertEqual(get(c1), get(c2),
                                         "%s: condition %s" % (loc, label))
                    counts["conditions"] += 1
                if "block" in a1 or "block" in a2:
                    self.assertEqual(a1.get("block"), a2.get("block"),
                                     "%s: block pairing" % loc)
                    counts["conditions"] += 1

                # Full-record parity beyond the frozen dimensions. NEVER widen the
                # normalization to make this pass — stop and report instead.
                f1, f2 = _normalize(a1), _normalize(a2)
                if f1 != f2:
                    fields = sorted(k for k in set(f1) | set(f2)
                                    if f1.get(k) != f2.get(k))
                    self.fail("fixpoint holds on frozen dimensions but full-record "
                              "parity fails on %r at %s (j1=%r j2=%r)"
                              % (fields, loc,
                                 {k: f1.get(k) for k in fields},
                                 {k: f2.get(k) for k in fields}))

        # R3 tripwire: every frozen dimension must have compared something on every
        # W3 fixture — a zero count means the comparison flattered itself.
        for dim in _DIMENSIONS:
            self.assertGreater(counts[dim], 0,
                               "dimension %r compared NOTHING on this fixture "
                               "(R3 tripwire)" % dim)
        return counts

    def test_fixpoint_zoom_if_else(self):
        self.assert_fixpoint(FIXTURES["zoom-if-else"])

    def test_fixpoint_cities_skylines_2_reexport(self):
        self.assert_fixpoint(FIXTURES["cs2-reexport"])

    def test_fixpoint_zoom_zoom(self):
        self.assert_fixpoint(FIXTURES["zoom-zoom"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
