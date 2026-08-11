"""MCP (Model Context Protocol) integration for django-ninja-aio-crud.

Turns registered ``APIViewSet`` instances into MCP tools (list/create/
retrieve/update/delete, bulk operations, and ``@action``/``@on`` custom
endpoints) so an MCP client (Claude Code, Claude Desktop, or any other MCP
client) can operate on a project's models directly.

Requires the ``mcp`` extra: ``pip install "django-ninja-aio-crud[mcp]"``.
"""

from .introspect import ToolSpec, describe_api_view, describe_viewset
from .invoke import ToolInvocationError, invoke_tool
from .server import NinjaAIOMCPServer, run_mcp_server

__all__ = [
    "NinjaAIOMCPServer",
    "run_mcp_server",
    "describe_viewset",
    "describe_api_view",
    "ToolSpec",
    "invoke_tool",
    "ToolInvocationError",
]
