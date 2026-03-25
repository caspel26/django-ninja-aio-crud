# Soft Delete

<p class="tutorial-subtitle">
Replace hard deletes with a soft delete flag — keep your data safe and recoverable.
</p>

---

## Overview

The `SoftDeleteViewSetMixin` replaces hard deletes with a boolean flag, automatically excludes soft-deleted records from queries, and provides restore and permanent delete endpoints.

**What changes when you add the mixin:**

| Endpoint | Without Mixin | With Mixin |
|---|---|---|
| `DELETE /{pk}/` | Row removed from DB | Sets `is_deleted=True` |
| `DELETE /bulk/` | Rows removed from DB | Sets `is_deleted=True` on all |
| `GET /` (list) | All records | Excludes `is_deleted=True` |
| `GET /{pk}/` | Any record | 404 if `is_deleted=True` |
| `PATCH /{pk}/` | Any record | 404 if `is_deleted=True` |
| `POST /{pk}/restore` | — | Restores soft-deleted record |
| `DELETE /{pk}/hard-delete` | — | Permanently removes record |

---

## Step 1: Add the Field to Your Model

The mixin requires a `BooleanField` on your model. Add it yourself — the mixin does **not** create it for you:

```python
from django.db import models

class Article(models.Model):
    title = models.CharField(max_length=255)
    content = models.TextField()
    is_deleted = models.BooleanField(default=False)  # (1)!
```

1. The field name defaults to `is_deleted` but is configurable via `soft_delete_field`.

Don't forget to run `makemigrations` and `migrate` after adding the field.

---

## Step 2: Add the Mixin to Your ViewSet

```python
from ninja_aio.views import APIViewSet
from ninja_aio.views.mixins import SoftDeleteViewSetMixin

class ArticleAPI(SoftDeleteViewSetMixin, APIViewSet):
    model = Article
```

That's it. All delete operations now soft-delete, and soft-deleted records are hidden from list/retrieve/update.

---

## Configuration

### Custom Field Name

If your boolean field is named differently:

```python
class ArticleAPI(SoftDeleteViewSetMixin, APIViewSet):
    model = Article
    soft_delete_field = "deleted"  # (1)!
```

1. Must match the actual `BooleanField` name on the model.

### Admin View (Include Deleted Records)

For admin viewsets that need to see and manage soft-deleted records:

```python
class ArticleAdminAPI(SoftDeleteViewSetMixin, APIViewSet):
    model = Article
    include_deleted = True  # (1)!
```

1. Soft-deleted records appear in list, can be retrieved and updated.

---

## Endpoints

### Soft Delete

```http
DELETE /articles/1/
```

Sets `is_deleted=True` on the record. The row **stays in the database**. Returns `204 No Content`.

Soft-deleting an already soft-deleted record is **idempotent** — no error.

### Bulk Soft Delete

```http
DELETE /articles/bulk/
Content-Type: application/json

{"ids": [1, 2, 3]}
```

Uses a single `UPDATE ... SET is_deleted=True WHERE pk IN (...)` query. Returns the standard `BulkResultSchema` with partial success semantics.

### Restore

```http
POST /articles/1/restore
```

Sets `is_deleted=False` and returns the serialized object. Uses `patch_auth` for authorization.

### Hard Delete

```http
DELETE /articles/1/hard-delete
```

Permanently removes the record from the database. Returns `204 No Content`. Uses `delete_auth` for authorization.

---

## Composability

The mixin works with all other mixins. Order matters — put `SoftDeleteViewSetMixin` **first**:

```python
class ArticleAPI(
    SoftDeleteViewSetMixin,
    PermissionViewSetMixin,
    IcontainsFilterViewSetMixin,
    APIViewSet,
):
    model = Article
    query_params = {"title": (str, None)}

    async def has_permission(self, request, operation):
        if operation in ("hard_delete", "restore"):
            return request.auth.is_staff
        return True
```

The hooks chain via `super()`:

1. **Soft delete** filters out `is_deleted=True`
2. **Permissions** filter by user role
3. **Filters** apply query parameters

---

## Validation

The mixin validates at initialization that the model has the configured field. If the field is missing, a clear error is raised immediately:

```
django.core.exceptions.ImproperlyConfigured:
Article does not have a 'is_deleted' field.
Add a BooleanField or set soft_delete_field to the correct name.
```

---

## Attributes Reference

| Attribute | Type | Default | Description |
|---|---|---|---|
| `soft_delete_field` | `str` | `"is_deleted"` | Name of the `BooleanField` on the model |
| `include_deleted` | `bool` | `False` | If `True`, soft-deleted records are visible in list/retrieve/update |
