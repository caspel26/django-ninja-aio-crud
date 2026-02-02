# Performance Benchmarks

[![Performance](https://github.com/caspel26/django-ninja-aio-crud/actions/workflows/performance.yml/badge.svg)](https://github.com/caspel26/django-ninja-aio-crud/actions/workflows/performance.yml)

## Overview

django-ninja-aio-crud includes an automated performance benchmark suite that measures the framework's throughput across schema generation, serialization, CRUD endpoints, and filter processing.

Benchmarks run automatically on every push to `main` and on every pull request, ensuring that performance regressions are caught early.

---

## Benchmark Categories

### Schema Generation

Measures the time to create Pydantic schemas from Django models via `ModelSerializer` and the Meta-driven `Serializer`, including relations and validators.

### Serialization

Measures single and bulk object serialization, input parsing, and relation serialization performance.

### CRUD Endpoints

Measures create, list, retrieve, update, and delete endpoint throughput through the async view layer.

### Filter Processing

Measures icontains, boolean, numeric, relation, match-case, and combined filter performance.

---

## Running Benchmarks Locally

Run the full suite and generate the HTML report:

```bash
./run-performance.sh
```

Or run only the tests without generating a report:

```bash
python -m django test tests.performance --settings=tests.test_settings --tag=performance -v2
```

To regenerate the report from existing results:

```bash
python tests/performance/generate_report.py
```

### Output Files

| File | Description |
|---|---|
| `performance_results.json` | Machine-readable results. Each run appends an entry with timestamp, Python version, and per-benchmark stats (iterations, min/max/avg/median in ms). |
| `performance_report.html` | Interactive HTML report with Chart.js charts. Shows bar charts for the latest run and line charts for median trends across multiple runs. |

Both files are gitignored.

---

## Live Performance Report

The latest performance benchmarks from the `main` branch are automatically published and available as an interactive HTML report:

<div class="cta-buttons" markdown>

[View Live Performance Report :material-chart-line:](https://caspel26.github.io/django-ninja-aio-crud/performance/performance_report.html){ .md-button .md-button--primary target="_blank" }

</div>

The live report includes:

- **Bar charts** showing min/avg/median/max times for the latest run
- **Trend charts** tracking median performance across multiple runs over time
- **Interactive tooltips** with exact timings
- **Automatic dark mode** support

---

## CI Integration

Performance benchmarks run as part of the CI pipeline via GitHub Actions on every push to `main` and on every pull request. The workflow:

1. Checks out the code and sets up Python
2. Installs dependencies via Flit
3. Runs the full benchmark suite
4. Generates the performance report
5. Downloads the baseline from the latest `main` run
6. Checks for regressions (fails if any benchmark regresses >20%)
7. Uploads the report as a workflow artifact
8. Deploys the report to GitHub Pages (main branch only)

You can download the report artifact from any workflow run in the [Actions tab](https://github.com/caspel26/django-ninja-aio-crud/actions/workflows/performance.yml){ target="_blank" }.

<div class="cta-buttons" markdown>

[View workflow runs :material-open-in-new:](https://github.com/caspel26/django-ninja-aio-crud/actions/workflows/performance.yml){ .md-button target="_blank" }

</div>

### Regression Detection

Pull requests are automatically checked for performance regressions:

- The latest `main` branch results are used as the baseline
- Each benchmark's **median** time is compared
- The build **fails** if any benchmark regresses by more than **20%**
- New benchmarks are skipped (no baseline to compare against)

This threshold accounts for CI runner variance while catching real performance issues.

---

## Interpreting Results

Each benchmark reports the following metrics over its configured number of iterations:

| Metric | Description |
|---|---|
| **Min** | Fastest single iteration |
| **Avg** | Mean time across all iterations |
| **Median** | Middle value — less sensitive to outliers than avg |
| **Max** | Slowest single iteration |

!!! tip "Median is the most reliable metric"
    Use **median** when comparing performance across runs, as it's less affected by GC pauses, OS scheduling, or other transient noise.

!!! warning "CI vs local results"
    Absolute timings on CI runners may differ from your local machine. Focus on **relative changes** between runs rather than absolute values.

---

## Framework Comparison

Wondering how django-ninja-aio-crud compares to other Python REST frameworks? We provide comprehensive benchmarks comparing performance against Django Ninja, ADRF (Async DRF), and FastAPI.

The comparison focuses on **complex async operations** - particularly reverse FK relations and M2M serialization - where django-ninja-aio-crud excels by automating what's notoriously difficult in async Django.

<div class="cta-buttons" markdown>

[View Full Comparison :material-chart-box-outline:](comparison.md){ .md-button .md-button--primary }

</div>

The comparison page includes detailed results, interactive charts, key insights, and links to the live HTML report.

---
