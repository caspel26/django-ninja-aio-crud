# 📋 Release Notes

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
