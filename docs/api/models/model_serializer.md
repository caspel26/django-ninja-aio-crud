# :material-file-document-edit: Model Serializer

`ModelSerializer` is a powerful abstract mixin for Django models that centralizes schema generation and serialization configuration directly on the model class.

## :material-format-list-bulleted: Overview

**Goals:**

- :material-content-copy: Eliminate duplication between Model and separate serializer classes
- :material-hook: Provide clear extension points (sync + async hooks, custom synthetic fields)
- :material-auto-fix: Auto-generate Ninja schemas from model metadata
- :material-link-variant: Support nested serialization for relationships

**Key Features:**

- :material-playlist-plus: Declarative schema configuration via inner classes
- :material-sync: Automatic CRUD schema generation
- :material-file-tree: Nested relationship handling
- :material-hook: Sync and async lifecycle hooks
- :material-pencil-plus: Custom field support (computed/synthetic fields)

---

## :material-rocket-launch: Quick Start

```python
from django.db import models
from ninja_aio.models import ModelSerializer

class User(ModelSerializer):
    username = models.CharField(max_length=150, unique=True)
    email = models.EmailField(unique=True)

    class CreateSerializer:
        fields = ["username", "email"]

    class ReadSerializer:
        fields = ["id", "username", "email"]

    def __str__(self):
        return self.username
```

---

## :material-playlist-plus: Inner Configuration Classes

### CreateSerializer

Describes how to build a create (input) schema for a model.

**Attributes:**

| Attribute   | Type                     | Description                                                                                                                       |
| ----------- | ------------------------ | --------------------------------------------------------------------------------------------------------------------------------- |
| `fields`    | `list[str \| tuple]`     | REQUIRED model field names for creation. Can also include inline custom tuples (see below)                                        |
| `optionals` | `list[tuple[str, type]]` | Optional model fields: `(field_name, python_type)`                                                                                |
| `customs`   | `list[tuple]`            | Synthetic inputs. Tuple forms: `(name, type)` = required (no default); `(name, type, default)` = optional (literal or callable)   |
| `excludes`  | `list[str]`              | Field names rejected on create                                                                                                    |

**Example:**

```python
class User(ModelSerializer):
    username = models.CharField(max_length=150)
    email = models.EmailField()
    password = models.CharField(max_length=128)
    bio = models.TextField(blank=True)

    class CreateSerializer:
        fields = ["username", "email", "password"]
        optionals = [
            ("bio", str),
        ]
        customs = [
            ("password_confirm", str),          # required (no default) equivalent of ("password_confirm", str, ...)
            ("send_welcome_email", bool, True), # optional with default
        ]
        excludes = ["id", "created_at"]
```

**Inline Custom Fields:**

You can also define custom fields directly in the `fields` list as tuples:

```python
class User(ModelSerializer):
    class CreateSerializer:
        fields = [
            "username",
            "email",
            ("password_confirm", str),          # 2-tuple: required
            ("send_welcome", bool, True),       # 3-tuple: optional with default
        ]
```

This is equivalent to using the separate `customs` list but keeps field definitions together.

**Resolution Order for `customs`:**

1. Payload value (if provided)
2. If default present and callable → invoked
3. Literal default (if provided)
4. If tuple was only (name, type) and no value supplied → validation error (required)

**Conceptual Equivalent (django-ninja):**

```python
# Without ModelSerializer
from ninja import ModelSchema

class UserIn(ModelSchema):
    class Meta:
        model = User
        fields = ["username", "email"]
```

### ReadSerializer

Describes how to build a read (output) schema for a model.

**Attributes**

| Attribute        | Type                 | Description |
|------------------|----------------------|-------------|
| `fields`         | `list[str \| tuple]` | **REQUIRED.** Model fields / related names explicitly included in the read (output) schema. Can also include inline custom tuples. |
| `excludes`       | `list[str]`          | Fields / related names to always omit (takes precedence over `fields` and `optionals`). Use for sensitive or noisy data (e.g., passwords, internal flags). |
| `customs`        | `list[tuple]`        | Computed / synthetic output values. Tuple formats:<br>• `(name, type)` = required resolvable attribute (object attribute or property). Serialization error if not resolvable.<br>• `(name, type, default)` = optional; default may be a callable (`lambda obj: ...`) or a literal value. |
| `relations_as_id`| `list[str]`          | Relation fields to serialize as IDs instead of nested objects. Works with forward FK, forward O2O, reverse FK, reverse O2O, and M2M relations. |

**Example:**

```python
class User(ModelSerializer):
    first_name = models.CharField(max_length=150)
    last_name = models.CharField(max_length=150)
    email = models.EmailField()
    password = models.CharField(max_length=128)

    class ReadSerializer:
        fields = ["id", "first_name", "last_name", "email", "created_at"]
        excludes = ["password"]
        customs = [
            ("full_name", str, lambda obj: f"{obj.first_name} {obj.last_name}".strip()),
            ("is_premium", bool, lambda obj: obj.subscription.is_active if hasattr(obj, 'subscription') else False),
        ]
```

**Resolution Order for `customs`:**

1. Attribute / property on instance
2. Callable default (if provided)
3. Literal default
4. If required (2‑tuple) and still unresolved → error

**Generated Output:**

```json
{
  "id": 1,
  "first_name": "John",
  "last_name": "Doe",
  "email": "john@example.com",
  "created_at": "2024-01-15T10:30:00Z",
  "full_name": "John Doe",
  "is_premium": true
}
```

### DetailSerializer

Describes how to build a detail (single object) output schema. Use this when you want the retrieve endpoint to return more fields than the list endpoint.

**Fallback Behavior:** `DetailSerializer` supports **per-field-type fallback** to `ReadSerializer`. Each attribute (`fields`, `customs`, `optionals`, `excludes`) is checked independently:

- If `DetailSerializer.fields` is empty → uses `ReadSerializer.fields`
- If `DetailSerializer.customs` is empty → uses `ReadSerializer.customs`
- If `DetailSerializer.optionals` is empty → uses `ReadSerializer.optionals`
- If `DetailSerializer.excludes` is empty → uses `ReadSerializer.excludes`

This allows partial overrides: define only `DetailSerializer.fields` while inheriting `customs` from `ReadSerializer`.

**Attributes:**

| Attribute   | Type                     | Description                                                                   |
| ----------- | ------------------------ | ----------------------------------------------------------------------------- |
| `fields`    | `list[str \| tuple]`     | Model fields to include in detail view. Can include inline custom tuples. Falls back to ReadSerializer.fields if empty |
| `excludes`  | `list[str]`              | Fields to exclude from detail view (falls back to ReadSerializer.excludes if empty) |
| `customs`   | `list[tuple]`            | Computed fields: `(name, type)` required; `(name, type, default)` optional (falls back to ReadSerializer.customs if empty) |
| `optionals` | `list[tuple[str, type]]` | Optional output fields (falls back to ReadSerializer.optionals if empty) |

**Example:**

```python
class Article(ModelSerializer):
    title = models.CharField(max_length=200)
    summary = models.TextField()
    content = models.TextField()
    author = models.ForeignKey(User, on_delete=models.CASCADE)
    tags = models.ManyToManyField(Tag)
    view_count = models.IntegerField(default=0)

    class ReadSerializer:
        # List view: minimal fields for performance
        fields = ["id", "title", "summary", "author"]
        customs = [
            ("word_count", int, lambda obj: len(obj.content.split())),
        ]

    class DetailSerializer:
        # Detail view: all fields including expensive relations
        # customs inherited from ReadSerializer (word_count)
        fields = ["id", "title", "summary", "content", "author", "tags", "view_count"]
```

**Generated Output (List):**

```json
[
  {"id": 1, "title": "Getting Started", "summary": "...", "author": {...}, "word_count": 500},
  {"id": 2, "title": "Advanced Topics", "summary": "...", "author": {...}, "word_count": 1200}
]
```

**Generated Output (Detail):**

```json
{
  "id": 1,
  "title": "Getting Started",
  "summary": "...",
  "content": "Full article content here...",
  "author": {...},
  "tags": [{"id": 1, "name": "python"}, {"id": 2, "name": "django"}],
  "view_count": 1234,
  "word_count": 500
}
```

**Example with Custom Override:**

```python
class Article(ModelSerializer):
    # ... fields ...

    class ReadSerializer:
        fields = ["id", "title", "summary"]
        customs = [("word_count", int, lambda obj: len(obj.content.split()))]

    class DetailSerializer:
        fields = ["id", "title", "summary", "content"]
        # Override customs - reading_time instead of word_count
        customs = [("reading_time", int, lambda obj: len(obj.content.split()) // 200)]
```

### UpdateSerializer

Describes how to build an update (partial/full) input schema.

**Attributes:**

| Attribute   | Type                     | Description                                                                   |
| ----------- | ------------------------ | ----------------------------------------------------------------------------- |
| `fields`    | `list[str \| tuple]`     | REQUIRED fields for update (rarely used). Can include inline custom tuples    |
| `optionals` | `list[tuple[str, type]]` | Updatable optional fields (typical for PATCH)                                 |
| `customs`   | `list[tuple]`            | Instruction fields: `(name, type)` required; `(name, type, default)` optional |
| `excludes`  | `list[str]`              | Immutable fields that cannot be updated                                       |

**Example:**

```python
class User(ModelSerializer):
    username = models.CharField(max_length=150, unique=True)
    email = models.EmailField()
    bio = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)

    class UpdateSerializer:
        optionals = [
            ("email", str),
            ("bio", str),
            ("is_active", bool),
        ]
        customs = [
            ("reset_password", bool, False),  # optional flag
            ("rotate_token", bool),          # required instruction
        ]
        excludes = ["username", "created_at", "id"]
```

**Usage (PATCH request):**

```json
{
  "email": "newemail@example.com",
  "bio": "Updated bio",
  "reset_password": true
}
```

---

## :material-auto-fix: Schema Generation

### Auto-Generated Schemas

ModelSerializer automatically generates five schema types:

| Method                       | Schema Type        | Purpose                              |
| ---------------------------- | ------------------ | ------------------------------------ |
| `generate_create_s()`        | Input ("In")       | POST endpoint payload                |
| `generate_update_s()`        | Input ("Patch")    | PATCH/PUT endpoint payload           |
| `generate_read_s(depth=1)`   | Output ("Out")     | List response with nested relations  |
| `generate_detail_s(depth=1)` | Output ("Detail")  | Single object response (retrieve)    |
| `generate_related_s()`       | Output ("Related") | Compact nested representation        |

**Example:**

```python
class User(ModelSerializer):
    username = models.CharField(max_length=150)
    email = models.EmailField()

    class CreateSerializer:
        fields = ["username", "email"]

    class ReadSerializer:
        fields = ["id", "username", "email"]

# Auto-generate schemas
UserCreateSchema = User.generate_create_s()
UserReadSchema = User.generate_read_s()
UserDetailSchema = User.generate_detail_s()  # Falls back to read schema if DetailSerializer not defined
UserUpdateSchema = User.generate_update_s()
UserRelatedSchema = User.generate_related_s()
```

### Nested Relationship Handling

ModelSerializer automatically serializes relationships if the related model is also a ModelSerializer.

#### ForeignKey (Forward)

```python
class Profile(ModelSerializer):
    bio = models.TextField()

    class ReadSerializer:
        fields = ["id", "bio"]

class User(ModelSerializer):
    username = models.CharField(max_length=150)
    profile = models.ForeignKey(Profile, on_delete=models.CASCADE)

    class ReadSerializer:
        fields = ["id", "username", "profile"]
```

**Output:**

```json
{
  "id": 1,
  "username": "john_doe",
  "profile": {
    "id": 10,
    "bio": "Software developer"
  }
}
```

#### ManyToMany

```python
class Tag(ModelSerializer):
    name = models.CharField(max_length=50)

    class ReadSerializer:
        fields = ["id", "name"]

class Article(ModelSerializer):
    title = models.CharField(max_length=200)
    tags = models.ManyToManyField(Tag, related_name="articles")

    class ReadSerializer:
        fields = ["id", "title", "tags"]
```

**Output:**

```json
{
  "id": 1,
  "title": "Getting Started",
  "tags": [
    { "id": 1, "name": "python" },
    { "id": 2, "name": "django" }
  ]
}
```

#### Reverse Relationships

```python
class Author(ModelSerializer):
    name = models.CharField(max_length=200)

    class ReadSerializer:
        fields = ["id", "name", "books"]  # Reverse FK

class Book(ModelSerializer):
    title = models.CharField(max_length=200)
    author = models.ForeignKey(Author, on_delete=models.CASCADE, related_name="books")

    class ReadSerializer:
        fields = ["id", "title"]
```

**Output:**

```json
{
  "id": 1,
  "name": "J.K. Rowling",
  "books": [
    { "id": 1, "title": "Harry Potter" },
    { "id": 2, "title": "Fantastic Beasts" }
  ]
}
```

#### Relations as ID

Use `relations_as_id` to serialize relation fields as IDs instead of nested objects. This is useful for:

- Reducing response payload size
- Avoiding circular serialization
- Performance optimization when nested data isn't needed
- API designs where clients fetch related data separately

**Supported Relations:**

| Relation Type      | Output Type       | Example Value        |
|--------------------|-------------------|----------------------|
| Forward FK         | `PK_TYPE \| None` | `5` or `null`        |
| Forward O2O        | `PK_TYPE \| None` | `3` or `null`        |
| Reverse FK         | `list[PK_TYPE]`   | `[1, 2, 3]`          |
| Reverse O2O        | `PK_TYPE \| None` | `7` or `null`        |
| M2M (forward)      | `list[PK_TYPE]`   | `[1, 2]`             |
| M2M (reverse)      | `list[PK_TYPE]`   | `[4, 5, 6]`          |

**Note:** `PK_TYPE` is automatically detected from the related model's primary key field. Supported types include `int` (default), `UUID`, `str`, and any other Django primary key type.

**Example:**

```python
class Author(ModelSerializer):
    name = models.CharField(max_length=200)

    class ReadSerializer:
        fields = ["id", "name", "books"]
        relations_as_id = ["books"]  # Serialize as list of IDs

class Book(ModelSerializer):
    title = models.CharField(max_length=200)
    author = models.ForeignKey(Author, on_delete=models.CASCADE, related_name="books")

    class ReadSerializer:
        fields = ["id", "title", "author"]
        relations_as_id = ["author"]  # Serialize as ID
```

**Output (Author):**

```json
{
  "id": 1,
  "name": "J.K. Rowling",
  "books": [1, 2, 3]
}
```

**Output (Book):**

```json
{
  "id": 1,
  "title": "Harry Potter",
  "author": 1
}
```

**M2M Example:**

```python
class Tag(ModelSerializer):
    name = models.CharField(max_length=50)

    class ReadSerializer:
        fields = ["id", "name", "articles"]
        relations_as_id = ["articles"]  # Reverse M2M as IDs

class Article(ModelSerializer):
    title = models.CharField(max_length=200)
    tags = models.ManyToManyField(Tag, related_name="articles")

    class ReadSerializer:
        fields = ["id", "title", "tags"]
        relations_as_id = ["tags"]  # Forward M2M as IDs
```

**Output (Article):**

```json
{
  "id": 1,
  "title": "Getting Started with Django",
  "tags": [1, 2, 5]
}
```

**UUID Primary Key Example:**

When models use UUID primary keys, the output type is automatically `UUID`:

```python
import uuid
from django.db import models
from ninja_aio.models import ModelSerializer

class Author(ModelSerializer):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=200)

    class ReadSerializer:
        fields = ["id", "name", "books"]
        relations_as_id = ["books"]

class Book(ModelSerializer):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(max_length=200)
    author = models.ForeignKey(Author, on_delete=models.CASCADE, related_name="books")

    class ReadSerializer:
        fields = ["id", "title", "author"]
        relations_as_id = ["author"]
```

**Output (Author with UUID):**

```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "name": "J.K. Rowling",
  "books": [
    "6ba7b810-9dad-11d1-80b4-00c04fd430c8",
    "6ba7b811-9dad-11d1-80b4-00c04fd430c8"
  ]
}
```

**Output (Book with UUID):**

```json
{
  "id": "6ba7b810-9dad-11d1-80b4-00c04fd430c8",
  "title": "Harry Potter",
  "author": "550e8400-e29b-41d4-a716-446655440000"
}
```

**Query Optimization Note:** When using `relations_as_id`, you should still use `select_related()` for forward relations and `prefetch_related()` for reverse/M2M relations to avoid N+1 queries:

```python
class Article(ModelSerializer):
    # ...

    class QuerySet:
        read = ModelQuerySetSchema(
            select_related=["author"],       # For forward FK
            prefetch_related=["tags"],        # For M2M
        )
```

---

## :material-lightning-bolt: Async Extension Points

### `queryset_request(request)`

Filter queryset based on request context (user, permissions, tenant, etc.).

```python
class Article(ModelSerializer):
    title = models.CharField(max_length=200)
    author = models.ForeignKey(User, on_delete=models.CASCADE)
    is_published = models.BooleanField(default=False)

    @classmethod
    async def queryset_request(cls, request):
        qs = cls.objects.select_related('author').all()

        # Non-authenticated users see only published
        if not request.auth:
            return qs.filter(is_published=True)

        # Authors see their own + published
        return qs.filter(
            models.Q(author=request.auth) | models.Q(is_published=True)
        )
```

### `post_create()`

Execute async logic after object creation.

```python
class User(ModelSerializer):
    email = models.EmailField()

    async def post_create(self):
        # Send welcome email
        from myapp.tasks import send_welcome_email
        await send_welcome_email(self.email)

        # Create related objects
        await Profile.objects.acreate(user=self)

        # Log creation
        await AuditLog.objects.acreate(
            action="user_created",
            user_id=self.id
        )
```

### `custom_actions(payload)`

React to synthetic/custom fields from the payload.

```python
class User(ModelSerializer):
    password = models.CharField(max_length=128)

    class CreateSerializer:
        fields = ["username", "email", "password"]
        customs = [
            ("password_confirm", str, None),
            ("send_welcome_email", bool, True),
        ]

    async def custom_actions(self, payload: dict):
        # Validate password confirmation
        if "password_confirm" in payload:
            if payload["password_confirm"] != self.password:
                raise ValueError("Passwords do not match")

        # Send welcome email if requested
        if payload.get("send_welcome_email", True):
            await send_email(self.email, "Welcome!")
```

---

## :material-hook: Sync Lifecycle Hooks

### Save Hooks

```python
class User(ModelSerializer):
    username = models.CharField(max_length=150)
    slug = models.SlugField(unique=True, blank=True)

    def before_save(self):
        """Executed before every save (create + update)"""
        if not self.slug:
            self.slug = slugify(self.username)

    def on_create_before_save(self):
        """Executed only on creation, before save"""
        self.set_password(self.password)  # Hash password

    def after_save(self):
        """Executed after every save"""
        cache.delete(f"user:{self.id}")

    def on_create_after_save(self):
        """Executed only after creation"""
        send_welcome_email_sync(self.email)
```

**Execution Order:**

```
CREATE:
1. on_create_before_save()
2. before_save()
3. super().save()
4. on_create_after_save()
5. after_save()

UPDATE:
1. before_save()
2. super().save()
3. after_save()
```

### Delete Hook

```python
class User(ModelSerializer):

    def on_delete(self):
        """Executed after object deletion"""
        # Clean up related data
        logger.info(f"User {self.username} deleted")

        # Remove from cache
        cache.delete(f"user:{self.id}")

        # Archive data
        ArchivedUser.objects.create(
            username=self.username,
            deleted_at=timezone.now()
        )
```

---

## :material-wrench: Utility Methods

### `has_changed(field)`

Check if a field value has changed compared to database.

```python
class Article(ModelSerializer):
    title = models.CharField(max_length=200)
    status = models.CharField(max_length=20)

    def before_save(self):
        if self.has_changed('status'):
            if self.status == 'published':
                self.published_at = timezone.now()
                notify_subscribers(self)
```

### `verbose_name_path_resolver()`

Get slugified plural verbose name for URL routing.

```python
class BlogPost(ModelSerializer):
    class Meta:
        verbose_name_plural = "blog posts"

# Returns: "blog-posts"
path = BlogPost.verbose_name_path_resolver()
```

---

## :material-cog-sync: ModelUtil

Helper class for async CRUD operations with ModelSerializer.

### Overview

```python
from ninja_aio.models import ModelUtil

util = ModelUtil(User)
```

**Key Responsibilities:**

- Introspect model metadata
- Normalize inbound/outbound payloads
- Handle FK resolution and base64 decoding
- Prefetch reverse relations
- Invoke serializer hooks

### Key Methods

#### `get_object(request, pk=None, filters=None, getters=None)`

Fetch single object or queryset with optimized queries.

```python
# Get single object
user = await util.get_object(request, pk=1)

# Get with filters
active_users = await util.get_object(
    request,
    filters={"is_active": True}
)

# Get with custom lookup
user = await util.get_object(
    request,
    getters={"email": "john@example.com"}
)
```

**Features:**

- Automatic `select_related()` and `prefetch_related()`
- Respects `queryset_request()` filtering
- Raises `SerializeError` (404) if not found

#### `parse_input_data(request, data)`

Convert incoming schema to model-ready dict.

**Transformations:**

1. Strips custom fields (stored separately)
2. Removes optional fields with `None` value
3. Decodes BinaryField (base64 → bytes)
4. Resolves FK IDs to model instances

```python
from ninja import Schema

class UserCreateSchema(Schema):
    username: str
    email: str
    profile_id: int
    avatar: str  # base64 for BinaryField
    send_welcome: bool  # custom field

data = UserCreateSchema(
    username="john",
    email="john@example.com",
    profile_id=5,
    avatar="iVBORw0KG...",  # base64
    send_welcome=True
)

payload, customs = await util.parse_input_data(request, data)

# payload = {
#     "username": "john",
#     "email": "john@example.com",
#     "profile": <Profile instance>,
#     "avatar": b'\x89PNG\r\n...'
# }
# customs = {"send_welcome": True}
```

#### `parse_output_data(request, data)`

Post-process serialized output for consistency.

**Transformations:**

1. Replaces nested FK dicts with actual instances
2. Rewrites nested FK keys to `<field>_id` format

```python
# Before
{
    "id": 1,
    "author": {"id": 10, "profile": {"id": 5}}
}

# After parse_output_data
{
    "id": 1,
    "author": <Author instance>,
    "author_id": 10,
    "profile_id": 5
}
```

#### CRUD Operations

##### `create_s(request, data, obj_schema)`

```python
user_data = UserCreateSchema(username="john", email="john@example.com")
result = await util.create_s(request, user_data, UserReadSchema)

# Executes:
# 1. parse_input_data (normalize)
# 2. Model.objects.acreate()
# 3. custom_actions(customs)
# 4. post_create()
# 5. read_s (serialize response)
```

##### `read_s(request, obj, obj_schema)`

```python
user = await User.objects.aget(id=1)
result = await util.read_s(request, user, UserReadSchema)
# Returns parsed dict ready for API response
```

##### `update_s(request, data, pk, obj_schema)`

```python
update_data = UserUpdateSchema(email="newemail@example.com")
result = await util.update_s(request, update_data, 1, UserReadSchema)

# Executes:
# 1. get_object(pk)
# 2. parse_input_data
# 3. Update changed fields
# 4. custom_actions(customs)
# 5. obj.asave()
# 6. read_s (serialize updated object)
```

##### `delete_s(request, pk)`

```python
await util.delete_s(request, 1)
# Returns None
```

### Error Handling

```python
from ninja_aio.exceptions import SerializeError

try:
    user = await util.get_object(request, pk=999)
except SerializeError as e:
    # e.details = {"user": "not found"}
    # e.status_code = 404
    pass

try:
    await util.create_s(request, bad_data, UserReadSchema)
except SerializeError as e:
    # e.details = {"avatar": "Invalid base64"}
    # e.status_code = 400
    pass
```

---

## :material-code-braces: Complete Example

```python
from django.db import models
from ninja_aio.models import ModelSerializer
from django.utils.text import slugify

class Category(ModelSerializer):
    name = models.CharField(max_length=100)
    slug = models.SlugField(unique=True, blank=True)

    class CreateSerializer:
        fields = ["name"]

    class ReadSerializer:
        fields = ["id", "name", "slug"]

    class UpdateSerializer:
        optionals = [("name", str)]

    def before_save(self):
        if not self.slug:
            self.slug = slugify(self.name)

class Author(ModelSerializer):
    name = models.CharField(max_length=200)
    email = models.EmailField(unique=True)
    bio = models.TextField(blank=True)

    class CreateSerializer:
        fields = ["name", "email"]
        optionals = [("bio", str)]

    class ReadSerializer:
        fields = ["id", "name", "email", "bio"]
        customs = [
            ("post_count", int, lambda obj: obj.articles.count()),
        ]

    class UpdateSerializer:
        optionals = [
            ("name", str),
            ("email", str),
            ("bio", str),
        ]

class Article(ModelSerializer):
    title = models.CharField(max_length=200)
    slug = models.SlugField(unique=True)
    content = models.TextField()
    author = models.ForeignKey(Author, on_delete=models.CASCADE, related_name="articles")
    category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True)
    tags = models.ManyToManyField('Tag', related_name="articles")
    is_published = models.BooleanField(default=False)
    views = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class CreateSerializer:
        fields = ["title", "slug", "content", "author", "category"]
        customs = [
            ("notify_subscribers", bool, True),
        ]

    class ReadSerializer:
        fields = [
            "id", "title", "slug", "content",
            "author", "category", "tags",
            "is_published", "views", "created_at"
        ]

    class UpdateSerializer:
        optionals = [
            ("title", str),
            ("content", str),
            ("category", int),
            ("is_published", bool),
        ]
        excludes = ["slug", "author", "created_at"]

    @classmethod
    async def queryset_request(cls, request):
        qs = cls.objects.select_related('author', 'category').prefetch_related('tags')

        if not request.auth:
            return qs.filter(is_published=True)

        return qs.filter(
            models.Q(author=request.auth) | models.Q(is_published=True)
        )

    async def post_create(self):
        await AuditLog.objects.acreate(
            action="article_created",
            article_id=self.id,
            author_id=self.author_id
        )

    async def custom_actions(self, payload: dict):
        if payload.get("notify_subscribers"):
            await notify_new_article(self)

    def before_save(self):
        if self.has_changed('is_published') and self.is_published:
            self.published_at = timezone.now()

class Tag(ModelSerializer):
    name = models.CharField(max_length=50, unique=True)

    class ReadSerializer:
        fields = ["id", "name"]
```

---

## :material-pencil-plus: Custom Fields Normalization

Custom tuples are normalized by `ModelSerializer.get_custom_fields()` to `(name, python_type, default)`.

Accepted forms:

- `(name, type)` -> stored with `default = Ellipsis` (treated as required)
- `(name, type, default)` -> default kept (callable or literal)

Invalid lengths raise `ValueError`.

Example mix:

```python
class CreateSerializer:
    customs = [
        ("password_confirm", str),           # required
        ("send_welcome", bool, True),        # optional
        ("initial_quota", int, lambda: 100)  # optional callable
    ]
```

At runtime:

```python
# Normalized
[
  ("password_confirm", str, Ellipsis),
  ("send_welcome", bool, True),
  ("initial_quota", int, <function ...>)
]
```

Required customs (Ellipsis) must be provided in input (create/update) or resolvable (read) or an error is raised.

## :material-alert-circle: Error Cases

| Situation                                    | Result              |
| -------------------------------------------- | ------------------- |
| 1‑item or 4‑item tuple                       | ValueError          |
| Missing required custom (2‑tuple) in payload | Validation error    |
| Unresolvable required read custom            | Serialization error |

## :material-shield-star: Best Practices

1. **Always exclude sensitive fields:**

   ```python
   class ReadSerializer:
       excludes = ["password", "secret_key", "internal_id"]
   ```

2. **Use optionals for PATCH operations:**

   ```python
   class UpdateSerializer:
       optionals = [("email", str), ("bio", str)]  # Partial updates
   ```

3. **Leverage customs for computed data:**

   ```python
   customs = [
       ("full_name", str, lambda obj: f"{obj.first_name} {obj.last_name}"),
   ]
   ```

4. **Optimize queries in queryset_request:**

   ```python
   @classmethod
   async def queryset_request(cls, request):
       return cls.objects.select_related('author').prefetch_related('tags')
   ```

5. **Keep hooks focused:**
   ```python
   async def post_create(self):
       # Do ONE thing well
       await send_welcome_email(self.email)
   ```

## :material-bookshelf: See Also

<div class="grid cards" markdown>

-   :material-cog-sync:{ .lg .middle } **ModelUtil**

    ---

    [:octicons-arrow-right-24: Deep dive](model_util.md)

-   :material-check-decagram:{ .lg .middle } **Validators**

    ---

    [:octicons-arrow-right-24: Field & model validators](validators.md)

-   :material-view-grid:{ .lg .middle } **APIViewSet**

    ---

    [:octicons-arrow-right-24: Using with ViewSets](../views/api_view_set.md)

-   :material-shield-lock:{ .lg .middle } **Authentication**

    ---

    [:octicons-arrow-right-24: Securing endpoints](../authentication.md)

</div>
