from unittest.mock import AsyncMock, patch

from django.core.exceptions import ImproperlyConfigured
from django.test import TestCase, tag
from mcp.shared.memory import create_connected_server_and_client_session

from ninja_aio import NinjaAIO, NinjaAIORouter
from ninja_aio.mcp import NinjaAIOMCPServer, run_mcp_server
from ninja_aio.views import APIView, APIViewSet
from tests.test_app import models


@tag("mcp")
class NinjaAIOMCPServerTests(TestCase):
    def test_auto_discovers_viewsets_registered_via_api_viewset(self):
        api = NinjaAIO(urls_namespace="mcp_server_auto")

        @api.viewset(models.TestModelSerializer, prefix="mcp-server-auto-test-model")
        class AutoTestModelSerializerAPI(APIViewSet):
            pass

        server = NinjaAIOMCPServer(api, name="test-server")

        self.assertIn(AutoTestModelSerializerAPI, server.viewsets)
        self.assertIn("testmodelserializer_create", server._tools)
        self.assertIn("testmodelserializer_list", server._tools)

    def test_auto_discovers_viewsets_and_views_on_nested_routers(self):
        api = NinjaAIO(urls_namespace="mcp_server_router")
        parent = NinjaAIORouter()
        child = NinjaAIORouter()

        @child.viewset(models.TestModelSerializer, prefix="mcp-router-model")
        class RouterModelAPI(APIViewSet):
            pass

        @parent.view(prefix="mcp-router-view")
        class RouterView(APIView):
            pass

        parent.add_router("/child", child)
        api.add_router("/v1", parent)
        server = NinjaAIOMCPServer(api, name="test-server")

        self.assertIn(RouterModelAPI, server.viewsets)
        self.assertIn(RouterView, server.views)
        self.assertIn("testmodelserializer_list", server._tools)

    def test_explicit_viewsets_override_registry(self):
        api = NinjaAIO(urls_namespace="mcp_server_explicit")
        viewset = APIViewSet(
            api=api,
            model=models.TestModelSerializer,
            prefix="mcp-server-explicit-test-model",
        )
        viewset.add_views_to_route()

        # Nothing was registered through @api.viewset, so the auto registry is empty.
        self.assertEqual(api._viewsets, [])

        server = NinjaAIOMCPServer(api, viewsets=[viewset], name="test-server")

        self.assertEqual(server.viewsets, [viewset])
        self.assertIn("testmodelserializer_create", server._tools)

    def test_viewsets_on_the_same_model_get_prefixed_tool_names(self):
        api = NinjaAIO(urls_namespace="mcp_server_collision")

        @api.viewset(models.TestModelSerializer, prefix="sync/items")
        class SyncItemsAPI(APIViewSet):
            pass

        @api.viewset(models.TestModelSerializer, prefix="async/items")
        class AsyncItemsAPI(APIViewSet):
            pass

        server = NinjaAIOMCPServer(api, name="test-server")

        self.assertNotIn("testmodelserializer_list", server._tools)
        self.assertIs(server._tools["sync_items_testmodelserializer_list"].owner, SyncItemsAPI)
        self.assertIs(server._tools["async_items_testmodelserializer_list"].owner, AsyncItemsAPI)

    def test_routers_mounted_under_different_prefixes_get_distinct_tool_names(self):
        api = NinjaAIO(urls_namespace="mcp_server_collision_routers")
        routers = {}
        for version in ("v1", "v2"):
            router = NinjaAIORouter()

            @router.viewset(models.TestModelSerializer, prefix="items")
            class ItemsAPI(APIViewSet):
                pass

            api.add_router(f"/{version}", router)
            routers[version] = ItemsAPI

        server = NinjaAIOMCPServer(api, name="test-server")

        self.assertIs(server._tools["v1_items_testmodelserializer_list"].owner, routers["v1"])
        self.assertIs(server._tools["v2_items_testmodelserializer_list"].owner, routers["v2"])

    def test_unresolvable_tool_name_collision_raises(self):
        api = NinjaAIO(urls_namespace="mcp_server_collision_same_prefix")
        first = APIViewSet(api=api, model=models.TestModelSerializer, prefix="same")
        second = APIViewSet(api=api, model=models.TestModelSerializer, prefix="same")
        first._add_views()
        second._add_views()

        with self.assertRaises(ImproperlyConfigured):
            NinjaAIOMCPServer(api, viewsets=[first, second], name="test-server")


@tag("mcp")
class NinjaAIOMCPServerProtocolTests(TestCase):
    """Drives the real MCP list_tools/call_tool protocol handlers, in-memory."""

    @classmethod
    def setUpTestData(cls):
        cls.api = NinjaAIO(urls_namespace="mcp_server_protocol")

        @cls.api.viewset(models.TestModelSerializer, prefix="mcp-protocol-test-model")
        class ProtocolTestModelSerializerAPI(APIViewSet):
            pass

        cls.viewset_cls = ProtocolTestModelSerializerAPI

    async def test_list_tools_over_protocol(self):
        server = NinjaAIOMCPServer(self.api, name="protocol-server")
        async with create_connected_server_and_client_session(server.server) as client:
            tools = await client.list_tools()
            names = {t.name for t in tools.tools}
            self.assertIn("testmodelserializer_create", names)

    async def test_call_tool_over_protocol_success_and_unknown_tool(self):
        server = NinjaAIOMCPServer(self.api, name="protocol-server")
        async with create_connected_server_and_client_session(server.server) as client:
            created = await client.call_tool(
                "testmodelserializer_create", {"name": "n", "description": "d"}
            )
            self.assertFalse(created.isError)

            unknown = await client.call_tool("does_not_exist", {})
            self.assertTrue(unknown.isError)


@tag("mcp")
class NinjaAIOMCPServerStdioTests(TestCase):
    async def test_run_stdio_wires_stdio_server_and_server_run(self):
        api = NinjaAIO(urls_namespace="mcp_server_stdio")
        server = NinjaAIOMCPServer(api, viewsets=[], name="stdio-server")

        fake_streams = ("read-stream", "write-stream")
        with (
            patch("ninja_aio.mcp.server.stdio_server") as mock_stdio_server,
            patch.object(server.server, "run", new=AsyncMock()) as mock_run,
        ):
            mock_stdio_server.return_value.__aenter__.return_value = fake_streams
            mock_stdio_server.return_value.__aexit__.return_value = False

            await server.run_stdio()

            mock_run.assert_awaited_once()
            args = mock_run.await_args.args
            self.assertEqual(args[0], "read-stream")
            self.assertEqual(args[1], "write-stream")

    async def test_run_mcp_server_builds_server_and_runs_it(self):
        api = NinjaAIO(urls_namespace="mcp_server_run_helper")
        with patch(
            "ninja_aio.mcp.server.NinjaAIOMCPServer.run_stdio", new=AsyncMock()
        ) as mock_run_stdio:
            await run_mcp_server(api, viewsets=[])
            mock_run_stdio.assert_awaited_once()
