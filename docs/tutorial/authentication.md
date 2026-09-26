---
type: tutorial
step: 4
steps: 7
title: Add authentication
description: Protect the write endpoints with JWT tokens.
---

# Add authentication

In this step you add a login endpoint that returns a JWT token, and require
the token for creating, updating and deleting articles.

<div class="nac-steps" markdown>

### Create the keys

Generate an RSA key pair. Keep the private key secret.

```bash
openssl genpkey -algorithm RSA -out private.pem -pkeyopt rsa_keygen_bits:2048
openssl rsa -in private.pem -pubout -out public.pem
```

### Configure the settings

```python title="project/settings.py"
from pathlib import Path

from joserfc import jwk

JWT_PRIVATE_KEY = jwk.RSAKey.import_key(Path("private.pem").read_text())
JWT_PUBLIC_KEY = jwk.RSAKey.import_key(Path("public.pem").read_text())
JWT_ISSUER = "blog-api"
JWT_AUDIENCE = "blog-clients"
```

In production, load the keys from environment variables or a secrets manager
instead of files in the project.

### Write the auth class

`auth_handler` runs after the token is verified. It returns the user, which
you then find in `request.auth`.

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
    }

    async def auth_handler(self, request):
        user_id = self.dcd.claims["sub"]
        return await User.objects.filter(pk=user_id, is_active=True).afirst()
```

`JWTAuth` works for both sync and async viewsets.

### Add a login endpoint

`encode_jwt()` signs the token with `JWT_PRIVATE_KEY` and adds the issuer and
audience from your settings.

=== "Sync"

    ```python title="blog/api.py"
    from django.contrib.auth import authenticate
    from ninja import Schema
    from ninja.errors import AuthenticationError
    from ninja_aio.auth import encode_jwt


    class LoginIn(Schema):
        username: str
        password: str


    class TokenOut(Schema):
        access_token: str


    @api.post("/auth/login", response=TokenOut, auth=None)
    def login(request, data: LoginIn):
        user = authenticate(request, username=data.username, password=data.password)
        if user is None:
            raise AuthenticationError()
        token = encode_jwt({"sub": str(user.pk)}, duration=3600)
        return {"access_token": token}
    ```

=== "Async"

    ```python title="blog/api.py"
    from django.contrib.auth import aauthenticate
    from ninja import Schema
    from ninja.errors import AuthenticationError
    from ninja_aio.auth import encode_jwt


    class LoginIn(Schema):
        username: str
        password: str


    class TokenOut(Schema):
        access_token: str


    @api.post("/auth/login", response=TokenOut, auth=None)
    async def login(request, data: LoginIn):
        user = await aauthenticate(request, username=data.username, password=data.password)
        if user is None:
            raise AuthenticationError()
        token = encode_jwt({"sub": str(user.pk)}, duration=3600)
        return {"access_token": token}
    ```

### Protect the viewset

`auth` applies to every endpoint. `get_auth = None` keeps reading public.

```python title="blog/api.py"
from .auth import JWTAuth


@api.viewset(model=Article)
class ArticleViewSet(APIViewSet):
    auth = [JWTAuth()]
    get_auth = None
```

</div>

You can also set `post_auth`, `patch_auth` and `delete_auth` one by one.
Custom actions follow the setting for their HTTP method.

## Try it

```bash
# Get a token
curl -X POST localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "alice", "password": "secret"}'

# Use it
curl -X POST localhost:8000/api/articles/ \
  -H "Authorization: Bearer <access_token>" \
  -H "Content-Type: application/json" \
  -d '{"title": "Hello", "body": "...", "category_id": 1}'
```

Without a valid token, write requests return `401`.

In the interactive docs, click **Authorize** and paste the token to try the
protected endpoints.

!!! tip

    For browser apps, you can store the token in an HttpOnly cookie instead.
    See [cookie authentication](../auth_cookie.md).

[Next: add permissions](permissions.md){ .md-button .md-button--primary }
