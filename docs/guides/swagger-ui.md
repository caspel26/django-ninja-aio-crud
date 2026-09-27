---
type: guide
title: Swagger UI
description: Configure, hide, protect and brand the interactive API docs, and describe each endpoint.
---

# Swagger UI

Your API comes with interactive docs at `/api/docs`. This page shows how to
set the title, hide or protect the docs, add your brand, and describe each
endpoint.

## Set the title and URLs

```python title="blog/api.py"
from ninja_aio import NinjaAIO

api = NinjaAIO(
    title="Blog API",
    version="1.0.0",
    description="Articles and categories of the blog.",
    docs_url="/docs",
    openapi_url="/openapi.json",
)
```

| Argument | Default | What it does |
| --- | --- | --- |
| `title` | `"NinjaAPI"` | The name shown at the top of the docs |
| `version` | `"1.0.0"` | The API version shown next to the title |
| `description` | `""` | Text shown under the title. Markdown works |
| `docs_url` | `"/docs"` | Where the Swagger UI page lives |
| `openapi_url` | `"/openapi.json"` | Where the OpenAPI schema lives |
| `docs_decorator` | `None` | A decorator for the docs page and the schema |

Both URLs are relative to where you mount the API, like `/api/docs`.

## Hide or protect the docs

Set `docs_url=None` to remove the Swagger UI page. The schema at
`/api/openapi.json` stays:

```python
api = NinjaAIO(title="Blog API", docs_url=None)
```

Set `openapi_url=None` to remove both the schema and the docs page.

To show the docs to staff only, pass a decorator. It protects the docs page
and the schema:

```python title="blog/api.py"
from django.contrib.admin.views.decorators import staff_member_required

api = NinjaAIO(title="Blog API", docs_decorator=staff_member_required)
```

## Add your brand

Pass a `Branding` to show your logo, color and favicon:

```python title="blog/api.py"
from ninja_aio import NinjaAIO
from ninja_aio.docs import Branding

api = NinjaAIO(
    title="Blog API",
    branding=Branding(
        logo_url="/static/blog/logo.svg",
        primary_color="#1a73e8",
        favicon_url="/static/blog/favicon.ico",
    ),
)
```

| Field | What it does |
| --- | --- |
| `logo_url` | Shows this image and the API title in the top bar |
| `primary_color` | Any CSS color. Used for the top bar, the Authorize button and `POST` badges |
| `favicon_url` | The icon in the browser tab |
| `custom_css` | CSS added inline to the page |
| `custom_css_url` | A stylesheet loaded with a `<link>` tag |

All fields are optional. Use `custom_css` for small changes and
`custom_css_url` for a full stylesheet:

```python
Branding(
    custom_css_url="/static/blog/swagger.css",
    custom_css=".swagger-ui .topbar { padding: 10px 20px; }",
)
```

When you also pass `docs=`, your docs class is used and `branding` has no
effect on the page.

!!! deprecated "Deprecated in 3.0"

    `from ninja_aio import Branding` still works but is deprecated. Import it from `ninja_aio.docs`.

## Override the template

With `branding` set, the page is rendered from the Django template
`ninja_aio/branded_swagger.html`. Copy the default one to start from:

```bash
mkdir -p templates/ninja_aio
python -c "from ninja_aio.docs import BrandedSwagger; print(open(BrandedSwagger.template_cdn).read())" > templates/ninja_aio/branded_swagger.html
```

Put the file where Django finds it first:

- In a folder listed in `TEMPLATES["DIRS"]`, like `templates/ninja_aio/branded_swagger.html`.
- Or in `blog/templates/ninja_aio/branded_swagger.html`, with `APP_DIRS`
  on. If `"ninja_aio"` is in `INSTALLED_APPS`, list `"blog"` before it.

```python title="settings.py"
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        # ...
    },
]
```

When Django finds no template, the bundled one is used.

The template gets these variables:

| Variable | What it holds |
| --- | --- |
| `api` | Your `NinjaAIO`, with `api.title` and `api.branding` |
| `swagger_settings` | The Swagger UI settings as JSON |
| `add_csrf` | Whether to send the CSRF token with requests |

## Describe viewset endpoints

Each generated endpoint gets a summary like "List Articles" or "Create
Article". Set the description with class attributes:

```python title="blog/api.py"
@api.viewset(model=Article, prefix="articles", tags=["Articles"])
class ArticleViewSet(APIViewSet):
    list_docs = "List the articles, newest first."
    create_docs = "Write a new article. It starts as a draft."
    retrieve_docs = "Get one article with its body."
    update_docs = "Change the title, body or status of an article."
    delete_docs = "Delete an article."
```

| Attribute | Endpoint |
| --- | --- |
| `list_docs` | `GET /api/articles` |
| `create_docs` | `POST /api/articles/` |
| `retrieve_docs` | `GET /api/articles/{id}` |
| `update_docs` | `PATCH /api/articles/{id}/` |
| `delete_docs` | `DELETE /api/articles/{id}/` |
| `bulk_create_docs`, `bulk_update_docs`, `bulk_delete_docs` | The bulk endpoints |

`tags` groups the endpoints in the docs. Without it, the tag is the verbose
name of the model. The names in summaries come from
`model_verbose_name` and `model_verbose_name_plural`. See
[Viewsets](viewsets.md).

## Describe custom actions

Pass the docs options to `@action` or `@on`:

```python title="blog/api.py"
@api.viewset(model=Article, prefix="articles", tags=["Articles"])
class ArticleViewSet(APIViewSet):
    @on(
        "publish",
        summary="Publish an article",
        description="Makes the article visible to readers.",
        tags=["Publishing"],
    )
    async def publish(self, request, obj):
        obj.is_published = True
        await obj.asave()
        return {"published": obj.pk}

    @action(detail=False, url_path="legacy-stats", deprecated=True)
    async def legacy_stats(self, request):
        return {"count": await Article.objects.acount()}

    @action(detail=False, url_path="internal", include_in_schema=False)
    async def internal(self, request):
        return {"ok": True}
```

| Option | What it does |
| --- | --- |
| `summary` | The short title. Defaults to the method and name, like "POST Publish Article" |
| `description` | The longer text |
| `tags` | The tags. Defaults to the viewset tags |
| `deprecated` | Shows the endpoint as deprecated |
| `include_in_schema` | Set `False` to hide the endpoint from the docs. It still works |
| `openapi_extra` | Extra OpenAPI data merged into the operation |

See [Custom actions](custom-actions.md).

## See also

- [Viewsets](viewsets.md)
- [Custom actions](custom-actions.md)
- [Deployment](../deployment.md)
- [APIViewSet reference](../api/views/api_view_set.md)
