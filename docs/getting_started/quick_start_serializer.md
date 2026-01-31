## :material-rocket-launch: Quick Start (Serializer)

This guide shows how to create a CRUD API using the `Serializer` class with plain Django models. This approach keeps your models unchanged and defines API configuration separately.

!!! tip "Alternative Approach"
    If you prefer an all-in-one approach with embedded serialization, see [Quick Start (ModelSerializer)](quick_start.md).

### When to Use Serializer

Choose the `Serializer` approach when:

- :material-database: You have existing Django models you don't want to modify
- :material-arrow-split-vertical: You want to keep models and API concerns separated
- :material-puzzle: You're adding API functionality to an existing project
- :material-account-group: Multiple teams work on models vs. API layers

### 1. Create Your Model

Use a standard Django model:

```python
# models.py
from django.db import models


class Article(models.Model):
    title = models.CharField(max_length=200)
    content = models.TextField()
    is_published = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
```

### 2. Create Your Serializer

Define a `Serializer` class with API configuration in a nested `Meta` class:

```python
# serializers.py
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

### 3. Create Your ViewSet

Define your API views using `APIViewSet` with `serializer_class`:

```python
# views.py
from ninja_aio import NinjaAIO
from ninja_aio.views import APIViewSet
from .models import Article
from .serializers import ArticleSerializer

api = NinjaAIO(title="My Blog API", version="1.0.0")


@api.viewset(model=Article)
class ArticleViewSet(APIViewSet):
    serializer_class = ArticleSerializer
```

### 4. Configure URLs

Add the API to your URL configuration:

```python
# urls.py
from django.urls import path
from .views import api

urlpatterns = [
    path("api/", api.urls),
]
```

### 5. Run Your Server

```bash
python manage.py runserver
```

Visit **[http://localhost:8000/api/docs](http://localhost:8000/api/docs)** to see your auto-generated API documentation!

## Adding Relationships

The `Serializer` approach supports nested serialization for related models:

```python
# models.py
from django.db import models


class Author(models.Model):
    name = models.CharField(max_length=200)
    email = models.EmailField()


class Article(models.Model):
    title = models.CharField(max_length=200)
    content = models.TextField()
    author = models.ForeignKey(Author, on_delete=models.CASCADE, related_name="articles")
    is_published = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
```

```python
# serializers.py
from ninja_aio.models import serializers
from .models import Author, Article


class AuthorSerializer(serializers.Serializer):
    class Meta:
        model = Author
        schema_out = serializers.SchemaModelConfig(
            fields=["id", "name", "email"]
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
            optionals=[
                ("title", str),
                ("content", str),
                ("is_published", bool),
            ]
        )
        # Nested serialization for the author field
        relations_serializers = {
            "author": AuthorSerializer,
        }

    class QuerySet:
        # Optimize queries with select_related
        read = serializers.ModelQuerySetSchema(
            select_related=["author"]
        )
```

## Adding Lifecycle Hooks

Add custom logic to CRUD operations using hooks:

```python
# serializers.py
from ninja_aio.models import serializers
from .models import Article


class ArticleSerializer(serializers.Serializer):
    class Meta:
        model = Article
        schema_in = serializers.SchemaModelConfig(
            fields=["title", "content"],
            customs=[("notify_subscribers", bool, False)],  # Custom field
        )
        schema_out = serializers.SchemaModelConfig(
            fields=["id", "title", "content", "is_published", "created_at"]
        )
        schema_update = serializers.SchemaModelConfig(
            optionals=[("title", str), ("content", str), ("is_published", bool)]
        )

    async def custom_actions(self, payload, instance):
        """Execute after field assignment, before save."""
        if payload.get("notify_subscribers"):
            await send_notification(instance.title)

    async def post_create(self, instance):
        """Execute after instance creation."""
        await AuditLog.objects.acreate(
            action="article_created",
            article_id=instance.id
        )

    def before_save(self, instance):
        """Execute before any save (sync hook)."""
        instance.slug = slugify(instance.title)

    def on_delete(self, instance):
        """Execute after deletion (sync hook)."""
        logger.info(f"Article {instance.id} deleted")
```

## :material-arrow-right-circle: Next Steps

<div class="grid cards" markdown>

-   :material-cube-outline:{ .lg .middle } **Serializer Configuration**

    ---

    [:octicons-arrow-right-24: Learn more](../api/models/serializers.md)

-   :material-view-grid:{ .lg .middle } **APIViewSet Features**

    ---

    [:octicons-arrow-right-24: Explore](../api/views/api_view_set.md)

-   :material-shield-lock:{ .lg .middle } **Authentication**

    ---

    [:octicons-arrow-right-24: Add auth](../api/authentication.md)

-   :material-page-next:{ .lg .middle } **Pagination**

    ---

    [:octicons-arrow-right-24: Configure](../api/pagination.md)

</div>
