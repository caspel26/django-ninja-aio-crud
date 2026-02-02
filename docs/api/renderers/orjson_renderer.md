# :material-code-json: ORJSON Renderer

Django Ninja AIO uses an internal ORJSON-based renderer for fast JSON serialization. It is enabled automatically when you use `NinjaAIO` — no configuration required.

<div class="grid cards" markdown>

-   :material-lightning-bolt:{ .lg .middle } **Fast**

    ---

    ORJSON is significantly faster than Python's built-in `json` module

-   :material-cog:{ .lg .middle } **Configurable**

    ---

    Customize serialization options via Django settings

-   :material-arrow-right-bold:{ .lg .middle } **Passthrough**

    ---

    `HttpResponse` objects bypass the renderer automatically

</div>

---

## :material-cog: Configuration

Configure serialization options via Django settings:

=== "Single option"

    ```python
    # settings.py
    import orjson

    NINJA_AIO_ORJSON_RENDERER_OPTION = orjson.OPT_INDENT_2
    ```

=== "Multiple options"

    ```python
    # settings.py
    import orjson

    NINJA_AIO_ORJSON_RENDERER_OPTION = (
        orjson.OPT_INDENT_2 | orjson.OPT_NON_STR_KEYS
    )
    ```

=== "No configuration"

    ```python
    # settings.py
    # If NINJA_AIO_ORJSON_RENDERER_OPTION is not set,
    # default orjson.dumps options are used (compact output).
    ```

### Available options

| Option | Description |
|---|---|
| `OPT_INDENT_2` | Pretty-print with 2-space indentation |
| `OPT_NON_STR_KEYS` | Allow non-string dict keys |
| `OPT_SORT_KEYS` | Sort dictionary keys in output |
| `OPT_NAIVE_UTC` | Serialize naive datetimes as UTC |
| `OPT_UTC_Z` | Use `Z` suffix instead of `+00:00` for UTC |
| `OPT_OMIT_MICROSECONDS` | Omit microseconds from datetime output |

!!! tip
    Combine options with the `|` (bitwise OR) operator. See the [orjson documentation](https://github.com/ijl/orjson#option) for the full list.

---

## :material-arrow-right-bold: HttpResponse Passthrough

The renderer automatically detects when you return a Django `HttpResponse` (or any `HttpResponseBase` subclass) and passes it through without JSON serialization.

=== "Custom content type"

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

=== "Streaming response"

    ```python
    from django.http import StreamingHttpResponse

    @api.get("/download")
    def download_file(request):
        return StreamingHttpResponse(
            file_iterator(),
            content_type="application/octet-stream",
        )
    ```

!!! warning "Important"
    When returning an `HttpResponse` directly, set the `status` parameter on the `HttpResponse` itself. Do not use a tuple return like `return 200, HttpResponse(...)` — the response bypasses the renderer entirely.

---

## :material-frequently-asked-questions: Supported Types

ORJSON natively handles types that Python's `json` module cannot:

| Type | Behavior |
|---|---|
| `datetime`, `date`, `time` | ISO 8601 format |
| `UUID` | String representation |
| `Decimal` | Serialized as number |
| `numpy` arrays | Serialized as lists |
| `dataclass` instances | Serialized as dicts |
| `bytes` | Not supported — convert to string first |

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
