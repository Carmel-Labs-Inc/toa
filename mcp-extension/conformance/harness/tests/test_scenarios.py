"""Pytest entry for T1–T18. SKIP is allowed until fixtures/`toa_ext` land."""

from __future__ import annotations

import pytest

from toa_ext_conformance.runner import run_all, run_scenario
from toa_ext_conformance.types import Status


SCENARIO_IDS = [f"T{i}" for i in range(1, 19)]


@pytest.mark.parametrize("scenario_id", SCENARIO_IDS)
def test_scenario(scenario_id: str):
    result = run_scenario(scenario_id)
    if result.status == Status.SKIP:
        pytest.skip(result.reason + (f" ({result.detail})" if result.detail else ""))
    assert result.status == Status.PASS, (
        f"{scenario_id} {result.name}: {result.status.value} reason={result.reason} detail={result.detail}"
    )


def test_run_all_has_eighteen_results():
    results = run_all()
    assert len(results) == 18
    assert {r.scenario_id for r in results} == set(SCENARIO_IDS)
    fails = [r for r in results if r.status == Status.FAIL]
    assert fails == [], f"unexpected failures: {[(r.scenario_id, r.reason, r.detail) for r in fails]}"
