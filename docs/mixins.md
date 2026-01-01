# ViewSet Mixins

These mixins implement a query_params_handler to apply common filtering patterns to Django QuerySets. Import from `ninja_aio.views.mixins`. Values used for filtering come from validated query params in your viewset’s `query_params`.

Note: Each mixin overrides `query_params_handler`. When composing multiple mixins, define your own `query_params_handler` and call `super()` in the desired order.

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

## ReverseBooleanFilterViewSetMixin

Excludes records matching provided boolean values.

- Behavior: Uses `queryset.exclude(**{key: value})` for `bool` entries.

Example:

```python
from ninja_aio.views.mixins import ReverseBooleanFilterViewSetMixin

class FeatureViewSet(ReverseBooleanFilterViewSetMixin, APIViewSet):
    model = models.FeatureFlag
    api = api
    query_params = {"enabled": (bool, False)}
```

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

Base mixin for date/datetime filtering with aliasing and custom comparisons.

- Attributes:
  - `field_alias`: map incoming filter keys to actual model field names.
  - `_compare_attr`: comparison operator suffix (e.g., `__gt`, `__lt`, `__gte`, `__lte`).
- Behavior: Applies filters for values that implement `isoformat` (date/datetime-like).

Example:

```python
from ninja_aio.views.mixins import DateFilterViewSetMixin

class EventViewSet(DateFilterViewSetMixin, APIViewSet):
    model = models.Event
    api = api
    # Pydantic types recommended for dates (e.g., datetime/date) in query_params.
    query_params = {"createdAfter": (str, "")}
    field_alias = {"createdAfter": "created_at"}
    _compare_attr = "__gt"
```

## GreaterThenDateFilterViewSetMixin

Sets comparison to strict greater-than (`__gt`).

Example:

```python
from ninja_aio.views.mixins import GreaterThenDateFilterViewSetMixin

class EventViewSet(GreaterThenDateFilterViewSetMixin, APIViewSet):
    model = models.Event
    api = api
    query_params = {"created_at": (str, "")}
```

## LessThenDateFilterViewSetMixin

Sets comparison to strict less-than (`__lt`).

Example:

```python
from ninja_aio.views.mixins import LessThenDateFilterViewSetMixin

class EventViewSet(LessThenDateFilterViewSetMixin, APIViewSet):
    model = models.Event
    api = api
    query_params = {"created_at": (str, "")}
```

## GreaterEqualDateFilterViewSetMixin

Sets comparison to greater-than-or-equal (`__gte`).

Example:

```python
from ninja_aio.views.mixins import GreaterEqualDateFilterViewSetMixin

class EventViewSet(GreaterEqualDateFilterViewSetMixin, APIViewSet):
    model = models.Event
    api = api
    query_params = {"created_at": (str, "")}
```

## LessEqualDateFilterViewSetMixin

Sets comparison to less-than-or-equal (`__lte`).

Example:

```python
from ninja_aio.views.mixins import LessEqualDateFilterViewSetMixin

class EventViewSet(LessEqualDateFilterViewSetMixin, APIViewSet):
    model = models.Event
    api = api
    query_params = {"created_at": (str, "")}
```

## Tips

- Align `query_params` types with expected filter values; prefer Pydantic `date`/`datetime` for date filters.
- Validate field names and lookups to avoid runtime errors.
- For multiple mixins, implement your own `async def query_params_handler(...)` and chain with `await super().query_params_handler(...)` to combine behaviors.
