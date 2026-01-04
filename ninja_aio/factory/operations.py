import asyncio
from typing import (
    Callable,
    Dict,
    List,
    Optional,
    Union,
    Any,
)
import inspect

from ninja.constants import NOT_SET, NOT_SET_TYPE
from ninja.throttling import BaseThrottle
from ninja import Router


class ApiMethodFactory:
    """
    Factory for creating class-bound API method decorators that register endpoints
    on a Ninja Router from instance methods.

    This class enables defining API handlers as instance methods while ensuring
    the resulting callables exposed to Ninja are free of `self`/`cls` in their
    OpenAPI signatures, preventing them from being interpreted as query params.

    Typical usage:
    - Use ApiMethodFactory.make("get" | "post" | "put" | "delete" | ...) to produce
        a decorator that can be applied to an instance method on a view class.
    - When the owning instance (e.g., a subclass of ninja_aio.views.api.API) is
        created, the method is lazily registered on its `router` with the provided
        configuration (path, auth, response, tags, etc.).

    The factory supports both sync and async methods. It wraps the original method
    with a handler whose first argument is `request` (as expected by Ninja),
    internally binding `self` from the instance so you can still write methods
    naturally.

    Attributes:
    - method_name: The HTTP method name used to select the corresponding Router
        adder (e.g., "get", "post", etc.).

    __init__(method_name: str)
            Initialize the factory for a specific HTTP method.

            Parameters:
            - method_name: The name of the Router method to call (e.g., "get", "post").
                This determines which endpoint registration function is used on the router.

    _build_handler(view_instance, original)
            Build a callable that Ninja can use as the endpoint handler, correctly
            binding `self` and presenting a `request`-first signature.

            Behavior:
            - If the original method is async, return an async wrapper that awaits it.
            - If the original method is sync, return a sync wrapper that calls it.
            - The wrapper passes (view_instance, request, *args, **kwargs) to the
                original method, ensuring instance binding while exposing a clean handler
                to Ninja.

            Parameters:
            - view_instance: The object instance that owns the router and the method.
            - original: The original instance method to be wrapped.

            Returns:
            - A callable suitable for Ninja route registration (sync or async).

    _apply_metadata(clean_handler, original)
            Copy relevant metadata from the original method to the wrapped handler to
            improve OpenAPI generation and introspection.

            Behavior:
            - Preserve the function name where possible.
            - Replace the __signature__ to exclude the first parameter if it is
                `self` or `cls`, ensuring Ninja does not treat them as parameters.
            - Copy annotations while removing `self` to avoid unwanted schema entries.

            Parameters:
            - clean_handler: The wrapped function produced by _build_handler.
            - original: The original method from which metadata will be copied.

    build_decorator(
            auth=NOT_SET,
            throttle=NOT_SET,
            response=NOT_SET,
            Create and return a decorator that can be applied to an instance method to
            lazily register it as an endpoint when the instance is initialized.

            How it works:
            - The decorator attaches an `_api_register` callable to the method.
            - When invoked with an API view instance, `_api_register` resolves the
                instance’s `router`, wraps the method via _build_handler, applies metadata
                via _apply_metadata, and registers the handler using the router’s method
                corresponding to `method_name` (e.g., router.get).

            Parameters mirror Ninja Router endpoint registration and control OpenAPI
            generation and request handling:
            - path: Route path for the endpoint.
            - auth: Authentication configuration or NOT_SET.
            - throttle: Throttle configuration(s) or NOT_SET.
            - response: Response schema/model or NOT_SET.
            - operation_id: Optional OpenAPI operation identifier.
            - summary: Short summary for OpenAPI.
            - description: Detailed description for OpenAPI.
            - tags: Grouping tags for OpenAPI.
            - deprecated: Mark endpoint as deprecated in OpenAPI.
            - by_alias, exclude_unset, exclude_defaults, exclude_none: Pydantic-related
                serialization options for response models.
            - url_name: Optional Django URL name.
            - include_in_schema: Whether to include this endpoint in OpenAPI schema.
            - openapi_extra: Additional raw OpenAPI metadata.

            Returns:
            - A decorator to apply to sync/async instance methods.

    make(method_name: str)
            Class method that returns a ready-to-use decorator function for the given
            HTTP method, suitable for direct use on instance methods.

            Example:
                    api_get = ApiMethodFactory.make("get")

                    class MyView(API):
                            router = Router()

                            @api_get("/items")
                            async def list_items(self, request):
                                    ...

            Parameters:
            - method_name: The HTTP method name to bind (e.g., "get", "post", "put").

            Returns:
            - A function that mirrors build_decorator’s signature, named
                "api_{method_name}", with a docstring indicating it registers the
                corresponding HTTP endpoint on the instance router.
    """

    def __init__(self, method_name: str):
        self.method_name = method_name

    def _build_handler(self, view_instance, original):
        is_async = asyncio.iscoroutinefunction(original)

        if is_async:

            async def clean_handler(request, *args, **kwargs):
                return await original(view_instance, request, *args, **kwargs)
        else:

            def clean_handler(request, *args, **kwargs):
                return original(view_instance, request, *args, **kwargs)

        return clean_handler

    def _apply_metadata(self, clean_handler, original):
        # name
        try:
            clean_handler.__name__ = getattr(
                original, "__name__", clean_handler.__name__
            )
        except Exception:
            pass

        # signature and annotations without self/cls
        try:
            sig = inspect.signature(original)
            params = sig.parameters
            params_list = list(params.values())
            if params_list and params_list[0].name in {"self", "cls"}:
                params_list = params_list[1:]
            clean_handler.__signature__ = sig.replace(parameters=params_list)  # type: ignore[attr-defined]

            anns = dict(getattr(original, "__annotations__", {}))
            anns.pop("self", None)
            clean_handler.__annotations__ = anns
        except Exception:
            pass

    def build_decorator(
        self,
        path: str,
        *,
        auth: Any = NOT_SET,
        throttle: Union[BaseThrottle, List[BaseThrottle], NOT_SET_TYPE] = NOT_SET,
        response: Any = NOT_SET,
        operation_id: Optional[str] = None,
        summary: Optional[str] = None,
        description: Optional[str] = None,
        tags: Optional[List[str]] = None,
        deprecated: Optional[bool] = None,
        by_alias: Optional[bool] = None,
        exclude_unset: Optional[bool] = None,
        exclude_defaults: Optional[bool] = None,
        exclude_none: Optional[bool] = None,
        url_name: Optional[str] = None,
        include_in_schema: bool = True,
        openapi_extra: Optional[Dict[str, Any]] = None,
        decorators: Optional[List[Callable]] = None,  # es. [paginate(...)]
    ):
        """
        Returns a decorator that can be applied to an async or sync instance method.
        When the instance is created and owns a `router`, the wrapped method is
        registered on that router using the provided configuration.
        """

        def decorator(func):
            from ninja_aio.views.api import API

            def register_on_instance(view_instance: API):
                router: Router = getattr(view_instance, "router", None)
                if router is None:
                    raise RuntimeError("The view instance does not have a router")

                clean_handler = self._build_handler(view_instance, func)
                self._apply_metadata(clean_handler, func)

                # Apply additional decorators if any
                if decorators:
                    for dec in reversed(decorators):
                        clean_handler = dec(clean_handler)

                route_adder = getattr(router, self.method_name)
                route_adder(
                    path=path,
                    auth=auth,
                    throttle=throttle,
                    response=response,
                    operation_id=operation_id,
                    summary=summary,
                    description=description,
                    tags=tags,
                    deprecated=deprecated,
                    by_alias=by_alias,
                    exclude_unset=exclude_unset,
                    exclude_defaults=exclude_defaults,
                    exclude_none=exclude_none,
                    url_name=url_name,
                    include_in_schema=include_in_schema,
                    openapi_extra=openapi_extra,
                )(clean_handler)

            setattr(func, "_api_register", register_on_instance)
            return func

        return decorator

    @classmethod
    def make(cls, method_name: str):
        """Factory returning a decorator function for the given HTTP method."""

        def wrapper(
            path: str,
            *,
            auth: Any = NOT_SET,
            throttle: Union[BaseThrottle, List[BaseThrottle], NOT_SET_TYPE] = NOT_SET,
            response: Any = NOT_SET,
            operation_id: Optional[str] = None,
            summary: Optional[str] = None,
            description: Optional[str] = None,
            tags: Optional[List[str]] = None,
            deprecated: Optional[bool] = None,
            by_alias: Optional[bool] = None,
            exclude_unset: Optional[bool] = None,
            exclude_defaults: Optional[bool] = None,
            exclude_none: Optional[bool] = None,
            url_name: Optional[str] = None,
            include_in_schema: bool = True,
            openapi_extra: Optional[Dict[str, Any]] = None,
            decorators: Optional[List[Callable]] = None,  # es. [paginate(...)]
        ):
            return cls(method_name).build_decorator(
                path,
                auth=auth,
                throttle=throttle,
                response=response,
                operation_id=operation_id,
                summary=summary,
                description=description,
                tags=tags,
                deprecated=deprecated,
                by_alias=by_alias,
                exclude_unset=exclude_unset,
                exclude_defaults=exclude_defaults,
                exclude_none=exclude_none,
                url_name=url_name,
                include_in_schema=include_in_schema,
                openapi_extra=openapi_extra,
                decorators=decorators,
            )

        wrapper.__name__ = f"api_{method_name}"
        wrapper.__doc__ = (
            f"Class method decorator that lazily registers a {method_name.upper()} endpoint on the instance router.\n\n"
            f"Parameters mirror api_get."
        )
        return wrapper