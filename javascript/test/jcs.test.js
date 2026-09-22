import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import test from "node:test";
import {
  CanonicalizeError,
  canonicalizeToString,
  rawJsonHasUnsafeIntegerLiteral,
} from "../src/jcs.js";
import { parseObservedAt, verifyDocument } from "../src/verify.js";

const here = dirname(fileURLToPath(import.meta.url));
const root = join(here, "..", "..");
const signedExample = JSON.parse(
  readFileSync(join(root, "examples", "signed-example.json"), "utf8")
);

test("JCS keeps raw unicode and collapses 1.0 to 1", () => {
  assert.equal(canonicalizeToString({ n: 1.0 }), '{"n":1}');
  assert.equal(canonicalizeToString({ q: "café" }), '{"q":"café"}');
  assert.equal(canonicalizeToString({ q: "😀 ok" }), '{"q":"😀 ok"}');
  assert.ok(!canonicalizeToString({ q: "≥" }).includes("\\u"));
});

test("unsafe integer fails closed", () => {
  assert.throws(() => canonicalizeToString({ n: 9007199254740992 }), CanonicalizeError);
  assert.equal(rawJsonHasUnsafeIntegerLiteral('{"n":9007199254740993}'), true);
  assert.equal(rawJsonHasUnsafeIntegerLiteral('{"n":1}'), false);
  assert.equal(rawJsonHasUnsafeIntegerLiteral('{"q":"9007199254740993"}'), false);
});

test("naive observed_at is rejected", () => {
  assert.equal(parseObservedAt("2026-09-20T22:45:12"), null);
  assert.ok(parseObservedAt("2026-09-20T22:45:12Z"));
  assert.ok(parseObservedAt("2026-09-20T22:45:12+00:00"));
  const naive = { ...signedExample, observed_at: "2026-09-20T22:45:12" };
  const result = verifyDocument(naive, { requireEmitter: "agentstatus" });
  assert.equal(result.valid, false);
});

test("unicode_float fixture verifies", () => {
  const pub = JSON.parse(
    readFileSync(
      join(root, "mcp-extension", "conformance", "fixtures", "keys", "toa-conformance-test-v1.json"),
      "utf8"
    )
  );
  const raw = readFileSync(
    join(root, "mcp-extension", "conformance", "fixtures", "unicode_float.json"),
    "utf8"
  );
  assert.match(raw, /café/);
  assert.match(raw, /≥/);
  assert.match(raw, /😀/);
  assert.match(raw, /"score": 1\.0/);
  const doc = JSON.parse(raw);
  const result = verifyDocument(doc, { publicKey: pub, requireEmitter: "toa-conformance" });
  assert.equal(result.valid, true, result.reason);
});
