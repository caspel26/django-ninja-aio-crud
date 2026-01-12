# APIViewSet

`APIViewSet` auto-generates async CRUD endpoints and optional Many-to-Many (M2M) endpoints for a Django `Model` or a `ModelSerializer`. It supports dynamic schema generation, per-verb authentication, pagination, list & relation filtering with runtime-built Pydantic schemas, and custom view injection.

## Generated CRUD Endpoints

| Method | Path            | Summary        | Response                           |
| ------ | --------------- | -------------- | ---------------------------------- |
| POST   | `/{base}/`      | Create Model   | `201 schema_out`                   |
| GET    | `/{base}/`      | List Models    | `200 List[schema_out]` (paginated) |
| GET    | `/{base}/{pk}`  | Retrieve Model | `200 schema_out`                   |
| PATCH  | `/{base}/{pk}/` | Update Model   | `200 schema_out`                   |
| DELETE | `/{base}/{pk}/` | Delete Model   | `204 No Content`                   |

Notes:

- Retrieve path typically includes a trailing slash by default (see settings below); update/delete include a trailing slash.
- `{base}` auto-resolves from model verbose name plural (lowercase) unless `api_route_path` is provided.
- Error responses may use a unified generic schema for codes: 400, 401, 404.

### Settings: trailing slash behavior

- NINJA_AIO_APPEND_SLASH (default: True)
  - When True (default, for backward compatibility), retrieve and POST paths includes a trailing slash into CRUD: `/{base}/{pk}/`.
  - When False, retrieve and post paths is generated without a trailing slash: `/{base}/{pk}`.

## Recommended: Decorator-based extra endpoints

Use class method decorators to add non-CRUD endpoints to your ViewSet. This is the preferred way to extend a ViewSet with custom routes. The decorators lazily bind instance methods to the router and ensure correct OpenAPI signatures (no `self` in parameters).

Available decorators (from `ninja_aio.decorators`):

- `@api_get(path, ...)`
- `@api_post(path, ...)`
- `@api_put(path, ...)`
- `@api_patch(path, ...)`
- `@api_delete(path, ...)`
- `@api_options(path, ...)`
- `@api_head(path, ...)`

Example:

```python
from ninja_aio import NinjaAIO
from ninja_aio.views import APIViewSet
from ninja_aio.decorators import api_get, api_post
from .models import Article

api = NinjaAIO(title="Blog API")

@api.viewset(model=Article)
class ArticleViewSet(APIViewSet):
    @api_get("/stats/")
    async def stats(self, request):
        total = await self.model.objects.acount()
        return {"total": total}

    @api_post("/{pk}/publish/")
    async def publish(self, request, pk: int):
        obj = await self.model.objects.aget(pk=pk)
        obj.is_published = True
        await obj.asave()
        return {"message": "published"}
```

Notes:

- Decorators support per-endpoint `auth`, `response`, `tags`, `summary`, `description`, and more.
- Sync methods are executed via `sync_to_async` automatically.
- Signatures and type hints are preserved for OpenAPI (excluding `self`).

## Legacy: views() method (still supported)

The previous pattern of injecting endpoints inside `views()` is still supported, but the decorator-based approach above is now recommended.

```python
class ArticleViewSet(APIViewSet):
    model = Article
    api = api

    def views(self):
        @self.router.get("/stats/")
        async def stats(request):
            total = await self.model.objects.acount()
            return {"total": total}

        @self.router.post("/{pk}/publish/")
        async def publish(request, pk: int):
            obj = await self.model.objects.aget(pk=pk)
            obj.is_published = True
            await obj.asave()
            return {"message": "published"}
```

## Core Attributes

| Attribute                   | Type                          | Default                                            | Description                                                             |
| --------------------------- | ----------------------------- | -------------------------------------------------- | ----------------------------------------------------------------------- |
| `model`                     | `ModelSerializer \| Model`    | —                                                  | Target model (required)                                                 |
| `api`                       | `NinjaAPI`                    | —                                                  | API instance (required)                                                 |
| `serializer_class`          | `Serializer \| None`          | `None`                                             | Serializer class for plain models (alternative to ModelSerializer)      |
| `schema_in`                 | `Schema \| None`              | `None` (auto)                                      | Create input schema override                                            |
| `schema_out`                | `Schema \| None`              | `None` (auto)                                      | Read/output schema override                                             |
| `schema_update`             | `Schema \| None`              | `None` (auto)                                      | Update input schema override                                            |
| `pagination_class`          | `type[AsyncPaginationBase]`   | `PageNumberPagination`                             | Pagination strategy                                                     |
| `query_params`              | `dict[str, tuple[type, ...]]` | `{}`                                               | List endpoint filters definition                                        |
| `disable`                   | `list[type[VIEW_TYPES]]`      | `[]`                                               | Disable CRUD views (`create`,`list`,`retrieve`,`update`,`delete`,`all`) |
| `api_route_path`            | `str`                         | `""`                                               | Base route segment                                                      |
| `list_docs`                 | `str`                         | `"List all objects."`                              | List endpoint description                                               |
| `create_docs`               | `str`                         | `"Create a new object."`                           | Create endpoint description                                             |
| `retrieve_docs`             | `str`                         | `"Retrieve a specific object by its primary key."` | Retrieve endpoint description                                           |
| `update_docs`               | `str`                         | `"Update an object by its primary key."`           | Update endpoint description                                             |
| `delete_docs`               | `str`                         | `"Delete an object by its primary key."`           | Delete endpoint description                                             |
| `m2m_relations`             | `list[M2MRelationSchema]`     | `[]`                                               | M2M relation configs                                                    |
| `m2m_auth`                  | `list \| None`                | `NOT_SET`                                          | Default auth for all M2M endpoints (overridden per relation if set)     |
| `extra_decorators`          | `DecoratorsSchema`            | `DecoratorsSchema()`                               | Custom decorators for CRUD operations                                   |
| `model_verbose_name`        | `str`                         | `""`                                               | Override model verbose name for display                                 |
| `model_verbose_name_plural` | `str`                         | `""`                                               | Override model verbose name plural for display                          |

## Authentication Attributes

| Attribute     | Type           | Default   | Description              |
| ------------- | -------------- | --------- | ------------------------ |
| `auth`        | `list \| None` | `NOT_SET` | Global fallback auth     |
| `get_auth`    | `list \| None` | `NOT_SET` | Auth for list + retrieve |
| `post_auth`   | `list \| None` | `NOT_SET` | Auth for create          |
| `patch_auth`  | `list \| None` | `NOT_SET` | Auth for update          |
| `delete_auth` | `list \| None` | `NOT_SET` | Auth for delete          |

Resolution rules:

- Per-verb auth overrides `auth` when not `NOT_SET`.
- `None` makes the endpoint public (no authentication).
- M2M endpoints use relation-level auth (`m2m_data.auth`) or fall back to `m2m_auth`.

## Transaction Management

Create, update, and delete operations are automatically wrapped in atomic transactions using the `@aatomic` decorator. This ensures that database operations are rolled back on exceptions:

```python
@api.viewset(model=Article)
class ArticleViewSet(APIViewSet):
    pass  # create/update/delete automatically transactional
```

The transaction behavior is applied by default. Custom decorators can be added via `extra_decorators` attribute.

## Automatic Schema Generation

If `model` is a subclass of `ModelSerializerMeta`:

- `schema_out` is generated from `ReadSerializer`
- `schema_in` from `CreateSerializer`
- `schema_update` from `UpdateSerializer`

For plain Django models, you can provide a `serializer_class` (Serializer) instead:

```python
from ninja_aio.models import serializers

class ArticleSerializer(serializers.Serializer):
    class Meta:
        model = models.Article
        schema_in = serializers.SchemaModelConfig(
            fields=["title", "content", "author"]
        )
        schema_out = serializers.SchemaModelConfig(
            fields=["id", "title", "content", "author"]
        )

@api.viewset(model=models.Article)
class ArticleViewSet(APIViewSet):
    serializer_class = ArticleSerializer
```

Otherwise provide schemas manually via `schema_in`, `schema_out`, and `schema_update` attributes.

## List Filtering

Define filters for the list view with `query_params`:

```python
query_params = {
    "is_active": (bool, None),
    "role": (str, None),
    "search": (str, None),
}
```

Override handler:

```python
async def query_params_handler(self, queryset, filters: dict):
    if filters.get("is_active") is not None:
        queryset = queryset.filter(is_active=filters["is_active"])
    if filters.get("role"):
        queryset = queryset.filter(role=filters["role"])
    if filters.get("search"):
        from django.db.models import Q
        s = filters["search"]
        queryset = queryset.filter(Q(username__icontains=s) | Q(email__icontains=s))
    return queryset
```

A dynamic Pydantic model (`FiltersSchema`) is built with `pydantic.create_model` from `query_params`.

## List and Retrieve implementations

List now leverages ModelUtil.get_objects and list_read_s, automatically applying read optimizations and optional filters:

```python
class ArticleViewSet(APIViewSet):
    model = Article
    api = api

    def views(self):
        @self.router.get("/")
        async def list(request, filters: self.filters_schema = None):
            qs = await self.model_util.get_objects(
                request,
                query_data=self._get_query_data(),  # defaults from ModelSerializer.QuerySet.read
                is_for_read=True,
            )
            if filters is not None:
                qs = await self.query_params_handler(qs, filters.model_dump())
            return await self.model_util.list_read_s(self.schema_out, request, qs)
```

Retrieve uses read_s with getters, deriving PK type from the model:

```python
@self.router.get("/{pk}/")
async def retrieve(request, pk: self.path_schema):
    return await self.model_util.read_s(
        self.schema_out,
        request,
        query_data=QuerySchema(getters={"pk": self._get_pk(pk)}),
        is_for_read=True,
    )
```

- Path schema PK type is inferred from the model’s primary key field.

## Many-to-Many Relations

Relations are declared via `M2MRelationSchema` objects (not tuples). Each schema can include:

- `model`: related Django model or ModelSerializer
- `related_name`: attribute name on the main model (e.g. `"tags"`)
- `path`: custom URL segment (optional)
- `auth`: list of auth instances (optional)
- `add`: enable additions (bool)
- `remove`: enable removals (bool)
- `get`: enable GET listing (bool)
- `filters`: dict of `{param_name: (type, default)}` for relation-level filtering
- `related_schema`: optional pre-built schema for the related model (auto-generated if the `model` is a `ModelSerializer`)
- `append_slash`: bool to control trailing slash for the GET relation endpoint path. Defaults to `False` (no trailing slash) for backward compatibility. When `True`, the GET path ends with a trailing slash.

If `path` is empty it falls back to the related model verbose name (lowercase plural).
If `filters` is provided, a per-relation filters schema is auto-generated and exposed on the GET relation endpoint:
`GET /{base}/{pk}/{related_path}?param=value`

Custom filter hook naming convention:
`<related_name>_query_params_handler(self, queryset, filters_dict)`

The M2M helper:

- Returns a paginated list of related items on GET.
- Supports both sync and async custom filter handlers.
- Uses `list_read_s` for related items serialization.

Example filter handler (sync or async):

```python
def tags_query_params_handler(self, queryset, filters_dict):
    name = filters_dict.get("name")
    return queryset.filter(name=name) if name else queryset

# or

async def tags_query_params_handler(self, queryset, filters_dict):
    # perform async lookups if needed, then return queryset
    return queryset
```

Warning: Model support

- You can supply a standard Django `Model` (not a `ModelSerializer`) in `M2MRelationSchema.model`. When doing so you must provide `related_schema` manually:

```python
M2MRelationSchema(
    model=Tag,                # plain django.db.models.Model
    related_name="tags",
    related_schema=TagOut,    # a Pydantic/Ninja Schema you define
    add=True,
    remove=True,
    get=True,
)
```

For `ModelSerializer` models, `related_schema` can be inferred automatically (via internal helpers).

Example with filters:

```python
class UserViewSet(APIViewSet):
    model = User
    api = api
    m2m_relations = [
        M2MRelationSchema(
            model=Tag,
            related_name="tags",
            filters={"name": (str, "")}
        )
    ]

    async def tags_query_params_handler(self, queryset, filters):
        name_filter = filters.get("name")
        if name_filter:
            queryset = queryset.filter(name__icontains=name_filter)
        return queryset
```

### Relation Handlers: GET filters vs POST per-PK resolution

- GET filters handler (per relation):

  - Name: `<related_name>_query_params_handler(self, queryset, filters_dict)`
  - Purpose: apply filters to the related list queryset (GET endpoint).
  - Supports both synchronous and asynchronous functions.

- POST per-PK resolution handler (per relation):
  - Name: `<related_name>_query_handler(self, request, pk, instance)`
  - Purpose: resolve a single related object (for add/remove validation) before mutation.
  - Must return a queryset; the object is resolved with `.afirst()`.
  - Automatic fallback if missing: `ModelUtil(related_model).get_objects(request, ObjectsQuerySchema(filters={"pk": pk}))` + `.afirst()`.

Example:

```python
class MyViewSet(APIViewSet):
    model = Article
    api = api

    async def tags_query_params_handler(self, qs, filters: dict):
        name = filters.get("name")
        return qs.filter(name__icontains=name) if name else qs

    async def tags_query_handler(self, request, pk, instance):
        # allow only tags belonging to the same project as the instance
        return Tag.objects.filter(pk=pk, project_id=instance.project_id)
```

### Endpoint paths and operation naming

- GET relation: `/{base}/{pk}/{rel_path}` by default (no trailing slash). You can enable a trailing slash per relation with `append_slash=True`, resulting in `/{base}/{pk}/{rel_path}/`.
- POST relation: `/{base}/{pk}/{rel_path}/` (always with trailing slash).

Path normalization rules:

- Relation `path` is normalized internally; providing `path` with or without a leading slash produces the same final URL.
  - Example: `path="tags"` or `path="/tags"` both yield `GET /{base}/{pk}/tags` (or `GET /{base}/{pk}/tags/` when `append_slash=True`) and `POST /{base}/{pk}/tags/`.
- If `path` is empty, it falls back to the related model verbose name.

### Request/Response and concurrency

Request bodies:

- Add & Remove: `{ "add": number[], "remove": number[] }`
- Add only: `{ "add": number[] }`
- Remove only: `{ "remove": number[] }`

Standard response (M2MSchemaOut):

```json
{
  "results": { "count": X, "details": ["..."] },
  "errors": { "count": Y, "details": ["..."] }
}
```

- Concurrency: `aadd(...)` and `aremove(...)` run in parallel via `asyncio.gather` when both lists are non-empty.
- Per-PK errors include: object not found, state mismatch (removing non-related, adding already-related).
- Per-PK success messages indicate the executed action.

### Generated M2M Endpoints (per relation)

| Method | Path                       | Feature                                            |
| ------ | -------------------------- | -------------------------------------------------- |
| GET    | `/{base}/{pk}/{rel_path}`  | List related objects (paginated, optional filters) |
| POST   | `/{base}/{pk}/{rel_path}/` | Add/remove related objects                         |

Example:

```python
class ArticleViewSet(APIViewSet):
    model = Article
    api = api
    m2m_relations = [
        M2MRelationSchema(model=Tag, related_name="tags"),
        M2MRelationSchema(model=Category, related_name="categories", path="article-categories"),
        M2MRelationSchema(model=User, related_name="authors", path="co-authors", auth=[AdminAuth()])
    ]
    m2m_auth = [JWTAuth()]  # fallback for relations without custom auth
```

Example with trailing slash on GET relation:

```python
M2MRelationSchema(
    model=Tag,
    related_name="tags",
    filters={"name": (str, "")},
    append_slash=True,  # GET /{base}/{pk}/tags/
)
```

## Custom Views

Preferred (decorators): see the section above.

Legacy (still supported):

```python
def views(self):
    @self.router.get("/stats/", response={200: GenericMessageSchema})
    async def stats(request):
        total = await self.model.objects.acount()
        return {"message": f"Total: {total}"}
```

## Dynamic View Naming

All generated handlers are decorated with `@unique_view(...)` to ensure stable unique function names (prevents collisions and ensures consistent OpenAPI schema generation). Relation endpoints use explicit names like `get_<model>_<rel_path>` and `manage_<model>_<rel_path>`.

## Extra Decorators

Apply custom decorators to specific CRUD operations via the `extra_decorators` attribute:

```python
from ninja_aio.schemas.helpers import DecoratorsSchema
from functools import wraps

def log_operation(func):
    @wraps(func)
    async def wrapper(*args, **kwargs):
        print(f"Calling {func.__name__}")
        return await func(*args, **kwargs)
    return wrapper

@api.viewset(model=Article)
class ArticleViewSet(APIViewSet):
    extra_decorators = DecoratorsSchema(
        create=[log_operation],
        update=[log_operation],
        delete=[log_operation],
    )
```

Available decorator fields:
- `create`: Decorators for create endpoint
- `list`: Decorators for list endpoint
- `retrieve`: Decorators for retrieve endpoint
- `update`: Decorators for update endpoint
- `delete`: Decorators for delete endpoint

## Overridable Hooks

| Hook                                                     | Purpose                         |
| -------------------------------------------------------- | ------------------------------- |
| `views()`                                                | Register custom endpoints       |
| `query_params_handler(queryset, filters)`                | Apply list filters              |
| `<related_name>_query_params_handler(queryset, filters)` | Apply relation-specific filters |

## Error Handling

All CRUD and M2M endpoints may respond with `GenericMessageSchema` for error codes: 400 (validation), 401 (auth), 404 (not found).

## Performance Tips

1. Implement `@classmethod async def queryset_request(cls, request)` in your `ModelSerializer` to prefetch related objects.
2. Use database indexes on filtered fields (`query_params` and relation `filters`).
3. Keep pagination enabled for large datasets.
4. Prefetch reverse relations via `model_util.get_reverse_relations()` (already applied in list view).
5. Limit slice size for expensive searches if needed (`queryset = queryset[:1000]`).

## Minimal Usage

=== "Recommended"
    ````python
    from ninja_aio import NinjaAIO
    from ninja_aio.views import APIViewSet
    from .models import User
    from ninja_aio.decorators import api_get

    api = NinjaAIO(title="My API")

    @api.viewset(model=User)
    class UserViewSet(APIViewSet):
        @api_get("/stats/")
        async def stats(self, request):
            total = await self.model.objects.acount()
            return {"total": total}
    ```

=== "Alternative implementation"
    ```python
    from ninja_aio import NinjaAIO
    from ninja_aio.views import APIViewSet
    from .models import User

    api = NinjaAIO(title="My API")

    class UserViewSet(APIViewSet):
        model = User
        api = api

        def views(self):
            @self.router.get("/stats/")
            async def stats(request):
                total = await self.model.objects.acount()
                return {"total": total}

    UserViewSet().add_views_to_route()
    ```

Note: prefix and tags are optional. If omitted, the base path is inferred from the model verbose name plural and tags default to the model verbose name.

## Disable Selected Views

```python
@api.viewset(model=User)
class ReadOnlyUserViewSet(APIViewSet):
    disable = ["create", "update", "delete"]
```

## Authentication Example

```python
@api.viewset(model=User)
class UserViewSet(APIViewSet):
    auth = [JWTAuth()]      # global fallback
    get_auth = None         # list/retrieve public
    delete_auth = [AdminAuth()]  # delete restricted
```

## Complete M2M + Filters Example

Recommended:

```python
from ninja_aio import NinjaAIO
from ninja_aio.views import APIViewSet
from ninja_aio.models import ModelSerializer
from ninja_aio.decorators import api_get
from django.db import models

api = NinjaAIO(title="My API")

class Tag(ModelSerializer):
    name = models.CharField(max_length=100)
    class ReadSerializer:
        fields = ["id", "name"]

class User(ModelSerializer):
    username = models.CharField(max_length=150)
    tags = models.ManyToManyField(Tag, related_name="users")
    class ReadSerializer:
        fields = ["id", "username", "tags"]

@api.viewset(model=User)
class UserViewSet(APIViewSet):
    query_params = {"search": (str, None)}
    m2m_relations = [
        M2MRelationSchema(
            model=Tag,
            related_name="tags",
            filters={"name": (str, "")},
            add=True,
            remove=True,
            get=True,
        )
    ]

    async def query_params_handler(self, queryset, filters):
        if filters.get("search"):
            from django.db.models import Q
            s = filters["search"]
            return queryset.filter(Q(username__icontains=s))
        return queryset

    async def tags_query_params_handler(self, queryset, filters):
        name_filter = filters.get("name")
        if name_filter:
            queryset = queryset.filter(name__icontains=name_filter)
        return queryset
```

Alternative implementation:

```python
class UserViewSet(APIViewSet):
    model = User
    api = api
    query_params = {"search": (str, None)}
    m2m_relations = [
        M2MRelationSchema(
            model=Tag,
            related_name="tags",
            filters={"name": (str, "")},
            add=True,
            remove=True,
            get=True,
        )
    ]

    async def query_params_handler(self, queryset, filters):
        if filters.get("search"):
            from django.db.models import Q
            s = filters["search"]
            return queryset.filter(Q(username__icontains=s))
        return queryset

    async def tags_query_params_handler(self, queryset, filters):
        name_filter = filters.get("name")
        if name_filter:
            queryset = queryset.filter(name__icontains=name_filter)
        return queryset

UserViewSet().add_views_to_route()
```

## ReadOnlyViewSet

ReadOnlyViewSet enables only list and retrieve endpoints.

```python
@api.viewset(model=MyModel)
class MyModelReadOnlyViewSet(ReadOnlyViewSet):
    pass
```

## WriteOnlyViewSet

WriteOnlyViewSet enables only create, update, and delete endpoints.

```python
@api.viewset(model=MyModel)
class MyModelWriteOnlyViewSet(WriteOnlyViewSet):
    pass
```

## See Also

- [ModelSerializer](../models/model_serializer.md)
- [Authentication](../authentication.md)
- [Pagination](../pagination.md)
- [APIView](api_view.md)
