"""Dictionary path resolution, driven from OUTSIDE the repo tree.

Repo-level home per the 2026-07-12 architecture ruling: these gates exercise both
skills' CLIs and neither skill's own suite may import the other's code.

The defect these guard: both name loaders used to compute ONE path, four directories up
from the package, and open it. That resolves only while the package sits inside the
repo — so both shipped 2.1.0 artifacts were non-functional under their own layout,
which puts the dictionary at <package root>/schema/, two hops up.

Every case runs the real CLI as a subprocess with VAP_DICTIONARY_PATH SCRUBBED from the
child environment. Without the scrub a positive case passes for the wrong reason the
moment the var is set in the ambient shell.

Layout note: the fake install is nested TWO levels under the temp dir
(<tmp>/installed/pkg/) so the loader's first candidate — four hops up, the repo
position — lands at <tmp>/schema/, inside the test's own tree. The test therefore
controls what does and does not exist at BOTH candidate positions, instead of leaving
the first one pointed at the shared system temp root.

Run:  python3 -m unittest discover -s tests/integration -t . -v
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))

DICT_NAME = "vap_capability_dictionary.json"
DICT_FILE = os.path.join(ROOT, "schema", DICT_NAME)
GENERATOR_SKILL = os.path.join(ROOT, "skills", "voiceattack-generator")
DECODER_SKILL = os.path.join(ROOT, "skills", "voiceattack-decoder")

# f13 is vk 124 and was added to the dictionary on 2026-08-14. The stale copy the 2.1.0
# artifacts shipped does NOT carry it, so a profile that emits keycode 124 proves the
# CURRENT dictionary was found — not merely that some dictionary was.
FIXTURE_PROFILE = {
    "name": "Dictionary Resolution Probe",
    "commands": [
        {"trigger": "probe function thirteen", "key": "f13"},
        {"trigger": "probe alpha", "key": "a"},
    ],
}
F13_KEYCODE_XML = "<unsignedShort>124</unsignedShort>"


def child_env(**overrides):
    """A child environment with VAP_DICTIONARY_PATH removed, plus any overrides."""
    env = dict(os.environ)
    env.pop("VAP_DICTIONARY_PATH", None)
    env.update(overrides)
    return env


def install_package(tmpdir, skill_dir, with_dictionary):
    """Lay a skill out the way the dist artifacts do: <root>/scripts/<pkg>/, and
    optionally <root>/schema/<dictionary>. Returns (root, repo_position_candidate)."""
    root = os.path.join(tmpdir, "installed", "pkg")
    os.makedirs(root)
    shutil.copytree(os.path.join(skill_dir, "scripts"), os.path.join(root, "scripts"))
    if with_dictionary:
        os.makedirs(os.path.join(root, "schema"))
        shutil.copy(DICT_FILE, os.path.join(root, "schema", DICT_NAME))
    # What the loader's four-hop repo-position candidate resolves to from this layout.
    repo_candidate = os.path.join(tmpdir, "schema", DICT_NAME)
    return root, repo_candidate


def run_module(root, module, args, env):
    return subprocess.run(
        [sys.executable, "-B", "-m", module] + args,
        cwd=os.path.join(root, "scripts"), env=env,
        capture_output=True, text=True)


class GeneratorResolutionTest(unittest.TestCase):
    """gen2, installed outside the repo."""

    def setUp(self):
        self.td = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.td, True)
        self.input = os.path.join(self.td, "profile.json")
        with open(self.input, "w", encoding="utf-8") as f:
            json.dump(FIXTURE_PROFILE, f)
        self.output = os.path.join(self.td, "out.vap")

    def test_finds_the_in_package_dictionary(self):
        """Test 1 — positive. With the dist layout's <root>/schema/ copy present and no
        env var, gen2 emits cleanly from outside the repo."""
        root, _ = install_package(self.td, GENERATOR_SKILL, with_dictionary=True)
        r = run_module(root, "gen2", [self.input, self.output], child_env())
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue(os.path.exists(self.output), r.stderr)
        with open(self.output, encoding="utf-8") as f:
            xml = f.read()
        # Keycode 124 can only come from a dictionary carrying f13 — the current one.
        self.assertIn(F13_KEYCODE_XML, xml)

    def test_no_dictionary_anywhere_exits_1_naming_every_path(self):
        """Test 2 — negative. No schema/, no env var: a DESIGNED failure that names the
        escape hatch and every path tried, not a traceback."""
        root, repo_candidate = install_package(self.td, GENERATOR_SKILL,
                                               with_dictionary=False)
        r = run_module(root, "gen2", [self.input, self.output], child_env())
        self.assertEqual(r.returncode, 1, r.stderr)
        self.assertFalse(os.path.exists(self.output))
        self.assertNotIn("Traceback", r.stderr)
        self.assertIn("VAP_DICTIONARY_PATH", r.stderr)
        self.assertIn(repo_candidate, r.stderr)
        self.assertIn(os.path.join(root, "schema", DICT_NAME), r.stderr)

    def test_env_var_misdirection_does_not_fall_through(self):
        """Test 3 — a typo'd override must RAISE, never quietly resolve to a different
        dictionary. The in-package copy is present and must NOT rescue the run."""
        root, _ = install_package(self.td, GENERATOR_SKILL, with_dictionary=True)
        bogus = os.path.join(self.td, "typo", "nope.json")
        r = run_module(root, "gen2", [self.input, self.output],
                       child_env(VAP_DICTIONARY_PATH=bogus))
        self.assertEqual(r.returncode, 1, r.stderr)
        self.assertFalse(os.path.exists(self.output))
        self.assertIn(bogus, r.stderr)


class DecoderResolutionTest(unittest.TestCase):
    """Test 4 — vap2 mirrors 1 to 3.

    Every case passes a REAL .vap path. vap2 returns 2 for a missing input file too, so
    a nonexistent input would let the wrong failure masquerade as the dictionary one."""

    @classmethod
    def setUpClass(cls):
        cls.shared = tempfile.mkdtemp()
        # Build the .vap with the in-repo generator, where the dictionary resolves.
        src = os.path.join(cls.shared, "profile.json")
        with open(src, "w", encoding="utf-8") as f:
            json.dump(FIXTURE_PROFILE, f)
        cls.vap = os.path.join(cls.shared, "probe.vap")
        r = subprocess.run(
            [sys.executable, "-B", "-m", "gen2", src, cls.vap],
            cwd=os.path.join(GENERATOR_SKILL, "scripts"),
            capture_output=True, text=True)
        if r.returncode != 0 or not os.path.exists(cls.vap):
            raise AssertionError("could not build the decoder fixture .vap: %s" % r.stderr)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.shared, True)

    def setUp(self):
        self.td = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.td, True)
        self.out_base = os.path.join(self.td, "decoded")

    def test_finds_the_in_package_dictionary(self):
        root, _ = install_package(self.td, DECODER_SKILL, with_dictionary=True)
        r = run_module(root, "vap2", [self.vap, self.out_base], child_env())
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue(os.path.exists(self.out_base + ".json"), r.stderr)

    def test_no_dictionary_blames_the_dictionary_not_the_vap(self):
        """The wrong-file blame this closes: vap2 resolves its dictionary BEFORE it
        opens the input, so a missing dictionary used to surface as
        'vap2: no such file: <input.vap>' — pointing at a file that is right there."""
        root, repo_candidate = install_package(self.td, DECODER_SKILL,
                                               with_dictionary=False)
        r = run_module(root, "vap2", [self.vap, self.out_base], child_env())
        self.assertEqual(r.returncode, 2, r.stderr)
        self.assertFalse(os.path.exists(self.out_base + ".json"))
        self.assertNotIn("Traceback", r.stderr)
        self.assertIn("VAP_DICTIONARY_PATH", r.stderr)
        self.assertIn(repo_candidate, r.stderr)
        self.assertIn(os.path.join(root, "schema", DICT_NAME), r.stderr)
        # The input .vap exists and must not be blamed for the dictionary's absence.
        self.assertNotIn("no such file", r.stderr)

    def test_env_var_misdirection_does_not_fall_through(self):
        root, _ = install_package(self.td, DECODER_SKILL, with_dictionary=True)
        bogus = os.path.join(self.td, "typo", "nope.json")
        r = run_module(root, "vap2", [self.vap, self.out_base],
                       child_env(VAP_DICTIONARY_PATH=bogus))
        self.assertEqual(r.returncode, 2, r.stderr)
        self.assertFalse(os.path.exists(self.out_base + ".json"))
        self.assertIn(bogus, r.stderr)
        self.assertNotIn("no such file", r.stderr)


if __name__ == "__main__":
    unittest.main(verbosity=2)
