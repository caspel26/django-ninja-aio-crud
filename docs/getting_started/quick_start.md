---
type: tutorial
title: Quick start
description: Build a working CRUD API with django-ninja-aio-crud in five minutes.
---

# Quick start

Build a complete CRUD API for one model in five minutes. You need a Django
project with an app called `blog` listed in `INSTALLED_APPS`.

<div class="nac-steps" markdown>

### Define the model

A `ModelSerializer` is a normal Django model with a `Schemas` class that says
which fields each operation reads and writes.

```python title="blog/models.py"
from django.db import models
from ninja_aio import ModelSerializer, SchemaConfig


class Article(ModelSerializer):
    title = models.CharField(max_length=200)
    body = models.TextField()
    is_published = models.BooleanField(default=False)
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
            fields=["id", "title", "body", "is_published", "created_at"],
        )
```

Create the table:

```bash
python manage.py makemigrations blog
python manage.py migrate
```

### Create the API

```python title="blog/api.py"
from ninja_aio import NinjaAIO, APIViewSet

from .models import Article

api = NinjaAIO(title="Blog API")


@api.viewset(model=Article)
class ArticleViewSet(APIViewSet):
    pass
```

### Add the URLs

```python title="project/urls.py"
from django.urls import path

from blog.api import api

urlpatterns = [
    path("api/", api.urls),
]
```

### Try it

```bash
python manage.py runserver
```

Open [http://localhost:8000/api/docs](http://localhost:8000/api/docs) to see the
interactive docs, or call the API directly:

```bash
curl -X POST localhost:8000/api/articles/ \
  -H "Content-Type: application/json" \
  -d '{"title": "Hello", "body": "My first article"}'
```

</div>

## What you get

| Method | Path | What it does |
| --- | --- | --- |
| `GET` | `/api/articles/` | List articles, with pagination |
| `POST` | `/api/articles/` | Create an article |
| `GET` | `/api/articles/{id}` | Get one article |
| `PATCH` | `/api/articles/{id}/` | Update some fields |
| `DELETE` | `/api/articles/{id}/` | Delete an article |

The list endpoint returns the items and the total count:

```json
{
  "items": [
    {"id": 1, "title": "Hello", "body": "My first article", "is_published": false, "created_at": "2026-09-26T10:00:00Z"}
  ],
  "count": 1
}
```

## Sync or async

Viewsets are async by default. To serve the same endpoints with regular sync
views, set `execution_mode`:

```python
@api.viewset(model=Article)
class ArticleViewSet(APIViewSet):
    execution_mode = "sync"
```

Paths, request bodies and responses stay exactly the same.

## Use it from Python

The model is also a CRUD API you can call in scripts, tasks and tests:

=== "Sync"

    ```python
    article = Article.create({"title": "Draft", "body": "..."})
    article = Article.update(article, {"is_published": True})
    data = Article.model_dump(article)
    ```

=== "Async"

    ```python
    article = await Article.acreate({"title": "Draft", "body": "..."})
    article = await Article.aupdate(article, {"is_published": True})
    data = await Article.amodel_dump(article)
    ```

## Next steps

- Keep your models as they are? See [choosing a serializer](choosing-a-serializer.md).
- Build a full API step by step in the [tutorial](../tutorial/index.md).
