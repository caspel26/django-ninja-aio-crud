# CLAUDE.md

## Project Overview

**django-ninja-aio-crud** is an async CRUD framework built on Django Ninja. It provides automated REST API generation with async support, authentication, filtering, pagination, and serialization.

- **Framework:** Django Ninja (>=1.3.0, <1.6)
- **Python:** 3.10 - 3.14
- **Build system:** Flit
- **Linter/Formatter:** Ruff

## Project Structure

- `ninja_aio/` - Main source package
  - `api.py` - NinjaAIO class extending NinjaAPI
  - `auth.py` - JWT authentication (AsyncJwtBearer)
  - `views/` - APIView, APIViewSet, mixins
  - `models/` - ModelSerializer, Meta-driven Serializer, model utilities
  - `schemas/` - Pydantic schema generation and filters
  - `decorators/` - View and operation decorators
  - `factory/` - Operation factory
  - `helpers/` - Query and API helpers
- `tests/` - Test suite
  - `test_settings.py` - Django settings for tests (SQLite in-memory)
  - `test_app/` - Test Django app with models, serializers, views
  - Subdirectories: `core/`, `generics/`, `helpers/`, `views/`, `models/`
- `docs/` - MkDocs documentation

## Running Tests

Activate the virtual environment and run the coverage script:

```sh
. ./.venv/bin/activate && ./run-local-coverage.sh
```

This runs `coverage run -m django test --settings=tests.test_settings` and generates an HTML report in `.html/`.

To run tests without coverage:

```sh
. ./.venv/bin/activate && python -m django test --settings=tests.test_settings
```

## Code Style

- Ruff is used for linting and formatting (configured via pre-commit hooks)
- Pre-commit hooks also check AST validity, merge conflicts, TOML/YAML syntax, trailing whitespace, and EOF newlines

## Architecture Notes

### Serializer System

Two serializer patterns exist:

- **ModelSerializer** (`ninja_aio/models/serializers.py`): Model-bound, config via inner classes (`CreateSerializer`, `ReadSerializer`, `UpdateSerializer`, `DetailSerializer`). Metaclass: `ModelSerializerMeta`.
- **Serializer** (`ninja_aio/models/serializers.py`): Meta-driven for arbitrary Django models, config via `Meta` class with `SchemaModelConfig` objects. Metaclass: `SerializerMeta`.

Both inherit from `BaseSerializer` which provides shared utilities and the core schema factory (`_generate_model_schema`).

### Schema Generation Pipeline

1. Field configuration gathered from inner classes / Meta
2. `ninja.orm.create_schema()` called (wraps `pydantic.create_model`) — accepts `base_class`, `fields`, `custom_fields`, `exclude`, `depth`
3. Validators collected and applied as a subclass of the generated schema (see Validators section)
4. Resulting Pydantic model class used for input validation and output serialization

### Validators on Serializers

Pydantic `@field_validator` and `@model_validator` can be declared on serializer config classes. The framework collects `PydanticDescriptorProxy` instances and creates a subclass of the generated schema with those validators attached.

**ModelSerializer** — validators on inner serializer classes:
```python
class MyModel(ModelSerializer):
    class CreateSerializer:
        fields = ["name", "email"]

        @field_validator("name")
        @classmethod
        def validate_name(cls, v):
            if len(v) < 3:
                raise ValueError("Name too short")
            return v
```

**Serializer** — validators on `{Type}Validators` inner classes:
```python
class MySerializer(Serializer):
    class Meta:
        model = MyModel
        schema_in = SchemaModelConfig(fields=["name", "email"])

    class CreateValidators:
        @field_validator("name")
        @classmethod
        def validate_name(cls, v):
            return v.strip()
```

Key methods in `BaseSerializer`:
- `_collect_validators(source_class)` — scans class for `PydanticDescriptorProxy` instances
- `_apply_validators(schema, validators)` — creates subclass with validators attached
- `_get_validators(schema_type)` — maps schema type to validator source class (overridden by each serializer)

## Writing Release Notes / Changelogs

When asked to write a changelog or release notes, generate a diff first and then produce a comprehensive `CHANGELOG.md` entry following the structure below. The changelog is kept in `CHANGELOG.md` at the project root.

### How to generate the diff

```sh
# Diff between the current branch and main (for a feature branch)
git diff main...HEAD > diff.txt

# Or diff between two tags
git diff v2.17.0..v2.18.0 > diff.txt

# Or diff of all uncommitted changes (staged + unstaged)
git diff HEAD > diff.txt
```

### Changelog structure and style guide

Each release entry follows this format:

```markdown
## [vX.Y.Z] - YYYY-MM-DD

---

### New Features

#### Feature Name
> `path/to/file.py`

Description of the feature. Include code examples when the feature introduces new API surface.

---

### Improvements

#### Improvement Name
> `path/to/file.py`

Description of what changed and why.

---

### Documentation

Brief summary of documentation changes. Do NOT list every CSS class or inline style change. Keep `main.py`, `extra.css`, and `mkdocs.yml` changes to one-line summaries unless they introduce user-facing functionality.

---

### Tests

#### `TestClassName` — N tests

**Category:**

| Test | Verifies |
|---|---|
| `test_name` | What it verifies |

**New test fixtures:**

| File | Addition |
|---|---|
| `tests/test_app/models.py` | `ModelName` — brief description |

---

### Summary

Brief paragraph summarizing the release. Then:

**Key benefits:**
- Bullet points

### All Files Changed

| File | Changes |
|---|---|
| `path/to/file` | Brief description |
```

### Key rules

- **Always overwrite `CHANGELOG.md`** — Every time a changelog is generated, overwrite the existing `CHANGELOG.md` file at the project root. Do not create a new file or append to it.
- **Use emojis** — Decorate section headers, sub-headers, bullet points, and table entries with contextual emojis (e.g., ✨ New Features, 🔧 Improvements, 🧪 Tests, ✅/❌ for pass/fail tests, 🎯 Summary)

- **Group by category**: New Features, Improvements, Documentation, Tests, Summary
- **Use `> path/to/file`** blockquotes to indicate which file a change belongs to
- **Include code examples** for new user-facing API features
- **Use tables** for listing tests, methods, file changes, and mappings
- **Keep docs/styling/config sections brief** — one-liner summaries for CSS, `main.py` template changes, and `mkdocs.yml` config. Do not enumerate individual CSS classes or JS functions
- **Always include "All Files Changed" table** at the bottom
- **Always include "Summary" section** with key benefits as bullet points
- **Separate sections with `---`** horizontal rules
