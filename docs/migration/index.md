---
type: migration
title: Migrate to 3.0
description: Upgrade a version 2 project to django-ninja-aio-crud 3.0 step by step.
---

# Migrate to 3.0

Most version 2 code runs on 3.0 unchanged and shows a `DeprecationWarning`
where something should be renamed. Follow these steps to upgrade.

<div class="nac-steps" markdown>

### Upgrade the package

```bash
pip install --upgrade "django-ninja-aio-crud>=3,<4"
```

Version 3 supports Python 3.10 to 3.14 and Django Ninja 1.7.x.

### Check the breaking changes

Read [breaking changes](breaking-changes.md). The most common ones are:

- `async def` hooks need the `a` prefix, like `apost_create`.
- `Serializer.create()`, `update()` and `model_dump()` are sync; use `acreate()`, `aupdate()` and `amodel_dump()` in async code.
- `PATCH` only changes the fields the client sends.

### Run the checks and the tests

```bash
python manage.py check
python -W error::DeprecationWarning manage.py test
```

`check` validates every `Schemas` class. Turning warnings into errors shows each
place that uses a deprecated name.

### Replace deprecated code

Use the [deprecations](deprecations.md) table and the [recipes](recipes.md)
to move to the version 3 names, for example inner serializer classes to
`Schemas`, and `ModelUtil` calls to `Article.create()` and
`Article.amodel_dump()`.

### Try the sync mode (optional)

If your project runs on WSGI, you can now serve viewsets with sync views:

```python
@api.viewset(model=Article)
class ArticleViewSet(APIViewSet):
    execution_mode = "sync"
```

See [sync and async](../concepts/sync-and-async.md).

</div>

## Checklist

- [ ] Package upgraded and `python manage.py check` passes
- [ ] Async hooks renamed with the `a` prefix
- [ ] Awaited `Serializer` methods changed to `acreate()`, `aupdate()`, `amodel_dump()`
- [ ] Tests pass with `-W error::DeprecationWarning`
- [ ] Clients reviewed for the new `401`, `409` and `PATCH` behavior

## See also

- [Breaking changes](breaking-changes.md)
- [Deprecations](deprecations.md)
- [Recipes](recipes.md)
- [Release notes](../release_notes.md)
