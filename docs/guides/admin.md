---
type: guide
title: Django admin
description: Register your models in the Django admin with options built from their Schemas.
---

# Django admin

Register a `ModelSerializer` in the Django admin with one decorator. The list
columns, search, filters, read-only fields and inlines come from its Schemas.

## Register a model

Add `@register_admin` above the model:

```python title="blog/models.py"
from django.db import models

from ninja_aio import ModelSerializer, SchemaConfig
from ninja_aio.admin import register_admin


@register_admin
class Article(ModelSerializer):
    title = models.CharField(max_length=200)
    body = models.TextField()
    is_published = models.BooleanField(default=False)
    views = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    category = models.ForeignKey(
        Category, on_delete=models.CASCADE, related_name="articles"
    )

    class Schemas:
        create = SchemaConfig(fields=["title", "body", "category"])
        read = SchemaConfig(
            fields=["id", "title", "is_published", "views", "created_at", "category"]
        )
        update = SchemaConfig(
            optionals=[("title", str), ("body", str), ("is_published", bool)]
        )
```

The article now shows up in the admin. You need `django.contrib.admin` in
`INSTALLED_APPS` and the admin URLs, as in any Django project.

!!! deprecated "Deprecated in 3.0"

    `from ninja_aio import register_admin` still works but is deprecated. Import it from `ninja_aio.admin`.

## Know what is generated

| Option | Built from |
| --- | --- |
| `list_display` | The `read` fields and customs. Many-to-many and reverse relations are left out |
| `search_fields` | Text fields in `read`: `CharField`, `TextField`, `SlugField`, `EmailField`, `URLField` |
| `list_filter` | Fields in `read` that are boolean, date, datetime, foreign key, one-to-one, many-to-many or have `choices` |
| `readonly_fields` | Fields in `read` that are not in the `fields` of `update`, and all customs. The primary key is never read-only |
| `inlines` | Every model with a foreign key to this one. One-to-one relations use a stacked inline, the others a tabular inline |
| `filter_horizontal` | Many-to-many fields declared on this model |

The `detail` schema is not used. For the `Article` above you get:

| Option | Value |
| --- | --- |
| `list_display` | `id`, `title`, `is_published`, `views`, `created_at`, `category` |
| `search_fields` | `title` |
| `list_filter` | `is_published`, `created_at`, `category` |
| `readonly_fields` | `title`, `is_published`, `views`, `created_at`, `category` |

Fields declared in `update` `optionals` are read-only in the admin. Pass
`readonly_fields` to make them editable, see below.

### Inlines

When you register `Category` too, its page gets an inline with its articles.
When the child model is a
`ModelSerializer`, the inline shows its `update` fields, or its `create` fields
if `update` has none. The foreign key back to the parent is hidden. Plain
Django models show all their editable fields.

## Override options

Pass any `ModelAdmin` option to the decorator. It replaces the generated
value:

```python title="blog/models.py"
@register_admin(
    list_per_page=50,
    readonly_fields=("views", "created_at"),
    list_filter=("is_published",),
)
class Article(ModelSerializer):
    ...
```

Use `inlines=()` or `filter_horizontal=()` to turn those off.

## Register on your own admin site

Pass `site` to register on a custom `AdminSite` instead of `admin.site`:

```python title="blog/admin.py"
from django.contrib.admin import AdminSite


class BlogAdminSite(AdminSite):
    site_header = "Blog admin"


blog_admin = BlogAdminSite(name="blog_admin")
```

```python title="blog/models.py"
from .admin import blog_admin


@register_admin(site=blog_admin)
class Article(ModelSerializer):
    ...
```

You can also call it as a function, for example in `admin.py`:

```python title="blog/admin.py"
from ninja_aio.admin import register_admin

from .models import Article

register_admin(Article, site=blog_admin, list_per_page=50)
```

## Build the ModelAdmin yourself

`as_admin()` returns the generated `ModelAdmin` class without registering it.
It takes the same overrides:

```python title="blog/admin.py"
from django.contrib import admin

from .models import Article

admin.site.register(Article, Article.as_admin(list_per_page=50))
```

Subclass it to add methods or actions:

```python title="blog/admin.py"
@admin.register(Article)
class ArticleAdmin(Article.as_admin()):
    actions = ["publish"]

    @admin.action(description="Publish selected articles")
    def publish(self, request, queryset):
        queryset.update(is_published=True)
```

## Use the admin with a Serializer

`register_admin` and `as_admin()` work only with `ModelSerializer`. For a
model described by a `Serializer`, write a regular `ModelAdmin`:

```python title="blog/admin.py"
from django.contrib import admin

from .models import Article


@admin.register(Article)
class ArticleAdmin(admin.ModelAdmin):
    list_display = ("id", "title", "is_published")
    search_fields = ("title",)
```

## See also

- [Schemas](schemas.md)
- [Relations](relations.md)
- [Define your model](../tutorial/model.md)
- [ModelSerializer reference](../api/models/model_serializer.md)
