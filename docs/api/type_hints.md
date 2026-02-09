# Type Hints & Type Safety

## Overview

`django-ninja-aio-crud` provides full type safety through generic classes. When you specify the model type parameter, you get:

- ✅ **IDE Autocomplete** - Your IDE suggests the correct model fields and methods
- ✅ **Type Checking** - Type checkers (mypy, pyright, pylance) catch errors at development time
- ✅ **Better Refactoring** - Renaming fields or changing types is caught by the type checker
- ✅ **Zero Runtime Overhead** - Generic types are erased at runtime

## Generic Serializer

The `Serializer` class is now generic, providing type-safe CRUD methods.

### Basic Usage

```python
from ninja_aio.models.serializers import Serializer, SchemaModelConfig
from myapp.models import Book

class BookSerializer(Serializer[Book]):  # 👈 Specify model type
    class Meta:
        model = Book
        schema_in = SchemaModelConfig(fields=["title", "author"])
        schema_out = SchemaModelConfig(fields=["id", "title", "author"])

# Now all methods are properly typed!
serializer = BookSerializer()

# ✅ Type checker knows this returns Book
book: Book = await serializer.create({"title": "1984", "author_id": 1})

# ✅ Type checker knows this accepts and returns Book
book: Book = await serializer.save(book)

# ✅ Type checker knows this accepts Book
data: dict = await serializer.model_dump(book)

# ✅ Optional: specify custom schema for serialization
custom_schema = BookSerializer.generate_read_s()
data: dict = await serializer.model_dump(book, schema=custom_schema)
```

### Benefits

- All CRUD methods (`create`, `update`, `save`, `model_dump`) return/accept the specific model type
- IDE autocomplete works for model attributes
- Type checker validates attribute access

## Generic APIViewSet

The `APIViewSet` class is generic for type-safe `model_util` access.

### Option 1: Type the ViewSet

Use this approach if you primarily use `self.model_util` in your ViewSet:

```python
from ninja_aio.views import APIViewSet
from ninja_aio.api import NinjaAIO
from myapp.models import Book

api = NinjaAIO()

@api.viewset(Book)
class BookAPI(APIViewSet[Book]):  # 👈 Specify model type
    async def my_method(self, request):
        # ✅ self.model_util is typed as ModelUtil[Book]
        book: Book = await self.model_util.get_object(request, pk=1)

        # ✅ IDE knows book.title, book.author, etc.
        print(book.title)
```

### Option 2: Type the Serializer (Recommended)

Use this approach if you primarily use `self.serializer` in your ViewSet:

```python
class BookSerializer(Serializer[Book]):
    class Meta:
        model = Book

@api.viewset(Book)
class BookAPI(APIViewSet):  # No generic parameter needed!
    serializer_class = BookSerializer

    async def my_method(self, request, data):
        # ✅ All serializer methods are typed
        book: Book = await self.serializer.create(data.model_dump())
        book: Book = await self.serializer.save(book)
        return await self.serializer.model_dump(book)
```

### Option 3: Both (Maximum Type Safety)

For complete type safety everywhere:

```python
class BookSerializer(Serializer[Book]):
    class Meta:
        model = Book

@api.viewset(Book)
class BookAPI(APIViewSet[Book]):  # Both are typed!
    serializer_class = BookSerializer

    async def method1(self, request):
        # ✅ model_util methods are typed
        book = await self.model_util.get_object(request, pk=1)

    async def method2(self, request, data):
        # ✅ serializer methods are typed
        book = await self.serializer.create(data.model_dump())
```

## Generic ModelUtil

When using `ModelUtil` directly, type inference works automatically:

```python
from ninja_aio.models.utils import ModelUtil
from myapp.models import Book

# Type is automatically inferred as ModelUtil[Book]
util = ModelUtil(Book)

# ✅ Type checker knows this returns Book
book: Book = await util.get_object(request, pk=1)

# ✅ Type checker knows this returns QuerySet[Book]
books: QuerySet[Book] = await util.get_objects(request)

# ✅ IDE autocompletes model attributes
print(book.title)
print(book.author)
```

## Generic Mixins

All ViewSet mixins are generic and follow the same pattern:

```python
from ninja_aio.views.mixins import IcontainsFilterViewSetMixin
from myapp.models import Author

@api.viewset(Author)
class AuthorAPI(IcontainsFilterViewSetMixin[Author]):  # 👈 Specify type
    query_params = {
        "name": (str, None),
    }

    async def custom_method(self, request):
        # ✅ Type checker knows author is Author
        author: Author = await self.model_util.get_object(request, pk=1)
        print(author.name)  # Autocomplete works!
```

Available generic mixins:

- `IcontainsFilterViewSetMixin[ModelT]`
- `BooleanFilterViewSetMixin[ModelT]`
- `NumericFilterViewSetMixin[ModelT]`
- `DateFilterViewSetMixin[ModelT]`
- `RelationFilterViewSetMixin[ModelT]`
- `MatchCaseFilterViewSetMixin[ModelT]`

## Why Explicit Type Parameters?

Python's type system cannot automatically infer generic types from:

- Class attributes (`model = Book`)
- Decorator arguments (`@api.viewset(Book)`)
- Constructor parameters

This is a fundamental limitation affecting all Python type checkers (mypy, pyright, pylance).

Other popular frameworks face the same issue:

=== "Django Stubs"
    ```python
    class BookManager(models.Manager["Book"]):  # Must specify
        def published(self) -> QuerySet["Book"]:  # Must specify again
            return self.get_queryset().filter(published=True)
    ```

=== "FastAPI"
    ```python
    @app.get("/books/{book_id}", response_model=BookSchema)  # Must specify
    async def get_book(book_id: int) -> BookSchema:  # Must specify again
        ...
    ```

=== "SQLAlchemy 2.0"
    ```python
    class User(Base):
        posts: Mapped[list["Post"]] = relationship()  # Must specify
    ```

## Type Checker Configuration

For the best experience, configure your type checker:

=== "VS Code (Pylance)"
    ```json
    {
        "python.analysis.typeCheckingMode": "basic"  // or "strict"
    }
    ```

=== "PyCharm"
    Type checking is enabled by default.

=== "mypy (command line)"
    ```bash
    mypy --strict your_file.py
    ```

## Troubleshooting

**Problem**: Type checker still shows `Any`

**Solution**: Make sure you specified the generic type parameter:

```python
# ❌ Wrong - type checker sees Any
class BookAPI(APIViewSet):
    pass

# ✅ Correct - type checker sees Book
class BookAPI(APIViewSet[Book]):
    pass
```

**Problem**: Import error with `ModelT`

**Solution**: Don't import `ModelT` - it's only used internally. Use your model class directly:

```python
# ❌ Wrong
from ninja_aio.views.api import ModelT
class BookAPI(APIViewSet[ModelT]):
    pass

# ✅ Correct
from myapp.models import Book
class BookAPI(APIViewSet[Book]):
    pass
```

## Summary

| Usage | Pattern |
|-------|---------|
| Serializer | `class MySerializer(Serializer[MyModel]):` |
| ViewSet with model_util | `class MyAPI(APIViewSet[MyModel]):` |
| ViewSet with serializer | Type the Serializer, not the ViewSet |
| ViewSet with mixin | `class MyAPI(SomeMixin[MyModel]):` |
| Direct ModelUtil | `util = ModelUtil(MyModel)` (auto-inferred) |

The small cost of repeating the type pays off massively in IDE support and type safety! 🎯
