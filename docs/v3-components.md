---
type: guide
status: new
since: "3.0"
title: Page patterns
description: Internal showcase of the documentation page patterns. Removed before the 3.0 release.
---

# Page patterns

Every building block a documentation page can use, on one page. Set `type:` in the front matter to pick the page layout.

!!! prerequisites "Before you start"

    You have a model and an `APIViewSet` from the [quick start](getting_started/quick_start.md).

## Numbered steps

<div class="nac-steps" markdown>

### Declare the schemas

```python
class Article(ModelSerializer):
    class Schemas:
        create = SchemaConfig(fields=["title", "body"])
        read = SchemaConfig(fields=["id", "title"])
```

### Register the viewset

```python
@api.viewset(model=Article)
class ArticleViewSet(APIViewSet):
    pass
```

### Open the docs

Run the server and visit `/api/docs`.

</div>

## Sync and async tabs

=== "Sync"

    ```python
    article = Article.create({"title": "Draft", "body": "..."})
    data = Article.model_dump(article)
    ```

=== "Async"

    ```python
    article = await Article.acreate({"title": "Draft", "body": "..."})
    data = await Article.amodel_dump(article)
    ```

## API signature

<div class="nac-signature" markdown>

```python
Article.create(data: dict | Schema, *, request: HttpRequest | None = None) -> Article
```

</div>

| Parameter | Description |
| --- | --- |
| `data` | The fields to save, as a dict or a schema instance. |
| `request` | Optional. Passed to your hooks and permission checks. |

## Version notices

!!! new "New in 3.0"

    `model_dumps()` serializes a list of objects in one call.

!!! changed "Changed in 3.0"

    `create()` now returns the model instance instead of a dict.

!!! deprecated "Deprecated in 3.0"

    `generate_read_s()` still works but shows a warning. Use `read_schema` instead.

## Callouts

!!! note

    Notes add useful context.

!!! tip

    Tips show a shortcut.

!!! warning

    Warnings point out something that can go wrong.

??? question "Can I use both serializer styles in one project?"

    Yes. Each viewset uses the style of the model it serves.
