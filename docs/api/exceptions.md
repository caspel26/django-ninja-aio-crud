---
type: reference
title: Exceptions
description: Lookup page for the exception classes, their response bodies and the handlers NinjaAIO registers.
---

# Exceptions

Exceptions you can raise from views, hooks and permission methods. The API turns
them into JSON responses. For how to use them, see [Errors](../guides/errors.md).

```python
from ninja_aio.exceptions import (
    BaseException,
    SerializeError,
    AuthError,
    NotFoundError,
    MultipleObjectsError,
    ForbiddenError,
    PydanticValidationError,
    OperationValidationError,
)
```

## Classes

| Class | Constructor | Default status | `code` |
| --- | --- | --- | --- |
| `BaseException` | `(error=None, status_code=None, details=None)` | `400` | `"operation_error"` |
| `SerializeError` | `(error=None, status_code=None, details=None)` | `400` | `"serialization_error"` |
| `AuthError` | `(error=None, status_code=None, details=None)` | `401` | `"authentication_error"` |
| `NotFoundError` | `(model, details=None)` | `404` | `"not_found"` |
| `MultipleObjectsError` | `(model, details=None)` | `400` | `"multiple_objects"` |
| `ForbiddenError` | `(error=None, details=None)` | `403` | `"forbidden"` |
| `PydanticValidationError` | `(details=None)` | `400` | `"validation_error"` |
| `OperationValidationError` | `(exc)` | `400` | `"validation_error"` |

All classes subclass `BaseException`. `OperationValidationError` subclasses
`PydanticValidationError`.

## Constructor parameters

| Parameter | Type | Description |
| --- | --- | --- |
| `error` | `str \| dict \| None` | A string becomes `{"error": "..."}`. A dict is the body as it is. `None` uses the class `error` attribute |
| `status_code` | `int \| None` | HTTP status. `None` uses the class default |
| `details` | any | Added to the body under `"details"` when truthy |
| `model` | model class | `NotFoundError` and `MultipleObjectsError` only. The model of the lookup |
| `exc` | `pydantic.ValidationError` | `OperationValidationError` only. The error to wrap |

## Attributes

| Attribute | Type | Description |
| --- | --- | --- |
| `error` | `dict` | The response body |
| `status_code` | `int` | HTTP status |
| `status` | `int` | Read-only alias of `status_code` |
| `code` | `str` | Stable error code, set per class |
| `message` | `str` | `error["error"]`, or the first value of the body. Also the exception text |
| `field_errors` | `dict[str, list[str]]` | Every body key except `error` and `details`, with its value as a one-item list |

`details` is not an attribute. Read it with `exc.error.get("details")`.

## Response bodies

| Raised as | Status | Body |
| --- | --- | --- |
| `BaseException("boom")` | `400` | `{"error": "boom"}` |
| `SerializeError({"title": "taken"}, 409)` | `409` | `{"title": "taken"}` |
| `AuthError("bad token", details="expired")` | `401` | `{"error": "bad token", "details": "expired"}` |
| `NotFoundError(Article)` | `404` | `{"article": "not found"}` |
| `MultipleObjectsError(Article)` | `400` | `{"article": "multiple objects match the lookup"}` |
| `ForbiddenError()` | `403` | `{"error": "forbidden"}` |
| `ForbiddenError(details="Only staff")` | `403` | `{"error": "forbidden", "details": "Only staff"}` |
| `PydanticValidationError([...])` | `400` | `{"error": "Validation Error", "details": [...]}` |

`OperationValidationError` has the same body as `PydanticValidationError`. The
details are the pydantic errors without the input values. Its `field_errors`
maps each dotted `loc`, like `"title"`, to its messages.

### `NotFoundError` key

The key is the model `verbose_name` with spaces replaced by underscores. With
`NINJA_AIO_NOT_FOUND_ERROR_USE_VERBOSE_NAMES = False` it is the class name in
snake case (`BlogPost` -> `blog_post`). The default is `True`.

To set the message yourself, add `not_found_name` to a `NinjaAIOMeta` inner
class on the model:

```python title="blog/models.py"
class Article(ModelSerializer):
    class NinjaAIOMeta:
        not_found_name = "article missing"
```

The body is then `{"error": "article missing"}`.

## Handlers registered by `NinjaAIO`

| Exception | Status | Body |
| --- | --- | --- |
| `ninja_aio.exceptions.BaseException` and subclasses | `exc.status_code` | `exc.error` |
| `pydantic.ValidationError` | `400` | `{"error": "Validation Error", "details": [...]}` |
| `joserfc.errors.JoseError` | `401` | `{"error": "<jose error>", "details": "<description>"}`. `details` only when the error has a description |
| `django.db.IntegrityError` | `409` | `{"error": "conflict", "details": "The request violates a database constraint."}` |

Register your own handler with `@api.exception_handler(...)` to replace one.

## See also

- [Errors](../guides/errors.md)
- [Permissions](../guides/permissions.md)
- [Settings](settings.md)
