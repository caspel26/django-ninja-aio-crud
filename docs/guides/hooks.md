---
type: guide
title: Hooks
description: Run your own code when objects are created, updated, deleted or loaded.
---

# Hooks

Hooks are methods on your serializer that run during create, update, delete
and queries. Use them to fill fields, react to changes or restrict rows.

## Follow the naming rule

Sync hooks use the plain name. Async hooks use the same name with an `a`
prefix:

| Sync | Async |
| --- | --- |
| `def post_create(self)` | `async def apost_create(self)` |
| `def custom_actions(self, payload)` | `async def acustom_actions(self, payload)` |
| `def queryset_request(cls, request)` | `async def aqueryset_request(cls, request)` |

Override one of the two. If you override only one, the other mode calls it for
you.

The save hooks (`before_save`, `after_save`, `on_create_before_save`,
`on_create_after_save`, `on_delete`) are always plain `def`. They also run in
async viewsets.

!!! warning

    A hook with the wrong kind stops your app at import time with
    `ImproperlyConfigured`:

    - `async def post_create` raises `Article.post_create is async; rename it to apost_create (sync hooks use the plain name).`
    - `def apost_create` raises `Article.apost_create must be async.`

## Change the object around a save

```python title="blog/models.py"
from django.utils.text import slugify
from ninja_aio import ModelSerializer


class Article(ModelSerializer):
    ...

    def before_save(self):
        self.slug = slugify(self.title)

    def on_create_after_save(self):
        logger.info("Article %s created", self.pk)
```

| Hook | Runs |
| --- | --- |
| `on_create_before_save` | Before the first save only |
| `before_save` | Before every save |
| `on_create_after_save` | After the first save only |
| `after_save` | After every save |
| `on_delete` | After the object is deleted |

These hooks run on every `save()` and `delete()` call, including your own
code.

## Check if a field changed

`has_changed(field)` compares the value on the object with the value in the
database:

```python
def before_save(self):
    if self.has_changed("is_published") and self.is_published:
        self.published_at = timezone.now()
```

It returns `False` for objects that are not saved yet. In async code, use
`await self.ahas_changed("is_published")`.

## Run code after create

=== "Sync"

    ```python
    class Article(ModelSerializer):
        def post_create(self):
            AuditLog.objects.create(action="create", article=self)
    ```

=== "Async"

    ```python
    class Article(ModelSerializer):
        async def apost_create(self):
            await AuditLog.objects.acreate(action="create", article=self)
    ```

`post_create` runs once, after the first save.

## Handle custom fields

Fields in `customs` are accepted in the request body but not saved to the
model. Read them in `custom_actions`:

=== "Sync"

    ```python title="blog/models.py"
    class Article(ModelSerializer):
        ...

        class Schemas:
            create = SchemaConfig(
                fields=["title", "body", "category"],
                customs=[("notify_editors", bool, False)],
            )

        def custom_actions(self, payload):
            if payload.get("notify_editors"):
                notify_editors(self.pk)
    ```

=== "Async"

    ```python title="blog/models.py"
    class Article(ModelSerializer):
        ...

        class Schemas:
            create = SchemaConfig(
                fields=["title", "body", "category"],
                customs=[("notify_editors", bool, False)],
            )

        async def acustom_actions(self, payload):
            if payload.get("notify_editors"):
                await notify_editors(self.pk)
    ```

`payload` is a dict with the custom fields, like `{"notify_editors": True}`.
It runs on create and update.

## Restrict rows per request

`queryset_request` is a classmethod that builds the base queryset. It is the
only hook that receives the request. It is used by the list, and to load the
object for retrieve, update, delete and `@on` actions:

=== "Sync"

    ```python
    class Article(ModelSerializer):
        @classmethod
        def queryset_request(cls, request):
            user = getattr(request, "auth", None)
            if user and user.is_staff:
                return cls.objects.all()
            return cls.objects.filter(is_published=True)
    ```

=== "Async"

    ```python
    class Article(ModelSerializer):
        @classmethod
        async def aqueryset_request(cls, request):
            user = getattr(request, "auth", None)
            if user and user.is_staff:
                return cls.objects.all()
            return cls.objects.filter(is_published=True)
    ```

`request` is `None` when you call the serializer from Python without passing
`request=`. Rows outside the queryset return `404`.

## React to changes with decorators

Mark any method with `@on_create`, `@on_update` or `@on_delete`:

```python title="blog/models.py"
from ninja_aio.models.hooks import on_create, on_delete, on_update


class Article(ModelSerializer):
    ...

    @on_create
    async def announce(self):
        await send_new_article_email(self.pk)

    @on_update("is_published")
    def published_changed(self):
        cache.delete(f"article:{self.pk}")

    @on_update
    def any_update(self):
        logger.info("Article %s updated", self.pk)

    @on_delete
    def cleanup(self):
        storage.delete(f"covers/{self.pk}.jpg")
```

| Decorator | Runs |
| --- | --- |
| `@on_create` | After an object is created |
| `@on_update` | After every update |
| `@on_update("status")` | After an update that changes `status` |
| `@on_update("status", "views")` | After an update that changes any of the fields |
| `@on_delete` | After an object is deleted |

The decorated methods can be `def` or `async def`. Both run in sync and async
viewsets. You can add many hooks for the same event: they run in the order you
define them.

When you call `save()` or `delete()` yourself, `@on_create`, `@on_update` and
`@on_delete` still run. `@on_update("field")` only runs through the framework
update, like `PATCH` or `Article.update()`.

!!! note

    The `on_delete` method and the `@on_delete` decorator share a name. If your
    class defines both, import the module instead:
    `from ninja_aio.models import hooks`, then use `@hooks.on_delete`.

## Know the order

For a `ModelSerializer`, hooks run in this order:

| Operation | Order |
| --- | --- |
| Create | `on_create_before_save`, `before_save`, save, `on_create_after_save`, `after_save`, `custom_actions`, `post_create`, `@on_create` |
| Update | `before_save`, save, `after_save`, `custom_actions`, `@on_update("field")`, `@on_update` |
| Delete | delete, `on_delete`, `@on_delete` |

In async viewsets, `custom_actions` runs before `before_save` on update.

On the generated endpoints, the write and its hooks run in one database
transaction. If a hook raises, the change is rolled back. To run code only
after the commit, use Django's `transaction.on_commit()` inside the hook.

## Use hooks on a Serializer

A `Serializer` for a plain Django model has the same hooks. They receive the
instance as an argument:

```python title="blog/serializers.py"
from ninja_aio import Serializer
from ninja_aio.models.hooks import on_update


class ArticleSerializer(Serializer):
    class Meta:
        model = Article

    class Schemas:
        ...

    def post_create(self, instance):
        AuditLog.objects.create(action="create", article=instance)

    def custom_actions(self, payload, instance):
        if payload.get("notify_editors"):
            notify_editors(instance.pk)

    @on_update("is_published")
    async def published_changed(self, instance):
        await clear_cache(instance.pk)
```

| Hook | Arguments |
| --- | --- |
| `post_create` / `apost_create` | `instance` |
| `custom_actions` / `acustom_actions` | `payload`, `instance` |
| `queryset_request` / `aqueryset_request` | `request` (classmethod) |
| `@on_create`, `@on_update`, `@on_delete` methods | `instance` |

## Hooks on the viewset

Viewsets have their own hooks that receive the request, like
`on_before_operation` and `on_list_queryset`. See
[Run code before each operation](viewsets.md#run-code-before-each-operation).
For access rules, see [Permissions](permissions.md).

## See also

- [Schemas](schemas.md)
- [Viewsets](viewsets.md)
- [Permissions](permissions.md)
- [Create the CRUD API](../tutorial/crud.md)
