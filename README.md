<p align="center">
  <img src="https://raw.githubusercontent.com/caspel26/django-ninja-aio-crud/main/docs/images/logo.png" alt="django-ninja-aio-crud" width="120">
</p>

<h1 align="center">django-ninja-aio-crud</h1>

<p align="center">
  <strong>Async CRUD framework for Django Ninja</strong><br>
  Automatic schema generation · Filtering · Pagination · Auth · M2M management
</p>

<p align="center">
  <a href="https://github.com/caspel26/django-ninja-aio-crud/actions/workflows/coverage.yml"><img src="https://github.com/caspel26/django-ninja-aio-crud/actions/workflows/coverage.yml/badge.svg" alt="Tests"></a>
  <a href="https://sonarcloud.io/summary/new_code?id=caspel26_django-ninja-aio-crud"><img src="https://sonarcloud.io/api/project_badges/measure?project=caspel26_django-ninja-aio-crud&metric=alert_status" alt="Quality Gate Status"></a>
  <a href="https://codecov.io/gh/caspel26/django-ninja-aio-crud/"><img src="https://codecov.io/gh/caspel26/django-ninja-aio-crud/graph/badge.svg?token=DZ5WDT3S20" alt="codecov"></a>
  <a href="https://pypi.org/project/django-ninja-aio-crud/"><img src="https://img.shields.io/pypi/v/django-ninja-aio-crud?color=g&logo=pypi&logoColor=white" alt="PyPI - Version"></a>
  <a href="LICENSE"><img src="https://img.shields.io/pypi/l/django-ninja-aio-crud" alt="PyPI - License"></a>
  <a href="https://github.com/astral-sh/ruff"><img src="https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json" alt="Ruff"></a>
</p>

<p align="center">
  <a href="https://django-ninja-aio.com">Documentation</a> ·
  <a href="https://pypi.org/project/django-ninja-aio-crud/">PyPI</a> ·
  <a href="https://github.com/caspel26/ninja-aio-blog-example">Example Project</a> ·
  <a href="https://github.com/caspel26/django-ninja-aio-crud/issues">Issues</a>
</p>

---

## Features

| | Feature | Description |
|---|---|---|
| **Meta-driven Serializer** | Dynamic schemas | Generate CRUD schemas for existing Django models without changing base classes |
| **Async CRUD ViewSets** | Full operations | Create, list, retrieve, update, delete — all async |
| **Auto Schemas** | Pydantic generation | Automatic read/create/update schemas from `ModelSerializer` |
| **Dynamic Query Params** | Runtime schemas | Built with `pydantic.create_model` for flexible filtering |
| **Per-method Auth** | Granular control | `auth`, `get_auth`, `post_auth`, etc. |
| **Async Pagination** | Customizable | Fully async, pluggable pagination classes |
| **M2M Relations** | Add/remove/list | Endpoints via `M2MRelationSchema` with filtering support |
| **Reverse Relations** | Nested serialization | Automatic handling of reverse FK and M2M |
| **Lifecycle Hooks** | Extensible | `before_save`, `after_save`, `custom_actions`, `on_delete`, and more |
| **Schema Validators** | Pydantic validators | `@field_validator` and `@model_validator` on serializer classes |
| **ORJSON Renderer** | Performance | Built-in fast JSON rendering via `NinjaAIO` |

---

## Quick Start

### Option A: Meta-driven Serializer (existing models)

Use this if you already have Django models and don't want to change their base class.

```python
from ninja_aio.models import serializers
from ninja_aio.views import APIViewSet
from ninja_aio import NinjaAIO
from . import models

class BookSerializer(serializers.Serializer):
    class Meta:
        model = models.Book
        schema_in = serializers.SchemaModelConfig(fields=["title", "published"])
        schema_out = serializers.SchemaModelConfig(fields=["id", "title", "published"])
        schema_update = serializers.SchemaModelConfig(
            optionals=[("title", str), ("published", bool)]
        )

api = NinjaAIO()

@api.viewset(models.Book)
class BookViewSet(APIViewSet):
    serializer_class = BookSerializer
```

### Option B: ModelSerializer (new projects)

Define models with built-in serialization for minimal boilerplate.

**models.py**

```python
from django.db import models
from ninja_aio.models import ModelSerializer

class Book(ModelSerializer):
    title = models.CharField(max_length=120)
    published = models.BooleanField(default=True)

    class ReadSerializer:
        fields = ["id", "title", "published"]

    class CreateSerializer:
        fields = ["title", "published"]

    class UpdateSerializer:
        optionals = [("title", str), ("published", bool)]
```

**views.py**

```python
from ninja_aio import NinjaAIO
from ninja_aio.views import APIViewSet
from .models import Book

api = NinjaAIO()

@api.viewset(Book)
class BookViewSet(APIViewSet):
    pass
```

> Visit `/docs` — CRUD endpoints ready.

---

## Query Filtering

```python
@api.viewset(Book)
class BookViewSet(APIViewSet):
    query_params = {"published": (bool, None), "title": (str, None)}

    async def query_params_handler(self, queryset, filters):
        if filters.get("published") is not None:
            queryset = queryset.filter(published=filters["published"])
        if filters.get("title"):
            queryset = queryset.filter(title__icontains=filters["title"])
        return queryset
```

```
GET /book/?published=true&title=python
```

---

## Many-to-Many Relations

```python
from ninja_aio.schemas import M2MRelationSchema

class Tag(ModelSerializer):
    name = models.CharField(max_length=50)
    class ReadSerializer:
        fields = ["id", "name"]

class Article(ModelSerializer):
    title = models.CharField(max_length=120)
    tags = models.ManyToManyField(Tag, related_name="articles")
    class ReadSerializer:
        fields = ["id", "title", "tags"]

@api.viewset(Article)
class ArticleViewSet(APIViewSet):
    m2m_relations = [
        M2MRelationSchema(
            model=Tag,
            related_name="tags",
            filters={"name": (str, "")}
        )
    ]

    async def tags_query_params_handler(self, queryset, filters):
        n = filters.get("name")
        if n:
            queryset = queryset.filter(name__icontains=n)
        return queryset
```

**Endpoints:**

```
GET  /article/{pk}/tag?name=dev
POST /article/{pk}/tag/    body: {"add": [1, 2], "remove": [3]}
```

---

## Authentication (JWT)

```python
from ninja_aio.auth import AsyncJwtBearer
from joserfc import jwk

class JWTAuth(AsyncJwtBearer):
    jwt_public = jwk.RSAKey.import_key("-----BEGIN PUBLIC KEY----- ...")
    jwt_alg = "RS256"
    claims = {"sub": {"essential": True}}

    async def auth_handler(self, request):
        book_id = self.dcd.claims.get("sub")
        return await Book.objects.aget(id=book_id)

@api.viewset(Book)
class SecureBookViewSet(APIViewSet):
    auth = [JWTAuth()]
    get_auth = None  # list/retrieve remain public
```

---

## Lifecycle Hooks

Available on every save/delete cycle:

| Hook | When |
|---|---|
| `on_create_before_save` | Before first save |
| `on_create_after_save` | After first save |
| `before_save` | Before any save |
| `after_save` | After any save |
| `on_delete` | After deletion |
| `custom_actions(payload)` | Create/update custom field logic |
| `post_create()` | After create commit |

---

## Custom Endpoints

```python
from ninja_aio.decorators import api_get

@api.viewset(Book)
class BookViewSet(APIViewSet):
    @api_get("/stats/")
    async def stats(self, request):
        total = await Book.objects.acount()
        return {"total": total}
```

---

## Pagination

Default: `PageNumberPagination`. Override per ViewSet:

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

## Schema Validators

Add Pydantic `@field_validator` and `@model_validator` directly on serializer classes for input validation.

### ModelSerializer

Declare validators on inner serializer classes:

```python
from django.db import models
from pydantic import field_validator, model_validator
from ninja_aio.models import ModelSerializer

class Book(ModelSerializer):
    title = models.CharField(max_length=120)
    description = models.TextField(blank=True)

    class CreateSerializer:
        fields = ["title", "description"]

        @field_validator("title")
        @classmethod
        def validate_title_min_length(cls, v):
            if len(v) < 3:
                raise ValueError("Title must be at least 3 characters")
            return v

    class UpdateSerializer:
        optionals = [("title", str), ("description", str)]

        @field_validator("title")
        @classmethod
        def validate_title_not_empty(cls, v):
            if v is not None and len(v.strip()) == 0:
                raise ValueError("Title cannot be blank")
            return v

    class ReadSerializer:
        fields = ["id", "title", "description"]

        @model_validator(mode="after")
        def enrich_output(self):
            # Transform or enrich the output schema
            return self
```

### Meta-driven Serializer

Use dedicated `{Type}Validators` inner classes:

```python
from pydantic import field_validator, model_validator
from ninja_aio.models import serializers
from . import models

class BookSerializer(serializers.Serializer):
    class Meta:
        model = models.Book
        schema_in = serializers.SchemaModelConfig(fields=["title", "description"])
        schema_out = serializers.SchemaModelConfig(fields=["id", "title", "description"])
        schema_update = serializers.SchemaModelConfig(
            optionals=[("title", str), ("description", str)]
        )

    class CreateValidators:
        @field_validator("title")
        @classmethod
        def validate_title_min_length(cls, v):
            if len(v) < 3:
                raise ValueError("Title must be at least 3 characters")
            return v

    class UpdateValidators:
        @field_validator("title")
        @classmethod
        def validate_title_not_empty(cls, v):
            if v is not None and len(v.strip()) == 0:
                raise ValueError("Title cannot be blank")
            return v

    class ReadValidators:
        @model_validator(mode="after")
        def enrich_output(self):
            return self
```

**Validator class mapping:**

| Schema type | ModelSerializer | Serializer (Meta-driven) |
|---|---|---|
| Create | `CreateSerializer` | `CreateValidators` |
| Update | `UpdateSerializer` | `UpdateValidators` |
| Read | `ReadSerializer` | `ReadValidators` |
| Detail | `DetailSerializer` | `DetailValidators` |

---

## Disable Operations

```python
@api.viewset(Book)
class ReadOnlyBookViewSet(APIViewSet):
    disable = ["update", "delete"]
```

---

## Performance Tips

- Use `queryset_request` classmethod to `select_related` / `prefetch_related`
- Index frequently filtered fields
- Keep pagination enabled for large datasets
- Limit slices (`queryset = queryset[:1000]`) for heavy searches

---

## Contributing

1. Fork the repository
2. Create a feature branch
3. Add tests for your changes
4. Run lint: `ruff check .`
5. Open a Pull Request

---

## Support

If you find this project useful, consider giving it a star or supporting development:

<a href="https://buymeacoffee.com/caspel26"><img src="https://img.shields.io/badge/Buy%20me%20a%20coffee-FFDD00?style=for-the-badge&logo=buy-me-a-coffee&logoColor=black" alt="Buy me a coffee"></a>

---

## License

MIT License. See [LICENSE](LICENSE).
