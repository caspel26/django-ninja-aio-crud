---
type: concept
title: Schema generation
description: How the input and output schemas are built from your Schemas class, and when.
---

# Schema generation

The framework turns each `SchemaConfig` in your `Schemas` class into a Pydantic
schema. These schemas validate request bodies, shape responses and appear in the
OpenAPI docs.

## From Schemas to schemas

| Kind | Schema attribute | Generated name | Used for |
| --- | --- | --- | --- |
| `create` | `Article.create_schema` | `articleSchemaIn` | `POST` body, `create()` |
| `update` | `Article.update_schema` | `articleSchemaPatch` | `PATCH` body, `update()` |
| `read` | `Article.read_schema` | `articleSchemaOut` | List items, create and update responses, `model_dumps()` |
| `detail` | `Article.detail_schema` | `articleDetailSchemaOut` | Retrieve response, `model_dump()` |
| | `Article.related_schema` | `articleSchemaRelated` | This model nested inside another one |

The name is the lowercase model name plus a suffix. It's the name you see in the
OpenAPI docs and in generated clients.

Without a `detail` kind, the detail schema has the same fields as `read`.

## Built once, when first used

A schema is built the first time you access it, usually when a viewset is
registered at startup, then reused for every request. Reading
`Article.read_schema` twice gives you the same class.

```python
Article.read_schema is Article.get_schema("read")  # True
```

If you change a `Schemas` class at runtime, for example in a test, call
`Article.clear_schema_cache()` so the next access builds fresh schemas.

## Checked at startup

`python manage.py check`, `runserver` and the test runner validate every
`Schemas` class before the first request. A misspelled field or an option on
the wrong kind shows up as a system check error:

```text
blog.Article: (ninja_aio.E003) Article.Schemas.read references unknown field 'titel' on Article.
    HINT: Use a model field, relation accessor, or declare it in customs.
```

See [Schemas](../guides/schemas.md) for every check.

## Related objects

When a schema includes a relation to another serializer, the related object is
dumped with that serializer's `related_schema`: its `read` fields without its
own relations. That keeps responses finite when two models point to each other.

Use `relations_as_id` to return only the primary key instead. See
[Relations](../guides/relations.md).

## See also

- [Schemas](../guides/schemas.md)
- [Validation](../guides/validation.md)
- [Serialize objects](../guides/dumping.md)
