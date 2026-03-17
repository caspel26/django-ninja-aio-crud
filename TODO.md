# 📋 TODO — django-ninja-aio-crud

> Tracked improvement tasks, organized by priority and category.

---

## ✅ Completed

| # | Task | File(s) | Version | Description |
|---|------|---------|---------|-------------|
| 1 | ~~Bounded `_relation_cache`~~ | `models/utils.py` | v2.25.0 | Replaced unbounded dict with LRU cache (`maxsize=512`). |
| 2 | ~~Mutable default arguments~~ | `schemas/helpers.py` | — | Not a bug: Pydantic v2 deep-copies mutable defaults per instance. `Field(default_factory=...)` also incompatible with `ninja.Schema` root validator. |
| 3 | ~~Bulk operations~~ | `models/utils.py`, `views/api.py` | — | Added `bulk_create_view`, `bulk_update_view`, `bulk_delete_view` with partial success semantics, `BulkResultSchema` response, and optimized bulk delete. |
| 4 | ~~Custom actions decorator~~ | `decorators/actions.py`, `views/api.py` | — | DRF-style `@action` decorator for `APIViewSet` — detail/list actions, multi-method, auth inheritance, custom decorators, OpenAPI metadata. |

---

## 🟠 High Priority

### Features

| # | Task | File(s) | Description |
|---|------|---------|-------------|
| 4 | Soft delete mixin | `views/mixins.py` | Add `SoftDeleteViewSetMixin` — override delete to set a flag, auto-filter soft-deleted records from list/retrieve, optional restore endpoint. |
| 5 | Ordering / sorting | `views/api.py` | Add native `order_by` query parameter on list views with dynamic ordering schema generation. |
| 6 | Full-text search mixin | `views/mixins.py` | Add `SearchViewSetMixin` — integrate Django `SearchVector` / `SearchQuery` for PostgreSQL full-text search. |
| 7 | Aggregation endpoints | `views/mixins.py` | Add `AggregationViewSetMixin` — COUNT, SUM, AVG, MIN, MAX on list views for dashboard/analytics use cases without downloading all data. |
| 8 | ETag / Conditional requests | `views/api.py`, `helpers/` | Support HTTP caching with `ETag`, `If-None-Match`, `If-Modified-Since` on retrieve/list to reduce traffic and DB load. |
| 9 | Multi-tenancy mixin | `views/mixins.py`, `models/` | Add `TenantViewSetMixin` — automatic tenant filtering on all queries based on header or JWT claim. Essential for SaaS. |

### Reliability

| # | Task | File(s) | Description |
|---|------|---------|-------------|
| 10 | Deadlock retry in `aatomic` | `decorators/views.py:22-60` | Add configurable exponential backoff with deadlock detection to the atomic transaction decorator. |
| 11 | Partial update validation | `models/utils.py`, `views/api.py` | PATCH endpoints silently accept empty payloads. Add optional validation requiring at least one field. |

---

## 🟡 Medium Priority

### API & Schema

| # | Task | File(s) | Description |
|---|------|---------|-------------|
| 12 | Runtime API introspection | `api.py` | Add `get_registered_viewsets()`, `get_endpoint_info(path)`, `get_viewset(model)` for runtime inspection. |
| 13 | Cursor-based pagination | `views/api.py:267` | Add cursor-based pagination option alongside `PageNumberPagination` for large datasets. |
| 14 | Conditional decorators | `schemas/helpers.py:205-209` | Allow conditional application in `DecoratorsSchema` (e.g., throttle only for unauthenticated users). |
| 15 | Nested validation error paths | `exceptions.py` | Return full field paths for nested object validation failures, not just top-level errors. |

### Performance & Data

| # | Task | File(s) | Description |
|---|------|---------|-------------|
| 16 | Metrics / instrumentation hooks | — | Add optional hook points for external metrics (Prometheus, StatsD) — operation counts, latencies. |
| 17 | Read operation caching | — | Add optional `@cache_query` decorator with configurable TTL and invalidation strategy. |
| 18 | Optimistic locking | — | Add optional version field support for concurrency control on update operations. |
| 19 | Bulk M2M set replacement | `helpers/api.py` | Add "replace entire set" operation alongside existing add/remove on M2M endpoints. |

### Extensibility & Data

| # | Task | File(s) | Description |
|---|------|---------|-------------|
| 20 | Async signal/event system | `signals.py` | Async signals for CRUD events (`pre_create`, `post_create`, `pre_update`, `post_update`, `pre_delete`, `post_delete`) — external hooks without modifying viewsets. |
| 21 | Field-level read permissions | `models/serializers.py` | Show/hide fields in ReadSerializer based on user role (e.g., `email` visible only to admins). |
| 22 | Nested resource routing | `views/api.py`, `helpers/` | Support nested resources like `/authors/{id}/books/` with full CRUD on the sub-resource, beyond existing M2M support. |
| 23 | Export mixin | `views/mixins.py` | Add `ExportViewSetMixin` — `/export` endpoint generating CSV or JSON of a filtered queryset, reusing existing filter mixins. |
| 24 | Batch transaction endpoint | `views/mixins.py` | Add `BatchViewSetMixin` — `POST /batch` executing multiple CRUD operations in a single atomic transaction with full rollback on error. |

---

## 🟢 Low Priority

### New Capabilities

| # | Task | Description |
|---|------|-------------|
| 25 | Streaming responses | Support for streaming large datasets (CSV export, file downloads). |
| 26 | WebSocket / SSE | Real-time update support beyond REST. |
| 27 | Scope-based permissions | Row-level security, field-level permissions, scope-based access control. |
| 28 | Audit trail mixin | Built-in `created_by`, `modified_by`, change history tracking. |

### Infrastructure

| # | Task | Description |
|---|------|-------------|
| 29 | Composite key support | Multi-field primary keys — all code currently assumes single-field PKs. |
| 30 | Async savepoint management | Expose savepoints in `AsyncAtomicContextManager` for nested transactions. |
| 31 | Deprecation warnings system | Runtime deprecation warnings and endpoint versioning strategy. |
| 32 | JSON Schema customization | Utilities for custom examples, OpenAPI discriminators, schema composition. |
| 33 | Context propagation | Mechanism for propagating request context (user, tenant) through the async call stack. |
| 34 | Rate limiting per-viewset | Granular throttling per viewset/endpoint (e.g., max 100 req/min on create, 1000 on list), beyond the global throttling on NinjaAIO. |
| 35 | Health check endpoint | Auto-generated `/health` endpoint with DB connectivity check, cache status, registered viewset status. Useful for Kubernetes liveness/readiness probes. |
| 36 | OpenAPI tags auto-generation | Automatic OpenAPI tag generation grouped by Django model/app, with descriptions derived from model docstrings. |
