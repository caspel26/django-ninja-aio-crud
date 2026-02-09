#!/usr/bin/env python3
"""
Detect performance regressions using statistical analysis.

This script compares the latest N runs against a baseline (previous N runs)
and uses statistical tests to determine if regressions are real or just noise.
"""
import json
import statistics
import sys
from collections import defaultdict
from pathlib import Path


def detect_regressions(
    baseline_size: int = 5,
    current_size: int = 5,
    threshold_pct: float = 15.0,
    significance: float = 2.0,
):
    """
    Detect performance regressions.

    Parameters
    ----------
    baseline_size : int
        Number of older runs to use as baseline
    current_size : int
        Number of recent runs to compare
    threshold_pct : float
        Minimum percentage change to consider (absolute threshold)
    significance : float
        Number of standard deviations for statistical significance
    """
    results_file = Path("performance_results.json")

    with open(results_file) as f:
        data = json.load(f)

    runs = data["runs"]
    if len(runs) < baseline_size + current_size:
        print(f"❌ Not enough runs: need {baseline_size + current_size}, have {len(runs)}")
        sys.exit(1)

    # Split into baseline and current
    baseline_runs = runs[-(baseline_size + current_size) : -current_size]
    current_runs = runs[-current_size:]

    print("=" * 80)
    print("REGRESSION DETECTION ANALYSIS")
    print("=" * 80)
    print(f"Baseline: {baseline_size} runs starting from {baseline_runs[0]['timestamp']}")
    print(f"Current:  {current_size} runs starting from {current_runs[0]['timestamp']}")
    print(f"Threshold: {threshold_pct}% change OR {significance}σ statistical significance")
    print("=" * 80)

    # Collect metrics
    baseline_metrics = defaultdict(list)
    current_metrics = defaultdict(list)

    for run in baseline_runs:
        for test_class, tests in run["results"].items():
            for bench_name, metrics in tests.items():
                key = f"{test_class}.{bench_name}"
                baseline_metrics[key].append(metrics["median_ms"])

    for run in current_runs:
        for test_class, tests in run["results"].items():
            for bench_name, metrics in tests.items():
                key = f"{test_class}.{bench_name}"
                current_metrics[key].append(metrics["median_ms"])

    # Analyze each benchmark
    regressions = []
    improvements = []
    stable = []

    for bench_name in sorted(baseline_metrics.keys()):
        if bench_name not in current_metrics:
            continue

        baseline_vals = baseline_metrics[bench_name]
        current_vals = current_metrics[bench_name]

        baseline_mean = statistics.mean(baseline_vals)
        current_mean = statistics.mean(current_vals)

        baseline_stdev = statistics.stdev(baseline_vals) if len(baseline_vals) > 1 else 0
        current_stdev = statistics.stdev(current_vals) if len(current_vals) > 1 else 0

        # Percentage change
        pct_change = (
            ((current_mean - baseline_mean) / baseline_mean * 100)
            if baseline_mean > 0
            else 0
        )

        # Statistical significance (number of standard deviations)
        # Using pooled standard deviation
        pooled_stdev = ((baseline_stdev**2 + current_stdev**2) / 2) ** 0.5
        if pooled_stdev > 0:
            z_score = abs(current_mean - baseline_mean) / pooled_stdev
        else:
            z_score = 0

        # Filter out extremely fast tests with microsecond-level noise
        if baseline_mean < 0.001:  # Less than 1 microsecond - noise
            continue

        # Determine if regression/improvement is significant
        is_significant_change = abs(pct_change) > threshold_pct or z_score > significance

        result = {
            "name": bench_name,
            "baseline_mean": baseline_mean,
            "current_mean": current_mean,
            "baseline_stdev": baseline_stdev,
            "current_stdev": current_stdev,
            "pct_change": pct_change,
            "z_score": z_score,
            "is_significant": is_significant_change,
        }

        if is_significant_change:
            if pct_change > 0:
                regressions.append(result)
            else:
                improvements.append(result)
        else:
            stable.append(result)

    # Report results
    print("\n🔴 REGRESSIONS DETECTED:")
    print("-" * 80)
    if regressions:
        regressions.sort(key=lambda x: x["pct_change"], reverse=True)
        for r in regressions:
            sig_marker = f"({r['z_score']:.1f}σ)" if r["z_score"] > significance else ""
            print(
                f"  🔴 {r['name']:<55} {r['baseline_mean']:8.4f}ms -> {r['current_mean']:8.4f}ms "
                f"({r['pct_change']:+6.2f}%) {sig_marker}"
            )
    else:
        print("  ✅ No significant regressions detected!")

    print("\n🟢 IMPROVEMENTS DETECTED:")
    print("-" * 80)
    if improvements:
        improvements.sort(key=lambda x: x["pct_change"])
        for r in improvements:
            sig_marker = f"({r['z_score']:.1f}σ)" if r["z_score"] > significance else ""
            print(
                f"  🟢 {r['name']:<55} {r['baseline_mean']:8.4f}ms -> {r['current_mean']:8.4f}ms "
                f"({r['pct_change']:+6.2f}%) {sig_marker}"
            )
    else:
        print("  ⚪ No significant improvements detected.")

    print(f"\n⚪ STABLE BENCHMARKS: {len(stable)}/{len(baseline_metrics)}")

    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print(f"  🔴 Regressions:  {len(regressions)}")
    print(f"  🟢 Improvements: {len(improvements)}")
    print(f"  ⚪ Stable:       {len(stable)}")
    print("=" * 80)

    # Exit with error if regressions detected
    if regressions:
        print("\n❌ Performance regressions detected! Review the changes above.")
        sys.exit(1)
    else:
        print("\n✅ No performance regressions detected. All benchmarks stable or improved.")
        sys.exit(0)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Detect performance regressions")
    parser.add_argument(
        "--baseline-size",
        type=int,
        default=5,
        help="Number of older runs to use as baseline (default: 5)",
    )
    parser.add_argument(
        "--current-size",
        type=int,
        default=5,
        help="Number of recent runs to compare (default: 5)",
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=15.0,
        help="Minimum percentage change to consider (default: 15.0)",
    )
    parser.add_argument(
        "--significance",
        type=float,
        default=2.0,
        help="Number of standard deviations for significance (default: 2.0)",
    )

    args = parser.parse_args()

    detect_regressions(
        baseline_size=args.baseline_size,
        current_size=args.current_size,
        threshold_pct=args.threshold,
        significance=args.significance,
    )
