"""Dictionary loader for the gen2 encoder — the single name authority (round-trip contract §1).

Same loading convention as the decoder's vap2/names.py, deliberately NOT imported from it:
the generation module is the top-tier component and depends only on the dictionary + stdlib
(architecture ruling 2026-07-12, Generator_Refactor_Plan §3). Action-type codes/names, XML
ActionType strings, condition value types, operator dropdown indexes, and mouse context
codes all resolve from `schema/vap_capability_dictionary.json` at runtime; there are NO
hand-edited name tables in this package (a contract violation per the contract's
tool-obligations section).
"""

import json
import os

_DICT_PATH_ENV = "VAP_DICTIONARY_PATH"


def _default_dict_path():
    here = os.path.dirname(os.path.abspath(__file__))
    root = os.path.abspath(os.path.join(here, "..", "..", "..", ".."))
    return os.path.join(root, "schema", "vap_capability_dictionary.json")


class Dictionary:
    """Loaded capability dictionary with the lookups the ENCODER needs — the reverse maps
    of the decoder's: canonical name -> binary code, code -> XML ActionType, operator
    NAME -> dropdown index, mouse action name -> context code."""

    def __init__(self, raw):
        self.raw = raw
        self.version = raw.get("meta", {}).get("version")

        # ActionType entries by binary code, plus canonical-name -> code.
        self.entry_by_code = {}
        self.code_by_canonical = {}
        for at in raw.get("action_types", []):
            code = at.get("binary_code")
            if code is None:
                continue
            self.entry_by_code[code] = at
            if at.get("canonical"):
                self.code_by_canonical[at["canonical"]] = code

        # Condition value types: name <-> code (spec sec 8.1; dictionary conditions).
        cond = raw.get("conditions", {})
        self.value_type_code_by_name = {}
        self.value_type_name_by_code = {}
        for vt in cond.get("value_types", []):
            self.value_type_code_by_name[vt["name"]] = vt["code"]
            self.value_type_name_by_code[vt["code"]] = vt["name"]

        # Operators: 0-indexed dropdown position IS the code (dictionary coding_rule).
        self.operators = {
            k: v for k, v in cond.get("operators", {}).items() if isinstance(v, list)
        }
        # Operators whose selection carries no value (spec sec 8.3 valueless rule).
        self._valueless = {"Has Been Set", "Has Not Been Set"}

        # Mouse: canonical action name (and every listed alias) -> context code, plus the
        # set of valid context codes for validating a record's own contextCode.
        self.mouse_code_by_name = {}
        mouse = raw.get("mouse", {})
        buttons = mouse.get("buttons", {})
        actions = mouse.get("button_actions", {})
        for bname, bcode in buttons.items():
            for aname, acode in actions.items():
                self.mouse_code_by_name["%s_%s" % (bname, aname)] = bcode + acode
        for sname, scode in mouse.get("scrolls", {}).items():
            self.mouse_code_by_name[sname] = scode
        cm = mouse.get("cursor_move", {})
        if cm.get("context_code"):
            self.mouse_code_by_name["cursor_move"] = cm["context_code"]
        self.mouse_context_codes = set(self.mouse_code_by_name.values())
        self.scroll_context_codes = set(mouse.get("scrolls", {}).values())
        self.cursor_move_code = cm.get("context_code")
        # Aliases are accepted forever once published (contract name-evolution rule).
        for alias, canonical in mouse.get("aliases", {}).items():
            if canonical in self.mouse_code_by_name:
                self.mouse_code_by_name.setdefault(alias, self.mouse_code_by_name[canonical])

        # Keys: name (canonical + every alias, lowercase) -> VK, and VK -> canonical.
        # The lowering layer's key table (plan W4) — replaces vap_generator's KEY_CODES
        # as the runtime authority; the dictionary is a superset of that hand table.
        self.key_vk_by_name = {}
        self.key_name_by_vk = {}
        for k in raw.get("keys", []):
            vk = k.get("vk")
            canonical = k.get("canonical")
            if vk is None or canonical is None:
                continue
            self.key_vk_by_name[canonical.lower()] = vk
            self.key_name_by_vk.setdefault(vk, canonical)
            for alias in k.get("aliases", []):
                self.key_vk_by_name.setdefault(alias.lower(), vk)

    # --- lookups (all return None on a miss; callers refuse, never guess) -----------

    def action_entry(self, code):
        return self.entry_by_code.get(code)

    def code_for_name(self, canonical):
        return self.code_by_canonical.get(canonical)

    def xml_action_type(self, code):
        entry = self.entry_by_code.get(code)
        return entry.get("xml_action_type") if entry else None

    def xml_confidence(self, code):
        entry = self.entry_by_code.get(code)
        return entry.get("xml_confidence") if entry else None

    def canonical(self, code):
        entry = self.entry_by_code.get(code)
        return entry.get("canonical") if entry else None

    def value_type_code(self, name):
        return self.value_type_code_by_name.get(name)

    def operator_index(self, value_type_name, operator_name):
        table = self.operators.get(value_type_name)
        if table is None or operator_name not in table:
            return None
        return table.index(operator_name)

    def operator_is_valueless(self, op_name):
        return op_name in self._valueless

    def mouse_context(self, action_name):
        return self.mouse_code_by_name.get(action_name)


def load(path=None):
    path = path or os.environ.get(_DICT_PATH_ENV) or _default_dict_path()
    with open(path, "r", encoding="utf-8") as f:
        return Dictionary(json.load(f))
