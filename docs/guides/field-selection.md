---
type: guide
title: Field selection
description: Let clients ask for only the fields they need with the fields query parameter.
---

# Field selection

This page shows how to let clients pick the fields of the response with
`?fields=`.

## Add the mixin

Put `FieldSelectionViewSetMixin` before `APIViewSet`:

```python title="blog/api.py"
from ninja_aio import NinjaAIO, APIViewSet
from ninja_aio.views.mixins import FieldSelectionViewSetMixin

from .models import Article

api = NinjaAIO(title="Blog API")


@api.viewset(model=Article)
class ArticleViewSet(FieldSelectionViewSetMixin, APIViewSet):
    pass
```

The list and retrieve endpoints now accept a `fields` query parameter. The
other endpoints don't change. The mixin works the same in sync and async
viewsets.

## Request some fields

Send a comma-separated list of field names:

```text
GET /api/articles?fields=id,title
```

```json
{
  "items": [
    {"id": 1, "title": "Hello Django"},
    {"id": 2, "title": "Async views"}
  ],
  "count": 2
}
```

The list keeps its `items` and `count` keys. Each item only has the fields you
asked for.

The retrieve endpoint works the same way:

```text
GET /api/articles/1?fields=id,title
```

```json
{"id": 1, "title": "Hello Django"}
```

| Endpoint | Fields you can pick |
| --- | --- |
| `GET /api/articles` | The fields of the `read` schema |
| `GET /api/articles/{id}` | The fields of the `detail` schema, or `read` when there is no `detail` |

Selection works on the top-level fields. A relation, like `category`, comes
back as the whole nested object or id.

## Unknown fields

Names that are not in the schema are ignored:

| Request | Response |
| --- | --- |
| `?fields=id,title` | Only `id` and `title` |
| `?fields=title,password` | Only `title` |
| `?fields=password` | The full response |
| `?fields=` | The full response |
| No `fields` | The full response |

When none of the names is valid, you get the full response. Unknown names
never return an error.

## Combine with filters and pagination

`fields` works with filters, ordering and pagination. Put all the mixins
before `APIViewSet`:

```python
from ninja_aio.views.mixins import FieldSelectionViewSetMixin, IcontainsFilterViewSetMixin


@api.viewset(model=Article)
class ArticleViewSet(FieldSelectionViewSetMixin, IcontainsFilterViewSetMixin, APIViewSet):
    query_params = {"title": (str, None)}
    ordering_fields = ["views", "title"]
```

```text
GET /api/articles?title=django&ordering=-views&page=1&page_size=10&fields=id,title
```

Filters, ordering and pagination run first. Then each item is cut down to
`id` and `title`. `count` is the number of articles that match the filters.

If you write your own `query_params_handler`, `filters` also holds the
`fields` value. The filter mixins don't use it as a filter.

## See also

- [Filtering](filtering.md)
- [Pagination](pagination.md)
- [Schemas](schemas.md)
- [Mixins reference](../api/views/mixins.md)
