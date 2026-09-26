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

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._viewsets: list[APIViewSet] = []
        self._views: list[APIView] = []
        self._aio_routers: list["NinjaAIORouter"] = []

    def add_router(self, prefix: str, router: Router, *args: Any, **kwargs: Any) -> None:
        super().add_router(prefix, router, *args, **kwargs)
        if isinstance(router, NinjaAIORouter):
            self._aio_routers.append(router)

    def registered_viewsets(self) -> list[APIViewSet]:
        """Viewsets registered on this router and its nested NinjaAIORouters."""
        nested = [vs for child in self._aio_routers for vs in child.registered_viewsets()]
        return [*self._viewsets, *nested]

    def registered_views(self) -> list[APIView]:
        """Views registered on this router and its nested NinjaAIORouters."""
        nested = [view for child in self._aio_routers for view in child.registered_views()]
        return [*self._views, *nested]

    def view(self, prefix: str, tags: list[str] = None) -> Any:
        def wrapper(view_cls: type[APIView]):
            instance = view_cls(api=self, prefix=prefix, tags=tags)
            instance.add_views_to_route()
            self._views.append(instance)
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
            self._viewsets.append(instance)
            return instance

        return wrapper
