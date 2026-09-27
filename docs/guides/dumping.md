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
    article = Article.get(1)
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
    queryset = Article.get_queryset()
    data = Article.model_dumps(queryset.filter(is_published=True))
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

## Know which queries run

Both modes load the relations the schema needs and are missing on the
objects, with one query per relation for the whole list, never one per
object. Relations you already loaded, with `optimize_for`, `select_related`
or `prefetch_related`, cost nothing:

```python
article = Article.get(1, optimize_for="detail")
data = Article.model_dump(article)  # no query
```

`model_dumps` and `amodel_dumps` accept a list of instances or a queryset. A
queryset that has not run yet is loaded with its relations in one go.

A foreign key that is `None` counts as loaded. Fields skipped with `only()` or
`defer()` are not loaded for you: the dump raises
`ValueError: Synchronous dump requires preloaded fields and relations`.

## Forbid queries during a sync dump

Pass `strict=True` to make sure a dump never touches the database, for
example in a hot path or a test:

```python
Article.model_dump(article, strict=True)
Article.model_dumps(articles, strict=True)
```

With `strict=True` a missing relation or deferred field raises
`ValueError: Synchronous dump requires preloaded fields and relations`, and a
queryset that has not run yet raises
`ValueError: Synchronous dump requires an evaluated queryset`.

## Use a Serializer

A `Serializer` has the same methods. Pass instances of its model:

```python
from blog.serializers import ArticleSerializer

article = ArticleSerializer.get(1)
data = ArticleSerializer.model_dump(article)
```

## See also

- [Use the CRUD API from Python](python-crud.md)
- [Schemas](schemas.md)
- [Relations](relations.md)
- [Query optimization](query-optimization.md)
