"""Library MCP over stdio, with an explicit member's authorization context."""
import asyncio
import os

import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "library_project.settings")
django.setup()

from django.test.client import AsyncRequestFactory  # noqa: E402
from ninja_aio.mcp import run_mcp_server  # noqa: E402
from library.api import api  # noqa: E402
from library.models import Member  # noqa: E402


async def member_request_factory(username):
    member = await Member.objects.select_related("user").filter(user__username=username, user__is_active=True).afirst()
    if member is None:
        raise ValueError(f"No active library member {username!r}. Run seed_library or set LIBRARY_MCP_USERNAME.")

    def factory():
        request = AsyncRequestFactory().get("/mcp/")
        request.user = member.user
        request.auth = member
        return request

    return factory


async def main():
    factory = await member_request_factory(os.environ.get("LIBRARY_MCP_USERNAME", "reader"))
    await run_mcp_server(api, name="library", request_factory=factory)


if __name__ == "__main__":
    asyncio.run(main())
