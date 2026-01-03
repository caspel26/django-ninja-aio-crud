from typing import (
    Dict,
    List,
    Optional,
    Union,
    Any,
)
import inspect

from asgiref.sync import sync_to_async
from ninja.constants import NOT_SET, NOT_SET_TYPE
from ninja.throttling import BaseThrottle
from ninja import Router


def _api_method(
    method_name: str,
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
):
    """
    Generic factory for method decorators that lazily register class-bound API handlers
        on a Ninja Router living on an instance. It ensures bound methods (with `self`)
        are exposed to Ninja as regular callables without `self` or `cls` in the OpenAPI
        signature, preventing them from being treated as query parameters.

        Parameters:
            method_name: Name of the Router method to call (e.g., "get", "post", "put").
            path: Route path to register on the router.
            auth: Optional authentication backend(s) for the endpoint. If NOT_SET, router defaults apply.
            throttle: Optional throttle backend(s) for the endpoint. If NOT_SET, router defaults apply.
            response: Expected response schema or status mapping for Ninja.
            operation_id: Custom OpenAPI operationId. If None, Ninja will infer one.
            summary: Short summary for the OpenAPI operation.
            description: Detailed description for the OpenAPI operation.
            tags: List of tags for grouping the operation in OpenAPI.
            deprecated: Marks the operation as deprecated in OpenAPI if True.
            by_alias: Whether to use field aliases in the serialized response.
            exclude_unset: Exclude unset fields from serialization.
            exclude_defaults: Exclude fields equal to their default values from serialization.
            exclude_none: Exclude fields with None values from serialization.
            url_name: Django URL name to assign to the route.
            include_in_schema: Whether to include the operation in the generated OpenAPI schema.
            openapi_extra: Extra OpenAPI metadata to merge into the operation.

        Returns:
            A decorator that can be applied to an async or sync instance method. When the
            instance is created and owns a `router`, the wrapped method is registered on
            that router using the provided configuration.

        Inner callables:
            decorator(func):
                Wraps the original function and attaches a `_api_register(view_instance)`
                method that performs the router registration. It does not modify the original
                method behavior, only enables deferred registration.

            register_on_instance(view_instance):
                Performs the actual router registration on the provided instance. It builds
                a `clean_handler` that:
                  - For async functions: awaits the original method with `(self, request, *args, **kwargs)`.
                  - For sync functions: runs the original method in an async-friendly way via `sync_to_async`.
                It then:
                  - Copies a meaningful name to `clean_handler` for better logging and docs.
                  - Replaces `clean_handler.__signature__` to the original function's signature
                    without the leading `self`/`cls`, so Ninja correctly infers parameters
                    and avoids treating `self` as a query param.
                  - Copies annotations excluding `self`, preserving type hints for OpenAPI.
                  - Registers `clean_handler` on the router using the specified `method_name`
                    and the supplied endpoint configuration.

            clean_handler(request, *args, **kwargs):
                The runtime handler bound to the router. It delegates to the original method,
                ensuring proper async/sync execution and preserving the intended instance
                context (`self`). This is the callable Ninja invokes for the endpoint.
    """

    def decorator(func):
        from ninja_aio.views.api import API

        def register_on_instance(view_instance: API):
            router: Router = getattr(view_instance, "router", None)
            if router is None:
                raise RuntimeError("The view instance does not have a router")

            async def clean_handler(request, *args, **kwargs):
                if inspect.iscoroutinefunction(func):
                    return await func(view_instance, request, *args, **kwargs)
                return await sync_to_async(func)(
                    view_instance, request, *args, **kwargs
                )

            # Keep a meaningful name
            try:
                clean_handler.__name__ = getattr(
                    func, "__name__", clean_handler.__name__
                )
            except Exception:
                pass

            # Expose the original signature minus `self` so Ninja infers params correctly
            try:
                sig = inspect.signature(func)
                params = list(sig.parameters.values())
                if params and params[0].name in {"self", "cls"}:
                    params = params[1:]
                new_sig = sig.replace(parameters=params)
                clean_handler.__signature__ = new_sig  # type: ignore[attr-defined]
                # Copy annotations excluding `self`
                if hasattr(func, "__annotations__"):
                    anns = dict(getattr(func, "__annotations__", {}))
                    anns.pop("self", None)
                    clean_handler.__annotations__ = anns
            except Exception:
                # Best-effort; if anything fails, Ninja will fallback to runtime signature
                pass

            # Dispatch to the correct router method
            router_method = getattr(router, method_name)
            router_method(
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


def api_get(
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
):
    """
    Class method decorator that lazily registers a GET endpoint on the instance router.

    Use this to annotate class methods that should be exposed as HTTP GET operations.
    The decorator defers registration until the class is instantiated, allowing the
    method to be bound to the instance router.

    Parameters:
        path (str): The URL path for the endpoint (e.g., "/items/{item_id}").
        auth (Any, optional): Authentication backend or configuration. If NOT_SET, router defaults apply.
        throttle (Union[BaseThrottle, List[BaseThrottle], NOT_SET_TYPE], optional): Throttle policies. If NOT_SET, router defaults apply.
        response (Any, optional): Response schema/model or mapping for OpenAPI docs.
        operation_id (Optional[str], optional): Custom operationId for OpenAPI.
        summary (Optional[str], optional): Short summary.
        description (Optional[str], optional): Detailed description.
        tags (Optional[List[str]], optional): Grouping tags.
        deprecated (Optional[bool], optional): Mark as deprecated.
        by_alias (Optional[bool], optional): Use field aliases in serialization.
        exclude_unset (Optional[bool], optional): Exclude unset fields from serialization.
        exclude_defaults (Optional[bool], optional): Exclude default-valued fields.
        exclude_none (Optional[bool], optional): Exclude None-valued fields.
        url_name (Optional[str], optional): Django URL name.
        include_in_schema (bool, optional): Include in OpenAPI schema. Defaults to True.
        openapi_extra (Optional[Dict[str, Any]], optional): Extra OpenAPI metadata.

    Returns:
        Callable: A decorator that registers the method as a GET endpoint on instantiation.
    """
    return _api_method(
        "get",
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
    )


def api_post(
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
):
    """
    Class method decorator that lazily registers a POST endpoint on the instance router.

    Use this to annotate class methods exposed as HTTP POST operations. Registration
    is deferred until instantiation so the method binds to the instance router.

    Parameters mirror api_get.

    Returns:
        Callable: A decorator that registers the method as a POST endpoint on instantiation.
    """
    return _api_method(
        "post",
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
    )


def api_put(
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
):
    """
    Class method decorator that lazily registers a PUT endpoint on the instance router.

    Use for HTTP PUT operations that update resources. Registration is deferred until
    instantiation, binding the method to the instance router.

    Parameters mirror api_get.

    Returns:
        Callable: A decorator that registers the method as a PUT endpoint on instantiation.
    """
    return _api_method(
        "put",
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
    )


def api_patch(
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
):
    """
    Class method decorator that lazily registers a PATCH endpoint on the instance router.

    Use for HTTP PATCH operations that partially update resources. Registration is
    deferred to bind the method when the class is instantiated.

    Parameters mirror api_get.

    Returns:
        Callable: A decorator that registers the method as a PATCH endpoint on instantiation.
    """
    return _api_method(
        "patch",
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
    )


def api_delete(
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
):
    """
    Class method decorator that lazily registers a DELETE endpoint on the instance router.

    Use for HTTP DELETE operations that remove resources. Registration is deferred
    until instantiation to bind the method to the instance router.

    Parameters mirror api_get.

    Returns:
        Callable: A decorator that registers the method as a DELETE endpoint on instantiation.
    """
    return _api_method(
        "delete",
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
    )


def api_options(
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
):
    """
    Class method decorator that lazily registers an OPTIONS endpoint on the instance router.

    Use for HTTP OPTIONS operations. Registration is deferred until instantiation.

    Parameters mirror api_get.

    Returns:
        Callable: A decorator that registers the method as an OPTIONS endpoint on instantiation.
    """
    return _api_method(
        "options",
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
    )


def api_head(
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
):
    """
    Class method decorator that lazily registers a HEAD endpoint on the instance router.

    Use for HTTP HEAD operations that return headers without a body. Registration is
    deferred until the class is instantiated.

    Parameters mirror api_get.

    Returns:
        Callable: A decorator that registers the method as a HEAD endpoint on instantiation.
    """
    return _api_method(
        "head",
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
    )
