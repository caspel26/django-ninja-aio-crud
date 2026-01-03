# Authentication

Django Ninja Aio CRUD provides built-in async JWT authentication support with flexible configuration and easy integration with your API endpoints.

## Overview

Authentication in Django Ninja Aio CRUD:
- **Fully Async** - No blocking operations
- **JWT-Based** - Industry-standard JSON Web Tokens
- **Type-Safe** - Proper type hints and validation
- **Flexible** - Per-endpoint or global authentication
- **Customizable** - Override default behavior
- **RSA/HMAC Support** - Multiple signing algorithms

## Quick Start

### 1. Create Authentication Class

```python
# auth.py
from ninja_aio.auth import AsyncJwtBearer
from joserfc import jwk

PUBLIC_KEY = """-----BEGIN PUBLIC KEY-----
MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEA...
-----END PUBLIC KEY-----"""


class JWTAuth(AsyncJwtBearer):
    jwt_public = jwk.RSAKey.import_key(PUBLIC_KEY)
    claims = {
        "iss": {"essential": True, "value": "https://your-issuer.com"},
        "aud": {"essential": True, "value": "your-api"}
    }

    async def auth_handler(self, request):
        user_id = self.dcd.claims.get("sub")
        user = await User.objects.aget(id=user_id)
        return user
```

### 2. Apply to ViewSet

```python
# views.py
from ninja_aio import NinjaAIO
from ninja_aio.views import APIViewSet
from .models import Article
from .auth import JWTAuth

api = NinjaAIO()


class ArticleViewSet(APIViewSet):
    model = Article
    api = api
    auth = [JWTAuth()]  # Apply to all endpoints


ArticleViewSet().add_views_to_route()
```

### 3. Make Authenticated Request

```bash
curl -H "Authorization: Bearer eyJhbGciOiJSUzI1NiIs..." \
     http://localhost:8000/api/article/
```

## AsyncJwtBearer

Base class for JWT authentication.

### Class Definition

```python
from ninja_aio.auth import AsyncJwtBearer
from joserfc import jwk

class MyAuth(AsyncJwtBearer):
    jwt_public: jwk.RSAKey | jwk.OctKey  # Public key for verification
    jwt_alg: str = "RS256"  # Signing algorithm
    claims: dict = {}  # Required claims

    async def auth_handler(self, request):
        # Return user object or custom auth context
        pass
```

### Required Attributes

#### `jwt_public`

Public key for JWT verification.

**RSA Key (Recommended):**

```python
from joserfc import jwk

PUBLIC_KEY = """-----BEGIN PUBLIC KEY-----
MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEA...
-----END PUBLIC KEY-----"""

class JWTAuth(AsyncJwtBearer):
    jwt_public = jwk.RSAKey.import_key(PUBLIC_KEY)
    jwt_alg = "RS256"
```

**HMAC Key (Shared Secret):**

```python
from joserfc import jwk

SECRET = "your-secret-key"

class JWTAuth(AsyncJwtBearer):
    jwt_public = jwk.OctKey.import_key(SECRET)
    jwt_alg = "HS256"
```

**From JWK (JSON Web Key):**

```python
import json
from joserfc import jwk

jwk_data = {
    "kty": "RSA",
    "n": "xGOr-H7A-PWgPZ...",
    "e": "AQAB",
    "alg": "RS256",
    "use": "sig"
}

class JWTAuth(AsyncJwtBearer):
    jwt_public = jwk.RSAKey.import_key(jwk_data)
```

#### `jwt_alg`

JWT signing algorithm (optional, default: `"RS256"`).

**Supported Algorithms:**

| Algorithm | Type | Description |
|-----------|------|-------------|
| `RS256` | RSA | RSA Signature with SHA-256 (recommended) |
| `RS384` | RSA | RSA Signature with SHA-384 |
| `RS512` | RSA | RSA Signature with SHA-512 |
| `HS256` | HMAC | HMAC with SHA-256 |
| `HS384` | HMAC | HMAC with SHA-384 |
| `HS512` | HMAC | HMAC with SHA-512 |
| `ES256` | ECDSA | ECDSA with SHA-256 |
| `ES384` | ECDSA | ECDSA with SHA-384 |
| `ES512` | ECDSA | ECDSA with SHA-512 |

```python
class JWTAuth(AsyncJwtBearer):
    jwt_public = jwk.RSAKey.import_key(PUBLIC_KEY)
    jwt_alg = "RS512"  # Use RS512 instead of default RS256
```

#### `claims`

Dictionary of required JWT claims for validation.

**Claim Options:**

| Key | Type | Description |
|-----|------|-------------|
| `essential` | `bool` | Claim must be present |
| `value` | `Any` | Exact value required |
| `values` | `list` | One of the values required |

**Examples:**

```python
class JWTAuth(AsyncJwtBearer):
    jwt_public = jwk.RSAKey.import_key(PUBLIC_KEY)
    claims = {
        # Issuer must be exact match
        "iss": {
            "essential": True,
            "value": "https://auth.example.com"
        },
        # Audience must be one of these
        "aud": {
            "essential": True,
            "values": ["api-prod", "api-staging"]
        },
        # Subject must be present (any value)
        "sub": {
            "essential": True
        },
        # Optional claim with default
        "scope": {
            "essential": False,
            "value": "read"
        }
    }
```

### Required Methods

#### `auth_handler()`

Process authenticated request and return user/auth context.

**Signature:**

```python
async def auth_handler(self, request: HttpRequest) -> Any
```

**Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `request` | `HttpRequest` | Django HTTP request |

**Return Value:**

Object attached to `request.auth` (typically User instance).

**Access to JWT Data:**

- `self.dcd` - Decoded JWT claims
- `self.dcd.claims` - Claims dictionary
- `self.dcd.header` - JWT header

**Examples:**

**Return User Object:**

```python
async def auth_handler(self, request):
    user_id = self.dcd.claims.get("sub")
    user = await User.objects.aget(id=user_id)
    return user

# In view
async def my_view(request):
    user = request.auth  # User instance
    print(user.username)
```

**Return Custom Context:**

```python
async def auth_handler(self, request):
    return {
        "user_id": self.dcd.claims.get("sub"),
        "email": self.dcd.claims.get("email"),
        "roles": self.dcd.claims.get("roles", []),
        "scopes": self.dcd.claims.get("scope", "").split()
    }

# In view
async def my_view(request):
    context = request.auth
    print(context["user_id"])
    print(context["roles"])
```

**With Additional Validation:**

```python
async def auth_handler(self, request):
    user_id = self.dcd.claims.get("sub")

    # Check if user exists and is active
    try:
        user = await User.objects.aget(id=user_id, is_active=True)
    except User.DoesNotExist:
        return False

    # Check subscription status
    if not await user.has_active_subscription():
        return False

    return user
```

**With Caching:**

```python
from django.core.cache import cache

async def auth_handler(self, request):
    user_id = self.dcd.claims.get("sub")

    # Try cache first
    cache_key = f"user:{user_id}"
    user = cache.get(cache_key)

    if user is None:
        user = await User.objects.aget(id=user_id)
        cache.set(cache_key, user, 300)  # Cache 5 minutes

    return user
```

## Authentication Levels

### Global Authentication

Apply authentication to all endpoints in a ViewSet:

```python
class ArticleViewSet(APIViewSet):
    model = Article
    api = api
    auth = [JWTAuth()]  # All endpoints require auth
```

**Generated Endpoints:**

| Method | Endpoint | Auth Required |
|--------|----------|---------------|
| GET | `/article/` | ✓ |
| POST | `/article/` | ✓ |
| GET | `/article/{id}` | ✓ |
| PATCH | `/article/{id}/` | ✓ |
| DELETE | `/article/{id}/` | ✓ |

### Per-Method Authentication

Apply authentication to specific HTTP methods:

```python
class ArticleViewSet(APIViewSet):
    model = Article
    api = api
    get_auth = None  # GET endpoints public
    post_auth = [JWTAuth()]  # POST requires auth
    patch_auth = [JWTAuth()]  # PATCH requires auth
    delete_auth = [JWTAuth()]  # DELETE requires auth
```

**Generated Endpoints:**

| Method | Endpoint | Auth Required |
|--------|----------|---------------|
| GET | `/article/` | ✗ (public) |
| POST | `/article/` | ✓ |
| GET | `/article/{id}` | ✗ (public) |
| PATCH | `/article/{id}/` | ✓ |
| DELETE | `/article/{id}/` | ✓ |

### Custom View Authentication

Apply authentication to custom views:

```python
class ArticleViewSet(APIViewSet):
    model = Article
    api = api
    auth = None  # CRUD endpoints public

    def views(self):
        # Authenticated custom endpoint
        @self.router.post("/publish/{pk}/", auth=JWTAuth())
        async def publish(request, pk: int):
            article = await Article.objects.aget(pk=pk)
            article.is_published = True
            await article.asave()
            return {"message": "Article published"}

        # Public custom endpoint
        @self.router.get("/stats/")
        async def stats(request):
            total = await Article.objects.acount()
            return {"total": total}
```

### Mixed Authentication

Combine different authentication strategies:

```python
class AdminAuth(AsyncJwtBearer):
    jwt_public = jwk.RSAKey.import_key(PUBLIC_KEY)

    async def auth_handler(self, request):
        user_id = self.dcd.claims.get("sub")
        user = await User.objects.aget(id=user_id)
        if not user.is_staff:
            return False
        return user


class ArticleViewSet(APIViewSet):
    model = Article
    api = api
    get_auth = None  # Public read
    post_auth = [JWTAuth()]  # Regular user can create
    patch_auth = [JWTAuth()]  # Regular user can edit own
    delete_auth = [AdminAuth()]  # Only admin can delete
```

## Advanced Usage

### Role-Based Access Control (RBAC)

```python
class RoleAuth(AsyncJwtBearer):
    jwt_public = jwk.RSAKey.import_key(PUBLIC_KEY)
    required_roles: list[str] = []

    async def auth_handler(self, request):
        user_id = self.dcd.claims.get("sub")
        user = await User.objects.aget(id=user_id)

        # Check roles
        user_roles = self.dcd.claims.get("roles", [])
        if self.required_roles:
            if not any(role in user_roles for role in self.required_roles):
                return False

        request.user_roles = user_roles
        return user


class AdminAuth(RoleAuth):
    required_roles = ["admin"]


class EditorAuth(RoleAuth):
    required_roles = ["editor", "admin"]


class ArticleViewSet(APIViewSet):
    model = Article
    api = api
    get_auth = None
    post_auth = [EditorAuth()]  # Editors and admins
    delete_auth = [AdminAuth()]  # Only admins
```

### Permission-Based Access

```python
class PermissionAuth(AsyncJwtBearer):
    jwt_public = jwk.RSAKey.import_key(PUBLIC_KEY)
    required_permissions: list[str] = []

    async def auth_handler(self, request):
        user_id = self.dcd.claims.get("sub")
        user = await User.objects.select_related('role').aget(id=user_id)

        # Get user permissions
        permissions = await sync_to_async(list)(
            user.role.permissions.values_list('code', flat=True)
        )

        # Check permissions
        if self.required_permissions:
            missing = set(self.required_permissions) - set(permissions)
            if missing:
                return False
        request.permissions = permissions
        return user


class ArticleCreateAuth(PermissionAuth):
    required_permissions = ["article.create"]


class ArticleDeleteAuth(PermissionAuth):
    required_permissions = ["article.delete"]


class ArticleViewSet(APIViewSet):
    model = Article
    api = api
    post_auth = [ArticleCreateAuth()]
    delete_auth = [ArticleDeleteAuth()]
```

### Tenant/Organization Isolation

```python
class TenantAuth(AsyncJwtBearer):
    jwt_public = jwk.RSAKey.import_key(PUBLIC_KEY)

    async def auth_handler(self, request):
        user_id = self.dcd.claims.get("sub")
        tenant_id = self.dcd.claims.get("tenant_id")

        if not tenant_id:
            return False

        user = await User.objects.aget(
            id=user_id,
            tenant_id=tenant_id,
            is_active=True
        )

        request.tenant_id = tenant_id
        return user


class Article(ModelSerializer):
    title = models.CharField(max_length=200)
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE)

    @classmethod
    async def queryset_request(cls, request):
        # Automatically filter by tenant
        qs = cls.objects.all()
        if hasattr(request, 'tenant_id'):
            qs = qs.filter(tenant_id=request.tenant_id)
        return qs


class ArticleViewSet(APIViewSet):
    model = Article
    api = api
    auth = [TenantAuth()]
```

### Scope-Based Access

```python
class ScopeAuth(AsyncJwtBearer):
    jwt_public = jwk.RSAKey.import_key(PUBLIC_KEY)
    required_scopes: list[str] = []

    async def auth_handler(self, request):
        # Get scopes from token
        scope_str = self.dcd.claims.get("scope", "")
        scopes = scope_str.split()

        # Check required scopes
        if self.required_scopes:
            missing = set(self.required_scopes) - set(scopes)
            if missing:
                return False

        user_id = self.dcd.claims.get("sub")
        user = await User.objects.aget(id=user_id)

        request.scopes = scopes
        return user


class ReadAuth(ScopeAuth):
    required_scopes = ["read"]


class WriteAuth(ScopeAuth):
    required_scopes = ["write"]


class ArticleViewSet(APIViewSet):
    model = Article
    api = api
    get_auth = [ReadAuth()]  # read scope
    post_auth = [WriteAuth()]  # write scope
    patch_auth = [WriteAuth()]  # write scope
    delete_auth = [WriteAuth()]  # write scope
```

### API Key Authentication

For machine-to-machine communication:

```python
from ninja.security import APIKeyHeader


class APIKeyAuth(APIKeyHeader):
    param_name = "X-API-Key"

    async def authenticate(self, request, key):
        try:
            api_key = await APIKey.objects.select_related('user').aget(
                key=key,
                is_active=True
            )

            # Check expiration
            if api_key.expires_at and api_key.expires_at < timezone.now():
                return None

            # Update last used
            api_key.last_used_at = timezone.now()
            await api_key.asave(update_fields=['last_used_at'])

            return api_key.user
        except APIKey.DoesNotExist:
            return None


class ArticleViewSet(APIViewSet):
    model = Article
    api = api
    auth = [APIKeyAuth()]
```

**Usage:**

```bash
curl -H "X-API-Key: your-api-key-here" \
     http://localhost:8000/api/article/
```

### Multiple Authentication Methods

Support both JWT and API Key:

```python
class ArticleViewSet(APIViewSet):
    model = Article
    api = api
    auth = [JWTAuth(), APIKeyAuth()]  # Either JWT or API Key
```

Django Ninja will try both methods; if either succeeds, the request is authenticated.

## Best Practices

1. **Use RSA (asymmetric) keys for production:**
   ```python
   jwt_public = jwk.RSAKey.import_key(PUBLIC_KEY)
   jwt_alg = "RS256"
   ```

2. **Validate essential claims:**
   ```python
   claims = {
       "iss": {"essential": True, "value": "your-issuer"},
       "aud": {"essential": True, "value": "your-api"},
       "sub": {"essential": True}
   }
   ```

3. **Keep tokens short-lived:**
   ```python
   # In your token issuer
   exp = datetime.utcnow() + timedelta(minutes=15)  # 15 min access token
   ```

4. **Cache user objects:**
   ```python
   async def auth_handler(self, request):
       user_id = self.dcd.claims.get("sub")
       cache_key = f"user:{user_id}"
       user = cache.get(cache_key)
       if not user:
           user = await User.objects.aget(id=user_id)
           cache.set(cache_key, user, 300)
       return user
   ```

5. **Log authentication failures:**
   ```python
   async def auth_handler(self, request):
       try:
           user = await User.objects.aget(id=user_id)
           return user
       except User.DoesNotExist:
           logger.warning(f"Auth failed for user_id: {user_id}")
           return False
   ```

6. **Use different auth for different operations:**
   ```python
   class ArticleViewSet(APIViewSet):
       model = Article
       api = api
       get_auth = None  # Public read
       post_auth = [UserAuth()]  # User can create
       delete_auth = [AdminAuth()]  # Only admin can delete
   ```

7. **Implement rate limiting for auth endpoints:**
   ```python
   from ninja.throttling import AnonRateThrottle

   @api.post("/login/", throttle=[AnonRateThrottle('5/minute')])
   async def login(request, credentials: LoginSchema):
       # Login logic
       pass
   ```

## Integration Examples

### With Auth0

```python
import httpx
from joserfc import jwk


class Auth0JWT(AsyncJwtBearer):
    jwt_alg = "RS256"

    def __init__(self):
        super().__init__()
        # Fetch JWKS from Auth0
        self.domain = "your-domain.auth0.com"
        self.audience = "your-api-identifier"

    async def get_jwks(self):
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"https://{self.domain}/.well-known/jwks.json"
            )
            return response.json()

    claims = {
        "iss": {"essential": True, "value": "https://your-domain.auth0.com/"},
        "aud": {"essential": True, "value": "your-api-identifier"}
    }

    async def auth_handler(self, request):
        user_id = self.dcd.claims.get("sub")
        # Extract user info from token or fetch from database
        return {"user_id": user_id, "email": self.dcd.claims.get("email")}
```

### With Keycloak

```python
class KeycloakJWT(AsyncJwtBearer):
    jwt_alg = "RS256"

    def __init__(self):
        super().__init__()
        self.realm_url = "https://keycloak.example.com/realms/your-realm"

    async def get_public_key(self):
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{self.realm_url}")
            data = response.json()
            return jwk.RSAKey.import_key(data["public_key"])

    claims = {
        "iss": {"essential": True, "value": "https://keycloak.example.com/realms/your-realm"},
        "azp": {"essential": True, "value": "your-client-id"}
    }

    async def auth_handler(self, request):
        user_id = self.dcd.claims.get("sub")
        roles = self.dcd.claims.get("realm_access", {}).get("roles", [])
        return {
            "user_id": user_id,
            "roles": roles,
            "email": self.dcd.claims.get("email")
        }
```

### With Firebase

```python
import google.auth.transport.requests
from google.oauth2 import id_token


class FirebaseAuth(HttpBearer):
    def __init__(self):
        self.project_id = "your-firebase-project"

    async def authenticate(self, request, token):
        try:
            # Verify Firebase ID token
            decoded_token = id_token.verify_firebase_token(
                token,
                google.auth.transport.requests.Request(),
                audience=self.project_id
            )

            user_id = decoded_token["uid"]
            user = await User.objects.aget(firebase_uid=user_id)
            return user
        except Exception as e:
            return None
```

## See Also

- [API ViewSet](views/api_view_set.md) - Applying auth to ViewSets
- [Tutorial: Authentication](../tutorial/authentication.md) - Step-by-step guide
- [Model Serializer](models/model_serializer.md) - Filtering by authenticated user

---
