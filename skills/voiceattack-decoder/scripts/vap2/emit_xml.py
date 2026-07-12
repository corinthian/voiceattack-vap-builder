"""Secondary XML output, gated (prelim spec sec 8).

JSON is the normative, lossless form (emit_json). XML is retained only for readability /
VoiceAttack-import utility and is GATED: a command containing ANY unknown-marked action is
excluded from <Commands> and listed in a manifest comment at the top of the file. Partial
ActionSequences are never emitted — a silently lossy import file is a workaround by another
name. This emitter is NOT round-trip-verified against VoiceAttack import (that is the
end-gate import test); it is a faithful view of what V2 decoded, no more.
"""

import xml.etree.ElementTree as ET
from xml.dom import minidom


def _has_unknown(command):
    return any(a.get("decoded") is False for a in command.get("actions", []))


def to_xml(profile):
    root = ET.Element("Profile")
    ET.SubElement(root, "Id").text = _s(profile.get("profile", {}).get("id"))
    ET.SubElement(root, "Name").text = _s(profile.get("profile", {}).get("name"))
    commands_el = ET.SubElement(root, "Commands")

    excluded = []
    for cmd in profile.get("commands", []):
        if _has_unknown(cmd):
            n = sum(1 for a in cmd["actions"] if a.get("decoded") is False)
            excluded.append((cmd.get("phrase"), n))
            continue
        _emit_command(commands_el, cmd)

    xml_body = ET.tostring(root, encoding="unicode")
    pretty = minidom.parseString(xml_body).toprettyxml(indent="  ")

    if excluded:
        manifest = ["<!-- vap2 gated XML (prelim sec 8): commands with undecoded actions "
                    "excluded from import -->"]
        for phrase, n in excluded:
            manifest.append("<!-- excluded: %s — %d undecoded action%s -->"
                            % (_esc_comment(phrase), n, "" if n == 1 else "s"))
        lines = pretty.splitlines()
        # insert the manifest right after the <?xml ...?> declaration line
        return "\n".join([lines[0]] + manifest + lines[1:]) + "\n"
    return pretty


def _emit_command(parent, cmd):
    cmd_el = ET.SubElement(parent, "Command")
    ET.SubElement(cmd_el, "Id").text = _s(cmd.get("id"))
    ET.SubElement(cmd_el, "CommandString").text = _s(cmd.get("phrase"))
    cat = cmd.get("category", {})
    ET.SubElement(cmd_el, "Category").text = _s(cat.get("value") if isinstance(cat, dict) else cat)
    seq = ET.SubElement(cmd_el, "ActionSequence")
    for a in cmd.get("actions", []):
        _emit_action(seq, a)


def _emit_action(parent, a):
    el = ET.SubElement(parent, "CommandAction")
    at = a.get("actionType", {})
    ET.SubElement(el, "ActionType").text = _s(at.get("name"))
    if "duration" in a and a["duration"] is not None:
        ET.SubElement(el, "Duration").text = repr(a["duration"])
    if a.get("keyCodes"):
        kcs = ET.SubElement(el, "KeyCodes")
        for kc in a["keyCodes"]:
            if isinstance(kc, dict) and "vk" in kc:
                ET.SubElement(kcs, "unsignedShort").text = str(kc["vk"])
    if a.get("contextCode") is not None:
        ET.SubElement(el, "Context").text = _s(a["contextCode"])
    cond = a.get("condition")
    if cond:
        ET.SubElement(el, "ConditionStartOperator").text = _s(cond.get("operator", {}).get("name"))
        ET.SubElement(el, "ConditionStartValueType").text = _s(cond.get("valueType", {}).get("name"))
        if cond.get("leftOperand") is not None:
            ET.SubElement(el, "ConditionStartValue").text = _s(cond["leftOperand"])
        if cond.get("pairing") is not None:
            ET.SubElement(el, "ConditionPairing").text = str(cond["pairing"])
    ET.SubElement(el, "IndentLevel").text = str(a.get("indentLevel", 0))


def _s(v):
    return "" if v is None else str(v)


def _esc_comment(s):
    return _s(s).replace("--", "––")
