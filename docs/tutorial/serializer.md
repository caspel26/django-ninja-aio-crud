<div class="tutorial-hero" markdown>

<span class="step-indicator">Alternative to Step 1</span>

# Define Your Serializer

<p class="tutorial-subtitle">
Use Meta-driven <code>Serializer</code> to add API functionality to existing Django models without changing their base class.
</p>

</div>

<div class="learning-objectives" markdown>

### :material-school: What You'll Learn

- :material-cube-outline: How `Serializer` differs from `ModelSerializer`
- :material-file-document-edit: Defining schemas with `SchemaModelConfig`
- :material-link-variant: Working with relationships via `relations_serializers`
- :material-pencil-plus: Adding custom and computed fields
- :material-database-search: Query optimizations with `QuerySet`
- :material-hook: Implementing lifecycle hooks
- :material-view-grid: Connecting to `APIViewSet`

</div>

<div class="prerequisites" markdown>

**Prerequisites** — Make sure you have Django 4.1+ installed, `django-ninja-aio-crud` installed, and a Django project set up.

</div>

!!! tip "When to Use Serializer"
    Choose `Serializer` when you have **existing Django models** you don't want to modify, want to keep models and API concerns **separated**, or when **multiple teams** work on models vs. API layers. If you're starting fresh, consider [ModelSerializer](model.md) instead.

---

## :material-cube-outline: How It Works

With `ModelSerializer`, you embed schema configuration directly on the model. With `Serializer`, your models stay as plain Django models and you define everything in a separate serializer class:

=== "Serializer (separated)"
    ```python
    # models.py — plain Django model
    from django.db import models

    class Article(models.Model):
        title = models.CharField(max_length=200)
        content = models.TextField()
        is_published = models.BooleanField(default=False)
        created_at = models.DateTimeField(auto_now_add=True)

    # serializers.py — API configuration
    from ninja_aio.models import serializers

    class ArticleSerializer(serializers.Serializer):
        class Meta:
            model = Article
            schema_in = serializers.SchemaModelConfig(
                fields=["title", "content"]
            )
            schema_out = serializers.SchemaModelConfig(
                fields=["id", "title", "content", "is_published", "created_at"]
            )
    ```

=== "ModelSerializer (embedded)"
    ```python
    # models.py — API config on the model
    from ninja_aio.models import ModelSerializer

    class Article(ModelSerializer):
        title = models.CharField(max_length=200)
        content = models.TextField()
        is_published = models.BooleanField(default=False)
        created_at = models.DateTimeField(auto_now_add=True)

        class ReadSerializer:
            fields = ["id", "title", "content", "is_published", "created_at"]

        class CreateSerializer:
            fields = ["title", "content"]
    ```

---

## :material-file-document-edit: Defining Schemas

The `Serializer` uses a nested `Meta` class with `SchemaModelConfig` to configure each operation:

### Create Schema (`schema_in`)

Defines which fields are accepted when creating an object:

```python
from ninja_aio.models import serializers
from .models import Article


class ArticleSerializer(serializers.Serializer):
    class Meta:
        model = Article
        schema_in = serializers.SchemaModelConfig(
            fields=["title", "content"],
            optionals=[("is_published", bool)],
        )
```

- **`fields`** — required fields for creation
- **`optionals`** — optional fields as `(name, type)` tuples

**Request body:**

```json
{
  "title": "My Article",
  "content": "Content here...",
  "is_published": true  // optional
}
```

### Read Schema (`schema_out`)

Defines which fields appear in list API responses:

```python
class ArticleSerializer(serializers.Serializer):
    class Meta:
        model = Article
        schema_out = serializers.SchemaModelConfig(
            fields=["id", "title", "content", "is_published", "created_at"]
        )
```

**Response:**

```json
{
  "id": 1,
  "title": "My Article",
  "content": "Content here...",
  "is_published": false,
  "created_at": "2024-01-15T10:30:00Z"
}
```

### Detail Schema (`schema_detail`)

Optionally return more fields for the retrieve endpoint than the list endpoint:

```python
class ArticleSerializer(serializers.Serializer):
    class Meta:
        model = Article
        schema_out = serializers.SchemaModelConfig(
            # List view: minimal fields
            fields=["id", "title", "is_published"]
        )
        schema_detail = serializers.SchemaModelConfig(
            # Detail view: all fields
            fields=["id", "title", "content", "is_published", "created_at"],
            customs=[("word_count", int, lambda obj: len(obj.content.split()))]
        )
```

!!! note "Fallback Behavior"
    If `schema_detail` is **not** defined, it falls back to `schema_out`. If `schema_detail` **is** defined, it does **not** inherit from `schema_out` — you must specify all fields explicitly.

### Update Schema (`schema_update`)

Defines which fields can be updated (PATCH):

```python
class ArticleSerializer(serializers.Serializer):
    class Meta:
        model = Article
        schema_update = serializers.SchemaModelConfig(
            optionals=[
                ("title", str),
                ("content", str),
                ("is_published", bool),
            ]
        )
```

**Request body (partial update):**

```json
{
  "title": "Updated Title"
}
```

### Complete Schema Definition

Putting it all together:

```python
from ninja_aio.models import serializers
from .models import Article


class ArticleSerializer(serializers.Serializer):
    class Meta:
        model = Article
        schema_in = serializers.SchemaModelConfig(
            fields=["title", "content"],
            optionals=[("is_published", bool)],
        )
        schema_out = serializers.SchemaModelConfig(
            fields=["id", "title", "content", "is_published", "created_at"]
        )
        schema_update = serializers.SchemaModelConfig(
            optionals=[
                ("title", str),
                ("content", str),
                ("is_published", bool),
            ]
        )
```

---

## :material-link-variant: Working with Relationships

Unlike `ModelSerializer` which auto-resolves nested serializers, `Serializer` requires you to explicitly declare them via `relations_serializers`.

### ForeignKey Relationships

```python
from ninja_aio.models import serializers
from .models import Author, Article


class AuthorSerializer(serializers.Serializer):
    class Meta:
        model = Author
        schema_in = serializers.SchemaModelConfig(
            fields=["name", "email"],
            optionals=[("bio", str)],
        )
        schema_out = serializers.SchemaModelConfig(
            fields=["id", "name", "email", "bio"]
        )
        schema_update = serializers.SchemaModelConfig(
            optionals=[("name", str), ("bio", str)]
        )


class ArticleSerializer(serializers.Serializer):
    class Meta:
        model = Article
        schema_in = serializers.SchemaModelConfig(
            fields=["title", "content", "author"],
        )
        schema_out = serializers.SchemaModelConfig(
            fields=["id", "title", "content", "author", "is_published", "created_at"]
        )
        schema_update = serializers.SchemaModelConfig(
            optionals=[("title", str), ("content", str), ("is_published", bool)]
        )
        # Explicit nested serialization
        relations_serializers = {
            "author": AuthorSerializer,
        }

    class QuerySet:
        read = serializers.ModelQuerySetSchema(
            select_related=["author"]
        )
```

**Response with nested author:**

```json
{
  "id": 1,
  "title": "My Article",
  "content": "Content here...",
  "author": {
    "id": 5,
    "name": "John Doe",
    "email": "john@example.com",
    "bio": "Software developer"
  },
  "is_published": false,
  "created_at": "2024-01-15T10:30:00Z"
}
```

### Reverse Relations

Include reverse relations (e.g., an author's articles) using `relations_serializers`:

```python
class AuthorSerializer(serializers.Serializer):
    class Meta:
        model = Author
        schema_out = serializers.SchemaModelConfig(
            fields=["id", "name", "email", "articles"]  # reverse related name
        )
        relations_serializers = {
            "articles": ArticleSerializer,
        }
```

### String References (Circular Dependencies)

When two serializers reference each other, use string references to avoid import errors:

```python
class AuthorSerializer(serializers.Serializer):
    class Meta:
        model = Author
        schema_out = serializers.SchemaModelConfig(
            fields=["id", "name", "articles"]
        )
        relations_serializers = {
            "articles": "ArticleSerializer",  # String reference
        }


class ArticleSerializer(serializers.Serializer):
    class Meta:
        model = Article
        schema_out = serializers.SchemaModelConfig(
            fields=["id", "title", "author"]
        )
        relations_serializers = {
            "author": "AuthorSerializer",  # Circular reference works!
        }
```

You can also use absolute import paths for cross-module references:

```python
relations_serializers = {
    "author": "users.serializers.UserSerializer",
}
```

### Relations as IDs

For lighter responses, serialize relations as IDs instead of nested objects:

```python
class ArticleSerializer(serializers.Serializer):
    class Meta:
        model = Article
        schema_out = serializers.SchemaModelConfig(
            fields=["id", "title", "author", "tags", "category"]
        )
        relations_serializers = {
            "author": AuthorSerializer,      # Nested object
            "category": CategorySerializer,  # Nested object
        }
        relations_as_id = ["tags"]           # Just IDs
```

**Response:**

```json
{
  "id": 1,
  "title": "My Article",
  "author": {"id": 5, "name": "John Doe", "email": "john@example.com"},
  "category": {"id": 2, "name": "Tutorials", "slug": "tutorials"},
  "tags": [1, 2, 5]
}
```

### ManyToMany Relationships

```python
from .models import Author, Tag, Article


class TagSerializer(serializers.Serializer):
    class Meta:
        model = Tag
        schema_in = serializers.SchemaModelConfig(fields=["name", "slug"])
        schema_out = serializers.SchemaModelConfig(fields=["id", "name", "slug"])


class ArticleSerializer(serializers.Serializer):
    class Meta:
        model = Article
        schema_in = serializers.SchemaModelConfig(
            fields=["title", "content", "author"],
            optionals=[("tags", list[int])],
        )
        schema_out = serializers.SchemaModelConfig(
            fields=["id", "title", "content", "author", "tags", "created_at"]
        )
        relations_serializers = {
            "author": AuthorSerializer,
            "tags": TagSerializer,
        }

    class QuerySet:
        read = serializers.ModelQuerySetSchema(
            select_related=["author"],
            prefetch_related=["tags"],
        )
```

---

## :material-pencil-plus: Custom and Computed Fields

### Custom Fields in Read Schema

Add computed fields using `customs`:

```python
class ArticleSerializer(serializers.Serializer):
    class Meta:
        model = Article
        schema_out = serializers.SchemaModelConfig(
            fields=["id", "title", "content", "views", "created_at"],
            customs=[
                ("word_count", int, lambda obj: len(obj.content.split())),
                ("reading_time", int, lambda obj: max(1, len(obj.content.split()) // 200)),
            ]
        )
```

### Inline Custom Fields

You can also define custom fields directly in the `fields` list as tuples:

```python
class ArticleSerializer(serializers.Serializer):
    class Meta:
        model = Article
        schema_out = serializers.SchemaModelConfig(
            fields=[
                "id",
                "title",
                ("word_count", int, 0),       # 3-tuple: (name, type, default)
                ("is_featured", bool),          # 2-tuple: (name, type) — required
            ]
        )
```

### Custom Fields in Create Schema

Use `customs` for instruction flags that aren't stored in the database:

```python
class ArticleSerializer(serializers.Serializer):
    class Meta:
        model = Article
        schema_in = serializers.SchemaModelConfig(
            fields=["title", "content", "author"],
            customs=[
                ("notify_subscribers", bool, True),
                ("schedule_publish", str, None),
            ],
        )
```

These are passed to the `custom_actions()` hook.

---

## :material-database-search: Query Optimizations

Configure `select_related` / `prefetch_related` for automatic optimization:

```python
from ninja_aio.schemas.helpers import ModelQuerySetSchema, ModelQuerySetExtraSchema


class ArticleSerializer(serializers.Serializer):
    class Meta:
        model = Article
        schema_out = serializers.SchemaModelConfig(
            fields=["id", "title", "author", "category"]
        )
        schema_detail = serializers.SchemaModelConfig(
            fields=["id", "title", "content", "author", "category", "tags", "comments"]
        )

    class QuerySet:
        read = ModelQuerySetSchema(
            select_related=["author", "category"],
            prefetch_related=["tags"],
        )
        detail = ModelQuerySetSchema(
            select_related=["author", "category"],
            prefetch_related=["tags", "comments", "comments__author"],
        )
        queryset_request = ModelQuerySetSchema(
            select_related=[],
            prefetch_related=["comments"],
        )
        extras = [
            ModelQuerySetExtraSchema(
                scope="cards",
                select_related=["author"],
                prefetch_related=[],
            )
        ]
```

- **`read`** — applied to list operations
- **`detail`** — applied to retrieve operations (falls back to `read` if not defined)
- **`queryset_request`** — applied inside the `queryset_request` hook
- **`extras`** — named scopes available via `QueryUtil.SCOPES`

---

## :material-hook: Lifecycle Hooks

`Serializer` supports the same hooks as `ModelSerializer`, with one key difference: **all hooks receive an `instance` parameter** instead of using `self`:

```python
class ArticleSerializer(serializers.Serializer):
    class Meta:
        model = Article
        schema_in = serializers.SchemaModelConfig(
            fields=["title", "content", "author"],
            customs=[("notify_author", bool, True)],
        )
        schema_out = serializers.SchemaModelConfig(
            fields=["id", "title", "content", "author"]
        )

    @classmethod
    async def queryset_request(cls, request):
        """Filter and optimize queryset per request."""
        return cls._meta.model.objects.select_related("author")

    async def custom_actions(self, payload, instance):
        """Execute after field assignment, before save."""
        if payload.get("notify_author"):
            await send_email(instance.author.email, f"Article created: {instance.title}")

    async def post_create(self, instance):
        """Execute after instance creation."""
        await AuditLog.objects.acreate(
            action="article_created",
            article_id=instance.id
        )

    def before_save(self, instance):
        """Sync hook before any save."""
        from django.utils.text import slugify
        instance.slug = slugify(instance.title)

    def after_save(self, instance):
        """Sync hook after any save."""
        from django.core.cache import cache
        cache.delete(f"article:{instance.id}")

    def on_create_before_save(self, instance):
        """Sync hook before creation save only."""
        print(f"Creating: {instance.title}")

    def on_create_after_save(self, instance):
        """Sync hook after creation save only."""
        print(f"Created with ID: {instance.id}")

    def on_delete(self, instance):
        """Sync hook after deletion."""
        print(f"Deleted: {instance.title}")
```

### Available Hooks

| Hook                             | Type  | When Called               | Parameters              |
| -------------------------------- | ----- | ------------------------- | ----------------------- |
| `queryset_request(request)`      | async | Before queryset building  | `request`               |
| `custom_actions(payload, i)`     | async | After field assignment    | `payload`, `instance`   |
| `post_create(instance)`          | async | After first save          | `instance`              |
| `before_save(instance)`          | sync  | Before any save           | `instance`              |
| `after_save(instance)`           | sync  | After any save            | `instance`              |
| `on_create_before_save(i)`       | sync  | Before creation save only | `instance`              |
| `on_create_after_save(i)`        | sync  | After creation save only  | `instance`              |
| `on_delete(instance)`            | sync  | After deletion            | `instance`              |

!!! warning "Execution Order"
    **Create**: `on_create_before_save()` → `before_save()` → `save()` → `on_create_after_save()` → `after_save()` → `custom_actions()` → `post_create()`

    **Update**: `before_save()` → `save()` → `after_save()` → `custom_actions()`

---

## :material-view-grid: Connecting to APIViewSet

Attach your serializer to a ViewSet using `serializer_class`:

```python
# views.py
from ninja_aio import NinjaAIO
from ninja_aio.views import APIViewSet
from .models import Article, Author, Tag
from .serializers import ArticleSerializer, AuthorSerializer, TagSerializer

api = NinjaAIO(title="Blog API", version="1.0.0")


@api.viewset(model=Article)
class ArticleViewSet(APIViewSet):
    serializer_class = ArticleSerializer


@api.viewset(model=Author)
class AuthorViewSet(APIViewSet):
    serializer_class = AuthorSerializer


@api.viewset(model=Tag)
class TagViewSet(APIViewSet):
    serializer_class = TagSerializer
```

That's it — full CRUD endpoints are generated automatically, using your serializer's schemas, query optimizations, and lifecycle hooks.

---

## :material-code-braces: Complete Example

Here's a full example with models, serializers, and views:

??? example "Complete blog API with Serializer (click to expand)"

    ```python
    # models.py
    from django.db import models


    class Author(models.Model):
        name = models.CharField(max_length=200)
        email = models.EmailField(unique=True)
        bio = models.TextField(blank=True)

        class Meta:
            ordering = ["name"]

        def __str__(self):
            return self.name


    class Category(models.Model):
        name = models.CharField(max_length=100)
        slug = models.SlugField(unique=True)

        def __str__(self):
            return self.name


    class Tag(models.Model):
        name = models.CharField(max_length=50, unique=True)

        def __str__(self):
            return self.name


    class Article(models.Model):
        title = models.CharField(max_length=200)
        slug = models.SlugField(unique=True, blank=True)
        content = models.TextField()
        author = models.ForeignKey(Author, on_delete=models.CASCADE, related_name="articles")
        category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True)
        tags = models.ManyToManyField(Tag, related_name="articles", blank=True)
        is_published = models.BooleanField(default=False)
        views = models.IntegerField(default=0)
        created_at = models.DateTimeField(auto_now_add=True)

        class Meta:
            ordering = ["-created_at"]

        def __str__(self):
            return self.title
    ```

    ```python
    # serializers.py
    from ninja_aio.models import serializers
    from ninja_aio.schemas.helpers import ModelQuerySetSchema
    from django.utils.text import slugify
    from .models import Author, Category, Tag, Article


    class AuthorSerializer(serializers.Serializer):
        class Meta:
            model = Author
            schema_in = serializers.SchemaModelConfig(
                fields=["name", "email"],
                optionals=[("bio", str)],
            )
            schema_out = serializers.SchemaModelConfig(
                fields=["id", "name", "email", "bio"]
            )
            schema_update = serializers.SchemaModelConfig(
                optionals=[("name", str), ("bio", str)]
            )


    class CategorySerializer(serializers.Serializer):
        class Meta:
            model = Category
            schema_in = serializers.SchemaModelConfig(fields=["name", "slug"])
            schema_out = serializers.SchemaModelConfig(fields=["id", "name", "slug"])


    class TagSerializer(serializers.Serializer):
        class Meta:
            model = Tag
            schema_in = serializers.SchemaModelConfig(fields=["name"])
            schema_out = serializers.SchemaModelConfig(fields=["id", "name"])


    class ArticleSerializer(serializers.Serializer):
        class Meta:
            model = Article
            schema_in = serializers.SchemaModelConfig(
                fields=["title", "content", "author", "category"],
                optionals=[
                    ("tags", list[int]),
                    ("is_published", bool),
                ],
                customs=[("notify_subscribers", bool, True)],
            )
            schema_out = serializers.SchemaModelConfig(
                fields=[
                    "id", "title", "slug", "content",
                    "author", "category", "tags",
                    "is_published", "views", "created_at",
                ],
                customs=[
                    ("word_count", int, lambda obj: len(obj.content.split())),
                    ("reading_time", int, lambda obj: max(1, len(obj.content.split()) // 200)),
                ]
            )
            schema_update = serializers.SchemaModelConfig(
                optionals=[
                    ("title", str),
                    ("content", str),
                    ("category", int),
                    ("tags", list[int]),
                    ("is_published", bool),
                ]
            )
            relations_serializers = {
                "author": AuthorSerializer,
                "category": CategorySerializer,
                "tags": TagSerializer,
            }

        class QuerySet:
            read = ModelQuerySetSchema(
                select_related=["author", "category"],
                prefetch_related=["tags"],
            )

        def before_save(self, instance):
            if not instance.slug:
                instance.slug = slugify(instance.title)

        async def custom_actions(self, payload, instance):
            if payload.get("notify_subscribers"):
                # Implement your notification logic
                pass

        async def post_create(self, instance):
            print(f"Article created: {instance.title}")
    ```

    ```python
    # views.py
    from ninja_aio import NinjaAIO
    from ninja_aio.views import APIViewSet
    from .models import Article, Author, Category, Tag
    from .serializers import (
        ArticleSerializer, AuthorSerializer,
        CategorySerializer, TagSerializer,
    )

    api = NinjaAIO(title="Blog API", version="1.0.0")


    @api.viewset(model=Author)
    class AuthorViewSet(APIViewSet):
        serializer_class = AuthorSerializer


    @api.viewset(model=Category)
    class CategoryViewSet(APIViewSet):
        serializer_class = CategorySerializer


    @api.viewset(model=Tag)
    class TagViewSet(APIViewSet):
        serializer_class = TagSerializer


    @api.viewset(model=Article)
    class ArticleViewSet(APIViewSet):
        serializer_class = ArticleSerializer
    ```

---

## :material-scale-balance: Serializer vs. ModelSerializer

| Feature                  | ModelSerializer                     | Serializer                                    |
| ------------------------ | ----------------------------------- | --------------------------------------------- |
| Model class              | Custom base class                   | Plain Django model                            |
| Configuration            | Nested classes on model             | Separate `Meta` class                         |
| Lifecycle hooks          | Instance methods (`self`)           | Receives `instance` parameter                 |
| Relation serializers     | Auto-resolved                       | Explicit via `relations_serializers`           |
| Best for                 | New projects                        | Existing projects                             |

Both approaches fully support nested relations, query optimization, lifecycle hooks, and `APIViewSet` integration.

---

<div class="next-step" markdown>

**Ready to build your API?**

Now continue with CRUD views, authentication, and filtering — they work the same way!

[Step 2: Create CRUD Views :material-arrow-right:](crud.md){ .md-button .md-button--primary }

</div>

<div class="summary-checklist" markdown>

### :material-check-all: What You've Learned

- :material-check: Creating serializers with `SchemaModelConfig`
- :material-check: Defining create, read, detail, and update schemas
- :material-check: Working with ForeignKey, M2M, and reverse relations
- :material-check: Adding custom computed fields
- :material-check: Configuring query optimizations
- :material-check: Implementing lifecycle hooks with `instance` parameter
- :material-check: Connecting serializers to `APIViewSet`

</div>

<div class="grid cards" markdown>

-   :material-book-open-variant:{ .lg .middle } **API Reference**

    ---

    [:octicons-arrow-right-24: Serializer](../api/models/serializers.md) &middot; [:octicons-arrow-right-24: APIViewSet](../api/views/api_view_set.md)

</div>
