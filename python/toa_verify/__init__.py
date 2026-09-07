"""Tool Outcome Attestation (toa/0.1) — verify only."""

from .verify import (
    DEFAULT_ALG,
    args_hash_for,
    claim_for_signing,
    parse_max_age_seconds,
    resolve_alg,
    verify_document,
)
from .sign import payload_hash_for_claim, sign_document

__all__ = [
    "DEFAULT_ALG",
    "args_hash_for",
    "claim_for_signing",
    "parse_max_age_seconds",
    "payload_hash_for_claim",
    "resolve_alg",
    "sign_document",
    "verify_document",
]
__version__ = "0.1.0"
