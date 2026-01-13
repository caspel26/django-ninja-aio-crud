# Serializer (Meta-driven)

The `Serializer` class provides dynamic schema generation and relation handling for existing Django models without requiring you to adopt the ModelSerializer base class. Use it when:

- You already have vanilla Django models in a project and want dynamic Ninja schemas.
- You prefer to keep models unchanged and define serialization externally.
- You need to keep your models lean and define API concerns separately.

It mirrors the behavior of ModelSerializer but reads configuration from a nested Meta class.

## Key Differences from ModelSerializer

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

## Key points

- Works with any Django model (no inheritance required).
- Generates read/create/update/related schemas on demand via ninja.orm.create_schema.
- Supports explicit relation serializers for forward and reverse relations.
- **Supports string references in `relations_serializers` for forward/circular dependencies**.
- **Supports Union types for polymorphic relations** (e.g., generic foreign keys, content types).
- Plays nicely with APIViewSet to auto-wire schemas and queryset handling.

## Configuration

Define a Serializer subclass with a nested Meta:

- **model**: Django model class
- **schema_in**: SchemaModelConfig for create inputs
- **schema_out**: SchemaModelConfig for read outputs
- **schema_update**: SchemaModelConfig for patch/update inputs
- **relations_serializers**: Mapping of relation field name -> Serializer class, **string reference**, or **Union of serializers** (supports forward/circular dependencies and polymorphic relations)

SchemaModelConfig fields:

- **fields**: `list[str]` - Model field names to include
- **optionals**: `list[tuple[str, type]]` - Optional fields with their types
- **exclude**: `list[str]` - Fields to exclude from schema
- **customs**: `list[tuple[str, type, Any]]` - Custom/computed fields

### Schema Generation

Generate schemas explicitly using these methods:

```python
# Explicitly generate schemas when needed
ArticleSerializer.generate_create_s()  # Returns create (In) schema
ArticleSerializer.generate_read_s()    # Returns read (Out) schema
ArticleSerializer.generate_update_s()  # Returns update (Patch) schema
ArticleSerializer.generate_related_s() # Returns related (nested) schema
```

Schemas support **forward references and circular dependencies** via string references in `relations_serializers`.

## Example: simple FK

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

## Lifecycle Hooks

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

## Example: reverse relation with nested serialization

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

## String References for Forward/Circular Dependencies

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

## Union Types for Polymorphic Relations

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

## Using with APIViewSet

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

## CRUD Operations with Serializer

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

## Advanced: customs and optionals

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

## Query Optimization with Serializer

Like ModelSerializer, Serializer supports query optimization via a nested QuerySet class:

```python
from ninja_aio.schemas.helpers import ModelQuerySetSchema, ModelQuerySetExtraSchema

class ArticleSerializer(serializers.Serializer):
    class Meta:
        model = models.Article
        schema_out = serializers.SchemaModelConfig(
            fields=["id", "title", "content", "author", "category"]
        )

    class QuerySet:
        read = ModelQuerySetSchema(
            select_related=["author", "category"],
            prefetch_related=["tags"],
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

The QuerySet configuration is used by ModelUtil to automatically optimize database queries during read operations.

## Complete Example

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

## When to choose Serializer vs ModelSerializer

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
