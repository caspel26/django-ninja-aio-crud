#!/usr/bin/env bash
# Run framework comparison benchmarks and generate HTML report

set -e

echo "======================================"
echo "Framework Comparison Benchmarks"
echo "======================================"
echo ""
echo "Comparing django-ninja-aio-crud against:"
echo "  - Django Ninja (pure)"
echo "  - Django REST Framework (sync)"
echo "  - ADRF (Async Django REST Framework)"
echo "  - FastAPI"
echo ""

# Run comparison benchmarks
echo "Running comparison benchmarks..."
python -m django test tests.comparison --settings=tests.test_settings --tag=comparison -v2

# Generate reports
echo ""
echo "Generating comparison reports..."
python tests/comparison/generate_report.py
python tests/comparison/generate_markdown.py

echo ""
echo "======================================"
echo "Comparison complete!"
echo ""
echo "Results saved to:"
echo "  - comparison_results.json (machine-readable)"
echo "  - comparison_report.html (interactive HTML)"
echo "  - docs/comparison.md (MkDocs page)"
echo ""
echo "View results:"
echo "  - Open comparison_report.html in your browser"
echo "  - Or serve docs: mkdocs serve"
echo "======================================"
