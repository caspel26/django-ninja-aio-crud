# Comparison with 2.36

Five process runs per implementation and database, alternating process order, on the same machine with Python 3.14.0 and identical dependencies. No other test processes ran during measurement. Baseline: tag `v2.36.0` (`5a07d014`). Previous v3: `70fbb48`. Candidate: FK aliases built into the initial schema class and one thread bridge for eligible async bulk creates. See [raw measurements](results/v3-comparison.json).

## sqlite

| Case | 2.36 ms | Previous v3 ms | Optimized v3 ms | Final vs 2.36 | Queries: 2.36 / v3 |
| --- | ---: | ---: | ---: | ---: | ---: |
| warm_create_schema | 0.0001 | 0.0007 | 0.0007 | +753.0% | 0 / 0 |
| cold_create_schema | 0.1247 | 0.1415 | 0.1360 | +9.0% | 0 / 0 |
| cold_fk_create_schema | 0.1503 | 0.3028 | 0.1770 | +17.8% | 0 / 0 |
| single_read_with_relations | 0.6950 | 0.7237 | 0.7225 | +3.9% | 2 / 2 |
| batch_read_100 | 3.5671 | 3.7267 | 3.6972 | +3.6% | 2 / 2 |
| batch_read_500 | 16.0977 | 15.7420 | 15.8464 | -1.6% | 2 / 2 |
| bulk_create_100 | 25.3674 | 29.2089 | 6.6684 | -73.7% | 100 / 300 |

## postgresql

| Case | 2.36 ms | Previous v3 ms | Optimized v3 ms | Final vs 2.36 | Queries: 2.36 / v3 |
| --- | ---: | ---: | ---: | ---: | ---: |
| warm_create_schema | 0.0001 | 0.0007 | 0.0007 | +753.0% | 0 / 0 |
| cold_create_schema | 0.1233 | 0.1364 | 0.1374 | +11.4% | 0 / 0 |
| cold_fk_create_schema | 0.1508 | 0.3003 | 0.1836 | +21.8% | 0 / 0 |
| single_read_with_relations | 0.9515 | 0.9416 | 0.9836 | +3.4% | 2 / 2 |
| batch_read_100 | 4.0557 | 4.2724 | 4.2780 | +5.5% | 2 / 2 |
| batch_read_500 | 16.9682 | 16.3833 | 17.2718 | +1.8% | 2 / 2 |
| bulk_create_100 | 31.7003 | 45.6602 | 16.5339 | -47.8% | 100 / 300 |

## What changed

FK input aliases are applied through Ninja custom fields before Pydantic builds the class. The second Pydantic subclass is no longer needed. Both FK spellings, existing validation aliases (including AliasChoices and AliasPath), serialization aliases, defaults, and validators remain supported. Cold FK generation still costs slightly more than 2.36, but the absolute difference is small and schemas are cached.

Eligible async bulk creates execute the synchronous item loop through one thread-pool call. Each item retains its transaction; query counts remain 300 for 100 creations (BEGIN/INSERT/COMMIT). Sync hook failures still roll back only the failed item. Models with async create/custom/reactive hooks, FK or M2M fields, nested writes, custom async saves, managers, or querysets retain the async path. This benchmark exercises a simple model eligible for the optimization; it does not establish the same speedup for those fallback cases.

These are local microbenchmarks, not server throughput. SQLite uses an in-memory database; PostgreSQL 17 uses a fresh local database for each process. Small timing differences can reflect machine noise. The JSON retains every process median, iteration count, query count, Python version, and dependency version.

## Reproduce

Create separate editable environments for tag `v2.36.0` and the current branch with the exact dependency versions in the JSON. Run the current harness with each environment’s Python:

```bash
/path/to/baseline-env/bin/python benchmarks/compare_v3.py --output /tmp/baseline.json
/path/to/v3-env/bin/python benchmarks/compare_v3.py --output /tmp/v3.json
```

For PostgreSQL, install psycopg in both environments and create a **fresh, empty benchmark database for each process**. Set `BENCHMARK_PGDATABASE` and the standard `PGUSER`, `PGPASSWORD`, `PGHOST`, and `PGPORT` variables. The harness creates its own model tables and seed rows; an existing set of benchmark tables causes the run to fail. Remove the dedicated database afterward.

The harness checks payloads, relation counts, and bulk successes. It clears both Ninja factory caches and framework caches for cold schema cases, captures query counts outside timing loops, and removes created rows between write iterations. Its legacy model declarations deliberately work in both implementations.
