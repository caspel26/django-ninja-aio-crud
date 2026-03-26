from django.test import TestCase, tag

from ninja_aio import NinjaAIO, Branding
from ninja_aio.docs import BrandedSwagger


@tag("branding")
class BrandingConfigTestCase(TestCase):
    """Test Branding dataclass and NinjaAIO integration."""

    def test_default_branding(self):
        """NinjaAIO without branding uses default Swagger."""
        api = NinjaAIO(urls_namespace="brand_default")
        self.assertIsNotNone(api.branding)
        self.assertIsNone(api.branding.logo_url)
        self.assertIsNone(api.branding.primary_color)

    def test_branding_activates_branded_swagger(self):
        """Passing branding= uses BrandedSwagger automatically."""
        api = NinjaAIO(
            urls_namespace="brand_auto",
            branding=Branding(logo_url="/static/logo.png"),
        )
        self.assertIsInstance(api.docs, BrandedSwagger)
        self.assertEqual(api.branding.logo_url, "/static/logo.png")

    def test_branding_with_all_options(self):
        """All branding options are stored correctly."""
        branding = Branding(
            logo_url="/static/logo.png",
            primary_color="#7c4dff",
            favicon_url="/static/favicon.ico",
            custom_css=".topbar { display: none; }",
        )
        api = NinjaAIO(urls_namespace="brand_full", branding=branding)
        self.assertEqual(api.branding.primary_color, "#7c4dff")
        self.assertEqual(api.branding.favicon_url, "/static/favicon.ico")
        self.assertEqual(api.branding.custom_css, ".topbar { display: none; }")

    def test_explicit_docs_overrides_branding(self):
        """Explicit docs= parameter takes precedence over branding."""
        from ninja.openapi.docs import Swagger

        custom_docs = Swagger(settings={"layout": "StandaloneLayout"})
        api = NinjaAIO(
            urls_namespace="brand_override",
            docs=custom_docs,
            branding=Branding(logo_url="/logo.png"),
        )
        # docs= was explicit, so it's used as-is
        self.assertIs(api.docs, custom_docs)
        # branding is still stored for template access
        self.assertEqual(api.branding.logo_url, "/logo.png")


@tag("branding")
class BrandedSwaggerTemplateTestCase(TestCase):
    """Test BrandedSwagger template exists and is valid."""

    def test_template_file_exists(self):
        """The branded Swagger CDN template file exists."""
        from pathlib import Path

        template = Path(BrandedSwagger.template_cdn)
        self.assertTrue(template.exists(), f"Template not found: {template}")

    def test_template_contains_branding_tags(self):
        """Template contains branding-related template tags."""
        from pathlib import Path

        content = Path(BrandedSwagger.template_cdn).read_text()
        self.assertIn("api.branding.logo_url", content)
        self.assertIn("api.branding.primary_color", content)
        self.assertIn("api.branding.favicon_url", content)
        self.assertIn("api.branding.custom_css", content)
        self.assertIn("api.branding.custom_css_url", content)


@tag("branding")
class BrandedSwaggerRenderTestCase(TestCase):
    """Test BrandedSwagger render_page actually renders with branding."""

    def test_render_page_includes_branding(self):
        """render_page injects branding CSS into the response."""
        from django.test import RequestFactory
        from unittest.mock import patch

        api = NinjaAIO(
            urls_namespace="brand_render",
            branding=Branding(
                logo_url="/static/logo.png",
                primary_color="#7c4dff",
                favicon_url="/static/fav.ico",
                custom_css=".custom { color: red; }",
            ),
        )

        factory = RequestFactory()
        request = factory.get("/api/docs")

        with patch.object(api.docs, "get_openapi_url", return_value="/api/openapi.json"):
            response = api.docs.render_page(request, api)

        content = response.content.decode()
        self.assertIn("#7c4dff", content)
        self.assertIn("/static/logo.png", content)
        self.assertIn("/static/fav.ico", content)
        self.assertIn(".custom { color: red; }", content)

    def test_render_page_with_css_url(self):
        """render_page loads external CSS file via link tag."""
        from django.test import RequestFactory
        from unittest.mock import patch

        api = NinjaAIO(
            urls_namespace="brand_css_url",
            branding=Branding(custom_css_url="/static/css/swagger.css"),
        )

        factory = RequestFactory()
        request = factory.get("/api/docs")

        with patch.object(api.docs, "get_openapi_url", return_value="/api/openapi.json"):
            response = api.docs.render_page(request, api)

        content = response.content.decode()
        self.assertIn('href="/static/css/swagger.css"', content)

    def test_render_page_with_django_template_engine(self):
        """render_page uses Django template engine when template is found."""
        from django.test import RequestFactory, override_settings
        from unittest.mock import patch, MagicMock

        api = NinjaAIO(
            urls_namespace="brand_tpl_engine",
            branding=Branding(primary_color="#ff0000"),
        )

        factory = RequestFactory()
        request = factory.get("/api/docs")

        mock_tpl = MagicMock()
        mock_tpl.render.return_value = "<html>branded</html>"

        with patch.object(api.docs, "get_openapi_url", return_value="/api/openapi.json"), \
             patch("ninja_aio.docs.get_template", return_value=mock_tpl):
            response = api.docs.render_page(request, api)

        self.assertEqual(response.content.decode(), "<html>branded</html>")
        mock_tpl.render.assert_called_once()

    def test_render_page_without_branding(self):
        """render_page works without any branding configured."""
        from django.test import RequestFactory
        from unittest.mock import patch

        api = NinjaAIO(
            urls_namespace="brand_render_none",
            branding=Branding(),
        )

        factory = RequestFactory()
        request = factory.get("/api/docs")

        with patch.object(api.docs, "get_openapi_url", return_value="/api/openapi.json"):
            response = api.docs.render_page(request, api)

        content = response.content.decode()
        self.assertIn("swagger-ui", content)
        self.assertNotIn("#7c4dff", content)
