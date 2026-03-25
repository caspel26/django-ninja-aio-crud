#!/bin/bash
# Fast test runner — excludes performance/scalability/comparison benchmarks
# Use this for quick verification. Use run-local-coverage.sh for full coverage.
python -m django test --settings=tests.test_settings --exclude-tag=performance --exclude-tag=scalability --exclude-tag=comparison "$@"
