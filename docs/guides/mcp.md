---
type: guide
title: AI agents (MCP)
description: Expose your viewsets as MCP tools so AI agents can list, create and change your data.
---

# AI agents (MCP)

Run an MCP (Model Context Protocol) server that turns your viewsets into
tools. AI clients like Claude Desktop or VS Code can then call your CRUD
endpoints and custom actions.

## Set up the server

<div class="nac-steps" markdown>

### Install the extra

```bash
pip install "django-ninja-aio-crud[mcp]"
```

### Add the app

Add `"ninja_aio"` to `INSTALLED_APPS` so Django finds the `mcp_server`
command:

```python title="settings.py"
INSTALLED_APPS = [
    # ...
    "ninja_aio",
    "blog",
]
```

### Point it at your API

Set the dotted path to your `NinjaAIO` instance:

```python title="settings.py"
NINJA_AIO_MCP_API = "blog.api.api"
```

### Run it

```bash
python manage.py mcp_server
```

</div>

The server talks over stdio. Your MCP client starts it, so you don't keep it
running yourself.

## Command options

```bash
python manage.py mcp_server blog.api.api --name blog-api
```

| Option | What it does |
| --- | --- |
| `api` | Dotted path to the `NinjaAIO` instance. Defaults to `NINJA_AIO_MCP_API` |
| `--name` | The server name shown to clients. Defaults to `django-ninja-aio-crud` |

Without the path and without the setting, the command stops with an error.

## Know which tools you get

Every viewset registered with `@api.viewset` becomes a set of tools. Tool
names are the model class name in lower case, plus the operation:

| Tool | Input |
| --- | --- |
| `article_list` | The viewset `query_params` filters. Returns the first page |
| `article_create` | The `create` fields |
| `article_retrieve` | `pk` |
| `article_update` | `pk` and the `update` fields |
| `article_delete` | `pk` |
| `article_bulk_create` | `items`: a list of `create` objects |
| `article_bulk_update` | `items`: a list of `update` objects, each with its `id` |
| `article_bulk_delete` | `ids`: a list of primary keys |
| `article_<method>` | Custom actions. `pk` for detail actions, plus the method parameters |

A tool exists only when its endpoint exists. `disable`, missing schemas and
`bulk_operations` apply to tools too. See [Viewsets](viewsets.md).

```python title="blog/api.py"
@api.viewset(model=Article, prefix="articles")
class ArticleViewSet(APIViewSet):
    bulk_operations = ["create", "delete"]

    @on("publish")
    async def publish(self, request, obj):
        obj.is_published = True
        await obj.asave()
        return {"published": obj.pk}
```

This gives `article_list`, `article_create`, `article_retrieve`,
`article_update`, `article_delete`, `article_bulk_create`,
`article_bulk_delete` and `article_publish`. An `@on` action takes only
`pk`.

The tool description of an action is its `description`, or its `summary`.
See [Custom actions](custom-actions.md).

Endpoints of an `APIView` become tools too. Endpoints with
`include_in_schema=False` are skipped.

!!! note

    Viewsets registered on a `NinjaAIORouter` are not found by the server.
    Register them with `@api.viewset` to expose them as tools, or pass them
    yourself as shown below.

## Choose what to expose

Write a small script and pass the viewsets and views you want:

```python title="mcp_server.py"
import asyncio
import os

import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "mysite.settings")
django.setup()

from ninja_aio.mcp import run_mcp_server

from blog.api import api, ArticleViewSet

if __name__ == "__main__":
    asyncio.run(run_mcp_server(api, viewsets=[ArticleViewSet], views=[]))
```

```bash
python mcp_server.py
```

| Argument | What it does |
| --- | --- |
| `viewsets` | The viewsets to expose. Defaults to all `@api.viewset` viewsets |
| `views` | The views to expose. Defaults to all `@api.view` views |
| `name` | The server name shown to clients |
| `request_factory` | A function that builds the request passed to each tool call |

This script also works without `"ninja_aio"` in `INSTALLED_APPS`.

## Handle authentication

Tool calls skip the `auth` of your API and viewsets. Each call gets a request
with an anonymous `request.user` and no `request.auth`.

Your viewset hooks and permission checks still run. Use `request_factory` to
give tool calls an identity your checks accept:

```python title="mcp_server.py"
from django.contrib.auth import get_user_model
from django.test.client import AsyncRequestFactory

agent = get_user_model().objects.get(username="mcp-agent")


def mcp_request():
    request = AsyncRequestFactory().get("/mcp/")
    request.user = agent
    request.auth = agent
    return request


if __name__ == "__main__":
    asyncio.run(run_mcp_server(api, request_factory=mcp_request))
```

The factory is a plain function called for each tool call. Load the user
before the server starts, not inside the factory.

With `PermissionViewSetMixin`, a denied check returns a `403` error to the
client. See [Permissions](permissions.md).

!!! warning

    Anyone who can start the MCP server can do what your hooks allow. Protect
    it like a Django shell.

## Connect a client

Use absolute paths, because the client starts the server from its own
folder.

=== "Claude Desktop"

    ```json title="claude_desktop_config.json"
    {
      "mcpServers": {
        "blog": {
          "command": "/path/to/project/.venv/bin/python",
          "args": ["/path/to/project/manage.py", "mcp_server"]
        }
      }
    }
    ```

=== "VS Code"

    ```json title=".vscode/mcp.json"
    {
      "servers": {
        "blog": {
          "type": "stdio",
          "command": "/path/to/project/.venv/bin/python",
          "args": ["/path/to/project/manage.py", "mcp_server"]
        }
      }
    }
    ```

Errors like a missing object or invalid input come back to the client as a
tool error with the same message as the HTTP API.

## See also

- [Viewsets](viewsets.md)
- [Custom actions](custom-actions.md)
- [Permissions](permissions.md)
- [APIViewSet reference](../api/views/api_view_set.md)
