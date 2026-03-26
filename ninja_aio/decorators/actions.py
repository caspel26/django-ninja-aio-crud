import logging
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

from ninja.constants import NOT_SET, NOT_SET_TYPE
from ninja.throttling import BaseThrottle

logger = logging.getLogger("ninja_aio.decorators")


@dataclass
class ActionConfig:
    """Configuration for an @action-decorated viewset method."""

    detail: bool
    methods: list[str] = field(default_factory=lambda: ["get"])
    url_path: str | None = None
    url_name: str | None = None
    auth: Any = NOT_SET
    response: Any = NOT_SET
    summary: str | None = None
    description: str | None = None
    tags: list[str] | None = None
    deprecated: bool | None = None
    decorators: list[Callable] | None = None
    throttle: BaseThrottle | list[BaseThrottle] | NOT_SET_TYPE = NOT_SET
    include_in_schema: bool = True
    openapi_extra: dict[str, Any] | None = None


def action(
    detail: bool,
    *,
    methods: list[str] | None = None,
    url_path: str | None = None,
    url_name: str | None = None,
    auth: Any = NOT_SET,
    response: Any = NOT_SET,
    summary: str | None = None,
    description: str | None = None,
    tags: list[str] | None = None,
    deprecated: bool | None = None,
    decorators: list[Callable] | None = None,
    throttle: BaseThrottle | list[BaseThrottle] | NOT_SET_TYPE = NOT_SET,
    include_in_schema: bool = True,
    openapi_extra: Optional[dict[str, Any]] = None,
):
    """
    Decorator that marks a viewset method as a custom action endpoint.

    The method is not registered immediately — the viewset discovers it
    during initialization and registers it on the router with the
    provided configuration.

    Parameters
    ----------
    detail : bool
        If True, the action operates on a single instance (URL includes {pk}).
        If False, the action operates on the collection (no pk in URL).
    methods : list[str], optional
        HTTP methods to register. Defaults to ["get"].
    url_path : str, optional
        Custom URL path segment. Used exactly as provided (no automatic
        slash appending). Defaults to the method name with underscores
        replaced by hyphens.
    url_name : str, optional
        Django URL name for reverse resolution.
    auth : Any
        Auth override. NOT_SET inherits from the viewset's per-verb auth.
    response : Any
        Response schema. NOT_SET lets Django Ninja infer it.
    summary : str, optional
        OpenAPI summary. Auto-generated if None.
    description : str, optional
        OpenAPI description.
    tags : list[str], optional
        OpenAPI tags. None inherits from viewset router tags.
    deprecated : bool, optional
        Mark as deprecated in OpenAPI.
    decorators : list[Callable], optional
        Additional decorators to apply to the handler.
    throttle : BaseThrottle | list[BaseThrottle]
        Throttle configuration. NOT_SET inherits from viewset.
    include_in_schema : bool
        Whether to include in OpenAPI schema. Defaults to True.
    openapi_extra : dict, optional
        Additional OpenAPI metadata.
    """

    def decorator(func):
        func._action_config = ActionConfig(
            detail=detail,
            methods=methods or ["get"],
            url_path=url_path,
            url_name=url_name,
            auth=auth,
            response=response,
            summary=summary,
            description=description,
            tags=tags,
            deprecated=deprecated,
            decorators=decorators,
            throttle=throttle,
            include_in_schema=include_in_schema,
            openapi_extra=openapi_extra,
        )
        return func

    return decorator


@dataclass
class OnConfig:
    """Marker for @on-decorated methods — triggers object fetch + hooks."""

    action_name: str


def on(
    action_name: str,
    *,
    methods: list[str] | None = None,
    url_path: str | None = None,
    url_name: str | None = None,
    auth: Any = NOT_SET,
    response: Any = NOT_SET,
    summary: str | None = None,
    description: str | None = None,
    tags: list[str] | None = None,
    deprecated: bool | None = None,
    decorators: list[Callable] | None = None,
    throttle: BaseThrottle | list[BaseThrottle] | NOT_SET_TYPE = NOT_SET,
    include_in_schema: bool = True,
    openapi_extra: Optional[dict[str, Any]] = None,
):
    """
    Decorator for detail actions with automatic object fetching and hooks.

    The handler receives ``(self, request, obj)`` instead of ``(self, request, pk)``.
    Before calling the handler, the framework:

    1. Calls ``on_before_operation(request, action_name)``
    2. Fetches the object via ``model_util.get_object(request, pk)``
    3. Calls ``on_before_object_operation(request, action_name, obj)``

    Parameters
    ----------
    action_name : str
        Operation name used for hooks and default URL path.
    methods : list[str], optional
        HTTP methods. Defaults to ``["post"]``.
    url_path : str, optional
        Custom URL segment. Defaults to action_name with ``_`` as ``-``.

    All other parameters are identical to :func:`action`.

    Example::

        @on("publish")
        async def publish(self, request, obj):
            obj.status = "published"
            await obj.asave()
            return Status(200, {"message": "published"})
    """

    def decorator(func):
        func._action_config = ActionConfig(
            detail=True,
            methods=methods or ["post"],
            url_path=url_path or action_name.replace("_", "-"),
            url_name=url_name,
            auth=auth,
            response=response,
            summary=summary,
            description=description,
            tags=tags,
            deprecated=deprecated,
            decorators=decorators,
            throttle=throttle,
            include_in_schema=include_in_schema,
            openapi_extra=openapi_extra,
        )
        func._on_config = OnConfig(action_name=action_name)
        return func

    return decorator
