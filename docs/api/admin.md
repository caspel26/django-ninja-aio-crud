# :material-shield-account: Auto Admin

Auto-generate Django Admin configuration from your `ModelSerializer` field definitions — zero extra boilerplate.

---

## Quick Start

### Option 1: `@register_admin` decorator

```python
from ninja_aio.admin import register_admin
from ninja_aio.models import ModelSerializer

@register_admin
class Book(ModelSerializer):
    title = models.CharField(max_length=200)
    author = models.ForeignKey(Author, on_delete=models.CASCADE)
    published = models.DateField()
    synopsis = models.TextField(blank=True)

    class ReadSerializer:
        fields = ["id", "title", "author", "published", "synopsis"]

    class UpdateSerializer:
        fields = ["title", "synopsis"]
```

This auto-generates:

| Admin attribute | Generated value |
|----------------|----------------|
| `list_display` | `("id", "title", "author", "published", "synopsis")` |
| `search_fields` | `("title", "synopsis")` |
| `list_filter` | `("author", "published")` |
| `readonly_fields` | `("author", "published")` |

### Option 2: `Model.as_admin()`

```python
# admin.py
from django.contrib import admin
from myapp.models import Book

admin.site.register(Book, Book.as_admin())
```

---

## Customization

Both approaches accept keyword overrides:

```python
# Via decorator
@register_admin(list_per_page=50, ordering=["-published"])
class Book(ModelSerializer): ...

# Via as_admin()
admin.site.register(Book, Book.as_admin(list_per_page=50))
```

Override any auto-generated attribute:

```python
@register_admin(
    list_display=("title", "author"),  # Override auto list_display
    search_fields=("title", "author__name"),  # Add relation search
)
class Book(ModelSerializer): ...
```

---

## Custom Admin Site

```python
from django.contrib.admin import AdminSite

custom_site = AdminSite(name="custom")

@register_admin(site=custom_site)
class Book(ModelSerializer): ...

# or
custom_site.register(Book, Book.as_admin())
```

---

## Field Classification Rules

| Django Field Type | `list_display` | `search_fields` | `list_filter` | `readonly_fields` |
|---|:---:|:---:|:---:|:---:|
| CharField, TextField, SlugField, EmailField | Yes | Yes | — | If not in UpdateSerializer |
| IntegerField, FloatField, DecimalField | Yes | — | — | If not in UpdateSerializer |
| BooleanField | Yes | — | Yes | If not in UpdateSerializer |
| DateField, DateTimeField | Yes | — | Yes | If not in UpdateSerializer |
| ForeignKey, OneToOneField | Yes | — | Yes | If not in UpdateSerializer |
| ManyToManyField | — | — | Yes | — |
| Field with choices | Yes | — | Yes | If not in UpdateSerializer |
| Custom/computed field | Yes | — | — | Always |

---

## API Reference

### `register_admin(model=None, *, site=None, **overrides)`

Decorator to auto-register a ModelSerializer in Django Admin.

**Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `site` | `AdminSite` | `admin.site` | Admin site to register on |
| `**overrides` | `Any` | — | Override any ModelAdmin attribute |

### `model_admin_factory(model, **overrides) -> type[ModelAdmin]`

Create a `ModelAdmin` class without registering it.

```python
from ninja_aio.admin import model_admin_factory

BookAdmin = model_admin_factory(Book, list_per_page=25)
admin.site.register(Book, BookAdmin)
```

### `ModelSerializer.as_admin(**overrides) -> type[ModelAdmin]`

Classmethod on any ModelSerializer subclass. Equivalent to `model_admin_factory(cls, **overrides)`.
