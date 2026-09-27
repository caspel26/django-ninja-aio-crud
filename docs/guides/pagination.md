---
type: guide
title: Pagination
description: Control how the list endpoint splits results into pages.
---

# Pagination

The list endpoint returns results in pages. This page shows how clients ask
for a page, how to change the page size and how to switch to limit and offset.

## Ask for a page

By default a viewset uses Django Ninja's `PageNumberPagination`. Clients send
`page` and `page_size`:

```text
GET /api/articles?page=2&page_size=20
```

The response holds the items of the page and the total number of rows:

```json
{
  "items": [
    {"id": 21, "title": "Async views"}
  ],
  "count": 42
}
```

| Parameter | Default | What it does |
| --- | --- | --- |
| `page` | `1` | The page number, starting from 1 |
| `page_size` | `100` | The number of items per page |

`count` is the number of rows after filters, not the number of items in the
page. A page past the end returns an empty `items` list.

## Change the page size

Set the defaults in your settings:

```python title="project/settings.py"
NINJA_PAGINATION_PER_PAGE = 20
NINJA_MAX_PER_PAGE_SIZE = 50
```

| Setting | Default | What it does |
| --- | --- | --- |
| `NINJA_PAGINATION_PER_PAGE` | `100` | Page size when the client sends no `page_size` |
| `NINJA_MAX_PER_PAGE_SIZE` | `100` | The largest `page_size` a client can ask for. Bigger values are capped |

These settings apply to every viewset.

## Use a different page size for one viewset

Subclass `PageNumberPagination` and pass the sizes to its constructor:

```python title="blog/api.py"
from ninja.pagination import PageNumberPagination


class SmallPages(PageNumberPagination):
    def __init__(self, **kwargs):
        super().__init__(page_size=10, max_page_size=25, **kwargs)


@api.viewset(model=Category, prefix="categories")
class CategoryViewSet(APIViewSet):
    pagination_class = SmallPages
```

`GET /api/categories` returns 10 items per page, and `?page_size=100` is capped
to 25.

## Use limit and offset

Set `pagination_class` to Django Ninja's `LimitOffsetPagination`:

```python title="blog/api.py"
from ninja.pagination import LimitOffsetPagination


@api.viewset(model=Article)
class ArticleViewSet(APIViewSet):
    pagination_class = LimitOffsetPagination
```

Clients send `limit` and `offset` instead of `page` and `page_size`:

```text
GET /api/articles?limit=20&offset=40
```

| Parameter | Default | What it does |
| --- | --- | --- |
| `limit` | `NINJA_PAGINATION_PER_PAGE` | The number of items to return |
| `offset` | `0` | The number of items to skip |

The response has the same `items` and `count` keys. To cap `limit`, set
`NINJA_PAGINATION_MAX_LIMIT` in your settings. Requests above it fail
validation.

!!! note

    The list endpoint reads only the page parameters of the pagination class,
    `page` and `page_size` or `limit` and `offset`. Custom paginators should
    subclass `PageNumberPagination` or `LimitOffsetPagination`.

## Sort before paging

Filters and ordering run before the list is split in pages, so every page
follows the same order:

```python
@api.viewset(model=Article)
class ArticleViewSet(APIViewSet):
    ordering_fields = ["created_at", "views"]
    default_ordering = "-created_at"
```

```text
GET /api/articles?ordering=-views&page=2&page_size=10
```

This returns the articles ranked 11 to 20 by views. Set `default_ordering` so
pages stay stable when clients send no `ordering`. See
[Filtering](filtering.md#sort-the-list).

## See also

- [Filtering](filtering.md)
- [Viewsets](viewsets.md)
- [Filter, search and sort](../tutorial/filtering.md)
- [Pagination reference](../api/pagination.md)
