---
type: tutorial
step: 1
steps: 7
title: Define the model
description: Create the Article model and describe what each operation reads and writes.
---

# Define the model

In this step you create the `Article` model and tell the framework which
fields each operation uses.

## Schema kinds

Every operation has its own schema. You only declare the ones you need.

| Kind | Used for | If you leave it out |
| --- | --- | --- |
| `create` | The body of `POST` | No create endpoint |
| `update` | The body of `PATCH` | No update endpoint |
| `read` | List responses and single objects | No list or retrieve endpoints |
| `detail` | Single object responses | `read` is used instead |

## Write the model

Choose where the schemas live. Both options give you the same API, see
[choosing a serializer](../getting_started/choosing-a-serializer.md).

=== "ModelSerializer"

    ```python title="blog/models.py"
    from django.db import models
    from ninja_aio import ModelSerializer, SchemaConfig


    class Article(ModelSerializer):
        title = models.CharField(max_length=200)
        body = models.TextField()
        is_published = models.BooleanField(default=False)
        views = models.PositiveIntegerField(default=0)
        created_at = models.DateTimeField(auto_now_add=True)

        class Schemas:
            create = SchemaConfig(
                fields=["title", "body"],
                optionals=[("is_published", bool)],
            )
            update = SchemaConfig(
                optionals=[("title", str), ("body", str), ("is_published", bool)],
            )
            read = SchemaConfig(
                fields=["id", "title", "is_published", "created_at"],
            )
            detail = SchemaConfig(
                fields=["id", "title", "body", "is_published", "views", "created_at"],
            )
    ```

=== "Serializer"

    ```python title="blog/models.py"
    from django.db import models


    class Article(models.Model):
        title = models.CharField(max_length=200)
        body = models.TextField()
        is_published = models.BooleanField(default=False)
        views = models.PositiveIntegerField(default=0)
        created_at = models.DateTimeField(auto_now_add=True)
    ```

    ```python title="blog/serializers.py"
    from ninja_aio import Serializer, SchemaConfig

    from .models import Article


    class ArticleSerializer(Serializer[Article]):
        class Meta:
            model = Article

        class Schemas:
            create = SchemaConfig(
                fields=["title", "body"],
                optionals=[("is_published", bool)],
            )
            update = SchemaConfig(
                optionals=[("title", str), ("body", str), ("is_published", bool)],
            )
            read = SchemaConfig(
                fields=["id", "title", "is_published", "created_at"],
            )
            detail = SchemaConfig(
                fields=["id", "title", "body", "is_published", "views", "created_at"],
            )
    ```

The list shows a short version of each article, and a single article shows
the full text.

The rest of the tutorial shows the `ModelSerializer` version. With a
`Serializer`, put the same `Schemas` on your serializer class.

## SchemaConfig options

| Option | What it does |
| --- | --- |
| `fields` | Required fields, in the order they appear |
| `optionals` | Fields the client may leave out, as `(name, type)` pairs |
| `customs` | Extra values that are not model fields, as `(name, type, default)` |
| `excludes` | Every field except these |

## Validate input

Add Pydantic validators to a `CreateValidators` or `UpdateValidators` class:

```python title="blog/models.py"
from pydantic import field_validator


class Article(ModelSerializer):
    # fields and Schemas as above

    class CreateValidators:
        @field_validator("title")
        @classmethod
        def title_not_blank(cls, value: str) -> str:
            if not value.strip():
                raise ValueError("Title cannot be blank")
            return value.strip()
```

Invalid input returns `422` with the error message.

## Create the table

```bash
python manage.py makemigrations blog
python manage.py migrate
```

Django checks your `Schemas` when it starts. A typo in a field name shows up as
an error before the first request:

```bash
python manage.py check
```

## Try it from Python

Open `python manage.py shell` and use the model directly:

=== "Sync"

    ```python
    from blog.models import Article

    article = Article.create({"title": "Hello", "body": "First post"})
    Article.model_dump(article)
    # {'id': 1, 'title': 'Hello', 'body': 'First post', 'is_published': False, ...}
    ```

=== "Async"

    ```python
    from blog.models import Article

    article = await Article.acreate({"title": "Hello", "body": "First post"})
    await Article.amodel_dump(article)
    # {'id': 1, 'title': 'Hello', 'body': 'First post', 'is_published': False, ...}
    ```

`model_dump()` uses the `detail` schema. Pass `schema=Article.read_schema` to get
the short version.

[Next: create the CRUD API](crud.md){ .md-button .md-button--primary }
