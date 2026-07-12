"""Fixpoint integration gate: decode(encode(decode(x))) == decode(x).

Repo-level home per the 2026-07-12 architecture ruling (Generator_Refactor_Plan §3):
the generator (gen2) is the top-tier component depending only on the dictionary; the
decoder (vap2) verifies its output from outside; the fixpoint test sits ABOVE both and
orchestrates the pair. Neither skill's own suite imports the other skill's code.

The comparison dimensions are contractually frozen (VAP_Round_Trip_Contract.md, Fixpoint
section): canonical names, key codes, durations, action order, condition structure. A
pass achieved by shrinking that subset is a stop-and-report, not a pass.

Relocated from skills/voiceattack-decoder/tests/test_vap2.py (FixpointStubTest), which
assumed a vap2.encoder home the ruling overrode. Activates at plan W3 for the profiles
gen2 can fully represent: zoom-if-else, Cities Skylines II re-export, Zoom Zoom.

Run:  python3 -m unittest discover -s tests/integration -t . -v
"""

import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "skills", "voiceattack-decoder", "scripts"))
sys.path.insert(0, os.path.join(ROOT, "skills", "voiceattack-generator", "scripts"))


class FixpointStubTest(unittest.TestCase):
    """Documents the gate; activates when the gen2 encoder package appears (plan W1),
    with real fixture comparisons landing at plan W3."""

    def test_fixpoint_placeholder(self):
        try:
            import gen2  # noqa: F401
        except Exception:
            self.skipTest("gen2 encoder not yet built (refactor plan W1) — fixpoint activates at W3")


if __name__ == "__main__":
    unittest.main(verbosity=2)
