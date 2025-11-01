# Step 2: Create CRUD Views

In this step, you'll learn how to create a complete REST API with CRUD operations using `APIViewSet`.

## What You'll Learn

- How to create a basic ViewSet
- Understanding auto-generated endpoints
- Customizing query parameters
- Adding custom endpoints
- Working with request context
- Handling errors

## Prerequisites

Make sure you've completed:

- [Step 1: Define Your Model](model.md)

You should have the `Article`, `Author`, `Category`, and `Tag` models defined.

## Basic ViewSet

Let's create a simple API for the Article model:

```python
# views.py
from ninja_aio import NinjaAIO
from ninja_aio.views import APIViewSet
from .models import Article

# Create API instance
api = NinjaAIO(
    title="Blog API",
    version="1.0.0",
    description="A simple blog API built with Django Ninja Aio CRUD"
)


class ArticleViewSet(APIViewSet):
    model = Article
    api = api


# Register the ViewSet
ArticleViewSet().add_views_to_route()
```

That's it! You now have a complete CRUD API with 5 endpoints.

### Configure URLs

Add the API to your Django URLs:

```python
# urls.py
from django.contrib import admin
from django.urls import path
from myapp.views import api

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/", api.urls),
]
```

### Auto-Generated Endpoints

The ViewSet automatically generates these endpoints:

| Method   | Endpoint             | Description                   | Request Body         | Response                           |
| -------- | -------------------- | ----------------------------- | -------------------- | ---------------------------------- |
| `GET`    | `/api/article/`      | List all articles (paginated) | None                 | `{count, next, previous, results}` |
| `POST`   | `/api/article/`      | Create new article            | Article data         | Created article                    |
| `GET`    | `/api/article/{id}`  | Retrieve single article       | None                 | Article data                       |
| `PATCH`  | `/api/article/{id}/` | Update article                | Partial article data | Updated article                    |
| `DELETE` | `/api/article/{id}/` | Delete article                | None                 | None (204)                         |

### Test Your API

Start the development server:

```bash
python manage.py runserver
```

Visit **http://localhost:8000/api/docs** to see the auto-generated Swagger UI documentation.

## Creating Multiple ViewSets

Let's add APIs for all our models:

```python
# views.py
from ninja_aio import NinjaAIO
from ninja_aio.views import APIViewSet
from .models import Article, Author, Category, Tag

api = NinjaAIO(title="Blog API", version="1.0.0")


class AuthorViewSet(APIViewSet):
    model = Author
    api = api


class CategoryViewSet(APIViewSet):
    model = Category
    api = api


class TagViewSet(APIViewSet):
    model = Tag
    api = api


class ArticleViewSet(APIViewSet):
    model = Article
    api = api


# Register all ViewSets
AuthorViewSet().add_views_to_route()
CategoryViewSet().add_views_to_route()
TagViewSet().add_views_to_route()
ArticleViewSet().add_views_to_route()
```

Now you have complete CRUD APIs for all models:

- `/api/author/`
- `/api/category/`
- `/api/tag/`
- `/api/article/`

## Adding Query Parameters

Let's add filtering to the Article list endpoint:

```python
class ArticleViewSet(APIViewSet):
    model = Article
    api = api
    query_params = {
        "is_published": (bool, None),
        "author": (int, None),
        "category": (int, None),
        "search": (str, None),
    }

    async def query_params_handler(self, queryset, filters):
        # Filter by published status
        if filters.get("is_published") is not None:
            queryset = queryset.filter(is_published=filters["is_published"])

        # Filter by author
        if filters.get("author"):
            queryset = queryset.filter(author_id=filters["author"])

        # Filter by category
        if filters.get("category"):
            queryset = queryset.filter(category_id=filters["category"])

        # Search in title and content
        if filters.get("search"):
            from django.db.models import Q
            search_term = filters["search"]
            queryset = queryset.filter(
                Q(title__icontains=search_term) |
                Q(content__icontains=search_term)
            )

        return queryset


ArticleViewSet().add_views_to_route()
```

### Using Query Parameters

Now you can filter articles:

```bash
# Get published articles
GET /api/article/?is_published=true

# Get articles by specific author
GET /api/article/?author=5

# Get articles in specific category
GET /api/article/?category=3

# Search articles
GET /api/article/?search=django

# Combine filters
GET /api/article/?is_published=true&author=5&category=3

# With pagination
GET /api/article/?is_published=true&page=2&page_size=20
```

## Custom Endpoints

Add custom endpoints beyond CRUD:

```python
class ArticleViewSet(APIViewSet):
    model = Article
    api = api

    def views(self):
        """Define custom endpoints"""

        # Publish an article
        @self.router.post("/{pk}/publish/")
        async def publish(request, pk: int):
            article = await Article.objects.aget(pk=pk)
            article.is_published = True
            from django.utils import timezone
            article.published_at = timezone.now()
            await article.asave()

            return {
                "message": "Article published successfully",
                "published_at": article.published_at
            }

        # Unpublish an article
        @self.router.post("/{pk}/unpublish/")
        async def unpublish(request, pk: int):
            article = await Article.objects.aget(pk=pk)
            article.is_published = False
            article.published_at = None
            await article.asave()

            return {"message": "Article unpublished successfully"}

        # Increment view count
        @self.router.post("/{pk}/view/")
        async def increment_views(request, pk: int):
            article = await Article.objects.aget(pk=pk)
            article.views += 1
            await article.asave(update_fields=["views"])

            return {"views": article.views}

        # Get article statistics
        @self.router.get("/stats/")
        async def stats(request):
            from django.db.models import Count, Avg, Sum

            total = await Article.objects.acount()
            published = await Article.objects.filter(is_published=True).acount()

            # Use sync_to_async for aggregate
            from asgiref.sync import sync_to_async

            avg_views = await sync_to_async(
                lambda: Article.objects.aggregate(avg=Avg("views"))
            )()

            total_views = await sync_to_async(
                lambda: Article.objects.aggregate(total=Sum("views"))
            )()

            return {
                "total_articles": total,
                "published_articles": published,
                "draft_articles": total - published,
                "average_views": avg_views["avg"] or 0,
                "total_views": total_views["total"] or 0,
            }

        # Get popular articles
        @self.router.get("/popular/")
        async def popular(request, limit: int = 10):
            articles = []
            async for article in Article.objects.filter(
                is_published=True
            ).order_by("-views")[:limit]:
                articles.append(article)

            # Serialize articles
            from ninja_aio.models import ModelUtil
            util = ModelUtil(Article)
            schema = Article.generate_read_s()

            results = []
            for article in articles:
                data = await util.read_s(request, article, schema)
                results.append(data)

            return results


ArticleViewSet().add_views_to_route()
```

### Custom Endpoint URLs

Your custom endpoints are now available:

```bash
# Publish article
POST /api/article/1/publish/

# Unpublish article
POST /api/article/1/unpublish/

# Increment views
POST /api/article/1/view/

# Get statistics
GET /api/article/stats/

# Get popular articles (top 10)
GET /api/article/popular/

# Get top 20
GET /api/article/popular/?limit=20
```

## Request Context

Access request information in your ViewSet:

```python
class ArticleViewSet(APIViewSet):
    model = Article
    api = api

    def views(self):
        @self.router.get("/my-articles/")
        async def my_articles(request):
            """Get articles by current user"""
            # Access authenticated user
            user = request.auth

            # Get user's articles
            articles = []
            async for article in Article.objects.filter(author=user):
                articles.append(article)

            # Serialize
            from ninja_aio.models import ModelUtil
            util = ModelUtil(Article)
            schema = Article.generate_read_s()

            results = []
            for article in articles:
                data = await util.read_s(request, article, schema)
                results.append(data)

            return results

        @self.router.post("/")
        async def create_article(request, data: Article.generate_create_s()):
            """Override create to set author from request"""
            # Set author from authenticated user
            data.author = request.auth.id

            # Use default create logic
            from ninja_aio.models import ModelUtil
            util = ModelUtil(Article)
            schema = Article.generate_read_s()

            return await util.create_s(request, data, schema)


ArticleViewSet().add_views_to_route()
```

## Filtering by User

Automatically filter queryset based on user:

```python
class Article(ModelSerializer):
    # ... fields ...

    @classmethod
    async def queryset_request(cls, request):
        """Filter articles based on user"""
        qs = cls.objects.select_related('author', 'category').prefetch_related('tags')

        # If user is not authenticated, show only published
        if not request.auth:
            return qs.filter(is_published=True)

        # If user is admin, show all
        user = request.auth
        if user.is_staff:
            return qs

        # Regular users see published + their own drafts
        from django.db.models import Q
        return qs.filter(
            Q(is_published=True) | Q(author=user)
        )


class ArticleViewSet(APIViewSet):
    model = Article
    api = api
    # queryset_request is automatically called for all operations


ArticleViewSet().add_views_to_route()
```

## Custom Pagination

Override default pagination:

```python
from ninja.pagination import PageNumberPagination


class LargePagePagination(PageNumberPagination):
    page_size = 50  # Default 50 items per page
    max_page_size = 200  # Allow up to 200 items


class ArticleViewSet(APIViewSet):
    model = Article
    api = api
    pagination_class = LargePagePagination


ArticleViewSet().add_views_to_route()
```

Now list endpoint uses custom pagination:

```bash
# Default 50 items
GET /api/article/

# Custom page size
GET /api/article/?page_size=100

# Page 2
GET /api/article/?page=2&page_size=50
```

## Ordering

Add ordering to list endpoint:

```python
class ArticleViewSet(APIViewSet):
    model = Article
    api = api
    query_params = {
        "is_published": (bool, None),
        "ordering": (str, "-created_at"),  # Default: newest first
    }

    async def query_params_handler(self, queryset, filters):
        # Apply published filter
        if filters.get("is_published") is not None:
            queryset = queryset.filter(is_published=filters["is_published"])

        # Apply ordering
        ordering = filters.get("ordering", "-created_at")

        # Validate ordering field
        valid_fields = [
            "created_at", "-created_at",
            "title", "-title",
            "views", "-views",
            "published_at", "-published_at"
        ]

        if ordering in valid_fields:
            queryset = queryset.order_by(ordering)

        return queryset


ArticleViewSet().add_views_to_route()
```

**Usage:**

```bash
# Newest first (default)
GET /api/article/

# Oldest first
GET /api/article/?ordering=created_at

# By title A-Z
GET /api/article/?ordering=title

# By title Z-A
GET /api/article/?ordering=-title

# Most viewed
GET /api/article/?ordering=-views

# Recently published
GET /api/article/?ordering=-published_at
```

## Error Handling

Handle errors gracefully:

```python
from ninja_aio.exceptions import SerializeError, NotFoundError


class ArticleViewSet(APIViewSet):
    model = Article
    api = api

    def views(self):
        @self.router.post("/{pk}/publish/")
        async def publish(request, pk: int):
            try:
                article = await Article.objects.aget(pk=pk)
            except Article.DoesNotExist:
                raise NotFoundError(self.model)

            # Check if already published
            if article.is_published:
                raise SerializeError(
                    {"article": "already published"},
                    status_code=400
                )

            # Publish
            article.is_published = True
            from django.utils import timezone
            article.published_at = timezone.now()
            await article.asave()

            return {
                "message": "Article published successfully",
                "published_at": article.published_at
            }


ArticleViewSet().add_views_to_route()
```

## Disabling Endpoints

Disable specific CRUD operations:

```python
class CategoryViewSet(APIViewSet):
    model = Category
    api = api

    # Disable delete (categories can't be deleted)
    disable_delete = True

    # Disable update (categories are immutable)
    disable_update = True


CategoryViewSet().add_views_to_route()
```

Now only these endpoints are available:

- `GET /api/category/` - List
- `POST /api/category/` - Create
- `GET /api/category/{id}` - Retrieve

## Response Customization

Customize response format:

```python
class ArticleViewSet(APIViewSet):
    model = Article
    api = api

    def views(self):
        @self.router.get("/{pk}/")
        async def retrieve(request, pk: int):
            """Custom retrieve with additional data"""
            article = await Article.objects.select_related(
                'author', 'category'
            ).prefetch_related('tags').aget(pk=pk)

            # Serialize article
            from ninja_aio.models import ModelUtil
            util = ModelUtil(Article)
            schema = Article.generate_read_s()
            article_data = await util.read_s(request, article, schema)

            # Get related articles
            related = []
            async for rel_article in Article.objects.filter(
                category=article.category,
                is_published=True
            ).exclude(pk=pk)[:5]:
                rel_data = await util.read_s(request, rel_article, schema)
                related.append(rel_data)

            # Get author's other articles
            author_articles = []
            async for auth_article in Article.objects.filter(
                author=article.author,
                is_published=True
            ).exclude(pk=pk)[:5]:
                auth_data = await util.read_s(request, auth_article, schema)
                author_articles.append(auth_data)

            return {
                "article": article_data,
                "related_articles": related,
                "author_articles": author_articles,
                "meta": {
                    "total_views": article.views,
                    "author_article_count": await Article.objects.filter(
                        author=article.author
                    ).acount()
                }
            }


ArticleViewSet().add_views_to_route()
```

## Complete Example

Here's a complete ViewSet with all features:

```python
# views.py
from ninja_aio import NinjaAIO
from ninja_aio.views import APIViewSet
from ninja.pagination import PageNumberPagination
from ninja_aio.exceptions import SerializeError, NotFoundError
from .models import Article, Author, Category, Tag
from django.db.models import Q

api = NinjaAIO(
    title="Blog API",
    version="1.0.0",
    description="A complete blog API"
)


class CustomPagination(PageNumberPagination):
    page_size = 20
    max_page_size = 100


class AuthorViewSet(APIViewSet):
    model = Author
    api = api


class CategoryViewSet(APIViewSet):
    model = Category
    api = api


class TagViewSet(APIViewSet):
    model = Tag
    api = api


class ArticleViewSet(APIViewSet):
    model = Article
    api = api
    pagination_class = CustomPagination

    query_params = {
        "is_published": (bool, None),
        "author": (int, None),
        "category": (int, None),
        "tag": (int, None),
        "search": (str, None),
        "ordering": (str, "-created_at"),
    }

    async def query_params_handler(self, queryset, filters):
        # Published filter
        if filters.get("is_published") is not None:
            queryset = queryset.filter(is_published=filters["is_published"])

        # Author filter
        if filters.get("author"):
            queryset = queryset.filter(author_id=filters["author"])

        # Category filter
        if filters.get("category"):
            queryset = queryset.filter(category_id=filters["category"])

        # Tag filter
        if filters.get("tag"):
            queryset = queryset.filter(tags__id=filters["tag"])

        # Search
        if filters.get("search"):
            search = filters["search"]
            queryset = queryset.filter(
                Q(title__icontains=search) |
                Q(content__icontains=search) |
                Q(excerpt__icontains=search)
            )

        # Ordering
        ordering = filters.get("ordering", "-created_at")
        valid_orderings = [
            "created_at", "-created_at",
            "title", "-title",
            "views", "-views",
            "published_at", "-published_at"
        ]
        if ordering in valid_orderings:
            queryset = queryset.order_by(ordering)

        return queryset

    def views(self):
        # Publish article
        @self.router.post("/{pk}/publish/")
        async def publish(request, pk: int):
            try:
                article = await Article.objects.aget(pk=pk)
            except Article.DoesNotExist:
                raise NotFoundError(self.model)

            if article.is_published:
                raise SerializeError(
                    {"article": "already published"},
                    status_code=400
                )

            article.is_published = True
            from django.utils import timezone
            article.published_at = timezone.now()
            await article.asave()

            return {"message": "Article published", "published_at": article.published_at}

        # Unpublish article
        @self.router.post("/{pk}/unpublish/")
        async def unpublish(request, pk: int):
            try:
                article = await Article.objects.aget(pk=pk)
            except Article.DoesNotExist:
                raise NotFoundError(self.model)

            article.is_published = False
            article.published_at = None
            await article.asave()

            return {"message": "Article unpublished"}

        # Increment views
        @self.router.post("/{pk}/view/")
        async def view(request, pk: int):
            try:
                article = await Article.objects.aget(pk=pk)
            except Article.DoesNotExist:
                raise NotFoundError(self.model)

            article.views += 1
            await article.asave(update_fields=["views"])

            return {"views": article.views}

        # Statistics
        @self.router.get("/stats/")
        async def stats(request):
            from django.db.models import Count, Avg, Sum
            from asgiref.sync import sync_to_async

            total = await Article.objects.acount()
            published = await Article.objects.filter(is_published=True).acount()

            avg_views = await sync_to_async(
                lambda: Article.objects.aggregate(avg=Avg("views"))
            )()

            total_views = await sync_to_async(
                lambda: Article.objects.aggregate(total=Sum("views"))
            )()

            return {
                "total_articles": total,
                "published": published,
                "drafts": total - published,
                "avg_views": avg_views["avg"] or 0,
                "total_views": total_views["total"] or 0,
            }

        # Popular articles
        @self.router.get("/popular/")
        async def popular(request, limit: int = 10):
            articles = []
            async for article in Article.objects.filter(
                is_published=True
            ).order_by("-views")[:limit]:
                articles.append(article)

            from ninja_aio.models import ModelUtil
            util = ModelUtil(Article)
            schema = Article.generate_read_s()

            results = []
            for article in articles:
                data = await util.read_s(request, article, schema)
                results.append(data)

            return results


# Register ViewSets
AuthorViewSet().add_views_to_route()
CategoryViewSet().add_views_to_route()
TagViewSet().add_views_to_route()
ArticleViewSet().add_views_to_route()
```

## Testing Your API

Test your endpoints using curl, httpie, or the Swagger UI:

```bash
# List articles
curl http://localhost:8000/api/article/

# Create article
curl -X POST http://localhost:8000/api/article/ \
  -H "Content-Type: application/json" \
  -d '{
    "title": "My Article",
    "content": "Content here...",
    "author": 1,
    "category": 2
  }'

# Get article
curl http://localhost:8000/api/article/1

# Update article
curl -X PATCH http://localhost:8000/api/article/1/ \
  -H "Content-Type: application/json" \
  -d '{"title": "Updated Title"}'

# Delete article
curl -X DELETE http://localhost:8000/api/article/1/

# Custom endpoints
curl -X POST http://localhost:8000/api/article/1/publish/
curl http://localhost:8000/api/article/stats/
curl http://localhost:8000/api/article/popular/?limit=5
```

## Next Steps

Now that you have CRUD operations set up, let's add authentication in [Step 3: Add Authentication](authentication.md).

!!! success "What You've Learned" - ✅ Creating ViewSets for CRUD operations - ✅ Understanding auto-generated endpoints - ✅ Adding query parameters and filtering - ✅ Creating custom endpoints - ✅ Working with pagination - ✅ Handling errors properly - ✅ Customizing responses

## See Also

- [APIViewSet API Reference](../api/views/api_view_set.md) - Complete API documentation
- [Pagination](../api/pagination.md) - Advanced pagination options
- [ModelUtil](../api/models/model_util.md) - Working with models
