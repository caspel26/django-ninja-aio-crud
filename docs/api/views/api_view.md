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

### `views()`

Override this method to define your custom endpoints.

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

**Usage:**

```python
view = UserAPIView()
view.add_views_to_route()
```

## Complete Example

```python
from ninja_aio import NinjaAIO
from ninja_aio.views import APIView
from ninja import Schema

api = NinjaAIO(title="My API")

class StatsSchema(Schema):
    total: int
    active: int

class AnalyticsView(APIView):
    api = api
    router_tag = "Analytics"
    api_route_path = "/analytics"

    def views(self):
        @self.router.get("/dashboard", response=StatsSchema)
        async def dashboard(request):
            return {
                "total": 1000,
                "active": 750
            }

        @self.router.post("/track")
        async def track_event(request, event: str):
            # tracking logic
            return {"tracked": event}

# Register views
AnalyticsView().add_views_to_route()
```

## Notes

- Use `APIView` for simple, non-CRUD endpoints
- For CRUD operations, use [`APIViewSet`](api_view_set.md) instead
- All views are automatically async-compatible
- Error codes `{400, 401, 404, 428}` are available via `self.error_codes`

Note:

- Path schema PK type is inferred from the model’s primary key for ViewSets.
- NinjaAIO remains API-compatible; global CSRF argument is no longer required in initialization.

## See Also

- [API View Set](api_view_set.md) - Full CRUD operations
- [Authentication](../authentication.md) - Authentication setup
