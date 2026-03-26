# :material-palette: Swagger UI Branding

Customize the Swagger UI appearance with your own logo, colors, favicon, and CSS — directly from `NinjaAIO`.

---

## Quick Start

```python
from ninja_aio import NinjaAIO, Branding

api = NinjaAIO(
    title="My Company API",
    version="1.0.0",
    branding=Branding(
        logo_url="/static/img/logo.png",
        primary_color="#7c4dff",
        favicon_url="/static/img/favicon.ico",
    ),
)
```

That's it. Visit `/docs` and you'll see your logo in the top bar, your color on buttons and accents, and your favicon in the browser tab.

---

## Configuration

The `Branding` dataclass accepts these options:

| Parameter | Type | Default | Description |
|---|---|---|---|
| `logo_url` | `str \| None` | `None` | URL to a logo image. Replaces the default Swagger logo in the top bar. |
| `primary_color` | `str \| None` | `None` | CSS color for the top bar, authorize button, POST method badge, and scheme container. Any valid CSS color works (`#hex`, `rgb()`, named). |
| `favicon_url` | `str \| None` | `None` | URL to a custom favicon. Replaces the default Django Ninja favicon. |
| `custom_css` | `str \| None` | `None` | Raw CSS injected inline into the page. Use for quick tweaks. |
| `custom_css_url` | `str \| None` | `None` | URL to an external CSS file loaded via `<link>` tag. Better for larger customizations. |

---

## Examples

### Logo only

```python
api = NinjaAIO(
    title="Acme API",
    branding=Branding(logo_url="/static/acme-logo.svg"),
)
```

### Full branding

```python
api = NinjaAIO(
    title="Dashboard API",
    branding=Branding(
        logo_url="/static/logo-white.png",
        primary_color="#1a73e8",
        favicon_url="/static/favicon.svg",
        custom_css="""
            .swagger-ui .info .title { color: #1a73e8; }
            .swagger-ui .topbar { padding: 10px 20px; }
        """,
    ),
)
```

### External CSS file

```python
api = NinjaAIO(
    title="Styled API",
    branding=Branding(
        custom_css_url="/static/css/swagger-custom.css",
    ),
)
```

Where `swagger-custom.css` contains your full CSS overrides:

```css
/* static/css/swagger-custom.css */
.swagger-ui .topbar { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); }
.swagger-ui .info .title { font-family: 'Inter', sans-serif; }
.swagger-ui .opblock-tag { font-size: 1.1em; }
```

### Both inline and file

You can combine `custom_css` (quick tweaks) and `custom_css_url` (full stylesheet):

```python
branding=Branding(
    custom_css_url="/static/css/swagger-base.css",
    custom_css=".swagger-ui .topbar-wrapper img { max-height: 50px; }",
)
```

### Hide the top bar entirely

```python
api = NinjaAIO(
    title="Minimal API",
    branding=Branding(
        custom_css=".swagger-ui .topbar { display: none; }",
    ),
)
```

---

## How It Works

When you pass `branding=` to `NinjaAIO`:

1. The framework automatically uses `BrandedSwagger` instead of the default `Swagger` docs class
2. `BrandedSwagger` renders a custom template that injects your branding as CSS
3. The `api.branding` object is accessible in the template context

If you pass both `docs=` and `branding=`, the explicit `docs=` takes precedence for rendering, but `branding` is still stored on the API instance for template access.

---

## Using with Static Files

For production, serve your logo and favicon via Django's static files:

```python
# settings.py
STATIC_URL = "/static/"

# views.py
api = NinjaAIO(
    title="My API",
    branding=Branding(
        logo_url="/static/img/api-logo.png",
        favicon_url="/static/img/favicon.ico",
    ),
)
```

Or use an external URL:

```python
branding=Branding(
    logo_url="https://cdn.example.com/logo.png",
)
```

---

## CSS Elements Affected by `primary_color`

| Element | CSS Selector |
|---|---|
| Top bar background | `.swagger-ui .topbar` |
| Authorize button | `.swagger-ui .btn.authorize` |
| POST method badge | `.swagger-ui .opblock.opblock-post .opblock-summary-method` |
| Scheme container | `.swagger-ui .scheme-container` |

For other elements, use `custom_css` or `custom_css_url`.

---

## Custom Template

There are three ways to customize the template, from simplest to most flexible:

### Option 1: Override via `INSTALLED_APPS` (recommended)

Add `ninja_aio` to your `INSTALLED_APPS` and create a template with the same name in your project's templates directory:

```python
# settings.py
INSTALLED_APPS = [
    ...
    "ninja_aio",
]
```

```
# Create this file in your project:
templates/ninja_aio/branded_swagger.html
```

Django's template resolution will pick up your version first. Export the default template as a starting point:

```bash
python -c "from ninja_aio.docs import BrandedSwagger; print(open(BrandedSwagger.template_cdn).read())" > templates/ninja_aio/branded_swagger.html
```

### Option 2: Subclass `BrandedSwagger`

If you don't want to use `INSTALLED_APPS`, subclass and point to your own template file:

```python
from ninja_aio.docs import BrandedSwagger

class MySwagger(BrandedSwagger):
    template_cdn = "path/to/my_swagger.html"

api = NinjaAIO(
    title="My API",
    docs=MySwagger(),
    branding=Branding(logo_url="/static/logo.png"),
)
```

To get started, export the default template as a base:

```bash
python -c "from ninja_aio.docs import BrandedSwagger; print(open(BrandedSwagger.template_cdn).read())" > templates/my_swagger.html
```

Then edit `templates/my_swagger.html` to your needs and point to it:

```python
class MySwagger(BrandedSwagger):
    template_cdn = "templates/my_swagger.html"
```

Your template has access to:

| Variable | Description |
|---|---|
| `{{ api.title }}` | API title |
| `{{ api.branding.logo_url }}` | Logo URL |
| `{{ api.branding.primary_color }}` | Primary color |
| `{{ api.branding.favicon_url }}` | Favicon URL |
| `{{ api.branding.custom_css }}` | Inline CSS |
| `{{ api.branding.custom_css_url }}` | External CSS URL |
| `{{ swagger_settings \| safe }}` | Swagger UI config JSON |
| `{{ add_csrf }}` | Whether to inject CSRF token |
