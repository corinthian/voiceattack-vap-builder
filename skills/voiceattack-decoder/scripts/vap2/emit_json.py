"""Normative JSON output (output contract sec 5).

JSON is the lossless normative form and the future encoder's input. Emission is
deterministic: the profile dict is built in a fixed key order upstream and Python
preserves insertion order, so the same input yields byte-identical output (the W6
determinism oracle) WITHOUT alphabetic sort_keys, which would scramble the semantic
field order that makes the record authorable.
"""

import json


def to_json(profile, indent=2):
    return json.dumps(profile, indent=indent, ensure_ascii=False)
