# :material-cube-outline: Serializer (Meta-driven)

The `Serializer` class provides dynamic schema generation and relation handling for existing Django models without requiring you to adopt the ModelSerializer base class. Use it when:

- :material-database: You already have vanilla Django models in a project and want dynamic Ninja schemas.
- :material-arrow-split-vertical: You prefer to keep models unchanged and define serialization externally.
- :material-package-variant: You need to keep your models lean and define API concerns separately.

It mirrors the behavior of ModelSerializer but reads configuration from a nested Meta class.

## :material-scale-balance: Key Differences from ModelSerializer

While both `ModelSerializer` and `Serializer` provide schema generation and CRUD operations, there are important differences:

| Feature                  | ModelSerializer                     | Serializer                                    |
| ------------------------ | ----------------------------------- | --------------------------------------------- |
| Model class              | Custom base class                   | Plain Django model                            |
| Configuration            | Nested classes (CreateSerializer)   | Meta class (schema_in/out/update)             |
| Lifecycle hooks          | Instance methods (uses `self`)      | Receives `instance` parameter                 |
| Schema generation        | On-demand via generate_*() methods  | On-demand via generate_*() methods            |
| Usage                    | Inherit from ModelSerializer        | Separate serializer class                     |
| Query optimization       | QuerySet nested class               | QuerySet nested class (inherited)             |
| Relation serializers     | Auto-resolved                       | Explicit via relations_serializers (supports string refs & Union) |

---

## :material-key-variant: Key Points

- Works with any Django model (no inheritance required).
- Generates read/create/update/related schemas on demand via ninja.orm.create_schema.
- Supports explicit relation serializers for forward and reverse relations.
- **Supports string references in `relations_serializers` for forward/circular dependencies**.
- **Supports Union types for polymorphic relations** (e.g., generic foreign keys, content types).
- Plays nicely with APIViewSet to auto-wire schemas and queryset handling.

---

## :material-cog: Configuration

Define a Serializer subclass with a nested Meta:

- **model**: Django model class
- **schema_in**: SchemaModelConfig for create inputs
- **schema_out**: SchemaModelConfig for read outputs (list endpoint)
- **schema_detail**: SchemaModelConfig for detail outputs (retrieve endpoint)
- **schema_update**: SchemaModelConfig for patch/update inputs
- **relations_serializers**: Mapping of relation field name -> Serializer class, **string reference**, or **Union of serializers** (supports forward/circular dependencies and polymorphic relations)
- **relations_as_id**: List of relation field names to serialize as IDs instead of nested objects

SchemaModelConfig fields:

- **fields**: `list[str | tuple]` - Model field names to include. Can also contain inline custom field tuples (see below)
- **optionals**: `list[tuple[str, type]]` - Optional fields with their types
- **exclude**: `list[str]` - Fields to exclude from schema
- **customs**: `list[tuple[str, type, Any]]` - Custom/computed fields

### Inline Custom Fields

You can define custom fields directly in the `fields` list as tuples, providing a more concise syntax:

```python
class ArticleSerializer(serializers.Serializer):
    class Meta:
        model = models.Article
        schema_out = serializers.SchemaModelConfig(
            # Mix regular fields with inline custom tuples
            fields=[
                "id",
                "title",
                ("word_count", int, 0),           # 3-tuple: (name, type, default)
                ("is_featured", bool),             # 2-tuple: (name, type) - required
            ]
        )
```

**Tuple formats:**

- **2-tuple**: `(name, type)` - Required field (equivalent to default `...`)
- **3-tuple**: `(name, type, default)` - Optional field with default value

This is equivalent to using the separate `customs` list but keeps field definitions together:

```python
# These two are equivalent:

# Using inline customs
fields=["id", "title", ("extra", str, "default")]

# Using separate customs list
fields=["id", "title"]
customs=[("extra", str, "default")]
```

### Schema Generation

Generate schemas explicitly using these methods:

```python
# Explicitly generate schemas when needed
ArticleSerializer.generate_create_s()  # Returns create (In) schema
ArticleSerializer.generate_read_s()    # Returns read (Out) schema for list endpoint
ArticleSerializer.generate_detail_s()  # Returns detail (Out) schema for retrieve endpoint
ArticleSerializer.generate_update_s()  # Returns update (Patch) schema
ArticleSerializer.generate_related_s() # Returns related (nested) schema
```

Schemas support **forward references and circular dependencies** via string references in `relations_serializers`.

### Detail Schema for Retrieve Endpoint

Use `schema_detail` when you want the retrieve endpoint to return more fields than the list endpoint:

```python
class ArticleSerializer(serializers.Serializer):
    class Meta:
        model = models.Article
        schema_out = serializers.SchemaModelConfig(
            # List view: minimal fields for performance
            fields=["id", "title", "summary"]
        )
        schema_detail = serializers.SchemaModelConfig(
            # Detail view: all fields including expensive relations
            fields=["id", "title", "summary", "content", "author", "tags"],
            customs=[("reading_time", int, lambda obj: len(obj.content.split()) // 200)]
        )
```

When used with `APIViewSet`:
- **List endpoint** (`GET /articles/`) uses `schema_out`
- **Retrieve endpoint** (`GET /articles/{pk}`) uses `schema_detail` (falls back to `schema_out` if not defined)

**Fallback Behavior:** Unlike `ModelSerializer`, `Serializer` uses **schema-level fallback**:

- If `schema_detail` is **not defined** → all field types (`fields`, `customs`, `optionals`, `exclude`) fall back to `schema_out`
- If `schema_detail` **is defined** → no inheritance from `schema_out`, even for empty field types

This means you must explicitly define all needed configurations in `schema_detail` if you define it at all:

```python
class ArticleSerializer(serializers.Serializer):
    class Meta:
        model = models.Article
        schema_out = serializers.SchemaModelConfig(
            fields=["id", "title"],
            customs=[("word_count", int, 0)],  # This custom...
        )
        schema_detail = serializers.SchemaModelConfig(
            fields=["id", "title", "content"],
            # ...is NOT inherited here because schema_detail is defined
            # You must explicitly add it if needed:
            # customs=[("word_count", int, 0)],
        )
```

---

## :material-link-variant: Example: Simple FK

```python
from ninja_aio.models import serializers
from . import models

class ArticleSerializer(serializers.Serializer):
    class Meta:
        model = models.Article
        schema_in = serializers.SchemaModelConfig(
            fields=["title", "content", "author"]
        )
        schema_out = serializers.SchemaModelConfig(
            fields=["id", "title", "content", "author"]
        )
        schema_update = serializers.SchemaModelConfig(
            optionals=[("title", str), ("content", str)]
        )
```

---

## :material-hook: Lifecycle Hooks

Serializer supports lifecycle hooks similar to ModelSerializer, but with a key difference: **all hooks receive an `instance` parameter** instead of using `self`:

```python
class ArticleSerializer(serializers.Serializer):
    class Meta:
        model = models.Article
        schema_in = serializers.SchemaModelConfig(
            fields=["title", "content", "author"],
            customs=[("notify_author", bool, True)]
        )
        schema_out = serializers.SchemaModelConfig(
            fields=["id", "title", "content", "author"]
        )

    @classmethod
    async def queryset_request(cls, request):
        """Filter and optimize queryset per request."""
        return cls._meta.model.objects.select_related("author")

    async def custom_actions(self, payload, instance):
        """Execute custom actions with access to the instance."""
        if payload.get("notify_author"):
            await send_email(instance.author.email, f"Article created: {instance.title}")

    async def post_create(self, instance):
        """Hook after instance creation."""
        await AuditLog.objects.acreate(
            action="article_created",
            article_id=instance.id
        )

    def before_save(self, instance):
        """Sync hook before save (receives instance)."""
        instance.slug = slugify(instance.title)

    def after_save(self, instance):
        """Sync hook after save (receives instance)."""
        cache.delete(f"article:{instance.id}")

    def on_delete(self, instance):
        """Sync hook after deletion (receives instance)."""
        logger.info(f"Article {instance.id} deleted")
```

### Available Hooks

| Hook                        | Type  | When Called               | Parameters              |
| --------------------------- | ----- | ------------------------- | ----------------------- |
| `queryset_request(request)` | async | Before queryset building  | `request`               |
| `custom_actions(payload, i)`| async | After field assignment    | `payload`, `instance`   |
| `post_create(instance)`     | async | After first save          | `instance`              |
| `before_save(instance)`     | sync  | Before any save           | `instance`              |
| `after_save(instance)`      | sync  | After any save            | `instance`              |
| `on_create_before_save(i)`  | sync  | Before creation save only | `instance`              |
| `on_create_after_save(i)`   | sync  | After creation save only  | `instance`              |
| `on_delete(instance)`       | sync  | After deletion            | `instance`              |

---

## :material-arrow-left-right: Example: Reverse Relation with Nested Serialization

```python
class AuthorSerializer(serializers.Serializer):
    class Meta:
        model = models.Author
        schema_out = serializers.SchemaModelConfig(
            fields=["id", "name", "articles"]  # reverse related name
        )
        relations_serializers = {
            "articles": ArticleSerializer,  # include nested article schema
        }
```

---

## :material-text-search: String References for Forward/Circular Dependencies

You can use string references in `relations_serializers` to handle forward references and circular dependencies:

```python
class AuthorSerializer(serializers.Serializer):
    class Meta:
        model = models.Author
        schema_out = serializers.SchemaModelConfig(
            fields=["id", "name", "articles"]
        )
        relations_serializers = {
            "articles": "ArticleSerializer",  # String reference - resolved lazily
        }

class ArticleSerializer(serializers.Serializer):
    class Meta:
        model = models.Article
        schema_out = serializers.SchemaModelConfig(
            fields=["id", "title", "author"]
        )
        relations_serializers = {
            "author": "AuthorSerializer",  # Circular reference works!
        }
```

**String Reference Formats:**

1. **Class name in the same module:**
   ```python
   relations_serializers = {
       "articles": "ArticleSerializer",  # Resolved in current module
   }
   ```

2. **Absolute import path:**
   ```python
   relations_serializers = {
       "articles": "myapp.serializers.ArticleSerializer",  # Full import path
   }
   ```

**String Reference Requirements:**
- String can be the class name of a serializer in the same module, or an absolute import path
- Absolute paths use dot notation: `"package.module.ClassName"`
- References are resolved lazily when schemas are generated
- Both forward and circular references are supported

**Example: Cross-Module References with Absolute Paths**

```python
# myapp/serializers.py
from ninja_aio.models import serializers
from . import models

class ArticleSerializer(serializers.Serializer):
    class Meta:
        model = models.Article
        schema_out = serializers.SchemaModelConfig(
            fields=["id", "title", "author"]
        )
        relations_serializers = {
            # Reference a serializer from another module
            "author": "users.serializers.UserSerializer",
        }

# users/serializers.py
from ninja_aio.models import serializers
from . import models

class UserSerializer(serializers.Serializer):
    class Meta:
        model = models.User
        schema_out = serializers.SchemaModelConfig(
            fields=["id", "username", "email", "articles"]
        )
        relations_serializers = {
            # Reference back to the article serializer
            "articles": "myapp.serializers.ArticleSerializer",
        }
```

---

## :material-set-merge: Union Types for Polymorphic Relations

You can use `Union` types in `relations_serializers` to handle polymorphic relationships where a field can reference multiple possible serializer types. This is particularly useful for generic foreign keys, content types, or any scenario where a relation can point to different model types.

```python
from typing import Union
from ninja_aio.models import serializers
from . import models

class VideoSerializer(serializers.Serializer):
    class Meta:
        model = models.Video
        schema_out = serializers.SchemaModelConfig(
            fields=["id", "title", "duration", "url"]
        )

class ImageSerializer(serializers.Serializer):
    class Meta:
        model = models.Image
        schema_out = serializers.SchemaModelConfig(
            fields=["id", "title", "width", "height", "url"]
        )

class CommentSerializer(serializers.Serializer):
    class Meta:
        model = models.Comment
        schema_out = serializers.SchemaModelConfig(
            fields=["id", "text", "content_object"]
        )
        relations_serializers = {
            # content_object can be a Video or Image
            "content_object": Union[VideoSerializer, ImageSerializer],
        }
```

**Union Type Formats:**

1. **Direct class references:**
   ```python
   relations_serializers = {
       "field": Union[SerializerA, SerializerB],
   }
   ```

2. **String references:**
   ```python
   relations_serializers = {
       "field": Union["SerializerA", "SerializerB"],
   }
   ```

3. **Mixed class and string references:**
   ```python
   relations_serializers = {
       "field": Union[SerializerA, "SerializerB"],
   }
   ```

4. **Absolute import paths:**
   ```python
   relations_serializers = {
       "field": Union["myapp.serializers.SerializerA", SerializerB],
   }
   ```

**Use Cases for Union Types:**

- **Polymorphic relations:** Generic foreign keys or Django ContentType relations
- **Flexible APIs:** Different response formats for the same field based on runtime type
- **Gradual migrations:** Transitioning between different serializer implementations
- **Multi-tenant systems:** Different serialization requirements per tenant

**Complete Polymorphic Example:**

```python
from typing import Union
from django.contrib.contenttypes.fields import GenericForeignKey
from ninja_aio.models import serializers

# Models
class Comment(models.Model):
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField()
    content_object = GenericForeignKey('content_type', 'object_id')
    text = models.TextField()

# Serializers for different content types
class BlogPostSerializer(serializers.Serializer):
    class Meta:
        model = models.BlogPost
        schema_out = serializers.SchemaModelConfig(
            fields=["id", "title", "body", "published_at"]
        )

class ProductSerializer(serializers.Serializer):
    class Meta:
        model = models.Product
        schema_out = serializers.SchemaModelConfig(
            fields=["id", "name", "price", "stock"]
        )

class EventSerializer(serializers.Serializer):
    class Meta:
        model = models.Event
        schema_out = serializers.SchemaModelConfig(
            fields=["id", "name", "date", "location"]
        )

# Comment serializer with Union support
class CommentSerializer(serializers.Serializer):
    class Meta:
        model = Comment
        schema_out = serializers.SchemaModelConfig(
            fields=["id", "text", "created_at", "content_object"]
        )
        relations_serializers = {
            # Comments can be on blog posts, products, or events
            "content_object": Union[BlogPostSerializer, ProductSerializer, EventSerializer],
        }
```

Notes:

- Forward relations are included as plain fields unless a related ModelSerializer/Serializer is declared.
- Reverse relations require an entry in relations_serializers when using vanilla Django models.
- When the related model is a ModelSerializer, related schemas can be auto-resolved.
- Absolute import paths are useful for cross-module references and avoiding circular import issues at module load time.
- Union types are resolved lazily, so forward and circular references work seamlessly.
- The schema generator will create a union of all possible schemas from the serializers in the Union.

---

## :material-identifier: Relations as ID

Use `relations_as_id` in Meta to serialize relation fields as IDs instead of nested objects. This is useful for:

- Reducing response payload size
- Avoiding circular serialization
- Performance optimization when nested data isn't needed
- API designs where clients fetch related data separately

**Supported Relations:**

| Relation Type      | Output Type       | Example Value        |
|--------------------|-------------------|----------------------|
| Forward FK         | `PK_TYPE \| None` | `5` or `null`        |
| Forward O2O        | `PK_TYPE \| None` | `3` or `null`        |
| Reverse FK         | `list[PK_TYPE]`   | `[1, 2, 3]`          |
| Reverse O2O        | `PK_TYPE \| None` | `7` or `null`        |
| M2M (forward)      | `list[PK_TYPE]`   | `[1, 2]`             |
| M2M (reverse)      | `list[PK_TYPE]`   | `[4, 5, 6]`          |

**Note:** `PK_TYPE` is automatically detected from the related model's primary key field. Supported types include `int` (default), `UUID`, `str`, and any other Django primary key type.

**Example:**

```python
from ninja_aio.models import serializers
from . import models

class AuthorSerializer(serializers.Serializer):
    class Meta:
        model = models.Author
        schema_out = serializers.SchemaModelConfig(
            fields=["id", "name", "books"]
        )
        relations_as_id = ["books"]  # Serialize reverse FK as list of IDs

class BookSerializer(serializers.Serializer):
    class Meta:
        model = models.Book
        schema_out = serializers.SchemaModelConfig(
            fields=["id", "title", "author"]
        )
        relations_as_id = ["author"]  # Serialize forward FK as ID
```

**Output (Author):**

```json
{
  "id": 1,
  "name": "J.K. Rowling",
  "books": [1, 2, 3]
}
```

**Output (Book):**

```json
{
  "id": 1,
  "title": "Harry Potter",
  "author": 1
}
```

**M2M Example:**

```python
class TagSerializer(serializers.Serializer):
    class Meta:
        model = models.Tag
        schema_out = serializers.SchemaModelConfig(
            fields=["id", "name", "articles"]
        )
        relations_as_id = ["articles"]  # Reverse M2M as list of IDs

class ArticleSerializer(serializers.Serializer):
    class Meta:
        model = models.Article
        schema_out = serializers.SchemaModelConfig(
            fields=["id", "title", "tags"]
        )
        relations_as_id = ["tags"]  # Forward M2M as list of IDs
```

**Output (Article):**

```json
{
  "id": 1,
  "title": "Getting Started with Django",
  "tags": [1, 2, 5]
}
```

**UUID Primary Key Example:**

When related models use UUID primary keys, the output type is automatically `UUID`:

```python
import uuid
from django.db import models

class Author(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=200)

class AuthorSerializer(serializers.Serializer):
    class Meta:
        model = Author
        schema_out = serializers.SchemaModelConfig(
            fields=["id", "name", "books"]
        )
        relations_as_id = ["books"]
```

**Output (Author with UUID):**

```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "name": "J.K. Rowling",
  "books": [
    "6ba7b810-9dad-11d1-80b4-00c04fd430c8",
    "6ba7b811-9dad-11d1-80b4-00c04fd430c8"
  ]
}
```

**Combining with relations_serializers:**

You can use both `relations_as_id` and `relations_serializers` in the same serializer. Fields in `relations_as_id` take precedence:

```python
class ArticleSerializer(serializers.Serializer):
    class Meta:
        model = models.Article
        schema_out = serializers.SchemaModelConfig(
            fields=["id", "title", "author", "tags", "category"]
        )
        relations_serializers = {
            "author": AuthorSerializer,      # Nested object
            "category": CategorySerializer,  # Nested object
        }
        relations_as_id = ["tags"]           # Just IDs
```

**Query Optimization Note:** When using `relations_as_id`, you should still use `select_related()` for forward relations and `prefetch_related()` for reverse/M2M relations to avoid N+1 queries:

```python
class ArticleSerializer(serializers.Serializer):
    class Meta:
        model = models.Article
        schema_out = serializers.SchemaModelConfig(
            fields=["id", "title", "author", "tags"]
        )
        relations_as_id = ["author", "tags"]

    class QuerySet:
        read = ModelQuerySetSchema(
            select_related=["author"],       # For forward FK
            prefetch_related=["tags"],        # For M2M
        )

---

## :material-view-grid: Using with APIViewSet

You can attach a Serializer to an APIViewSet to auto-generate schemas and leverage queryset_request when present:

```python
from ninja_aio.views import APIViewSet
from ninja_aio import NinjaAIO
from . import models

api = NinjaAIO()

@api.viewset(model=models.Article)
class ArticleViewSet(APIViewSet):
    serializer_class = ArticleSerializer
    # Optionally define query_params or custom handlers
```

Behavior:

- If `model` is a ModelSerializer, APIViewSet uses the model to generate schemas directly
- If `model` is a vanilla Django model and `serializer_class` is provided, APIViewSet uses the Serializer to generate missing schemas
- ModelUtil creates a serializer instance and uses its `queryset_request()` hook if defined to build optimized querysets
- Lifecycle hooks from the serializer are invoked during CRUD operations

---

## :material-database-refresh: CRUD Operations with Serializer

When using a Serializer with APIViewSet, CRUD operations automatically invoke the appropriate lifecycle hooks:

```python
# Create operation flow:
# 1. parse_input_data() - normalize payload
# 2. create() - create instance
# 3. custom_actions() - execute custom logic
# 4. save() - persists with before/after hooks
# 5. post_create() - post-creation hook
# 6. read_s() - serialize response

# Update operation flow:
# 1. get_object() - fetch instance
# 2. parse_input_data() - normalize payload
# 3. update() - update instance fields
# 4. custom_actions() - execute custom logic
# 5. save() - persists with before/after hooks
# 6. read_s() - serialize response

# Delete operation flow:
# 1. get_object() - fetch instance
# 2. adelete() - delete instance
# 3. on_delete() - deletion hook
```

---

## :material-tune-variant: Advanced: Customs and Optionals

Customs and optionals behave like ModelSerializer:

- customs: synthetic fields included in schemas (with default or required when default is Ellipsis).
- optionals: patch-like optional fields. In read schema, they are included with default None.

```python
class PublishSerializer(serializers.Serializer):
    class Meta:
        model = models.Article
        schema_update = serializers.SchemaModelConfig(
            optionals=[("is_published", bool)],
            customs=[("notify_subscribers", bool, True)],
        )
```

generate_update_s merges optionals and customs for the Patch schema.

---

## :material-lightning-bolt: Query Optimization with Serializer

Like ModelSerializer, Serializer supports query optimization via a nested QuerySet class:

```python
from ninja_aio.schemas.helpers import ModelQuerySetSchema, ModelQuerySetExtraSchema

class ArticleSerializer(serializers.Serializer):
    class Meta:
        model = models.Article
        schema_out = serializers.SchemaModelConfig(
            fields=["id", "title", "content", "author", "category"]
        )
        schema_detail = serializers.SchemaModelConfig(
            fields=["id", "title", "content", "author", "category", "tags", "comments"]
        )

    class QuerySet:
        read = ModelQuerySetSchema(
            select_related=["author", "category"],
            prefetch_related=["tags"],
        )
        detail = ModelQuerySetSchema(
            select_related=["author", "category", "author__profile"],
            prefetch_related=["tags", "comments", "comments__author"],
        )
        queryset_request = ModelQuerySetSchema(
            select_related=[],
            prefetch_related=["comments"],
        )
        extras = [
            ModelQuerySetExtraSchema(
                scope="detail_view",
                select_related=["author__profile"],
                prefetch_related=["tags", "comments__author"],
            )
        ]
```

The QuerySet configuration is used by ModelUtil to automatically optimize database queries:

- **read**: Applied to list operations (`is_for="read"`)
- **detail**: Applied to retrieve/detail operations (`is_for="detail"`). Falls back to `read` if not defined.
- **queryset_request**: Applied inside the `queryset_request` hook
- **extras**: Named configurations available via `QueryUtil.SCOPES`

---

## :material-code-braces: Complete Example

```python
from ninja_aio.models import serializers
from ninja_aio import NinjaAIO
from ninja_aio.views import APIViewSet
from django.db import models as django_models

# Plain Django models
class Author(django_models.Model):
    name = django_models.CharField(max_length=200)
    email = django_models.EmailField()

class Article(django_models.Model):
    title = django_models.CharField(max_length=200)
    content = django_models.TextField()
    author = django_models.ForeignKey(Author, on_delete=django_models.CASCADE)
    is_published = django_models.BooleanField(default=False)

# Serializers
class AuthorSerializer(serializers.Serializer):
    class Meta:
        model = Author
        schema_out = serializers.SchemaModelConfig(
            fields=["id", "name", "email"]
        )

class ArticleSerializer(serializers.Serializer):
    class Meta:
        model = Article
        schema_in = serializers.SchemaModelConfig(
            fields=["title", "content", "author"]
        )
        schema_out = serializers.SchemaModelConfig(
            fields=["id", "title", "content", "author", "is_published"]
        )
        schema_update = serializers.SchemaModelConfig(
            optionals=[("title", str), ("content", str)],
            customs=[("publish_now", bool, False)]
        )
        relations_serializers = {
            "author": AuthorSerializer
        }

    class QuerySet:
        read = serializers.ModelQuerySetSchema(
            select_related=["author"]
        )

    async def custom_actions(self, payload, instance):
        if payload.get("publish_now"):
            instance.is_published = True
            await sync_to_async(instance.save)()

# ViewSets
api = NinjaAIO()

@api.viewset(model=Article)
class ArticleViewSet(APIViewSet):
    serializer_class = ArticleSerializer
```

---

## :material-swap-horizontal: When to Choose Serializer vs ModelSerializer

**Choose Serializer when:**

- You have existing Django models that you can't or don't want to modify
- You want to keep models and API concerns separated
- You're incrementally adding API functionality to an existing project
- You prefer declarative configuration via Meta classes
- Multiple teams work on models vs API layers

**Choose ModelSerializer when:**

- You're building a new project from scratch
- You want to centralize all model and API concerns in one place
- You prefer configuration via nested classes on the model
- You want auto-binding and less boilerplate
- Your models are specifically designed for API usage

Both approaches support:

- Nested relations and dynamic schema generation
- Query optimization via QuerySet configuration
- Lifecycle hooks for custom business logic
- Integration with APIViewSet for auto-generated CRUD endpoints

Choose the pattern that best fits your project architecture and team structure.

---

## :material-compass: See Also

<div class="grid cards" markdown>

- :material-file-document-edit: **Model Serializer** — Base class approach with auto-binding

    [:octicons-arrow-right-24: Model Serializer](model_serializer.md)

- :material-check-decagram: **Validators** — Field & model validators on serializers

    [:octicons-arrow-right-24: Validators](validators.md)

- :material-cog-sync: **Model Util** — Internal CRUD engine and query optimization

    [:octicons-arrow-right-24: Model Util](model_util.md)

- :material-view-grid: **APIViewSet** — Auto-generated CRUD endpoints

    [:octicons-arrow-right-24: APIViewSet](../views/api_view_set.md)

- :material-school: **Tutorial: Serializer** — Step-by-step guide

    [:octicons-arrow-right-24: Serializer Tutorial](../../tutorial/serializer.md)

</div>
