# :material-puzzle: ViewSet Mixins

These mixins implement a `query_params_handler` to apply common filtering patterns to Django QuerySets. Import from `ninja_aio.views.mixins`. Values used for filtering come from validated query params in your viewset's `query_params`.

!!! note
    Each mixin overrides `query_params_handler`. When composing multiple mixins, define your own `query_params_handler` and call `super()` in the desired order.

## IcontainsFilterViewSetMixin

Applies case-insensitive substring filters (`__icontains`) for string values.

- Behavior: For each `str` value in `filters`, applies `field__icontains=value`.
- Ignores non-string values.

Example:

```python
from ninja_aio.views.mixins import IcontainsFilterViewSetMixin
from ninja_aio.views.api import APIViewSet

class UserViewSet(IcontainsFilterViewSetMixin, APIViewSet):
    model = models.User
    api = api
    query_params = {"name": (str, ""), "email": (str, "")}
```

## BooleanFilterViewSetMixin

Filters boolean fields using exact match.

- Behavior: Applies `{key: value}` only for `bool` values.

Example:

```python
from ninja_aio.views.mixins import BooleanFilterViewSetMixin

class FeatureViewSet(BooleanFilterViewSetMixin, APIViewSet):
    model = models.FeatureFlag
    api = api
    query_params = {"enabled": (bool, False)}
```

<!-- Removed ReverseBooleanFilterViewSetMixin: not implemented in code -->

## NumericFilterViewSetMixin

Applies exact filters for numeric values.

- Behavior: Filters only `int` and `float` values.

Example:

```python
from ninja_aio.views.mixins import NumericFilterViewSetMixin

class OrderViewSet(NumericFilterViewSetMixin, APIViewSet):
    model = models.Order
    api = api
    query_params = {"amount": (float, 0.0), "quantity": (int, 0)}
```

## DateFilterViewSetMixin

Base mixin for date/datetime filtering with custom comparisons.

- Attributes:
  - `_compare_attr`: comparison operator suffix (e.g., `__gt`, `__lt`, `__gte`, `__lte`).
- Behavior: Applies filters for values that implement `isoformat` (date/datetime-like). Prefer using Pydantic `date`/`datetime` types in `query_params`.

Example:

```python
from ninja_aio.views.mixins import DateFilterViewSetMixin

class EventViewSet(DateFilterViewSetMixin, APIViewSet):
    model = models.Event
    api = api
    # Use date/datetime types so values have `isoformat`.
    query_params = {"created_at": (datetime, None)}
    _compare_attr = "__gt"
```

## GreaterDateFilterViewSetMixin

Sets comparison to strict greater-than (`__gt`).

Example:

```python
from ninja_aio.views.mixins import GreaterDateFilterViewSetMixin

class EventViewSet(GreaterDateFilterViewSetMixin, APIViewSet):
    model = models.Event
    api = api
    query_params = {"created_at": (datetime, None)}
```

## LessDateFilterViewSetMixin

Sets comparison to strict less-than (`__lt`).

Example:

```python
from ninja_aio.views.mixins import LessDateFilterViewSetMixin

class EventViewSet(LessDateFilterViewSetMixin, APIViewSet):
    model = models.Event
    api = api
    query_params = {"created_at": (datetime, None)}
```

## GreaterEqualDateFilterViewSetMixin

Sets comparison to greater-than-or-equal (`__gte`).

Example:

```python
from ninja_aio.views.mixins import GreaterEqualDateFilterViewSetMixin

class EventViewSet(GreaterEqualDateFilterViewSetMixin, APIViewSet):
    model = models.Event
    api = api
    query_params = {"created_at": (datetime, None)}
```

## LessEqualDateFilterViewSetMixin

Sets comparison to less-than-or-equal (`__lte`).

Example:

```python
from ninja_aio.views.mixins import LessEqualDateFilterViewSetMixin

class EventViewSet(LessEqualDateFilterViewSetMixin, APIViewSet):
    model = models.Event
    api = api
    query_params = {"created_at": (datetime, None)}
```

## RelationFilterViewSetMixin

Filters by related model fields using configurable `RelationFilterSchema` entries.

- Behavior: Maps query parameters to Django ORM lookups on related models.
- Configuration: Define `relations_filters` as a list of `RelationFilterSchema` objects.
- Query params are automatically registered from `relations_filters`.

Each `RelationFilterSchema` requires:

- `query_param`: The API query parameter name exposed to clients.
- `query_filter`: The Django ORM lookup path (e.g., `author__id`, `category__name__icontains`).
- `filter_type`: Tuple of `(type, default)` for schema generation (e.g., `(int, None)`).

Example:

```python
from ninja_aio.views.mixins import RelationFilterViewSetMixin
from ninja_aio.views.api import APIViewSet
from ninja_aio.schemas import RelationFilterSchema

class BookViewSet(RelationFilterViewSetMixin, APIViewSet):
    model = models.Book
    api = api
    relations_filters = [
        RelationFilterSchema(
            query_param="author",
            query_filter="author__id",
            filter_type=(int, None),
        ),
        RelationFilterSchema(
            query_param="category_name",
            query_filter="category__name__icontains",
            filter_type=(str, None),
        ),
    ]
```

This enables:

- `GET /books?author=5` → `queryset.filter(author__id=5)`
- `GET /books?category_name=fiction` → `queryset.filter(category__name__icontains="fiction")`

## MatchCaseFilterViewSetMixin

Applies conditional filtering based on boolean query parameters, where different filter conditions are applied for `True` and `False` values. This is useful when you need to map a simple boolean API parameter to complex underlying filter logic.

- Behavior: For each `MatchCaseFilterSchema` entry, applies different Django ORM filters based on the boolean value of the query parameter.
- Configuration: Define `filters_match_cases` as a list of `MatchCaseFilterSchema` objects.
- Query params are automatically registered from `filters_match_cases`.
- Supports both `filter()` (include) and `exclude()` operations via the `include` attribute.

Each `MatchCaseFilterSchema` requires:

- `query_param`: The API query parameter name exposed to clients.
- `cases`: A `BooleanMatchFilterSchema` defining the filter conditions for `True` and `False` cases.

Each `MatchConditionFilterSchema` (used within `BooleanMatchFilterSchema`) requires:

- `query_filter`: A dictionary of Django ORM lookups to apply (e.g., `{"status": "active"}`).
- `include`: Boolean indicating whether to use `filter()` (True) or `exclude()` (False). Defaults to `True`.

Example - Simple status filtering:

```python
from ninja_aio.views.mixins import MatchCaseFilterViewSetMixin
from ninja_aio.views.api import APIViewSet
from ninja_aio.schemas import (
    MatchCaseFilterSchema,
    MatchConditionFilterSchema,
    BooleanMatchFilterSchema,
)

class OrderViewSet(MatchCaseFilterViewSetMixin, APIViewSet):
    model = models.Order
    api = api
    filters_match_cases = [
        MatchCaseFilterSchema(
            query_param="is_completed",
            cases=BooleanMatchFilterSchema(
                true=MatchConditionFilterSchema(
                    query_filter={"status": "completed"},
                    include=True,
                ),
                false=MatchConditionFilterSchema(
                    query_filter={"status": "completed"},
                    include=False,  # excludes completed orders
                ),
            ),
        ),
    ]
```

This enables:

- `GET /orders?is_completed=true` → `queryset.filter(status="completed")`
- `GET /orders?is_completed=false` → `queryset.exclude(status="completed")`

Example - Complex filtering with multiple conditions:

```python
class TaskViewSet(MatchCaseFilterViewSetMixin, APIViewSet):
    model = models.Task
    api = api
    filters_match_cases = [
        MatchCaseFilterSchema(
            query_param="show_active",
            cases=BooleanMatchFilterSchema(
                true=MatchConditionFilterSchema(
                    query_filter={"status__in": ["pending", "in_progress"]},
                    include=True,
                ),
                false=MatchConditionFilterSchema(
                    query_filter={"status__in": ["completed", "cancelled"]},
                    include=True,
                ),
            ),
        ),
    ]
```

This enables:

- `GET /tasks?show_active=true` → `queryset.filter(status__in=["pending", "in_progress"])`
- `GET /tasks?show_active=false` → `queryset.filter(status__in=["completed", "cancelled"])`

## Tips

- Align `query_params` types with expected filter values; prefer Pydantic `date`/`datetime` for date filters so values implement `isoformat`.
- Validate field names and lookups to avoid runtime errors.
- For multiple mixins, implement your own `async def query_params_handler(...)` and chain with `await super().query_params_handler(...)` to combine behaviors.

---

## :material-arrow-right-circle: See Also

<div class="grid cards" markdown>

-   :material-view-grid:{ .lg .middle } **APIViewSet**

    ---

    Complete CRUD operations with mixin support

    [:octicons-arrow-right-24: Learn more](api_view_set.md)

-   :material-filter:{ .lg .middle } **Filtering Tutorial**

    ---

    Step-by-step guide to filtering & pagination

    [:octicons-arrow-right-24: Learn more](../../tutorial/filtering.md)

-   :material-tag:{ .lg .middle } **Decorators**

    ---

    Route decorators for pagination and unique views

    [:octicons-arrow-right-24: Learn more](decorators.md)

-   :material-eye:{ .lg .middle } **APIView**

    ---

    Base view class for custom endpoints

    [:octicons-arrow-right-24: Learn more](api_view.md)

</div>
