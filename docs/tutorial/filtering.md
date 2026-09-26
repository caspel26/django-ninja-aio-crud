---
type: tutorial
step: 6
steps: 7
title: Filter, search and sort
description: Add query parameters to filter, search, sort and paginate the article list.
---

# Filter, search and sort

In this step you let clients narrow down the article list:

```text
GET /api/articles/?title=django&category=1&search=async&ordering=-views&page=2
```

## Add the filters

Declare the query parameters in `query_params` and add the mixins that apply
them. Each parameter is a `(type, default)` pair.

```python title="blog/api.py"
from ninja_aio.schemas import RelationFilterSchema
from ninja_aio.views.mixins import (
    IcontainsFilterViewSetMixin,
    PermissionViewSetMixin,
    RelationFilterViewSetMixin,
    SearchViewSetMixin,
)


@api.viewset(model=Article)
class ArticleViewSet(
    IcontainsFilterViewSetMixin,
    RelationFilterViewSetMixin,
    SearchViewSetMixin,
    PermissionViewSetMixin,
    APIViewSet,
):
    # auth and permission methods as before

    query_params = {"title": (str, None)}
    relations_filters = [
        RelationFilterSchema(
            query_param="category",
            query_filter="category__id",
            filter_type=(int, None),
        ),
    ]
    search_fields = ["title", "body", "category__name"]
    ordering_fields = ["created_at", "title", "views"]
    default_ordering = "-created_at"
```

Put the mixins before `APIViewSet`. They work the same in sync and async
viewsets.

| Parameter | Example | Result |
| --- | --- | --- |
| `title` | `?title=django` | Titles that contain "django", ignoring case |
| `category` | `?category=1` | Articles in category 1 |
| `search` | `?search=async` | "async" in the title, body or category name |
| `ordering` | `?ordering=-views,title` | Most viewed first, then by title |

Parameters you don't send are ignored. `ordering` only accepts fields listed in
`ordering_fields`. Without it, the list uses `default_ordering`.

## Other filter mixins

| Mixin | Filters | Example |
| --- | --- | --- |
| `IcontainsFilterViewSetMixin` | Text that contains the value | `?title=django` |
| `BooleanFilterViewSetMixin` | Exact `True`/`False` | `?is_published=true` |
| `NumericFilterViewSetMixin` | Exact numbers | `?views=100` |
| `GreaterEqualDateFilterViewSetMixin` | Dates from this value on | `?created_at=2026-01-01` |
| `LessEqualDateFilterViewSetMixin` | Dates up to this value | `?created_at=2026-12-31` |
| `RelationFilterViewSetMixin` | A field on a related model | `?category=1` |
| `MatchCaseFilterViewSetMixin` | Different filters for `true` and `false` | `?popular=true` |

Each mixin handles the parameters of its type, so you can combine them.

## Paginate

The list is split in pages of 100 items. Clients choose the page and its size:

```text
GET /api/articles/?page=2&page_size=20
```

Change the default size in your settings:

```python title="project/settings.py"
NINJA_PAGINATION_PER_PAGE = 20
```

[Next: go to production](production.md){ .md-button .md-button--primary }
