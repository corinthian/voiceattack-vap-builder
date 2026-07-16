"""Atomic output writes for gen2.

Writing directly to the output path lets a pre-existing symlink at that path redirect
the write to an arbitrary file. write_text_atomic() writes to a temp file in the same
directory and os.replace()s it into place, so the destination is always either the old
content or the new content, never a followed symlink.
"""

import os
import tempfile


def write_text_atomic(path, text):
    """Write text to path atomically via temp-file-then-replace."""
    directory = os.path.dirname(os.path.abspath(path)) or "."
    tmp = tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", delete=False, dir=directory)
    try:
        tmp.write(text)
        tmp.close()
    except Exception:
        tmp.close()
        os.unlink(tmp.name)
        raise
    try:
        os.replace(tmp.name, path)
    except Exception:
        os.unlink(tmp.name)
        raise
