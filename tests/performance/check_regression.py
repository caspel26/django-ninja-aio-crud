#!/usr/bin/env python
"""Check for performance regressions against a baseline.

Compares the latest run in performance_results.json against a baseline file
and fails if any benchmark median regresses beyond the threshold.

Usage:
    python tests/performance/check_regression.py --baseline baseline.json --threshold 20
"""

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CURRENT = PROJECT_ROOT / "performance_results.json"
DEFAULT_THRESHOLD = 20.0  # percent


def load_results(path: Path) -> dict:
    """Load performance results JSON file."""
    resolved_path = path.resolve()
    if not str(resolved_path).startswith(str(PROJECT_ROOT)):
        print(
            f"Error: path must be within project root ({PROJECT_ROOT})",
            file=sys.stderr,
        )
        sys.exit(1)
    if not resolved_path.exists():
        print(f"Error: {resolved_path} not found", file=sys.stderr)
        sys.exit(1)
    return json.loads(resolved_path.read_text())


def get_latest_run(data: dict) -> dict | None:
    """Extract the latest run from results data."""
    runs = data.get("runs", [])
    if not runs:
        return None
    return runs[-1]


def compare_runs(baseline: dict, current: dict, threshold: float) -> tuple[bool, list]:
    """Compare two runs and detect regressions.

    Returns:
        (passed, regressions) where regressions is a list of dicts with:
        - class_name
        - benchmark
        - baseline_median
        - current_median
        - percent_change
    """
    baseline_results = baseline.get("results", {})
    current_results = current.get("results", {})

    regressions = []
    all_passed = True

    for cls_name, benchmarks in current_results.items():
        baseline_benchmarks = baseline_results.get(cls_name, {})

        for bench_name, stats in benchmarks.items():
            baseline_stats = baseline_benchmarks.get(bench_name)
            if not baseline_stats:
                # New benchmark, skip comparison
                continue

            baseline_median = baseline_stats["median_ms"]
            current_median = stats["median_ms"]

            # Calculate percent change (positive = regression/slower)
            if baseline_median == 0:
                # Avoid division by zero
                percent_change = 0 if current_median == 0 else 100
            else:
                percent_change = (
                    (current_median - baseline_median) / baseline_median
                ) * 100

            if percent_change > threshold:
                all_passed = False
                regressions.append(
                    {
                        "class_name": cls_name,
                        "benchmark": bench_name,
                        "baseline_median": baseline_median,
                        "current_median": current_median,
                        "percent_change": percent_change,
                    }
                )

    return all_passed, regressions


def format_report(regressions: list, threshold: float) -> str:
    """Format regression report for console output."""
    lines = [
        f"\n{'=' * 80}",
        "PERFORMANCE REGRESSION DETECTED",
        f"{'=' * 80}\n",
        f"Threshold: {threshold}% regression allowed\n",
    ]

    for reg in regressions:
        lines.append(f"Class: {reg['class_name']}")
        lines.append(f"Benchmark: {reg['benchmark']}")
        lines.append(f"  Baseline median: {reg['baseline_median']:.4f} ms")
        lines.append(f"  Current median:  {reg['current_median']:.4f} ms")
        lines.append(f"  Change: +{reg['percent_change']:.2f}%")
        lines.append("")

    lines.append(f"{'=' * 80}\n")
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Check for performance regressions")
    parser.add_argument(
        "--baseline",
        "-b",
        type=Path,
        required=True,
        help="Path to baseline performance_results.json",
    )
    parser.add_argument(
        "--current",
        "-c",
        type=Path,
        default=DEFAULT_CURRENT,
        help="Path to current performance_results.json",
    )
    parser.add_argument(
        "--threshold",
        "-t",
        type=float,
        default=DEFAULT_THRESHOLD,
        help="Regression threshold in percent (default: 20%%)",
    )
    args = parser.parse_args()

    baseline_data = load_results(args.baseline)
    current_data = load_results(args.current)

    baseline_run = get_latest_run(baseline_data)
    current_run = get_latest_run(current_data)

    if not baseline_run:
        print("Error: No runs found in baseline file", file=sys.stderr)
        sys.exit(1)

    if not current_run:
        print("Error: No runs found in current file", file=sys.stderr)
        sys.exit(1)

    passed, regressions = compare_runs(baseline_run, current_run, args.threshold)

    if passed:
        print(f"✓ All benchmarks within {args.threshold}% threshold")
        baseline_ts = baseline_run["timestamp"][:19].replace("T", " ")
        current_ts = current_run["timestamp"][:19].replace("T", " ")
        print(f"  Baseline: {baseline_ts}")
        print(f"  Current:  {current_ts}")
        sys.exit(0)
    else:
        print(format_report(regressions, args.threshold), file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
