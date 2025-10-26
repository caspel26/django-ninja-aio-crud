# API ViewSet

The `APIViewSet` class provides complete CRUD operations with automatic endpoint generation, pagination, filtering, and many-to-many relationship management.

## Overview

`APIViewSet` automatically generates:
- **List** endpoint with pagination and filtering
- **Create** endpoint with validation
- **Retrieve** endpoint for single objects
- **Update** endpoint (partial/full)
- **Delete** endpoint
- **Many-to-Many** relationship endpoints (optional)

## Class Definition

```python
class APIViewSet:
    model: ModelSerializer | Model
    api: NinjaAPI
    schema_in: Schema | None = None
    schema_out: Schema | None = None
    schema_update: Schema | None = None
    # ... additional attributes
```

## Core Attributes

| Attribute | Type | Default | Description |
|-----------|------|---------|-------------|
| `model` | `ModelSerializer \| Model` | **Required** | Django model or ModelSerializer |
| `api` | `NinjaAPI` | **Required** | API instance |
| `schema_in` | `Schema \| None` | `None` | Input schema for create |
| `schema_out` | `Schema \| None` | `None` | Output schema for read |
| `schema_update` | `Schema \| None` | `None` | Input schema for update |

## Authentication Attributes

| Attribute | Type | Default | Description |
|-----------|------|---------|-------------|
| `auth` | `list \| None` | `NOT_SET` | Global auth for all views |
| `get_auth` | `list \| None` | `NOT_SET` | Auth for GET requests |
| `post_auth` | `list \| None` | `NOT_SET` | Auth for POST requests |
| `patch_auth` | `list \| None` | `NOT_SET` | Auth for PATCH requests |
| `delete_auth` | `list \| None` | `NOT_SET` | Auth for DELETE requests |

## Pagination & Filtering

| Attribute | Type | Default | Description |
|-----------|------|---------|-------------|
| `pagination_class` | `type[AsyncPaginationBase]` | `PageNumberPagination` | Pagination class |
| `query_params` | `dict[str, tuple[type, ...]]` | `{}` | Query parameter filters |

## Customization Attributes

| Attribute | Type | Default | Description |
|-----------|------|---------|-------------|
| `disable` | `list[type[VIEW_TYPES]]` | `[]` | Disable specific views |
| `api_route_path` | `str` | `""` | Custom base path |
| `list_docs` | `str` | `"List all objects."` | List endpoint docs |
| `create_docs` | `str` | `"Create a new object."` | Create endpoint docs |
| `retrieve_docs` | `str` | `"Retrieve a specific object..."` | Retrieve endpoint docs |
| `update_docs` | `str` | `"Update an object..."` | Update endpoint docs |
| `delete_docs` | `str` | `"Delete an object..."` | Delete endpoint docs |

## Many-to-Many Attributes

| Attribute | Type | Default | Description |
|-----------|------|---------|-------------|
| `m2m_relations` | `tuple[ModelSerializer \| Model, str]` | `[]` | M2M relations to manage |
| `m2m_add` | `bool` | `True` | Enable add operation |
| `m2m_remove` | `bool` | `True` | Enable remove operation |
| `m2m_get` | `bool` | `True` | Enable get operation |
| `m2m_auth` | `list \| None` | `NOT_SET` | Auth for M2M views |

## Generated Endpoints

When you create an `APIViewSet`, the following endpoints are automatically generated:

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/` | List all objects (paginated) |
| `POST` | `/` | Create new object |
| `GET` | `/{id}` | Retrieve single object |
| `PATCH` | `/{id}/` | Update object |
| `DELETE` | `/{id}/` | Delete object |

## Basic Example

```python
from ninja_aio import NinjaAIO
from ninja_aio.views import APIViewSet
from ninja_aio.models import ModelSerializer
from django.db import models

# Define your model
class User(ModelSerializer):
    username = models.CharField(max_length=150, unique=True)
    email = models.EmailField()
    is_active = models.BooleanField(default=True)
    
    class CreateSerializer:
        fields = ["username", "email"]
    
    class ReadSerializer:
        fields = ["id", "username", "email", "is_active"]
    
    class UpdateSerializer:
        optionals = [("email", str), ("is_active", bool)]

# Create API
api = NinjaAIO(title="My API")

# Create ViewSet
class UserViewSet(APIViewSet):
    model = User
    api = api

# Register routes
UserViewSet().add_views_to_route()
```

This generates:
- `GET /user/` - List users
- `POST /user/` - Create user
- `GET /user/{id}` - Get user
- `PATCH /user/{id}/` - Update user
- `DELETE /user/{id}/` - Delete user

## Advanced Examples

### With Custom Authentication

```python
from ninja_aio.auth import AsyncJwtBearer

class MyAuth(AsyncJwtBearer):
    jwt_public = jwk.RSAKey.import_key(PUBLIC_KEY)
    claims = {"iss": {"value": "my-issuer"}}
    
    async def auth_handler(self, request):
        user_id = self.dcd.claims.get("sub")
        return await User.objects.aget(id=user_id)

class UserViewSet(APIViewSet):
    model = User
    api = api
    auth = [MyAuth()]  # Apply to all endpoints
    delete_auth = None  # Except delete (public)
```

### With Query Parameters

```python
class UserViewSet(APIViewSet):
    model = User
    api = api
    query_params = {
        "is_active": (bool, ...),
        "created_after": (str, None),
        "role": (str, None),
    }
    
    async def query_params_handler(self, queryset, filters):
        if filters.get("is_active") is not None:
            queryset = queryset.filter(is_active=filters["is_active"])
        if filters.get("created_after"):
            queryset = queryset.filter(
                created_at__gte=filters["created_after"]
            )
        if filters.get("role"):
            queryset = queryset.filter(role=filters["role"])
        return queryset
```

Usage: `GET /user/?is_active=true&role=admin`

### Disabling Specific Views

```python
class UserViewSet(APIViewSet):
    model = User
    api = api
    disable = ["delete", "update"]  # Only list, create, retrieve
```

### Custom Views

```python
class UserViewSet(APIViewSet):
    model = User
    api = api
    
    def views(self):
        # Add custom endpoint
        @self.router.post("/{pk}/activate/")
        async def activate_user(request, pk: int):
            user = await User.objects.aget(pk=pk)
            user.is_active = True
            await user.asave()
            return {"message": "User activated"}
        
        @self.router.get("/statistics/")
        async def statistics(request):
            total = await User.objects.acount()
            active = await User.objects.filter(is_active=True).acount()
            return {"total": total, "active": active}
```

## Many-to-Many Relationships

### Setup

```python
class Group(ModelSerializer):
    name = models.CharField(max_length=100)
    
    class ReadSerializer:
        fields = ["id", "name"]

class User(ModelSerializer):
    username = models.CharField(max_length=150)
    groups = models.ManyToManyField(Group, related_name="users")
    
    class ReadSerializer:
        fields = ["id", "username", "groups"]

class UserViewSet(APIViewSet):
    model = User
    api = api
    m2m_relations = [(Group, "groups")]
```

### Generated M2M Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/{id}/group/` | List related groups |
| `POST` | `/{id}/group/` | Add/remove groups |

### Usage Examples

**Get related groups:**
```bash
GET /user/1/group/
```

Response:
```json
{
  "items": [
    {"id": 1, "name": "Admins"},
    {"id": 2, "name": "Users"}
  ],
  "count": 2
}
```

**Add and remove groups:**
```bash
POST /user/1/group/
Content-Type: application/json

{
  "add": [3, 4],
  "remove": [2]
}
```

Response:
```json
{
  "results": {
    "count": 3,
    "details": [
      "Group with id 3 successfully added",
      "Group with id 4 successfully added",
      "Group with id 2 successfully removed"
    ]
  },
  "errors": {
    "count": 0,
    "details": []
  }
}
```

## Overridable Methods

### `query_params_handler(queryset, filters)`

Handle custom filtering logic.

```python
async def query_params_handler(self, queryset, filters):
    if filters.get("search"):
        queryset = queryset.filter(
            Q(username__icontains=filters["search"]) |
            Q(email__icontains=filters["search"])
        )
    return queryset
```

## Error Handling

All endpoints automatically return appropriate error responses:

| Status Code | Description |
|-------------|-------------|
| `400` | Bad Request (validation errors) |
| `401` | Unauthorized |
| `404` | Not Found |
| `428` | Precondition Required |

## Performance Tips

1. **Use `select_related()` and `prefetch_related()`** - Automatically handled for ModelSerializer
2. **Implement custom `queryset_request()`** - Filter at database level
3. **Use pagination** - Prevents loading too many objects
4. **Optimize query parameters** - Use indexed fields for filtering

## See Also

- [Model Serializer](../models/model_serializer.md) - Define schemas on models
- [Authentication](../authentication.md) - Secure your endpoints
- [Pagination](../pagination.md) - Configure pagination
- [API View](api_view.md) - Simple custom views