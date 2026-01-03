from typing import Any, Sequence

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
from .models import ModelSerializer


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
        model: models.Model | ModelSerializer,
        prefix: str = None,
        tags: list[str] = None,
    ) -> None:
        def wrapper(viewset: type[APIViewSet]):
            instance = viewset(api=self, model=model, prefix=prefix, tags=tags)
            instance.add_views_to_route()
            return instance

        return wrapper
