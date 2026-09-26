---
type: guide
title: Installation
description: Install django-ninja-aio-crud and check the supported Python and Django Ninja versions.
---

# Installation

Install the package from PyPI. Django Ninja comes with it.

=== "pip"

    ```bash
    pip install django-ninja-aio-crud
    ```

=== "uv"

    ```bash
    uv add django-ninja-aio-crud
    ```

=== "poetry"

    ```bash
    poetry add django-ninja-aio-crud
    ```

## Requirements

| Package | Supported versions |
| --- | --- |
| Python | 3.10 to 3.14 |
| Django Ninja | 1.3 to 1.7 |
| Django | Any version supported by your Django Ninja release |

You don't need to add anything to `INSTALLED_APPS`. Add `"ninja_aio"` only if
you want the [`mcp_server`](../mcp.md) management command.

## Optional extras

```bash
pip install "django-ninja-aio-crud[mcp]"   # AI agent integration (MCP)
```

## Next step

Build your first API in the [quick start](quick_start.md).
