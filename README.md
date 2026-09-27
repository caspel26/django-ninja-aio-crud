<p align="center">
  <img src="https://raw.githubusercontent.com/caspel26/django-ninja-aio-crud/main/docs/images/logo-full.png" alt="django-ninja-aio-crud">
</p>

<p align="center">
  <strong>CRUD framework for Django Ninja, sync or async</strong><br>
  Serializer-first schemas · Relations · Filtering · Pagination · Auth · Permissions
</p>

<p align="center">
  <a href="https://github.com/caspel26/django-ninja-aio-crud/actions/workflows/coverage.yml"><img src="https://github.com/caspel26/django-ninja-aio-crud/actions/workflows/coverage.yml/badge.svg" alt="Tests"></a>
  <a href="https://sonarcloud.io/summary/new_code?id=caspel26_django-ninja-aio-crud"><img src="https://sonarcloud.io/api/project_badges/measure?project=caspel26_django-ninja-aio-crud&metric=alert_status" alt="Quality Gate Status"></a>
  <a href="https://codecov.io/gh/caspel26/django-ninja-aio-crud/"><img src="https://codecov.io/gh/caspel26/django-ninja-aio-crud/graph/badge.svg?token=DZ5WDT3S20" alt="codecov"></a>
  <a href="https://pypi.org/project/django-ninja-aio-crud/"><img src="https://img.shields.io/pypi/v/django-ninja-aio-crud?color=g&logo=pypi&logoColor=white" alt="PyPI - Version"></a>
  <a href="LICENSE"><img src="https://img.shields.io/pypi/l/django-ninja-aio-crud" alt="PyPI - License"></a>
  <a href="https://github.com/astral-sh/ruff"><img src="https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json" alt="Ruff"></a>
  <a href="https://github.com/caspel26/django-ninja-aio-crud/actions/workflows/performance.yml"><img src="https://github.com/caspel26/django-ninja-aio-crud/actions/workflows/performance.yml/badge.svg" alt="Performance"></a>
</p>

<p align="center">
  <a href="https://django-ninja-aio.com">Documentation</a> ·
  <a href="https://pypi.org/project/django-ninja-aio-crud/">PyPI</a> ·
  <a href="https://django-ninja-aio.com/comparison/">Framework Comparison</a> ·
  <a href="https://caspel26.github.io/django-ninja-aio-crud/">Performance Benchmarks</a> ·
  <a href="https://github.com/caspel26/ninja-aio-blog-example">Example Project</a> ·
  <a href="https://github.com/caspel26/django-ninja-aio-crud/issues">Issues</a>
</p>

---

django-ninja-aio-crud builds complete REST APIs on top of Django Ninja. You say
which fields each operation reads and writes, register a viewset, and get
create, list, retrieve, update and delete endpoints with validation,
pagination and interactive docs. The same serializer is also a CRUD API you can
call from Python, in sync or async code.

## Features

| | Feature | Description |
|---|---|---|
| ⚡ | Sync and async | Every viewset runs async by default, or sync with `execution_mode = "sync"` |
| 🐍 | Python CRUD API | `create`, `get`, `update`, `destroy`, `model_dump` and their async versions on every serializer |
| 📐 | Schemas | Declare `create`, `update`, `read` and `detail` with `class Schemas` and `SchemaConfig` |
| 🔗 | Relations | Nested reads, relations as ids, and nested writes for child objects |
| 📦 | Bulk operations | Bulk create, update and delete with per-item results |
| 🔍 | Filtering | Filter, search, ordering and pagination mixins |
| 🛡️ | Permissions | Viewset and object-level permission checks, including role-based access |
| 🗑️ | Soft delete | Mark rows as deleted instead of removing them |
| 🔑 | Authentication | JWT bearer and cookie auth, with per-method settings |
| 🪝 | Hooks | Reactive `@on_create`, `@on_update` and `@on_delete` hooks on your models |
| 🧰 | Django admin | Register a `ModelSerializer` in the admin with `@register_admin` |
| 🤖 | MCP server | Expose your viewsets as [MCP](https://modelcontextprotocol.io) tools |
| 🔒 | Type safety | Generic `Serializer` and `APIViewSet` classes for IDE autocomplete |

## Install

```bash
pip install django-ninja-aio-crud
```

Requires Python 3.10-3.14, Django 5.2 or 6.0, and Django Ninja 1.7.x.

## Quick start

Define the model. A `ModelSerializer` is a normal Django model with a `Schemas`
class that says which fields each operation reads and writes.

```python
# blog/models.py
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

Create the API and add the URLs:

```python
# blog/api.py
from ninja_aio import NinjaAIO, APIViewSet

from .models import Article

api = NinjaAIO(title="Blog API")


@api.viewset(model=Article)
class ArticleViewSet(APIViewSet):
    pass
```

```python
# project/urls.py
from django.urls import path

from blog.api import api

urlpatterns = [
    path("api/", api.urls),
]
```

Run `python manage.py runserver` and open http://localhost:8000/api/docs.

| Method | Path | What it does |
| --- | --- | --- |
| `GET` | `/api/articles` | List articles, with pagination |
| `POST` | `/api/articles/` | Create an article |
| `GET` | `/api/articles/{id}` | Get one article |
| `PATCH` | `/api/articles/{id}/` | Update some fields |
| `DELETE` | `/api/articles/{id}/` | Delete an article |

## Keep your models as they are

Use a `Serializer` when you don't want to change your model's base class:

```python
# blog/serializers.py
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

```python
@api.viewset(model=Article)
class ArticleViewSet(APIViewSet):
    serializer_class = ArticleSerializer
```

## Sync or async

Viewsets are async by default. To serve the same endpoints with regular sync
views, set `execution_mode`:

```python
@api.viewset(model=Article)
class ArticleViewSet(APIViewSet):
    execution_mode = "sync"
```

The model is also a CRUD API you can call in scripts, tasks and tests:

```python
# Sync
article = Article.create({"title": "Draft", "body": "..."})
article = Article.update(article, {"is_published": True})
data = Article.model_dump(article)
```

```python
# Async
article = await Article.acreate({"title": "Draft", "body": "..."})
article = await Article.aupdate(article, {"is_published": True})
data = await Article.amodel_dump(article)
```

## Custom actions

```python
from ninja_aio import APIViewSet, action, on


@api.viewset(model=Article)
class ArticleViewSet(APIViewSet):
    @on("publish")
    async def publish(self, request, obj):
        obj.is_published = True
        await obj.asave(update_fields=["is_published"])
        return await Article.amodel_dump(obj)

    @action(detail=False, url_path="stats")
    async def stats(self, request):
        return {"total": await Article.objects.acount()}
```

This adds `POST /api/articles/{id}/publish` and `GET /api/articles/stats`.

## Validators

Add Pydantic validators to a `CreateValidators` or `UpdateValidators` class:

```python
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

## Upgrading from 2.x

Version 3 replaces the inner `ReadSerializer`/`CreateSerializer` classes and
`Meta.schema_in`/`schema_out` with a single `class Schemas`, adds sync
viewsets and the Python CRUD API. Follow the
[migration guide](https://django-ninja-aio.com/migration/) to upgrade.

## Links

- [Documentation](https://django-ninja-aio.com)
- [Tutorial](https://django-ninja-aio.com/tutorial/)
- [Guides](https://django-ninja-aio.com/guides/schemas/)
- [Release notes](https://django-ninja-aio.com/release_notes/)
- [Contributing](https://django-ninja-aio.com/contributing/)

## Support

If you find this project useful, consider giving it a star or supporting development:

<a href="https://buymeacoffee.com/caspel26"><img src="https://img.shields.io/badge/Buy%20me%20a%20coffee-FFDD00?style=for-the-badge&logo=buy-me-a-coffee&logoColor=black" alt="Buy me a coffee"></a>

## License

MIT License. See [LICENSE](LICENSE).
