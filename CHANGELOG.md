# 📋 Release Notes

## 🏷️ [v2.18.0] - 2026-02-01

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
