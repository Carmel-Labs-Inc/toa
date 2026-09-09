"""MCP extension AttestationBinding validation + attach for `dev.agentstatus/toa`."""

from .attach import (
    TOA_ERROR_CODE,
    attach_binding_to_result,
    attach_signed_document,
    build_claim,
    embedded_binding,
    enforce_client_require,
    reference_binding,
    should_attach,
    toa_failure_error,
)
from .binding import (
    ClientSettings,
    EXTENSION_ID,
    default_min_layers,
    layer_satisfies,
    validate_binding,
)
from .negotiation import (
    ABSENCE_ATTESTATION_GAP,
    ABSENCE_KEY_UNAVAILABLE,
    ABSENCE_NEGATIVE,
    ABSENCE_OUTSIDE_TOA,
    ABSENCE_POSITIVE,
    ABSENCE_UNTRUSTED_KEY,
    NEGOTIATION_SPEC,
    REVOCATION_INVALID_IF_REVOKED_NOW,
    REVOCATION_VALID_AT_OBSERVED,
    build_negotiation_record,
    classify_absence,
    document_is_negative_evidence,
    evaluate_revocation,
    key_fingerprint,
    negotiation_from_initialize,
    pin_matches_document,
    validate_negotiation_record,
)

__all__ = [
    "ABSENCE_ATTESTATION_GAP",
    "ABSENCE_KEY_UNAVAILABLE",
    "ABSENCE_NEGATIVE",
    "ABSENCE_OUTSIDE_TOA",
    "ABSENCE_POSITIVE",
    "ABSENCE_UNTRUSTED_KEY",
    "ClientSettings",
    "EXTENSION_ID",
    "NEGOTIATION_SPEC",
    "REVOCATION_INVALID_IF_REVOKED_NOW",
    "REVOCATION_VALID_AT_OBSERVED",
    "TOA_ERROR_CODE",
    "attach_binding_to_result",
    "attach_signed_document",
    "build_claim",
    "build_negotiation_record",
    "classify_absence",
    "default_min_layers",
    "document_is_negative_evidence",
    "embedded_binding",
    "enforce_client_require",
    "evaluate_revocation",
    "key_fingerprint",
    "layer_satisfies",
    "negotiation_from_initialize",
    "pin_matches_document",
    "reference_binding",
    "should_attach",
    "toa_failure_error",
    "validate_binding",
    "validate_negotiation_record",
]
__version__ = "0.1.0"

try:
    from .mcp_sdk import ToaAttachExtension  # noqa: F401

    __all__.append("ToaAttachExtension")
except ImportError:
    pass
