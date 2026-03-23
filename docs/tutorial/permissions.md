# Permissions & Authorization

<p class="tutorial-subtitle">
Control who can access and modify your API resources with granular permission checks.
</p>

---

## Overview

Django Ninja AIO CRUD separates **authentication** (who is the user?) from **authorization** (what can they do?). Authentication is handled by `AsyncJwtBearer` or any Django Ninja auth class. Authorization is handled by **permission mixins**.

Two mixins are available:

| Mixin | Use case |
|-------|----------|
| `PermissionViewSetMixin` | Custom permission logic via overridable hooks |
| `RoleBasedPermissionMixin` | Declarative role-to-operations mapping |

---

## PermissionViewSetMixin

### Basic setup

```python
from ninja_aio.views import APIViewSet
from ninja_aio.views.mixins import PermissionViewSetMixin

class ArticleAPI(PermissionViewSetMixin, APIViewSet):
    model = Article

    async def has_permission(self, request, operation):
        """Called before any DB query."""
        if operation in ("create", "update", "delete"):
            return getattr(request.auth, "is_staff", False)
        return True
```

With just this, non-staff users get a **403 Forbidden** response when trying to create, update, or delete articles, but can still list and retrieve.

### Object-level permissions

For row-level control, override `has_object_permission`. It receives the actual model instance **after** it's fetched from the database:

```python
class ArticleAPI(PermissionViewSetMixin, APIViewSet):
    model = Article

    async def has_permission(self, request, operation):
        return request.auth is not None

    async def has_object_permission(self, request, operation, obj):
        # Authors can edit their own articles; everyone else can only read
        if operation in ("update", "delete"):
            return obj.author_id == request.auth.id
        return True
```

!!! info
    `has_object_permission` is only called for **retrieve**, **update**, and **delete** operations. List views use `get_permission_queryset` instead to avoid N+1 queries.

### Row-level filtering

Use `get_permission_queryset` to restrict which objects are visible in list views:

```python
class ArticleAPI(PermissionViewSetMixin, APIViewSet):
    model = Article

    def get_permission_queryset(self, request, queryset):
        if not getattr(request.auth, "is_staff", False):
            return queryset.filter(status="published")
        return queryset
```

### Complete example

```python
class ProjectAPI(PermissionViewSetMixin, APIViewSet):
    model = Project

    async def has_permission(self, request, operation):
        user = request.auth
        if user is None:
            return False
        if operation == "create":
            return user.can_create_projects
        return True

    async def has_object_permission(self, request, operation, obj):
        user = request.auth
        if operation in ("update", "delete"):
            return obj.owner_id == user.id or user.is_admin
        return True

    def get_permission_queryset(self, request, queryset):
        user = request.auth
        if user.is_admin:
            return queryset
        return queryset.filter(
            Q(owner=user) | Q(members=user)
        ).distinct()
```

---

## RoleBasedPermissionMixin

For simpler role-based access, use the declarative approach:

```python
from ninja_aio.views.mixins import RoleBasedPermissionMixin

class BookAPI(RoleBasedPermissionMixin, APIViewSet):
    model = Book
    permission_roles = {
        "admin": ["create", "list", "retrieve", "update", "delete"],
        "editor": ["create", "list", "retrieve", "update"],
        "reader": ["list", "retrieve"],
    }
```

The mixin reads the role from `request.auth.role` by default. Customize with `role_attribute`:

```python
class BookAPI(RoleBasedPermissionMixin, APIViewSet):
    model = Book
    role_attribute = "access_level"  # reads request.auth.access_level
    permission_roles = {
        "full": ["create", "list", "retrieve", "update", "delete"],
        "readonly": ["list", "retrieve"],
    }
```

### Bulk operations

Include bulk operation names in the roles mapping:

```python
permission_roles = {
    "admin": [
        "create", "list", "retrieve", "update", "delete",
        "bulk_create", "bulk_update", "bulk_delete",
    ],
    "editor": ["create", "list", "retrieve", "update"],
}
```

### Custom actions

`@action` endpoints are automatically checked using the action method name:

```python
from ninja_aio.decorators import action

class BookAPI(RoleBasedPermissionMixin, APIViewSet):
    model = Book
    permission_roles = {
        "admin": ["create", "list", "retrieve", "update", "delete", "archive"],
        "editor": ["create", "list", "retrieve", "update"],
    }

    @action(detail=True, methods=["post"])
    async def archive(self, request, pk):
        # Only admin can access — checked automatically with operation="archive"
        ...
```

---

## Combining with filters

Permission mixins work seamlessly with filter mixins:

```python
from ninja_aio.views.mixins import (
    PermissionViewSetMixin,
    IcontainsFilterViewSetMixin,
    BooleanFilterViewSetMixin,
)

class UserAPI(
    PermissionViewSetMixin,
    IcontainsFilterViewSetMixin,
    BooleanFilterViewSetMixin,
    APIViewSet,
):
    model = User
    query_params = {
        "name": (str, None),
        "is_active": (bool, None),
    }

    async def has_permission(self, request, operation):
        return request.auth is not None
```

The permission check runs **first**, then filters are applied to the queryset.

---

## Error responses

When permission is denied, the API returns:

```json
{
    "error": "forbidden",
    "details": "Permission denied for operation: delete"
}
```

HTTP status code: **403 Forbidden**

You can customize the error by raising `ForbiddenError` directly in your hooks:

```python
from ninja_aio.exceptions import ForbiddenError

async def has_permission(self, request, operation):
    if not request.auth:
        raise ForbiddenError(error={"auth": "login required"})
    return True
```
