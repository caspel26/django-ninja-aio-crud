---
type: migration
title: Breaking changes
description: Behavior that changes in 3.0 without a deprecation warning, and what to do.
---

# Breaking changes

Most version 2 code keeps working in 3.0 and shows a `DeprecationWarning`
instead, see [deprecations](deprecations.md). The changes on this page take
effect immediately. Check each one against your project.

## Sync methods keep the plain name

In version 2 some serializer methods were async under a plain name. In 3.0 the
plain name is sync and the async version starts with `a`.

| 2.x (async) | 3.0 sync | 3.0 async |
| --- | --- | --- |
| `await serializer.create(data)` | `ArticleSerializer.create(data)` | `await ArticleSerializer.acreate(data)` |
| `await serializer.update(instance, data)` | `ArticleSerializer.update(instance, data)` | `await ArticleSerializer.aupdate(instance, data)` |
| `await serializer.model_dump(instance)` | `ArticleSerializer.model_dump(instance)` | `await ArticleSerializer.amodel_dump(instance)` |
| `create_view()`, `list_view()`, … | register sync endpoints | `acreate_view()`, `alist_view()`, … |
| `await util.get_object(...)` | `Article.get(pk)` | `await Article.aget(pk)` |
| `await util.get_objects(...)` | `Article.get_queryset()` | `await Article.aget_queryset()` |

Add `await` and the `a` prefix in async code. Binding an instance with
`Serializer(instance=...)` is no longer used for CRUD: pass the object to the
method.

## Async hooks start with `a`

An `async def` under a sync hook name fails at startup:

```text
ImproperlyConfigured: Article.post_create is async; rename it to apost_create (sync hooks use the plain name).
```

Rename `post_create`, `custom_actions`, `queryset_request`,
`on_before_operation`, `on_before_object_operation`, `query_params_handler`,
`has_permission` and `has_object_permission` to their `a` versions when they are
`async def`. See [recipes](recipes.md#rename-async-hooks).

## Updates only change the fields you send

`PATCH` and `update()` only touch the fields present in the request. An explicit
`null` is saved when the update schema allows it, for example
`optionals=[("note", str | None)]`. In 2.x, `null` values were ignored.

`@on_update("field")` hooks run only when that field was sent and changed.

Optional fields that the client leaves out are no longer passed to the model,
even when the schema also has custom fields.

## Hooks run the same way everywhere

Hooks now run in the same order in sync and async code, for both serializer
styles. See [request lifecycle](../concepts/lifecycle.md). For `Serializer`
classes this means:

- `before_save`, `after_save`, `on_create_before_save` and `on_create_after_save` also run for sync calls.
- `on_delete(instance)` now runs after a delete.
- `@on_create` hooks run after `post_create`.

## Writes with hooks run in a transaction

`create()`, `update()` and `destroy()` now run in a transaction when a hook runs
after the write, so an exception in `post_create` also removes the new row. See
[transactions](../concepts/transactions.md).

## Authentication and permissions

| Change | What to check |
| --- | --- |
| `PUT` actions follow `patch_auth`, `HEAD` follows `get_auth`. In 2.x a `PUT` action without its own `auth` was public. | Actions that were meant to be public need `auth=None`. |
| Many-to-many endpoints use the viewset auth (`get_auth` for reads, `patch_auth` for changes) unless `m2m_auth` or the relation `auth` is set. In 2.x they fell back to the API auth. | Clients of relation endpoints on protected viewsets now need a token. |
| `M2MRelationSchema(auth=None)` makes that relation public. In 2.x `None` meant "use the default". | Remove `auth=None` if you meant the default. |
| `AuthError` returns `401` by default instead of `400`. | Client code that checks the status. |
| Your own `aon_before_object_operation` / `on_before_object_operation` runs on retrieve, update and delete. In 2.x it only ran there with the permission or soft delete mixin. | Hooks that should only run for `@on` actions need to check `operation`. |
| `@action(detail=True)` runs the object checks (`has_object_permission`, soft delete, your object hook) before the method when the viewset has them. A missing object returns `404`. | Detail actions that must work on objects the user can't see. |
| Bulk update and bulk delete check every object with the operation `update` or `delete`. Refused objects are listed in `errors`. | Permission rules that should allow bulk changes. |
| Many-to-many endpoints check the parent object: `GET` with the operation `retrieve`, add and remove with `update`. `has_object_permission`, soft delete and your object hook apply. In 2.x they were skipped. | Permission rules for relation endpoints. |
| JWT auth classes without `claims` raise `ImproperlyConfigured` when created. In 2.x they failed on the first request. | Set `claims`, or `claims = {}` to check none. |

## Errors

A database constraint error, such as a duplicate unique value, returns `409`:

```json
{"error": "conflict", "details": "The request violates a database constraint."}
```

In 2.x it was an unhandled `500`. Your own handler for `IntegrityError` still
takes precedence.

A lookup for one object that matches more than one row raises
`MultipleObjectsError` (`400`). In 2.x it was an unhandled `500`. When a join
in `queryset_request` only repeats the same row, you now get the object.

## Soft delete

With `SoftDeleteViewSetMixin`:

- `@on` actions on a soft-deleted row return `404`.
- Restore and hard delete call `has_object_permission` with the operations `restore` and `hard_delete`.
- Bulk delete reports ids that were already deleted as errors.

## Bulk delete runs delete hooks

The HTTP bulk delete endpoint deletes objects one by one, so `on_delete` and
`@on_delete` hooks run for each object. The request and response bodies are the
same as in 2.x.

## Views and filters

| Change | What to check |
| --- | --- |
| On viewsets, `tags=` passed to `@api.viewset` or the constructor wins over `router_tags`, like on `APIView`. In 2.x `router_tags` won. | Viewsets that set both. |
| An `APIView` without any tag has no tag in OpenAPI. In 2.x it had an empty `""` tag. | Tools that group endpoints by tag. |
| `FieldSelectionViewSetMixin._fields_param` is now `fields_param`, and it is never passed to `query_params_handler`. | Subclasses that renamed the parameter. |
| Combining two date filter mixins with different comparisons raises `ImproperlyConfigured`. In 2.x only the first one applied. | Use one date mixin and parameters like `created_at__gte`. |
| MCP tools of viewsets that share a model start with their URL prefix, like `sync_articles_article_list`. | MCP clients that call those tools by name. |
| When the same view is mounted twice, the repeated OpenAPI `operationId`s get a `_2`, `_3`... suffix. In 2.x they were duplicated. | Generated clients that use those ids. |

Foreign keys in request bodies are accepted as `category` or `category_id` in
both create and update. Code that sent the 2.x names keeps working.

## Admin

- Fields listed in update `optionals` are editable in the generated admin. In 2.x they were read-only.
- `register_admin` raises `TypeError` for classes that are not a `ModelSerializer`.

## See also

- [Migration overview](index.md)
- [Deprecations](deprecations.md)
- [Recipes](recipes.md)
