"""Condition encoding (spec sec 8) — compares, block structure, derived IndentLevel.

Conditions are FIELDS on a CommandAction, not a separate action type (spec sec 5).
A compare lives on ActionTypes 19 (Begin), 63 (Else If), 30 (Begin Loop While); the
block-structure actions 20 (End), 29 (Else), 31 (End Loop) carry only pairing links.
Records are emitted in an authorable shape: no field depends on a byte offset to be
interpretable (output contract sec 5) — pairing is a sequence index, ordinals and
operator/type codes are self-contained.
"""

from .primitives import ReadError, ABSENT
from . import primitives as P

COMPARE_TYPES = {19, 63, 30}
BLOCK_STRUCTURE_TYPES = {20, 29, 31}
BLOCK_TYPES = COMPARE_TYPES | BLOCK_STRUCTURE_TYPES

# Value-type code -> which slot/type holds the right operand (spec sec 8.3).
_TEXT_VTYPE = 1
_DECIMAL_VTYPE = 4
_BOOL_VTYPE = 2


def decode_compare(d, atype, dictionary):
    """Decode the compare carried by a Begin / Else If / Begin Loop While action.

    `d` is a primitives.Deref bound to the action's array. Returns a condition record.
    Operand reads are type-gated on m[24]; the value key is suppressed for valueless
    operators by the OPERATOR, never by inspecting the slot (spec sec 8.3 hazard).
    """
    rec = {}
    unknown_fields = []

    # Left operand — m[19] string (spec sec 8.3): inline token or pool-local var name.
    # This is the linchpin: m[24]=0 (SmallInteger) and m[20]=0 (Equals) are BYTE-IDENTICAL
    # to unset, so a compare is only identifiable when m[19] carries an operand (spec sec
    # 8.1: "identify a Small-Int compare structurally by m[2]=19 + operand m[19] + operator
    # m[20]"). Read it first and let its presence gate the type/operator claims.
    try:
        left = d.at(19, P.string)
    except ReadError:
        left = None

    vtype_code = _try_u32(d, 24)
    op_code = _try_u32(d, 20)

    if left is None:
        # No operand: the zero-default type/operator are indistinguishable from unset, so do
        # NOT assert SmallInteger/Equals (spec sec 8.1). Emit an honest unresolved marker.
        # Seen on Begin Loop While and compound Begins whose sub-compares live off the normal
        # slots (m[31] region) — pairing/ordinal/compound below are still valid.
        rec["leftOperand"] = None
        rec["valueType"] = {"code": vtype_code, "name": None}
        rec["operator"] = {"code": op_code, "name": None}
        rec["unresolved"] = {
            "decoded": False,
            "reason": "left operand (m[19]) absent; m[24]=0/m[20]=0 alias unset — "
                      "value-type and operator not identifiable (spec sec 8.1)",
        }
    else:
        vtype_name = dictionary.value_type(vtype_code) if vtype_code is not None else None
        rec["valueType"] = {"code": vtype_code, "name": vtype_name}
        op_name = dictionary.operator(vtype_name, op_code) if (vtype_name and op_code is not None) else None
        rec["operator"] = {"code": op_code, "name": op_name}
        rec["leftOperand"] = left
        # Right operand — split by value type; suppressed for valueless operators.
        if op_name is not None and dictionary.operator_is_valueless(op_name):
            pass  # Has/Has-Not-Been-Set: no value key (spec sec 8.3), by operator not slot
        else:
            rec["value"] = _read_right_operand(d, vtype_code, unknown_fields)

    # Pairing — m[17] (spec sec 8.4): 0-based index of the paired action.
    rec["pairing"] = _try_u32(d, 17)
    # Block-open ordinal — m[18] (spec sec 8.5). Emitted as blockOrdinal, NOT ConditionGroup.
    rec["blockOrdinal"] = _try_u32(d, 18)

    # Compound — m[31] scalar = sub-condition count (spec sec 8.6). Decode-only: emit the
    # first sub-compare (already above) plus an explicit marker; never silence the rest.
    # On a SIMPLE compare m[31] derefs to the 0xFFFFFFFF absent sentinel (verified: only a
    # true compound holds a small count, e.g. 2 on corinthian's `(return to main screen)`).
    sub_count = _try_u32(d, 31)
    if sub_count is not None and sub_count != ABSENT and 2 <= sub_count <= 64:
        rec["compound"] = {
            "subConditions": sub_count,
            "decoded": False,
            "note": "AND/OR sub-compare list format unverified (spec sec 8.6, parked #1)",
        }

    if unknown_fields:
        rec["unknownFields"] = unknown_fields
    return rec


def _read_right_operand(d, vtype_code, unknown_fields):
    try:
        if vtype_code == _TEXT_VTYPE:
            return d.at(7, P.string)
        if vtype_code == _DECIMAL_VTYPE:
            return d.at(25, P.decimal16)
        if vtype_code == _BOOL_VTYPE:
            return bool(d.at(21, P.i32) == 1)  # True=1 (spec sec 8.3)
        # SmallInteger(0) / Integer(3): i32, negatives real (spec sec 8.3).
        return d.at(21, P.i32)
    except ReadError:
        unknown_fields.append({"slot": "right-operand", "reason": "value unreadable"})
        return None


def decode_block_structure(d, atype, dictionary):
    """End (20) / Else (29) / End Loop (31): pairing link only (spec sec 8.4)."""
    return {"pairing": _try_u32(d, 17)}


def _try_u32(d, i):
    try:
        return d.at(i, P.u32)
    except ReadError:
        return None


# --- derived IndentLevel and block assembly (spec sec 8.7: derived, not stored) ---

def derive_indent(actions):
    """Annotate each action with indentLevel, reconstructed from Begin/End nesting
    (spec sec 8.7 — IndentLevel is not stored in any member slot). Mutates in place."""
    depth = 0
    for a in actions:
        code = _atype_code(a)
        if code in (20, 31):          # End / End Loop: close before printing
            depth = max(0, depth - 1)
            a["indentLevel"] = depth
        elif code in (29, 63):        # Else / Else If: branch keyword dedents one
            a["indentLevel"] = max(0, depth - 1)
        elif code in (19, 30):        # Begin / Begin Loop While: open after printing
            a["indentLevel"] = depth
            depth += 1
        else:
            a["indentLevel"] = depth
    return actions


def _atype_code(a):
    at = a.get("actionType")
    if isinstance(at, dict):
        return at.get("code")
    return a.get("actionTypeCode")
