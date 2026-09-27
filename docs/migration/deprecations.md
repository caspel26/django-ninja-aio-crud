---
type: migration
title: Deprecations
description: Version 2 names that still work in 3.0, and what to use instead.
---

# Deprecations

These version 2 APIs still work in 3.0, but they emit a `DeprecationWarning`.
They are removed in 4.0. Each table lists the old name and its replacement.

For before and after code, see [Migration recipes](recipes.md).

## Schemas configuration

| Version 2 | Use instead |
| --- | --- |
| `CreateSerializer` inner class | `Schemas.create = SchemaConfig(...)` |
| `ReadSerializer` inner class | `Schemas.read = SchemaConfig(...)` |
| `UpdateSerializer` inner class | `Schemas.update = SchemaConfig(...)` |
| `DetailSerializer` inner class | `Schemas.detail = SchemaConfig(...)` |
| `ReadSerializer.relations_as_id` | `relations_as_id=[...]` on the `read` and `detail` configs |
| `CreateSerializer.nested` | `nested={...}` on the `create` config |
| `Meta.schema_in` | `Schemas.create` |
| `Meta.schema_out` | `Schemas.read` |
| `Meta.schema_update` | `Schemas.update` |
| `Meta.schema_detail` | `Schemas.detail` |
| `Meta.relations_as_id` | `relations_as_id=[...]` on the `read` and `detail` configs |
| `SchemaModelConfig(...)` | `SchemaConfig(...)` |

The warning is raised once, when the class is defined. `SchemaModelConfig`
warns through the `Meta` attribute that holds it.

A class that declares both `Schemas` and a legacy name raises
`ImproperlyConfigured`. Move everything to `Schemas`.

```text
Article: CreateSerializer, ReadSerializer is deprecated; declare a Schemas class with SchemaConfig entries instead.
```

See [Schemas](../guides/schemas.md).

## Schema factories

| Version 2 | Use instead |
| --- | --- |
| `generate_create_s()` | `create_schema` |
| `generate_update_s()` | `update_schema` |
| `generate_read_s()` | `read_schema` |
| `generate_read_s(depth)` | `get_schema("read", depth=depth)` |
| `generate_detail_s()` | `detail_schema` |
| `generate_detail_s(depth)` | `get_schema("detail", depth=depth)` |
| `generate_related_s()` | `related_schema` |

The replacements are class attributes, not methods. They work on
`ModelSerializer` and `Serializer`.

```text
Article.generate_read_s() is deprecated; use read_schema instead.
```

## The util attribute

| Version 2 | Use instead |
| --- | --- |
| `Article.util` | The methods on `Article`: `create`/`acreate`, `get`/`aget`, `update`/`aupdate`, `destroy`/`adestroy`, `model_dump`/`amodel_dump`, ... |
| `ArticleSerializer.util` | The same methods on `ArticleSerializer` |

Reading `.util` warns on the class and on instances:

```text
Article.util is deprecated; use the serializer methods (create/acreate, get/aget, update/aupdate, destroy/adestroy, model_dump/amodel_dump, ...) instead.
```

## ModelUtil

These `ModelUtil` methods warn when you call them. Calling them through
`.util` shows two warnings: one for `.util` and one for the method.

| Version 2 | Use instead |
| --- | --- |
| `create_s(request, data, schema)` | `acreate(data, request=request)`, then `amodel_dump(instance)` |
| `read_s(schema, request, instance)` | `amodel_dump(instance)` |
| `list_read_s(schema, request, instances)` | `amodel_dumps(instances)` |
| `update_s(request, data, pk, schema)` | `aupdate(pk, data, request=request)`, then `amodel_dump(instance)` |
| `delete_s(request, pk)` | `adestroy(pk, request=request)` |
| `bulk_create_s(request, data_list)` | `abulk_create(items, request=request)` |
| `bulk_update_s(request, data_list)` | `abulk_update(items, request=request)` |
| `bulk_delete_s(request, pks)` | `abulk_destroy(pks, request=request)` |

Each replacement is a class method of your serializer, like
`Article.acreate(...)`. The sync versions drop the `a` prefix. The bulk
methods return a `BulkResult` instead of a `(success, errors)` tuple. See
[Use the CRUD API from Python](../guides/python-crud.md) and
[Bulk operations](../guides/bulk-operations.md).

`get_object()` and `get_objects()` don't warn on their own, but calling them
through `.util` does. Replace them with `aget()` and `aget_queryset()`:

```python
article = await Article.aget(pk, request=request)
articles = await Article.aget_queryset(request=request)
```

!!! warning

    In 3.0, `ModelUtil.get_object()` and `get_objects()` are sync. Code that
    still awaits them fails. See [Breaking changes](breaking-changes.md).

## Route decorators

| Version 2 | Use instead |
| --- | --- |
| `@api_get(path)` | `@action(detail=False, url_path=...)` |
| `@api_post(path)` | `@action(detail=False, methods=["post"], url_path=...)` |
| `@api_put(path)` | `@action(detail=False, methods=["put"], url_path=...)` |
| `@api_patch(path)` | `@action(detail=False, methods=["patch"], url_path=...)` |
| `@api_delete(path)` | `@action(detail=False, methods=["delete"], url_path=...)` |
| `@api_options(path)` | `@action(detail=False, methods=["options"], url_path=...)` |
| `@api_head(path)` | `@action(detail=False, methods=["head"], url_path=...)` |

Import `action` from `ninja_aio`. It works on `APIView` and `APIViewSet`. The
warning is raised when the decorator is applied:

```text
api_get is deprecated; use @action(detail=False, methods=['get'], url_path=...) instead.
```

See [Custom actions](../guides/custom-actions.md).

## Top-level imports

| Version 2 | Use instead |
| --- | --- |
| `from ninja_aio import register_admin` | `from ninja_aio.admin import register_admin` |
| `from ninja_aio import Branding` | `from ninja_aio.docs import Branding` |

```text
Importing register_admin from ninja_aio is deprecated; import it from ninja_aio.admin.
```

## Find deprecated code

Python hides `DeprecationWarning` by default. Turn the warnings into errors
while you run your tests, so each one fails with a traceback:

```bash
python -W error::DeprecationWarning manage.py test
```

To list the warnings raised when your code is imported, like the schemas
configuration and the route decorators, run the system checks:

```bash
python -W default::DeprecationWarning manage.py check
```

Warnings for `.util` and `ModelUtil` methods appear only when the code runs,
so use the test command to find them.

## See also

- [Migration recipes](recipes.md)
- [Breaking changes](breaking-changes.md)
- [Migrate to 3.0](index.md)
- [Schemas](../guides/schemas.md)
