---
type: guide
title: JWT authentication
description: Verify JWT tokens, issue them, and choose which endpoints need one.
---

# JWT authentication

This page shows how to verify JWT tokens sent in the `Authorization: Bearer`
header, how to issue tokens, and how to choose which endpoints require one.

## Configure the keys

Put the signing keys and the default claims in your settings:

```python title="project/settings.py"
import os

from joserfc import jwk

JWT_PRIVATE_KEY = jwk.RSAKey.import_key(os.environ["JWT_PRIVATE_KEY"])
JWT_PUBLIC_KEY = jwk.RSAKey.import_key(os.environ["JWT_PUBLIC_KEY"])
JWT_ISSUER = "blog-api"
JWT_AUDIENCE = "blog-clients"
```

| Setting | What it does |
| --- | --- |
| `JWT_PRIVATE_KEY` | Key that `encode_jwt()` signs tokens with |
| `JWT_PUBLIC_KEY` | Key that `decode_jwt()` verifies tokens with |
| `JWT_ISSUER` | Added as `iss` to every token you encode |
| `JWT_AUDIENCE` | Added as `aud` to every token you encode |

Keys are joserfc keys: `jwk.RSAKey`, `jwk.ECKey` or `jwk.OctKey`. Any other
value raises `ValueError`.

## Write an auth class

Subclass `AsyncJwtBearer`. The token is verified first, then `auth_handler`
runs and returns the user:

```python title="blog/auth.py"
from django.conf import settings
from django.contrib.auth import get_user_model
from ninja_aio.auth import AsyncJwtBearer

User = get_user_model()


class JWTAuth(AsyncJwtBearer):
    jwt_public = settings.JWT_PUBLIC_KEY
    claims = {
        "iss": {"essential": True, "value": settings.JWT_ISSUER},
        "aud": {"essential": True, "value": settings.JWT_AUDIENCE},
        "sub": {"essential": True},
        "scope": {"values": ["read", "write"]},
    }

    async def auth_handler(self, request):
        user_id = self.dcd.claims["sub"]
        return await User.objects.filter(pk=user_id, is_active=True).afirst()
```

| Attribute | Default | What it does |
| --- | --- | --- |
| `jwt_public` | required | Key that verifies the token signature |
| `claims` | required | Rules for the token claims |
| `algorithms` | `["RS256"]` | Signature algorithms you accept |

Each entry of `claims` is a claim name with its rules:

| Rule | What it does |
| --- | --- |
| `"essential": True` | The claim must be in the token |
| `"value": x` | The claim must equal `x` |
| `"values": [x, y]` | The claim must be one of the listed values |

`self.dcd.claims` holds the claims of the token of the current request.

The value `auth_handler` returns is available as `request.auth` in your
endpoints and hooks. When it returns `None` or another falsy value, the
request gets `401`. An invalid signature or a failed claim rule also returns
`401`.

## Issue tokens

`encode_jwt()` signs a token with `JWT_PRIVATE_KEY`:

```python
from ninja_aio.auth import encode_jwt

token = encode_jwt({"sub": str(user.pk), "scope": "write"}, duration=3600)
```

| Parameter | Default | What it does |
| --- | --- | --- |
| `claims` | required | Claims to put in the token |
| `duration` | required | Lifetime in seconds |
| `private_key` | `JWT_PRIVATE_KEY` | Key to sign with |
| `algorithm` | `"RS256"` | Signature algorithm |

The token also gets `iat`, `nbf` and `exp`. `iss` and `aud` come from
`JWT_ISSUER` and `JWT_AUDIENCE` unless you pass them in `claims`. When neither
is set, `encode_jwt()` raises `ValueError`.

For a complete login endpoint, see [Add authentication](../tutorial/authentication.md).

`decode_jwt()` verifies a token and returns it, for example to read a token
outside a request:

```python
from ninja_aio.auth import decode_jwt

token = decode_jwt(raw_token)
user_id = token.claims["sub"]
```

| Parameter | Default | What it does |
| --- | --- | --- |
| `token` | required | The token string |
| `public_key` | `JWT_PUBLIC_KEY` | Key to verify with |
| `algorithms` | `["RS256"]` | Signature algorithms you accept |

It raises a joserfc `JoseError` when the token is not valid. `decode_jwt()`
checks only the signature. Check the claims you need yourself.

## Use an EC or HMAC key

The default algorithm is `RS256`. With another key type, pass the matching
algorithm everywhere: to `encode_jwt()` and in `algorithms` on the auth class.

### EC key

```bash
openssl ecparam -name prime256v1 -genkey -noout -out ec-private.pem
openssl ec -in ec-private.pem -pubout -out ec-public.pem
```

```python title="project/settings.py"
from pathlib import Path

from joserfc import jwk

JWT_PRIVATE_KEY = jwk.ECKey.import_key(Path("ec-private.pem").read_text())
JWT_PUBLIC_KEY = jwk.ECKey.import_key(Path("ec-public.pem").read_text())
```

```python
token = encode_jwt({"sub": str(user.pk)}, duration=3600, algorithm="ES256")


class JWTAuth(AsyncJwtBearer):
    jwt_public = settings.JWT_PUBLIC_KEY
    algorithms = ["ES256"]
    claims = {"sub": {"essential": True}}
```

### HMAC secret

With HMAC, the same secret signs and verifies:

```python title="project/settings.py"
JWT_PRIVATE_KEY = JWT_PUBLIC_KEY = jwk.OctKey.import_key(os.environ["JWT_SECRET"])
```

```python
token = encode_jwt({"sub": str(user.pk)}, duration=3600, algorithm="HS256")


class JWTAuth(AsyncJwtBearer):
    jwt_public = settings.JWT_PUBLIC_KEY
    algorithms = ["HS256"]
    claims = {"sub": {"essential": True}}
```

Call `decode_jwt(token, algorithms=["HS256"])` too. With the default
`["RS256"]` it rejects the token.

## Choose which endpoints need a token

Set auth at the level you need. The most specific setting wins:

```python title="blog/api.py"
from ninja_aio import NinjaAIO, APIViewSet, action

from .auth import JWTAuth
from .models import Article

api = NinjaAIO(title="Blog API", auth=[JWTAuth()])


@api.viewset(model=Article)
class ArticleViewSet(APIViewSet):
    get_auth = None

    @action(detail=False, url_path="stats", auth=[JWTAuth()])
    async def stats(self, request):
        return {"articles": await Article.objects.acount()}
```

Here every endpoint of the API needs a token, reading articles is public, and
`GET /api/articles/stats` still needs a token.

| Where | Applies to |
| --- | --- |
| `NinjaAIO(auth=[...])` | Every endpoint of the API |
| Viewset `auth` | Every endpoint of the viewset |
| `get_auth`, `post_auth`, `patch_auth`, `delete_auth` | Endpoints of one HTTP method, including bulk endpoints and custom actions |
| `auth=` on `@action` or `@on` | One custom action |
| `auth=` on `@api.get`, `@api.post`, ... | One plain endpoint |

A setting you leave out inherits from the level above. `None` makes the
endpoints public. For example, `auth=None` on a login endpoint keeps it open
when the whole API needs a token.

!!! note

    Many-to-many endpoints don't use the viewset `auth`. Set `m2m_auth` on the
    viewset, or `auth` on each `M2MRelationSchema`.

The same auth classes work in sync viewsets (`execution_mode = "sync"`). You
keep `auth_handler` as `async def`.

## Try it in the interactive docs

Open `/api/docs`, click **Authorize**, and paste a token. The docs then send
it with every request to a protected endpoint.

## See also

- [Add authentication](../tutorial/authentication.md)
- [Cookie authentication](cookie-authentication.md)
- [Permissions](permissions.md)
- [Custom actions](custom-actions.md)
- [Viewsets](viewsets.md)
