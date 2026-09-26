---
type: guide
title: Schemas
description: Choose which fields each endpoint accepts and returns with the Schemas class.
---

# Schemas

Schemas decide which fields your API accepts and returns. This page shows how
to declare them, every `SchemaConfig` option, and how to use the generated
schemas in your own code.

## Declare the schemas

Add a `Schemas` class to your model with one `SchemaConfig` for each kind:

```python title="blog/models.py"
from django.db import models
from ninja_aio import ModelSerializer, SchemaConfig


class Article(ModelSerializer):
    title = models.CharField(max_length=200)
    body = models.TextField()
    is_published = models.BooleanField(default=False)
    views = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    category = models.ForeignKey(
        Category, on_delete=models.CASCADE, related_name="articles"
    )

    class Schemas:
        create = SchemaConfig(
            fields=["title", "body", "category"],
            optionals=[("is_published", bool)],
        )
        update = SchemaConfig(
            optionals=[("title", str), ("body", str), ("is_published", bool)],
        )
        read = SchemaConfig(fields=["id", "title", "category", "created_at"])
        detail = SchemaConfig(
            fields=["id", "title", "body", "is_published", "views", "category", "created_at"],
        )
```

Each kind is used by these endpoints:

| Kind | Used for | When you omit it |
| --- | --- | --- |
| `create` | The body of `POST /api/articles/` | No create endpoint |
| `update` | The body of `PATCH /api/articles/{id}/` | No update endpoint |
| `read` | List items, and the create and update responses | No list or retrieve endpoints |
| `detail` | The response of `GET /api/articles/{id}` | The `read` fields are used |

With a `Serializer`, the `Schemas` class is the same. Only the `Meta` class
is added:

```python title="blog/serializers.py"
from ninja_aio import Serializer, SchemaConfig

from .models import Article


class ArticleSerializer(Serializer[Article]):
    class Meta:
        model = Article

    class Schemas:
        create = SchemaConfig(fields=["title", "body", "category"])
        read = SchemaConfig(fields=["id", "title", "category", "created_at"])
```

## SchemaConfig options

| Option | What it does |
| --- | --- |
| `fields` | Model fields to include. Input fields are required |
| `optionals` | Fields the client may leave out, as `(name, type)` pairs. They default to `None` |
| `customs` | Extra values that are not model fields, as `(name, type)` for required values or `(name, type, default)` |
| `excludes` | Include every model field except these |
| `relations_as_id` | Return these relations as their primary key. `read` and `detail` only |
| `nested` | Create related objects in the same request, like `{"comments": Comment}`. `create` on `ModelSerializer` only |
| `model_config` | A Pydantic `ConfigDict` for the generated schema |

An optional field that the client leaves out or sends as `null` is skipped.
On create the model default is used, on update the current value is kept.

A foreign key in `create` fields becomes `<name>_id` in the request body, like
`"category_id": 1`. In `update`, declare it as `optionals=[("category", int)]`.
See [Relations](relations.md) and [Nested writes](nested-writes.md).

## Accept extra input values

Use `customs` for values the client sends that are not saved on the model:

```python
create = SchemaConfig(
    fields=["title", "body", "category"],
    customs=[("notify_editors", bool, False)],
)
```

The request accepts `notify_editors`. Read its value in the `custom_actions`
hook, see [Hooks](hooks.md).

## Return computed values

In `read` and `detail`, a custom value comes from the attribute or property
with the same name on the object:

```python
class Article(ModelSerializer):
    # fields as above

    @property
    def summary(self) -> str:
        return self.body[:100]

    class Schemas:
        read = SchemaConfig(
            fields=["id", "title"],
            customs=[("summary", str, "")],
        )
```

When the object has no such attribute, the default is returned.

In `read` and `detail` you can also put the tuple straight into `fields`:

```python
read = SchemaConfig(fields=["id", "title", ("summary", str, "")])
```

!!! warning

    Inline tuples in `fields` only work in `read` and `detail`. For `create`
    and `update`, use `customs`.

## Change the schema settings

Pass a Pydantic `ConfigDict` to `model_config`:

```python
from pydantic import ConfigDict

create = SchemaConfig(
    fields=["title", "body", "category"],
    model_config=ConfigDict(str_strip_whitespace=True),
)
```

Here `"  Hello  "` is saved as `"Hello"`.

## Use the generated schemas

Each kind is available as a class attribute:

```python
Article.create_schema
Article.update_schema
Article.read_schema
Article.detail_schema
```

`Article.get_schema("read")` returns the same class as `Article.read_schema`.
A kind without a `SchemaConfig` returns `None`, except `detail`, which falls
back to the `read` fields.

Use them like any Pydantic model:

```python
data = Article.create_schema(title="Hello", body="...", category_id=1)
```

## Schema names in OpenAPI

The schemas appear in the OpenAPI document with the model name in lowercase:

| Kind | Name |
| --- | --- |
| `create` | `articleSchemaIn` |
| `update` | `articleSchemaPatch` |
| `read` | `articleSchemaOut` |
| `detail` | `articleDetailSchemaOut` |
| List response | `PaginatedarticleSchemaOut` |

## Catch mistakes at startup

Django checks your `Schemas` when the project starts. Run the checks
yourself with:

```bash
python manage.py check
```

| Code | Problem |
| --- | --- |
| `ninja_aio.E001` | An attribute of `Schemas` is not `create`, `update`, `read` or `detail` |
| `ninja_aio.E002` | A kind is not a `SchemaConfig` |
| `ninja_aio.E003` | A name in `fields`, `optionals`, `excludes`, `relations_as_id` or `nested` is not a field of the model |
| `ninja_aio.E004` | A field is listed in both `fields` and `optionals` |
| `ninja_aio.E005` | `relations_as_id` or `nested` is set on a kind that does not support it |
| `ninja_aio.E006` | A `relations_as_id` entry is not a relation |

## See also

- [Define the model](../tutorial/model.md)
- [Validation](validation.md)
- [Relations](relations.md)
- [Nested writes](nested-writes.md)
- [Choosing a serializer](../getting_started/choosing-a-serializer.md)
