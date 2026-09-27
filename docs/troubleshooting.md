---
type: guide
title: Troubleshooting
description: Fix the most common problems with schemas, sync and async code, authentication and errors.
---

# Troubleshooting

Find the problem you see below and apply the fix.

## Schemas and relations

### A related object is missing from the response

Add the relation to the `read` (or `detail`) fields:

```python title="blog/models.py"
class Schemas:
    read = SchemaConfig(fields=["id", "title", "category"])
```

The related model must have a `read` schema of its own, which gives the
nested fields. To return only the primary key, add the relation to
`relations_as_id`:

```python
read = SchemaConfig(fields=["id", "title", "category"], relations_as_id=["category"])
```

With a Meta-driven `Serializer`, list the related serializer in
`Meta.relations_serializers`. See [Relations](guides/relations.md).

### `ninja_aio.E003` unknown field

```text
Article.Schemas.read references unknown field 'titel' on Article.
```

Django checks every `Schemas` class at startup. The name is not a model field
or a relation accessor. Fix the spelling, use the `related_name` of a reverse
relation, or declare a value that is not on the model in `customs`. Run
`python manage.py check` to see every problem at once. See
[Schemas](guides/schemas.md).

## Sync and async

### `Synchronous dump requires preloaded fields and relations`

The object has fields skipped with `only()` or `defer()`, or you passed
`strict=True` and a relation of the schema is not loaded. Load the object
without `only()`/`defer()`, or with the relations the schema needs:

```python
article = Article.get(pk=1, optimize_for="detail")
data = Article.model_dump(article, strict=True)
```

Without `strict=True`, missing relations are loaded for you. See
[Serialize objects](guides/dumping.md).

### `SynchronousOnlyOperation`

You ran an ORM query from async code without `await`, often by reading a
relation like `article.category` that is not loaded. Use the async methods,
like `await Article.aget()` and `await Article.amodel_dump()`, or move the code
into a sync viewset with `execution_mode = "sync"`.

### `ImproperlyConfigured: ... is async; rename it to a...`

```text
Article.post_create is async; rename it to apost_create (sync hooks use the plain name).
```

Sync hooks use the plain name and `def`. Async hooks start with `a` and use
`async def`:

```python
async def apost_create(self):
    await notify_editors(self.pk)
```

The same rule applies to viewset hooks like `has_permission` and
`ahas_permission`. See [Sync and async](concepts/sync-and-async.md).

### `ImproperlyConfigured: ... overrides has_permission() but not ahas_permission()`

The viewset mode calls the other version of the hook. Override the hook that
matches `execution_mode`: `ahas_permission` for async viewsets (the default),
`has_permission` for `execution_mode = "sync"`.

## Authentication

### 401 on every request

Check these causes in order:

- The header is `Authorization: Bearer <token>`.
- `auth_handler` returns a truthy value, like the user. `None` or `False`
  means the request is rejected.
- The `iss` and `aud` claims in the token match `claims` on your auth class.
  Tokens made with `encode_jwt()` use `JWT_ISSUER` and `JWT_AUDIENCE`.
- `jwt_public` is the public key of the private key that signed the token, and
  `algorithms` includes its algorithm (default `["RS256"]`).

See [Authentication](guides/authentication.md).

## Errors

### `GET /api/articles/` returns 405

The list path has no trailing slash, while create does:

| Request | Path |
| --- | --- |
| List | `GET /api/articles` |
| Create | `POST /api/articles/` |
| Retrieve | `GET /api/articles/{id}` |
| Update, delete | `PATCH`, `DELETE /api/articles/{id}/` |

Set `NINJA_AIO_APPEND_SLASH = False` in your settings to remove the trailing
slash from every path.

### 422 on PATCH

The body does not match the `update` schema. Check the field types in the
error `loc`. An explicit `null` is only accepted when the type allows it:

```python
update = SchemaConfig(optionals=[("title", str), ("note", str | None)])
```

To clear a field, the model field must be nullable and the type must be
`str | None` (or `int | None`, and so on).

### 409 conflict

```json
{"error": "conflict", "details": "The request violates a database constraint."}
```

The data breaks a database constraint, most often a unique field, like a
`Category` name that already exists. Send a different value, or check it in a
validator to return a clearer `422`. See [Errors](guides/errors.md).

### My `@on_update` hook doesn't fire

A field hook runs only when the client sends that field and its value changes:

```python
from ninja_aio.models.hooks import on_update


class Article(ModelSerializer):
    @on_update("is_published")
    def notify_on_publish(self):
        ...
```

`PATCH {"is_published": true}` on an article that is already published does
not fire it. Use `@on_update` without arguments to run on every update. See
[Hooks](guides/hooks.md).

## Still stuck?

Search the [GitHub issues](https://github.com/caspel26/django-ninja-aio-crud/issues)
or open a new one with your code and the full error message.
