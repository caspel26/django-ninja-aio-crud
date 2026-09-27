# 📋 Release Notes

## 🏷️ [v3.0.0] - 2026-09-27

---

### ✨ New Features

#### 🔄 Explicit Sync and Async APIs
> `ninja_aio/models/serializers.py`, `ninja_aio/views/api.py`, `ninja_aio/views/api_view.py`

Version 3 gives `ModelSerializer` and standalone `Serializer` the same class-based CRUD facade. Plain method names run synchronously; methods prefixed with `a` run asynchronously. Viewsets can serve either execution mode while retaining the same response contracts and hooks:

```python
@api.viewset(model=Article)
class ArticleViewSet(APIViewSet):
    execution_mode = "sync"  # async remains the default
```

Use `Article.create(data)` in sync code and `await Article.acreate(data)` in async code. The same naming applies to updates, serialization, lookups, and bulk operations. This supports WSGI applications, ASGI applications, management commands, and background tasks through one public API.

#### 🧩 Declarative Schemas
> `ninja_aio/models/config.py`, `ninja_aio/models/serializers.py`, `ninja_aio/models/checks.py`

The `Schemas` declaration and `SchemaConfig` replace scattered inner serializer declarations. Create, update, read, and detail schemas are generated lazily, cached, and validated by Django's system checks:

```python
from django.db import models
from ninja_aio import ModelSerializer, SchemaConfig

class Article(ModelSerializer):
    title = models.CharField(max_length=200)

    class Schemas:
        create = SchemaConfig(fields=["title"])
        update = SchemaConfig(optionals=[("title", str)])
        read = SchemaConfig(fields=["id", "title"])
```

Foreign-key inputs accept both the field name and its `_id` spelling while preserving custom aliases. The public package also ships type information and a `py.typed` marker.

#### 📦 Structured Bulk Results
> `ninja_aio/models/utils.py`, `ninja_aio/types.py`

Bulk writes expose typed success/error results and protect each item independently. If an item's hook fails after writing to the database, that item's row and hook writes roll back; other successful items remain saved. Bulk delete runs delete hooks for every object, and bulk update/delete apply object permissions to each item.

#### 🤖 API Mounts, MCP, and Admin
> `ninja_aio/mcp/`, `ninja_aio/admin.py`, `ninja_aio/api.py`

Repeated API mounts receive unique OpenAPI operation IDs and distinct MCP tool names derived from their routes. Generated admin forms include optional update fields, making the serializer's editable field contract available in Django Admin too.

---

### 🐛 Bug Fixes and Hardening

#### 🛡️ Transactions and Hook Parity
> `ninja_aio/models/hooks.py`, `ninja_aio/models/utils.py`

Sync and async operations now run equivalent hooks in a consistent order. Writes with post-write hooks and nested writes roll back when a hook fails. Field update hooks run only when the client supplies a field and its value changes. Async hooks use the `a` prefix; incompatible declarations fail during startup checks.

#### 📝 PATCH and Error Handling
> `ninja_aio/models/serializers.py`, `ninja_aio/exceptions.py`

PATCH changes only supplied fields, so omitted fields retain their values. An explicit `null` is saved when the update schema permits it. Database constraint failures return `409`, ambiguous object lookups return `400`, and authentication failures return `401` by default.

#### 🔐 Authentication and Object Permissions
> `ninja_aio/auth.py`, `ninja_aio/views/mixins.py`, `ninja_aio/helpers/api.py`

JWT authentication keeps decoded claims local to each request, including concurrent requests from different users. Sync endpoints can use async authentication handlers. Detail actions, bulk operations, and many-to-many endpoints enforce object permissions; soft-delete visibility and restore/delete permissions apply consistently across endpoint styles.

---

### ⚡ Performance Improvements
> `ninja_aio/models/utils.py`, `ninja_aio/models/serializers.py`, `ninja_aio/models/transformations.py`

Eligible simple async bulk creates use a single sync bridge while retaining per-item transactions. Models with async hooks or custom relation handling continue through the async path. Relation serialization reuses populated caches, and foreign-key input schemas are built in one pass.

Compared with the previous v3 implementation, recorded benchmark runs measured roughly **39–42% less cold FK schema time** and **64–77% less simple bulk-create time** across SQLite and PostgreSQL. These are microbenchmarks, not production latency guarantees; see the [benchmark methodology](benchmarks/README.md).

---

### 📚 Documentation and Examples

The rebuilt docs cover sync/async APIs, schemas, hooks, transactions, permissions, and integrations, with executable examples and migration recipes. Older documentation versions retain their historical content and use the new site style.

The runnable library app mounts the same domain through sync and async APIs, including authentication, permissions, relations, bulk writes, Admin, background tasks, and MCP. Its **63 tests** cover request parity, complete user journeys, rollback, concurrent user isolation, and query scaling. A real blog migration is documented with a reproducible patch.

CI covers Python/Django combinations, PostgreSQL, browser checks, and hash-verified dependency locks. Publishing uses a verified Flit CLI/backend pair.

---

### ⚠️ Breaking Changes and Migration

This is a major release. Some async methods previously used plain names: change awaited calls to their `a` counterparts, and rename async hooks similarly. Review the changed PATCH, authentication, permission, and error behavior before upgrading.

Compatibility aliases emit `DeprecationWarning` and are scheduled for removal in version 4. Python **3.10–3.14**, Django **5.2–6.0**, and Django Ninja **1.7.x** are supported.

See the [migration guide](docs/migration/index.md), [breaking changes](docs/migration/breaking-changes.md), [deprecations](docs/migration/deprecations.md), and [migration recipes](docs/migration/recipes.md).

---

### 🎯 Summary

Version 3 makes sync and async APIs explicit, unifies schema declarations and hook behavior, and strengthens transaction and permission handling. Migration guidance and a tested example application accompany the public API changes.

**Key benefits:**

- 🔄 Matching sync and async APIs across viewsets, serializers, commands, and tasks.
- 🧩 Lazy, cached schemas with clear declarations and foreign-key aliases.
- 🛡️ Transaction-protected hooks and per-item bulk rollback.
- 🔐 Consistent object permissions and request-local JWT state.
- ⚡ Faster eligible bulk writes and cold foreign-key schema generation.
- 📚 Rebuilt documentation, migration recipes, and a runnable application.

## 🏷️ [v2.36.0] - 2026-09-21

---

### ✨ New Features

#### 🧩 Configurable Error Schema
> `ninja_aio/views/api.py`, `ninja_aio/views/mixins.py`, `ninja_aio/helpers/api.py`

Every generated CRUD/M2M endpoint documents its error responses with a fixed `GenericMessageSchema` for the codes in `error_codes` (400/401/403/404), with no override point — a project with its own error contract had to hand-redeclare `response=` on every single view just to fix the OpenAPI schema.

`API.error_schema` (default `GenericMessageSchema`, fully backward compatible) replaces that hardcoding: every `self.error_codes: GenericMessageSchema` declaration across `views/api.py`, `views/mixins.py`, and the M2M helpers in `helpers/api.py` now reads `self.error_codes: self.error_schema`. Override it once on a shared base class and every generated endpoint documents your own error contract project-wide:

```python
from ninja import Schema
from ninja_aio.views import APIViewSet

class ErrorResponse(Schema):
    error_id: str
    error_description: str

class MyBaseViewSet(APIViewSet):
    error_schema = ErrorResponse  # every generated endpoint documents this instead

class BookAPI(MyBaseViewSet):
    model = Book
```

This only changes what the OpenAPI/Swagger schema documents for those status codes — it has no effect on the response your own exception handlers actually produce at runtime.

---

### 📚 Documentation

Expanded the `APIViewSet` "Error Handling" section with the `error_schema` override mechanism and an example, and fixed a pre-existing omission (403 was missing from the listed error codes).

---

### 🎯 Summary

A small, fully backward-compatible extension point closes a real documentation gap: projects with their own error contract can now make generated CRUD/M2M endpoints document it accurately, without redeclaring `response=` by hand on every view. The full suite passes with 1,156 tests, including 3 new tests covering the default schema, subclass overrides across every generated action, and availability on `APIView`.

**Key benefits:**

- 🧩 One attribute, one place, applies to every generated endpoint.
- 🔄 Fully backward compatible — default behavior is unchanged.
- 📄 Swagger/OpenAPI finally reflects a project's real error contract instead of a generic placeholder.
