---
type: guide
title: Permissions
description: Allow or deny each operation, check single objects and hide rows from the list.
---

# Permissions

Add a permission mixin to a viewset to decide who can call each endpoint,
who can touch each object, and which rows the list shows.

## Add the permission mixin

Put `PermissionViewSetMixin` before `APIViewSet` and override the methods you
need. Every method allows everything by default.

=== "Sync"

    ```python title="blog/api.py"
    from ninja_aio import APIViewSet
    from ninja_aio.views.mixins import PermissionViewSetMixin

    from .auth import JWTAuth
    from .models import Article


    @api.viewset(model=Article)
    class ArticleViewSet(PermissionViewSetMixin, APIViewSet):
        execution_mode = "sync"
        auth = [JWTAuth()]

        def has_permission(self, request, operation):
            if operation == "delete":
                return request.auth.is_staff
            return True
    ```

=== "Async"

    ```python title="blog/api.py"
    from ninja_aio import APIViewSet
    from ninja_aio.views.mixins import PermissionViewSetMixin

    from .auth import JWTAuth
    from .models import Article


    @api.viewset(model=Article)
    class ArticleViewSet(PermissionViewSetMixin, APIViewSet):
        auth = [JWTAuth()]

        async def ahas_permission(self, request, operation):
            if operation == "delete":
                return request.auth.is_staff
            return True
    ```

| Method | Runs | Arguments |
| --- | --- | --- |
| `has_permission` / `ahas_permission` | Before every endpoint, before any query | `request`, `operation` |
| `has_object_permission` / `ahas_object_permission` | After the object is loaded | `request`, `operation`, `obj` |
| `get_permission_queryset` | On the list endpoint | `request`, `queryset` |

Sync viewsets call the plain names, async viewsets call the `a` names.
`get_permission_queryset` is a plain `def` in both modes.

## Know the operation names

`operation` tells you which endpoint is running:

| Endpoint | `operation` |
| --- | --- |
| CRUD | `list`, `retrieve`, `create`, `update`, `delete` |
| Bulk | `bulk_create`, `bulk_update`, `bulk_delete` |
| Custom action | The method name, like `publish` for `def publish(...)` |
| Soft delete | `restore`, `hard_delete`. See [Soft delete](soft-delete.md) |

## Check a single object

Override the object method to look at the loaded instance. Here only the
author of an article can change or delete it:

=== "Sync"

    ```python
    def has_object_permission(self, request, operation, obj):
        if operation in ("update", "delete"):
            return obj.author_id == request.auth.id
        return True
    ```

=== "Async"

    ```python
    async def ahas_object_permission(self, request, operation, obj):
        if operation in ("update", "delete"):
            return obj.author_id == request.auth.id
        return True
    ```

The object check runs for `retrieve`, `update`, `delete` and `@on` actions.
It does not run for `create`, `list`, bulk endpoints or `@action` endpoints:
those only call `has_permission`.

## Hide rows from the list

Return a filtered queryset from `get_permission_queryset`:

```python
def get_permission_queryset(self, request, queryset):
    if request.auth.is_staff:
        return queryset
    return queryset.filter(is_published=True)
```

This only changes `GET /api/articles`. To block a single hidden article on
retrieve, check it in `has_object_permission` too.

## Read the 403 response

Returning `False` stops the request with status `403`:

```json
{
  "error": "forbidden",
  "details": "Permission denied for operation: delete"
}
```

## Use permissions with authentication

Authentication runs first. A request without a valid token gets `401` and never
reaches your permission methods.

`request.auth` is only set on endpoints that require authentication. If you
make an endpoint public, for example with `get_auth = None`, read the user
safely:

```python
def get_permission_queryset(self, request, queryset):
    user = getattr(request, "auth", None)
    if user and user.is_staff:
        return queryset
    return queryset.filter(is_published=True)
```

See [Authentication](authentication.md) for tokens and per-method `auth`.

## Allow operations by role

`RoleBasedPermissionMixin` reads a role from `request.auth` and checks it
against a mapping. You don't write any method:

```python title="blog/api.py"
from ninja_aio.views.mixins import RoleBasedPermissionMixin


@api.viewset(model=Article)
class ArticleViewSet(RoleBasedPermissionMixin, APIViewSet):
    auth = [JWTAuth()]
    permission_roles = {
        "admin": ["list", "retrieve", "create", "update", "delete", "publish"],
        "editor": ["list", "retrieve", "create", "update"],
        "reader": ["list", "retrieve"],
    }
```

| Attribute | Default | What it does |
| --- | --- | --- |
| `permission_roles` | `{}` | Maps each role to the operations it can call. Empty allows everything |
| `role_attribute` | `"role"` | The attribute read from `request.auth` |

The role is read as an attribute, like `request.auth.role`. When
`request.auth` is a dict, such as decoded token claims, it is read as a key,
like `request.auth["role"]`.

Requests without `request.auth`, without a role, or with a role that is not in
the mapping get `403`. List bulk operations and custom actions by name too.

The mixin still has `has_object_permission` and `get_permission_queryset`, so
you can add object and row checks on top.

## Combine with other mixins

Put every mixin before `APIViewSet`. Filter mixins work in any order with the
permission mixin:

```python
from ninja_aio.views.mixins import IcontainsFilterViewSetMixin, PermissionViewSetMixin


@api.viewset(model=Article)
class ArticleViewSet(PermissionViewSetMixin, IcontainsFilterViewSetMixin, APIViewSet):
    query_params = {"title": (str, None)}
```

With `SoftDeleteViewSetMixin`, put the soft delete mixin first:

```python
class ArticleViewSet(SoftDeleteViewSetMixin, PermissionViewSetMixin, APIViewSet):
    ...
```

The list applies `get_permission_queryset` first, then the filters, then
pagination.

!!! warning

    Override the methods that match your mode. An async viewset with a sync
    `def` custom action calls the sync methods for that action, so override
    both `has_permission` and `ahas_permission`. Otherwise the viewset raises
    `ImproperlyConfigured` at startup.

## See also

- [Add permissions](../tutorial/permissions.md)
- [Viewsets](viewsets.md)
- [Authentication](authentication.md)
- [Custom actions](custom-actions.md)
- [Filtering](filtering.md)
