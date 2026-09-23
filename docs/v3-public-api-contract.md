# Version 3 Public API Contract

Status: internal implementation contract for `feat/v3-api-redesign`. Remove
this file before the final version 3 release after its stable content has been
transferred to the user-facing API reference and migration guide.

This document defines the public serializer API that version 3 must implement.
It is intentionally narrower than the version 2 surface: model inspection,
payload parsing, query planning, and `ModelUtil` are implementation details.

## API owners

The same facade is exposed by both supported serializer styles:

```python
class Book(ModelSerializer):
    ...

class BookSerializer(Serializer[BookModel]):
    ...
```

Calls in this document use `BookSerializer` generically and apply to either
style. Native Django instance methods keep their original meaning:

```python
book.save()
await book.asave()
book.delete()
await book.adelete()
```

The request-aware framework deletion pipeline is therefore named
`destroy()`/`adestroy()`.

## Common types

The signatures below use these conceptual types:

```python
PK: TypeAlias = int | str | UUID
InputData: TypeAlias = dict[str, Any] | ninja.Schema
SchemaType: TypeAlias = type[ninja.Schema]
ModelInstance: TypeAlias = ModelT
```

`request` is always optional and keyword-only. A serializer hook that requires
a request must raise a precise configuration error when invoked without one.

## CRUD facade

### Create

```python
BookSerializer.create(
    data: InputData,
    *,
    request: HttpRequest | None = None,
) -> ModelT

await BookSerializer.acreate(
    data: InputData,
    *,
    request: HttpRequest | None = None,
) -> ModelT
```

Creation validates and transforms input, persists one model instance, executes
the applicable hooks, and returns the model instance. It never returns a
serialized dictionary.

Dictionary input is validated with `create_schema`. Passing any `Schema`
instance revalidates its aliased payload with `create_schema`. A serializer
without a configured create schema raises `ImproperlyConfigured` before any
database access.

### Retrieve

```python
BookSerializer.get(
    pk: PK | None = None,
    *,
    request: HttpRequest | None = None,
    **lookups: Any,
) -> ModelT

await BookSerializer.aget(
    pk: PK | None = None,
    *,
    request: HttpRequest | None = None,
    **lookups: Any,
) -> ModelT
```

Exactly one lookup strategy must be supplied: `pk` or keyword lookups. Missing
objects raise the version 3 not-found exception in both modes.

Omitting both strategies or combining them raises `ValueError` before any
database access.

### Update

```python
BookSerializer.update(
    target: ModelT | PK,
    data: InputData,
    *,
    request: HttpRequest | None = None,
) -> ModelT

await BookSerializer.aupdate(
    target: ModelT | PK,
    data: InputData,
    *,
    request: HttpRequest | None = None,
) -> ModelT
```

Passing an instance avoids a redundant lookup. Passing a primary key performs
the request-aware lookup before applying the update. The returned value is the
updated model instance.

Update data follows the same validation rules through `update_schema`. An
unsaved target raises `ValueError`; an instance of the wrong model raises
`TypeError`.

### Destroy

```python
BookSerializer.destroy(
    target: ModelT | PK,
    *,
    request: HttpRequest | None = None,
) -> None

await BookSerializer.adestroy(
    target: ModelT | PK,
    *,
    request: HttpRequest | None = None,
) -> None
```

Passing an instance avoids a redundant lookup. This operation owns framework
hooks, soft-delete integration, error normalization, and transaction policy;
native Django `delete()`/`adelete()` remain untouched.

As with update, an unsaved target raises `ValueError` and an instance of the
wrong model raises `TypeError`.

## Serialization facade

```python
BookSerializer.model_dump(
    instance: ModelT,
    *,
    schema: SchemaType | None = None,
) -> dict[str, Any]

BookSerializer.model_dumps(
    instances: Iterable[ModelT] | QuerySet[ModelT],
    *,
    schema: SchemaType | None = None,
) -> list[dict[str, Any]]
```

The synchronous dump methods do not perform implicit database queries. The
caller must provide instances with the relations required by the selected
schema already loaded.

```python
await BookSerializer.amodel_dump(
    instance: ModelT,
    *,
    schema: SchemaType | None = None,
) -> dict[str, Any]

await BookSerializer.amodel_dumps(
    instances: Iterable[ModelT] | QuerySet[ModelT],
    *,
    schema: SchemaType | None = None,
) -> list[dict[str, Any]]
```

The async variants may execute the relation-loading plan required by the
schema. `model_dump`/`amodel_dump` default to `detail_schema`;
`model_dumps`/`amodel_dumps` default to `read_schema`.

## Schema access

Default schemas are synchronous, lazy class attributes:

```python
BookSerializer.create_schema
BookSerializer.update_schema
BookSerializer.read_schema
BookSerializer.detail_schema
BookSerializer.related_schema
```

The first access dynamically builds the schema from serializer configuration,
model metadata, validators, and relations. Results are cached per serializer,
schema kind, and depth. A subclass may replace an attribute with an explicit
schema class.

Parameterized access uses:

```python
BookSerializer.get_schema(
    kind: Literal["create", "update", "read", "detail", "related"],
    *,
    depth: int = 1,
) -> SchemaType | None

BookSerializer.clear_schema_cache() -> None
```

`depth` affects read/detail relation expansion. Unsupported depth values or
schema kinds raise configuration errors rather than silently falling back.

## Bulk operations

```python
BookSerializer.bulk_create(
    items: Iterable[InputData],
    *,
    request: HttpRequest | None = None,
) -> BulkResult[ModelT]

await BookSerializer.abulk_create(...) -> BulkResult[ModelT]

BookSerializer.bulk_update(
    items: Iterable[InputData],
    *,
    request: HttpRequest | None = None,
) -> BulkResult[ModelT]

await BookSerializer.abulk_update(...) -> BulkResult[ModelT]

BookSerializer.bulk_destroy(
    targets: Iterable[ModelT | PK],
    *,
    request: HttpRequest | None = None,
) -> BulkResult[PK]

await BookSerializer.abulk_destroy(...) -> BulkResult[PK]
```

Bulk operations retain version 2's per-item partial-success behavior unless an
explicit atomic policy is configured. They return typed results rather than
tuples.

## Hooks and model helpers

The following remain supported public extension points:

- `queryset_request`
- `has_changed` and `ahas_changed`
- `as_admin`
- reactive `@on_create`, `@on_update`, and `@on_delete`

Lifecycle hooks are normalized in Step 7. A hook may be implemented as a
regular or async callable under one semantic name; callers do not select hooks
by execution mode.

`save`, `asave`, `delete`, and `adelete` on a `ModelSerializer` model instance
remain Django-compatible instance operations. Standalone serializer persistence
helpers become private implementation details behind the CRUD facade.

## Version 2 compatibility decisions

Version 3 does not preserve aliases merely because they existed in version 2.
Temporary aliases may exist during branch development, but Step 13 removes the
entries marked "remove" before the final release.

| Version 2 API | Version 3 disposition |
| --- | --- |
| `generate_create_s()` | Replace with lazy `create_schema` |
| `generate_update_s()` | Replace with lazy `update_schema` |
| `generate_read_s()` | Replace with lazy `read_schema` |
| `generate_detail_s()` | Replace with lazy `detail_schema` |
| `generate_related_s()` | Replace with lazy `related_schema` |
| `generate_nested_child_schema()` | Make internal; reached through schema generation |
| `Serializer.create()` (async) | Replace with sync `create()` and async `acreate()` |
| `Serializer.update()` (async) | Replace with sync `update()` and async `aupdate()` |
| `Serializer.save()` (async) | Make internal; CRUD owns persistence |
| `Serializer.model_dump()` (async) | Replace with sync `model_dump()` and async `amodel_dump()` |
| `Serializer.models_dump()` | Replace with `model_dumps()`/`amodel_dumps()` |
| bound `Serializer(instance=...)` CRUD | Remove; pass target explicitly |
| `ModelUtil.get_object()` | Replace with `get()`/`aget()` |
| `ModelUtil.get_objects()` | Make internal query planning; use Django queryset APIs |
| `ModelUtil.create_s()` | Replace with `create()`/`acreate()` |
| `ModelUtil.read_s()` | Replace with `model_dump()`/`amodel_dump()` |
| `ModelUtil.list_read_s()` | Replace with `model_dumps()`/`amodel_dumps()` |
| `ModelUtil.update_s()` | Replace with `update()`/`aupdate()` |
| `ModelUtil.delete_s()` | Replace with `destroy()`/`adestroy()` |
| `ModelUtil.bulk_create_s()` | Replace with `bulk_create()`/`abulk_create()` |
| `ModelUtil.bulk_update_s()` | Replace with `bulk_update()`/`abulk_update()` |
| `ModelUtil.bulk_delete_s()` | Replace with `bulk_destroy()`/`abulk_destroy()` |
| `ModelUtil.parse_input_data()` | Make internal |
| `ModelUtil.get_reverse_relations()` | Make internal |
| `ModelUtil.get_select_relateds()` | Make internal |
| `ModelUtil` metadata properties/resolvers | Make internal |
| `BaseSerializer.get_fields()` and field helpers | Make internal |
| `BaseSerializer.get_schema_out_data()` | Make internal |
| `BaseSerializer.get_related_schema_data()` | Make internal |
| `queryset_request()` | Keep as extension hook; normalize sync/async invocation |
| `has_changed()`/`ahas_changed()` | Keep |
| `ModelSerializer.as_admin()` | Keep |
| Django model `save()`/`delete()` | Keep Django behavior unchanged |

## Generated API execution mode

`APIViewSet.execution_mode` selects `"sync"` or `"async"` for the generated
HTTP endpoints of a viewset. The default remains `"async"` so existing routes
retain their execution behavior. Sync mode registers regular Django Ninja view
functions and uses native synchronous serializer/ORM operations; async mode
registers coroutine view functions and uses their `a`-prefixed counterparts.
The selection applies to generated CRUD, bulk, and M2M endpoints together; it
must not silently mix modes or wrap an entire endpoint in `async_to_sync()` or
`sync_to_async()`. Custom `APIView` routes continue to use the `def` or
`async def` declared by their author.

Both modes preserve the same HTTP paths, schemas, status codes, authorization,
filtering, pagination, error responses, and OpenAPI operation IDs. Viewset
hooks and decorators must execute in the selected mode with equivalent ordering
and transaction semantics. Sync mode becomes available only after synchronous
serialization, bulk operations, and hook parity are implemented and tested.

## Stability rules

- Public names are documented and exported deliberately; lack of a leading
  underscore alone does not make an internal helper public in version 3.
- Every public API has complete parameter and return annotations. Lazy
  descriptors must expose the resolved value type to static analyzers rather
  than leaking their internal descriptor type.
- Sync and async pairs must have equivalent outcomes, exceptions, hook order,
  and transaction semantics.
- Performance improvements may reduce query counts; regressions require an
  explicit approved contract change.
- Generated schema class names and HTTP OpenAPI contracts remain stable unless
  the migration guide records an intentional break.
- No public operation returns different broad result types based on optional
  arguments.
