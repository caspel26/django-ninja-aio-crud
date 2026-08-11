from io import StringIO
from unittest.mock import AsyncMock, patch

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings, tag

DUMMY_API = object()


@tag("mcp")
class McpServerCommandTests(TestCase):
    def test_runs_with_explicit_dotted_path(self):
        with patch("ninja_aio.mcp.run_mcp_server", new=AsyncMock()) as mock_run:
            call_command(
                "mcp_server",
                "tests.mcp.test_management_command.DUMMY_API",
                stderr=StringIO(),
            )
        mock_run.assert_awaited_once_with(DUMMY_API)

    def test_passes_name_option_through(self):
        with patch("ninja_aio.mcp.run_mcp_server", new=AsyncMock()) as mock_run:
            call_command(
                "mcp_server",
                "tests.mcp.test_management_command.DUMMY_API",
                "--name",
                "my-server",
                stderr=StringIO(),
            )
        mock_run.assert_awaited_once_with(DUMMY_API, name="my-server")

    @override_settings(NINJA_AIO_MCP_API="tests.mcp.test_management_command.DUMMY_API")
    def test_falls_back_to_settings_when_no_path_given(self):
        with patch("ninja_aio.mcp.run_mcp_server", new=AsyncMock()) as mock_run:
            call_command("mcp_server", stderr=StringIO())
        mock_run.assert_awaited_once_with(DUMMY_API)

    def test_no_path_and_no_setting_raises_command_error(self):
        with self.assertRaises(CommandError):
            call_command("mcp_server", stderr=StringIO())

    def test_dotted_path_without_module_raises_command_error(self):
        with self.assertRaises(CommandError):
            call_command("mcp_server", "not_a_dotted_path", stderr=StringIO())

    def test_unimportable_module_raises_command_error(self):
        with self.assertRaises(CommandError):
            call_command(
                "mcp_server", "tests.mcp.does_not_exist.attr", stderr=StringIO()
            )

    def test_missing_attribute_raises_command_error(self):
        with self.assertRaises(CommandError):
            call_command(
                "mcp_server",
                "tests.mcp.test_management_command.NOT_AN_ATTRIBUTE",
                stderr=StringIO(),
            )

    def test_missing_mcp_extra_raises_command_error(self):
        with patch.dict("sys.modules", {"ninja_aio.mcp": None}):
            with self.assertRaises(CommandError):
                call_command(
                    "mcp_server",
                    "tests.mcp.test_management_command.DUMMY_API",
                    stderr=StringIO(),
                )
