---
type: guide
title: Choosing a serializer
description: Pick between ModelSerializer and Serializer. Both give you the same API.
---

# Choosing a serializer

There are two ways to describe your schemas. They produce the same endpoints and
the same Python methods, so you can mix them in one project.

| | `ModelSerializer` | `Serializer` |
| --- | --- | --- |
| Where schemas live | On the model | In a separate class |
| Changes your models | Yes, models inherit from it | No |
| Works with third-party models | No | Yes |
| Best for | New projects | Existing projects, shared or external models |

## ModelSerializer

The model itself carries the schemas.

```python title="blog/models.py"
from django.db import models
from ninja_aio import ModelSerializer, SchemaConfig


class Article(ModelSerializer):
    title = models.CharField(max_length=200)
    body = models.TextField()

    class Schemas:
        create = SchemaConfig(fields=["title", "body"])
        update = SchemaConfig(optionals=[("title", str), ("body", str)])
        read = SchemaConfig(fields=["id", "title", "body"])
```

```python title="blog/api.py"
@api.viewset(model=Article)
class ArticleViewSet(APIViewSet):
    pass
```

## Serializer

Your model stays a plain Django model. The serializer points to it with
`Meta.model`.

```python title="blog/models.py"
from django.db import models


class Article(models.Model):
    title = models.CharField(max_length=200)
    body = models.TextField()
```

```python title="blog/serializers.py"
from ninja_aio import Serializer, SchemaConfig

from .models import Article


class ArticleSerializer(Serializer[Article]):
    class Meta:
        model = Article

    class Schemas:
        create = SchemaConfig(fields=["title", "body"])
        update = SchemaConfig(optionals=[("title", str), ("body", str)])
        read = SchemaConfig(fields=["id", "title", "body"])
```

Pass it to the viewset with `serializer_class`:

```python title="blog/api.py"
@api.viewset(model=Article)
class ArticleViewSet(APIViewSet):
    serializer_class = ArticleSerializer
```

## The same in both

Everything else works the same way with either style:

- The `Schemas` class and its four kinds: `create`, `update`, `read` and `detail`.
- The Python methods, like `create()`, `get()` and `model_dump()`, and their async versions.
- Validators, hooks, relations, filtering and permissions.

```python
Article.create({"title": "Hello", "body": "..."})            # ModelSerializer
ArticleSerializer.create({"title": "Hello", "body": "..."})  # Serializer
```

## Next step

Follow the [tutorial](../tutorial/index.md) to build a complete API.
