---
type: guide
title: Query optimization
description: Load related objects in few queries, scope the base queryset and check query counts in tests.
---

# Query optimization

This page shows how related objects are loaded, how to tune the loading with
a `QuerySet` class, how to scope every query by request, and how to check
query counts in tests.

## Relations load automatically

Relations listed in `read` or `detail` are loaded for you:

```python
class Schemas:
    read = SchemaConfig(fields=["id", "title", "category", "tags"])
```

| Relation in the schema | Loaded with |
| --- | --- |
| Foreign key or one-to-one, like `category` | `select_related` |
| Reverse foreign key, like `articles` on `Category` | `prefetch_related` |
| Many-to-many, like `tags` | `prefetch_related` |
| Reverse one-to-one | `prefetch_related` |

The list endpoint uses the `read` fields. The retrieve endpoint uses the
`detail` fields, or `read` when there is no `detail` schema. A list of
articles with their category and tags takes one query for the articles and
one for the tags, however many articles there are. The list endpoint adds a
`COUNT` query for pagination.

## Load extra relations

Custom fields aren't checked for relations. Here `category_name` reads
`self.category`, so each article would run one more query:

```python title="blog/models.py"
from ninja_aio import ModelSerializer, SchemaConfig
from ninja_aio.schemas.helpers import ModelQuerySetSchema


class Article(ModelSerializer):
    # fields as before

    @property
    def category_name(self):
        return self.category.name

    class Schemas:
        read = SchemaConfig(
            fields=["id", "title", "tags"],
            customs=[("category_name", str, "")],
        )

    class QuerySet:
        read = ModelQuerySetSchema(select_related=["category"])
```

Add the `QuerySet` class to list the relations yourself:

| Attribute | Used for |
| --- | --- |
| `read` | The list endpoint and `optimize_for="read"` |
| `detail` | The retrieve endpoint and `optimize_for="detail"`. Defaults to `read` |
| `queryset_request` | Every query, through the default `queryset_request` |
| `extras` | Named scopes that you apply yourself |

`ModelQuerySetSchema` takes `select_related` and `prefetch_related`, both
lists of strings. Lookups across relations work too, like
`"category__parent"`.

!!! warning

    A list you set replaces the relations found in the schema. With
    `select_related=["category"]`, other foreign keys in `read` are no longer
    loaded. List every relation you need. An empty list keeps the automatic
    loading.

With a `Serializer`, put the `QuerySet` class on the serializer, next to
`Meta`:

```python title="blog/serializers.py"
class ArticleSerializer(Serializer[Article]):
    class Meta:
        model = Article

    class Schemas:
        read = SchemaConfig(fields=["id", "title", "tags"])

    class QuerySet:
        read = ModelQuerySetSchema(prefetch_related=["tags"])
```

### Named scopes

`extras` adds scopes with a name. They are not applied on their own. Apply
one to a queryset with `query_util`:

```python
from ninja_aio.schemas.helpers import ModelQuerySetExtraSchema, ModelQuerySetSchema


class Article(ModelSerializer):
    # fields and schemas as before

    class QuerySet:
        extras = [
            ModelQuerySetExtraSchema(scope="with_tags", prefetch_related=["tags"]),
        ]


queryset = Article.query_util.apply_queryset_optimizations(
    Article.objects.filter(is_published=True), "with_tags"
)
```

An unknown scope name raises `ValueError`.

## Scope the base queryset

Override `queryset_request` to change the queryset every query starts from.
It runs for the list, retrieve, update, delete and bulk endpoints, and for
`get()` and `get_queryset()` in Python:

=== "Sync"

    ```python title="blog/models.py"
    class Article(ModelSerializer):
        # fields and schemas as before

        @classmethod
        def queryset_request(cls, request):
            queryset = super().queryset_request(request)
            if request is None:
                return queryset
            return queryset.filter(is_published=True)
    ```

=== "Async"

    ```python title="blog/models.py"
    class Article(ModelSerializer):
        # fields and schemas as before

        @classmethod
        async def aqueryset_request(cls, request):
            queryset = await super().aqueryset_request(request)
            if request is None:
                return queryset
            return queryset.filter(is_published=True)
    ```

API clients now only see published articles. An unpublished id returns
`404`. Python calls without `request=` get `None` and see every article. You
can also return an annotated queryset.

Call `super()` to keep the `QuerySet.queryset_request` settings. Sync
viewsets call `queryset_request`, async viewsets call `aqueryset_request`. If
you define only one of them, it's used in both modes.

To filter only the list endpoint, use `on_list_queryset` on the viewset. See
[Viewsets](viewsets.md).

## Load relations in Python

`get()` and `get_queryset()` don't load relations unless you pass
`optimize_for`:

```python
article = Article.get(1, optimize_for="detail")
data = Article.model_dump(article)

articles = list(Article.get_queryset(optimize_for="read"))
data = Article.model_dumps(articles)
```

`optimize_for` takes `"read"` or `"detail"` and applies the same loading as
the endpoints. The sync `model_dump()` raises `ValueError` when a relation
isn't loaded, and `model_dumps()` needs an evaluated queryset, like a list.
The async `amodel_dump()` and `amodel_dumps()` load relations for you. See
[Dumping](dumping.md).

## Check query counts in tests

Wrap the code in `assertNumQueries` to fail the test when the count changes:

```python title="blog/tests.py"
from django.test import TestCase

from .models import Article, Category


class ArticleQueryTests(TestCase):
    def test_read_queries(self):
        category = Category.create({"name": "Django"})
        for i in range(5):
            Article.create(
                {"title": f"Post {i}", "body": "...", "category_id": category.pk}
            )

        with self.assertNumQueries(2):
            articles = list(Article.get_queryset(optimize_for="read"))
            Article.model_dumps(articles)
```

With `category` and `tags` in `read`, this takes two queries with 5 articles
or 500. To see the SQL, use Django's `CaptureQueriesContext` from
`django.test.utils`.

## See also

- [Relations](relations.md)
- [Dumping](dumping.md)
- [Python CRUD](python-crud.md)
- [Viewsets](viewsets.md)
