#!/usr/bin/env node
import { readFileSync } from "node:fs";
import { verifyDocument } from "./verify.js";

function usage() {
  console.error(`Usage: toa-verify <document.json> [--public-key keys/v1.json] [--require-emitter agentstatus] [--require-layer functional=pass]`);
  process.exit(2);
}

const args = process.argv.slice(2);
if (!args.length || args.includes("-h") || args.includes("--help")) usage();

const path = args[0];
const opts = {};
const requireLayers = [];
for (let i = 1; i < args.length; i++) {
  if (args[i] === "--public-key") opts.publicKey = args[++i];
  else if (args[i] === "--require-emitter") opts.requireEmitter = args[++i];
  else if (args[i] === "--require-layer") requireLayers.push(args[++i]);
  else usage();
}

const doc = JSON.parse(readFileSync(path, "utf8"));
const result = verifyDocument(doc, opts);
if (!result.valid) {
  console.log(JSON.stringify(result, null, 2));
  process.exit(1);
}

const layers = result.layers || {};
for (const req of requireLayers) {
  const [layer, want] = req.split("=");
  if (layers[layer] !== want) {
    console.log(
      JSON.stringify(
        { valid: false, reason: `layer_mismatch:${layer}`, expected: want, got: layers[layer] },
        null,
        2
      )
    );
    process.exit(1);
  }
}

console.log(JSON.stringify(result, null, 2));
