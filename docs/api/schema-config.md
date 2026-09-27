---
type: reference
title: SchemaConfig
description: Lookup page for the SchemaConfig fields, the schema kinds and the startup checks that validate them.
---

# SchemaConfig

The field configuration of one generated schema, declared on a serializer's
`Schemas` class. For how to use it, see [Schemas](../guides/schemas.md).

```python
from ninja_aio import SchemaConfig
```

## Fields

`SchemaConfig` is a frozen dataclass. Every field is optional.

| Field | Type | Default | Kinds | Description |
| --- | --- | --- | --- | --- |
| `fields` | `list[str \| tuple]` | `[]` | all | Fields included in the schema |
| `optionals` | `list[tuple[str, type]]` | `[]` | all | Fields included as optional, with default `None` |
| `customs` | `list[tuple]` | `[]` | all | Extra fields that are not on the model |
| `excludes` | `list[str]` | `[]` | all | Fields left out of the schema |
| `relations_as_id` | `list[str]` | `[]` | `read`, `detail` | Relations returned as their primary key instead of a nested object |
| `nested` | `dict[str, Any]` | `{}` | `create`, `ModelSerializer` only | Relations written as nested objects in the request body |
| `model_config` | `dict \| None` | `None` | all | Pydantic `model_config` for the generated schema |

## Entry shapes

| Field | Entry | Meaning |
| --- | --- | --- |
| `fields` | `"title"` | A model field or relation accessor |
| `fields` | `("slug", str)` | Inline custom field, required |
| `fields` | `("slug", str, "")` | Inline custom field with a default |
| `optionals` | `("category", int)` | Optional field with its type |
| `customs` | `("notify", bool)` | Custom field, required |
| `customs` | `("notify", bool, False)` | Custom field with a default |

```python title="blog/models.py"
class Article(ModelSerializer):
    class Schemas:
        create = SchemaConfig(fields=["title", "body", "category"])
        read = SchemaConfig(fields=["id", "title", "category"], relations_as_id=["category"])
```

## Schema kinds

| Kind | Used for | When omitted |
| --- | --- | --- |
| `create` | Create request body | No create endpoint |
| `update` | Update request body | No update endpoint |
| `read` | List items, create and update responses | No list and no retrieve endpoint |
| `detail` | Retrieve response | `read` is used |

The delete endpoint does not need a schema.

Any other attribute name on `Schemas` fails the `ninja_aio.E001` check.
Attribute names that start with `_` are ignored.

## System checks

Django runs these checks at startup (`manage.py check`, `runserver`, `migrate`).

| Id | Raised when |
| --- | --- |
| `ninja_aio.E001` | A `Schemas` attribute is not one of `create`, `update`, `read`, `detail` |
| `ninja_aio.E002` | A kind is set to something that is not a `SchemaConfig` |
| `ninja_aio.E003` | A name in `fields`, `optionals`, `excludes`, `relations_as_id` or `nested` is not a field or relation accessor on the model |
| `ninja_aio.E004` | A name is in both `fields` and `optionals` |
| `ninja_aio.E005` | `relations_as_id` is set outside `read`/`detail`, or `nested` is set outside a `ModelSerializer` `create` schema |
| `ninja_aio.E006` | A `relations_as_id` entry is a field but not a relation |

Inline custom fields in `fields` and names in `customs` are not checked.

## See also

- [Schemas](../guides/schemas.md)
- [Schema generation](../concepts/schema-generation.md)
- [ModelSerializer](models/model_serializer.md)
- [Serializer](models/serializers.md)
