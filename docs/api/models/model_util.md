# Model Util

`ModelUtil` is an async utility class that provides high-level CRUD operations and serialization management for Django models and ModelSerializer instances.

## Overview

ModelUtil acts as a bridge between Django Ninja schemas and Django ORM, handling:

- **Data normalization** (input/output)
- **Relationship resolution** (FK/M2M)
- **Binary field handling** (base64 encoding/decoding)
- **Query optimization** (select_related/prefetch_related)
- **Lifecycle hook invocation** (custom_actions, post_create, queryset_request)

## Class Definition

```python
from ninja_aio.models import ModelUtil

util = ModelUtil(model, serializer_class=None)
```

**Parameters:**

- `model` (`type[ModelSerializer] | models.Model`): Django model or ModelSerializer subclass
- `serializer_class` (`Serializer | None`): Optional Serializer class for plain Django models

## Properties

### `with_serializer`

Indicates if a serializer_class is associated.

```python
util = ModelUtil(User, serializer_class=UserSerializer)
print(util.with_serializer)  # True
```

### `pk_field_type`

Returns the Python type corresponding to the model's primary key field.

```python
util = ModelUtil(User)
print(util.pk_field_type)  # <class 'int'>
```

Uses the Django field's internal type and `ninja.orm.fields.TYPES` mapping. Raises `ConfigError` if the internal type is not registered.

### `model_pk_name`

Returns the primary key field name.

```python
util = ModelUtil(User)
print(util.model_pk_name)  # "id"
```

### `model_fields`

Returns a list of all model field names.

```python
util = ModelUtil(User)
print(util.model_fields)
# ["id", "username", "email", "created_at", "is_active"]
```

### `serializable_fields`

Returns serializable fields (ReadSerializer fields or all model fields).

```python
class User(ModelSerializer):
    username = models.CharField(max_length=150)
    password = models.CharField(max_length=128)
    email = models.EmailField()

    class ReadSerializer:
        fields = ["id", "username", "email"]

util = ModelUtil(User)
print(util.serializable_fields)
# ["id", "username", "email"]  (password excluded)
```

### `model_name`

Returns the Django internal model name.

```python
util = ModelUtil(User)
print(util.model_name)  # "user"
```

### `serializer_meta`

Returns the ModelSerializerMeta instance if model uses ModelSerializer.

```python
if util.serializer_meta:
    fields = util.serializer_meta.get_fields("create")
```

## QuerySet configuration on ModelSerializer

You can declare query optimizations directly on your ModelSerializer via a nested QuerySet:

```python
from ninja_aio.models import ModelSerializer
from ninja_aio.schemas.helpers import ModelQuerySetSchema, ModelQuerySetExtraSchema

class Book(ModelSerializer):
    # ...existing fields...

    class QuerySet:
        read = ModelQuerySetSchema(
            select_related=["author", "category"],
            prefetch_related=["tags"],
        )
        queryset_request = ModelQuerySetSchema(
            select_related=[],
            prefetch_related=["related_items"],
        )
        extras = [
            ModelQuerySetExtraSchema(
                scope="detail_cards",
                select_related=["author"],
                prefetch_related=["tags"],
            )
        ]
```

- read: applied to read operations (list/retrieve).
- queryset_request: applied inside queryset_request hook.
- extras: named configurations available via QueryUtil.SCOPES.

## QueryUtil

Each ModelSerializer now exposes a query_util helper:

```python
util = MyModel.query_util
qs = util.apply_queryset_optimizations(MyModel.objects.all(), util.SCOPES.READ)
```

- SCOPES: includes READ, QUERYSET_REQUEST, plus any extras you've defined.
- apply_queryset_optimizations: applies select_related/prefetch_related for a scope.

## Query schemas

New helper schemas standardize filters and getters:

```python
from ninja_aio.schemas.helpers import (
    QuerySchema,           # generic: filters or getters
    ObjectQuerySchema,     # getters + select/prefetch
    ObjectsQuerySchema,    # filters + select/prefetch
    ModelQuerySetSchema,   # select/prefetch only
)
```

## Core Methods

### `get_objects`

Fetch an optimized queryset with optional filters and select/prefetch hints:

```python
from ninja_aio.models import ModelUtil
from ninja_aio.schemas.helpers import ObjectsQuerySchema

qs = await ModelUtil(Book).get_objects(
    request,
    query_data=ObjectsQuerySchema(
        filters={"is_published": True},
        select_related=["author"],
        prefetch_related=["tags"],
    ),
    with_qs_request=True,  # Apply queryset_request hook
    is_for_read=True,  # union with auto-discovered relations
)
```

**Parameters:**

- `request` (`HttpRequest`): Current HTTP request
- `query_data` (`ObjectsQuerySchema | None`): Query configuration (filters, select_related, prefetch_related)
- `with_qs_request` (`bool`): Apply queryset_request hook if available (default: True)
- `is_for_read` (`bool`): Merge with read-specific optimizations (default: False)

**Returns:** Optimized `QuerySet`

### `get_object`

Fetch a single object by pk or getters with optimizations:

```python
from ninja_aio.schemas.helpers import ObjectQuerySchema, QuerySchema

# by pk + select/prefetch
obj = await ModelUtil(Book).get_object(
    request,
    pk=42,
    query_data=ObjectQuerySchema(select_related=["author"]),
    with_qs_request=True,
    is_for_read=True,
)

# by getters (required if pk omitted)
obj = await ModelUtil(Book).get_object(
    request,
    query_data=QuerySchema(getters={"slug": "my-book-slug"}),
)
```

**Parameters:**

- `request` (`HttpRequest`): Current HTTP request
- `pk` (`int | str | None`): Primary key value (optional if getters provided)
- `query_data` (`ObjectQuerySchema | QuerySchema | None`): Query configuration
- `with_qs_request` (`bool`): Apply queryset_request hook if available (default: True)
- `is_for_read` (`bool`): Merge with read-specific optimizations (default: False)

**Returns:** Model instance

**Errors:**

- `ValueError` if neither pk nor getters provided
- `NotFoundError` if no match found

### `read_s` and `list_read_s`

Uniform serialization methods that accept either instances or query data:

```python
schema = Book.generate_read_s()

# single instance
data = await ModelUtil(Book).read_s(schema, request, instance=obj)

# single via getters
data = await ModelUtil(Book).read_s(
    schema,
    request,
    query_data=ObjectQuerySchema(getters={"pk": 42}),
    is_for_read=True,
)

# list from queryset
items = await ModelUtil(Book).list_read_s(schema, request, instances=qs)

# list via filters
items = await ModelUtil(Book).list_read_s(
    schema,
    request,
    query_data=ObjectsQuerySchema(filters={"is_published": True}),
    is_for_read=True,
)
```

**Parameters (read_s):**

- `schema` (`Schema`): Output schema for serialization
- `request` (`HttpRequest`): Current HTTP request
- `instance` (`Model | None`): Model instance to serialize (optional)
- `query_data` (`ObjectQuerySchema | QuerySchema | None`): Query configuration for fetching (optional)
- `is_for_read` (`bool`): Merge with read-specific optimizations (default: False)

**Parameters (list_read_s):**

- `schema` (`Schema`): Output schema for serialization
- `request` (`HttpRequest`): Current HTTP request
- `instances` (`QuerySet | list[Model] | None`): Instances to serialize (optional)
- `query_data` (`ObjectsQuerySchema | None`): Query configuration for fetching (optional)
- `is_for_read` (`bool`): Merge with read-specific optimizations (default: False)

**Behavior:**

- When `is_for_read=True`, select_related and prefetch_related are merged with model-discovered relations
- Passing `instance`/`instances` skips fetching; passing `query_data` fetches automatically
- Either `instance`/`instances` OR `query_data` must be provided, not both

### `get_reverse_relations()`

Discovers reverse relationship field names for prefetch optimization.

#### Signature

```python
def get_reverse_relations() -> list[str]
```

#### Return Value

List of reverse relation accessor names.

#### Example

```python
class Author(ModelSerializer):
    name = models.CharField(max_length=200)

class Book(ModelSerializer):
    author = models.ForeignKey(Author, on_delete=models.CASCADE, related_name="books")

util = ModelUtil(Author)
reverse_rels = util.get_reverse_relations()
print(reverse_rels)  # ["books"]
```

#### Detected Relation Types

| Django Descriptor            | Example        | Detected |
| ---------------------------- | -------------- | -------- |
| `ReverseManyToOneDescriptor` | `author.books` | ✓        |
| `ReverseOneToOneDescriptor`  | `user.profile` | ✓        |
| `ManyToManyDescriptor`       | `article.tags` | ✓        |
| `ForwardManyToOneDescriptor` | `book.author`  | ✗        |
| `ForwardOneToOneDescriptor`  | `profile.user` | ✗        |

#### Use Case

```python
# Avoid N+1 queries when serializing reverse relations
relations = util.get_reverse_relations()
queryset = Author.objects.prefetch_related(*relations)

# Now iterating over authors won't trigger additional queries for books
async for author in queryset:
    books = await sync_to_async(list)(author.books.all())  # No query!
```

### `parse_input_data()`

Normalize incoming schema data into model-ready dictionary.

#### Signature

```python
async def parse_input_data(
    request: HttpRequest,
    data: Schema
) -> tuple[dict, dict]
```

#### Parameters

| Parameter | Type          | Description           |
| --------- | ------------- | --------------------- |
| `request` | `HttpRequest` | Current HTTP request  |
| `data`    | `Schema`      | Ninja schema instance |

#### Return Value

`(payload, customs)` where:

- `payload` (`dict`): Model-ready data with resolved relationships
- `customs` (`dict`): Custom/synthetic fields stripped from payload

#### Transformations

1. **Strip custom fields** → Move to `customs` dict
2. **Remove optional None values** → Don't update if not provided
3. **Decode BinaryField** → Convert base64 string to bytes
4. **Resolve FK IDs** → Fetch related instances

#### Examples

**Basic transformation:**

```python
from ninja import Schema

class UserCreateSchema(Schema):
    username: str
    email: str
    bio: str | None = None

data = UserCreateSchema(
    username="john_doe",
    email="john@example.com",
    bio=None  # Optional, not provided
)

payload, customs = await util.parse_input_data(request, data)

print(payload)
# {"username": "john_doe", "email": "john@example.com"}
# bio is omitted (None stripped)

print(customs)
# {}
```

**With custom fields:**

```python
class User(ModelSerializer):
    username = models.CharField(max_length=150)
    email = models.EmailField()

    class CreateSerializer:
        fields = ["username", "email"]
        customs = [
            ("password_confirm", str, None),
            ("send_welcome_email", bool, True),
        ]

# Schema includes custom fields
data = UserCreateSchema(
    username="john",
    email="john@example.com",
    password_confirm="secret123",
    send_welcome_email=False
)

payload, customs = await util.parse_input_data(request, data)

print(payload)
# {"username": "john", "email": "john@example.com"}

print(customs)
# {"password_confirm": "secret123", "send_welcome_email": False}
```

**With ForeignKey resolution:**

```python
class Article(ModelSerializer):
    title = models.CharField(max_length=200)
    author = models.ForeignKey(User, on_delete=models.CASCADE)
    category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True)

# Input schema expects IDs
data = ArticleCreateSchema(
    title="Getting Started",
    author=5,      # User ID
    category=10    # Category ID
)

payload, customs = await util.parse_input_data(request, data)

print(payload)
# {
#     "title": "Getting Started",
#     "author": <User instance with id=5>,
#     "category": <Category instance with id=10>
# }
```

**With BinaryField (base64):**

```python
class Document(ModelSerializer):
    name = models.CharField(max_length=200)
    file_data = models.BinaryField()

data = DocumentCreateSchema(
    name="report.pdf",
    file_data="iVBORw0KGgoAAAANSUhEUgA..."  # base64 string
)

payload, customs = await util.parse_input_data(request, data)

print(payload)
# {
#     "name": "report.pdf",
#     "file_data": b'\x89PNG\r\n\x1a\n...'  # decoded bytes
# }
```

**Error handling:**

```python
try:
    payload, customs = await util.parse_input_data(request, bad_data)
except SerializeError as e:
    print(e.status_code)  # 400
    print(e.details)
    # {"file_data": "Invalid base64 encoding"}
    # or {"author": "User with id 999 not found"}
```

### `parse_output_data()`

Post-process serialized output for consistency.

#### Signature

```python
async def parse_output_data(
    request: HttpRequest,
    data: Schema
) -> dict
```

#### Parameters

| Parameter | Type          | Description                |
| --------- | ------------- | -------------------------- |
| `request` | `HttpRequest` | Current HTTP request       |
| `data`    | `Schema`      | Serialized schema instance |

#### Return Value

Post-processed dictionary ready for API response.

#### Transformations

1. **Replace nested FK dicts** → Actual model instances
2. **Add `<field>_id` keys** → For nested FK references
3. **Flatten nested structures** → Consistent response format

#### Examples

**Basic FK transformation:**

```python
# Before parse_output_data
{
    "id": 1,
    "title": "Article Title",
    "author": {"id": 10, "username": "john_doe"}
}

# After parse_output_data
{
    "id": 1,
    "title": "Article Title",
    "author": <User instance>,
    "author_id": 10
}
```

**Nested relationships:**

```python
# Before
{
    "id": 1,
    "author": {
        "id": 10,
        "profile": {
            "id": 5,
            "bio": "Developer"
        }
    }
}

# After
{
    "id": 1,
    "author": <User instance>,
    "author_id": 10,
    "profile_id": 5
}
```

**Why is this useful?**

Allows accessing relationships directly in subsequent operations:

```python
result = await util.read_s(request, article, ArticleReadSchema)

# Direct access to instances (no additional queries)
author_name = result["author"].username
has_premium = result["author"].is_premium

# Also provides IDs for convenience
author_id = result["author_id"]
```

### `verbose_name_path_resolver()`

Get URL-friendly path segment from model's verbose name plural.

#### Signature

```python
def verbose_name_path_resolver() -> str
```

#### Return Value

Slugified plural verbose name.

#### Example

```python
class BlogPost(ModelSerializer):
    class Meta:
        verbose_name = "blog post"
        verbose_name_plural = "blog posts"

util = ModelUtil(BlogPost)
path = util.verbose_name_path_resolver()
print(path)  # "blog-posts"

# Used in URL routing:
# /api/blog-posts/
# /api/blog-posts/{id}/
```

### `verbose_name_view_resolver()`

Get display name from model's singular verbose name.

#### Signature

```python
def verbose_name_view_resolver() -> str
```

#### Return Value

Capitalized singular verbose name.

#### Example

```python
class BlogPost(ModelSerializer):
    class Meta:
        verbose_name = "blog post"

util = ModelUtil(BlogPost)
name = util.verbose_name_view_resolver()
print(name)  # "Blog post"

# Used in OpenAPI documentation:
# "Create Blog post"
# "Update Blog post"
```

## CRUD Operations

### `create_s()`

Create new model instance with full lifecycle support.

#### Signature

```python
async def create_s(
    request: HttpRequest,
    data: Schema,
    obj_schema: Schema
) -> dict
```

#### Parameters

| Parameter    | Type          | Description                     |
| ------------ | ------------- | ------------------------------- |
| `request`    | `HttpRequest` | Current HTTP request            |
| `data`       | `Schema`      | Input schema with creation data |
| `obj_schema` | `Schema`      | Output schema for response      |

#### Return Value

Serialized created object as dictionary.

#### Execution Flow

```
1. parse_input_data(data) → (payload, customs)
2. Model.objects.acreate(**payload)
3. custom_actions(customs)    [if ModelSerializer]
4. post_create()              [if ModelSerializer]
5. read_s(obj, obj_schema)
6. return serialized_dict
```

#### Example

```python
from ninja import Schema

class UserCreateSchema(Schema):
    username: str
    email: str
    send_welcome: bool = True

class UserReadSchema(Schema):
    id: int
    username: str
    email: str
    created_at: datetime

# Create user
data = UserCreateSchema(
    username="john_doe",
    email="john@example.com",
    send_welcome=True
)

result = await util.create_s(request, data, UserReadSchema)

print(result)
# {
#     "id": 1,
#     "username": "john_doe",
#     "email": "john@example.com",
#     "created_at": "2024-01-15T10:30:00Z"
# }
```

#### With Hooks

```python
class User(ModelSerializer):
    username = models.CharField(max_length=150)
    email = models.EmailField()

    class CreateSerializer:
        fields = ["username", "email"]
        customs = [("send_welcome", bool, True)]

    async def custom_actions(self, payload):
        if payload.get("send_welcome"):
            await send_welcome_email(self.email)

    async def post_create(self):
        await AuditLog.objects.acreate(
            action="user_created",
            user_id=self.id
        )

# Hooks are automatically invoked
result = await util.create_s(request, data, UserReadSchema)
```

### `read_s()`

Serialize model instance to response dict.

#### Signature

```python
async def read_s(
    request: HttpRequest,
    obj: ModelSerializer | models.Model,
    obj_schema: Schema
) -> dict
```

#### Parameters

| Parameter    | Type                              | Description                 |
| ------------ | --------------------------------- | --------------------------- |
| `request`    | `HttpRequest`                     | Current HTTP request        |
| `obj`        | `ModelSerializer \| models.Model` | Model instance to serialize |
| `obj_schema` | `Schema`                          | Output schema               |

#### Return Value

Serialized object as dictionary.

#### Execution Flow

```
1. obj_schema.from_orm(obj)
2. schema.model_dump(mode="json")
3. parse_output_data(dumped_data)
4. return processed_dict
```

#### Example

```python
user = await User.objects.aget(id=1)
result = await util.read_s(request, user, UserReadSchema)

print(result)
# {
#     "id": 1,
#     "username": "john_doe",
#     "email": "john@example.com",
#     "created_at": "2024-01-15T10:30:00Z"
# }
```

#### With Nested Relations

```python
class ArticleReadSchema(Schema):
    id: int
    title: str
    author: UserReadSchema  # Nested

article = await Article.objects.select_related('author').aget(id=1)
result = await util.read_s(request, article, ArticleReadSchema)

print(result)
# {
#     "id": 1,
#     "title": "Getting Started",
#     "author": <User instance>,
#     "author_id": 10
# }
```

### `update_s()`

Update existing model instance.

#### Signature

```python
async def update_s(
    request: HttpRequest,
    data: Schema,
    pk: int | str,
    obj_schema: Schema
) -> dict
```

#### Parameters

| Parameter    | Type          | Description                     |
| ------------ | ------------- | ------------------------------- |
| `request`    | `HttpRequest` | Current HTTP request            |
| `data`       | `Schema`      | Input schema with update data   |
| `pk`         | `int \| str`  | Primary key of object to update |
| `obj_schema` | `Schema`      | Output schema for response      |

#### Return Value

Serialized updated object as dictionary.

#### Execution Flow

```
1. get_object(pk=pk)
2. parse_input_data(data) → (payload, customs)
3. Update obj fields from payload
4. custom_actions(customs)    [if ModelSerializer]
5. obj.asave()
6. read_s(obj, obj_schema)
7. return serialized_dict
```

#### Example

```python
class UserUpdateSchema(Schema):
    email: str | None = None
    bio: str | None = None

data = UserUpdateSchema(email="newemail@example.com")
result = await util.update_s(request, data, pk=1, obj_schema=UserReadSchema)

print(result)
# {
#     "id": 1,
#     "username": "john_doe",  # unchanged
#     "email": "newemail@example.com",  # updated
#     "bio": "...",  # unchanged
# }
```

#### Partial Updates

Only provided fields are updated:

```python
# Update only email
data = UserUpdateSchema(email="new@example.com")
await util.update_s(request, data, pk=1, UserReadSchema)

# Update only bio
data = UserUpdateSchema(bio="New bio")
await util.update_s(request, data, pk=1, UserReadSchema)

# Update both
data = UserUpdateSchema(email="new@example.com", bio="New bio")
await util.update_s(request, data, pk=1, UserReadSchema)
```

#### With Custom Actions

```python
class User(ModelSerializer):
    class UpdateSerializer:
        optionals = [("email", str)]
        customs = [("reset_password", bool, False)]

    async def custom_actions(self, payload):
        if payload.get("reset_password"):
            await self.send_password_reset_email()

data = UserUpdateSchema(email="new@example.com", reset_password=True)
await util.update_s(request, data, pk=1, UserReadSchema)
# Email updated AND password reset email sent
```

### `delete_s()`

Delete model instance.

#### Signature

```python
async def delete_s(
    request: HttpRequest,
    pk: int | str
) -> None
```

#### Parameters

| Parameter | Type          | Description                     |
| --------- | ------------- | ------------------------------- |
| `request` | `HttpRequest` | Current HTTP request            |
| `pk`      | `int \| str`  | Primary key of object to delete |

#### Return Value

`None`

#### Execution Flow

```
1. get_object(pk=pk)
2. obj.adelete()
3. obj.on_delete()    [if ModelSerializer]
```

#### Example

```python
await util.delete_s(request, pk=1)
# User with id=1 is deleted
```

#### With Delete Hook

```python
class User(ModelSerializer):
    def on_delete(self):
        logger.info(f"User {self.username} deleted")
        cache.delete(f"user:{self.id}")

await util.delete_s(request, pk=1)
# Logs deletion and clears cache
```

## Error Handling

ModelUtil raises `SerializeError` for various failure scenarios:

### 404 Not Found

```python
from ninja_aio.exceptions import SerializeError

try:
    user = await util.get_object(request, pk=999)
except SerializeError as e:
    print(e.status_code)  # 404
    print(e.details)
    # {"user": "not found"}
```

### 400 Bad Request

**Invalid base64:**

```python
try:
    data = DocumentCreateSchema(
        name="doc.pdf",
        file_data="not-valid-base64!!!"
    )
    await util.create_s(request, data, DocumentReadSchema)
except SerializeError as e:
    print(e.status_code)  # 400
    print(e.details)
    # {"file_data": "Invalid base64 encoding"}
```

**Missing related object:**

```python
try:
    data = ArticleCreateSchema(
        title="Test",
        author=999  # Non-existent user ID
    )
    await util.create_s(request, data, ArticleReadSchema)
except SerializeError as e:
    print(e.status_code)  # 400
    print(e.details)
    # {"author": "User with id 999 not found"}
```

## Performance Optimization

### Automatic Query Optimization

```python
class Article(ModelSerializer):
    author = models.ForeignKey(User, on_delete=models.CASCADE)
    category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True)
    tags = models.ManyToManyField(Tag, related_name="articles")

util = ModelUtil(Article)

# Single query optimization
article = await util.get_object(request, pk=1)
# Automatically executes:
# SELECT * FROM article
#   LEFT JOIN user ON article.author_id = user.id
#   LEFT JOIN category ON article.category_id = category.id
# WITH prefetch for tags

# Queryset optimization
articles = await util.get_object(request)
# Automatically adds select_related and prefetch_related
```

### Manual Optimization

For complex scenarios, override in ModelSerializer:

```python
class Article(ModelSerializer):
    @classmethod
    async def queryset_request(cls, request):
        return cls.objects.select_related(
            'author',
            'author__profile',  # Deep relation
            'category'
        ).prefetch_related(
            'tags',
            'comments__author'  # Nested prefetch
        ).only(
            'id', 'title', 'content',  # Limit fields
            'author__username',
            'category__name'
        )
```

## Integration with APIViewSet

ModelUtil is automatically used by APIViewSet:

```python
from ninja_aio.views import APIViewSet

class UserViewSet(APIViewSet):
    model = User
    api = api

    # Internally creates ModelUtil(User)
    # All CRUD operations use ModelUtil methods
```

## Complete Example

```python
from django.db import models
from ninja_aio.models import ModelSerializer, ModelUtil
from ninja import Schema
from django.http import HttpRequest

# Models
class Author(ModelSerializer):
    name = models.CharField(max_length=200)
    email = models.EmailField(unique=True)

    class CreateSerializer:
        fields = ["name", "email"]

    class ReadSerializer:
        fields = ["id", "name", "email"]

class Book(ModelSerializer):
    title = models.CharField(max_length=200)
    author = models.ForeignKey(Author, on_delete=models.CASCADE, related_name="books")
    isbn = models.CharField(max_length=13, unique=True)
    cover_image = models.BinaryField(null=True)
    is_published = models.BooleanField(default=False)

    class CreateSerializer:
        fields = ["title", "author", "isbn"]
        optionals = [("cover_image", str)]  # base64
        customs = [("notify_author", bool, True)]

    class ReadSerializer:
        fields = ["id", "title", "author", "isbn", "is_published"]

    class UpdateSerializer:
        optionals = [
            ("title", str),
            ("is_published", bool),
        ]

    async def custom_actions(self, payload):
        if payload.get("notify_author"):
            await send_email(
                self.author.email,
                f"New book created: {self.title}"
            )

    async def post_create(self):
        await AuditLog.objects.acreate(
            action="book_created",
            book_id=self.id
        )

# Usage
async def example(request: HttpRequest):
    util = ModelUtil(Book)

    # Create
    book_data = BookCreateSchema(
        title="Django Unleashed",
        author=5,
        isbn="9781234567890",
        cover_image="iVBORw0KGgo...",  # base64
        notify_author=True
    )
    created = await util.create_s(request, book_data, BookReadSchema)

    # Read
    book = await util.get_object(request, pk=created["id"])
    serialized = await util.read_s(request, book, BookReadSchema)

    # Update
    update_data = BookUpdateSchema(is_published=True)
    updated = await util.update_s(request, update_data, created["id"], BookReadSchema)

    # Delete
    await util.delete_s(request, created["id"])
```

## Best Practices

1. **Always use with async views:**

   ```python
   async def my_view(request):
       util = ModelUtil(User)
       users = await util.get_object(request)
   ```

2. **Reuse util instances when possible:**

   ```python
   # Good: One util per view
   util = ModelUtil(User)
   user = await util.create_s(...)
   updated = await util.update_s(...)
   ```

3. **Let ModelUtil handle query optimization:**

   ```python
   # Don't manually optimize unless necessary
   user = await util.get_object(request, pk=1)
   # ModelUtil already applied select_related/prefetch_related
   ```

4. **Handle SerializeError appropriately:**

   ```python
   from ninja_aio.exceptions import SerializeError

   try:
       result = await util.create_s(request, data, schema)
   except SerializeError as e:
       return e.status_code, e.details
   ```

5. **Use parse_input_data for custom processing:**
   ```python
   payload, customs = await util.parse_input_data(request, data)
   # Process customs before creation
   if customs.get("validate_uniqueness"):
       # Custom validation logic
       pass
   ```

## See Also

- [Model Serializer](model_serializer.md) - Define schemas on models
- [API ViewSet](../views/api_view_set.md) - High-level CRUD views using ModelUtil
