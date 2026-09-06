"""Conformance harness for MCP extension ``dev.agentstatus/toa``."""

from .constants import EXTENSION_ID, TOA_SPEC
from .runner import ScenarioResult, run_all, run_scenario
from .validate_api import ValidationResult, validate_binding

__all__ = [
    "EXTENSION_ID",
    "TOA_SPEC",
    "ScenarioResult",
    "ValidationResult",
    "run_all",
    "run_scenario",
    "validate_binding",
]

__version__ = "0.1.0"
