#!/usr/bin/env python3
"""Compare performance between yesterday and today."""
import json
from collections import defaultdict
from pathlib import Path

def compare_days():
    results_file = Path("performance_results.json")

    with open(results_file) as f:
        data = json.load(f)

    # Separate runs by date
    yesterday_runs = []
    today_runs = []

    for run in data["runs"]:
        timestamp = run["timestamp"]
        if timestamp.startswith("2026-02-01"):
            yesterday_runs.append(run)
        elif timestamp.startswith("2026-02-02"):
            today_runs.append(run)

    print(f"Yesterday (2026-02-01): {len(yesterday_runs)} runs")
    print(f"Today (2026-02-02): {len(today_runs)} runs")
    print()

    if not yesterday_runs or not today_runs:
        print("Not enough data to compare")
        return

    # Calculate averages for each day
    def calc_averages(runs):
        metrics = defaultdict(lambda: defaultdict(list))
        for run in runs:
            for test_class, benchmarks in run["results"].items():
                for bench_name, data in benchmarks.items():
                    metrics[test_class][bench_name].append(data["median_ms"])

        # Average the medians
        averages = {}
        for test_class, benchmarks in metrics.items():
            averages[test_class] = {}
            for bench_name, values in benchmarks.items():
                averages[test_class][bench_name] = sum(values) / len(values)

        return averages

    yesterday_avg = calc_averages(yesterday_runs)
    today_avg = calc_averages(today_runs)

    print("=" * 80)
    print("PERFORMANCE COMPARISON: Yesterday vs Today (median averages)")
    print("=" * 80)

    total_tests = 0
    slower_tests = 0
    faster_tests = 0

    for test_class in sorted(today_avg.keys()):
        if test_class not in yesterday_avg:
            continue

        print(f"\n{test_class}:")
        print("-" * 80)

        for bench_name in sorted(today_avg[test_class].keys()):
            if bench_name not in yesterday_avg[test_class]:
                continue

            yesterday_val = yesterday_avg[test_class][bench_name]
            today_val = today_avg[test_class][bench_name]

            delta = today_val - yesterday_val
            pct_change = (delta / yesterday_val * 100) if yesterday_val > 0 else 0

            total_tests += 1

            if delta > 0:
                symbol = "🔴"
                slower_tests += 1
            elif delta < 0:
                symbol = "🟢"
                faster_tests += 1
            else:
                symbol = "⚪"

            print(f"  {symbol} {bench_name:40} {yesterday_val:8.4f}ms -> {today_val:8.4f}ms ({pct_change:+7.2f}%)")

    print("\n" + "=" * 80)
    print(f"SUMMARY: {slower_tests} slower, {faster_tests} faster, {total_tests - slower_tests - faster_tests} unchanged (out of {total_tests} tests)")
    print("=" * 80)

    # Find biggest regressions
    print("\nBIGGEST REGRESSIONS:")
    regressions = []
    for test_class in today_avg.keys():
        if test_class not in yesterday_avg:
            continue
        for bench_name in today_avg[test_class].keys():
            if bench_name not in yesterday_avg[test_class]:
                continue
            yesterday_val = yesterday_avg[test_class][bench_name]
            today_val = today_avg[test_class][bench_name]
            pct_change = ((today_val - yesterday_val) / yesterday_val * 100) if yesterday_val > 0 else 0
            if pct_change > 0:
                regressions.append((pct_change, test_class, bench_name, yesterday_val, today_val))

    regressions.sort(reverse=True)
    for pct, test_class, bench_name, yesterday_val, today_val in regressions[:10]:
        print(f"  🔴 {test_class}.{bench_name}: {yesterday_val:.4f}ms -> {today_val:.4f}ms (+{pct:.2f}%)")

if __name__ == "__main__":
    compare_days()
