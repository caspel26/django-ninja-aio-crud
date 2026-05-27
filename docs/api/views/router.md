# :material-router: NinjaAIORouter

`NinjaAIORouter` is a composable router that mirrors the `NinjaAIO` API surface. It lets you group related views and viewsets into a self-contained unit that can then be attached to the main API with a single call.

<div class="grid cards" markdown>

-   :material-group:{ .lg .middle } **Logical Grouping**

    ---

    Bundle views and viewsets for a domain (e.g. `/v1`, `/admin`) into one object

-   :material-transit-connection-variant:{ .lg .middle } **Nested Routers**

    ---

    Each view/viewset gets its own sub-router, fully nested under the parent prefix

-   :material-power-plug:{ .lg .middle } **Two Attachment Styles**

    ---

    Use `api.add_router()` or the `@api.router()` decorator — both are supported

</div>

---

## :material-code-braces: Class Definition

`NinjaAIORouter` extends Django Ninja's `Router`, so every method available on a plain `Router` (`.get()`, `.post()`, `add_router()`, etc.) is available here too.

```python
from ninja_aio import NinjaAIORouter
```

| Method | Description |
|---|---|
| `.view(prefix, tags)` | Register an `APIView` subclass as a nested sub-router |
| `.viewset(model, prefix, tags)` | Register an `APIViewSet` subclass as a nested sub-router |

---

## :material-function-variant: Registering Views and ViewSets

The `.view()` and `.viewset()` decorators work identically to the ones on `NinjaAIO`:

```python
from ninja_aio import NinjaAIO, NinjaAIORouter
from ninja_aio.views import APIView, APIViewSet
from ninja_aio.decorators import api_get
from ninja import Schema

api = NinjaAIO(title="My API")

class StatusSchema(Schema):
    ok: bool

router = NinjaAIORouter()

@router.view(prefix="/health", tags=["Health"])
class HealthView(APIView):
    @api_get("/check", response=StatusSchema)
    async def check(self, request):
        return {"ok": True}

@router.viewset(model=Article, prefix="/articles", tags=["Articles"])
class ArticleViewSet(APIViewSet):
    schema_in = ArticleSchemaIn
    schema_out = ArticleSchemaOut
    schema_update = ArticleSchemaPatch
```

---

## :material-transit-connection: Attaching to NinjaAIO

### Option 1 — `api.add_router()` (standard Django Ninja call)

```python
api.add_router("/v1", router)
```

Compatible with any `NinjaAPI` instance, not just `NinjaAIO`.

### Option 2 — `@api.router()` decorator

```python
@api.router("/v1")
class V1Router(NinjaAIORouter):
    pass

@V1Router.view(prefix="/health", tags=["Health"])
class HealthView(APIView):
    ...

@V1Router.viewset(model=Article, prefix="/articles", tags=["Articles"])
class ArticleViewSet(APIViewSet):
    ...
```

The decorator instantiates the router class and mounts it on the API in one step. Additional keyword arguments are forwarded to `api.add_router()` (e.g. `auth`, `tags`).

---

## :material-layers: Versioned API Example

A common pattern is using `NinjaAIORouter` to build versioned APIs:

```python
from ninja_aio import NinjaAIO, NinjaAIORouter
from ninja_aio.views import APIView, APIViewSet

api = NinjaAIO(title="My API")

# --- v1 router ---

@api.router("/v1")
class V1Router(NinjaAIORouter):
    pass

@V1Router.viewset(model=Article, prefix="/articles", tags=["v1 - Articles"])
class ArticleV1ViewSet(APIViewSet):
    schema_in = ArticleSchemaIn
    schema_out = ArticleSchemaOut
    schema_update = ArticleSchemaPatch

# --- v2 router (extended schema) ---

@api.router("/v2")
class V2Router(NinjaAIORouter):
    pass

@V2Router.viewset(model=Article, prefix="/articles", tags=["v2 - Articles"])
class ArticleV2ViewSet(APIViewSet):
    schema_in = ArticleV2SchemaIn
    schema_out = ArticleV2SchemaOut
    schema_update = ArticleV2SchemaPatch
```

All routes end up correctly nested under their version prefix in the OpenAPI docs.

---

## :material-information: When to Use NinjaAIORouter

| Scenario | Recommendation |
|---|---|
| Small API with a handful of viewsets | Register directly on `NinjaAIO` with `@api.viewset()` |
| Versioned API (`/v1`, `/v2`) | Use one `NinjaAIORouter` per version |
| Domain-separated modules (auth, billing, catalog…) | Use one `NinjaAIORouter` per domain |
| Reusable router shipped as a library | Define the router in isolation, let consumers attach it |

---

## :material-bookshelf: See Also

<div class="grid cards" markdown>

-   :material-eye:{ .lg .middle } **APIView**

    ---

    Custom non-CRUD endpoints

    [:octicons-arrow-right-24: Learn more](api_view.md)

-   :material-view-grid:{ .lg .middle } **APIViewSet**

    ---

    Full CRUD operations with auto-generated endpoints

    [:octicons-arrow-right-24: Learn more](api_view_set.md)

-   :material-decagram:{ .lg .middle } **Decorators**

    ---

    View and operation decorators

    [:octicons-arrow-right-24: Learn more](decorators.md)

</div>
