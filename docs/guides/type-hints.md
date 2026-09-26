---
type: guide
title: Type hints
description: Get typed models, schemas and hooks in your editor and type checker.
---

# Type hints

The framework is typed, so your editor and type checkers like mypy and
Pyright know which model you get back. This page shows what is typed and
where you add the model type yourself.

## Get typed results from a ModelSerializer

A `ModelSerializer` needs nothing extra. Its methods return the model class
you call them on:

=== "Sync"

    ```python
    article = Article.create({"title": "Hello", "body": "...", "category_id": 1})
    article = Article.get(pk=1)
    article = Article.update(article, {"title": "Hi"})
    result = Article.bulk_create([{"title": "A", "body": "...", "category_id": 1}])
    ```

=== "Async"

    ```python
    article = await Article.acreate({"title": "Hello", "body": "...", "category_id": 1})
    article = await Article.aget(pk=1)
    article = await Article.aupdate(article, {"title": "Hi"})
    ```

| Call | Type |
| --- | --- |
| `create()`, `acreate()` | `Article` |
| `get()`, `aget()` | `Article` |
| `update()`, `aupdate()` | `Article` |
| `bulk_create()` | `BulkResult[Article]`, so `result.succeeded` is `list[Article]` |
| `model_dump()`, `amodel_dump()` | `dict[str, Any]` |
| `model_dumps()`, `amodel_dumps()` | `list[dict[str, Any]]` |

The arguments are typed too: `model_dump()` takes an `Article`, and
`update()` takes an `Article` or a primary key.

## Type a Serializer

A `Serializer` describes a plain Django model. Put the model in brackets so
the type checker knows it:

```python title="blog/serializers.py"
from ninja_aio import Serializer, SchemaConfig

from .models import Article


class ArticleSerializer(Serializer[Article]):
    class Meta:
        model = Article

    class Schemas:
        create = SchemaConfig(fields=["title", "body", "category"])
        read = SchemaConfig(fields=["id", "title", "category"])
```

Now the same methods return `Article`:

```python
article = ArticleSerializer.create({"title": "Hello", "body": "...", "category_id": 1})
result = ArticleSerializer.bulk_create([...])  # BulkResult[Article]
```

Without `[Article]`, the type checker cannot tell which model you get back.

## Type a viewset

Write `APIViewSet[Article]` to type the model in your viewset methods:

```python title="blog/api.py"
from ninja_aio import APIViewSet
from ninja_aio.exceptions import ForbiddenError

from .models import Article


@api.viewset(model=Article)
class ArticleViewSet(APIViewSet[Article]):
    async def aon_before_object_operation(self, request, operation, obj):
        if operation == "delete" and obj.is_published:
            raise ForbiddenError()
```

| Name | Type |
| --- | --- |
| `self.model` | `type[Article]` |
| `obj` in `on_before_object_operation` / `aon_before_object_operation` | `Article` |
| `obj` in `has_object_permission` / `ahas_object_permission` | `Article` |

Mixins take the model the same way:

```python
from ninja_aio.views.mixins import PermissionViewSetMixin


@api.viewset(model=Article)
class ArticleViewSet(PermissionViewSetMixin[Article], APIViewSet[Article]):
    async def ahas_object_permission(self, request, operation, obj):
        return obj.is_published or operation != "retrieve"
```

`@api.viewset` keeps your class type. After the decorator, `ArticleViewSet`
is the registered viewset, typed as `ArticleViewSet`.

## Use schema attributes

`read_schema`, `detail_schema`, `create_schema`, `update_schema` and
`related_schema` are typed `type[Schema] | None`. They are `None` when you do
not declare that kind, so check before you use one:

```python
schema = Article.read_schema
assert schema is not None
print(schema.model_json_schema())
```

`get_schema("read", depth=2)` has the same type.

## Type request.auth

Django's `HttpRequest` has no `auth` attribute, so type checkers do not know
what your auth class stored there. Read it through a small typed helper:

```python title="blog/auth.py"
from django.contrib.auth.models import User
from django.http import HttpRequest


def current_user(request: HttpRequest) -> User | None:
    return getattr(request, "auth", None)
```

```python
user = current_user(request)
if user is not None:
    print(user.username)
```

The helper returns whatever your `auth_handler` returned, or `None` on
endpoints without authentication. Use your own user model in the annotation
if you have one.

## See also

- [Python CRUD](python-crud.md)
- [Viewsets](viewsets.md)
- [Permissions](permissions.md)
- [Authentication](authentication.md)
- [Choosing a serializer](../getting_started/choosing-a-serializer.md)
