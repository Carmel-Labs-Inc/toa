"""Pytest entry for T1–T13. SKIP is allowed until fixtures/`toa_ext` land."""

from __future__ import annotations

import pytest

from toa_ext_conformance.runner import run_all, run_scenario
from toa_ext_conformance.types import Status


@pytest.mark.parametrize(
    "scenario_id",
    ["T1", "T2", "T3", "T4", "T5", "T6", "T7", "T8", "T9", "T10", "T11", "T12", "T13"],
)
def test_scenario(scenario_id: str):
    result = run_scenario(scenario_id)
    if result.status == Status.SKIP:
        pytest.skip(result.reason + (f" ({result.detail})" if result.detail else ""))
    assert result.status == Status.PASS, (
        f"{scenario_id} {result.name}: {result.status.value} reason={result.reason} detail={result.detail}"
    )


def test_run_all_has_thirteen_results():
    results = run_all()
    assert len(results) == 13
    assert {r.scenario_id for r in results} == {f"T{i}" for i in range(1, 14)}
    fails = [r for r in results if r.status == Status.FAIL]
    assert fails == [], f"unexpected failures: {[(r.scenario_id, r.reason, r.detail) for r in fails]}"
