---
type: reference
title: APIViewSet
description: Lookup page for APIViewSet arguments, class attributes, endpoints, methods and hooks.
---

# APIViewSet

`APIViewSet` turns a model into CRUD endpoints. For how to use it, see
[Viewsets](../../guides/viewsets.md).

```python
from ninja_aio import APIViewSet
```

## Registration

```python
@api.viewset(model=Article, prefix="articles", tags=["Articles"])
class ArticleViewSet(APIViewSet):
    pass
```

| Argument | Type | Default | Description |
| --- | --- | --- | --- |
| `model` | model class | required | A `ModelSerializer`, or a Django model with `serializer_class` |
| `prefix` | `str \| None` | `None` | URL path. Falls back to `api_route_path`, then to the plural verbose name with spaces as hyphens |
| `tags` | `list[str] \| None` | `None` | OpenAPI tags, used when `router_tags` is not set. Falls back to `[router_tag]` |

`NinjaAIORouter` has the same `viewset()` decorator.

## Class attributes

| Attribute | Type | Default | Description |
| --- | --- | --- | --- |
| `serializer_class` | `type[Serializer] \| None` | `None` | Serializer for a plain Django model |
| `execution_mode` | `"async" \| "sync"` | `"async"` | Mode of the generated endpoints |
| `auth` | `list \| None` | `NOT_SET` | Auth for every endpoint. `NOT_SET` uses the API auth, `None` makes it public |
| `get_auth`, `post_auth`, `patch_auth`, `delete_auth` | `list \| None` | `NOT_SET` | Auth for one HTTP method. `NOT_SET` uses `auth` |
| `m2m_relations` | `list[M2MRelationSchema]` | `[]` | Many-to-many endpoints to add |
| `m2m_auth` | `list \| None` | `NOT_SET` | Auth for the many-to-many endpoints. `NOT_SET` uses `get_auth` for the list and `patch_auth` for add/remove |
| `disable` | `list[str]` | `[]` | Endpoints to skip: `create`, `list`, `retrieve`, `update`, `delete`, `bulk_create`, `bulk_update`, `bulk_delete`, `all` |
| `pagination_class` | `type[AsyncPaginationBase]` | `PageNumberPagination` | Paginator of the list endpoint |
| `query_params` | `dict[str, tuple]` | `{}` | List filters as `{"name": (type, default)}` |
| `ordering_fields` | `list[str]` | `[]` | Fields accepted by `?ordering=` |
| `default_ordering` | `str \| list[str]` | `[]` | Ordering when the client sends none |
| `bulk_operations` | `list[str]` | `[]` | Bulk endpoints to add: `create`, `update`, `delete` |
| `bulk_response_fields` | `list[str] \| str \| None` | `None` | Value returned per bulk success. `None` returns the primary key |
| `require_update_fields` | `bool` | `False` | Reject an empty update body with `400` |
| `extra_decorators` | `DecoratorsSchema` | `DecoratorsSchema()` | Decorators per endpoint, one list per endpoint name |
| `schema_in` | `Schema \| None` | `None` | Create body. `None` uses the `create` schema |
| `schema_out` | `Schema \| None` | `None` | List items and default response. `None` uses the `read` schema |
| `schema_detail` | `Schema \| None` | `None` | Retrieve response. `None` uses the `detail` schema, then `schema_out` |
| `schema_update` | `Schema \| None` | `None` | Update body. `None` uses the `update` schema |
| `schema_create_out` | `Schema \| None` | `None` | Create response. `None` uses `schema_out` |
| `schema_update_out` | `Schema \| None` | `None` | Update response. `None` uses `schema_out` |
| `schema_delete_out` | `Schema \| None` | `None` | Delete response. When set, delete returns `200` with this schema |
| `list_docs`, `create_docs`, `retrieve_docs`, `update_docs`, `delete_docs` | `str` | Short sentence | OpenAPI description of each endpoint |
| `bulk_create_docs`, `bulk_update_docs`, `bulk_delete_docs` | `str` | Short sentence | OpenAPI description of each bulk endpoint |
| `model_verbose_name`, `model_verbose_name_plural` | `str` | `""` | Names in summaries. `""` uses `NinjaAIOMeta`, then the model `Meta` |
| `api_route_path` | `str` | `""` | URL path, set in the class instead of `prefix` |
| `router_tag` | `str` | `""` | Single tag. `""` uses `model_verbose_name` |
| `router_tags` | `list[str]` | `[]` | OpenAPI tags. Takes precedence over `tags` |
| `error_schema` | `type[Schema]` | `GenericMessageSchema` | Schema documented for `400`, `401`, `403` and `404` |

`disable = ["all"]` skips the five CRUD endpoints only.

## Generated endpoints

Paths for `prefix="articles"` with the default `NINJA_AIO_APPEND_SLASH = True`.
An endpoint is only added when its body schema exists (delete always is).

| Operation | Method | Path | Status | Body | Response |
| --- | --- | --- | --- | --- | --- |
| `list` | `GET` | `/api/articles` | 200 | | `{"items": [...], "count": N}` of `schema_out` |
| `create` | `POST` | `/api/articles/` | 201 | `schema_in` | `schema_create_out` |
| `retrieve` | `GET` | `/api/articles/{id}` | 200 | | `schema_detail` |
| `update` | `PATCH` | `/api/articles/{id}/` | 200 | `schema_update` | `schema_update_out` |
| `delete` | `DELETE` | `/api/articles/{id}/` | 204 | | none, or `schema_delete_out` with 200 |
| `bulk_create` | `POST` | `/api/articles/bulk/` | 200 | list of `schema_in` | `BulkResultSchema` |
| `bulk_update` | `PATCH` | `/api/articles/bulk/` | 200 | list of `schema_update` plus the primary key | `BulkResultSchema` |
| `bulk_delete` | `DELETE` | `/api/articles/bulk/` | 200 | `{"ids": [...]}` | `BulkResultSchema` |
| many-to-many list | `GET` | `/api/articles/{id}/tags` | 200 | | Paginated related objects |
| many-to-many add/remove | `POST` | `/api/articles/{id}/tags/` | 200 | `{"add": [...], "remove": [...]}` | `M2MSchemaOut` |

With `NINJA_AIO_APPEND_SLASH = False` no path ends with a slash. The
many-to-many path defaults to the plural verbose name of the related model.

## Operation methods

Each endpoint calls one of these methods. Sync viewsets call the plain names,
async viewsets the `a` names. They return a Django Ninja `Status`.

| Operation | Sync | Async | Arguments |
| --- | --- | --- | --- |
| Create | `create` | `acreate` | `request`, `data` |
| List | `list` | `alist` | `request`, `filters`, `ninja_pagination` |
| Retrieve | `retrieve` | `aretrieve` | `request`, `pk` |
| Update | `update` | `aupdate` | `request`, `data`, `pk` |
| Delete | `delete` | `adelete` | `request`, `pk` |
| Bulk create | `bulk_create` | `abulk_create` | `request`, `data` |
| Bulk update | `bulk_update` | `abulk_update` | `request`, `data` |
| Bulk delete | `bulk_delete` | `abulk_delete` | `request`, `data` |

`pk` is a schema with the primary key as attribute, like `pk.id`.

## Hooks

Override the name that matches the mode. A mismatch raises
`ImproperlyConfigured` at startup. See [Request lifecycle](../../concepts/lifecycle.md).

| Hook | Arguments | Runs |
| --- | --- | --- |
| `on_before_operation` / `aon_before_operation` | `request`, `operation` | Before every endpoint, bulk endpoint and custom action |
| `on_before_object_operation` / `aon_before_object_operation` | `request`, `operation`, `obj` | After the object is loaded in `@on` actions. On retrieve, update and delete only with `PermissionViewSetMixin` or `SoftDeleteViewSetMixin` |
| `on_list_queryset` | `request`, `queryset` | On list, before filters and pagination. Plain `def` in both modes. Returns the queryset |
| `query_params_handler` / `aquery_params_handler` | `queryset`, `filters` | On list, with the filter values as a dict. Returns the queryset |
| `views()` | none | At registration. Add Django Ninja routes to `self.router` |

::: ninja_aio.views.api.API.aon_before_operation
    options:
      show_root_heading: true
      show_root_full_path: false

::: ninja_aio.views.api.APIViewSet.aon_before_object_operation
    options:
      show_root_heading: true
      show_root_full_path: false

::: ninja_aio.views.api.APIViewSet.on_list_queryset
    options:
      show_root_heading: true
      show_root_full_path: false

Custom endpoints use `@action` and `@on`. See [Custom actions](../../guides/custom-actions.md).

## Shipped subclasses

```python
from ninja_aio.views import ReadOnlyViewSet, WriteOnlyViewSet
```

| Class | `disable` | Endpoints |
| --- | --- | --- |
| `ReadOnlyViewSet` | `["create", "update", "delete"]` | List and retrieve |
| `WriteOnlyViewSet` | `["list", "retrieve"]` | Create, update and delete |

Mixins for filters, permissions and soft delete are listed in [Mixins](mixins.md).

## See also

- [Viewsets](../../guides/viewsets.md)
- [Custom actions](../../guides/custom-actions.md)
- [Request lifecycle](../../concepts/lifecycle.md)
- [APIView](api_view.md)
