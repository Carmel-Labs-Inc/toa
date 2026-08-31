"""Tool Outcome Attestation (toa/0.1) — verify only."""

from .verify import claim_for_signing, parse_max_age_seconds, verify_document

__all__ = ["claim_for_signing", "parse_max_age_seconds", "verify_document"]
__version__ = "0.1.0"
