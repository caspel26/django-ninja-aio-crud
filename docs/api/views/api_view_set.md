# APIViewSet

`APIViewSet` auto-generates CRUD + optional Many-to-Many (M2M) endpoints for a Django model (or `ModelSerializer`) with async support, pagination, filtering, per-method authentication, and dynamic schema generation.

## Generated CRUD Endpoints

| Method | Path Pattern | Summary (auto) | Response |
|--------|--------------|----------------|----------|
| POST | `/{base}/` | Create Model | `201 {schema_out}` |
| GET | `/{base}/` | List Models | `200 List[{schema_out}]` (paginated) |
| GET | `/{base}/{pk}` | Retrieve Model | `200 {schema_out}` |
| PATCH | `/{base}/{pk}/` | Update Model | `200 {schema_out}` |
| DELETE | `/{base}/{pk}/` | Delete Model | `204 No Content` |

Notes:
- Retrieve path has no trailing slash; update/delete use trailing slash.
- `{base}` defaults to the model verbose name (lowercased plural) unless `api_route_path` overrides.
- Error responses share a unified schema for codes: 400, 401, 404, 428.

## Core Attributes

| Attribute | Type | Default | Description |
|-----------|------|---------|-------------|
| `model` | `ModelSerializer \| Model` | — | Target model (required) |
| `api` | `NinjaAPI` | — | API instance (required) |
| `schema_in` | `Schema \| None` | `None` (auto) | Create schema override |
| `schema_out` | `Schema \| None` | `None` (auto) | Read/output schema override |
| `schema_update` | `Schema \| None` | `None` (auto) | Update schema override |
| `pagination_class` | `type[AsyncPaginationBase]` | `PageNumberPagination` | Pagination strategy |
| `query_params` | `dict[str, tuple[type, ...]]` | `{}` | Declares filter parameters |
| `disable` | `list[type[VIEW_TYPES]]` | `[]` | Disable view types (`"create"`, `"list"`, `"retrieve"`, `"update"`, `"delete"`, `"all"`) |
| `api_route_path` | `str` | `""` | Base route segment (falls back to resolved verbose name) |
| `list_docs` | `str` | `"List all objects."` | List endpoint description |
| `create_docs` | `str` | `"Create a new object."` | Create endpoint description |
| `retrieve_docs` | `str` | `"Retrieve a specific object by its primary key."` | Retrieve endpoint description |
| `update_docs` | `str` | `"Update an object by its primary key."` | Update endpoint description |
| `delete_docs` | `str` | `"Delete an object by its primary key."` | Delete endpoint description |

## Authentication Attributes

| Attribute | Type | Default | Description |
|-----------|------|---------|-------------|
| `auth` | `list \| None` | `NOT_SET` | Global fallback auth |
| `get_auth` | `list \| None` | `NOT_SET` | Auth for list + retrieve |
| `post_auth` | `list \| None` | `NOT_SET` | Auth for create |
| `patch_auth` | `list \| None` | `NOT_SET` | Auth for update |
| `delete_auth` | `list \| None` | `NOT_SET` | Auth for delete |
| `m2m_auth` | `list \| None` | `NOT_SET` | Default auth for M2M endpoints |

Resolution: per-method auth overrides `auth` unless set to `NOT_SET`. `None` makes endpoint public.

## Automatic Schema Generation

If `model` inherits `ModelSerializer`, the following are auto-created:
- `schema_out` from `ReadSerializer`
- `schema_in` from `CreateSerializer`
- `schema_update` from `UpdateSerializer`

Otherwise supply them manually.

## Filtering

Declare parameter types via `query_params`:

```python
query_params = {
    "is_active": (bool, None),
    "role": (str, None),
    "search": (str, None),
}
```

Override:

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

## Many-to-Many Relations

`m2m_relations: list[tuple[ModelSerializer | Model, str, str, list]]`

Tuple formats supported (variable length):
1. `(RelatedModel, related_name)`
2. `(RelatedModel, related_name, custom_path)`
3. `(RelatedModel, related_name, custom_path, per_relation_auth)`

Resolution rules:
- If `custom_path` missing or empty → auto path from related model verbose name.
- If per-relation auth omitted → falls back to `m2m_auth`.
- `None` auth makes that relation’s endpoints public.

Generated per relation (if enabled):
| Method | Path | Feature |
|--------|------|---------|
| GET | `/{base}/{pk}/{rel_path}` | List related objects (paginated) |
| POST | `/{base}/{pk}/{rel_path}/` | Add/remove operations |

Add/remove schema:
- If both `m2m_add` and `m2m_remove` are True: payload `{ "add": [ids], "remove": [ids] }`
- If only add: `{ "add": [ids] }`
- If only remove: `{ "remove": [ids] }`

Response format:
```json
{
  "results": { "count": X, "details": ["..."] },
  "errors": { "count": Y, "details": ["..."] }
}
```

### M2M Example

```python
class ArticleViewSet(APIViewSet):
    model = Article
    api = api
    m2m_relations = [
        (Tag, "tags"),                                 # auto path + m2m_auth
        (Category, "categories", "article-categories"),# custom path
        (User, "authors", "co-authors", [AdminAuth()]) # custom path + custom auth
    ]
    m2m_auth = [JWTAuth()]      # fallback for first two
    m2m_add = True
    m2m_remove = True
    m2m_get = True
```

### Controlling Operations

```python
m2m_add = False       # disable additions
m2m_remove = True
m2m_get = True
```

## Custom Views

Add extra endpoints by overriding `views()`:

```python
def views(self):
    @self.router.get("/stats/", response={200: GenericMessageSchema})
    async def stats(request):
        total = await self.model.objects.acount()
        return {"message": f"Total: {total}"}
```

## Dynamic View Naming

All generated handlers are wrapped with `@unique_view(...)` to ensure stable unique function names (important for schema generation and avoiding collisions).

## Error Codes

Unified error schema for: 400 (validation), 401 (auth), 404 (not found), 428 (precondition).

## Performance Tips

1. Implement `@classmethod async def queryset_request(cls, request)` on `ModelSerializer` to prefetch relations.
2. Use indexes on fields referenced in `query_params`.
3. Keep pagination enabled to prevent large memory usage.
4. Apply selective slicing for expensive searches (`queryset = queryset[:1000]`).

## Minimal Usage

```python
class UserViewSet(APIViewSet):
    model = User
    api = api

UserViewSet().add_views_to_route()
```

## Disable Views

```python
class ReadOnlyUserViewSet(APIViewSet):
    model = User
    api = api
    disable = ["create", "update", "delete"]
```

## Authentication Example

```python
class UserViewSet(APIViewSet):
    model = User
    api = api
    auth = [JWTAuth()]        # default
    get_auth = None           # list/retrieve public
    delete_auth = [AdminAuth()]  # delete restricted
```

## See Also

- [ModelSerializer](../models/model_serializer.md)
- [Authentication](../authentication.md)
- [Pagination](../pagination.md)
- [APIView](api_view.md)