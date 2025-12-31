# JWT Authentication and AsyncJwtBearer

This page documents the JWT helpers and the `AsyncJwtBearer` class in `ninja_aio/auth.py`, including configuration, validation, and usage in Django Ninja.

## Overview

- `AsyncJwtBearer`: Asynchronous HTTP Bearer auth that verifies JWTs, validates claims via a registry, and delegates user resolution to `auth_handler`.
- Helpers:
  - `validate_key`: Ensures JWK keys are present and of the correct type.
  - `validate_mandatory_claims`: Ensures `iss` and `aud` are present (from settings if not provided).
  - `encode_jwt`: Signs a JWT with time-based claims (`iat`, `nbf`, `exp`) and mandatory `iss/aud`.
  - `decode_jwt`: Verifies and decodes a JWT with a public key and allowed algorithms.

## Settings

Required settings (used by helpers and defaults):

- `JWT_PRIVATE_KEY`: jwk.RSAKey or jwk.ECKey for signing.
- `JWT_PUBLIC_KEY`: jwk.RSAKey or jwk.ECKey for verification.
- `JWT_ISSUER`: issuer string (e.g. `https://auth.example`).
- `JWT_AUDIENCE`: audience string (e.g. `my-api`).

## AsyncJwtBearer

### Key points

- `jwt_public`: Must be a JWK (RSA or EC) used to verify signatures.
- `claims`: Dict passed to `jwt.JWTClaimsRegistry` defining validations (e.g., `iss`, `aud`, `exp`, `nbf`).
- `algorithms`: Allowed algorithms (default `["RS256"]`).
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
        # Resolve your user from `sub` or other claims
        # return await get_user_by_id(sub)
        return {"user_id": sub}  # minimal example

api = NinjaAPI()

@api.get("/secure", auth=MyBearer())
def secure_endpoint(request):
    return {"ok": True}
```

## encode_jwt

Signs a JWT with safe defaults:

- Adds `iat`, `nbf`, and `exp` using timezone-aware `timezone.now()`.
- Ensures `iss` and `aud` are present via `validate_mandatory_claims`.
- Header includes `alg`, `typ=JWT`, and optional `kid`.

```python
from django.utils import timezone
from joserfc import jwk
from ninja_aio.auth import encode_jwt

private_key = jwk.RSAKey.import_key(open("priv.jwk").read())

claims = {"sub": "123", "scope": "read"}
token = encode_jwt(
    claims=claims,
    duration=3600,  # 1 hour
    private_key=private_key,  # defaults to settings.JWT_PRIVATE_KEY if omitted
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
    public_key=public_key,   # defaults to settings.JWT_PUBLIC_KEY if omitted
    algorithms=["RS256"],
)

# Access claims:
claims = decoded.claims
sub = claims.get("sub")
```

## validate_key

Ensures a JWK key is provided either directly or via settings and has the correct type (RSA or EC). Raises `ValueError` if invalid.

```python
from ninja_aio.auth import validate_key
from joserfc import jwk

pkey = validate_key(None, "JWT_PRIVATE_KEY")  # pulls from settings.JWT_PRIVATE_KEY
assert isinstance(pkey, (jwk.RSAKey, jwk.ECKey))
```

## validate_mandatory_claims

Ensures `iss` and `aud` are present; fills from settings if missing.

```python
from ninja_aio.auth import validate_mandatory_claims

claims = {"sub": "123"}
claims = validate_mandatory_claims(claims)
# claims now contains `iss` and `aud` from settings if they were absent.
```

## Error handling

- `authenticate` returns `False` on decode or claim validation failure. Map this to 401/403 in your views as needed.
- `validate_claims` raises `jose.errors.JoseError` for invalid claims.
- `encode_jwt` and `decode_jwt` raise `ValueError` for missing/invalid keys or configuration.

## Security notes

- Rotate keys and use `kid` headers to support key rotation.
- Validate critical claims (`exp`, `nbf`, `iss`, `aud`) via the registry.
- Do not log raw tokens or sensitive claims.
