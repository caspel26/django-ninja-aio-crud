import asyncio
from importlib import import_module

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError


def _import_dotted(path: str):
    """Import ``module.path.attr`` and return the attribute."""
    module_path, _, attr = path.rpartition(".")
    if not module_path:
        raise CommandError(
            f"Invalid dotted path {path!r} — expected 'module.path.attr' "
            "(e.g. myproject.api.api)."
        )
    try:
        module = import_module(module_path)
    except ImportError as exc:
        raise CommandError(f"Could not import {module_path!r}: {exc}") from exc
    try:
        return getattr(module, attr)
    except AttributeError as exc:
        raise CommandError(f"Module {module_path!r} has no attribute {attr!r}.") from exc


class Command(BaseCommand):
    """Run an MCP server exposing registered NinjaAIO viewsets/views as tools.

    Usage::

        python manage.py mcp_server myproject.api.api

    Or configure a default in settings::

        NINJA_AIO_MCP_API = "myproject.api.api"

        python manage.py mcp_server

    Requires ``"ninja_aio"`` in ``INSTALLED_APPS`` (for command discovery)
    and the ``mcp`` extra: ``pip install "django-ninja-aio-crud[mcp]"``.
    """

    help = (
        "Run an MCP (Model Context Protocol) stdio server exposing registered "
        "NinjaAIO viewsets/views as tools for AI agents (Claude Code, Claude "
        "Desktop, or any other MCP client)."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "api",
            nargs="?",
            default=None,
            help=(
                "Dotted path to a NinjaAIO instance, e.g. myproject.api.api. "
                "Defaults to settings.NINJA_AIO_MCP_API."
            ),
        )
        parser.add_argument(
            "--name", default=None, help="MCP server name advertised to clients."
        )

    def handle(self, *args, **options):
        try:
            from ninja_aio.mcp import run_mcp_server
        except ImportError as exc:
            raise CommandError(
                "The 'mcp' extra is required to run this command: "
                'pip install "django-ninja-aio-crud[mcp]"'
            ) from exc

        dotted_path = options["api"] or getattr(settings, "NINJA_AIO_MCP_API", None)
        if not dotted_path:
            raise CommandError(
                "Provide a dotted path to a NinjaAIO instance "
                "(python manage.py mcp_server myproject.api.api) "
                "or set settings.NINJA_AIO_MCP_API."
            )
        api = _import_dotted(dotted_path)

        server_kwargs = {}
        if options.get("name"):
            server_kwargs["name"] = options["name"]

        self.stderr.write(
            self.style.SUCCESS(f"Starting MCP server for {dotted_path} (stdio)...")
        )
        asyncio.run(run_mcp_server(api, **server_kwargs))
