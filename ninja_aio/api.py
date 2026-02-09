from typing import Any, Sequence, TypeVar

from ninja.router import Router
from ninja.throttling import BaseThrottle
from ninja import NinjaAPI
from ninja.openapi.docs import DocsBase, Swagger
from ninja.constants import NOT_SET, NOT_SET_TYPE
from django.db import models

from .parsers import ORJSONParser
from .renders import ORJSONRenderer
from .exceptions import set_api_exception_handlers
from .views import APIView, APIViewSet

# TypeVar for generic typing in decorators
ModelT = TypeVar("ModelT", bound=models.Model)
ViewSetT = TypeVar("ViewSetT", bound=APIViewSet)


class NinjaAIO(NinjaAPI):
    def __init__(
        self,
        title: str = "NinjaAPI",
        version: str = "1.0.0",
        description: str = "",
        openapi_url: str | None = "/openapi.json",
        docs: DocsBase = Swagger(),
        docs_url: str | None = "/docs",
        docs_decorator=None,
        servers: list[dict[str, Any]] | None = None,
        urls_namespace: str | None = None,
        auth: Sequence[Any] | NOT_SET_TYPE = NOT_SET,
        throttle: BaseThrottle | list[BaseThrottle] | NOT_SET_TYPE = NOT_SET,
        default_router: Router | None = None,
        openapi_extra: dict[str, Any] | None = None,
    ):
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
            renderer=ORJSONRenderer(),
            parser=ORJSONParser(),
        )

    def set_default_exception_handlers(self):
        set_api_exception_handlers(self)
        super().set_default_exception_handlers()

    def view(self, prefix: str, tags: list[str] = None) -> Any:
        def wrapper(view: type[APIView]):
            instance = view(api=self, prefix=prefix, tags=tags)
            instance.add_views_to_route()
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

        The decorator preserves the ViewSet's type, allowing type checkers
        to infer that model_util is properly typed based on the model parameter.

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
            return instance

        return wrapper
