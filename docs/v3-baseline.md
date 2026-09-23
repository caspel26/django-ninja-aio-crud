# Version 3 Baseline

> Internal implementation artifact. Remove this file before the final version
> 3 release after release-regression data has moved to its permanent home.

This baseline records the version 2.36 behavior against which version 3 work
is reviewed. It is not a promise that every number must remain identical:
approved improvements may reduce queries or latency, while intentional HTTP
changes must be documented in the migration guide.

## Environment

- Recorded: 2026-09-24
- Package version: 2.36.0
- Python: 3.14.0
- Database for tests: SQLite in-memory
- Branch baseline: `feat/v3-api-redesign`

## Functional suite

The repository runner uses `python`, which was not present in the active PATH.
The equivalent virtualenv command was used:

```console
.venv/bin/python -m django test \
  --settings=tests.test_settings \
  --exclude-tag=performance \
  --exclude-tag=scalability \
  --exclude-tag=comparison
```

Result before Step 1 changes:

```text
Ran 1113 tests in 6.018s
OK
System check identified no issues (0 silenced).
```

## OpenAPI baseline

Representative generated CRUD contracts are stored for both serializer
styles:

- `tests/v3/snapshots/model_serializer_openapi.json`
- `tests/v3/snapshots/standalone_serializer_openapi.json`

The snapshots intentionally cover paths, HTTP methods, operation IDs, response
codes, and component schema names. Full schema bodies are excluded because
field-level schema behavior already has dedicated serializer tests and a full
document snapshot would add unrelated churn.

## Performance baseline

The latest existing run in `performance_results.json` was recorded on
2026-09-21 with Python 3.14.0. Median times used as the initial comparison
baseline are:

| Scenario | Median |
| --- | ---: |
| CRUD create | 0.9229 ms |
| CRUD retrieve | 0.5465 ms |
| CRUD update | 1.0276 ms |
| CRUD delete | 0.8460 ms |
| CRUD list | 1.1306 ms |
| Single-object serialization | 0.3041 ms |
| Relation serialization | 0.3101 ms |
| 100-object serialization | 0.5402 ms |
| 500-object serialization | 1.4742 ms |
| Three-FK create | 1.2971 ms |
| Three-FK bulk create (50 items) | 18.6280 ms |

Schema generation medians are approximately 0.0002 ms because the benchmark
measures the existing warm cache. Step 2 must add cold-cache measurements for
the new lazy schema attributes rather than treating this number as generation
cost.

Step 2 added and executed isolated cold-cache benchmarks with 100 iterations:

| Lazy schema scenario | Median |
| --- | ---: |
| ModelSerializer, four default schemas | 0.0154 ms |
| Standalone Serializer, four default schemas | 0.0224 ms |

## Query-count baseline

`tests/v3/test_query_baseline.py` freezes representative query counts for
single-object CRUD and serialization. A lower count is acceptable; increasing
a count requires an explicit explanation and approval at that implementation
step.

| Version 2 operation | Queries |
| --- | ---: |
| `get_object()` | 1 |
| `create_s()` plus output serialization | 1 |
| `update_s()` plus output serialization | 2 |
| `delete_s()` with primary-key lookup | 2 |
| `read_s()` with an existing instance | 0 |
| `list_read_s()` with a lazy queryset | 1 |

Step 3 moved payload classification, field inspection, lookup construction,
relation planning, read validation, and output transformation into typed,
execution-mode-independent helpers. The frozen query-count suite retained all
six values above. The broader non-performance regression suite completed with
1,146 passing tests, including ten new no-database transformation tests.

Step 4 added the asynchronous serializer facade with these query counts:

| Version 3 async operation | Primary-key target | Loaded target |
| --- | ---: | ---: |
| `acreate()` | 1 | N/A |
| `aget()` | 1 | N/A |
| `aupdate()` | 2 | 1 |
| `adestroy()` | 2 | 1 |

The loaded-target paths deliberately avoid a redundant lookup. After Step 4,
the broader non-performance regression suite completed with 1,172 passing
tests.

Step 5 added native synchronous serializer CRUD with the same query counts:

| Version 3 sync operation | Primary-key target | Loaded target |
| --- | ---: | ---: |
| `create()` | 1 | N/A |
| `get()` | 1 | N/A |
| `update()` | 2 | 1 |
| `destroy()` | 2 | 1 |

The synchronous executor uses Django's synchronous ORM directly. Its internal
counterparts are `get_object()` and `get_objects()`; asynchronous retrieval is
explicitly named `aget_object()` and `aget_objects()`.
