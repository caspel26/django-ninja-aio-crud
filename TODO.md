# 📋 TODO — django-ninja-aio-crud

> Tracked improvement tasks, organized by priority and category.

---

## ✅ Completed

| # | Task | File(s) | Version | Description |
|---|------|---------|---------|-------------|
| 1 | ~~Bounded `_relation_cache`~~ | `models/utils.py` | v2.25.0 | Replaced unbounded dict with LRU cache (`maxsize=512`). |
| 2 | ~~Mutable default arguments~~ | `schemas/helpers.py` | — | Not a bug: Pydantic v2 deep-copies mutable defaults per instance. `Field(default_factory=...)` also incompatible with `ninja.Schema` root validator. |
| 3 | ~~Bulk operations~~ | `models/utils.py`, `views/api.py` | — | Added `bulk_create_view`, `bulk_update_view`, `bulk_delete_view` with partial success semantics, `BulkResultSchema` response, and optimized bulk delete. |
| 4 | ~~Custom actions decorator~~ | `decorators/actions.py`, `views/api.py` | — | `@action` decorator for `APIViewSet` — detail/list actions, multi-method, auth inheritance, custom decorators, OpenAPI metadata. |
| 5 | ~~Ordering / sorting~~ | `views/api.py` | — | Native `ordering_fields` and `default_ordering` attributes with automatic query parameter generation, field validation, and multi-field support. |

---

## 🟠 High Priority

### Features

| # | Task | File(s) | Description |
|---|------|---------|-------------|
| 4 | Soft delete mixin | `views/mixins.py` | Add `SoftDeleteViewSetMixin` — override delete to set a flag, auto-filter soft-deleted records from list/retrieve, optional restore endpoint. |
| 5 | Full-text search mixin | `views/mixins.py` | Add `SearchViewSetMixin` — integrate Django `SearchVector` / `SearchQuery` for PostgreSQL full-text search. |
| 6 | Aggregation endpoints | `views/mixins.py` | Add `AggregationViewSetMixin` — COUNT, SUM, AVG, MIN, MAX on list views for dashboard/analytics use cases without downloading all data. |
| 7 | ETag / Conditional requests | `views/api.py`, `helpers/` | Support HTTP caching with `ETag`, `If-None-Match`, `If-Modified-Since` on retrieve/list to reduce traffic and DB load. |
| 8 | Multi-tenancy mixin | `views/mixins.py`, `models/` | Add `TenantViewSetMixin` — automatic tenant filtering on all queries based on header or JWT claim. Essential for SaaS. |
| 36 | Granular permission system | `views/mixins.py`, `views/api.py` | Add `PermissionViewSetMixin` with `has_permission(request)` and `has_object_permission(request, obj)` hooks. Add `RoleBasedPermission` mapping roles to allowed operations (`{"admin": ["create", "update", "delete"], "reader": ["list", "retrieve"]}`). |
| 37 | Auto-generate Django Admin from ModelSerializer | `admin.py` (new) | Add `ModelSerializer.as_admin()` and `@admin_registered` decorator — auto-generate `ModelAdmin` with `list_display`, `search_fields`, `list_filter` derived from `ReadSerializer` config. Zero extra boilerplate. |
| 38 | Webhook mixin | `views/mixins.py` | Add `WebhookViewSetMixin` — async HTTP POST to configured URLs on CRUD events (`on_create`, `on_update`, `on_delete`). Configurable per-event, with retry and timeout. Essential for SaaS integrations. |

### Reliability

| # | Task | File(s) | Description |
|---|------|---------|-------------|
| 9 | Deadlock retry in `aatomic` | `decorators/views.py:22-60` | Add configurable exponential backoff with deadlock detection to the atomic transaction decorator. |
| 10 | Partial update validation | `models/utils.py`, `views/api.py` | PATCH endpoints silently accept empty payloads. Add optional validation requiring at least one field. |

---

## 🟡 Medium Priority

### API & Schema

| # | Task | File(s) | Description |
|---|------|---------|-------------|
| 11 | Runtime API introspection | `api.py` | Add `get_registered_viewsets()`, `get_endpoint_info(path)`, `get_viewset(model)` for runtime inspection. |
| 12 | Cursor-based pagination | `views/api.py:267` | Add cursor-based pagination option alongside `PageNumberPagination` for large datasets. |
| 13 | Conditional decorators | `schemas/helpers.py:205-209` | Allow conditional application in `DecoratorsSchema` (e.g., throttle only for unauthenticated users). |
| 14 | Nested validation error paths | `exceptions.py` | Return full field paths for nested object validation failures, not just top-level errors. |

### Performance & Data

| # | Task | File(s) | Description |
|---|------|---------|-------------|
| 15 | Metrics / instrumentation hooks | — | Add optional hook points for external metrics (Prometheus, StatsD) — operation counts, latencies. |
| 16 | Read operation caching | — | Add optional `@cache_query` decorator with configurable TTL and invalidation strategy. |
| 17 | Optimistic locking | — | Add optional version field support for concurrency control on update operations. |
| 18 | Bulk M2M set replacement | `helpers/api.py` | Add "replace entire set" operation alongside existing add/remove on M2M endpoints. |

### Extensibility & Data

| # | Task | File(s) | Description |
|---|------|---------|-------------|
| 19 | Async signal/event system | `signals.py` | Async signals for CRUD events (`pre_create`, `post_create`, `pre_update`, `post_update`, `pre_delete`, `post_delete`) — external hooks without modifying viewsets. |
| 20 | Field-level read permissions | `models/serializers.py` | Show/hide fields in ReadSerializer based on user role (e.g., `email` visible only to admins). |
| 21 | Nested resource routing | `views/api.py`, `helpers/` | Support nested resources like `/authors/{id}/books/` with full CRUD on the sub-resource, beyond existing M2M support. |
| 22 | Export mixin | `views/mixins.py` | Add `ExportViewSetMixin` — `/export` endpoint generating CSV or JSON of a filtered queryset, reusing existing filter mixins. |
| 23 | Batch transaction endpoint | `views/mixins.py` | Add `BatchViewSetMixin` — `POST /batch` executing multiple CRUD operations in a single atomic transaction with full rollback on error. |
| 39 | Structured logging | `views/api.py`, `views/mixins.py` | Auto-log every CRUD operation with `user`, `model`, `operation`, `pk`, `duration_ms`. Overridable `on_log(request, operation, data)` hook. Compatible with structlog / python-json-logger. |
| 40 | Audit trail mixin | `views/mixins.py` | Add `AuditTrailViewSetMixin` — auto-log create/update/delete to a dedicated audit table with `created_by`, `changed_fields`, `timestamp`. |
| 41 | Draft/Publish pattern | `views/mixins.py` | Add `DraftPublishViewSetMixin` — manage draft/published state with `POST /publish` and `POST /unpublish` endpoints. Auto-filter drafts from list/retrieve for non-privileged users. Integrates with soft-delete (#4). |
| 42 | Import endpoint (CSV/JSON) | `views/mixins.py` | Add `ImportViewSetMixin` — `POST /import` accepting CSV or JSON file, row-level validation feedback, and optional async job mode with `GET /import/{job_id}/status` for large files. |

---

## 🟢 Low Priority

### New Capabilities

| # | Task | Description |
|---|------|-------------|
| 24 | Streaming responses | Support for streaming large datasets (CSV export, file downloads). |
| 25 | WebSocket / SSE | Real-time update support beyond REST. |
| 26 | Scope-based permissions | Row-level security, field-level permissions, scope-based access control. |
| 27 | Audit trail mixin | Built-in `created_by`, `modified_by`, change history tracking. |

### Infrastructure

| # | Task | Description |
|---|------|-------------|
| 28 | Composite key support | Multi-field primary keys — all code currently assumes single-field PKs. |
| 29 | Async savepoint management | Expose savepoints in `AsyncAtomicContextManager` for nested transactions. |
| 30 | Deprecation warnings system | Runtime deprecation warnings and endpoint versioning strategy. |
| 31 | JSON Schema customization | Utilities for custom examples, OpenAPI discriminators, schema composition. |
| 32 | Context propagation | Mechanism for propagating request context (user, tenant) through the async call stack. |
| 33 | Rate limiting per-viewset | Granular throttling per viewset/endpoint (e.g., max 100 req/min on create, 1000 on list), beyond the global throttling on NinjaAIO. |
| 34 | Health check endpoint | Auto-generated `/health` endpoint with DB connectivity check, cache status, registered viewset status. Useful for Kubernetes liveness/readiness probes. |
| 35 | OpenAPI tags auto-generation | Automatic OpenAPI tag generation grouped by Django model/app, with descriptions derived from model docstrings. |
| 43 | CLI management commands | Add `python manage.py ninja_aio list_viewsets`, `ninja_aio generate_client` (TypeScript/OpenAPI), `ninja_aio check_schema` for dev tooling and CI integration. |
| 44 | Plugin system | Registerable plugins on `NinjaAIO` — inject middleware, exception handlers, and schema modifications declaratively, similar to Django apps but scoped to the API layer. |
| 45 | OpenAPI auto-examples | Auto-generate `openapi_extra` examples from serializer defaults and field types. Add `@deprecated_action` decorator marking endpoints as `"deprecated": true` in the OpenAPI schema. |
| 46 | NinjaAIO Admin Dashboard | Django view embedding Swagger UI of all registered APIs directly inside the Django admin interface — useful for teams using both admin panel and APIs. |
| 47 | API versioning support | URL versioning (`/v1/`, `/v2/`) with automatic routing. Schema migration helpers for deprecating fields without breaking changes. |
