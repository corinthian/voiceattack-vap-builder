"""gen2 — VoiceAttack profile encoder (Generator Refactor Plan, 2.1 line).

Consumes normative schema-v1.1 JSON (the decoder's frozen output contract,
skills/voiceattack-decoder/docs/V2_JSON_Schema.md) and emits a VoiceAttack-importable
XML .vap. Top-tier component per the 2026-07-12 architecture ruling: depends ONLY on
schema/vap_capability_dictionary.json + stdlib — never on decoder code. The decoder
verifies this package's output from outside (repo-level tests/integration/).

Public entry points: encode_file() below, or the module pieces (schema_input.load /
parse, emit_profile.emit, names.load).
"""

from . import names
from .emit_profile import EmitError, emit
from .lower import LoweringError, lower_profile
from .schema_input import SchemaError, load, parse


def encode_file(input_path, output_path, dictionary=None):
    """Schema-JSON file -> XML .vap file. Returns the warning list (contract §3
    refusals); raises SchemaError/EmitError on hard-fail defects, writing nothing."""
    model = load(input_path)
    xml, warnings = emit(model, dictionary or names.load())
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(xml)
    return warnings
