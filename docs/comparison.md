---
type: benchmark
title: Framework comparison
description: Compare django-ninja-aio-crud with Django Ninja, ADRF and FastAPI on code size and speed.
---

# Framework comparison

This page compares django-ninja-aio-crud with Django Ninja, ADRF and FastAPI:
how much code you write for the same API, and how fast each one runs.

<!-- comparison-facts:start -->
| Fact | Value |
| --- | --- |
| Operations tested | 13 (CRUD, filtering, relation serialization, bulk serialization) |
| Frameworks | django-ninja-aio-crud, Django Ninja, ADRF, FastAPI |
| Python | 3.14.0 |
| Run date | 2026-09-26T18:01:09.533824 |
| Database | SQLite in-memory, same Django models for every framework |
<!-- comparison-facts:end -->

!!! note

    django-ninja-aio-crud is not the fastest option for simple CRUD. FastAPI
    and plain Django Ninja are faster on basic operations. In exchange, you
    write much less code, especially for models with relations.

## Compare the code

The task: a CRUD API for authors, with each author's books in the response
(a reverse foreign key).

=== "django-ninja-aio-crud"

    ```python
    from django.db import models
    from ninja_aio import NinjaAIO, APIViewSet, ModelSerializer, SchemaConfig


    class Author(ModelSerializer):
        name = models.CharField(max_length=200)
        email = models.EmailField()

        class Schemas:
            create = SchemaConfig(fields=["name", "email"])
            read = SchemaConfig(fields=["id", "name", "email", "books"])
            update = SchemaConfig(optionals=[("name", str), ("email", str)])


    class Book(ModelSerializer):
        title = models.CharField(max_length=200)
        author = models.ForeignKey(Author, on_delete=models.CASCADE, related_name="books")

        class Schemas:
            read = SchemaConfig(fields=["id", "title"])


    api = NinjaAIO()


    @api.viewset(model=Author)
    class AuthorViewSet(APIViewSet):
        pass
    ```

    You get create, list, retrieve, update and delete endpoints, the books
    nested in each author, the related query loaded for you, input
    validation and pagination.

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

    You write every endpoint by hand, iterate the books with `async for`,
    add `prefetch_related` yourself, and handle pagination, filtering and
    errors on your own.

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

    The viewset gives you CRUD, but you wire the serializers yourself, declare
    a nested serializer for the books and set up `prefetch_related`.

### Summary

| Framework | Lines of code | Reverse FK | Related query loading | CRUD endpoints |
| --- | --- | --- | --- | --- |
| django-ninja-aio-crud | ~30 | Automatic | Automatic | Generated |
| FastAPI | ~80+ | Manual `async for` | Manual | Written by hand |
| ADRF | ~45+ | Nested serializer | Manual | Partial, via viewsets |

### When to choose which

Choose django-ninja-aio-crud when:

- Your models have relations.
- You use async Django and want the ORM handled for you.
- Development time matters more than small speed gains.

Choose a lower-level framework when:

- Your models are flat and simple.
- Every millisecond matters more than development time.
- You want full manual control over each endpoint.

## Results

Median time per operation. Lower is better.

<!-- comparison-results:start -->
| Operation | django-ninja-aio-crud | Django Ninja | ADRF | FastAPI |
| --- | --- | --- | --- | --- |
| Bulk serialization 100 | 0.60ms | 0.38ms | 67.98ms | 0.48ms |
| Bulk serialization 500 | 2.47ms | 1.39ms | 339.20ms | 1.93ms |
| Complex async query | 0.40ms | 0.29ms | 21.50ms | 0.31ms |
| Create | 0.29ms | 0.14ms | 1.11ms | 0.15ms |
| Delete | 0.36ms | 0.32ms | 0.32ms | 0.32ms |
| Filter | 0.21ms | 0.19ms | 0.95ms | 0.18ms |
| List | 0.24ms | 0.18ms | 13.84ms | 0.22ms |
| Many to many | 0.51ms | 0.41ms | 5.12ms | 0.45ms |
| Nested relations | 0.33ms | 0.21ms | 1.51ms | 0.20ms |
| Relation serialization | 0.30ms | 0.20ms | 1.41ms | 0.21ms |
| Retrieve | 0.27ms | 0.17ms | 0.92ms | 0.17ms |
| Reverse relations | 0.59ms | 0.47ms | 21.67ms | 0.52ms |
| Update | 0.46ms | 0.32ms | 1.14ms | 0.33ms |
<!-- comparison-results:end -->

## Live report

The latest comparison from the `main` branch is published as an interactive
HTML report.

[View the live comparison report](https://caspel26.github.io/django-ninja-aio-crud/comparison/comparison_report.html){ .md-button .md-button--primary target="_blank" }

## Methodology

Every framework runs under the same conditions:

- **Same database**: SQLite in-memory, with the same Django models.
- **Same operations**: identical CRUD, filter and serialization tasks.
- **Async where possible**: sync frameworks are wrapped with `sync_to_async`.
- **Repeated runs**: each operation runs many times and the medians are compared.

To run the comparison yourself:

```bash
pip install -e ".[comparison]"
python -m django test tests.comparison --settings=tests.test_settings --tag=comparison -v2
python tests/comparison/generate_report.py
```

The results go to `comparison_results.json` and `comparison_report.html`.

## See also

- [Performance](performance.md)
- [Query optimization](guides/query-optimization.md)
- [Contributing](contributing.md)
