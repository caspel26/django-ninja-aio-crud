"""Expose the library API to AI agents over MCP (stdio).

    cd examples/library && python -m library.mcp_server
"""

import asyncio
import os

import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "library_project.settings")
django.setup()

from ninja_aio.mcp import run_mcp_server  # noqa: E402  (needs django.setup())

from library.api import api  # noqa: E402

if __name__ == "__main__":
    asyncio.run(run_mcp_server(api, name="library"))
