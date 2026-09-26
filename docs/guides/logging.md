---
type: guide
title: Logging
description: See what the framework does by turning on its loggers in your Django settings.
---

# Logging

The framework writes its messages with Python's `logging` module, under the
`ninja_aio` logger. This page shows how to turn them on and what each logger
tells you.

## Turn on the logs

Add a `ninja_aio` logger to `LOGGING`:

```python title="settings.py"
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
        },
    },
    "loggers": {
        "ninja_aio": {
            "handlers": ["console"],
            "level": "DEBUG",
        },
    },
}
```

Every framework logger is a child of `ninja_aio`, so this one entry shows all
of them. Without a `ninja_aio` entry you see nothing: all messages are `DEBUG`
or `INFO`, below the default `WARNING` level.

## Know the loggers

| Logger | What it logs |
| --- | --- |
| `ninja_aio.models` | Create, update and delete of objects, object lookups, foreign key resolution, `select_related` and `prefetch_related` choices, and `@on_create` / `@on_update` / `@on_delete` hooks being fired |
| `ninja_aio.views` | Viewset setup, each registered endpoint and custom action, and filter fields that do not exist on the model |
| `ninja_aio.factory` | The method and path of each custom action endpoint |
| `ninja_aio.helpers` | Many-to-many endpoints: registration, related objects not found, and add/remove results |
| `ninja_aio.auth` | JWT authentication: missing token, failure with its reason, success, and token encoding and decoding |
| `ninja_aio.exceptions` | Each error turned into an error response, with its status code |
| `ninja_aio.decorators` | Entering the transaction of an async write endpoint |
| `ninja_aio.mcp` | How many MCP tools were registered |

## Know the levels

The framework logs at two levels:

| Level | Messages |
| --- | --- |
| `INFO` | `Creating Article`, `Updating Article (pk=42)`, `Deleting Article (pk=42)`, and many-to-many results like `M2M manage tags: 3 succeeded, 1 errors` |
| `DEBUG` | Everything else in the table above |

Errors are not logged as `WARNING` or `ERROR`. The client gets them as error
responses, and `ninja_aio.exceptions` logs them at `DEBUG`.

!!! note

    Create, update and delete messages come from async code: async viewsets
    and `acreate()`, `aupdate()`, `adestroy()`. Sync viewsets and the sync
    methods do not log them.

With `DEBUG` on, one async create looks like this:

```text
DEBUG ninja_aio.auth JWT authentication successful
DEBUG ninja_aio.decorators Entering atomic transaction for ...
INFO ninja_aio.models Creating Article
DEBUG ninja_aio.models Resolving FK 'category' -> Category (pk=1) for Article
DEBUG ninja_aio.models Created Article (pk=42)
```

## Log only some parts

Configure single loggers instead of `ninja_aio`. This shows object changes and
authentication only:

```python title="settings.py"
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
        },
    },
    "loggers": {
        "ninja_aio.models": {
            "handlers": ["console"],
            "level": "INFO",
        },
        "ninja_aio.auth": {
            "handlers": ["console"],
            "level": "DEBUG",
        },
    },
}
```

## Write changes to a file

Use `INFO` to keep only the write messages:

```python title="settings.py"
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "{asctime} {levelname} {name} {message}",
            "style": "{",
        },
    },
    "handlers": {
        "file": {
            "class": "logging.FileHandler",
            "filename": "ninja_aio.log",
            "formatter": "verbose",
        },
    },
    "loggers": {
        "ninja_aio": {
            "handlers": ["file"],
            "level": "INFO",
        },
    },
}
```

```text title="ninja_aio.log"
2026-03-12 10:30:01,120 INFO ninja_aio.models Creating Article
2026-03-12 10:30:01,480 INFO ninja_aio.models Updating Article (pk=42)
2026-03-12 10:30:02,015 INFO ninja_aio.models Deleting Article (pk=42)
```

## Silence the reverse relation warning

A `Serializer` whose `read` fields list a reverse relation, like `articles` on
a `Category` serializer, needs an entry in `relations_serializers` or
`relations_as_id`. Without one, Python shows a `UserWarning` when the schema
is built. Turn it off with a setting:

```python title="settings.py"
NINJA_AIO_RAISE_SERIALIZATION_WARNINGS = False
```

The default is `True`. This is a Python warning, not a log message, so
`LOGGING` does not change it. See [Relations](relations.md).

## See also

- [Errors](errors.md)
- [Authentication](authentication.md)
- [Hooks](hooks.md)
- [Deployment](../deployment.md)
