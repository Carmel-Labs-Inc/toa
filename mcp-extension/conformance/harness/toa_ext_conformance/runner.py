"""Scenario runner: execute T1–T16 and report PASS/FAIL/SKIP."""

from __future__ import annotations

import argparse
import json
import sys
from typing import Dict, Iterable, List, Optional, Sequence

from .fixtures import fixture_status
from .scenarios import SCENARIOS
from .types import ScenarioResult, Status


def run_scenario(scenario_id: str) -> ScenarioResult:
    key = scenario_id.upper()
    for sid, _name, fn in SCENARIOS:
        if sid == key:
            return fn()
    return ScenarioResult(
        scenario_id=scenario_id,
        name="unknown",
        status=Status.FAIL,
        reason="unknown_scenario",
    )


def run_all(only: Optional[Sequence[str]] = None) -> List[ScenarioResult]:
    wanted = {s.upper() for s in only} if only else None
    results: List[ScenarioResult] = []
    for sid, _name, fn in SCENARIOS:
        if wanted is not None and sid not in wanted:
            continue
        results.append(fn())
    return results


def summarize(results: Iterable[ScenarioResult]) -> Dict[str, int]:
    counts = {Status.PASS.value: 0, Status.FAIL.value: 0, Status.SKIP.value: 0}
    for r in results:
        counts[r.status.value] = counts.get(r.status.value, 0) + 1
    return counts


def format_table(results: Sequence[ScenarioResult]) -> str:
    lines = [
        f"{'ID':<4} {'Status':<6} {'Name':<36} Reason",
        "-" * 80,
    ]
    for r in results:
        lines.append(f"{r.scenario_id:<4} {r.status.value:<6} {r.name:<36} {r.reason}")
        if r.detail:
            lines.append(f"     detail: {r.detail}")
    counts = summarize(results)
    lines.append("-" * 80)
    lines.append(
        f"PASS={counts.get('PASS', 0)}  FAIL={counts.get('FAIL', 0)}  SKIP={counts.get('SKIP', 0)}"
    )
    return "\n".join(lines)


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Run TOA MCP extension conformance scenarios T1–T16")
    parser.add_argument(
        "--only",
        nargs="+",
        help="Run specific scenario ids (e.g. T1 T3 T9)",
    )
    parser.add_argument("--json", action="store_true", help="Emit JSON report")
    parser.add_argument("--fixtures", action="store_true", help="Print fixture readiness and exit")
    args = parser.parse_args(list(argv) if argv is not None else None)

    if args.fixtures:
        print(json.dumps(fixture_status(), indent=2))
        return 0

    results = run_all(only=args.only)
    if args.json:
        payload = {
            "fixtures": fixture_status(),
            "results": [r.as_dict() for r in results],
            "summary": summarize(results),
        }
        print(json.dumps(payload, indent=2))
    else:
        print(format_table(results))

    # Exit non-zero only on FAIL (SKIP is ok for incomplete fixtures).
    return 1 if any(r.status == Status.FAIL for r in results) else 0


if __name__ == "__main__":
    sys.exit(main())
