"""Thin CLI for gen2 (mirrors vap2's invocation shape).

    python3 -m gen2 input_schema.json [output.vap]

Input is normative schema-v1.1 JSON (a vap2 decode); output is an uncompressed XML .vap.
Default output is <input base>.vap; writing over the input file is refused. Exit codes
follow vap_generator.py: 0 clean, 1 hard fail (no output file written), 2 output written
with warnings (contract §3 refusals are warnings, never silent).
"""

import argparse
import json
import os
import sys

from . import names
from .emit_profile import EmitError, emit
from .schema_input import SchemaError, load


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="gen2", description="Emit a VoiceAttack .vap (XML) from schema-v1.1 JSON.")
    parser.add_argument("input", help="path to a schema-JSON file (vap2 decode output)")
    parser.add_argument("output", nargs="?", default=None,
                        help="output .vap path (default: <input base>.vap)")
    args = parser.parse_args(argv)

    output = args.output
    if output is None:
        base, ext = os.path.splitext(args.input)
        output = (base if ext.lower() == ".json" else args.input) + ".vap"
    if os.path.abspath(output) == os.path.abspath(args.input):
        print("ERROR: Output file would overwrite input file: %s" % output, file=sys.stderr)
        return 1

    try:
        model = load(args.input)
    except FileNotFoundError:
        print("ERROR: File not found: %s" % args.input, file=sys.stderr)
        return 1
    except (SchemaError, json.JSONDecodeError) as e:
        print("ERROR: %s" % e, file=sys.stderr)
        return 1

    try:
        # Warnings stream as they occur so everything accumulated before a hard-fail
        # is already printed when the ERROR line lands (W5 fix wave, finding 4).
        xml, warnings = emit(model, names.load(),
                             warn=lambda w: print("WARNING: %s" % w, file=sys.stderr))
    except EmitError as e:
        print("ERROR: %s" % e, file=sys.stderr)
        return 1

    with open(output, "w", encoding="utf-8") as f:
        f.write(xml)

    print("Generated: %s" % output)
    print("Commands: %d" % len(model["commands"]))
    if warnings:
        print("Warnings: %d" % len(warnings))
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
