# :material-text-box-search: Logging

Django Ninja AIO uses Python's standard `logging` module to provide structured observability across all framework operations. Logging is **disabled by default** and has **zero runtime overhead** until you explicitly enable it.

---

## :material-lightning-bolt: Quick Start

Add this to your Django `settings.py` to enable all framework logs:

```python
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

---

## :material-format-list-bulleted: Available Loggers

Django Ninja AIO exposes the following loggers, organized by module:

| Logger | Module | What it logs |
|---|---|---|
| `ninja_aio.models` | `ninja_aio/models/utils.py` | CRUD operations (create, update, delete), FK resolution, binary field decoding, query optimizations, relation cache hits/misses |
| `ninja_aio.views` | `ninja_aio/views/api.py` | ViewSet initialization, CRUD view registration, filter field validation |
| `ninja_aio.auth` | `ninja_aio/auth.py` | JWT authentication success/failure, token encoding/decoding |
| `ninja_aio.helpers` | `ninja_aio/helpers/api.py` | M2M operations (add/remove results, validation errors, view registration) |
| `ninja_aio.factory` | `ninja_aio/factory/operations.py` | API endpoint registration via `@api_get`, `@api_post`, etc. |
| `ninja_aio.exceptions` | `ninja_aio/exceptions.py` | Exception handler invocations (BaseException, PydanticValidationError, JoseError) |
| `ninja_aio.decorators` | `ninja_aio/decorators/views.py` | Atomic transaction entry |

All loggers are children of the `ninja_aio` parent logger, so configuring `ninja_aio` captures everything.

---

## :material-tune: Selective Logging

You can enable logging for specific modules only. For example, to log only CRUD operations and authentication:

```python
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
            "level": "DEBUG",
        },
        "ninja_aio.auth": {
            "handlers": ["console"],
            "level": "DEBUG",
        },
    },
}
```

---

## :material-filter: Log Levels

The framework uses two log levels:

| Level | Used for |
|---|---|
| `INFO` | Write operations: create, update, delete, M2M add/remove results |
| `DEBUG` | Detailed internals: FK resolution, cache hits, query optimizations, view registration, auth flow |

Set the level to `INFO` for production monitoring or `DEBUG` for development/troubleshooting.

---

## :material-file-document: Production Example

A production-ready configuration that logs `INFO` and above to a file:

```python
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

This will produce logs like:

```
2026-03-12 10:30:01 INFO ninja_aio.models Creating Book
2026-03-12 10:30:01 INFO ninja_aio.models Updating Book (pk=42)
2026-03-12 10:30:02 INFO ninja_aio.models Deleting Book (pk=42)
2026-03-12 10:30:03 INFO ninja_aio.helpers M2M manage tags: 3 succeeded, 1 errors
```

---

## :material-cancel: Disabling Logging

Logging is disabled by default. If you've enabled it and want to turn it off:

```python
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "loggers": {
        "ninja_aio": {
            "handlers": [],
            "level": "CRITICAL",
            "propagate": False,
        },
    },
}
```

Or simply remove the `ninja_aio` logger entry from your `LOGGING` configuration.

---

## :material-console: Example Output (DEBUG)

With `DEBUG` level enabled, you'll see the full request lifecycle:

```
DEBUG ninja_aio.views APIViewSet initialized for Book at /books
DEBUG ninja_aio.views Registered create view for Book
DEBUG ninja_aio.views Registered list view for Book
DEBUG ninja_aio.views Registered retrieve view for Book
DEBUG ninja_aio.views Registered update view for Book
DEBUG ninja_aio.views Registered delete view for Book
DEBUG ninja_aio.auth JWT authentication successful
INFO  ninja_aio.models Creating Book
DEBUG ninja_aio.models Resolving FK 'author' -> Author (pk=5) for Book
DEBUG ninja_aio.models Created Book (pk=42)
DEBUG ninja_aio.models Select related cache hit for Book (is_for=read)
DEBUG ninja_aio.models Reverse relations cache hit for Book (is_for=read)
```
