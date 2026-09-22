/**
 * RFC 8785 JSON Canonicalization Scheme (JCS) for toa/0.1.
 *
 * UTF-8, raw non-ASCII, keys sorted by UTF-16 code units (JS default),
 * ES6 NumberToString via JSON.stringify. Integers outside
 * [-(2^53)+1, 2^53-1] fail closed.
 */

export const SAFE_INTEGER_MAX = Number.MAX_SAFE_INTEGER;
export const SAFE_INTEGER_MIN = -Number.MAX_SAFE_INTEGER;

export class CanonicalizeError extends Error {
  constructor(code) {
    super(code);
    this.name = "CanonicalizeError";
    this.code = code;
  }
}

export function canonicalJson(value) {
  return Buffer.from(canonicalizeToString(value), "utf8");
}

export function canonicalizeToString(value) {
  return _serialize(value);
}

function _serialize(value) {
  if (value === null) return "null";
  const t = typeof value;
  if (t === "boolean") return value ? "true" : "false";
  if (t === "number") return _serializeNumber(value);
  if (t === "string") return JSON.stringify(value);
  if (Array.isArray(value)) {
    return `[${value.map(_serialize).join(",")}]`;
  }
  if (t === "object") {
    const keys = Object.keys(value).sort();
    return `{${keys.map((k) => `${JSON.stringify(k)}:${_serialize(value[k])}`).join(",")}}`;
  }
  throw new CanonicalizeError(`jcs_unsupported_type:${t}`);
}

function _serializeNumber(value) {
  if (!Number.isFinite(value)) {
    throw new CanonicalizeError("non_finite_number");
  }
  if (Number.isInteger(value) && !Number.isSafeInteger(value)) {
    throw new CanonicalizeError("unsafe_json_integer");
  }
  return JSON.stringify(value);
}

/**
 * Scan raw JSON text for integer literals outside the IEEE 754 safe range.
 * Needed because JSON.parse silently rounds 2^53+1 before JCS can see it.
 */
export function rawJsonHasUnsafeIntegerLiteral(text) {
  if (typeof text !== "string") return false;
  let i = 0;
  const n = text.length;
  while (i < n) {
    const ch = text[i];
    if (ch === '"') {
      i += 1;
      while (i < n) {
        if (text[i] === "\\") {
          i += 2;
          continue;
        }
        if (text[i] === '"') {
          i += 1;
          break;
        }
        i += 1;
      }
      continue;
    }
    if (ch === "-" || (ch >= "0" && ch <= "9")) {
      const start = i;
      if (text[i] === "-") i += 1;
      if (i >= n || text[i] < "0" || text[i] > "9") {
        i = start + 1;
        continue;
      }
      while (i < n && text[i] >= "0" && text[i] <= "9") i += 1;
      const digits = text.slice(start, i);
      const next = i < n ? text[i] : "";
      if (next === "." || next === "e" || next === "E") {
        continue;
      }
      try {
        const v = BigInt(digits);
        if (v > BigInt(SAFE_INTEGER_MAX) || v < BigInt(SAFE_INTEGER_MIN)) {
          return true;
        }
      } catch {
        return true;
      }
      continue;
    }
    i += 1;
  }
  return false;
}
