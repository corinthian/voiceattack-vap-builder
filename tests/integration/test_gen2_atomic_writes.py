"""Atomic output write + encode_file self-clobber guard (SECURITY_REVIEW finding 5).

encode_file() has no prior callers or tests anywhere in the repo (confirmed by grep
before writing these) — this module is its first executable contract. Modeled on the
structure of test_gen2_equivalence.py, the closest existing pattern, since there is no
direct encode_file precedent to crib from.

Run:  python3 -m unittest discover -s tests/integration -t . -v
"""

import os
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "skills", "voiceattack-decoder", "scripts"))
sys.path.insert(0, os.path.join(ROOT, "skills", "voiceattack-generator", "scripts"))

from gen2 import encode_file, names  # noqa: E402
from gen2.emit_profile import EmitError  # noqa: E402
from gen2.fsout import write_text_atomic  # noqa: E402

DICT = names.load()

SIMPLE_MODEL = {"profile": {"id": None, "name": "AtomicWrites"},
                "commands": [{"phrase": "atomic test", "category": {"value": "t"},
                              "actions": [
                                  {"actionType": {"code": 21, "name": "SetText"},
                                   "targetVariable": "x", "value": "y"}]}]}


def write_schema_json(path):
    import json
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"schema_version": 2, **SIMPLE_MODEL}, f)


class EncodeFileSymlinkTest(unittest.TestCase):
    """A pre-existing symlink at the output path must not redirect the write to the
    victim file it points at; os.replace() breaks the link and replaces it in place."""

    def test_symlink_output_replaced_not_followed(self):
        with tempfile.TemporaryDirectory() as td:
            inp = os.path.join(td, "in.json")
            write_schema_json(inp)

            victim = os.path.join(td, "victim.vap")
            with open(victim, "w", encoding="utf-8") as f:
                f.write("VICTIM CONTENT — must not be touched")

            out = os.path.join(td, "out.vap")
            os.symlink(victim, out)

            warnings = encode_file(inp, out, DICT)
            self.assertEqual(warnings, [])

            self.assertFalse(os.path.islink(out), "output path should no longer be a symlink")
            with open(out, encoding="utf-8") as f:
                out_content = f.read()
            self.assertIn("<?xml", out_content)

            with open(victim, encoding="utf-8") as f:
                victim_content = f.read()
            self.assertEqual(victim_content, "VICTIM CONTENT — must not be touched")


class WriteTextAtomicFailureTest(unittest.TestCase):
    """A failure after the temp file is created must leave the destination untouched
    and must not leave a stray temp file behind in the directory."""

    def test_failure_leaves_no_destination_and_no_stray_temp(self):
        with tempfile.TemporaryDirectory() as td:
            out = os.path.join(td, "out.vap")

            class Boom(Exception):
                pass

            orig_replace = os.replace

            def failing_replace(src, dst):
                raise Boom("simulated failure after temp creation")

            os.replace = failing_replace
            try:
                with self.assertRaises(Boom):
                    write_text_atomic(out, "content")
            finally:
                os.replace = orig_replace

            self.assertFalse(os.path.exists(out))
            leftover = [f for f in os.listdir(td) if f != "out.vap"]
            self.assertEqual(leftover, [], "no stray temp files should remain: %r" % leftover)


class EncodeFileSelfClobberTest(unittest.TestCase):
    """encode_file(x, x) is refused; the input file must survive intact."""

    def test_same_path_refused_input_intact(self):
        with tempfile.TemporaryDirectory() as td:
            path = os.path.join(td, "same.json")
            write_schema_json(path)
            with open(path, encoding="utf-8") as f:
                original = f.read()

            with self.assertRaises(EmitError):
                encode_file(path, path, DICT)

            with open(path, encoding="utf-8") as f:
                self.assertEqual(f.read(), original)

    def test_same_path_via_relative_and_absolute_refused(self):
        with tempfile.TemporaryDirectory() as td:
            path = os.path.join(td, "same2.json")
            write_schema_json(path)
            cwd = os.getcwd()
            try:
                os.chdir(td)
                with self.assertRaises(EmitError):
                    encode_file("same2.json", os.path.abspath("same2.json"), DICT)
            finally:
                os.chdir(cwd)


class EncodeFileNormalGenerationTest(unittest.TestCase):
    """Normal generation still round-trips cleanly (the existing fixpoint gate in
    test_fixpoint.py exercises this more deeply; this is a smoke check that encode_file
    itself, now routed through write_text_atomic, produces valid output)."""

    def test_normal_generation_round_trips(self):
        import vap2
        with tempfile.TemporaryDirectory() as td:
            inp = os.path.join(td, "in.json")
            write_schema_json(inp)
            out = os.path.join(td, "out.vap")

            warnings = encode_file(inp, out, DICT)
            self.assertEqual(warnings, [])
            self.assertTrue(os.path.exists(out))

            decoded = vap2.decode_file(out)
            self.assertEqual(decoded["commands"][0]["phrase"], "atomic test")


if __name__ == "__main__":
    unittest.main(verbosity=2)
