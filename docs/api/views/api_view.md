---
type: reference
title: APIView
description: Lookup page for APIView registration, class attributes, custom routes and hooks.
---

# APIView

`APIView` groups endpoints that don't belong to a model. For how to use it,
see [Viewsets](../../guides/viewsets.md#add-endpoints-without-a-model).

```python
from ninja_aio import APIView
```

## Registration

```python
@api.view(prefix="/reports", tags=["Reports"])
class ReportsView(APIView):
    ...
```

| Argument | Type | Default | Description |
| --- | --- | --- | --- |
| `prefix` | `str` | required | URL path of the view |
| `tags` | `list[str] \| None` | `None` | OpenAPI tags. Takes precedence over `router_tags` |

`NinjaAIORouter` has the same `view()` decorator.

## Class attributes

| Attribute | Type | Default | Description |
| --- | --- | --- | --- |
| `api_route_path` | `str` | `""` | URL path, used when `prefix` is empty |
| `router_tag` | `str` | `""` | Single tag, used when `tags` and `router_tags` are empty. With no tag at all, Swagger lists the endpoints under `default` |
| `router_tags` | `list[str]` | `[]` | OpenAPI tags, used when `tags` is empty |
| `auth` | `list \| None` | `NOT_SET` | Auth for `@action` endpoints. `NOT_SET` uses the API auth, `None` makes them public |
| `error_schema` | `type[Schema]` | `GenericMessageSchema` | Schema documented for error responses |
| `router` | `Router` | set at registration | The Django Ninja router of the view |

## Actions

Methods decorated with `@action(detail=False)` become endpoints under the
prefix. The path defaults to the method name with `_` replaced by `-`.

```python
from ninja_aio import APIView, action


@api.view(prefix="/reports", tags=["Reports"])
class ReportsView(APIView):
    @action(detail=False, url_path="totals")
    async def totals(self, request):
        return {"articles": await Article.objects.acount()}
```

This adds `GET /api/reports/totals`. `@action(detail=True)` and `@on` need a
model and raise `ImproperlyConfigured` on an `APIView`. For all `@action`
options, see [Decorators](decorators.md).

## Methods

| Method | Description |
| --- | --- |
| `views()` | Called at registration. Add Django Ninja routes with `@self.router.get(...)`, `@self.router.post(...)` and so on |
| `on_before_operation(request, operation)` | Runs before each sync `@action`. `operation` is the method name |
| `aon_before_operation(request, operation)` | Runs before each async `@action` |

The hooks don't run for routes added in `views()`.

```python
@api.view(prefix="/health", tags=["Health"])
class HealthView(APIView):
    def views(self):
        @self.router.get("/version")
        def version(request):
            return {"version": "1.0"}
```

## See also

- [Viewsets](../../guides/viewsets.md#add-endpoints-without-a-model)
- [Custom actions](../../guides/custom-actions.md)
- [APIViewSet](api_view_set.md)
