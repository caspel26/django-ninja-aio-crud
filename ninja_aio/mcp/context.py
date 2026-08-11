"""Synthetic request construction for MCP-invoked operations.

MCP tool calls happen outside Django's HTTP request/response cycle, so a
plain ``HttpRequest`` has to be built for each invocation. django-ninja-aio-crud's
view hooks (``on_before_operation``, ``query_params_handler``, ...) all expect a
real ``HttpRequest``-like object, so one is built here with Django's own
``AsyncRequestFactory`` — the same helper the test suite uses for the same
reason (see ``tests/generics/request.py``).

Tool calls bypass django-ninja's ``auth=`` wiring entirely: that check happens
in django-ninja's ``Operation.run``, not inside the view handler itself, and
MCP tool invocation calls the handler directly. Pass a ``request_factory`` to
:class:`~ninja_aio.mcp.server.NinjaAIOMCPServer` to attach ``request.user`` (or
any other attribute your ``on_before_operation``/``on_before_object_operation``
hooks rely on) so authorization can still be enforced from within the viewset.
"""

from typing import Callable, Optional

from django.contrib.auth.models import AnonymousUser
from django.http import HttpRequest
from django.test.client import AsyncRequestFactory

RequestFactory = Callable[[], HttpRequest]


def default_request_factory() -> HttpRequest:
    """Build a bare HttpRequest carrying an AnonymousUser and no auth context."""
    request = AsyncRequestFactory().get("/mcp/")
    request.user = AnonymousUser()
    return request


def build_request(factory: Optional[RequestFactory] = None) -> HttpRequest:
    """Build the HttpRequest passed to a viewset operation for one tool call."""
    return (factory or default_request_factory)()
