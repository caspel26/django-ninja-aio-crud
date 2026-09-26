---
type: concept
title: Transactions
description: When your changes are saved together and when they are rolled back.
---

# Transactions

A transaction saves several database changes together: either all of them are
kept, or none.

## Endpoints

Every generated endpoint that writes data runs in a transaction: create,
update, delete, restore and hard delete. If anything fails, for example a
hook raises an exception, nothing from that request is saved.

```python
class Article(ModelSerializer):
    ...

    def post_create(self):
        if not self.title.strip():
            raise SerializeError({"title": "cannot be blank"})
```

A `POST` that fails in `post_create` returns `400` and leaves no article in the
database.

## Python methods

`Article.create()`, `update()` and `destroy()` (and their async versions) run
in a transaction when there is work after the write that can fail:

- `post_create`, `custom_actions`, `after_save`, `on_create_after_save` or `on_delete`
- `@on_create`, `@on_update` or `@on_delete` hooks
- nested writes

A model without any of these saves with a single query, which is already atomic.

To group several calls, wrap them yourself:

=== "Sync"

    ```python
    from django.db import transaction

    with transaction.atomic():
        category = Category.create({"name": "Django"})
        Article.create({"title": "Hello", "body": "...", "category_id": category.pk})
    ```

=== "Async"

    ```python
    from ninja_aio.decorators import aatomic


    @aatomic
    async def publish_first_article():
        category = await Category.acreate({"name": "Django"})
        await Article.acreate({"title": "Hello", "body": "...", "category_id": category.pk})
    ```

## Bulk operations

Each item of a bulk operation runs in its own transaction. A failing item is
rolled back and reported in the response, the other items are saved. See
[bulk operations](../guides/bulk-operations.md).

## Work after the commit

Hooks run inside the transaction. To send an email or call another service only
when the data is really saved, use Django's `transaction.on_commit()`:

```python
from django.db import transaction


class Article(ModelSerializer):
    def post_create(self):
        transaction.on_commit(lambda: notify_editors(self.pk))
```

## See also

- [Hooks](../guides/hooks.md)
- [Nested writes](../guides/nested-writes.md)
- [Use the CRUD API from Python](../guides/python-crud.md)
