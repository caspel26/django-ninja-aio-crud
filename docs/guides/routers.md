---
type: guide
title: Routers
description: Group viewsets and views in a router and mount it on your API under one prefix.
---

# Routers

A `NinjaAIORouter` groups viewsets and views, so you can mount them on the
API together under one prefix, like `/api/v1`.

## Create a router

Register viewsets and views on the router with the same decorators you use
on the API:

```python title="blog/routers.py"
from ninja_aio import NinjaAIORouter, APIView, APIViewSet, action

from .models import Article, Category

router = NinjaAIORouter()


@router.viewset(model=Article, prefix="articles", tags=["Articles"])
class ArticleViewSet(APIViewSet):
    pass


@router.viewset(model=Category, prefix="categories", tags=["Categories"])
class CategoryViewSet(APIViewSet):
    pass


@router.view(prefix="/reports", tags=["Reports"])
class ReportsView(APIView):
    @action(detail=False, url_path="totals")
    async def totals(self, request):
        return {"articles": await Article.objects.acount()}
```

| Decorator | Arguments |
| --- | --- |
| `router.viewset(...)` | `model`, `prefix`, `tags`, like `api.viewset` |
| `router.view(...)` | `prefix` (required), `tags`, like `api.view` |

See [Viewsets](viewsets.md) for what each viewset generates.

## Mount the router

Add the router to the API with a prefix:

```python title="blog/api.py"
from ninja_aio import NinjaAIO

from .routers import router

api = NinjaAIO(title="Blog API")
api.add_router("/v1", router)
```

The endpoints move under the prefix. The article detail is now
`GET /api/v1/articles/{id}`, and the report is `GET /api/v1/reports/totals`.

Register everything on the router before Django loads your URLs.

You can also create and mount a router in one step with `@api.router`. The
class becomes the router instance:

```python
from ninja_aio import NinjaAIORouter


@api.router("/v1")
class V1Router(NinjaAIORouter):
    pass


@V1Router.viewset(model=Article, prefix="articles", tags=["Articles"])
class ArticleViewSet(APIViewSet):
    pass
```

Keyword arguments of `@api.router`, like `auth` or `tags`, are passed to
`api.add_router`.

## Set auth and tags for the whole router

Pass `auth` when you mount the router:

```python
from ninja_aio.auth import AsyncJwtBearer

api.add_router("/v1", router, auth=AsyncJwtBearer())
```

Every endpoint in the router without its own `auth` uses it. Viewset
settings like `auth`, `get_auth` or `auth=None` on an action still apply. See
[Authentication](authentication.md).

Pass `tags` when you create the router to add them to every endpoint in it,
next to the tags of each viewset:

```python
router = NinjaAIORouter(tags=["v1"])
```

`NinjaAIORouter` is a Django Ninja `Router`, so it also accepts `auth` and
`throttle`.

## Nest routers

Add a router to another router with `add_router`:

```python
v1 = NinjaAIORouter()
admin = NinjaAIORouter(tags=["Admin"])


@admin.view(prefix="/stats", tags=["Stats"])
class StatsView(APIView):
    @action(detail=False, url_path="daily")
    async def daily(self, request):
        return {"articles": await Article.objects.acount()}


v1.add_router("/admin", admin)
api.add_router("/v1", v1)
```

This adds `GET /api/v1/admin/stats/daily`. Prefixes add up from the API down
to the view.

## See also

- [Viewsets](viewsets.md)
- [Custom actions](custom-actions.md)
- [Authentication](authentication.md)
