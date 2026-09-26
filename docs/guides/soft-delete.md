---
type: guide
title: Soft delete
description: Hide deleted rows instead of removing them, and restore or permanently delete them later.
---

# Soft delete

This page shows how to mark articles as deleted instead of removing them, and
how to restore or permanently delete them.

## Add the field to your model

Add a `BooleanField` named `is_deleted` to the model:

```python title="blog/models.py" hl_lines="11"
from django.db import models

from ninja_aio import ModelSerializer, SchemaConfig


class Article(ModelSerializer):
    title = models.CharField(max_length=200)
    body = models.TextField()
    is_published = models.BooleanField(default=False)
    views = models.PositiveIntegerField(default=0)
    is_deleted = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Schemas:
        create = SchemaConfig(fields=["title", "body"])
        update = SchemaConfig(optionals=[("title", str), ("body", str)])
        read = SchemaConfig(fields=["id", "title", "is_published", "created_at"])
```

Then run `makemigrations` and `migrate`. Leave `is_deleted` out of the
schemas: clients use the delete and restore endpoints to change it.

## Add the mixin

Put `SoftDeleteViewSetMixin` before `APIViewSet`:

```python title="blog/api.py"
from ninja_aio import NinjaAIO, APIViewSet
from ninja_aio.views.mixins import SoftDeleteViewSetMixin

from .models import Article

api = NinjaAIO(title="Blog API")


@api.viewset(model=Article)
class ArticleViewSet(SoftDeleteViewSetMixin, APIViewSet):
    pass
```

If the model has no `is_deleted` field, the app fails at startup with
`ImproperlyConfigured`. The mixin works the same in sync and async viewsets.

| Attribute | Default | What it does |
| --- | --- | --- |
| `soft_delete_field` | `"is_deleted"` | The name of the boolean field on the model |
| `include_deleted` | `False` | Show deleted rows in list, retrieve and update |

## What changes

| Method | Path | With the mixin |
| --- | --- | --- |
| `DELETE` | `/api/articles/{id}/` | Sets `is_deleted` to `True` and returns `204`. The row stays in the database |
| `GET` | `/api/articles` | Leaves out deleted articles. `count` leaves them out too |
| `GET` | `/api/articles/{id}` | Returns `404` for a deleted article |
| `PATCH` | `/api/articles/{id}/` | Returns `404` for a deleted article |
| `POST` | `/api/articles/{id}/restore` | New. Sets `is_deleted` to `False` |
| `DELETE` | `/api/articles/{id}/hard-delete` | New. Removes the row from the database |

Deleting an article that is already deleted returns `204` again. When you set
`schema_delete_out`, delete returns `200` with the article instead.

Custom actions like `@on("publish")` still run on deleted articles. Check
`obj.is_deleted` in the action if that matters.

## Restore an article

```text
POST /api/articles/1/restore
```

```json
{"id": 1, "title": "Hello Django", "is_published": false, "created_at": "2026-01-01T09:00:00Z"}
```

Restore returns `200` with the `read` schema. It uses the auth of `PATCH`
(`patch_auth`). An article that doesn't exist returns `404`.

## Delete an article for good

```text
DELETE /api/articles/1/hard-delete
```

Hard delete removes the row and returns `204`. It works on deleted and
active articles, and uses the auth of `DELETE` (`delete_auth`). An article
that doesn't exist returns `404`.

## Delete many articles

Enable the bulk delete endpoint with `bulk_operations`:

```python
@api.viewset(model=Article)
class ArticleViewSet(SoftDeleteViewSetMixin, APIViewSet):
    bulk_operations = ["delete"]
```

```text
DELETE /api/articles/bulk/
{"ids": [1, 2, 999]}
```

```json
{
  "success": {"count": 2, "details": [1, 2]},
  "errors": {"count": 1, "details": [{"article": "not found"}]}
}
```

Every existing article in `ids` gets `is_deleted` set to `True`, in one
query. Ids that don't exist go to `errors`. Articles that were already
deleted count as a success. See [Bulk operations](bulk-operations.md).

## Show deleted articles

Set `include_deleted = True` on a second viewset, for example one for staff:

```python
@api.viewset(model=Article, prefix="admin/articles", tags=["Admin"])
class ArticleAdminViewSet(SoftDeleteViewSetMixin, APIViewSet):
    include_deleted = True
```

This viewset lists, retrieves and updates deleted articles too. Delete still
only sets the flag.

## Use another field name

Point `soft_delete_field` to your own boolean field:

```python
@api.viewset(model=Article)
class ArticleViewSet(SoftDeleteViewSetMixin, APIViewSet):
    soft_delete_field = "deleted"
```

## Control who can restore and hard delete

Restore and hard delete run the operation hook with the operation names
`restore` and `hard_delete`. With `PermissionViewSetMixin`, check them in
`has_permission`:

=== "Sync"

    ```python
    from ninja_aio.views.mixins import PermissionViewSetMixin, SoftDeleteViewSetMixin


    @api.viewset(model=Article)
    class ArticleViewSet(SoftDeleteViewSetMixin, PermissionViewSetMixin, APIViewSet):
        execution_mode = "sync"
        auth = [JWTAuth()]
        get_auth = None

        def has_permission(self, request, operation):
            if operation in ("restore", "hard_delete"):
                return is_staff(request)
            return True
    ```

=== "Async"

    ```python
    from ninja_aio.views.mixins import PermissionViewSetMixin, SoftDeleteViewSetMixin


    @api.viewset(model=Article)
    class ArticleViewSet(SoftDeleteViewSetMixin, PermissionViewSetMixin, APIViewSet):
        auth = [JWTAuth()]
        get_auth = None

        async def ahas_permission(self, request, operation):
            if operation in ("restore", "hard_delete"):
                return is_staff(request)
            return True
    ```

`JWTAuth` and `is_staff` come from [Permissions](../tutorial/permissions.md).
A denied request returns `403`. The soft delete itself uses the `delete`
operation, and bulk delete uses `bulk_delete`.

!!! note

    Restore and hard delete don't call `has_object_permission`. Put the checks
    for these two endpoints in `has_permission`.

## Hooks

A soft delete saves the article, so it runs the save hooks, not the delete
hooks:

| Action | Model hooks that run |
| --- | --- |
| Soft delete, restore | `before_save`, `after_save`, `@on_update` without field names |
| Bulk soft delete | None. The rows are updated in one query |
| Hard delete | The delete hooks, like `on_delete` and `@on_delete` |

See [Hooks](hooks.md).

## See also

- [Viewsets](viewsets.md)
- [Permissions](permissions.md)
- [Bulk operations](bulk-operations.md)
- [Mixins reference](../api/views/mixins.md)
