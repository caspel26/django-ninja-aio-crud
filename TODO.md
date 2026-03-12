# 📋 TODO — django-ninja-aio-crud

> Tracked improvement tasks, organized by priority and category.

---

## 🔴 Critical

| # | Task | File(s) | Description |
|---|------|---------|-------------|
| 1 | Bounded `_relation_cache` | `models/utils.py:121` | Class-level dict grows unbounded in long-running processes. Replace with LRU-bounded cache (`maxsize=512`). |
| 2 | Mutable default arguments | `schemas/helpers.py:79-80, 205-209` | `DecoratorsSchema`, `M2MRelationSchema`, query schemas use `[]` / `{}` as defaults — all instances share the same object. Use `Field(default_factory=...)`. |

---

## 🟠 High Priority

### Features

| # | Task | File(s) | Description |
|---|------|---------|-------------|
| 3 | Soft delete mixin | `views/mixins.py` | Add `SoftDeleteViewSetMixin` — override delete to set a flag, auto-filter soft-deleted records from list/retrieve, optional restore endpoint. |
| 4 | Bulk operations | `models/utils.py`, `views/api.py` | Add `bulk_create_view`, `bulk_update_view`, `bulk_delete_view` — only single-item CRUD exists today. |
| 5 | Ordering / sorting | `views/api.py` | Add native `order_by` query parameter on list views with dynamic ordering schema generation. |
| 6 | Full-text search mixin | `views/mixins.py` | Add `SearchViewSetMixin` — integrate Django `SearchVector` / `SearchQuery` for PostgreSQL full-text search. |

### Reliability

| # | Task | File(s) | Description |
|---|------|---------|-------------|
| 7 | Deadlock retry in `aatomic` | `decorators/views.py:22-60` | Add configurable exponential backoff with deadlock detection to the atomic transaction decorator. |
| 8 | Partial update validation | `models/utils.py`, `views/api.py` | PATCH endpoints silently accept empty payloads. Add optional validation requiring at least one field. |

---

## 🟡 Medium Priority

### API & Schema

| # | Task | File(s) | Description |
|---|------|---------|-------------|
| 9 | Runtime API introspection | `api.py` | Add `get_registered_viewsets()`, `get_endpoint_info(path)`, `get_viewset(model)` for runtime inspection. |
| 10 | Cursor-based pagination | `views/api.py:267` | Add cursor-based pagination option alongside `PageNumberPagination` for large datasets. |
| 11 | Conditional decorators | `schemas/helpers.py:205-209` | Allow conditional application in `DecoratorsSchema` (e.g., throttle only for unauthenticated users). |
| 12 | Nested validation error paths | `exceptions.py` | Return full field paths for nested object validation failures, not just top-level errors. |

### Performance & Data

| # | Task | File(s) | Description |
|---|------|---------|-------------|
| 13 | Metrics / instrumentation hooks | — | Add optional hook points for external metrics (Prometheus, StatsD) — operation counts, latencies. |
| 14 | Read operation caching | — | Add optional `@cache_query` decorator with configurable TTL and invalidation strategy. |
| 15 | Optimistic locking | — | Add optional version field support for concurrency control on update operations. |
| 16 | Bulk M2M set replacement | `helpers/api.py` | Add "replace entire set" operation alongside existing add/remove on M2M endpoints. |

---

## 🟢 Low Priority

### New Capabilities

| # | Task | Description |
|---|------|-------------|
| 17 | Streaming responses | Support for streaming large datasets (CSV export, file downloads). |
| 18 | WebSocket / SSE | Real-time update support beyond REST. |
| 19 | Scope-based permissions | Row-level security, field-level permissions, scope-based access control. |
| 20 | Audit trail mixin | Built-in `created_by`, `modified_by`, change history tracking. |

### Infrastructure

| # | Task | Description |
|---|------|-------------|
| 21 | Composite key support | Multi-field primary keys — all code currently assumes single-field PKs. |
| 22 | Async savepoint management | Expose savepoints in `AsyncAtomicContextManager` for nested transactions. |
| 23 | Deprecation warnings system | Runtime deprecation warnings and endpoint versioning strategy. |
| 24 | JSON Schema customization | Utilities for custom examples, OpenAPI discriminators, schema composition. |
| 25 | Context propagation | Mechanism for propagating request context (user, tenant) through the async call stack. |
