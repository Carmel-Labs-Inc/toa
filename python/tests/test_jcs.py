"""RFC 8785 JCS + observed_at offset + Python/JS interop."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from toa_verify import args_hash_for, sign_document, verify_document
from toa_verify.jcs import CanonicalizeError, canonical_json, canonicalize_to_string
from toa_verify.verify import parse_observed_at

ROOT = Path(__file__).resolve().parents[2]
PRIV = ROOT / "mcp-extension" / "conformance" / "fixtures" / "keys" / "toa-conformance-test-v1.private.json"
PUB = ROOT / "mcp-extension" / "conformance" / "fixtures" / "keys" / "toa-conformance-test-v1.json"


def _js_canonicalize(value) -> str:
    script = (
        "import { canonicalizeToString } from './javascript/src/jcs.js';"
        f"console.log(canonicalizeToString({json.dumps(value, ensure_ascii=False)}));"
    )
    proc = subprocess.run(
        ["node", "--input-type=module", "-e", script],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr or proc.stdout)
    return proc.stdout.strip()


def test_jcs_ascii_and_unicode_and_float():
    cases = [
        ({"a": 1, "b": 2}, '{"a":1,"b":2}'),
        ({"n": 1.0}, '{"n":1}'),
        ({"q": "café"}, '{"q":"café"}'),
        ({"q": "latency ≥ 200 ms"}, '{"q":"latency ≥ 200 ms"}'),
        ({"q": "😀 ok"}, '{"q":"😀 ok"}'),
        ({"n": 1.5}, '{"n":1.5}'),
    ]
    for value, expected in cases:
        got = canonicalize_to_string(value)
        assert got == expected, (value, got, expected)
        assert canonical_json(value) == expected.encode("utf-8")


def test_jcs_matches_js_verifier():
    values = [
        {"a": 1, "b": 2},
        {"n": 1.0},
        {"q": "café"},
        {"q": "😀 ok"},
        {"n": 1.5},
        {"z": "latency ≥ 200 ms — café", "n": 1.0},
    ]
    for value in values:
        py = canonicalize_to_string(value)
        js = _js_canonicalize(value)
        assert py == js, (value, py, js)


def test_jcs_rejects_unsafe_integer():
    with pytest.raises(CanonicalizeError, match="unsafe_json_integer"):
        canonicalize_to_string({"n": 9007199254740993})


def test_args_hash_unicode_float_agrees_with_js():
    args = {"q": "café", "n": 1.0}
    digest = args_hash_for(args)
    script = (
        "import { createHash } from 'node:crypto';"
        "import { canonicalJson } from './javascript/src/jcs.js';"
        f"const d=createHash('sha256').update(canonicalJson({json.dumps(args, ensure_ascii=False)})).digest('hex');"
        "console.log('sha256:'+d);"
    )
    proc = subprocess.run(
        ["node", "--input-type=module", "-e", script],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    assert digest == proc.stdout.strip()
    assert args_hash_for({"q": "cafe", "n": 1}) != digest


def test_naive_observed_at_rejected():
    assert parse_observed_at("2026-09-20T22:45:12") is None
    assert parse_observed_at("2026-09-20T22:45:12Z") is not None
    assert parse_observed_at("2026-09-20T22:45:12+00:00") is not None


def test_sign_and_verify_unicode_float_roundtrip():
    from toa_ext.attach import build_claim

    claim = build_claim(
        tool_name="echo",
        server_id="jcs",
        decision_id="jcs-1",
        agent_id="a1",
        layers={
            "reach": "pass",
            "invoke": "pass",
            "functional": "pass",
            "shape": "n/a",
            "openapi_fidelity": "n/a",
            "compositional": "n/a",
            "score": 1.0,
        },
        emitter_name="toa-conformance",
        emitter_key_id="test-v1",
        reasons=["latency ≥ 200 ms — café", "😀 ok"],
        disposition="delivered",
        args_hash=args_hash_for({"q": "café", "n": 1.0}),
        observed_at="2026-09-20T22:45:12Z",
    )
    doc = sign_document(claim, private_key=PRIV, public_key_id="test-v1")
    ok = verify_document(doc, public_key=PUB, require_emitter="toa-conformance")
    assert ok["valid"] is True, ok

    naive = dict(doc)
    naive["observed_at"] = "2026-09-20T22:45:12"
    # Tampered field is signed; signature will fail first. Build unsigned-naive via claim.
    unsigned = {k: v for k, v in claim.items()}
    unsigned["observed_at"] = "2026-09-20T22:45:12"
    with pytest.raises(ValueError, match="observed_at_missing_offset"):
        sign_document(unsigned, private_key=PRIV, public_key_id="test-v1")


def test_existing_ascii_fixture_still_verifies():
    doc = json.loads(
        (ROOT / "mcp-extension" / "conformance" / "fixtures" / "pass_functional.json").read_text()
    )
    # Conformance fixture uses the test key, not AgentStatus v1.
    result = verify_document(doc, public_key=PUB, require_emitter="toa-conformance")
    assert result["valid"] is True, result


def test_unicode_float_fixture_verifies_in_python_and_js():
    path = ROOT / "mcp-extension" / "conformance" / "fixtures" / "unicode_float.json"
    raw = path.read_text(encoding="utf-8")
    assert "café" in raw and "≥" in raw and "😀" in raw
    assert '"score": 1.0' in raw
    doc = json.loads(raw)
    result = verify_document(doc, public_key=PUB, require_emitter="toa-conformance")
    assert result["valid"] is True, result
    assert doc["args_hash"] == args_hash_for({"q": "café", "n": 1.0})
    proc = subprocess.run(
        [
            "node",
            str(ROOT / "javascript" / "src" / "cli.js"),
            str(path),
            "--public-key",
            str(PUB),
            "--require-emitter",
            "toa-conformance",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stdout or proc.stderr
    js_result = json.loads(proc.stdout)
    assert js_result["valid"] is True


def test_jcs_utf16_key_sort_and_negative_zero():
    value = {"€": 1, "a": 2, "😀": 3}
    expected = canonicalize_to_string(value)
    assert _js_canonicalize(value) == expected
    assert canonicalize_to_string(-0.0) == "0"
    assert _js_canonicalize(-0.0) == "0"
