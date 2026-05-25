"""
Eval report — formats EvalResults to stdout and saves JSON to evals/reports/.
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from engine.evals.base import EvalResult

REPORTS_DIR = Path(__file__).parent / "reports"


def _bar(score: float, width: int = 24) -> str:
    filled = int(round(score * width))
    return "█" * filled + "░" * (width - filled)


def print_report(results: list[EvalResult], suite: str) -> None:
    passed = sum(1 for r in results if r.passed)
    total = len(results)
    run_at = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")

    print()
    print(f"{'=' * 58}")
    print(f"  EVAL REPORT — {suite.upper()}")
    print(f"  Run: {run_at}   Cases: {total}   Passed: {passed}   Failed: {total - passed}")
    print(f"{'=' * 58}")

    # Per-scorer averages
    if results and results[0].scores:
        scorer_names = [s.scorer for s in results[0].scores]
        print("\nSCORES (average across all cases):")
        for name in scorer_names:
            scores = [
                next(s.score for s in r.scores if s.scorer == name)
                for r in results if r.scores
            ]
            avg = sum(scores) / len(scores) if scores else 0.0
            print(f"  {name:<22} {avg:.2f}  {_bar(avg)}")

    # Overall
    overall_scores = [r.overall_score for r in results]
    overall_avg = sum(overall_scores) / len(overall_scores) if overall_scores else 0.0
    print(f"\n  {'OVERALL':<22} {overall_avg:.2f}  {_bar(overall_avg)}")

    # Failures
    failures = [r for r in results if not r.passed]
    if failures:
        print(f"\nFAILURES ({len(failures)}):")
        for r in failures:
            if r.error:
                print(f"  {r.case.case_id:<15} CRASHED: {r.error}")
                continue
            failing_scores = [s for s in r.scores if not s.passed]
            summary = "  |  ".join(
                f"{s.scorer}={s.score:.2f} — {s.reason}" for s in failing_scores
            )
            print(f"  {r.case.case_id:<15} {summary}")
    else:
        print("\n  All cases passed ✓")

    print(f"{'=' * 58}\n")


def save_report(results: list[EvalResult], suite: str) -> Path:
    """Save full results as JSON to evals/reports/."""
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    path = REPORTS_DIR / f"{suite}_{timestamp}.json"

    payload = {
        "suite": suite,
        "run_at": datetime.utcnow().isoformat(),
        "total": len(results),
        "passed": sum(1 for r in results if r.passed),
        "overall_avg": round(
            sum(r.overall_score for r in results) / len(results), 3
        ) if results else 0.0,
        "cases": [
            {
                "case_id": r.case.case_id,
                "description": r.case.description,
                "passed": r.passed,
                "overall_score": r.overall_score,
                "status": r.run_result.status if r.run_result else None,
                "steps": r.run_result.steps_taken if r.run_result else None,
                "cost_usd": r.run_result.total_cost_usd if r.run_result else None,
                "latency_ms": r.run_result.latency_ms if r.run_result else None,
                "tools_called": r.tools_called,
                "error": r.error,
                "scores": [
                    {"scorer": s.scorer, "score": s.score, "passed": s.passed, "reason": s.reason}
                    for s in r.scores
                ],
            }
            for r in results
        ],
    }

    path.write_text(json.dumps(payload, indent=2))
    return path
