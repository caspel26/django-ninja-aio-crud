---
type: reference
title: ModelSerializer
description: Lookup page for ModelSerializer schemas, Python methods, hooks and options.
---

# ModelSerializer

`ModelSerializer` is a Django model base class that carries its own schemas,
Python CRUD methods and hooks. For how to use it, see
[Schemas](../../guides/schemas.md) and [Python CRUD](../../guides/python-crud.md).

```python
from ninja_aio import ModelSerializer, SchemaConfig
```

## Schemas

Declare each kind with a `SchemaConfig` inside `class Schemas:`. The generated
names below are for a model named `Article`.

| Kind | Schema attribute | Generated name | Used for |
| --- | --- | --- | --- |
| `create` | `create_schema` | `articleSchemaIn` | Create request body |
| `update` | `update_schema` | `articleSchemaPatch` | Update request body |
| `read` | `read_schema` | `articleSchemaOut` | List, create and update responses |
| `detail` | `detail_schema` | `articleDetailSchemaOut` | Retrieve response. Falls back to `read` |
| (automatic) | `related_schema` | `articleSchemaRelated` | This model nested inside another model |

```python
class Article(ModelSerializer):
    ...

    class Schemas:
        create = SchemaConfig(fields=["title", "body", "category"])
        update = SchemaConfig(optionals=[("title", str), ("body", str)])
        read = SchemaConfig(fields=["id", "title", "category"])
```

A kind you leave out has no schema (`None`), and its endpoint is not generated.
See [Schema generation](../../concepts/schema-generation.md) for how fields become
schemas.

## Validators

Put Pydantic `@field_validator` and `@model_validator` methods on these inner
classes:

| Inner class | Applies to |
| --- | --- |
| `CreateValidators` | `create` schema |
| `UpdateValidators` | `update` schema |
| `ReadValidators` | `read` schema |
| `DetailValidators` | `detail` schema |

## Schema attributes

| Attribute | Description |
| --- | --- |
| `create_schema`, `update_schema`, `read_schema`, `detail_schema`, `related_schema` | The generated schema class, or `None` if the kind is not declared. Built on first access and cached |
| `get_schema(kind, *, depth=1)` | Returns the schema for `"create"`, `"update"`, `"read"`, `"detail"` or `"related"`. `depth` (relation nesting) only applies to `read` and `detail` |
| `clear_schema_cache()` | Drops the cached schemas of this class |

Assign your own `Schema` subclass to an attribute, for example
`read_schema = ArticleOut`, to replace the generated one.

## Python methods

All methods are classmethods. `request` is keyword-only and optional in every
method.

| Sync | Async | Returns |
| --- | --- | --- |
| `create(data, *, request=None)` | `acreate(...)` | `Article` |
| `get(pk=None, *, request=None, optimize_for=None, **lookups)` | `aget(...)` | `Article` |
| `get_queryset(*, request=None, optimize_for=None)` | `aget_queryset(...)` | `QuerySet[Article]` |
| `update(target, data, *, request=None)` | `aupdate(...)` | `Article` |
| `destroy(target, *, request=None)` | `adestroy(...)` | `None` |
| `model_dump(instance, *, schema=None, strict=False)` | `amodel_dump(instance, *, schema=None)` | `dict` (default: detail schema) |
| `model_dumps(instances, *, schema=None, strict=False)` | `amodel_dumps(instances, *, schema=None)` | `list[dict]` (default: read schema) |
| `bulk_create(items, *, request=None)` | `abulk_create(...)` | `BulkResult[Article]` |
| `bulk_update(items, *, request=None)` | `abulk_update(...)` | `BulkResult[Article]` |
| `bulk_destroy(targets, *, request=None)` | `abulk_destroy(...)` | `BulkResult` of primary keys |

`target` is an instance or a primary key. `optimize_for` is `"read"` or
`"detail"`. The dump methods load missing relations with one query per
relation. `strict=True` makes the sync dump raise `ValueError` instead of
running any query.

::: ninja_aio.models.serializers.ModelSerializer.create
    options:
      show_root_heading: true
      show_root_full_path: false

::: ninja_aio.models.serializers.ModelSerializer.acreate
    options:
      show_root_heading: true
      show_root_full_path: false

::: ninja_aio.models.serializers.ModelSerializer.get
    options:
      show_root_heading: true
      show_root_full_path: false

::: ninja_aio.models.serializers.ModelSerializer.aget
    options:
      show_root_heading: true
      show_root_full_path: false

::: ninja_aio.models.serializers.ModelSerializer.update
    options:
      show_root_heading: true
      show_root_full_path: false

::: ninja_aio.models.serializers.ModelSerializer.aupdate
    options:
      show_root_heading: true
      show_root_full_path: false

::: ninja_aio.models.serializers.ModelSerializer.destroy
    options:
      show_root_heading: true
      show_root_full_path: false

::: ninja_aio.models.serializers.ModelSerializer.adestroy
    options:
      show_root_heading: true
      show_root_full_path: false

::: ninja_aio.models.serializers.ModelSerializer.model_dump
    options:
      show_root_heading: true
      show_root_full_path: false

::: ninja_aio.models.serializers.ModelSerializer.amodel_dump
    options:
      show_root_heading: true
      show_root_full_path: false

::: ninja_aio.models.serializers.ModelSerializer.model_dumps
    options:
      show_root_heading: true
      show_root_full_path: false

::: ninja_aio.models.serializers.ModelSerializer.amodel_dumps
    options:
      show_root_heading: true
      show_root_full_path: false

## Hooks

Sync viewsets call the plain names, async viewsets the `a` names. Override one
of the pair. See [Hooks](../../guides/hooks.md).

| Hook | Signature | Runs |
| --- | --- | --- |
| `queryset_request` / `aqueryset_request` | `(cls, request)` classmethod | Builds the base queryset for lookups, lists, updates and deletes |
| `post_create` / `apost_create` | `(self)` | Once, after the object is created |
| `custom_actions` / `acustom_actions` | `(self, payload)` | On create and update, with the `customs` fields as a dict |
| `on_create_before_save` | `(self)` | Before the first save only |
| `before_save` | `(self)` | Before every save |
| `on_create_after_save` | `(self)` | After the first save only |
| `after_save` | `(self)` | After every save |
| `on_delete` | `(self)` | After the object is deleted |
| `has_changed` / `ahas_changed` | `(self, field) -> bool` | Helper: `True` if the value differs from the database |
| `as_admin` | `(cls, **overrides) -> type` | Helper: returns a Django `ModelAdmin` class built from the schemas |

## Query optimization

Declare `class QuerySet:` on the model to add `select_related` and
`prefetch_related` to generated queries.

| Attribute | Type | Description |
| --- | --- | --- |
| `read`, `detail`, `queryset_request`, `extras` | `ModelQuerySetSchema` (`extras`: list of `ModelQuerySetExtraSchema`) | Relations to load for list, retrieve and the base queryset. `detail` falls back to `read`. `extras` adds named scopes |

```python
from ninja_aio.schemas import ModelQuerySetSchema


class Article(ModelSerializer):
    ...

    class QuerySet:
        read = ModelQuerySetSchema(select_related=["category"])
```

## NinjaAIOMeta

Optional inner class with names the framework uses instead of Django's `Meta`.

| Key | Default | Description |
| --- | --- | --- |
| `verbose_name` | `Meta.verbose_name` | Singular name, used in the OpenAPI tag |
| `verbose_name_plural` | `Meta.verbose_name_plural` | Plural name. Spaces become hyphens in the default URL path |
| `not_found_name` | Model name | Error text of `404` responses: `{"error": "<not_found_name>"}` |

```python
class Article(ModelSerializer):
    ...

    class NinjaAIOMeta:
        verbose_name_plural = "blog posts"  # -> /api/blog-posts
```

## See also

- [Schemas](../../guides/schemas.md)
- [Python CRUD](../../guides/python-crud.md)
- [Hooks](../../guides/hooks.md)
- [Serializer](serializers.md)
