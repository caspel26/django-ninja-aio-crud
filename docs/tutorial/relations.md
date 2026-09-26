---
type: tutorial
step: 3
steps: 7
title: Add relations
description: Link articles to categories, return related objects and accept them as input.
---

# Add relations

In this step you add a `Category` model, link each article to a category and
return the category inside the article.

## Add the Category model

```python title="blog/models.py"
class Category(ModelSerializer):
    name = models.CharField(max_length=100, unique=True)

    class Schemas:
        create = SchemaConfig(fields=["name"])
        read = SchemaConfig(fields=["id", "name"])

    def __str__(self):
        return self.name
```

Then add a foreign key to `Article` and list it in the schemas:

```python title="blog/models.py" hl_lines="3-5 9 13 16"
class Article(ModelSerializer):
    # other fields as before
    category = models.ForeignKey(
        Category, on_delete=models.PROTECT, related_name="articles"
    )

    class Schemas:
        create = SchemaConfig(
            fields=["title", "body", "category"],
            optionals=[("is_published", bool)],
        )
        update = SchemaConfig(
            optionals=[("title", str), ("body", str), ("is_published", bool), ("category", int)],
        )
        read = SchemaConfig(
            fields=["id", "title", "is_published", "created_at", "category"],
        )
        # detail as before, plus "category"
```

Run `makemigrations` and `migrate`, then register a viewset for categories:

```python title="blog/api.py"
from .models import Article, Category


@api.viewset(model=Category)
class CategoryViewSet(APIViewSet):
    pass
```

## Send related objects

To create an article, send the category's `id` as `category_id`:

```bash
curl -X POST localhost:8000/api/articles/ \
  -H "Content-Type: application/json" \
  -d '{"title": "Hello", "body": "...", "category_id": 1}'
```

To move an article to another category, send `category` in a `PATCH`:

```bash
curl -X PATCH localhost:8000/api/articles/1/ \
  -H "Content-Type: application/json" \
  -d '{"category": 2}'
```

An `id` that doesn't exist returns `404`.

## Read related objects

Because `Category` has a `read` schema, the article includes the whole
category:

```json
{
  "id": 1,
  "title": "Hello",
  "is_published": false,
  "created_at": "2026-09-26T10:00:00Z",
  "category": {"id": 1, "name": "Django"}
}
```

The framework loads the category in the same query, so listing many articles
doesn't run one query per article.

### Return only the id

List the relation in `relations_as_id` to return the `id` instead of the
object:

```python
read = SchemaConfig(
    fields=["id", "title", "is_published", "created_at", "category"],
    relations_as_id=["category"],
)
```

```json
{"id": 1, "title": "Hello", "is_published": false, "created_at": "...", "category": 1}
```

## Show articles in a category

Reverse relations work the same way. Add `articles`, the `related_name` of the
foreign key, to the category's `read` schema:

```python
class Category(ModelSerializer):
    ...

    class Schemas:
        create = SchemaConfig(fields=["name"])
        read = SchemaConfig(fields=["id", "name", "articles"])
```

```json
{
  "id": 1,
  "name": "Django",
  "articles": [{"id": 1, "title": "Hello", "is_published": false, "created_at": "..."}]
}
```

Each nested article leaves out its `category`, so the response doesn't loop.

!!! tip

    To create a category and its articles in one request, see
    [nested writes](../guides/nested-writes.md).

[Next: add authentication](authentication.md){ .md-button .md-button--primary }
