# CLAUDE.md

## Project Overview

**django-ninja-aio-crud** is an async CRUD framework built on Django Ninja. It provides automated REST API generation with async support, authentication, filtering, pagination, and serialization.

- **Framework:** Django Ninja (>=1.3.0, <1.6)
- **Python:** 3.10 - 3.14
- **Build system:** Flit
- **Linter/Formatter:** Ruff

## Project Structure

- `ninja_aio/` - Main source package
  - `api.py` - NinjaAIO class extending NinjaAPI
  - `auth.py` - JWT authentication (AsyncJwtBearer)
  - `views/` - APIView, APIViewSet, mixins
  - `models/` - ModelSerializer, Meta-driven Serializer, model utilities
  - `schemas/` - Pydantic schema generation and filters
  - `decorators/` - View and operation decorators
  - `factory/` - Operation factory
  - `helpers/` - Query and API helpers
- `tests/` - Test suite
  - `test_settings.py` - Django settings for tests (SQLite in-memory)
  - `test_app/` - Test Django app with models, serializers, views
  - Subdirectories: `core/`, `generics/`, `helpers/`, `views/`, `models/`
- `docs/` - MkDocs documentation

## Running Tests

Activate the virtual environment and run the coverage script:

```sh
. ./.venv/bin/activate && ./run-local-coverage.sh
```

This runs `coverage run -m django test --settings=tests.test_settings` and generates an HTML report in `.html/`.

To run tests without coverage:

```sh
. ./.venv/bin/activate && python -m django test --settings=tests.test_settings
```

## Test-Driven Development Protocol

**CRITICAL:** After implementing any code change, you MUST follow this protocol:

1. **Run all tests** to verify nothing broke:
   ```sh
   . ./.venv/bin/activate && python -m django test --settings=tests.test_settings
   ```

2. **Check coverage** to identify uncovered lines:
   ```sh
   . ./.venv/bin/activate && coverage run -m django test --settings=tests.test_settings && coverage report
   ```

3. **If new uncovered lines exist:**
   - Write tests following the existing test structure in `tests/`
   - Match the naming conventions and organization patterns
   - Ensure new tests follow the same patterns as existing tests in the same module

4. **Run tests again** to verify new tests pass and coverage is maintained

5. **Run performance benchmarks** to detect performance regressions:
   ```sh
   # Run tests 5 times for statistical reliability
   . ./.venv/bin/activate
   for i in 1 2 3 4 5; do
     python -m django test tests.performance --settings=tests.test_settings --tag=performance -v0
   done
   ```

6. **Check for performance regressions using statistical analysis:**
   ```sh
   python tests/performance/tools/detect_regression.py
   ```

   This tool uses statistical methods to distinguish real regressions from noise:
   - Compares last N runs against baseline runs
   - Uses percentage thresholds AND statistical significance (σ)
   - Filters out microsecond-level noise
   - Exit code 0 = no regressions, 1 = regressions detected

   **If regressions are detected:**
   - Review the output to see which benchmarks regressed
   - Investigate the root cause by analyzing the code path being tested
   - Determine if the regression is justified by the change (e.g., added functionality that inherently costs more)
   - If the regression is NOT justified:
     - Identify the bottleneck using profiling tools if needed
     - Optimize the implementation to restore performance
     - Re-run benchmarks to verify the fix
   - If the regression IS justified:
     - Document why the performance trade-off is necessary
     - Consider if the benefits outweigh the performance cost
     - Update the changelog to note the performance impact if significant

7. **Analyze unexpected performance changes:**
   - If tests that should NOT be affected by your changes show regressions:
     ```sh
     # Check benchmark stability
     python tests/performance/tools/analyze_variance.py
     ```
   - If Coefficient of Variation (CV) is high (>15%), it's likely noise
   - Check for system-level factors (CPU load, memory pressure, background processes)
   - Run more iterations to improve statistical confidence
   - Investigate potential second-order effects (import overhead, cache invalidation, JIT compiler behavior)

This protocol applies to ALL code changes, including:
- New features
- Bug fixes
- Refactoring
- Performance optimizations
- Security fixes

**Do not consider a task complete until all tests pass, coverage is maintained or improved, and performance regressions are analyzed and justified.**

## Running Performance Tests

Performance benchmarks live in `tests/performance/` and measure schema generation, serialization, CRUD endpoints, and filter processing.

Run benchmarks and generate the HTML report in one step:

```sh
. ./.venv/bin/activate && ./run-performance.sh
```

This executes all 19 benchmarks, appends results to `performance_results.json`, and generates an interactive `performance_report.html` with Chart.js charts.

To run only the tests (no report):

```sh
. ./.venv/bin/activate && python -m django test tests.performance --settings=tests.test_settings --tag=performance -v2
```

To regenerate the HTML report from existing results:

```sh
python tests/performance/generate_report.py
# or with custom paths:
python tests/performance/generate_report.py --input path/to/results.json --output path/to/report.html
```

### Output files

- `performance_results.json` — Machine-readable results. Each run appends an entry with timestamp, Python version, and per-benchmark stats (iterations, min/max/avg/median in ms). Accumulates across runs for trend comparison.
- `performance_report.html` — Interactive HTML report (Chart.js via CDN, zero dependencies). Shows bar charts for the latest run and line charts for median trends across multiple runs. Open directly in a browser.

Both files are gitignored.

### Benchmark categories

- **SchemaGenerationPerformanceTest** — ModelSerializer and Meta-driven Serializer schema creation, including relations and validators
- **SerializationPerformanceTest** — Single/bulk object serialization, input parsing, relation serialization
- **CRUDPerformanceTest** — Create, list, retrieve, update, delete endpoint throughput
- **FilterPerformanceTest** — icontains, boolean, numeric, relation, match-case, and combined filter performance

### Performance Analysis Tools

Performance analysis tools are located in `tests/performance/tools/`. These tools help analyze benchmark results, detect regressions, and understand performance trends.

**Quick reference using helper script:**

```sh
./check-performance.sh detect    # Detect regressions (recommended)
./check-performance.sh quick     # Quick overview of last 5 runs
./check-performance.sh variance  # Analyze benchmark stability
./check-performance.sh compare   # Compare days
./check-performance.sh all       # Run all analysis tools
```

**Or call tools directly:**

```sh
# 1. Quick overview of last 5 runs
python tests/performance/tools/analyze_perf.py

# 2. Compare performance between days
python tests/performance/tools/compare_days.py

# 3. Analyze benchmark stability and variance
python tests/performance/tools/analyze_variance.py

# 4. Detect statistical regressions (CI/CD recommended)
python tests/performance/tools/detect_regression.py
```

**Primary tool for regression detection:**

Use `detect_regression.py` for statistical analysis that distinguishes real regressions from noise:

```sh
# Default: compare last 5 runs vs previous 5, 15% threshold, 2σ significance
python tests/performance/tools/detect_regression.py

# Strict mode for CI/CD
python tests/performance/tools/detect_regression.py --threshold 10.0 --significance 2.0

# More samples for better statistical reliability
python tests/performance/tools/detect_regression.py --baseline-size 10 --current-size 10
```

Exit codes:
- `0` = No regressions detected ✅
- `1` = Regressions detected ❌

**Full documentation:** See `tests/performance/tools/README.md` for detailed usage of all tools.

## Framework Comparison Benchmarks

Framework comparison benchmarks live in `tests/comparison/` and measure django-ninja-aio-crud performance against other popular Python REST frameworks (Django Ninja, Django REST Framework, ADRF, FastAPI).

Run comparison benchmarks and generate the HTML report in one step:

```sh
. ./.venv/bin/activate && ./run-comparison.sh
```

Or run components separately:

```sh
# Install comparison dependencies
pip install -e ".[comparison]"

# Run comparison benchmarks
. ./.venv/bin/activate && python -m django test tests.comparison --settings=tests.test_settings --tag=comparison -v2

# Generate comparison report
python tests/comparison/generate_report.py
```

### Output files

- `comparison_results.json` — Machine-readable results with timing statistics for each framework and operation
- `comparison_report.html` — Interactive HTML report with bar charts comparing framework performance

Both files are gitignored.

### Compared frameworks

- **django-ninja-aio-crud** (this framework) — Native async CRUD automation
- **Django Ninja** (pure) — Async-ready but manual endpoint definition
- **Django REST Framework** — Synchronous (wrapped with sync_to_async)
- **ADRF** — Async Django REST Framework with native async support
- **FastAPI** — Native async, Starlette-based

### Operations tested

- **create** — Creating a single item via POST
- **list** — Listing items with pagination (20 items)
- **retrieve** — Fetching a single item by ID
- **update** — Updating a single item via PATCH
- **delete** — Deleting a single item by ID
- **filter** — Applying multiple filters to list query
- **relation_serialization** — Serializing items with FK relations (select_related)
- **bulk_serialization_100** — Serializing 100 items with pagination
- **bulk_serialization_500** — Serializing 500 items to test larger dataset performance

All frameworks use the same Django models and database, ensuring comparison focuses on framework overhead rather than I/O performance.

## Code Style

- Ruff is used for linting and formatting (configured via pre-commit hooks)
- Pre-commit hooks also check AST validity, merge conflicts, TOML/YAML syntax, trailing whitespace, and EOF newlines
- **ALWAYS add imports at the top of the file** — Place all import statements at the beginning of each Python file, following PEP 8 conventions. The only exception is when avoiding circular imports, in which case imports may be placed inside functions or methods with a clear comment explaining why.

## Architecture Notes

### Serializer System

Two serializer patterns exist:

- **ModelSerializer** (`ninja_aio/models/serializers.py`): Model-bound, config via inner classes (`CreateSerializer`, `ReadSerializer`, `UpdateSerializer`, `DetailSerializer`). Metaclass: `ModelSerializerMeta`.
- **Serializer** (`ninja_aio/models/serializers.py`): Meta-driven for arbitrary Django models, config via `Meta` class with `SchemaModelConfig` objects. Metaclass: `SerializerMeta`.

Both inherit from `BaseSerializer` which provides shared utilities and the core schema factory (`_generate_model_schema`).

### Schema Generation Pipeline

1. Field configuration gathered from inner classes / Meta
2. `ninja.orm.create_schema()` called (wraps `pydantic.create_model`) — accepts `base_class`, `fields`, `custom_fields`, `exclude`, `depth`
3. Validators collected and applied as a subclass of the generated schema (see Validators section)
4. Resulting Pydantic model class used for input validation and output serialization

### Validators on Serializers

Pydantic `@field_validator` and `@model_validator` can be declared on serializer config classes. The framework collects `PydanticDescriptorProxy` instances and creates a subclass of the generated schema with those validators attached.

**ModelSerializer** — validators on inner serializer classes:
```python
class MyModel(ModelSerializer):
    class CreateSerializer:
        fields = ["name", "email"]

        @field_validator("name")
        @classmethod
        def validate_name(cls, v):
            if len(v) < 3:
                raise ValueError("Name too short")
            return v
```

**Serializer** — validators on `{Type}Validators` inner classes:
```python
class MySerializer(Serializer):
    class Meta:
        model = MyModel
        schema_in = SchemaModelConfig(fields=["name", "email"])

    class CreateValidators:
        @field_validator("name")
        @classmethod
        def validate_name(cls, v):
            return v.strip()
```

Key methods in `BaseSerializer`:
- `_collect_validators(source_class)` — scans class for `PydanticDescriptorProxy` instances
- `_apply_validators(schema, validators)` — creates subclass with validators attached
- `_get_validators(schema_type)` — maps schema type to validator source class (overridden by each serializer)

## Writing Release Notes / Changelogs

When asked to write a changelog or release notes, generate a diff first and then produce a comprehensive `CHANGELOG.md` entry following the structure below. The changelog is kept in `CHANGELOG.md` at the project root.

### How to generate the diff

```sh
# Diff between the current branch and main (for a feature branch)
git diff main...HEAD > diff.txt

# Or diff between two tags
git diff v2.17.0..v2.18.0 > diff.txt

# Or diff of all uncommitted changes (staged + unstaged)
git diff HEAD > diff.txt
```

### Changelog structure and style guide

Each release entry follows this format:

```markdown
## [vX.Y.Z] - YYYY-MM-DD

---

### New Features

#### Feature Name
> `path/to/file.py`

Description of the feature. Include code examples when the feature introduces new API surface.

---

### Improvements

#### Improvement Name
> `path/to/file.py`

Description of what changed and why.

---

### Documentation

Brief summary of documentation changes. Do NOT list every CSS class or inline style change. Keep `main.py`, `extra.css`, and `mkdocs.yml` changes to one-line summaries unless they introduce user-facing functionality.

---

### Tests

#### `TestClassName` — N tests

**Category:**

| Test | Verifies |
|---|---|
| `test_name` | What it verifies |

**New test fixtures:**

| File | Addition |
|---|---|
| `tests/test_app/models.py` | `ModelName` — brief description |

---

### Summary

Brief paragraph summarizing the release. Then:

**Key benefits:**
- Bullet points

### Key rules

- **Always overwrite `CHANGELOG.md`** — Every time a changelog is generated, overwrite the existing `CHANGELOG.md` file at the project root. Do not create a new file or append to it.
- **Use emojis** — Decorate section headers, sub-headers, bullet points, and table entries with contextual emojis (e.g., ✨ New Features, 🔧 Improvements, 🧪 Tests, ✅/❌ for pass/fail tests, 🎯 Summary)

- **Group by category**: New Features, Improvements, Documentation, Tests, Summary
- **Use `> path/to/file`** blockquotes to indicate which file a change belongs to
- **Include code examples** for new user-facing API features
- **Use tables** for listing tests, methods, file changes, and mappings
- **Keep docs/styling/config sections brief** — one-liner summaries for CSS, `main.py` template changes, and `mkdocs.yml` config. Do not enumerate individual CSS classes or JS functions
- **Always include "Summary" section** with key benefits as bullet points
- **Separate sections with `---`** horizontal rules
