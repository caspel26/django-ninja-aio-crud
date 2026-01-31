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
