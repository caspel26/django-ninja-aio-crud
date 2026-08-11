"""Dispatch MCP tool calls to the already-registered operation handlers.

CRUD/bulk/action ``ToolSpec``s point at ``owner._operations[spec.operation]``
— the exact async closure django-ninja-aio-crud registered on the router for
that operation (see ``APIViewSet._add_views``/``_set_additional_views``/
``_register_single_action`` in ``ninja_aio/views/api.py``). Router
``ToolSpec``s (plain ``APIView`` endpoints) point at ``spec.view_func``
directly — django-ninja's own ``Operation.view_func`` (see
``ninja_aio.mcp.introspect.describe_api_view``). Either way, calling the
handler directly reuses pagination, filtering, and the
``on_before_operation``/``on_before_object_operation``/
``query_params_handler``/``on_list_queryset`` hooks exactly as the HTTP path
does — only django-ninja's router-level ``auth=`` wiring is not applied (see
``ninja_aio.mcp.context``).

Each operation's arguments are built by a small ``(viewset, arguments) ->
tuple`` function, looked up per ``spec.operation`` — the tables below are the
single place that knows what each registered handler expects to be called
with (see the handler signatures in ``ninja_aio/views/api.py``).
"""

from __future__ import annotations

from typing import Any, Callable, Optional

from ninja.responses import Status
from pydantic import ValidationError

from ninja_aio.exceptions import BaseException as NinjaAIOError
from ninja_aio.views import APIViewSet

from .context import RequestFactory, build_request
from .introspect import ToolSpec


class ToolInvocationError(Exception):
    """Raised when a tool call fails; carries a JSON-serializable error payload."""

    def __init__(self, payload: Any, status_code: int = 400) -> None:
        self.payload = payload
        self.status_code = status_code
        super().__init__(payload)

    def __str__(self) -> str:
        return str(self.payload)


def _kwargs_from_action_params(spec: ToolSpec, arguments: dict) -> dict:
    """Build call kwargs from ``spec.action_params``, parsing Schema-typed ones."""
    kwargs: dict = {}
    for name, param_info in spec.action_params.items():
        if name not in arguments:
            continue
        schema_cls = param_info.get("schema")
        kwargs[name] = schema_cls(**arguments[name]) if schema_cls else arguments[name]
    return kwargs


# --- CRUD argument builders --------------------------------------------------


def _create_args(viewset: APIViewSet, arguments: dict) -> tuple:
    return (viewset.schema_in(**arguments),)


def _list_args(viewset: APIViewSet, arguments: dict) -> tuple:
    filters = viewset.filters_schema(**arguments)
    pagination_input = viewset.pagination_class.Input()
    return filters, pagination_input


def _retrieve_or_delete_args(viewset: APIViewSet, arguments: dict) -> tuple:
    pk_name = viewset.model_util.model_pk_name
    return (viewset.path_schema(**{pk_name: arguments.get("pk")}),)


def _update_args(viewset: APIViewSet, arguments: dict) -> tuple:
    pk_name = viewset.model_util.model_pk_name
    pk = viewset.path_schema(**{pk_name: arguments.pop("pk", None)})
    data = viewset.schema_update(**arguments)
    return data, pk


_CRUD_ARG_BUILDERS: dict[str, Callable[[APIViewSet, dict], tuple]] = {
    "create": _create_args,
    "list": _list_args,
    "retrieve": _retrieve_or_delete_args,
    "update": _update_args,
    "delete": _retrieve_or_delete_args,
}


async def _invoke_crud(spec: ToolSpec, request, arguments: dict) -> Any:
    viewset = spec.owner
    handler = viewset._operations[spec.operation]
    args = _CRUD_ARG_BUILDERS[spec.operation](viewset, arguments)
    return await handler(request, *args)


# --- Bulk argument builders ---------------------------------------------------


def _bulk_create_args(viewset: APIViewSet, arguments: dict) -> tuple:
    return ([viewset.schema_in(**item) for item in arguments.get("items", [])],)


def _bulk_update_args(viewset: APIViewSet, arguments: dict) -> tuple:
    return ([viewset.bulk_update_schema(**item) for item in arguments.get("items", [])],)


def _bulk_delete_args(viewset: APIViewSet, arguments: dict) -> tuple:
    return (viewset.bulk_delete_schema(ids=arguments.get("ids", [])),)


_BULK_ARG_BUILDERS: dict[str, Callable[[APIViewSet, dict], tuple]] = {
    "bulk_create": _bulk_create_args,
    "bulk_update": _bulk_update_args,
    "bulk_delete": _bulk_delete_args,
}


async def _invoke_bulk(spec: ToolSpec, request, arguments: dict) -> Any:
    viewset = spec.owner
    handler = viewset._operations[spec.operation]
    args = _BULK_ARG_BUILDERS[spec.operation](viewset, arguments)
    return await handler(request, *args)


# --- Custom @action/@on and plain APIView endpoints ---------------------------


async def _invoke_action(spec: ToolSpec, request, arguments: dict) -> Any:
    viewset = spec.owner
    handler = viewset._operations[spec.operation]
    kwargs = _kwargs_from_action_params(spec, arguments)

    if spec.detail:
        pk_name = viewset.model_util.model_pk_name
        kwargs[pk_name] = arguments.get("pk")

    return await handler(request, **kwargs)


async def _invoke_router(spec: ToolSpec, request, arguments: dict) -> Any:
    kwargs = _kwargs_from_action_params(spec, arguments)
    return await spec.view_func(request, **kwargs)


_INVOKERS = {
    "crud": _invoke_crud,
    "bulk": _invoke_bulk,
    "action": _invoke_action,
    "router": _invoke_router,
}


async def invoke_tool(
    spec: ToolSpec,
    arguments: Optional[dict],
    request_factory: Optional[RequestFactory] = None,
) -> Any:
    """Invoke the operation described by *spec* with *arguments*.

    Returns a JSON-serializable payload on success. Raises
    :class:`ToolInvocationError` (carrying a structured, already-serializable
    error payload) on validation failures or framework errors
    (``ninja_aio.exceptions.BaseException`` subclasses) instead of letting
    the underlying Django/pydantic exception propagate raw.
    """
    request = build_request(request_factory)
    arguments = dict(arguments or {})

    try:
        result = await _INVOKERS[spec.kind](spec, request, arguments)
    except NinjaAIOError as exc:
        raise ToolInvocationError(exc.error, exc.status_code) from exc
    except ValidationError as exc:
        raise ToolInvocationError(
            {"error": "Validation Error", "details": exc.errors(include_input=False)},
            400,
        ) from exc

    value = result.value if isinstance(result, Status) else result
    return {"success": True} if value is None else value
