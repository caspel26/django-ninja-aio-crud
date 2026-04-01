# :material-shield-lock-outline: JWT Authentication and AsyncJwtBearer

This page documents the JWT helpers and the `AsyncJwtBearer` and `AsyncJwtCookie` classes in `ninja_aio/auth.py`, including configuration, validation, and usage in Django Ninja.

## :material-information-outline: Overview

- :material-shield-check: **AsyncJwtBearer** — Asynchronous HTTP Bearer auth that verifies JWTs, validates claims via a registry, and delegates user resolution to `auth_handler`.
- :material-cookie-lock: **AsyncJwtCookie** — Asynchronous cookie-based JWT auth for BFF (Backend for Frontend) patterns. Reads JWTs from HttpOnly cookies with CSRF protection.
- :material-wrench: **Helpers:**
  - :material-key-variant: `validate_key` — Ensures JWK keys are present and of the correct type.
  - :material-check-decagram: `validate_mandatory_claims` — Ensures `iss` and `aud` are present (from settings if not provided).
  - :material-pencil-lock: `encode_jwt` — Signs a JWT with time-based claims (`iat`, `nbf`, `exp`) and mandatory `iss/aud`.
  - :material-lock-open-check: `decode_jwt` — Verifies and decodes a JWT with a public key and allowed algorithms.
  - :material-cookie-plus: `set_jwt_cookie` — Sets a JWT as an HttpOnly cookie on a response.
  - :material-cookie-remove: `delete_jwt_cookie` — Removes a JWT cookie from a response (for logout).

---

## :material-cog-off: Configuration without Settings

Settings are not required. Provide keys and claims explicitly:

- Pass `private_key` to `encode_jwt` and `public_key` to `decode_jwt`/`AsyncJwtBearer.jwt_public`.
- Include `iss` and `aud` directly in the `claims` you encode if you are not using settings.

Example key usage without settings:

```python
# ...existing code...
from joserfc import jwk
from ninja_aio.auth import encode_jwt, decode_jwt

private_key = jwk.RSAKey.import_key(open("priv.jwk").read())
public_key = jwk.RSAKey.import_key(open("pub.jwk").read())

token = encode_jwt(
    claims={"sub": "123", "iss": "https://auth.example", "aud": "my-api"},
    duration=3600,
    private_key=private_key,
    algorithm="RS256",
)

decoded = decode_jwt(token=token, public_key=public_key, algorithms=["RS256"])
# ...existing code...
```

### Mandatory Claims

The library enforces `iss` and `aud` via `JWT_MANDATORY_CLAIMS`. If you do not use settings, include them in the payload you pass to `encode_jwt`.

---

## :material-cog: Configuration with Settings (Optional)

You can centralize configuration in Django settings and omit explicit keys/claims:

- `JWT_PRIVATE_KEY`: jwk.RSAKey or jwk.ECKey for signing
- `JWT_PUBLIC_KEY`: jwk.RSAKey or jwk.ECKey for verification
- `JWT_ISSUER`: issuer string
- `JWT_AUDIENCE`: audience string

When present:

- `encode_jwt` reads `JWT_PRIVATE_KEY` if `private_key` is not passed, and fills `iss`/`aud` via `validate_mandatory_claims` if missing.
- `decode_jwt` reads `JWT_PUBLIC_KEY` if `public_key` is not passed.
- `AsyncJwtBearer` can read the public key from settings by assigning `jwt_public = settings.JWT_PUBLIC_KEY`.

```python
# settings.py (example)
JWT_PRIVATE_KEY = jwk.RSAKey.import_key(open("priv.jwk").read())
JWT_PUBLIC_KEY = jwk.RSAKey.import_key(open("pub.jwk").read())
JWT_ISSUER = "https://auth.example"
JWT_AUDIENCE = "my-api"
```

Usage without passing keys/claims explicitly:

```python
from ninja_aio.auth import encode_jwt, decode_jwt
# claims missing iss/aud will be completed from settings
token = encode_jwt(claims={"sub": "123"}, duration=3600)

decoded = decode_jwt(token=token)  # uses settings.JWT_PUBLIC_KEY
```

AsyncJwtBearer wired to settings:

```python
from django.conf import settings
from ninja_aio.auth import AsyncJwtBearer

class SettingsBearer(AsyncJwtBearer):
    jwt_public = settings.JWT_PUBLIC_KEY
    claims = {
        "iss": {"value": settings.JWT_ISSUER},
        "aud": {"value": settings.JWT_AUDIENCE},
        # Optionally require time-based claims:
        # "exp": {"essential": True},
        # "nbf": {"essential": True},
    }

    async def auth_handler(self, request):
        sub = self.dcd.claims.get("sub")
        return {"user_id": sub}
```

---

## :material-puzzle: JwtAuthMixin

Both `AsyncJwtBearer` and `AsyncJwtCookie` share the same JWT logic via `JwtAuthMixin`. The mixin provides:

- `jwt_public`: Must be a JWK (RSA or EC) used to verify signatures.
- `claims`: Dict passed to `jwt.JWTClaimsRegistry` defining validations (e.g., `iss`, `aud`, `exp`, `nbf`).
- `algorithms`: Allowed algorithms (default `["RS256"]`).
- `dcd`: Set after successful decode; instance of `jwt.Token` containing `header` and `claims`.
- `get_claims()`: Builds the claim registry from `claims`.
- `validate_claims(claims)`: Validates decoded claims; raises `jose.errors.JoseError` on failure.
- `auth_handler(request)`: Async hook to resolve application user given the decoded token (`self.dcd`).
- `authenticate(request, token)`: Decodes, validates, and delegates to `auth_handler`. Returns user or `False`.

---

## :material-shield-check: AsyncJwtBearer

Extracts JWTs from the `Authorization: Bearer <token>` header. Extends `JwtAuthMixin` and Django Ninja's `HttpBearer`.

### :material-code-braces: Example

```python
from joserfc import jwk
from ninja import NinjaAPI
from ninja_aio.auth import AsyncJwtBearer

class MyBearer(AsyncJwtBearer):
    jwt_public = jwk.RSAKey.import_key(open("pub.jwk").read())
    claims = {
        "iss": {"value": "https://auth.example"},
        "aud": {"value": "my-api"},
        # You can add time-based checks if needed:
        # "exp": {"essential": True},
        # "nbf": {"essential": True},
    }

    async def auth_handler(self, request):
        sub = self.dcd.claims.get("sub")
        return {"user_id": sub}

api = NinjaAPI()

@api.get("/secure", auth=MyBearer())
def secure_endpoint(request):
    return {"ok": True}
```

### :material-format-list-checks: Claims Registry Helper

You can construct and reuse a registry from your class-level `claims`:

```python
registry = MyBearer.get_claims()
# registry.validate(token_claims)  # raises JoseError on failure
```

---

## :material-pencil-lock: encode_jwt

Signs a JWT with safe defaults:

- Adds `iat`, `nbf`, and `exp` using timezone-aware `timezone.now()`.
- Ensures `iss` and `aud` are present via `validate_mandatory_claims` (include them in `claims` if not using settings).
- Header includes `alg`, `typ=JWT`, and optional `kid`.

```python
from joserfc import jwk
from ninja_aio.auth import encode_jwt

private_key = jwk.RSAKey.import_key(open("priv.jwk").read())

claims = {"sub": "123", "scope": "read", "iss": "https://auth.example", "aud": "my-api"}
token = encode_jwt(
    claims=claims,
    duration=3600,
    private_key=private_key,
    algorithm="RS256",
)
```

---

## :material-lock-open-check: decode_jwt

Verifies and decodes a JWT with a public key and algorithm allow-list.

```python
from joserfc import jwk
from ninja_aio.auth import decode_jwt

public_key = jwk.RSAKey.import_key(open("pub.jwk").read())

decoded = decode_jwt(
    token=token,
    public_key=public_key,
    algorithms=["RS256"],
)

claims = decoded.claims
sub = claims.get("sub")
```

---

## :material-cookie-lock: AsyncJwtCookie

Extracts JWTs from an HttpOnly cookie. Extends `JwtAuthMixin` and Django Ninja's `APIKeyCookie`. Designed for BFF (Backend for Frontend) patterns where the backend manages JWT cookies and the frontend never handles raw tokens.

### :material-key-variant: Key Points

- `param_name`: Cookie name (default `"access_token"`).
- CSRF protection is **enabled by default** (inherited from `APIKeyCookie`).
- Same `jwt_public`, `claims`, `algorithms`, `dcd`, and `auth_handler` as `AsyncJwtBearer`.

### :material-code-braces: Example

```python
from joserfc import jwk
from ninja_aio.auth import AsyncJwtCookie

class MyCookieAuth(AsyncJwtCookie):
    jwt_public = jwk.RSAKey.import_key(open("pub.jwk").read())
    claims = {
        "iss": {"value": "https://auth.example"},
        "aud": {"value": "my-api"},
    }

    async def auth_handler(self, request):
        sub = self.dcd.claims.get("sub")
        return {"user_id": sub}

# CSRF disabled (not recommended for production):
# auth = MyCookieAuth(csrf=False)
```

### :material-compare: When to Use Which

| | `AsyncJwtBearer` | `AsyncJwtCookie` |
|---|---|---|
| **Token location** | `Authorization: Bearer <token>` header | HttpOnly cookie |
| **Best for** | SPAs, mobile apps, API-to-API | BFF pattern, server-rendered apps |
| **XSS protection** | Token accessible to JS | Token inaccessible to JS (HttpOnly) |
| **CSRF protection** | Not needed (explicit header) | Built-in (enabled by default) |

---

## :material-cookie-plus: set_jwt_cookie

Sets a JWT as an HttpOnly cookie on a Django response. Pairs with `AsyncJwtCookie` for BFF patterns.

```python
from ninja_aio.auth import set_jwt_cookie, encode_jwt

# In a login endpoint:
@api.post("/auth/login/")
async def login(request, data: LoginSchema):
    # ... authenticate user ...
    token = encode_jwt(claims={"sub": str(user.id)}, duration=900)

    response = api.create_response(request, {"message": "ok"})
    set_jwt_cookie(response, token, max_age=900)
    return response
```

**Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `response` | `HttpResponse` | — | Django response object |
| `token` | `str` | — | JWT compact string |
| `cookie_name` | `str` | `"access_token"` | Should match `AsyncJwtCookie.param_name` |
| `max_age` | `int` | `None` | Cookie lifetime in seconds |
| `secure` | `bool` | `not settings.DEBUG` | HTTPS only (auto-safe: secure in production, permissive in development) |
| `httponly` | `bool` | `True` | Inaccessible to JavaScript |
| `samesite` | `str` | `"Lax"` | SameSite policy |
| `path` | `str` | `"/"` | Cookie path |
| `domain` | `str` | `None` | Cookie domain |

---

## :material-cookie-remove: delete_jwt_cookie

Removes the JWT cookie from a response (for logout flows).

```python
from ninja_aio.auth import delete_jwt_cookie

@api.post("/auth/logout/")
async def logout(request):
    response = api.create_response(request, {"message": "logged out"})
    delete_jwt_cookie(response)
    return response
```

---

## :material-key-check: validate_key

If you do not use settings, pass keys directly. `validate_key` will raise `ValueError` only when neither an explicit key nor a configured setting is provided.

```python
from ninja_aio.auth import validate_key
from joserfc import jwk

pkey = validate_key(jwk.RSAKey.import_key(open("priv.jwk").read()), "JWT_PRIVATE_KEY")
```

---

## :material-check-decagram: validate_mandatory_claims

Ensures `iss` and `aud` are present; if settings are not used, include them in your input claims.

```python
from ninja_aio.auth import validate_mandatory_claims

claims = {"sub": "123", "iss": "https://auth.example", "aud": "my-api"}
claims = validate_mandatory_claims(claims)
```

---

## :material-alert-circle: Error Handling

- `authenticate` returns `False` on decode (`ValueError`) or claim validation failure (`JoseError`). Map this to 401/403 in your views as needed.
- `validate_claims` raises `jose.errors.JoseError` for invalid claims.
- `encode_jwt` and `decode_jwt` raise `ValueError` for missing/invalid keys or configuration.

---

## :material-security: Security Notes

!!! warning "Security Best Practices"
    - Rotate keys and use `kid` headers to support key rotation.
    - Validate critical claims (`exp`, `nbf`, `iss`, `aud`) via the registry.
    - Do not log raw tokens or sensitive claims.

---

## :material-compass: See Also

<div class="grid cards" markdown>

- :material-shield-lock: **API Authentication** — Authentication levels and ViewSet integration

    [:octicons-arrow-right-24: API Authentication](api/authentication.md)

- :material-school: **Tutorial: Authentication** — Step-by-step auth setup guide

    [:octicons-arrow-right-24: Authentication Tutorial](tutorial/authentication.md)

- :material-view-grid: **APIViewSet** — Auto-generated CRUD with auth support

    [:octicons-arrow-right-24: APIViewSet](api/views/api_view_set.md)

</div>
