---
type: guide
title: Serialize objects
description: Turn model instances into dicts with the same schemas as your API responses.
---

# Serialize objects

Turn instances into dicts with the same fields as your API responses. Use it
in scripts, tasks, tests and custom endpoints.

!!! new "New in 3.0"

    `model_dump` and `model_dumps` are available on every `ModelSerializer`
    and `Serializer`.

## Serialize one object

=== "Sync"

    ```python
    article = Article.get(1, optimize_for="detail")
    data = Article.model_dump(article)
    ```

=== "Async"

    ```python
    article = await Article.aget(1)
    data = await Article.amodel_dump(article)
    ```

You get a dict with the fields of the `detail` schema. Without a `detail`
schema, the `read` fields are used. Relations are nested like in the API:

```python
print(data["category"])
# {'id': 1, 'name': 'Django'}
```

## Serialize many objects

=== "Sync"

    ```python
    articles = list(Article.get_queryset(optimize_for="read"))
    data = Article.model_dumps(articles)
    ```

=== "Async"

    ```python
    queryset = await Article.aget_queryset()
    data = await Article.amodel_dumps(queryset.filter(is_published=True))
    ```

You get a list of dicts with the fields of the `read` schema, like the items
of the list endpoint.

## Use another schema

Pass `schema` to pick the fields:

```python
data = Article.model_dump(article, schema=Article.read_schema)
```

Any schema works, including one you write yourself:

```python
from ninja import Schema


class ArticleTitle(Schema):
    id: int
    title: str


data = Article.model_dumps(articles, schema=ArticleTitle)
# [{'id': 1, 'title': 'Hello'}, ...]
```

## Load relations before a sync dump

The sync methods never run database queries. Every relation and field in the
schema must already be loaded on the objects.

Load them with `optimize_for`, using the kind of schema you dump with:

| You dump with | Load with |
| --- | --- |
| `model_dump(obj)` | `Article.get(pk, optimize_for="detail")` |
| `model_dump(obj, schema=Article.read_schema)` | `Article.get(pk, optimize_for="read")` |
| `model_dumps(objs)` | `list(Article.get_queryset(optimize_for="read"))` |

`model_dumps` needs the objects themselves. Pass a list, or a queryset you
already iterated. A queryset that has not run yet is rejected.

When something is missing you get a `ValueError`:

| Message | Cause |
| --- | --- |
| `Synchronous dump requires an evaluated queryset` | You passed a queryset to `model_dumps` before it ran |
| `Synchronous dump requires preloaded fields and relations` | A relation in the schema is not loaded, or a field was skipped with `only()` or `defer()` |

A plain `Article.get(1)` or `Article.objects.get(pk=1)` does not load
relations. Dumping it with a schema that has `category` raises the second
error.

!!! tip

    A foreign key that is `None` counts as loaded.

## Let async dumps load relations

`amodel_dump` and `amodel_dumps` load the relations the schema needs, so you
can pass any instance:

```python
article = await Article.objects.aget(pk=1)
data = await Article.amodel_dump(article)
```

`amodel_dumps` accepts a list of instances or a queryset. A queryset that has
not run yet is loaded with its relations in one go.

## Use a Serializer

A `Serializer` has the same methods. Pass instances of its model:

```python
from blog.serializers import ArticleSerializer

article = ArticleSerializer.get(1, optimize_for="detail")
data = ArticleSerializer.model_dump(article)
```

## See also

- [Use the CRUD API from Python](python-crud.md)
- [Schemas](schemas.md)
- [Relations](relations.md)
- [Query optimization](query-optimization.md)
