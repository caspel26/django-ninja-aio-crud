# Model Serializer

`ModelSerializer` is a powerful abstract mixin for Django models that centralizes schema generation and serialization configuration directly on the model class.

## Overview

**Goals:**

- Eliminate duplication between Model and separate serializer classes
- Provide clear extension points (sync + async hooks, custom synthetic fields)
- Auto-generate Ninja schemas from model metadata
- Support nested serialization for relationships

**Key Features:**

- Declarative schema configuration via inner classes
- Automatic CRUD schema generation
- Nested relationship handling
- Sync and async lifecycle hooks
- Custom field support (computed/synthetic fields)

## Quick Start

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

## Inner Configuration Classes

### CreateSerializer

Describes how to build a create (input) schema for a model.

**Attributes:**

| Attribute   | Type                     | Description                                                                                                                       |
| ----------- | ------------------------ | --------------------------------------------------------------------------------------------------------------------------------- |
| `fields`    | `list[str]`              | REQUIRED model field names for creation                                                                                           |
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

| Attribute  | Type            | Description |
|-----------|-----------------|-------------|
| `fields`   | `list[str]`     | **REQUIRED.** Model fields / related names explicitly included in the read (output) schema. |
| `excludes` | `list[str]`     | Fields / related names to always omit (takes precedence over `fields` and `optionals`). Use for sensitive or noisy data (e.g., passwords, internal flags). |
| `customs`  | `list[tuple]`   | Computed / synthetic output values. Tuple formats:<br>• `(name, type)` = required resolvable attribute (object attribute or property). Serialization error if not resolvable.<br>• `(name, type, default)` = optional; default may be a callable (`lambda obj: ...`) or a literal value. |

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

### UpdateSerializer

Describes how to build an update (partial/full) input schema.

**Attributes:**

| Attribute   | Type                     | Description                                                                   |
| ----------- | ------------------------ | ----------------------------------------------------------------------------- |
| `fields`    | `list[str]`              | REQUIRED fields for update (rarely used)                                      |
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

## Schema Generation

### Auto-Generated Schemas

ModelSerializer automatically generates four schema types:

| Method                     | Schema Type        | Purpose                        |
| -------------------------- | ------------------ | ------------------------------ |
| `generate_create_s()`      | Input ("In")       | POST endpoint payload          |
| `generate_update_s()`      | Input ("Patch")    | PATCH/PUT endpoint payload     |
| `generate_read_s(depth=1)` | Output ("Out")     | Response with nested relations |
| `generate_related_s()`     | Output ("Related") | Compact nested representation  |

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

## Async Extension Points

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

## Sync Lifecycle Hooks

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

## Utility Methods

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

## ModelUtil

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

## Complete Example

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

## Custom Fields Normalization

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

## Error Cases

| Situation                                    | Result              |
| -------------------------------------------- | ------------------- |
| 1‑item or 4‑item tuple                       | ValueError          |
| Missing required custom (2‑tuple) in payload | Validation error    |
| Unresolvable required read custom            | Serialization error |

## Best Practices

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

## See Also

- [Model Util](model_util.md) - Deep dive into ModelUtil
- [API ViewSet](../views/api_view_set.md) - Using ModelSerializer with ViewSets
- [Authentication](../authentication.md) - Securing endpoints
