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

---

## High Priority

| # | Task | File(s) | Description |
|---|------|---------|-------------|
| 21 | Multi-tenancy mixin | `views/mixins.py` | `TenantViewSetMixin` — auto tenant filtering on all queries from header or JWT claim. |
| 22 | Aggregation endpoints | `views/mixins.py` | `AggregationViewSetMixin` — COUNT, SUM, AVG, MIN, MAX on list views for dashboards. |
| 23 | Field selection | `views/api.py` | `?fields=id,name,email` — select only needed fields in response. Reduces payload, improves performance. |
| 24 | Nested writes | `models/utils.py`, `views/api.py` | Create parent + children in one atomic request. `POST /order` with `{"items": [...]}`. |
| 25 | File upload mixin | `views/mixins.py` | `FileUploadViewSetMixin` — `POST /{pk}/upload` with `multipart/form-data`, configurable storage (local, S3). |
| 26 | Auto admin inlines | `admin.py` | Extend `@register_admin` to auto-generate `InlineModelAdmin` for FK/M2M relations. |
| 27 | Admin actions from ViewSet | `admin.py` | `@action` endpoints become available as Django Admin actions. `@action("publish")` → admin "Publish selected" action. |
| 28 | ETag / Conditional requests | `views/api.py` | HTTP caching with `ETag`, `If-None-Match`, `If-Modified-Since` on retrieve/list. |
| 29 | Deadlock retry in `aatomic` | `decorators/views.py` | Configurable exponential backoff with deadlock detection. |

---

## Medium Priority

| # | Task | File(s) | Description |
|---|------|---------|-------------|
| 30 | Simple multi-field search | `views/mixins.py` | `SearchViewSetMixin` — `?search=john` searches across configurable fields with `icontains`. Works on all DBs. |
| 31 | Idempotency keys | `decorators/`, `views/api.py` | `Idempotency-Key` header on POST — cache response, return cached on retry. Prevents double-creation for payments/orders. |
| 32 | NinjaAIO theme/branding | `api.py` | Custom logo, colors, title on Swagger UI via `NinjaAIO(logo_url=..., theme_color=...)`. |
| 33 | API Explorer in Django Admin | `admin.py`, `templates/` | Embedded API tester in admin panel — browse endpoints, send requests, see responses. Swagger-like but inside admin. |
| 34 | Admin validator sync | `admin.py`, `forms.py` | Admin forms auto-use `CreateSerializer`/`UpdateSerializer` Pydantic validators. Single source of truth for validation. |
| 35 | Admin audit log | `admin.py`, `models/` | Unified audit log for API + admin actions. Same table, same format — who changed what, from where. |
| 36 | Admin dashboard widget | `admin.py`, `templates/` | Home widget showing model counts, recent changes, API stats. Zero config. |
| 37 | Field-level read permissions | `models/serializers.py` | Show/hide fields in ReadSerializer based on user role. |
| 38 | Optimistic locking | `models/utils.py` | Version field for concurrency control on updates. |
| 39 | Bulk M2M set replacement | `helpers/api.py` | "Replace entire set" operation alongside add/remove on M2M endpoints. |
| 40 | Nested resource routing | `views/api.py`, `helpers/` | `/authors/{id}/books/` with full CRUD on sub-resources. |
| 41 | Export mixin | `views/mixins.py` | `ExportViewSetMixin` — CSV/JSON export of filtered querysets. |
| 42 | Audit trail mixin | `views/mixins.py` | Auto-log create/update/delete to audit table with `created_by`, `changed_fields`, `timestamp`. |
| 43 | Draft/Publish pattern | `views/mixins.py` | `DraftPublishViewSetMixin` — draft/published state management. |
| 44 | Webhook mixin | `views/mixins.py` | Async HTTP POST to configured URLs on CRUD events with retry. |
| 45 | Nested validation error paths | `exceptions.py` | Full field paths for nested object validation failures. |
| 46 | Auto-form generation | `forms.py` (new) | Generate Django Forms from `schema_in` — server-side rendering with HTMX/Alpine.js. Template tag `{% ninja_form "articles" "create" %}`. |
| 47 | Response compression | `api.py`, `middleware/` | Auto GZip/Brotli for large responses. Configurable threshold. |

---

## Low Priority

| # | Task | Description |
|---|------|-------------|
| 48 | Metrics / instrumentation hooks | Optional hook points for Prometheus, StatsD — operation counts, latencies. |
| 49 | Read operation caching | `@cache_query` decorator with configurable TTL and invalidation. |
| 50 | Batch transaction endpoint | `POST /batch` executing multiple CRUD operations in a single atomic transaction. |
| 51 | Rate limiting per-viewset | Granular throttling per endpoint beyond global NinjaAIO throttling. |
| 52 | Health check endpoint | Auto-generated `/health` with DB connectivity check. |
| 53 | Async savepoint management | Expose savepoints in `AsyncAtomicContextManager`. |
