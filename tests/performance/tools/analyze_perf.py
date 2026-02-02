#!/usr/bin/env python3
"""Analyze performance test results to compare recent runs."""
import json
from datetime import datetime
from pathlib import Path

def analyze_performance():
    results_file = Path("performance_results.json")

    if not results_file.exists():
        print("performance_results.json not found")
        return

    with open(results_file) as f:
        data = json.load(f)

    # Get last 5 runs
    recent_runs = data["runs"][-5:]

    print("=" * 80)
    print("PERFORMANCE COMPARISON - Last 5 Runs")
    print("=" * 80)

    for idx, run in enumerate(recent_runs, 1):
        timestamp = run["timestamp"]
        python_ver = run["python_version"]
        print(f"\nRun {idx}: {timestamp} (Python {python_ver})")
        print("-" * 80)

        for test_class, benchmarks in run["results"].items():
            print(f"\n  {test_class}:")
            for bench_name, metrics in benchmarks.items():
                median = metrics["median_ms"]
                avg = metrics["avg_ms"]
                print(f"    {bench_name:35} median: {median:8.4f}ms  avg: {avg:8.4f}ms")

    # Compare last run vs previous run
    if len(recent_runs) >= 2:
        print("\n" + "=" * 80)
        print("DELTA: Latest Run vs Previous Run")
        print("=" * 80)

        latest = recent_runs[-1]
        previous = recent_runs[-2]

        print(f"\nLatest:   {latest['timestamp']}")
        print(f"Previous: {previous['timestamp']}")

        for test_class in latest["results"]:
            if test_class not in previous["results"]:
                continue

            print(f"\n  {test_class}:")

            for bench_name in latest["results"][test_class]:
                if bench_name not in previous["results"][test_class]:
                    continue

                latest_median = latest["results"][test_class][bench_name]["median_ms"]
                prev_median = previous["results"][test_class][bench_name]["median_ms"]

                delta = latest_median - prev_median
                pct_change = (delta / prev_median * 100) if prev_median > 0 else 0

                symbol = "🔴" if delta > 0 else "🟢" if delta < 0 else "⚪"

                print(f"    {symbol} {bench_name:35} {prev_median:8.4f}ms -> {latest_median:8.4f}ms "
                      f"({pct_change:+6.2f}%)")

if __name__ == "__main__":
    analyze_performance()
