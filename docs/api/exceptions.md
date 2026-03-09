# :material-alert-circle: Exceptions

Django Ninja AIO CRUD provides a structured exception hierarchy for consistent error handling across all API endpoints.

---

## :material-format-list-bulleted: Overview

All framework exceptions inherit from `BaseException` and carry a serializable error payload and an HTTP status code. Exception handlers registered on the `NinjaAIO` instance automatically convert them into JSON responses.

```python
from ninja_aio.exceptions import (
    BaseException,
    SerializeError,
    AuthError,
    NotFoundError,
    PydanticValidationError,
)
```

---

## :material-code-braces: Exception Classes

### `BaseException`

Base class for all framework exceptions.

```python
class BaseException(Exception):
    error: str | dict = ""
    status_code: int = 400
```

**Constructor:**

```python
BaseException(
    error: str | dict = None,
    status_code: int | None = None,
    details: str | None = None,
)
```

| Parameter     | Type            | Description |
|---------------|-----------------|-------------|
| `error`       | `str \| dict`   | Error payload. Strings are wrapped under the `"error"` key; dicts are used directly. |
| `status_code` | `int \| None`   | HTTP status code. Defaults to `400`. |
| `details`     | `str \| None`   | Optional detail message merged into the error dict under `"details"`. |

**Example:**

```python
# String error
exc = BaseException("Something went wrong", 400)
print(exc.error)  # {"error": "Something went wrong"}

# Dict error with details
exc = BaseException({"field": "invalid"}, details="must be positive")
print(exc.error)  # {"field": "invalid", "details": "must be positive"}
```

---

### `SerializeError`

Raised when serialization of request or response payloads fails. Inherits directly from `BaseException` with the same interface.

```python
raise SerializeError("Invalid base64 encoding", 400)
```

---

### `AuthError`

Raised when authentication or authorization fails. Inherits from `BaseException`.

```python
raise AuthError("Unauthorized", 401)
```

---

### `NotFoundError`

Raised when a requested model instance cannot be found. Always returns HTTP 404.

```python
class NotFoundError(BaseException):
    status_code = 404
    error = "not found"
    use_verbose_name = getattr(
        settings, "NINJA_AIO_NOT_FOUND_ERROR_USE_VERBOSE_NAMES", True
    )
```

**Constructor:**

```python
NotFoundError(model: Model, details=None)
```

**Error key format:**

By default the error key is the model's `verbose_name` with spaces replaced by underscores:

```python
# Model with verbose_name = "blog post"
raise NotFoundError(BlogPost)
# {"blog_post": "not found"}
```

When `NINJA_AIO_NOT_FOUND_ERROR_USE_VERBOSE_NAMES = False` the error key is derived from the model class name converted to `snake_case`:

```python
# settings.py
NINJA_AIO_NOT_FOUND_ERROR_USE_VERBOSE_NAMES = False

raise NotFoundError(BlogPost)
# {"blog_post": "not found"}

raise NotFoundError(TestModelSerializer)
# {"test_model_serializer": "not found"}
```

#### `NINJA_AIO_NOT_FOUND_ERROR_USE_VERBOSE_NAMES`

| Value | Error key source | Example |
|-------|-----------------|---------|
| `True` (default) | `model._meta.verbose_name` with spaces → `_` | `{"blog_post": "not found"}` |
| `False` | `model.__name__` converted to `snake_case` | `{"test_model_serializer": "not found"}` |

Configure in `settings.py`:

```python
# Use snake_case model class name in not-found errors
NINJA_AIO_NOT_FOUND_ERROR_USE_VERBOSE_NAMES = False
```

#### Per-model override with `not_found_name`

For full control over a specific model's error payload, set `not_found_name` directly on `model._meta`. This takes precedence over both `verbose_name` and `NINJA_AIO_NOT_FOUND_ERROR_USE_VERBOSE_NAMES`.

**String value** — wrapped under the `"error"` key:

```python
class BlogPost(Model):
    # logic here
    class Meta:
        not_found_name = "blog_post"

raise NotFoundError(BlogPost)
# {"blog_post": "not found"}
```

**Dict value** — used as the full error payload:

```python
BlogPost._meta.not_found_name = {"blog_post": "not found"}

raise NotFoundError(BlogPost)
# {"blog_post": "not found"}
```

**Resolution order:**

| Priority | Source | Condition |
|---|---|---|
| 1 | `model._meta.not_found_name` | If set |
| 2 | `model._meta.verbose_name` (spaces → `_`) | `use_verbose_name=True` (default) |
| 3 | `snake_case(model.__name__)` | `use_verbose_name=False` |

---

### `PydanticValidationError`

Wraps a Pydantic `ValidationError` into a normalized 400 response.

```python
PydanticValidationError(details=None)
```

Response format:

```json
{
  "error": "Validation Error",
  "details": [...]
}
```

---

## :material-shield-check: Exception Handlers

Exception handlers are automatically registered when using `NinjaAIO`. You can also register them manually:

```python
from ninja_aio.exceptions import set_api_exception_handlers

api = NinjaAIO()
set_api_exception_handlers(api)
```

| Exception type        | Handler                      | Response code |
|-----------------------|------------------------------|---------------|
| `BaseException`       | `_default_error`             | From `exc.status_code` |
| `JoseError`           | `_jose_error`                | `401` |
| `ValidationError`     | `_pydantic_validation_error` | `400` |

---

## :material-code-braces: Complete Example

```python
from ninja_aio.exceptions import NotFoundError, SerializeError

async def get_article(request, pk: int):
    try:
        article = await Article.objects.aget(pk=pk)
    except Article.DoesNotExist:
        raise NotFoundError(Article)  # {"article": "not found"}, 404

    return article


async def create_article(request, data):
    try:
        payload, customs = await util.parse_input_data(request, data)
    except SerializeError as e:
        # Already handled by NinjaAIO exception handlers
        raise

    return await Article.objects.acreate(**payload)
```

---

## :material-bookshelf: See Also

<div class="grid cards" markdown>

-   :material-cog-sync:{ .lg .middle } **ModelUtil**

    ---

    [:octicons-arrow-right-24: Error handling in CRUD operations](models/model_util.md)

-   :material-shield-lock:{ .lg .middle } **Authentication**

    ---

    [:octicons-arrow-right-24: JWT & AsyncJwtBearer](authentication.md)

</div>
