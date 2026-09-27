---
type: reference
title: Types
description: Lookup page for the helper types you pass to or get back from the framework.
---

# Types

Helper types you meet when you configure viewsets and serializers or read the
result of a bulk operation.

```python
from ninja_aio import HttpMethod
from ninja_aio.types import BulkFailure, BulkResult, QueryPurpose
from ninja_aio.schemas import GenericMessageSchema, M2MRelationSchema
from ninja_aio.schemas.helpers import (
    DecoratorsSchema,
    ModelQuerySetExtraSchema,
    ModelQuerySetSchema,
)
```

## BulkResult

Returned by `bulk_create`, `bulk_update`, `bulk_destroy` and their async
versions. See [Bulk operations](../guides/bulk-operations.md).

| Member | Type | Description |
| --- | --- | --- |
| `succeeded` | `list` | Created or updated instances. Primary keys for `bulk_destroy` |
| `failed` | `list[BulkFailure]` | One entry per failed item |
| `has_errors` | `bool` | Property. `True` when `failed` is not empty |
| `success_count` | `int` | Property. `len(succeeded)` |
| `failure_count` | `int` | Property. `len(failed)` |

## BulkFailure

A frozen dataclass describing one failed item.

| Field | Type | Default | Description |
| --- | --- | --- | --- |
| `index` | `int` | required | Position of the item in the input list |
| `code` | `str` | required | Error code, like `"validation_error"`, `"not_found"`, `"invalid_value"`, `"invalid_type"` or `"operation_error"` |
| `message` | `str` | required | Readable message |
| `fields` | `dict[str, list[str]]` | `{}` | Errors by field |
| `pk` | `int \| str \| UUID \| None` | `None` | Primary key of the item, for update and destroy |
| `error` | `dict` | `{}` | The error body as the HTTP bulk response shows it |

## HttpMethod

A `str` enum for the `methods` of `@action` and `@on`. Members compare equal
to their value, so you can also pass the lowercase string. See
[Viewsets](../guides/viewsets.md).

| Member | Value |
| --- | --- |
| `HttpMethod.GET` | `"get"` |
| `HttpMethod.POST` | `"post"` |
| `HttpMethod.PUT` | `"put"` |
| `HttpMethod.PATCH` | `"patch"` |
| `HttpMethod.DELETE` | `"delete"` |
| `HttpMethod.HEAD` | `"head"` |
| `HttpMethod.OPTIONS` | `"options"` |

## QueryPurpose

`Literal["read", "detail"]`. The value of `optimize_for` in `get`, `aget`,
`get_queryset` and `aget_queryset`: it applies the relation loading of the
`read` or `detail` schema. See [Query optimization](../guides/query-optimization.md).

## ModelQuerySetSchema

Used in the serializer `QuerySet` class for `read`, `detail` and
`queryset_request`. See [Query optimization](../guides/query-optimization.md).

| Field | Type | Default | Description |
| --- | --- | --- | --- |
| `select_related` | `list[str]` | `[]` | Relations passed to `select_related` |
| `prefetch_related` | `list[str]` | `[]` | Relations passed to `prefetch_related` |

## ModelQuerySetExtraSchema

A named scope for `QuerySet.extras`. It has the fields of
`ModelQuerySetSchema` plus:

| Field | Type | Default | Description |
| --- | --- | --- | --- |
| `scope` | `str` | required | Name of the scope |

## M2MRelationSchema

One entry of `APIViewSet.m2m_relations`. See [Relations](../guides/relations.md).

| Field | Type | Default | Description |
| --- | --- | --- | --- |
| `model` | `ModelSerializer` or model class | required | The related model |
| `related_name` | `str` | required | The many-to-many field on the viewset model |
| `add` | `bool` | `True` | Accept `add` in the `POST` body |
| `remove` | `bool` | `True` | Accept `remove` in the `POST` body |
| `get` | `bool` | `True` | Add the `GET` endpoint |
| `path` | `str \| None` | `""` | URL segment. Empty uses the plural verbose name |
| `auth` | any | `NOT_SET` | `NOT_SET` inherits the viewset `m2m_auth`, then the viewset auth. `None` makes the relation public |
| `filters` | `dict[str, tuple] \| None` | `None` | Query parameters for `GET`, as `{"name": (type, default)}` |
| `related_schema` | `Schema \| None` | `None` | Schema of each listed object. Generated from `model` or `serializer_class` when omitted |
| `serializer_class` | `Serializer \| None` | `None` | `Serializer` for a plain Django model. Not allowed with a `ModelSerializer` |
| `append_slash` | `bool` | `False` | Add a trailing slash to the `GET` path |
| `verbose_name_plural` | `str \| None` | `None` | Name used in summaries. `None` uses the model's |
| `get_decorators` | `list` | `[]` | Decorators for the `GET` endpoint |
| `post_decorators` | `list` | `[]` | Decorators for the `POST` endpoint |

A plain Django model needs `related_schema` or `serializer_class`.

## DecoratorsSchema

The type of `APIViewSet.extra_decorators`. Each field is a list of decorators
for one generated endpoint. See [Viewsets](../guides/viewsets.md).

| Field | Default |
| --- | --- |
| `list` | `[]` |
| `retrieve` | `[]` |
| `create` | `[]` |
| `update` | `[]` |
| `delete` | `[]` |
| `bulk_create` | `[]` |
| `bulk_update` | `[]` |
| `bulk_delete` | `[]` |

## GenericMessageSchema

A root model of `dict[str, str]`, like `{"error": "forbidden"}`. It is the
default `error_schema` of `APIView` and `APIViewSet`, used to document the
error responses. See [Errors](../guides/errors.md).

## See also

- [Bulk operations](../guides/bulk-operations.md)
- [Relations](../guides/relations.md)
- [Query optimization](../guides/query-optimization.md)
- [Viewsets](../guides/viewsets.md)
