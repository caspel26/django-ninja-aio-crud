# 🥷 Django Ninja Aio CRUD

[![Test](https://github.com/caspel26/django-ninja-aio-crud/actions/workflows/coverage.yml/badge.svg)](https://github.com/caspel26/django-ninja-aio-crud/actions)
[![Quality Gate Status](https://sonarcloud.io/api/project_badges/measure?project=caspel26_django-ninja-aio-crud&metric=alert_status)](https://sonarcloud.io/summary/new_code?id=caspel26_django-ninja-aio-crud)
[![codecov](https://codecov.io/gh/caspel26/django-ninja-aio-crud/graph/badge.svg?token=DZ5WDT3S20)](https://codecov.io/gh/caspel26/django-ninja-aio-crud)
[![PyPI - Version](https://img.shields.io/pypi/v/django-ninja-aio-crud?color=g&logo=pypi&logoColor=white)](https://pypi.org/project/django-ninja-aio-crud/)
[![PyPI - License](https://img.shields.io/pypi/l/django-ninja-aio-crud)](https://github.com/caspel26/django-ninja-aio-crud/blob/main/LICENSE)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)

**Django Ninja Aio CRUD** is a powerful async REST framework built on top of [Django Ninja](https://django-ninja.dev/). It provides automatic CRUD operations, class-based views, and built-in utilities to make API development faster and cleaner.

## ✨ Key Features

- 🚀 **Fully Async** - Built for Django's async ORM
- 🔄 **Automatic CRUD** - Generate complete REST APIs with minimal code
- 📝 **ModelSerializer** - Define schemas directly on models
- 🎯 **Class-Based Views** - Clean, organized view architecture
- 🔐 **JWT Authentication** - Built-in async JWT bearer authentication
- 📄 **Auto Documentation** - OpenAPI/Swagger UI out of the box
- 🔗 **Relationship Support** - Automatic nested serialization (FK, M2M, reverse relations)
- 📊 **Pagination** - Built-in async pagination support
- ⚡ **Performance** - Using `orjson` for fast JSON serialization

## 🎯 Why Django Ninja Aio CRUD?

Traditional Django REST development requires:
- Separate serializer classes
- Manual CRUD view implementation
- Repetitive boilerplate code
- Complex relationship handling

**Django Ninja Aio CRUD** eliminates this complexity:

=== "Traditional Approach"
    ```python
    # schema.py
    class UserSchemaOut(ModelSchema):
        class Meta:
            model = User
            fields = ['id', 'username', 'email']
    
    class UserSchemaIn(ModelSchema):
        class Meta:
            model = User
            fields = ['username', 'email', 'password']
    
    # views.py
    @api.get("users", response={200: UserSchemaOut})
    async def list_users(request):
        return [user async for user in User.objects.all()]
    
    
    @api.post("users/", response{201: UserSchemaOut})
    async def create_user(request, data: UserSchemaIn):
        user_pk = (await User.objects.acreate(**data.model_dump())).pk
        return 201, await User.objects.aget(pk=pk)

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
    class UserViewSet(APIViewSet):
        model = User
        api = api
    
    UserViewSet().add_views_to_route()
    # Done! List, Create, Retrieve, Update, Delete endpoints ready
    ```

### 📚 Documentation

Explore detailed documentation for each component:

#### Models
- **[Model Serializer](api/models/model_serializer.md)** - Schema generation and serialization
- **[Model Util](api/models/model_util.md)** - Async CRUD utilities

#### Views
- **[API View](api/views/api_view.md)** - Simple custom views
- **[API View Set](api/views/api_view_set.md)** - Complete CRUD operations

#### Advanced Topics
- **[Authentication](api/authentication.md)** - JWT and custom auth
- **[Pagination](api/pagination.md)** - Customize pagination behavior

## 💡 Example: Complete Blog API

Here's a real-world example with relationships:

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


class AuthorViewSet(APIViewSet):
    model = Author
    api = api


class CategoryViewSet(APIViewSet):
    model = Category
    api = api


class ArticleViewSet(APIViewSet):
    model = Article
    api = api
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


class TagViewSet(APIViewSet):
    model = Tag
    api = api


# Register all views
AuthorViewSet().add_views_to_route()
CategoryViewSet().add_views_to_route()
ArticleViewSet().add_views_to_route()
TagViewSet().add_views_to_route()
```

This creates a complete blog API with:
- 4 models with relationships
- Automatic nested serialization
- Query filtering
- Custom actions
- Full CRUD operations for all models

## 🌟 Key Concepts

### ModelSerializer

Central to Django Ninja Aio CRUD - defines schemas directly on models:

```python
class User(ModelSerializer):
    username = models.CharField(max_length=150)
    
    class ReadSerializer:
        fields = ["id", "username"]  # Response schema
    
    class CreateSerializer:
        fields = ["username"]  # Input schema
    
    class UpdateSerializer:
        optionals = [("username", str)]  # Partial update schema
```

### APIViewSet

Automatically generates complete CRUD endpoints:

```python
class UserViewSet(APIViewSet):
    model = User
    api = api
    # Generates: List, Create, Retrieve, Update, Delete
```

### Custom Views

Extend with custom endpoints:

```python
class UserViewSet(APIViewSet):
    model = User
    api = api
    
    def views(self):
        @self.router.post("/{pk}/activate/")
        async def activate(request, pk: int):
            user = await User.objects.aget(pk=pk)
            user.is_active = True
            await user.asave()
            return {"message": "User activated"}
```

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](https://github.com/caspel26/django-ninja-aio-crud/blob/main/LICENSE) file for details.

## ☕ Support

If you find Django Ninja Aio CRUD useful, consider supporting the project:

[![Buy Me A Coffee](https://img.shields.io/badge/Buy%20Me%20A%20Coffee-Support-yellow?logo=buy-me-a-coffee)](https://buymeacoffee.com/caspel26)

## 🔗 Links

- **Documentation:** [https://django-ninja-aio.com](https://django-ninja-aio.com)
- **GitHub:** [https://github.com/caspel26/django-ninja-aio-crud](https://github.com/caspel26/django-ninja-aio-crud)
- **PyPI:** [https://pypi.org/project/django-ninja-aio-crud/](https://pypi.org/project/django-ninja-aio-crud/)
- **Django Ninja:** [https://django-ninja.dev/](https://django-ninja.dev/)

---

Built with ❤️ using [Django Ninja](https://django-ninja.dev/)