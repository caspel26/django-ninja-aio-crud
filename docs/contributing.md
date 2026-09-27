---
type: guide
title: Contributing
description: Set up the project locally, run the tests and send your first pull request.
---

# Contributing

This page shows how to set up the project, run the tests and benchmarks,
build the docs and open a pull request.

You can help by reporting bugs, suggesting features, improving the docs,
adding tests or reviewing pull requests.

## Set up the project

<div class="nac-steps" markdown>

### Clone and install

```bash
git clone https://github.com/caspel26/django-ninja-aio-crud.git
cd django-ninja-aio-crud
python -m venv .venv
source .venv/bin/activate  # on Windows: .venv\Scripts\activate
pip install -e ".[dev,test]"
```

This installs the package in editable mode with `coverage`, `pre-commit` and
`ruff`.

### Install the pre-commit hooks

```bash
pre-commit install
```

Ruff and the other checks now run on every commit.

### Check that the tests pass

```bash
./run-tests.sh
```

Start from a green test run before you change anything.

</div>

## Run the tests

| Command | What it does |
| --- | --- |
| `./run-tests.sh` | Runs the test suite without the benchmarks. Use it while you work. |
| `./run-local-coverage.sh` | Runs every test with coverage and writes an HTML report to `.html/`. |
| `python -m django test tests.views --settings=tests.test_settings` | Runs a single test module. |

After the full run, print the coverage summary:

```bash
coverage report
```

!!! note

    All tests must pass, new code needs tests, and coverage must not go down.

## Run the performance benchmarks

Run the benchmarks and build the HTML report:

```bash
./run-performance.sh
```

To check for regressions, run the benchmarks a few times, then compare the
latest runs with the previous ones:

```bash
for i in 1 2 3 4 5; do
  python -m django test tests.performance --settings=tests.test_settings --tag=performance -v0
done
python tests/performance/tools/detect_regression.py
```

The script exits with `0` when there are no regressions and `1` when it finds
some. See [Performance](performance.md) for the full list of benchmarks.

## Build the docs

```bash
pip install -r docs/requirements.txt
mkdocs serve
```

Open `http://127.0.0.1:8000` to preview your changes. The pages live in
`docs/`.

## Follow the code style

The project uses Ruff for linting and formatting. The pre-commit hooks also
check Python syntax, merge conflict markers, TOML and YAML files, trailing
whitespace and end-of-file newlines.

To format by hand before you commit:

```bash
ruff check . --fix
ruff format .
```

- Put imports at the top of the file. Import inside a function only to avoid
  a circular import, and add a short comment that says so.
- Add type hints to function signatures and class attributes.

## Open a pull request

- [ ] One feature or fix per pull request
- [ ] Tests added or updated for every code change
- [ ] Docs updated for user-facing changes
- [ ] Related issue linked in the description
- [ ] All tests pass locally

Name your branch after the change:

| Prefix | Use for | Example |
| --- | --- | --- |
| `feature/` | New features | `feature/add-bulk-create` |
| `fix/` | Bug fixes | `fix/pagination-offset-bug` |
| `docs/` | Documentation | `docs/improve-auth-examples` |

## Report an issue

Open an issue on [GitHub](https://github.com/caspel26/django-ninja-aio-crud/issues)
and include:

- Python and Django versions
- The `django-ninja-aio-crud` version (`pip show django-ninja-aio-crud`)
- Steps to reproduce
- Expected and actual behavior
- The full traceback or logs
- A minimal code example that reproduces the problem

## Project structure

```text
ninja_aio/            # Main package
├── api.py            # NinjaAIO
├── auth.py           # JWT authentication
├── admin.py          # Django admin integration
├── docs.py           # Docs branding
├── views/            # APIView, APIViewSet, mixins
├── models/           # ModelSerializer, Serializer, SchemaConfig
├── schemas/          # Schema generation and filter schemas
├── decorators/       # View and operation decorators
├── factory/          # Operation factory
├── helpers/          # Query and API helpers
└── mcp/              # MCP server

tests/                # Test suite
├── test_settings.py  # Django settings (SQLite in-memory)
├── test_app/         # Test app with models, serializers and views
├── core/             # Core tests
├── views/            # View tests
├── models/           # Model tests
├── v3/               # Sync and async API tests
├── performance/      # Performance benchmarks
└── comparison/       # Framework comparison benchmarks

docs/                 # Documentation
```

## Support the project

- Star the project on [GitHub](https://github.com/caspel26/django-ninja-aio-crud).
- Leave a tip on [Buy Me a Coffee](https://buymeacoffee.com/caspel26).

## See also

- [Performance](performance.md)
- [Framework comparison](comparison.md)
- [Troubleshooting](troubleshooting.md)
