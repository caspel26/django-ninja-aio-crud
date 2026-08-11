"""Describe registered APIViewSets/APIViews as MCP tool specs.

No business logic lives here — it only reads what was already built during
registration:

- ``APIViewSet``: ``_operations``, schemas, ``_action_config`` (CRUD, bulk,
  and ``@action``/``@on`` custom endpoints).
- ``APIView``: the underlying django-ninja ``Router.path_operations``, for
  arbitrary hand-registered endpoints (e.g. ``self.router.post(...)``) that
  have no schema/serializer plumbing to introspect.

Both are turned into JSON-Schema-shaped tool definitions. Invocation lives in
``ninja_aio.mcp.invoke``.
"""

from __future__ import annotations

import inspect
import typing
from dataclasses import dataclass, field
from typing import Any, Callable, Literal, Optional

from ninja import Schema
from ninja.operation import Operation

from ninja_aio.decorators.actions import ActionConfig
from ninja_aio.views import APIView, APIViewSet

CRUD_DESCRIPTIONS = {
    "create": "Create a new {model}.",
    "list": "List {model_plural}, optionally filtered.",
    "retrieve": "Retrieve a single {model} by primary key.",
    "update": "Partially update a {model} by primary key.",
    "delete": "Delete a {model} by primary key.",
}
BULK_DESCRIPTIONS = {
    "bulk_create": "Create multiple {model_plural} in one call.",
    "bulk_update": "Update multiple {model_plural} in one call.",
    "bulk_delete": "Delete multiple {model_plural} by primary key.",
}
_JSON_TYPE_MAP = {str: "string", int: "integer", float: "number", bool: "boolean"}
ToolKind = Literal["crud", "bulk", "action", "router"]


@dataclass
class ToolSpec:
    """Describes one MCP tool generated from a single viewset/view operation."""

    name: str
    description: str
    input_schema: dict
    operation: str
    kind: ToolKind
    owner: APIViewSet | APIView
    detail: bool = False
    action_params: dict[str, dict] = field(default_factory=dict)
    view_func: Optional[Callable] = None


# --- shared helpers ---------------------------------------------------------


def _unwrap_annotation(annotation: Any) -> Any:
    """Unwrap django-ninja's ``Annotated`` param markers (``Path[X]``, ``Query[X]``, ...)."""
    if typing.get_origin(annotation) is typing.Annotated:
        args = typing.get_args(annotation)
        return args[0] if args else annotation
    return annotation


def _is_schema(annotation: Any) -> bool:
    return inspect.isclass(annotation) and issubclass(annotation, Schema)


def _json_type(annotation: Any) -> str:
    return _JSON_TYPE_MAP.get(annotation, "string")


def _pk_field(viewset: APIViewSet) -> dict:
    pk_type = _json_type(viewset.model_util.pk_field_type)
    return {"pk": {"type": pk_type, "description": "Primary key."}}


def _schema_properties(schema: Optional[type[Schema]]) -> dict:
    if schema is None:
        return {}
    return schema.model_json_schema().get("properties", {})


def _json_schema(properties: dict, required: list[str]) -> dict:
    return {"type": "object", "properties": properties, "required": required}


def _format_description(templates: dict[str, str], operation: str, viewset: APIViewSet) -> str:
    return templates[operation].format(
        model=viewset.model_verbose_name,
        model_plural=viewset.model_verbose_name_plural,
    )


def _describe_params(
    method: Callable, reserved: set[str]
) -> tuple[dict, list[str], dict[str, dict]]:
    """Build (properties, required, action_params) from a callable's signature.

    Schema-typed parameters become a nested object property (the caller sends
    that parameter's fields as a sub-object); everything else becomes a
    top-level primitive property. Either shape is required unless the
    parameter has a default.
    """
    properties: dict = {}
    required: list[str] = []
    action_params: dict[str, dict] = {}
    for pname, param in inspect.signature(method).parameters.items():
        if pname in reserved:
            continue
        annotation = _unwrap_annotation(param.annotation)
        if _is_schema(annotation):
            properties[pname] = {
                "type": "object",
                "properties": _schema_properties(annotation),
            }
            action_params[pname] = {"schema": annotation}
        else:
            properties[pname] = {"type": _json_type(annotation)}
            action_params[pname] = {"schema": None}
        if param.default is inspect.Parameter.empty:
            required.append(pname)
    return properties, required, action_params


# --- CRUD --------------------------------------------------------------------


def _create_schema(viewset: APIViewSet) -> tuple[dict, list[str]]:
    properties = _schema_properties(viewset.schema_in)
    return properties, list(properties)


def _list_schema(viewset: APIViewSet) -> tuple[dict, list[str]]:
    return _schema_properties(viewset.filters_schema), []


def _retrieve_or_delete_schema(viewset: APIViewSet) -> tuple[dict, list[str]]:
    return _pk_field(viewset), ["pk"]


def _update_schema(viewset: APIViewSet) -> tuple[dict, list[str]]:
    properties = {**_pk_field(viewset), **_schema_properties(viewset.schema_update)}
    return properties, ["pk"]


_CRUD_SCHEMA_BUILDERS: dict[str, Callable[[APIViewSet], tuple[dict, list[str]]]] = {
    "create": _create_schema,
    "list": _list_schema,
    "retrieve": _retrieve_or_delete_schema,
    "update": _update_schema,
    "delete": _retrieve_or_delete_schema,
}


def _crud_tool_specs(viewset: APIViewSet) -> list[ToolSpec]:
    model_name = viewset.model.__name__.lower()
    specs = []
    for operation in viewset._operations:
        builder = _CRUD_SCHEMA_BUILDERS.get(operation)
        if builder is None:
            continue
        properties, required = builder(viewset)
        specs.append(
            ToolSpec(
                name=f"{model_name}_{operation}",
                description=_format_description(CRUD_DESCRIPTIONS, operation, viewset),
                input_schema=_json_schema(properties, required),
                operation=operation,
                kind="crud",
                owner=viewset,
                detail=operation in ("retrieve", "update", "delete"),
            )
        )
    return specs


# --- Bulk ----------------------------------------------------------------------


def _bulk_create_schema(viewset: APIViewSet) -> dict:
    item_schema = {"type": "object", "properties": _schema_properties(viewset.schema_in)}
    return {"items": {"type": "array", "items": item_schema}}


def _bulk_update_schema(viewset: APIViewSet) -> dict:
    item_schema = {
        "type": "object",
        "properties": _schema_properties(viewset.bulk_update_schema),
    }
    return {"items": {"type": "array", "items": item_schema}}


def _bulk_delete_schema(viewset: APIViewSet) -> dict:
    pk_type = _json_type(viewset.model_util.pk_field_type)
    return {"ids": {"type": "array", "items": {"type": pk_type}}}


_BULK_SCHEMA_BUILDERS: dict[str, Callable[[APIViewSet], dict]] = {
    "bulk_create": _bulk_create_schema,
    "bulk_update": _bulk_update_schema,
    "bulk_delete": _bulk_delete_schema,
}


def _bulk_tool_specs(viewset: APIViewSet) -> list[ToolSpec]:
    model_name = viewset.model.__name__.lower()
    specs = []
    for operation in viewset._operations:
        builder = _BULK_SCHEMA_BUILDERS.get(operation)
        if builder is None:
            continue
        properties = builder(viewset)
        specs.append(
            ToolSpec(
                name=f"{model_name}_{operation}",
                description=_format_description(BULK_DESCRIPTIONS, operation, viewset),
                input_schema=_json_schema(properties, list(properties)),
                operation=operation,
                kind="bulk",
                owner=viewset,
            )
        )
    return specs


# --- Custom @action/@on -------------------------------------------------------


def _action_schema(
    viewset: APIViewSet, method: Callable, config: ActionConfig, reserved: set[str]
) -> tuple[dict, list[str], dict[str, dict]]:
    properties: dict = {}
    required: list[str] = []
    action_params: dict[str, dict] = {}
    if config.detail:
        properties.update(_pk_field(viewset))
        required.append("pk")
    if not config.prefetch_object:
        # @on-shorthand handlers only ever accept `pk` (the object is
        # pre-fetched internally) — only plain @action methods forward
        # their extra parameters straight through to the caller.
        extra_properties, extra_required, action_params = _describe_params(method, reserved)
        properties.update(extra_properties)
        required.extend(extra_required)
    return properties, required, action_params


def _action_tool_specs(viewset: APIViewSet) -> list[ToolSpec]:
    model_name = viewset.model.__name__.lower()
    reserved = {"self", "request", "pk", viewset.model_util.model_pk_name}
    known_ops = set(CRUD_DESCRIPTIONS) | set(BULK_DESCRIPTIONS)
    specs = []
    for name in dir(type(viewset)):
        if name in known_ops or name not in viewset._operations:
            continue
        method = getattr(type(viewset), name)
        config = method._action_config
        properties, required, action_params = _action_schema(viewset, method, config, reserved)
        specs.append(
            ToolSpec(
                name=f"{model_name}_{name}",
                description=config.description
                or config.summary
                or f"Custom action '{name}' on {viewset.model_verbose_name}.",
                input_schema=_json_schema(properties, required),
                operation=name,
                kind="action",
                owner=viewset,
                detail=config.detail,
                action_params=action_params,
            )
        )
    return specs


def describe_viewset(viewset: APIViewSet) -> list[ToolSpec]:
    """Build the full list of MCP tool specs exposed by a single viewset."""
    return [
        *_crud_tool_specs(viewset),
        *_bulk_tool_specs(viewset),
        *_action_tool_specs(viewset),
    ]


# --- Plain APIView (router-registered) endpoints ------------------------------


def _router_tool_spec(view: APIView, view_name: str, operation: Operation) -> Optional[ToolSpec]:
    if not operation.include_in_schema:
        return None
    properties, required, action_params = _describe_params(
        operation.view_func, reserved={"self", "request"}
    )
    method_verb = operation.methods[0].lower() if operation.methods else "get"
    op_name = getattr(operation.view_func, "__name__", "operation")
    return ToolSpec(
        name=f"{view_name}_{op_name}_{method_verb}",
        description=operation.description
        or operation.summary
        or f"{method_verb.upper()} {operation.path}",
        input_schema=_json_schema(properties, required),
        operation=op_name,
        kind="router",
        owner=view,
        action_params=action_params,
        view_func=operation.view_func,
    )


def describe_api_view(view: APIView) -> list[ToolSpec]:
    """Build the MCP tool specs exposed by a plain ``APIView``.

    Unlike ``APIViewSet``, a plain view has no schema/serializer plumbing to
    read — endpoints are hand-registered on ``self.router`` inside
    ``views()``. Tools are built straight from django-ninja's own
    ``Router.path_operations``, which retains the exact function each
    endpoint was registered with (``Operation.view_func``) — the same
    function invoked over HTTP, called here directly the same way
    ``@action``-decorated viewset methods are (see ``invoke.py``).
    """
    view_name = type(view).__name__.lower()
    return [
        spec
        for path_view in view.router.path_operations.values()
        for operation in path_view.operations
        if (spec := _router_tool_spec(view, view_name, operation)) is not None
    ]
