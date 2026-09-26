---
type: guide
title: Errors
description: Read the error responses your API returns, raise your own errors and add custom handlers.
---

# Errors

This page shows the status and JSON body of each error your API returns, and
how to raise and handle your own errors.

## Read the error responses

| Status | When | Body |
| --- | --- | --- |
| `400` | The body is not valid JSON | `{"detail": "Cannot parse request body"}` |
| `401` | Authentication fails | `{"detail": "Unauthorized"}` |
| `403` | A permission check returns `False` | `{"error": "forbidden", "details": "..."}` |
| `404` | The object or a related object does not exist | `{"article": "not found"}` |
| `422` | The body, path or query does not match the schema | `{"detail": [...]}` |
| `500` | Your code raises an exception nobody handles | Django's error response |

### Validation errors

A body that does not match the create or update schema returns `422` with one
entry per problem:

```json
{
  "detail": [
    {"type": "string_type", "loc": ["body", "data", "title"], "msg": "Input should be a valid string"},
    {"type": "missing", "loc": ["body", "data", "body"], "msg": "Field required"}
  ]
}
```

A wrong path value, like `GET /api/articles/abc`, returns `422` with
`"loc": ["path", "id"]`.

### Not found

`GET`, `PATCH` and `DELETE` on a missing id return `404`. The key is the model
name:

```json
{"article": "not found"}
```

Creating an article with a `category_id` that does not exist returns the same
shape for the related model: `{"category": "not found"}`.

### Empty updates

By default a `PATCH` with an empty body is accepted. Set
`require_update_fields = True` on the viewset to reject it:

```python
@api.viewset(model=Article)
class ArticleViewSet(APIViewSet):
    require_update_fields = True
```

An empty body then returns `400`:

```json
{"error": "No fields provided for update."}
```

### Database errors

Database errors, like a duplicate value in a unique field, are not converted.
They return `500`. Add a handler to turn them into a clean response, see
[Handle your own exceptions](#handle-your-own-exceptions).

## Raise an error from your code

Raise these exceptions from custom actions, viewset hooks, permission methods
and serializer hooks. The API turns them into a JSON response.

```python title="blog/api.py"
from ninja_aio import APIViewSet, on
from ninja_aio.exceptions import ForbiddenError, SerializeError

from .auth import JWTAuth
from .models import Article


@api.viewset(model=Article)
class ArticleViewSet(APIViewSet):
    auth = [JWTAuth()]

    @on("publish")
    async def publish(self, request, obj):
        if obj.is_published:
            raise SerializeError({"is_published": "already published"}, 409)
        if not request.auth.is_staff:
            raise ForbiddenError(details="Only staff can publish")
        obj.is_published = True
        await obj.asave(update_fields=["is_published"])
        return {"published": True}
```

The first error returns `409` with `{"is_published": "already published"}`.
The second returns `403` with
`{"error": "forbidden", "details": "Only staff can publish"}`.

| Exception | Arguments | Default status |
| --- | --- | --- |
| `SerializeError` | `error`, `status_code=None`, `details=None` | `400` |
| `NotFoundError` | `model`, `details=None` | `404` |
| `ForbiddenError` | `error=None`, `details=None` | `403` |
| `AuthError` | `error`, `status_code=None`, `details=None` | `400` |
| `BaseException` | `error`, `status_code=None`, `details=None` | `400` |

All of them live in `ninja_aio.exceptions`. The body depends on `error`:

- A string becomes `{"error": "..."}`.
- A dict is returned as it is, like `{"title": "is taken"}`.
- `details`, when given, is added under the `"details"` key.

`raise NotFoundError(Article)` returns `{"article": "not found"}` with `404`.

You can also raise Django Ninja's `HttpError`:

```python
from ninja.errors import HttpError

raise HttpError(409, "Title already used")
```

This returns `409` with `{"detail": "Title already used"}`.

## Create your own error class

Subclass `BaseException` and set `status_code`:

```python title="blog/errors.py"
from ninja_aio.exceptions import BaseException


class PaymentRequired(BaseException):
    status_code = 402
    code = "payment_required"
```

```python
raise PaymentRequired("Upgrade your plan")
```

The response is `402` with `{"error": "Upgrade your plan"}`. Every instance has
`error` (the body), `status_code` and `code`.

## Change the not found key

The `404` key comes from the model's `verbose_name`, with spaces replaced by
underscores. Set this in `settings.py` to use the class name in snake case
instead:

```python title="settings.py"
NINJA_AIO_NOT_FOUND_ERROR_USE_VERBOSE_NAMES = False
```

| Model | `True` (default) | `False` |
| --- | --- | --- |
| `class BlogPost`, no `verbose_name` | `blog_post` | `blog_post` |
| `class Article`, `verbose_name = "blog post"` | `blog_post` | `article` |

## Document errors in OpenAPI

Every generated CRUD endpoint documents `400`, `401`, `403` and `404` with the
viewset's `error_schema`. The default is `GenericMessageSchema`, an object with
string values. Set your own schema on the viewset:

```python title="blog/api.py"
from ninja import Schema


class ErrorSchema(Schema):
    error: str
    details: str | None = None


@api.viewset(model=Article)
class ArticleViewSet(APIViewSet):
    error_schema = ErrorSchema
```

This changes only the documentation, not the responses. Custom actions document
only the responses you pass with `response=`.

## Handle your own exceptions

Register a handler on the API with `@api.exception_handler`. It works for any
exception class, including Django ones:

```python title="blog/api.py"
from django.db import IntegrityError

from ninja_aio import NinjaAIO

api = NinjaAIO(title="Blog API")


@api.exception_handler(IntegrityError)
def integrity_error(request, exc):
    return api.create_response(request, {"error": "conflict"}, status=409)
```

A duplicate category name now returns `409` with `{"error": "conflict"}`
instead of `500`.

## Unhandled errors

Any other exception returns `500`. With `DEBUG = False`, Django handles it and
returns its standard error page. With `DEBUG = True`, the response is the
traceback as plain text.

## See also

- [Permissions](permissions.md)
- [Custom actions](custom-actions.md)
- [Hooks](hooks.md)
- [Validation](validation.md)
- [Exceptions reference](../api/exceptions.md)
