"""
Performance analysis tools for django-ninja-aio-crud.

This package contains tools for analyzing performance benchmark results,
detecting regressions, and understanding performance trends.

Tools:
------
- analyze_perf: Quick overview of last 5 runs
- compare_days: Day-over-day performance comparison
- analyze_variance: Benchmark stability analysis
- detect_regression: Statistical regression detection (recommended for CI/CD)

For detailed usage, see README.md in this directory.
"""

__all__ = [
    "analyze_perf",
    "compare_days",
    "analyze_variance",
    "detect_regression",
]
