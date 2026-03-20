<div class="tutorial-hero" markdown>

<span class="step-indicator">Step 2 of 4</span>

# Create CRUD Views

<p class="tutorial-subtitle">
Build a complete REST API with automatic CRUD operations using <code>APIViewSet</code>.
</p>

</div>

<div class="learning-objectives" markdown>

### :material-school: What You'll Learn

- :material-view-grid: How to create a basic ViewSet
- :material-auto-fix: Understanding auto-generated endpoints
- :material-filter: Customizing query parameters
- :material-content-copy: Enabling bulk operations
- :material-pencil-plus: Adding custom endpoints
- :material-web: Working with request context
- :material-alert-circle: Handling errors

</div>

<div class="prerequisites" markdown>

**Prerequisites** — Make sure you've completed [Step 1: Define Your Model](model.md). You should have the `Article`, `Author`, `Category`, and `Tag` models defined.

</div>

---

## :material-view-grid: Basic ViewSet

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
    description="A simple blog API built with Django Ninja AIO"
)


@api.viewset(model=Article)
class ArticleViewSet(APIViewSet):
    pass
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

---

## :material-view-grid-plus: Creating Multiple ViewSets

Let's add APIs for all our models:

```python
# views.py
from ninja_aio import NinjaAIO
from ninja_aio.views import APIViewSet
from .models import Article, Author, Category, Tag

api = NinjaAIO(title="Blog API", version="1.0.0")


@api.viewset(model=Author)
class AuthorViewSet(APIViewSet):
    pass


@api.viewset(model=Category)
class CategoryViewSet(APIViewSet):
    pass


@api.viewset(model=Tag)
class TagViewSet(APIViewSet):
    pass


@api.viewset(model=Article)
class ArticleViewSet(APIViewSet):
    pass
```

Now you have complete CRUD APIs for all models:

- `/api/author/`
- `/api/category/`
- `/api/tag/`
- `/api/article/`

---

## :material-filter-variant: Adding Query Parameters

Let's add filtering to the Article list endpoint:

```python
@api.viewset(model=Article)
class ArticleViewSet(APIViewSet):
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

---

## :material-pencil-plus: Custom Endpoints (using `@api_get` / `@api_post`)

Add custom endpoints beyond CRUD using method decorators. For a higher-level alternative with automatic URL generation, auth inheritance, and detail/list distinction, see [Custom Actions](#custom-actions) below.

```python
from ninja_aio.decorators import api_get, api_post


@api.viewset(model=Article)
class ArticleViewSet(APIViewSet):
    # Publish an article
    @api_post("/{pk}/publish/")
    async def publish(self, request, pk: int):
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
    @api_post("/{pk}/unpublish/")
    async def unpublish(self, request, pk: int):
        article = await Article.objects.aget(pk=pk)
        article.is_published = False
        article.published_at = None
        await article.asave()

        return {"message": "Article unpublished successfully"}

    # Increment view count
    @api_post("/{pk}/view/")
    async def increment_views(self, request, pk: int):
        article = await Article.objects.aget(pk=pk)
        article.views += 1
        await article.asave(update_fields=["views"])

        return {"views": article.views}

    # Get article statistics
    @api_get("/stats/")
    async def stats(self, request):
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
    @api_get("/popular/")
    async def popular(self, request, limit: int = 10):
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

---

## :material-star: Custom Actions

Use the `@action` decorator to add custom endpoints to your ViewSet. Actions can operate on single instances (detail) or the collection (list):

```python
from ninja import Schema, Status
from ninja_aio.views import APIViewSet
from ninja_aio.decorators import action
from .models import Article


class CountSchema(Schema):
    count: int


@api.viewset(model=Article)
class ArticleViewSet(APIViewSet):
    # Detail action: operates on a single article
    @action(detail=True, methods=["post"], url_path="activate")
    async def activate(self, request, pk):
        obj = await self.model_util.get_object(request, pk)
        obj.is_active = True
        await obj.asave()
        return Status(200, {"message": "activated"})

    # List action: operates on the collection
    @action(detail=False, methods=["get"], url_path="count", response=CountSchema)
    async def count(self, request):
        total = await self.model.objects.acount()
        return {"count": total}

    # Action with request body
    @action(detail=False, methods=["post"], url_path="import")
    async def import_articles(self, request, data: ArticleImportSchema):
        return Status(200, {"message": f"imported {len(data.items)} articles"})

    # Auto url_path from method name (underscores → hyphens)
    @action(detail=False, methods=["get"])
    async def recent_published(self, request):
        return {"message": "recent"}
```

This generates:

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/article/{id}/activate` | Activate a single article |
| `GET` | `/api/article/count` | Count all articles |
| `POST` | `/api/article/import` | Import articles |
| `GET` | `/api/article/recent-published` | Recent published (auto path) |

### Key differences from `@api_get` / `@api_post`

| Feature | `@action` | `@api_get` / `@api_post` |
|---------|-----------|--------------------------|
| Detail actions (with pk) | `detail=True` auto-adds `{pk}` | Manual `/{pk}/path` |
| Multiple methods | `methods=["get", "post"]` | One decorator per method |
| Auth inheritance | Inherits from viewset per-verb auth | Manual `auth=` |
| URL path | Auto-generated from method name | Manual path required |
| OpenAPI metadata | `summary`, `description`, `tags`, `deprecated` | Same via kwargs |

!!! tip
    Actions are **not affected** by `disable = ["all"]` — they are always registered, even when all CRUD endpoints are disabled.

---

## :material-web: Request Context

Access request information in your ViewSet:

```python
from ninja_aio.decorators import api_get, api_post


@api.viewset(model=Article)
class ArticleViewSet(APIViewSet):
    @api_get("/my-articles/")
    async def my_articles(self, request):
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

    @api_post("/")
    async def create_article(self, request, data: Article.generate_create_s()):
        """Override create to set author from request"""
        # Set author from authenticated user
        data.author = request.auth.id

        # Use default create logic
        from ninja_aio.models import ModelUtil
        util = ModelUtil(Article)
        schema = Article.generate_read_s()

        return await util.create_s(request, data, schema)
```

## :material-account-filter: Filtering by User

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


@api.viewset(model=Article)
class ArticleViewSet(APIViewSet):
    pass
    # queryset_request is automatically called for all operations
```

## :material-page-next: Custom Pagination

Override default pagination:

```python
from ninja.pagination import PageNumberPagination


class LargePagePagination(PageNumberPagination):
    page_size = 50  # Default 50 items per page
    max_page_size = 200  # Allow up to 200 items


@api.viewset(model=Article)
class ArticleViewSet(APIViewSet):
    pagination_class = LargePagePagination
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

## :material-sort: Ordering

Add native ordering to the list endpoint with `ordering_fields` and `default_ordering`:

```python
@api.viewset(model=Article)
class ArticleViewSet(APIViewSet):
    ordering_fields = ["created_at", "title", "views", "published_at"]
    default_ordering = "-created_at"  # Newest first by default
```

That's it! The framework automatically adds an `ordering` query parameter to the list endpoint and validates fields.

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

# Multiple fields (comma-separated)
GET /api/article/?ordering=-views,title

# Combined with filters
GET /api/article/?ordering=-created_at&is_published=true
```

!!! tip
    Invalid field names are silently ignored. If all requested fields are invalid, `default_ordering` is applied.

---

## :material-alert-circle: Error Handling

Handle errors gracefully:

```python
from ninja_aio.exceptions import SerializeError, NotFoundError
from ninja_aio.decorators import api_post


@api.viewset(model=Article)
class ArticleViewSet(APIViewSet):
    @api_post("/{pk}/publish/")
    async def publish(self, request, pk: int):
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
```

## :material-content-copy: Bulk Operations

Need to create, update, or delete multiple objects at once? Enable bulk operations:

```python
@api.viewset(model=Article)
class ArticleViewSet(APIViewSet):
    bulk_operations = ["create", "update", "delete"]
```

This adds three new endpoints to your API:

| Method   | Endpoint              | Description                    | Request Body              | Response              |
| -------- | --------------------- | ------------------------------ | ------------------------- | --------------------- |
| `POST`   | `/api/articles/bulk/`  | Create multiple articles       | `[{...}, {...}]`          | `200 BulkResultSchema` |
| `PATCH`  | `/api/articles/bulk/`  | Update multiple articles       | `[{id, ...}, {id, ...}]`  | `200 BulkResultSchema` |
| `DELETE` | `/api/articles/bulk/`  | Delete multiple articles       | `{"ids": [1, 2, 3]}`     | `200 BulkResultSchema` |

Bulk operations use **partial success** semantics — each item is processed independently. Successful items are committed while failures are collected in the response without affecting other items.

### Response Format

All bulk endpoints return a `BulkResultSchema`:

```json
{
  "success": {
    "count": 2,
    "details": [1, 3]
  },
  "errors": {
    "count": 1,
    "details": [{"error": "Not found."}]
  }
}
```

- **`success.details`** contains the primary keys of successfully processed objects (default). Customizable via `bulk_response_fields`.
- **`errors.details`** contains error details for each failed item.

### Bulk Create

Send a list of objects to create them all in one request:

```bash
curl -X POST http://localhost:8000/api/article/bulk/ \
  -H "Content-Type: application/json" \
  -d '[
    {"title": "Article 1", "content": "Content 1", "author": 1},
    {"title": "Article 2", "content": "Content 2", "author": 1},
    {"title": "Article 3", "content": "Content 3", "author": 2}
  ]'
```

### Bulk Update

Send a list of objects with their primary key and the fields to update:

```bash
curl -X PATCH http://localhost:8000/api/article/bulk/ \
  -H "Content-Type: application/json" \
  -d '[
    {"id": 1, "title": "Updated Title 1"},
    {"id": 2, "title": "Updated Title 2", "is_published": true}
  ]'
```

### Bulk Delete

Send a list of primary keys to delete. This operation is **optimized** — it uses a single database query to delete all existing objects instead of deleting them one by one:

```bash
curl -X DELETE http://localhost:8000/api/article/bulk/ \
  -H "Content-Type: application/json" \
  -d '{"ids": [1, 2, 3]}'
```

### Custom Response Fields

By default, `success.details` returns primary keys. Use `bulk_response_fields` to customize what's returned:

```python
@api.viewset(model=Article)
class ArticleViewSet(APIViewSet):
    bulk_operations = ["create", "update", "delete"]
    bulk_response_fields = "title"  # Returns ["Article 1", "Article 2"]
    # Or return multiple fields as dicts:
    # bulk_response_fields = ["id", "title"]  # Returns [{"id": 1, "title": "..."}, ...]
```

### Selective Bulk Operations

You can enable only the operations you need:

```python
@api.viewset(model=Article)
class ArticleViewSet(APIViewSet):
    bulk_operations = ["create"]  # Only bulk create
```

!!! tip
    Bulk operations reuse your existing `schema_in` and `schema_update` schemas, so all validations and hooks (like `custom_actions` and `post_create`) are applied per item.

---

## :material-shield-check: Partial Update Validation

By default, PATCH endpoints accept empty payloads. Enable validation to reject them:

```python
@api.viewset(model=Article)
class ArticleViewSet(APIViewSet):
    require_update_fields = True
```

Empty PATCH requests will return a `400` error: `"No fields provided for update."`. This also applies to bulk updates — empty items are collected as errors in partial success responses.

---

## :material-eye-off: Disabling Endpoints

Disable specific CRUD operations:

```python
@api.viewset(model=Category)
class CategoryViewSet(APIViewSet):
    # Disable delete (categories can't be deleted)
    disable_delete = True

    # Disable update (categories are immutable)
    disable_update = True
```

Now only these endpoints are available:

- `GET /api/category/` - List
- `POST /api/category/` - Create
- `GET /api/category/{id}` - Retrieve

## :material-code-json: Response Customization

Customize response format:

```python
from ninja_aio.decorators import api_get


@api.viewset(model=Article)
class ArticleViewSet(APIViewSet):
    @api_get("/{pk}/")
    async def retrieve(self, request, pk: int):
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
```

---

## :material-code-braces: Complete Example

Here's a complete ViewSet with all features:

??? example "Full ViewSet code (click to expand)"

    ```python
    # views.py
    from ninja_aio import NinjaAIO
    from ninja_aio.views import APIViewSet
    from ninja.pagination import PageNumberPagination
    from ninja_aio.exceptions import SerializeError, NotFoundError
    from ninja_aio.decorators import api_get, api_post
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


    @api.viewset(model=Author)
    class AuthorViewSet(APIViewSet):
        pass


    @api.viewset(model=Category)
    class CategoryViewSet(APIViewSet):
        pass


    @api.viewset(model=Tag)
    class TagViewSet(APIViewSet):
        pass


    @api.viewset(model=Article)
    class ArticleViewSet(APIViewSet):
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

        # Publish article
        @api_post("/{pk}/publish/")
        async def publish(self, request, pk: int):
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
        @api_post("/{pk}/unpublish/")
        async def unpublish(self, request, pk: int):
            try:
                article = await Article.objects.aget(pk=pk)
            except Article.DoesNotExist:
                raise NotFoundError(self.model)

            article.is_published = False
            article.published_at = None
            await article.asave()

            return {"message": "Article unpublished"}

        # Increment views
        @api_post("/{pk}/view/")
        async def view(self, request, pk: int):
            try:
                article = await Article.objects.aget(pk=pk)
            except Article.DoesNotExist:
                raise NotFoundError(self.model)

            article.views += 1
            await article.asave(update_fields=["views"])

            return {"views": article.views}

        # Statistics
        @api_get("/stats/")
        async def stats(self, request):
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
        @api_get("/popular/")
        async def popular(self, request, limit: int = 10):
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


    ```

## :material-test-tube: Testing Your API

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

---

<div class="next-step" markdown>

**Ready for the next step?**

Now that you have CRUD operations set up, let's add authentication!

[Step 3: Add Authentication :material-arrow-right:](authentication.md){ .md-button .md-button--primary }

</div>

<div class="summary-checklist" markdown>

### :material-check-all: What You've Learned

- :material-check: Creating ViewSets for CRUD operations
- :material-check: Understanding auto-generated endpoints
- :material-check: Adding query parameters and filtering
- :material-check: Creating custom endpoints
- :material-check: Working with pagination
- :material-check: Handling errors properly
- :material-check: Using bulk operations
- :material-check: Customizing responses

</div>

<div class="grid cards" markdown>

-   :material-book-open-variant:{ .lg .middle } **API Reference**

    ---

    [:octicons-arrow-right-24: APIViewSet](../api/views/api_view_set.md) &middot; [:octicons-arrow-right-24: Pagination](../api/pagination.md) &middot; [:octicons-arrow-right-24: ModelUtil](../api/models/model_util.md)

</div>
