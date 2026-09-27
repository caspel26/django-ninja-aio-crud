---
type: tutorial
step: 2
steps: 7
title: Create the CRUD API
description: Expose the Article endpoints with a viewset and add custom actions.
---

# Create the CRUD API

In this step you turn the model into REST endpoints and add two custom
actions.

<div class="nac-steps" markdown>

### Register a viewset

```python title="blog/api.py"
from ninja_aio import NinjaAIO, APIViewSet

from .models import Article

api = NinjaAIO(title="Blog API", version="1.0.0")


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

### Open the docs

Run `python manage.py runserver` and open
[http://localhost:8000/api/docs](http://localhost:8000/api/docs).

</div>

You now have five endpoints:

| Method | Path | Status | Body | Response |
| --- | --- | --- | --- | --- |
| `GET` | `/api/articles` | 200 | | Paginated `read` |
| `POST` | `/api/articles/` | 201 | `create` | `read` |
| `GET` | `/api/articles/{id}` | 200 | | `detail` |
| `PATCH` | `/api/articles/{id}/` | 200 | `update` | `read` |
| `DELETE` | `/api/articles/{id}/` | 204 | | |

The list endpoint is paginated with `?page=` and `?page_size=`:

```json
{
  "items": [{"id": 1, "title": "Hello", "is_published": false, "created_at": "2026-09-26T10:00:00Z"}],
  "count": 1
}
```

## Choose sync or async

Viewsets run async by default. Set `execution_mode = "sync"` to serve the same
endpoints with sync views, for example when your project runs on WSGI.

```python
@api.viewset(model=Article)
class ArticleViewSet(APIViewSet):
    execution_mode = "sync"
```

URLs, schemas and responses are the same in both modes. The code you write
inside the viewset follows the mode: plain `def` methods for sync, `async def`
for async.

## Add a custom action

Use `@on` for actions on one object. The object is loaded for you and a missing
`id` returns `404`.

=== "Sync"

    ```python title="blog/api.py"
    from ninja_aio import NinjaAIO, APIViewSet, on


    @api.viewset(model=Article)
    class ArticleViewSet(APIViewSet):
        execution_mode = "sync"

        @on("publish")
        def publish(self, request, obj):
            obj.is_published = True
            obj.save(update_fields=["is_published"])
            return Article.model_dump(obj)
    ```

=== "Async"

    ```python title="blog/api.py"
    from ninja_aio import NinjaAIO, APIViewSet, on


    @api.viewset(model=Article)
    class ArticleViewSet(APIViewSet):
        @on("publish")
        async def publish(self, request, obj):
            obj.is_published = True
            await obj.asave(update_fields=["is_published"])
            return await Article.amodel_dump(obj)
    ```

This adds `POST /api/articles/{id}/publish`.

Use `@action(detail=False)` for actions on the whole collection:

=== "Sync"

    ```python
    from ninja_aio import action


    @action(detail=False, url_path="stats")
    def stats(self, request):
        return {
            "total": Article.objects.count(),
            "published": Article.objects.filter(is_published=True).count(),
        }
    ```

=== "Async"

    ```python
    from ninja_aio import action


    @action(detail=False, url_path="stats")
    async def stats(self, request):
        return {
            "total": await Article.objects.acount(),
            "published": await Article.objects.filter(is_published=True).acount(),
        }
    ```

This adds `GET /api/articles/stats`. Pass `methods=["post"]` to change the
HTTP method.

## Turn off endpoints

List the endpoints you don't want in `disable`:

```python
@api.viewset(model=Article)
class ArticleViewSet(APIViewSet):
    disable = ["delete"]
```

Leaving a kind out of `Schemas` has the same effect. Without an `update`
schema, there is no `PATCH` endpoint.

[Next: add relations](relations.md){ .md-button .md-button--primary }
