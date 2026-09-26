---
type: reference
title: Mixins
description: Lookup page for the viewset mixins and the filter schemas they use.
---

# Mixins

Mixins add filtering, permissions, search, soft delete and field selection to
an `APIViewSet`. Put them before `APIViewSet` in the class bases. For how to use
them, see [Filtering](../../guides/filtering.md).

```python
from ninja_aio.views.mixins import IcontainsFilterViewSetMixin, PermissionViewSetMixin
from ninja_aio.schemas import RelationFilterSchema, MatchCaseFilterSchema
```

```python
class ArticleViewSet(IcontainsFilterViewSetMixin, APIViewSet):
    model = Article
    query_params = {"title": (str, None)}
```

## Filter mixins

Filter mixins read the values declared in `query_params` and apply them to the
list endpoint. Each one overrides `query_params_handler` (sync) and
`aquery_params_handler` (async) and calls `super()` first, so you can combine
them. Field names that are not valid model fields or lookups are ignored.

| Mixin | Values it uses | Lookup |
| --- | --- | --- |
| `IcontainsFilterViewSetMixin` | `str` | `field__icontains=value` |
| `BooleanFilterViewSetMixin` | `bool` | `field=value` |
| `NumericFilterViewSetMixin` | `int`, `float` | `field=value` |
| `DateFilterViewSetMixin` | `date`, `datetime` | `field=value` |
| `GreaterDateFilterViewSetMixin` | `date`, `datetime` | `field__gt=value` |
| `LessDateFilterViewSetMixin` | `date`, `datetime` | `field__lt=value` |
| `GreaterEqualDateFilterViewSetMixin` | `date`, `datetime` | `field__gte=value` |
| `LessEqualDateFilterViewSetMixin` | `date`, `datetime` | `field__lte=value` |

These mixins add no attributes. The query parameters are the keys of
`query_params`. Values that are `None` are skipped.

## `IcontainsFilterViewSetMixin`

Filters string values with a case-insensitive substring match.

## `BooleanFilterViewSetMixin`

Filters boolean values with an exact match.

## `NumericFilterViewSetMixin`

Filters integer and float values with an exact match.

## `DateFilterViewSetMixin`

Filters date and datetime values with an exact match. It is the base of the
four date mixins below.

## `GreaterDateFilterViewSetMixin`

Keeps rows whose date is after the value (`__gt`).

## `LessDateFilterViewSetMixin`

Keeps rows whose date is before the value (`__lt`).

## `GreaterEqualDateFilterViewSetMixin`

Keeps rows whose date is on or after the value (`__gte`).

## `LessEqualDateFilterViewSetMixin`

Keeps rows whose date is on or before the value (`__lte`).

## `RelationFilterViewSetMixin`

Maps a query parameter to a lookup on a related model.

| Attribute | Type | Default | Description |
| --- | --- | --- | --- |
| `relations_filters` | `list[RelationFilterSchema]` | `[]` | One entry per query parameter |

Each `query_param` is added to `query_params` for you. A value is applied as
`queryset.filter(<query_filter>=value)` unless it is `None`.

```python
relations_filters = [
    RelationFilterSchema(
        query_param="category",
        query_filter="category__id",
        filter_type=(int, None),
    ),
]
# GET /api/articles?category=1
```

## `MatchCaseFilterViewSetMixin`

Maps a boolean query parameter to one condition for `true` and one for `false`.

| Attribute | Type | Default | Description |
| --- | --- | --- | --- |
| `filters_match_cases` | `list[MatchCaseFilterSchema]` | `[]` | One entry per query parameter |

Each `query_param` is added to `query_params` for you. When the parameter is
missing, nothing is filtered.

## Filter schemas

Import them from `ninja_aio.schemas`.

### `RelationFilterSchema`

| Field | Type | Default | Description |
| --- | --- | --- | --- |
| `query_param` | `str` | required | Query parameter name |
| `query_filter` | `str` | required | ORM lookup, like `category__id` |
| `filter_type` | `tuple[type, Any]` | required | Type and default, like `(int, None)` |

### `MatchCaseFilterSchema`

| Field | Type | Default | Description |
| --- | --- | --- | --- |
| `query_param` | `str` | required | Query parameter name |
| `cases` | `BooleanMatchFilterSchema` | required | Conditions for `true` and `false` |
| `filter_type` | `tuple[type, Any]` | `(bool, None)` | Type and default |

### `BooleanMatchFilterSchema`

| Field | Type | Default | Description |
| --- | --- | --- | --- |
| `true` | `MatchConditionFilterSchema` | required | Applied when the value is `true` |
| `false` | `MatchConditionFilterSchema` | required | Applied when the value is `false` |

### `MatchConditionFilterSchema`

| Field | Type | Default | Description |
| --- | --- | --- | --- |
| `query_filter` | `dict[str, Any] \| Q` | required | Lookups, like `{"is_published": True}`, or a `Q` object |
| `include` | `bool` | `True` | `True` uses `filter()`, `False` uses `exclude()` |

## `PermissionViewSetMixin`

Adds permission checks to every endpoint. All hooks allow everything by default.
For how to use it, see [Permissions](../../guides/permissions.md).

| Hook | Sync | Async | Return |
| --- | --- | --- | --- |
| View-level check | `has_permission(request, operation)` | `ahas_permission(request, operation)` | `bool` |
| Object-level check | `has_object_permission(request, operation, obj)` | `ahas_object_permission(request, operation, obj)` | `bool` |
| Row filter for list | `get_permission_queryset(request, queryset)` | same method in both modes | `QuerySet` |

Returning `False` raises a 403. The view-level check runs from
`on_before_operation` / `aon_before_operation`, before any query. The
object-level check runs from `on_before_object_operation` /
`aon_before_object_operation`, after the object is loaded. The row filter runs
from `on_list_queryset`.

| `operation` | Checks |
| --- | --- |
| `"create"`, `"list"`, `"bulk_create"`, `"bulk_update"`, `"bulk_delete"` | View-level |
| `"retrieve"`, `"update"`, `"delete"` | View-level and object-level |
| action name | View-level, plus object-level for `@on` |

## `RoleBasedPermissionMixin`

A `PermissionViewSetMixin` that allows operations by role.

| Attribute | Type | Default | Description |
| --- | --- | --- | --- |
| `permission_roles` | `dict[str, list[str]]` | `{}` | Role to allowed operations. Empty allows everything |
| `role_attribute` | `str` | `"role"` | Attribute (or dict key) read from `request.auth` |

It overrides `has_permission` and `ahas_permission`. When `request.auth` is
`None` or has no role, every operation is denied.

## `SearchViewSetMixin`

Adds a search parameter that matches any of the listed fields with
`__icontains`, joined with OR.

| Attribute | Type | Default | Description |
| --- | --- | --- | --- |
| `search_fields` | `list[str]` | `[]` | Fields to search. Related lookups like `category__name` work. Empty disables search |
| `search_param` | `str` | `"search"` | Query parameter name |

Query parameter: `GET /api/articles?search=django`. Applies to the list endpoint.

## `SoftDeleteViewSetMixin`

Replaces delete with setting a boolean flag. For how to use it, see
[Soft delete](../../guides/soft-delete.md).

| Attribute | Type | Default | Description |
| --- | --- | --- | --- |
| `soft_delete_field` | `str` | `"is_deleted"` | Boolean model field. A missing field raises `ImproperlyConfigured` |
| `include_deleted` | `bool` | `False` | Show soft-deleted rows in list and retrieve |

| Method | Sync | Async | Behavior |
| --- | --- | --- | --- |
| Delete | `delete` | `adelete` | Sets the flag, returns 204 |
| Bulk delete | `bulk_delete` | `abulk_delete` | Sets the flag on matching live rows |
| Restore | `restore` | `arestore` | Clears the flag, returns 200 with the read schema |
| Hard delete | `hard_delete` | `ahard_delete` | Deletes the row, returns 204 |

It also overrides `on_list_queryset` to hide soft-deleted rows and
`on_before_object_operation` / `aon_before_object_operation` to return 404 for
them on retrieve and update.

| Endpoint | Operation name |
| --- | --- |
| `POST /api/articles/{id}/restore` | `"restore"` |
| `DELETE /api/articles/{id}/hard-delete` | `"hard_delete"` |

## `FieldSelectionViewSetMixin`

Adds a `fields` query parameter to the list and retrieve endpoints. For how to
use it, see [Field selection](../../guides/field-selection.md).

```text
GET /api/articles?fields=id,title
GET /api/articles/1?fields=id,title
```

Only fields present in the response schema are kept. Unknown names are ignored.
When no valid name is left, the full response is returned. It adds no
attributes and overrides `list` / `alist` and the retrieve endpoint.

## See also

- [Filtering](../../guides/filtering.md)
- [Permissions](../../guides/permissions.md)
- [Soft delete](../../guides/soft-delete.md)
- [Field selection](../../guides/field-selection.md)
- [APIViewSet](api_view_set.md)
