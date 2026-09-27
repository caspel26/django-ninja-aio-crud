---
type: benchmark
title: Performance
description: Run the performance benchmarks, read the results and find the live report.
---

# Performance

[![Performance](https://github.com/caspel26/django-ninja-aio-crud/actions/workflows/performance.yml/badge.svg)](https://github.com/caspel26/django-ninja-aio-crud/actions/workflows/performance.yml)

The project has a benchmark suite that measures schema generation,
serialization, CRUD endpoints and filters. It runs on every push to `main`
and on every pull request.

## What is measured

| Category | What it measures |
| --- | --- |
| Schema generation | Building schemas from Django models with `ModelSerializer` and `Serializer`, including relations and validators |
| Serialization | Single and bulk object serialization, input parsing and relation serialization |
| CRUD endpoints | Create, list, retrieve, update and delete through the view layer |
| Filters | `icontains`, boolean, numeric, relation, match-case and combined filters |

## Run the benchmarks locally

Run the full suite and build the HTML report:

```bash
./run-performance.sh
```

Run only the benchmarks, without the report:

```bash
python -m django test tests.performance --settings=tests.test_settings --tag=performance -v2
```

Rebuild the report from existing results:

```bash
python tests/performance/generate_report.py
```

Each run writes these files. Both are ignored by git.

| File | What it contains |
| --- | --- |
| `performance_results.json` | One entry per run with the timestamp, Python version and per-benchmark stats (iterations, min/max/avg/median in ms). |
| `performance_report.html` | Interactive charts: bar charts for the latest run and line charts for median trends across runs. |

To check your changes for regressions, see
[Run the performance benchmarks](contributing.md#run-the-performance-benchmarks).

## Live report

The latest results from the `main` branch are published as an interactive
HTML report.

[View the live performance report](https://caspel26.github.io/django-ninja-aio-crud/performance/performance_report.html){ .md-button .md-button--primary target="_blank" }

The report shows:

- Bar charts with min, avg, median and max times for the latest run
- Trend charts with the median of each benchmark over time
- Tooltips with exact timings
- Dark mode, following your system setting

## CI

GitHub Actions runs the benchmarks on every push to `main` and on every pull
request. The workflow:

1. Checks out the code and sets up Python.
2. Installs the dependencies with Flit.
3. Runs the benchmark suite.
4. Builds the performance report.
5. Downloads the baseline from the latest `main` run.
6. Checks for regressions.
7. Uploads the report as a workflow artifact.
8. Publishes the report to GitHub Pages (`main` only).

You can download the report from any run in the
[Actions tab](https://github.com/caspel26/django-ninja-aio-crud/actions/workflows/performance.yml){ target="_blank" }.

### Regression check

Pull requests are checked against the latest `main` results:

- The median time of each benchmark is compared with the baseline.
- The build fails if a benchmark is more than 120% slower than the baseline.
- New benchmarks are skipped, because they have no baseline yet.

CI runners are shared and noisy, so the threshold is high. For a stricter
check, run `python tests/performance/tools/detect_regression.py` locally.

## Read the results

Each benchmark reports these values over its iterations:

| Metric | What it means |
| --- | --- |
| Min | Fastest iteration |
| Avg | Mean of all iterations |
| Median | Middle value, less affected by outliers |
| Max | Slowest iteration |

!!! tip

    Compare runs by the median. It is less affected by garbage collection
    pauses and other short spikes.

!!! warning

    CI timings differ from your machine. Compare changes between runs, not
    absolute values.

## See also

- [Framework comparison](comparison.md)
- [Contributing](contributing.md)
- [Query optimization](guides/query-optimization.md)
