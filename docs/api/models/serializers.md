# Serializer (Meta-driven)

The Serializer class provides dynamic schema generation and relation handling for existing Django models without requiring you to adopt the ModelSerializer base class. Use it when:

- You already have vanilla Django models in a project and want dynamic Ninja schemas.
- You prefer to keep models unchanged and define serialization externally.

It mirrors the behavior of ModelSerializer but reads configuration from a nested Meta class.

## Key points

- Works with any Django model (no inheritance required).
- Generates read/create/update/related schemas on demand via ninja.orm.create_schema.
- Supports explicit relation serializers for forward and reverse relations.
- Plays nicely with APIViewSet to auto-wire schemas and queryset handling.

## Configuration

Define a Serializer subclass with a nested Meta:

- model: Django model class.
- schema_in: SchemaModelConfig for create inputs.
- schema_out: SchemaModelConfig for read outputs.
- schema_update: SchemaModelConfig for patch/update inputs.
- relations_serializers: mapping of relation field name -> Serializer to include nested schemas for relations.

SchemaModelConfig fields:

- fields: list[str]
- optionals: list[tuple[str, type]]
- exclude: list[str]
- customs: list[tuple[str, type, Any]]

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

Generate schemas when needed:

```python
ArticleSerializer.generate_read_s()
ArticleSerializer.generate_create_s()
ArticleSerializer.generate_update_s()
ArticleSerializer.generate_related_s()
```

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

Notes:

- Forward relations are included as plain fields unless a related ModelSerializer/Serializer is declared.
- Reverse relations require an entry in relations_serializers when using vanilla Django models.
- When the related model is a ModelSerializer, related schemas can be auto-resolved.

## Using with APIViewSet

You can attach a Serializer to an APIViewSet to auto-generate schemas and leverage queryset_request when present:

```python
from ninja_aio.views import APIViewSet
from ninja_aio import NinjaAIO
from . import models

api = NinjaAIO()

@api.viewset(models.Article)
class ArticleViewSet(APIViewSet):
    serializer_class = ArticleSerializer
    # Optionally define query_params or custom handlers
```

Behavior:

- If model is a ModelSerializer, APIViewSet uses the model to generate schemas.
- If model is a vanilla model and serializer_class is provided, APIViewSet uses the Serializer to generate missing schemas.
- ModelUtil uses serializer_class.queryset_request if defined to build optimized querysets.

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

## When to choose Serializer vs ModelSerializer

- Serializer: Keep your existing models unchanged; define schemas near your API layer. Ideal for incremental adoption.
- ModelSerializer: Centralize API schema and hooks on the model class itself. Ideal for greenfield projects inside this framework.

Both approaches support nested relations and dynamic schema generation. Choose the one that best fits your project structure.
