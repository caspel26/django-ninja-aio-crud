---
type: guide
title: Viewsets
description: Register a viewset, configure its endpoints and change what each operation does.
---

# Viewsets

A viewset turns a model into REST endpoints. This page shows how to register
one, configure it with class attributes, and customize each operation.

## Register a viewset

```python title="blog/api.py"
from ninja_aio import NinjaAIO, APIViewSet

from .models import Article

api = NinjaAIO(title="Blog API")


@api.viewset(model=Article, prefix="articles", tags=["Articles"])
class ArticleViewSet(APIViewSet):
    pass
```

| Argument | What it does |
| --- | --- |
| `model` | The model to expose. Use a `ModelSerializer`, or a plain Django model with `serializer_class`. |
| `prefix` | The URL path. Defaults to the plural verbose name of the model, like `articles`. |
| `tags` | The OpenAPI tags. Defaults to the verbose name of the model. |

You get these endpoints:

| Method | Path | Status | Body | Response |
| --- | --- | --- | --- | --- |
| `GET` | `/api/articles` | 200 | | Paginated `read` |
| `POST` | `/api/articles/` | 201 | `create` | `read` |
| `GET` | `/api/articles/{id}` | 200 | | `detail` |
| `PATCH` | `/api/articles/{id}/` | 200 | `update` | `read` |
| `DELETE` | `/api/articles/{id}/` | 204 | | |

An endpoint is only created when its schema exists. Without an `update`
schema there is no `PATCH` endpoint. See [Schemas](schemas.md).

## Choose sync or async

!!! new "New in 3.0"

    `execution_mode` lets the same viewset serve sync views.

```python
@api.viewset(model=Article)
class ArticleViewSet(APIViewSet):
    execution_mode = "sync"
```

The default is `"async"`. URLs, schemas and responses are the same in both
modes. The methods you override follow the mode: plain names with `def` in
sync viewsets, `a`-prefixed names with `async def` in async viewsets.

## Configure the viewset

Set these class attributes on your viewset:

| Attribute | Default | What it does |
| --- | --- | --- |
| `serializer_class` | `None` | The `Serializer` to use when `model` is a plain Django model |
| `execution_mode` | `"async"` | `"async"` or `"sync"` views |
| `auth` | API auth | Authentication for every endpoint |
| `get_auth`, `post_auth`, `patch_auth`, `delete_auth` | `auth` | Authentication for one HTTP method. Set `None` to make it public |
| `disable` | `[]` | Endpoints to skip: `create`, `list`, `retrieve`, `update`, `delete`, `bulk_create`, `bulk_update`, `bulk_delete`, or `all` |
| `pagination_class` | `PageNumberPagination` | How the list is split in pages. See [Pagination](pagination.md) |
| `query_params` | `{}` | List filters as `{"name": (type, default)}`. See [Filtering](filtering.md) |
| `ordering_fields` | `[]` | Fields clients can sort by with `?ordering=` |
| `default_ordering` | `[]` | Ordering used when the client sends none, like `"-created_at"` |
| `bulk_operations` | `[]` | Bulk endpoints to add: `create`, `update`, `delete`. See [Bulk operations](bulk-operations.md) |
| `bulk_response_fields` | `None` | Fields returned for each bulk success. `None` returns the primary key |
| `m2m_relations` | `[]` | Endpoints for many-to-many relations. See [Relations](relations.md) |
| `require_update_fields` | `False` | Reject a `PATCH` with an empty body with `400` |
| `extra_decorators` | none | Decorators for each generated endpoint |
| `list_docs`, `create_docs`, `retrieve_docs`, `update_docs`, `delete_docs` | Short sentences | OpenAPI description of each endpoint |
| `bulk_create_docs`, `bulk_update_docs`, `bulk_delete_docs` | Short sentences | OpenAPI description of each bulk endpoint |
| `model_verbose_name`, `model_verbose_name_plural` | From the model | Names used in summaries like "Create Article" |
| `api_route_path` | `""` | The URL path, set in the class instead of `prefix` |

`disable = ["all"]` removes the five CRUD endpoints only. Bulk endpoints,
many-to-many endpoints and custom actions are still added.

Add decorators to single endpoints with `extra_decorators`:

```python
from ninja_aio.schemas.helpers import DecoratorsSchema


@api.viewset(model=Article)
class ArticleViewSet(APIViewSet):
    extra_decorators = DecoratorsSchema(list=[cache_for_a_minute])
```

Each field of `DecoratorsSchema` is named after an endpoint: `list`,
`retrieve`, `create`, `update`, `delete`, `bulk_create`, `bulk_update`,
`bulk_delete`.

## Change the schemas

Schemas come from the `Schemas` of your serializer. Set a schema attribute to
use a different one for a single endpoint:

| Attribute | Used for |
| --- | --- |
| `schema_in` | Create request body |
| `schema_update` | Update request body |
| `schema_out` | List items and default responses |
| `schema_detail` | Retrieve response |
| `schema_create_out` | Create response. Defaults to `schema_out` |
| `schema_update_out` | Update response. Defaults to `schema_out` |
| `schema_delete_out` | Delete response. When set, delete returns `200` with the deleted object instead of `204` |

```python
@api.viewset(model=Article)
class ArticleViewSet(APIViewSet):
    schema_delete_out = Article.read_schema
```

## Run code before each operation

Override the operation hook to run code before every endpoint, including bulk
endpoints and custom actions. `operation` is the name of the endpoint, like
`list`, `create` or `bulk_delete`, or the method name of a custom action.

=== "Sync"

    ```python
    @api.viewset(model=Article)
    class ArticleViewSet(APIViewSet):
        execution_mode = "sync"

        def on_before_operation(self, request, operation):
            logger.info("%s on articles", operation)
    ```

=== "Async"

    ```python
    @api.viewset(model=Article)
    class ArticleViewSet(APIViewSet):
        async def aon_before_operation(self, request, operation):
            logger.info("%s on articles", operation)
    ```

Raise an exception in the hook to stop the request.

| Hook | Runs | Arguments |
| --- | --- | --- |
| `on_before_operation` / `aon_before_operation` | Before every endpoint | `request`, `operation` |
| `on_before_object_operation` / `aon_before_object_operation` | After the object is loaded, before `@on` actions | `request`, `operation`, `obj` |
| `on_list_queryset` | On the list endpoint, before filters and pagination | `request`, `queryset` |

`on_list_queryset` is a plain `def` in both modes. Return the filtered
queryset:

```python
def on_list_queryset(self, request, queryset):
    return queryset.filter(is_published=True)
```

For checks on the object of retrieve, update and delete, use
`has_object_permission` from [Permissions](permissions.md).

!!! warning

    Override the hook that matches your mode. An async viewset that overrides
    only `on_before_operation` raises `ImproperlyConfigured` at startup, and so
    does an `async def on_before_operation`.

## Change an operation

Each endpoint calls a method you can override. Call `super()` to keep the
default behavior:

=== "Sync"

    ```python
    @api.viewset(model=Article)
    class ArticleViewSet(APIViewSet):
        execution_mode = "sync"

        def create(self, request, data):
            result = super().create(request, data)
            notify_editors(result.value["id"])
            return result
    ```

=== "Async"

    ```python
    @api.viewset(model=Article)
    class ArticleViewSet(APIViewSet):
        async def acreate(self, request, data):
            result = await super().acreate(request, data)
            await notify_editors(result.value["id"])
            return result
    ```

| Endpoint | Sync | Async | Arguments |
| --- | --- | --- | --- |
| Create | `create` | `acreate` | `request`, `data` |
| List | `list` | `alist` | `request`, `filters`, `ninja_pagination` |
| Retrieve | `retrieve` | `aretrieve` | `request`, `pk` |
| Update | `update` | `aupdate` | `request`, `data`, `pk` |
| Delete | `delete` | `adelete` | `request`, `pk` |
| Bulk create, update, delete | `bulk_create`, `bulk_update`, `bulk_delete` | `abulk_create`, `abulk_update`, `abulk_delete` | `request`, `data` |

These methods return a Django Ninja `Status`. `result.value` is the response
body. `pk` holds the primary key as an attribute, like `pk.id`.

## Add endpoints without a model

Use `APIView` for endpoints that don't belong to a model:

```python title="blog/api.py"
from ninja_aio import APIView, action


@api.view(prefix="/reports", tags=["Reports"])
class ReportsView(APIView):
    @action(detail=False, url_path="totals")
    async def totals(self, request):
        return {"articles": await Article.objects.acount()}
```

This adds `GET /api/reports/totals`. `APIView` supports `auth` and
`@action(detail=False)`. See [Custom actions](custom-actions.md).

Both classes also have a `views()` method. Add plain Django Ninja routes to
`self.router` there:

```python
@api.view(prefix="/health", tags=["Health"])
class HealthView(APIView):
    def views(self):
        @self.router.get("/version")
        def version(request):
            return {"version": "1.0"}
```

## See also

- [Create the CRUD API](../tutorial/crud.md)
- [Custom actions](custom-actions.md)
- [Routers](routers.md)
- [Permissions](permissions.md)
- [Hooks](hooks.md)
