from unittest.mock import AsyncMock, patch

from django.test import TestCase, tag
from mcp.shared.memory import create_connected_server_and_client_session

from ninja_aio import NinjaAIO
from ninja_aio.mcp import NinjaAIOMCPServer, run_mcp_server
from ninja_aio.views import APIViewSet
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
