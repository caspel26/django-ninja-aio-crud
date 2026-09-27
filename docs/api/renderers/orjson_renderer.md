---
type: reference
title: JSON renderer and parser
description: Lookup page for the orjson renderer and parser that NinjaAIO uses by default.
---

# JSON renderer and parser

`NinjaAIO` renders responses with `ORJSONRenderer` and parses JSON request
bodies with `ORJSONParser`. Both use [orjson](https://github.com/ijl/orjson).
You do not need to configure them.

```python
from ninja_aio.renders import ORJSONRenderer
from ninja_aio.parsers import ORJSONParser
```

## ORJSONRenderer

A Django Ninja `BaseRenderer` with `media_type = "application/json"`.

| Value in the response | Rendered as |
| --- | --- |
| `bytes` | Base64 string |
| `IPv4Address`, `IPv6Address`, pydantic `AnyUrl` | String |
| Django `HttpResponse` returned by the view | Sent as is |
| Anything else | orjson output |

| Attribute | Type | Default | Description |
| --- | --- | --- | --- |
| `option` | `int \| None` | `NINJA_AIO_ORJSON_RENDERER_OPTION` | orjson option flags passed to `orjson.dumps` |

## ORJSONParser

A Django Ninja `Parser` that reads the JSON body with `orjson.loads`. Form data
and files are parsed as in Django Ninja.

## Renderer options

Set `NINJA_AIO_ORJSON_RENDERER_OPTION` to any orjson option. Combine flags with
`|`:

```python title="settings.py"
import orjson

NINJA_AIO_ORJSON_RENDERER_OPTION = orjson.OPT_INDENT_2 | orjson.OPT_SORT_KEYS
```

The value is read once, when the framework is imported. See
[Settings](../settings.md).

## Use a different renderer or parser

Pass an instance to `NinjaAIO`:

```python title="blog/api.py"
from ninja.parser import Parser
from ninja.renderers import JSONRenderer

from ninja_aio import NinjaAIO

api = NinjaAIO(title="Blog API", renderer=JSONRenderer(), parser=Parser())
```

| Argument | Type | Default | Description |
| --- | --- | --- | --- |
| `renderer` | `BaseRenderer \| None` | `None` | `None` uses `ORJSONRenderer()` |
| `parser` | `Parser \| None` | `None` | `None` uses `ORJSONParser()` |

## See also

- [Settings](../settings.md)
- [Viewsets](../../guides/viewsets.md)
- [Errors](../../guides/errors.md)
