from django.core.exceptions import ImproperlyConfigured
from django.test import TestCase, tag
from ninja.testing import TestAsyncClient, TestClient

from ninja_aio import NinjaAIO, action, on
from ninja_aio.decorators import api_get, api_options
from ninja_aio.types import HttpMethod
from ninja_aio.views import APIView, APIViewSet
from tests.test_app import models


def deny(request):
    return None


def allow(request):
    return "user"


@tag("actions", "action_routing")
class APIViewActionTests(TestCase):
    def test_actions_on_api_view_run_hooks_and_inherit_view_auth(self):
        calls = []

        class StatsView(APIView):
            api_route_path = "stats-view"
            router_tag = "stats"
            auth = [deny]

            def on_before_operation(self, request, operation):
                calls.append(operation)

            @action(detail=False, url_path="ping", auth=None)
            def ping(self, request):
                return {"pong": True}

            @action(detail=False, methods=[HttpMethod.POST])
            def secret(self, request):
                return {"ok": True}

        api = NinjaAIO(urls_namespace="action_routing_view")
        StatsView(api=api).add_views_to_route()
        client = TestClient(api)

        self.assertEqual(client.get("/stats-view/ping").json(), {"pong": True})
        self.assertEqual(calls, ["ping"])
        self.assertEqual(client.post("/stats-view/secret").status_code, 401)

    def test_detail_actions_require_a_viewset(self):
        class DetailView(APIView):
            @on("toggle")
            def toggle(self, request, obj):
                return {}

        with self.assertRaisesRegex(ImproperlyConfigured, "require an APIViewSet"):
            DetailView(api=NinjaAIO(urls_namespace="action_routing_detail"))


@tag("actions", "action_routing")
class PutActionAuthTests(TestCase):
    def test_put_follows_patch_auth_instead_of_becoming_public(self):
        class PutAPI(APIViewSet):
            model = models.TestModelSerializer
            disable = ["all"]
            auth = [allow]
            patch_auth = [deny]

            @action(detail=False, methods=["put"])
            def replace(self, request):
                return {"replaced": True}

        api = NinjaAIO(urls_namespace="action_routing_put")
        PutAPI(api=api, prefix="put-verbs").add_views_to_route()
        self.assertEqual(TestClient(api).put("/put-verbs/replace").status_code, 401)


@tag("actions", "action_routing")
class ActionVerbTests(TestCase):
    def setUp(self):
        class VerbAPI(APIViewSet):
            model = models.TestModelSerializer
            execution_mode = "sync"
            disable = ["all"]
            auth = [allow]
            get_auth = [deny]

            @action(detail=False, methods=["head"])
            def probe(self, request):
                return {}

            @action(detail=False, methods=["options"])
            def capabilities(self, request):
                return {"methods": ["GET"]}

        api = NinjaAIO(urls_namespace=f"action_routing_verbs_{id(self)}")
        VerbAPI(api=api, prefix="verbs").add_views_to_route()
        self.client = TestClient(api)

    def test_head_follows_get_auth(self):
        self.assertEqual(self.client.request("HEAD", "/verbs/probe").status_code, 401)

    def test_options_action_is_registered(self):
        response = self.client.request("OPTIONS", "/verbs/capabilities")
        self.assertEqual(response.json(), {"methods": ["GET"]})


@tag("actions", "action_routing")
class DeprecatedApiDecoratorTests(TestCase):
    def test_api_decorators_warn_and_options_registers(self):
        with self.assertWarnsRegex(DeprecationWarning, r"api_options is deprecated"):

            class LegacyView(APIView):
                api_route_path = "legacy-view"
                router_tag = "legacy"

                @api_options("/caps")
                def caps(self, request):
                    return {"ok": True}

        with self.assertWarnsRegex(DeprecationWarning, r"api_get is deprecated"):
            api_get("/x")

        api = NinjaAIO(urls_namespace="action_routing_legacy")
        LegacyView(api=api).add_views_to_route()
        response = TestClient(api).request("OPTIONS", "/legacy-view/caps")
        self.assertEqual(response.json(), {"ok": True})


def _routing_viewset(mode: str) -> type[APIViewSet]:
    """Viewset with CRUD, bulk and actions whose static paths sit next to {pk}."""

    class RoutingAPI(APIViewSet):
        model = models.TestModelSerializer
        execution_mode = mode
        bulk_operations = ["update", "delete"]

        if mode == "sync":

            @action(detail=False, url_path="stats")
            def stats(self, request):
                return {"count": models.TestModelSerializer.objects.count()}

            @on("publish")
            def publish(self, request, obj):
                return {"name": obj.name}

            @action(detail=True, methods=["post"])
            def bump(self, request, pk: int):
                return {"pk": pk}

            @action(detail=True)
            def peek(self, request, id: int):
                return {"id": id}

        else:

            @action(detail=False, url_path="stats")
            async def stats(self, request):
                return {"count": await models.TestModelSerializer.objects.acount()}

            @on("publish")
            async def publish(self, request, obj):
                return {"name": obj.name}

            @action(detail=True, methods=["post"])
            async def bump(self, request, pk: int):
                return {"pk": pk}

    return RoutingAPI


@tag("actions", "action_routing")
class SyncStaticRouteResolutionTests(TestCase):
    """Static action and bulk paths resolve before the {pk} CRUD routes."""

    def setUp(self):
        api = NinjaAIO(urls_namespace=f"action_routing_static_sync_{id(self)}")
        _routing_viewset("sync")(api=api, prefix="routing").add_views_to_route()
        self.client = TestClient(api)
        self.obj = models.TestModelSerializer.objects.create(name="a", description="b")

    def test_collection_action_is_not_captured_by_retrieve(self):
        response = self.client.get("/routing/stats")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"count": 1})

    def test_on_action_loads_the_object(self):
        response = self.client.post(f"/routing/{self.obj.pk}/publish")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"name": "a"})

    def test_on_action_missing_object_returns_404(self):
        self.assertEqual(self.client.post("/routing/999/publish").status_code, 404)

    def test_detail_action_receives_pk_argument(self):
        response = self.client.post(f"/routing/{self.obj.pk}/bump")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"pk": self.obj.pk})

    def test_detail_action_can_name_the_argument_after_the_pk_field(self):
        response = self.client.get(f"/routing/{self.obj.pk}/peek")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"id": self.obj.pk})

    def test_bulk_routes_are_not_captured_by_update_and_delete(self):
        updated = self.client.patch(
            "/routing/bulk/", json=[{"id": self.obj.pk, "description": "new"}]
        )
        self.assertEqual(updated.status_code, 200)
        deleted = self.client.delete("/routing/bulk/", json={"ids": [self.obj.pk]})
        self.assertEqual(deleted.status_code, 200)
        self.assertFalse(models.TestModelSerializer.objects.exists())


@tag("actions", "action_routing")
class AsyncStaticRouteResolutionTests(TestCase):
    """Async viewsets resolve static paths the same way as sync ones."""

    def setUp(self):
        api = NinjaAIO(urls_namespace=f"action_routing_static_async_{id(self)}")
        _routing_viewset("async")(api=api, prefix="routing").add_views_to_route()
        self.client = TestAsyncClient(api)
        self.obj = models.TestModelSerializer.objects.create(name="a", description="b")

    async def test_collection_action_is_not_captured_by_retrieve(self):
        response = await self.client.get("/routing/stats")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"count": 1})

    async def test_on_action_loads_the_object(self):
        response = await self.client.post(f"/routing/{self.obj.pk}/publish")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"name": "a"})

    async def test_detail_action_receives_pk_argument(self):
        response = await self.client.post(f"/routing/{self.obj.pk}/bump")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"pk": self.obj.pk})

    async def test_bulk_delete_route_is_not_captured_by_delete(self):
        response = await self.client.delete("/routing/bulk/", json={"ids": [self.obj.pk]})
        self.assertEqual(response.status_code, 200)
        self.assertFalse(await models.TestModelSerializer.objects.aexists())
