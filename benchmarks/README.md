# v3 comparison with 2.36

Five process runs per implementation on the same machine, Python 3.14, and identical dependencies. Baseline: tag `v2.36.0` (`5a07d014`). Candidate: the v3 branch with the relation cache optimization. See [raw measurements](results/v3-comparison.json).

| Case | 2.36 median ms | v3 before ms | v3 final ms | Final vs 2.36 | Queries: 2.36 / v3 |
| --- | ---: | ---: | ---: | ---: | ---: |
| warm_create_schema | 0.0001 | 0.0007 | 0.0007 | +703.6% | 0 / 0 |
| cold_create_schema | 0.1236 | 0.1375 | 0.1357 | +9.8% | 0 / 0 |
| cold_fk_create_schema | 0.1496 | 0.2947 | 0.2985 | +99.5% | 0 / 0 |
| single_read_with_relations | 0.6939 | 0.8018 | 0.7175 | +3.4% | 2 / 2 |
| batch_read_100 | 3.5990 | 3.6103 | 3.7148 | +3.2% | 2 / 2 |
| batch_read_500 | 15.9008 | 15.4277 | 15.8909 | -0.1% | 2 / 2 |
| bulk_create_100 | 25.2658 | 30.4164 | 29.0402 | +14.9% | 100 / 300 |

The final single-object read is 10.5% faster than the v3 implementation before optimization. It avoids an unnecessary async prefetch adapter call when Django relation caches prove every requested relation is loaded. Unloaded or nested paths still use Django prefetch. Three regression tests cover loaded, unloaded, and nested paths.

Warm schema lookup remains below one microsecond despite its large relative percentage. Cold FK schema generation costs about 0.15 ms more because v3 builds validation aliases accepting both FK names and attnames. These classes are cached; this is a startup cost.

Bulk creation costs about 15% more in this workload. Query counts include transaction control: v3 isolates every item with BEGIN/INSERT/COMMIT so hook failures roll back that item while other items can succeed. The baseline issues one INSERT per item. This protection remains enabled.

These are local microbenchmarks, not server throughput or PostgreSQL measurements. The baseline and pre-optimization runs alternated process order; final runs followed the optimization with other test processes stopped. Run order and system noise can affect a few percent. Per-process medians and iteration counts are retained in the JSON; do not treat small differences as universal improvements.

## Reproduce

Create separate editable environments for tag `v2.36.0` and the current branch with the exact dependency versions in the JSON. Run the current harness with each environment’s Python:

```bash
/path/to/baseline-env/bin/python benchmarks/compare_v3.py --output /tmp/baseline.json
/path/to/v3-env/bin/python benchmarks/compare_v3.py --output /tmp/v3.json
```

The harness checks payloads, relation counts, and bulk successes. It clears both Ninja factory caches and framework caches for cold schema cases, captures query counts outside timing loops, and removes created rows between write iterations. Its legacy model declarations deliberately work in both implementations.
