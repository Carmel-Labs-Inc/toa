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

__all__ = [
    "ClientSettings",
    "EXTENSION_ID",
    "TOA_ERROR_CODE",
    "attach_binding_to_result",
    "attach_signed_document",
    "build_claim",
    "default_min_layers",
    "embedded_binding",
    "enforce_client_require",
    "layer_satisfies",
    "reference_binding",
    "should_attach",
    "toa_failure_error",
    "validate_binding",
]
__version__ = "0.1.0"

try:
    from .mcp_sdk import ToaAttachExtension  # noqa: F401

    __all__.append("ToaAttachExtension")
except ImportError:
    pass
