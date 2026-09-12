"""NegotiationRecord + offline absence / key-pin classification."""

from __future__ import annotations

from pathlib import Path

from toa_ext.negotiation import (
    ABSENCE_ATTESTATION_GAP,
    ABSENCE_INCONSISTENT,
    ABSENCE_KEY_UNAVAILABLE,
    ABSENCE_NEGATIVE,
    ABSENCE_OUTSIDE_TOA,
    ABSENCE_POSITIVE,
    ABSENCE_REVOCATION_UNAVAILABLE,
    ABSENCE_UNTRUSTED_KEY,
    NEGOTIATION_SPEC,
    REVOCATION_INVALID_IF_REVOKED_NOW,
    REVOCATION_VALID_AT_OBSERVED,
    build_negotiation_record,
    classify_absence,
    document_claims_are_inconsistent,
    document_is_negative_evidence,
    evaluate_revocation,
    key_fingerprint,
    negotiation_from_initialize,
    pin_matches_document,
    validate_negotiation_record,
)

ROOT = Path(__file__).resolve().parents[2]
PUB = ROOT / "mcp-extension" / "conformance" / "fixtures" / "keys" / "toa-conformance-test-v1.json"


def test_build_and_validate_negotiation_record():
    rec = build_negotiation_record(
        server_id="s1",
        protocol_version="2026-07-28",
        server_advertised_toa=True,
        server_settings={"attach": "on_require"},
        client_settings={"require": True},
        pinned_public_key_id="test-v1",
        pinned_key_fingerprint=key_fingerprint(PUB),
        transport="stdio",
    )
    assert rec["spec"] == NEGOTIATION_SPEC
    assert validate_negotiation_record(rec)["valid"] is True
    assert rec["transport"] == "stdio"


def test_negotiation_from_initialize_advertised():
    init = {
        "protocolVersion": "2026-07-28",
        "capabilities": {
            "extensions": {
                "dev.agentstatus/toa": {
                    "attach": "always",
                    "supportedEmitterRoles": ["third_party"],
                }
            }
        },
    }
    rec = negotiation_from_initialize(
        init,
        server_id="srv",
        pinned_public_key_id="v1",
        pinned_emitter_name="toa-conformance",
    )
    assert rec["server_advertised_toa"] is True
    assert rec["server_settings"]["attach"] == "always"
    assert rec["pinned_public_key_id"] == "v1"


def test_negotiation_from_initialize_not_advertised():
    init = {"protocolVersion": "2025-06-18", "capabilities": {"tools": {}}}
    rec = negotiation_from_initialize(init, server_id="srv")
    assert rec["server_advertised_toa"] is False
    assert rec["server_settings"] is None


def test_classify_outside_vs_gap_distinct():
    never = build_negotiation_record(
        server_id="a", protocol_version="2026-07-28", server_advertised_toa=False
    )
    yes = build_negotiation_record(
        server_id="a", protocol_version="2026-07-28", server_advertised_toa=True
    )
    c1 = classify_absence(negotiation=never, attestation_present=False, attach_expected=True)
    c2 = classify_absence(negotiation=yes, attestation_present=False, attach_expected=True)
    assert c1["class"] == ABSENCE_OUTSIDE_TOA
    assert c2["class"] == ABSENCE_ATTESTATION_GAP
    assert c1["class"] != c2["class"]


def test_classify_positive_and_negative():
    yes = build_negotiation_record(
        server_id="a", protocol_version="2026-07-28", server_advertised_toa=True
    )
    pos = classify_absence(
        negotiation=yes,
        attestation_present=True,
        document={"disposition": "delivered", "layers": {"functional": "pass"}},
        attach_expected=True,
    )
    neg = classify_absence(
        negotiation=yes,
        attestation_present=True,
        document={"disposition": "failed", "layers": {"functional": "fail"}},
        attach_expected=True,
    )
    assert pos["class"] == ABSENCE_POSITIVE
    assert neg["class"] == ABSENCE_NEGATIVE


def test_document_is_negative_from_layers_without_disposition():
    assert document_is_negative_evidence({"layers": {"functional": "fail"}}) is True
    assert document_is_negative_evidence({"disposition": "delivered", "layers": {}}) is False


def test_delivered_plus_failing_layer_is_inconsistent_not_positive():
    """René #3350: disposition=delivered must not short-circuit failing layers."""
    doc = {"disposition": "delivered", "layers": {"functional": "fail"}}
    assert document_is_negative_evidence(doc) is True
    assert document_claims_are_inconsistent(doc) is True
    yes = build_negotiation_record(
        server_id="a", protocol_version="2026-07-28", server_advertised_toa=True
    )
    classified = classify_absence(
        negotiation=yes,
        attestation_present=True,
        document=doc,
        attach_expected=True,
    )
    assert classified["class"] == ABSENCE_INCONSISTENT
    assert classified["class"] != ABSENCE_POSITIVE
    assert classified["reason"] == "disposition_delivered_with_failing_core_layer"


def test_classify_key_unavailable_not_gap():
    yes = build_negotiation_record(
        server_id="a",
        protocol_version="2026-07-28",
        server_advertised_toa=True,
        pinned_public_key_id="test-v1",
    )
    doc = {"disposition": "delivered", "emitter": {"name": "toa-conformance", "key_id": "test-v1"}}
    c = classify_absence(
        negotiation=yes,
        attestation_present=True,
        document=doc,
        public_key_available=False,
    )
    gap = classify_absence(negotiation=yes, attestation_present=False, attach_expected=True)
    assert c["class"] == ABSENCE_KEY_UNAVAILABLE
    assert gap["class"] == ABSENCE_ATTESTATION_GAP
    assert c["class"] != gap["class"]


def test_classify_untrusted_key_not_gap():
    yes = build_negotiation_record(
        server_id="a", protocol_version="2026-07-28", server_advertised_toa=True
    )
    doc = {"disposition": "delivered", "emitter": {"name": "x", "key_id": "y"}}
    c = classify_absence(
        negotiation=yes,
        attestation_present=True,
        document=doc,
        key_matches_pin=False,
    )
    assert c["class"] == ABSENCE_UNTRUSTED_KEY


def test_pin_matches_and_fingerprint():
    fp = key_fingerprint(PUB)
    rec = build_negotiation_record(
        server_id="a",
        protocol_version="2026-07-28",
        server_advertised_toa=True,
        pinned_public_key_id="test-v1",
        pinned_key_fingerprint=fp,
        pinned_emitter_name="toa-conformance",
    )
    doc = {
        "public_key_id": "test-v1",
        "emitter": {"name": "toa-conformance", "key_id": "test-v1"},
    }
    assert pin_matches_document(rec, doc, public_key=PUB) is True
    doc_bad = {
        "public_key_id": "other",
        "emitter": {"name": "toa-conformance", "key_id": "other"},
    }
    assert pin_matches_document(rec, doc_bad, public_key=PUB) is False


def test_evaluate_revocation_policies():
    ledger_ok = evaluate_revocation(
        observed_at="2026-01-01T00:00:00Z",
        key_revoked_at="2026-06-01T00:00:00Z",
        policy=REVOCATION_VALID_AT_OBSERVED,
    )
    assert ledger_ok["acceptable"] is True

    after_revoke = evaluate_revocation(
        observed_at="2026-07-01T00:00:00Z",
        key_revoked_at="2026-06-01T00:00:00Z",
        policy=REVOCATION_VALID_AT_OBSERVED,
    )
    assert after_revoke["acceptable"] is False

    strict = evaluate_revocation(
        observed_at="2026-01-01T00:00:00Z",
        key_revoked_at="2026-06-01T00:00:00Z",
        policy=REVOCATION_INVALID_IF_REVOKED_NOW,
        now=__import__("datetime").datetime(2026, 9, 1, tzinfo=__import__("datetime").timezone.utc),
    )
    assert strict["acceptable"] is False


def test_evaluate_revocation_requires_explicit_policy_when_revoked():
    unspecified = evaluate_revocation(
        observed_at="2026-01-01T00:00:00Z",
        key_revoked_at="2026-06-01T00:00:00Z",
    )
    assert unspecified["acceptable"] is False
    assert unspecified["reason"] == "revocation_policy_unspecified"

    rec = build_negotiation_record(
        server_id="a",
        protocol_version="2026-07-28",
        server_advertised_toa=True,
        revocation_policy=REVOCATION_VALID_AT_OBSERVED,
    )
    from_record = evaluate_revocation(
        observed_at="2026-01-01T00:00:00Z",
        key_revoked_at="2026-06-01T00:00:00Z",
        negotiation=rec,
    )
    assert from_record["acceptable"] is True
    assert from_record["policy"] == REVOCATION_VALID_AT_OBSERVED

    no_revoke = evaluate_revocation(observed_at="2026-01-01T00:00:00Z")
    assert no_revoke["acceptable"] is True
    assert no_revoke["reason"] == "key_not_revoked"


def test_gate_without_revocation_source_is_unavailable_not_accept():
    """Sattyam #3350: invalid_if_revoked_now with no source must not pass."""
    gate = evaluate_revocation(
        observed_at="2026-01-01T00:00:00Z",
        policy=REVOCATION_INVALID_IF_REVOKED_NOW,
    )
    assert gate["acceptable"] is False
    assert gate["reason"] == ABSENCE_REVOCATION_UNAVAILABLE
    assert gate["source_consulted"] is False

    checked_clean = evaluate_revocation(
        observed_at="2026-01-01T00:00:00Z",
        policy=REVOCATION_INVALID_IF_REVOKED_NOW,
        revocation_checked=True,
    )
    assert checked_clean["acceptable"] is True
    assert checked_clean["reason"] == "key_not_revoked"
    assert checked_clean["source_consulted"] is True

    ledger = evaluate_revocation(
        observed_at="2026-01-01T00:00:00Z",
        policy=REVOCATION_VALID_AT_OBSERVED,
    )
    assert ledger["acceptable"] is True
    assert ledger["reason"] == "key_not_revoked"

    rec = build_negotiation_record(
        server_id="a",
        protocol_version="2026-07-28",
        server_advertised_toa=True,
        revocation_policy=REVOCATION_INVALID_IF_REVOKED_NOW,
    )
    classified = classify_absence(
        negotiation=rec,
        attestation_present=True,
        document={"disposition": "delivered", "layers": {"functional": "pass"}},
        revocation_result=gate,
    )
    gap = classify_absence(negotiation=rec, attestation_present=False, attach_expected=True)
    untrusted = classify_absence(
        negotiation=rec,
        attestation_present=True,
        document={"disposition": "delivered"},
        key_matches_pin=False,
    )
    assert classified["class"] == ABSENCE_REVOCATION_UNAVAILABLE
    assert classified["class"] != gap["class"]
    assert classified["class"] != untrusted["class"]
    assert classified["class"] != ABSENCE_POSITIVE
