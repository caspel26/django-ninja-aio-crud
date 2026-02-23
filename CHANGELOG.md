# 📋 Release Notes

## 🏷️ [v2.22.0] - 2026-02-23

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

## 🏷️ [v2.21.0] - 2026-02-10

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

## 🏷️ [v2.20.0] - 2026-02-09

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

## 🏷️ [v2.19.0] - 2026-02-04

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

**Note:** Serializer uses `model_config_override` instead of `model_config` because `SchemaModelConfig` itself is a Pydantic model, so `model_config` is a reserved Pydantic attribute.

**Supported on all schema types:**
- ✅ CreateSerializer / schema_in
- ✅ ReadSerializer / schema_out
- ✅ UpdateSerializer / schema_update
- ✅ DetailSerializer / schema_detail
- ✅ RelatedSerializer / schema_related

**Common ConfigDict options:**
- `str_strip_whitespace` — Strip leading/trailing whitespace from strings
- `validate_assignment` — Validate attribute assignments after initial validation
- `use_enum_values` — Use enum values instead of enum instances
- `arbitrary_types_allowed` — Allow arbitrary user types

---

### 🔧 Improvements

#### 📦 Enhanced Schema Generation Pipeline
> `ninja_aio/models/serializers.py`

The schema generation pipeline in `BaseSerializer._generate_model_schema()` now handles three types of customizations:

**Pipeline flow:**

```
1. ninja.orm.create_schema() → Base Pydantic schema
2. _collect_validators() → Gather @field_validator, @model_validator
3. _collect_schema_overrides() → Gather method overrides (model_dump, etc.)
4. _apply_validators() → Create subclass with validators + overrides
5. Return final schema class
```

**Validation priority:**
- Validators and overrides are collected separately
- Both are injected into the same subclass
- Method overrides can call `super()` which resolves to the base schema methods
- Validators run before method overrides in the Pydantic execution flow

---

#### 🧹 Code Cleanup
> `ninja_aio/models/serializers.py`

**Configuration attribute detection:**
- Added `_CONFIG_ATTRS` frozenset with all configuration attribute names
- `_is_config_attr()` method for clean attribute filtering
- Prevents configuration attributes from being mistaken for validators or method overrides

**Schema override collection:**
- `_collect_schema_overrides()` filters out:
  - Validators (`PydanticDescriptorProxy` instances)
  - Configuration attributes (via `_CONFIG_ATTRS`)
  - Dunders (`__*__`)
- Only collects regular callable methods intended as overrides

---

### 📚 Documentation

Documentation has been extensively updated across multiple files to cover schema method overrides and `model_config` support:

**Files updated:**

| File | Additions |
|---|---|
| `docs/api/models/model_serializer.md` | 🔧 Schema method overrides section, `model_config` examples, configuration guide |
| `docs/api/models/serializers.md` | ⚙️ Pydantic Configuration section, `model_config_override` examples, schema overrides |
| `README.md` | 📝 Brief mention in Serializer features |

**New documentation sections:**

1. **Pydantic Configuration & Schema Overrides** — Complete guide with:
   - `model_config` / `model_config_override` usage
   - Schema method override syntax
   - Combined usage examples
   - IDE autocomplete tips (TYPE_CHECKING + self: Schema annotation)

2. **Configuration tables** — All available Pydantic ConfigDict options with descriptions

3. **Code examples** — Full working examples for both serializer patterns

---

### 🎯 Summary

Version 2.19.0 significantly enhances schema customization capabilities by allowing Pydantic `model_config` and schema method overrides directly on serializer inner classes. This brings django-ninja-aio-crud closer to native Pydantic flexibility while maintaining the framework's declarative, Django-first design.

**Key benefits:**
- 🎨 **Flexible Serialization** — Override `model_dump` to transform output on-the-fly
- ⚙️ **Pydantic Config** — Apply validation rules (strip whitespace, validate assignments, etc.)
- 🧩 **Composable** — Validators, config, and method overrides work together seamlessly
- 📚 **Well-Documented** — Comprehensive guides for both ModelSerializer and Serializer patterns

This release focuses on developer experience, providing more control over schema behavior without adding complexity to the core CRUD workflow.
