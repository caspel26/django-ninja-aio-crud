---
type: guide
title: Filtering
description: Filter, search and sort the list endpoint with query parameters and filter mixins.
---

# Filtering

This page shows how to declare query parameters on a viewset, apply them with
the filter mixins, sort the list and write your own filters.

## Declare query parameters

List each parameter in `query_params` as `{"name": (type, default)}`:

```python title="blog/api.py"
import datetime

from ninja_aio import NinjaAIO, APIViewSet
from ninja_aio.views.mixins import IcontainsFilterViewSetMixin

from .models import Article

api = NinjaAIO(title="Blog API")


@api.viewset(model=Article)
class ArticleViewSet(IcontainsFilterViewSetMixin, APIViewSet):
    query_params = {
        "title": (str, None),
        "views": (int, None),
        "is_published": (bool, None),
        "created_at": (datetime.date, None),
    }
```

The type tells the client what to send:

| Type | Query string |
| --- | --- |
| `str` | `?title=django` |
| `int`, `float` | `?views=100` |
| `bool` | `?is_published=true` or `?is_published=false` |
| `datetime.date` | `?created_at=2026-01-01` |
| `datetime.datetime` | `?created_at=2026-01-01T09:00:00` |

A value that doesn't match the type returns a validation error. Use `None` as
the default so a filter only applies when the client sends it.

The parameters only declare the query string. A mixin, or your own handler,
applies them to the queryset. Filters apply to the list endpoint only.

## Filter text

`IcontainsFilterViewSetMixin` matches `str` parameters that contain the value,
ignoring case:

```python
@api.viewset(model=Article)
class ArticleViewSet(IcontainsFilterViewSetMixin, APIViewSet):
    query_params = {"title": (str, None), "body": (str, None)}
```

`GET /api/articles?title=django` returns articles with "django" or "Django" in
the title.

## Filter booleans and numbers

`BooleanFilterViewSetMixin` matches `bool` parameters exactly.
`NumericFilterViewSetMixin` matches `int` and `float` parameters exactly.

```python
from ninja_aio.views.mixins import BooleanFilterViewSetMixin, NumericFilterViewSetMixin


@api.viewset(model=Article)
class ArticleViewSet(BooleanFilterViewSetMixin, NumericFilterViewSetMixin, APIViewSet):
    query_params = {"is_published": (bool, None), "views": (int, None)}
```

`GET /api/articles?is_published=true&views=0` returns published articles with
no views.

## Filter dates

Each date mixin compares the date and datetime parameters in its own way:

| Mixin | Matches | Example |
| --- | --- | --- |
| `DateFilterViewSetMixin` | The exact value | `?created_at=2026-01-01T09:00:00` |
| `GreaterDateFilterViewSetMixin` | After the value | `?created_at=2026-01-01` |
| `LessDateFilterViewSetMixin` | Before the value | `?created_at=2026-01-01` |
| `GreaterEqualDateFilterViewSetMixin` | From the value on | `?created_at=2026-01-01` |
| `LessEqualDateFilterViewSetMixin` | Up to the value | `?created_at=2026-12-31` |

```python
from ninja_aio.views.mixins import GreaterEqualDateFilterViewSetMixin


@api.viewset(model=Article)
class ArticleViewSet(GreaterEqualDateFilterViewSetMixin, APIViewSet):
    query_params = {"created_at": (datetime.date, None)}
```

`GET /api/articles?created_at=2026-01-01` returns articles created on or after
January 1st.

!!! note

    A date mixin applies to every date and datetime parameter of the viewset.
    Use one date mixin per viewset. For a range, like "from" and "to", write
    your own handler as shown in [Write your own filters](#write-your-own-filters).

## Filter by a related model

`RelationFilterViewSetMixin` maps a query parameter to a lookup on a related
model. Declare the filters in `relations_filters`, not in `query_params`:

```python
from ninja_aio.schemas import RelationFilterSchema
from ninja_aio.views.mixins import RelationFilterViewSetMixin


@api.viewset(model=Article)
class ArticleViewSet(RelationFilterViewSetMixin, APIViewSet):
    relations_filters = [
        RelationFilterSchema(
            query_param="category",
            query_filter="category__id",
            filter_type=(int, None),
        ),
        RelationFilterSchema(
            query_param="category_name",
            query_filter="category__name__icontains",
            filter_type=(str, None),
        ),
    ]
```

| Field | What it does |
| --- | --- |
| `query_param` | The name in the query string |
| `query_filter` | The Django lookup to apply, like `category__id` |
| `filter_type` | The `(type, default)` pair of the parameter |

`GET /api/articles?category=1` returns the articles in category 1.
`?category_name=djan` returns the articles whose category name contains "djan".

## Apply different filters for true and false

`MatchCaseFilterViewSetMixin` adds a boolean parameter and runs one filter for
`true` and another for `false`:

```python
from django.db.models import Q

from ninja_aio.schemas import (
    BooleanMatchFilterSchema,
    MatchCaseFilterSchema,
    MatchConditionFilterSchema,
)
from ninja_aio.views.mixins import MatchCaseFilterViewSetMixin


@api.viewset(model=Article)
class ArticleViewSet(MatchCaseFilterViewSetMixin, APIViewSet):
    filters_match_cases = [
        MatchCaseFilterSchema(
            query_param="popular",
            cases=BooleanMatchFilterSchema(
                true=MatchConditionFilterSchema(
                    query_filter={"views__gte": 1000},
                    include=True,
                ),
                false=MatchConditionFilterSchema(
                    query_filter={"views__gte": 1000},
                    include=False,
                ),
            ),
        ),
        MatchCaseFilterSchema(
            query_param="featured",
            cases=BooleanMatchFilterSchema(
                true=MatchConditionFilterSchema(
                    query_filter=Q(is_published=True) & Q(views__gte=100),
                ),
                false=MatchConditionFilterSchema(
                    query_filter=Q(is_published=True) & Q(views__gte=100),
                    include=False,
                ),
            ),
        ),
    ]
```

`?popular=true` returns articles with at least 1000 views, `?popular=false`
the others. `query_filter` is a dict of lookups or a `Q` object. `include=True`
(the default) keeps the matching rows, `include=False` excludes them.

## Search across fields

`SearchViewSetMixin` adds a `search` parameter that looks for the value in
several fields, ignoring case. A row matches when any field contains it:

```python
from ninja_aio.views.mixins import SearchViewSetMixin


@api.viewset(model=Article)
class ArticleViewSet(SearchViewSetMixin, APIViewSet):
    search_fields = ["title", "body", "category__name"]
    search_param = "q"
```

`GET /api/articles?q=async` searches the title, the body and the category
name. `search_param` defaults to `search`.

## Combine mixins

Put all the mixins before `APIViewSet`. Each mixin only handles the parameters
of its own type, so they work together:

```python
@api.viewset(model=Article)
class ArticleViewSet(
    IcontainsFilterViewSetMixin,
    BooleanFilterViewSetMixin,
    RelationFilterViewSetMixin,
    SearchViewSetMixin,
    APIViewSet,
):
    query_params = {"title": (str, None), "is_published": (bool, None)}
    relations_filters = [
        RelationFilterSchema(
            query_param="category",
            query_filter="category__id",
            filter_type=(int, None),
        ),
    ]
    search_fields = ["title", "body"]
```

`GET /api/articles?title=django&is_published=true&category=1&search=orm`
applies all four filters. The mixins work the same in sync and async viewsets.

## Sort the list

List the fields clients can sort by in `ordering_fields`:

```python
@api.viewset(model=Article)
class ArticleViewSet(APIViewSet):
    ordering_fields = ["created_at", "title", "views"]
    default_ordering = "-created_at"
```

Clients send a comma-separated list. A leading `-` sorts in descending order:

```text
GET /api/articles?ordering=-views,title
```

Fields not in `ordering_fields` are ignored. When the client sends no valid
field, the list uses `default_ordering`, a field name or a list of names.
`default_ordering` needs `ordering_fields` to be set.

## Write your own filters

Override the query parameters handler for filters the mixins don't cover.
`filters` is a dict with every declared parameter, `None` when the client
didn't send it. Call `super()` to keep the mixins working:

=== "Sync"

    ```python
    @api.viewset(model=Article)
    class ArticleViewSet(IcontainsFilterViewSetMixin, APIViewSet):
        execution_mode = "sync"
        query_params = {
            "title": (str, None),
            "published_after": (datetime.date, None),
            "published_before": (datetime.date, None),
        }

        def query_params_handler(self, queryset, filters):
            queryset = super().query_params_handler(queryset, filters)
            if filters["published_after"]:
                queryset = queryset.filter(created_at__date__gte=filters["published_after"])
            if filters["published_before"]:
                queryset = queryset.filter(created_at__date__lte=filters["published_before"])
            return queryset
    ```

=== "Async"

    ```python
    @api.viewset(model=Article)
    class ArticleViewSet(IcontainsFilterViewSetMixin, APIViewSet):
        query_params = {
            "title": (str, None),
            "published_after": (datetime.date, None),
            "published_before": (datetime.date, None),
        }

        async def aquery_params_handler(self, queryset, filters):
            queryset = await super().aquery_params_handler(queryset, filters)
            if filters["published_after"]:
                queryset = queryset.filter(created_at__date__gte=filters["published_after"])
            if filters["published_before"]:
                queryset = queryset.filter(created_at__date__lte=filters["published_before"])
            return queryset
    ```

Return the filtered queryset. Override the handler that matches your mode: an
async viewset that overrides only `query_params_handler` raises
`ImproperlyConfigured` at startup.

## Unknown fields are ignored

The mixins check every parameter name and lookup against the model. A
parameter that isn't a model field, like `published_after` above, is skipped
by the mixins, so only your handler uses it. The same applies to a
`query_filter` or a match-case lookup that points to a field that doesn't
exist.

## See also

- [Filter, search and sort](../tutorial/filtering.md)
- [Pagination](pagination.md)
- [Viewsets](viewsets.md)
- [Mixins reference](../api/views/mixins.md)
