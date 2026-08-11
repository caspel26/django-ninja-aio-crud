"""MCP server exposing registered APIViewSets and APIViews as MCP tools over stdio.

Usage::

    # my_project/mcp_server.py
    import django
    django.setup()

    import asyncio
    from myapp.api import api  # your NinjaAIO() instance with @api.viewset(...) registered
    from ninja_aio.mcp import run_mcp_server

    if __name__ == "__main__":
        asyncio.run(run_mcp_server(api))

Then point an MCP client (e.g. Claude Code's ``.mcp.json``) at
``python my_project/mcp_server.py`` with ``"type": "stdio"``.

.. warning::
    Tool calls bypass django-ninja's ``auth=`` wiring — see
    ``ninja_aio.mcp.context`` and the README's "AI Agent Integration (MCP)"
    section before exposing this to untrusted clients.
"""

from __future__ import annotations

import logging
from typing import Iterable, Optional

from mcp import types
from mcp.server import Server
from mcp.server.stdio import stdio_server

from .context import RequestFactory
from .introspect import ToolSpec, describe_api_view, describe_viewset
from .invoke import invoke_tool

logger = logging.getLogger("ninja_aio.mcp")


class NinjaAIOMCPServer:
    """Exposes a set of registered ``APIViewSet``/``APIView`` instances as MCP tools."""

    def __init__(
        self,
        api,
        *,
        viewsets: Optional[Iterable] = None,
        views: Optional[Iterable] = None,
        name: str = "django-ninja-aio-crud",
        request_factory: Optional[RequestFactory] = None,
    ) -> None:
        self.api = api
        self.viewsets = list(viewsets) if viewsets is not None else list(api._viewsets)
        self.views = list(views) if views is not None else list(api._views)
        self.request_factory = request_factory
        self.server = Server(name)
        self._tools: dict[str, ToolSpec] = {}
        self._build_tools()
        self._register_handlers()

    def _build_tools(self) -> None:
        for viewset in self.viewsets:
            for spec in describe_viewset(viewset):
                self._tools[spec.name] = spec
        for view in self.views:
            for spec in describe_api_view(view):
                self._tools[spec.name] = spec
        logger.debug(f"Registered {len(self._tools)} MCP tool(s)")

    def _register_handlers(self) -> None:
        @self.server.list_tools()
        async def list_tools() -> list[types.Tool]:
            return [
                types.Tool(
                    name=spec.name,
                    description=spec.description,
                    inputSchema=spec.input_schema,
                )
                for spec in self._tools.values()
            ]

        @self.server.call_tool()
        async def call_tool(name: str, arguments: dict):
            spec = self._tools.get(name)
            if spec is None:
                raise ValueError(f"Unknown tool: {name}")
            return await invoke_tool(spec, arguments, self.request_factory)

    async def run_stdio(self) -> None:
        """Run the MCP server over stdio until the client disconnects."""
        async with stdio_server() as (read_stream, write_stream):
            await self.server.run(
                read_stream,
                write_stream,
                self.server.create_initialization_options(),
            )


async def run_mcp_server(api, **kwargs) -> None:
    """Build a :class:`NinjaAIOMCPServer` for *api* and run it over stdio."""
    await NinjaAIOMCPServer(api, **kwargs).run_stdio()
