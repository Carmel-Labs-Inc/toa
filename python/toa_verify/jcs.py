"""
RFC 8785 JSON Canonicalization Scheme (JCS) for toa/0.1.

Signing input and args_hash MUST be JCS: UTF-8, no ASCII escaping of non-ASCII,
object keys sorted by UTF-16 code units, ES6 NumberToString. Integers outside
[-(2^53)+1, 2^53-1] are rejected rather than silently rounded.
"""

from __future__ import annotations

import math
from typing import Any

SAFE_INTEGER_MAX = (1 << 53) - 1
SAFE_INTEGER_MIN = -SAFE_INTEGER_MAX

_ESCAPE = {
    ord('"'): '\\"',
    ord("\\"): "\\\\",
    ord("\b"): "\\b",
    ord("\t"): "\\t",
    ord("\n"): "\\n",
    ord("\f"): "\\f",
    ord("\r"): "\\r",
}


class CanonicalizeError(ValueError):
    """Claim or args cannot be serialized under the toa/0.1 JCS profile."""


def canonical_json(value: Any) -> bytes:
    """Return RFC 8785 JCS bytes (UTF-8, no trailing newline)."""
    return canonicalize_to_string(value).encode("utf-8")


def canonicalize_to_string(value: Any) -> str:
    return _serialize(value)


def _serialize(value: Any) -> str:
    if value is None:
        return "null"
    if value is True:
        return "true"
    if value is False:
        return "false"
    if isinstance(value, str):
        return _serialize_string(value)
    if isinstance(value, int) and not isinstance(value, bool):
        return _serialize_int(value)
    if isinstance(value, float):
        return _serialize_float(value)
    if isinstance(value, list):
        return "[" + ",".join(_serialize(item) for item in value) + "]"
    if isinstance(value, tuple):
        return "[" + ",".join(_serialize(item) for item in value) + "]"
    if isinstance(value, dict):
        keys = sorted(value.keys(), key=lambda k: _utf16_sort_key(k))
        parts = []
        for key in keys:
            if not isinstance(key, str):
                raise CanonicalizeError("jcs_key_not_string")
            parts.append(_serialize_string(key) + ":" + _serialize(value[key]))
        return "{" + ",".join(parts) + "}"
    raise CanonicalizeError(f"jcs_unsupported_type:{type(value).__name__}")


def _utf16_sort_key(key: str) -> bytes:
    return key.encode("utf-16-be")


def _serialize_string(value: str) -> str:
    out = ['"']
    for ch in value:
        o = ord(ch)
        esc = _ESCAPE.get(o)
        if esc is not None:
            out.append(esc)
        elif o < 0x20:
            out.append(f"\\u{o:04x}")
        else:
            out.append(ch)
    out.append('"')
    return "".join(out)


def _serialize_int(value: int) -> str:
    if value > SAFE_INTEGER_MAX or value < SAFE_INTEGER_MIN:
        raise CanonicalizeError("unsafe_json_integer")
    return str(value)


def _serialize_float(value: float) -> str:
    if not math.isfinite(value):
        raise CanonicalizeError("non_finite_number")
    if value.is_integer():
        as_int = int(value)
        if as_int > SAFE_INTEGER_MAX or as_int < SAFE_INTEGER_MIN:
            raise CanonicalizeError("unsafe_json_integer")
        return str(as_int)
    return _es6_number_to_string(value)


def _es6_number_to_string(value: float) -> str:
    """
    ECMAScript NumberToString (RFC 8785 §3.2.2).

    Post-processes Python's unique float string so 1.0 → 1, exponents match
    V8/JSON.stringify, and -0 becomes 0.
    """
    if value == 0.0:
        return "0"
    text = str(float(value))
    if "n" in text.lower():
        raise CanonicalizeError("non_finite_number")
    sign = ""
    if text[0] == "-":
        sign = "-"
        text = text[1:]
    exp_str = ""
    exp_val = 0
    q = text.find("e")
    if q > 0:
        exp_str = text[q:]
        if exp_str[2:3] == "0":
            exp_str = exp_str[:2] + exp_str[3:]
        text = text[:q]
        exp_val = int(exp_str[1:])
    first = text
    dot = ""
    last = ""
    q = text.find(".")
    if q > 0:
        dot = "."
        first = text[:q]
        last = text[q + 1 :]
    if last == "0":
        dot = ""
        last = ""
    if 0 < exp_val < 21:
        first = first + last
        last = ""
        dot = ""
        exp_str = ""
        pad = exp_val - len(first)
        while pad >= 0:
            pad -= 1
            first += "0"
    elif -7 < exp_val < 0:
        last = first + last
        first = "0"
        dot = "."
        exp_str = ""
        q = exp_val
        while q < -1:
            q += 1
            last = "0" + last
    return sign + first + dot + last + exp_str
