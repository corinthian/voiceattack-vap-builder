#!/usr/bin/env python3
"""
dictionary_tools.py - tooling for vap_capability_dictionary.json

Subcommands:
    validate    structural validation of the dictionary
    render      generate schema/VAP_Capability_Dictionary.md from the JSON
    audit       zero-orphans check between the dictionary and the live decoder/generator sources

Python 3, stdlib only. See schema/VAP_Round_Trip_Contract.md for the contract this enforces.
"""

import argparse
import importlib.util
import json
import re
import sys
from pathlib import Path

SCRIPT_PATH = Path(__file__).resolve()
SCHEMA_DIR = SCRIPT_PATH.parent
REPO_ROOT = SCHEMA_DIR.parent

DICT_PATH = SCHEMA_DIR / "vap_capability_dictionary.json"
MD_OUT_PATH = SCHEMA_DIR / "VAP_Capability_Dictionary.md"
DECODER_PATH = REPO_ROOT / "skills" / "voiceattack-decoder" / "scripts" / "vap_decoder.py"
GENERATOR_PATH = REPO_ROOT / "skills" / "voiceattack-generator" / "scripts" / "vap_generator.py"

CONFIDENCE_LEVELS = {"solid", "plausible", "inferred", "parked"}
ROUND_TRIP_VALUES = {"canonical", "warn", "opaque"}

# Preferred display order for key groups; unknown groups sort alphabetically after these.
GROUP_ORDER = [
    "letters", "digits", "function", "special", "arrows",
    "modifiers", "punctuation", "locks", "numpad", "media",
]


def load_dict(path=DICT_PATH):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def group_sort_key(group):
    if group in GROUP_ORDER:
        return (0, GROUP_ORDER.index(group), "")
    return (1, 0, group or "")


def derive_mouse_names(mouse):
    """Return {name: code} for all 34 derivable mouse names from a dictionary mouse block."""
    derived = {}
    buttons = mouse.get("buttons", {})
    button_actions = mouse.get("button_actions", {})
    scrolls = mouse.get("scrolls", {})
    for bname, bcode in buttons.items():
        for aname, acode in button_actions.items():
            derived[f"{bname}_{aname}"] = f"{bcode}{acode}"
    for sname, scode in scrolls.items():
        derived[sname] = scode
    return derived


# ---------------------------------------------------------------------------
# validate
# ---------------------------------------------------------------------------

def validate(d):
    """Return a list of violation strings. Empty list == clean."""
    violations = []

    # --- meta ---
    meta = d.get("meta")
    if not isinstance(meta, dict):
        violations.append("meta: missing or not an object")
        meta = {}
    for field in ("name", "version", "date", "spec"):
        if field not in meta:
            violations.append(f"meta.{field}: missing")

    # --- action_types ---
    action_types = d.get("action_types")
    if not isinstance(action_types, list):
        violations.append("action_types: missing or not a list")
        action_types = []

    seen_codes = {}
    seen_canon = {}
    required_at_fields = [
        "binary_code", "canonical", "xml_action_type",
        "xml_confidence", "confidence", "spec_ref", "fields", "round_trip",
    ]
    for idx, at in enumerate(action_types):
        label = f"action_types[{idx}]"
        if not isinstance(at, dict):
            violations.append(f"{label}: not an object")
            continue
        canon = at.get("canonical")
        for rk in required_at_fields:
            if rk not in at:
                violations.append(f"{label} ({canon!r}): missing {rk}")

        bc = at.get("binary_code")
        if bc is not None and not isinstance(bc, int):
            violations.append(f"{label} ({canon!r}): binary_code must be int or null, got {bc!r}")
        if canon is not None and not isinstance(canon, str):
            violations.append(f"{label}: canonical must be str or null, got {canon!r}")
        xat = at.get("xml_action_type")
        if xat is not None and not isinstance(xat, str):
            violations.append(f"{label} ({canon!r}): xml_action_type must be str or null, got {xat!r}")
        if at.get("xml_confidence") not in CONFIDENCE_LEVELS:
            violations.append(f"{label} ({canon!r}): xml_confidence {at.get('xml_confidence')!r} not in {sorted(CONFIDENCE_LEVELS)}")
        if at.get("confidence") not in CONFIDENCE_LEVELS:
            violations.append(f"{label} ({canon!r}): confidence {at.get('confidence')!r} not in {sorted(CONFIDENCE_LEVELS)}")
        if not at.get("spec_ref"):
            violations.append(f"{label} ({canon!r}): spec_ref missing/empty")
        if not isinstance(at.get("fields"), dict):
            violations.append(f"{label} ({canon!r}): fields missing or not an object")
        if at.get("round_trip") not in ROUND_TRIP_VALUES:
            violations.append(f"{label} ({canon!r}): round_trip {at.get('round_trip')!r} not in {sorted(ROUND_TRIP_VALUES)}")

        if isinstance(bc, int):
            if bc in seen_codes:
                violations.append(f"action_types: duplicate binary_code {bc} ({seen_codes[bc]!r} and {canon!r})")
            else:
                seen_codes[bc] = canon
        if isinstance(canon, str):
            if canon in seen_canon:
                violations.append(f"action_types: duplicate canonical {canon!r} (binary_code {seen_canon[canon]!r} and {bc!r})")
            else:
                seen_canon[canon] = bc

    # --- keys ---
    keys = d.get("keys")
    if not isinstance(keys, list):
        violations.append("keys: missing or not a list")
        keys = []

    canonical_count = {}
    alias_count = {}
    name_vk = {}
    required_key_fields = ["canonical", "vk", "aliases", "group", "confidence"]
    for idx, k in enumerate(keys):
        label = f"keys[{idx}]"
        if not isinstance(k, dict):
            violations.append(f"{label}: not an object")
            continue
        canon = k.get("canonical")
        for field in required_key_fields:
            if field not in k:
                violations.append(f"{label} ({canon!r}): missing {field}")

        vk = k.get("vk")
        if not isinstance(vk, int):
            violations.append(f"{label} ({canon!r}): vk must be int, got {vk!r}")

        aliases = k.get("aliases")
        if not isinstance(aliases, list):
            violations.append(f"{label} ({canon!r}): aliases must be a list")
            aliases = []

        if canon is not None:
            canonical_count[canon] = canonical_count.get(canon, 0) + 1

        for a in aliases:
            alias_count[a] = alias_count.get(a, 0) + 1

        for name in ([canon] if canon is not None else []) + list(aliases):
            if name in name_vk and name_vk[name] != vk:
                violations.append(f"keys: name {name!r} maps to multiple VKs ({name_vk[name]!r} vs {vk!r})")
            else:
                name_vk[name] = vk

    for canon, cnt in canonical_count.items():
        if cnt > 1:
            violations.append(f"keys: duplicate canonical name {canon!r} ({cnt} occurrences)")

    canonical_set = set(canonical_count.keys())
    for alias, cnt in alias_count.items():
        if alias in canonical_set:
            violations.append(f"keys: alias {alias!r} collides with a canonical key name")
        if cnt > 1:
            violations.append(f"keys: alias {alias!r} used by {cnt} different key entries")

    # --- mouse ---
    mouse = d.get("mouse")
    if not isinstance(mouse, dict):
        violations.append("mouse: missing or not an object")
        mouse = {}
    buttons = mouse.get("buttons", {})
    button_actions = mouse.get("button_actions", {})
    scrolls = mouse.get("scrolls", {})
    if len(buttons) != 5:
        violations.append(f"mouse.buttons: expected 5 entries, got {len(buttons)}")
    if len(button_actions) != 6:
        violations.append(f"mouse.button_actions: expected 6 entries, got {len(button_actions)}")
    if len(scrolls) != 4:
        violations.append(f"mouse.scrolls: expected 4 entries, got {len(scrolls)}")

    derived_codes = {}
    for bname, bcode in buttons.items():
        for aname, acode in button_actions.items():
            name = f"{bname}_{aname}"
            code = f"{bcode}{acode}"
            if code in derived_codes:
                violations.append(f"mouse: duplicate derived code {code!r} ({derived_codes[code]!r} and {name!r})")
            else:
                derived_codes[code] = name
    for sname, scode in scrolls.items():
        if scode in derived_codes:
            violations.append(f"mouse: duplicate derived code {scode!r} ({derived_codes[scode]!r} and {sname!r})")
        else:
            derived_codes[scode] = sname
    if len(derived_codes) != 34:
        violations.append(f"mouse: expected 34 derivable codes, got {len(derived_codes)}")

    mouse_aliases = mouse.get("aliases", {})
    if not isinstance(mouse_aliases, dict):
        violations.append("mouse.aliases: must be an object")
        mouse_aliases = {}
    derived_names = set(derive_mouse_names(mouse))
    for alias, target in mouse_aliases.items():
        if target not in derived_names:
            violations.append(f"mouse.aliases: {alias!r} -> {target!r}, which is not a derived mouse name")
        if alias in derived_names:
            violations.append(f"mouse.aliases: alias {alias!r} collides with a derived mouse name")

    # --- conditions ---
    conditions = d.get("conditions")
    if not isinstance(conditions, dict):
        violations.append("conditions: missing or not an object")
        conditions = {}

    vts = conditions.get("value_types")
    if not isinstance(vts, list):
        violations.append("conditions.value_types: missing or not a list")
        vts = []
    codes_seen = {}
    for vt in vts:
        if not isinstance(vt, dict):
            violations.append("conditions.value_types: entry not an object")
            continue
        code = vt.get("code")
        if code in codes_seen:
            violations.append(f"conditions.value_types: duplicate code {code}")
        codes_seen[code] = vt.get("name")
    if set(codes_seen.keys()) != {0, 1, 2, 3, 4}:
        violations.append(f"conditions.value_types: expected codes 0-4, got {sorted(c for c in codes_seen if isinstance(c, int))}")

    ops = conditions.get("operators", {})
    if not isinstance(ops, dict):
        violations.append("conditions.operators: missing or not an object")
        ops = {}
    expected_lengths = {"Text": 10, "Integer": 8, "Decimal": 8, "SmallInteger": 8, "Boolean": 4}
    for name, exp_len in expected_lengths.items():
        lst = ops.get(name)
        if not isinstance(lst, list):
            violations.append(f"conditions.operators.{name}: missing or not a list")
        elif len(lst) != exp_len:
            violations.append(f"conditions.operators.{name}: expected {exp_len} operators, got {len(lst)}")

    return violations


def cmd_validate(args):
    d = load_dict(args.dict)
    violations = validate(d)
    if not violations:
        print("validate: OK - no structural violations")
        return 0
    print(f"validate: {len(violations)} violation(s):")
    for v in violations:
        print(f"  - {v}")
    return 1


# ---------------------------------------------------------------------------
# render
# ---------------------------------------------------------------------------

def _esc_pipe(s):
    return (s or "").replace("|", "\\|")


def render_markdown(d):
    meta = d.get("meta", {})
    lines = []

    lines.append(
        f"GENERATED from vap_capability_dictionary.json v{meta.get('version', '?')} "
        f"— do not hand-edit; regenerate with dictionary_tools.py render"
    )
    lines.append("")
    lines.append("# VAP Capability Dictionary")
    lines.append("")
    lines.append(f"- Name: {meta.get('name', '')}")
    lines.append(f"- Version: {meta.get('version', '')}")
    lines.append(f"- Date: {meta.get('date', '')}")
    spec = meta.get("spec", {})
    if isinstance(spec, dict):
        lines.append(f"- Spec: {spec.get('file', '')} v{spec.get('version', '')}")
    if meta.get("purpose"):
        lines.append(f"- Purpose: {meta['purpose']}")
    if meta.get("canonical_rule"):
        lines.append(f"- Canonical rule: {meta['canonical_rule']}")
    lines.append("")

    conf_legend = meta.get("confidence_legend", {})
    if isinstance(conf_legend, dict) and conf_legend:
        lines.append("## Confidence Legend")
        lines.append("")
        for level in ("solid", "plausible", "inferred", "parked"):
            if level in conf_legend:
                lines.append(f"- **{level}**: {conf_legend[level]}")
        lines.append("")

    # --- Action Types ---
    lines.append("## Action Types")
    lines.append("")
    lines.append("| Code | Canonical | XML Name | Confidence | Round-Trip | Notes |")
    lines.append("|---|---|---|---|---|---|")
    action_types = sorted(
        d.get("action_types", []),
        key=lambda at: (
            at.get("binary_code") is None,
            at.get("binary_code") if at.get("binary_code") is not None else 0,
            at.get("canonical") or "",
        ),
    )
    for at in action_types:
        code = at.get("binary_code")
        code_s = str(code) if code is not None else "—"
        canon = at.get("canonical") or "—"
        xat = at.get("xml_action_type") or "—"
        conf = at.get("confidence") or "—"
        rt = at.get("round_trip") or "—"
        notes = _esc_pipe(at.get("notes"))
        lines.append(f"| {code_s} | {canon} | {xat} | {conf} | {rt} | {notes} |")
    lines.append("")

    # --- Keys ---
    lines.append("## Keys")
    lines.append("")
    keys = d.get("keys", [])
    groups = sorted({k.get("group") for k in keys if isinstance(k, dict)}, key=group_sort_key)
    for g in groups:
        lines.append(f"### {g}")
        lines.append("")
        lines.append("| Canonical | VK (dec) | VK (hex) | Aliases | Confidence |")
        lines.append("|---|---|---|---|---|")
        group_keys = sorted(
            (k for k in keys if k.get("group") == g),
            key=lambda k: k.get("canonical") or "",
        )
        for k in group_keys:
            canon = k.get("canonical")
            vk = k.get("vk")
            vk_hex = f"0x{vk:02X}" if isinstance(vk, int) else "—"
            aliases = ", ".join(k.get("aliases") or []) or "—"
            conf = k.get("confidence") or "—"
            lines.append(f"| {canon} | {vk} | {vk_hex} | {aliases} | {conf} |")
        lines.append("")

    # --- Mouse ---
    lines.append("## Mouse")
    lines.append("")
    mouse = d.get("mouse", {})
    if mouse.get("canonical_rule"):
        lines.append(f"Rule: {mouse['canonical_rule']}")
        lines.append("")
    lines.append("| Name | Code |")
    lines.append("|---|---|")
    derived = derive_mouse_names(mouse)
    for name in sorted(derived.keys()):
        lines.append(f"| {name} | {derived[name]} |")
    lines.append("")
    mouse_aliases = mouse.get("aliases", {})
    if mouse_aliases:
        lines.append("Aliases: " + ", ".join(f"{a} = {t}" for a, t in sorted(mouse_aliases.items())))
        lines.append("")

    # --- Conditions ---
    lines.append("## Conditions")
    lines.append("")
    conditions = d.get("conditions", {})

    lines.append("### Value Types")
    lines.append("")
    lines.append("| Code | Name | Right-Operand Slot | Confidence | Notes |")
    lines.append("|---|---|---|---|---|")
    for vt in sorted(conditions.get("value_types", []), key=lambda v: v.get("code", 0)):
        notes = _esc_pipe(vt.get("notes"))
        lines.append(
            f"| {vt.get('code')} | {vt.get('name')} | {vt.get('right_operand_slot', '')} | "
            f"{vt.get('confidence', '')} | {notes} |"
        )
    lines.append("")

    lines.append("### Operators")
    lines.append("")
    ops = conditions.get("operators", {})
    lines.append(f"Coding rule: {ops.get('coding_rule', '')}")
    lines.append("")
    for vt_name in ["Text", "Integer", "Decimal", "SmallInteger", "Boolean"]:
        lst = ops.get(vt_name, [])
        lines.append(f"- **{vt_name}** ({len(lst)}): {', '.join(lst)}")
    lines.append("")

    lines.append("### Block Structure")
    lines.append("")
    bs = conditions.get("block_structure", {})
    for k in ("pairing", "block_ordinal", "indent_level", "confidence"):
        if k in bs:
            lines.append(f"- **{k}**: {bs[k]}")
    lines.append("")

    compound = conditions.get("compound", {})
    if compound:
        lines.append(f"- **compound**: status={compound.get('status')} — {compound.get('contract', '')}")
        lines.append("")

    hazards = conditions.get("operand_hazards", [])
    if hazards:
        lines.append("### Operand Hazards")
        lines.append("")
        for h in hazards:
            lines.append(f"- {h}")
        lines.append("")

    # --- Durations ---
    lines.append("## Durations")
    lines.append("")
    dur = d.get("durations", {})
    for k in ("binary", "json_default", "serialization", "confidence"):
        if k in dur:
            lines.append(f"- **{k}**: {dur[k]}")
    lines.append("")

    # --- Parked ---
    lines.append("## Parked Registry Pointer")
    lines.append("")
    lines.append(d.get("parked_registry_pointer", ""))
    lines.append("")

    return "\n".join(lines) + "\n"


def cmd_render(args):
    d = load_dict(args.dict)
    md = render_markdown(d)
    out_path = Path(args.out)
    out_path.write_text(md, encoding="utf-8")
    print(f"render: wrote {out_path}")
    return 0


# ---------------------------------------------------------------------------
# audit
# ---------------------------------------------------------------------------

def load_tool_module(path):
    spec = importlib.util.spec_from_file_location(path.stem, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def extract_action_dispatch_types(generator_src):
    """Regex-extract the action_type names vap_generator.py's action_xml() dispatches on."""
    m = re.search(r"def action_xml\(.*?\):\n(.*?)\ndef ", generator_src, re.S)
    body = m.group(1) if m else generator_src
    types = set()
    for tup in re.findall(r'action_type in \(([^)]*)\)', body):
        types.update(re.findall(r'"([^"]+)"', tup))
    for s in re.findall(r'action_type == "([^"]+)"', body):
        types.add(s)
    return types


def dict_key_name_maps(d):
    """Return (all_names_set, canonical_names_set, name->vk map) from dictionary keys."""
    all_names = set()
    canonical_names = set()
    name_vk = {}
    for k in d.get("keys", []):
        canon = k.get("canonical")
        vk = k.get("vk")
        if canon is not None:
            all_names.add(canon)
            canonical_names.add(canon)
            name_vk[canon] = vk
        for a in k.get("aliases", []) or []:
            all_names.add(a)
            name_vk[a] = vk
    return all_names, canonical_names, name_vk


def audit(d, decoder_mod, generator_mod, generator_src):
    report = {}

    dict_names, dict_canonical_names, dict_name_vk = dict_key_name_maps(d)

    # --- Keys: decoder side ---
    vk_codes = decoder_mod.VK_CODES  # int -> UPPER name
    decoder_name_vk = {name.lower(): vk for vk, name in vk_codes.items()}
    decoder_names = set(decoder_name_vk.keys())

    orphans_decoder_keys = sorted(decoder_names - dict_names)

    # --- Keys: generator side ---
    key_codes = generator_mod.KEY_CODES  # lower name -> int
    generator_names = set(key_codes.keys())
    generator_name_vk = dict(key_codes)

    orphans_generator_keys = sorted(generator_names - dict_names)

    # --- VK-code mismatches (name present in both a tool table and dict, different VK) ---
    vk_mismatches = []
    for name in sorted(decoder_names & dict_names):
        if decoder_name_vk[name] != dict_name_vk[name]:
            vk_mismatches.append(
                f"{name!r}: decoder VK={decoder_name_vk[name]} dict VK={dict_name_vk[name]}"
            )
    for name in sorted(generator_names & dict_names):
        if generator_name_vk[name] != dict_name_vk[name]:
            vk_mismatches.append(
                f"{name!r}: generator VK={generator_name_vk[name]} dict VK={dict_name_vk[name]}"
            )

    # --- Pending adoption (dictionary ahead of tools; expected V2/encoder work) ---
    pending_keys_not_in_generator = sorted(dict_names - generator_names)
    pending_canonical_not_emitted_by_decoder = sorted(dict_canonical_names - decoder_names)

    report["keys"] = {
        "orphans_decoder_emits_not_in_dict": orphans_decoder_keys,
        "orphans_generator_accepts_not_in_dict": orphans_generator_keys,
        "vk_mismatches": vk_mismatches,
        "pending_dict_names_not_accepted_by_generator": pending_keys_not_in_generator,
        "pending_dict_canonical_not_emitted_by_decoder": pending_canonical_not_emitted_by_decoder,
    }

    # --- Mouse ---
    mouse = d.get("mouse", {})
    dict_mouse_codes = derive_mouse_names(mouse)  # name -> code
    mouse_aliases = mouse.get("aliases", {}) or {}
    for alias, target in mouse_aliases.items():
        if target in dict_mouse_codes:
            dict_mouse_codes[alias] = dict_mouse_codes[target]
    dict_mouse_names = set(dict_mouse_codes.keys())

    context_to_generator = decoder_mod.CONTEXT_TO_GENERATOR  # context code -> name
    decoder_mouse_code_by_name = {v: k for k, v in context_to_generator.items()}
    decoder_mouse_names = set(decoder_mouse_code_by_name.keys())

    mouse_codes = generator_mod.MOUSE_CODES  # name -> code
    generator_mouse_names = set(mouse_codes.keys())

    mouse_generator_only = sorted(generator_mouse_names - dict_mouse_names)
    mouse_decoder_only = sorted(decoder_mouse_names - dict_mouse_names)

    mouse_pending_dict_not_in_generator = sorted(dict_mouse_names - generator_mouse_names)
    mouse_pending_dict_not_in_decoder = sorted(dict_mouse_names - decoder_mouse_names)

    mouse_code_mismatches = []
    for name in sorted(dict_mouse_names & decoder_mouse_names):
        if dict_mouse_codes[name] != decoder_mouse_code_by_name[name]:
            mouse_code_mismatches.append(
                f"{name!r}: dict={dict_mouse_codes[name]} decoder={decoder_mouse_code_by_name[name]}"
            )
    for name in sorted(dict_mouse_names & generator_mouse_names):
        if dict_mouse_codes[name] != mouse_codes[name]:
            mouse_code_mismatches.append(
                f"{name!r}: dict={dict_mouse_codes[name]} generator={mouse_codes[name]}"
            )

    report["mouse"] = {
        "orphans_generator_accepts_not_in_dict": mouse_generator_only,
        "orphans_decoder_emits_not_in_dict": mouse_decoder_only,
        "code_mismatches": mouse_code_mismatches,
        "pending_dict_names_not_accepted_by_generator": mouse_pending_dict_not_in_generator,
        "pending_dict_names_not_emitted_by_decoder": mouse_pending_dict_not_in_decoder,
    }

    # --- Action types ---
    dict_xml_types = {
        at.get("xml_action_type")
        for at in d.get("action_types", [])
        if at.get("xml_action_type")
    }
    generator_action_types = extract_action_dispatch_types(generator_src)

    orphans_action_types = sorted(generator_action_types - dict_xml_types)
    pending_action_types = sorted(dict_xml_types - generator_action_types)

    report["action_types"] = {
        "orphans_generator_handles_not_in_dict": orphans_action_types,
        "pending_dict_xml_types_not_handled_by_generator": pending_action_types,
    }

    # --- Failure tally (true orphans/mismatches only; pending-adoption never fails) ---
    fail_count = (
        len(orphans_decoder_keys)
        + len(orphans_generator_keys)
        + len(vk_mismatches)
        + len(mouse_generator_only)
        + len(mouse_decoder_only)
        + len(mouse_code_mismatches)
        + len(orphans_action_types)
    )
    report["fail_count"] = fail_count
    return report


def _fmt_list(items):
    return "none" if not items else ", ".join(repr(i) for i in items)


def format_audit_report(report):
    lines = []
    k = report["keys"]
    lines.append("=== Keys: decoder (VK_CODES) vs dictionary ===")
    lines.append(f"Orphans - decoder emits, absent from dictionary [FAIL]: {_fmt_list(k['orphans_decoder_emits_not_in_dict'])}")
    lines.append("")
    lines.append("=== Keys: generator (KEY_CODES) vs dictionary ===")
    lines.append(f"Orphans - generator accepts, absent from dictionary [FAIL]: {_fmt_list(k['orphans_generator_accepts_not_in_dict'])}")
    lines.append("")
    lines.append("=== Keys: VK-code mismatches ===")
    lines.append(f"[FAIL]: {_fmt_list(k['vk_mismatches'])}")
    lines.append("")
    lines.append("=== Keys: pending adoption (dictionary ahead of tools; expected V2/encoder work) ===")
    lines.append(f"Dictionary names not yet accepted by generator: {_fmt_list(k['pending_dict_names_not_accepted_by_generator'])}")
    lines.append(f"Dictionary canonical names not yet emitted by decoder: {_fmt_list(k['pending_dict_canonical_not_emitted_by_decoder'])}")
    lines.append("")

    m = report["mouse"]
    lines.append("=== Mouse ===")
    lines.append(f"Orphans - generator accepts, absent from dictionary's 34 [FAIL]: {_fmt_list(m['orphans_generator_accepts_not_in_dict'])}")
    lines.append(f"Orphans - decoder emits, absent from dictionary's 34 [FAIL]: {_fmt_list(m['orphans_decoder_emits_not_in_dict'])}")
    lines.append(f"Code mismatches [FAIL]: {_fmt_list(m['code_mismatches'])}")
    lines.append(f"Pending - dictionary names not accepted by generator: {_fmt_list(m['pending_dict_names_not_accepted_by_generator'])}")
    lines.append(f"Pending - dictionary names not emitted by decoder: {_fmt_list(m['pending_dict_names_not_emitted_by_decoder'])}")
    lines.append("")

    a = report["action_types"]
    lines.append("=== Action Types (generator dispatch vs dictionary xml_action_type) ===")
    lines.append(f"Orphans - generator handles, absent from dictionary [FAIL]: {_fmt_list(a['orphans_generator_handles_not_in_dict'])}")
    lines.append(f"Pending - dictionary xml_action_type values generator doesn't handle: {_fmt_list(a['pending_dict_xml_types_not_handled_by_generator'])}")
    lines.append("")

    lines.append("=== Summary ===")
    lines.append(f"Total true orphans/mismatches: {report['fail_count']}")
    lines.append("Exit: 0" if report["fail_count"] == 0 else "Exit: 1")
    return "\n".join(lines)


def cmd_audit(args):
    d = load_dict(args.dict)
    decoder_mod = load_tool_module(Path(args.decoder))
    generator_mod = load_tool_module(Path(args.generator))
    generator_src = Path(args.generator).read_text(encoding="utf-8")

    report = audit(d, decoder_mod, generator_mod, generator_src)
    print(format_audit_report(report))
    return 0 if report["fail_count"] == 0 else 1


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def build_parser():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--dict", default=str(DICT_PATH), help="path to vap_capability_dictionary.json")
    sub = p.add_subparsers(dest="command", required=True)

    sp_validate = sub.add_parser("validate", help="structural validation of the dictionary")
    sp_validate.set_defaults(func=cmd_validate)

    sp_render = sub.add_parser("render", help="generate VAP_Capability_Dictionary.md from the JSON")
    sp_render.add_argument("--out", default=str(MD_OUT_PATH), help="output markdown path")
    sp_render.set_defaults(func=cmd_render)

    sp_audit = sub.add_parser("audit", help="zero-orphans check against live decoder/generator sources")
    sp_audit.add_argument("--decoder", default=str(DECODER_PATH), help="path to vap_decoder.py")
    sp_audit.add_argument("--generator", default=str(GENERATOR_PATH), help="path to vap_generator.py")
    sp_audit.set_defaults(func=cmd_audit)

    return p


def main():
    parser = build_parser()
    args = parser.parse_args()
    sys.exit(args.func(args))


if __name__ == "__main__":
    main()
