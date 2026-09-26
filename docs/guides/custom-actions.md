---
type: guide
title: Custom actions
description: Add your own endpoints to a viewset with @action and @on.
---

# Custom actions

Custom actions add endpoints next to the CRUD endpoints of a viewset. Use
`@on` for actions on one object and `@action` for everything else.

## Act on one object

```python title="blog/api.py"
from ninja_aio import NinjaAIO, APIViewSet, on

from .models import Article

api = NinjaAIO(title="Blog API")


@api.viewset(model=Article)
class ArticleViewSet(APIViewSet):
    @on("publish", response={200: Article.read_schema})
    async def publish(self, request, obj):
        obj.is_published = True
        await obj.asave(update_fields=["is_published"])
        return await Article.amodel_dump(obj, schema=Article.read_schema)
```

This adds `POST /api/articles/{id}/publish`. The article is loaded for you
and passed as `obj`. When it doesn't exist, the client gets `404` and your
method doesn't run.

`@on` accepts the same options as `@action`, except `detail`. The default
method is `POST`. The handler receives only `request` and `obj`. To read a
request body, use `@action(detail=True)`.

## Add a collection endpoint

```python
from ninja_aio import action


@api.viewset(model=Article)
class ArticleViewSet(APIViewSet):
    @action(detail=False, url_path="stats")
    async def stats(self, request):
        published = await Article.objects.filter(is_published=True).acount()
        return {"published": published}
```

This adds `GET /api/articles/stats`. Collection handlers receive `request`
and any parameters you declare.

## Add a detail endpoint

With `detail=True` the path includes the primary key and your handler
receives it as `pk`:

```python
from ninja import Schema


class RejectIn(Schema):
    reason: str


@api.viewset(model=Article)
class ArticleViewSet(APIViewSet):
    @action(detail=True, methods=["post"], url_path="reject")
    async def reject(self, request, pk: int, data: RejectIn):
        await Article.objects.filter(pk=pk).aupdate(is_published=False)
        return {"id": pk, "reason": data.reason}
```

This adds `POST /api/articles/{id}/reject`. Annotate `pk` with the type of
the primary key, like `pk: int`. Without an annotation it arrives as a
string. A parameter annotated with a `Schema` is read from the request body.

Unlike `@on`, `@action(detail=True)` doesn't load the object. Load it
yourself, for example with `await Article.aget(pk=pk)`.

## Choose the path

| Decorator | Path |
| --- | --- |
| `@action(detail=False)` on `stats` | `/api/articles/stats` |
| `@action(detail=False)` on `top_rated` | `/api/articles/top-rated` |
| `@action(detail=True)` on `reject` | `/api/articles/{id}/reject` |
| `@action(detail=False, url_path="summary/today")` | `/api/articles/summary/today` |
| `@on("publish")` | `/api/articles/{id}/publish` |

Without `url_path`, `@action` uses the method name with underscores replaced
by hyphens. `@on` uses its first argument. `url_path` is used exactly as you
write it, with no slash added.

## Return data and status codes

Return a dict or a schema instance to answer with `200`. Return a Django
Ninja `Status` to pick the code, and declare that code in `response`:

```python
from ninja import Status


@on("archive", response={202: Article.read_schema})
async def archive(self, request, obj):
    obj.is_published = False
    await obj.asave(update_fields=["is_published"])
    return Status(202, await Article.amodel_dump(obj, schema=Article.read_schema))
```

Without `response`, only `200` responses are allowed and the response isn't
validated.

## Pick the HTTP methods

Pass lowercase names or `HttpMethod` members. One endpoint is added for each
method, on the same path:

```python
from ninja_aio import HttpMethod


@action(detail=True, methods=[HttpMethod.GET, HttpMethod.POST], url_path="likes")
async def likes(self, request, pk: int):
    ...
```

`HttpMethod` has `GET`, `POST`, `PUT`, `PATCH`, `DELETE`, `HEAD` and
`OPTIONS`. Any other name, including uppercase strings like `"GET"`, raises
`ValueError`.

## Options

| Option | Default | What it does |
| --- | --- | --- |
| `detail` | required | `True` puts the primary key in the path. `@action` only |
| `methods` | `["get"]`, `["post"]` for `@on` | HTTP methods to register |
| `url_path` | Method name, action name for `@on` | Path segment after the viewset path |
| `url_name` | `None` | Django URL name for `reverse()` |
| `auth` | Viewset auth for the method | Authentication. `None` makes the endpoint public |
| `response` | Not set | Response schemas, like `{200: Article.read_schema}` |
| `summary` | Like "POST Publish Article" | OpenAPI summary |
| `description` | `None` | OpenAPI description |
| `tags` | Viewset tags | OpenAPI tags |
| `deprecated` | `None` | Mark the endpoint as deprecated in OpenAPI |
| `decorators` | `None` | Decorators for the handler. The first one is the outermost |
| `throttle` | Router and API throttles | Throttles for the endpoint |
| `include_in_schema` | `True` | Show the endpoint in OpenAPI |
| `openapi_extra` | `None` | Extra OpenAPI data for the operation |

An unknown option raises `TypeError`.

## Write sync or async handlers

The handler can be `def` or `async def`, in any viewset. The hooks follow
the handler: a `def` handler runs the sync hooks, an `async def` handler runs
the async ones.

=== "Sync"

    ```python
    @on("publish")
    def publish(self, request, obj):
        obj.is_published = True
        obj.save(update_fields=["is_published"])
        return {"id": obj.pk, "is_published": obj.is_published}
    ```

=== "Async"

    ```python
    @on("publish")
    async def publish(self, request, obj):
        obj.is_published = True
        await obj.asave(update_fields=["is_published"])
        return {"id": obj.pk, "is_published": obj.is_published}
    ```

## Run hooks and permissions

The `operation` passed to hooks is the method name, like `publish` or
`stats`.

| Decorator | Hooks that run |
| --- | --- |
| `@action` | `aon_before_operation` |
| `@on` | `aon_before_operation`, then the object lookup, then `aon_before_object_operation` |

The sync names (`on_before_operation`, `on_before_object_operation`) run for
`def` handlers. See [Viewsets](viewsets.md#run-code-before-each-operation).

With `PermissionViewSetMixin`, every action checks `has_permission(request,
operation)`, and `@on` actions also check `has_object_permission(request,
operation, obj)`:

```python
from ninja_aio.views.mixins import PermissionViewSetMixin


@api.viewset(model=Article)
class ArticleViewSet(PermissionViewSetMixin, APIViewSet):
    async def ahas_permission(self, request, operation):
        if operation == "publish":
            return request.auth.is_staff
        return True
```

A denied check answers `403`. See [Permissions](permissions.md).

## Set authentication

Without `auth`, an action uses the viewset setting for its HTTP method:

| Method | Uses |
| --- | --- |
| `GET`, `HEAD` | `get_auth` |
| `POST` | `post_auth` |
| `PATCH`, `PUT` | `patch_auth` |
| `DELETE` | `delete_auth` |
| `OPTIONS` | `auth` |

When the method setting isn't set, `auth` is used. Pass `auth=None` to make
a single action public.

## Add actions to an APIView

`APIView` supports `@action(detail=False)`. Every action uses the `auth` of
the view:

```python
from ninja_aio import APIView, action


@api.view(prefix="/reports", tags=["Reports"])
class ReportsView(APIView):
    @action(detail=False, url_path="totals")
    async def totals(self, request):
        return {"articles": await Article.objects.acount()}
```

This adds `GET /api/reports/totals`. `@action(detail=True)` and `@on` raise
`ImproperlyConfigured` on an `APIView`.

## See also

- [Viewsets](viewsets.md)
- [Permissions](permissions.md)
- [Routers](routers.md)
- [Hooks](hooks.md)
