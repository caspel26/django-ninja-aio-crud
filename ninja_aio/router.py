from typing import Any, TypeVar

from ninja import Router
from django.db.models import Model

from .views import APIView, APIViewSet

ModelT = TypeVar("ModelT", bound=Model)
ViewSetT = TypeVar("ViewSetT", bound=APIViewSet)


class NinjaAIORouter(Router):
    """
    A Router that mirrors NinjaAIO's .view() and .viewset() decorators.

    Views and viewsets registered here mount their sub-routers onto this
    router (nested), so the whole tree can be attached to a NinjaAIO
    instance with a single api.add_router(prefix, router) call.

    Attachment options:

        # Option 1 — standard Django Ninja call
        api.add_router("/v1", my_router)

        # Option 2 — decorator on NinjaAIO (requires NinjaAIO.router() support)
        @api.router("/v1")
        class MyRouter(NinjaAIORouter):
            pass
    """

    def view(self, prefix: str, tags: list[str] = None) -> Any:
        def wrapper(view_cls: type[APIView]):
            instance = view_cls(api=self, prefix=prefix, tags=tags)
            instance.add_views_to_route()
            return instance

        return wrapper

    def viewset(
        self,
        model: type[ModelT],
        prefix: str = None,
        tags: list[str] = None,
    ) -> Any:
        def wrapper(viewset_cls: type[ViewSetT]) -> ViewSetT:
            instance: ViewSetT = viewset_cls(api=self, model=model, prefix=prefix, tags=tags)
            instance.add_views_to_route()
            return instance

        return wrapper
