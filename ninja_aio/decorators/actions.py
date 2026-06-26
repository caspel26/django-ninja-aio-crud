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
    prefetch_object: bool = False


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
    Shorthand decorator for detail actions that pre-fetches the model instance.

    The decorated method receives ``(self, request, obj)`` instead of
    ``(self, request, pk)``. ``on_before_operation`` and
    ``on_before_object_operation`` are called automatically before the
    handler runs, eliminating the common boilerplate found in ``@action``
    detail handlers.

    Parameters
    ----------
    action_name : str
        URL path segment for this action (e.g. ``"publish"``).
        Defaults to the ``url_path`` when not overridden.
    methods : list[str], optional
        HTTP methods. Defaults to ``["post"]``.
    url_path : str, optional
        Override the URL path segment. Defaults to *action_name*.
    auth : Any
        Auth override. ``NOT_SET`` inherits from the viewset's per-verb auth.
    response : Any
        Response schema. ``NOT_SET`` lets Django Ninja infer it.

    Example
    -------
    ::

        class ArticleAPI(APIViewSet):
            model = Article

            @on("publish", methods=["post"], response={200: ArticleReadSchema})
            async def publish(self, request, obj):
                obj.status = "published"
                await obj.asave(update_fields=["status"])
                return Status(200, await self.model_util.read_s(self.schema_out, request, obj))

    .. note::
        The handler **must** be ``async``.
    """

    def decorator(func):
        func._action_config = ActionConfig(
            detail=True,
            methods=methods or ["post"],
            url_path=url_path if url_path is not None else action_name,
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
            prefetch_object=True,
        )
        return func

    return decorator
