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
| `inlines` | One `TabularInline`/`StackedInline` per reverse FK/O2O relation (e.g. `Chapter` if it has a FK to `Book`) |
| `filter_horizontal` | One entry per forward `ManyToManyField` declared on `Book` |

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

## Relations: Inlines & M2M Widgets

`@register_admin` / `Model.as_admin()` also inspect the model's Django
relation graph and wire up sensible relation widgets automatically — no
separate `TabularInline` classes to write for the common case.

- **Reverse ForeignKey** → `TabularInline` (a child editable in a table on
  the parent's change page).
- **Reverse OneToOne** → `StackedInline` (a single child form, since there's
  at most one).
- **Forward ManyToManyField** → `filter_horizontal` (Django's dual-list
  widget), unless the field uses a custom `through` model with extra fields
  (Django doesn't support `filter_horizontal` for those, so they're left for
  you to configure explicitly).
- **Reverse ManyToMany** is skipped — there's no owning FK to inline against.

```python
@register_admin
class Book(ModelSerializer):
    author = models.ForeignKey(Author, on_delete=models.CASCADE)
    tags = models.ManyToManyField(Tag)

    class ReadSerializer:
        fields = ["id", "author", "tags"]

@register_admin
class Chapter(ModelSerializer):
    book = models.ForeignKey(Book, on_delete=models.CASCADE, related_name="chapters")
    title = models.CharField(max_length=200)
    number = models.PositiveIntegerField()

    class ReadSerializer:
        fields = ["id", "book", "title", "number"]

    class UpdateSerializer:
        fields = ["title", "number"]
```

Opening `Book` in the admin now shows a `Chapters` inline table (fields
`title`, `number` — taken from `Chapter.UpdateSerializer.fields`, since
that's what should be editable in place) and a dual-list widget for `tags`.
No `admin.py` boilerplate required.

**The inline's field list:**

- Uses the child's `UpdateSerializer.fields` when defined, falling back to
  `CreateSerializer.fields`.
- Always drops the FK field pointing back at the parent (`book` above) — it
  is supplied via Django's inline formset (`fk_name`), so listing it
  explicitly raises a `FieldError`.
- Falls back to Django Admin's own default (all editable fields) for plain
  (non-`ModelSerializer`) child models.

**Overriding:** pass `inlines=(...)` or `filter_horizontal=(...)` like any
other override — it replaces the auto-generated value entirely:

```python
@register_admin(inlines=(MyCustomChapterInline,))
class Book(ModelSerializer): ...

# Disable auto-inlines entirely
@register_admin(inlines=())
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
