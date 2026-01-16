# View decorators

This package provides:

- decorate_view: compose multiple decorators (sync/async views), preserving Python stacking order, and skipping None values.
- APIViewSet.extra_decorators: declarative per-operation decorators.

## decorate_view

Behavior:

- Order matches normal stacking: `@d1` over `@d2` ≡ `d1(d2(view))`.
- Works with sync/async views.
- Ignores None values, useful for conditional decoration.

Example:

```python
from ninja_aio.decorators import decorate_view
from ninja_aio.views import APIViewSet

class MyViewSet(APIViewSet):
    api = api
    model = MyModel

    def views(self):
        @self.router.get("health/")
        @decorate_view(authenticate, log_request)
        async def health(request):
            return {"ok": True}
```

Conditional decoration:

```python
cache_dec = cache_page(60) if settings.ENABLE_CACHE else None

@self.router.get("data/")
@decorate_view(cache_dec, authenticate)
async def data(request):
    ...
```

Note: decorate_view does not add an extra wrapper; each decorator should preserve metadata itself (e.g., functools.wraps).

## APIViewSet.extra_decorators

Attach decorators to CRUD operations without redefining views:

```python
from ninja_aio.schemas.helpers import DecoratorsSchema

@api.viewset(MyModel)
class MyViewSet(APIViewSet):
    extra_decorators = DecoratorsSchema(
        list=[require_auth, cache_page(30)],
        retrieve=[require_auth],
        create=[require_auth],
        update=[require_auth],
        delete=[require_auth],
    )
```

These are applied in combination with built-ins (e.g., unique_view, paginate) using decorate_view in the implementation.

## ApiMethodFactory.decorators

Example: use api_get within a ViewSet with extra decorators:

```python
from ninja.pagination import PageNumberPagination
from ninja_aio.decorators.operations import api_get
from ninja_aio.views import APIViewSet
from ninja_aio.models import ModelSerializer
from ninja_aio.decorators import unique_view
from ninja.pagination import paginate

from . import models

api = NinjaAIO()

@api.viewset(models.Book)
class BookAPI(APIViewSet):
    query_params = {
        "title": (str, None),
    }

    @api_get(
        "/custom-get",
        response={200: list[GenericMessageSchema]},
        decorators=[paginate(PageNumberPagination), unique_view("test-unique-view")],
    )
    async def get_test(self, request):
        return [{"message": "This is a custom GET method in BookAPI"}]
```

Notes:

- Provide decorators as a list; they are applied in reverse order internally.
- paginate(PageNumberPagination) enables async pagination on the handler.
- unique_view(name) marks the route as unique to avoid duplicate registration.
- Works with @api.viewset(Model) classes extending APIViewSet.
