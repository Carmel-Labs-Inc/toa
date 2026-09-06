"""MCP extension AttestationBinding validation for `dev.agentstatus/toa`."""

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
    "default_min_layers",
    "layer_satisfies",
    "validate_binding",
]
__version__ = "0.1.0"
