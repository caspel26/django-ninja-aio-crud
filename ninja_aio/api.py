from typing import Any, Sequence, TypeVar

from ninja import NinjaAPI
from ninja.constants import NOT_SET, NOT_SET_TYPE
from ninja.openapi.docs import DocsBase, Swagger
from ninja.parser import Parser
from ninja.renderers import BaseRenderer
from ninja.router import Router
from ninja.throttling import BaseThrottle
from django.db import models

from .parsers import ORJSONParser
from .renders import ORJSONRenderer
from .exceptions import set_api_exception_handlers
from .views import APIView, APIViewSet
from .docs import Branding, BrandedSwagger
from .router import NinjaAIORouter

# TypeVar for generic typing in decorators
ModelT = TypeVar("ModelT", bound=models.Model)
ViewSetT = TypeVar("ViewSetT", bound=APIViewSet)
RouterT = TypeVar("RouterT", bound=NinjaAIORouter)


class NinjaAIO(NinjaAPI):
    branding: Branding

    # Mirrors NinjaAPI's constructor on purpose, so the parameter count is inherited.
    def __init__(  # NOSONAR
        self,
        title: str = "NinjaAPI",
        version: str = "1.0.0",
        description: str = "",
        openapi_url: str | None = "/openapi.json",
        docs: DocsBase | None = None,
        docs_url: str | None = "/docs",
        docs_decorator=None,
        servers: list[dict[str, Any]] | None = None,
        urls_namespace: str | None = None,
        auth: Sequence[Any] | NOT_SET_TYPE = NOT_SET,
        throttle: BaseThrottle | list[BaseThrottle] | NOT_SET_TYPE = NOT_SET,
        default_router: Router | None = None,
        openapi_extra: dict[str, Any] | None = None,
        branding: Branding | None = None,
        renderer: BaseRenderer | None = None,
        parser: Parser | None = None,
    ):
        self.branding = branding or Branding()
        self._viewsets: list[APIViewSet] = []
        self._views: list[APIView] = []
        self._aio_routers: list[NinjaAIORouter] = []
        if docs is None:
            docs = BrandedSwagger() if branding else Swagger()
        super().__init__(
            title=title,
            version=version,
            description=description,
            openapi_url=openapi_url,
            docs=docs,
            docs_url=docs_url,
            docs_decorator=docs_decorator,
            servers=servers,
            urls_namespace=urls_namespace,
            auth=auth,
            throttle=throttle,
            default_router=default_router,
            openapi_extra=openapi_extra,
            renderer=renderer or ORJSONRenderer(),
            parser=parser or ORJSONParser(),
        )

    def set_default_exception_handlers(self):
        set_api_exception_handlers(self)
        super().set_default_exception_handlers()

    def add_router(self, prefix: str, router: Router | str, *args: Any, **kwargs: Any) -> None:
        super().add_router(prefix, router, *args, **kwargs)
        if isinstance(router, NinjaAIORouter):
            self._aio_routers.append(router)

    def registered_viewsets(self) -> list[APIViewSet]:
        """Viewsets registered on this API, including those on attached NinjaAIORouters."""
        nested = [vs for router in self._aio_routers for vs in router.registered_viewsets()]
        return [*self._viewsets, *nested]

    def registered_views(self) -> list[APIView]:
        """Views registered on this API, including those on attached NinjaAIORouters."""
        nested = [view for router in self._aio_routers for view in router.registered_views()]
        return [*self._views, *nested]

    def view(self, prefix: str, tags: list[str] = None) -> Any:
        def wrapper(view: type[APIView]):
            instance = view(api=self, prefix=prefix, tags=tags)
            instance.add_views_to_route()
            self._views.append(instance)
            return instance

        return wrapper

    def viewset(
        self,
        model: type[ModelT],
        prefix: str = None,
        tags: list[str] = None,
    ):
        """
        Decorator to register an APIViewSet with a specific model.

        The decorator preserves the ViewSet's type, so type checkers see the
        concrete viewset class returned by the decorator.

        Usage:
            @api.viewset(MyModel)
            class MyModelViewSet(APIViewSet):
                pass
        """

        def wrapper(viewset: type[ViewSetT]) -> ViewSetT:
            instance: ViewSetT = viewset(
                api=self, model=model, prefix=prefix, tags=tags
            )
            instance.add_views_to_route()
            self._viewsets.append(instance)
            return instance

        return wrapper

    def router(self, prefix: str, **kwargs) -> Any:
        """
        Decorator to attach a NinjaAIORouter to this API under the given prefix.

        Usage:
            @api.router("/v1")
            class V1Router(NinjaAIORouter):
                pass

        Keyword arguments are forwarded to api.add_router() (e.g. tags, auth).
        """

        def wrapper(router_cls: type[RouterT]) -> RouterT:
            instance: RouterT = router_cls()
            self.add_router(prefix, instance, **kwargs)
            return instance

        return wrapper
