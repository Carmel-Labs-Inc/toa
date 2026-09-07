"""NegotiationRecord + offline absence classification."""

from __future__ import annotations

from toa_ext.negotiation import (
    ABSENCE_ATTESTATION_GAP,
    ABSENCE_NEGATIVE,
    ABSENCE_OUTSIDE_TOA,
    ABSENCE_POSITIVE,
    NEGOTIATION_SPEC,
    build_negotiation_record,
    classify_absence,
    document_is_negative_evidence,
    negotiation_from_initialize,
    validate_negotiation_record,
)


def test_build_and_validate_negotiation_record():
    rec = build_negotiation_record(
        server_id="s1",
        protocol_version="2026-07-28",
        server_advertised_toa=True,
        server_settings={"attach": "on_require"},
        client_settings={"require": True},
    )
    assert rec["spec"] == NEGOTIATION_SPEC
    assert validate_negotiation_record(rec)["valid"] is True


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
    rec = negotiation_from_initialize(init, server_id="srv")
    assert rec["server_advertised_toa"] is True
    assert rec["server_settings"]["attach"] == "always"


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
