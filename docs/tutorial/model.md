# Step 1: Define Your Model

In this first step, you'll learn how to define Django models using `ModelSerializer`, which allows you to declare schemas directly on your models.

## What You'll Learn

- How to create a model with `ModelSerializer`
- Defining serialization schemas (Create, Read, Update)
- Working with relationships
- Adding custom fields
- Implementing lifecycle hooks

## Prerequisites

Make sure you have:

- Django 4.1+ installed
- `django-ninja-aio-crud` installed
- A Django project set up

## Basic Model Definition

Let's create a simple blog article model:

```python
# models.py
from django.db import models
from ninja_aio.models import ModelSerializer


class Article(ModelSerializer):
    title = models.CharField(max_length=200)
    content = models.TextField()
    is_published = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.title
```

!!! tip "Why ModelSerializer?"
`ModelSerializer` is a powerful mixin that combines Django's `Model` with automatic schema generation capabilities. Instead of creating separate serializer classes, you define everything on the model itself.

## Adding Serializer Classes

Now let's add serialization schemas to control which fields are exposed in different operations:

### ReadSerializer

Defines which fields appear in API responses:

```python
class Article(ModelSerializer):
    title = models.CharField(max_length=200)
    content = models.TextField()
    is_published = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class ReadSerializer:
        fields = ["id", "title", "content", "is_published", "created_at", "updated_at"]

    def __str__(self):
        return self.title
```

**Result**: When you retrieve an article, the API will return:

```json
{
  "id": 1,
  "title": "Getting Started with Django",
  "content": "In this article...",
  "is_published": true,
  "created_at": "2024-01-15T10:30:00Z",
  "updated_at": "2024-01-15T11:00:00Z"
}
```

### CreateSerializer

Defines which fields are required/allowed when creating:

```python
class Article(ModelSerializer):
    title = models.CharField(max_length=200)
    content = models.TextField()
    is_published = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class ReadSerializer:
        fields = ["id", "title", "content", "is_published", "created_at", "updated_at"]

    class CreateSerializer:
        fields = ["title", "content"]
        optionals = [
            ("is_published", bool),
        ]

    def __str__(self):
        return self.title
```

**Usage**: When creating an article:

```json
// Required fields
{
  "title": "My New Article",
  "content": "Article content here..."
}

// With optional field
{
  "title": "My New Article",
  "content": "Article content here...",
  "is_published": true
}
```

!!! note "Auto-generated Fields"
Fields like `id`, `created_at`, and `updated_at` are automatically handled by Django and shouldn't be in `CreateSerializer.fields`.

### UpdateSerializer

Defines which fields can be updated (usually all optional for PATCH):

```python
class Article(ModelSerializer):
    title = models.CharField(max_length=200)
    content = models.TextField()
    is_published = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class ReadSerializer:
        fields = ["id", "title", "content", "is_published", "created_at", "updated_at"]

    class CreateSerializer:
        fields = ["title", "content"]
        optionals = [("is_published", bool)]

    class UpdateSerializer:
        optionals = [
            ("title", str),
            ("content", str),
            ("is_published", bool),
        ]
        excludes = ["created_at", "updated_at"]

    def __str__(self):
        return self.title
```

**Usage**: Partial update (PATCH):

```json
// Update only title
{
  "title": "Updated Title"
}

// Update multiple fields
{
  "title": "Updated Title",
  "is_published": true
}
```

## Working with Relationships

### ForeignKey Relationships

Let's add an author to our articles:

```python
class Author(ModelSerializer):
    name = models.CharField(max_length=200)
    email = models.EmailField(unique=True)
    bio = models.TextField(blank=True)

    class ReadSerializer:
        fields = ["id", "name", "email", "bio"]

    class CreateSerializer:
        fields = ["name", "email"]
        optionals = [("bio", str)]

    class UpdateSerializer:
        optionals = [
            ("name", str),
            ("email", str),
            ("bio", str),
        ]

    def __str__(self):
        return self.name


class Article(ModelSerializer):
    title = models.CharField(max_length=200)
    content = models.TextField()
    author = models.ForeignKey(Author, on_delete=models.CASCADE, related_name="articles")
    is_published = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class ReadSerializer:
        fields = ["id", "title", "content", "author", "is_published", "created_at"]

    class CreateSerializer:
        fields = ["title", "content", "author"]
        optionals = [("is_published", bool)]

    class UpdateSerializer:
        optionals = [
            ("title", str),
            ("content", str),
            ("is_published", bool),
        ]
        excludes = ["author"]  # Can't change author after creation

    def __str__(self):
        return self.title
```

**Creating an article with author:**

```json
{
  "title": "My Article",
  "content": "Content here...",
  "author": 5 // Author ID
}
```

**Response includes nested author data:**

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

!!! tip "Automatic Nested Serialization"
When `Author` is also a `ModelSerializer`, Django Ninja Aio CRUD automatically serializes it in the response!

### ManyToMany Relationships

Let's add tags to articles:

```python
class Tag(ModelSerializer):
    name = models.CharField(max_length=50, unique=True)
    slug = models.SlugField(unique=True)

    class ReadSerializer:
        fields = ["id", "name", "slug"]

    class CreateSerializer:
        fields = ["name", "slug"]

    def __str__(self):
        return self.name


class Article(ModelSerializer):
    title = models.CharField(max_length=200)
    content = models.TextField()
    author = models.ForeignKey(Author, on_delete=models.CASCADE, related_name="articles")
    tags = models.ManyToManyField(Tag, related_name="articles", blank=True)
    is_published = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class ReadSerializer:
        fields = ["id", "title", "content", "author", "tags", "is_published", "created_at"]

    class CreateSerializer:
        fields = ["title", "content", "author"]
        optionals = [
            ("is_published", bool),
            ("tags", list[int]),  # List of tag IDs
        ]

    class UpdateSerializer:
        optionals = [
            ("title", str),
            ("content", str),
            ("is_published", bool),
            ("tags", list[int]),
        ]

    def __str__(self):
        return self.title
```

**Creating with tags:**

```json
{
  "title": "My Article",
  "content": "Content...",
  "author": 5,
  "tags": [1, 2, 3] // Tag IDs
}
```

**Response:**

```json
{
  "id": 1,
  "title": "My Article",
  "content": "Content...",
  "author": {...},
  "tags": [
    {"id": 1, "name": "python", "slug": "python"},
    {"id": 2, "name": "django", "slug": "django"},
    {"id": 3, "name": "tutorial", "slug": "tutorial"}
  ],
  "is_published": false,
  "created_at": "2024-01-15T10:30:00Z"
}
```

## Adding Custom Fields

Sometimes you need computed or synthetic fields in your API responses:

```python
class Article(ModelSerializer):
    title = models.CharField(max_length=200)
    content = models.TextField()
    author = models.ForeignKey(Author, on_delete=models.CASCADE, related_name="articles")
    views = models.IntegerField(default=0)
    is_published = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class ReadSerializer:
        fields = ["id", "title", "content", "author", "views", "is_published", "created_at"]
        customs = [
            ("word_count", int, lambda obj: len(obj.content.split())),
            ("reading_time", int, lambda obj: len(obj.content.split()) // 200),  # Assume 200 words/min
            ("author_name", str, lambda obj: obj.author.name),
        ]

    class CreateSerializer:
        fields = ["title", "content", "author"]
        customs = [
            ("notify_subscribers", bool, True),  # Custom action flag
            ("schedule_publish", str, None),  # ISO datetime string
        ]

    def __str__(self):
        return self.title
```

**Response with custom fields:**

```json
{
  "id": 1,
  "title": "My Article",
  "content": "...",
  "author": {...},
  "views": 150,
  "is_published": true,
  "created_at": "2024-01-15T10:30:00Z",
  "word_count": 842,
  "reading_time": 4,
  "author_name": "John Doe"
}
```

!!! info "Custom Fields in CreateSerializer"
Custom fields in `CreateSerializer` are used for **instructions** (like flags or metadata), not stored in the database. They're passed to `custom_actions()` hook.

## Query optimizations (QuerySet)

Configure select_related/prefetch_related for read and queryset_request hooks:

```python
from ninja_aio.schemas.helpers import ModelQuerySetSchema, ModelQuerySetExtraSchema

class Article(ModelSerializer):
    # ...existing fields...

    class QuerySet:
        read = ModelQuerySetSchema(
            select_related=["author", "category"],
            prefetch_related=["tags"],
        )
        queryset_request = ModelQuerySetSchema(
            select_related=[],
            prefetch_related=["tags"],
        )
        extras = [
            ModelQuerySetExtraSchema(
                scope="cards",
                select_related=["author"],
                prefetch_related=[],
            )
        ]
```

Use the QueryUtil for custom scopes:

```python
qs = Article.query_util.apply_queryset_optimizations(
    Article.objects.all(),
    Article.query_util.SCOPES.cards,  # from extras
)
```

## Fetch and serialize with ModelUtil

```python
from ninja_aio.models import ModelUtil
from ninja_aio.schemas.helpers import ObjectsQuerySchema, ObjectQuerySchema

util = ModelUtil(Article)

# List published with default read optimizations
items = await util.list_read_s(
    Article.generate_read_s(),
    request,
    query_data=ObjectsQuerySchema(filters={"is_published": True}),
    is_for_read=True,
)

# Retrieve by slug with getters
item = await util.read_s(
    Article.generate_read_s(),
    request,
    query_data=ObjectQuerySchema(getters={"slug": "my-article"}),
    is_for_read=True,
)
```

## Lifecycle Hooks

Add behavior at key points in the model lifecycle:

### Sync Hooks

```python
class Article(ModelSerializer):
    title = models.CharField(max_length=200)
    content = models.TextField()
    slug = models.SlugField(unique=True, blank=True)
    is_published = models.BooleanField(default=False)
    published_at = models.DateTimeField(null=True, blank=True)

    class ReadSerializer:
        fields = ["id", "title", "slug", "is_published", "published_at"]

    def before_save(self):
        """Called before every save (create and update)"""
        if not self.slug:
            from django.utils.text import slugify
            self.slug = slugify(self.title)

    def on_create_before_save(self):
        """Called only on creation, before save"""
        print(f"Creating new article: {self.title}")

    def after_save(self):
        """Called after every save"""
        from django.core.cache import cache
        cache.delete(f"article:{self.id}")

    def on_create_after_save(self):
        """Called only after creation"""
        print(f"Article created with ID: {self.id}")

    def on_delete(self):
        """Called after deletion"""
        print(f"Article deleted: {self.title}")
```

### Async Hooks

```python
class Article(ModelSerializer):
    title = models.CharField(max_length=200)
    content = models.TextField()
    author = models.ForeignKey(Author, on_delete=models.CASCADE)
    is_published = models.BooleanField(default=False)

    class CreateSerializer:
        fields = ["title", "content", "author"]
        customs = [
            ("notify_subscribers", bool, True),
            ("schedule_publish", str, None),
        ]

    async def post_create(self):
        """Called after object creation (async)"""
        # Send notification email
        from myapp.tasks import send_new_article_notification
        await send_new_article_notification(self.id)

        # Create activity log
        from myapp.models import ActivityLog
        await ActivityLog.objects.acreate(
            action="article_created",
            article_id=self.id,
            user_id=self.author_id
        )

    async def custom_actions(self, payload: dict):
        """Process custom fields from CreateSerializer"""
        if payload.get("notify_subscribers"):
            from myapp.tasks import notify_subscribers
            await notify_subscribers(self.id)

        if payload.get("schedule_publish"):
            from datetime import datetime
            schedule_time = datetime.fromisoformat(payload["schedule_publish"])
            from myapp.tasks import schedule_publish_task
            await schedule_publish_task(self.id, schedule_time)
```

!!! warning "Execution Order"
**Create**: `on_create_before_save()` → `before_save()` → `save()` → `on_create_after_save()` → `after_save()` → `custom_actions()` → `post_create()`

    **Update**: `before_save()` → `save()` → `after_save()` → `custom_actions()`

## Complete Example

Here's a complete blog model with all features:

```python
# models.py
from django.db import models
from django.utils.text import slugify
from ninja_aio.models import ModelSerializer


class Author(ModelSerializer):
    name = models.CharField(max_length=200)
    email = models.EmailField(unique=True)
    bio = models.TextField(blank=True)
    avatar = models.URLField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class ReadSerializer:
        fields = ["id", "name", "email", "bio", "avatar", "created_at"]
        customs = [
            ("article_count", int, lambda obj: obj.articles.count()),
        ]

    class CreateSerializer:
        fields = ["name", "email"]
        optionals = [("bio", str), ("avatar", str)]

    class UpdateSerializer:
        optionals = [
            ("name", str),
            ("bio", str),
            ("avatar", str),
        ]
        excludes = ["email", "created_at"]

    def __str__(self):
        return self.name


class Category(ModelSerializer):
    name = models.CharField(max_length=100)
    slug = models.SlugField(unique=True, blank=True)
    description = models.TextField(blank=True)

    class ReadSerializer:
        fields = ["id", "name", "slug", "description"]

    class CreateSerializer:
        fields = ["name"]
        optionals = [("description", str)]

    def before_save(self):
        if not self.slug:
            self.slug = slugify(self.name)

    def __str__(self):
        return self.name


class Tag(ModelSerializer):
    name = models.CharField(max_length=50, unique=True)
    slug = models.SlugField(unique=True, blank=True)

    class ReadSerializer:
        fields = ["id", "name", "slug"]

    class CreateSerializer:
        fields = ["name"]

    def before_save(self):
        if not self.slug:
            self.slug = slugify(self.name)

    def __str__(self):
        return self.name


class Article(ModelSerializer):
    title = models.CharField(max_length=200)
    slug = models.SlugField(unique=True, blank=True)
    content = models.TextField()
    excerpt = models.TextField(max_length=300, blank=True)
    author = models.ForeignKey(Author, on_delete=models.CASCADE, related_name="articles")
    category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True, related_name="articles")
    tags = models.ManyToManyField(Tag, related_name="articles", blank=True)
    cover_image = models.URLField(blank=True)
    is_published = models.BooleanField(default=False)
    published_at = models.DateTimeField(null=True, blank=True)
    views = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class ReadSerializer:
        fields = [
            "id", "title", "slug", "content", "excerpt",
            "author", "category", "tags", "cover_image",
            "is_published", "published_at", "views",
            "created_at", "updated_at"
        ]
        customs = [
            ("word_count", int, lambda obj: len(obj.content.split())),
            ("reading_time", int, lambda obj: max(1, len(obj.content.split()) // 200)),
        ]

    class CreateSerializer:
        fields = ["title", "content", "author", "category"]
        optionals = [
            ("excerpt", str),
            ("cover_image", str),
            ("tags", list[int]),
            ("is_published", bool),
        ]
        customs = [
            ("notify_subscribers", bool, True),
        ]

    class UpdateSerializer:
        optionals = [
            ("title", str),
            ("content", str),
            ("excerpt", str),
            ("category", int),
            ("tags", list[int]),
            ("cover_image", str),
            ("is_published", bool),
        ]
        excludes = ["author", "created_at", "views"]

    def before_save(self):
        # Generate slug from title
        if not self.slug:
            self.slug = slugify(self.title)

        # Auto-generate excerpt
        if not self.excerpt and self.content:
            self.excerpt = self.content[:297] + "..."

        # Set published_at when publishing
        if self.is_published and not self.published_at:
            from django.utils import timezone
            self.published_at = timezone.now()

    async def post_create(self):
        # Log creation
        from myapp.models import ActivityLog
        await ActivityLog.objects.acreate(
            action="article_created",
            article_id=self.id,
            user_id=self.author_id
        )

    async def custom_actions(self, payload: dict):
        if payload.get("notify_subscribers"):
            # Send notifications (implement your notification logic)
            from myapp.tasks import notify_article_published
            await notify_article_published(self.id)

    def __str__(self):
        return self.title
```

## Run Migrations

After defining your models, create and run migrations:

```bash
# Create migrations
python manage.py makemigrations

# Apply migrations
python manage.py migrate
```

## Next Steps

Now that you have your models defined, let's create CRUD views in [Step 2: Create CRUD Views](crud.md).

!!! success "What You've Learned" - ✅ Creating models with `ModelSerializer` - ✅ Defining Read, Create, and Update serializers - ✅ Working with ForeignKey and ManyToMany relationships - ✅ Adding custom computed fields - ✅ Implementing lifecycle hooks

## See Also

- [ModelSerializer API Reference](../api/models/model_serializer.md) - Complete API documentation
- [ModelUtil API Reference](../api/models/model_util.md) - Utility methods
