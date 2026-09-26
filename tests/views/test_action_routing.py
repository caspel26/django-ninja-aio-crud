from django.core.exceptions import ImproperlyConfigured
from django.test import TestCase, tag
from ninja.testing import TestClient

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
