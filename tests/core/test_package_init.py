from django.test import SimpleTestCase, tag

import ninja_aio


@tag("core")
class PackageLazyInitTests(SimpleTestCase):
    """ninja_aio/__init__.py resolves its public names lazily (PEP 562) so
    that plain `import ninja_aio` has no side effects requiring Django's app
    registry to be ready (needed for `ninja_aio` to be usable as an installed
    app — see ninja_aio/apps.py and ninja_aio/management/commands/mcp_server.py).
    """

    def test_public_names_resolve_via_getattr(self):
        from ninja_aio.api import NinjaAIO as NinjaAIODirect
        from ninja_aio.admin import register_admin as register_admin_direct
        from ninja_aio.docs import Branding as BrandingDirect
        from ninja_aio.router import NinjaAIORouter as NinjaAIORouterDirect

        self.assertIs(ninja_aio.NinjaAIO, NinjaAIODirect)
        self.assertIs(ninja_aio.NinjaAIORouter, NinjaAIORouterDirect)
        self.assertIs(ninja_aio.register_admin, register_admin_direct)
        self.assertIs(ninja_aio.Branding, BrandingDirect)

    def test_v3_surface_resolves_to_defining_modules(self):
        from ninja_aio.decorators.actions import action, on
        from ninja_aio.models.config import SchemaConfig
        from ninja_aio.models.serializers import ModelSerializer, Serializer
        from ninja_aio.types import HttpMethod
        from ninja_aio.views.api import APIView, APIViewSet

        for exported in (
            action, on, ModelSerializer, Serializer, SchemaConfig, HttpMethod, APIView, APIViewSet,
        ):
            self.assertIs(getattr(ninja_aio, exported.__name__), exported)

    def test_unknown_attribute_raises_attribute_error(self):
        with self.assertRaises(AttributeError):
            ninja_aio.DoesNotExist

    def test_dir_includes_all_public_names(self):
        self.assertTrue(set(ninja_aio.__all__).issubset(set(dir(ninja_aio))))

    def test_star_import_exposes_all_public_names(self):
        namespace = {}
        exec("from ninja_aio import *", namespace)
        for name in ninja_aio.__all__:
            self.assertIn(name, namespace)
