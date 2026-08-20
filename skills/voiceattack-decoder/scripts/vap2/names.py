"""Dictionary loader — the single name authority (round-trip contract sec 1).

Every canonical name V2 emits comes from `schema/vap_capability_dictionary.json`; there
are NO hand-edited name tables in this package (a contract violation, per the contract's
Tool-obligations section). Names not present in the dictionary are emitted as explicit
`unknown` markers, never guessed.

Module-level tables VK_CODES and CONTEXT_TO_GENERATOR are derived from the dictionary at
import so `schema/dictionary_tools.py audit` can introspect this module the way it does
the v1 decoder (audit reads decoder_mod.VK_CODES / decoder_mod.CONTEXT_TO_GENERATOR).
"""

import json
import os

_DICT_PATH_ENV = "VAP_DICTIONARY_PATH"

_DICT_FILENAME = "vap_capability_dictionary.json"

# The path load() actually resolved, or None until a load succeeds. It must survive the
# import-time swallow at the foot of this module — the audit reads it to identity-check
# the dictionary this package really uses (dictionary path fix plan, step 8b).
RESOLVED_DICT_PATH = None


class DictionaryNotFound(Exception):
    """The name authority could not be located. Nothing this package decodes is
    representable without it, so callers hard-fail; none may guess a name
    (round-trip contract sec 1). gen2 defines its own — the two tools never
    cross-import (architecture ruling 2026-07-12)."""


def _candidate_dict_paths():
    """The two layouts this package ships in, in precedence order.

    1. Repo position — four hops up from vap2/, i.e. <repo>/schema/. Checked FIRST so
       a copy landing inside the repo tree can never shadow the one dictionary the
       generator and the audit read (Decision A).
    2. In-package position — two hops up, i.e. <package root>/schema/. That is the
       layout the dist artifacts already use; it is not a new invention.

    Deliberately absent: os.getcwd() and any upward walk. Either would make decoded
    output depend on where the caller stood.
    """
    here = os.path.dirname(os.path.abspath(__file__))
    repo_root = os.path.abspath(os.path.join(here, "..", "..", "..", ".."))
    package_root = os.path.abspath(os.path.join(here, "..", ".."))
    return [os.path.join(repo_root, "schema", _DICT_FILENAME),
            os.path.join(package_root, "schema", _DICT_FILENAME)]


class Dictionary:
    """Loaded capability dictionary with the lookups the decoder needs."""

    def __init__(self, raw):
        self.raw = raw
        self.version = raw.get("meta", {}).get("version")

        # ActionType code -> canonical name (spec sec 9.1); plus reverse maps for XML input.
        self.action_type_by_code = {}
        self.action_type_confidence = {}
        self.code_by_xml_type = {}
        self.code_by_canonical = {}
        for at in raw.get("action_types", []):
            code = at.get("binary_code")
            if code is not None:
                self.action_type_by_code[code] = at.get("canonical")
                self.action_type_confidence[code] = at.get("confidence", "unknown")
                if at.get("xml_action_type"):
                    self.code_by_xml_type[at["xml_action_type"]] = code
                if at.get("canonical"):
                    self.code_by_canonical[at["canonical"]] = code

        # Condition value-type code -> name, and right-operand slot note (spec sec 8.1)
        cond = raw.get("conditions", {})
        self.value_type_by_code = {}
        for vt in cond.get("value_types", []):
            self.value_type_by_code[vt["code"]] = vt["name"]

        # Operators: per value-type dropdown, index == code (spec sec 8.2)
        self.operators = {
            k: v for k, v in cond.get("operators", {}).items() if isinstance(v, list)
        }
        # Operators whose selection carries no value (spec sec 8.3 valueless rule)
        self._valueless = {"Has Been Set", "Has Not Been Set"}

        # Mouse context code -> canonical name (spec sec 9.3, dictionary `mouse`)
        self.mouse_name_by_code = self._build_mouse(raw.get("mouse", {}))

        # Keys: vk -> UPPER canonical (for VK_CODES / audit), and vk -> canonical
        self.vk_upper = {}
        self.vk_canonical = {}
        for k in raw.get("keys", []):
            vk = k.get("vk")
            canon = k.get("canonical")
            if vk is not None and canon is not None:
                self.vk_upper[vk] = canon.upper()
                self.vk_canonical[vk] = canon

    @staticmethod
    def _build_mouse(mouse):
        by_code = {}
        buttons = mouse.get("buttons", {})
        actions = mouse.get("button_actions", {})
        for bname, bcode in buttons.items():
            for aname, acode in actions.items():
                by_code[bcode + acode] = "%s_%s" % (bname, aname)
        for sname, scode in mouse.get("scrolls", {}).items():
            by_code[scode] = sname
        cm = mouse.get("cursor_move", {})
        if cm.get("context_code"):
            by_code[cm["context_code"]] = "cursor_move"
        return by_code

    # --- lookups (all return None / a marker on a miss; callers decide) ---

    def action_type(self, code):
        return self.action_type_by_code.get(code)

    def code_for_xml_type(self, xml_type):
        """Map an XML <ActionType> name to its binary code (XML input path)."""
        if xml_type in self.code_by_xml_type:
            return self.code_by_xml_type[xml_type]
        return self.code_by_canonical.get(xml_type)

    def value_type(self, code):
        return self.value_type_by_code.get(code)

    def operator(self, value_type_name, code):
        table = self.operators.get(value_type_name)
        if table is None or code < 0 or code >= len(table):
            return None
        return table[code]

    def operator_is_valueless(self, op_name):
        return op_name in self._valueless

    def mouse_name(self, context_code):
        return self.mouse_name_by_code.get(context_code)

    def key_name(self, vk):
        return self.vk_canonical.get(vk, "VK_%d" % vk)


def _not_found_message(tried):
    lines = ["cannot locate the VoiceAttack capability dictionary (%s)." % _DICT_FILENAME,
             "Tried, in order:"]
    lines += ["  %d. %s (%s)" % (i, path, label) for i, (label, path) in enumerate(tried, 1)]
    lines.append("Set %s to the dictionary's full path, or place a copy at the in-package "
                 "location <package root>/schema/%s — the layout the release artifacts use."
                 % (_DICT_PATH_ENV, _DICT_FILENAME))
    return "\n".join(lines)


def load(path=None):
    """Load the name authority. Precedence: explicit `path=`, then $VAP_DICTIONARY_PATH,
    then _candidate_dict_paths() in order.

    An explicit path and a set-but-missing env var do NOT fall through to the candidates:
    a typo'd override silently resolving to a *different* dictionary is exactly the
    silent degradation this project forbids, so it raises DictionaryNotFound instead.
    A candidate that exists but will not parse also raises rather than falling through.

    Records the winning path in the module-level RESOLVED_DICT_PATH for the audit.
    """
    global RESOLVED_DICT_PATH
    env = os.environ.get(_DICT_PATH_ENV)
    if path is not None:
        tried = [("explicit path argument", path)]
    elif env:
        tried = [("%s environment variable" % _DICT_PATH_ENV, env)]
    else:
        tried = list(zip(("repo position", "in-package position"), _candidate_dict_paths()))

    for _, candidate in tried:
        try:
            f = open(candidate, "r", encoding="utf-8")
        except OSError:
            continue
        with f:
            raw = json.load(f)
        RESOLVED_DICT_PATH = os.path.abspath(candidate)
        return Dictionary(raw)

    raise DictionaryNotFound(_not_found_message(tried))


# --- audit-facing module tables (derived, never hand-edited) --------------------
# Built at import so dictionary_tools.py audit can read them off this module. The
# swallow is KEPT deliberately: the module must still import for load_tool_module() to
# introspect it. It is no longer a hollow pass — empty tables and a None
# RESOLVED_DICT_PATH now COUNT as audit failures (dictionary path fix plan, step 8),
# so the "audit will surface it" claim below is finally true. RESOLVED_DICT_PATH is
# never reset here: load() sets it only on success, so it stays None on failure.
try:
    _DEFAULT = load()
    VK_CODES = {vk: name for vk, name in _DEFAULT.vk_upper.items()}
    CONTEXT_TO_GENERATOR = dict(_DEFAULT.mouse_name_by_code)
except Exception:  # pragma: no cover - the audit surfaces a missing dictionary (step 8)
    _DEFAULT = None
    VK_CODES = {}
    CONTEXT_TO_GENERATOR = {}
