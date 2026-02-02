# :material-frequently-asked-questions: Troubleshooting & FAQ

Common questions and issues when working with Django Ninja AIO.

---

## :material-link-variant: Relations & Serialization

??? question "My reverse FK / M2M fields return empty lists"

    Django Ninja AIO uses `prefetch_related` automatically for reverse relations, but it requires:

    1. The related field name must be in your `ReadSerializer.fields`
    2. The related model must also be a `ModelSerializer` (or have a schema defined)

    ```python
    class Author(ModelSerializer):
        name = models.CharField(max_length=200)

        class ReadSerializer:
            fields = ["id", "name", "books"]  # "books" = related_name on Book.author
    ```

    If `books` is not the correct `related_name`, check your ForeignKey definition:

    ```python
    class Book(ModelSerializer):
        author = models.ForeignKey(Author, on_delete=models.CASCADE, related_name="books")
    ```

??? question "I get 'SynchronousOnlyOperation' errors with relations"

    This happens when Django's ORM is accessed synchronously inside an async context. Django Ninja AIO handles this automatically through `prefetch_related` and async iteration, but if you're writing custom code:

    ```python
    # Wrong - synchronous access in async view
    async def my_view(request):
        author = await Author.objects.aget(pk=1)
        books = author.books.all()  # SynchronousOnlyOperation!

    # Correct - use async iteration
    async def my_view(request):
        author = await Author.objects.prefetch_related("books").aget(pk=1)
        books = [book async for book in author.books.all()]
    ```

    !!! tip
        Let Django Ninja AIO handle relation serialization through `ReadSerializer` — it manages the async complexity for you.

??? question "Nested relations only show IDs, not full objects"

    Make sure the related model is also a `ModelSerializer` with its own `ReadSerializer`:

    ```python
    # This will serialize books as full objects
    class Book(ModelSerializer):
        title = models.CharField(max_length=200)

        class ReadSerializer:
            fields = ["id", "title"]  # This is required!

    class Author(ModelSerializer):
        name = models.CharField(max_length=200)

        class ReadSerializer:
            fields = ["id", "name", "books"]
    ```

    If `Book` doesn't have a `ReadSerializer`, the framework can't know how to serialize it.

---

## :material-cog: Configuration & Setup

??? question "How do I disable specific CRUD operations?"

    Use the `disable` attribute on your ViewSet:

    ```python
    @api.viewset(Book)
    class BookViewSet(APIViewSet):
        disable = ["update", "delete"]  # Read-only API
    ```

    Available operations: `"create"`, `"list"`, `"retrieve"`, `"update"`, `"delete"`

??? question "How do I use a different primary key type (UUID, etc.)?"

    Django Ninja AIO automatically infers the PK type from your model:

    ```python
    import uuid
    from django.db import models

    class Article(ModelSerializer):
        id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
        title = models.CharField(max_length=200)

        class ReadSerializer:
            fields = ["id", "title"]
    ```

    The generated endpoints will use `UUID` in the path schema automatically.

??? question "How do I change the pagination page size?"

    Override the pagination class on your ViewSet:

    ```python
    from ninja.pagination import PageNumberPagination

    class LargePagination(PageNumberPagination):
        page_size = 50
        max_page_size = 200

    @api.viewset(Book)
    class BookViewSet(APIViewSet):
        pagination_class = LargePagination
    ```

---

## :material-shield-lock: Authentication

??? question "How do I make some endpoints public and others protected?"

    Use per-method auth attributes:

    ```python
    @api.viewset(Book)
    class BookViewSet(APIViewSet):
        auth = [JWTAuth()]      # Default: all endpoints require auth
        get_auth = None          # GET endpoints (list, retrieve) are public
    ```

    Available per-method attributes: `get_auth`, `post_auth`, `put_auth`, `patch_auth`, `delete_auth`

??? question "I get 401 errors even with a valid token"

    Check these common causes:

    1. **Token format** — Ensure the header is `Authorization: Bearer <token>` (not `Token` or `JWT`)
    2. **Key mismatch** — Verify your public key matches the key used to sign tokens
    3. **Algorithm** — Make sure `jwt_alg` matches the signing algorithm (e.g., `RS256`, `HS256`)
    4. **Claims** — Check required claims are present in the token payload

---

## :material-database: Database & Queries

??? question "How do I optimize queries for large datasets?"

    Use `QuerySet` configuration on your model:

    ```python
    class Article(ModelSerializer):
        title = models.CharField(max_length=200)
        author = models.ForeignKey(Author, on_delete=models.CASCADE)

        class ReadSerializer:
            fields = ["id", "title", "author"]

        class QuerySet:
            read = {
                "select_related": ["author"],
                "prefetch_related": ["tags"],
            }
    ```

    This ensures `select_related` and `prefetch_related` are applied automatically.

??? question "Filtering is slow on large tables"

    1. **Add database indexes** to frequently filtered fields:

        ```python
        class Article(ModelSerializer):
            title = models.CharField(max_length=200, db_index=True)
            is_published = models.BooleanField(default=False, db_index=True)
        ```

    2. **Keep pagination enabled** — never return unbounded querysets
    3. **Limit slices** for search-heavy endpoints: `queryset = queryset[:1000]`

---

## :material-bug: Common Errors

??? question "`ImportError: cannot import name 'ModelSerializer'`"

    Make sure you're importing from the correct module:

    ```python
    # Correct
    from ninja_aio.models import ModelSerializer

    # Wrong
    from ninja_aio import ModelSerializer
    ```

??? question "`AttributeError: type object 'MyModel' has no attribute 'generate_read_s'`"

    Your model must inherit from `ModelSerializer`, not Django's `models.Model`:

    ```python
    # Correct
    from ninja_aio.models import ModelSerializer

    class MyModel(ModelSerializer):
        ...

    # Wrong
    from django.db import models

    class MyModel(models.Model):
        ...
    ```

    If you can't change the base class, use the [Meta-driven Serializer](api/models/serializers.md) instead.

??? question "Circular import errors between models"

    Use string references for ForeignKey relations to models in other files:

    ```python
    class Book(ModelSerializer):
        author = models.ForeignKey("myapp.Author", on_delete=models.CASCADE)
    ```

    For serializer references, Django Ninja AIO supports string-based relation resolution.

---

## :material-help-circle: Still Stuck?

<div class="grid cards" markdown>

-   :material-github:{ .lg .middle } **Open an Issue**

    ---

    Search existing issues or create a new one

    [:octicons-arrow-right-24: GitHub Issues](https://github.com/caspel26/django-ninja-aio-crud/issues)

-   :material-book-open-variant:{ .lg .middle } **Browse the Docs**

    ---

    Full API reference and tutorials

    [:octicons-arrow-right-24: Documentation](index.md)

-   :material-rocket-launch:{ .lg .middle } **Quick Start**

    ---

    Step-by-step getting started guide

    [:octicons-arrow-right-24: Get Started](getting_started/installation.md)

</div>
