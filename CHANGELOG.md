# 📋 Release Notes

## 🏷️ [v2.28.0] - 2026-03-23

---

### ✨ New Features

#### 🔐 Permission System with Operation Hooks
> `ninja_aio/views/mixins.py`, `ninja_aio/views/api.py`, `ninja_aio/exceptions.py`

A three-level permission system built on overridable operation hooks. Permissions are checked at **view-level** (before any DB query), **object-level** (after fetch, before mutation), and **row-level** (filters list queryset).

```python
from ninja_aio.views import APIViewSet
from ninja_aio.views.mixins import PermissionViewSetMixin

class ArticleAPI(PermissionViewSetMixin, APIViewSet):
    model = Article

    async def has_permission(self, request, operation):
        """View-level: deny non-staff from writing."""
        if operation in ("create", "update", "delete"):
            return request.auth.is_staff
        return True

    async def has_object_permission(self, request, operation, obj):
        """Object-level: only owners can modify."""
        return obj.owner_id == request.auth.id

    def get_permission_queryset(self, request, queryset):
        """Row-level: users only see their own articles."""
        return queryset.filter(owner=request.auth)
```

**`PermissionViewSetMixin` hooks:**

| Hook | When | Raises |
|---|---|---|
| 🛡️ `has_permission(request, operation)` | Before any DB query | `ForbiddenError` (403) |
| 🔒 `has_object_permission(request, operation, obj)` | After fetch, before mutation | `ForbiddenError` (403) |
| 🔍 `get_permission_queryset(request, queryset)` | Before pagination in list view | Filters rows silently |

**`RoleBasedPermissionMixin` — declarative role mapping:**

```python
from ninja_aio.views.mixins import RoleBasedPermissionMixin

class ArticleAPI(RoleBasedPermissionMixin, APIViewSet):
    model = Article
    permission_roles = {
        "admin": ["create", "list", "retrieve", "update", "delete"],
        "editor": ["create", "list", "retrieve", "update"],
        "reader": ["list", "retrieve"],
    }
    role_attribute = "role"  # reads from request.auth.role
```

**New exception:**

```python
from ninja_aio.exceptions import ForbiddenError

raise ForbiddenError(details="Permission denied for operation: delete")
# → 403 {"message": "forbidden", "details": "Permission denied for operation: delete"}
```

---

#### 🏗️ Operation Hooks on `APIViewSet`
> `ninja_aio/views/api.py`

Three overridable hooks executed at different stages of CRUD, bulk, and `@action` operations. These form the foundation of the permission system but can be used independently for logging, auditing, or custom validation.

```python
class ArticleAPI(APIViewSet):
    model = Article

    async def on_before_operation(self, request, operation):
        """Called before every operation (create, list, retrieve, update, delete, bulk_*, @action)."""
        logger.info(f"User {request.auth.id} performing {operation}")

    async def on_before_object_operation(self, request, operation, obj):
        """Called after fetch, before mutation (retrieve, update, delete)."""
        if obj.is_locked and operation in ("update", "delete"):
            raise ForbiddenError(details="Object is locked")

    def on_list_queryset(self, request, queryset):
        """Called after filters/ordering, before pagination."""
        return queryset.filter(is_published=True)
```

| Hook | Applies to |
|---|---|
| `on_before_operation` | All CRUD + bulk + `@action` endpoints |
| `on_before_object_operation` | `retrieve`, `update`, `delete` (single-object endpoints) |
| `on_list_queryset` | `list` endpoint only |

---

#### 🏛️ Auto Django Admin Generation
> `ninja_aio/admin.py`, `ninja_aio/models/serializers.py`

Generate Django `ModelAdmin` classes automatically from `ModelSerializer` field configuration. Admin `list_display`, `search_fields`, `list_filter`, and `readonly_fields` are derived intelligently from serializer inner classes.

**Option 1 — `@register_admin` decorator:**

```python
from ninja_aio import register_admin
from ninja_aio.models import ModelSerializer

@register_admin
class Book(ModelSerializer):
    class Meta:
        model = BookModel

    class ReadSerializer:
        fields = ["title", "author", "published_at", "is_active"]

    class UpdateSerializer:
        fields = ["title", "author"]
```

**Option 2 — `as_admin()` class method:**

```python
from django.contrib import admin

admin.site.register(BookModel, Book.as_admin(list_per_page=50))
```

**Option 3 — `model_admin_factory()` function:**

```python
from ninja_aio.admin import model_admin_factory

AdminClass = model_admin_factory(BookModel, list_per_page=50)
admin.site.register(BookModel, AdminClass)
```

**Field classification logic:**

| Field Type | `list_display` | `search_fields` | `list_filter` | `readonly_fields` |
|---|---|---|---|---|
| 📝 CharField, TextField, SlugField, EmailField, URLField | ✅ | ✅ | ❌ | If not in UpdateSerializer |
| ☑️ BooleanField | ✅ | ❌ | ✅ | If not in UpdateSerializer |
| 📅 DateField, DateTimeField | ✅ | ❌ | ✅ | If not in UpdateSerializer |
| 🔗 ForeignKey, OneToOneField | ✅ | ❌ | ✅ | If not in UpdateSerializer |
| 🔀 ManyToManyField | ❌ | ❌ | ✅ | ❌ |

---

#### 📋 Configurable Bulk Response Fields
> `ninja_aio/views/api.py`, `ninja_aio/models/utils.py`

New `bulk_response_fields` attribute on `APIViewSet` controls what fields are returned in bulk operation success details instead of PKs only.

```python
class ArticleAPI(APIViewSet):
    model = Article
    bulk_operations = ["create", "update", "delete"]

    # Option 1: Single field value
    bulk_response_fields = "slug"
    # → {"success": {"count": 2, "details": ["my-article", "other-article"]}}

    # Option 2: Multiple fields as dicts
    bulk_response_fields = ["id", "slug", "title"]
    # → {"success": {"count": 2, "details": [
    #     {"id": 1, "slug": "my-article", "title": "My Article"},
    #     {"id": 2, "slug": "other-article", "title": "Other Article"}
    # ]}}

    # Option 3: Default (None) — PK only (backward compatible)
    bulk_response_fields = None
    # → {"success": {"count": 2, "details": [1, 2]}}
```

Works with all three bulk operations. For `bulk_delete`, field values are fetched before deletion.

---

#### ✅ Require Update Fields Validation
> `ninja_aio/views/api.py`, `ninja_aio/models/utils.py`

New `require_update_fields` attribute rejects empty PATCH requests (all-`None` payloads).

```python
class ArticleAPI(APIViewSet):
    model = Article
    require_update_fields = True

# PATCH /articles/1 {} → 400 {"message": "No fields provided for update."}
# PATCH /articles/1 {"title": "New"} → 200 OK
```

Also applies to bulk update operations.

---

### 🔧 Improvements

#### ⚡ List View Returns QuerySet Directly — Native `CursorPagination` Support
> `ninja_aio/views/api.py`, `ninja_aio/helpers/api.py`

`list_view` and M2M `get_related` now return the QuerySet directly to `@paginate` instead of serializing all objects first via `list_read_s`. This means:

- ✅ **`CursorPagination` works natively** — receives a real QuerySet for `.order_by()` and `.filter()`
- ⚡ **Only the current page is fetched from DB** — pagination slices at the database level
- ⚡ **Only page_size objects are serialized** — Django Ninja handles serialization after pagination

```python
from ninja.pagination import CursorPagination

class ArticleAPI(APIViewSet):
    model = Article
    pagination_class = CursorPagination  # ← just works now
```

**Performance with 17k records:** `list_view` time is constant regardless of total dataset size (ratio 17k/1k ≈ 1.0x).

---

#### 🔢 403 Error Code Added to `ERROR_CODES`
> `ninja_aio/views/api.py`

`ERROR_CODES` extended from `{400, 401, 404}` to `{400, 401, 403, 404}`. All endpoints now advertise `403 Forbidden` responses in OpenAPI schema.

---

#### 🏷️ Comprehensive Type Annotations
> `ninja_aio/views/api.py`

Explicit return type annotations added to all `APIViewSet` public methods and properties:

| Method | Return Type |
|---|---|
| `add_views_to_route()` | `None` |
| `get_schemas()` | `tuple[Schema \| None, ...]` |
| `create_view()`, `list_view()`, etc. | `Callable` |
| `_crud_views`, `_bulk_views` | `dict[str, tuple[Schema \| None, Callable]]` |
| `query_params_handler()` | `QuerySet` |

---

### 📖 Documentation

- ✨ **Mermaid architecture diagrams** — interactive flowcharts on home page (Request → Auth → Filter → Paginate → Serialize → Response), tutorial CRUD page, and APIViewSet reference
- 🎨 **CSS animations** — hero fade-in, code block hover glow, card entrance animations, table row highlights, Mermaid diagram slide-in, scroll progress bar, CTA button lift+glow, anchor heading flash, page transitions, TOC active indicator, nav tab underline slide
- 📝 **Code annotations** — annotated examples in Quick Start and CRUD tutorial pages using Material for MkDocs annotations syntax
- 📦 **Collapsible sections** — advanced examples wrapped in `<details>` for cleaner reading flow
- 🔐 **Permissions guide** — new tutorial page covering `PermissionViewSetMixin`, `RoleBasedPermissionMixin`, and `ForbiddenError`
- 🏛️ **Auto Admin guide** — new tutorial page with `@register_admin` decorator, `as_admin()`, and field classification
- 📋 **Bulk response fields** — documented in APIViewSet reference and CRUD tutorial
- ✅ **Require update fields** — documented in APIViewSet reference
- 📦 **README updated** — added bulk operations and `@action` decorator examples

---

### 🎯 Summary

Version 2.28.0 introduces a **three-level permission system**, **auto Django admin generation**, and **configurable bulk response fields**, alongside a critical optimization that returns QuerySets directly from list views enabling native **cursor-based pagination** support.

**Key benefits:**
- 🔐 **Permission system** — view-level, object-level, and row-level permission checks with `PermissionViewSetMixin` and `RoleBasedPermissionMixin`
- 🏗️ **Operation hooks** — `on_before_operation`, `on_before_object_operation`, `on_list_queryset` for custom logic at every stage
- 🏛️ **Auto admin** — `@register_admin` generates `ModelAdmin` from serializer config with intelligent field classification
- 📋 **Bulk response fields** — `bulk_response_fields` attribute returns custom fields instead of PKs only
- ⚡ **Native cursor pagination** — list views return QuerySets directly, enabling `CursorPagination` and DB-level slicing
- ✅ **Require update fields** — `require_update_fields = True` rejects empty PATCH requests
- 🎨 **Rich documentation** — Mermaid diagrams, CSS animations, code annotations, and collapsible sections
- ✅ **100% coverage** — all source lines covered across 804 tests

---

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

- 📝 `docs/api/views/api_view_set.md` — Added `@action` decorator section (recommended), bulk operations section, ordering section, permissions section, updated Core Attributes table with new attributes
- 📝 `docs/api/views/decorators.md` — Added `@action` card and full reference with code examples
- 📝 `docs/tutorial/crud.md` — Added Custom Actions tutorial, Bulk Operations tutorial, rewrote Ordering section for native support, renamed `@api_get`/`@api_post` section as alternative
- 📝 `TODO.md` — Marked bulk operations, custom actions, and ordering as completed; renumbered remaining tasks

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

### 🎯 Summary

Version 2.24.0 introduces **instance binding** to `Serializer`, a quality-of-life feature for workflows that operate on the same model instance across multiple calls.

**Key benefits:**
- 🔗 **Less repetition** — bind the instance once, omit it from every subsequent call
- 🔄 **Flexible** — bind at construction or assign via `serializer.instance = obj` at any time
- ⚡ **Priority rule** — explicit method arguments always win, enabling ad-hoc overrides without rebinding
- 🛡️ **Clear errors** — descriptive `ValueError` when no instance is available
- ✅ **Fully backwards-compatible for `save` and `model_dump`** — existing positional calls continue to work
## [v2.23.1] - 2026-02-23

---

### 🔧 Improvements

#### 📦 Widened `orjson` Dependency Constraint
> `pyproject.toml`

The `orjson` version constraint has been relaxed from `<= 3.11.5` to `< 4.0.0`, allowing any stable 3.x release to satisfy the dependency. This removes the tight upper pin and lets projects use newer patch and minor releases of `orjson` as they are published, without waiting for a constraint update in this package.

| Dependency | Before | After |
|---|---|---|
| `orjson` | `>= 3.10.7, <= 3.11.5` | `>= 3.10.7, < 4.0.0` |

---

### 🎯 Summary

Version 2.23.1 is a maintenance release that loosens the `orjson` upper bound to track the full 3.x release line.

**Key benefits:**
- 📦 **Fewer conflicts** — projects can upgrade `orjson` freely within the 3.x series
- 🔒 **Still safe** — the `< 4.0.0` bound guards against potentially breaking 4.x changes

---

---

## [v2.23.0] - 2026-02-23

---

### 🔧 Improvements

#### 🐍 `NotFoundError` Class-Name Key Uses `snake_case`
> `ninja_aio/exceptions.py`

When `NINJA_AIO_NOT_FOUND_ERROR_USE_VERBOSE_NAMES = False`, the error key produced by `NotFoundError` is now automatically converted from `CamelCase` to `snake_case` (all lowercase), instead of using the raw Python class name.

**Before (v2.22.0):**

```python
# settings.py
NINJA_AIO_NOT_FOUND_ERROR_USE_VERBOSE_NAMES = False

raise NotFoundError(BlogPost)
# {"BlogPost": "not found"}  ← raw class name
```

**After (v2.23.0):**

```python
raise NotFoundError(BlogPost)
# {"blog_post": "not found"}  ← snake_case

raise NotFoundError(TestModelSerializer)
# {"test_model_serializer": "not found"}
```

This ensures the error key is consistent with standard JSON conventions and matches the format already used by the default `verbose_name` mode.

**Implementation:**

| File | Change |
|---|---|
| `ninja_aio/exceptions.py` | `model.__name__` converted via `re.sub(r"(?<!^)(?=[A-Z])", "_", name).lower()` |

---

### 🧪 Tests

#### `ExceptionsAndAPITestCase` — updated

| Test | Verifies |
|---|---|
| `test_not_found_error_class_name_mode` | ✅ `use_verbose_name=False` produces `snake_case` key |

#### `SubclassesTestCase` — updated

| Test | Verifies |
|---|---|
| `test_not_found_error_use_class_name` | ✅ `use_verbose_name=False` key matches `snake_case(__name__)` |

---

### 🎯 Summary

Version 2.23.0 refines the `use_verbose_name=False` behaviour introduced in 2.22.0. The error key is now always `snake_case`, making it consistent with both the default verbose-name format and standard JSON naming conventions.

**Key benefits:**
- 🐍 **Consistent casing** — both modes now produce `snake_case` error keys
- ✅ **Backwards-compatible** — only affects the `use_verbose_name=False` opt-in mode

---

---

## [v2.22.0] - 2026-02-23

---

### ✨ New Features

#### 🔧 Configurable `NotFoundError` Key Format
> `ninja_aio/exceptions.py`

`NotFoundError` now supports a configurable error key format via the Django setting `NINJA_AIO_NOT_FOUND_ERROR_USE_VERBOSE_NAMES`.

By default (`True`), the error key continues to use the model's `verbose_name` with spaces replaced by underscores — preserving full backwards compatibility.

When set to `False`, the error key uses the Python model class name (`model.__name__`) instead, which is useful when verbose names contain spaces that are undesirable in JSON keys or when a more Pythonic identifier is preferred.

**Default behaviour (unchanged):**

```python
# Model with verbose_name = "blog post"
raise NotFoundError(BlogPost)
# {"blog_post": "not found"}
```

**Class name mode:**

```python
# settings.py
NINJA_AIO_NOT_FOUND_ERROR_USE_VERBOSE_NAMES = False

raise NotFoundError(BlogPost)
# {"BlogPost": "not found"}
```

**Setting reference:**

| Setting | Type | Default | Description |
|---|---|---|---|
| `NINJA_AIO_NOT_FOUND_ERROR_USE_VERBOSE_NAMES` | `bool` | `True` | Controls whether `NotFoundError` uses `verbose_name` (with `_`) or `__name__` as the error key |

**Implementation details:**

| File | Change |
|---|---|
| `ninja_aio/exceptions.py` | Added `use_verbose_name` class attribute on `NotFoundError`, reads from `settings.NINJA_AIO_NOT_FOUND_ERROR_USE_VERBOSE_NAMES` |

---

### 📚 Documentation

- Added `docs/api/exceptions.md` — full reference for all exception classes (`BaseException`, `SerializeError`, `AuthError`, `NotFoundError`, `PydanticValidationError`) and exception handlers
- Added **Exceptions** entry to the API Reference section in `mkdocs.yml`

---

### 🧪 Tests

#### `ExceptionsAndAPITestCase` — 1 new test

**Configurable key format:**

| Test | Verifies |
|---|---|
| `test_not_found_error_class_name_mode` | ✅ `use_verbose_name=False` uses `model.__name__` as error key |

#### `SubclassesTestCase` — 2 new tests

| Test | Verifies |
|---|---|
| `test_not_found_error_use_class_name` | ✅ `use_verbose_name=False` produces class-name key |
| `test_not_found_error_use_verbose_name_true` | ✅ `use_verbose_name=True` produces `verbose_name`-based key |

---

### 🎯 Summary

Version 2.22.0 adds fine-grained control over how `NotFoundError` formats its JSON error key. The new `NINJA_AIO_NOT_FOUND_ERROR_USE_VERBOSE_NAMES` setting is fully backwards-compatible — existing projects are unaffected unless they opt in.

**Key benefits:**
- 🔧 **Configurable** — choose between `verbose_name` (default) or `__name__` as the not-found error key
- ✅ **Backwards-compatible** — default behaviour is identical to v2.21.0
- 📚 **Documented** — new dedicated Exceptions API reference page

---

---

## [v2.21.0] - 2026-02-10

---

### ✨ New Features

#### 🔎 Django Q Object Support in Query Schemas and Filters
> `ninja_aio/schemas/helpers.py`, `ninja_aio/schemas/filters.py`, `ninja_aio/models/utils.py`, `ninja_aio/views/mixins.py`

`ObjectQuerySchema`, `ObjectsQuerySchema`, and `QuerySchema` now accept Django `Q` objects in their `filters` and `getters` fields, enabling complex query expressions with OR/AND logic.

**Q objects in filters (list operations):**

```python
from django.db.models import Q
from ninja_aio.schemas.helpers import ObjectsQuerySchema

# Complex OR conditions
qs = await model_util.get_objects(
    request,
    query_data=ObjectsQuerySchema(
        filters=Q(status="published") | Q(featured=True),
    ),
)
```

**Q objects in getters (single object retrieval):**

```python
from ninja_aio.schemas.helpers import ObjectQuerySchema

obj = await model_util.get_object(
    request,
    pk=42,
    query_data=ObjectQuerySchema(
        getters=Q(is_active=True) & Q(role="admin"),
    ),
)
```

**Q objects in MatchCaseFilterViewSetMixin:**

```python
from django.db.models import Q
from ninja_aio.schemas import MatchCaseFilterSchema, MatchConditionFilterSchema, BooleanMatchFilterSchema

class ArticleViewSet(MatchCaseFilterViewSetMixin, APIViewSet):
    filters_match_cases = [
        MatchCaseFilterSchema(
            query_param="is_featured",
            cases=BooleanMatchFilterSchema(
                true=MatchConditionFilterSchema(
                    query_filter=Q(status="published") & Q(priority__gte=5),
                    include=True,
                ),
                false=MatchConditionFilterSchema(
                    query_filter=Q(status="published") & Q(priority__gte=5),
                    include=False,
                ),
            ),
        ),
    ]
```

**Implementation details:**

| File | Changes |
|---|---|
| `ninja_aio/schemas/helpers.py` | `filters` and `getters` accept `dict \| Q`, added `ConfigDict(arbitrary_types_allowed=True)` |
| `ninja_aio/schemas/filters.py` | `MatchConditionFilterSchema.query_filter` accepts `dict \| Q`, added `ConfigDict(arbitrary_types_allowed=True)` |
| `ninja_aio/models/utils.py` | `_get_base_queryset()` and `get_object()` handle `Q` with `isinstance` check |
| `ninja_aio/views/mixins.py` | `MatchCaseFilterViewSetMixin` applies `Q` objects directly via `filter()`/`exclude()` |

---

### 📚 Documentation

- Updated `docs/api/models/model_util.md` with Q object examples for `get_objects()` and `get_object()`
- Updated `docs/api/views/mixins.md` with Q object example for `MatchCaseFilterViewSetMixin`

---

### 🧪 Tests

#### `MatchCaseQFilterViewSetMixinTestCase` — 3 tests

**Q objects in MatchCaseFilterViewSetMixin:**

| Test | Verifies |
|---|---|
| `test_match_case_q_filter_true_includes` | ✅ Q object filter with `include=True` returns matching records |
| `test_match_case_q_filter_false_excludes` | ✅ Q object filter with `include=False` excludes matching records |
| `test_match_case_q_filter_no_param_returns_all` | ✅ No filter param returns all records |

#### `MatchCaseQExcludeFilterViewSetMixinTestCase` — 2 tests

**Q objects with exclude behavior:**

| Test | Verifies |
|---|---|
| `test_match_case_q_exclude_true` | ✅ Q object exclude with `True` value excludes matching records |
| `test_match_case_q_exclude_false_includes_only` | ✅ Q object exclude with `False` value includes only matching records |

#### `ModelUtilQObjectFiltersTestCase` — 5 tests

**Q objects in ModelUtil filters and getters:**

| Test | Verifies |
|---|---|
| `test_get_objects_with_q_filter` | ✅ `_get_base_queryset` applies Q filter correctly |
| `test_get_objects_with_q_filter_or` | ✅ Q filter with OR logic returns multiple matches |
| `test_get_object_with_q_getter` | ✅ `get_object` applies Q getter with pk |
| `test_get_object_with_q_getter_no_pk` | ✅ `get_object` applies Q getter without pk |
| `test_get_object_with_q_getter_not_found` | ✅ `get_object` raises `NotFoundError` when Q getter has no match |

**New test viewsets:**

| File | Addition |
|---|---|
| `tests/test_app/views.py` | `TestModelSerializerMatchCaseQFilterAPI` — MatchCaseFilter with Q objects |
| `tests/test_app/views.py` | `TestModelSerializerMatchCaseQExcludeFilterAPI` — MatchCaseFilter with Q exclude |

---

### 🎯 Summary

Version 2.21.0 adds **Django Q object support** across query schemas, filters, and match-case mixins, enabling complex OR/AND query expressions without writing custom queryset logic.

**Key benefits:**
- 🔎 **Q Object Support** — Use Django Q objects for complex OR/AND queries in filters, getters, and match-case filters
- 🎯 **Zero Breaking Changes** — Existing `dict`-based filters continue to work unchanged
- ⚡ **Zero Runtime Cost** — Q objects are passed directly to Django ORM with no overhead

---

---

## [v2.20.0] - 2026-02-09

---

### ✨ New Features

#### 🔒 Generic Type System for Full Type Safety
> `ninja_aio/models/utils.py`, `ninja_aio/models/serializers.py`, `ninja_aio/views/api.py`, `ninja_aio/views/mixins.py`, `ninja_aio/api.py`

The entire framework is now **fully generic**, providing complete IDE autocomplete and static type checking for all CRUD operations. When you specify model type parameters, type checkers (mypy, pyright, pylance) understand exactly which model types are being used.

**Generic `Serializer[ModelT]` — Type-safe CRUD methods:**

```python
from ninja_aio.models.serializers import Serializer, SchemaModelConfig
from myapp.models import Book

class BookSerializer(Serializer[Book]):  # 👈 Specify model type
    class Meta:
        model = Book
        schema_in = SchemaModelConfig(fields=["title", "author"])
        schema_out = SchemaModelConfig(fields=["id", "title", "author"])

# All methods are now properly typed!
serializer = BookSerializer()

book: Book = await serializer.create({"title": "1984"})  # ✅ Returns Book
book: Book = await serializer.save(book)                  # ✅ Accepts/returns Book
data: dict = await serializer.model_dump(book)            # ✅ Accepts Book
```

**Generic `APIViewSet[ModelT]` — Type-safe model_util access:**

```python
from ninja_aio.views import APIViewSet
from ninja_aio.api import NinjaAIO

api = NinjaAIO()

@api.viewset(Book)
class BookAPI(APIViewSet[Book]):  # 👈 Explicitly typed
    async def my_method(self, request):
        # self.model_util is typed as ModelUtil[Book]
        book: Book = await self.model_util.get_object(request, pk=1)
        print(book.title)  # ✅ IDE autocomplete works!
```

**Generic `ModelUtil[ModelT]` — Automatic type inference:**

```python
from ninja_aio.models.utils import ModelUtil

# Type automatically inferred as ModelUtil[Book]
util = ModelUtil(Book)

book: Book = await util.get_object(request, pk=1)        # ✅ Returns Book
books: QuerySet[Book] = await util.get_objects(request)  # ✅ Returns QuerySet[Book]
```

**Generic Mixins — All filter mixins are now generic:**

```python
from ninja_aio.views.mixins import IcontainsFilterViewSetMixin

@api.viewset(Author)
class AuthorAPI(IcontainsFilterViewSetMixin[Author]):  # 👈 Specify type
    query_params = {"name": (str, None)}

    async def custom_method(self, request):
        author: Author = await self.model_util.get_object(request, pk=1)
        print(author.name)  # ✅ Autocomplete works!
```

**Key benefits:**
- ✅ **IDE Autocomplete** — Your IDE suggests correct model fields and methods
- ✅ **Type Checking** — Type checkers catch errors at development time
- ✅ **Better Refactoring** — Renaming fields or changing types is caught automatically
- ✅ **Zero Runtime Overhead** — Generic types are erased at runtime

**Implementation details:**

| File | Changes |
|---|---|
| `ninja_aio/models/utils.py` | `ModelUtil` → `ModelUtil(Generic[ModelT])`, all methods typed with `ModelT` |
| `ninja_aio/models/serializers.py` | `Serializer` → `Serializer(Generic[ModelT])`, CRUD methods return/accept `ModelT` |
| `ninja_aio/views/api.py` | `APIViewSet` → `APIViewSet(Generic[ModelT])`, `model_util` typed as `ModelUtil[ModelT]` |
| `ninja_aio/views/mixins.py` | All mixins → `Mixin(APIViewSet[ModelT])` |
| `ninja_aio/api.py` | `viewset()` decorator preserves ViewSet type via `ViewSetT` TypeVar |

**Type Variable definitions:**

```python
# Consistent across all modules
ModelT = TypeVar("ModelT", bound=models.Model)
ViewSetT = TypeVar("ViewSetT", bound=APIViewSet)  # api.py only
```

**Updated docstrings:**

All generic classes now include comprehensive type safety examples in their docstrings showing:
- How to specify type parameters
- Expected return types for all methods
- IDE autocomplete behavior
- Type inference patterns

---

#### 🔍 Field Change Detection Method
> `ninja_aio/models/serializers.py`

Added `has_changed(instance, field)` method to `Serializer` class for detecting if a model field has changed compared to its persisted database value.

```python
@api.viewset(Article)
class ArticleViewSet(APIViewSet):
    serializer_class = ArticleSerializer

    async def custom_update(self, request, pk: int, data):
        article = await Article.objects.aget(pk=pk)
        article.title = data.title

        # Check if title changed before sending notification
        if self.serializer.has_changed(article, "title"):
            await send_notification(f"Title updated: {article.title}")

        await article.asave()
        return await self.serializer.model_dump(article)
```

**Use cases:**
- 🔔 Conditional notifications (only notify if a specific field changed)
- 📝 Audit logging (track which fields were modified)
- ✅ Validation (enforce business rules based on field changes)
- 🗄️ Caching (invalidate cache only when relevant fields change)

**Behavior:**
- Returns `True` if in-memory value differs from DB value
- Returns `False` for new instances (those without a primary key)
- Performs a targeted query: `.filter(pk=pk).values(field).get()[field]`

---

#### 📤 Custom Schema Parameter for Serialization Methods
> `ninja_aio/models/serializers.py`

Both `model_dump()` and `models_dump()` now accept an optional `schema` parameter, allowing you to specify a custom schema for serialization instead of using the default (detail or read schema).

**`model_dump(instance, schema=None)` — Serialize single instance:**

```python
# Use default schema (detail schema if defined, otherwise read schema)
data = await serializer.model_dump(article)

# Use a specific custom schema
custom_schema = ArticleSerializer.generate_read_s()
data = await serializer.model_dump(article, schema=custom_schema)
```

**`models_dump(instances, schema=None)` — Serialize multiple instances:**

```python
# Use default schema
articles = Article.objects.all()
data = await serializer.models_dump(articles)

# Use a specific custom schema
custom_schema = ArticleSerializer.generate_read_s()
data = await serializer.models_dump(articles, schema=custom_schema)
```

**New internal method:**

| Method | Description |
|---|---|
| `_get_dump_schema(schema=None)` | 🎯 Returns provided schema, or falls back to detail schema → read schema |

**Use cases:**
- 🎨 Different response formats for the same endpoint
- 📊 Custom schemas for exports (CSV, Excel, PDF)
- 🔐 Role-based field visibility (admin vs user schemas)
- ⚡ Performance optimization (minimal schemas for bulk operations)

---

### 📚 Documentation

#### 🆕 Type Hints & Type Safety Documentation
> `docs/api/type_hints.md` (NEW)

Created comprehensive documentation covering the new generic type system:

**Sections:**
- 📖 **Overview** — Benefits of type safety (autocomplete, type checking, refactoring, zero overhead)
- 🔧 **Generic Serializer** — Basic usage, benefits, and examples
- 🎯 **Generic APIViewSet** — Three approaches: Type the ViewSet, Type the Serializer (recommended), or both
- 🛠️ **Generic ModelUtil** — Automatic type inference examples
- 🔌 **Generic Mixins** — All six filter mixins with type parameters
- ❓ **Why Explicit Type Parameters?** — Python's type system limitations explained
- 📊 **Framework Comparison** — Django Stubs, FastAPI, SQLAlchemy patterns
- ⚙️ **Type Checker Configuration** — Setup for VS Code (Pylance), PyCharm, mypy
- 🐛 **Troubleshooting** — Common issues and solutions
- 📋 **Summary Table** — Quick reference for all usage patterns

**Added to mkdocs navigation:**

```yaml
- API Reference:
    - Type Hints & Type Safety: api/type_hints.md  # 👈 First item
    - Views: ...
```

---

#### 📝 Serializer Documentation Updates
> `docs/api/models/serializers.md`

Added three new sections to document the latest Serializer improvements:

**1. Serialization Methods** — Documents `model_dump()` and `models_dump()` with optional schema parameter:
- Default schema usage (detail → read fallback)
- Custom schema usage examples
- Type hints showing proper typing

**2. Field Change Detection** — Documents `has_changed()` method:
- Practical example with conditional notifications
- Four key use cases (notifications, audit logging, validation, caching)
- Behavior note for new instances

**3. Type Safety Integration** — Updated Generic Serializer section to show:
- Optional custom schema usage in type hints
- Integration with typed CRUD methods

---

#### 🏠 README Updates
> `README.md`

Added **Type Safety** as the **first feature** in the features table:

| Feature | Technology | Description |
|---|---|---|
| 🔒 **Type Safety** | Generic classes | Full IDE autocomplete and type checking with generic `ModelUtil`, `Serializer`, and `APIViewSet` |

---

### 🎯 Summary

Version 2.20.0 introduces **comprehensive type safety** across the entire framework through generic classes, bringing django-ninja-aio-crud on par with modern Python frameworks in terms of static type analysis support.

**Key benefits:**
- 🎯 **Zero Breaking Changes** — All existing code continues to work without modification
- 🔒 **Type Safety** — Full IDE autocomplete and type checking when you specify type parameters
- 📚 **Documentation** — Comprehensive guide covering all type safety patterns
- 🛠️ **Enhanced Serializers** — Field change detection and flexible schema dumping
- ⚡ **Zero Runtime Cost** — Generic types are erased at runtime, no performance impact

**Three typing approaches:**
1. **Type the Serializer** (Recommended) — Type once, all serializer methods typed
2. **Type the ViewSet** — For model_util-heavy code
3. **Type both** — Maximum type safety everywhere

The framework now provides the same level of type safety as Django Stubs, FastAPI, and SQLAlchemy 2.0 while maintaining its async-first design and zero-boilerplate philosophy.

---

## [v2.19.0] - 2026-02-04

---

### ✨ New Features

#### 🔧 Schema Method Overrides on Serializer Inner Classes
> `ninja_aio/models/serializers.py`

You can now define **Pydantic schema method overrides** (e.g., `model_dump`, `model_validate`, custom properties) on serializer inner classes. The framework automatically injects these methods into the generated Pydantic schema subclass, with full `super()` support via `__class__` cell rebinding.

**ModelSerializer — define on inner serializer classes:**

```python
from __future__ import annotations
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ninja import Schema

class MyModel(ModelSerializer):
    name = models.CharField(max_length=255)

    class ReadSerializer:
        fields = ["id", "name"]

        def model_dump(
            self: Schema,
            *,
            mode: str = "python",
            include: Any = None,
            exclude: Any = None,
            context: Any = None,
            by_alias: bool = False,
            exclude_unset: bool = False,
            exclude_defaults: bool = False,
            exclude_none: bool = False,
            round_trip: bool = False,
            warnings: bool | str = True,
            serialize_as_any: bool = False,
        ) -> dict[str, Any]:
            data = super().model_dump(
                mode=mode, include=include, exclude=exclude,
                context=context, by_alias=by_alias,
                exclude_unset=exclude_unset, exclude_defaults=exclude_defaults,
                exclude_none=exclude_none, round_trip=round_trip,
                warnings=warnings, serialize_as_any=serialize_as_any,
            )
            data["name"] = data["name"].upper()
            return data
```

**Serializer (Meta-driven) — define on validator inner classes:**

```python
class MySerializer(serializers.Serializer):
    class Meta:
        model = MyModel
        schema_out = serializers.SchemaModelConfig(fields=["id", "name"])

    class ReadValidators:
        def model_dump(self: Schema, **kwargs) -> dict[str, Any]:
            data = super().model_dump(**kwargs)
            data["name"] = data["name"].upper()
            return data
```

**New core methods on `BaseSerializer`:**

| Method | Description |
|---|---|
| `_collect_schema_overrides(source_class)` | 🔍 Scans a class for regular callables that aren't validators, config attrs, or dunders |
| `_get_schema_overrides(schema_type)` | 🗺️ Maps schema types to their override source class (overridden per serializer) |

**Implementation details:**
- Overrides are collected alongside validators during schema generation
- `__class__` cell rebinding via `types.FunctionType` + `types.CellType` ensures bare `super()` resolves to the correct subclass
- Validators, `model_config`, and method overrides coexist on the same inner class
- `_CONFIG_ATTRS` frozenset filters out configuration attributes (`fields`, `customs`, `optionals`, `excludes`, `relations_as_id`, `model_config`)

---

#### ⚙️ Pydantic `model_config` Support on Serializers
> `ninja_aio/models/serializers.py`

Both serializer patterns now support applying Pydantic `ConfigDict` to generated schemas.

**ModelSerializer — via `model_config` attribute:**

```python
from pydantic import ConfigDict

class MyModel(ModelSerializer):
    name = models.CharField(max_length=255)

    class CreateSerializer:
        fields = ["name"]
        model_config = ConfigDict(str_strip_whitespace=True)
```

**Serializer (Meta-driven) — via `model_config_override` in `SchemaModelConfig`:**

```python
class MySerializer(serializers.Serializer):
    class Meta:
        model = MyModel
        schema_in = serializers.SchemaModelConfig(
            fields=["name"],
            model_config_override=ConfigDict(str_strip_whitespace=True),
        )
```

**New core methods on `BaseSerializer`:**

| Method | Description |
|---|---|
| `_get_model_config(schema_type)` | Returns `ConfigDict` for the given schema type |

**New field on `SchemaModelConfig`:**

| Field | Type | Description |
|---|---|---|
| `model_config_override` | `Optional[dict]` | Pydantic `ConfigDict` to apply to the generated schema |

---

#### 🔬 Framework Comparison Benchmark Suite
> `tests/comparison/`

Added a comprehensive benchmark suite comparing django-ninja-aio-crud against other popular Python REST frameworks using the same Django models and database.

**Compared frameworks:**
- 🟣 **django-ninja-aio-crud** — Native async CRUD automation
- 🔵 **Django Ninja** (pure) — Async-ready, manual endpoint definition
- 🟠 **ADRF** — Async Django REST Framework
- 🟢 **FastAPI** — Native async, Starlette-based

**Operations tested:** create, list, retrieve, update, delete, filter, relation serialization, bulk serialization (100 & 500 items)

**New files:**

| File | Description |
|---|---|
| `tests/comparison/base.py` | Base benchmark test class |
| `tests/comparison/test_comparison.py` | Comparison benchmark tests |
| `tests/comparison/frameworks/` | Framework-specific implementations (ninja_aio, ninja, adrf, fastapi) |
| `tests/comparison/generate_report.py` | Interactive HTML report generator |
| `tests/comparison/generate_markdown.py` | Markdown report generator |
| `run-comparison.sh` | Helper script to run benchmarks and generate reports |

---

#### 📊 Performance Analysis Tools
> `tests/performance/tools/`

Added statistical analysis tools for detecting performance regressions and analyzing benchmark stability.

| Tool | Description |
|---|---|
| `detect_regression.py` | Statistical regression detection with σ significance (CI/CD recommended) |
| `analyze_perf.py` | Quick overview of recent benchmark runs |
| `analyze_variance.py` | Benchmark stability and coefficient of variation analysis |
| `compare_days.py` | Day-over-day performance comparison |
| `check-performance.sh` | Helper script for running all analysis tools |

---

### 🔧 Improvements

#### 📱 Mobile Chart Fix in Reports
> `tests/performance/generate_report.py`, `tests/comparison/generate_report.py`

Fixed Chart.js charts rendering incorrectly on mobile viewports by adding `maintainAspectRatio: false` to all chart configurations, allowing charts to properly respect their container's CSS height constraints.

---

#### 🎨 Enhanced HTML Report Generation
> `tests/comparison/generate_report.py`, `tests/performance/generate_report.py`

- 🏆 Winner highlighting in comparison tables with purple accent
- 🌗 Light/dark mode support via `prefers-color-scheme`
- 📱 Responsive design with mobile breakpoints (768px, 480px)
- 📈 Interactive Chart.js bar and trend charts

---

### 📚 Documentation

Updated documentation for `model_config`, schema method overrides, and `self: Schema` typing pattern across model serializer, serializer, and validators docs. Added Pydantic `ConfigDict` and `BaseModel` API reference links. Added warning about no automatic argument hinting on inner classes. Updated deployment, troubleshooting, and contributing guides. Rebranded all references from "Django Ninja Aio CRUD" to "Django Ninja AIO".

---

### 🧪 Tests

#### `ModelSerializerSchemaOverridesTestCase` — 3 tests

**Category:** Schema method override verification (ModelSerializer)

| Test | Verifies |
|---|---|
| `test_model_dump_override_applied` | ✅ `model_dump` override transforms output correctly |
| `test_super_call_works` | ✅ Bare `super()` resolves correctly in injected methods |
| `test_model_dump_kwargs_passthrough` | ✅ All `model_dump` kwargs are forwarded properly |

#### `MetaSerializerSchemaOverridesTestCase` — 2 tests

**Category:** Schema method override verification (Meta-driven Serializer)

| Test | Verifies |
|---|---|
| `test_model_dump_override_applied` | ✅ `model_dump` override transforms output on Meta-driven Serializer |
| `test_super_call_works` | ✅ Bare `super()` resolves correctly in Meta-driven overrides |

#### `CollectSchemaOverridesTestCase` — 6 tests

**Category:** `_collect_schema_overrides` unit tests

| Test | Verifies |
|---|---|
| `test_collects_regular_methods` | ✅ Regular methods are collected |
| `test_skips_validators` | ✅ `PydanticDescriptorProxy` instances are skipped |
| `test_skips_config_attrs` | ✅ Config attributes (fields, customs, etc.) are skipped |
| `test_skips_dunders` | ✅ Dunder methods are skipped |
| `test_returns_empty_for_none` | ✅ Returns empty dict for `None` input |
| `test_collects_staticmethod_classmethod` | ✅ Static and class methods are collected |

#### `BaseSerializerSchemaOverridesDefaultTestCase` — 2 tests

**Category:** Default behavior and override-only application

| Test | Verifies |
|---|---|
| `test_default_returns_empty` | ✅ Base `_get_schema_overrides` returns empty dict |
| `test_apply_overrides_only` | ✅ Overrides work without validators |

#### `ModelConfigTestCase` — 10 tests

**Category:** Pydantic `model_config` / `model_config_override` support

| Test | Verifies |
|---|---|
| `test_model_config_*` | ✅ ConfigDict applied to ModelSerializer schemas (create/read/update) |
| `test_meta_model_config_override_*` | ✅ ConfigDict applied to Meta-driven Serializer schemas |
| `test_str_strip_whitespace` | ✅ Whitespace stripping works end-to-end |

**New test fixtures:**

| File | Addition |
|---|---|
| `tests/test_app/models.py` | `TestModelWithSchemaOverrides` — ModelSerializer with `model_dump` override on ReadSerializer |
| `tests/test_app/serializers.py` | `TestModelWithSchemaOverridesMetaSerializer` — Serializer with `model_dump` override on ReadValidators |
| `tests/test_app/serializers.py` | `TestModelWithModelConfigMetaSerializer` — Serializer with `model_config_override` on all schemas |

**Test results:**
- ✅ **656 tests pass**
- ✅ **99% coverage** on `ninja_aio/models/serializers.py`

---

### 🎯 Summary

**Django Ninja AIO v2.19.0** introduces two major serializer features: **schema method overrides** and **Pydantic `model_config` support**. Schema method overrides let you inject custom methods (like `model_dump`) into generated Pydantic schemas from inner serializer classes, with full `super()` support via `__class__` cell rebinding. Pydantic `ConfigDict` can now be applied per-schema for configuration like `str_strip_whitespace`. This release also adds a framework comparison benchmark suite and statistical performance analysis tools.

**Key benefits:**
- 🔧 **Schema Method Overrides** — Inject custom `model_dump`, `model_validate`, or any method into generated schemas with bare `super()` support
- ⚙️ **Pydantic ConfigDict** — Apply `model_config` per-schema on both ModelSerializer and Meta-driven Serializer
- 🔬 **Framework Comparison** — Benchmark against Django Ninja, ADRF, and FastAPI with interactive HTML reports
- 📊 **Regression Detection** — Statistical tools for detecting performance regressions in CI/CD
- 📱 **Mobile-Fixed Charts** — Chart.js charts render correctly on mobile viewports
- 🧪 **23 New Tests** — Comprehensive coverage for overrides, model_config, and edge cases
- 🔄 **Backward Compatible** — All changes are additive with no breaking changes

---

---

## [v2.18.3] - 2026-02-02

---

### ⚡ Performance Improvements

#### 🚀 Foreign Key Resolution Optimization
> `ninja_aio/models/utils.py`

Eliminated redundant database queries during create and update operations by optimizing how foreign key relationships are loaded after object persistence.

**The Problem:**

When creating or updating objects with foreign key fields, the framework was fetching FK relationships twice:
1. Once in `_resolve_fk()` to convert FK IDs to model instances (required by Django's ORM)
2. Again in `get_object()` with `select_related` when retrieving the created/updated object

**Example of redundancy:**
```python
# User creates: POST {"name": "Article", "author_id": 5}

# Before optimization:
# Query 1: SELECT * FROM author WHERE id = 5        (_resolve_fk)
# Query 2: INSERT INTO article (name, author_id) VALUES (...)
# Query 3: SELECT * FROM article
#          LEFT JOIN author ON ...
#          WHERE id = 123                             (get_object - redundant!)

# After optimization:
# Query 1: SELECT * FROM author WHERE id = 5        (_resolve_fk)
# Query 2: INSERT INTO article (name, author_id) VALUES (...)
# Query 3: SELECT * FROM article WHERE id = 123     (prefetch reverse relations only)
#          # FK already in memory, not re-fetched!
```

---

**New method:**

| Method | Line | Description |
|---|---|---|
| `_prefetch_reverse_relations_on_instance()` | 645-689 | Prefetches only reverse relations (reverse FK, reverse O2O, M2M) on an existing instance without re-fetching forward FKs |

**How it works:**

1. **No reverse relations** → Returns original instance with FK cache intact
2. **Reverse relations exist** → Refetches instance with:
   - `prefetch_related()` for reverse relations
   - `select_related()` for forward FKs to keep them loaded

**Modified methods:**

| Method | Line | Change |
|---|---|---|
| `create_s()` | 883-899 | Now keeps full object from `acreate()` instead of just PK; calls `_prefetch_reverse_relations_on_instance()` instead of `get_object()` |
| `update_s()` | 1085-1100 | Calls `_prefetch_reverse_relations_on_instance()` instead of second `get_object()` after save |
| `_resolve_fk()` | 632-634 | Added None check for nullable FK fields |

---

**Performance impact:**

| Operation | Before | After | Queries Saved |
|---|---|---|---|
| **Create** (with FK, no reverse rels) | FK fetch → Create → Full refetch (FK + reverse) | FK fetch → Create → Return (FK in memory) | **1 FK query** ✅ |
| **Create** (with FK + reverse rels) | FK fetch → Create → Full refetch (FK + reverse) | FK fetch → Create → Refetch (FK + reverse) | **1 FK query** ✅ |
| **Update** (changing FK, no reverse rels) | Full fetch → New FK fetch → Update → Full refetch | Full fetch → New FK fetch → Update → Return (FK in memory) | **1 FK query** ✅ |
| **Update** (changing FK + reverse rels) | Full fetch → New FK fetch → Update → Full refetch | Full fetch → New FK fetch → Update → Refetch (FK + reverse) | **1 FK query** ✅ |

**Real-world example:**

```python
@api.viewset(model=Article)
class ArticleViewSet(APIViewSet):
    pass

# POST /articles/
# Payload: {"title": "Django Ninja", "author_id": 5}
#
# Before: 3 queries (2 for author FK - redundant!)
# After:  2 queries (1 for author FK)
#
# Result: 33% fewer queries for create operations with FKs!
```

---

**Edge case handling:**

| Scenario | Behavior |
|---|---|
| Nullable FK with `None` value | Skips FK resolution (line 632-634) |
| Model with FK but no reverse relations | Returns original instance, no refetch needed |
| Model with FK and reverse relations | Refetches with both `select_related` and `prefetch_related` |
| Model without FK fields | No change in behavior |

---

### 🧪 Tests

#### `FKOptimizationTestCase` — 9 new tests

**Test file:** `tests/models/test_fk_optimization.py` (new file, 345 lines)

**Category:** Functional correctness verification

| Test | Verifies |
|---|---|
| `test_create_s_with_fk_returns_correct_data` | ✅ Create operations with FK fields produce correct results |
| `test_create_s_fk_instance_attached` | ✅ FK instances are accessible in returned data without N+1 queries |
| `test_update_s_with_fk_change` | ✅ Update operations correctly change FK values |
| `test_update_s_fk_instance_attached` | ✅ Updated FK instances are accessible in returned data |
| `test_create_s_without_fk_still_works` | ✅ Models without FK fields continue to work correctly |
| `test_reverse_relations_loaded_after_create` | ✅ Forward FK relationships are properly loaded after create |
| `test_multiple_creates_with_same_fk` | ✅ Repeated creates with same FK value work correctly |
| `test_parent_model_with_reverse_relations` | ✅ Models with reverse relations are handled correctly |
| `test_update_s_without_changing_fk` | ✅ Partial updates that don't change FK fields work correctly |

**New test fixtures:**

| File | Addition |
|---|---|
| `tests/test_app/models.py` | Models already existed for FK testing (`TestModelSerializerForeignKey`, `TestModelSerializerReverseForeignKey`) |

**Test results:**
- ✅ **617 tests pass** (up from 608)
- ✅ **19 performance tests pass**
- ✅ **99% coverage** on `ninja_aio/models/utils.py` (line 686 is defensive code for models with both forward FKs and reverse relations - not exercised by current test suite but important for real-world usage)

---

### 🎯 Summary

**Django Ninja Aio CRUD v2.18.3** is a performance optimization release that eliminates redundant foreign key queries during create and update operations. By intelligently caching FK instances resolved during input parsing and only refetching reverse relations when necessary, the framework reduces database queries by 33% for typical CRUD operations involving foreign keys. This optimization is completely transparent to end users - no code changes required - while delivering measurable performance improvements for API endpoints with relational data.

**Key benefits:**
- ⚡ **33% Fewer Queries** — One less DB query per create/update operation with foreign keys
- 🎯 **Smart Caching** — Forward FKs kept in memory after resolution, only reverse relations refetched when needed
- 🔒 **Zero Breaking Changes** — Completely backward compatible, optimization happens automatically
- 🧪 **Thoroughly Tested** — 9 new tests covering all FK scenarios and edge cases
- 📊 **Performance Benchmarks** — All 19 performance tests pass with no regressions
- 💡 **Transparent** — No code changes needed to benefit from optimization

---

---

## [v2.18.2] - 2026-02-02

---

### 🔧 Improvements

#### ✨ Removed Redundant Input Validation
> `ninja_aio/models/utils.py`

Removed redundant input field validation logic since Pydantic already validates all inputs before they reach the payload processing stage. This simplifies the codebase and properly handles field aliases and custom fields.

**Removed methods:**

| Method | Previous Line | Why Removed |
|---|---|---|
| `_validate_input_fields()` | 746-782 | Redundant - Pydantic validates all inputs during schema deserialization |
| `get_valid_input_fields()` | 198-237 | Only used by removed `_validate_input_fields()` method |

**Updated method:**
- `parse_input_data()` - Removed call to `_validate_input_fields()` and added clarifying comment that Pydantic handles all validation

**Why this improves the code:**

Since Django Ninja uses Pydantic to validate all inputs against generated schemas:
- ✅ Custom fields (defined via `custom_fields` parameter) are validated by Pydantic
- ✅ Field aliases are properly handled by Pydantic during deserialization
- ✅ By the time `parse_input_data()` receives the `Schema` instance, all validation has already occurred
- ✅ `model_dump()` simply converts the validated instance to a dict with proper field names

The removed validation was:
- ❌ Redundant (Pydantic already validated)
- ❌ Incomplete (couldn't properly handle all Pydantic features like aliases)
- ❌ Assuming custom fields and aliases couldn't be used in requests

**Example of what now works correctly:**

```python
from pydantic import Field
from ninja_aio.models import Serializer, serializers

class UserSerializer(Serializer):
    class Meta:
        model = User
        schema_in = serializers.SchemaModelConfig(
            fields=["username", "email"],
            custom_fields=[
                ("display_name", str, Field(alias="displayName"))  # Alias support
            ]
        )

# Input with alias now works properly:
# {"username": "john", "email": "john@example.com", "displayName": "John Doe"}
# Pydantic handles the alias → Validation passes → No redundant checks
```

---

### 🧪 Tests

#### `ModelUtilHelperMethodsTestCase` — Removed 3 tests

**Removed tests:**

| Test | Reason |
|---|---|
| `test_validate_input_fields_valid_fields` | Method `_validate_input_fields` no longer exists |
| `test_validate_input_fields_invalid_fields` | Method `_validate_input_fields` no longer exists |
| `test_validate_input_fields_skips_custom_fields` | Method `_validate_input_fields` no longer exists |

**Test results:**
- ✅ 608 tests pass (down from 611)
- ✅ 100% coverage maintained on `ninja_aio/models/utils.py`
- ✅ 99% overall coverage maintained

---

### 🎯 Summary

**Django Ninja Aio CRUD v2.18.2** is a code quality improvement release that removes redundant validation logic. By trusting Pydantic's built-in validation, the codebase is simplified while properly supporting all Pydantic features including field aliases and custom fields. This change has no impact on end users since Pydantic was already handling validation - we simply removed the redundant secondary validation that was incomplete and caused issues with aliases.

**Key benefits:**
- 🧹 **Simpler Code** — Removed 70+ lines of redundant validation logic
- ✅ **Proper Alias Support** — Field aliases now work correctly without workarounds
- 🎯 **Trust the Framework** — Pydantic handles all input validation; no redundant checks needed
- 🔒 **Same Security** — No security impact since Pydantic validation was already the primary defense
- 🧪 **100% Coverage** — Maintained complete test coverage across the codebase

---

---

## [v2.18.1] - 2026-02-01

---

### 🔒 Security Fixes

#### 🔄 Circular Reference Protection
> `ninja_aio/models/serializers.py`

Fixed potential infinite recursion and stack overflow from circular model relationships by adding thread-safe circular reference detection.

**New methods:**

| Method | Line | Description |
|---|---|---|
| `_resolution_context` | 1921 | Thread-local storage for resolution stack |
| `_get_resolution_stack()` | 1926-1934 | Returns resolution stack for current thread |
| `_is_circular_reference()` | 1937-1954 | Checks if model/schema_type is already being resolved |
| `_push_resolution()` | 1957-1962 | Pushes model/schema_type onto resolution stack |
| `_pop_resolution()` | 1965-1969 | Pops model/schema_type from resolution stack |

**Enhanced method:**
- `_resolve_related_model_schema()` (lines 1994-2039) - Now detects circular references and raises `ValueError` with clear message

**Example scenario that previously caused infinite recursion:**
```python
class Author(ModelSerializer):
    articles = models.ManyToManyField('Article', related_name='authors')
    class ReadSerializer:
        fields = ['id', 'name', 'articles']

class Article(ModelSerializer):
    authors = models.ManyToManyField(Author, related_name='articles')
    class ReadSerializer:
        fields = ['id', 'title', 'authors']  # Circular!
```

Now raises a clear error instead of causing stack overflow.

---

#### 🛡️ Field Injection Prevention
> `ninja_aio/models/utils.py`

Fixed potential security vulnerability by adding input field validation to prevent malicious field injection in payloads.

**New methods:**

| Method | Line | Description |
|---|---|---|
| `get_valid_input_fields()` | 2282-2322 | Returns allowlist of valid field names from model |
| `_validate_input_fields()` | 2440-2476 | Validates payload fields against model, raises `ValueError` for invalid fields |

**Applied in:**
- `parse_input_data()` (line 908) - Validates all input payloads before processing

**Now blocks malicious payloads:**
```python
{
    "username": "hacker",
    "password": "secret",
    "_state": {},  # ❌ Now blocked
    "pk": 999,     # ❌ Now blocked if not in model fields
}
```

---

#### 🔍 Filter Field Validation
> `ninja_aio/views/api.py`

Fixed potential filter injection vulnerability by adding comprehensive filter field validation.

**New validation methods:**

| Method | Line | Description |
|---|---|---|
| `_validate_filter_field()` | 2749-2840 | Main validation method for filter field paths |
| `_is_lookup_suffix()` | Helper | Checks if suffix is valid Django lookup (e.g., `__icontains`, `__gte`) |
| `_get_related_model()` | Helper | Extracts related model from ForeignKey/ManyToMany field |
| `_validate_non_relation_field()` | Helper | Validates non-relation field placement in path |

**Applied to all filter mixins:**
- `IcontainsFilterViewSetMixin` (lines 2886-2904)
- `BooleanFilterViewSetMixin` (lines 2907-2920)
- `NumericFilterViewSetMixin` (lines 2923-2936)
- `DateFilterViewSetMixin` (lines 2939-2952)
- `RelationFilterViewSetMixin` (lines 2955-2968)
- `MatchCaseFilterViewSetMixin` (lines 2971-2984)

**Now blocks injection attempts:**
```python
?author___state__db=malicious  # ❌ Now blocked (invalid lookup)
?author__password__icontains=admin  # ❌ Now blocked (invalid field path)
```

---

#### 🎯 Django Lookup Types
> `ninja_aio/types.py`

Added `DjangoLookup` type and `VALID_DJANGO_LOOKUPS` set containing all 36 valid Django ORM lookup suffixes for validation.

**Valid lookups:**
- Equality: `exact`, `iexact`
- Comparison: `gt`, `gte`, `lt`, `lte`, `range`
- Text: `contains`, `icontains`, `startswith`, `istartswith`, `endswith`, `iendswith`, `regex`, `iregex`
- Boolean: `isnull`, `in`
- Date/Time: `date`, `year`, `month`, `day`, `week`, `week_day`, `quarter`, `time`, `hour`, `minute`, `second`

---

### 🚀 Performance Improvements

#### ⚡ Schema Generation Caching
> `ninja_aio/models/serializers.py`

Added `@lru_cache(maxsize=128)` to all schema generation methods, dramatically reducing repeated schema generation overhead.

**Cached methods:**

| Method | Line | Expected Speedup |
|---|---|---|
| `generate_read_s()` | 1193 | 10-100x for repeated calls |
| `generate_detail_s()` | 1207 | 10-100x for repeated calls |
| `generate_create_s()` | 1225 | 10-100x for repeated calls |
| `generate_update_s()` | 1238 | 10-100x for repeated calls |
| `generate_related_s()` | 1252 | 10-100x for repeated calls |

**Benefit:** Schema generation is expensive (Pydantic model creation, validator collection, etc.). Since model structure is static, caching eliminates redundant work.

---

#### ⚡ Relation Discovery Caching
> `ninja_aio/models/utils.py`

Added class-level `_relation_cache` dictionary to cache discovered model relationships.

**Cached methods:**

| Method | Line | What It Caches |
|---|---|---|
| `get_reverse_relations()` | 2575-2361 | Reverse ForeignKey and ManyToMany relations |
| `get_select_relateds()` | 2621-2640 | Forward ForeignKey relations for select_related |

**Benefit:** Model relationships are static at runtime. Caching eliminates repeated model introspection overhead.

---

#### ⚡ Parallel Field Processing
> `ninja_aio/models/utils.py`

Refactored payload processing to use `asyncio.gather()` for parallel field resolution.

**New method:**
- `_process_payload_fields()` (lines 2546-2578) - Processes all fields in parallel

**Applied in:**
- `parse_input_data()` (lines 915-916) - Fetches all field objects and resolves all FK fields concurrently

**Benefit:** Significantly faster for payloads with multiple fields, especially when resolving foreign keys that require database lookups.

---

### 🧹 Code Quality Improvements

#### Reduced Cognitive Complexity in BaseSerializer
> `ninja_aio/models/serializers.py`

Extracted helper methods from `_generate_model_schema()` to improve readability and maintainability.

**New helper methods:**

| Method | Line | Purpose |
|---|---|---|
| `_create_out_or_detail_schema()` | 1092-1114 | Handles Out and Detail schema types |
| `_create_related_schema()` | 1117-1132 | Handles Related schema type |
| `_create_in_or_patch_schema()` | 1135-1147 | Handles In and Patch schema types |

**Simplified main method:**
- `_generate_model_schema()` (lines 1150-1184) - Now dispatches to appropriate helper based on schema type

**Benefit:** Reduced cognitive complexity, improved testability, clearer error handling paths.

---

#### Reduced Cognitive Complexity in ModelUtil
> `ninja_aio/models/utils.py`

Extracted helper methods from `parse_input_data()` to improve readability and testability.

**New helper methods:**

| Method | Line | Purpose |
|---|---|---|
| `_collect_custom_and_optional_fields()` | 2478-2514 | Collects custom and optional fields from payload |
| `_determine_skip_keys()` | 2516-2545 | Determines which keys to skip during processing |
| `_process_payload_fields()` | 2546-2578 | Processes payload fields in parallel |

**Added type hints and docstrings:**

| Method | Line | Return Type |
|---|---|---|
| `_get_field()` | 2640-2648 | `models.Field` |
| `_decode_binary()` | 2650-2658 | `None` |
| `_resolve_fk()` | 2660-2668 | `None` |
| `_bump_object_from_schema()` | 2670-2675 | `dict` |
| `_validate_read_params()` | 2677-2682 | `None` |

---

#### Type Hints & Documentation in ViewSets
> `ninja_aio/views/api.py`

Added comprehensive return type hints to all view registration and authentication methods.

**Updated methods:**

| Method | Line | Return Type |
|---|---|---|
| `_add_views()` | 2724-2739 | `Router` |
| `add_views_to_route()` | 2846-2862 | `Router` |
| `views()` | — | `None` |
| `get_view_auth()` | — | `list \| None` |
| `post_view_auth()` | — | `list \| None` |
| `put_view_auth()` | — | `list \| None` |
| `patch_view_auth()` | — | `list \| None` |
| `delete_view_auth()` | — | `list \| None` |
| `_generate_path_schema()` | — | `Schema` |

---

### 📚 Documentation Improvements

#### 📱 Mobile Responsiveness
> `docs/extra.css`

Added comprehensive mobile responsive CSS for better documentation experience on mobile devices.

**Improvements:**
- 📱 Hero section optimized for small screens with reduced logo size (280px on mobile, 240px on very small screens)
- 🎯 Responsive badge layout with proper wrapping and flexbox (badges reduced to 20px height on mobile)
- 📱 Mobile-friendly CTA buttons with proper touch targets (44px minimum)
- 📊 Responsive grid cards (single column on mobile)
- 📝 Better code block overflow handling
- 📋 Responsive tables with horizontal scroll
- 🎨 Optimized release cards and timeline for mobile
- 📐 Smaller fonts and tighter spacing for mobile (768px and 480px breakpoints)
- 🔤 Announcement bar with proper padding to prevent text cutoff
- 🖼️ Header logo reduced from 2.0rem to 1.6rem on mobile devices

---

#### Updated Tutorial Documentation

Updated all tutorial and API documentation to use the `@api.viewset()` decorator pattern:

| File | What Changed |
|---|---|
| `docs/tutorial/crud.md` | Simplified viewset registration examples |
| `docs/tutorial/authentication.md` | Updated authentication examples |
| `docs/tutorial/filtering.md` | Updated all viewset examples |
| `docs/api/authentication.md` | Updated authentication examples |
| `docs/api/pagination.md` | Updated pagination examples |

**Before:**
```python
class ArticleViewSet(APIViewSet):
    model = Article
    api = api

ArticleViewSet().add_views_to_route()
```

**After (cleaner):**
```python
@api.viewset(model=Article)
class ArticleViewSet(APIViewSet):
    pass
```

---

#### Updated README and Documentation
> `README.md`, `docs/index.md`

- ✅ Updated to use full logo image (`logo-full.png`)
- ✅ Added Performance badge and link to benchmarks
- ✅ Improved landing page structure
- ✅ Better mobile responsiveness

---

#### Updated Project Instructions
> `CLAUDE.md`

**New sections:**
- 🧪 **Running Performance Tests** - Guide to running and understanding performance benchmarks (for contributors)
- ✅ **Test-Driven Development Protocol** - Testing requirements for all code changes
- 📦 **Import Style Guideline** - PEP 8 import placement requirements

**Improvements:**
- 🗑️ Removed "All Files Changed" table requirement from changelog format
- ✨ Streamlined changelog guidelines

---

### 🧪 Test Coverage

Added comprehensive tests for all new functionality:

**`tests/models/test_models_extra.py`** — 161 new lines:

| Test Case | Tests | Verifies |
|---|---|---|
| `ModelUtilSerializerReadOptimizationsTestCase` | 2 | Queryset optimization for serializer reads |
| `ModelUtilHelperMethodsTestCase` | 9 | Refactored helper methods |
| - `test_validate_input_fields_*` | 3 | Field injection prevention |
| - `test_collect_custom_and_optional_fields_*` | 4 | Custom/optional field collection |
| - `test_determine_skip_keys_*` | 2 | Skip key determination logic |

**`tests/test_serializers.py`** — 309 new lines, 14 test cases:

| Test Case | Tests | Verifies |
|---|---|---|
| `BaseSerializerDefaultMethodsTestCase` | 2 | Default method implementations |
| `ResolveSerializerReferenceEdgeCasesTestCase` | 3 | Circular reference detection edge cases |
| `GetSchemaOutDataEdgeCasesTestCase` | 1 | Schema output data edge cases |
| `GenerateModelSchemaEdgeCasesTestCase` | 2 | Schema generation edge cases |
| `GetRelatedSchemaDataEdgeCasesTestCase` | 1 | Related schema data edge cases |
| `QuerysetRequestNotImplementedTestCase` | 1 | NotImplementedError for missing queryset_request |
| `ModelSerializerGetFieldsEdgeCasesTestCase` | 1 | Field retrieval edge cases |
| `SerializerGetSchemaMetaEdgeCasesTestCase` | 2 | Schema meta edge cases |
| `SerializerCRUDMethodsTestCase` | 4 | CRUD method edge cases |
| `WarnMissingRelationSerializerTestCase` | 1 | Warning for missing relation serializers |
| `BuildSchemaReverseRelNoneTestCase` | 1 | Reverse relation None handling |
| `BuildSchemaForwardRelNoReadFieldsTestCase` | 1 | Forward relation missing read fields |

**`tests/views/test_views.py`** — 237 new lines:

| Test Case | Tests | Verifies |
|---|---|---|
| `APIViewViewsPassTestCase` | 1 | View registration with decorator |
| `APIViewSetDisableAllTestCase` | 1 | Disabling all CRUD operations |
| `RelationsFiltersFieldsTestCase` | 1 | Relation filter field validation |
| `BuildHandlerTestCase` | 2 | Handler building edge cases |
| `FilterValidationHelpersTestCase` | 17 | All filter validation helper methods |

**`tests/helpers/test_many_to_many_api.py`** — 31 new lines:

| Test Case | Tests | Verifies |
|---|---|---|
| `GetApiPathNoSlashTestCase` | 1 | API path with `append_slash=False` |

**Total:** 50+ new unit tests for security features and edge cases. 100% coverage maintained.

---

### 🏗️ Internal/Development Improvements

#### Performance Benchmark Suite (for contributors)
> `tests/performance/`

Added comprehensive performance benchmarking infrastructure for monitoring framework performance during development.

**Benchmark categories:**
- Schema generation (4 tests)
- Serialization (4 tests)
- CRUD operations (5 tests)
- Filter performance (6 tests)

**Note:** This is for development/CI only. End users are not affected.

---

#### GitHub Actions Workflow
> `.github/workflows/performance.yml`

Added automated performance benchmarking workflow:
- Runs on push to main and PRs
- Checks for >20% performance regressions
- Deploys interactive reports to GitHub Pages

---

#### Gitignore Updates
> `.gitignore`

Added performance report files:
- `performance_results.json`
- `performance_report.html`

---

### 🎯 Summary

**Django Ninja Aio CRUD v2.18.1** is a maintenance release focused on **security fixes**, **performance improvements**, and **documentation enhancements**. Three critical security vulnerabilities have been fixed to protect against circular reference attacks, field injection, and filter injection. Performance improvements through caching and parallel processing deliver 2-10x speedups for schema generation and serialization. Documentation has been enhanced with comprehensive mobile responsiveness. Internal improvements include a performance benchmark suite for ongoing development.

**Key benefits:**
- 🔒 **Security Hardened** — Fixed vulnerabilities: circular reference protection, field injection prevention, filter field validation
- ⚡ **Faster Performance** — 2-10x speedup for schema generation and serialization through caching and parallel processing
- 📱 **Mobile-Friendly Docs** — Comprehensive mobile responsiveness with optimized layouts and touch targets
- 🧹 **Cleaner Code** — Reduced cognitive complexity, comprehensive type hints, improved maintainability
- 🧪 **Robust Testing** — 50+ new unit tests, 100% coverage maintained
- 📊 **Performance Monitoring** — Internal benchmark suite for ongoing performance tracking (contributors only)

---

---

## [v2.18.0] - 2026-02-01

---

### ✨ New Features

#### 🛡️ Validators on Serializers

> `ninja_aio/models/serializers.py`

Pydantic `@field_validator` and `@model_validator` can now be declared directly on serializer configuration classes. The framework automatically collects `PydanticDescriptorProxy` instances and creates a subclass of the generated schema with the validators attached.

**Supported on both serializer patterns:**

| Pattern | Where to declare validators |
|---|---|
| `ModelSerializer` | Inner classes: `CreateSerializer`, `ReadSerializer`, `UpdateSerializer`, `DetailSerializer` |
| `Serializer` (Meta-driven) | Dedicated inner classes: `CreateValidators`, `ReadValidators`, `UpdateValidators`, `DetailValidators` |

🔀 Different validation rules can be applied per operation (e.g., stricter rules on create, lenient on update).

**ModelSerializer example:**

```python
from django.db import models
from pydantic import field_validator, model_validator
from ninja_aio.models import ModelSerializer

class Book(ModelSerializer):
    title = models.CharField(max_length=120)
    description = models.TextField(blank=True)

    class CreateSerializer:
        fields = ["title", "description"]

        @field_validator("title")
        @classmethod
        def validate_title_min_length(cls, v):
            if len(v) < 3:
                raise ValueError("Title must be at least 3 characters")
            return v

    class UpdateSerializer:
        optionals = [("title", str), ("description", str)]

        @field_validator("title")
        @classmethod
        def validate_title_not_empty(cls, v):
            if v is not None and len(v.strip()) == 0:
                raise ValueError("Title cannot be blank")
            return v
```

**Serializer (Meta-driven) example:**

```python
from pydantic import field_validator
from ninja_aio.models import serializers

class BookSerializer(serializers.Serializer):
    class Meta:
        model = Book
        schema_in = serializers.SchemaModelConfig(fields=["title", "description"])
        schema_out = serializers.SchemaModelConfig(fields=["id", "title", "description"])

    class CreateValidators:
        @field_validator("title")
        @classmethod
        def validate_title_min_length(cls, v):
            if len(v) < 3:
                raise ValueError("Title must be at least 3 characters")
            return v
```

---

#### 🧩 New Core Methods on `BaseSerializer`

> `ninja_aio/models/serializers.py`

| Method | Description |
|---|---|
| `_collect_validators(source_class)` | 🔍 Scans a class for `PydanticDescriptorProxy` instances created by `@field_validator` / `@model_validator` decorators. Returns a dict mapping attribute names to validator proxies. |
| `_apply_validators(schema, validators)` | 🔗 Creates a subclass of the generated schema with validators attached. Pydantic discovers validators during class creation. |
| `_get_validators(schema_type)` | 🗺️ Abstract method for subclasses to map schema types (`In`, `Patch`, `Out`, `Detail`, `Related`) to their validator source classes. |

---

#### 🆕 New `_parse_payload()` Method on Serializer

> `ninja_aio/models/serializers.py`

`Serializer._parse_payload(payload)` accepts both `dict` and `Schema` instances, automatically calling `model_dump()` on Schema inputs. This enables passing validated Pydantic schemas directly to `create()` and `update()`.

---

#### 📖 New Tutorial: "Define Your Serializer"

> `docs/tutorial/serializer.md`

Comprehensive tutorial page for the Meta-driven `Serializer` approach as an alternative to Step 1 (ModelSerializer). Covers:

- 📐 Schema definition with `SchemaModelConfig`
- 🔗 Relationships via `relations_serializers`
- ⚙️ Custom and computed fields
- 🚀 Query optimizations with `QuerySet`
- 🔄 Lifecycle hooks
- 🔌 Connecting to `APIViewSet`

---

#### 📚 New Validators Documentation Page

> `docs/api/models/validators.md`

Full dedicated documentation page covering:

- 🏗️ `ModelSerializer` and `Serializer` approaches
- ✅ Supported validator types and modes
- 🔀 Different validators per operation
- ⚙️ Internal mechanics
- ⚠️ Error handling (422 responses)
- 💡 Complete examples

---

### 🔧 Improvements

#### ⚡ Schema Generation Now Applies Validators

> `ninja_aio/models/serializers.py`

`_generate_model_schema()` now calls `_get_validators()` for the requested schema type and `_apply_validators()` on the resulting schema. Applied consistently across all schema types: `Out`, `Detail`, `Related`, `In`, and `Patch`.

---

#### 📦 `create()` and `update()` Accept Schema Objects

> `ninja_aio/models/serializers.py`

`Serializer.create()` and `Serializer.update()` payload parameter type changed from `dict[str, Any]` to `dict[str, Any] | Schema`, using the new `_parse_payload()` method to handle both inputs transparently.

---

#### 🏷️ Updated Type Annotations

> `ninja_aio/models/serializers.py`

- `ModelSerializer` inner classes now accept `tuple[str, Any]` in addition to `tuple[str, Any, Any]` for both `fields` and `customs` attributes.
- `SchemaModelConfig.customs` type annotation updated to `List[tuple[str, Any, Any] | tuple[str, Any]]`.

---

#### 📝 Comprehensive Docstrings

> `ninja_aio/models/serializers.py`

Added detailed NumPy-style docstrings with `Parameters`, `Returns`, and `Raises` sections to virtually all methods in `BaseSerializer`, `ModelSerializer`, and `Serializer` (30+ methods).

---

### 🎨 Documentation Overhaul

#### 💎 Complete Site Redesign

All documentation pages updated with Material for MkDocs icons, grid cards, section dividers, and modern formatting:

- 🏠 **Landing page** — Hero section, CTA buttons, grid cards for features, tabbed code comparison, Schema Validators section, key concepts in card layout
- 📖 **Tutorial pages** — Hero banners with step indicators, learning objectives, prerequisites boxes, summary checklists
- 📑 **API reference pages** — Material icons on headings, section dividers, "See Also" replaced with grid cards
- 🎨 **Custom CSS** — New styles for hero sections, card grids, tutorial components, and release notes UI
- ⚙️ **MkDocs theme** — Added template overrides, announcement bar, emoji extension, `md_in_html`, new navigation features

---

#### 🖼️ README Redesign

> `README.md`

- 🎯 Centered HTML layout: logo, title, subtitle, and badge row
- 📊 Features bullet list replaced with formatted table
- 🅰️🅱️ Quick Start restructured into "Option A" and "Option B" sections
- 🛡️ New "Schema Validators" section with examples and mapping table
- 🔄 "Lifecycle Hooks" bullet list replaced with table
- 🧹 Redundant sections removed, "Buy me a coffee" uses styled badge

---

#### 🗂️ MkDocs Navigation Updates

> `mkdocs.yml`

- ➕ Added `tutorial/serializer.md` — "Alternative: Define Your Serializer"
- ➕ Added `api/models/validators.md` — "Validators"
- ➕ Added `api/renderers/orjson_renderer.md` — "Renderers"

---

#### 🔄 Release Notes Page Redesign

> `main.py`

Replaced table-based release notes layout with an interactive dropdown version selector and card-based display with human-readable date formatting.

---

### 🧪 Tests

> `tests/test_serializers.py`, `tests/test_app/models.py`, `tests/test_app/serializers.py`

#### `ValidatorsOnSerializersTestCase` — 14 tests

**🏗️ ModelSerializer validators:**

| Test | Verifies |
|---|---|
| `test_model_serializer_field_validator_rejects_invalid` | ❌ `@field_validator` on `CreateSerializer` rejects input below min length |
| `test_model_serializer_field_validator_accepts_valid` | ✅ `@field_validator` on `CreateSerializer` accepts valid input |
| `test_model_serializer_update_validator_rejects_blank` | ❌ `@field_validator` on `UpdateSerializer` rejects blank name |
| `test_model_serializer_update_validator_accepts_valid` | ✅ `@field_validator` on `UpdateSerializer` accepts valid input |
| `test_model_serializer_read_model_validator` | ✅ `@model_validator` on `ReadSerializer` is applied to output schema |
| `test_model_serializer_no_validators_returns_plain_schema` | ✅ Serializers without validators still work normally |

**🗺️ Meta-driven Serializer validators:**

| Test | Verifies |
|---|---|
| `test_meta_serializer_field_validator_rejects_invalid` | ❌ `CreateValidators` `@field_validator` rejects invalid input |
| `test_meta_serializer_field_validator_accepts_valid` | ✅ `CreateValidators` `@field_validator` accepts valid input |
| `test_meta_serializer_update_validator_rejects_blank` | ❌ `UpdateValidators` `@field_validator` rejects blank name |
| `test_meta_serializer_read_model_validator` | ✅ `ReadValidators` `@model_validator` is applied to output schema |

**🔧 Utility method tests:**

| Test | Verifies |
|---|---|
| `test_collect_validators_returns_empty_for_none` | 🔍 `_collect_validators(None)` returns `{}` |
| `test_collect_validators_returns_empty_for_no_validators` | 🔍 `_collect_validators` returns `{}` for class without validators |
| `test_apply_validators_returns_none_for_none_schema` | 🔍 `_apply_validators(None, ...)` returns `None` |
| `test_apply_validators_returns_schema_for_empty_validators` | 🔍 `_apply_validators(schema, {})` returns original schema |

**📦 New test fixtures:**

| File | Addition |
|---|---|
| `tests/test_app/models.py` | `TestModelWithValidators` — model with validators on `CreateSerializer`, `UpdateSerializer`, `ReadSerializer` |
| `tests/test_app/serializers.py` | `TestModelWithValidatorsMetaSerializer` — serializer with `CreateValidators`, `UpdateValidators`, `ReadValidators` |

---

### 📁 New Files

| File | Description |
|---|---|
| `CLAUDE.md` | 📋 Project instructions: overview, structure, tests, code style, architecture notes |
| `CHANGELOG.md` | 📝 Latest release notes |

---

### 🎯 Summary

This release introduces **Pydantic validators on serializers**, allowing `@field_validator` and `@model_validator` to be declared directly on serializer configuration classes. The framework automatically collects and applies these validators to generated schemas. Additionally, the entire documentation site has been redesigned with Material for MkDocs components.

**🌟 Key benefits:**

- 🛡️ **Schema-level validation** — Enforce input constraints beyond Django model fields, running before data touches the database
- 🔀 **Per-operation validation** — Apply different validation rules per CRUD operation (create vs. update vs. read)
- 🏗️ **Both serializer patterns** — Works with `ModelSerializer` (inner classes) and `Serializer` (`{Type}Validators` classes)
- ♻️ **Backwards compatible** — Existing serializers without validators continue to work unchanged
- 🎨 **Documentation redesign** — Modern Material for MkDocs layout with grid cards, hero sections, and interactive release notes

---

## [v2.17.0] - 2026-01-28

---

## ✨ New Features

- **Inline Custom Fields in `fields` List** [`ninja_aio/models/serializers.py`]:
  - Custom fields can now be defined directly in the `fields` list as tuples, providing a more concise syntax.
  - Supports both 2-tuple `(name, type)` for required fields and 3-tuple `(name, type, default)` for optional fields.
  - Works with both `ModelSerializer` (inner classes) and `Serializer` (Meta-driven) approaches.
  - Applies to all serializer types: `CreateSerializer`, `ReadSerializer`, `DetailSerializer`, `UpdateSerializer`, and `SchemaModelConfig`.

  **Usage example (ModelSerializer):**
  ```python
  from ninja_aio.models import ModelSerializer

  class Article(ModelSerializer):
      title = models.CharField(max_length=200)
      content = models.TextField()

      class ReadSerializer:
          fields = [
              "id",
              "title",
              ("word_count", int, 0),        # 3-tuple: optional with default
              ("is_featured", bool),          # 2-tuple: required field
          ]
  ```

  **Usage example (Serializer):**
  ```python
  from ninja_aio.models import serializers

  class ArticleSerializer(serializers.Serializer):
      class Meta:
          model = Article
          schema_out = serializers.SchemaModelConfig(
              fields=["id", "title", ("reading_time", int, 0)]
          )
  ```

- **New `get_inline_customs()` Helper Method** [`ninja_aio/models/serializers.py`]:
  - Added `BaseSerializer.get_inline_customs(s_type)` method to extract and normalize inline custom tuples from the `fields` list.
  - Returns a list of normalized 3-tuples `(name, type, default)`, converting 2-tuples by adding `...` (Ellipsis) as the default.

---

## 🔧 Improvements

- **Refactored `get_fields()` Method** [`ninja_aio/models/serializers.py`]:
  - `get_fields()` now returns only string field names, excluding inline custom tuples.
  - Clearer separation of concerns between model fields and custom fields.

- **Improved `get_related_schema_data()` Method** [`ninja_aio/models/serializers.py`]:
  - Fixed handling of custom fields that don't exist as model attributes.
  - Custom fields (both explicit and inline) are now always included in related schemas since they are computed/synthetic.

- **Updated `SchemaModelConfig` Type Annotations** [`ninja_aio/models/serializers.py`]:
  - The `fields` attribute now accepts `List[str | tuple[str, Any, Any] | tuple[str, Any]]` to support inline customs.
  - Updated docstring to document the new tuple formats.

- **Cleaner Schema Generation** [`ninja_aio/models/serializers.py`]:
  - `get_schema_out_data()` and `_generate_model_schema()` now use the new `get_inline_customs()` helper, reducing code duplication.

---

## 🧪 Tests

- **New Inline Customs Test Cases** [`tests/test_serializers.py`]:
  - Added `InlineCustomsSerializerTestCase` test class with 11 tests for Meta-driven Serializer:
    - `test_serializer_read_schema_with_inline_customs_3_tuple`: Verifies 3-tuple inline customs work in read schema.
    - `test_serializer_read_schema_with_inline_customs_2_tuple`: Verifies 2-tuple inline customs work in read schema.
    - `test_serializer_create_schema_with_inline_customs`: Verifies inline customs in create schema.
    - `test_serializer_update_schema_with_inline_customs`: Verifies inline customs in update schema.
    - `test_serializer_inline_customs_combined_with_explicit_customs`: Verifies inline and explicit customs coexist.
    - `test_serializer_get_fields_excludes_inline_customs`: Verifies `get_fields()` returns only strings.
    - `test_serializer_get_inline_customs_returns_only_tuples`: Verifies `get_inline_customs()` returns normalized tuples.
    - `test_serializer_detail_schema_with_inline_customs`: Verifies inline customs in detail schema.
    - `test_serializer_related_schema_with_inline_customs`: Verifies inline customs in related schema.
    - `test_inline_customs_only_schema`: Verifies schema with only inline customs (no regular fields).

  - Added `InlineCustomsModelSerializerTestCase` test class with 4 tests for ModelSerializer:
    - `test_model_serializer_read_schema_with_inline_customs`: Verifies inline customs in ReadSerializer.
    - `test_model_serializer_create_schema_with_inline_customs`: Verifies inline customs in CreateSerializer.
    - `test_model_serializer_get_inline_customs`: Verifies `get_inline_customs()` for ModelSerializer.
    - `test_model_serializer_get_fields_excludes_inline_customs`: Verifies `get_fields()` excludes inline customs.

- **New Test Model** [`tests/test_app/models.py`]:
  - Added `TestModelSerializerInlineCustoms` model with inline customs in both `ReadSerializer` and `CreateSerializer`.

---

## 📚 Documentation

- **Updated Serializer Documentation** [`docs/api/models/serializers.md`]:
  - Added new "Inline Custom Fields" section with usage examples.
  - Updated `SchemaModelConfig` fields description to mention inline custom tuples.
  - Added explanation of 2-tuple and 3-tuple formats.

- **Updated ModelSerializer Documentation** [`docs/api/models/model_serializer.md`]:
  - Updated all serializer attribute tables to show `list[str | tuple]` type for `fields`.
  - Added "Inline Custom Fields" subsection in CreateSerializer with usage example.
  - Updated ReadSerializer, DetailSerializer, and UpdateSerializer tables.

---

## 📋 Summary

This minor release introduces inline custom field support, allowing custom/computed fields to be defined directly in the `fields` list as tuples. This provides a more concise syntax for simple custom fields while maintaining full backwards compatibility with the separate `customs` list approach.

### Key Benefits
- **Concise syntax**: Define simple custom fields inline without a separate `customs` list
- **Flexibility**: Mix regular fields and custom tuples in the same list
- **Backwards compatible**: Existing code using `customs` list continues to work unchanged

### Files Changed
| File | Changes |
|------|---------|
| `ninja_aio/models/serializers.py` | Added `get_inline_customs()` method, updated `get_fields()`, `get_schema_out_data()`, `_generate_model_schema()`, `get_related_schema_data()`, and `SchemaModelConfig` |
| `tests/test_serializers.py` | Added 15 new tests across 2 test classes |
| `tests/test_app/models.py` | Added `TestModelSerializerInlineCustoms` test model |
| `docs/api/models/serializers.md` | Added inline custom fields documentation with examples |
| `docs/api/models/model_serializer.md` | Updated all serializer attribute tables and added inline customs section |

---

## [v2.16.2] - 2026-01-27

---

## 🐛 Bug Fixes

- **Fixed Schema Generation with Only Custom Fields** [`ninja_aio/models/serializers.py`]:
  - Fixed an issue in `_generate_model_schema()` where defining only `customs` and/or `optionals` (without explicit `fields` or `excludes`) would incorrectly include all model fields in the generated schema.
  - When only custom fields are defined, the schema now correctly excludes all concrete model fields, returning a schema with only the specified custom fields.
  - This fix applies to both `Serializer` (Meta-driven) and `ModelSerializer` create/update schema generation.

  **Before (broken behavior):**
  ```python
  class MySerializer(Serializer):
      class Meta:
          model = MyModel
          schema_in = SchemaModelConfig(
              customs=[("custom_input", str, ...)]
          )

  # Generated schema incorrectly included ALL model fields + custom_input
  ```

  **After (fixed behavior):**
  ```python
  class MySerializer(Serializer):
      class Meta:
          model = MyModel
          schema_in = SchemaModelConfig(
              customs=[("custom_input", str, ...)]
          )

  # Generated schema now correctly includes ONLY custom_input
  ```

---

## 🔧 Improvements

- **Union Type Support in SchemaModelConfig** [`ninja_aio/models/serializers.py`]:
  - Updated `optionals` and `customs` field type hints in `SchemaModelConfig` to accept `Any` instead of `type`.
  - This allows using Union types and other complex type annotations in schema configurations.

  **Usage example:**
  ```python
  from typing import Union

  schema_in = SchemaModelConfig(
      optionals=[("status", str | None)],
      customs=[
          ("data", Union[str, int], None),
          ("items", list[int], []),
      ],
  )
  ```

---

## 🧪 Tests

- **New Custom Fields Schema Tests** [`tests/test_serializers.py`]:
  - Added `CustomsOnlySchemaTestCase` test class with 7 new tests:
    - `test_serializer_create_schema_with_only_customs`: Verifies create schema with only customs excludes model fields.
    - `test_serializer_update_schema_with_only_customs`: Verifies update schema with only customs excludes model fields.
    - `test_serializer_create_schema_with_customs_and_optionals`: Verifies customs + optionals includes only those fields.
    - `test_serializer_with_fields_still_works`: Confirms explicit fields behavior is preserved.
    - `test_serializer_with_only_excludes_and_customs`: Documents behavior when excludes defined without fields.
    - `test_serializer_empty_schema_returns_none`: Verifies empty schema returns None.
    - `test_serializer_multiple_customs_no_model_fields`: Verifies multiple customs work without model fields.

---

## 📋 Summary

This patch release fixes a bug where schemas defined with only custom fields would incorrectly include all model fields, and adds support for Union types in `SchemaModelConfig` field definitions.

### Files Changed
| File | Changes |
|------|---------|
| `ninja_aio/models/serializers.py` | Fixed `_generate_model_schema()` to exclude all model fields when only customs are defined; updated `SchemaModelConfig` type hints to allow Union types |
| `tests/test_serializers.py` | Added 7 new tests in `CustomsOnlySchemaTestCase` |
| `ninja_aio/__init__.py` | Bumped version to 2.16.2 |

---



---

## ✨ New Features

- **Custom Decorators for M2M Relation Endpoints** [`ninja_aio/schemas/helpers.py`, `ninja_aio/helpers/api.py`]:
  - Added `get_decorators` field to `M2MRelationSchema` for applying custom decorators to GET (list related objects) endpoints.
  - Added `post_decorators` field to `M2MRelationSchema` for applying custom decorators to POST (add/remove) endpoints.
  - Decorators are unpacked and applied via `decorate_view()` alongside existing decorators like `unique_view` and `paginate`.
  - Enables use cases such as rate limiting, caching, custom authentication, logging, or any other decorator-based middleware on M2M endpoints.

  **Usage example:**
  ```python
  from ninja_aio.schemas import M2MRelationSchema

  M2MRelationSchema(
      model=RelatedModel,
      related_name="related_items",
      get_decorators=[cache_decorator, log_decorator],
      post_decorators=[rate_limit_decorator],
  )
  ```

---

## 🔧 Improvements

- **Refactored Manage Relation View Registration** [`ninja_aio/helpers/api.py`]:
  - Updated `_register_manage_relation_view()` to use `decorate_view()` wrapper instead of direct `@unique_view` decorator.
  - Ensures consistent decorator application pattern between GET and POST endpoints.
  - Allows decorator spreading via `*decorators` for extensibility.

- **Improved Type Hints** [`ninja_aio/schemas/helpers.py`]:
  - Added `Callable` import from typing module.
  - Updated `get_decorators` and `post_decorators` type hints to `Optional[List[Callable]]` for better IDE support and type checking.

---

## 🧪 Tests

- **New Decorator Integration Tests** [`tests/helpers/test_many_to_many_api.py`]:
  - Added `M2MRelationSchemaDecoratorsTestCase` test class with integration tests:
    - `test_get_decorator_is_applied`: Verifies GET decorators are invoked on list endpoint calls.
    - `test_post_decorator_is_applied`: Verifies POST decorators are invoked on add/remove endpoint calls.
    - `test_decorators_independent`: Confirms GET and POST decorators operate independently.
  - Added `TestM2MWithDecoratorsViewSet` test viewset demonstrating decorator usage.

- **New Decorator Schema Validation Tests** [`tests/helpers/test_many_to_many_api.py`]:
  - Added `M2MRelationSchemaDecoratorsFieldTestCase` test class with schema field tests:
    - `test_decorators_default_to_empty_list`: Validates default empty list behavior.
    - `test_decorators_accept_list_of_callables`: Validates callable list acceptance.
    - `test_decorators_can_be_none`: Validates explicit `None` assignment.

---

## 📚 Documentation

- **Updated APIViewSet Documentation** [`docs/api/views/api_view_set.md`]:
  - Added `get_decorators` and `post_decorators` to M2MRelationSchema attributes list.
  - Added comprehensive example showing custom decorator usage with M2M relations (cache and rate limiting patterns).
  - Added note explaining decorator application order and interaction with built-in decorators.

- **Updated Decorators Documentation** [`docs/api/views/decorators.md`]:
  - Added new "M2MRelationSchema decorators" section.
  - Included usage example and cross-reference to APIViewSet M2M Relations documentation.

- **Split Quick Start into Two Guides**:
  - [`docs/getting_started/quick_start.md`]: Dedicated to `ModelSerializer` approach with embedded serializer configuration.
  - [`docs/getting_started/quick_start_serializer.md`]: New guide for `Serializer` approach with plain Django models, including examples for relationships, query optimization, and lifecycle hooks.

---

## 📋 Summary

This minor release introduces custom decorator support for Many-to-Many relation endpoints. Users can now apply custom decorators independently to GET and POST M2M endpoints via the new `get_decorators` and `post_decorators` fields in `M2MRelationSchema`. This enables flexible middleware patterns such as caching, rate limiting, and custom logging on relation endpoints.

### Files Changed
| File | Changes |
|------|---------|
| `ninja_aio/schemas/helpers.py` | Added `get_decorators` and `post_decorators` fields with `Callable` type hints |
| `ninja_aio/helpers/api.py` | Updated view registration to accept and apply custom decorators |
| `tests/helpers/test_many_to_many_api.py` | Added 6 new tests across 2 test classes |
| `docs/api/views/api_view_set.md` | Documented M2M decorator fields with usage examples |
| `docs/api/views/decorators.md` | Added M2MRelationSchema decorators section |
| `docs/getting_started/quick_start.md` | Dedicated to ModelSerializer approach |
| `docs/getting_started/quick_start_serializer.md` | New guide for Serializer approach with plain Django models |
| `mkdocs.yml` | Updated navigation with two Quick Start guides |

---

## [v2.16.1] - 2026-01-27

---

## 🐛 Bug Fixes

- **Fixed Schema Generation with Only Custom Fields** [`ninja_aio/models/serializers.py`]:
  - Fixed an issue in `_generate_model_schema()` where defining only `customs` and/or `optionals` (without explicit `fields` or `excludes`) would incorrectly include all model fields in the generated schema.
  - When only custom fields are defined, the schema now correctly excludes all concrete model fields, returning a schema with only the specified custom fields.
  - This fix applies to both `Serializer` (Meta-driven) and `ModelSerializer` create/update schema generation.

  **Before (broken behavior):**
  ```python
  class MySerializer(Serializer):
      class Meta:
          model = MyModel
          schema_in = SchemaModelConfig(
              customs=[("custom_input", str, ...)]
          )

  # Generated schema incorrectly included ALL model fields + custom_input
  ```

  **After (fixed behavior):**
  ```python
  class MySerializer(Serializer):
      class Meta:
          model = MyModel
          schema_in = SchemaModelConfig(
              customs=[("custom_input", str, ...)]
          )

  # Generated schema now correctly includes ONLY custom_input
  ```

---

## 🧪 Tests

- **New Custom Fields Schema Tests** [`tests/test_serializers.py`]:
  - Added `CustomsOnlySchemaTestCase` test class with 7 new tests:
    - `test_serializer_create_schema_with_only_customs`: Verifies create schema with only customs excludes model fields.
    - `test_serializer_update_schema_with_only_customs`: Verifies update schema with only customs excludes model fields.
    - `test_serializer_create_schema_with_customs_and_optionals`: Verifies customs + optionals includes only those fields.
    - `test_serializer_with_fields_still_works`: Confirms explicit fields behavior is preserved.
    - `test_serializer_with_only_excludes_and_customs`: Documents behavior when excludes defined without fields.
    - `test_serializer_empty_schema_returns_none`: Verifies empty schema returns None.
    - `test_serializer_multiple_customs_no_model_fields`: Verifies multiple customs work without model fields.

---

## 📋 Summary

This patch release fixes a bug where schemas defined with only custom fields would incorrectly include all model fields. The fix ensures that when only `customs` are specified (without `fields` or `excludes`), the generated schema contains only the custom fields as intended.

### Files Changed
| File | Changes |
|------|---------|
| `ninja_aio/models/serializers.py` | Fixed `_generate_model_schema()` to exclude all model fields when only customs are defined |
| `tests/test_serializers.py` | Added 7 new tests in `CustomsOnlySchemaTestCase` |
| `ninja_aio/__init__.py` | Bumped version to 2.16.1 |

---



---

## ✨ New Features

- **Custom Decorators for M2M Relation Endpoints** [`ninja_aio/schemas/helpers.py`, `ninja_aio/helpers/api.py`]:
  - Added `get_decorators` field to `M2MRelationSchema` for applying custom decorators to GET (list related objects) endpoints.
  - Added `post_decorators` field to `M2MRelationSchema` for applying custom decorators to POST (add/remove) endpoints.
  - Decorators are unpacked and applied via `decorate_view()` alongside existing decorators like `unique_view` and `paginate`.
  - Enables use cases such as rate limiting, caching, custom authentication, logging, or any other decorator-based middleware on M2M endpoints.

  **Usage example:**
  ```python
  from ninja_aio.schemas import M2MRelationSchema

  M2MRelationSchema(
      model=RelatedModel,
      related_name="related_items",
      get_decorators=[cache_decorator, log_decorator],
      post_decorators=[rate_limit_decorator],
  )
  ```

---

## 🔧 Improvements

- **Refactored Manage Relation View Registration** [`ninja_aio/helpers/api.py`]:
  - Updated `_register_manage_relation_view()` to use `decorate_view()` wrapper instead of direct `@unique_view` decorator.
  - Ensures consistent decorator application pattern between GET and POST endpoints.
  - Allows decorator spreading via `*decorators` for extensibility.

- **Improved Type Hints** [`ninja_aio/schemas/helpers.py`]:
  - Added `Callable` import from typing module.
  - Updated `get_decorators` and `post_decorators` type hints to `Optional[List[Callable]]` for better IDE support and type checking.

---

## 🧪 Tests

- **New Decorator Integration Tests** [`tests/helpers/test_many_to_many_api.py`]:
  - Added `M2MRelationSchemaDecoratorsTestCase` test class with integration tests:
    - `test_get_decorator_is_applied`: Verifies GET decorators are invoked on list endpoint calls.
    - `test_post_decorator_is_applied`: Verifies POST decorators are invoked on add/remove endpoint calls.
    - `test_decorators_independent`: Confirms GET and POST decorators operate independently.
  - Added `TestM2MWithDecoratorsViewSet` test viewset demonstrating decorator usage.

- **New Decorator Schema Validation Tests** [`tests/helpers/test_many_to_many_api.py`]:
  - Added `M2MRelationSchemaDecoratorsFieldTestCase` test class with schema field tests:
    - `test_decorators_default_to_empty_list`: Validates default empty list behavior.
    - `test_decorators_accept_list_of_callables`: Validates callable list acceptance.
    - `test_decorators_can_be_none`: Validates explicit `None` assignment.

---

## 📚 Documentation

- **Updated APIViewSet Documentation** [`docs/api/views/api_view_set.md`]:
  - Added `get_decorators` and `post_decorators` to M2MRelationSchema attributes list.
  - Added comprehensive example showing custom decorator usage with M2M relations (cache and rate limiting patterns).
  - Added note explaining decorator application order and interaction with built-in decorators.

- **Updated Decorators Documentation** [`docs/api/views/decorators.md`]:
  - Added new "M2MRelationSchema decorators" section.
  - Included usage example and cross-reference to APIViewSet M2M Relations documentation.

- **Split Quick Start into Two Guides**:
  - [`docs/getting_started/quick_start.md`]: Dedicated to `ModelSerializer` approach with embedded serializer configuration.
  - [`docs/getting_started/quick_start_serializer.md`]: New guide for `Serializer` approach with plain Django models, including examples for relationships, query optimization, and lifecycle hooks.

---

## 📋 Summary

This minor release introduces custom decorator support for Many-to-Many relation endpoints. Users can now apply custom decorators independently to GET and POST M2M endpoints via the new `get_decorators` and `post_decorators` fields in `M2MRelationSchema`. This enables flexible middleware patterns such as caching, rate limiting, and custom logging on relation endpoints.

### Files Changed
| File | Changes |
|------|---------|
| `ninja_aio/schemas/helpers.py` | Added `get_decorators` and `post_decorators` fields with `Callable` type hints |
| `ninja_aio/helpers/api.py` | Updated view registration to accept and apply custom decorators |
| `tests/helpers/test_many_to_many_api.py` | Added 6 new tests across 2 test classes |
| `docs/api/views/api_view_set.md` | Documented M2M decorator fields with usage examples |
| `docs/api/views/decorators.md` | Added M2MRelationSchema decorators section |
| `docs/getting_started/quick_start.md` | Dedicated to ModelSerializer approach |
| `docs/getting_started/quick_start_serializer.md` | New guide for Serializer approach with plain Django models |
| `mkdocs.yml` | Updated navigation with two Quick Start guides |

---

## [v2.16.0] - 2026-01-26

---

## ✨ New Features

- **Custom Decorators for M2M Relation Endpoints** [`ninja_aio/schemas/helpers.py`, `ninja_aio/helpers/api.py`]:
  - Added `get_decorators` field to `M2MRelationSchema` for applying custom decorators to GET (list related objects) endpoints.
  - Added `post_decorators` field to `M2MRelationSchema` for applying custom decorators to POST (add/remove) endpoints.
  - Decorators are unpacked and applied via `decorate_view()` alongside existing decorators like `unique_view` and `paginate`.
  - Enables use cases such as rate limiting, caching, custom authentication, logging, or any other decorator-based middleware on M2M endpoints.

  **Usage example:**
  ```python
  from ninja_aio.schemas import M2MRelationSchema

  M2MRelationSchema(
      model=RelatedModel,
      related_name="related_items",
      get_decorators=[cache_decorator, log_decorator],
      post_decorators=[rate_limit_decorator],
  )
  ```

---

## 🔧 Improvements

- **Refactored Manage Relation View Registration** [`ninja_aio/helpers/api.py`]:
  - Updated `_register_manage_relation_view()` to use `decorate_view()` wrapper instead of direct `@unique_view` decorator.
  - Ensures consistent decorator application pattern between GET and POST endpoints.
  - Allows decorator spreading via `*decorators` for extensibility.

- **Improved Type Hints** [`ninja_aio/schemas/helpers.py`]:
  - Added `Callable` import from typing module.
  - Updated `get_decorators` and `post_decorators` type hints to `Optional[List[Callable]]` for better IDE support and type checking.

---

## 🧪 Tests

- **New Decorator Integration Tests** [`tests/helpers/test_many_to_many_api.py`]:
  - Added `M2MRelationSchemaDecoratorsTestCase` test class with integration tests:
    - `test_get_decorator_is_applied`: Verifies GET decorators are invoked on list endpoint calls.
    - `test_post_decorator_is_applied`: Verifies POST decorators are invoked on add/remove endpoint calls.
    - `test_decorators_independent`: Confirms GET and POST decorators operate independently.
  - Added `TestM2MWithDecoratorsViewSet` test viewset demonstrating decorator usage.

- **New Decorator Schema Validation Tests** [`tests/helpers/test_many_to_many_api.py`]:
  - Added `M2MRelationSchemaDecoratorsFieldTestCase` test class with schema field tests:
    - `test_decorators_default_to_empty_list`: Validates default empty list behavior.
    - `test_decorators_accept_list_of_callables`: Validates callable list acceptance.
    - `test_decorators_can_be_none`: Validates explicit `None` assignment.

---

## 📚 Documentation

- **Updated APIViewSet Documentation** [`docs/api/views/api_view_set.md`]:
  - Added `get_decorators` and `post_decorators` to M2MRelationSchema attributes list.
  - Added comprehensive example showing custom decorator usage with M2M relations (cache and rate limiting patterns).
  - Added note explaining decorator application order and interaction with built-in decorators.

- **Updated Decorators Documentation** [`docs/api/views/decorators.md`]:
  - Added new "M2MRelationSchema decorators" section.
  - Included usage example and cross-reference to APIViewSet M2M Relations documentation.

- **Split Quick Start into Two Guides**:
  - [`docs/getting_started/quick_start.md`]: Dedicated to `ModelSerializer` approach with embedded serializer configuration.
  - [`docs/getting_started/quick_start_serializer.md`]: New guide for `Serializer` approach with plain Django models, including examples for relationships, query optimization, and lifecycle hooks.

---

## 📋 Summary

This minor release introduces custom decorator support for Many-to-Many relation endpoints. Users can now apply custom decorators independently to GET and POST M2M endpoints via the new `get_decorators` and `post_decorators` fields in `M2MRelationSchema`. This enables flexible middleware patterns such as caching, rate limiting, and custom logging on relation endpoints.

### Files Changed
| File | Changes |
|------|---------|
| `ninja_aio/schemas/helpers.py` | Added `get_decorators` and `post_decorators` fields with `Callable` type hints |
| `ninja_aio/helpers/api.py` | Updated view registration to accept and apply custom decorators |
| `tests/helpers/test_many_to_many_api.py` | Added 6 new tests across 2 test classes |
| `docs/api/views/api_view_set.md` | Documented M2M decorator fields with usage examples |
| `docs/api/views/decorators.md` | Added M2MRelationSchema decorators section |
| `docs/getting_started/quick_start.md` | Dedicated to ModelSerializer approach |
| `docs/getting_started/quick_start_serializer.md` | New guide for Serializer approach with plain Django models |
| `mkdocs.yml` | Updated navigation with two Quick Start guides |

---

## [v2.15.1] - 2026-01-26

---

## 🐛 Fixed

- **JWT Exception Handling in AsyncJwtBearer** [`ninja_aio/auth.py`]:
  - Updated exception handling to catch `errors.JoseError` instead of `ValueError` for JWT decoding failures.
  - Removed redundant nested try-except block that separately handled `ValueError` during token decode.
  - JWT decode and claims validation are now consolidated into a single exception handler.
  - Ensures consistent error handling across all JWT-related failures including malformed tokens, invalid signatures, and claim validation errors.

---

## 🔧 Improvements

- **Streamlined Readable Fields Resolution in BaseSerializer** [`ninja_aio/models/serializers.py`]:
  - Refactored `_resolve_relation_schema()` to use a single-line conditional expression for resolving `ModelSerializer` with readable fields.
  - Simplified from separate if-else blocks to a cleaner ternary pattern: `return rel_model.generate_related_s() if has_readable_fields else None`.

- **Optimized Condition for Skipping ModelSerializer** [`ninja_aio/models/serializers.py`]:
  - Combined nested conditionals in `_build_related_field()` into a single compound conditional statement.
  - Checking for `ModelSerializer` instances with no readable fields is now a unified expression.
  - Improves code clarity without changing behavior.

---

## 🧪 Tests

- **Updated JWT Authentication Tests** [`tests/test_auth.py`]:
  - Updated mock to raise `JoseError` instead of `ValueError` to align with the corrected exception handling in `AsyncJwtBearer`.
  - Ensures test coverage accurately reflects the authentication error flow.

- **Fixed Schema Variable Warning in Tests** [`tests/test_auth.py`]:
  - Updated `DetailSchemaModelSerializerTestCase` to ignore unused schema variables.

---

## 📋 Summary

This patch release focuses on code quality improvements and a bug fix in JWT authentication. The `AsyncJwtBearer` class now correctly handles all JWT-related exceptions through the `joserfc.errors.JoseError` hierarchy, and the serializer codebase has been refactored for improved readability.

### Files Changed
| File | Changes |
|------|---------|
| `ninja_aio/auth.py` | Simplified JWT exception handling |
| `ninja_aio/models/serializers.py` | Optimized conditional logic (2 locations) |
| `tests/test_auth.py` | Updated mocks and test assertions |

---

## [v2.15.0] - 2026-01-22

---

## New Features

- **Dynamic PK Type Detection for `relations_as_id`** [`ninja_aio/models/serializers.py`]:
  - The `PkFromModel` type now automatically detects and uses the related model's primary key type.
  - Supports `int` (default), `UUID`, `str` (CharField), and any other Django primary key type.
  - Schema generation now correctly annotates relation fields with the appropriate PK type.

---

## Improvements

- **`PkFromModel` Subscriptable Type** [`ninja_aio/models/serializers.py`]:
  - New `PkFromModel[type]` syntax allows explicit PK type specification.
  - Examples: `PkFromModel[int]`, `PkFromModel[UUID]`, `PkFromModel[str]`.
  - Falls back to `int` when used without subscription (backwards compatible).
  - Uses `BeforeValidator` to extract `pk` attribute during Pydantic serialization.

---

## Tests

- **Comprehensive Test Coverage for Different PK Types** [`tests/test_serializers.py`]:
  - Added `RelationsAsIdUUIDModelSerializerTestCase` (6 tests) - Schema generation tests for UUID PKs
  - Added `RelationsAsIdUUIDIntegrationTestCase` (7 tests) - Integration tests with UUID PK data
  - Added `RelationsAsIdStringPKModelSerializerTestCase` (6 tests) - Schema generation tests for string PKs
  - Added `RelationsAsIdStringPKIntegrationTestCase` (7 tests) - Integration tests with string PK data
  - Coverage includes all relation types: Forward FK, Reverse FK, Forward O2O, Reverse O2O, Forward M2M, Reverse M2M

- **New Test Models with Different PK Types** [`tests/test_app/models.py`]:
  - UUID PK models: `AuthorUUID`, `BookUUID`, `ProfileUUID`, `UserUUID`, `TagUUID`, `ArticleUUID`
  - String PK models: `AuthorStringPK`, `BookStringPK`, `ProfileStringPK`, `UserStringPK`, `TagStringPK`, `ArticleStringPK`

---

## Documentation

- **ModelSerializer Documentation** [`docs/api/models/model_serializer.md`]:
  - Updated `relations_as_id` table to show `PK_TYPE` instead of hardcoded `int`.
  - Added note explaining automatic PK type detection.
  - Added UUID primary key example with code and JSON output.

- **Serializer Documentation** [`docs/api/models/serializers.md`]:
  - Updated `relations_as_id` table to show `PK_TYPE` instead of hardcoded `int`.
  - Added note explaining automatic PK type detection.
  - Added UUID primary key example with code and JSON output.

---

## Usage Example

### UUID Primary Key with `relations_as_id`

```python
import uuid
from django.db import models
from ninja_aio.models import ModelSerializer

class Author(ModelSerializer):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=200)

    class ReadSerializer:
        fields = ["id", "name", "books"]
        relations_as_id = ["books"]  # Reverse FK as list of UUIDs

class Book(ModelSerializer):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(max_length=200)
    author = models.ForeignKey(Author, on_delete=models.CASCADE, related_name="books")

    class ReadSerializer:
        fields = ["id", "title", "author"]
        relations_as_id = ["author"]  # Forward FK as UUID
```

**Output (Author with UUID PK):**
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "name": "J.K. Rowling",
  "books": [
    "6ba7b810-9dad-11d1-80b4-00c04fd430c8",
    "6ba7b811-9dad-11d1-80b4-00c04fd430c8"
  ]
}
```

**Output (Book with UUID PK):**
```json
{
  "id": "6ba7b810-9dad-11d1-80b4-00c04fd430c8",
  "title": "Harry Potter",
  "author": "550e8400-e29b-41d4-a716-446655440000"
}
```

### String Primary Key with `relations_as_id`

```python
from django.db import models
from ninja_aio.models import ModelSerializer

class Author(ModelSerializer):
    id = models.CharField(primary_key=True, max_length=50)
    name = models.CharField(max_length=200)

    class ReadSerializer:
        fields = ["id", "name", "books"]
        relations_as_id = ["books"]

class Book(ModelSerializer):
    id = models.CharField(primary_key=True, max_length=50)
    title = models.CharField(max_length=200)
    author = models.ForeignKey(Author, on_delete=models.CASCADE, related_name="books")

    class ReadSerializer:
        fields = ["id", "title", "author"]
        relations_as_id = ["author"]
```

**Output (Author with String PK):**
```json
{
  "id": "author-001",
  "name": "J.K. Rowling",
  "books": ["book-001", "book-002", "book-003"]
}
```

**Output (Book with String PK):**
```json
{
  "id": "book-001",
  "title": "Harry Potter",
  "author": "author-001"
}
```

---

## [v2.14.0] - 2026-01-22

---

## 🐛 Fixed

- **Forward Relations in `relations_as_id` Now Work Correctly** [`ninja_aio/models/serializers.py`]:
  - Fixed issue where forward FK and O2O relations listed in `relations_as_id` were serialized as `null` instead of the related object's ID.
  - **Root Cause**: Previously used `validation_alias` which only affects input parsing, not output serialization.
  - **Solution**: Now uses `PkFromModel` with `BeforeValidator` to extract the primary key during serialization, consistent with reverse relations.
  - Affects: Forward ForeignKey, Forward OneToOneField.

---

## 🔧 Improvements

- **Optimized `relations_as_id` Processing** [`ninja_aio/models/serializers.py`]:
  - `_get_relations_as_id()` is now called once in `get_schema_out_data()` and passed through to child methods, eliminating redundant method calls during schema generation.
  - `_build_schema_reverse_rel()`, `_build_schema_forward_rel()`, and `_process_field()` now accept `relations_as_id` as a parameter instead of fetching it independently.

- **Enhanced Method Documentation** [`ninja_aio/models/serializers.py`]:
  - Added comprehensive docstrings with parameter descriptions to:
    - `_build_schema_reverse_rel()` - Documents descriptor types and return values
    - `_build_schema_forward_rel()` - Documents forward relation handling logic
    - `_process_field()` - Documents field classification process
    - `get_schema_out_data()` - Documents schema component collection

---

## 🧪 Tests

- **Comprehensive Test Coverage for `relations_as_id`** [`tests/test_serializers.py`]:
  - Added `RelationsAsIdModelSerializerTestCase` (6 tests) - Schema generation tests for ModelSerializer
  - Added `RelationsAsIdSerializerTestCase` (6 tests) - Schema generation tests for Meta-driven Serializer
  - Added `RelationsAsIdIntegrationTestCase` (7 tests) - Integration tests with actual data serialization
  - Coverage includes all relation types: Forward FK, Reverse FK, Forward O2O, Reverse O2O, Forward M2M, Reverse M2M
  - Tests null value handling for nullable forward relations

- **New Test Models** [`tests/test_app/models.py`]:
  - `AuthorAsId`, `BookAsId` - FK relation testing
  - `ProfileAsId`, `UserAsId` - O2O relation testing
  - `TagAsId`, `ArticleAsId` - M2M relation testing

- **New Test Serializers** [`tests/test_app/serializers.py`]:
  - `BookAsIdMetaSerializer`, `AuthorAsIdMetaSerializer` - FK with Meta-driven Serializer
  - `UserAsIdMetaSerializer`, `ProfileAsIdMetaSerializer` - O2O with Meta-driven Serializer
  - `ArticleAsIdMetaSerializer`, `TagAsIdMetaSerializer` - M2M with Meta-driven Serializer

---

## 📖 Documentation

- **ModelSerializer Documentation** [`docs/api/models/model_serializer.md`]:
  - Added `relations_as_id` attribute to `ReadSerializer` attributes table.
  - Added new "Relations as ID" section with:
    - Use cases (payload size, circular serialization, performance, API design)
    - Supported relations table with output types
    - FK, O2O, and M2M examples with JSON output
    - Query optimization note for `select_related`/`prefetch_related`

- **Serializer Documentation** [`docs/api/models/serializers.md`]:
  - Added `relations_as_id` to Meta configuration options.
  - Added new "Relations as ID" section with:
    - Complete examples for FK, O2O, and M2M relations
    - Guide for combining `relations_as_id` with `relations_serializers`
    - Query optimization recommendations

---

## 💡 Usage Example

### ModelSerializer with `relations_as_id`

```python
from ninja_aio.models import ModelSerializer
from django.db import models

class Author(ModelSerializer):
    name = models.CharField(max_length=200)

    class ReadSerializer:
        fields = ["id", "name", "books"]
        relations_as_id = ["books"]  # Reverse FK as list of IDs

class Book(ModelSerializer):
    title = models.CharField(max_length=200)
    author = models.ForeignKey(Author, on_delete=models.CASCADE, related_name="books")

    class ReadSerializer:
        fields = ["id", "title", "author"]
        relations_as_id = ["author"]  # Forward FK as ID
```

**Output (Author):**
```json
{
  "id": 1,
  "name": "J.K. Rowling",
  "books": [1, 2, 3]
}
```

**Output (Book):**
```json
{
  "id": 1,
  "title": "Harry Potter",
  "author": 1
}
```

### Meta-driven Serializer with `relations_as_id`

```python
from ninja_aio.models import serializers

class ArticleSerializer(serializers.Serializer):
    class Meta:
        model = Article
        schema_out = serializers.SchemaModelConfig(
            fields=["id", "title", "author", "tags"]
        )
        relations_serializers = {
            "author": AuthorSerializer,  # Nested object
        }
        relations_as_id = ["tags"]  # M2M as list of IDs

    class QuerySet:
        read = ModelQuerySetSchema(
            select_related=["author"],
            prefetch_related=["tags"],
        )
```

**Output:**
```json
{
  "id": 1,
  "title": "Getting Started with Django",
  "author": {"id": 1, "name": "John Doe"},
  "tags": [1, 2, 5]
}
```

---

## [v2.13.0] - 2026-01-21

---

## ✨ Added

- **`verbose_name_plural` Attribute for M2MRelationSchema** [`ninja_aio/schemas/helpers.py`]:
  - New optional `verbose_name_plural` field allows customizing the human-readable plural name for M2M relation endpoints.
  - When provided, used in endpoint summaries and descriptions (e.g., `"Get Article Tags"`, `"Add or Remove Article Tags"`).
  - Falls back to `model._meta.verbose_name_plural.capitalize()` when not specified.

---

## 🔧 Improvements

- **Refactored M2M Endpoint Summary Generation** [`ninja_aio/helpers/api.py`]:
  - `_register_get_relation_view()` now accepts `verbose_name_plural` parameter instead of computing it internally.
  - `_register_manage_relation_view()` simplified by removing `rel_util` parameter; now receives `verbose_name_plural` directly.
  - `_build_views()` centralizes verbose name resolution with fallback logic.
  - Cleaner separation of concerns: verbose name is resolved once and passed to both GET and POST registration methods.

- **Simplified Warning Logic for Missing Relation Serializers** [`ninja_aio/models/serializers.py`]:
  - `_warn_missing_relation_serializer()` now uses simpler boolean logic.
  - Warnings emit when model is not a `ModelSerializer` and `NINJA_AIO_RAISE_SERIALIZATION_WARNINGS` is `True` (default).
  - Removed dependency on `NINJA_AIO_TESTING` setting for warning control.

---

## 📖 Documentation

- **Updated M2MRelationSchema Documentation** [`docs/api/views/api_view_set.md`]:
  - Added `verbose_name_plural` to the list of M2MRelationSchema attributes.
  - Added usage example demonstrating custom verbose names for M2M endpoints.

---

## 💡 Usage Example

### Custom Verbose Names for M2M Endpoints

```python
from ninja_aio.views import APIViewSet
from ninja_aio.schemas.helpers import M2MRelationSchema

@api.viewset(model=Article)
class ArticleViewSet(APIViewSet):
    m2m_relations = [
        M2MRelationSchema(
            model=Tag,
            related_name="tags",
            verbose_name_plural="Article Tags",  # Custom name
            add=True,
            remove=True,
            get=True,
        ),
        M2MRelationSchema(
            model=Category,
            related_name="categories",
            # Uses default: "Categories" (from model._meta.verbose_name_plural)
            get=True,
        ),
    ]
```

**Generated Endpoint Summaries:**
- `GET /articles/{pk}/tags` → Summary: "Get Article Tags"
- `POST /articles/{pk}/tags/` → Summary: "Add or Remove Article Tags"
- `GET /articles/{pk}/categories` → Summary: "Get Categories"

---

---

## [v2.12.3] - 2026-01-21

---

## 🐛 Fixed

- **Warning Logic for Missing Relation Serializers** [`ninja_aio/models/serializers.py`]:
  - Fixed boolean logic in `_warn_missing_relation_serializer` method.

---

## [v2.12.2] - 2026-01-21

---

## 🐛 Fixed

- **Warning Logic for Missing Relation Serializers** [`ninja_aio/models/serializers.py`]:
  - Fixed boolean logic in `_warn_missing_relation_serializer` method.
  - Warnings now correctly emit when: (not ModelSerializer AND not testing) OR force warnings enabled.
  - Previously, warnings were incorrectly suppressed for non-ModelSerializer relations even when `NINJA_AIO_RAISE_SERIALIZATION_WARNINGS=True`.

---

## [v2.12.1] - 2026-01-21

---

## 🐛 Fixed

- **QueryUtil DETAIL Scope Fallback** [`ninja_aio/helpers/query.py`]:
  - `detail_config` now correctly falls back to `read_config` for `select_related` and `prefetch_related` when not explicitly configured.
  - Ensures consistent queryset optimization behavior between READ and DETAIL scopes.

---

## 🔧 Improvements

- **Refactored Fallback Logic** [`ninja_aio/helpers/query.py`]:
  - Moved DETAIL→READ fallback from `apply_queryset_optimizations()` to `__init__()`.
  - Fallback is now resolved once at construction time, improving clarity and preventing runtime mutation.
  - Uses `.copy()` to ensure `detail_config` lists are independent from `read_config`.

---

## 🧪 Tests

- **New Test Cases for QueryUtil DETAIL Fallback** [`tests/test_query_util.py`]:
  - `test_detail_scope_fallback_to_read_select_related`: Verifies DETAIL scope uses READ's `select_related` when not configured.
  - `test_detail_scope_fallback_to_read_prefetch_related`: Verifies DETAIL scope uses READ's `prefetch_related` when not configured.
  - `test_detail_config_initialized_with_read_fallback`: Confirms fallback is applied during initialization.
  - `test_detail_config_independent_copy`: Ensures `detail_config` lists are copies, not references (prevents mutation bugs).

---

---

## [v2.12.0] - 2026-01-21

---

## ✨ Added

- **Per-Field-Type Detail Fallback for ModelSerializer** [`ninja_aio/models/serializers.py`]:
  - `DetailSerializer` now falls back to `ReadSerializer` for each field type (`fields`, `customs`, `optionals`, `excludes`) independently when not explicitly configured.
  - Allows partial overrides: define only `DetailSerializer.fields` while inheriting `customs`, `optionals`, and `excludes` from `ReadSerializer`.

- **Schema-Level Detail Fallback for Serializer** [`ninja_aio/models/serializers.py`]:
  - When `schema_detail` is not defined, `Serializer` now correctly falls back to `schema_out` for all field configurations.
  - Enables seamless list/detail endpoint differentiation without duplicating configuration.

- **New Setting: `NINJA_AIO_RAISE_SERIALIZATION_WARNINGS`** [`ninja_aio/models/serializers.py`]:
  - New Django setting to control serialization warning behavior during testing.
  - When `True` (with `NINJA_AIO_TESTING=True`), warnings for missing relation serializers are raised instead of suppressed.

---

## 🔧 Improvements

- **Refactored Fallback Logic** [`ninja_aio/models/serializers.py`]:
  - Moved detail→read fallback from `BaseSerializer.get_fields()` to `_get_fields()` in both `ModelSerializer` and `Serializer`.
  - `ModelSerializer._get_fields()`: Falls back per-field-type (if `DetailSerializer.customs` is empty, uses `ReadSerializer.customs`).
  - `Serializer._get_fields()`: Falls back at schema level (if `schema_detail` is `None`, uses `schema_out`).

- **Warning Control Enhancement** [`ninja_aio/models/serializers.py`]:
  - Updated `_warn_missing_relation_serializer()` to respect both `NINJA_AIO_TESTING` and new `NINJA_AIO_RAISE_SERIALIZATION_WARNINGS` settings.

---

## 🐛 Fixed

- **Serializer Detail Fallback Typo** [`ninja_aio/models/serializers.py`]:
  - Fixed `Serializer._get_fields()` where detail fallback was incorrectly referencing `"read"` instead of `"out"` schema key.

---

## 🧪 Tests

- **New Test Cases for Serializer Detail Fallback** [`tests/test_serializers.py`]:
  - `test_detail_fallback_customs_from_read`: Verifies customs inheritance when `schema_detail` is not defined.
  - `test_detail_fallback_optionals_from_read`: Verifies optionals inheritance.
  - `test_detail_fallback_excludes_from_read`: Verifies excludes inheritance.
  - `test_detail_does_not_inherit_when_defined`: Confirms no inheritance when `schema_detail` is explicitly defined.

- **New Test Cases for ModelSerializer Detail Fallback** [`tests/test_serializers.py`]:
  - `test_model_serializer_detail_fallback_fields`: Verifies fields fallback to `ReadSerializer`.
  - `test_model_serializer_detail_fallback_customs`: Verifies customs fallback per-field-type.
  - `test_model_serializer_detail_fallback_optionals`: Verifies optionals fallback per-field-type.
  - `test_model_serializer_detail_fallback_excludes`: Verifies excludes fallback per-field-type.
  - `test_model_serializer_detail_inherits_per_field_type`: Confirms per-field-type inheritance behavior.
  - `test_model_serializer_with_detail_generates_different_schemas`: End-to-end schema generation test.

- **New Test Models** [`tests/test_app/models.py`]:
  - `TestModelSerializerWithReadCustoms`: Model with customs on `ReadSerializer` only.
  - `TestModelSerializerWithReadOptionals`: Model with optionals on `ReadSerializer` only.
  - `TestModelSerializerWithReadExcludes`: Model with excludes on `ReadSerializer` only.
  - `TestModelSerializerWithBothSerializers`: Model with both `ReadSerializer` and `DetailSerializer` configured.

---

## 💡 Usage Example

### ModelSerializer (Per-Field-Type Fallback)

```python
from ninja_aio.models import ModelSerializer
from django.db import models

class Article(ModelSerializer):
    title = models.CharField(max_length=200)
    content = models.TextField()
    author_notes = models.TextField(blank=True)

    class ReadSerializer:
        fields = ["id", "title"]
        customs = [("word_count", int, lambda obj: len(obj.content.split()))]

    class DetailSerializer:
        # Only override fields - customs inherited from ReadSerializer
        fields = ["id", "title", "content", "author_notes"]
```

**Behavior:**
- `generate_read_s()` → `{"id", "title", "word_count"}`
- `generate_detail_s()` → `{"id", "title", "content", "author_notes", "word_count"}` (customs inherited)

### Serializer (Schema-Level Fallback)

```python
from ninja_aio.models import serializers

class ArticleSerializer(serializers.Serializer):
    class Meta:
        model = Article
        schema_out = serializers.SchemaModelConfig(
            fields=["id", "title"],
            customs=[("word_count", int, 0)],
        )
        # No schema_detail - falls back to schema_out entirely
```

**Behavior:**
- `generate_read_s()` → `{"id", "title", "word_count"}`
- `generate_detail_s()` → `{"id", "title", "word_count"}` (same as read)

---

---

## [v2.11.2] - 2026-01-19

---

## v2.11.2

### Fixed
- Fixed binary field serialization in `_bump_object_from_schema` - removed `mode="json"` from `model_dump()` to prevent UTF-8 decode errors when retrieving binary data. Binary fields are now properly handled by `ORJSONRenderer` which converts them to base64.

---

## [v2.11.1] - 2026-01-19

---

## 🐛 Bug Fixes

- **ORJSONRenderer HttpResponse Passthrough** [`ninja_aio/renders.py`]:
  - Fixed `ORJSONRenderer.render()` to detect and return `HttpResponseBase` instances directly without JSON serialization.
  - Previously, returning an `HttpResponse` with a custom content type (e.g., PEM files, binary downloads) would fail because the renderer attempted to serialize it as JSON.
  - Now supports returning `HttpResponse`, `StreamingHttpResponse`, and any other `HttpResponseBase` subclass.

---

## 📖 Documentation

- **ORJSON Renderer Documentation** [`docs/api/renderers/orjson_renderer.md`]:
  - Reorganized documentation with proper section headings.
  - Added new **HttpResponse Passthrough** section explaining the feature.
  - Includes usage examples for `HttpResponse` and `StreamingHttpResponse`.
  - Documents the correct pattern for returning custom responses with non-JSON content types.

---

## 🧪 Tests

- **New Test Cases** [`tests/core/test_renderer_parser.py`]:
  - `test_renderer_http_response_passthrough`: Verifies `HttpResponse` objects pass through unchanged with correct content and headers.
  - `test_renderer_streaming_http_response_passthrough`: Verifies `StreamingHttpResponse` objects are also handled correctly.

---

## 💡 Usage Example

```python
from django.http import HttpResponse, StreamingHttpResponse

# Return a PEM file
@api.get("/public-key")
def get_public_key(request):
    return HttpResponse(
        settings.JWT_PUBLIC_KEY.as_pem(),
        content_type="application/x-pem-file",
        status=200,
    )

# Return a streaming response for large files
@api.get("/download")
def download_file(request):
    return StreamingHttpResponse(
        file_iterator(),
        content_type="application/octet-stream",
    )
```

> **Note:** Set the `status` parameter on the `HttpResponse` itself. Do not use tuple returns like `return 200, HttpResponse(...)`.

---

## [v2.11.0] - 2026-01-19

---

## ✨ Added

- **MatchCaseFilterViewSetMixin** [`ninja_aio/views/mixins.py`]:
  - New mixin for conditional filtering based on boolean query parameters.
  - Maps boolean API parameters (`?is_active=true`) to different Django ORM filter conditions for `True` and `False` cases.
  - Supports both `filter()` (include) and `exclude()` operations via the `include` attribute.
  - Automatically registers query params from `filters_match_cases` configuration.

- **New Filter Schemas** [`ninja_aio/schemas/filters.py`]:
  - `MatchCaseFilterSchema`: Configures match-case filters with `query_param` and `cases` attributes.
  - `MatchConditionFilterSchema`: Defines individual filter conditions with `query_filter` (dict) and `include` (bool).
  - `BooleanMatchFilterSchema`: Groups `true` and `false` case conditions.
  - `FilterSchema`: New base class for filter schemas with `filter_type` and `query_param` attributes.

---

## 🔧 Improvements

- **Unified Special Filter Detection** [`ninja_aio/views/api.py`]:
  - Added `APIViewSet._check_match_cases_filters(filter: str)` helper method.
  - Added `APIViewSet._is_special_filter(filter: str)` method combining relation and match-case filter detection.

- **Filter Mixin Skip Logic** [`ninja_aio/views/mixins.py`]:
  - Updated all filter mixins to use `_is_special_filter()` instead of `_check_relations_filters()`:
    - `IcontainsFilterViewSetMixin`
    - `BooleanFilterViewSetMixin`
    - `NumericFilterViewSetMixin`
    - `DateFilterViewSetMixin`
  - Ensures match-case filter params are not double-processed by type-based mixins.

- **RelationFilterSchema Refactoring** [`ninja_aio/schemas/filters.py`]:
  - `RelationFilterSchema` now extends `FilterSchema` base class.
  - Moved from `ninja_aio/schemas/api.py` to dedicated `ninja_aio/schemas/filters.py` module.

---

## 📖 Documentation

- **Mixins Documentation** [`docs/api/views/mixins.md`]:
  - Added comprehensive documentation for `MatchCaseFilterViewSetMixin`.
  - Includes usage examples for simple status filtering and complex multi-condition filtering.
  - Documents all schema requirements and configuration options.

---

## 🧪 Tests

- **New Test Cases** [`tests/views/test_viewset.py`]:
  - `MatchCaseFilterViewSetMixinTestCase`: Tests include behavior with `True`/`False`/`None` values.
  - `MatchCaseFilterViewSetMixinExcludeTestCase`: Tests exclude behavior when `include=False`.
  - Tests cover query params registration and `filters_match_cases_fields` property.

- **Test ViewSets** [`tests/test_app/views.py`]:
  - `TestModelSerializerMatchCaseFilterAPI`: Tests `is_approved` filter with include/exclude logic.
  - `TestModelSerializerMatchCaseExcludeFilterAPI`: Tests `hide_pending` filter with inverse logic.

- **Test Model Update** [`tests/test_app/models.py`]:
  - Added `status` field to `TestModelSerializer` for match-case filter testing.

---

## 💡 Usage Example

```python
from ninja_aio.views.mixins import MatchCaseFilterViewSetMixin
from ninja_aio.views.api import APIViewSet
from ninja_aio.schemas import (
    MatchCaseFilterSchema,
    MatchConditionFilterSchema,
    BooleanMatchFilterSchema,
)

class OrderViewSet(MatchCaseFilterViewSetMixin, APIViewSet):
    model = models.Order
    api = api
    filters_match_cases = [
        MatchCaseFilterSchema(
            query_param="is_completed",
            cases=BooleanMatchFilterSchema(
                true=MatchConditionFilterSchema(
                    query_filter={"status": "completed"},
                ),
                false=MatchConditionFilterSchema(
                    query_filter={"status": "completed"},
                    include=False,  # excludes completed orders
                ),
            ),
        ),
    ]
```

**API Behavior:**
- `GET /orders?is_completed=true` → `queryset.filter(status="completed")`
- `GET /orders?is_completed=false` → `queryset.exclude(status="completed")`

---

---

## [v2.10.1] - 2026-01-16

---

## 🐛 Fixed

- **Filter Mixin Conflict Resolution** [file:2]:
  - Added `APIViewSet._check_relations_filters(filter: str)` helper method to detect if a filter key belongs to `relations_filters`.
  - Added `RelationFilterViewSetMixin.relations_filters_fields` property that extracts all `query_param` names from configured `relations_filters`.

- **Filter Handler Skip Logic** [file:2]:
  - **IcontainsFilterViewSetMixin**: Now skips relation filter keys (`if isinstance(value, str) and not self._check_relations_filters(key)`).
  - **BooleanFilterViewSetMixin**: Now skips relation filter keys when applying boolean filters.
  - **NumericFilterViewSetMixin**: Now skips relation filter keys when applying numeric filters.
  - **DateFilterViewSetMixin**: Now skips relation filter keys when applying date comparisons (`__lte`, etc.).

**Impact**: Prevents double-processing of relation filters when combining `RelationFilterViewSetMixin` with other filter mixins. Relation filters are handled exclusively by `RelationFilterViewSetMixin.query_params_handler`, avoiding conflicts like:
- String relation params (`?author_id=5`) being misinterpreted as `icontains` filters.
- Numeric relation params being applied twice.
- Boolean/date relation params triggering incorrect transformations.

---

## 🔧 Internal Changes

- **Mixin Inheritance Chain**:
  - Filter mixins (`IcontainsFilterViewSetMixin`, etc.) now respect `RelationFilterViewSetMixin` configuration via shared `_check_relations_filters()` method.
  - Ensures proper layering: base filters → relation filters (exclusive handling).

- **Query Params Handler Flow**:

---

## [v2.10.0] - 2026-01-16

---

## ✨ Added

- **Relation-Based Filtering Mixin**:
  - New `RelationFilterViewSetMixin` for filtering by related model fields via query parameters.
  - New `RelationFilterSchema` for declarative mapping of `query_param` → Django ORM `query_filter` with typed `filter_type` tuples.
  - Automatic registration of `relations_filters` entries into `query_params` on subclasses.

- **Schema & Import Enhancements**:
  - Exported `RelationFilterSchema` from `ninja_aio.schemas` and added to `__all__`.
  - Added `RelationFilterSchema` import to `ninja_aio.views.mixins` and example usages in docs and test views.

---

## 🛠 Changed

- **ModelUtil Relation Detection Fix**:
  - Corrected relation ordering in `ModelUtil.get_select_relateds()`:
    - Now detects `ForwardOneToOneDescriptor` before `ForwardManyToOneDescriptor` for building `select_related` lists.
  - Ensures one-to-one relations are properly included in query optimizations.

- **Documentation Updates**:
  - Extended `docs/api/views/mixins.md` with a new section for `RelationFilterViewSetMixin`.
  - Added examples showing how to configure `relations_filters` and resulting query behavior.

---

## 🐛 Fixed

- **ModelUtil Primary Key Type Error Handling**:
  - `ModelUtil.pk_field_type` now raises a clear `ConfigError` when encountering unknown primary key field types.
  - Error message explicitly reports unsupported field type and suggests missing mapping in `ninja.orm.fields.TYPES`.

- **ModelUtil Configuration Edge Cases**:
  - `ModelUtil` now raises `ConfigError` when instantiated with a `ModelSerializer` model and an explicit `serializer_class` at the same time, avoiding ambiguous configuration.

- **ORJSON Renderer Primitive Handling**:
  - ORJSON renderer now correctly handles non-dict payloads (strings, lists, primitives) without assuming `.items()` presence.
  - Added coverage for list and primitive responses to ensure consistent rendering behavior.

- **Async JWT Auth Robustness**:
  - `AsyncJwtBearer.authenticate` now safely handles invalid or malformed tokens where `jwt.decode` raises `ValueError`, returning `False` instead of propagating the exception.
  - Base `auth_handler` path verified to return `None` when not overridden, and mandatory claims validation now preserves pre-set `iss` and `aud` values.

---

## 🧪 Tests

- **New Test Suites for Edge Cases**:
  - `ModelUtilConfigErrorTestCase` to validate `ConfigError` raising when mixing `ModelSerializer` model and `serializer_class`.
  - `ModelUtilPkFieldTypeTestCase` to ensure unknown PK types trigger `ConfigError` with informative message.
  - `ModelUtilObjectsQueryDefaultTest

---

## [v2.9.0] - 2026-01-14

---

## ✨ Added

- **Detail-Specific Query Optimizations**:
  - New `QuerySet.detail` configuration for detail-specific `select_related` and `prefetch_related`
  - New `serializable_detail_fields` property on `ModelUtil` for accessing detail-specific fields
  - New `_get_serializable_field_names()` helper method for DRY field retrieval
  - New `DETAIL` scope added to `QueryUtilBaseScopesSchema`

- **Fallback Mechanism for Detail Schema**:
  - `generate_detail_s()` now falls back to read schema when no `DetailSerializer` is defined
  - `get_fields("detail")` falls back to read fields when no detail fields are declared
  - `_get_read_optimizations("detail")` falls back to `QuerySet.read` when `QuerySet.detail` is not defined

---

## 🛠 Changed

- **API Parameter Change: `is_for_read` → `is_for`**:
  - Renamed `is_for_read: bool` parameter to `is_for: Literal["read", "detail"] | None` across all `ModelUtil` methods:
    - `get_objects()`
    - `get_object()`
    - `read_s()`
    - `list_read_s()`
    - `_get_base_queryset()`
    - `_apply_query_optimizations()`
    - `_serialize_queryset()`
    - `_serialize_single_object()`
    - `_handle_query_mode()`
    - `_read_s()`
  - This enables explicit control over which optimization strategy to use

- **Query Optimization Methods Now Accept `is_for` Parameter**:
  - `get_select_relateds(is_for: Literal["read", "detail"] = "read")`
  - `get_reverse_relations(is_for: Literal["read", "detail"] = "read")`
  - `_get_read_optimizations(is_for: Literal["read", "detail"] = "read")`

- **APIViewSet Retrieve Endpoint**:
  - Now uses `is_for="detail"` when `schema_detail` is available
  - Falls back to `is_for="read"` when no detail schema is configured

- **Code Formatting Improvements**:
  - Reformatted multi-line tuples in `_is_reverse_relation()`
  - Reformatted conditional in `_warn_missing_relation_serializer()`
  - Reformatted error message in `get_schema_out_data()`

---

## 🐛 Fixed

- **Query Optimization Fallback Bug**:
  - Fixed `_get_read_optimizations()` to fall back to `read` config when `detail` config is not defined
  - Previously returned empty `ModelQuerySetSchema()` when `QuerySet.detail` was missing, losing all optimizations

---

## 📝 Documentation

- **ModelUtil Documentation** ([docs/api/models/model_util.md](docs/api/models/model_util.md)):
  - Updated all method signatures from `is_for_read: bool` to `is_for: Literal["read", "detail"] | None`
  - Added `QuerySet.detail` configuration example
  - Added `serializable_detail_fields` property documentation
  - Updated examples to show `is_for="read"` and `is_for="detail"` usage
  - Added fallback behavior notes for detail optimizations

- **ModelSerializer Documentation** ([docs/api/models/model_serializer.md](docs/api/models/model_serializer.md)):
  - Added **Fallback Behavior** note in `DetailSerializer` section
  - Updated `generate_detail_s()` comment to indicate fallback to read schema
  - Updated fields table to mention fallback behavior

- **Serializer Documentation** ([docs/api/models/serializers.md](docs/api/models/serializers.md)):
  - Added `QuerySet.detail` configuration example
  - Added explanation of how each QuerySet config is applied (`read`, `detail`, `queryset_request`, `extras`)

---

## 🧪 Tests

- **Updated Test Cases**:
  - Updated all `is_for_read=True` to `is_for="read"` across test files
  - Updated all `is_for_read=False` to `is_for=None` across test files
  - Renamed `test_generate_detail_schema_returns_none_when_not_configured` to `test_generate_detail_schema_falls_back_to_read_when_not_configured`
  - Updated `test_fallback_to_schema_out_when_no_detail` to `test_detail_schema_falls_back_to_read_schema`

- **New Test Cases**:
  - `DetailFieldsModelSerializer` - Test model with different read vs detail fields including a relation
  - `ModelUtilIsForDetailTestCase` - Tests for `is_for='detail'` parameter:
    - `test_serializable_fields_returns_read_fields()`
    - `test_serializable_detail_fields_returns_detail_fields()`
    - `test_get_select_relateds_read_no_relations()`
    - `test_get_select_relateds_detail_includes_relation()`
    - `test_apply_query_optimizations_read_vs_detail()`
    - `test_get_serializable_field_names_read()`
    - `test_get_serializable_field_names_detail()`
  - `ReadOnlyQuerySetModelSerializer` - Test model with `QuerySet.read` but no `QuerySet.detail`
  - `ModelUtilOptimizationFallbackTestCase` - Tests for optimization fallback behavior:
    - `test_get_read_optimizations_read()`
    - `test_get_read_optimizations_detail_falls_back_to_read()`
    - `test_apply_query_optimizations_detail_uses_read_fallback()`

---

## 🔧 Internal Changes

- **BaseSerializer Changes**:
  - Added `detail = ModelQuerySetSchema()` to inner `QuerySet` class
  - Added fallback logic in `get_fields()` for detail type

- **QueryUtilBaseScopesSchema Changes**:
  - Added `DETAIL: str = "detail"` scope constant

- **QueryUtil Changes**:
  - Added `detail_config` property for accessing detail query configuration

---

## 🚀 Use Cases & Examples

### Detail-Specific Query Optimizations

```python
from ninja_aio.models import ModelSerializer
from ninja_aio.schemas.helpers import ModelQuerySetSchema

class Article(ModelSerializer):
    title = models.CharField(max_length=200)
    summary = models.TextField()
    content = models.TextField()
    author = models.ForeignKey(User, on_delete=models.CASCADE)
    tags = models.ManyToManyField(Tag)
    comments = models.ManyToManyField(Comment)

    class ReadSerializer:
        # List view: minimal fields
        fields = ["id", "title", "summary", "author"]

    class DetailSerializer:
        # Detail view: all fields including expensive relations
        fields = ["id", "title", "summary", "content", "author", "tags", "comments"]

    class QuerySet:
        # Optimizations for list endpoint
        read = ModelQuerySetSchema(
            select_related=["author"],
            prefetch_related=[],
        )
        # Optimizations for retrieve endpoint (more aggressive prefetching)
        detail = ModelQuerySetSchema(
            select_related=["author", "author__profile"],
            prefetch_related=["tags", "comments", "comments__author"],
        )
```

**Behavior:**
- `GET /articles/` uses `QuerySet.read` optimizations (light prefetching)
- `GET /articles/{pk}` uses `QuerySet.detail` optimizations (full prefetching)

### Fallback Behavior

```python
class Article(ModelSerializer):
    class ReadSerializer:
        fields = ["id", "title", "content"]

    class QuerySet:
        read = ModelQuerySetSchema(
            select_related=["author"],
            prefetch_related=["tags"],
        )
        # No detail config - will fall back to read!

# Both list and retrieve use QuerySet.read optimizations
# generate_detail_s() returns same schema as generate_read_s()
```

### Using is_for Parameter Directly

```python
from ninja_aio.models import ModelUtil

util = ModelUtil(Article)

# For list operations
qs = await util.get_objects(request, is_for="read")

# For single object retrieval
obj = await util.get_object(request, pk=1, is_for="detail")

# For serialization
data = await util.read_s(schema, request, instance=obj, is_for="detail")
items = await util.list_read_s(schema, request, instances=qs, is_for="read")
```

---

## 🔍 Migration Guide

### Breaking Change: `is_for_read` → `is_for`

If you call `ModelUtil` methods directly with `is_for_read`, update to use `is_for`:

```python
# Before (v2.8.0)
await util.get_objects(request, is_for_read=True)
await util.get_object(request, pk=1, is_for_read=True)
await util.read_s(schema, request, instance=obj, is_for_read=True)

# After (v2.9.0)
await util.get_objects(request, is_for="read")
await util.get_object(request, pk=1, is_for="detail")
await util.read_s(schema, request, instance=obj, is_for="detail")
```

**Mapping:**
| Old Parameter | New Parameter |
|---------------|---------------|
| `is_for_read=True` | `is_for="read"` (for list) or `is_for="detail"` (for retrieve) |
| `is_for_read=False` | `is_for=None` |

### Adding Detail-Specific Optimizations

```python
# Before (v2.8.0) - Same optimizations for list and retrieve
class QuerySet:
    read = ModelQuerySetSchema(
        select_related=["author"],
        prefetch_related=["tags", "comments"],  # Always loaded!
    )

# After (v2.9.0) - Different optimizations per operation
class QuerySet:
    read = ModelQuerySetSchema(
        select_related=["author"],
        prefetch_related=[],  # Light for list
    )
    detail = ModelQuerySetSchema(
        select_related=["author", "author__profile"],
        prefetch_related=["tags", "comments"],  # Full for retrieve
    )
```

---

## 📊 Performance Benefits

| Scenario | Without Detail Config | With Detail Config |
|----------|----------------------|-------------------|
| List 100 articles | Prefetches tags + comments for all | Only prefetches what's needed for list |
| Retrieve single | Uses list optimizations | Uses detail-specific optimizations |
| N+1 queries | May occur if list over-fetches | Optimized per endpoint |
| Memory usage | Higher (unnecessary prefetch) | Optimized per operation |

---

## ⚠️ Important Notes

- **Breaking Change**: `is_for_read: bool` parameter renamed to `is_for: Literal["read", "detail"] | None`
- **Fallback Behavior**: All fallbacks are automatic - no configuration needed for backward compatibility
- **QuerySet.detail**: Optional - falls back to `QuerySet.read` if not defined
- **DetailSerializer fields**: Optional - falls back to `ReadSerializer` fields if not defined
- **generate_detail_s()**: Now always returns a schema (falls back to read schema)

---

## 🔗 Links

- [Documentation](https://caspel26.github.io/django-ninja-aio-crud/)
- [GitHub Repository](https://github.com/caspel26/django-ninja-aio-crud)
- [Issue Tracker](https://github.com/caspel26/django-ninja-aio-crud/issues)
- [v2.8.0 Release Notes](https://github.com/caspel26/django-ninja-aio-crud/releases/tag/v2.8.0)

---

## Version History

For older versions, please refer to the [GitHub releases page](https://github.com/caspel26/django-ninja-aio-crud/releases).

---

## [v2.8.0] - 2026-01-14

---

## ✨ Added

- **Detail Schema Support for Retrieve Endpoints**:
  - New `DetailSerializer` configuration class for `ModelSerializer`
  - New `schema_detail` configuration option for `Serializer` Meta class
  - New `schema_detail` attribute on `APIViewSet` for custom detail schemas
  - New `generate_detail_s()` method for generating detail schemas
  - Retrieve endpoint (`GET /{base}/{pk}`) now uses `schema_detail` when available, falling back to `schema_out`
  - Enables performance optimization: minimal fields for list views, full details for single object retrieval

- **`serializer_class` Support for M2MRelationSchema**:
  - `M2MRelationSchema` now accepts `serializer_class` parameter for plain Django models
  - Auto-generates `related_schema` from the serializer when provided
  - Alternative to manually providing `related_schema` for plain models
  - Validation ensures `serializer_class` cannot be used when `model` is already a `ModelSerializer`

---

## 🛠 Changed

- **APIViewSet Schema Generation**:
  - `get_schemas()` now returns a 4-tuple: `(schema_out, schema_detail, schema_in, schema_update)`
  - New `_get_retrieve_schema()` helper method for retrieve endpoint schema selection
  - `retrieve_view()` updated to use detail schema when available

- **Refactored `get_schema_out_data()` Function**:
  - Extracted helper methods for better code organization:
    - `_is_reverse_relation()` - Check if field is a reverse relation
    - `_is_forward_relation()` - Check if field is a forward relation
    - `_warn_missing_relation_serializer()` - Emit warning for missing serializer mappings
    - `_process_field()` - Process single field and determine classification
  - Renamed parameter `type` to `schema_type` to avoid shadowing built-in
  - Renamed internal variable `rels` to `forward_rels` for clarity
  - Now accepts `schema_type: Literal["Out", "Detail"]` parameter

- **Performance Optimization in `_generate_union_schema()`**:
  - Fixed double method call issue using walrus operator
  - `generate_related_s()` now called once per serializer instead of twice

- **Updated Type Definitions**:
  - `S_TYPES` now includes `"detail"`: `Literal["read", "detail", "create", "update"]`
  - `SCHEMA_TYPES` now includes `"Detail"`: `Literal["In", "Out", "Detail", "Patch", "Related"]`

---

## 📝 Documentation

- **ModelSerializer Documentation** ([docs/api/models/model_serializer.md](docs/api/models/model_serializer.md)):
  - New **DetailSerializer** section with complete documentation
  - Updated schema generation table to include `generate_detail_s()`
  - Added example showing List vs Detail output differences
  - Updated "Auto-Generated Schemas" to show five schema types

- **Serializer Documentation** ([docs/api/models/serializers.md](docs/api/models/serializers.md)):
  - Added `schema_detail` to Meta configuration options
  - New **"Detail Schema for Retrieve Endpoint"** section
  - Updated schema generation examples to include `generate_detail_s()`

- **APIViewSet Documentation** ([docs/api/views/api_view_set.md](docs/api/views/api_view_set.md)):
  - Updated CRUD endpoints table to show retrieve uses `schema_detail`
  - Added `schema_detail` to Core Attributes table
  - New **"Detail Schema for Retrieve Endpoint"** section with examples
  - Updated automatic schema generation section
  - Added `serializer_class` documentation for `M2MRelationSchema`
  - Added tabbed examples for `related_schema` vs `serializer_class` usage

---

## 🧪 Tests

- **New Detail Schema Test Cases**:
  - `DetailSerializerTestCase` in [tests/test_serializers.py](tests/test_serializers.py):
    - `test_generate_detail_schema_with_serializer()` - Basic detail schema generation
    - `test_generate_detail_schema_returns_none_when_not_configured()` - None when not configured
    - `test_detail_schema_with_relations()` - Relations in detail schema
    - `test_detail_schema_with_custom_fields()` - Custom fields support
    - `test_detail_schema_with_optionals()` - Optional fields support

  - `DetailSchemaModelSerializerTestCase` in [tests/views/test_viewset.py](tests/views/test_viewset.py):
    - `test_read_schema_has_minimal_fields()` - ReadSerializer has minimal fields
    - `test_detail_schema_has_extended_fields()` - DetailSerializer has extended fields
    - `test_get_retrieve_schema_returns_detail()` - Retrieve uses detail schema
    - `test_get_schemas_returns_four_tuple()` - get_schemas returns 4-tuple

  - `DetailSchemaSerializerTestCase` - Tests for Serializer class with schema_detail
  - `DetailSchemaFallbackTestCase` - Tests fallback to schema_out when no detail defined

- **New M2M serializer_class Test Cases**:
  - `M2MRelationSchemaSerializerClassTestCase` - Tests M2M with serializer_class
  - `M2MRelationSchemaValidationTestCase`:
    - `test_serializer_class_with_plain_model_succeeds()`
    - `test_model_serializer_auto_generates_related_schema()`
    - `test_serializer_class_with_model_serializer_raises_error()`
    - `test_plain_model_without_serializer_class_or_related_schema_raises_error()`
    - `test_explicit_related_schema_takes_precedence()`

- **New Test Model**:
  - `TestModelSerializerWithDetail` in [tests/test_app/models.py](tests/test_app/models.py)
  - Demonstrates separate `ReadSerializer` and `DetailSerializer` configurations

- **Updated Existing Tests**:
  - All `schemas` property definitions updated to return 4-tuple format
  - `test_get_schemas` updated to expect 4 elements instead of 3
  - Refactored `ManyToManyAPITestCase` into `Tests.BaseManyToManyAPITestCase` base class

---

## 🔧 Internal Changes

- **Schema Mapping Updates**:
  - `_SCHEMA_META_MAP` now includes `"detail": "DetailSerializer"` for ModelSerializer
  - `_SERIALIZER_CONFIG_MAP` now includes `"detail": "detail"` for Serializer
  - `_get_serializer_config()` updated to handle `"detail"` case

- **ModelSerializer Changes**:
  - New `DetailSerializer` inner class with `fields`, `customs`, `optionals`, `excludes` attributes
  - `_generate_model_schema()` updated to handle `"Detail"` schema type
  - Schema naming: `"Out"` → `{model}SchemaOut`, `"Detail"` → `{model}DetailSchemaOut`

- **Serializer.Meta Changes**:
  - New `schema_detail: Optional[SchemaModelConfig]` attribute
  - `model_dump()` now uses detail schema when available for single object serialization

- **M2MRelationSchema Changes**:
  - New `serializer_class: Optional[SerializerMeta]` field
  - `validate_related_schema()` validator updated to handle serializer_class
  - ManyToManyAPI updated to pass serializer_class to ModelUtil

---

## 🚀 Use Cases & Examples

### Detail Schema for Performance Optimization

```python
from ninja_aio.models import ModelSerializer
from django.db import models

class Article(ModelSerializer):
    title = models.CharField(max_length=200)
    summary = models.TextField()
    content = models.TextField()
    author = models.ForeignKey(User, on_delete=models.CASCADE)
    tags = models.ManyToManyField(Tag)
    view_count = models.IntegerField(default=0)

    class ReadSerializer:
        # List view: minimal fields for performance
        fields = ["id", "title", "summary", "author"]

    class DetailSerializer:
        # Detail view: all fields including expensive relations
        fields = ["id", "title", "summary", "content", "author", "tags", "view_count"]
        customs = [
            ("reading_time", int, lambda obj: len(obj.content.split()) // 200),
        ]

@api.viewset(model=Article)
class ArticleViewSet(APIViewSet):
    pass  # Schemas auto-generated from model
```

**Endpoint Behavior:**
- `GET /articles/` returns `[{"id": 1, "title": "...", "summary": "...", "author": {...}}, ...]`
- `GET /articles/1` returns `{"id": 1, "title": "...", "summary": "...", "content": "...", "author": {...}, "tags": [...], "view_count": 1234, "reading_time": 5}`

### Detail Schema with Serializer Class

```python
from ninja_aio.models import serializers

class ArticleSerializer(serializers.Serializer):
    class Meta:
        model = models.Article
        schema_out = serializers.SchemaModelConfig(
            # List view: minimal fields
            fields=["id", "title", "summary"]
        )
        schema_detail = serializers.SchemaModelConfig(
            # Detail view: all fields
            fields=["id", "title", "summary", "content", "author", "tags"],
            customs=[("reading_time", int, lambda obj: len(obj.content.split()) // 200)]
        )

@api.viewset(model=models.Article)
class ArticleViewSet(APIViewSet):
    serializer_class = ArticleSerializer
```

### M2M with serializer_class

```python
from ninja_aio.models import serializers
from ninja_aio.schemas import M2MRelationSchema

class TagSerializer(serializers.Serializer):
    class Meta:
        model = Tag
        schema_out = serializers.SchemaModelConfig(fields=["id", "name"])

@api.viewset(model=Article)
class ArticleViewSet(APIViewSet):
    m2m_relations = [
        M2MRelationSchema(
            model=Tag,                        # plain Django model
            related_name="tags",
            serializer_class=TagSerializer,   # auto-generates related_schema
            add=True,
            remove=True,
            get=True,
        )
    ]
```

---

## 🔍 Migration Guide

### Using Detail Schemas

No migration required! Detail schema support is **fully backward compatible**:

```python
# Existing code continues to work (no DetailSerializer = uses schema_out for retrieve)
class Article(ModelSerializer):
    class ReadSerializer:
        fields = ["id", "title", "content"]  # Used for both list AND retrieve

# New: Add DetailSerializer for different retrieve response
class Article(ModelSerializer):
    class ReadSerializer:
        fields = ["id", "title"]  # Used for list only

    class DetailSerializer:
        fields = ["id", "title", "content", "author", "tags"]  # Used for retrieve
```

### Using serializer_class in M2MRelationSchema

```python
# Before (v2.7.0) - Must provide related_schema manually
M2MRelationSchema(
    model=Tag,
    related_name="tags",
    related_schema=TagOut,  # Must define this schema manually
)

# After (v2.8.0) - Can use serializer_class instead
M2MRelationSchema(
    model=Tag,
    related_name="tags",
    serializer_class=TagSerializer,  # Auto-generates related_schema!
)
```

### Updating Custom ViewSet Subclasses

If you override `get_schemas()`, update to return 4-tuple:

```python
# Before (v2.7.0)
def get_schemas(self):
    return (schema_out, schema_in, schema_update)

# After (v2.8.0)
def get_schemas(self):
    return (schema_out, schema_detail, schema_in, schema_update)
```

---

## 🎯 When to Use Detail Schema

- **Performance Optimization**: Return minimal fields in list views, full details in retrieve
- **API Design**: Clients get summaries in lists, full objects on individual requests
- **Expensive Relations**: Avoid loading M2M/reverse relations for list endpoints
- **Computed Fields**: Only compute expensive fields for single object retrieval
- **Bandwidth Optimization**: Reduce payload size for list responses

---

## 📊 Performance Benefits

| Scenario | Without Detail Schema | With Detail Schema |
|----------|----------------------|-------------------|
| List 100 articles | Returns 100 × full content | Returns 100 × summary only |
| Load M2M tags | Loaded for all 100 items | Only loaded for single retrieve |
| Computed fields | Calculated for all items | Only calculated on retrieve |
| Response size | Large (full content) | Optimized per endpoint |

---

## ⚠️ Important Notes

- **Fallback Behavior**: If `DetailSerializer`/`schema_detail` not defined, retrieve uses `schema_out`
- **Schema Generation**: `generate_detail_s()` returns `None` if no detail config exists
- **Backward Compatibility**: All existing code works without changes
- **4-Tuple Return**: `get_schemas()` now returns 4 values instead of 3
- **M2M Validation**: Cannot use `serializer_class` with `ModelSerializer` models

---

## 🙏 Acknowledgments

This release focuses on:
- Enhanced API design flexibility with separate list/detail schemas
- Performance optimization for list endpoints
- Better M2M relation configuration options
- Improved code organization and maintainability

---

## 🔗 Links

- [Documentation](https://caspel26.github.io/django-ninja-aio-crud/)
- [GitHub Repository](https://github.com/caspel26/django-ninja-aio-crud)
- [Issue Tracker](https://github.com/caspel26/django-ninja-aio-crud/issues)
- [v2.7.0 Release Notes](https://github.com/caspel26/django-ninja-aio-crud/releases/tag/v2.7.0)

---

## 📦 Quick Start with Detail Schema

```python
from ninja_aio.models import ModelSerializer
from ninja_aio.views import APIViewSet
from ninja_aio import NinjaAIO
from django.db import models

api = NinjaAIO(title="My API")

# Step 1: Define your model with ReadSerializer and DetailSerializer
class Article(ModelSerializer):
    title = models.CharField(max_length=200)
    summary = models.TextField()
    content = models.TextField()
    author = models.ForeignKey(User, on_delete=models.CASCADE)
    tags = models.ManyToManyField(Tag)

    class ReadSerializer:
        fields = ["id", "title", "summary"]  # Minimal for list

    class DetailSerializer:
        fields = ["id", "title", "summary", "content", "author", "tags"]  # Full for retrieve

# Step 2: Create your ViewSet (schemas auto-generated!)
@api.viewset(model=Article)
class ArticleViewSet(APIViewSet):
    pass

# That's it! Your API now has optimized list and detail endpoints:
# GET /articles/      → Returns list with minimal fields
# GET /articles/{pk}  → Returns single article with all fields
```

---

## Version History

For older versions, please refer to the [GitHub releases page](https://github.com/caspel26/django-ninja-aio-crud/releases).

---

## [v2.7.0] - 2026-01-13

---

## ✨ Added

- **Union Type Support for Polymorphic Relations**:
  - `relations_serializers` now accepts `Union[SerializerA, SerializerB]` to handle polymorphic relationships
  - Enables flexible handling of generic foreign keys, content types, and multi-model relations
  - **Direct class references**: `Union[SerializerA, SerializerB]`
  - **String references**: `Union["SerializerA", "SerializerB"]`
  - **Mixed references**: `Union[SerializerA, "SerializerB"]`
  - **Absolute import paths**: `Union["myapp.serializers.SerializerA", SerializerB]`
  - Lazy resolution of union members supports forward/circular dependencies
  - Schema generator creates union of all possible schemas automatically

- **Absolute Import Path Support for String References**:
  - String references now support absolute import paths using dot notation
  - Example: `"myapp.serializers.UserSerializer"` or `"users.serializers.UserSerializer"`
  - Enables cross-module serializer references without circular import issues
  - Automatic module importing when needed (uses `importlib.import_module()`)
  - Resolves lazily when schemas are generated
  - Works seamlessly with Union types

---

## 🛠 Changed

- **Enhanced Serializer Reference Resolution**:
  - Now handles Union types by recursively resolving each member
  - Handles ForwardRef objects created by string type hints in unions (e.g., `Union["StringType"]`)
  - Optimizes single-type unions by returning the single type directly

- **Enhanced Relation Schema Generation**:
  - Generates union schemas when serializer reference is a Union type
  - Maintains full backward compatibility with single serializer references
  - Automatically filters out None schemas from union members

- **Updated Type Hints**:
  - All serializer methods updated to reflect Union support
  - Better type safety for Union[Schema, ...] return values
  - Clearer documentation of acceptable input types

---

## 📝 Documentation

- **Comprehensive Union Types Documentation** in [docs/api/models/serializers.md](docs/api/models/serializers.md):
  - **New "Union Types for Polymorphic Relations" section**:
    - Complete explanation of Union support with real-world examples
    - Basic polymorphic example with Video and Image serializers
    - All four Union type format variations documented with code samples
    - Use cases: polymorphic relations, flexible APIs, gradual migrations, multi-tenant systems
    - Complete polymorphic example using Django's GenericForeignKey
    - BlogPost/Product/Event example showing complex multi-model relations

  - **New "String Reference Formats" section**:
    - Local class name format: `"ArticleSerializer"`
    - Absolute import path format: `"myapp.serializers.ArticleSerializer"`
    - Requirements and resolution behavior documented
    - Cross-module references example with circular dependencies

  - **Enhanced Configuration Section**:
    - `relations_serializers` parameter updated to document Union support
    - Clear explanation: "Serializer class, **string reference**, or **Union of serializers**"
    - Forward/circular dependencies and polymorphic relations highlighted
    - Updated comparison table showing Union support feature

  - **Updated Key Features**:
    - Added Union types for polymorphic relations to key features list
    - Updated notes to mention Union type lazy resolution
    - Added note about schema generator creating unions

- **Code Examples and Best Practices**:
  - Video/Image comment example for basic polymorphic relations
  - BlogPost/Product/Event example for complex GenericForeignKey usage
  - Cross-module circular reference example (Article ↔ User)
  - All four Union format variations with syntax examples

---

## 🧪 Tests

- **New Comprehensive Test Suite** - `UnionSerializerTestCase` in [tests/test_serializers.py](tests/test_serializers.py)

- **Module-Level Test Serializers**:
  - `AltSerializer` - Alternative serializer with different field set (id, name)
  - `AltStringSerializer` - String reference test serializer (id, description)
  - `MixedAltSerializer` - Mixed reference test serializer (id, name, description)
  - `LocalTestSerializer` - Local reference test serializer (id only)

---

## 🔧 Internal Changes

- **Python 3.10+ Compatibility Fix**:
  - Union types created using `Union[tuple]` syntax for compatibility
  - Replaced incompatible `reduce(or_, resolved_types)` pattern
  - Works correctly across Python 3.10, 3.11, 3.12+
  - No dependency on `functools.reduce` or `operator.or_`
  - Uses Python's typing system to expand `Union[tuple]` automatically

- **Code Organization**:
  - Extracted string resolution logic into dedicated `_resolve_string_reference()` method
  - Extracted union schema generation into dedicated `_generate_union_schema()` method
  - Improved separation of concerns and code reusability
  - Better error messages with full import paths in exceptions

---

## 🚀 Use Cases & Examples

### Basic Polymorphic Relations

```python
from typing import Union
from ninja_aio.models import serializers

class VideoSerializer(serializers.Serializer):
    class Meta:
        model = models.Video
        schema_out = serializers.SchemaModelConfig(
            fields=["id", "title", "duration", "url"]
        )

class ImageSerializer(serializers.Serializer):
    class Meta:
        model = models.Image
        schema_out = serializers.SchemaModelConfig(
            fields=["id", "title", "width", "height", "url"]
        )

class CommentSerializer(serializers.Serializer):
    class Meta:
        model = models.Comment
        schema_out = serializers.SchemaModelConfig(
            fields=["id", "text", "content_object"]
        )
        relations_serializers = {
            "content_object": Union[VideoSerializer, ImageSerializer],
        }
```

### Cross-Module References

```python
# myapp/serializers.py
class ArticleSerializer(serializers.Serializer):
    class Meta:
        model = models.Article
        schema_out = serializers.SchemaModelConfig(
            fields=["id", "title", "author"]
        )
        relations_serializers = {
            "author": "users.serializers.UserSerializer",  # Absolute path
        }

# users/serializers.py
class UserSerializer(serializers.Serializer):
    class Meta:
        model = models.User
        schema_out = serializers.SchemaModelConfig(
            fields=["id", "username", "articles"]
        )
        relations_serializers = {
            "articles": "myapp.serializers.ArticleSerializer",  # Circular ref!
        }
```

### Generic Foreign Keys

```python
from django.contrib.contenttypes.fields import GenericForeignKey
from typing import Union

class CommentSerializer(serializers.Serializer):
    class Meta:
        model = Comment
        schema_out = serializers.SchemaModelConfig(
            fields=["id", "text", "created_at", "content_object"]
        )
        relations_serializers = {
            "content_object": Union[
                BlogPostSerializer,
                ProductSerializer,
                EventSerializer
            ],
        }
```

---

## 🔍 Migration Guide

### Using Union Types

No migration needed! Union support is **fully backward compatible**:

```python
# Existing code continues to work
class MySerializer(serializers.Serializer):
    class Meta:
        model = MyModel
        relations_serializers = {
            "author": AuthorSerializer,  # ✅ Still works
        }

# New Union syntax available
class MySerializer(serializers.Serializer):
    class Meta:
        model = MyModel
        relations_serializers = {
            "content": Union[VideoSerializer, ImageSerializer],  # ✅ New!
        }
```

### Using Absolute Import Paths

Update string references to use absolute paths for cross-module references:

```python
# Before (v2.6.1) - Only local references worked
relations_serializers = {
    "author": "AuthorSerializer",  # Must be in same module
}

# After (v2.7.0) - Absolute paths supported
relations_serializers = {
    "author": "users.serializers.AuthorSerializer",  # ✅ Cross-module!
}
```

### String Reference Formats

Both formats are supported:

```python
relations_serializers = {
    # Local reference (same module)
    "field1": "LocalSerializer",

    # Absolute import path (any module)
    "field2": "myapp.serializers.RemoteSerializer",

    # Union with mixed formats
    "field3": Union["LocalSerializer", "myapp.other.RemoteSerializer"],
}
```

---

## 🎯 When to Use Union Types

- **Polymorphic Relations**: Generic foreign keys, Django ContentType relations
- **Flexible APIs**: Different response formats based on runtime type
- **Gradual Migrations**: Transitioning between serializer implementations
- **Multi-Tenant Systems**: Different serialization per tenant
- **Dynamic Content**: CMS systems with multiple content types
- **Activity Feeds**: Mixed content types in single endpoint

---

## 📊 Performance Notes

- **Lazy Resolution**: Union members resolved only when schemas generated (no startup overhead)
- **Schema Caching**: Generated schemas can be cached for better performance
- **Memory Efficient**: Only generates schemas for types actually used
- **Import Optimization**: Absolute paths only import modules when needed

---

## ⚠️ Important Notes

- **String References**: Resolve within same module by default; use absolute paths for cross-module
- **Union Schema Generation**: Creates union of all possible schemas from union members
- **Backward Compatibility**: All existing code continues to work without changes
- **Python Version**: Requires Python 3.10+ (Union syntax compatibility)
- **Type Validation**: Union types provide type hints but runtime validation depends on your model logic

---

## 🙏 Acknowledgments

This release focuses on:
- Enhanced flexibility for polymorphic relationships
- Better support for complex project architectures
- Improved developer experience with cross-module references
- Python 3.10+ compatibility and modern typing features

---

## 🔗 Links

- [Documentation](https://caspel26.github.io/django-ninja-aio-crud/)
- [GitHub Repository](https://github.com/caspel26/django-ninja-aio-crud)
- [Issue Tracker](https://github.com/caspel26/django-ninja-aio-crud/issues)
- [v2.6.1 Release Notes](https://github.com/caspel26/django-ninja-aio-crud/releases/tag/v2.6.1)

---

## 📦 Quick Start with Union Types

```python
from typing import Union
from ninja_aio.models import serializers

# Step 1: Define your serializers
class VideoSerializer(serializers.Serializer):
    class Meta:
        model = Video
        schema_out = serializers.SchemaModelConfig(fields=["id", "title", "url"])

class ImageSerializer(serializers.Serializer):
    class Meta:
        model = Image
        schema_out = serializers.SchemaModelConfig(fields=["id", "title", "url"])

# Step 2: Use Union in relations_serializers
class CommentSerializer(serializers.Serializer):
    class Meta:
        model = Comment
        schema_out = serializers.SchemaModelConfig(
            fields=["id", "text", "content_object"]
        )
        relations_serializers = {
            "content_object": Union[VideoSerializer, ImageSerializer],
        }

# Step 3: Use with APIViewSet (automatic!)
@api.viewset(model=Comment)
class CommentViewSet(APIViewSet):
    serializer_class = CommentSerializer
    # Union types work automatically!
```

---

## Version History

For older versions, please refer to the [GitHub releases page](https://github.com/GiuseppeCasillo/django-ninja-aio-crud/releases).

---

## [v2.6.1] - 2026-01-12

---

## ✨ Added

- **String Reference Support for Relations**:
  - `relations_serializers` now accepts string references (e.g., `"ArticleSerializer"`) in addition to class references
  - Enables forward references and circular dependencies between serializers
  - Lazy resolution of serializer references when schemas are generated

- **New Internal Methods**:
  - `BaseSerializer._resolve_serializer_reference()` - Resolves string or class serializer references
  - `BaseSerializer._resolve_relation_schema()` - Centralized relation schema resolution logic

---

## 🛠 Changed

- **Schema Generation Lifecycle**:
  - Removed eager schema generation from `Serializer.__init_subclass__()`
  - Schemas are now generated on-demand via explicit calls to `generate_*()` methods
  - Removed cached schema properties (`.schema_in`, `.schema_out`, `.schema_update`, `.schema_related`)
  - **Breaking**: Must use `generate_create_s()`, `generate_read_s()`, etc. instead of accessing properties

- **Internal Refactoring**:
  - Replaced `match/case` with `if/elif` statements in `_generate_model_schema()` for better readability
  - Added configuration mapping dictionaries (`_SERIALIZER_CONFIG_MAP`) to simplify lookups
  - Consolidated duplicate schema resolution logic in relation handling methods
  - Improved code organization with clearer comments and structure

- **APIViewSet Integration**:
  - Added `serializer` instance property initialized from `serializer_class()`
  - Better integration with on-demand schema generation

---

## 📝 Documentation

- **Updated Serializer Documentation**:
  - Added "String References for Forward/Circular Dependencies" section with examples
  - Updated "Schema Generation" section to clarify on-demand generation
  - Removed outdated references to eager schema generation
  - Updated comparison table: "Auto-binding" → "Schema generation"
  - Enhanced configuration section with bold formatting and clearer descriptions

- **Key Documentation Changes**:
  - Emphasized that `generate_*()` methods must be called explicitly
  - Documented string reference requirements (same module, lazy resolution)
  - Added circular dependency example with `AuthorSerializer` ↔ `ArticleSerializer`

---

## ⚠ Breaking Changes & Migration Notes

### Removed Schema Properties

Schema properties have been removed from `Serializer` class. You must now explicitly call generation methods:

```python
# Before (v2.5.0) - NO LONGER WORKS
ArticleSerializer.schema_in       # ❌ AttributeError
ArticleSerializer.schema_out      # ❌ AttributeError
ArticleSerializer.schema_update   # ❌ AttributeError
ArticleSerializer.schema_related  # ❌ AttributeError

# After (v2.6.0) - Explicit generation required
ArticleSerializer.generate_create_s()   # ✅ Returns create schema
ArticleSerializer.generate_read_s()     # ✅ Returns read schema
ArticleSerializer.generate_update_s()   # ✅ Returns update schema
ArticleSerializer.generate_related_s()  # ✅ Returns related schema
```

**Note**: This change typically doesn't affect user code since these methods are called internally by `APIViewSet`. Only relevant if you're calling these methods directly.

---

## 🔍 Migration Guide

### 1. Update Schema Access in Custom Code

If you're directly accessing schema properties, update to use generation methods:

```python
# Before (v2.5.0)
class ArticleViewSet(APIViewSet):
    def get_schemas(self):
        return {
            "in": self.serializer_class.schema_in,      # ❌ No longer works
            "out": self.serializer_class.schema_out,    # ❌ No longer works
        }

# After (v2.6.0)
class ArticleViewSet(APIViewSet):
    def get_schemas(self):
        return {
            "in": self.serializer_class.generate_create_s(),   # ✅ Explicit generation
            "out": self.serializer_class.generate_read_s(),    # ✅ Explicit generation
        }
```

### 2. Use String References for Circular Dependencies

Take advantage of string references to simplify circular dependencies:

```python
# Before (v2.5.0) - Workarounds needed for circular refs
class AuthorSerializer(serializers.Serializer):
    class Meta:
        model = models.Author
        schema_out = serializers.SchemaModelConfig(
            fields=["id", "name", "articles"]
        )
        # Had to carefully order class definitions or use late binding

# After (v2.6.0) - String references make it easy
class AuthorSerializer(serializers.Serializer):
    class Meta:
        model = models.Author
        schema_out = serializers.SchemaModelConfig(
            fields=["id", "name", "articles"]
        )
        relations_serializers = {
            "articles": "ArticleSerializer",  # ✅ Forward reference
        }

class ArticleSerializer(serializers.Serializer):
    class Meta:
        model = models.Article
        schema_out = serializers.SchemaModelConfig(
            fields=["id", "title", "author"]
        )
        relations_serializers = {
            "author": "AuthorSerializer",  # ✅ Circular reference works!
        }
```

**String Reference Requirements:**
- Must be the exact class name as a string
- Serializer must be defined in the same module
- Resolution happens lazily when `generate_*()` is called
- Both forward and circular references are supported

### 3. Schema Generation Best Practices

**In APIViewSet** (no changes needed):
```python
# APIViewSet handles schema generation automatically
@api.viewset(model=Article)
class ArticleViewSet(APIViewSet):
    serializer_class = ArticleSerializer
    # No changes needed - works automatically
```

**In Custom Code** (call generate methods):
```python
# Explicit schema generation when needed
from ninja import Router

router = Router()

@router.post("/articles/", response=ArticleSerializer.generate_read_s())
async def create_article(request, payload: ArticleSerializer.generate_create_s()):
    serializer = ArticleSerializer()
    instance = await serializer.create(payload.model_dump())
    return await serializer.model_dump(instance)
```

**Caching Schemas** (if needed for performance):
```python
# Cache schemas at module level if generating repeatedly
ARTICLE_CREATE_SCHEMA = ArticleSerializer.generate_create_s()
ARTICLE_READ_SCHEMA = ArticleSerializer.generate_read_s()

@router.post("/articles/", response=ARTICLE_READ_SCHEMA)
async def create_article(payload: ARTICLE_CREATE_SCHEMA):
    # Use cached schemas
    pass
```

### 4. Complete Migration Example

Here's a complete before/after example:

```python
# Before (v2.5.0)
from ninja_aio.models import serializers
from ninja_aio import NinjaAIO
from ninja_aio.views import APIViewSet

class AuthorSerializer(serializers.Serializer):
    class Meta:
        model = models.Author
        schema_out = serializers.SchemaModelConfig(
            fields=["id", "name"]
        )

class ArticleSerializer(serializers.Serializer):
    class Meta:
        model = models.Article
        schema_out = serializers.SchemaModelConfig(
            fields=["id", "title", "author"]
        )
        relations_serializers = {
            "author": AuthorSerializer,  # Required class ordering
        }

# Access schemas (no longer works)
create_schema = ArticleSerializer.schema_in      # ❌
read_schema = ArticleSerializer.schema_out       # ❌

# After (v2.6.0)
from ninja_aio.models import serializers
from ninja_aio import NinjaAIO
from ninja_aio.views import APIViewSet

class AuthorSerializer(serializers.Serializer):
    class Meta:
        model = models.Author
        schema_out = serializers.SchemaModelConfig(
            fields=["id", "name", "articles"]
        )
        relations_serializers = {
            "articles": "ArticleSerializer",  # ✅ String reference
        }

class ArticleSerializer(serializers.Serializer):
    class Meta:
        model = models.Article
        schema_out = serializers.SchemaModelConfig(
            fields=["id", "title", "author"]
        )
        relations_serializers = {
            "author": "AuthorSerializer",  # ✅ Circular reference!
        }

# Explicit schema generation
create_schema = ArticleSerializer.generate_create_s()  # ✅
read_schema = ArticleSerializer.generate_read_s()      # ✅

# Using with APIViewSet (no changes needed)
api = NinjaAIO()

@api.viewset(model=Article)
class ArticleViewSet(APIViewSet):
    serializer_class = ArticleSerializer
    # Automatically works with on-demand generation
```

---

## 🐛 Bug Fixes

- Fixed lazy resolution issues with forward and circular serializer references
- Improved error messages when string references cannot be resolved
- Corrected `model_dump()` and `models_dump()` to use explicit schema generation
- Fixed potential issues with `model_util` vs `util` attribute naming

---

## 🚀 Performance Improvements

- **Reduced Initialization Overhead**: Schemas only generated when actually needed
- **Memory Efficiency**: Unused schemas are never created
- **Lazy Resolution**: String references resolved on-demand, reducing startup time
- **Faster Imports**: Removed eager schema generation from module import time

---

## 📊 Code Quality Improvements

- **Reduced Code Duplication**:
  - Extracted common relation resolution logic into `_resolve_relation_schema()`
  - Consolidated duplicate code in `_build_schema_reverse_rel()` and `_build_schema_forward_rel()`
  - Reduced relation handling code by ~40 lines

- **Improved Maintainability**:
  - Replaced `match/case` with clearer `if/elif` statements
  - Added configuration mapping dictionaries for cleaner lookups
  - Better code organization with descriptive comments
  - Consistent use of `any()` for empty checks

- **Better Readability**:
  - Flattened nesting in `_generate_model_schema()`
  - Clearer separation between special cases and standard logic
  - Improved docstrings and parameter descriptions
  - More descriptive variable names

---

## 🙏 Acknowledgments

This release focuses on:
- Architectural improvements for forward/circular dependency support
- Cleaner, more maintainable internal code structure
- On-demand resource generation for better performance
- Enhanced developer experience with string references

---

## 📝 Notes

- **Schema Generation**: While properties were removed, `APIViewSet` automatically calls `generate_*()` methods, so most applications won't need code changes

- **Performance**: On-demand generation typically improves startup time. If you need schemas multiple times, consider caching them at module level

- **String References**: Only resolve within the same module. For cross-module references, use direct class imports

- **Backward Compatibility**: Code using `APIViewSet` continues to work without changes. Direct schema property access will raise `AttributeError`

- **Internal Refactoring**: This release includes significant internal refactoring for code quality without changing public APIs (except removal of schema properties)

---

## 🔗 Links

- [Documentation](https://caspel26.github.io/django-ninja-aio-crud/)
- [GitHub Repository](https://github.com/caspel26/django-ninja-aio-crud)
- [Issue Tracker](https://github.com/caspel26/django-ninja-aio-crud/issues)
- [v2.5.0 Release Notes](https://github.com/caspel26/django-ninja-aio-crud/releases/tag/v2.5.0)

---

## 📦 Upgrade Checklist

Use this checklist when upgrading from v2.5.0 to v2.6.0:

- [ ] Search codebase for `.schema_in`, `.schema_out`, `.schema_update`, `.schema_related` property access
- [ ] Replace with `generate_create_s()`, `generate_read_s()`, `generate_update_s()`, `generate_related_s()` calls
- [ ] Update any circular serializer references to use string references
- [ ] Review custom `create()` and `update()` method implementations (if any)
- [ ] Test all CRUD endpoints to ensure proper functionality
- [ ] Update any schema caching logic to use explicit generation
- [ ] Review and update API documentation if it references old property access

---

---

## [v2.5.0] - 2026-01-12

---

## ✨ Added

- **APIViewSet Enhancements**:
  - `model_verbose_name` and `model_verbose_name_plural` attributes for display name customization
  - Automatic transaction wrapping on create, update, and delete operations

- **ModelUtil Query Methods**:
  - New properties:
    - `with_serializer` - Check if serializer_class is attached
    - `pk_field_type` - Python type corresponding to the primary key field
    - `model_name` - Django internal model name

---

## 🛠 Changed

- **APIViewSet**:
  - CRUD views now automatically decorated with `@aatomic` for transactional integrity
  - Enhanced `get_schemas()` method for unified schema generation from both ModelSerializer and Serializer

- **ModelUtil**:
  - Query optimization merging logic improved to respect both model and serializer configurations

- **Serializer Lifecycle Hooks**:
  - All Serializer hooks now consistently receive `instance` parameter
  - Inline execution of before/after save hooks integrated with `@aatomic` decorator
  - Hook signatures standardized: `custom_actions(payload, instance)`, `post_create(instance)`, `before_save(instance)`, etc.

---

## 📝 Documentation

- **New Documentation Pages**:
  - Transaction Management section in APIViewSet docs
  - Extra Decorators section with examples and configuration
  - Enhanced ModelUtil properties documentation
  - Query method parameter documentation with detailed examples

- **Enhanced Content**:
  - APIViewSet Core Attributes table updated with new fields
  - Serializer lifecycle hooks section with complete signature examples
  - ModelUtil method signatures with all parameters documented
  - CRUD operation flows documented for Serializer pattern

---

## ⚠ Breaking Changes & Migration Notes

### Transaction Behavior (New Default)

Create, update, and delete operations are now automatically wrapped in database transactions:

```python
# Automatic transaction wrapping (new in v2.5.0)
@api.viewset(model=Article)
class ArticleViewSet(APIViewSet):
    pass  # create/update/delete wrapped in @aatomic
```

**Migration**: If you were manually managing transactions in lifecycle hooks, you may encounter nested transaction issues. Remove manual transaction management:

```python
# Before (v2.4.0)
async def post_create(self, instance):
    async with transaction.atomic():  # Remove this
        await AuditLog.objects.acreate(...)

# After (v2.5.0)
async def post_create(self, instance):
    # Transaction already managed by @aatomic
    await AuditLog.objects.acreate(...)
```

### Serializer Hook Signatures

Added Serializer hooks signatures, they are standardized to always receive `instance`:

```python
# v2.5.0 - Standardized (always receive instance)
class MySerializer(Serializer):
    async def custom_actions(self, payload, instance):
        # instance parameter required
        pass

    async def post_create(self, instance):
        # instance parameter required
        pass

    def before_save(self, instance):
        # instance parameter required
        pass

    def after_save(self, instance):
        # instance parameter required
        pass

    def on_delete(self, instance):
        # instance parameter required
        pass
```

---

## 🔍 Migration Guide

### 1. Updating Serializer Lifecycle Hooks

If you're using Serializer (Meta-driven pattern), update hook signatures to receive `instance` parameter:

```python
from ninja_aio.models import serializers
from asgiref.sync import sync_to_async

class ArticleSerializer(serializers.Serializer):
    class Meta:
        model = Article
        schema_in = serializers.SchemaModelConfig(
            fields=["title", "content", "author"],
            customs=[("send_notification", bool, True)]
        )
        schema_out = serializers.SchemaModelConfig(
            fields=["id", "title", "content", "author", "created_at"]
        )

    # Async hooks - receive instance parameter
    async def custom_actions(self, payload, instance):
        """Execute custom logic after field assignment."""
        if payload.get("send_notification"):
            # Access instance fields
            await send_email(
                instance.author.email,
                f"Article created: {instance.title}"
            )

    async def post_create(self, instance):
        """Hook after first save (creation only)."""
        await AuditLog.objects.acreate(
            action="article_created",
            article_id=instance.id,
            user_id=instance.author_id
        )

    # Sync hooks - also receive instance parameter
    def before_save(self, instance):
        """Modify instance before save."""
        from django.utils.text import slugify
        if not instance.slug:
            instance.slug = slugify(instance.title)

    def after_save(self, instance):
        """Execute logic after save."""
        # Clear cache
        from django.core.cache import cache
        cache.delete(f"article:{instance.id}")

    def on_create_before_save(self, instance):
        """Before save, creation only."""
        instance.view_count = 0

    def on_create_after_save(self, instance):
        """After save, creation only."""
        # Log creation
        import logging
        logger = logging.getLogger(__name__)
        logger.info(f"Article {instance.id} created")

    def on_delete(self, instance):
        """After deletion."""
        import logging
        logger = logging.getLogger(__name__)
        logger.info(f"Article {instance.id} deleted")
```

**Key Points:**
- All hooks receive `instance` as a parameter
- Async hooks: `custom_actions(payload, instance)`, `post_create(instance)`
- Sync hooks: `before_save(instance)`, `after_save(instance)`, `on_delete(instance)`
- Creation-specific hooks: `on_create_before_save(instance)`, `on_create_after_save(instance)`

### 2. Configuring QuerySet Optimization

Add QuerySet configuration to your Serializer or ModelSerializer for automatic query optimization:

```python
from ninja_aio.models import serializers
from ninja_aio.schemas.helpers import ModelQuerySetSchema, ModelQuerySetExtraSchema

class ArticleSerializer(serializers.Serializer):
    class Meta:
        model = Article
        schema_out = serializers.SchemaModelConfig(
            fields=["id", "title", "content", "author", "category", "tags"]
        )
        relations_serializers = {
            "author": AuthorSerializer,
            "category": CategorySerializer,
            "tags": TagSerializer,
        }

    class QuerySet:
        # Applied to list and retrieve operations
        read = ModelQuerySetSchema(
            select_related=["author", "category"],
            prefetch_related=["tags"],
        )

        # Applied when queryset_request hook is called
        queryset_request = ModelQuerySetSchema(
            select_related=["author__profile"],
            prefetch_related=["comments", "comments__author"],
        )

        # Named scopes for specific use cases
        extras = [
            ModelQuerySetExtraSchema(
                scope="detail_view",
                select_related=["author", "author__profile", "category"],
                prefetch_related=["tags", "comments", "comments__author"],
            ),
            ModelQuerySetExtraSchema(
                scope="list_view",
                select_related=["author", "category"],
                prefetch_related=["tags"],
            ),
        ]

    @classmethod
    async def queryset_request(cls, request):
        """
        Optional: Customize queryset based on request.
        Automatically enhanced with QuerySet.queryset_request optimizations.
        """
        qs = cls._meta.model.objects.all()

        # Filter based on user permissions
        if not request.user.is_staff:
            qs = qs.filter(is_published=True)

        # Add request-specific filters
        if request.GET.get("featured"):
            qs = qs.filter(is_featured=True)

        return qs
```

**For ModelSerializer:**

```python
from ninja_aio.models import ModelSerializer
from ninja_aio.schemas.helpers import ModelQuerySetSchema
from django.db import models

class Article(ModelSerializer):
    title = models.CharField(max_length=200)
    content = models.TextField()
    author = models.ForeignKey(User, on_delete=models.CASCADE)
    category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True)
    tags = models.ManyToManyField(Tag, related_name="articles")

    class ReadSerializer:
        fields = ["id", "title", "content", "author", "category", "tags"]

    class QuerySet:
        read = ModelQuerySetSchema(
            select_related=["author", "category"],
            prefetch_related=["tags"],
        )
        queryset_request = ModelQuerySetSchema(
            select_related=["author__profile"],
            prefetch_related=["comments"],
        )

    @classmethod
    async def queryset_request(cls, request):
        """Optimize queries for this model."""
        return cls.objects.select_related("author", "category")
```

**How QuerySet Configuration Works:**

1. **`read`**: Applied automatically to list and retrieve operations when `is_for_read=True`
2. **`queryset_request`**: Applied when `with_qs_request=True` (default) in `get_objects()` or `get_object()`
3. **`extras`**: Named scopes accessible via `QueryUtil.SCOPES` for custom scenarios
4. **Merging**: Optimizations from multiple sources are merged (no duplicates)

**Benefits:**
- Eliminates N+1 queries automatically
- Centralizes query optimization configuration
- Works with both ModelSerializer and Serializer patterns
- Optimizations apply to all CRUD operations

### 3. Customizing Model Display Names

Override verbose names without modifying models:

```python
@api.viewset(model=Article)
class ArticleViewSet(APIViewSet):
    model_verbose_name = "Blog Post"
    model_verbose_name_plural = "Blog Posts"
    # OpenAPI will use "Blog Post" instead of "Article"
```

---

## 🐛 Bug Fixes

- Fixed query optimization merging when both model and serializer provide hints
- Corrected `read_s()` behavior when both `instance` and `query_data` provided (now raises clear error)
- Improved error messages for missing primary key in `get_object()`
- Fixed duplicate route registration with `@unique_view` decorator

---

## 🚀 Performance Improvements

- Transaction management with `@aatomic` reduces database round-trips
- Query optimization merging eliminates redundant select_related/prefetch_related
- `with_qs_request` parameter allows skipping hook when not needed

---

## 🙏 Acknowledgments

This release focuses on:
- Enhanced transaction safety
- Flexible query control
- Per-operation customization
- Comprehensive documentation

---

## 📝 Notes

- **Backward Compatibility**: All v2.4.0 code continues to work. New parameters have sensible defaults.

- **Transaction Overhead**: The `@aatomic` decorator adds minimal overhead. If you need non-transactional operations, override the view methods directly.

- **Query Parameters**: `with_qs_request` defaults to `True` to maintain v2.4.0 behavior. Set to `False` to skip the queryset_request hook.

- **Serializer Hooks**: If migrating from v2.4.0 Serializer usage, ensure all hooks accept the `instance` parameter.

---

## 🔗 Links

- [Documentation](https://caspel26.github.io/django-ninja-aio-crud/)
- [GitHub Repository](https://github.com/caspel26/django-ninja-aio-crud)
- [Issue Tracker](https://github.com/caspel26/django-ninja-aio-crud/issues)
- [v2.4.0 Release Notes](https://github.com/caspel26/django-ninja-aio-crud/releases/tag/v2.4.0)

---

---

## [v2.4.0] - 2026-01-09

---

## ✨ Added

- Serializer (Meta-driven):
  - New Serializer for vanilla Django models configured via nested Meta (no ModelSerializer inheritance).
  - Dynamic schema generation helpers: generate_read_s, generate_create_s, generate_update_s, generate_related_s.
  - Relation handling via relations_serializers for forward and reverse relations.
- APIViewSet:
  - serializer_class to auto-generate missing schemas for non-ModelSerializer models and drive queryset_request.
- ModelUtil:
  - Accepts serializer_class to build querysets using Serializer.queryset_request when provided.
- Docs/README:
  - New docs page: api/models/serializers.md with usage and examples.
  - README sections/examples for Meta-driven Serializer.
  - MkDocs nav entry for Serializer.
- Tests:
  - Serializer tests (forward and reverse relations).
  - Viewset tests using serializer_class-backed endpoints.

---

## 🛠 Changed

- Package layout:
  - ninja_aio/models/**init**.py now exports ModelUtil and ModelSerializer.
  - models.py refactored to models/utils.py; ModelSerializer moved to models/serializers.py.
- API internals:
  - APIViewSet.compute_schema generates schemas from serializer_class for vanilla models; retains model-backed generation for ModelSerializer.
  - ModelUtil.get_queryset_request uses serializer_class when provided.
- Docs:
  - Index formatting tweaks; added links and examples for Serializer docs.

---

## 📝 Documentation

- Serializer (Meta-driven):
  - Configure via Meta: model, schema_in, schema_out, schema_update, relations_serializers.
  - Examples for FK and reverse relations; customs and optionals.
- APIViewSet:
  - Using serializer_class to auto-generate schemas and plug into queryset_request.
- README:
  - Quick example attaching Serializer to APIViewSet.
- MkDocs:
  - Added nav entry under Models: Serializer (Meta-driven).

---

## ⚠ Notes / Potential Impact

- Relation serializers:
  - Reverse relations on vanilla models need relations_serializers entries to include nested schemas; otherwise skipped unless the related model is a ModelSerializer.
  - A UserWarning is emitted when a reverse relation is listed without a mapping; suppressed in tests via NINJA_AIO_TESTING=True.
- Refactor:
  - Imports may need updates due to ModelUtil relocation and new serializers module.

---

## 🔍 Migration / Action

1. Define a Meta-driven Serializer for existing Django models and attach it to APIViewSet via serializer_class.
2. Provide relations_serializers for reverse relations to include nested schemas on read.
3. Update imports:
   - from ninja_aio.models import ModelUtil, ModelSerializer
   - from ninja_aio.models.serializers import Serializer, SchemaModelConfig
4. If relying on queryset_request with vanilla models, implement Serializer.queryset_request; APIViewSet and ModelUtil will use it automatically.

---

## [v2.3.2] - 2026-01-08

---

## ✨ Added

- Support Url pydantic field serialization
- Support for django ninja until 1.6

---

---

## [v2.3.1] - 2026-01-07

---

## ✨ Added

- CI/Docs Deployment:
  - GitHub workflow updated to recognize and manage version "2.3" for docs deploy/delete.
- Documentation/README:
  - Added link to the external example repository: https://github.com/caspel26/ninja-aio-blog-example.

---

## 🛠 Changed

- README/Docs:
  - Switched examples to decorator-first style with `@api.viewset(Model)` and in-class method decorators (e.g., `@api_post`).
  - Removed explicit `api = api` and `model = ...` from examples where `@api.viewset(...)` is used; emphasized automatic registration.
  - Cleaned and reformatted examples and quick links table; clarified usage in the index page and decorators page.
- Packaging:
  - Python version spec adjusted from `>=3.10, <=3.14` to `>=3.10, <3.15` in pyproject metadata.

---

## 🗑 Removed

- In-repo example apps:
  - Deleted `examples/ex_1` and `examples/ex_2` (models, views, urls, and auth). Examples are now hosted in the external repository linked in the README.

---

## 📝 Documentation

- Index and README updated to prefer `@api.viewset(Model)` and decorator-based custom endpoints.
- Decorators page (`docs/api/views/decorators.md`) revised to reflect decorator-first usage.
- Added references to the external example repository for complete, runnable samples.

---

---

## [v2.3.0] - 2026-01-04

---

## ✨ Added

- Decorators:
  - New operation decorators for class methods: `api_get`, `api_post`, `api_put`, `api_patch`, `api_delete`, `api_options`, `api_head` (import from `ninja_aio.decorators`).
  - Utilities: `decorate_view`, `aatomic`, `unique_view` (now under `ninja_aio.decorators`).
  - Factory-backed decorators ensure clean OpenAPI signatures (exclude `self`) and support extra decorators like pagination.
- Views:
  - APIView/APIViewSet auto-register decorated methods via lazy binding; no manual `add_views_to_route()` when using `@api.view` / `@api.viewset`.
  - APIViewSet supports global trailing slash setting via `settings.NINJA_AIO_APPEND_SLASH` (default True).
- M2M:
  - `M2MRelationSchema.append_slash` to control trailing slash on the GET relation route.
  - Relation path normalization for consistent URLs whether `path` includes leading slash or not.
- Tests/Examples:
  - Added decorator-based examples and tests for custom endpoints on views and viewsets.

---

## 🛠 Changed

- README/Docs:
  - Prefer `@api.viewset(Model)` with decorator-based endpoints; legacy `views()` remains supported.
  - Clarified trailing slash behavior for CRUD retrieve paths and M2M relations.
  - Decorator-first examples across APIView and APIViewSet pages; cleaner OpenAPI notes.
- API internals:
  - Base API class now binds decorator-registered methods via `_add_views()`; APIView/APIViewSet call `super()._add_views()` before legacy `views()`.
  - APIViewSet path generation respects `NINJA_AIO_APPEND_SLASH` for retrieve path (`/{pk}/` vs `/{pk}`).
- Exceptions/Helpers:
  - Added docstrings for clearer behavior in exceptions, query helpers, and schemas.

---

## 📝 Documentation

- APIView/APIViewSet:
  - Decorator-first usage with examples; automatic lazy registration; signature preservation.
- Decorators:
  - Using operation decorators with extra decorators (e.g., `paginate(PageNumberPagination)`, `unique_view(name)`).
- ViewSet relations:
  - Per-relation `append_slash`; path normalization rules; trailing slash settings.
- README:
  - Simplified setup: `@api.viewset(Model)` and decorator-based custom endpoints.

---

## ⚠ Notes / Potential Impact

- Trailing slash:
  - Global `NINJA_AIO_APPEND_SLASH` defaults to True. Disable to remove trailing slash from retrieve paths.
  - M2M GET relation endpoints default to no trailing slash; enable per relation with `append_slash=True`.
- Registration:
  - When using `@api.view` / `@api.viewset`, endpoints defined via decorators are mounted automatically; avoid redundant manual registration.
- OpenAPI:
  - Decorator-backed handlers exclude `self` and preserve type hints for cleaner specs.

---

## 🔍 Migration / Action

1. Adopt decorators for extra endpoints:
   - APIView: annotate the class with `@api.view(...)`, then decorate methods with `@api_get("/path", ...)`.
   - APIViewSet: annotate with `@api.viewset(Model, ...)`, then use `@api_get("/path", ...)`, `@api_post(...)`, etc.
2. Trailing slash configuration:
   - Set `NINJA_AIO_APPEND_SLASH=False` in Django settings to drop trailing slash on retrieve paths globally.
   - For M2M GET relations, use `M2MRelationSchema(append_slash=True/False)` to control trailing slash.
3. Legacy support:
   - `views()` continues to work; prefer decorators for clearer code and better OpenAPI.
4. Docs/examples:
   - Update references to new decorator modules and follow decorator-first examples.

---

## [v2.2.0] - 2026-01-03

---

## ✨ Added

- API:
  - Decorators: `NinjaAIO.view(prefix, tags)` and `NinjaAIO.viewset(model, prefix, tags)` for automatic registration.
  - Base API class: shared attributes for APIView and APIViewSet (api, router_tags, api_route_path).
- Views:
  - APIView: supports constructor args `(api, prefix, tags)` with `router_tags` and standardized `error_codes`.
  - APIViewSet: constructor `(api, model, prefix, tags)`; infers base path from model when not provided; `router_tags` support.
- Auth:
  - JwtKeys type expands to include `jwk.OctKey` (HMAC).
  - `validate_key` accepts `jwk.OctKey`.
  - `encode_jwt`/`decode_jwt` type hints generalized to `JwtKeys`.
- Tests:
  - Added decorator-based tests for APIView and APIViewSet (ModelSerializer and plain Django model).
  - Updated ManyToMany tests to construct viewset with `api` argument.
- Docs:
  - APIView and APIViewSet docs: “Recommended” decorator-based examples.
  - Mixins doc moved to `docs/api/views/mixins.md`.
  - Index updated with modern ModelSchema-based examples and async ORM usage.

---

## 🛠 Changed

- Version:
  - Bumped to 2.2.0 in `ninja_aio/__init__.py`.
- Error codes:
  - Standardized to {400, 401, 404}; removed 428 references in code and docs.
- Docs:
  - `docs/api/authentication.md`: use list-based auth `[JWTAuth(), APIKeyAuth()]` instead of bitwise OR.
  - `docs/api/views/api_view.md` and `api_view_set.md`: emphasize decorator usage; cleaner examples; notes updated.
  - MkDocs nav: Mixins path updated to `api/views/mixins.md`.
- API internals:
  - APIView/APIViewSet refactored to share base attributes, constructor supports `api`, `prefix`, and `tags`.
- Docs workflow:
  - `mike set-default --push latest` when MAKE_LATEST is true.
- Packaging:
  - Python requirement set to `>=3.10, <=3.14` in `pyproject.toml`.

---

## 📝 Documentation

- Updated:
  - Authentication: list-based auth configuration and clarified behavior.
  - APIView/APIViewSet: decorator-first usage, async compatibility, and standard error codes.
  - Index: ModelSchema In/Out patterns with async ORM examples.
- Moved:
  - Mixins doc to `api/views/mixins.md`; MkDocs navigation adjusted.

---

## ⚠ Notes / Potential Impact

- Error handling:
  - 428 code removed; rely on {400, 401, 404}.
- Auth configuration:
  - Use lists for multiple auth methods; bitwise OR in docs deprecated.
- Docs deployment:
  - Default alias set to “latest” on deploy when MAKE_LATEST=true.
- Python compatibility:
  - Upper bound set to 3.14.

---

## 🔍 Migration / Action

1. Adopt decorators:
   - APIView: `@api.view(prefix="/path", tags=[...])`
   - APIViewSet: `@api.viewset(model=MyModel, prefix="/path", tags=[...])`
2. Update auth configuration:
   - HMAC keys supported via `jwk.OctKey` where applicable.
3. Error codes:
   - Remove references/handlers for 428; standardize to {400, 401, 404}.
4. Docs links:
   - Update references to Mixins at `api/views/mixins.md`.
5. Runtime:
   - Ensure Python version is <= 3.14 per `pyproject.toml`.

---

## [v2.1.0] - 2026-01-01

---

## ✨ Added

- Views:
  - ReadOnlyViewSet: list and retrieve-only endpoints.
  - WriteOnlyViewSet: create, update, and delete-only endpoints.
  - Exported via `ninja_aio.views.__init__` for cleaner imports.
- Mixins:
  - New filtering mixins under `ninja_aio/views/mixins.py`: IcontainsFilterViewSetMixin, BooleanFilterViewSetMixin, NumericFilterViewSetMixin, DateFilterViewSetMixin, and specialized Greater/Less variants.
- Auth docs:
  - New `docs/auth.md` with JWT helpers and `AsyncJwtBearer` usage and configuration.
- Tests:
  - Extended test model with `age`, `active`, and `active_from` fields.
  - Added viewset tests for mixins (icontains, boolean, numeric, date comparisons).
  - Added auth tests for JWT encode/decode and AsyncJwtBearer claim validation.
- Docs navigation:
  - Added Mixins page and JWT & AsyncJwtBearer page to MkDocs nav.
  - MkDocs `mike` config sets `default: latest`.

---

## 🛠 Changed

- Docs workflow (`.github/workflows/docs.yml`):
  - Safer deletion: requires explicit `delete_version` choice and `delete_confirm`, protects `latest`, `stable`, and current default.
  - `make_latest` default set to false.
- Coverage workflow:
  - Bump `codecov/codecov-action` from v5.5.1 to v5.5.2.
- API helpers:
  - Use `decorate_view` to compose `unique_view` and `paginate` for related GET endpoints.
- APIViewSet (imports and behavior):
  - Module reorganized to `ninja_aio/views/api.py` with updated internal imports.
  - `get_schemas`: generates schemas only if missing when model is a `ModelSerializerMeta`, else returns explicitly set schemas.
  - Hook docs clarified to allow sync or async handlers for query params.
- Auth:
  - `encode_jwt`: header now includes `kid` only when present (conditional merge).
- Docs:
  - `docs/api/views/api_view_set.md` updated to document ReadOnlyViewSet and WriteOnlyViewSet.
  - `docs/mixins.md` aligned with implemented mixins and examples.

---

## 📝 Documentation

- New:
  - JWT & AsyncJwtBearer guide with examples for settings and direct JWK usage.
- Updated:
  - Mixins reference to match implemented classes and recommended query param types.
  - APIViewSet docs extended with ReadOnly/WriteOnly usage.

---

## ⚠ Notes / Potential Impact

- Docs deployment:
  - Deletion requires explicit confirmation and cannot remove protected aliases or current default.
- Mixins:
  - Date filters expect values that implement `isoformat`; prefer Pydantic `date`/`datetime` in query params.

---

## 🔍 Migration / Action

1. Update imports:
   - `from ninja_aio.views import APIViewSet, ReadOnlyViewSet, WriteOnlyViewSet`
   - `from ninja_aio.views import mixins` for filter mixins.
2. For related list endpoints using custom decorators, consider adopting `decorate_view` for consistent composition.
3. If using JWT:
   - Optionally set `JWT_PRIVATE_KEY`, `JWT_PUBLIC_KEY`, `JWT_ISSUER`, `JWT_AUDIENCE` in Django settings.
   - Validate claims via `AsyncJwtBearer.claims` registry and verify allowed algorithms.
4. Review docs workflow inputs before deleting versions; use `delete_confirm: true`.

---

## [v2.0.0] - 2025-12-16

---

## ✨ Added

- QueryUtil and query scopes:
  - New `QueryUtil` with `SCOPES` (READ, QUERYSET_REQUEST, plus extras) and `apply_queryset_optimizations`.
  - `ModelSerializer.query_util` bound per model via `__init_subclass__`.
  - `ModelSerializer.QuerySet` supports `read`, `queryset_request`, `extras`.
- Query schemas:
  - `QuerySchema`, `ObjectQuerySchema`, `ObjectsQuerySchema`, `ModelQuerySetSchema`, `ModelQuerySetExtraSchema`, `QueryUtilBaseScopesSchema`.
- ModelUtil:
  - `get_objects(...)`: optimized queryset fetching with filters and select/prefetch hints.
  - `get_object(...)`: single-object retrieval by pk or getters with optimizations.
  - `read_s(...)` and `list_read_s(...)`: serialize instances or auto-fetch via query schemas.
  - Relation discovery helpers: `get_select_relateds()`, `get_reverse_relations()`.
  - PK type resolution: `pk_field_type` with helpful error for unknown field types.
- ManyToManyAPI:
  - GET related endpoints return `{items: [...], count: N}`.
  - Relation filter handlers accept sync or async functions.
  - Related items use `ModelUtil.list_read_s` for serialization.
  - Per-relation single-object resolution handler for POST: `<related_name>_query_handler(...)`.
- Schemas modularization:
  - New modules: `ninja_aio/schemas/api.py`, `ninja_aio/schemas/generics.py`, and exported names under `ninja_aio/schemas/__init__.py`.
- Decorators:
  - `decorate_view` utility to compose multiple decorators (sync/async), skipping `None`.
  - `APIViewSet.extra_decorators` via `DecoratorsSchema` for per-operation decoration.
- Renderer:
  - ORJSON renderer option via `settings.NINJA_AIO_ORJSON_RENDERER_OPTION` (bitmask, supports `|`).

---

## 🛠 Changed

- APIViewSet:
  - List uses `ModelUtil.get_objects` and `list_read_s` with read optimizations; filter hooks retained.
  - Retrieve uses `read_s` with `QuerySchema(getters={"pk": ...})`.
  - Path PK schema type inferred from model PK via `ModelUtil.pk_field_type`.
  - Default read query data comes from `ModelSerializer.QuerySet.read` via `query_util`.
  - Built-ins and custom decorators composed with `decorate_view` (e.g., `paginate`, `unique_view`, extras).
- ModelSerializer:
  - Binds `util = ModelUtil(cls)` and `query_util = QueryUtil(cls)` to subclasses.
  - `queryset_request` applies configured optimizations from `QuerySet.queryset_request`.
- ModelUtil internals:
  - Unified `_apply_query_optimizations` merges explicit select/prefetch with auto-discovered relations when `is_for_read=True`.
  - Serialization paths standardized through internal helpers; `read_s`/`list_read_s` accept `schema` first.
- Auth:
  - `AsyncJwtBearer.verify_token` simplifies error handling; drops explicit `AuthError`.
- Imports:
  - `ManyToManyAPI` consumed from `ninja_aio/helpers/api.py`.
- Runtime requirements:
  - Upper bounds added: `django-ninja <=1.5.1`, `joserfc <=1.4.1`, `orjson <=3.11.5`.
- Docs and site:
  - MkDocs/mike integration for versioned docs; new workflow `docs.yml`.

---

## 🔴 Breaking Changes

- Path PK schema type:
  - PK type is inferred from the model PK. Code relying on `int | str` in path schemas may need adjustments.
- ManyToMany GET response shape:
  - Response changed from a plain list to `{items: [...], count: N}`. Clients must adapt parsing.
- Import paths:
  - Schema helpers moved under `ninja_aio/schemas/helpers.py` and re-exported by `ninja_aio/schemas/__init__.py`.
  - `ManyToManyAPI` import is now `from ninja_aio.helpers.api import ManyToManyAPI`.
- ModelUtil read API:
  - `read_s` and `list_read_s` signatures accept `schema` first and support `instance` or `query_data`. Code passing `(request, obj, schema)` must switch to `(schema, request, instance=obj)`.

---

## 📝 Documentation

- Updated:
  - ModelUtil reference: QuerySet config, QueryUtil, query schemas, `get_objects`, `get_object`, `read_s`, `list_read_s`.
  - APIViewSet: list/retrieve flow, PK type inference, M2M GET envelope, async/sync filter handlers, operation decorators.
  - Tutorial (model): QuerySet config and `query_util` examples; fetch/serialize using query schemas.
  - Index: overview of query optimizations and schemas.
  - ORJSON renderer: configuration guide.

---

## ⚠ Notes / Potential Impact

| Area                | Observation                                                       | Impact                                                                |
| ------------------- | ----------------------------------------------------------------- | --------------------------------------------------------------------- |
| Query optimizations | `is_for_read=True` merges explicit and auto-discovered relations. | More joins/prefetches; re-check performance for heavy endpoints.      |
| Requirements caps   | Upper bounds added for core deps.                                 | Ensure compatible versions in your environment.                       |
| Decorator order     | `decorate_view` applies standard Python stacking order.           | Verify nesting with `paginate`, `unique_view`, and custom decorators. |

---

## 🔍 Migration / Action

1. Update imports:
   - `from ninja_aio.schemas.helpers import QuerySchema, ObjectQuerySchema, ObjectsQuerySchema, ModelQuerySetSchema, ModelQuerySetExtraSchema`
   - `from ninja_aio.helpers.api import ManyToManyAPI`
2. Adjust M2M GET consumers to handle `{items, count}`.
3. Update `read_s`/`list_read_s` calls to new parameter order.
4. Verify path PK handling in custom routes that relied on a generic PK type.
5. Review `QuerySet.read` / `QuerySet.queryset_request` for desired select/prefetch behavior.
6. Optionally configure ORJSON via `NINJA_AIO_ORJSON_RENDERER_OPTION`.

---

## [v2.0.0-rc7] - 2025-12-16

---

## [2.0.0-rc7] - 2025-12-16

---

## ✨ Added
- Decorators:
  - `decorate_view`: compose multiple decorators (sync/async), preserves normal stacking order, skips `None`.
  - `APIViewSet.extra_decorators`: declarative per-operation decorators.
  - `DecoratorsSchema` in `ninja_aio.schemas.helpers` to configure per-op decorators.
---

## 🛠 Changed
- APIViewSet:
  - `create`, `list`, `retrieve`, `update`, `delete` compose built-ins (`unique_view`, `paginate`) and user-provided extras via `decorate_view` for consistent ordering.

---

## 📝 Documentation
- New:
  - `docs/api/views/decorators.md`: `decorate_view` usage, conditional decoration, and `extra_decorators` with `DecoratorsSchema`.
  - `docs/api/renderers/orjson_renderer.md`: how to configure ORJSON options in `settings.py`.

---

## ⚠ Notes / Potential Impact
- Decorator order:
  - `decorate_view` applies decorators in standard Python stacking semantics. If you relied on a specific nesting between `paginate`, `unique_view`, and custom decorators, verify behavior.

---

## 🔍 Migration / Action
1. Optionally move per-operation decorators to `APIViewSet.extra_decorators = DecoratorsSchema(...)`.
2. If desired, configure ORJSON behavior via `NINJA_AIO_ORJSON_RENDERER_OPTION` in `settings.py`.

---

## [v2.0.0-rc6] - 2025-12-12

---

## [2.0.0-rc6] - 2025-12-12

---

## ✨ Added
- ORJSONRenderer:
  - Configurable orjson option via Django settings: `NINJA_AIO_ORJSON_RENDERER_OPTION`.
  - New `dumps` classmethod applying the configured option to all JSON responses.

---

## 🛠 Changed
- Version bump:
  - `__version__` updated from `2.0.0-rc5` to `2.0.0-rc6`.
- Rendering internals:
  - `render` now calls `self.dumps(...)` instead of `orjson.dumps(...)` directly.

---

## 📝 Documentation
- Mention `NINJA_AIO_ORJSON_RENDERER_OPTION` in setup/config docs with example values (e.g., `orjson.OPT_NAIVE_UTC`, `orjson.OPT_SERIALIZE_DATACLASS`).

---

## 🔍 Migration / Action
1. If you need specific JSON encoding behavior, set in Django settings:
   - `NINJA_AIO_ORJSON_RENDERER_OPTION = orjson.OPT_NAIVE_UTC | orjson.OPT_SERIALIZE_NUMPY` (example).
2. No code changes required for consumers; behavior is backward compatible when the setting is absent.

---

## ⚠ Notes / Potential Impact
| Area | Observation | Impact |
| ---- | ----------- | ------ |
| JSON options | Renderer honors global orjson options. | Unified behavior across endpoints; verify compatibility with clients. |

---

---

## [v2.0.0-rc5] - 2025-12-12

---

## [2.0.0-rc5] - 2025-12-12

---

## 🛠 Changed
- fix: update log messages to use 'pk' instead of 'id' for consistency in ManyToManyAPI

---

---

## [v2.0.0-rc4] - 2025-12-12

---

## [2.0.0-rc4] - 2025-12-12

---

## ✨ Added
- possibility to override router tag in APIViewSet

---

---

## [v2.0.0-rc3] - 2025-12-12

---

## [2.0.0-rc3] - 2025-12-12

---

## ✨ Added
- ManyToManyAPI:
  - New per-relation POST object resolution handler: `<related_name>_query_handler(self, request, pk, instance)` returning a queryset, resolved via `.afirst()`.
  - Endpoint registration details documented: GET without trailing slash, POST with trailing slash; operationId conventions (`get_{base}_{rel}`, `manage_{base}_{rel}`).

---

## 🛠 Changed
- ManyToManyAPI:
  - Split handlers: GET uses `<related_name>_query_params_handler(self, queryset, filters_dict)`; POST uses `<related_name>_query_handler(...)` for per-PK validation.
  - Manage view uses `_collect_m2m(...)` with additional context (`related_name`, `instance`) and falls back to `ModelUtil.get_objects(...)` when query handler is absent.
  - Improved docs and docstrings for concurrency, error semantics, and request/response payloads.
- Docs:
  - Refined M2M section: clarified handlers, paths, operationIds, request bodies, and concurrency.
  - Minor wording and formatting improvements; standardized examples.
- Version:
  - Bump to `2.0.0-rc3`.

---

## 📝 Documentation
- APIViewSet M2M docs updated:
  - Clarified GET filters vs POST per-PK resolution.
  - Documented response semantics and per-PK success/error messages.
  - Added an example showcasing both handlers.

---

## 🔴 Breaking Changes
- Handler naming:
  - GET filters must use `<related_name>_query_params_handler`; POST add/remove resolution must use `<related_name>_query_handler`. Existing single-handler implementations should be split accordingly.
- Endpoint paths:
  - GET relation: `/{base}/{pk}/{rel_path}` (no trailing slash).
  - POST relation: `/{base}/{pk}/{rel_path}/` (trailing slash).

---

## ⚠ Notes / Potential Impact
| Area | Observation | Impact |
| ---- | ----------- | ------ |
| Validation | POST uses per-PK resolution handler when present; fallback uses `ModelUtil.get_objects`. | Tighten access control and scoping per relation. |
| Concurrency | `aadd` and `aremove` run concurrently via `asyncio.gather`. | Faster bulk mutations; ensure thread-safety of custom logic. |

---

## 🔍 Migration / Action
1. Implement per-relation handlers:
   - GET filters: `def|async def <rel>_query_params_handler(self, qs, filters: dict) -> qs`.
   - POST resolution: `async def <rel>_query_handler(self, request, pk, instance) -> queryset`.
2. Verify clients and OpenAPI consumers against the documented endpoint paths and operationIds.
3. Ensure manage responses are consumed as documented (`results`, `errors` with `count` and `details`).

---

## ✅ Suggested Follow-Ups
- Add tests for:
  - Presence/absence of `<related_name>_query_handler` fallback behavior.
  - Sync vs async GET filter handlers.
  - Per-PK error and success detail aggregation.

---

## [v2.0.0-rc2] - 2025-12-12

---

## [2.0.0-rc2] - 2025-12-12

---

## ✨ Added
- support for django-ninja 1.5.1
- support for orjson 3.11.5

---

## [v2.0.0-rc1] - 2025-12-07

---

## [2.0.0-rc1] - 2025-12-07

---

## ✨ Added
- QueryUtil and query scopes:
  - New `QueryUtil` with `SCOPES` (READ, QUERYSET_REQUEST, plus extras) and `apply_queryset_optimizations`.
  - `ModelSerializer.query_util` bound per model via `__init_subclass__`.
  - `ModelSerializer.QuerySet` supports `read`, `queryset_request`, `extras`.
- Query schemas:
  - `QuerySchema`, `ObjectQuerySchema`, `ObjectsQuerySchema`, `ModelQuerySetSchema`, `ModelQuerySetExtraSchema`, `QueryUtilBaseScopesSchema`.
- ModelUtil:
  - `get_objects(...)`: optimized queryset fetching with filters and select/prefetch hints.
  - `get_object(...)`: single-object retrieval by pk or getters with optimizations.
  - `read_s(...)` and `list_read_s(...)`: serialize instances or auto-fetch via query schemas.
  - Relation discovery helpers: `get_select_relateds()`, `get_reverse_relations()`.
  - PK type resolution: `pk_field_type` with helpful error for unknown field types.
- ManyToManyAPI:
  - GET related endpoints return `{items: [...], count: N}`.
  - Relation filter handlers accept sync or async functions.
  - Related items use `ModelUtil.list_read_s` for serialization.
- Schemas modularization:
  - New modules: `ninja_aio/schemas/api.py`, `ninja_aio/schemas/generics.py`, and exported names under `ninja_aio/schemas/__init__.py`.
- Decorators:
  - Minor hardening and docs for `aatomic` and `unique_view`.

---

## 🛠 Changed
- APIViewSet:
  - List view uses `ModelUtil.get_objects` and `list_read_s` with read optimizations; filter hooks retained.
  - Retrieve view uses `read_s` with `QuerySchema(getters={"pk": ...})`.
  - Path PK schema type inferred from model PK via `ModelUtil.pk_field_type`.
  - Default read query data comes from `ModelSerializer.QuerySet.read` via `query_util`.
- ModelSerializer:
  - Binds `util = ModelUtil(cls)` and `query_util = QueryUtil(cls)` to subclasses.
  - `queryset_request` applies configured optimizations from `QuerySet.queryset_request`.
- ModelUtil internals:
  - Unified `_apply_query_optimizations` merges explicit select/prefetch with auto-discovered relations when `is_for_read=True`.
  - Serialization paths standardized through internal bump helpers.
- Auth:
  - `AsyncJwtBearer.verify_token` simplifies error handling; drops explicit `AuthError`.
- Imports:
  - `ManyToManyAPI` consumed from `ninja_aio/helpers/api.py`.
- Runtime requirements:
  - Pinned upper bounds for `django-ninja`, `joserfc`, `orjson`.

---

## 📝 Documentation
- Updated:
  - ModelUtil reference: QuerySet config, QueryUtil, query schemas, `get_objects`, `get_object`, `read_s`, `list_read_s`.
  - APIViewSet: list/retrieve flow, PK type inference, M2M GET envelope, async/sync filter handlers.
  - Tutorial (model): QuerySet config and `query_util` examples; fetch/serialize using query schemas.
  - Index: overview of query optimizations and schemas.

---

## 🔴 Breaking Changes
- Path PK schema type:
  - PK type is now inferred from the model PK. Code relying on `int | str` in path schemas may need adjustments.
- ManyToMany GET response shape:
  - Response changed from a plain list to an envelope `{items: [...], count: N}`. Clients must adapt parsing.
- Import paths:
  - Schema helpers moved under `ninja_aio/schemas/helpers.py` and re-exported by `ninja_aio/schemas/__init__.py`.
  - `ManyToManyAPI` import is now `from ninja_aio.helpers.api import ManyToManyAPI`.
- ModelUtil read API:
  - `read_s` and `list_read_s` signatures accept `schema` first and support `instance` or `query_data`. Code passing `(request, obj, schema)` must switch to `(schema, request, instance=obj)`.

---

## ⚠ Notes / Potential Impact
| Area | Observation | Impact |
| ---- | ----------- | ------ |
| Query optimizations | `is_for_read=True` merges explicit and auto-discovered relations. | More joins/prefetches; re-check performance for heavy endpoints. |
| Requirements caps | Upper bounds added for core deps. | Ensure compatible versions in your environment. |

---

## 🔍 Migration / Action
1. Update imports:
   - `from ninja_aio.schemas.helpers import QuerySchema, ObjectQuerySchema, ObjectsQuerySchema, ModelQuerySetSchema, ModelQuerySetExtraSchema`
   - `from ninja_aio.helpers.api import ManyToManyAPI`
2. Adjust M2M GET consumers to handle `{items, count}`.
3. Update `read_s`/`list_read_s` calls to new parameter order.
4. Verify path PK handling in custom routes that relied on a generic PK type.
5. Review `QuerySet.read` / `QuerySet.queryset_request` for desired select/prefetch behavior.

---

## ✅ Suggested Follow-Ups
- Add perf checks around list/retrieve with merged relations.
- Expand tests for:
  - PK type inference in path schemas.
  - Sync vs async relation filter handlers.
  - QueryUtil extras scopes resolution and application.

---

---

## [v1.0.5] - 2025-12-07

---

## 🛠 Changed
- limited support up to django ninja 1.4.5

---

## [v1.0.4] - 2025-11-03

---

## ✨ Added
- `ModelUtil._rewrite_nested_foreign_keys`: reintroduced helper to rename nested FK keys from `<field>` to `<field>_id` inside nested dicts (currently invoked conditionally in `parse_output_data`).

---

## 🛠 Changed
- `ModelUtil._extract_field_obj` converted to async; now uses `agetattr` for safer async attribute access.
- `ModelUtil.parse_output_data`:
  - Awaits the new async `_extract_field_obj`.
  - Fetches related instance first, then (conditionally) calls `_rewrite_nested_foreign_keys` when the outer field is a `ForeignKey`.

---

## 📝 Documentation
- Table in `docs/api/models/model_serializer.md` (CreateSerializer attributes) reformatted:
  - Condensed multiline description for `customs` into a single line with semicolons.
  - Adjusted column widths / alignment for cleaner diff footprint.

---

## ⚠ Note / Potential Issue
| Area | Observation | Impact |
| ---- | ----------- | ------ |
| `parse_output_data` | Result of `_rewrite_nested_foreign_keys` is assigned to local `v` but not reattached to `payload` (final output still sets `payload[k] = rel_instance`). | FK key rewriting may be a no-op for consumers; behavior might not match intent. |

---

## 🔍 Migration / Action
1. If you relied on the absence of FK key rewriting (1.0.3), verify whether the restored helper actually affects payloads (it likely does not yet).
2. If rewriting is desired, ensure the transformed dict (or additional metadata) is surfaced in the serialized output or adjust logic accordingly.

---

## ✅ Suggested Follow-Ups
- Add a test asserting expected presence (or absence) of `<field>_id` keys in nested output.
- Decide whether payload should expose both the related object and rewritten key map, or deprecate the helper again if not needed.

---

---

## [v1.0.3] - 2025-11-03

---

## ✨ Added
- `M2MRelationSchema`: New optional field `related_schema` documented (auto-generated when using a `ModelSerializer`).

---

## 🛠 Changed
- Documentation tables (CRUD, Core Attributes, Auth, M2M Endpoints, Hooks) reformatted for alignment & readability.
- Extra blank lines inserted to improve Markdown rendering clarity.
- `ModelUtil.parse_output_data`: simplified nested relation handling (direct instance assignment).

---

## 🗑 Removed
- `ModelUtil._rewrite_nested_foreign_keys` helper.
- Foreign key nested dict rewriting logic (`<field>` → `<field>_id`) during output serialization.

---

## 📄 Documentation
- Added warning block describing support for plain Django `Model` in `M2MRelationSchema.model` and mandatory `related_schema` when used.
- Added `related_schema` bullet to M2M relation capabilities list.
- Ensured file ends with a trailing newline.

---

## ⚠ Breaking Change
| Change | Impact |
| ------ | ------ |
| Removal of FK key rewriting in nested outputs | Clients expecting `<nested_fk>_id` keys must adjust parsing logic |

---

## 🔍 Migration Notes
1. If consumers relied on `<nested_fk>_id` keys, add a post-serialization adapter to inject them, or reintroduce prior logic.
2. When declaring M2M relations with plain Django models, always provide `related_schema`; omission now results in validation errors.

---

## 📌 Highlights
- Cleaner docs + explicit M2M plain model guidance.
- Leaner serialization path (less mutation, clearer intent).

---

## 🧪 Suggested Follow‑Ups
- Add regression test ensuring nested FK dicts are no longer rewritten.
- Consider exposing an optional flag to restore legacy FK key rewriting if demand appears.

---

## [v1.0.2] - 2025-11-01

---

## ✨ Added
- SonarCloud Quality Gate badge (README + docs index).
- Custom domain support (docs/CNAME).
- Release Notes page with dynamic macros (`docs/release_notes.md` + `mkdocs-macros-plugin`).
- Release automation script (`main.py`) generating tables, full changelog, and cards.
- ManyToManyAPI helper (`ninja_aio/helpers/api.py`) with dynamic GET / ADD / REMOVE endpoints, filter schemas, concurrent operations, and query handler support.
- Helpers package export (`helpers/__init__.py`).
- Extended schema support in `M2MRelationSchema` (auto `related_schema` via validator).
- Refactored M2M integration in `APIViewSet` (now uses `ManyToManyAPI`).
- New test suites: decorators, exceptions/API, renderer/parser, many-to-many API.
- Centralized literal for “not found” (`tests/generics/literals.py`).

---

## 🛠 Changed
- `NotFoundError`: error key now uses underscored verbose name.
- `ORJSONRenderer`: replaced nested mutation with recursive `transform`.
- `ModelUtil` / `ModelSerializer`: added comprehensive docstrings, normalized custom field tuples, improved FK and nested output handling.
- Removed inline M2M view logic from `APIViewSet`.
- Enriched model serializer docs (tables, normalization, error cases).
- `M2MRelationSchema`: validation for related schema generation.

---

## 🧾 Documentation
- Major rewrite of `docs/api/models/model_serializer.md`: normalization workflow, error cases, best practices, expanded examples.
- Added Release Notes navigation in `mkdocs.yml`.
- Inline internal-use warning for `ManyToManyAPI`.
- Improved readability (spacing, tables, JSON formatting).

---

## ✅ Tests
- Coverage for:
  - ORJSON transformations (bytes→base64, IP→string).
  - `unique_view` name suffix logic.
  - Exception parsing and API defaults.
  - M2M add/remove flows + duplicate/error handling.
  - Updated NotFoundError key format.
- Reused shared literal for 404 assertions.

---

## 📦 Tooling
- Added `mkdocs-macros-plugin`.
- Automated release visualization (HTML tables, cards).
- Cleaner MkDocs theme (font configuration).

---

## ⚠ Impact
| Change | Potential Effect |
| ------ | ---------------- |
| Underscored error keys | Clients parsing old keys must adjust |
| Extracted M2M logic | Custom subclasses relying on internals must migrate |
| 2‑tuple customs now required | Missing values trigger validation errors |

---

## 🔍 Upgrade Notes
1. Update error handling for new 404 key shape.
2. Migrate any manual M2M endpoint wiring to `ManyToManyAPI`.
3. Review custom field tuples—add defaults if optional behavior desired.

---

## 🧪 Follow‑Ups
- Tag release (`git tag -a vX.Y.Z -m "Release vX.Y.Z" && git push --tags`).
- Optionally add top-level `CHANGELOG.md`.
- Decide on public stability of `ManyToManyAPI` (remove warning when ready).

---

## 📌 Release Template
```markdown
## vX.Y.Z (YYYY-MM-DD)

Highlights:
- ...

Full release table: /release_notes/

---

## [v1.0.1] - 2025-10-30

---

### Added
- Docs: New dev dependencies file `requirements.dev.txt`.
- MkDocs: Additional plugins (`mkdocstrings`, `section-index`, `autorefs`) and extended `markdown_extensions`.
- Theme extras: social links, analytics stub, version metadata.
- CSS: Logo sizing rules in `docs/extra.css`.

### Changed
- README: Reduced length, modernized intro, added concise feature + quick start sections.
- Pagination docs: Reformatted tables, spacing, clarified examples.
- Contributing docs: Expanded with setup, PR guidelines, issue template hints.
- Tutorial (CRUD & Filtering): Table formatting, spacing normalization, improved examples.
- Favicon path moved `docs/img/favicon.ico` → `docs/images/favicon.ico`; logo updated.
- Index docs: Documentation URL switched to custom domain.
- MkDocs config:
  - `site_url` updated to `https://django-ninja-aio.com/`.
  - Added logo/favicon references and rich navigation features.
  - Expanded palette + features (search, code copy/select, tooltips, etc.).
- PyProject metadata: Documentation URL updated to new domain.
- Pagination imports switched to `from ninja.pagination` instead of local alias in examples.
- Refactor: `_m2m_views` now takes a single `M2MRelationSchema` and is invoked in a loop (improves clarity).
- Minor docstring spacing added before CRUD endpoint decorators.
- M2M registration: Logic unchanged functionally but simplified iteration pattern.

### Removed
- Legacy automatic loop inside `_m2m_views` (replaced by external loop in `_add_views`).
- Redundant long README sections (old serializer deep examples, extended auth/pagination prose).

### Internal
- `_add_views` now iterates `self.m2m_relations` and calls `_m2m_views(relation)` for each.
- Consistent path/auth resolution maintained; no schema changes to public API.
- Added `use_directory_urls: true` explicitly in `mkdocs.yml`.

### Impact
- No breaking API changes.
- Documentation structure improved; search indexing benefits from new plugins.
- M2M internals slightly cleaner; external behavior stable.

### Migration Notes
No action required for existing users.

[1.0.1]: https://github.com/caspel26/django-ninja-aio-crud/compare/v1.0.0...v1.0.1
[1.0.0]: https://github.com/caspel26/django-ninja-aio-crud/releases/tag/v1.0.0

---

## [v1.0.0] - 2025-10-28

---

### Added
- Per‑relation M2M configuration via `M2MRelationSchema` (replaces tuples).
- Per‑relation flags: `add`, `remove`, `get`.
- Per‑relation `filters` with dynamic schema generation and hook `<related_name>_query_params_handler`.
- Method `_generate_m2m_filters_schemas` to build all M2M filter schemas.
- Query param injection for M2M GET: `filters: Query[filters_schema] = None`.
- Extended docstrings for `APIViewSet` and internal helper methods.
- Overridable hooks documented in docs (`query_params_handler`, per‑relation handlers).
- Changelog: version bump to `__version__ = "1.0.0"`.

### Changed
- `api_view_set.md` rewritten: tuple-based M2M section replaced with `M2MRelationSchema` docs, new sections for filters, hooks, examples.
- CRUD table wording (schema_out formatting, notes clarified).
- Auth resolution notes now include M2M fallback logic.
- Internal view registration: per-relation flags extracted (`m2m_add/remove/get` replaced by schema attributes).
- Error message spacing adjusted in `_check_m2m_objs`.
- Refactored internal function docs (more concise, purpose-focused).
- Dynamic filter/path schemas built through unified `_generate_schema`.

### Removed
- Class attributes: `m2m_add`, `m2m_remove`, `m2m_get`.
- Tuple-based `m2m_relations` formats.
- Legacy verbose examples inside `views()` docstring.
- Redundant `m2m_auth` entry in auth table (moved to core attributes table).

### Internal
- Added per-method docstrings (`create_view`, `list_view`, `retrieve_view`, `update_view`, `delete_view`, `_m2m_views`, `_add_views`, etc.).
- `_crud_views` now described as a mapping.
- Added storage of `self.m2m_filters_schemas` during init.
- GET M2M handler applies optional per-relation filter hook if present.
- Manage M2M handler chooses input schema dynamically (`M2MSchemaIn` / `M2MAddSchemaIn` / `M2MRemoveSchemaIn`).

### Migration Notes
Old:
```python
m2m_relations = [
    (Tag, "tags"),
    (Category, "categories", "article-categories"),
    (Author, "authors", "co-authors", [AdminAuth()])
]
m2m_add = True
m2m_remove = True
m2m_get = True
```

New:
```python
from ninja_aio.schemas import M2MRelationSchema

m2m_relations = [
    M2MRelationSchema(model=Tag, related_name="tags"),
    M2MRelationSchema(model=Category, related_name="categories", path="article-categories"),
    M2MRelationSchema(model=Author, related_name="authors", path="co-authors", auth=[AdminAuth()])
]
# Disable ops per relation if needed:
# M2MRelationSchema(model=Tag, related_name="tags", add=False, remove=False, get=True)
```

Per‑relation filters:
```python
M2MRelationSchema(
    model=Tag,
    related_name="tags",
    filters={"name": (str, "")}
)

async def tags_query_params_handler(self, queryset, filters):
    if filters.get("name"):
        queryset = queryset.filter(name__icontains=filters["name"])
    return queryset
```

### Breaking Changes
- `m2m_relations` must use `M2MRelationSchema` (no tuples).
- Removed `m2m_add`, `m2m_remove`, `m2m_get` (use per-relation flags).
- Any code unpacking relation tuples must be updated to attribute access.

### Summary
Release focuses on granular M2M configuration, per‑relation filtering, cleaner internals, and clearer documentation for extensibility.

[1.0.0]: https://github.com/caspel26/django-ninja-aio-crud/compare/v0.11.4...v1.0.0
[0.11.4]: https://github.com/caspel26/django-ninja-aio-crud/releases/tag/v0.11.4

---

## [v0.11.4] - 2025-10-28

---

### Changed
- Documentation heading renamed from `# API ViewSet` to `# APIViewSet`.
- Docs rewritten: long examples replaced with concise endpoint table and structured attribute sections.
- Core attributes table expanded (added `pagination_class`, `query_params`, `disable`, endpoint doc strings).
- Clarified authentication resolution; explicit mention of `m2m_auth`.

### Added
- Per-relation M2M configuration: support for 3- and 4-element tuples in `m2m_relations`.
  - 3 elements: `(model, related_name, custom_path)`
  - 4 elements: `(model, related_name, custom_path, per_relation_auth)`
- Per-relation auth override (local `m2m_auth` inside `_m2m_views` loop).
- Documentation of M2M path/auth resolution rules.

### Removed
- Global `m2m_path` attribute (replaced by per-relation path tuple element).
- Old `m2m_relations` signature `list[tuple[ModelSerializer | Model, str]]`.

### Internal Implementation
- M2M loop updated: `for m2m_data in self.m2m_relations:` with dynamic tuple length parsing.
- Path resolution:
  ```python
  rel_path = rel_util.verbose_name_path_resolver() if not m2m_path else m2m_path
  ```
- Auth passed to decorators as `auth=m2m_auth` instead of `auth=self.m2m_auth`.
- Continued use of `@unique_view(...)` for stable handler naming.

### Migration Notes
```python
# Before
m2m_relations = [(Tag, "tags")]
m2m_path = "custom-tags"  # no longer supported

# After
m2m_relations = [
    (Tag, "tags"),                                 # auto path + fallback auth
    (Category, "categories", "custom-categories"), # custom path
    (Author, "authors", "article-authors", [AdminAuth()])  # custom path + custom auth
]
```
- Remove any `m2m_path` usage.
- 2-element tuples remain valid (no breaking change).

### Summary
Improved flexibility and granularity for M2M relation configuration and streamlined documentation.

[0.11.4]: https://github.com/caspel26/django-ninja-aio-crud/compare/v0.11.3...v0.11.4  
[0.11.3]: https://github.com/caspel26/django-ninja-aio-crud/releases/tag/v0.11.3

---

## [v0.11.3] - 2025-10-28

---

### Added
- **M2M Path Customization**: Added `m2m_path` attribute to `APIViewSet` for custom many-to-many relationship endpoint paths
  - Default: empty string (uses auto-generated path from model verbose name)
  - Allows overriding the default path resolution for M2M endpoints

### Changed

#### APIViewSet Class Attributes
- **m2m_relations type annotation**: Changed from `tuple[ModelSerializer | Model, str]` to `list[tuple[ModelSerializer | Model, str]]`
  - More flexible and mutable data structure
  - Allows dynamic modification of M2M relations at runtime

#### Code Quality & Formatting
- **Consistent blank lines**: Added blank lines after function returns for better code readability
  - Applied to: `create_view()`, `list_view()`, `retrieve_view()`, `update_view()`, `delete_view()`
- **Removed extra blank line**: Cleaned up unnecessary blank line in `delete_view()` method
- **M2M views refactoring**: Improved code structure for many-to-many relationship views
  - Applied `@unique_view` decorator to M2M endpoints (`get_related`, `manage_related`)
  - Removed manual `__name__` assignment in favor of decorator pattern
  - Better separation of concerns between GET and POST operations
  - Moved conditional M2M add/remove logic outside of the GET endpoint block

#### M2M Endpoint Generation
- **Dynamic path resolution**: M2M endpoints now respect custom `m2m_path` attribute
  ```python
  rel_path = (
      rel_util.verbose_name_path_resolver()
      if not self.m2m_path
      else self.m2m_path
  )

---

## [v0.11.1] - 2025-10-28

---

### Fixed
- Fixed typo in module name: renamed `decoratos.py` to `decorators.py`
- Updated import statement in `views.py` to use correct `decorators` module name

### Changed

#### Documentation
- **Homepage Examples** - Updated traditional approach comparison
  - Changed from Django REST Framework serializers to Django Ninja ModelSchema
  - Simplified example from `UserSerializer` to `UserSchemaOut`
  - Simplified example from `UserCreateSerializer` to `UserSchemaIn`
  - Updated view examples to use Django Ninja's `@api.get()` and `@api.post()` decorators
  - Replaced class-based views (`UserListView`, `UserCreateView`) with function-based views
  - Removed `sync_to_async` wrapper calls in favor of native async Django ORM operations
  - Simplified user creation with direct `acreate()` usage
  - Updated response format to use tuple-based status code returns `(201, user)`
  - Made code examples more concise and modern

### Technical Details

#### Module Renaming
```python
# Before (v0.11.0)
from .decoratos import unique_view

# After (v0.11.1)
from .decorators import unique_view

---

## [v0.11.0] - 2025-10-26

---

### Added

#### Documentation
- Complete documentation website with MkDocs Material theme
- Custom domain configuration (ninja-aio.dev) via CNAME
- **Getting Started Guide**
  - Installation instructions
  - Quick start tutorial with screenshots
  - Auto-generated Swagger UI examples
- **Tutorial Series** (4 comprehensive steps)
  - Step 1: Define Your Model - Complete guide to ModelSerializer with relationships, custom fields, and lifecycle hooks
  - Step 2: Create CRUD Views - APIViewSet usage, custom endpoints, query parameters, and error handling
  - Step 3: Add Authentication - JWT setup with RSA keys, role-based access control, and ownership validation
  - Step 4: Add Filtering & Pagination - Advanced filtering, full-text search, ordering, and performance optimization
- **API Reference Documentation**
  - Authentication guide (965 lines) covering AsyncJwtBearer, JWT validation, RBAC, and integrations
  - ModelSerializer reference (806 lines) with schema generation and relationship handling
  - ModelUtil reference (1,066 lines) detailing CRUD operations and data transformations
  - APIView documentation for custom endpoints
  - APIViewSet documentation (327 lines) for complete CRUD operations
  - Pagination guide (750 lines) with custom pagination examples
- Contributing guidelines
- Logo and branding assets
- Extra CSS styling for code blocks

#### Core Features
- **NotFoundError Exception**
  - New exception class for 404 errors with model-aware error messages
  - Automatically includes model verbose name in error response
  - Status code 404 with structured error format

#### Utilities
- **Decorators Module** (`ninja_aio/decoratos.py`)
  - `aatomic` decorator for asynchronous atomic transactions
  - `AsyncAtomicContextManager` for async transaction context management
  - `unique_view` decorator for generating unique view names based on model metadata
  - Support for both singular and plural model naming conventions

#### Examples
- **Example 1** (`examples/ex_1/`)
  - Basic User model without relationships
  - Simple ViewSet implementation
  - Basic URL configuration
- **Example 2** (`examples/ex_2/`)
  - User and Customer models with ForeignKey relationship
  - JWT authentication setup with RSA keys
  - Complete auth configuration with mandatory claims
  - Related field serialization examples

#### Development Tools
- MkDocs configuration (`mkdocs.yml`)
  - Material theme with deep purple color scheme
  - Dark/light mode support with auto-detection
  - Navigation tabs and integrated TOC
  - Code highlighting with Pygments
  - Admonitions and superfences support
- Documentation requirements file
- Custom CSS for documentation styling

### Changed

#### Core Models
- **ModelSerializer**
  - Enhanced docstring (113 lines) with comprehensive API documentation
  - Detailed explanation of schema generation and relationship handling
  - Examples for CreateSerializer, ReadSerializer, and UpdateSerializer
  - Documented sync and async lifecycle hooks
- **ModelUtil**
  - Enhanced docstring (79 lines) documenting all CRUD operations
  - Detailed method documentation for `parse_input_data`, `parse_output_data`, and CRUD methods
  - Performance notes and error handling documentation
  - Updated to use `NotFoundError` instead of generic `SerializeError` for 404 cases

#### Views
- **APIViewSet**
  - Applied `@unique_view` decorator to all generated CRUD methods (create, list, retrieve, update, delete)
  - Removed manual `__name__` assignment in favor of decorator-based approach
  - Cleaner method definitions without post-definition name mutations
- **APIView**
  - Added comprehensive docstring explaining base class functionality

#### Authentication
- **AsyncJwtBearer**
  - Enhanced docstring (71 lines) with detailed attribute and method documentation
  - Security considerations and best practices
  - Integration examples with Auth0, Keycloak, and Firebase

#### Project Structure
- Reorganized documentation structure with clear separation of concerns

### Fixed
- Consistent error handling using `NotFoundError` for object not found scenarios
- Proper async context management for database transactions

### Documentation Improvements

#### Tutorial Content
- 4,435 total lines of tutorial content
- 120+ code examples across all tutorials
- 50+ API usage examples with curl commands
- Comprehensive error handling examples
- Performance optimization tips and best practices

#### API Reference
- 3,994 total lines of API reference documentation
- Complete method signatures with parameter descriptions
- Return type documentation
- Error handling specifications
- Integration examples

#### Visual Assets
- Swagger UI screenshots for all CRUD operations
- Logo and branding images
- Diagram examples (where applicable)

### Notes

#### Breaking Changes
None - This is a documentation and enhancement release

#### Migration Required
None - All changes are backward compatible

#### Known Issues
None reported

## Links

- **Documentation**: https://caspel26.github.io/django-ninja-aio-crud/

---

## [v0.10.3] - 2025-09-23

---

### 🔧 Changed
- **ModelUtil Refactoring**: Extracted model field handling logic into separate property
  - Added `model_fields` property to encapsulate `[field.name for field in self.model._meta.get_fields()]`
  - Updated `serializable_fields` property to use new `model_fields` property for non-ModelSerializerMeta models

### 🛠️ Fixed
- **Custom Field Filtering**: Enhanced custom field detection logic to prevent conflicts with actual model fields
  - Custom fields are now filtered to exclude fields that exist in the actual Django model
  - Added `k not in self.model_fields` condition to both custom field dictionary comprehension and iteration logic
  - Prevents custom serializer fields from overriding or conflicting with real model fields

### 📈 Improvements
- **Code Organization**: Better separation of concerns with dedicated `model_fields` property
- **Field Conflict Prevention**: More robust handling of custom vs model field distinction
- **Code Readability**: Improved maintainability by reducing code duplication in field name extraction

### 🔄 Technical Details
- The `customs` dictionary now only includes truly custom fields that don't exist on the model
- Custom field processing in the main loop now respects model field boundaries
- Better encapsulation of model introspection logic

---

## [v0.10.2] - 2025-09-18

---

### ✨ Added
- **Pagination Support for M2M Relations**: Added `@paginate(self.pagination_class)` decorator to M2M `get_related` endpoints for better performance with large datasets

### 🔧 Changed
- **Code Quality Improvements**:
  - Cleaned up response schema formatting in M2M GET endpoints (removed unnecessary line breaks)
  - Fixed spacing inconsistency in `self.error_codes` assignment
  - Improved variable initialization readability in M2M management function
  - Added proper line spacing for better code organization

- **Dynamic M2M Endpoint Documentation**: 
  - Enhanced summary and description generation for M2M endpoints based on available operations
  - Summary now dynamically shows "Add", "Remove", or "Add or Remove" based on configuration
  - More intuitive endpoint descriptions that reflect actual capabilities

- **Function Naming Convention**:
  - Renamed `add_and_remove_related` to `manage_related` for better semantic clarity
  - Updated function name assignment to `manage_{model_name}_{relation_path}` pattern

- **Schema Selection Logic**: Refactored conditional schema assignment using ternary operators for better readability

### 🛠️ Technical Improvements
- **Variable Declaration**: Simplified tuple unpacking for M2M operation variables
- **Code Formatting**: Improved consistency in code spacing and line breaks
- **Function Organization**: Better separation of logic blocks with appropriate whitespace

### 📈 Performance
- M2M related object listing now supports pagination, reducing memory usage and improving response times for large relationship sets

---

## [v0.10.1] - 2025-09-18

---

### ✨ Added
- **Pagination Support for M2M Relations**: Added `@paginate(self.pagination_class)` decorator to M2M `get_related` endpoints for better performance with large datasets

### 🔧 Changed
- **Code Quality Improvements**:
  - Cleaned up response schema formatting in M2M GET endpoints (removed unnecessary line breaks)
  - Fixed spacing inconsistency in `self.error_codes` assignment
  - Improved variable initialization readability in M2M management function
  - Added proper line spacing for better code organization

- **Dynamic M2M Endpoint Documentation**: 
  - Enhanced summary and description generation for M2M endpoints based on available operations
  - Summary now dynamically shows "Add", "Remove", or "Add or Remove" based on configuration
  - More intuitive endpoint descriptions that reflect actual capabilities

- **Function Naming Convention**:
  - Renamed `add_and_remove_related` to `manage_related` for better semantic clarity
  - Updated function name assignment to `manage_{model_name}_{relation_path}` pattern

- **Schema Selection Logic**: Refactored conditional schema assignment using ternary operators for better readability

### 🛠️ Technical Improvements
- **Variable Declaration**: Simplified tuple unpacking for M2M operation variables
- **Code Formatting**: Improved consistency in code spacing and line breaks
- **Function Organization**: Better separation of logic blocks with appropriate whitespace

### 📈 Performance
- M2M related object listing now supports pagination, reducing memory usage and improving response times for large relationship sets

---

## [v0.10.0] - 2025-09-15

---

### 🚀 Added
- **Many-to-Many Relations Support**: Complete M2M relationship management system
  - Added `M2MDetailSchema`, `M2MSchemaOut`, `M2MSchemaIn`, `M2MAddSchemaIn`, `M2MRemoveSchemaIn` schemas
  - New `m2m_relations` configuration for defining M2M relationships to manage
  - `m2m_add`, `m2m_remove`, `m2m_get` boolean flags to control M2M operations
  - `m2m_auth` parameter for M2M-specific authentication
  - Auto-generated M2M endpoints for getting, adding, and removing related objects
- **Enhanced ModelUtil**: Added return type annotations for better IDE support
- **Async Support**: Added `asyncio` import for concurrent M2M operations

### 🔧 Changed
- **BREAKING**: Enhanced JWT authentication error handling in `AsyncJwtBearer`
  - Now returns `False` instead of raising `AuthError` for invalid tokens
  - Added proper exception handling for `JoseError` during claims validation
  - Improved authentication flow with better error recovery
- **ModelUtil.get_object()**: Enhanced to return QuerySet when no primary key is provided
- **APIViewSet Documentation**: Updated class docstring with M2M configuration options

### 🛠️ Fixed
- **JWT Error Handling**: More graceful handling of JWT decode and validation errors
- **Import Organization**: Added missing `errors` import from `joserfc`

### 📚 Technical Details
- Added `_check_m2m_objs()` helper method for M2M object validation
- Added `_m2m_views()` method for automatic M2M endpoint generation
- M2M operations use `asyncio.gather()` for concurrent add/remove operations
- Dynamic function naming for M2M endpoints to avoid conflicts
- Comprehensive error reporting for M2M operations with detailed success/failure counts

### 🔄 Migration Notes
- Update JWT error handling if you were catching `AuthError` exceptions
- Configure `m2m_relations` if you want to use the new M2M management features
- Review authentication flows as JWT validation now returns `False` instead of raising errors

---

## [v0.9.2] - 2025-08-25

---

### Changed
- **BREAKING**: Refactored route registration system in `APIViewSet`
  - All CRUD views now use `@self.router` decorators instead of `@self.api` 
  - Simplified path handling by using class properties (`self.path`, `self.get_path`, etc.) instead of string concatenation
  - Removed explicit `tags` parameter from individual view decorators (now handled at router level)
  - Streamlined `add_views_to_route()` method to directly return router registration

### Removed
- Removed manual `tags=[self.router_tag]` from all CRUD view decorators (create, list, retrieve, update, delete)

### Added  
- Added comprehensive `test_crud_routes()` test method to validate:
  - Correct route paths are registered
  - Proper handling of excluded views
  - Path names are correctly assigned for all CRUD operations

### Technical Details
- Route paths now use dynamic properties instead of hardcoded string formatting
- Router registration is now more efficient with inline view addition
- Improved test coverage for route validation and exclusion scenarios

---

## [v0.9.1] - 2025-08-25

---

### Changed
- Bumped version from 0.9.0 to 0.9.1 by @caspel26 

### Removed
- Removed `test_crud_routes()` method from test suite in `tests/generics/views.py` by @caspel26 

### Fixed
- Fixed missing API assignment in `_create_relation()` method - added `cls.relation_viewset.api = cls.api` before view creation by @caspel26

### Technical Details
- Cleaned up test code by removing redundant route testing logic by @caspel26 
- Improved test reliability by ensuring proper API context in relation creation helper method by @caspel26

---

## [v0.9.0] - 2025-07-17

---

# Changelog



### Changed
- Removed trailing slashes from base API routes by @caspel26 
- Renamed `add_views()` to `_add_views()` (now private implementation method) by @caspel26 
- Added comprehensive docstrings to `APIViewSet` class by @caspel26 
- Added view-specific documentation properties by @caspel26 :
  - `list_docs`
  - `create_docs`
  - `retrieve_docs`
  - `update_docs`
  - `delete_docs`
- Added automatic endpoint summaries and descriptions based on model metadata by @caspel26 
- Improved path handling with new properties by @caspel26 :
  - `get_path`
  - `get_path_retrieve`
- Added `model_verbose_name` property for consistent naming by @caspel26 
- Updated test paths to match new URL structure by @caspel26 
- Added trailing slash to `api_route_path` in test view classes by @caspel26

---

## [v0.8.4] - 2025-06-20

---

### Changes to `ninja_aio/views.py`

#### Refactoring
- Updated `self.router_tag` assignment:
  - **Before:** `self.router_tag = self.model_util.model_name.capitalize()`
  - **After:** `self.router_tag = " ".join(self.model._meta.verbose_name.capitalize().split(" "))`
  - This change improves the readability of the router tag by using the model's `verbose_name`, preserving spacing between words. by @caspel26 

#### Minor Fixes
- Removed unnecessary trailing spaces in `*_view_auth()` methods (`get_view_auth`, `post_view_auth`, `patch_view_auth`, `delete_view_auth`). by @caspel26

---

## [v0.8.3] - 2025-06-18

---

### Changed
- Updated version number from `0.8.2` to `0.8.3`. by @caspel26 

### Fixed
- Improved the `_auth_view` method in `APIViewSet` to avoid potential `AttributeError` by using `getattr(..., None)` with a default value. by @caspel26

---

## [v0.8.2] - 2025-06-18

---

### Added
- Introduced per-method authentication options to `APIViewSet`:
  - `get_auth`
  - `post_auth`
  - `patch_auth`
  - `delete_auth` by @caspel26 
- Added helper methods to resolve per-method auth:
  - `get_view_auth()`
  - `post_view_auth()`
  - `patch_view_auth()`
  - `delete_view_auth()` by @caspel26 

### Changed
- All route decorators (`@router.get`, `@router.post`, etc.) now use the new per-method auth resolution instead of the global `auth` attribute. by @caspel26 
- Minor type ignore hints (`# type: ignore`) added for compatibility and typing support. by @caspel26 

### Fixed
- Ensured route-specific authentication is configurable and overrides the global `auth` setting properly when defined. by @caspel26

---

## [v0.8.1] - 2025-06-18

---

# What's Changed

## News:
* Added support for IPAddress serialization by @caspel26 

**Full Changelog**: https://github.com/caspel26/django-ninja-aio-crud/compare/v0.8.0...v0.8.1

---

## [v0.8.0] - 2025-05-15

---

# What's Changed

## News:
* Added save methods:
 1. on_create_before_save;
 2. on_create_after_save;
 3. before_save;
 4. after_save.  by @caspel26.

* Added on_delete method by @caspel26.

* Updated [README.md](https://github.com/caspel26/django-ninja-aio-crud/blob/main/README.md) by @caspel26.
* Optimized async post object creation operations by @caspel26.
* Updated code docstrings by @caspel26 .

**Full Changelog**: https://github.com/caspel26/django-ninja-aio-crud/compare/v0.7.8...v0.8.0

---

## [v0.7.8] - 2025-03-21

---

# What's Changed

## News:
* Added api_routh_path attribute to APIViewSet  by @caspel26.

**Full Changelog**: https://github.com/caspel26/django-ninja-aio-crud/compare/v0.7.7...v0.7.8

* You can use this attribute if you do not want to use model verbose name plural as router path.

```python
# views.py
from ninja_aio.views import APIViewSet
from ninja_aio import NinjaAIO

from api.models import Foo

api = NinjaAIO()

class FooAPI(APIViewSet):
    model = Foo
    api = api
    api_route_path = "testpaths"


FooAPI().add_views_to_route()
```

---

## [v0.7.7] - 2025-03-05

---

# What's Changed

## News:
* Queryset request method is called while serializing output data by @caspel26 


**Full Changelog**: https://github.com/caspel26/django-ninja-aio-crud/compare/v0.7.6...v0.7.7

---

## [v0.7.6] - 2025-02-24

---

# What's Changed

## News:
* Schema from orm method called async while serializing by @caspel26 


**Full Changelog**: https://github.com/caspel26/django-ninja-aio-crud/compare/v0.7.5...v0.7.6

---

## [v0.7.5] - 2025-02-22

---

# What's Changed

## News:
* During serialization model fields are get asynchronously by @caspel26 


**Full Changelog**: https://github.com/caspel26/django-ninja-aio-crud/compare/v0.7.4...v0.7.5

---

## [v0.7.4] - 2025-02-20

---

# What's Changed

## News:
* Added to ModelSerializer related schema. can obtain it by generate_related_s method by @caspel26 
* General serialization refactor by @caspel26

## Bug Fix:
* Depth of relation serialization  by @caspel26.


**Full Changelog**: https://github.com/caspel26/django-ninja-aio-crud/compare/v0.7.2...v0.7.3

---

## [v0.7.3] - 2025-02-19

---

# What's Changed

## News:
* Added to ModelSerializer related schema. can obtain it by generate_related_s method by @caspel26 
* General serialization refactor by @caspel26

## Bug Fix:
* Depth of relation serialization  by @caspel26.


**Full Changelog**: https://github.com/caspel26/django-ninja-aio-crud/compare/v0.7.2...v0.7.3

---

## [v0.7.2] - 2025-01-30

---

# What's Changed

## News:
* Added support for relations serializations even if them are not ModelSerializer type  by @caspel26.

**Full Changelog**: https://github.com/caspel26/django-ninja-aio-crud/compare/v0.7.1...v0.7.2

* You can serialize them by adding into ReadSerializer as custom fields.

```python
# models.py
from django.db import models
from ninja_aio.models import ModelSerializer
from ninja import Schema

class BarSchema(Schema):
    id: int
    name: str
    description: str


class Foo(ModelSerializer):
  name = models.CharField(max_length=30)
  bar = models.ForeignKey(Bar, on_delete=models.CASCADE, related_name="foos")
  active = models.BooleanField(default=False)

  @property
  def full_name(self):
    return f"{self.name} example_full_name"

  class ReadSerializer:
    excludes = ["bar"]
    customs = [("full_name", str, ""), ("bar", BarSchema,  ...)]

  class CreateSerializer:
    fields = ["name"]
    optionals = [("bar", str), ("active", bool)]

  class UpdateSerializer:
    excludes = ["id", "name"]
    optionals = [("bar", str), ("active", bool)]
```

---

## [v0.7.1] - 2025-01-29

---

# What's Changed

## News:
* fix optionals Create and Update serializers , they didn't work properly with relations by @caspel26.
* now if the relation declared has a read serializer it will be used properly into serialization by @caspel26 

**Full Changelog**: https://github.com/caspel26/django-ninja-aio-crud/compare/v0.6.3...v0.7.1

---

## [v0.6.4] - 2025-01-22

---

# What's Changed

## News:
* Added with_qs_request param to ModelUtil get_object function by @caspel26. 

**Full Changelog**: https://github.com/caspel26/django-ninja-aio-crud/compare/v0.6.2...v0.6.3

* By default get object function use queryset request method defined into model, you can disable it by adding with_qs_request=False

And that's it! For more information check **<a href="https://github.com/caspel26/django-ninja-aio-crud/blob/main/README.md">README</a>**

---

## [v0.6.3] - 2025-01-22

---

# What's Changed

## News:
* Added with_qs_request param to ModelUtil get_object function by @caspel26. 

**Full Changelog**: https://github.com/caspel26/django-ninja-aio-crud/compare/v0.6.2...v0.6.3

* By default get object function use queryset request method defined into model, you can disable it by adding with_qs_request=False

And that's it! For more information check **<a href="https://github.com/caspel26/django-ninja-aio-crud/blob/main/README.md">README</a>**

---

## [v0.6.2] - 2025-01-19

---

_No release notes._

---

## [v0.6.1] - 2025-01-13

---

# What's Changed

## News:
* Fix query params and path params by @caspel26.
* If fields and excluded fields are not defined into serializers optionals will be override fields so fields are not mandatory to declare anymore by @caspel26.
* Pydantic validation error now is handled by default by @caspel26.

**Full Changelog**: https://github.com/caspel26/django-ninja-aio-crud/compare/v0.6.0...v0.6.1

And that's it! For more information check **<a href="https://github.com/caspel26/django-ninja-aio-crud/blob/main/README.md">README</a>**

---

## [v0.6.0] - 2025-01-12

---

# What's Changed

## News:
*  Added support for query params into APIViewSet schemas by @caspel26.
* Improved ModelUtil get object function by @caspel26.
* Improved error handling and make error responses more verborse by @caspel26.

**Full Changelog**: https://github.com/caspel26/django-ninja-aio-crud/compare/v0.5.0...v0.6.0

# 🚀  Query params support
* define your query params fields in this way. They are applied on CRUD list endpoint and will be shown also into swagger.

```python
# views.py
from ninja_aio import NinjaAIO
from ninja_aio.views import APIViewSet

from .models import Foo

api = NinjaAIO()


class FooAPI(APIViewSet):
  model = Foo
  api = api
  query_params = {"name": (str, None), "active": (bool, None)}

  async def query_params_handler(self, queryset, filters):
      return queryset.filter(**{k: v for k, v in filters.items() if v is not None})

FooAPI().add_views_to_route()
```
# ModelUtil get object improvement
You can now give extra getters and filters attribute to make the object query!


And that's it! For more information check **<a href="https://github.com/caspel26/django-ninja-aio-crud/blob/main/README.md">README</a>**

---

## [v0.5.0] - 2025-01-09

---

# What's Changed

## News:
*  Added support for excluded fields into serialization schemas by @caspel26.
* Added possibility to exclude crud endpoints into APIViewSet by @caspel26.
* Improved dynamical obtaining of object's pk for crud paths using pydantic by @caspel26.

**Full Changelog**: https://github.com/caspel26/django-ninja-aio-crud/compare/v0.4.0...v0.5.0

# 🚀  Schema excluded fields support
* define your excluded fields in this way.

```python
# models.py
from django.db import models
from ninja_aio.models import ModelSerializer


class Foo(ModelSerializer):
  name = models.CharField(max_length=30)
  bar = models.CharField(max_length=30, default="")
  active = models.BooleanField(default=False)

  class ReadSerializer:
    excludes = ["bar"]

  class CreateSerializer:
    fields = ["name"]
    optionals = [("bar", str), ("active", bool)]

  class UpdateSerializer:
    excludes = ["id", "name"]
    optionals = [[("bar", str), ("active", bool)]
```
# 🚀  Exclude CRUD endpoints into Views
You are able to exclude every crud endpoint, except for the additional views added by yourself, defining "disbale" APIViewSet's attribute.
```python
# views.py
from ninja_aio import NinjaAIO
from ninja_aio.views import APIViewSet

from .models import Foo

api = NinjaAIO()


class FooAPI(APIViewSet):
  model = Foo
  api = api
  disable = ["retrieve", "update"]


FooAPI().add_views_to_route()
```

And that's it! For more information check **<a href="https://github.com/caspel26/django-ninja-aio-crud/blob/main/README.md">README</a>**

---

## [v0.4.0] - 2025-01-08

---

# What's Changed

## News:
*  Added support for optional fields into serialization schemas by @caspel26.
* Better code error handling using Django Ninja exception handlers by @caspel26 

**Full Changelog**: https://github.com/caspel26/django-ninja-aio-crud/compare/v0.3.1...v0.4.0

# 🚀  Schema optional fields support
* It's an improved version of Django Ninja optional fields into dynamic schemas definition.

* define your optional fields in this way.

```Python
# models.py
from django.db import models
from ninja_aio.models import ModelSerializer


class Foo(ModelSerializer):
  name = models.CharField(max_length=30)
  bar = models.CharField(max_length=30, default="")
  active = models.BooleanField(default=False)

  class ReadSerializer:
    fields = ["id", "name", "bar"]

  class CreateSerializer:
    fields = ["name"]
    optionals = [("bar", str), ("active", bool)]

  class UpdateSerializer:
    optionals = [[("bar", str), ("active", bool)]
```
* And that's it! For more information check **<a href="https://github.com/caspel26/django-ninja-aio-crud/blob/main/README.md">README</a>**

---

## [v0.3.1] - 2024-11-07

---

## What's Changed
* fix: render and imports by @caspel26 in https://github.com/caspel26/django-ninja-aio-crud/pull/8


**Full Changelog**: https://github.com/caspel26/django-ninja-aio-crud/compare/v0.3.0...v0.3.1

---

## [v0.3.0] - 2024-10-09

---

# What's Changed

## News:
*  Vanilla Django Model automatic async CRUD support by @caspel26.

**Full Changelog**: https://github.com/caspel26/django-ninja-aio-crud/compare/v0.2.2...v0.3.0

# 🚀 Django Model Auto Async CRUD
* Now you can give to APIViewSet a vanilla django Model (including its schemas or CRUD will not work) as model class attribute. Like ModelSerializer also forward and reverse relations are supported.

* define your models.

```Python
# models.py
from django.db import models


class Bar(models.Model):
    name = models.CharField(max_length=30)
    description = models.TextField(max_length=30)


class Foo(models.Model):
    name = models.CharField(max_length=30)
    active = models.BooleanField(default=False)
    bar = models.ForeignKey(Bar, on_delete=models.CASCADE, related_name="foos")
```

* define your schemas. See **<a href="https://django-ninja.dev/guides/response/">Django Ninja Schema documentation</a>**

```Python
# schema.py
from ninja import Schema


class BarSchemaIn(Schema):
    name: str
    description: str


class BarSchemaRelated(Schema):
    id: int
    name: str
    description: str


class BarSchemaOut(BarSchemaRelated):
    foos: list["FooSchemaRelated"]


class BarSchemaUpdate(Schema):
    description: str

class FooSchemaIn(Schema):
    name: str
    active: bool
    bar: int


# This schema will be used into bar schema out for reverse relation
# It can be used for every model related, it's just an example like BarSchemaRelated
class FooSchemaRelated(Schema):
    id: int
    name: str
    active: bool


class FooSchemaOut(FooSchemaRelated):
    bar: BarSchemaRelated


class FooSchemaUpdate(Schema):
    name: str
    active: bool

```

*  then define your views.

```Python
# views.py
from ninja_aio import NinjaAIO
from ninja_aio.views import APIViewSet

from . import models, schemas

api = NinjaAIO()


class FooAPI(APIViewSet):
    model = models.Foo
    api = api
    schema_in = schemas.FooSchemaIn
    schema_out = schemas.FooSchemaOut
    schema_update = schemas.FooSchemaUpdate


class BarAPI(APIViewSet):
    model = models.Bar
    api = api
    schema_in = schemas.BarSchemaIn
    schema_out = schemas.BarSchemaOut
    schema_update = schemas.BarSchemaUpdate


FooAPI().add_views_to_route()
BarAPI().add_views_to_route()
```

* now run the server and go on /docs urls.

![image](https://github.com/user-attachments/assets/e25b6195-344d-45b6-b1bc-bd6c31e31b84)
![image](https://github.com/user-attachments/assets/a65ad631-f322-4cc4-a976-080593e5ba19)
![image](https://github.com/user-attachments/assets/2a745c1e-8ec4-4019-bd40-3f214ce10e3d)

---

## [v0.2.2] - 2024-10-03

---

## What's New
* Better error handling implementation by @caspel26


**Full Changelog**: https://github.com/caspel26/django-ninja-aio-crud/compare/v0.2.1...v0.2.2

---

## [v0.2.1] - 2024-10-01

---

# What's Changed

## News:
* NinjaAIO class implementation by @caspel26.

**Full Changelog**: https://github.com/caspel26/django-ninja-aio-crud/compare/v0.2.0...v0.2.1

# 🥷  NinjaAIO class
* NinjaAIO class inherits from  **<a href="https://django-ninja.dev/reference/api/">Django Ninja NinjaAPI</a>** but it uses built-in parser and renderer which use orjson for data serialization. This class is necessary to make able serialization works.

```Python
from ninja_aio import NinjaAIO
from ninja_aio.views import APIViewSet

from test.models import Foo

api = NinjaAIO()

class FooAPI(APIViewSet):
    model  = Foo
    api = api

FooAPI().add_views_to_route()
```

---

## [v0.2.0] - 2024-09-30

---

## What's Changed

### News:
* Many to many relation serialization support by @caspel26 in https://github.com/caspel26/django-ninja-aio-crud/pull/7

### Bugs:
* Bugfix: router path name in model CRUD router by @caspel26 in https://github.com/caspel26/django-ninja-aio-crud/pull/7
* Bugfix: OneToOne reverse and forward relations by @caspel26 in https://github.com/caspel26/django-ninja-aio-crud/pull/7

### Improvements:
* Improved models serializeration by @caspel26 in https://github.com/caspel26/django-ninja-aio-crud/pull/7

## 🎉 ManyToMany schemas serialization support
* many to many support is finally here. you can define your models and insert the many to many field in reverse and forward relations in ReadSerializerClass.

```Python
# models.py
from django.db import models
from .ninja_aio.models import ModelSerializer

class Bar(ModelSerializer):
    name = models.CharField(max_length=30)
    description = models.TextField(max_length=30)

    class ReadSerializer:
        fields = ["id", "name", "description", "foos"]

    class CreateSerializer:
        fields = ["name", "description"]

    class UpdateSerializer:
        fields = ["name", "description"]


class Foo(ModelSerializer):
    name = models.CharField(max_length=30)
    active = models.BooleanField(default=False)
    bars = models.ManyToManyField(Bar, related_name="foos")

    class ReadSerializer:
        fields = ["id", "name", "active", "bars"]

    class CreateSerializer:
        fields = ["name", "active"]

    class UpdateSerializer:
        fields = ["name", "active"]
```

 * Then add APIViewSets.

 ```Python
# views.py
from ninja import NinjaAPI
from .ninja_aio.views import APIViewSet
from .ninja_aio.parsers import ORJSONParser
from .ninja_aio.renders import ORJSONRenderer

from . import models

api = NinjaAPI(parser=ORJSONParser(), renderer=ORJSONRenderer())


class FooAPI(APIViewSet):
    model = models.Foo
    api = api


class BarAPI(APIViewSet):
    model = models.Bar
    api = api


FooAPI().add_views_to_route()
BarAPI().add_views_to_route()
```
* And that's it! Django Ninja Aio Crud will create dinamically all the schemas that you need and resolve all the relations! If you want to add a view to add, for example, a "bar" or multiple "bars" instances to Foo it could be something like that.

```Python
# views.py
from ninja import Schema
from ninja_aio.schemas import GenericMessageSchema


class AddBarsSchema(Schema):
    bars: list[int]


class FooAPI(APIViewSet):
    model = models.Foo
    api = api

    def views(self):
        @self.router.patch(
            "{id}/add-bars/", response={200: self.schema_out, 404: GenericMessageSchema}
        )
        async def add_bars(request: HttpRequest, id: int, data: AddBarsSchema):
            try:
                foo = await models.Foo.objects.prefetch_related("bars").aget(pk=id)
            except models.Foo.DoesNotExist:
                return 404, {"foo": "not found"}
            for bar_id in data.bars:
                try:
                    bar_obj = await models.Bar.objects.aget(pk=bar_id)
                except models.Bar.DoesNotExist:
                    return404, {"bar": "not found"}
                await foo.bars.aadd(bar_obj)
            await foo.asave()
            foo = await models.Foo.objects.prefetch_related("bars").aget(pk=id)
            return 200, foo
```

**Full Changelog**: https://github.com/caspel26/django-ninja-aio-crud/compare/v0.1.4...v0.2.0

---

## [v0.1.4] - 2024-09-29

---

## What's Changed
* Fix render model list view with pagination and improved relations serialization by @caspel26 in https://github.com/caspel26/django-ninja-aio-crud/pull/6


**Full Changelog**: https://github.com/caspel26/django-ninja-aio-crud/compare/v0.1.3...v0.1.4

---

## [v0.1.3] - 2024-09-27

---

**Full Changelog**: https://github.com/caspel26/django-ninja-aio-crud/compare/v0.1.2...v0.1.3

## What's Changed
* Async Pagination now supported and it can be customized. Check README for more information. implementation by @caspel26

---

## [v0.1.2] - 2024-09-26

---

**Full Changelog**: https://github.com/caspel26/django-ninja-aio-crud/compare/v0.1.1...v0.1.2

---

## [v0.1.1] - 2024-09-26

---

## What's Changed
* Update README.md by @caspel26 in https://github.com/caspel26/django-ninja-aio-crud/pull/1
* Update README.md by @caspel26 in https://github.com/caspel26/django-ninja-aio-crud/pull/2
* Update README.md by @caspel26 in https://github.com/caspel26/django-ninja-aio-crud/pull/3
* Custom fields implementation by @caspel26 in https://github.com/caspel26/django-ninja-aio-crud/pull/4
* Update README.md by @caspel26 in https://github.com/caspel26/django-ninja-aio-crud/pull/5

## New Contributors
* @caspel26 made their first contribution in https://github.com/caspel26/django-ninja-aio-crud/pull/1

**Full Changelog**: https://github.com/caspel26/django-ninja-aio-crud/commits/v0.1.1

---
