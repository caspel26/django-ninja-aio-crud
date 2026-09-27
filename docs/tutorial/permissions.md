---
type: tutorial
step: 5
steps: 7
title: Add permissions
description: Decide who can see and change each article.
---

# Add permissions

In this step you decide who can do what:

- Everyone can read published articles. Drafts stay hidden.
- Logged-in users can create and update articles.
- Only staff users can delete or publish articles.

## Add the permission mixin

`PermissionViewSetMixin` gives you three methods to override. Returning `False`
stops the request with `403`. In async viewsets the first two start with `a`.

| Method | Runs | Use it to |
| --- | --- | --- |
| `has_permission` / `ahas_permission` | Before every operation | Allow or deny by operation |
| `has_object_permission` / `ahas_object_permission` | After loading one object | Allow or deny by object |
| `get_permission_queryset` | On the list endpoint | Hide rows |

=== "Sync"

    ```python title="blog/api.py"
    from ninja_aio.views.mixins import PermissionViewSetMixin


    def is_staff(request):
        user = getattr(request, "auth", None)
        return bool(user and user.is_staff)


    @api.viewset(model=Article)
    class ArticleViewSet(PermissionViewSetMixin, APIViewSet):
        execution_mode = "sync"
        auth = [JWTAuth()]
        get_auth = None

        def has_permission(self, request, operation):
            if operation in ("delete", "publish"):
                return is_staff(request)
            return True

        def has_object_permission(self, request, operation, obj):
            if operation == "retrieve":
                return obj.is_published
            return True

        def get_permission_queryset(self, request, queryset):
            return queryset.filter(is_published=True)
    ```

=== "Async"

    ```python title="blog/api.py"
    from ninja_aio.views.mixins import PermissionViewSetMixin


    def is_staff(request):
        user = getattr(request, "auth", None)
        return bool(user and user.is_staff)


    @api.viewset(model=Article)
    class ArticleViewSet(PermissionViewSetMixin, APIViewSet):
        auth = [JWTAuth()]
        get_auth = None

        async def ahas_permission(self, request, operation):
            if operation in ("delete", "publish"):
                return is_staff(request)
            return True

        async def ahas_object_permission(self, request, operation, obj):
            if operation == "retrieve":
                return obj.is_published
            return True

        def get_permission_queryset(self, request, queryset):
            return queryset.filter(is_published=True)
    ```

The operation is one of `list`, `retrieve`, `create`, `update` and `delete`.
For custom actions it is the method name, like `publish`.

## Try it

| Request | Anonymous | Logged in | Staff |
| --- | --- | --- | --- |
| `GET /api/articles` | Published only | Published only | Published only |
| `GET` a draft | `403` | `403` | `403` |
| `POST /api/articles/` | `401` | `201` | `201` |
| `PATCH .../{id}/` | `401` | `200` | `200` |
| `POST .../{id}/publish` | `401` | `403` | `200` |
| `DELETE .../{id}/` | `401` | `403` | `204` |

!!! note

    `request.auth` is only set on endpoints that require authentication. To let
    staff users read drafts, remove `get_auth = None` so reading also needs a
    token, then check `is_staff(request)` in `get_permission_queryset`.

## Permissions by role

If your user model has a `role` field, `RoleBasedPermissionMixin` maps roles to
operations without writing any method:

```python
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

Users without a role, or with a role that is not listed, get `403`.

[Next: filter, search and sort](filtering.md){ .md-button .md-button--primary }
