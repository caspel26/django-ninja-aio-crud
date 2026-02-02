# :material-handshake: Contributing

We welcome contributions! Here's how you can help:

<div class="grid cards" markdown>

-   :material-bug:{ .lg .middle } **Report Bugs**

    ---

    Open an issue on [GitHub](https://github.com/caspel26/django-ninja-aio-crud/issues)

-   :material-lightbulb:{ .lg .middle } **Suggest Features**

    ---

    Share ideas in issues or discussions

-   :material-source-pull:{ .lg .middle } **Submit PRs**

    ---

    Improve code, tests, or docs

-   :material-file-document-edit:{ .lg .middle } **Improve Docs**

    ---

    Clarify, expand, or add examples

-   :material-test-tube:{ .lg .middle } **Add Tests**

    ---

    Increase coverage and reliability

-   :material-comment-check:{ .lg .middle } **Review PRs**

    ---

    Provide constructive feedback

</div>

---

## :material-wrench: Development Setup

### 1. Clone and install

```bash
git clone https://github.com/caspel26/django-ninja-aio-crud.git
cd django-ninja-aio-crud
python -m venv .venv
source .venv/bin/activate  # or .venv\Scripts\activate on Windows
pip install -e ".[dev]"
```

### 2. Install pre-commit hooks

```bash
pre-commit install
```

This ensures Ruff linting, AST validation, and formatting run automatically on every commit.

### 3. Verify your setup

```bash
python -m django test --settings=tests.test_settings
```

All tests should pass before you start making changes.

---

## :material-test-tube: Running Tests

=== "All tests"

    ```bash
    python -m django test --settings=tests.test_settings
    ```

=== "With coverage"

    ```bash
    ./run-local-coverage.sh
    ```

    This generates an HTML report in `.html/`.

=== "Specific module"

    ```bash
    python -m django test tests.views --settings=tests.test_settings
    ```

=== "Performance benchmarks"

    ```bash
    python -m django test tests.performance --settings=tests.test_settings --tag=performance -v2
    ```

!!! important "Test requirements"
    - All tests must pass before submitting a PR
    - New features must include tests
    - Coverage should not decrease — check with `coverage report`

---

## :material-format-paint: Code Style

Django Ninja AIO uses **Ruff** for linting and formatting, enforced via pre-commit hooks.

| Tool | Purpose |
|---|---|
| **Ruff** | Linting and formatting |
| **pre-commit** | AST checks, merge conflicts, TOML/YAML syntax, trailing whitespace, EOF newlines |

### Key rules

- **Imports at the top** — Always place imports at the beginning of each file (PEP 8). The only exception is avoiding circular imports, in which case place the import inside the function with a comment explaining why.
- **Async first** — All view methods should be `async def`. Sync methods are wrapped with `sync_to_async` automatically, but native async is preferred.
- **Type hints** — Use type annotations for function signatures and class attributes.

### Format before committing

```bash
ruff check . --fix
ruff format .
```

Or let pre-commit handle it automatically.

---

## :material-source-pull: Pull Request Guidelines

!!! info "PR Checklist"
    - [ ] Keep PRs focused and small — one feature or fix per PR
    - [ ] Follow existing code style (Ruff will enforce this)
    - [ ] Add or update tests for any code changes
    - [ ] Update docs for user-facing changes
    - [ ] Link related issue in the PR description
    - [ ] All tests pass locally before pushing

### Branch naming

Use descriptive branch names:

- `feature/add-bulk-create` — New features
- `fix/pagination-offset-bug` — Bug fixes
- `docs/improve-auth-examples` — Documentation improvements

---

## :material-bug: Issue Reports

!!! warning "Please include"
    - Python and Django versions
    - `django-ninja-aio-crud` version (`pip show django-ninja-aio-crud`)
    - Steps to reproduce
    - Expected vs actual behavior
    - Full traceback or logs (if any)
    - Minimal code example that reproduces the issue

---

## :material-file-tree: Project Structure

```
ninja_aio/           # Main source package
├── api.py           # NinjaAIO class
├── auth.py          # JWT authentication
├── views/           # APIView, APIViewSet, mixins
├── models/          # ModelSerializer, Serializer, ModelUtil
├── schemas/         # Pydantic schema generation, filters
├── decorators/      # View and operation decorators
├── factory/         # Operation factory
└── helpers/         # Query and API helpers

tests/               # Test suite
├── test_settings.py # Django settings (SQLite in-memory)
├── test_app/        # Test Django app with models
├── core/            # Core tests
├── generics/        # Generic test utilities
├── views/           # View tests
├── models/          # Model tests
├── performance/     # Performance benchmarks
└── comparison/      # Framework comparison benchmarks

docs/                # MkDocs documentation
```

---

## :material-star: Support the Project

If this project helps you, please give it a GitHub star to show support.

### :material-coffee: Buy Me a Coffee

Optional tip: [Buy Me a Coffee](https://buymeacoffee.com/caspel26).

---

Thank you for helping improve Django Ninja AIO.
