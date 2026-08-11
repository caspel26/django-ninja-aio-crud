# :material-robot: AI Agent Integration (MCP)

This page documents `ninja_aio.mcp` — turning registered `APIViewSet`s and `APIView`s into [MCP](https://modelcontextprotocol.io) (Model Context Protocol) tools, so any MCP client can list and call CRUD operations, bulk operations, custom `@action`/`@on` endpoints, and plain custom endpoints directly — without you writing any glue code.

## :material-lightbulb-on-outline: Why This Is Useful

Without MCP, "let an AI agent operate on your app's data" means one of: giving it raw database/shell access (unsafe, no validation, no business logic), building a bespoke chat-command layer on top of your API (a whole extra thing to design and maintain), or having a human relay every request through your admin UI. None of that scales past a demo.

MCP tools solve this the same way your REST API solves it for human-facing frontends — except the "frontend" is a model doing multi-step reasoning:

- **Natural-language operations on real data.** "Find all unpublished books by this author and publish them" becomes a handful of `list`/`publish` tool calls the agent plans and executes itself — no custom endpoint written for that exact request.
- **Safety for free.** Every call still goes through your model's validation, hooks, and (optionally) authorization checks — see [Auth Caveat](#auth-caveat) — so the agent can't do anything your own serializers/hooks wouldn't already allow a normal request to do.
- **Nothing new to maintain.** Tools are generated from the ViewSets/Views you already wrote. Add a field to a schema or a new `@action`, and the next `tools/list` call reflects it automatically — there's no separate "AI-facing API" to keep in sync.
- **Composable with any MCP client.** Since it's a standard protocol, the same server works with a coding agent, a support-ops assistant, an internal ChatOps bot, or anything else that speaks MCP — you wire it up once.

In short: this turns "build an AI feature into my app" into "point an MCP client at an app I already built."

## :material-information-outline: Overview

- :material-toy-brick-outline: **Zero-config discovery** — every `@api.viewset(...)` and `@api.view(...)` registration is automatically picked up.
- :material-sync: **Real behavior, not a re-implementation** — tool calls invoke the exact same registered handler functions the HTTP layer uses (pagination, filters, `on_before_operation`/`on_before_object_operation`/`query_params_handler`/`on_list_queryset` hooks all run identically).
- :material-transit-connection-variant: **stdio transport** — the standard way MCP clients launch a local server via a `command`.
- :material-cube-outline: **Everything is covered:** CRUD, bulk operations, `@action`/`@on` custom endpoints, and plain `APIView`-registered endpoints.

!!! info "Requires the `mcp` extra"
    ```sh
    pip install "django-ninja-aio-crud[mcp]"
    ```

---

## :material-play-circle-outline: Running the Server

### Option A: `manage.py mcp_server` (recommended)

Add `"ninja_aio"` to `INSTALLED_APPS`:

```python
INSTALLED_APPS = [
    # ...
    "ninja_aio",
]
```

```sh
python manage.py mcp_server myproject.api.api
```

The argument is a dotted path to a `NinjaAIO()` instance. Set a default in settings to drop it:

```python
# settings.py
NINJA_AIO_MCP_API = "myproject.api.api"
```

```sh
python manage.py mcp_server
```

`--name` overrides the server name advertised to clients:

```sh
python manage.py mcp_server myproject.api.api --name my-project-mcp
```

!!! note "Why an app?"
    `NinjaAIO`, `APIViewSet`, etc. work fine as plain importable classes without `ninja_aio` ever being listed in `INSTALLED_APPS`. Adding it enables two things that rely on Django's app-loading machinery:

    - **`manage.py mcp_server`** — Django only discovers management commands inside installed apps, so this command is invisible until `ninja_aio` is one.
    - **Swagger UI branding via a template file, no Python required** — `BrandedSwagger` looks up `ninja_aio/branded_swagger.html` through Django's app-directories template loader (`get_template(...)`). With `ninja_aio` installed, dropping a same-named template in your own project's `templates/` directory is enough to override it — Django's loader resolution order means your app's copy is found first. Without it, `get_template()` never finds *any* app-provided version of that template (ninja_aio's own bundled one included) and always falls back to reading it straight off disk, so the only way to customize it is subclassing `BrandedSwagger` in Python and pointing at your own file. See [Swagger UI](api/branding.md) for both approaches.

    Neither is required for the CRUD/serialization/auth features this framework is built around — only opt in if you want one of these two things.

### Option B: standalone script

If you'd rather not touch `INSTALLED_APPS`, run it as its own process:

```python
# mcp_server.py
import asyncio
import django
django.setup()

from myproject.api import api  # your NinjaAIO() instance
from ninja_aio.mcp import run_mcp_server

if __name__ == "__main__":
    asyncio.run(run_mcp_server(api))
```

```sh
python mcp_server.py
```

### Connecting an MCP client

Most MCP clients use the same `mcpServers` config shape — point `command`/`args` at whichever option you chose above:

```json
{
  "mcpServers": {
    "myproject": {
      "type": "stdio",
      "command": "python",
      "args": ["manage.py", "mcp_server"]
    }
  }
}
```

Check your specific client's docs for where this config file lives.

---

## :material-hammer-wrench: How Tools Are Generated

`describe_viewset(viewset)` and `describe_api_view(view)` (in `ninja_aio.mcp.introspect`) build one `ToolSpec` per operation. `NinjaAIOMCPServer` calls these for every registered viewset/view and exposes the result as MCP tools.

### ViewSet tools

For an `APIViewSet`, tools are named `<model>_<operation>`:

| Operation | Tool name example | Input |
|---|---|---|
| Create | `book_create` | Fields from the create schema |
| List | `book_list` | Fields from the viewset's `query_params`/filters |
| Retrieve | `book_retrieve` | `pk` |
| Update | `book_update` | `pk` + fields from the update schema |
| Delete | `book_delete` | `pk` |
| Bulk create | `book_bulk_create` | `items`: array of create-schema objects |
| Bulk update | `book_bulk_update` | `items`: array of `{pk, ...update fields}` |
| Bulk delete | `book_bulk_delete` | `ids`: array of primary keys |
| Custom `@action`/`@on` | `book_<method_name>` | `pk` (if `detail=True`) + the method's own extra parameters |

Only operations that are actually registered are exposed — respecting `disable = [...]` on the viewset and whether `bulk_operations` is configured.

```python
@api.viewset(Book)
class BookViewSet(APIViewSet):
    bulk_operations = ["create", "update", "delete"]

    @action(detail=True, methods=["post"], url_path="publish")
    async def publish(self, request, pk):
        book = await self.model_util.get_object(request, pk)
        book.published = True
        await book.asave()
        return Status(200, {"message": "published"})
```

Exposes: `book_create`, `book_list`, `book_retrieve`, `book_update`, `book_delete`, `book_bulk_create`, `book_bulk_update`, `book_bulk_delete`, `book_publish`.

!!! tip "`@on`-shorthand actions"
    `@on`-decorated methods (`(self, request, obj)`) only ever accept `pk` — the object is fetched internally before your handler runs, so there's nothing else for the caller to supply.

### View tools

For a plain `APIView`, tools are named `<viewclass>_<function>_<httpmethod>`, built directly from django-ninja's own `Router.path_operations` — the exact function each endpoint was registered with:

```python
@api.view(prefix="/reports")
class ReportsView(APIView):
    def views(self):
        @self.router.get("/stats", response=StatsSchema)
        async def stats(request):
            return {"total": await Book.objects.acount()}
```

Exposes: `reportsview_stats_get`.

Extra parameters on a view function become tool input fields the same way custom `@action` parameters do — Schema-typed parameters become a nested object, primitives become top-level fields (required unless they have a default). django-ninja's `Path[X]`/`Query[X]` markers are unwrapped to their inner type automatically. Endpoints registered with `include_in_schema=False` are skipped.

---

## :material-eye-outline: What the AI Agent Actually Sees

This walks through the exact protocol messages for the `Book` viewset above, so you can see what an MCP client receives at each step.

### 1. Discovery — `tools/list`

When the client connects, it calls `list_tools()`. The server responds with one [`Tool`](https://modelcontextprotocol.io/docs/concepts/tools) entry per operation — `name`, `description`, and `inputSchema` (a standard JSON Schema object). For `book_create`:

```json
{
  "name": "book_create",
  "description": "Create a new Book.",
  "inputSchema": {
    "type": "object",
    "properties": {
      "title": {"type": "string"},
      "published": {"type": "boolean"}
    },
    "required": ["title", "published"]
  }
}
```

The agent reads this the same way it reads any other tool's schema — no framework-specific knowledge required. `book_publish` (the custom `@action` above) looks like:

```json
{
  "name": "book_publish",
  "description": "POST Publish Book.",
  "inputSchema": {
    "type": "object",
    "properties": {
      "pk": {"type": "integer", "description": "Primary key."}
    },
    "required": ["pk"]
  }
}
```

### 2. Invocation — `tools/call`

The client sends a tool name plus arguments matching that `inputSchema`:

```json
{
  "name": "book_create",
  "arguments": {"title": "Dune", "published": true}
}
```

`invoke_tool` parses the arguments into `BookViewSet.schema_in`, calls the exact same registered `create` handler the HTTP endpoint uses, and the server returns a [`CallToolResult`](https://modelcontextprotocol.io/docs/concepts/tools#tool-result) — the created object, serialized as text content the model reads directly:

```json
{
  "content": [
    {"type": "text", "text": "{\n  \"id\": 1,\n  \"title\": \"Dune\",\n  \"published\": true\n}"}
  ],
  "structuredContent": {"id": 1, "title": "Dune", "published": true},
  "isError": false
}
```

A failure (e.g. `book_retrieve` with an unknown `pk`) comes back as an error result instead of crashing the connection:

```json
{
  "content": [
    {"type": "text", "text": "{'book': 'not found'}"}
  ],
  "isError": true
}
```

### 3. A full turn, end to end

```text
User:  "Add a book called Dune and then mark it published."

Agent: [calls tools/list]                     -> sees book_create, book_publish, ...
Agent: [calls book_create {"title": "Dune", "published": false}]
       <- {"id": 1, "title": "Dune", "published": false}
Agent: [calls book_publish {"pk": 1}]
       <- {"message": "published"}
Agent: "Done — created 'Dune' (id 1) and published it."
```

Nothing here is MCP-server-specific glue: the agent is doing ordinary tool-calling against ordinary JSON Schemas. The only django-ninja-aio-crud-specific piece is that the tools it's calling happen to be your app's real CRUD/action endpoints.

---

## :material-code-braces: Calling Tools Programmatically

Useful for tests or for embedding the dispatch logic elsewhere without spinning up a full stdio server:

```python
from ninja_aio.mcp import describe_viewset, invoke_tool

specs = {s.name: s for s in describe_viewset(book_viewset)}

created = await invoke_tool(specs["book_create"], {"title": "Dune", "published": True})
# created == {"id": 1, "title": "Dune", "published": True}

book = await invoke_tool(specs["book_retrieve"], {"pk": created["id"]})
```

`invoke_tool` raises `ToolInvocationError` (carrying a structured, JSON-serializable `.payload` and `.status_code`) instead of letting framework exceptions propagate raw — e.g. a missing object raises `ToolInvocationError` with `status_code=404` and the same payload `ninja_aio.exceptions.NotFoundError` would produce over HTTP.

---

## :material-shield-alert-outline: Auth Caveat

Tool calls invoke the registered handler function directly — the same function the HTTP router calls — so viewset-level hooks (`on_before_operation`, `on_before_object_operation`, `query_params_handler`, `on_list_queryset`) all run identically to the HTTP path. **django-ninja's router-level `auth=` wiring is not applied**, because that check happens in django-ninja's `Operation.run`, not inside the handler itself.

Use `request_factory` to attach whatever `request.user`/auth context your own `on_before_operation` hooks check:

```python
from django.test.client import AsyncRequestFactory
from ninja_aio.mcp import NinjaAIOMCPServer

def mcp_request_factory():
    request = AsyncRequestFactory().get("/mcp/")
    request.user = get_service_account_user()  # your own resolution logic
    return request

server = NinjaAIOMCPServer(api, request_factory=mcp_request_factory)
```

```python
@api.viewset(Book)
class BookViewSet(APIViewSet):
    async def on_before_operation(self, request, operation: str) -> None:
        if not request.user.has_perm(f"library.{operation}_book"):
            raise ForbiddenError(f"Not allowed to {operation} books")
```

!!! warning "Treat the MCP server as a privileged process"
    Because router-level `auth=` doesn't apply, gate who can run the MCP server process itself (stdio access = full model access, minus what your own hooks enforce) the same way you'd gate a database shell or an admin CLI.

---

## :material-api: `NinjaAIOMCPServer`

```python
NinjaAIOMCPServer(
    api: NinjaAIO,
    *,
    viewsets: Iterable[APIViewSet] | None = None,
    views: Iterable[APIView] | None = None,
    name: str = "django-ninja-aio-crud",
    request_factory: Callable[[], HttpRequest] | None = None,
)
```

| Parameter | Description |
|---|---|
| `api` | Your `NinjaAIO()` instance. |
| `viewsets` | Explicit list of viewset instances. Defaults to `api._viewsets` — every `@api.viewset(...)`-decorated class. |
| `views` | Explicit list of view instances. Defaults to `api._views` — every `@api.view(...)`-decorated class. |
| `name` | Server name advertised to MCP clients during initialization. |
| `request_factory` | Builds the synthetic `HttpRequest` passed to each tool call. See [Auth Caveat](#auth-caveat) above. |

```python
server = NinjaAIOMCPServer(api)          # auto-discovers everything registered via @api.viewset/@api.view
await server.run_stdio()

# or the one-line convenience coroutine:
from ninja_aio.mcp import run_mcp_server
await run_mcp_server(api)

# expose only specific viewsets/views:
server = NinjaAIOMCPServer(api, viewsets=[BookViewSet], views=[])
```

---

## :material-compass: See Also

<div class="grid cards" markdown>

- :material-view-grid: **APIViewSet** — CRUD, bulk operations, custom actions

    [:octicons-arrow-right-24: APIViewSet](api/views/api_view_set.md)

- :material-view-column: **APIView** — Custom non-CRUD endpoints

    [:octicons-arrow-right-24: APIView](api/views/api_view.md)

- :material-lightning-bolt: **Decorators** — `@action`, `@on`, and operation decorators

    [:octicons-arrow-right-24: Decorators](api/views/decorators.md)

</div>
