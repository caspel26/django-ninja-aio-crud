#!/usr/bin/env python3
"""Analyze performance variance within a single day."""
import json
import statistics
from collections import defaultdict
from pathlib import Path

def analyze_variance():
    results_file = Path("performance_results.json")

    with open(results_file) as f:
        data = json.load(f)

    # Get today's runs
    today_runs = [r for r in data["runs"] if r["timestamp"].startswith("2026-02-02")]

    if len(today_runs) < 2:
        print("Not enough runs to analyze variance")
        return

    print(f"Analyzing {len(today_runs)} runs from 2026-02-02")
    print("=" * 80)

    # Collect all median values for each benchmark
    benchmarks = defaultdict(list)
    for run in today_runs:
        for test_class, tests in run["results"].items():
            for bench_name, metrics in tests.items():
                key = f"{test_class}.{bench_name}"
                benchmarks[key].append(metrics["median_ms"])

    # Calculate variance statistics
    print("\nBENCHMARK STABILITY ANALYSIS")
    print("=" * 80)
    print(f"{'Benchmark':<60} {'Mean':>8} {'StdDev':>8} {'CV%':>8} {'Min':>8} {'Max':>8}")
    print("-" * 80)

    unstable_benchmarks = []

    for bench_name in sorted(benchmarks.keys()):
        values = benchmarks[bench_name]
        mean = statistics.mean(values)
        stdev = statistics.stdev(values) if len(values) > 1 else 0
        cv = (stdev / mean * 100) if mean > 0 else 0  # Coefficient of variation
        min_val = min(values)
        max_val = max(values)

        symbol = "🔴" if cv > 15 else "🟡" if cv > 10 else "🟢"

        print(f"{symbol} {bench_name:<57} {mean:8.4f} {stdev:8.4f} {cv:7.2f}% {min_val:8.4f} {max_val:8.4f}")

        if cv > 15:
            unstable_benchmarks.append((cv, bench_name, mean, stdev))

    print("\n" + "=" * 80)
    print("STABILITY LEGEND:")
    print("  🟢 CV < 10%  - Stable (low variance)")
    print("  🟡 CV 10-15% - Moderate variance")
    print("  🔴 CV > 15%  - Unstable (high variance)")
    print("=" * 80)

    if unstable_benchmarks:
        print("\nMOST UNSTABLE BENCHMARKS (CV > 15%):")
        unstable_benchmarks.sort(reverse=True)
        for cv, bench, mean, stdev in unstable_benchmarks[:10]:
            print(f"  🔴 {bench}: CV={cv:.2f}% (mean={mean:.4f}ms, stdev={stdev:.4f}ms)")

    # Compare first 5 vs last 5 runs
    if len(today_runs) >= 10:
        print("\n" + "=" * 80)
        print("EARLY vs LATE RUNS COMPARISON")
        print("=" * 80)

        early_runs = today_runs[:5]
        late_runs = today_runs[-5:]

        early_avg = defaultdict(list)
        late_avg = defaultdict(list)

        for run in early_runs:
            for test_class, tests in run["results"].items():
                for bench_name, metrics in tests.items():
                    key = f"{test_class}.{bench_name}"
                    early_avg[key].append(metrics["median_ms"])

        for run in late_runs:
            for test_class, tests in run["results"].items():
                for bench_name, metrics in tests.items():
                    key = f"{test_class}.{bench_name}"
                    late_avg[key].append(metrics["median_ms"])

        print(f"\n{'Benchmark':<60} {'Early':>8} {'Late':>8} {'Delta':>8}")
        print("-" * 80)

        for bench_name in sorted(early_avg.keys()):
            if bench_name not in late_avg:
                continue

            early_mean = statistics.mean(early_avg[bench_name])
            late_mean = statistics.mean(late_avg[bench_name])
            delta_pct = ((late_mean - early_mean) / early_mean * 100) if early_mean > 0 else 0

            symbol = "🔴" if abs(delta_pct) > 10 else "🟡" if abs(delta_pct) > 5 else "🟢"

            print(f"{symbol} {bench_name:<57} {early_mean:8.4f} {late_mean:8.4f} {delta_pct:+7.2f}%")

if __name__ == "__main__":
    analyze_variance()
