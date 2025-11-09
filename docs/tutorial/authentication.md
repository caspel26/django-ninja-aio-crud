# Step 3: Add Authentication

In this step, you'll learn how to secure your API with JWT authentication and implement role-based access control.

## What You'll Learn

- Setting up JWT authentication
- Protecting endpoints
- Implementing role-based access
- Creating login/register endpoints
- Testing authenticated requests

## Prerequisites

Make sure you've completed:
- [Step 1: Define Your Model](model.md)
- [Step 2: Create CRUD Views](crud.md)

## Setting Up JWT Keys

### Generate RSA Keys (Recommended for Production)

```bash
# Generate private key
openssl genrsa -out private_key.pem 2048

# Generate public key
openssl rsa -in private_key.pem -pubout -out public_key.pem
```

### Store Keys Securely

```python
# settings.py
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

# JWT Settings
JWT_PRIVATE_KEY_PATH = os.path.join(BASE_DIR, 'private_key.pem')
JWT_PUBLIC_KEY_PATH = os.path.join(BASE_DIR, 'public_key.pem')

# Read keys
with open(JWT_PUBLIC_KEY_PATH, 'r') as f:
    JWT_PUBLIC_KEY = f.read()

with open(JWT_PRIVATE_KEY_PATH, 'r') as f:
    JWT_PRIVATE_KEY = f.read()

# Token expiration (in seconds)
JWT_ACCESS_TOKEN_EXPIRE = 60 * 15  # 15 minutes
JWT_REFRESH_TOKEN_EXPIRE = 60 * 60 * 24 * 7  # 7 days

# JWT Claims
JWT_ISSUER = "https://your-api.com"
JWT_AUDIENCE = "your-api"
```

!!! warning "Security"
    Never commit your private key to version control! Add `private_key.pem` to your `.gitignore`.

## Create User Model

Update your User model to work with authentication:

```python
# models.py
from django.contrib.auth.models import AbstractUser
from django.db import models
from ninja_aio.models import ModelSerializer


class User(AbstractUser, ModelSerializer):
    email = models.EmailField(unique=True)
    bio = models.TextField(blank=True)
    avatar = models.URLField(blank=True)

    class ReadSerializer:
        fields = ["id", "username", "email", "first_name", "last_name", "bio", "avatar"]
        excludes = ["password"]

    class CreateSerializer:
        fields = ["username", "email", "password", "first_name", "last_name"]
        optionals = [("bio", str), ("avatar", str)]

    class UpdateSerializer:
        optionals = [
            ("first_name", str),
            ("last_name", str),
            ("bio", str),
            ("avatar", str),
        ]
        excludes = ["username", "email", "password"]

    def __str__(self):
        return self.username


# Update Article model to use custom User
class Article(ModelSerializer):
    # ... existing fields ...
    author = models.ForeignKey(
        "User",  # Use string reference
        on_delete=models.CASCADE,
        related_name="articles"
    )
    # ... rest of model ...
```

### Configure Django to Use Custom User

```python
# settings.py
AUTH_USER_MODEL = 'myapp.User'  # Replace 'myapp' with your app name
```

### Run Migrations

```bash
python manage.py makemigrations
python manage.py migrate
```

## Create Authentication Class

```python
# auth.py
from ninja_aio.auth import AsyncJwtBearer
from joserfc import jwk
from django.conf import settings
from .models import User


class JWTAuth(AsyncJwtBearer):
    # Import public key for verification
    jwt_public = jwk.RSAKey.import_key(settings.JWT_PUBLIC_KEY)
    jwt_alg = "RS256"

    # Validate required claims
    claims = {
        "iss": {"essential": True, "value": settings.JWT_ISSUER},
        "aud": {"essential": True, "value": settings.JWT_AUDIENCE},
        "sub": {"essential": True},  # User ID
    }

    async def auth_handler(self, request):
        """
        Called after token validation.
        Returns the user object that will be attached to request.auth
        """
        # Get user ID from token
        user_id = self.dcd.claims.get("sub")

        try:
            # Fetch user from database
            user = await User.objects.aget(id=user_id, is_active=True)
            return user
        except User.DoesNotExist:
            return False
```

## Create Token Generation Helper

```python
# utils.py
from datetime import datetime, timedelta
import jwt
from django.conf import settings


def create_access_token(user_id: int, **extra_claims) -> str:
    """Generate JWT access token"""
    now = datetime.utcnow()

    payload = {
        "sub": str(user_id),
        "iss": settings.JWT_ISSUER,
        "aud": settings.JWT_AUDIENCE,
        "iat": now,
        "exp": now + timedelta(seconds=settings.JWT_ACCESS_TOKEN_EXPIRE),
        **extra_claims
    }

    token = jwt.encode(
        payload,
        settings.JWT_PRIVATE_KEY,
        algorithm="RS256"
    )

    return token


def create_refresh_token(user_id: int) -> str:
    """Generate JWT refresh token"""
    now = datetime.utcnow()

    payload = {
        "sub": str(user_id),
        "iss": settings.JWT_ISSUER,
        "aud": settings.JWT_AUDIENCE,
        "iat": now,
        "exp": now + timedelta(seconds=settings.JWT_REFRESH_TOKEN_EXPIRE),
        "type": "refresh"
    }

    token = jwt.encode(
        payload,
        settings.JWT_PRIVATE_KEY,
        algorithm="RS256"
    )

    return token
```

## Create Login/Register Endpoints

```python
# views.py
from ninja_aio import NinjaAIO
from ninja import Schema
from ninja_aio.exceptions import SerializeError
from django.contrib.auth.hashers import make_password, check_password
from .models import User
from .utils import create_access_token, create_refresh_token
from .auth import JWTAuth

api = NinjaAIO(title="Blog API", version="1.0.0")


# Schemas for authentication
class RegisterSchema(Schema):
    username: str
    email: str
    password: str
    first_name: str = ""
    last_name: str = ""


class LoginSchema(Schema):
    username: str
    password: str


class TokenResponse(Schema):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


class UserResponse(Schema):
    id: int
    username: str
    email: str
    first_name: str
    last_name: str


# Register endpoint
@api.post("/auth/register/", response=TokenResponse)
async def register(request, data: RegisterSchema):
    """Register a new user"""
    # Check if username exists
    if await User.objects.filter(username=data.username).aexists():
        raise SerializeError(
            {"username": "Username already taken"},
            status_code=400
        )

    # Check if email exists
    if await User.objects.filter(email=data.email).aexists():
        raise SerializeError(
            {"email": "Email already registered"},
            status_code=400
        )

    # Create user
    user = await User.objects.acreate(
        username=data.username,
        email=data.email,
        password=make_password(data.password),
        first_name=data.first_name,
        last_name=data.last_name,
    )

    # Generate tokens
    access_token = create_access_token(user.id)
    refresh_token = create_refresh_token(user.id)

    from django.conf import settings
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "expires_in": settings.JWT_ACCESS_TOKEN_EXPIRE
    }


# Login endpoint
@api.post("/auth/login/", response=TokenResponse)
async def login(request, data: LoginSchema):
    """Login user"""
    try:
        user = await User.objects.aget(username=data.username)
    except User.DoesNotExist:
        raise SerializeError(
            {"detail": "Invalid credentials"},
            status_code=401
        )

    # Check password
    if not check_password(data.password, user.password):
        raise SerializeError(
            {"detail": "Invalid credentials"},
            status_code=401
        )

    # Check if user is active
    if not user.is_active:
        raise SerializeError(
            {"detail": "Account is disabled"},
            status_code=401
        )

    # Generate tokens
    access_token = create_access_token(user.id)
    refresh_token = create_refresh_token(user.id)

    from django.conf import settings
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "expires_in": settings.JWT_ACCESS_TOKEN_EXPIRE
    }


# Get current user
@api.get("/auth/me/", response=UserResponse, auth=JWTAuth())
async def me(request):
    """Get current authenticated user"""
    user = request.auth
    return {
        "id": user.id,
        "username": user.username,
        "email": user.email,
        "first_name": user.first_name,
        "last_name": user.last_name,
    }


# Refresh token
@api.post("/auth/refresh/", response=TokenResponse)
async def refresh(request, refresh_token: str):
    """Refresh access token"""
    import jwt
    from django.conf import settings

    try:
        # Decode refresh token
        payload = jwt.decode(
            refresh_token,
            settings.JWT_PUBLIC_KEY,
            algorithms=["RS256"],
            audience=settings.JWT_AUDIENCE,
            issuer=settings.JWT_ISSUER
        )

        # Check token type
        if payload.get("type") != "refresh":
            raise SerializeError(
                {"detail": "Invalid token type"},
                status_code=401
            )

        user_id = int(payload.get("sub"))

        # Generate new tokens
        new_access_token = create_access_token(user_id)
        new_refresh_token = create_refresh_token(user_id)

        return {
            "access_token": new_access_token,
            "refresh_token": new_refresh_token,
            "expires_in": settings.JWT_ACCESS_TOKEN_EXPIRE
        }

    except jwt.ExpiredSignatureError:
        raise SerializeError(
            {"detail": "Refresh token expired"},
            status_code=401
        )
    except jwt.InvalidTokenError:
        raise SerializeError(
            {"detail": "Invalid refresh token"},
            status_code=401
        )
```

## Protect Your ViewSets

Now let's add authentication to your CRUD endpoints:

```python
# views.py
from ninja_aio.views import APIViewSet
from .models import Article
from .auth import JWTAuth

api = NinjaAIO(title="Blog API", version="1.0.0")


class ArticleViewSet(APIViewSet):
    model = Article
    api = api

    # Public read, authenticated write
    get_auth = None  # List and retrieve are public
    post_auth = [JWTAuth()]  # Create requires auth
    patch_auth = [JWTAuth()]  # Update requires auth
    delete_auth = [JWTAuth()]  # Delete requires auth


ArticleViewSet().add_views_to_route()
```

### Set Author Automatically

Modify the Article model to set the author from the authenticated user:

```python
# models.py
class Article(ModelSerializer):
    # ... existing fields ...

    @classmethod
    async def queryset_request(cls, request):
        """Filter articles based on authentication"""
        qs = cls.objects.select_related('author', 'category').prefetch_related('tags')

        # Show all published articles
        # Plus user's own drafts if authenticated
        if request.auth:
            from django.db.models import Q
            return qs.filter(
                Q(is_published=True) | Q(author=request.auth)
            )

        return qs.filter(is_published=True)

    async def custom_actions(self, payload: dict):
        """Set author from request"""
        # This is called during creation
        if hasattr(self, '_request') and self._request.auth:
            self.author = self._request.auth
            await self.asave(update_fields=['author'])

        # Call parent
        await super().custom_actions(payload)
```

## Role-Based Access Control

Create different authentication classes for different roles:

```python
# auth.py
from ninja_aio.auth import AsyncJwtBearer
from joserfc import jwk
from django.conf import settings
from .models import User


class JWTAuth(AsyncJwtBearer):
    """Base JWT authentication"""
    jwt_public = jwk.RSAKey.import_key(settings.JWT_PUBLIC_KEY)
    jwt_alg = "RS256"
    claims = {
        "iss": {"essential": True, "value": settings.JWT_ISSUER},
        "aud": {"essential": True, "value": settings.JWT_AUDIENCE},
        "sub": {"essential": True},
    }

    async def auth_handler(self, request):
        user_id = self.dcd.claims.get("sub")
        try:
            user = await User.objects.aget(id=user_id, is_active=True)
            return user
        except User.DoesNotExist:
            return False


class AdminAuth(JWTAuth):
    """Requires admin/staff privileges"""

    async def auth_handler(self, request):
        user = await super().auth_handler(request)

        if not user.is_staff:
            return False

        return user


class SuperuserAuth(JWTAuth):
    """Requires superuser privileges"""

    async def auth_handler(self, request):
        user = await super().auth_handler(request)

        if not user.is_superuser:
            return False

        return user
```

### Apply Role-Based Auth

```python
# views.py
from .auth import JWTAuth, AdminAuth


class ArticleViewSet(APIViewSet):
    model = Article
    api = api

    # Public read
    get_auth = None

    # Regular users can create
    post_auth = [JWTAuth()]

    # Regular users can update (own articles)
    patch_auth = [JWTAuth()]

    # Only admins can delete
    delete_auth = [AdminAuth()]


class UserViewSet(APIViewSet):
    model = User
    api = api

    # Only admins can manage users
    auth = [AdminAuth()]


ArticleViewSet().add_views_to_route()
UserViewSet().add_views_to_route()
```

## Ownership Validation

Ensure users can only edit their own articles:

```python
# views.py
class ArticleViewSet(APIViewSet):
    model = Article
    api = api

    get_auth = None
    post_auth = [JWTAuth()]
    patch_auth = [JWTAuth()]
    delete_auth = [JWTAuth()]

    def views(self):
        # Override update to check ownership
        @self.router.patch("/{pk}/")
        async def update(request, pk: int, data: Article.generate_update_s()):
            """Update article (owner or admin only)"""
            try:
                article = await Article.objects.aget(pk=pk)
            except Article.DoesNotExist:
                raise SerializeError({"article": "not found"}, status_code=404)

            # Check ownership (unless admin)
            user = request.auth
            if article.author_id != user.id and not user.is_staff:
                raise SerializeError(
                    {"detail": "You can only edit your own articles"},
                    status_code=403
                )

            # Update article
            from ninja_aio.models import ModelUtil
            util = ModelUtil(Article)
            schema = Article.generate_read_s()

            return await util.update_s(request, article, data, schema)

        # Override delete to check ownership
        @self.router.delete("/{pk}/")
        async def delete(request, pk: int):
            """Delete article (owner or admin only)"""
            try:
                article = await Article.objects.aget(pk=pk)
            except Article.DoesNotExist:
                raise SerializeError({"article": "not found"}, status_code=404)

            # Check ownership (unless admin)
            user = request.auth
            if article.author_id != user.id and not user.is_staff:
                raise SerializeError(
                    {"detail": "You can only delete your own articles"},
                    status_code=403
                )

            await article.adelete()
            return {"message": "Article deleted successfully"}


ArticleViewSet().add_views_to_route()
```

## Testing Authentication

### Register a User

```bash
curl -X POST http://localhost:8000/api/auth/register/ \
  -H "Content-Type: application/json" \
  -d '{
    "username": "johndoe",
    "email": "john@example.com",
    "password": "secure_password_123",
    "first_name": "John",
    "last_name": "Doe"
  }'
```

**Response:**

```json
{
  "access_token": "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9...",
  "refresh_token": "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "expires_in": 900
}
```

### Login

```bash
curl -X POST http://localhost:8000/api/auth/login/ \
  -H "Content-Type: application/json" \
  -d '{
    "username": "johndoe",
    "password": "secure_password_123"
  }'
```

### Get Current User

```bash
curl http://localhost:8000/api/auth/me/ \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

### Create Article (Authenticated)

```bash
curl -X POST http://localhost:8000/api/article/ \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "title": "My Article",
    "content": "Article content...",
    "category": 1
  }'
```

### Refresh Token

```bash
curl -X POST http://localhost:8000/api/auth/refresh/ \
  -H "Content-Type: application/json" \
  -d '{"refresh_token": "YOUR_REFRESH_TOKEN"}'
```

## Error Responses

### Missing Token

```bash
curl http://localhost:8000/api/article/ \
  -X POST \
  -H "Content-Type: application/json" \
  -d '{"title": "Test"}'
```

**Response (401):**

```json
{
  "detail": "Unauthorized"
}
```

### Invalid Token

```bash
curl http://localhost:8000/api/article/ \
  -H "Authorization: Bearer invalid_token" \
  -X POST
```

**Response (401):**

```json
{
  "detail": "Invalid token"
}
```

### Expired Token

**Response (401):**

```json
{
  "detail": "Token has expired"
}
```

### Insufficient Permissions

```bash
# Regular user trying to delete
curl -X DELETE http://localhost:8000/api/article/1/ \
  -H "Authorization: Bearer USER_TOKEN"
```

**Response (403):**

```json
{
  "detail": "Admin privileges required"
}
```

## Using Swagger UI with Auth

The Swagger UI at `/api/docs` has built-in authentication support:

1. Click the **"Authorize"** button at the top
2. Enter your token: `Bearer YOUR_ACCESS_TOKEN`
3. Click **"Authorize"**
4. Now all requests will include the token

## Custom Claims

Add custom claims to your tokens:

```python
# utils.py
def create_access_token(user_id: int, **extra_claims) -> str:
    """Generate JWT access token with custom claims"""
    now = datetime.utcnow()

    # Add custom claims
    payload = {
        "sub": str(user_id),
        "iss": settings.JWT_ISSUER,
        "aud": settings.JWT_AUDIENCE,
        "iat": now,
        "exp": now + timedelta(seconds=settings.JWT_ACCESS_TOKEN_EXPIRE),
        **extra_claims
    }

    return jwt.encode(payload, settings.JWT_PRIVATE_KEY, algorithm="RS256")


# In login endpoint
async def login(request, data: LoginSchema):
    # ... authentication logic ...

    # Create token with custom claims
    access_token = create_access_token(
        user.id,
        email=user.email,
        username=user.username,
        is_staff=user.is_staff,
        permissions=["read:articles", "write:articles"]
    )

    # ...
```

Access custom claims in your auth handler:

```python
class JWTAuth(AsyncJwtBearer):
    # ...

    async def auth_handler(self, request):
        user_id = self.dcd.claims.get("sub")
        user = await User.objects.aget(id=user_id, is_active=True)

        # Attach custom claims to request
        request.user_permissions = self.dcd.claims.get("permissions", [])
        request.user_email = self.dcd.claims.get("email")

        return user
```

## Best Practices

1. **Use RSA keys in production:**
   ```python
   jwt_public = jwk.RSAKey.import_key(settings.JWT_PUBLIC_KEY)
   jwt_alg = "RS256"
   ```

2. **Keep access tokens short-lived:**
   ```python
   JWT_ACCESS_TOKEN_EXPIRE = 60 * 15  # 15 minutes
   ```

3. **Use refresh tokens:**
   ```python
   JWT_REFRESH_TOKEN_EXPIRE = 60 * 60 * 24 * 7  # 7 days
   ```

4. **Validate claims:**
   ```python
   claims = {
       "iss": {"essential": True, "value": "your-issuer"},
       "aud": {"essential": True, "value": "your-api"},
   }
   ```

5. **Hash passwords properly:**
   ```python
   from django.contrib.auth.hashers import make_password
   password = make_password(raw_password)
   ```

6. **Check user ownership:**
   ```python
   if article.author_id != user.id and not user.is_staff:
       raise SerializeError({"detail": "Forbidden"}, status_code=403)
   ```

7. **Use HTTPS in production** - Never send tokens over HTTP

8. **Implement token blacklist** for logout functionality

## Next Steps

Now that you have authentication set up, let's customize schemas in [Step 4: Filtering & Pagination](filtering.md).

!!! success "What You've Learned"
    - ✅ Setting up JWT authentication
    - ✅ Creating login/register endpoints
    - ✅ Protecting API endpoints
    - ✅ Implementing role-based access control
    - ✅ Validating ownership
    - ✅ Testing authenticated requests

## See Also

- [Authentication API Reference](../api/authentication.md) - Complete authentication documentation
- [APIViewSet Auth Options](../api/views/api_view_set.md#authentication-attributes) - ViewSet authentication options
