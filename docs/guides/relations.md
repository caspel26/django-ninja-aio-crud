---
type: guide
title: Relations
description: Return related objects, send foreign keys and manage many-to-many links.
---

# Relations

This page shows how to return foreign keys, reverse relations, one-to-one and
many-to-many fields, how to send related ids, and how to add many-to-many
endpoints to a viewset.

The examples add a `Tag` model to the blog:

```python title="blog/models.py"
class Tag(ModelSerializer):
    name = models.CharField(max_length=50, unique=True)

    class Schemas:
        create = SchemaConfig(fields=["name"])
        read = SchemaConfig(fields=["id", "name"])


class Article(ModelSerializer):
    # other fields as before
    category = models.ForeignKey(
        Category, on_delete=models.PROTECT, related_name="articles"
    )
    tags = models.ManyToManyField(Tag, related_name="articles", blank=True)
```

## Return related objects

List the relation in `read` or `detail`, like any other field:

```python
read = SchemaConfig(fields=["id", "title", "category", "tags"])
```

```json
{
  "id": 1,
  "title": "Hello",
  "category": {"id": 1, "name": "Django"},
  "tags": [{"id": 1, "name": "python"}, {"id": 2, "name": "async"}]
}
```

Each nested object uses the related model's `read` fields, without its own
relations. The related model needs a `read` schema, otherwise the relation is
left out.

| Relation | Returned as |
| --- | --- |
| Foreign key, like `category` | One object, or `null` |
| One-to-one, both sides | One object, or `null` |
| Reverse foreign key, like `articles` on `Category` | A list of objects |
| Many-to-many, both sides | A list of objects |

Reverse relations use the `related_name`. Add `articles` to the category's
`read` schema to list its articles:

```python
class Category(ModelSerializer):
    ...

    class Schemas:
        create = SchemaConfig(fields=["name"])
        read = SchemaConfig(fields=["id", "name", "articles"])
```

```json
{"id": 1, "name": "Django", "articles": [{"id": 1, "title": "Hello"}]}
```

Each nested article leaves out its `category`, so the response doesn't loop.
The framework loads the relations of `read` and `detail` for you, so a list
doesn't run one query per item.

## Return only the id

List the relation in `relations_as_id` to return primary keys instead of
objects:

```python
read = SchemaConfig(
    fields=["id", "title", "category", "tags"],
    relations_as_id=["category", "tags"],
)
```

```json
{"id": 1, "title": "Hello", "category": 1, "tags": [1, 2]}
```

`relations_as_id` works for every relation kind in the table above. Single
relations become one id, or `null`. Many relations become a list of ids.
Use it in `read` and `detail` only.

## Send a foreign key

A foreign key in `create` fields becomes `<name>_id` in the request body:

```python
create = SchemaConfig(fields=["title", "body", "category"])
```

```bash
curl -X POST localhost:8000/api/articles/ \
  -H "Content-Type: application/json" \
  -d '{"title": "Hello", "body": "...", "category_id": 1}'
```

In `update`, declare the foreign key as an optional with the id type. The
body key is the field name:

```python
update = SchemaConfig(optionals=[("title", str), ("category", int)])
```

```bash
curl -X PATCH localhost:8000/api/articles/1/ \
  -H "Content-Type: application/json" \
  -d '{"category": 2}'
```

An id that doesn't exist returns `404` and nothing is saved:

```json
{"category": "not found"}
```

To create related objects in the same request, see
[Nested writes](nested-writes.md).

## Add many-to-many endpoints

Add an `M2MRelationSchema` to `m2m_relations` for each many-to-many field:

```python title="blog/api.py"
from ninja_aio import APIViewSet
from ninja_aio.schemas import M2MRelationSchema

from .models import Article, Tag


@api.viewset(model=Article)
class ArticleViewSet(APIViewSet):
    m2m_relations = [
        M2MRelationSchema(model=Tag, related_name="tags"),
    ]
```

You get these endpoints:

| Method | Path | Status | Body | Response |
| --- | --- | --- | --- | --- |
| `GET` | `/api/articles/{id}/tags` | 200 | | Paginated tags |
| `POST` | `/api/articles/{id}/tags/` | 200 | `{"add": [...], "remove": [...]}` | Results and errors |

The path comes from the plural verbose name of the related model. The list
uses the tag's `read` fields without relations, with `?page=` and
`?page_size=` like the main list.

Send the ids to add and remove in one request. Both keys are optional:

```bash
curl -X POST localhost:8000/api/articles/1/tags/ \
  -H "Content-Type: application/json" \
  -d '{"add": [1, 2, 99], "remove": [3]}'
```

```json
{
  "results": {
    "count": 2,
    "details": ["Tag with pk 1 successfully added", "Tag with pk 2 successfully added"]
  },
  "errors": {
    "count": 2,
    "details": ["Tag with pk 99 not found.", "Tag with pk 3 is not in article"]
  }
}
```

Each id is checked on its own. Valid ids are saved and the others are listed
in `errors`, so the status is `200` even when some ids fail. Adding a tag
that is already linked, or removing one that isn't, is an error.

### M2MRelationSchema options

| Option | Default | What it does |
| --- | --- | --- |
| `model` | required | The related model |
| `related_name` | required | The many-to-many field on the viewset model, like `tags` |
| `get` | `True` | Add the `GET` endpoint |
| `add` | `True` | Accept `add` in the `POST` body |
| `remove` | `True` | Accept `remove` in the `POST` body |
| `path` | plural verbose name | The URL segment after `{id}/` |
| `auth` | viewset `m2m_auth` | Authentication for these endpoints |
| `filters` | `None` | Query parameters for the `GET` endpoint, as `{"name": (type, default)}` |
| `related_schema` | related `read` fields | The schema of each listed object. Required for a plain Django model without `serializer_class` |
| `serializer_class` | `None` | The `Serializer` of a plain Django model, used to build `related_schema` |
| `append_slash` | `False` | Add a trailing slash to the `GET` path |
| `verbose_name_plural` | from the model | Name used in summaries like "Get Tags" |
| `get_decorators`, `post_decorators` | `[]` | Decorators for the `GET` or `POST` endpoint |

With `add=False` or `remove=False`, the body only accepts the other key. With
both set to `False` there is no `POST` endpoint.

!!! warning

    Many-to-many endpoints don't use the viewset `auth`. Set `m2m_auth` on the
    viewset or `auth` on the relation. Without either, the API auth is used.

### Filter the related list

`filters` adds query parameters. Apply them in a method named
`<related_name>_query_params_handler`:

```python
@api.viewset(model=Article)
class ArticleViewSet(APIViewSet):
    m2m_relations = [
        M2MRelationSchema(model=Tag, related_name="tags", filters={"name": (str, "")}),
    ]

    def tags_query_params_handler(self, queryset, filters):
        if filters.get("name"):
            queryset = queryset.filter(name__icontains=filters["name"])
        return queryset
```

`GET /api/articles/1/tags?name=py` returns the matching tags. Without the
method, the parameters are accepted but ignored. In sync viewsets the method
must be a plain `def`. Async viewsets accept `def` or `async def`.

## Relations with a Serializer

With a `Serializer`, map each relation to the serializer of the related model
in `Meta.relations_serializers`:

```python title="blog/serializers.py"
from ninja_aio import Serializer, SchemaConfig

from .models import Article, Category


class CategorySerializer(Serializer[Category]):
    class Meta:
        model = Category

    class Schemas:
        read = SchemaConfig(fields=["id", "name"])


class ArticleSerializer(Serializer[Article]):
    class Meta:
        model = Article
        relations_serializers = {"category": CategorySerializer}

    class Schemas:
        read = SchemaConfig(fields=["id", "title", "category"])
```

The value can also be a string, like `"CategorySerializer"` for a class in
the same module or `"blog.serializers.CategorySerializer"`. Use it when two
serializers refer to each other.

A reverse relation without an entry is left out of the response, with a
warning. `relations_as_id` works the same way as with `ModelSerializer` and
needs no entry.

## See also

- [Add relations](../tutorial/relations.md)
- [Schemas](schemas.md)
- [Nested writes](nested-writes.md)
- [Query optimization](query-optimization.md)
- [Viewsets](viewsets.md)
