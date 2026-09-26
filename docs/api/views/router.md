---
type: reference
title: NinjaAIORouter
description: Lookup page for NinjaAIORouter decorators, nesting and attaching it to the API.
---

# NinjaAIORouter

`NinjaAIORouter` is a Django Ninja `Router` with the `viewset()` and `view()`
decorators of `NinjaAIO`. For how to use it, see [Routers](../../guides/routers.md).

```python
from ninja_aio import NinjaAIORouter
```

## Constructor

`NinjaAIORouter(...)` accepts the same arguments as the Django Ninja `Router`,
like `auth`, `throttle` and `tags`.

## Decorators

```python
router = NinjaAIORouter()


@router.viewset(model=Article, prefix="articles", tags=["Articles"])
class ArticleViewSet(APIViewSet):
    pass
```

| Decorator | Arguments | Registers |
| --- | --- | --- |
| `viewset(model, prefix=None, tags=None)` | Same as `api.viewset()`. See [APIViewSet](api_view_set.md#registration) | An `APIViewSet` |
| `view(prefix, tags=None)` | URL path and OpenAPI tags | An `APIView` |

Both decorators return the view instance, not the class.

## Methods

| Method | Description |
| --- | --- |
| `add_router(prefix, router, ...)` | Nests another router under `prefix`. Same arguments as Django Ninja |
| `registered_viewsets()` | Viewsets on this router and its nested `NinjaAIORouter`s |
| `registered_views()` | Views on this router and its nested `NinjaAIORouter`s |

## Attach to the API

Use `api.add_router()`:

```python title="blog/api.py"
api.add_router("/v1", router)
```

Or decorate a subclass with `@api.router()`. It creates the router and
attaches it. Keyword arguments go to `api.add_router()`.

```python title="blog/api.py"
@api.router("/v1")
class V1Router(NinjaAIORouter):
    pass


@V1Router.viewset(model=Article, prefix="articles")
class ArticleViewSet(APIViewSet):
    pass
```

The article list is then at `GET /api/v1/articles`. Viewsets registered after
the router is attached are included.

`api.registered_viewsets()` and `api.registered_views()` include those of
attached `NinjaAIORouter`s.

## See also

- [Routers](../../guides/routers.md)
- [APIViewSet](api_view_set.md)
- [APIView](api_view.md)
