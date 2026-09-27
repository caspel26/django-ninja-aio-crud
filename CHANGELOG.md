# 📋 Release Notes

## 🏷️ [v3.0.0] - 2026-09-27

Version 3 introduces explicit sync and async APIs, consistent serializer hooks,
and safer writes. It supports Python 3.10–3.14, Django 5.2–6.0, and Django Ninja
1.7.x. Review the [migration guide](docs/migration/index.md) before upgrading.

### APIs and schemas

- Plain serializer methods are synchronous; async methods use the `a` prefix,
  such as `acreate`, `aupdate`, and `amodel_dump`. Both `ModelSerializer` and
  standalone `Serializer` expose class-based CRUD methods.
- Viewsets support `execution_mode = "sync"` alongside the default async mode.
- Declare create, update, read, and detail schemas using `Schemas` and
  `SchemaConfig`. Schema attributes are generated lazily and cached.
- Foreign-key input accepts both the field name and its `_id` spelling while
  preserving custom aliases. Relation loading avoids unnecessary queries and
  reuses populated relation caches.
- Public APIs include type information and the `py.typed` marker.

### Writes, hooks, and errors

- PATCH changes only supplied fields. Explicit `null` is saved when the input
  schema permits it; omitted fields keep their existing values.
- Sync and async operations run equivalent hooks. Async hooks use the `a`
  prefix, and incompatible hook declarations fail during startup checks.
- Writes with post-write hooks and nested writes roll back on failure. Bulk
  operations protect each item independently and return typed success/error
  results; failed items do not discard successful items.
- Bulk delete invokes delete hooks for each object. Field update hooks run only
  when a supplied field changes.
- Database constraint failures return `409`; ambiguous object lookups return
  `400`. Authentication failures return `401` by default.

### Authentication, permissions, and integrations

- JWT authentication keeps decoded claims local to each request. Sync endpoints
  can use async authentication handlers.
- Detail actions, bulk updates/deletes, and many-to-many operations enforce
  object permissions. Soft-delete visibility and restore/delete permissions
  apply consistently across endpoint styles.
- Repeated API mounts receive unique OpenAPI operation IDs and distinct MCP tool
  names derived from their routes.
- Generated admin forms include optional update fields.

### Performance

- Simple async bulk creates use a single sync bridge when model customizations
  permit it, retaining per-item transactions. Models with async hooks or custom
  relation handling continue through the async path.
- Foreign-key input schemas are built in one pass. Compared with the previous
  v3 implementation, the recorded benchmark runs measured roughly 39–42% less
  cold FK schema time and 64–77% less simple bulk-create time across SQLite and
  PostgreSQL. These are microbenchmarks, not production latency guarantees; see
  [the benchmark methodology](benchmarks/README.md).

### Documentation and examples

- Rebuilt documentation includes API references, executable examples,
  migration recipes, breaking changes, and deprecation guidance.
- The runnable library app mounts the same domain through sync and async APIs,
  with authentication, permissions, relations, hooks, bulk operations, admin,
  background tasks, and MCP. Its 63 tests cover both request parity and complete
  user journeys, including rollback and concurrent user isolation.
- A real blog migration is documented with a reproducible patch.
- CI covers supported Python/Django combinations, PostgreSQL, browser checks,
  and hash-verified dependency locks. Publishing uses a verified Flit tool pair.

### Migration

Some async methods previously used plain names: change awaited calls to their
`a` counterparts. Rename async hooks similarly, and review changed PATCH,
authentication, permission, and error behavior. Existing compatibility aliases
emit `DeprecationWarning` and are scheduled for removal in version 4.

See [breaking changes](docs/migration/breaking-changes.md),
[deprecations](docs/migration/deprecations.md), and
[migration recipes](docs/migration/recipes.md).

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
