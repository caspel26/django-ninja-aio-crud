---
type: concept
title: Sync and async
description: How the sync and async execution modes relate, and which code runs in each.
---

# Sync and async

Every feature exists in a sync and an async version. They behave the same way:
same URLs, same schemas, same responses, same hooks in the same order.

## Two versions of every method

Sync methods use the plain name. Async methods start with `a`.

| Sync | Async |
| --- | --- |
| `Article.create()` | `await Article.acreate()` |
| `Article.get()` | `await Article.aget()` |
| `Article.model_dump()` | `await Article.amodel_dump()` |
| `post_create()` | `apost_create()` |
| `has_permission()` | `ahas_permission()` |
| `on_before_operation()` | `aon_before_operation()` |

Call the sync methods from sync code (scripts, management commands, Celery
tasks, WSGI views) and the async methods from async code.

## The viewset picks the mode

A viewset serves its generated endpoints in one mode:

```python
@api.viewset(model=Article)
class ArticleViewSet(APIViewSet):
    execution_mode = "sync"  # default: "async"
```

| `execution_mode` | Endpoints are | Hooks called |
| --- | --- | --- |
| `"async"` | `async def` views | `a`-prefixed hooks, like `ahas_permission` |
| `"sync"` | Regular `def` views | Plain hooks, like `has_permission` |

Custom actions follow their own definition: a `def` action runs sync, an
`async def` action runs async, whatever the viewset mode.

## Writing a hook for one mode only

If you override only one version of a serializer hook, the framework calls it
from the other mode too:

```python
class Article(ModelSerializer):
    def post_create(self):
        notify_editors(self.pk)
```

`post_create` runs after `Article.create()` and also after `await
Article.acreate()`.

Viewset hooks must match the viewset mode. An async viewset that overrides only
`has_permission` fails at startup with a message like `ArticleViewSet overrides
has_permission() but not ahas_permission(), which its async endpoints call.`

## Choosing a mode

| You run Django with | Use |
| --- | --- |
| ASGI (Uvicorn, Daphne, Granian) | `"async"` |
| WSGI (Gunicorn, uWSGI) | `"sync"` |

Both modes work on both servers. Matching the server avoids switching between
sync and async code on every request.

## See also

- [Deployment](../deployment.md)
- [Hooks](../guides/hooks.md)
- [Viewsets](../guides/viewsets.md)
