# 🥷 django-ninja-aio-crud

![Tests](https://github.com/caspel26/django-ninja-aio-crud/actions/workflows/coverage.yml/badge.svg)
[![Quality Gate Status](https://sonarcloud.io/api/project_badges/measure?project=caspel26_django-ninja-aio-crud&metric=alert_status)](https://sonarcloud.io/summary/new_code?id=caspel26_django-ninja-aio-crud)
[![codecov](https://codecov.io/gh/caspel26/django-ninja-aio-crud/graph/badge.svg?token=DZ5WDT3S20)](https://codecov.io/gh/caspel26/django-ninja-aio-crud/)
[![PyPI - Version](https://img.shields.io/pypi/v/django-ninja-aio-crud?color=g&logo=pypi&logoColor=white)](https://pypi.org/project/django-ninja-aio-crud/)
[![PyPI - License](https://img.shields.io/pypi/l/django-ninja-aio-crud)](LICENSE)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)

> Lightweight async CRUD layer on top of **[Django Ninja](https://django-ninja.dev/)** with automatic schema generation, filtering, pagination, auth & Many‑to‑Many management.

---

## ✨ Features

- Async CRUD ViewSets (create, list, retrieve, update, delete)
- Automatic Pydantic schemas from `ModelSerializer` (read/create/update)
- Dynamic query params (runtime schema via `pydantic.create_model`)
- Per-method authentication (`auth`, `get_auth`, `post_auth`, etc.)
- Async pagination (customizable)
- M2M relation endpoints via `M2MRelationSchema` (add/remove/get + filters)
- Reverse relation serialization
- Hook methods (`query_params_handler`, `<related>_query_params_handler`, `custom_actions`, lifecycle hooks)
- ORJSON renderer through `NinjaAIO`
- Clean, minimal integration

---

## 📦 Installation

```bash
pip install django-ninja-aio-crud
```

Add to your project’s dependencies and ensure Django Ninja is installed.

---

## 🚀 Quick Start

models.py
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

views.py
```python
from ninja_aio import NinjaAIO
from ninja_aio.views import APIViewSet
from .models import Book

api = NinjaAIO()

class BookViewSet(APIViewSet):
    model = Book
    api = api

BookViewSet().add_views_to_route()
```

Visit `/docs` → CRUD endpoints ready.

---

## 🔄 Query Filtering

```python
class BookViewSet(APIViewSet):
    model = Book
    api = api
    query_params = {"published": (bool, None), "title": (str, None)}

    async def query_params_handler(self, queryset, filters):
        if filters.get("published") is not None:
            queryset = queryset.filter(published=filters["published"])
        if filters.get("title"):
            queryset = queryset.filter(title__icontains=filters["title"])
        return queryset
```

Request:
```
GET /book/?published=true&title=python
```

---

## 🤝 Many-to-Many Example (with filters)

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

class ArticleViewSet(APIViewSet):
    model = Article
    api = api
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

ArticleViewSet().add_views_to_route()
```

Endpoints:
- `GET /article/{pk}/tag?name=dev`
- `POST /article/{pk}/tag/` body: `{"add":[1,2],"remove":[3]}`

---

## 🔐 Authentication (JWT example)

```python
from ninja_aio.auth import AsyncJwtBearer
from joserfc import jwk
from .models import Book

PUBLIC_KEY = "-----BEGIN PUBLIC KEY----- ..."

class JWTAuth(AsyncJwtBearer):
    jwt_public = jwk.RSAKey.import_key(PUBLIC_KEY)
    jwt_alg = "RS256"
    claims = {"sub": {"essential": True}}

    async def auth_handler(self, request):
        book_id = self.dcd.claims.get("sub")
        return await Book.objects.aget(id=book_id)

class SecureBookViewSet(APIViewSet):
    model = Book
    api = api
    auth = [JWTAuth()]
    get_auth = None  # list/retrieve public
```

---

## 📑 Lifecycle Hooks (ModelSerializer)

Available on every save/delete:
- `on_create_before_save`
- `on_create_after_save`
- `before_save`
- `after_save`
- `on_delete`
- `custom_actions(payload)` (create/update custom field logic)
- `post_create()` (after create commit)

---

## 🧩 Adding Custom Endpoints

```python
class BookViewSet(APIViewSet):
    model = Book
    api = api

    def views(self):
        @self.router.get("/stats/")
        async def stats(request):
            total = await Book.objects.acount()
            return {"total": total}
```

---

## 📄 Pagination

Default: `PageNumberPagination`. Override:

```python
from ninja.pagination import PageNumberPagination

class LargePagination(PageNumberPagination):
    page_size = 50
    max_page_size = 200

class BookViewSet(APIViewSet):
    model = Book
    api = api
    pagination_class = LargePagination
```

---

## 🛠 Project Structure & Docs

Documentation (MkDocs + Material):
```
docs/
  getting_started/
  tutorial/
  api/
    views/
    models/
    authentication.md
    pagination.md
```

Browse full reference:
- APIViewSet: `docs/api/views/api_view_set.md`
- APIView: `docs/api/views/api_view.md`
- ModelSerializer: `docs/api/models/model_serializer.md`
- Authentication: `docs/api/authentication.md`
- Pagination: `docs/api/pagination.md`

---

## 🧪 Tests

Use Django test runner + async ORM patterns. Example async pattern:
```python
obj = await Book.objects.acreate(title="T1", published=True)
count = await Book.objects.acount()
```

---

## 🚫 Disable Operations

```python
class ReadOnlyBookViewSet(APIViewSet):
    model = Book
    api = api
    disable = ["update", "delete"]
```

---

## 📌 Performance Tips

- Use `queryset_request` classmethod to prefetch
- Index frequently filtered fields
- Keep pagination enabled
- Limit slices (`queryset = queryset[:1000]`) for heavy searches

---

## 🤲 Contributing

1. Fork
2. Create branch
3. Add tests
4. Run lint (`ruff check .`)
5. Open PR

---

## ⭐ Support

Star the repo or donate:
- [Buy me a coffee](https://buymeacoffee.com/caspel26)

---

## 📜 License

MIT License. See [LICENSE](LICENSE).

---

## 🔗 Quick Links

| Item | Link |
|------|------|
| PyPI | https://pypi.org/project/django-ninja-aio-crud/ |
| Docs | https://django-ninja-aio.com
| Issues | https://github.com/caspel26/django-ninja-aio-crud/issues |

---
