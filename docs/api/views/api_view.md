# API View

The `APIView` class provides a base for creating simple API endpoints with custom views.

## Overview

`APIView` is a lightweight wrapper around Django Ninja's `Router` that provides:

- Organized routing with tags
- Custom authentication configuration
- Error handling with standard HTTP status codes

## Class Definition

```python
class APIView:
    api: NinjaAPI
    router_tag: str
    api_route_path: str
    auth: list | None = NOT_SET
```

## Attributes

| Attribute        | Type           | Description                                     |
| ---------------- | -------------- | ----------------------------------------------- |
| `api`            | `NinjaAPI`     | The NinjaAPI instance to register routes        |
| `router_tag`     | `str`          | Tag name for grouping endpoints in OpenAPI docs |
| `api_route_path` | `str`          | Base path for all routes in this view           |
| `auth`           | `list \| None` | Authentication classes (optional)               |

## Methods

### Recommended: decorator-based endpoints

Prefer class method decorators to define non-CRUD endpoints. Decorators lazily bind instance methods to the router and automatically remove `self` from the OpenAPI signature while preserving type hints.

Available decorators (from `ninja_aio.decorators`):

- `@api_get(path, ...)`
- `@api_post(path, ...)`
- `@api_put(path, ...)`
- `@api_patch(path, ...)`
- `@api_delete(path, ...)`
- `@api_options(path, ...)`
- `@api_head(path, ...)`

Example:

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

Notes:

- Decorators support per-endpoint `auth`, `response`, `tags`, `summary`, `description`, throttling, and OpenAPI extras.
- Sync methods run via `sync_to_async` automatically.
- `self` is excluded from the exposed signature; parameter type hints are preserved.

### Legacy: `views()` (still supported)

You can still override `views()` to define endpoints imperatively.

**Example - Basic Views:**

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
            # bulk creation logic
            return {"created": len(data)}
```

**Example - With Authentication:**

```python
class ProtectedAPIView(APIView):
    api = api_instance
    router_tag = "Protected"
    api_route_path = "/protected"
    auth = [JWTAuth()]

    def views(self):
        # Authenticated endpoint
        @self.router.get("/private", auth=self.auth)
        async def private_data(request):
            return {"user_id": request.auth.user_id}

        # Public endpoint
        @self.router.get("/public")
        async def public_data(request):
            return {"message": "This is public"}
```

### `add_views_to_route()`

Registers all defined views to the API instance.

**Returns:** The router instance

**Note:** When using `@api.view(prefix="/path", tags=[...])`, the router is mounted automatically and decorator-based endpoints are registered lazily on instantiation; manual registration via `add_views_to_route()` is not required.

## Complete Example

**Recommended:**

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

**Alternative implementation:**

```python
api = NinjaAIO(title="My API")

class AnalyticsView(APIView):
    api = api
    router_tag = "Analytics"
    api_route_path = "/analytics"

    def views(self):
        @self.router.get("/dashboard", response=StatsSchema)
        async def dashboard(request):
            return {"total": 1000, "active": 750}

        @self.router.post("/track")
        async def track_event(request, event: str):
            return {"tracked": event}

AnalyticsView().add_views_to_route()
```

## Notes

- Use `APIView` for simple, non-CRUD endpoints
- For CRUD operations, use [`APIViewSet`](api_view_set.md)
- All views are async-compatible
- Standard error codes are available via `self.error_codes`
- Decorator-based endpoints are preferred for clarity and better OpenAPI signatures.

Note:

- Path schema PK type is inferred from the model’s primary key for ViewSets.
- NinjaAIO remains API-compatible; global CSRF argument is no longer required in initialization.

## See Also

- [API View Set](api_view_set.md) - Full CRUD operations
- [Authentication](../authentication.md) - Authentication setup
