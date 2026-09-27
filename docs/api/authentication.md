---
type: reference
title: Authentication
description: Lookup page for the JWT auth classes and the token and cookie helpers.
---

# Authentication

JWT auth classes for Django Ninja and helpers to create, read and store tokens.
For how to use them, see [Authentication](../guides/authentication.md) and
[Cookie authentication](../guides/cookie-authentication.md).

```python
from ninja_aio.auth import (
    AsyncJwtBearer,
    AsyncJwtCookie,
    encode_jwt,
    decode_jwt,
    set_jwt_cookie,
    delete_jwt_cookie,
)
```

## `AsyncJwtBearer`

Reads the token from the `Authorization: Bearer <token>` header.

```python title="blog/auth.py"
class JwtAuth(AsyncJwtBearer):
    jwt_public = settings.JWT_PUBLIC_KEY
    claims = {"iss": {"value": "blog"}, "aud": {"value": "blog-api"}}

    async def auth_handler(self, request):
        return await User.objects.aget(pk=self.dcd.claims["sub"])
```

### Class attributes

| Attribute | Type | Default | Description |
| --- | --- | --- | --- |
| `jwt_public` | `RSAKey \| ECKey \| OctKey` | `JWT_PUBLIC_KEY` | Key used to verify the signature |
| `claims` | `dict[str, dict]` | required | Claim rules passed to joserfc `JWTClaimsRegistry`, like `{"iss": {"value": "blog"}}`. Missing raises `ImproperlyConfigured` on creation; `{}` checks none |
| `algorithms` | `list[str] \| None` | `None` | Allowed signing algorithms. `None` means `[JWT_ALGORITHM]`, or `["RS256"]` |

### Methods

| Member | Description |
| --- | --- |
| `async auth_handler(request)` | Override it. Return the value for `request.auth`, or a falsy value to reject. Default returns `None` |
| `async authenticate(request, token)` | Decodes the token, validates `claims`, then calls `auth_handler`. Returns `False` when the token is missing, invalid or expired |
| `dcd` | Property. The decoded token (`joserfc.jwt.Token`) of the current request, or `None`. Use `self.dcd.claims` inside `auth_handler` |

`dcd` is scoped to the current request, so concurrent requests never share it.

## `AsyncJwtCookie`

Same attributes and methods as `AsyncJwtBearer`, but reads the token from a
cookie.

| Attribute | Type | Default | Description |
| --- | --- | --- | --- |
| `param_name` | `str` | `"access_token"` | Cookie name |

The constructor takes `csrf: bool = True`. When a token cookie is present and
CSRF is on, a failed CSRF check returns 403. Use `JwtCookieAuth(csrf=False)` to
turn it off.

## `encode_jwt()`

```python
token = encode_jwt({"sub": str(user.pk)}, duration=3600)
```

| Parameter | Type | Default | Description |
| --- | --- | --- | --- |
| `claims` | `dict` | required | Claims to add. They override the generated ones |
| `duration` | `int` | required | Lifetime in seconds |
| `private_key` | `RSAKey \| ECKey \| OctKey \| None` | `None` | Signing key. `None` reads `JWT_PRIVATE_KEY` |
| `algorithm` | `str \| None` | `None` | Signing algorithm. `None` uses `JWT_ALGORITHM`, or `"RS256"` |

Returns the token as a string. It adds `iat`, `nbf` and `exp`. When `iss` or
`aud` are not in `claims`, it reads `JWT_ISSUER` and `JWT_AUDIENCE`. The header
gets the key `kid` when the key has one. The `claims` dict you pass is not
changed.

Raises `ValueError` when the key is missing or not a supported type, or when
`iss` or `aud` is missing from both `claims` and settings.

## `decode_jwt()`

```python
token = decode_jwt(raw_token)
user_id = token.claims["sub"]
```

| Parameter | Type | Default | Description |
| --- | --- | --- | --- |
| `token` | `str` | required | The token string |
| `public_key` | `RSAKey \| ECKey \| OctKey \| None` | `None` | Verification key. `None` reads `JWT_PUBLIC_KEY` |
| `algorithms` | `list[str] \| None` | `None` | Allowed algorithms. `None` uses `[JWT_ALGORITHM]`, or `["RS256"]` |

Returns a `joserfc.jwt.Token` with `header` and `claims`. It checks the
signature only, not the claims. Raises `ValueError` for a missing or unsupported
key and a joserfc `JoseError` for an invalid token.

## `set_jwt_cookie()`

Sets the token cookie on a response and returns the response.

| Parameter | Type | Default | Description |
| --- | --- | --- | --- |
| `response` | `HttpResponse` | required | Response to change |
| `token` | `str` | required | The token string |
| `cookie_name` | `str` | `"access_token"` | Cookie name. Match `AsyncJwtCookie.param_name` |
| `max_age` | `int \| None` | `None` | Lifetime in seconds. `None` makes a session cookie |
| `secure` | `bool \| None` | `None` | HTTPS only. `None` means `not settings.DEBUG` |
| `httponly` | `bool` | `True` | Hide the cookie from JavaScript |
| `samesite` | `str` | `"Lax"` | SameSite policy |
| `path` | `str` | `"/"` | Cookie path |
| `domain` | `str \| None` | `None` | Cookie domain |

## `delete_jwt_cookie()`

Removes the token cookie from a response and returns the response.

| Parameter | Type | Default | Description |
| --- | --- | --- | --- |
| `response` | `HttpResponse` | required | Response to change |
| `cookie_name` | `str` | `"access_token"` | Cookie name |
| `path` | `str` | `"/"` | Cookie path. Match the one used in `set_jwt_cookie` |
| `domain` | `str \| None` | `None` | Cookie domain. Match the one used in `set_jwt_cookie` |

## Settings

| Setting | Read by | Description |
| --- | --- | --- |
| `JWT_PRIVATE_KEY` | `encode_jwt` | Default signing key |
| `JWT_PUBLIC_KEY` | `decode_jwt` | Default verification key |
| `JWT_ISSUER` | `encode_jwt` | Default `iss` claim |
| `JWT_AUDIENCE` | `encode_jwt` | Default `aud` claim |

The auth classes do not read settings. Set `jwt_public` and `claims` on your
subclass.

## Key types

Keys must be joserfc key objects, not PEM strings:

| Key | Use with |
| --- | --- |
| `jwk.RSAKey` | `RS256`, `RS384`, `RS512`, `PS256`... |
| `jwk.ECKey` | `ES256`, `ES384`, `ES512` |
| `jwk.OctKey` | `HS256`, `HS384`, `HS512` |

```python title="settings.py"
from joserfc import jwk

JWT_PRIVATE_KEY = jwk.RSAKey.import_key(open("private.pem").read())
JWT_PUBLIC_KEY = jwk.RSAKey.import_key(open("public.pem").read())
```

## See also

- [Authentication](../guides/authentication.md)
- [Cookie authentication](../guides/cookie-authentication.md)
- [Permissions](../guides/permissions.md)
