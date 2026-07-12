"""Strict v1.1 schema-JSON reader (plan W2) — the encoder's front door.

Validates the FROZEN normative decode shape (skills/voiceattack-decoder/docs/
V2_JSON_Schema.md v1.1): top level `{schema_version: 2, profile, commands, ...}`.
Provenance/offset annotations (`offset`, `head`, `guid`, `guidOffset`, `regionOffset`,
`source`, `census`, `confidence`, ...) are tolerated and ignored, never required — the
schema's one rule is that no value depends on a byte offset to be interpretable.

Unknown top-level shapes are rejected with SchemaError. In particular the v1 simple
authoring format (no `schema_version`) is rejected here by design: it enters through the
W4 lowering layer, not this reader.

Null mapping (v1.1 migration note): `category.value` null means the command has no
category and maps to an EMPTY XML `<Category>`; null profile name / command phrase map
to "" the same way. Actions carrying `decoded: false` (unknown markers) pass validation
untouched — emit_profile routes them to the contract §3 warn-and-emit-nothing path; they
are refusals downstream, never load errors here.
"""

import json


class SchemaError(Exception):
    """The input is not a v1.1 schema-JSON document. Hard fail: exit 1, no output."""


def load(path):
    """Load + validate a schema-JSON file. Returns the normalized model."""
    with open(path, "r", encoding="utf-8") as f:
        try:
            doc = json.load(f)
        except json.JSONDecodeError as e:
            raise SchemaError("invalid JSON in %s: %s" % (path, e)) from e
    return parse(doc)


def parse(doc):
    """Validate a parsed schema-JSON document. Returns the normalized model:

        {"profile": {"id": <str|None>, "name": <str>},
         "commands": [{"phrase": <str>, "category": <str|None>,
                       "actions": [<raw action records>]}, ...]}

    Action records are passed through as-is (decoded payload keys intact) — the emitter
    owns representability decisions; this reader owns document shape.
    """
    if not isinstance(doc, dict):
        raise SchemaError("top level must be a JSON object, got %s" % _kind(doc))
    if "schema_version" not in doc:
        raise SchemaError(
            "missing schema_version — not a v1.1 schema-JSON document "
            "(the v1 simple authoring format enters via the lowering layer, not here)")
    if doc["schema_version"] != 2:
        raise SchemaError("schema_version %r not supported (expected 2)" % (doc["schema_version"],))

    profile = doc.get("profile")
    if not isinstance(profile, dict):
        raise SchemaError("profile must be an object, got %s" % _kind(profile))
    name = profile.get("name")
    if name is not None and not isinstance(name, str):
        raise SchemaError("profile.name must be a string or null")
    pid = profile.get("id")
    if pid is not None and not isinstance(pid, str):
        raise SchemaError("profile.id must be a string or null")

    commands = doc.get("commands")
    if not isinstance(commands, list):
        raise SchemaError("commands must be an array, got %s" % _kind(commands))

    out_commands = []
    for i, cmd in enumerate(commands):
        out_commands.append(_parse_command(cmd, i))

    return {
        "profile": {"id": pid, "name": name if name is not None else ""},
        "commands": out_commands,
    }


def _parse_command(cmd, i):
    if not isinstance(cmd, dict):
        raise SchemaError("commands[%d] must be an object, got %s" % (i, _kind(cmd)))

    phrase = cmd.get("phrase")
    if phrase is not None and not isinstance(phrase, str):
        raise SchemaError("commands[%d].phrase must be a string or null" % i)

    # category: {"value": <str>|null, "provenance": ...} — provenance ignored; null value
    # means NO category (never a synthetic placeholder, v1.1 migration note).
    category = None
    cat = cmd.get("category")
    if cat is not None:
        if not isinstance(cat, dict) or ("value" in cat and not isinstance(cat["value"], (str, type(None)))):
            raise SchemaError("commands[%d].category must be an object with a string-or-null value" % i)
        category = cat.get("value")

    actions = cmd.get("actions")
    if not isinstance(actions, list):
        raise SchemaError("commands[%d].actions must be an array" % i)
    for j, a in enumerate(actions):
        _check_action(a, i, j)

    return {"phrase": phrase if phrase is not None else "",
            "category": category,
            "actions": actions}


def _check_action(a, i, j):
    where = "commands[%d].actions[%d]" % (i, j)
    if not isinstance(a, dict):
        raise SchemaError("%s must be an object, got %s" % (where, _kind(a)))
    if a.get("decoded") is False:
        return  # unknown marker: passes through; refused loudly at emission (contract §3)
    at = a.get("actionType")
    if not isinstance(at, dict):
        raise SchemaError("%s.actionType must be an object (or the action must carry decoded: false)" % where)
    code = at.get("code")
    if code is not None and not isinstance(code, int):
        raise SchemaError("%s.actionType.code must be an integer or null" % where)
    aname = at.get("name")
    if aname is not None and not isinstance(aname, str):
        raise SchemaError("%s.actionType.name must be a string or null" % where)
    cond = a.get("condition")
    if cond is not None and not isinstance(cond, dict):
        raise SchemaError("%s.condition must be an object" % where)


def _kind(v):
    return type(v).__name__
