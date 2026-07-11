"""XML-variant input (spec sec 3, sec 5).

A .vap may be an uncompressed `<Profile>` document instead of raw-deflate binary;
VoiceAttack imports both. v1 crashed on this documented-valid form; V2 parses it via
ElementTree into the SAME normative model the binary walker produces (output contract),
so downstream JSON is uniform regardless of container. Malformed XML raises a clean
XmlInputError, never an uncaught stack trace.

The XML form already stores the logical field set by NAME (ActionType text, Context,
KeyCodes, Condition* fields), so no member-slot deref is involved; this is a straight
field map. Fields the XML doesn't carry are simply absent, mirroring the binary path.
"""

import xml.etree.ElementTree as ET

from . import conditions


class XmlInputError(Exception):
    pass


def parse(data, dictionary):
    """Parse `<Profile>` XML bytes into the normative profile model."""
    try:
        root = ET.fromstring(data)
    except ET.ParseError as e:
        raise XmlInputError("malformed profile XML: %s" % e) from e

    tag = root.tag.split("}")[-1]  # tolerate a default namespace
    if tag != "Profile":
        raise XmlInputError("root element is <%s>, expected <Profile>" % tag)

    commands = []
    commands_el = _find_local(root, "Commands")
    if commands_el is not None:
        for cmd_el in _iter_local(commands_el, "Command"):
            commands.append(_parse_command(cmd_el, dictionary))

    return {
        "schema_version": 2,
        "decoder": "vap2",
        "source": "xml",
        "dictionary_version": dictionary.version,
        "profile": {
            "id": _local_text(root, "Id"),
            "name": _local_text(root, "Name"),
            "commandCount": len(commands),
        },
        "commands": commands,
        "census": _census(commands),
    }


def _parse_command(cmd_el, dictionary):
    actions = []
    seq = _find_local(cmd_el, "ActionSequence")
    if seq is not None:
        for i, act_el in enumerate(_iter_local(seq, "CommandAction")):
            actions.append(_parse_action(act_el, i, dictionary))
    conditions.derive_indent(actions)
    return {
        "id": _local_text(cmd_el, "Id"),
        "phrase": _local_text(cmd_el, "CommandString"),
        "category": {"value": _local_text(cmd_el, "Category") or None,
                     "provenance": "xml"},
        "actionCount": len(actions),
        "actions": actions,
    }


def _parse_action(act_el, index, dictionary):
    xml_type = _local_text(act_el, "ActionType")
    code = dictionary.code_for_xml_type(xml_type) if xml_type else None
    base = {
        "index": index,
        "actionType": {"code": code, "name": dictionary.action_type(code) if code is not None else xml_type},
        "source": "xml",
    }

    duration = _local_float(act_el, "Duration")
    if duration is not None:
        base["duration"] = duration
    context = _local_text(act_el, "Context")
    if context is not None:
        base["context"] = context

    keycodes = _parse_keycodes(act_el, dictionary)
    if keycodes:
        base["keyCodes"] = keycodes

    # Conditions are fields on the action (spec sec 5) — present as Condition* elements.
    op = _local_text(act_el, "ConditionStartOperator")
    vtype = _local_text(act_el, "ConditionStartValueType")
    if op or vtype:
        base["condition"] = {
            "valueType": {"name": vtype},
            "operator": {"name": op},
            "leftOperand": _local_text(act_el, "ConditionStartValue"),
            "pairing": _local_int(act_el, "ConditionPairing"),
            "ordinal": _local_int(act_el, "Ordinal"),
            "indentLevelStored": _local_int(act_el, "IndentLevel"),
        }
    return base


def _parse_keycodes(act_el, dictionary):
    kc = _find_local(act_el, "KeyCodes")
    if kc is None:
        return []
    out = []
    for us in _iter_local(kc, "unsignedShort"):
        if us.text is None:
            continue
        try:
            vk = int(us.text)
        except ValueError:
            continue
        out.append({"vk": vk, "name": dictionary.key_name(vk)})
    return out


def _census(commands):
    total = sum(len(c["actions"]) for c in commands)
    return {"totalActions": total, "decoded": total, "unknownMarked": 0, "source": "xml"}


# --- namespace-tolerant element helpers ----------------------------------------

def _local_name(el):
    return el.tag.split("}")[-1]


def _find_local(parent, name):
    for child in parent:
        if _local_name(child) == name:
            return child
    return None


def _iter_local(parent, name):
    for child in parent:
        if _local_name(child) == name:
            yield child


def _local_text(parent, name):
    el = _find_local(parent, name)
    return el.text if (el is not None and el.text is not None) else None


def _local_int(parent, name):
    t = _local_text(parent, name)
    try:
        return int(t) if t is not None else None
    except ValueError:
        return None


def _local_float(parent, name):
    t = _local_text(parent, name)
    try:
        return float(t) if t is not None else None
    except ValueError:
        return None
