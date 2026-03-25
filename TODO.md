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
| 12 | ~~Soft delete mixin~~ | `views/mixins.py` | v2.29.0 | `SoftDeleteViewSetMixin` — flag-based delete, auto-filter, `POST /restore`, `DELETE /hard-delete`. |
| 13 | ~~Performance: N+1 M2M batch~~ | `helpers/api.py` | v2.29.0 | Batched `filter(pk__in=...)` in M2M validation instead of per-PK queries. |
| 14 | ~~Performance: batch field resolve~~ | `models/utils.py` | v2.29.0 | Single `sync_to_async` for all field objects instead of N thread pool switches. |
| 15 | ~~Performance: COUNT optimization~~ | `views/api.py` | v2.29.0 | `.acount()` instead of `.values(pk).acount()` subquery. |
| 16 | ~~Performance: prefetch without refetch~~ | `models/utils.py` | v2.29.0 | `aprefetch_related_objects` instead of full object refetch after update. |
| 17 | ~~Performance: cache key id()~~ | `models/utils.py` | v2.29.0 | `id()` O(1) instead of `str()` O(n) for cache keys. |
| 18 | ~~Performance: cached_property~~ | `models/utils.py` | v2.29.0 | `pk_field_type`, `model_fields`, `model_name`, `model_pk_name` computed once. |
| 19 | ~~Performance: no .copy() on cache~~ | `models/utils.py` | v2.29.0 | Removed redundant list copies on cache hit/miss. |
| 20 | ~~Performance: getattr vs model_dump~~ | `views/api.py` | v2.29.0 | `_get_pk` uses direct attribute access instead of full schema serialization. |
| 21 | ~~Multi-field search~~ | `views/mixins.py` | v2.29.0 | `SearchViewSetMixin` — `?search=` across configurable fields with OR logic, composable with all filter mixins. |

---

## High Priority

| # | Task | File(s) | Description |
|---|------|---------|-------------|
| 21 | `@on` detail action shorthand | `decorators/actions.py` | `@on("publish", detail=True)` — pre-fetches object, runs hooks, you write only the logic. Wrapper over `@action` with zero boilerplate. |
| 22 | Reactive model hooks | `models/serializers.py`, `models/` | `@on_create`, `@on_update("status")`, `@on_delete` decorators on ModelSerializer AND Serializer. Field-level triggers (`@on_update("status")` fires only when `status` changes). Works from API, admin, shell. |
| 23 | Multi-tenancy mixin | `views/mixins.py` | `TenantViewSetMixin` — auto tenant filtering on all queries from header or JWT claim. |
| 24 | Aggregation endpoints | `views/mixins.py` | `AggregationViewSetMixin` — COUNT, SUM, AVG, MIN, MAX on list views for dashboards. |
| 25 | Field selection | `views/api.py` | `?fields=id,name,email` — select only needed fields in response. Reduces payload, improves performance. |
| 26 | Nested writes | `models/utils.py`, `views/api.py` | Create parent + children in one atomic request. `POST /order` with `{"items": [...]}`. |
| 27 | File upload mixin | `views/mixins.py` | `FileUploadViewSetMixin` — `POST /{pk}/upload` with `multipart/form-data`, configurable storage (local, S3). |
| 28 | Auto admin inlines | `admin.py` | Extend `@register_admin` to auto-generate `InlineModelAdmin` for FK/M2M relations. |
| 29 | Admin actions from ViewSet | `admin.py` | `@action` endpoints become available as Django Admin actions. `@action("publish")` → admin "Publish selected" action. |
| 30 | ETag / Conditional requests | `views/api.py` | HTTP caching with `ETag`, `If-None-Match`, `If-Modified-Since` on retrieve/list. |
| 31 | Deadlock retry in `aatomic` | `decorators/views.py` | Configurable exponential backoff with deadlock detection. |

---

## Medium Priority

| # | Task | File(s) | Description |
|---|------|---------|-------------|
| 32 | Idempotency keys | `decorators/`, `views/api.py` | `Idempotency-Key` header on POST — cache response, return cached on retry. Prevents double-creation for payments/orders. |
| 33 | NinjaAIO theme/branding | `api.py` | Custom logo, colors, title on Swagger UI via `NinjaAIO(logo_url=..., theme_color=...)`. |
| 34 | API Explorer in Django Admin | `admin.py`, `templates/` | Embedded API tester in admin panel — browse endpoints, send requests, see responses. Swagger-like but inside admin. |
| 35 | Admin validator sync | `admin.py`, `forms.py` | Admin forms auto-use `CreateSerializer`/`UpdateSerializer` Pydantic validators. Single source of truth for validation. |
| 36 | Admin audit log | `admin.py`, `models/` | Unified audit log for API + admin actions. Same table, same format — who changed what, from where. |
| 37 | Admin dashboard widget | `admin.py`, `templates/` | Home widget showing model counts, recent changes, API stats. Zero config. |
| 38 | Field-level read permissions | `models/serializers.py` | Show/hide fields in ReadSerializer based on user role. |
| 39 | Optimistic locking | `models/utils.py` | Version field for concurrency control on updates. |
| 40 | Bulk M2M set replacement | `helpers/api.py` | "Replace entire set" operation alongside add/remove on M2M endpoints. |
| 41 | Nested resource routing | `views/api.py`, `helpers/` | `/authors/{id}/books/` with full CRUD on sub-resources. |
| 42 | Export mixin | `views/mixins.py` | `ExportViewSetMixin` — CSV/JSON export of filtered querysets. |
| 43 | Audit trail mixin | `views/mixins.py` | Auto-log create/update/delete to audit table with `created_by`, `changed_fields`, `timestamp`. |
| 44 | Draft/Publish pattern | `views/mixins.py` | `DraftPublishViewSetMixin` — draft/published state management. |
| 45 | Webhook mixin | `views/mixins.py` | Async HTTP POST to configured URLs on CRUD events with retry. |
| 46 | Nested validation error paths | `exceptions.py` | Full field paths for nested object validation failures. |
| 47 | Auto-form generation | `forms.py` (new) | Generate Django Forms from `schema_in` — server-side rendering with HTMX/Alpine.js. Template tag `{% ninja_form "articles" "create" %}`. |
| 48 | Response compression | `api.py`, `middleware/` | Auto GZip/Brotli for large responses. Configurable threshold. |

---

## Low Priority

| # | Task | Description |
|---|------|-------------|
| 49 | Metrics / instrumentation hooks | Optional hook points for Prometheus, StatsD — operation counts, latencies. |
| 50 | Read operation caching | `@cache_query` decorator with configurable TTL and invalidation. |
| 51 | Batch transaction endpoint | `POST /batch` executing multiple CRUD operations in a single atomic transaction. |
| 52 | Rate limiting per-viewset | Granular throttling per endpoint beyond global NinjaAIO throttling. |
| 53 | Health check endpoint | Auto-generated `/health` with DB connectivity check. |
| 54 | Async savepoint management | Expose savepoints in `AsyncAtomicContextManager`. |
