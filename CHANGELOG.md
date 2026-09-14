# 📋 Release Notes

## 🏷️ [v2.35.0] - 2026-09-14

---

### ✨ New Features

#### 🌳 Nested Creation
> `ninja_aio/models/serializers.py`, `ninja_aio/models/utils.py`

Declare owned reverse-FK children with `CreateSerializer.nested` to create a parent and its children in one request. The generated child input schema excludes the parent FK automatically; persistence injects the newly created parent.

```python
from django.db import models
from ninja_aio.models import ModelSerializer

class OrderItem(ModelSerializer):
    order = models.ForeignKey(
        "Order", on_delete=models.CASCADE, related_name="items"
    )
    quantity = models.PositiveIntegerField()

    class CreateSerializer:
        fields = ["order", "quantity"]

class Order(ModelSerializer):
    reference = models.CharField(max_length=100)

    class CreateSerializer:
        fields = ["reference"]
        nested = {"items": OrderItem}
```

The parent's create input accepts:

```json
{"reference": "ORD-001", "items": [{"quantity": 2}, {"quantity": 1}]}
```

Child validators, model configuration, custom input fields, and lifecycle hooks are preserved. Omitted child lists default to independent empty lists; grandchildren are supported. Each owned graph is transactional: validation, persistence, or hook failures roll back its parent and children, including direct utility calls and per-parent isolation during bulk creation.

**Scope:** create-only, `ModelSerializer` reverse-FK relations on one database. Nested updates, deletes, and cyclic configurations are unsupported. Child ViewSet permissions are not invoked: the parent endpoint authorizes the operation, while normal request-scoped FK resolution still applies. External hook side effects cannot be rolled back; defer them with `transaction.on_commit` when appropriate.

---

#### 🛠️ Automatic Admin Relations
> `ninja_aio/admin.py`

`register_admin` and `model_admin_factory` now generate relation-aware admin configuration without hand-written inline classes.

| 🔗 Relation | 🛠️ Generated configuration |
|---|---|
| Reverse ForeignKey | `TabularInline` |
| Reverse one-to-one | `StackedInline` |
| Editable forward M2M with an automatic through table | `filter_horizontal` |
| Reverse M2M or custom-through M2M widgets | Not generated automatically |

Inlines set an explicit `fk_name`, handling multiple FKs from the same child model. Editable fields prefer `UpdateSerializer`, then `CreateSerializer`; parent FKs, primary keys, non-editable fields, and synthetic fields are excluded. Plain Django children use Django's normal editable-field defaults.

Explicit overrides remain authoritative:

```python
from ninja_aio import register_admin
from ninja_aio.admin import model_admin_factory

register_admin(Order)
CustomOrderAdmin = model_admin_factory(
    Order, inlines=(), filter_horizontal=(), list_per_page=50
)
```

---

### 🔧 Improvements

#### ⏳ Startup-Safe Admin Discovery
> `ninja_aio/admin.py`

Field and relation discovery is deferred until Django's model registry is ready, so model decorators discover children declared later and reverse relations are not misclassified as list cells or read-only form fields.

#### 🔄 Performance CI Maintenance
> `.github/workflows/performance.yml`

Updated the pinned baseline artifact download action from v21 to v24.

---

### 📚 Documentation

Updated the README and serializer/admin API guides with nested creation, transaction and authorization boundaries, generated relation configuration, and override examples; marked both features complete in the roadmap.

---

### 🎯 Summary

Two declarative features reduce boilerplate for owned-object creation and relation editing in Django Admin. The full suite passes with 1,153 tests, including 45 new tests; all three changed runtime modules retain 100% coverage, and the five-run baseline comparison detected no significant performance regressions.

**Key benefits:**

- 🌳 Create parents, children, and grandchildren atomically.
- ✅ Preserve child validation and hooks without accepting client-supplied parent FKs.
- 🛠️ Edit related objects through generated, overridable admin inlines.
- ⏳ Discover relations safely during Django application startup.
