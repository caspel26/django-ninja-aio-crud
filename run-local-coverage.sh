#! /bin/sh
# Run tests with coverage and generate HTML report
# Usage: ./run-local-coverage.sh
# Requires: coverage, django
# Install dependencies: pip install coverage django
# Ensure you have a Django settings module for tests at tests.test_settings
# Generate HTML report in .html/ directory
# Warning: this is for local use only and may overwrite existing .html/ directory
coverage run -m django test --settings=tests.test_settings
coverage html -d .html