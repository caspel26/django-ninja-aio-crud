"""
Branded Swagger UI
==================

Custom Swagger docs class that supports logo, colors, favicon, and
custom CSS injection via the ``Branding`` configuration.

Usage::

    from ninja_aio import NinjaAIO

    api = NinjaAIO(
        title="My API",
        branding=Branding(
            logo_url="/static/logo.png",
            primary_color="#7c4dff",
            favicon_url="/static/favicon.ico",
        ),
    )
"""

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from django.http import HttpRequest, HttpResponse
from django.template import Template, Context
from django.template.loader import get_template
from django.template.exceptions import TemplateDoesNotExist
from ninja.openapi.docs import DocsBase, Swagger, _csrf_needed

TEMPLATE_PATH = str(Path(__file__).parent / "templates" / "ninja_aio")


@dataclass
class Branding:
    """Swagger UI branding configuration.

    Parameters
    ----------
    logo_url : str, optional
        URL to a logo image displayed in the Swagger top bar.
    primary_color : str, optional
        CSS color for the top bar, buttons, and accents (e.g. ``"#7c4dff"``).
    favicon_url : str, optional
        URL to a custom favicon.
    custom_css : str, optional
        Raw CSS injected inline into the Swagger page.
    custom_css_url : str, optional
        URL to an external CSS file loaded via ``<link>`` tag
        (e.g. ``"/static/css/swagger-custom.css"``).
    """

    logo_url: str | None = None
    primary_color: str | None = None
    favicon_url: str | None = None
    custom_css: str | None = None
    custom_css_url: str | None = None


DJANGO_TEMPLATE_NAME = "ninja_aio/branded_swagger.html"


class BrandedSwagger(Swagger):
    """Swagger UI with branding support.

    Uses a custom template that renders logo, colors, and CSS
    based on the ``Branding`` config attached to the API instance.

    Template resolution order:

    1. Django template engine (``ninja_aio/branded_swagger.html``) —
       allows override via ``INSTALLED_APPS`` and project templates.
    2. Fallback to the bundled CDN template file.
    """

    template_cdn = str(Path(TEMPLATE_PATH) / "branded_swagger.html")

    def render_page(
        self, request: HttpRequest, api: Any, **kwargs: Any
    ) -> HttpResponse:
        """Render the Swagger page with branding context."""
        self.settings["url"] = self.get_openapi_url(api, kwargs)
        context = {
            "swagger_settings": json.dumps(self.settings, indent=1),
            "api": api,
            "add_csrf": _csrf_needed(api),
        }

        # Try Django template engine first (supports INSTALLED_APPS override)
        try:
            tpl = get_template(DJANGO_TEMPLATE_NAME)
            return HttpResponse(tpl.render(context, request))
        except TemplateDoesNotExist:
            pass

        # Fallback: load bundled template from filesystem
        content = Path(self.template_cdn).read_text()
        html = Template(content).render(Context(context))
        return HttpResponse(html)
