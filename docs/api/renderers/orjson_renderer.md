# :material-code-json: ORJSON Renderer

This package uses an internal ORJSON-based renderer that automatically handles JSON serialization with support for special types.

## :material-cog: Configuration

Configure serialization options via Django settings:

```python
# settings.py
import orjson

# Single option
NINJA_AIO_ORJSON_RENDERER_OPTION = orjson.OPT_INDENT_2

# Multiple options (bitwise OR)
NINJA_AIO_ORJSON_RENDERER_OPTION = (
    orjson.OPT_INDENT_2 | orjson.OPT_NON_STR_KEYS
)
```

Notes:

- The value is an orjson option bitmask (e.g., `orjson.OPT_INDENT_2`, `orjson.OPT_NON_STR_KEYS`), and you can combine multiple options using `|`.
- If not set, the default `orjson.dumps` options are used.

---

## :material-arrow-right-bold: HttpResponse Passthrough

The renderer automatically detects when you return a Django `HttpResponse` (or any `HttpResponseBase` subclass) and passes it through without JSON serialization. This allows you to return custom responses with different content types.

```python
from django.http import HttpResponse

@api.get("/public-key")
def get_public_key(request):
    return HttpResponse(
        settings.JWT_PUBLIC_KEY.as_pem(),
        content_type="application/x-pem-file",
        status=200,
    )
```

This also works with `StreamingHttpResponse` for large files:

```python
from django.http import StreamingHttpResponse

@api.get("/download")
def download_file(request):
    return StreamingHttpResponse(
        file_iterator(),
        content_type="application/octet-stream",
    )
```

!!! note
    When returning an `HttpResponse` directly, the response bypasses the renderer entirely. Set the `status` parameter on the `HttpResponse` itself rather than using a tuple return like `return 200, HttpResponse(...)`.

---

## :material-arrow-right-circle: See Also

<div class="grid cards" markdown>

-   :material-view-grid:{ .lg .middle } **APIViewSet**

    ---

    Auto-generated CRUD endpoints using orjson rendering

    [:octicons-arrow-right-24: Learn more](../views/api_view_set.md)

-   :material-file-document-edit:{ .lg .middle } **ModelSerializer**

    ---

    Schema generation for fast JSON serialization

    [:octicons-arrow-right-24: Learn more](../models/model_serializer.md)

-   :material-rocket-launch:{ .lg .middle } **Quick Start**

    ---

    Get up and running in minutes

    [:octicons-arrow-right-24: Get started](../../getting_started/quick_start.md)

</div>
