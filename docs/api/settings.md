---
type: reference
title: Settings
description: Lookup page for every Django setting the framework reads.
---

# Settings

Django settings you can add to `settings.py` to change the framework behavior.
All of them are optional unless you use the feature that needs them.

## django-ninja-aio-crud settings

| Setting | Type | Default | Description |
| --- | --- | --- | --- |
| `NINJA_AIO_APPEND_SLASH` | `bool` | `True` | Adds a trailing slash to the create, update, delete and bulk paths. `False` removes it. See [Viewsets](../guides/viewsets.md) |
| `NINJA_AIO_NOT_FOUND_ERROR_USE_VERBOSE_NAMES` | `bool` | `True` | Uses the model `verbose_name` as the `404` body key. `False` uses the class name in snake case. See [Errors](../guides/errors.md) |
| `NINJA_AIO_RAISE_SERIALIZATION_WARNINGS` | `bool` | `True` | Warns when a `Serializer` read schema lists a reverse relation that is not in `relations_serializers` or `relations_as_id`. See [Logging](../guides/logging.md) |
| `NINJA_AIO_ORJSON_RENDERER_OPTION` | `int \| None` | `None` | orjson option flags for the default renderer, like `orjson.OPT_INDENT_2`. See [ORJSONRenderer](renderers/orjson_renderer.md) |
| `NINJA_AIO_MCP_API` | `str \| None` | `None` | Dotted path to your `NinjaAIO` instance, used by `manage.py mcp_server` when you pass none. See [MCP](../guides/mcp.md) |
| `JWT_PRIVATE_KEY` | `RSAKey \| ECKey \| OctKey \| None` | `None` | Default signing key for `encode_jwt`. See [Authentication](../guides/authentication.md) |
| `JWT_PUBLIC_KEY` | `RSAKey \| ECKey \| OctKey \| None` | `None` | Default verification key for `decode_jwt` and the JWT auth classes. See [Authentication](../guides/authentication.md) |
| `JWT_ISSUER` | `str \| None` | `None` | Default `iss` claim for `encode_jwt`. See [Authentication](../guides/authentication.md) |
| `JWT_AUDIENCE` | `str \| None` | `None` | Default `aud` claim for `encode_jwt`. See [Authentication](../guides/authentication.md) |
| `JWT_ALGORITHM` | `str \| None` | `None` | Default signature algorithm for `encode_jwt`, `decode_jwt` and the JWT auth classes. `None` means `"RS256"` |

`set_jwt_cookie` also reads Django's `DEBUG`: when you do not pass `secure`, the
cookie is HTTPS only if `DEBUG` is `False`. See
[Cookie authentication](../guides/cookie-authentication.md).

```python title="settings.py"
NINJA_AIO_APPEND_SLASH = False
NINJA_AIO_MCP_API = "blog.api.api"
```

## Django Ninja settings

These Django Ninja settings change the list endpoints of your viewsets.

| Setting | Type | Default | Description |
| --- | --- | --- | --- |
| `NINJA_PAGINATION_PER_PAGE` | `int` | `100` | Page size when the client sends no `page_size` |
| `NINJA_MAX_PER_PAGE_SIZE` | `int` | `100` | Largest `page_size` a client can ask for. Bigger values are capped |
| `NINJA_PAGINATION_MAX_LIMIT` | `int` | no limit | Largest `limit` with `LimitOffsetPagination`. Bigger values fail validation |

See [Pagination](../guides/pagination.md).

## See also

- [Exceptions](exceptions.md)
- [Authentication](authentication.md)
- [Pagination](../guides/pagination.md)
