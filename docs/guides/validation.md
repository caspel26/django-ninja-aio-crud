---
type: guide
title: Validation
description: Check input and adjust output with Pydantic validators on your serializer.
---

# Validation

Add Pydantic validators to check what clients send and to adjust what they
get back. This page shows where validators go and what an invalid request
returns.

## Add a field validator

Put validators in a `CreateValidators` class on your model:

```python title="blog/models.py"
from django.db import models
from pydantic import field_validator
from ninja_aio import ModelSerializer, SchemaConfig


class Article(ModelSerializer):
    title = models.CharField(max_length=200)
    body = models.TextField()
    # other fields

    class Schemas:
        create = SchemaConfig(fields=["title", "body", "category"])
        update = SchemaConfig(optionals=[("title", str), ("body", str)])
        read = SchemaConfig(fields=["id", "title", "category"])

    class CreateValidators:
        @field_validator("title")
        @classmethod
        def title_long_enough(cls, value: str) -> str:
            if len(value) < 3:
                raise ValueError("Title must be at least 3 characters")
            return value
```

A validator runs on the schema of its kind:

| Class | Runs on |
| --- | --- |
| `CreateValidators` | The `create` schema: the body of `POST` |
| `UpdateValidators` | The `update` schema: the body of `PATCH` |
| `ReadValidators` | The `read` schema: list items and create/update responses |
| `DetailValidators` | The `detail` schema: the retrieve response |

The value you return is the value that is saved or returned. Use this to
clean up input, like `return value.strip()`.

## Check several fields together

Use `model_validator` when a rule needs more than one field:

```python
from pydantic import model_validator


class Article(ModelSerializer):
    # fields and Schemas as above

    class CreateValidators:
        @model_validator(mode="after")
        def body_differs_from_title(self):
            if self.body == self.title:
                raise ValueError("Body must differ from the title")
            return self
```

With `mode="after"`, `self` is the validated schema, so you read the fields
as attributes.

## Validate updates

In `update`, fields declared in `optionals` are `None` when the client leaves
them out. Let `None` through:

```python
class Article(ModelSerializer):
    # fields and Schemas as above

    class UpdateValidators:
        @field_validator("title")
        @classmethod
        def title_not_blank(cls, value: str | None) -> str | None:
            if value is not None and not value.strip():
                raise ValueError("Title cannot be blank")
            return value
```

## Adjust the output

`ReadValidators` and `DetailValidators` change what the API returns:

```python
class Article(ModelSerializer):
    # fields and Schemas as above

    class ReadValidators:
        @field_validator("title")
        @classmethod
        def title_case(cls, value: str) -> str:
            return value.title()
```

!!! note

    `ReadValidators` do not run on the retrieve response, even when you omit
    `detail`. Add the same validator to `DetailValidators` to apply it there.

## What the client gets

An invalid request body returns `422`:

```json
{
  "detail": [
    {
      "type": "value_error",
      "loc": ["body", "data", "title"],
      "msg": "Value error, Title must be at least 3 characters",
      "ctx": {"error": "Title must be at least 3 characters"}
    }
  ]
}
```

`loc` ends with the field name. For a `model_validator`, `loc` is
`["body", "data"]`.

## Validate in Python

The same validators run when you call the serializer in your own code.
`Article.create()` raises `OperationValidationError` with status `400`:

```python
from ninja_aio.exceptions import OperationValidationError

try:
    Article.create({"title": "Hi", "body": "...", "category_id": 1})
except OperationValidationError as exc:
    print(exc.field_errors)
    # {"title": ["Value error, Title must be at least 3 characters"]}
```

## Use validators on a Serializer

The validator classes work the same way on a `Serializer`. Put them next to
`Meta` and `Schemas`:

```python title="blog/serializers.py"
from pydantic import field_validator
from ninja_aio import Serializer, SchemaConfig

from .models import Article


class ArticleSerializer(Serializer[Article]):
    class Meta:
        model = Article

    class Schemas:
        create = SchemaConfig(fields=["title", "body", "category"])
        read = SchemaConfig(fields=["id", "title", "category"])

    class CreateValidators:
        @field_validator("title")
        @classmethod
        def title_long_enough(cls, value: str) -> str:
            if len(value) < 3:
                raise ValueError("Title must be at least 3 characters")
            return value
```

## See also

- [Schemas](schemas.md)
- [Errors](errors.md)
- [Hooks](hooks.md)
- [Define the model](../tutorial/model.md)
