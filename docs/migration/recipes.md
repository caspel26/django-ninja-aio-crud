---
type: migration
title: Migration recipes
description: Before and after code for the most common changes from version 2 to 3.0.
---

# Migration recipes

Each recipe shows version 2 code and the same code in 3.0. Apply the ones
that match your project.

## Move inner serializer classes to Schemas

Replace `CreateSerializer`, `ReadSerializer`, `UpdateSerializer` and
`DetailSerializer` with one `Schemas` class. Each kind is a `SchemaConfig`
with the same `fields`, `optionals`, `customs` and `excludes` options.

=== "Before (2.x)"

    ```python title="blog/models.py"
    from ninja_aio.models import ModelSerializer


    class Article(ModelSerializer):
        ...

        class CreateSerializer:
            fields = ["title", "body", "category"]
            optionals = [("is_published", bool)]
            customs = [("notify", bool, False)]

        class ReadSerializer:
            fields = ["id", "title", "is_published", "category"]

        class DetailSerializer:
            fields = ["id", "title", "body", "is_published", "category"]

        class UpdateSerializer:
            optionals = [("title", str), ("body", str), ("is_published", bool)]
            excludes = ["views"]
    ```

=== "After (3.0)"

    ```python title="blog/models.py"
    from ninja_aio import ModelSerializer, SchemaConfig


    class Article(ModelSerializer):
        ...

        class Schemas:
            create = SchemaConfig(
                fields=["title", "body", "category"],
                optionals=[("is_published", bool)],
                customs=[("notify", bool, False)],
            )
            read = SchemaConfig(fields=["id", "title", "is_published", "category"])
            detail = SchemaConfig(
                fields=["id", "title", "body", "is_published", "category"]
            )
            update = SchemaConfig(
                optionals=[("title", str), ("body", str), ("is_published", bool)],
                excludes=["views"],
            )
    ```

## Move Meta schemas to Schemas

On a `Serializer`, move `schema_in`, `schema_out`, `schema_update` and
`schema_detail` out of `Meta`. `Meta` keeps `model` and
`relations_serializers`.

=== "Before (2.x)"

    ```python title="blog/serializers.py"
    from ninja_aio.models.serializers import Serializer, SchemaModelConfig


    class ArticleSerializer(Serializer):
        class Meta:
            model = Article
            schema_in = SchemaModelConfig(fields=["title", "body", "category"])
            schema_out = SchemaModelConfig(fields=["id", "title", "category"])
            schema_update = SchemaModelConfig(optionals=[("title", str)])
            schema_detail = SchemaModelConfig(
                fields=["id", "title", "body", "category"]
            )
            relations_serializers = {"category": CategorySerializer}
    ```

=== "After (3.0)"

    ```python title="blog/serializers.py"
    from ninja_aio import Serializer, SchemaConfig


    class ArticleSerializer(Serializer):
        class Meta:
            model = Article
            relations_serializers = {"category": CategorySerializer}

        class Schemas:
            create = SchemaConfig(fields=["title", "body", "category"])
            read = SchemaConfig(fields=["id", "title", "category"])
            update = SchemaConfig(optionals=[("title", str)])
            detail = SchemaConfig(fields=["id", "title", "body", "category"])
    ```

## Rename async hooks

Async hooks now start with `a`. The plain names are for sync hooks.

=== "Before (2.x)"

    ```python
    class Article(ModelSerializer):
        async def post_create(self):
            ...

    class ArticleViewSet(APIViewSet):
        async def on_before_operation(self, request, operation):
            ...
    ```

=== "After (3.0)"

    ```python
    class Article(ModelSerializer):
        async def apost_create(self):
            ...

    class ArticleViewSet(APIViewSet):
        async def aon_before_operation(self, request, operation):
            ...
    ```

| Version 2 | 3.0 |
| --- | --- |
| `async def post_create(self)` | `async def apost_create(self)` |
| `async def custom_actions(self, payload)` | `async def acustom_actions(self, payload)` |
| `async def queryset_request(cls, request)` (classmethod) | `async def aqueryset_request(cls, request)` (classmethod) |
| `async def on_before_operation(...)` | `async def aon_before_operation(...)` |
| `async def on_before_object_operation(...)` | `async def aon_before_object_operation(...)` |
| `async def query_params_handler(...)` | `async def aquery_params_handler(...)` |
| `async def has_permission(...)` | `async def ahas_permission(...)` |
| `async def has_object_permission(...)` | `async def ahas_object_permission(...)` |

If you keep an async hook under its old name, the app fails at startup with
`ImproperlyConfigured` and tells you the new name:

```text
Article.post_create is async; rename it to apost_create (sync hooks use the plain name).
```

## Replace util calls with serializer methods

Call the methods on your serializer instead of `.util`. You no longer pass a
schema to read data back: `amodel_dump()` uses the detail schema and
`amodel_dumps()` uses the read schema, unless you pass `schema=`.

=== "Before (2.x)"

    ```python
    data = await Article.util.create_s(request, payload, Article.generate_read_s())

    article = await Article.util.get_object(request, pk)
    data = await Article.util.read_s(Article.generate_read_s(), request, article)

    articles = await Article.util.get_objects(request)
    items = await Article.util.list_read_s(Article.generate_read_s(), request, articles)
    ```

=== "After (3.0)"

    ```python
    article = await Article.acreate(payload, request=request)
    data = await Article.amodel_dump(article, schema=Article.read_schema)

    article = await Article.aget(pk, request=request)
    data = await Article.amodel_dump(article, schema=Article.read_schema)

    articles = await Article.aget_queryset(request=request)
    items = await Article.amodel_dumps(articles)
    ```

See [Deprecations](deprecations.md#modelutil) for the full list.

## Replace route decorators with action

Use `@action(detail=False, ...)` for extra endpoints on a viewset. `GET` is
the default method.

=== "Before (2.x)"

    ```python title="blog/views.py"
    from ninja_aio.decorators import api_get, api_post


    class ArticleViewSet(APIViewSet):
        model = Article
        api = api

        @api_get("/stats")
        async def stats(self, request):
            return {"total": await Article.objects.acount()}

        @api_post("/archive-old")
        async def archive_old(self, request):
            ...
    ```

=== "After (3.0)"

    ```python title="blog/views.py"
    from ninja_aio import APIViewSet, action


    class ArticleViewSet(APIViewSet):
        model = Article
        api = api

        @action(detail=False, url_path="stats")
        async def stats(self, request):
            return {"total": await Article.objects.acount()}

        @action(detail=False, methods=["post"], url_path="archive-old")
        async def archive_old(self, request):
            ...
    ```

## Use the async methods on Serializer

In version 2, you awaited `create()`, `update()` and `model_dump()` on a
`Serializer`. In 3.0 they are sync class methods. In async code, use
`acreate()`, `aupdate()` and `amodel_dump()`.

=== "Before (2.x)"

    ```python
    serializer = ArticleSerializer()
    article = await serializer.create(payload)
    article = await serializer.update(changes, article)
    data = await serializer.model_dump(article)
    ```

=== "After (3.0)"

    ```python
    article = await ArticleSerializer.acreate(payload)
    article = await ArticleSerializer.aupdate(article, changes)
    data = await ArticleSerializer.amodel_dump(article)
    ```

Note the new argument order of `aupdate()`: the instance (or its primary key)
comes first, then the data.

## Serve a viewset with sync views

Set `execution_mode = "sync"` on the viewset. Rename the async hooks you
override to their sync names and write them as plain functions.

=== "Before (2.x)"

    ```python title="blog/views.py"
    class ArticleViewSet(APIViewSet):
        model = Article
        api = api

        async def on_before_operation(self, request, operation):
            ...
    ```

=== "After (3.0)"

    ```python title="blog/views.py"
    class ArticleViewSet(APIViewSet):
        model = Article
        api = api
        execution_mode = "sync"

        def on_before_operation(self, request, operation):
            ...
    ```

The URLs, schemas and responses stay the same.

## See also

- [Deprecations](deprecations.md)
- [Breaking changes](breaking-changes.md)
- [Migration overview](index.md)
- [Hooks](../guides/hooks.md)
