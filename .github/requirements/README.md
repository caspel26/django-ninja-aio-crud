# CI dependency locks

CI installs exact versions and validates artifact hashes with pip's
`--require-hashes --only-binary :all:`. The library's published dependency ranges
remain in `pyproject.toml`; these locks make the test environments repeatable.
The checked-out project is installed separately with Flit, with dependency
installation disabled. This executes the repository code the jobs already test.

Inputs preserve Django 5.2, Django 6.0, and the minimum Django/Ninja combination.
The docs lock includes its build tooling. Regenerate with uv, inspect dependency
changes, and run the corresponding CI matrix:

```sh
uv pip compile .github/requirements/django52.in --universal --python-version 3.10 --generate-hashes --only-binary :all: -o .github/requirements/django52.txt
uv pip compile .github/requirements/django60.in --universal --python-version 3.14 --generate-hashes --only-binary :all: -o .github/requirements/django60.txt
uv pip compile .github/requirements/minimum.in --universal --python-version 3.10 --generate-hashes --only-binary :all: -o .github/requirements/minimum.txt
uv pip compile .github/requirements/docs.in --universal --python-version 3.13 --generate-hashes --only-binary :all: -o .github/requirements/docs.txt
uv pip compile .github/requirements/publish.in --universal --python-version 3.10 --generate-hashes --only-binary :all: -o .github/requirements/publish.txt
```

Each `.in` file declares the direct test dependencies. When changing a published
range or a test extra in `pyproject.toml`, update the matching inputs too.

The publishing lock pins a compatible Flit CLI/backend pair. Verify changes with
`flit build`; building artifacts locally does not publish them.
