/**
 * Node built-in tests for args_hash + alg envelope.
 * Run: node --test test/args_hash_alg.test.js
 */
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import test from "node:test";
import {
  DEFAULT_ALG,
  argsHashFor,
  resolveAlg,
  verifyDocument,
} from "../src/verify.js";

const here = dirname(fileURLToPath(import.meta.url));
const root = join(here, "..", "..");
const signedExample = JSON.parse(
  readFileSync(join(root, "examples", "signed-example.json"), "utf8")
);

test("argsHashFor is order-stable", () => {
  assert.equal(argsHashFor({ a: 1, b: 2 }), argsHashFor({ b: 2, a: 1 }));
  assert.match(argsHashFor({ text: "hi" }), /^sha256:[a-f0-9]{64}$/);
});

test("legacy doc without alg still verifies as Ed25519", () => {
  assert.equal(resolveAlg({}), DEFAULT_ALG);
  assert.equal(resolveAlg(signedExample), DEFAULT_ALG);
  const result = verifyDocument(signedExample, { requireEmitter: "agentstatus" });
  assert.equal(result.valid, true);
  assert.equal(result.alg, DEFAULT_ALG);
});

test("unsupported alg fails closed", () => {
  const doc = { ...signedExample, alg: "ML-DSA-65" };
  const result = verifyDocument(doc);
  assert.equal(result.valid, false);
  assert.match(result.reason, /^unsupported_algorithm:/);
});

test("requireArgsHash fails when args_hash absent", () => {
  const result = verifyDocument(signedExample, {
    requireEmitter: "agentstatus",
    requireArgsHash: true,
  });
  assert.equal(result.valid, false);
  assert.equal(result.reason, "missing_args_hash");
});
