---
type: guide
title: Use the CRUD API from Python
description: Create, read, update and delete objects from your own code with the same rules as the API.
---

# Use the CRUD API from Python

Your serializers have classmethods that run the same create, read, update and
delete logic as the endpoints. Use them in scripts, background tasks and
tests.

!!! new "New in 3.0"

    `create`, `get`, `update` and `destroy` are available on every
    `ModelSerializer` and `Serializer`.

## Create an object

=== "Sync"

    ```python
    article = Article.create(
        {"title": "Hello", "body": "First post", "category_id": 1}
    )
    ```

=== "Async"

    ```python
    article = await Article.acreate(
        {"title": "Hello", "body": "First post", "category_id": 1}
    )
    ```

The data is validated with the `create` schema, so it uses the same keys as
the request body. You get the saved instance back. Unknown keys are ignored.

You can also pass a schema instance instead of a dict:

```python
data = Article.create_schema(title="Hello", body="First post", category_id=1)
article = Article.create(data)
```

## Get one object

=== "Sync"

    ```python
    article = Article.get(1)
    article = Article.get(title="Hello")
    ```

=== "Async"

    ```python
    article = await Article.aget(1)
    article = await Article.aget(title="Hello")
    ```

Pass the primary key, or keyword lookups like `title="Hello"` or
`category__name="Django"`. Use one or the other: passing both, or neither,
raises `ValueError`.

Add `optimize_for` to load the relations of a schema in the same query:

```python
article = Article.get(1, optimize_for="detail")
```

`optimize_for` accepts `"read"` or `"detail"`. Use it when you want to
serialize the object next, see [Serialize objects](dumping.md).

## Get many objects

=== "Sync"

    ```python
    published = Article.get_queryset().filter(is_published=True)
    ```

=== "Async"

    ```python
    queryset = await Article.aget_queryset()
    published = [a async for a in queryset.filter(is_published=True)]
    ```

You get a Django queryset built by your `queryset_request` hook. It also
accepts `optimize_for="read"` or `optimize_for="detail"`.

## Update an object

=== "Sync"

    ```python
    article = Article.update(1, {"is_published": True})
    article = Article.update(article, {"title": "Hello again"})
    ```

=== "Async"

    ```python
    article = await Article.aupdate(1, {"is_published": True})
    article = await Article.aupdate(article, {"title": "Hello again"})
    ```

The target is a primary key or an instance you already loaded. A primary key
is looked up first, an instance is used as it is. The data is validated with
the `update` schema. Fields you leave out, or send as `None`, keep their
value. You get the updated instance back.

## Delete an object

=== "Sync"

    ```python
    Article.destroy(1)
    Article.destroy(article)
    ```

=== "Async"

    ```python
    await Article.adestroy(1)
    await Article.adestroy(article)
    ```

The target is a primary key or an instance. The method returns `None`.

## Pass the request

Every method accepts an optional `request`:

```python
def my_view(request, pk):
    article = Article.get(pk, request=request)
```

| Where it is used | What happens |
| --- | --- |
| `queryset_request` / `aqueryset_request` | Receives the request. `get`, `get_queryset`, and `update` or `destroy` with a primary key only find objects in that queryset |
| Foreign key ids in the data | Looked up through the `queryset_request` of the related serializer |

Without `request`, your `queryset_request` receives `None`. Handle that case
if the hook reads `request.user`. See [Hooks](hooks.md).

## Handle errors

```python
from ninja_aio.exceptions import NotFoundError, OperationValidationError

try:
    Article.create({"title": "Hello", "category_id": 1})
except OperationValidationError as exc:
    print(exc.field_errors)
    # {'body': ['Field required']}

try:
    Article.get(999)
except NotFoundError as exc:
    print(exc.error, exc.status_code)
    # {'article': 'not found'} 404
```

| Exception | When |
| --- | --- |
| `OperationValidationError` | The data does not match the `create` or `update` schema |
| `NotFoundError` | No object matches the primary key or lookups, in `get`, `update` or `destroy`. Also raised for a foreign key id that does not exist |
| `ValueError` | `get` receives both a primary key and lookups, or neither. `update` or `destroy` receives an instance that was never saved |
| `MultipleObjectsReturned` | The lookups of `get` match more than one object. This is the Django exception of the model, like `Article.MultipleObjectsReturned` |

Both framework exceptions have these attributes:

| Attribute | What it holds |
| --- | --- |
| `field_errors` | A dict of field name to list of messages |
| `error` | The error body the API would return |
| `status_code` | The HTTP status the API would return: `400` or `404` |

When the same error happens inside an endpoint, the client gets `error` as the
response body with `status_code`. See [Errors](errors.md).

## Use a Serializer

A `Serializer` has the same methods. They return instances of the model in
`Meta.model`:

```python
from blog.serializers import ArticleSerializer

article = ArticleSerializer.create(
    {"title": "Hello", "body": "First post", "category_id": 1}
)
article = ArticleSerializer.get(article.pk)
ArticleSerializer.destroy(article)
```

## Use transactions

A call runs in a transaction when the serializer has `@on_create`,
`@on_update` or `@on_delete` hooks, or nested writes. Otherwise the row is
saved before your `post_create` and `custom_actions` hooks run, and it stays
saved if a hook raises.

Wrap the calls in `transaction.atomic()` when several steps must succeed or
fail together:

```python
from django.db import transaction

with transaction.atomic():
    category = Category.create({"name": "Django"})
    Article.create({"title": "Hello", "body": "...", "category_id": category.pk})
```

## Use it in scripts and tasks

The sync methods work anywhere Django is set up, like a management command or
a background task:

```python title="blog/tasks.py"
from celery import shared_task

from .models import Article


@shared_task
def publish_article(pk):
    Article.update(pk, {"is_published": True})
```

Pass primary keys to tasks, not instances.

## Use it in tests

Create test data with the same validation as the API:

```python title="blog/tests.py"
from django.test import TestCase

from ninja_aio.exceptions import OperationValidationError

from .models import Article, Category


class ArticleTests(TestCase):
    def setUp(self):
        self.category = Category.create({"name": "Django"})

    def test_title_is_required(self):
        with self.assertRaises(OperationValidationError) as ctx:
            Article.create({"body": "...", "category_id": self.category.pk})
        self.assertIn("title", ctx.exception.field_errors)

    def test_publish(self):
        article = Article.create(
            {"title": "Hello", "body": "...", "category_id": self.category.pk}
        )
        article = Article.update(article, {"is_published": True})
        self.assertTrue(article.is_published)
```

## See also

- [Serialize objects](dumping.md)
- [Bulk operations](bulk-operations.md)
- [Hooks](hooks.md)
- [Errors](errors.md)
- [Schemas](schemas.md)
