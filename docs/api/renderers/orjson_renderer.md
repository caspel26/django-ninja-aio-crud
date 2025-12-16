# ORJSON renderer option

This package uses an internal ORJSON-based renderer. Configure serialization options via Django settings:

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
