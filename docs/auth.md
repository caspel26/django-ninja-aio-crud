# JWT Authentication and AsyncJwtBearer

This page documents the JWT helpers and the `AsyncJwtBearer` class in `ninja_aio/auth.py`, including configuration, validation, and usage in Django Ninja.

## Overview

- `AsyncJwtBearer`: Asynchronous HTTP Bearer auth that verifies JWTs, validates claims via a registry, and delegates user resolution to `auth_handler`.
- Helpers:
  - `validate_key`: Ensures JWK keys are present and of the correct type.
  - `validate_mandatory_claims`: Ensures `iss` and `aud` are present (from settings if not provided).
  - `encode_jwt`: Signs a JWT with time-based claims (`iat`, `nbf`, `exp`) and mandatory `iss/aud`.
  - `decode_jwt`: Verifies and decodes a JWT with a public key and allowed algorithms.

## Configuration without settings

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

### Mandatory claims

The library enforces `iss` and `aud` via `JWT_MANDATORY_CLAIMS`. If you do not use settings, include them in the payload you pass to `encode_jwt`.

## Configuration with settings (optional)

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

## AsyncJwtBearer

### Key points

- `jwt_public`: Must be a JWK (RSA or EC) used to verify signatures.
- `claims`: Dict passed to `jwt.JWTClaimsRegistry` defining validations (e.g., `iss`, `aud`, `exp`, `nbf`).
- `algorithms`: Allowed algorithms (default `["RS256"]`).
- `dcd`: Set after successful decode; instance of `jwt.Token` containing `header` and `claims`.
- `get_claims()`: Builds the claim registry from `claims`.
- `validate_claims(claims)`: Validates decoded claims; raises `jose.errors.JoseError` on failure.
- `auth_handler(request)`: Async hook to resolve application user given the decoded token (`self.dcd`).
- `authenticate(request, token)`: Decodes, validates, and delegates to `auth_handler`. Returns user or `False`.

### Example

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

### Claims registry helper

You can construct and reuse a registry from your class-level `claims`:

```python
registry = MyBearer.get_claims()
# registry.validate(token_claims)  # raises JoseError on failure
```

## encode_jwt

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

## decode_jwt

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

## validate_key

If you do not use settings, pass keys directly. `validate_key` will raise `ValueError` only when neither an explicit key nor a configured setting is provided.

```python
from ninja_aio.auth import validate_key
from joserfc import jwk

pkey = validate_key(jwk.RSAKey.import_key(open("priv.jwk").read()), "JWT_PRIVATE_KEY")
```

## validate_mandatory_claims

Ensures `iss` and `aud` are present; if settings are not used, include them in your input claims.

```python
from ninja_aio.auth import validate_mandatory_claims

claims = {"sub": "123", "iss": "https://auth.example", "aud": "my-api"}
claims = validate_mandatory_claims(claims)
```

## Error handling

- `authenticate` returns `False` on decode (`ValueError`) or claim validation failure (`JoseError`). Map this to 401/403 in your views as needed.
- `validate_claims` raises `jose.errors.JoseError` for invalid claims.
- `encode_jwt` and `decode_jwt` raise `ValueError` for missing/invalid keys or configuration.

## Security notes

- Rotate keys and use `kid` headers to support key rotation.
- Validate critical claims (`exp`, `nbf`, `iss`, `aud`) via the registry.
- Do not log raw tokens or sensitive claims.
