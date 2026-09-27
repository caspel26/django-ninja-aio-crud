---
type: reference
title: Serializer
description: Lookup page for the Meta-driven Serializer, its options, methods and hooks.
---

# Serializer

`Serializer` describes schemas, Python CRUD methods and hooks for a plain Django
model, in a separate class. To pick between it and `ModelSerializer`, see
[Choosing a serializer](../../getting_started/choosing-a-serializer.md).

```python
from ninja_aio import Serializer, SchemaConfig
```

```python title="blog/serializers.py"
class ArticleSerializer(Serializer[Article]):
    class Meta:
        model = Article

    class Schemas:
        create = SchemaConfig(fields=["title", "body", "category"])
        read = SchemaConfig(fields=["id", "title", "category"])
```

The generic parameter (`Serializer[Article]`) types the methods for your model.
Pass the class to a viewset with `serializer_class = ArticleSerializer`.

## Meta options

| Option | Type | Description |
| --- | --- | --- |
| `model` | Django model class | Required. The model this serializer works on |
| `relations_serializers` | `dict[str, Serializer \| str]` | Maps a relation field to the serializer used to nest it in `read` and `detail` output. Values can be a class, a class name in the same module, a dotted import path, or a `Union` of serializers |

Relations to a `ModelSerializer` model do not need an entry.

## Schemas and validators

`Serializer` uses the same `class Schemas:` kinds (`create`, `update`, `read`,
`detail`), schema attributes (`create_schema`, `read_schema`, ...,
`get_schema()`, `clear_schema_cache()`) and validator classes
(`CreateValidators`, `UpdateValidators`, `ReadValidators`, `DetailValidators`)
as `ModelSerializer`. See the table in
[ModelSerializer](model_serializer.md#schemas).

## Python methods

The classmethods are the same as on
[ModelSerializer](model_serializer.md#python-methods). They take and return
instances of `Meta.model`:

| Sync | Async | Returns |
| --- | --- | --- |
| `create(data, *, request=None)` | `acreate(...)` | `Article` |
| `get(pk=None, *, request=None, optimize_for=None, **lookups)` | `aget(...)` | `Article` |
| `get_queryset(*, request=None, optimize_for=None)` | `aget_queryset(...)` | `QuerySet[Article]` |
| `update(target, data, *, request=None)` | `aupdate(...)` | `Article` |
| `destroy(target, *, request=None)` | `adestroy(...)` | `None` |
| `model_dump(instance, *, schema=None, strict=False)` | `amodel_dump(instance, *, schema=None)` | `dict` |
| `model_dumps(instances, *, schema=None, strict=False)` | `amodel_dumps(instances, *, schema=None)` | `list[dict]` |
| `bulk_create` / `bulk_update` / `bulk_destroy` | `abulk_create` / `abulk_update` / `abulk_destroy` | `BulkResult` |

## Instance helpers

| Member | Description |
| --- | --- |
| `ArticleSerializer(instance=None)` | Binds an instance, so you can omit `instance` below |
| `await serializer.save(instance=None)` | Saves the instance and runs the save hooks |
| `has_changed(field, instance=None)` / `await ahas_changed(...)` | `True` if the value differs from the database |

## Hooks

Hooks on a `Serializer` receive the model instance as `instance`. Sync viewsets
call the plain names, async viewsets the `a` names. See
[Hooks](../../guides/hooks.md).

| Hook | Signature | Runs |
| --- | --- | --- |
| `queryset_request` / `aqueryset_request` | `(cls, request)` classmethod | Builds the base queryset for lookups, lists, updates and deletes |
| `post_create` / `apost_create` | `(self, instance)` | Once, after the object is created |
| `custom_actions` / `acustom_actions` | `(self, payload, instance)` | On create and update, with the `customs` fields as a dict |
| `on_create_before_save` | `(self, instance)` | Before the first save only |
| `before_save` | `(self, instance)` | Before every save |
| `on_create_after_save` | `(self, instance)` | After the first save only |
| `after_save` | `(self, instance)` | After every save |
| `on_delete` | `(self, instance)` | After the object is deleted |

The save and delete hooks run for writes made through the serializer (API,
Python methods, `save()`), not for a plain `instance.save()`.

```python
class ArticleSerializer(Serializer[Article]):
    ...

    def before_save(self, instance):
        instance.slug = slugify(instance.title)
```

!!! warning

    A method named `on_delete` hides the `@on_delete` decorator for the lines
    after it in the class body. Define the `on_delete` method after the
    decorated methods, or use `@hooks.on_delete` with
    `from ninja_aio.models import hooks`.

## See also

- [Choosing a serializer](../../getting_started/choosing-a-serializer.md)
- [Hooks](../../guides/hooks.md)
- [ModelSerializer](model_serializer.md)
