/**
 * Verify Tool Outcome Attestation documents (toa/0.1).
 * Ed25519 over canonical JSON of signed claim fields.
 */

import { createPublicKey, verify } from "node:crypto";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

export const TOA_SPEC = "toa/0.1";

export const SIGNED_KEYS = [
  "spec",
  "toa_id",
  "tool",
  "run",
  "observed_at",
  "layers",
  "outcome_grade",
  "business_outcome_ok",
  "reasons",
  "emitter",
];

export function canonicalJson(payload) {
  return Buffer.from(JSON.stringify(payload, Object.keys(payload).sort()), "utf8");
}

/** Stable canonical JSON: sort keys recursively via replacer pattern. */
export function canonicalJsonSorted(value) {
  return Buffer.from(_stableStringify(value), "utf8");
}

function _stableStringify(value) {
  if (value === null || typeof value !== "object") {
    return JSON.stringify(value);
  }
  if (Array.isArray(value)) {
    return `[${value.map((v) => _stableStringify(v)).join(",")}]`;
  }
  const keys = Object.keys(value).sort();
  return `{${keys.map((k) => `${JSON.stringify(k)}:${_stableStringify(value[k])}`).join(",")}}`;
}

export function claimForSigning(document) {
  const out = {};
  for (const k of SIGNED_KEYS) {
    if (Object.prototype.hasOwnProperty.call(document, k)) {
      out[k] = document[k];
    }
  }
  return out;
}

function loadPublicKeyRaw(keyMaterial) {
  if (Buffer.isBuffer(keyMaterial) && keyMaterial.length === 32) {
    return keyMaterial;
  }
  if (typeof keyMaterial === "object" && keyMaterial !== null && keyMaterial.public_key) {
    return Buffer.from(keyMaterial.public_key, "base64");
  }
  if (typeof keyMaterial === "string") {
    const s = keyMaterial.trim();
    if (s.startsWith("{")) {
      return loadPublicKeyRaw(JSON.parse(s));
    }
    // path?
    if (s.endsWith(".json") || s.includes("/")) {
      try {
        return loadPublicKeyRaw(JSON.parse(readFileSync(s, "utf8")));
      } catch {
        /* fall through to base64 */
      }
    }
    return Buffer.from(s, "base64");
  }
  throw new Error("unsupported public key material");
}

export function defaultAgentstatusV1KeyPath() {
  const here = dirname(fileURLToPath(import.meta.url));
  return join(here, "..", "..", "keys", "agentstatus-v1.json");
}


export function parseMaxAgeSeconds(value) {
  if (typeof value === "number") {
    if (value < 0 || !Number.isFinite(value)) throw new Error("max_age must be non-negative");
    return Math.floor(value);
  }
  const s = String(value).trim().toLowerCase();
  const m = s.match(/^(\d+)\s*([smhd]?)$/);
  if (!m) throw new Error(`bad_max_age:${value}`);
  const n = Number(m[1]);
  const unit = m[2] || "s";
  const mult = { s: 1, m: 60, h: 3600, d: 86400 }[unit];
  return n * mult;
}

export function parseObservedAt(value) {
  if (typeof value !== "string" || !value.trim()) return null;
  const s = value.trim();
  const d = new Date(s);
  if (Number.isNaN(d.getTime())) return null;
  return d;
}

/**
 * @param {object} document
 * @param {{ publicKey?: any, requireEmitter?: string, maxAgeSeconds?: number, now?: Date }} [opts]
 */
export function verifyDocument(document, opts = {}) {
  if (!document || typeof document !== "object") {
    return { valid: false, reason: "not_an_object" };
  }
  if (document.spec !== TOA_SPEC) {
    return { valid: false, reason: `unsupported_spec:${document.spec}` };
  }
  if (!document.signature || typeof document.signature !== "string") {
    return { valid: false, reason: "missing_signature" };
  }

  const body = claimForSigning(document);
  const emitter = body.emitter && typeof body.emitter === "object" ? body.emitter : {};
  if (opts.requireEmitter && emitter.name !== opts.requireEmitter) {
    return {
      valid: false,
      reason: `emitter_mismatch:${emitter.name}`,
      claim: body,
    };
  }

  let keyRaw;
  try {
    const material =
      opts.publicKey ??
      JSON.parse(readFileSync(defaultAgentstatusV1KeyPath(), "utf8"));
    keyRaw = loadPublicKeyRaw(material);
  } catch (err) {
    return { valid: false, reason: `no_public_key_configured:${err.message}` };
  }

  const keyObject = createPublicKey({
    key: Buffer.concat([
      // SPKI prefix for Ed25519 raw 32-byte key
      Buffer.from("302a300506032b6570032100", "hex"),
      keyRaw,
    ]),
    format: "der",
    type: "spki",
  });

  const message = canonicalJsonSorted(body);
  const sig = Buffer.from(document.signature, "base64");
  const ok = verify(null, message, keyObject, sig);
  if (!ok) {
    return { valid: false, reason: "invalid_signature", claim: body };
  }

  if (opts.maxAgeSeconds != null) {
    const observed = parseObservedAt(body.observed_at);
    if (!observed) {
      return { valid: false, reason: "missing_or_invalid_observed_at", claim: body };
    }
    const ref = opts.now instanceof Date ? opts.now : new Date();
    const age = (ref.getTime() - observed.getTime()) / 1000;
    if (age < 0) {
      return { valid: false, reason: "observed_at_in_future", claim: body, age_seconds: age };
    }
    if (age > opts.maxAgeSeconds) {
      return {
        valid: false,
        reason: "stale_attestation",
        claim: body,
        age_seconds: Math.floor(age),
        max_age_seconds: opts.maxAgeSeconds,
      };
    }
  }

  return {
    valid: true,
    reason: "ok",
    claim: body,
    toa_id: body.toa_id,
    layers: body.layers,
    tool: body.tool,
    observed_at: body.observed_at,
    business_outcome_ok: body.business_outcome_ok,
    outcome_grade: body.outcome_grade,
    public_key_id: document.public_key_id || emitter.key_id,
  };
}
