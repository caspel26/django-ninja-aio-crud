# :material-eye: API View

The `APIView` class provides a base for creating custom API endpoints outside of CRUD operations.

<div class="grid cards" markdown>

-   :material-tag:{ .lg .middle } **Organized Routing**

    ---

    Automatic tag grouping in OpenAPI docs

-   :material-shield-lock:{ .lg .middle } **Auth Support**

    ---

    Per-view and per-endpoint authentication

-   :material-lightning-bolt:{ .lg .middle } **Async First**

    ---

    Native async with automatic sync wrapping

</div>

---

## :material-code-braces: Class Definition

```python
class APIView:
    api: NinjaAPI
    router_tag: str
    api_route_path: str
    auth: list | None = NOT_SET
```

| Attribute        | Type           | Description                                     |
| ---------------- | -------------- | ----------------------------------------------- |
| `api`            | `NinjaAPI`     | The NinjaAPI instance to register routes        |
| `router_tag`     | `str`          | Tag name for grouping endpoints in OpenAPI docs |
| `api_route_path` | `str`          | Base path for all routes in this view           |
| `auth`           | `list \| None` | Authentication classes (optional)               |

---

## :material-function-variant: Creating Endpoints

### Recommended: `@api.view()` with decorators

Use class method decorators to define endpoints. Decorators lazily bind instance methods to the router and automatically remove `self` from the OpenAPI signature while preserving type hints.

```python
from ninja_aio import NinjaAIO
from ninja_aio.views import APIView
from ninja_aio.decorators import api_get, api_post
from ninja import Schema

api = NinjaAIO(title="My API")

class StatsSchema(Schema):
    total: int
    active: int

@api.view(prefix="/analytics", tags=["Analytics"])
class AnalyticsView(APIView):
    @api_get("/dashboard", response=StatsSchema)
    async def dashboard(self, request):
        return {"total": 1000, "active": 750}

    @api_post("/track")
    async def track_event(self, request, event: str):
        return {"tracked": event}
```

Available decorators (from `ninja_aio.decorators`):

| Decorator | HTTP Method |
|---|---|
| `@api_get(path, ...)` | GET |
| `@api_post(path, ...)` | POST |
| `@api_put(path, ...)` | PUT |
| `@api_patch(path, ...)` | PATCH |
| `@api_delete(path, ...)` | DELETE |
| `@api_options(path, ...)` | OPTIONS |
| `@api_head(path, ...)` | HEAD |

!!! tip "Decorator features"
    Decorators support per-endpoint `auth`, `response`, `tags`, `summary`, `description`, throttling, and OpenAPI extras. Sync methods are wrapped with `sync_to_async` automatically.

---

### Alternative: `views()` method (legacy)

You can override `views()` to define endpoints imperatively. This approach still works but decorator-based endpoints are preferred.

=== "Basic views"

    ```python
    class UserAPIView(APIView):
        api = api_instance
        router_tag = "Users"
        api_route_path = "/users"

        def views(self):
            @self.router.get("/stats")
            async def get_stats(request):
                return {"total_users": 100}

            @self.router.post("/bulk-create")
            async def bulk_create(request, data: list[UserSchema]):
                return {"created": len(data)}
    ```

=== "With authentication"

    ```python
    class ProtectedAPIView(APIView):
        api = api_instance
        router_tag = "Protected"
        api_route_path = "/protected"
        auth = [JWTAuth()]

        def views(self):
            @self.router.get("/private", auth=self.auth)
            async def private_data(request):
                return {"user_id": request.auth.user_id}

            @self.router.get("/public")
            async def public_data(request):
                return {"message": "This is public"}
    ```

!!! note "Manual registration"
    When using `@api.view(prefix="/path", tags=[...])`, the router is mounted automatically. With the legacy approach, call `add_views_to_route()` to register endpoints manually.

---

## :material-information: When to Use APIView vs APIViewSet

| Use Case | APIView | APIViewSet |
|---|---|---|
| Custom analytics endpoints | :material-check: | |
| Health checks, webhooks | :material-check: | |
| Full CRUD for a model | | :material-check: |
| Model with filtering + pagination | | :material-check: |
| Mix of CRUD + custom endpoints | | :material-check: (add custom via decorators) |

!!! tip
    Use `APIView` for non-CRUD endpoints. For CRUD operations, use [`APIViewSet`](api_view_set.md) which generates all endpoints automatically and still supports custom endpoints via decorators.

---

## :material-bookshelf: See Also

<div class="grid cards" markdown>

-   :material-view-grid:{ .lg .middle } **APIViewSet**

    ---

    Full CRUD operations with auto-generated endpoints

    [:octicons-arrow-right-24: Learn more](api_view_set.md)

-   :material-decagram:{ .lg .middle } **Decorators**

    ---

    View and operation decorators for custom endpoints

    [:octicons-arrow-right-24: Learn more](decorators.md)

-   :material-shield-lock:{ .lg .middle } **Authentication**

    ---

    JWT and custom auth configuration

    [:octicons-arrow-right-24: Learn more](../authentication.md)

</div>
