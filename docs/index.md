<div class="hero" markdown>

# Django Ninja Aio CRUD

<p class="subtitle">
Powerful async CRUD framework built on top of Django Ninja.<br>
Automatic REST APIs with auth, filtering, pagination, and serialization.
</p>

</div>

<div class="badges" markdown>

[![Test](https://github.com/caspel26/django-ninja-aio-crud/actions/workflows/coverage.yml/badge.svg)](https://github.com/caspel26/django-ninja-aio-crud/actions)
[![Quality Gate Status](https://sonarcloud.io/api/project_badges/measure?project=caspel26_django-ninja-aio-crud&metric=alert_status)](https://sonarcloud.io/summary/new_code?id=caspel26_django-ninja-aio-crud)
[![codecov](https://codecov.io/gh/caspel26/django-ninja-aio-crud/graph/badge.svg?token=DZ5WDT3S20)](https://codecov.io/gh/caspel26/django-ninja-aio-crud)
[![PyPI - Version](https://img.shields.io/pypi/v/django-ninja-aio-crud?color=g&logo=pypi&logoColor=white)](https://pypi.org/project/django-ninja-aio-crud/)
[![PyPI - License](https://img.shields.io/pypi/l/django-ninja-aio-crud)](https://github.com/caspel26/django-ninja-aio-crud/blob/main/LICENSE)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)

</div>

<div class="cta-buttons" markdown>

[Get Started :material-rocket-launch:](getting_started/installation.md){ .md-button .md-button--primary }
[View on GitHub :material-github:](https://github.com/caspel26/django-ninja-aio-crud){ .md-button }

</div>

---

## :material-star-shooting: Key Features

<div class="grid cards" markdown>

-   :material-lightning-bolt:{ .lg .middle } **Fully Async**

    ---

    Built for Django's async ORM from the ground up

-   :material-sync:{ .lg .middle } **Automatic CRUD**

    ---

    Generate complete REST APIs with minimal code

-   :material-file-document-edit:{ .lg .middle } **ModelSerializer**

    ---

    Define schemas directly on your Django models

-   :material-view-grid:{ .lg .middle } **Class-Based Views**

    ---

    Clean, organized view architecture with APIView & APIViewSet

-   :material-shield-lock:{ .lg .middle } **JWT Authentication**

    ---

    Built-in async JWT bearer authentication

-   :material-link-variant:{ .lg .middle } **Relationship Support**

    ---

    Automatic nested serialization for FK, M2M, and reverse relations

-   :material-book-open-page-variant:{ .lg .middle } **Auto Documentation**

    ---

    OpenAPI / Swagger UI out of the box

-   :material-page-next:{ .lg .middle } **Pagination**

    ---

    Built-in async pagination support

-   :material-flash:{ .lg .middle } **Performance**

    ---

    Using `orjson` for fast JSON serialization

</div>

---

## :material-target: Why Django Ninja Aio CRUD?

Traditional Django REST development requires separate serializer classes, manual CRUD view implementation, repetitive boilerplate code, and complex relationship handling. **Django Ninja Aio CRUD** eliminates this complexity:

=== "Traditional Approach"
    ```python
    # schema.py
    class UserSchemaOut(ModelSchema)
        class Meta:
        model = User
        fields = ['id', 'username', 'email']

    class UserSchemaIn(ModelSchema):
        class Meta:
            model = User
            fields = ['username', 'email', 'password']

    # views.py
    @api.get("/users", response={200: list[UserSchemaOut]})
    async def list_users(request):
        return [user async for user in User.objects.select_related().all()]

    @api.post("/users/", response={201: UserSchemaOut})
    async def create_user(request, data: UserSchemaIn):
        user = await User.objects.select_related().acreate(**data.model_dump())
        return 201, user


    # ... more views for retrieve, update, delete
    ```

=== "Django Ninja Aio CRUD"
    ```python
    # models.py
    class User(ModelSerializer):
        username = models.CharField(max_length=150)
        email = models.EmailField()
        password = models.CharField(max_length=128)

        class ReadSerializer:
            fields = ["id", "username", "email"]

        class CreateSerializer:
            fields = ["username", "email", "password"]

        class UpdateSerializer:
            optionals = [("email", str)]

    # views.py
    @api.viewset(User)
    class UserViewSet(APIViewSet):
        pass

    # Done! List, Create, Retrieve, Update, Delete endpoints ready
    ```

---

## :material-book-open-variant: Documentation

<div class="grid cards" markdown>

-   :material-cube-outline:{ .lg .middle } **Serializer (Meta-driven)**

    ---

    Dynamic schemas for existing Django models without inheriting ModelSerializer

    [:octicons-arrow-right-24: Learn more](api/models/serializers.md)

-   :material-database:{ .lg .middle } **Models**

    ---

    Schema generation, serialization, and async CRUD utilities

    [:octicons-arrow-right-24: ModelSerializer](api/models/model_serializer.md) &middot; [:octicons-arrow-right-24: ModelUtil](api/models/model_util.md)

-   :material-eye:{ .lg .middle } **Views**

    ---

    Simple custom views and complete CRUD operations

    [:octicons-arrow-right-24: APIView](api/views/api_view.md) &middot; [:octicons-arrow-right-24: APIViewSet](api/views/api_view_set.md)

-   :material-cog:{ .lg .middle } **Advanced Topics**

    ---

    JWT auth, custom auth, and pagination behavior

    [:octicons-arrow-right-24: Authentication](api/authentication.md) &middot; [:octicons-arrow-right-24: Pagination](api/pagination.md)

</div>

---

## :material-play-circle: Start with Serializer

Use Meta-driven Serializer first if you already have Django models and want immediate CRUD without changing bases:

```python
from ninja_aio.models import serializers
from . import models

class BookSerializer(serializers.Serializer):
    class Meta:
        model = models.Book
        schema_in = serializers.SchemaModelConfig(fields=["title", "published"])
        schema_out = serializers.SchemaModelConfig(fields=["id", "title", "published"])
        schema_update = serializers.SchemaModelConfig(optionals=[("title", str), ("published", bool)])
```

Attach to a ViewSet:

```python
from ninja_aio.views import APIViewSet
from ninja_aio import NinjaAIO

api = NinjaAIO()

@api.viewset(models.Book)
class BookViewSet(APIViewSet):
    serializer_class = BookSerializer
```

---

## :material-database-search: Query Optimization and Schemas

- Declare query optimizations on models via `class QuerySet` (read, queryset_request, extras).
- Use `QueryUtil` to apply scope-based `select_related` / `prefetch_related`.
- Standard query schemas:
  - `ObjectsQuerySchema(filters=..., select_related=..., prefetch_related=...)`
  - `ObjectQuerySchema(getters=..., select_related=..., prefetch_related=...)`
  - `QuerySchema(filters=... | getters=...)`

ViewSets internally use these to build optimized querysets in list/retrieve and serialize via `list_read_s` and `read_s`.

??? example "Query optimization example"

    ```python
    items = await ModelUtil(Article).list_read_s(
        Article.generate_read_s(),
        request,
        query_data=ObjectsQuerySchema(filters={"category": 3}),
        is_for_read=True,
    )
    ```

---

## :material-lightbulb: Example: Complete Blog API

Here's a real-world example with relationships:

??? example "Full blog API code (click to expand)"

    ```python
    # models.py
    from django.db import models
    from ninja_aio.models import ModelSerializer


    class Author(ModelSerializer):
        name = models.CharField(max_length=200)
        email = models.EmailField(unique=True)
        bio = models.TextField(blank=True)

        class ReadSerializer:
            fields = ["id", "name", "email", "bio", "articles"]

        class CreateSerializer:
            fields = ["name", "email"]
            optionals = [("bio", str)]


    class Category(ModelSerializer):
        name = models.CharField(max_length=100)
        slug = models.SlugField(unique=True)

        class ReadSerializer:
            fields = ["id", "name", "slug"]

        class CreateSerializer:
            fields = ["name", "slug"]


    class Article(ModelSerializer):
        title = models.CharField(max_length=200)
        slug = models.SlugField(unique=True)
        content = models.TextField()
        author = models.ForeignKey(Author, on_delete=models.CASCADE, related_name="articles")
        category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True)
        tags = models.ManyToManyField('Tag', related_name="articles")
        is_published = models.BooleanField(default=False)
        views = models.IntegerField(default=0)
        created_at = models.DateTimeField(auto_now_add=True)

        class ReadSerializer:
            fields = [
                "id", "title", "slug", "content",
                "author", "category", "tags",
                "is_published", "views", "created_at"
            ]

        class CreateSerializer:
            fields = ["title", "slug", "content", "author", "category"]
            customs = [("notify_subscribers", bool, True)]

        class UpdateSerializer:
            optionals = [
                ("title", str),
                ("content", str),
                ("is_published", bool),
            ]

        async def custom_actions(self, payload: dict):
            if payload.get("notify_subscribers"):
                # Send notifications
                await notify_new_article(self)


    class Tag(ModelSerializer):
        name = models.CharField(max_length=50, unique=True)

        class ReadSerializer:
            fields = ["id", "name"]


    # views.py
    from ninja_aio import NinjaAIO
    from ninja_aio.views import APIViewSet
    from .models import Author, Category, Article, Tag

    api = NinjaAIO(title="Blog API", version="1.0.0")


    @api.viewset(Author)
    class AuthorViewSet(APIViewSet):
        pass


    @api.viewset(Category)
    class CategoryViewSet(APIViewSet):
        pass


    @api.viewset(Article)
    class ArticleViewSet(APIViewSet):
        query_params = {
            "is_published": (bool, None),
            "category": (int, None),
            "author": (int, None),
        }

        async def query_params_handler(self, queryset, filters):
            if filters.get("is_published") is not None:
                queryset = queryset.filter(is_published=filters["is_published"])
            if filters.get("category"):
                queryset = queryset.filter(category_id=filters["category"])
            if filters.get("author"):
                queryset = queryset.filter(author_id=filters["author"])
            return queryset


    @api.viewset(Tag)
    class TagViewSet(APIViewSet):
        pass
    ```

This creates a complete blog API with 4 models with relationships, automatic nested serialization, query filtering, custom actions, and full CRUD operations for all models.

---

## :material-star-circle: Key Concepts

<div class="grid cards" markdown>

-   :material-file-document-edit:{ .lg .middle } **ModelSerializer**

    ---

    Central to Django Ninja Aio CRUD — define schemas directly on models:

    ```python
    class User(ModelSerializer):
        username = models.CharField(max_length=150)

        class ReadSerializer:
            fields = ["id", "username"]

        class CreateSerializer:
            fields = ["username"]

        class UpdateSerializer:
            optionals = [("username", str)]
    ```

-   :material-cube-outline:{ .lg .middle } **Serializer (Meta-driven)**

    ---

    For vanilla Django models — dynamic serialization without changing the base class:

    ```python
    class BookSerializer(serializers.Serializer):
        class Meta:
            model = models.Book
            schema_in = serializers.SchemaModelConfig(
                fields=["title", "published"]
            )
            schema_out = serializers.SchemaModelConfig(
                fields=["id", "title", "published"]
            )
    ```

-   :material-view-grid:{ .lg .middle } **APIViewSet**

    ---

    Generates complete CRUD endpoints automatically:

    ```python
    @api.viewset(User)
    class UserViewSet(APIViewSet):
        pass
        # List, Create, Retrieve, Update, Delete
    ```

-   :material-pencil-plus:{ .lg .middle } **Custom Views**

    ---

    Extend with custom endpoints:

    ```python
    @api.viewset(User)
    class UserViewSet(APIViewSet):
        @api_post("/{pk}/activate")
        async def activate(self, request, pk: int):
            user = await User.objects.aget(pk=pk)
            user.is_active = True
            await user.asave()
            return {"message": "User activated"}
    ```

</div>

---

## :material-scale-balance: License

This project is licensed under the MIT License - see the [LICENSE](https://github.com/caspel26/django-ninja-aio-crud/blob/main/LICENSE) file for details.

## :material-coffee: Support

If you find Django Ninja Aio CRUD useful, consider supporting the project:

[![Buy Me A Coffee](https://img.shields.io/badge/Buy%20Me%20A%20Coffee-Support-yellow?logo=buy-me-a-coffee)](https://buymeacoffee.com/caspel26)

## :material-link: Links

- **Documentation:** [https://django-ninja-aio.com](https://django-ninja-aio.com)
- **GitHub:** [https://github.com/caspel26/django-ninja-aio-crud](https://github.com/caspel26/django-ninja-aio-crud)
- **PyPI:** [https://pypi.org/project/django-ninja-aio-crud/](https://pypi.org/project/django-ninja-aio-crud/)
- **Django Ninja:** [https://django-ninja.dev/](https://django-ninja.dev/)
- **Example repository:** [https://github.com/caspel26/ninja-aio-blog-example](https://github.com/caspel26/ninja-aio-blog-example)

---

<div style="text-align: center; opacity: 0.7;" markdown>
Built with :material-heart: using [Django Ninja](https://django-ninja.dev/)
</div>
