# :material-decagram: View Decorators

Django Ninja AIO provides decorator utilities for composing view behavior and attaching decorators to CRUD operations declaratively.

<div class="grid cards" markdown>

-   :material-layers:{ .lg .middle } **`decorate_view`**

    ---

    Compose multiple decorators on sync/async views

-   :material-cog:{ .lg .middle } **`extra_decorators`**

    ---

    Declarative per-operation decorators on ViewSets

-   :material-link-variant:{ .lg .middle } **M2M Decorators**

    ---

    Custom decorators for relation endpoints

-   :material-factory:{ .lg .middle } **`api_get` / `api_post`**

    ---

    Endpoint decorators with built-in decorator support

</div>

---

## :material-layers: `decorate_view`

Compose multiple decorators into a single view wrapper.

```python
from ninja_aio.decorators import decorate_view
```

**Behavior:**

- Order matches normal stacking: `@d1` over `@d2` ≡ `d1(d2(view))`
- Works with both sync and async views
- `None` values are ignored — useful for conditional decoration

=== "Basic usage"

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

=== "Conditional decoration"

    ```python
    cache_dec = cache_page(60) if settings.ENABLE_CACHE else None

    @self.router.get("data/")
    @decorate_view(cache_dec, authenticate)
    async def data(request):
        ...
    ```

!!! note
    `decorate_view` does not add an extra wrapper layer. Each decorator should preserve metadata itself (e.g., via `functools.wraps`).

---

## :material-cog: `APIViewSet.extra_decorators`

Attach decorators to auto-generated CRUD operations without redefining views:

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

### Available operations

| Field | Applies to |
|---|---|
| `list` | `GET /` — List all items |
| `retrieve` | `GET /{pk}` — Get single item |
| `create` | `POST /` — Create item |
| `update` | `PATCH /{pk}` — Update item |
| `delete` | `DELETE /{pk}` — Delete item |

!!! tip
    These decorators are applied in combination with built-in decorators (`unique_view`, `paginate`) using `decorate_view` internally.

---

## :material-link-variant: M2M Relation Decorators

Apply custom decorators to Many-to-Many relation endpoints via `get_decorators` and `post_decorators`:

```python
from ninja_aio.schemas import M2MRelationSchema

M2MRelationSchema(
    model=Tag,
    related_name="tags",
    get_decorators=[cache_decorator, log_decorator],   # GET (list related)
    post_decorators=[rate_limit_decorator],             # POST (add/remove)
)
```

| Parameter | Applies to |
|---|---|
| `get_decorators` | `GET /{pk}/tag` — List related items |
| `post_decorators` | `POST /{pk}/tag` — Add/remove relations |

See [APIViewSet M2M Relations](api_view_set.md#many-to-many-relations) for more details.

---

## :material-factory: `api_get` / `api_post` with Decorators

Endpoint decorators accept a `decorators` parameter for inline decorator composition:

```python
from ninja.pagination import PageNumberPagination
from ninja_aio.decorators.operations import api_get
from ninja_aio.decorators import unique_view
from ninja.pagination import paginate

@api.viewset(models.Book)
class BookAPI(APIViewSet):
    @api_get(
        "/custom-get",
        response={200: list[GenericMessageSchema]},
        decorators=[paginate(PageNumberPagination), unique_view("test-unique-view")],
    )
    async def get_test(self, request):
        return [{"message": "This is a custom GET method in BookAPI"}]
```

!!! info "How decorators are applied"
    - Provide decorators as a list — they are applied in reverse order internally
    - `paginate(PageNumberPagination)` enables async pagination on the handler
    - `unique_view(name)` marks the route as unique to avoid duplicate registration
    - Works with `@api.viewset(Model)` classes extending `APIViewSet`

---

## :material-arrow-right-circle: See Also

<div class="grid cards" markdown>

-   :material-view-grid:{ .lg .middle } **APIViewSet**

    ---

    Complete CRUD view generation with decorator support

    [:octicons-arrow-right-24: Learn more](api_view_set.md)

-   :material-eye:{ .lg .middle } **APIView**

    ---

    Base view class for custom endpoints

    [:octicons-arrow-right-24: Learn more](api_view.md)

-   :material-puzzle:{ .lg .middle } **Mixins**

    ---

    Reusable filtering and query behaviors

    [:octicons-arrow-right-24: Learn more](mixins.md)

-   :material-page-next:{ .lg .middle } **Pagination**

    ---

    Async pagination support for list endpoints

    [:octicons-arrow-right-24: Learn more](../pagination.md)

</div>
