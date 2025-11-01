# Pagination

Django Ninja Aio CRUD provides built-in async pagination support for efficiently handling large datasets in your API responses.

## Overview

Pagination in Django Ninja Aio CRUD:

- **Fully async** - No blocking database queries
- **Customizable** - Override default behavior per ViewSet
- **Type-safe** - Proper type hints and validation
- **Automatic** - Works out of the box with APIViewSet
- **Flexible** - Support for multiple pagination styles

## Default Pagination

### PageNumberPagination

The default pagination class used by `APIViewSet`.

**Features:**

- Page-based navigation
- Configurable page size
- Total count included
- Next/previous page info

**Default Configuration:**

| Parameter       | Default | Description               |
| --------------- | ------- | ------------------------- |
| `page`          | `1`     | Current page number       |
| `page_size`     | `10`    | Items per page            |
| `max_page_size` | `100`   | Maximum allowed page size |

### Response Format

```json
{
  "count": 45,
  "next": 3,
  "previous": 1,
  "results": [
    {
      "id": 11,
      "title": "Article 11",
      "created_at": "2024-01-15T10:30:00Z"
    },
    {
      "id": 12,
      "title": "Article 12",
      "created_at": "2024-01-15T11:00:00Z"
    }
  ]
}
```

**Response Fields:**

| Field      | Type          | Description                               |
| ---------- | ------------- | ----------------------------------------- |
| `count`    | `int`         | Total number of items                     |
| `next`     | `int \| None` | Next page number (null if last page)      |
| `previous` | `int \| None` | Previous page number (null if first page) |
| `results`  | `list`        | Array of items for current page           |

## Basic Usage

### With APIViewSet

Pagination is automatically applied to list endpoints:

```python
from ninja_aio import NinjaAIO
from ninja_aio.views import APIViewSet
from .models import Article

api = NinjaAIO()


class ArticleViewSet(APIViewSet):
    model = Article
    api = api


ArticleViewSet().add_views_to_route()
```

**Generated endpoint:**

```
GET /article/?page=1&page_size=10
```

### Manual Usage

```python
from ninja.pagination import PageNumberPagination
from django.http import HttpRequest

async def my_view(request: HttpRequest):
    # Get queryset
    queryset = Article.objects.all()

    # Create paginator
    paginator = PageNumberPagination()

    # Paginate (accepts query params from request)
    result = await paginator.apaginate_queryset(
        queryset=queryset,
        pagination=paginator,
        request=request
    )

    return result
```

## Query Parameters

### page

Current page number (1-indexed).

```bash
GET /article/?page=2
```

**Validation:**

- Must be >= 1
- Returns 404 if page doesn't exist

### page_size

Number of items per page.

```bash
GET /article/?page=1&page_size=20
```

**Validation:**

- Must be >= 1
- Cannot exceed `max_page_size`
- Defaults to pagination class default

### Examples

**First page with 10 items:**

```bash
GET /article/?page=1&page_size=10
```

**Second page with 25 items:**

```bash
GET /article/?page=2&page_size=25
```

**Maximum items per page:**

```bash
GET /article/?page=1&page_size=100
```

## Custom Pagination

### Override Default Page Size

```python
from ninja.pagination import PageNumberPagination


class LargePagePagination(PageNumberPagination):
    page_size = 50  # Default 50 items per page
    max_page_size = 200  # Allow up to 200 items


class ArticleViewSet(APIViewSet):
    model = Article
    api = api
    pagination_class = LargePagePagination
```

### Small Page Size for Mobile

```python
class MobilePagination(PageNumberPagination):
    page_size = 5
    max_page_size = 20


class ArticleViewSet(APIViewSet):
    model = Article
    api = api
    pagination_class = MobilePagination
```

## AsyncPaginationBase

Base class for creating custom pagination.

### Class Definition

```python
from ninja.pagination import AsyncPaginationBase

class MyPagination(AsyncPaginationBase):
    page_size: int = 10
    max_page_size: int = 100

    async def apaginate_queryset(
        self,
        queryset,
        pagination,
        request=None,
        **params
    ):
        # Custom pagination logic
        pass
```

### Required Methods

#### `apaginate_queryset()`

Main pagination method that processes the queryset.

**Signature:**

```python
async def apaginate_queryset(
    self,
    queryset: QuerySet,
    pagination: AsyncPaginationBase,
    request: HttpRequest = None,
    **params
) -> dict
```

**Parameters:**

| Parameter    | Type                  | Description                 |
| ------------ | --------------------- | --------------------------- |
| `queryset`   | `QuerySet`            | Django queryset to paginate |
| `pagination` | `AsyncPaginationBase` | Pagination instance         |
| `request`    | `HttpRequest`         | HTTP request object         |
| `**params`   | `dict`                | Additional parameters       |

**Returns:**

Dictionary with pagination metadata and results.

## Custom Pagination Examples

### Cursor-Based Pagination

```python
from ninja.pagination import AsyncPaginationBase
from ninja import Schema


class CursorPaginationSchema(Schema):
    cursor: str | None = None
    page_size: int = 10


class CursorPagination(AsyncPaginationBase):
    page_size = 10
    max_page_size = 100

    async def apaginate_queryset(self, queryset, pagination, request=None, **params):
        cursor = params.get('cursor')
        page_size = min(params.get('page_size', self.page_size), self.max_page_size)

        # Apply cursor filtering
        if cursor:
            queryset = queryset.filter(id__gt=cursor)

        # Fetch items + 1 to check if there's next page
        items = []
        async for item in queryset[:page_size + 1]:
            items.append(item)

        has_next = len(items) > page_size
        results = items[:page_size]

        next_cursor = None
        if has_next and results:
            next_cursor = str(results[-1].id)

        return {
            "next_cursor": next_cursor,
            "results": results
        }


class ArticleViewSet(APIViewSet):
    model = Article
    api = api
    pagination_class = CursorPagination
```

**Usage:**

```bash
# First page
GET /article/?page_size=10

# Next page
GET /article/?cursor=10&page_size=10
```

**Response:**

```json
{
  "next_cursor": "20",
  "results": [...]
}
```

### Offset-Based Pagination

```python
class OffsetPagination(AsyncPaginationBase):
    page_size = 10
    max_page_size = 100

    async def apaginate_queryset(self, queryset, pagination, request=None, **params):
        offset = params.get('offset', 0)
        limit = min(params.get('limit', self.page_size), self.max_page_size)

        # Get total count
        total_count = await queryset.acount()

        # Slice queryset
        items = []
        async for item in queryset[offset:offset + limit]:
            items.append(item)

        return {
            "count": total_count,
            "offset": offset,
            "limit": limit,
            "results": items
        }


class ArticleViewSet(APIViewSet):
    model = Article
    api = api
    pagination_class = OffsetPagination
```

**Usage:**

```bash
# First 10 items
GET /article/?offset=0&limit=10

# Next 10 items
GET /article/?offset=10&limit=10

# Skip 20, get 15
GET /article/?offset=20&limit=15
```

**Response:**

```json
{
  "count": 100,
  "offset": 20,
  "limit": 15,
  "results": [...]
}
```

### Link Header Pagination

```python
from django.http import HttpResponse


class LinkHeaderPagination(AsyncPaginationBase):
    page_size = 10
    max_page_size = 100

    async def apaginate_queryset(self, queryset, pagination, request=None, **params):
        page = params.get('page', 1)
        page_size = min(params.get('page_size', self.page_size), self.max_page_size)

        total_count = await queryset.acount()
        total_pages = (total_count + page_size - 1) // page_size

        start = (page - 1) * page_size
        end = start + page_size

        items = []
        async for item in queryset[start:end]:
            items.append(item)

        # Build Link header
        base_url = request.build_absolute_uri(request.path)
        links = []

        if page > 1:
            links.append(f'<{base_url}?page={page-1}&page_size={page_size}>; rel="prev"')
        if page < total_pages:
            links.append(f'<{base_url}?page={page+1}&page_size={page_size}>; rel="next"')

        links.append(f'<{base_url}?page=1&page_size={page_size}>; rel="first"')
        links.append(f'<{base_url}?page={total_pages}&page_size={page_size}>; rel="last"')

        return {
            "results": items,
            "_links": ", ".join(links)
        }
```

**Response Headers:**

```
Link: <http://api.example.com/article/?page=1&page_size=10>; rel="first",
      <http://api.example.com/article/?page=2&page_size=10>; rel="prev",
      <http://api.example.com/article/?page=4&page_size=10>; rel="next",
      <http://api.example.com/article/?page=10&page_size=10>; rel="last"
```

## Disable Pagination

### For Specific ViewSet

```python
class ArticleViewSet(APIViewSet):
    model = Article
    api = api
    pagination_class = None  # Disable pagination
```

Now the list endpoint returns all items without pagination:

```bash
GET /article/
```

```json
[
  {"id": 1, "title": "Article 1"},
  {"id": 2, "title": "Article 2"},
  ...
]
```

### Conditional Pagination

```python
class ConditionalPagination(PageNumberPagination):
    async def apaginate_queryset(self, queryset, pagination, request=None, **params):
        # Disable pagination if 'all' parameter is present
        if params.get('all'):
            items = []
            async for item in queryset:
                items.append(item)
            return {"results": items}

        # Otherwise use default pagination
        return await super().apaginate_queryset(queryset, pagination, request, **params)
```

**Usage:**

```bash
# Paginated
GET /article/?page=1&page_size=10

# All items
GET /article/?all=true
```

## Integration with Filtering

Pagination works seamlessly with query parameter filtering:

```python
class ArticleViewSet(APIViewSet):
    model = Article
    api = api
    query_params = {
        "is_published": (bool, None),
        "category": (int, None),
    }

    async def query_params_handler(self, queryset, filters):
        if filters.get("is_published") is not None:
            queryset = queryset.filter(is_published=filters["is_published"])
        if filters.get("category"):
            queryset = queryset.filter(category_id=filters["category"])
        return queryset
```

**Usage:**

```bash
# Filter + pagination
GET /article/?is_published=true&category=5&page=2&page_size=20
```

The filtering is applied first, then pagination is applied to the filtered queryset.

## Performance Optimization

### Count Optimization

For large datasets, counting can be expensive. Cache the count:

```python
from django.core.cache import cache


class OptimizedPagination(PageNumberPagination):
    async def apaginate_queryset(self, queryset, pagination, request=None, **params):
        page = params.get('page', 1)
        page_size = min(params.get('page_size', self.page_size), self.max_page_size)

        # Try to get cached count
        cache_key = f"count_{queryset.model.__name__}"
        total_count = cache.get(cache_key)

        if total_count is None:
            total_count = await queryset.acount()
            cache.set(cache_key, total_count, 300)  # Cache for 5 minutes

        # Rest of pagination logic
        start = (page - 1) * page_size
        end = start + page_size

        items = []
        async for item in queryset[start:end]:
            items.append(item)

        return {
            "count": total_count,
            "page": page,
            "page_size": page_size,
            "results": items
        }
```

### Select Related / Prefetch Related

Optimize queries when paginating related data:

```python
class Article(ModelSerializer):
    author = models.ForeignKey(User, on_delete=models.CASCADE)
    category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True)
    tags = models.ManyToManyField(Tag, related_name="articles")

    @classmethod
    async def queryset_request(cls, request):
        # Optimize queries before pagination
        return cls.objects.select_related(
            'author',
            'category'
        ).prefetch_related(
            'tags'
        )


class ArticleViewSet(APIViewSet):
    model = Article
    api = api
```

Now pagination queries are optimized:

```sql
-- Single query with joins instead of N+1
SELECT article.*, user.*, category.*
FROM article
LEFT JOIN user ON article.author_id = user.id
LEFT JOIN category ON article.category_id = category.id
LIMIT 10 OFFSET 0;
```

### Approximate Counts

For very large tables, use approximate counts:

```python
class ApproximatePagination(PageNumberPagination):
    async def apaginate_queryset(self, queryset, pagination, request=None, **params):
        from django.db import connection

        # Get approximate count from PostgreSQL statistics
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT reltuples::bigint FROM pg_class WHERE relname = %s",
                [queryset.model._meta.db_table]
            )
            approximate_count = cursor.fetchone()[0]

        # Rest of pagination logic using approximate_count
        # ...
```

## Error Handling

### Invalid Page Number

```python
# Request
GET /article/?page=999&page_size=10

# Response (404)
{
  "detail": "Invalid page."
}
```

### Invalid Page Size

```python
# Request
GET /article/?page=1&page_size=1000

# Automatically clamped to max_page_size (100)
# Response
{
  "count": 45,
  "page": 1,
  "page_size": 100,
  "results": [...]
}
```

### Custom Error Handling

```python
class StrictPagination(PageNumberPagination):
    async def apaginate_queryset(self, queryset, pagination, request=None, **params):
        page_size = params.get('page_size', self.page_size)

        if page_size > self.max_page_size:
            raise ValueError(
                f"page_size cannot exceed {self.max_page_size}"
            )

        # Continue with pagination
        # ...
```

## Testing Pagination

```python
import pytest
from ninja.testing import TestAsyncClient
from myapp.views import api


@pytest.mark.asyncio
async def test_pagination():
    client = TestAsyncClient(api)

    # Create test data
    for i in range(25):
        await Article.objects.acreate(title=f"Article {i}")

    # Test first page
    response = await client.get("/article/?page=1&page_size=10")
    assert response.status_code == 200
    data = response.json()
    assert data["count"] == 25
    assert len(data["results"]) == 10
    assert data["next"] == 2
    assert data["previous"] is None

    # Test middle page
    response = await client.get("/article/?page=2&page_size=10")
    data = response.json()
    assert len(data["results"]) == 10
    assert data["next"] == 3
    assert data["previous"] == 1

    # Test last page
    response = await client.get("/article/?page=3&page_size=10")
    data = response.json()
    assert len(data["results"]) == 5
    assert data["next"] is None
    assert data["previous"] == 2


@pytest.mark.asyncio
async def test_invalid_page():
    client = TestAsyncClient(api)

    response = await client.get("/article/?page=999")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_page_size_limit():
    client = TestAsyncClient(api)

    # Request exceeds max_page_size
    response = await client.get("/article/?page=1&page_size=1000")
    data = response.json()
    assert len(data["results"]) <= 100  # Clamped to max_page_size
```

## Best Practices

1. **Choose appropriate page size:**

   ```python
   # Mobile API
   page_size = 10

   # Desktop/Web API
   page_size = 25

   # Admin/Internal API
   page_size = 100
   ```

2. **Set reasonable max_page_size:**

   ```python
   # Prevent excessive data transfer
   max_page_size = 100
   ```

3. **Cache expensive counts:**

   ```python
   # For large, slowly-changing datasets
   cache.set(f"count_{model}", count, timeout=300)
   ```

4. **Optimize queries:**

   ```python
   queryset = queryset.select_related(...).prefetch_related(...)
   ```

5. **Use cursor pagination for infinite scroll:**

   ```python
   # Better for real-time feeds
   class FeedPagination(CursorPagination):
       page_size = 20
   ```

6. **Consider approximate counts for huge tables:**
   ```python
   # Faster than exact count for millions of rows
   use_approximate = queryset.count() > 1_000_000
   ```

## See Also

- [API ViewSet](views/api_view_set.md) - Using pagination with ViewSets
- [Model Util](models/model_util.md) - Query optimization
- [Authentication](authentication.md) - Securing paginated endpoints

---

**Next:** Learn about [Authentication](authentication.md) to secure your API endpoints.
