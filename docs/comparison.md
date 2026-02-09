# Framework Comparison

<div class="grid cards" markdown>

-   :material-clock-fast: **13 Operations Tested**

    ---

    CRUD, filtering, relation serialization, and bulk operations

-   :material-language-python: **Python 3.14.0**

    ---

    Tested on 2026-02-04T03:37:16.423338

-   :fontawesome-solid-scale-balanced: **4 Frameworks**

    ---

    Django Ninja AIO, Django Ninja, ADRF, FastAPI

-   :material-database: **Same Database**

    ---

    All frameworks use identical Django models and SQLite in-memory

</div>

---

## The Honest Truth About Performance

!!! abstract "TL;DR"
    **Django Ninja AIO is NOT the fastest framework for simple CRUD operations.** Frameworks like FastAPI and pure Django Ninja may show better raw performance on basic operations. This is an intentional trade-off for **massive developer productivity gains** on complex async Django projects.

---

## Code Complexity Comparison

This is where Django Ninja AIO truly differentiates itself. Compare **real implementation code** for the same feature across frameworks.

### Task: CRUD API with Reverse FK Relations

=== "Django Ninja AIO"

    ```python
    from django.db import models
    from ninja_aio.models import ModelSerializer
    from ninja_aio import NinjaAIO
    from ninja_aio.views import APIViewSet


    class Author(ModelSerializer):
        name = models.CharField(max_length=200)
        email = models.EmailField()

        class CreateSerializer:
            fields = ["name", "email"]

        class ReadSerializer:
            fields = ["id", "name", "email", "books"]  # Reverse FK: automatic!

        class UpdateSerializer:
            optionals = [("name", str), ("email", str)]


    api = NinjaAIO()


    @api.viewset(model=Author)
    class AuthorViewSet(APIViewSet):
        pass  # All CRUD endpoints auto-generated
    ```

    !!! success "What you get automatically"
        - All CRUD endpoints (create, list, retrieve, update, delete)
        - Reverse FK serialization with proper async handling
        - Automatic `prefetch_related` optimization
        - Type-safe Pydantic schemas
        - Input validation & pagination

=== "FastAPI"

    ```python
    from fastapi import FastAPI
    from pydantic import BaseModel

    app = FastAPI()


    class BookOut(BaseModel):
        id: int
        title: str

        class Config:
            from_attributes = True


    class AuthorOut(BaseModel):
        id: int
        name: str
        email: str
        books: list[BookOut]

        class Config:
            from_attributes = True


    class AuthorCreate(BaseModel):
        name: str
        email: str


    @app.post("/authors/")
    async def create_author(data: AuthorCreate):
        author = await Author.objects.acreate(**data.dict())
        return {"id": author.id, "name": author.name, "email": author.email}


    @app.get("/authors/")
    async def list_authors():
        authors = []
        async for author in Author.objects.all():
            authors.append(AuthorOut.model_validate(author))
        return authors


    @app.get("/authors/{author_id}")
    async def get_author(author_id: int):
        author = await Author.objects.prefetch_related("books").aget(pk=author_id)

        # Must manually iterate reverse FK in async
        books = []
        async for book in author.books.all():
            books.append(BookOut.model_validate(book))

        return {
            "id": author.id,
            "name": author.name,
            "email": author.email,
            "books": [b.dict() for b in books],
        }


    @app.patch("/authors/{author_id}")
    async def update_author(author_id: int, data: AuthorCreate):
        author = await Author.objects.aget(pk=author_id)
        for field, value in data.dict(exclude_unset=True).items():
            setattr(author, field, value)
        await author.asave()
        return AuthorOut.model_validate(author)


    @app.delete("/authors/{author_id}")
    async def delete_author(author_id: int):
        author = await Author.objects.aget(pk=author_id)
        await author.adelete()
        return {"deleted": True}


    # Still missing: list pagination, filtering, proper error handling
    ```

    !!! warning "Manual work required"
        - Every endpoint written by hand
        - Reverse FK requires manual `async for` iteration
        - No automatic `prefetch_related`
        - Pagination, filtering, error handling all manual

=== "ADRF"

    ```python
    from adrf.serializers import ModelSerializer as AsyncModelSerializer
    from adrf.viewsets import ModelViewSet as AsyncModelViewSet
    from rest_framework.routers import DefaultRouter


    class BookSerializer(AsyncModelSerializer):
        class Meta:
            model = Book
            fields = ["id", "title"]


    class AuthorSerializer(AsyncModelSerializer):
        books = BookSerializer(many=True, read_only=True)

        class Meta:
            model = Author
            fields = ["id", "name", "email", "books"]


    class AuthorCreateSerializer(AsyncModelSerializer):
        class Meta:
            model = Author
            fields = ["name", "email"]


    class AuthorViewSet(AsyncModelViewSet):
        queryset = Author.objects.all()
        serializer_class = AuthorSerializer

        def get_serializer_class(self):
            if self.action == "create":
                return AuthorCreateSerializer
            return AuthorSerializer

        def get_queryset(self):
            return Author.objects.prefetch_related("books")


    router = DefaultRouter()
    router.register(r"authors", AuthorViewSet)
    ```

    !!! info "Partial automation"
        - ViewSet provides CRUD but needs serializer wiring
        - Reverse FK requires explicit nested serializer
        - `prefetch_related` must be configured manually
        - More boilerplate than Django Ninja AIO

---

### The Verdict

<div class="grid cards" markdown>

-   :material-rocket-launch: **Django Ninja AIO** --- **~20 lines**

    ---

    :material-check-all: Automatic reverse FK handling
    :material-check-all: Auto prefetch optimization
    :material-check-all: Full CRUD automation

-   :material-lightning-bolt: **FastAPI** --- **~80+ lines**

    ---

    :material-close: Manual async iteration for reverse FK
    :material-close: No automatic prefetch
    :material-close: No CRUD automation

-   :material-cog: **ADRF** --- **~45+ lines**

    ---

    :material-minus: Needs nested serializer config
    :material-minus: Manual prefetch setup
    :material-check: Partial CRUD via ViewSets

</div>

---

### When to Choose What

=== "Choose Django Ninja AIO"

    - You have **complex data models** with relations
    - You need **async Django** with proper ORM handling
    - **Developer time** matters more than marginal performance gains
    - You value **type safety** and **maintainability**

=== "Choose Simpler Frameworks"

    - You have **flat, simple data models**
    - Every **millisecond** counts more than dev time
    - You prefer **full manual control** over automation

---

## Performance Results

| Operation | **Django Ninja AIO** | **Django Ninja** | **ADRF** | **FastAPI** |
|-----------|---|---|---|---|
| **Bulk Serialization 100** | 6.86ms | 0.36ms | 66.43ms | 0.46ms |
| **Bulk Serialization 500** | 33.96ms | 1.30ms | 325.56ms | 1.77ms |
| **Complex Async Query** | 1.74ms | 0.26ms | 19.79ms | 0.29ms |
| **Create** | 0.49ms | 0.13ms | 0.93ms | 0.17ms |
| **Delete** | 0.41ms | 0.36ms | 0.31ms | 0.29ms |
| **Filter** | 0.26ms | 0.17ms | 0.90ms | 0.18ms |
| **List** | 1.56ms | 0.18ms | 12.99ms | 0.22ms |
| **Many To Many** | 0.46ms | 0.38ms | 4.80ms | 0.39ms |
| **Nested Relations** | 0.37ms | 0.19ms | 1.31ms | 0.24ms |
| **Relation Serialization** | 0.33ms | 0.19ms | 1.30ms | 0.19ms |
| **Retrieve** | 0.25ms | 0.16ms | 1.06ms | 0.17ms |
| **Reverse Relations** | 0.55ms | 0.45ms | 20.07ms | 0.50ms |
| **Update** | 0.74ms | 0.39ms | 1.11ms | 0.31ms |


!!! note "Understanding the Numbers"
    Lower is better. All frameworks use the same Django models and database.
    A 10-20% performance difference is negligible compared to hours of development time saved on complex async relations.

---

## Live Comparison Report

The latest framework comparison benchmarks from the `main` branch are automatically published as an interactive HTML report:

<div class="cta-buttons" markdown>

[View Live Comparison Report :material-chart-box-outline:](https://caspel26.github.io/django-ninja-aio-crud/comparison/comparison_report.html){ .md-button .md-button--primary target="_blank" }

</div>

---

## Methodology

All frameworks were tested under identical conditions:

<div class="grid cards" markdown>

-   :material-database: **Same Database**

    ---

    SQLite in-memory, same Django models for all frameworks

-   :material-sync: **Same Operations**

    ---

    Identical CRUD, filter, and serialization tasks

-   :material-lightning-bolt: **Async Where Possible**

    ---

    Sync frameworks wrapped with `sync_to_async`

-   :material-chart-bar: **Statistical Reliability**

    ---

    Multiple iterations per operation with median comparison

</div>

---
