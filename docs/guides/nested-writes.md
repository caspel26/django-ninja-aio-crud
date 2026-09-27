---
type: guide
title: Nested writes
description: Create an object and its related children in one request.
---

# Nested writes

A nested write creates an object and its children in one request. This page
shows how to enable it, what the client sends, and what happens when
something fails.

## Enable nested writes

Add `nested` to the `create` schema of the parent. The key is the
`related_name` of the child's foreign key, the value is the child model:

```python title="blog/models.py" hl_lines="21"
class Article(ModelSerializer):
    # fields as before
    category = models.ForeignKey(
        "Category", on_delete=models.PROTECT, related_name="articles"
    )

    class Schemas:
        create = SchemaConfig(
            fields=["title", "body", "category"],
            optionals=[("is_published", bool)],
        )
        read = SchemaConfig(fields=["id", "title", "category", "created_at"])


class Category(ModelSerializer):
    name = models.CharField(max_length=100, unique=True)

    class Schemas:
        create = SchemaConfig(
            fields=["name"],
            nested={"articles": Article},
        )
        read = SchemaConfig(fields=["id", "name", "articles"])
```

Define the child first so the parent can refer to it. The child's foreign key
uses the string `"Category"`.

## Send the children

Send the children as a list under the relation name:

```bash
curl -X POST localhost:8000/api/categories/ \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Django",
    "articles": [
      {"title": "Hello", "body": "..."},
      {"title": "Models", "body": "...", "is_published": true}
    ]
  }'
```

The response is `201` with the category and its new articles:

```json
{
  "id": 1,
  "name": "Django",
  "articles": [
    {"id": 1, "title": "Hello", "created_at": "2026-09-26T10:00:00Z"},
    {"id": 2, "title": "Models", "created_at": "2026-09-26T10:00:00Z"}
  ]
}
```

Each child accepts the fields of the child's `create` schema, except the
foreign key to the parent. The framework sets `category` for you, and a
`category_id` sent inside a child is ignored. Leave out `articles`, or send
`[]`, to create the category alone.

The child schema keeps everything else from the child's `create` schema:

- Other foreign keys, sent as `<name>_id`.
- `optionals` and `customs`.
- Validators from `CreateValidators` and the `model_config`.
- The child's own `nested` relations, so a child can have children too.

The child's hooks, like `post_create` and `@on_create`, run for each child.

## What happens when something fails

The parent and all its children are saved in one transaction. If anything
fails, nothing is saved.

| Problem | Status |
| --- | --- |
| A child doesn't match its schema, like a missing `title` | `422` |
| The parent or a child sends a related id that doesn't exist | `404` |

A `422` points at the child that failed:

```json
{
  "detail": [
    {"type": "missing", "loc": ["body", "data", "articles", 0, "title"], "msg": "Field required"}
  ]
}
```

Database errors, like a duplicate unique value, and exceptions raised in hooks
also undo the whole request.

With [bulk create](bulk-operations.md), each item is saved with its children
on its own. A failed item doesn't undo the others.

## Limits

- `nested` works on the `create` schema of a `ModelSerializer` only. The
  `update` schema never accepts children, and a `Serializer` doesn't support
  nested writes.
- Each key must be a reverse foreign key, and the value must be the
  `ModelSerializer` of that relation. Many-to-many and one-to-one relations
  are not supported.
- A model can't nest itself, directly or through its children.
- The parent and its children must be saved in the same database.

Setting `nested` on another kind or on a `Serializer` is reported by
`python manage.py check` as `ninja_aio.E005`. An unknown name is reported as
`ninja_aio.E003`. See [Schemas](schemas.md).

To link existing objects in a many-to-many field instead, see
[Relations](relations.md).

## See also

- [Relations](relations.md)
- [Schemas](schemas.md)
- [Validation](validation.md)
- [Hooks](hooks.md)
- [Bulk operations](bulk-operations.md)
