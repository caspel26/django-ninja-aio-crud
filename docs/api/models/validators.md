# :material-check-decagram: Validators on Serializers

Pydantic's `@field_validator` and `@model_validator` can be declared directly on serializer configuration classes. The framework automatically collects these validators and applies them to the generated Pydantic schemas.

**Use validators when:**

- :material-text-box-check: You need to enforce input constraints beyond what Django model fields provide (min length, format, cross-field logic)
- :material-shield-check: You want schema-level validation that runs before data touches the database
- :material-swap-horizontal: You need different validation rules per operation (create vs. update)

---

## :material-file-document-edit: ModelSerializer

Define validators directly on the inner serializer classes (`CreateSerializer`, `ReadSerializer`, `UpdateSerializer`, `DetailSerializer`):

```python
from django.db import models
from ninja_aio.models import ModelSerializer
from pydantic import field_validator, model_validator


class User(ModelSerializer):
    username = models.CharField(max_length=150)
    email = models.EmailField()
    age = models.PositiveIntegerField(default=0)

    class CreateSerializer:
        fields = ["username", "email", "age"]

        @field_validator("username")
        @classmethod
        def validate_username(cls, v):
            if len(v) < 3:
                raise ValueError("Username must be at least 3 characters")
            if not v.isalnum():
                raise ValueError("Username must be alphanumeric")
            return v.lower()

        @field_validator("age")
        @classmethod
        def validate_age(cls, v):
            if v < 13:
                raise ValueError("Must be at least 13 years old")
            return v

    class ReadSerializer:
        fields = ["id", "username", "email"]

    class UpdateSerializer:
        optionals = [("username", str), ("email", str)]

        @field_validator("username")
        @classmethod
        def validate_username_not_blank(cls, v):
            if v is not None and len(v.strip()) == 0:
                raise ValueError("Username cannot be blank")
            return v
```

!!! info "Import location"
    The `@field_validator` and `@model_validator` decorators must be imported inside each inner class, or at the model class level. Python's scoping rules require the decorator to be accessible where it is used.

---

## :material-cube-outline: Serializer (Meta-driven)

For Meta-driven Serializers, define validators on inner classes named `CreateValidators`, `ReadValidators`, `UpdateValidators`, or `DetailValidators`:

```python
from ninja_aio.models import serializers
from pydantic import field_validator, model_validator
from . import models


class UserSerializer(serializers.Serializer):
    class Meta:
        model = models.User
        schema_in = serializers.SchemaModelConfig(
            fields=["username", "email", "age"]
        )
        schema_out = serializers.SchemaModelConfig(
            fields=["id", "username", "email"]
        )
        schema_update = serializers.SchemaModelConfig(
            optionals=[("username", str), ("email", str)]
        )

    class CreateValidators:
        from pydantic import field_validator

        @field_validator("username")
        @classmethod
        def validate_username(cls, v):
            if len(v) < 3:
                raise ValueError("Username must be at least 3 characters")
            return v.lower()

    class UpdateValidators:
        from pydantic import field_validator

        @field_validator("username")
        @classmethod
        def validate_username_not_blank(cls, v):
            if v is not None and len(v.strip()) == 0:
                raise ValueError("Username cannot be blank")
            return v
```

### Validators Class Mapping

| Schema Type      | Validators Class     |
| ---------------- | -------------------- |
| `schema_in`      | `CreateValidators`   |
| `schema_update`  | `UpdateValidators`   |
| `schema_out`     | `ReadValidators`     |
| `schema_detail`  | `DetailValidators`   |

---

## :material-check-all: Supported Validator Types

### `@field_validator`

Validates individual fields. Runs during schema instantiation.

```python
from pydantic import field_validator

class CreateSerializer:
    fields = ["email", "username"]

    @field_validator("email")
    @classmethod
    def validate_email_domain(cls, v):
        if not v.endswith("@company.com"):
            raise ValueError("Only company emails allowed")
        return v
```

**Modes:**

| Mode       | Description                              |
| ---------- | ---------------------------------------- |
| `"after"`  | Runs after Pydantic's type validation (default) |
| `"before"` | Runs before type coercion               |
| `"wrap"`   | Wraps the default validation             |
| `"plain"`  | Replaces default validation entirely     |

```python
@field_validator("age", mode="before")
@classmethod
def coerce_age(cls, v):
    """Accept string ages and convert to int."""
    if isinstance(v, str):
        return int(v)
    return v
```

### `@model_validator`

Validates the entire model after all fields are set. Useful for cross-field validation.

```python
from pydantic import model_validator

class CreateSerializer:
    fields = ["password", "email"]
    customs = [("password_confirm", str)]

    @model_validator(mode="after")
    def check_passwords_match(self):
        if hasattr(self, 'password_confirm') and self.password != self.password_confirm:
            raise ValueError("Passwords do not match")
        return self
```

**Modes:**

| Mode       | Description                                     |
| ---------- | ----------------------------------------------- |
| `"after"`  | Runs after all field validators (receives model instance) |
| `"before"` | Runs before field validation (receives raw dict) |
| `"wrap"`   | Wraps the entire validation process              |

---

## :material-swap-horizontal: Different Validators per Operation

A key advantage is applying different validation rules per operation. Create might enforce stricter rules while update allows partial changes:

```python
class Article(ModelSerializer):
    title = models.CharField(max_length=200)
    content = models.TextField()
    status = models.CharField(max_length=20, default="draft")

    class CreateSerializer:
        fields = ["title", "content"]

        @field_validator("title")
        @classmethod
        def validate_title(cls, v):
            if len(v) < 10:
                raise ValueError("Title must be at least 10 characters")
            return v

        @field_validator("content")
        @classmethod
        def validate_content(cls, v):
            if len(v) < 50:
                raise ValueError("Content must be at least 50 characters")
            return v

    class UpdateSerializer:
        optionals = [("title", str), ("content", str), ("status", str)]

        @field_validator("status")
        @classmethod
        def validate_status_transition(cls, v):
            allowed = {"draft", "review", "published", "archived"}
            if v not in allowed:
                raise ValueError(f"Status must be one of: {', '.join(allowed)}")
            return v
```

---

## :material-lightning-bolt: How It Works

Validators are processed during schema generation:

1. When `generate_create_s()`, `generate_read_s()`, etc. are called, the framework collects any `PydanticDescriptorProxy` instances (created by `@field_validator` / `@model_validator`) from the corresponding configuration class
2. After `ninja.orm.create_schema()` generates the base Pydantic schema, a subclass is created with the validators attached
3. Pydantic discovers the validators during class creation and registers them normally

This means validators behave exactly as they would on a regular Pydantic model — including error formatting, mode handling, and validator ordering.

---

## :material-alert-circle: Error Handling

Validation errors are automatically caught and returned as structured API responses with status code **422**:

```json
{
  "detail": [
    {
      "type": "value_error",
      "loc": ["body", "username"],
      "msg": "Value error, Username must be at least 3 characters"
    }
  ]
}
```

No additional error handling configuration is needed.

---

## :material-code-braces: Complete Example

```python
from django.db import models
from ninja_aio.models import ModelSerializer
from pydantic import field_validator, model_validator


class Product(ModelSerializer):
    name = models.CharField(max_length=200)
    sku = models.CharField(max_length=50, unique=True)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    stock = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class CreateSerializer:
        fields = ["name", "sku", "price", "stock"]

        @field_validator("sku")
        @classmethod
        def validate_sku_format(cls, v):
            if not v.startswith("PRD-"):
                raise ValueError("SKU must start with 'PRD-'")
            return v.upper()

        @field_validator("price")
        @classmethod
        def validate_price_positive(cls, v):
            if v <= 0:
                raise ValueError("Price must be greater than zero")
            return v

    class ReadSerializer:
        fields = ["id", "name", "sku", "price", "stock", "is_active"]
        customs = [
            ("in_stock", bool, lambda obj: obj.stock > 0),
        ]

    class UpdateSerializer:
        optionals = [
            ("name", str),
            ("price", float),
            ("stock", int),
            ("is_active", bool),
        ]
        excludes = ["sku"]  # SKU cannot be changed

        @field_validator("price")
        @classmethod
        def validate_price_positive(cls, v):
            if v is not None and v <= 0:
                raise ValueError("Price must be greater than zero")
            return v

        @model_validator(mode="after")
        def validate_stock_active_consistency(self):
            """Cannot activate a product with zero stock."""
            if (
                getattr(self, "is_active", None) is True
                and getattr(self, "stock", None) == 0
            ):
                raise ValueError("Cannot activate a product with zero stock")
            return self
```

---

## :material-compass: See Also

<div class="grid cards" markdown>

- :material-file-document-edit: **Model Serializer** — Base class approach with auto-binding

    [:octicons-arrow-right-24: Model Serializer](model_serializer.md)

- :material-cube-outline: **Serializer (Meta-driven)** — External serializer for vanilla models

    [:octicons-arrow-right-24: Serializer](serializers.md)

- :material-view-grid: **APIViewSet** — Auto-generated CRUD endpoints

    [:octicons-arrow-right-24: APIViewSet](../views/api_view_set.md)

</div>
