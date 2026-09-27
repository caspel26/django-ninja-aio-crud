---
type: reference
title: Decorators
description: Lookup page for the @action and @on decorators, HttpMethod and the view decorators.
---

# Decorators

`@action` and `@on` add custom endpoints to a view or viewset. For how to use
them, see [Custom actions](../../guides/custom-actions.md).

```python
from ninja_aio import action, on, HttpMethod
from ninja_aio.decorators import aatomic, decorate_view
```

## `@action`

```python
@action(detail=False, url_path="stats")
async def stats(self, request):
    ...
```

`detail` is required. `detail=True` adds the primary key to the path and works
only on `APIViewSet`. On `APIView` it raises `ImproperlyConfigured`.

## `@on`

```python
@on("publish")
async def publish(self, request, obj):
    ...
```

`@on(action_name)` is a detail action that loads the object for you. It works
only on `APIViewSet`. `action_name` is the path segment unless you pass
`url_path`.

## Options

`@action` and `@on` accept the same keyword options.

| Option | Type | Default | Description |
| --- | --- | --- | --- |
| `methods` | `list[HttpMethod \| str]` | `["get"]` for `@action`, `["post"]` for `@on` | HTTP methods. One route per method |
| `url_path` | `str \| None` | `None` | Path segment, used as written. `None` uses the method name with `_` as `-` (`@on`: `action_name`) |
| `url_name` | `str \| None` | `None` | Django URL name |
| `auth` | auth or `None` | `NOT_SET` | Auth for the route. `NOT_SET` uses the viewset auth for the HTTP method |
| `response` | schema or dict | `NOT_SET` | Response schema. `NOT_SET` lets Django Ninja infer it |
| `summary` | `str \| None` | `None` | OpenAPI summary. `None` builds one from the method and the name |
| `description` | `str \| None` | `None` | OpenAPI description |
| `tags` | `list[str] \| None` | `None` | OpenAPI tags. `None` uses the viewset tags |
| `deprecated` | `bool \| None` | `None` | Mark the route as deprecated in OpenAPI |
| `decorators` | `list[Callable] \| None` | `None` | Decorators applied to the handler, first one outermost |
| `throttle` | throttle or list | `NOT_SET` | Throttling. `NOT_SET` uses the API throttling |
| `include_in_schema` | `bool` | `True` | Show the route in OpenAPI |
| `openapi_extra` | `dict \| None` | `None` | Extra OpenAPI data for the operation |

An unknown value in `methods` raises `ValueError`.

## Handler signatures

The handler may be `def` or `async def`.

| Decorator | Signature |
| --- | --- |
| `@action(detail=False)` | `(self, request, ...)` |
| `@action(detail=True)` | `(self, request, pk, ...)` |
| `@on(...)` | `(self, request, obj)` |

Extra arguments are parsed by Django Ninja as query, path or body parameters.
In a detail action, name the key argument `pk` or after the model primary key,
like `id`. Every action runs `on_before_operation` first. `@on` also loads the
object and runs `on_before_object_operation`. Async handlers get the `a`
versions of the hooks.

## Resulting paths

For `prefix="articles"`:

| Decorator | Path |
| --- | --- |
| `@action(detail=False, url_path="stats")` | `GET /api/articles/stats` |
| `@action(detail=True)` on `mark_read` | `GET /api/articles/{id}/mark-read` |
| `@on("publish")` | `POST /api/articles/{id}/publish` |

No trailing slash is added to action paths.

## `HttpMethod`

A string enum. Plain strings like `"post"` are accepted too.

| Member | Value |
| --- | --- |
| `HttpMethod.GET` | `"get"` |
| `HttpMethod.POST` | `"post"` |
| `HttpMethod.PUT` | `"put"` |
| `HttpMethod.PATCH` | `"patch"` |
| `HttpMethod.DELETE` | `"delete"` |
| `HttpMethod.HEAD` | `"head"` |
| `HttpMethod.OPTIONS` | `"options"` |

## View decorators

| Decorator | Description |
| --- | --- |
| `aatomic` | Runs an async function inside a database transaction. Rolls back when it raises. Async functions only |
| `decorate_view(*decorators)` | Applies several decorators in stacking order. `None` entries are skipped |

```python
@action(detail=False, methods=["post"], decorators=[aatomic])
async def import_articles(self, request):
    ...
```

!!! deprecated "Deprecated in 3.0"

    `@api_get`, `@api_post`, `@api_put`, `@api_patch`, `@api_delete`, `@api_options` and `@api_head` are replaced by `@action`. See [Route decorators](../../migration/deprecations.md#route-decorators).

## See also

- [Custom actions](../../guides/custom-actions.md)
- [APIViewSet](api_view_set.md)
- [APIView](api_view.md)
