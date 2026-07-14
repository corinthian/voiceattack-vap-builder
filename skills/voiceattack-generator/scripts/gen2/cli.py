"""CLI for gen2 — the VoiceAttack .vap generator (2.1 line).

    python3 -m gen2 input.json [output.vap] [--no-idiom]

Input is EITHER the simple authoring format (hand-written: {"name", "commands":[...]})
OR normative schema-v1.1 JSON (a vap2 decode). The format is auto-detected: a document
carrying a "schema_version" key takes the schema door (enters the pipeline at stage two);
anything else is lowered from the simple format (key/action shorthand, _section markers,
overloaded-trigger idiom compilation). Output is an uncompressed XML .vap.

Default output is <input base>.vap; overwriting the input file is refused. Exit codes:
0 clean, 1 hard fail (no output file written), 2 output written with warnings (contract
§3 refusals are warnings, never silent).
"""

import argparse
import json
import os
import sys

from . import names
from . import lower as lower_mod
from . import schema_input
from .emit_profile import EmitError, emit
from .lower import LoweringError
from .schema_input import SchemaError


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="gen2",
        description="Emit a VoiceAttack .vap (XML) from the simple authoring format "
                    "or schema-v1.1 JSON.")
    parser.add_argument("input", help="simple-format JSON (hand-authored) or "
                                       "schema-JSON (vap2 decode output)")
    parser.add_argument("output", nargs="?", default=None,
                        help="output .vap path (default: <input base>.vap)")
    parser.add_argument("--no-idiom", action="store_true",
                        help="disable overloaded-trigger idiom lowering (simple format only)")
    args = parser.parse_args(argv)

    output = args.output
    if output is None:
        base, ext = os.path.splitext(args.input)
        output = (base if ext.lower() == ".json" else args.input) + ".vap"
    if os.path.abspath(output) == os.path.abspath(args.input):
        print("ERROR: Output file would overwrite input file: %s" % output, file=sys.stderr)
        return 1

    try:
        with open(args.input, "r", encoding="utf-8") as f:
            doc = json.load(f)
    except FileNotFoundError:
        print("ERROR: File not found: %s" % args.input, file=sys.stderr)
        return 1
    except (UnicodeDecodeError, json.JSONDecodeError) as e:
        print("ERROR: invalid JSON in %s: %s" % (args.input, e), file=sys.stderr)
        return 1

    dictionary = names.load()
    # Warnings/infos stream as they occur so everything accumulated before a hard-fail is
    # already printed when the ERROR line lands (W5 fix wave, finding 4).
    warn = lambda w: print("WARNING: %s" % w, file=sys.stderr)
    info = lambda m: print("INFO: %s" % m, file=sys.stderr)

    # Format auto-detect: a schema_version key marks a decoded schema-JSON document; it
    # enters at stage two. Everything else is the simple authoring format and is lowered.
    schema_door = isinstance(doc, dict) and "schema_version" in doc
    lower_warnings = []
    try:
        if schema_door:
            model = schema_input.parse(doc)
        else:
            model, _infos, lower_warnings = lower_mod.lower_profile(
                doc, dictionary, no_idiom=args.no_idiom, info=info, warn=warn)
    except (SchemaError, LoweringError) as e:
        print("ERROR: %s" % e, file=sys.stderr)
        return 1

    try:
        xml, emit_warnings = emit(model, dictionary, warn=warn)
    except EmitError as e:
        print("ERROR: %s" % e, file=sys.stderr)
        return 1

    with open(output, "w", encoding="utf-8") as f:
        f.write(xml)

    print("Generated: %s (%s door)" % (output, "schema" if schema_door else "simple"))
    print("Commands: %d" % len(model["commands"]))
    total_warnings = len(lower_warnings) + len(emit_warnings)
    if total_warnings:
        print("Warnings: %d" % total_warnings)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
