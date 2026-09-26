---
type: guide
title: Bulk operations
description: Create, update and delete many objects in one request or one Python call.
---

# Bulk operations

This page shows how to add bulk endpoints to a viewset, what they accept and
return, and how to run the same operations from Python.

## Add bulk endpoints

List the operations you want in `bulk_operations`:

```python title="blog/api.py"
from ninja_aio import NinjaAIO, APIViewSet

from .models import Article

api = NinjaAIO(title="Blog API")


@api.viewset(model=Article)
class ArticleViewSet(APIViewSet):
    bulk_operations = ["create", "update", "delete"]
```

You get these endpoints:

| Method | Path | Status | Body |
| --- | --- | --- | --- |
| `POST` | `/api/articles/bulk/` | 200 | A list of `create` bodies |
| `PATCH` | `/api/articles/bulk/` | 200 | A list of `update` bodies, each with its `id` |
| `DELETE` | `/api/articles/bulk/` | 200 | `{"ids": [...]}` |

Bulk create needs a `create` schema and bulk update needs an `update` schema.
With `NINJA_AIO_APPEND_SLASH = False` the path is `/api/articles/bulk`. Each
endpoint uses the auth of its HTTP method, like `post_auth` for bulk create.

To skip one endpoint, add `bulk_create`, `bulk_update` or `bulk_delete` to
`disable`.

## Send the requests

Bulk create takes the same body as a single create, in a list:

```bash
curl -X POST localhost:8000/api/articles/bulk/ \
  -H "Content-Type: application/json" \
  -d '[{"title": "One", "body": "...", "category_id": 1},
       {"title": "Two", "body": "...", "category_id": 99}]'
```

```json
{
  "success": {"count": 1, "details": [1]},
  "errors": {"count": 1, "details": [{"category": "not found"}]}
}
```

Bulk update takes `update` bodies with the primary key of each object:

```bash
curl -X PATCH localhost:8000/api/articles/bulk/ \
  -H "Content-Type: application/json" \
  -d '[{"id": 1, "title": "New title"}, {"id": 99, "title": "Missing"}]'
```

```json
{
  "success": {"count": 1, "details": [1]},
  "errors": {"count": 1, "details": [{"article": "not found"}]}
}
```

Bulk delete takes the list of primary keys:

```bash
curl -X DELETE localhost:8000/api/articles/bulk/ \
  -H "Content-Type: application/json" \
  -d '{"ids": [1, 2, 99]}'
```

```json
{
  "success": {"count": 2, "details": [1, 2]},
  "errors": {"count": 1, "details": [{"article": "not found"}]}
}
```

`success.details` lists the primary keys of the saved or deleted objects.

## Handle partial failures

Each item is saved on its own. Valid items are saved, the others are listed
in `errors`, so the status is `200` even when some items fail. A failed item
doesn't undo the others.

The body is still validated as a whole first. If one item is missing a
required field or has a wrong type, the request returns `422` and nothing is
saved.

In bulk update, an item with only the `id` is accepted and changes nothing.
Set `require_update_fields = True` on the viewset to list it in `errors`
instead.

Each item runs through the same code as the single endpoint. Your model
hooks run once per item, and bulk update and delete only find objects
returned by `queryset_request`. See [Hooks](hooks.md).

## Choose the returned fields

Set `bulk_response_fields` to return other fields in `success.details`:

```python
@api.viewset(model=Article)
class ArticleViewSet(APIViewSet):
    bulk_operations = ["create", "update", "delete"]
    bulk_response_fields = ["id", "title"]
```

```json
{
  "success": {"count": 1, "details": [{"id": 1, "title": "One"}]},
  "errors": {"count": 0, "details": []}
}
```

| Value | Each detail is |
| --- | --- |
| `None` (default) | The primary key, like `1` |
| `"title"` | The field value, like `"One"` |
| `["id", "title"]` | An object with those fields |

## Run bulk operations in Python

The same operations are classmethods on your `ModelSerializer` or
`Serializer`. They return a `BulkResult`:

=== "Sync"

    ```python
    result = Article.bulk_create([
        {"title": "One", "body": "...", "category_id": 1},
        {"title": "Two"},
    ])
    ```

=== "Async"

    ```python
    result = await Article.abulk_create([
        {"title": "One", "body": "...", "category_id": 1},
        {"title": "Two"},
    ])
    ```

```python
result.success_count  # 1
result.failure_count  # 1
result.has_errors     # True
result.succeeded      # [<Article: One>]

failure = result.failed[0]
failure.index   # 1
failure.code    # "validation_error"
failure.fields  # {"body": ["Field required"], "category_id": ["Field required"]}
```

Each item is validated on its own, so an invalid item becomes a failure and
the valid ones are still saved.

Bulk update takes a dict with the primary key, or a `(target, data)` pair.
The target is an instance or a primary key:

=== "Sync"

    ```python
    result = Article.bulk_update([
        {"id": 1, "title": "New title"},
        (article, {"body": "New body"}),
        (3, {"title": "Third"}),
    ])
    ```

=== "Async"

    ```python
    result = await Article.abulk_update([
        {"id": 1, "title": "New title"},
        (article, {"body": "New body"}),
        (3, {"title": "Third"}),
    ])
    ```

Bulk destroy takes instances or primary keys. `succeeded` holds the deleted
primary keys:

=== "Sync"

    ```python
    result = Article.bulk_destroy([article, 2, 99])
    result.succeeded  # [1, 2]
    ```

=== "Async"

    ```python
    result = await Article.abulk_destroy([article, 2, 99])
    result.succeeded  # [1, 2]
    ```

| Method | Items | `succeeded` |
| --- | --- | --- |
| `bulk_create` / `abulk_create` | Dicts or `create_schema` instances | Created instances |
| `bulk_update` / `abulk_update` | Dicts with the primary key, or `(target, data)` pairs | Updated instances |
| `bulk_destroy` / `abulk_destroy` | Instances or primary keys | Deleted primary keys |

All of them accept `request=` to apply `queryset_request`.

### BulkResult and BulkFailure

Import them for type hints:

```python
from ninja_aio.types import BulkFailure, BulkResult
```

| `BulkResult` | What it holds |
| --- | --- |
| `succeeded` | The results of the items that worked |
| `failed` | A list of `BulkFailure` |
| `has_errors` | `True` when at least one item failed |
| `success_count` | `len(succeeded)` |
| `failure_count` | `len(failed)` |

| `BulkFailure` | What it holds |
| --- | --- |
| `index` | The position of the item in your list |
| `code` | A short code, like `"validation_error"` or `"not_found"` |
| `message` | A readable message |
| `fields` | Errors by field, like `{"body": ["Field required"]}` |
| `pk` | The primary key of the item, for update and destroy |
| `error` | The error as the HTTP response shows it, like `{"article": "not found"}` |

## See also

- [Viewsets](viewsets.md)
- [Python CRUD](python-crud.md)
- [Hooks](hooks.md)
- [Errors](errors.md)
