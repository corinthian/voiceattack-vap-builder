"""Dictionary identity gates: packaged-copy drift, and the audit's hollow-gate guard.

Round-trip contract line 38 permits a derived or shipped dictionary copy only "verified
identical by the audit tool". No such verification existed, and the measured consequence
was two shipped artifacts carrying a dictionary that had silently drifted from the
repo's under the SAME version string 0.5.0 — the packaged copy predated the 2026-08-14
f13-f24 addition, which shipped as a silent update by ruling. A version string
structurally cannot detect that. A content hash can.

The audit gates here close the second half: before this, the only checks on the LIVE v2
decoder's tables were the ones that could not fail. vap2/names.py swallows a failed
import-time load and leaves VK_CODES and CONTEXT_TO_GENERATOR empty; every
set-difference the audit anchors on those tables is then empty too, so a poisoned run
reported zero orphans and exit 0.

Run:  python3 -m unittest discover -s tests/integration -t . -v
"""

import glob
import importlib.util
import json
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile
import unittest
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))

DICT_NAME = "vap_capability_dictionary.json"
DICT_FILE = os.path.join(ROOT, "schema", DICT_NAME)
TOOLS_PATH = os.path.join(ROOT, "schema", "dictionary_tools.py")
DIST_DIR = os.path.join(ROOT, "dist")
VAP2_NAMES = os.path.join(ROOT, "skills", "voiceattack-decoder", "scripts", "vap2", "names.py")
V1_DECODER = os.path.join(ROOT, "skills", "voiceattack-decoder", "scripts", "vap_decoder.py")
V1_GENERATOR = os.path.join(ROOT, "skills", "voiceattack-generator", "scripts", "vap_generator.py")


def load_tools():
    spec = importlib.util.spec_from_file_location("dictionary_tools", TOOLS_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def write_drifted_dictionary(path):
    """A dictionary that LOADS cleanly but is not the repo's — one key removed. This is
    the shadow-copy shape: a set-difference against it finds no orphan (the decoder's
    names are a subset), so only an identity check can catch it."""
    with open(DICT_FILE, encoding="utf-8") as f:
        d = json.load(f)
    d["keys"] = [k for k in d["keys"] if k.get("canonical") != "f13"]
    with open(path, "w", encoding="utf-8") as f:
        json.dump(d, f, indent=2)
    return path


class PackagedCopyDriftTest(unittest.TestCase):
    """Test 5 — the drift gate. Every dictionary copy shipped under dist/ must be
    byte-identical to the repo's.

    Red against the deleted 2.1.0 artifacts (both carried sha256 fa9d783b... against the
    repo's 83bd1a1b...). It lands green-by-skip while dist/ is empty and becomes the
    packaging pipeline's live gate the moment artifacts reappear."""

    def test_every_packaged_dictionary_matches_the_repo(self):
        if not os.path.isdir(DIST_DIR):
            self.skipTest("no dist/ directory — artifacts are built by the packaging pipeline")
        archives = sorted(glob.glob(os.path.join(DIST_DIR, "*.zip")))
        if not archives:
            self.skipTest("dist/ holds no artifacts")

        checked = []
        td = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, td, True)
        for archive in archives:
            with zipfile.ZipFile(archive) as zf:
                for entry in zf.namelist():
                    if os.path.basename(entry) != DICT_NAME:
                        continue
                    extracted = os.path.join(
                        td, "%s__%s" % (os.path.basename(archive), os.path.basename(entry)))
                    with zf.open(entry) as src, open(extracted, "wb") as dst:
                        shutil.copyfileobj(src, dst)
                    # Route through the shipped gate itself, not a private hash here.
                    r = subprocess.run(
                        [sys.executable, "-B", TOOLS_PATH, "verify-copy", extracted],
                        capture_output=True, text=True)
                    self.assertEqual(
                        r.returncode, 0,
                        "%s!%s has drifted from the repo dictionary\n%s%s"
                        % (os.path.basename(archive), entry, r.stdout, r.stderr))
                    checked.append("%s!%s" % (os.path.basename(archive), entry))

        # A pass achieved by comparing nothing is not a pass. Say so and skip instead.
        if not checked:
            self.skipTest("no packaged dictionary copies found in %d archive(s)" % len(archives))
        sys.stderr.write("\n[packaged dictionary drift] verified %d copies: %s\n"
                         % (len(checked), checked))


class VerifyCopyTest(unittest.TestCase):
    """The verify-copy subcommand itself — the packaging pipeline's identity gate.
    PackagedCopyDriftTest skips while dist/ is empty, so this is where the gate's own
    behaviour is pinned."""

    def run_verify(self, candidate):
        return subprocess.run(
            [sys.executable, "-B", TOOLS_PATH, "verify-copy", candidate],
            capture_output=True, text=True)

    def test_identical_copy_passes(self):
        td = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, td, True)
        copy = os.path.join(td, DICT_NAME)
        shutil.copy(DICT_FILE, copy)
        r = self.run_verify(copy)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("byte-identical", r.stdout)

    def test_drifted_copy_fails(self):
        td = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, td, True)
        drifted = write_drifted_dictionary(os.path.join(td, DICT_NAME))
        r = self.run_verify(drifted)
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn("DRIFTED", r.stderr)

    def test_missing_candidate_fails_without_a_traceback(self):
        r = self.run_verify(os.path.join(tempfile.gettempdir(), "no-such-dictionary.json"))
        self.assertEqual(r.returncode, 1)
        self.assertNotIn("Traceback", r.stderr)


class HollowGateTest(unittest.TestCase):
    """Test 6 — the audit can now go red on the live decoder.

    ORDER MATTERS in every case: vap2/names.py reads VAP_DICTIONARY_PATH at EXEC time,
    so the module must be loaded INSIDE the patched environment. Loading it first and
    patching after would populate the tables from the real dictionary and pass for
    exactly the reason this test exists to catch.

    Case (d) of the plan — the two pre-existing decoder-suite audit tests keeping their
    fail_count == 0 with the env scrubbed — lives in that suite, at
    skills/voiceattack-decoder/tests/test_vap2.py::AuditGateTest."""

    def run_audit(self, dict_path_env):
        saved = os.environ.pop("VAP_DICTIONARY_PATH", None)
        if dict_path_env is not None:
            os.environ["VAP_DICTIONARY_PATH"] = dict_path_env
        try:
            tools = load_tools()
            live_decoder_mod = tools.load_tool_module(pathlib.Path(VAP2_NAMES))
            d = tools.load_dict()
            decoder_mod = tools.load_tool_module(pathlib.Path(V1_DECODER))
            generator_mod = tools.load_tool_module(pathlib.Path(V1_GENERATOR))
            with open(V1_GENERATOR, encoding="utf-8") as f:
                generator_src = f.read()
            return tools.audit(d, decoder_mod, generator_mod, generator_src,
                               live_decoder_mod=live_decoder_mod,
                               dict_path=str(tools.DICT_PATH))
        finally:
            os.environ.pop("VAP_DICTIONARY_PATH", None)
            if saved is not None:
                os.environ["VAP_DICTIONARY_PATH"] = saved

    def test_a_unreachable_dictionary_fails(self):
        """(a) Empty tables can no longer pass. This exact configuration reported
        'Total true orphans/mismatches: 0' and exit 0 before the fix."""
        report = self.run_audit(os.path.join(tempfile.gettempdir(), "nonexistent-nope.json"))
        self.assertGreater(report["fail_count"], 0, report)
        self.assertEqual(sorted(report["live_decoder"]["empty_tables"]),
                         ["CONTEXT_TO_GENERATOR", "VK_CODES"])
        self.assertIn("FAIL", report["live_decoder"]["identity"])

    def test_b_different_dictionary_fails_on_the_hash(self):
        """(b) A LOADED but different dictionary can no longer pass. The tables are
        non-empty here, so nothing but the identity check can catch it — which is the
        whole point: set-differencing vap2's tables against the dictionary they derive
        from is a tautology."""
        td = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, td, True)
        drifted = write_drifted_dictionary(os.path.join(td, DICT_NAME))
        report = self.run_audit(drifted)
        self.assertEqual(report["live_decoder"]["empty_tables"], [])
        self.assertIn("DIFFERENT dictionary", report["live_decoder"]["identity"])
        self.assertEqual(report["fail_count"], 1, report)

    def test_c_clean_run_stays_green(self):
        """(c) The gate must still pass when everything is right, or it is just noise."""
        report = self.run_audit(None)
        self.assertEqual(report["fail_count"], 0, report)
        self.assertEqual(report["live_decoder"]["empty_tables"], [])
        self.assertTrue(report["live_decoder"]["identity"].startswith("OK"),
                        report["live_decoder"]["identity"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
