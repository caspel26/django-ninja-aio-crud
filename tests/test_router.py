from django.test import TestCase, tag

from ninja import Schema

from ninja_aio import NinjaAIO, NinjaAIORouter
from ninja_aio.views import APIView, APIViewSet
from tests.test_app import models, schema


class PingSchema(Schema):
    pong: bool


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


class PingView(APIView):
    def views(self):
        @self.router.get("/ping", response=PingSchema)
        async def ping(request):
            return {"pong": True}


class TestModelViewSet(APIViewSet):
    model = models.TestModel
    schema_in = schema.TestModelSchemaIn
    schema_out = schema.TestModelSchemaOut
    schema_update = schema.TestModelSchemaPatch


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _all_prefixes(router, depth=0) -> list[str]:
    """Recursively collect all nested router prefixes."""
    result = []
    for prefix, child, _ in router._routers:
        result.append(prefix)
        result.extend(_all_prefixes(child, depth + 1))
    return result


# ---------------------------------------------------------------------------
# Tests: NinjaAIORouter standalone usage
# ---------------------------------------------------------------------------


@tag("router")
class NinjaAIORouterStructureTest(TestCase):
    """NinjaAIORouter exposes .view() and .viewset() and is a Router subclass."""

    def test_is_router_subclass(self):
        from ninja import Router

        self.assertTrue(issubclass(NinjaAIORouter, Router))

    def test_has_view_decorator(self):
        self.assertTrue(callable(getattr(NinjaAIORouter, "view", None)))

    def test_has_viewset_decorator(self):
        self.assertTrue(callable(getattr(NinjaAIORouter, "viewset", None)))


# ---------------------------------------------------------------------------
# Tests: view() decorator on NinjaAIORouter
# ---------------------------------------------------------------------------


@tag("router")
class NinjaAIORouterViewTest(TestCase):
    """NinjaAIORouter.view() registers an APIView sub-router."""

    @classmethod
    def setUpTestData(cls):
        cls.router = NinjaAIORouter()
        cls.router.view(prefix="/custom", tags=["Custom"])(PingView)

    def test_sub_router_registered(self):
        self.assertEqual(len(self.router._routers), 1)

    def test_sub_router_prefix(self):
        prefix, _, __ = self.router._routers[0]
        self.assertEqual(prefix, "/custom")


# ---------------------------------------------------------------------------
# Tests: viewset() decorator on NinjaAIORouter
# ---------------------------------------------------------------------------


@tag("router")
class NinjaAIORouterViewSetTest(TestCase):
    """NinjaAIORouter.viewset() registers an APIViewSet sub-router."""

    @classmethod
    def setUpTestData(cls):
        cls.router = NinjaAIORouter()
        cls.router.viewset(model=models.TestModel, prefix="/items", tags=["Items"])(
            TestModelViewSet
        )

    def test_sub_router_registered(self):
        self.assertEqual(len(self.router._routers), 1)

    def test_sub_router_prefix(self):
        prefix, _, __ = self.router._routers[0]
        self.assertEqual(prefix, "/items")


# ---------------------------------------------------------------------------
# Tests: attach via api.add_router()
# ---------------------------------------------------------------------------


@tag("router")
class NinjaAIORouterAddRouterTest(TestCase):
    """api.add_router(prefix, NinjaAIORouter) correctly mounts all nested routes."""

    @classmethod
    def setUpTestData(cls):
        cls.api = NinjaAIO(urls_namespace="router_add_test")
        cls.router = NinjaAIORouter()
        cls.router.view(prefix="/custom", tags=["Custom"])(PingView)
        cls.router.viewset(model=models.TestModel, prefix="/items", tags=["Items"])(
            TestModelViewSet
        )
        cls.api.add_router("/v1", cls.router)

    def test_router_mounted_on_api(self):
        prefixes = [prefix for prefix, _ in self.api._routers]
        self.assertIn("/v1", prefixes)

    def test_nested_view_paths_reachable(self):
        # api._routers is List[Tuple[str, Router]] at the NinjaAPI level
        prefixes = _all_prefixes(self.router)
        self.assertTrue(any("custom" in p for p in prefixes))

    def test_nested_viewset_paths_reachable(self):
        prefixes = _all_prefixes(self.router)
        self.assertTrue(any("items" in p for p in prefixes))


# ---------------------------------------------------------------------------
# Tests: attach via @api.router() decorator
# ---------------------------------------------------------------------------


@tag("router")
class NinjaAIORouterDecoratorTest(TestCase):
    """@api.router(prefix) decorator attaches NinjaAIORouter to NinjaAIO."""

    @classmethod
    def setUpTestData(cls):
        cls.api = NinjaAIO(urls_namespace="router_decorator_test")

        @cls.api.router("/v2")
        class V2Router(NinjaAIORouter):
            pass

        V2Router.view(prefix="/ping", tags=["Ping"])(PingView)
        V2Router.viewset(
            model=models.TestModel, prefix="/items", tags=["Items"]
        )(TestModelViewSet)
        cls.router = V2Router

    def test_router_mounted_on_api(self):
        prefixes = [prefix for prefix, _ in self.api._routers]
        self.assertIn("/v2", prefixes)

    def test_is_ninja_aio_router_instance(self):
        self.assertIsInstance(self.router, NinjaAIORouter)


# ---------------------------------------------------------------------------
# Tests: decorator syntax on class body
# ---------------------------------------------------------------------------


@tag("router")
class NinjaAIORouterDecoratorSyntaxTest(TestCase):
    """NinjaAIORouter works with decorator syntax at class-definition time."""

    @classmethod
    def setUpTestData(cls):
        cls.api = NinjaAIO(urls_namespace="router_syntax_test")

        @cls.api.router("/api")
        class AppRouter(NinjaAIORouter):
            pass

        @AppRouter.view(prefix="/health", tags=["Health"])
        class HealthView(APIView):
            def views(self):
                @self.router.get("/check")
                async def check(request):
                    return {"status": "ok"}

        @AppRouter.viewset(
            model=models.TestModel, prefix="/models", tags=["Models"]
        )
        class ModelViewSet(APIViewSet):
            model = models.TestModel
            schema_in = schema.TestModelSchemaIn
            schema_out = schema.TestModelSchemaOut
            schema_update = schema.TestModelSchemaPatch

        cls.app_router = AppRouter

    def test_view_registered(self):
        prefixes = [prefix for prefix, *_ in self.app_router._routers]
        self.assertIn("/health", prefixes)

    def test_viewset_registered(self):
        prefixes = [prefix for prefix, *_ in self.app_router._routers]
        self.assertIn("/models", prefixes)

    def test_two_sub_routers_on_app_router(self):
        self.assertEqual(len(self.app_router._routers), 2)
