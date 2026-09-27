---
type: reference
title: Pagination
description: Lookup page for the pagination classes and query parameters of the list endpoint.
---

# Pagination

The pagination classes a viewset can use for its list endpoint. For how to use
them, see [Pagination](../guides/pagination.md).

```python
from ninja.pagination import LimitOffsetPagination, PageNumberPagination
```

## Viewset attribute

| Attribute | Type | Default | Description |
| --- | --- | --- | --- |
| `pagination_class` | `type[AsyncPaginationBase]` | `PageNumberPagination` | Pagination class of the list endpoint and of the many-to-many `GET` endpoints |

The viewset creates the class with no arguments, so the sizes come from the
class defaults or from the [settings](settings.md#django-ninja-settings).

## PageNumberPagination

The default. Clients send `page` and `page_size`.

| Query parameter | Type | Default | Description |
| --- | --- | --- | --- |
| `page` | `int` | `1` | Page number, starting from 1 |
| `page_size` | `int \| None` | `NINJA_PAGINATION_PER_PAGE` | Items per page. Capped to `NINJA_MAX_PER_PAGE_SIZE` |

| Constructor argument | Default | Description |
| --- | --- | --- |
| `page_size` | `NINJA_PAGINATION_PER_PAGE` | Page size when the client sends no `page_size` |
| `max_page_size` | `NINJA_MAX_PER_PAGE_SIZE` | Largest `page_size` a client can ask for |

## LimitOffsetPagination

Clients send `limit` and `offset`.

| Query parameter | Type | Default | Description |
| --- | --- | --- | --- |
| `limit` | `int` | `NINJA_PAGINATION_PER_PAGE` | Items to return. Above `NINJA_PAGINATION_MAX_LIMIT` fails validation |
| `offset` | `int` | `0` | Items to skip |

## Response

Every pagination class returns the same body:

```json
{"items": [{"id": 1, "title": "Hello"}], "count": 42}
```

| Key | Type | Description |
| --- | --- | --- |
| `items` | `list` | The objects of the page, with the `read` schema |
| `count` | `int` | Rows after filters, not the length of `items` |

## Custom pagination classes

The viewset reads only the page parameters from the class `Input`:

| Input has | Used as |
| --- | --- |
| `page` and `page_size` | Page number and page size, capped like `PageNumberPagination` |
| `limit` and `offset` | Slice of the queryset |
| neither | First 100 items |

The paginator's own queryset logic and its `Output` schema are not used.
Subclass `PageNumberPagination` or `LimitOffsetPagination` for custom
paginators.

## See also

- [Pagination](../guides/pagination.md)
- [Filtering](../guides/filtering.md)
- [Settings](settings.md)
- [APIViewSet](views/api_view_set.md)
