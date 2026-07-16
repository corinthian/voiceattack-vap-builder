"""Tests for vap2.container bounded input/decompression.

Run:  python3 -m unittest discover -s skills/voiceattack-decoder/tests -v
  or:  python3 skills/voiceattack-decoder/tests/test_container.py
"""

import os
import sys
import tempfile
import unittest
import zlib

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
SCRIPTS = os.path.join(ROOT, "skills", "voiceattack-decoder", "scripts")
PROFILES = os.path.join(ROOT, "reference profiles")
sys.path.insert(0, SCRIPTS)

import vap2  # noqa: E402
import vap2.container as container  # noqa: E402


def raw_deflate(data):
    c = zlib.compressobj(9, zlib.DEFLATED, -15)
    return c.compress(data) + c.flush()


class DecompressBombTests(unittest.TestCase):
    def test_bomb_over_limit_raises(self):
        # ~80 MB of zeros compresses to a few KB but decompresses well past the cap.
        payload = raw_deflate(b"\x00" * (80 * 1024 * 1024))
        with self.assertRaises(container.ContainerError):
            container.decompress(payload)

    def test_under_limit_decompresses_fine(self):
        orig = container.MAX_DECOMPRESSED_BYTES
        try:
            container.MAX_DECOMPRESSED_BYTES = 1024
            payload = raw_deflate(b"x" * 512)
            out = container.decompress(payload)
            self.assertEqual(out, b"x" * 512)
        finally:
            container.MAX_DECOMPRESSED_BYTES = orig

    def test_truncated_stream_raises(self):
        payload = raw_deflate(b"hello world" * 100)
        truncated = payload[: len(payload) // 2]
        with self.assertRaises(container.ContainerError):
            container.decompress(truncated)


class LoadBoundsTests(unittest.TestCase):
    def test_oversized_file_raises(self):
        with tempfile.NamedTemporaryFile(suffix=".vap", delete=False) as f:
            f.write(b"<?xml version='1.0'?><Profile>")
            f.write(b"a" * (container.MAX_FILE_BYTES + 1))
            path = f.name
        try:
            with self.assertRaises(container.ContainerError):
                container.load(path)
        finally:
            os.unlink(path)


class ReferenceProfileRegressionTests(unittest.TestCase):
    def test_all_reference_profiles_still_decode(self):
        if not os.path.isdir(PROFILES):
            self.skipTest("no local reference profiles")
        vaps = [f for f in os.listdir(PROFILES) if f.endswith(".vap")]
        if not vaps:
            self.skipTest("no local reference profiles")
        for fname in sorted(vaps):
            with self.subTest(fname=fname):
                vap2.decode_file(os.path.join(PROFILES, fname))


if __name__ == "__main__":
    unittest.main()
