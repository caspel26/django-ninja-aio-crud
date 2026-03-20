# 📋 Release Notes

## 🏷️ [v2.27.0] - 2026-03-18

---

### ✨ New Features

#### ⚡ `@action` Decorator for Custom ViewSet Endpoints
> `ninja_aio/decorators/actions.py`, `ninja_aio/views/api.py`

Add custom endpoints to any `APIViewSet` using the `@action` decorator. Actions support detail (single instance) and list (collection) modes, multiple HTTP methods, auth inheritance, custom decorators, and full OpenAPI metadata.

```python
from ninja import Schema, Status
from ninja_aio.decorators import action

class CountSchema(Schema):
    count: int

@api.viewset(model=Article)
class ArticleViewSet(APIViewSet):
    # Detail action: operates on a single instance
    @action(detail=True, methods=["post"], url_path="activate")
    async def activate(self, request, pk):
        obj = await self.model_util.get_object(request, pk)
        obj.is_active = True
        await obj.asave()
        return Status(200, {"message": "activated"})

    # List action: operates on the collection
    @action(detail=False, methods=["get"], url_path="count", response=CountSchema)
    async def count(self, request):
        total = await self.model.objects.acount()
        return {"count": total}
```

**Key features:**

| Feature | Description |
|---|---|
| 🎯 `detail=True` | Auto-adds `{pk}` to URL, renamed to match model PK field |
| 🔗 `url_path` | Auto-generated from method name (`_` → `-`) if not provided |
| 🔐 Auth inheritance | `auth=NOT_SET` inherits from viewset per-verb auth |
| 🛡️ Survives `disable=["all"]` | Actions are always registered, even when CRUD is disabled |
| 🔄 Multiple methods | `methods=["get", "post"]` creates separate routes |
| 🎨 Decorators | `decorators=[aatomic]` applies custom wrappers |

---

#### 📦 Bulk Operations (Create, Update, Delete)
> `ninja_aio/models/utils.py`, `ninja_aio/views/api.py`, `ninja_aio/schemas/api.py`

Opt-in bulk endpoints for creating, updating, or deleting multiple objects in a single request with **partial success** semantics.

```python
@api.viewset(model=Article)
class ArticleViewSet(APIViewSet):
    bulk_operations = ["create", "update", "delete"]
```

**Generated endpoints:**

| Method | Path | Description |
|---|---|---|
| `POST` | `/{base}/bulk/` | Bulk create |
| `PATCH` | `/{base}/bulk/` | Bulk update |
| `DELETE` | `/{base}/bulk/` | Bulk delete |

**Response format** — `BulkResultSchema`:

```json
{
  "success": { "count": 2, "details": [1, 3] },
  "errors": { "count": 1, "details": [{"error": "Not found."}] }
}
```

**Design decisions:**

- ✅ **Partial success** — each item is processed independently; failures don't affect other items
- ✅ **PKs only** — `success.details` returns primary keys, not serialized objects
- ✅ **Optimized bulk delete** — single `DELETE ... WHERE pk IN (...)` query
- ✅ **Per-item hooks** — `parse_input_data()`, `custom_actions()`, `post_create()` called per item
- ✅ **Per-verb auth** — `post_auth` for create, `patch_auth` for update, `delete_auth` for delete

**New schemas:**

| Schema | Description |
|---|---|
| `BulkDetailSchema` | `{count: int, details: list}` |
| `BulkResultSchema` | `{success: BulkDetailSchema, errors: BulkDetailSchema}` |

**Refactored `ModelUtil` methods:**

| Method | Description |
|---|---|
| `_create_instance()` | Extracted from `create_s()` — creates object + runs hooks, returns model instance |
| `_update_instance()` | Extracted from `update_s()` — updates object + runs hooks, returns model instance |
| `bulk_create_s()` | Creates multiple objects, returns `(created_pks, error_details)` |
| `bulk_update_s()` | Updates multiple objects, returns `(updated_pks, error_details)` |
| `bulk_delete_s()` | Deletes multiple objects (single query), returns `(deleted_pks, error_details)` |
| `_format_bulk_error()` | Static helper for error formatting |

---

#### 🔀 Native Ordering / Sorting
> `ninja_aio/views/api.py`

Add native ordering to the list endpoint with two new `APIViewSet` attributes:

```python
@api.viewset(model=Article)
class ArticleViewSet(APIViewSet):
    ordering_fields = ["created_at", "title", "views"]
    default_ordering = "-created_at"
```

**How it works:**

- 📌 Automatically adds an `ordering` query parameter to the filters schema
- ✅ Validates each field against `ordering_fields` (invalid fields silently ignored)
- 🔄 Supports ascending (`field`), descending (`-field`), and multi-field (`-views,title`)
- 📦 `default_ordering` accepts a string or list; applied when no valid `?ordering` is provided
- 🛡️ `ordering` is popped from filters before `query_params_handler` runs — no interference with filter mixins
- ⚡ Completely disabled when `ordering_fields` is empty (default)

**New `APIViewSet` attributes:**

| Attribute | Type | Default | Description |
|---|---|---|---|
| `ordering_fields` | `list[str]` | `[]` | Fields allowed for ordering |
| `default_ordering` | `str \| list[str]` | `[]` | Default ordering when no `?ordering` param |

---

### 🔧 Improvements

#### 🏷️ `disable` Attribute Extended for Bulk Operations
> `ninja_aio/views/api.py`, `ninja_aio/types.py`

The `disable` attribute now supports bulk operation values:

| Value | Description |
|---|---|
| `bulk_create` | Disable bulk create endpoint |
| `bulk_update` | Disable bulk update endpoint |
| `bulk_delete` | Disable bulk delete endpoint |

#### 🎨 `DecoratorsSchema` Extended for Bulk Operations
> `ninja_aio/schemas/helpers.py`

Three new fields added to `DecoratorsSchema`:

| Field | Description |
|---|---|
| `bulk_create` | Decorators for bulk create endpoint |
| `bulk_update` | Decorators for bulk update endpoint |
| `bulk_delete` | Decorators for bulk delete endpoint |

---

#### 🚀 Batch Queryset Serialization — Up to 94% Faster
> `ninja_aio/models/utils.py`

Queryset serialization has been fundamentally optimized. Previously, each object in a queryset was serialized via an individual `sync_to_async(schema.from_orm)(obj)` call, creating N event loop context switches for N objects. Now, the entire queryset is serialized in a **single `sync_to_async` call** via the new `_bump_queryset_from_schema()` method.

**Before (per-object):**
```python
# N sync_to_async calls — one per object
[await self._bump_object_from_schema(obj, schema) async for obj in instance]
```

**After (batched):**
```python
# 1 sync_to_async call — entire queryset serialized at once
async def _bump_queryset_from_schema(self, queryset, schema):
    def _serialize_all():
        return [schema.from_orm(obj).model_dump() for obj in queryset]
    return await sync_to_async(_serialize_all)()
```

**Benchmark results:**

| Metric | Before | After | Improvement |
|---|---|---|---|
| ⏱️ Bulk serialization (500 objects) | 21.80ms | 1.35ms | **-93.8%** |
| ⏱️ Bulk serialization (100 objects) | 6.03ms | 0.49ms | **-92.0%** |
| ⏱️ List endpoint (100 records) | 5.14ms | 0.82ms | **-84.0%** |
| 🔄 `sync_to_async` overhead | 4975% | 102% | **~50x reduction** |
| 📊 Per-object overhead | 0.119ms | 0.001ms | **119x less** |

**Scalability at 17k records:**

| Metric | Before | After |
|---|---|---|
| ⏱️ `list_read_s` (17k records) | 1.217s | 0.077s |
| 📊 Throughput | ~0.07ms/obj | ~0.005ms/obj |

Both `_read_s()` and `_serialize_queryset()` now use `_bump_queryset_from_schema()` for list serialization. Single-object serialization via `_bump_object_from_schema()` remains unchanged.

---

#### 🔗 Set-Based M2M Membership Validation
> `ninja_aio/helpers/api.py`

M2M add/remove validation now uses a **set of PKs** instead of a list of full model instances for membership checks.

**Before:**
```python
# O(n) list — loads all related objects with select_related
rel_objs = [rel_obj async for rel_obj in related_manager.select_related().all()]
# O(n) membership check per PK
if remove ^ (rel_obj in rel_objs):
```

**After:**
```python
# O(n) set — loads only PKs, no select_related overhead
rel_obj_pks = {rel_obj.pk async for rel_obj in related_manager.all()}
# O(1) membership check per PK
if remove ^ (rel_obj.pk in rel_obj_pks):
```

**Two optimizations combined:**
- 🔍 **O(1) membership checks** — `set` lookup instead of `list` scan
- 📦 **No `select_related()`** — only PKs are needed, not full related objects

---

### 📖 Documentation

- 📝 `docs/api/views/api_view_set.md` — Added `@action` decorator section (recommended), bulk operations section, ordering section, updated Core Attributes table with new attributes
- 📝 `docs/api/views/decorators.md` — Added `@action` card and full reference with code examples
- 📝 `docs/tutorial/crud.md` — Added Custom Actions tutorial, Bulk Operations tutorial, rewrote Ordering section for native support, renamed `@api_get`/`@api_post` section as alternative
- 📝 `TODO.md` — Marked bulk operations, custom actions, and ordering as completed; renumbered remaining tasks (35 total)

---

### 🧪 Tests

#### `ActionRegistrationTestCase` — 5 tests

#### `ActionExecutionTestCase` — 4 tests

#### `ActionDisableTestCase` — 2 tests

#### `ActionAuthTestCase` — 2 tests

#### `BulkCreateTestCase` — 5 tests, `BulkUpdateTestCase` — 5 tests, `BulkDeleteTestCase` — 6 tests

#### `OrderingTestCase` — 10 tests

#### `OrderingDisabledTestCase` — 2 tests

#### `OrderingWithFiltersTestCase` — 2 tests

#### `OrderingDefaultListTestCase` — 4 tests

---

### 🎯 Summary

Version 2.27.0 introduces three major features — **`@action` decorator**, **bulk operations**, and **native ordering** — alongside a **major performance optimization** that makes serialization up to 94% faster for large datasets.

**Key benefits:**
- ⚡ **`@action` decorator** — add custom endpoints with auth inheritance, detail/list distinction, and auto URL generation
- 📦 **Bulk operations** — create, update, and delete multiple objects in a single request with optimized bulk delete
- 🔀 **Native ordering** — two-attribute configuration (`ordering_fields`, `default_ordering`) replaces manual `query_params_handler` ordering logic
- 🚀 **Up to 94% faster serialization** — batch `sync_to_async` eliminates per-object overhead; 17k records in 0.077s (down from 1.2s)
- 🔗 **O(1) M2M validation** — set-based PK membership checks replace O(n) list scans
- 🧩 **Composable** — all features work seamlessly with existing filter mixins, pagination, and decorators

---

## 🏷️ [v2.26.0] - 2026-03-13

---

### ✨ New Features

#### 🏷️ `NinjaAIOMeta` Inner Class for Model-Level Framework Configuration
> `ninja_aio/types.py`, `ninja_aio/exceptions.py`, `ninja_aio/models/utils.py`, `ninja_aio/models/serializers.py`, `ninja_aio/views/api.py`

Models can now declare a `NinjaAIOMeta` inner class for framework-specific configuration that Django's `Meta` class cannot handle. All attributes are optional.

```python
class Article(models.Model):
    title = models.CharField(max_length=255)

    class NinjaAIOMeta:
        not_found_name = "article"            # custom 404 error key
        verbose_name = "Blog Article"         # override for API display
        verbose_name_plural = "Blog Articles" # override for routes & display
```

**Resolution priority (3-tier):**

| Priority | Source | Example |
|---|---|---|
| 1️⃣ Highest | ViewSet class attribute | `model_verbose_name = "Article"` |
| 2️⃣ Middle | `NinjaAIOMeta` inner class | `NinjaAIOMeta.verbose_name = "Blog Article"` |
| 3️⃣ Lowest | Django `Meta` | `Meta.verbose_name = "article"` |

**New helper function:**

```python
from ninja_aio.types import get_ninja_aio_meta_attr

# Returns attribute from NinjaAIOMeta, or default if not found
name = get_ninja_aio_meta_attr(MyModel, "not_found_name")
name = get_ninja_aio_meta_attr(MyModel, "verbose_name", default="fallback")
```

**New `ModelUtil` property:**

| Property | Description |
|---|---|
| `model_verbose_name` | 🏷️ Returns model verbose name (NinjaAIOMeta → Django Meta fallback) |

---

#### 📦 `Status` Object Returns for All View Endpoints
> `ninja_aio/views/api.py`, `ninja_aio/helpers/api.py`

All CRUD and M2M view endpoints now return Django Ninja `Status` objects instead of raw tuples or data. This provides explicit HTTP status codes with typed response data.

**CRUD views:**

| Endpoint | Return |
|---|---|
| `create` | `Status(201, data)` |
| `list` | `Status(200, data)` |
| `retrieve` | `Status(200, data)` |
| `update` | `Status(200, data)` |
| `delete` | `Status(204, data)` |

**M2M views:**

| Endpoint | Return |
|---|---|
| `get_related` | `Status(200, data)` |
| `manage_related` | `Status(200, M2MSchemaOut(...))` |

---

### 🔧 Improvements

#### 📦 Widened Dependency Constraints
> `pyproject.toml`

| Dependency | Before | After |
|---|---|---|
| `django-ninja` | `>=1.3.0, <1.6` | `>=1.3.0, <1.7.0` |
| `joserfc` | `>=1.0.0, <=1.4.1` | `>=1.0.0, <1.5.0` |

---

#### 🐛 Fix `NotFoundError` with `model._meta` Custom Attributes
> `ninja_aio/exceptions.py`

The previous `not_found_name` feature checked `model._meta.not_found_name`, but Django's `Options` class silently ignores custom attributes on `Meta`. This was effectively dead code. Now uses `NinjaAIOMeta.not_found_name` via the `get_ninja_aio_meta_attr()` helper.

---

### 📖 Documentation

- 📝 `docs/api/exceptions.md` — Replaced broken `model._meta.not_found_name` docs with `NinjaAIOMeta` usage
- 📝 `docs/api/views/api_view_set.md` — Added "Verbose Name Resolution" section with 3-tier priority table
- 📝 `docs/api/models/model_util.md` — Added `NinjaAIOMeta` tip to `verbose_name_path_resolver()`
- 📝 `docs/api/models/model_serializer.md` — Added `NinjaAIOMeta` example to `verbose_name_path_resolver()`
- 🔄 `.github/workflows/docs.yml` — Added version `2.26` option

---

### 🧪 Tests

#### `NinjaAIOMetaVerboseNameTestCase` — 7 tests

#### `GetNinjaAIOMetaAttrTestCase` — 4 tests

#### Updated test fixtures

| File | Change |
|---|---|
| `tests/test_app/models.py` | `TestModelWithNinjaAIOMeta` — full NinjaAIOMeta with all 3 attributes |
| `tests/test_app/models.py` | `TestModelWithPartialNinjaAIOMeta` — only `not_found_name` set |
| `tests/test_exceptions.py` | Replaced `_meta` monkey-patching with NinjaAIOMeta models |
| `tests/core/test_exceptions_api.py` | Replaced `_meta` monkey-patching with NinjaAIOMeta models |
| `tests/generics/views.py` | Updated all view tests for `Status` object returns |
| `tests/helpers/test_many_to_many_api.py` | Updated all M2M tests for `Status` object returns |
| `tests/views/test_views.py` | Updated route name assertions for Django Ninja compatibility |

**Coverage:** 100% across all 1888 statements in `ninja_aio/` (744 tests, 0 failures)

---

### 🎯 Summary

Version 2.26.0 introduces **`NinjaAIOMeta`** for model-level framework configuration and migrates all view returns to **Django Ninja `Status` objects** for explicit HTTP status code handling. The release also fixes the broken `not_found_name` feature and widens dependency constraints.

**Key benefits:**
- 🏷️ **Model-level configuration** — `NinjaAIOMeta` inner class for `not_found_name`, `verbose_name`, and `verbose_name_plural`
- 📦 **Explicit status codes** — All views return `Status(code, data)` instead of raw tuples
- 🐛 **Bug fix** — `not_found_name` now works correctly via `NinjaAIOMeta` (was dead code via `model._meta`)
- 🔧 **Wider compatibility** — Support for Django Ninja <1.7.0 and joserfc <1.5.0
- ✅ **100% coverage** — all 1888 source lines covered by tests

---

## 🏷️ [v2.25.0] - 2026-03-12

---

### ✨ New Features

#### 🔍 Comprehensive Debug Logging
> `ninja_aio/auth.py`, `ninja_aio/decorators/views.py`, `ninja_aio/exceptions.py`, `ninja_aio/factory/operations.py`, `ninja_aio/helpers/api.py`, `ninja_aio/models/utils.py`, `ninja_aio/views/api.py`

All framework operations now emit structured log messages via Python's standard `logging` module. Logging is **disabled by default** with **zero runtime overhead** until explicitly enabled.

**Quick start:**

```python
# settings.py
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {
        "console": {"class": "logging.StreamHandler"},
    },
    "loggers": {
        "ninja_aio": {
            "handlers": ["console"],
            "level": "DEBUG",
        },
    },
}
```

**Logger hierarchy:**

| Logger | Covers |
|---|---|
| `ninja_aio` | 🌐 All framework logs (parent) |
| `ninja_aio.auth` | 🔐 JWT authentication, encoding/decoding |
| `ninja_aio.decorators` | 🔄 Atomic transaction entry |
| `ninja_aio.exceptions` | ⚠️ Exception handler invocations |
| `ninja_aio.factory` | 🏭 Endpoint registration |
| `ninja_aio.helpers` | 🔗 M2M relation operations |
| `ninja_aio.models` | 📦 CRUD operations, cache events, query optimizations, FK resolution |
| `ninja_aio.views` | 🖥️ ViewSet initialization, view registration, filter validation |

**Log levels used:**

| Level | When |
|---|---|
| `INFO` | CRUD operations (create, update, delete), M2M manage results |
| `DEBUG` | Authentication, cache hits/misses, query optimizations, FK resolution, endpoint registration, binary field decoding |
| `WARNING` | Binary field decode failures |

---

#### 📦 LRU-Bounded Relation Cache
> `ninja_aio/models/utils.py`

The class-level `_relation_cache` on `ModelUtil` has been replaced with a bounded **LRU cache** (`maxsize=512`). In long-running processes, the previous unbounded `dict` could grow indefinitely; the new cache evicts least-recently-used entries when the limit is reached.

```python
class LRUCache:
    """Thread-safe LRU cache backed by OrderedDict."""
    def __init__(self, maxsize: int = 512): ...
    def get(self, key): ...      # Returns None on miss, promotes on hit
    def set(self, key, value): ... # Evicts LRU entry when full
    def clear(self): ...
```

**Behavior:**
- `get()` promotes entries to most-recent position (LRU semantics)
- `set()` evicts the oldest entry when `maxsize` is exceeded, logging the eviction at DEBUG level
- Cache key format unchanged: `(model, serializer_class_str, is_for)`

---

### 🔧 Improvements

#### 🔁 Refactored Match Case Filter Application
> `ninja_aio/views/mixins.py`

The `MatchCaseFilterViewSetMixin.query_params_handler` method has been refactored: the inline filter application logic was extracted into a dedicated `_apply_case_filter(queryset, case_filter)` method. This improves readability and testability without changing behavior.

| Before | After |
|---|---|
| 20-line inline `if/else` block with nested `isinstance` checks | Single `_apply_case_filter()` call per match case |

---

#### 🐛 Fix `NotFoundError` Constructor
> `ninja_aio/exceptions.py`

Fixed incorrect `return super().__init__(...)` in `NotFoundError.__init__` when a custom `not_found_name` is set. The `return` keyword prevented the constructor from completing properly. Now calls `super().__init__(...)` followed by an explicit `return`.

---

### 📖 Documentation

- 📝 `docs/logging.md` — New comprehensive logging guide with quick start, logger hierarchy, per-module examples, production configuration, and performance notes
- ⚙️ `mkdocs.yml` — Added **Logging** entry to navigation
- 🔄 `.github/workflows/docs.yml` — Added version `2.24` to the documentation workflow
- 🔄 `.github/workflows/performance.yml` — Updated `actions/upload-artifact` to v7 and `dawidd6/action-download-artifact` to v16
- 📋 `TODO.md` — Added project improvement roadmap with 25 tracked tasks across 4 priority levels

---

### 🧪 Tests

#### `LRUCacheTestCase` — 10 tests

#### `M2MQueryHandlerTestCase` — 1 test

#### `M2MNotFoundTestCase` — 1 test

#### `M2MAsyncQueryParamsHandlerTestCase` — 1 test

#### `SchemaOverridesNonFunctionTestCase` — 1 test

#### `CircularReferenceDetectionTestCase` — 1 test

#### `ModelSerializerGetModelConfigNoneTestCase` — 1 test

#### `SerializerGetModelConfigUnknownTypeTestCase` — 1 test

#### `SerializerGetDumpSchemaTestCase` — 2 tests

#### `PrefetchWithForwardRelsTestCase` — 1 test

#### `MatchCaseFilterInvalidFieldTestCase` — 1 test

**New test helpers:**

| File | Addition |
|---|---|
| `tests/helpers/test_many_to_many_api.py` | `TestM2MWithQueryHandlerViewSet` — ViewSet with custom M2M `query_handler` |
| `tests/helpers/test_many_to_many_api.py` | `TestM2MWithAsyncQueryParamsHandlerViewSet` — ViewSet with async `query_params_handler` |

**Coverage:** 100% across all 1878 statements in `ninja_aio/` (734 tests, 0 failures)

---

### 🎯 Summary

Version 2.25.0 adds **comprehensive debug logging** across the entire framework and replaces the unbounded relation cache with a **bounded LRU cache** to prevent memory growth in long-running processes. The release also achieves **100% code coverage** with 21 new tests targeting previously uncovered edge cases.

**Key benefits:**
- 🔍 **Full observability** — structured logging across auth, CRUD, M2M, exceptions, and query optimization with zero overhead when disabled
- 📦 **Memory-safe caching** — LRU eviction prevents unbounded growth of `_relation_cache` in long-lived processes
- 🐛 **Bug fix** — corrected `NotFoundError` constructor when using `not_found_name`
- 🧹 **Cleaner code** — extracted `_apply_case_filter()` method in match-case filter mixin
- ✅ **100% coverage** — all source code lines covered by tests

---

## 🏷️ [v2.24.0] - 2026-03-09

---

### ✨ New Features

#### 🔗 Instance Binding on `Serializer`
> `ninja_aio/models/serializers.py`

`Serializer` now supports **instance binding**: a model instance can be attached to a serializer at construction time or via attribute assignment, eliminating the need to pass it on every method call.

**Constructor:**

```python
serializer = ArticleSerializer(instance=article)
```

**Attribute assignment (after construction):**

```python
serializer = ArticleSerializer()
serializer.instance = article
```

**Instance-bound usage:**

```python
serializer = ArticleSerializer(instance=article)

await serializer.update({"title": "Breaking news"})  # uses bound instance
await serializer.save()                               # uses bound instance
data    = await serializer.model_dump()               # uses bound instance
changed = serializer.has_changed("title")             # uses bound instance
changed = await serializer.ahas_changed("title")      # uses bound instance
```

Explicit method arguments always take priority over `self.instance`. Calling an instance-dependent method when neither is set raises a clear `ValueError`.

---

### 🔧 Improvements

#### 📐 Optional `instance` on `save`, `update`, `model_dump`, `has_changed`, `ahas_changed`
> `ninja_aio/models/serializers.py`

All instance-dependent methods now accept `instance` as an **optional** parameter that falls back to `self.instance`:

| Method | Old signature | New signature |
|---|---|---|
| `save` | `save(instance)` | `save(instance=None)` |
| `update` | `update(instance, payload)` | `update(payload, instance=None)` |
| `model_dump` | `model_dump(instance, schema=None)` | `model_dump(instance=None, schema=None)` |
| `has_changed` | `has_changed(instance, field)` | `has_changed(field, instance=None)` |
| `ahas_changed` | `ahas_changed(instance, field)` | `ahas_changed(field, instance=None)` |

!!! warning "Breaking: parameter order changed for `update`, `has_changed`, `ahas_changed`"
    `payload`/`field` moved to first position and `instance` became the optional trailing arg.

#### 🛡️ `_resolve_instance` helper
> `ninja_aio/models/serializers.py`

Internal `_resolve_instance(instance)` method centralizes instance resolution logic: prefers the explicit argument, falls back to `self.instance`, and raises `ValueError` with a descriptive message when neither is available.

---

### 📖 Documentation

- `docs/api/models/serializers.md` — added **Instance Binding** section; updated all method signatures and code examples to the new parameter order; added `save` and `update` examples; added migration warning admonitions.
- `docs/tutorial/serializer.md` — added **Instance Binding** tutorial section covering constructor binding, attribute assignment, instance replacement, priority rules, and error behaviour; updated learning objectives and checklist.

---

### 🧪 Tests

#### `SerializerInstanceBindingTestCase` — 18 tests
> `tests/test_serializers.py`

**Constructor & attribute assignment:**

| Test | Verifies |
|---|---|
| `test_init_without_instance_sets_none` | ✅ `Serializer()` → `self.instance` is `None` |
| `test_init_with_instance_stores_it` | ✅ `Serializer(instance=obj)` stores the instance |
| `test_instance_attribute_assignment` | ✅ `serializer.instance = obj` works after construction |
| `test_instance_attribute_can_be_replaced` | ✅ `self.instance` can be replaced with a different object |

**`_resolve_instance`:**

| Test | Verifies |
|---|---|
| `test_resolve_instance_prefers_explicit_arg` | ✅ explicit arg beats `self.instance` |
| `test_resolve_instance_falls_back_to_bound` | ✅ `None` arg falls back to `self.instance` |
| `test_resolve_instance_raises_when_none` | ✅ raises `ValueError` when both are `None` |

**`save()`:**

| Test | Verifies |
|---|---|
| `test_save_uses_bound_instance` | ✅ `save()` persists `self.instance` |
| `test_save_raises_without_instance` | ✅ raises `ValueError` with no instance |

**`update()`:**

| Test | Verifies |
|---|---|
| `test_update_uses_bound_instance` | ✅ `update(payload)` applies to `self.instance` |
| `test_update_explicit_instance_overrides_bound` | ✅ explicit arg takes priority |
| `test_update_raises_without_instance` | ✅ raises `ValueError` with no instance |

**`model_dump()`:**

| Test | Verifies |
|---|---|
| `test_model_dump_uses_bound_instance` | ✅ `model_dump()` serializes `self.instance` |
| `test_model_dump_explicit_instance_overrides_bound` | ✅ explicit arg takes priority |
| `test_model_dump_raises_without_instance` | ✅ raises `ValueError` with no instance |

**`has_changed()`:**

| Test | Verifies |
|---|---|
| `test_has_changed_uses_bound_instance` | ✅ `has_changed(field)` checks `self.instance` |
| `test_has_changed_explicit_instance_overrides_bound` | ✅ explicit arg takes priority |
| `test_has_changed_raises_without_instance` | ✅ raises `ValueError` with no instance |

**`ahas_changed()`:**

| Test | Verifies |
|---|---|
| `test_ahas_changed_uses_bound_instance` | ✅ async `ahas_changed(field)` checks `self.instance` |
| `test_ahas_changed_explicit_instance_overrides_bound` | ✅ explicit arg takes priority |
| `test_ahas_changed_raises_without_instance` | ✅ raises `ValueError` with no instance |

**Updated existing tests** — adjusted `update`, `has_changed`, and `ahas_changed` call sites to the new parameter order.

---

### 🎯 Summary

Version 2.24.0 introduces **instance binding** to `Serializer`, a quality-of-life feature for workflows that operate on the same model instance across multiple calls.

**Key benefits:**
- 🔗 **Less repetition** — bind the instance once, omit it from every subsequent call
- 🔄 **Flexible** — bind at construction or assign via `serializer.instance = obj` at any time
- ⚡ **Priority rule** — explicit method arguments always win, enabling ad-hoc overrides without rebinding
- 🛡️ **Clear errors** — descriptive `ValueError` when no instance is available
- ✅ **Fully backwards-compatible for `save` and `model_dump`** — existing positional calls continue to work
