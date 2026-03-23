# TODO — django-ninja-aio-crud

> Tracked improvement tasks, organized by priority.

---

## Completed

| # | Task | File(s) | Version | Description |
|---|------|---------|---------|-------------|
| 1 | ~~Bounded `_relation_cache`~~ | `models/utils.py` | v2.25.0 | LRU cache (`maxsize=512`). |
| 2 | ~~Mutable default arguments~~ | `schemas/helpers.py` | — | Not a bug: Pydantic v2 deep-copies. |
| 3 | ~~Bulk operations~~ | `models/utils.py`, `views/api.py` | v2.27.0 | Bulk create/update/delete with partial success. |
| 4 | ~~Custom actions decorator~~ | `decorators/actions.py`, `views/api.py` | v2.27.0 | `@action` for detail/list endpoints. |
| 5 | ~~Ordering / sorting~~ | `views/api.py` | v2.27.0 | `ordering_fields` and `default_ordering`. |
| 6 | ~~Granular permission system~~ | `views/mixins.py`, `exceptions.py` | v2.28.0 | `PermissionViewSetMixin`, `RoleBasedPermissionMixin`, `ForbiddenError`. |
| 7 | ~~Auto-generate Django Admin~~ | `admin.py`, `models/serializers.py` | v2.28.0 | `@register_admin`, `as_admin()`, `model_admin_factory()`. |
| 8 | ~~Cursor-based pagination~~ | `views/api.py`, `helpers/api.py` | v2.28.0 | List views return QuerySet to `@paginate`. |
| 9 | ~~Bulk response fields~~ | `views/api.py`, `models/utils.py` | v2.28.0 | `bulk_response_fields` attribute. |
| 10 | ~~Partial update validation~~ | `models/utils.py`, `views/api.py` | v2.28.0 | `require_update_fields = True`. |
| 11 | ~~Operation hooks~~ | `views/api.py` | v2.28.0 | `on_before_operation`, `on_before_object_operation`, `on_list_queryset`. |

---

## High Priority

| # | Task | File(s) | Description |
|---|------|---------|-------------|
| 12 | Soft delete mixin | `views/mixins.py` | `SoftDeleteViewSetMixin` — flag-based delete, auto-filter from list/retrieve, `POST /restore` endpoint. |
| 13 | Multi-tenancy mixin | `views/mixins.py` | `TenantViewSetMixin` — auto tenant filtering on all queries from header or JWT claim. |
| 14 | Aggregation endpoints | `views/mixins.py` | `AggregationViewSetMixin` — COUNT, SUM, AVG, MIN, MAX on list views for dashboards. |
| 15 | ETag / Conditional requests | `views/api.py` | HTTP caching with `ETag`, `If-None-Match`, `If-Modified-Since` on retrieve/list. |
| 16 | Deadlock retry in `aatomic` | `decorators/views.py` | Configurable exponential backoff with deadlock detection. |

---

## Medium Priority

| # | Task | File(s) | Description |
|---|------|---------|-------------|
| 17 | Field-level read permissions | `models/serializers.py` | Show/hide fields in ReadSerializer based on user role. |
| 18 | Optimistic locking | `models/utils.py` | Version field for concurrency control on updates. |
| 19 | Bulk M2M set replacement | `helpers/api.py` | "Replace entire set" operation alongside add/remove on M2M endpoints. |
| 20 | Nested resource routing | `views/api.py`, `helpers/` | `/authors/{id}/books/` with full CRUD on sub-resources. |
| 21 | Export mixin | `views/mixins.py` | `ExportViewSetMixin` — CSV/JSON export of filtered querysets. |
| 22 | Audit trail mixin | `views/mixins.py` | Auto-log create/update/delete to audit table with `created_by`, `changed_fields`, `timestamp`. |
| 23 | Draft/Publish pattern | `views/mixins.py` | `DraftPublishViewSetMixin` — draft/published state management. |
| 24 | Webhook mixin | `views/mixins.py` | Async HTTP POST to configured URLs on CRUD events with retry. |
| 25 | Nested validation error paths | `exceptions.py` | Full field paths for nested object validation failures. |
| 26 | Auto-form generation | `forms.py` (new) | Generate Django Forms from `schema_in` — server-side rendering with HTMX/Alpine.js without duplicating schema definitions. Template tag `{% ninja_form "articles" "create" %}`. |
| 27 | Admin API dashboard widget | `admin.py`, `templates/` | Django admin widget showing API stats: registered endpoints, request counts, recent errors. Cockpit view for teams using admin panel alongside APIs. |

---

## Low Priority

| # | Task | Description |
|---|------|-------------|
| 28 | Metrics / instrumentation hooks | Optional hook points for Prometheus, StatsD — operation counts, latencies. |
| 29 | Read operation caching | `@cache_query` decorator with configurable TTL and invalidation. |
| 30 | Batch transaction endpoint | `POST /batch` executing multiple CRUD operations in a single atomic transaction. |
| 31 | Rate limiting per-viewset | Granular throttling per endpoint beyond global NinjaAIO throttling. |
| 32 | Health check endpoint | Auto-generated `/health` with DB connectivity check. |
| 33 | Async savepoint management | Expose savepoints in `AsyncAtomicContextManager`. |
