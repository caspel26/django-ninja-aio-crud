#! /bin/sh
# Run performance benchmarks and generate an HTML report with charts.
# Usage: ./run-performance.sh
# Results are appended to performance_results.json
# Charts are generated in performance_report.html
python -m django test tests.performance --settings=tests.test_settings --tag=performance -v2
python tests/performance/generate_report.py
