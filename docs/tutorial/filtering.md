# Step 4: Add Filtering & Pagination

In this final step, you'll learn how to implement advanced filtering, searching, and pagination for your API endpoints.

## What You'll Learn

- Query parameter filtering
- Full-text search
- Ordering and sorting
- Custom pagination
- Filter combinations
- Performance optimization

## Prerequisites

Make sure you've completed:

- [Step 1: Define Your Model](model.md)
- [Step 2: Create CRUD Views](crud.md)
- [Step 3: Add Authentication](authentication.md)

## Basic Filtering

### Simple Field Filters

```python
# views.py
from ninja_aio.views import APIViewSet
from .models import Article

class ArticleViewSet(APIViewSet):
    model = Article
    api = api

    query_params = {
        "is_published": (bool, None),
        "author": (int, None),
        "category": (int, None),
    }

    async def query_params_handler(self, queryset, filters):
        # Filter by published status
        if filters.get("is_published") is not None:
            queryset = queryset.filter(is_published=filters["is_published"])

        # Filter by author ID
        if filters.get("author"):
            queryset = queryset.filter(author_id=filters["author"])

        # Filter by category ID
        if filters.get("category"):
            queryset = queryset.filter(category_id=filters["category"])

        return queryset


ArticleViewSet().add_views_to_route()
```

**Usage:**

```bash
# Get published articles
GET /api/article/?is_published=true

# Get articles by author
GET /api/article/?author=5

# Get articles in category
GET /api/article/?category=3

# Combine filters
GET /api/article/?is_published=true&author=5&category=3
```

### Date Range Filters

```python
from datetime import datetime

class ArticleViewSet(APIViewSet):
    model = Article
    api = api

    query_params = {
        "created_after": (str, None),   # ISO date string
        "created_before": (str, None),
        "published_after": (str, None),
        "published_before": (str, None),
    }

    async def query_params_handler(self, queryset, filters):
        # Filter by creation date
        if filters.get("created_after"):
            date = datetime.fromisoformat(filters["created_after"])
            queryset = queryset.filter(created_at__gte=date)

        if filters.get("created_before"):
            date = datetime.fromisoformat(filters["created_before"])
            queryset = queryset.filter(created_at__lte=date)

        # Filter by publication date
        if filters.get("published_after"):
            date = datetime.fromisoformat(filters["published_after"])
            queryset = queryset.filter(published_at__gte=date)

        if filters.get("published_before"):
            date = datetime.fromisoformat(filters["published_before"])
            queryset = queryset.filter(published_at__lte=date)

        return queryset
```

**Usage:**

```bash
# Articles created after a date
GET /api/article/?created_after=2024-01-01

# Articles published in a date range
GET /api/article/?published_after=2024-01-01&published_before=2024-01-31

# Articles from last 7 days
GET /api/article/?created_after=2024-01-15
```

### Numeric Range Filters

```python
class ArticleViewSet(APIViewSet):
    model = Article
    api = api

    query_params = {
        "min_views": (int, None),
        "max_views": (int, None),
        "min_rating": (float, None),
        "max_rating": (float, None),
    }

    async def query_params_handler(self, queryset, filters):
        # Filter by views
        if filters.get("min_views"):
            queryset = queryset.filter(views__gte=filters["min_views"])

        if filters.get("max_views"):
            queryset = queryset.filter(views__lte=filters["max_views"])

        # Filter by rating
        if filters.get("min_rating"):
            queryset = queryset.filter(rating__gte=filters["min_rating"])

        if filters.get("max_rating"):
            queryset = queryset.filter(rating__lte=filters["max_rating"])

        return queryset
```

**Usage:**

```bash
# Popular articles (1000+ views)
GET /api/article/?min_views=1000

# Highly rated articles (4.5+)
GET /api/article/?min_rating=4.5

# Articles with 100-1000 views
GET /api/article/?min_views=100&max_views=1000
```

## Search Functionality

### Simple Text Search

```python
from django.db.models import Q

class ArticleViewSet(APIViewSet):
    model = Article
    api = api

    query_params = {
        "search": (str, None),
    }

    async def query_params_handler(self, queryset, filters):
        if filters.get("search"):
            search_term = filters["search"]
            queryset = queryset.filter(
                Q(title__icontains=search_term) |
                Q(content__icontains=search_term) |
                Q(excerpt__icontains=search_term)
            )

        return queryset
```

**Usage:**

```bash
# Search in title and content
GET /api/article/?search=django

# Search with other filters
GET /api/article/?search=tutorial&is_published=true
```

### Full-Text Search (PostgreSQL)

For better performance with large datasets:

```python
from django.contrib.postgres.search import SearchVector, SearchQuery, SearchRank

class ArticleViewSet(APIViewSet):
    model = Article
    api = api

    query_params = {
        "search": (str, None),
    }

    async def query_params_handler(self, queryset, filters):
        if filters.get("search"):
            search_term = filters["search"]

            # Create search vector
            vector = SearchVector('title', weight='A') + \
                     SearchVector('content', weight='B')

            query = SearchQuery(search_term)

            # Filter and rank by relevance
            queryset = queryset.annotate(
                rank=SearchRank(vector, query)
            ).filter(
                rank__gte=0.1
            ).order_by('-rank')

        return queryset
```

### Search with Highlights

```python
from django.contrib.postgres.search import SearchVector, SearchQuery, SearchHeadline

class ArticleViewSet(APIViewSet):
    model = Article
    api = api

    query_params = {
        "search": (str, None),
    }

    async def query_params_handler(self, queryset, filters):
        if filters.get("search"):
            search_term = filters["search"]
            query = SearchQuery(search_term)

            # Add highlighted excerpts
            queryset = queryset.annotate(
                headline=SearchHeadline(
                    'content',
                    query,
                    start_sel='<mark>',
                    stop_sel='</mark>',
                    max_words=50,
                )
            )

        return queryset
```

## Ordering

### Basic Ordering

```python
class ArticleViewSet(APIViewSet):
    model = Article
    api = api

    query_params = {
        "ordering": (str, "-created_at"),  # Default: newest first
    }

    async def query_params_handler(self, queryset, filters):
        ordering = filters.get("ordering", "-created_at")

        # Whitelist allowed ordering fields
        valid_orderings = [
            "created_at", "-created_at",
            "updated_at", "-updated_at",
            "title", "-title",
            "views", "-views",
            "rating", "-rating",
            "published_at", "-published_at",
        ]

        if ordering in valid_orderings:
            queryset = queryset.order_by(ordering)

        return queryset
```

**Usage:**

```bash
# Newest first (default)
GET /api/article/?ordering=-created_at

# Oldest first
GET /api/article/?ordering=created_at

# By title A-Z
GET /api/article/?ordering=title

# Most viewed
GET /api/article/?ordering=-views

# Highest rated
GET /api/article/?ordering=-rating
```

### Multiple Field Ordering

```python
class ArticleViewSet(APIViewSet):
    model = Article
    api = api

    query_params = {
        "ordering": (str, "-created_at,title"),  # Multiple fields
    }

    async def query_params_handler(self, queryset, filters):
        ordering = filters.get("ordering", "-created_at,title")

        # Parse ordering string
        order_fields = ordering.split(',')

        # Validate each field
        valid_fields = {
            "created_at", "-created_at",
            "title", "-title",
            "views", "-views",
        }

        validated_fields = [
            field for field in order_fields
            if field in valid_fields
        ]

        if validated_fields:
            queryset = queryset.order_by(*validated_fields)

        return queryset
```

**Usage:**

```bash
# Order by date, then title
GET /api/article/?ordering=-created_at,title

# Order by views, then rating
GET /api/article/?ordering=-views,-rating
```

## Advanced Filtering

### Related Field Filters

```python
class ArticleViewSet(APIViewSet):
    model = Article
    api = api

    query_params = {
        "author_username": (str, None),
        "category_slug": (str, None),
        "tag_name": (str, None),
    }

    async def query_params_handler(self, queryset, filters):
        # Filter by author username
        if filters.get("author_username"):
            queryset = queryset.filter(
                author__username__iexact=filters["author_username"]
            )

        # Filter by category slug
        if filters.get("category_slug"):
            queryset = queryset.filter(
                category__slug=filters["category_slug"]
            )

        # Filter by tag name
        if filters.get("tag_name"):
            queryset = queryset.filter(
                tags__name__iexact=filters["tag_name"]
            )

        return queryset
```

**Usage:**

```bash
# By author username
GET /api/article/?author_username=johndoe

# By category slug
GET /api/article/?category_slug=tutorials

# By tag name
GET /api/article/?tag_name=python
```

### Multiple Tags Filter

```python
class ArticleViewSet(APIViewSet):
    model = Article
    api = api

    query_params = {
        "tags": (str, None),  # Comma-separated tag IDs or names
        "tags_mode": (str, "any"),  # "any" or "all"
    }

    async def query_params_handler(self, queryset, filters):
        if filters.get("tags"):
            tag_list = filters["tags"].split(',')
            mode = filters.get("tags_mode", "any")

            # Check if tags are IDs or names
            if tag_list[0].isdigit():
                # Filter by tag IDs
                tag_ids = [int(t) for t in tag_list]

                if mode == "all":
                    # Must have ALL tags
                    for tag_id in tag_ids:
                        queryset = queryset.filter(tags__id=tag_id)
                else:
                    # Must have ANY tag
                    queryset = queryset.filter(tags__id__in=tag_ids).distinct()
            else:
                # Filter by tag names
                if mode == "all":
                    for tag_name in tag_list:
                        queryset = queryset.filter(tags__name__iexact=tag_name)
                else:
                    queryset = queryset.filter(
                        tags__name__in=tag_list
                    ).distinct()

        return queryset
```

**Usage:**

```bash
# Articles with ANY of these tags
GET /api/article/?tags=1,2,3

# Articles with ALL of these tags
GET /api/article/?tags=python,django,tutorial&tags_mode=all

# Using tag IDs
GET /api/article/?tags=1,2,3&tags_mode=all
```

### Exclude Filters

```python
class ArticleViewSet(APIViewSet):
    model = Article
    api = api

    query_params = {
        "exclude_author": (int, None),
        "exclude_category": (int, None),
        "exclude_ids": (str, None),  # Comma-separated IDs
    }

    async def query_params_handler(self, queryset, filters):
        # Exclude specific author
        if filters.get("exclude_author"):
            queryset = queryset.exclude(author_id=filters["exclude_author"])

        # Exclude specific category
        if filters.get("exclude_category"):
            queryset = queryset.exclude(category_id=filters["exclude_category"])

        # Exclude specific article IDs
        if filters.get("exclude_ids"):
            ids = [int(id) for id in filters["exclude_ids"].split(',')]
            queryset = queryset.exclude(id__in=ids)

        return queryset
```

**Usage:**

```bash
# Exclude articles by specific author
GET /api/article/?exclude_author=5

# Exclude specific articles
GET /api/article/?exclude_ids=1,2,3
```

## Pagination

### Default Pagination

Django Ninja Aio CRUD uses page-number pagination by default:

```python
class ArticleViewSet(APIViewSet):
    model = Article
    api = api
    # Uses default PageNumberPagination
```

**Usage:**

```bash
# First page (10 items)
GET /api/article/?page=1

# Custom page size
GET /api/article/?page=1&page_size=20

# Second page
GET /api/article/?page=2&page_size=20
```

**Response:**

```json
{
  "count": 150,
  "next": 3,
  "previous": 1,
  "results": [...]
}
```

### Custom Pagination

```python
from ninja.pagination import PageNumberPagination


class CustomPagination(PageNumberPagination):
    page_size = 25  # Default items per page
    max_page_size = 100  # Maximum allowed


class ArticleViewSet(APIViewSet):
    model = Article
    api = api
    pagination_class = CustomPagination
```

### Disable Pagination

```python
class ArticleViewSet(APIViewSet):
    model = Article
    api = api
    pagination_class = None  # Return all results


# Or conditionally
class ConditionalPagination(PageNumberPagination):
    async def apaginate_queryset(self, queryset, pagination, request=None, **params):
        # Disable if 'all' parameter present
        if params.get('all'):
            items = []
            async for item in queryset:
                items.append(item)
            return {"results": items}

        return await super().apaginate_queryset(queryset, pagination, request, **params)
```

## Filter Presets

Create reusable filter combinations:

```python
class ArticleViewSet(APIViewSet):
    model = Article
    api = api

    query_params = {
        "preset": (str, None),
        # ... other filters
    }

    async def query_params_handler(self, queryset, filters):
        preset = filters.get("preset")

        # Apply preset filters
        if preset == "trending":
            # Popular recent articles
            from django.utils import timezone
            from datetime import timedelta

            last_week = timezone.now() - timedelta(days=7)
            queryset = queryset.filter(
                created_at__gte=last_week,
                is_published=True
            ).order_by('-views', '-rating')

        elif preset == "featured":
            # Featured articles
            queryset = queryset.filter(
                is_published=True,
                is_featured=True
            ).order_by('-featured_at')

        elif preset == "recent":
            # Recently published
            queryset = queryset.filter(
                is_published=True
            ).order_by('-published_at')[:20]

        elif preset == "popular":
            # All-time most viewed
            queryset = queryset.filter(
                is_published=True
            ).order_by('-views')[:50]

        # Apply other filters
        # ...

        return queryset
```

**Usage:**

```bash
# Get trending articles
GET /api/article/?preset=trending

# Get featured articles
GET /api/article/?preset=featured

# Combine with other filters
GET /api/article/?preset=recent&category=1
```

## Performance Optimization

### Select Related

Optimize queries with foreign keys:

```python
class Article(ModelSerializer):
    # ... fields ...

    @classmethod
    async def queryset_request(cls, request):
        # Always include related objects
        return cls.objects.select_related(
            'author',
            'category'
        ).prefetch_related(
            'tags',
            'comments'
        )


class ArticleViewSet(APIViewSet):
    model = Article
    api = api
    # Queries are now optimized automatically
```

### Index Database Fields

```python
# models.py
class Article(ModelSerializer):
    title = models.CharField(max_length=200, db_index=True)
    slug = models.SlugField(unique=True, db_index=True)
    is_published = models.BooleanField(default=False, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        indexes = [
            models.Index(fields=['-created_at']),
            models.Index(fields=['is_published', '-created_at']),
            models.Index(fields=['author', '-created_at']),
            models.Index(fields=['category', '-created_at']),
        ]
```

### Limit Query Results

```python
class ArticleViewSet(APIViewSet):
    model = Article
    api = api

    async def query_params_handler(self, queryset, filters):
        # Apply filters
        # ...

        # Limit results for expensive queries
        if filters.get("search"):
            queryset = queryset[:1000]  # Max 1000 results for search

        return queryset
```

## Complete Example

Here's a comprehensive filtering implementation:

```python
# views.py
from ninja_aio import NinjaAIO
from ninja_aio.views import APIViewSet
from ninja.pagination import PageNumberPagination
from django.db.models import Q
from datetime import datetime
from .models import Article

api = NinjaAIO(title="Blog API", version="1.0.0")


class ArticlePagination(PageNumberPagination):
    page_size = 20
    max_page_size = 100


class ArticleViewSet(APIViewSet):
    model = Article
    api = api
    pagination_class = ArticlePagination

    query_params = {
        # Basic filters
        "is_published": (bool, None),
        "author": (int, None),
        "category": (int, None),

        # Text search
        "search": (str, None),

        # Date range
        "created_after": (str, None),
        "created_before": (str, None),

        # Numeric range
        "min_views": (int, None),
        "max_views": (int, None),

        # Related filters
        "author_username": (str, None),
        "category_slug": (str, None),
        "tags": (str, None),
        "tags_mode": (str, "any"),

        # Ordering
        "ordering": (str, "-created_at"),

        # Presets
        "preset": (str, None),
    }

    async def query_params_handler(self, queryset, filters):
        # Apply preset first
        preset = filters.get("preset")
        if preset == "trending":
            from django.utils import timezone
            from datetime import timedelta
            last_week = timezone.now() - timedelta(days=7)
            queryset = queryset.filter(
                created_at__gte=last_week,
                is_published=True
            )
        elif preset == "popular":
            queryset = queryset.filter(is_published=True)

        # Published status
        if filters.get("is_published") is not None:
            queryset = queryset.filter(is_published=filters["is_published"])

        # Author filter
        if filters.get("author"):
            queryset = queryset.filter(author_id=filters["author"])
        elif filters.get("author_username"):
            queryset = queryset.filter(
                author__username__iexact=filters["author_username"]
            )

        # Category filter
        if filters.get("category"):
            queryset = queryset.filter(category_id=filters["category"])
        elif filters.get("category_slug"):
            queryset = queryset.filter(category__slug=filters["category_slug"])

        # Tags filter
        if filters.get("tags"):
            tag_list = filters["tags"].split(',')
            mode = filters.get("tags_mode", "any")

            if mode == "all":
                for tag in tag_list:
                    if tag.isdigit():
                        queryset = queryset.filter(tags__id=int(tag))
                    else:
                        queryset = queryset.filter(tags__name__iexact=tag)
            else:
                if tag_list[0].isdigit():
                    tag_ids = [int(t) for t in tag_list]
                    queryset = queryset.filter(tags__id__in=tag_ids).distinct()
                else:
                    queryset = queryset.filter(tags__name__in=tag_list).distinct()

        # Search
        if filters.get("search"):
            search_term = filters["search"]
            queryset = queryset.filter(
                Q(title__icontains=search_term) |
                Q(content__icontains=search_term)
            )

        # Date range
        if filters.get("created_after"):
            date = datetime.fromisoformat(filters["created_after"])
            queryset = queryset.filter(created_at__gte=date)

        if filters.get("created_before"):
            date = datetime.fromisoformat(filters["created_before"])
            queryset = queryset.filter(created_at__lte=date)

        # Views range
        if filters.get("min_views"):
            queryset = queryset.filter(views__gte=filters["min_views"])

        if filters.get("max_views"):
            queryset = queryset.filter(views__lte=filters["max_views"])

        # Ordering
        ordering = filters.get("ordering", "-created_at")
        valid_orderings = [
            "created_at", "-created_at",
            "title", "-title",
            "views", "-views",
            "published_at", "-published_at",
        ]

        if ordering in valid_orderings:
            queryset = queryset.order_by(ordering)
        elif preset == "trending":
            queryset = queryset.order_by('-views', '-rating')
        elif preset == "popular":
            queryset = queryset.order_by('-views')

        return queryset


ArticleViewSet().add_views_to_route()
```

## Testing Filters

```bash
# Basic filtering
curl "http://localhost:8000/api/article/?is_published=true"

# Search
curl "http://localhost:8000/api/article/?search=django"

# Date range
curl "http://localhost:8000/api/article/?created_after=2024-01-01&created_before=2024-01-31"

# Multiple filters
curl "http://localhost:8000/api/article/?is_published=true&category=1&min_views=100&ordering=-views"

# Tags
curl "http://localhost:8000/api/article/?tags=python,django&tags_mode=all"

# Presets
curl "http://localhost:8000/api/article/?preset=trending"

# Pagination
curl "http://localhost:8000/api/article/?page=2&page_size=50"

# Combined
curl "http://localhost:8000/api/article/?search=tutorial&category=1&is_published=true&min_views=1000&ordering=-rating&page=1&page_size=20"
```

## Congratulations! 🎉

You've completed all tutorial steps and built a complete, production-ready API with:

- ✅ Models with automatic schema generation
- ✅ Full CRUD operations
- ✅ JWT authentication
- ✅ Custom schemas and validation
- ✅ Advanced filtering and search
- ✅ Pagination
- ✅ Performance optimization

## Next Steps

Explore advanced topics:

- [API Reference](../api/views/api_view_set.md) - Complete API documentation
- [Authentication](../api/authentication.md) - Advanced auth patterns
- [Pagination](../api/pagination.md) - Custom pagination strategies

## See Also

- [Pagination API Reference](../api/pagination.md) - Pagination classes
- [ModelUtil](../api/models/model_util.md) - Query optimization
