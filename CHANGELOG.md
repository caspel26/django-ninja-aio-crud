# 📋 Release Notes

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
- ✅ **100% coverage** — all 1888 source lines covered

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
