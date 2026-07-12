"""Thin CLI for vap2 (preserves v1's invocation shape).

    python3 -m vap2 input.vap [output_base] [--stdout]

Default output writes <output_base>.json (or <input>_decoded.json) — never into the
input file's own directory unless output_base says so (output contract sec 5 / W5).
"""

import argparse
import os
import sys

from . import decode_file
from .container import ContainerError
from .emit_json import to_json
from .emit_xml import to_xml
from .xml_input import XmlInputError


def main(argv=None):
    parser = argparse.ArgumentParser(prog="vap2", description="Decode a VoiceAttack .vap to JSON.")
    parser.add_argument("input", help="path to a .vap file")
    parser.add_argument("output_base", nargs="?", default=None,
                        help="output base path; writes <base>.json (and <base>.xml with --xml)")
    parser.add_argument("--stdout", action="store_true", help="write to stdout instead of a file")
    parser.add_argument("--xml", action="store_true",
                        help="also emit the secondary gated XML view (prelim sec 8)")
    args = parser.parse_args(argv)

    try:
        profile = decode_file(args.input)
    except (ContainerError, XmlInputError) as e:
        print("vap2: %s" % e, file=sys.stderr)
        return 2
    except FileNotFoundError:
        print("vap2: no such file: %s" % args.input, file=sys.stderr)
        return 2

    text = to_json(profile)
    if args.stdout:
        print(to_xml(profile) if args.xml else text)
        return 0

    base = args.output_base or os.path.join(
        os.getcwd(), os.path.splitext(os.path.basename(args.input))[0] + "_decoded")
    json_path = base + ".json"
    with open(json_path, "w", encoding="utf-8") as f:
        f.write(text)
    print("wrote %s" % json_path)
    if args.xml:
        xml_path = base + ".xml"
        with open(xml_path, "w", encoding="utf-8") as f:
            f.write(to_xml(profile))
        print("wrote %s" % xml_path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
