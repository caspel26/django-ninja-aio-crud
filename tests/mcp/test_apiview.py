from django.test import TestCase, tag
from ninja import Path

from ninja_aio import NinjaAIO
from ninja_aio.mcp import (
    NinjaAIOMCPServer,
    ToolInvocationError,
    describe_api_view,
    invoke_tool,
)
from ninja_aio.views import APIView
from tests.generics.views import GenericAPIView


@tag("mcp")
class DescribeApiViewTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.api = NinjaAIO(urls_namespace="mcp_describe_apiview")
        cls.view = GenericAPIView(api=cls.api)
        cls.view.add_views_to_route()
        cls.specs = describe_api_view(cls.view)
        cls.by_name = {s.name: s for s in cls.specs}

    def test_registered_router_endpoint_becomes_a_tool(self):
        self.assertEqual(len(self.specs), 1)
        spec = self.specs[0]
        self.assertEqual(spec.kind, "router")
        self.assertEqual(spec.owner, self.view)
        self.assertTrue(spec.view_func is not None)

    def test_tool_input_schema_reflects_body_schema_param(self):
        spec = self.specs[0]
        self.assertEqual(set(spec.input_schema["properties"]), {"data"})
        self.assertEqual(spec.input_schema["properties"]["data"]["type"], "object")
        self.assertEqual(
            set(spec.input_schema["properties"]["data"]["properties"]), {"a", "b"}
        )
        self.assertEqual(spec.input_schema["required"], ["data"])


@tag("mcp")
class InvokeApiViewTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.api = NinjaAIO(urls_namespace="mcp_invoke_apiview")
        cls.view = GenericAPIView(api=cls.api)
        cls.view.add_views_to_route()
        cls.spec = describe_api_view(cls.view)[0]

    async def test_invoking_router_tool_calls_the_registered_handler(self):
        result = await invoke_tool(self.spec, {"data": {"a": 2, "b": 3}})
        self.assertEqual(result["result"], 5)


@tag("mcp")
class DescribeApiViewAnnotatedAndHiddenTests(TestCase):
    """Covers django-ninja's Annotated param markers (Path[X]/Query[X]) and
    endpoints excluded from the schema (include_in_schema=False)."""

    @classmethod
    def setUpTestData(cls):
        class MiscView(APIView):
            def views(self):
                @self.router.get("/echo/{item_id}", response=int)
                async def echo_id(request, item_id: Path[int]):
                    return item_id

                @self.router.get("/hidden", include_in_schema=False)
                async def hidden(request):
                    return {"ok": True}

        cls.api = NinjaAIO(urls_namespace="mcp_describe_apiview_misc")
        cls.view = MiscView(api=cls.api, prefix="mcp-misc-view")
        cls.view.add_views_to_route()
        cls.specs = describe_api_view(cls.view)
        cls.by_name = {s.name: s for s in cls.specs}

    def test_annotated_path_param_is_unwrapped_to_its_inner_type(self):
        spec = self.by_name["miscview_echo_id_get"]
        self.assertEqual(spec.input_schema["properties"]["item_id"]["type"], "integer")
        self.assertEqual(spec.input_schema["required"], ["item_id"])

    def test_endpoint_excluded_from_schema_is_not_exposed_as_a_tool(self):
        self.assertNotIn("miscview_hidden_get", self.by_name)


@tag("mcp")
class NinjaAIOMCPServerApiViewTests(TestCase):
    def test_auto_discovers_views_registered_via_api_view(self):
        api = NinjaAIO(urls_namespace="mcp_server_apiview_auto")

        @api.view(prefix="mcp-server-apiview-auto")
        class AutoSumView(APIView):
            def views(self):
                from tests.test_app import schema

                @self.router.post("/", response=schema.SumSchemaOut)
                async def sum(request, data: schema.SumSchemaIn):
                    return {"result": data.a + data.b}

        server = NinjaAIOMCPServer(api, name="test-server")

        self.assertIn(AutoSumView, server.views)
        tool_names = list(server._tools)
        self.assertEqual(len(tool_names), 1)

    def test_explicit_views_override_registry(self):
        api = NinjaAIO(urls_namespace="mcp_server_apiview_explicit")
        view = GenericAPIView(api=api)
        view.add_views_to_route()

        # Nothing was registered through @api.view, so the auto registry is empty.
        self.assertEqual(api._views, [])

        server = NinjaAIOMCPServer(api, viewsets=[], views=[view], name="test-server")

        self.assertEqual(server.views, [view])
        self.assertEqual(len(server._tools), 1)


@tag("mcp")
class InvokeApiViewErrorTests(TestCase):
    async def test_invalid_body_raises_tool_invocation_error(self):
        api = NinjaAIO(urls_namespace="mcp_invoke_apiview_error")
        view = GenericAPIView(api=api)
        view.add_views_to_route()
        spec = describe_api_view(view)[0]

        with self.assertRaises(ToolInvocationError):
            await invoke_tool(spec, {"data": {"a": "not-a-number", "b": 1}})
