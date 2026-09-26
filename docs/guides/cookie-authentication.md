---
type: guide
title: Cookie authentication
description: Keep the JWT token in an HttpOnly cookie for browser apps.
---

# Cookie authentication

This page shows how to read the JWT token from an HttpOnly cookie instead of
the `Authorization` header. Use it when a browser app talks to your API.

The keys and settings are the same as for the header. See
[JWT authentication](authentication.md).

## Write a cookie auth class

Subclass `AsyncJwtCookie`. It works like `AsyncJwtBearer`, but reads the token
from a cookie:

```python title="blog/auth.py"
from django.conf import settings
from django.contrib.auth import get_user_model
from ninja_aio.auth import AsyncJwtCookie

User = get_user_model()


class CookieAuth(AsyncJwtCookie):
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

| Attribute | Default | What it does |
| --- | --- | --- |
| `param_name` | `"access_token"` | Name of the cookie that holds the token |
| `jwt_public`, `claims`, `algorithms` | | Same as on `AsyncJwtBearer` |

Use it like any other auth class:

```python title="blog/api.py"
@api.viewset(model=Article)
class ArticleViewSet(APIViewSet):
    auth = [CookieAuth()]
    get_auth = None
```

## Log in and log out

Add a `response: HttpResponse` parameter to your endpoint. Django Ninja passes
the response it is about to send, and you set the cookie on it:

=== "Sync"

    ```python title="blog/api.py"
    from django.contrib.auth import authenticate
    from django.http import HttpResponse
    from ninja import Schema
    from ninja.errors import AuthenticationError
    from ninja_aio.auth import delete_jwt_cookie, encode_jwt, set_jwt_cookie


    class LoginIn(Schema):
        username: str
        password: str


    @api.post("/auth/login", auth=None)
    def login(request, data: LoginIn, response: HttpResponse):
        user = authenticate(request, username=data.username, password=data.password)
        if user is None:
            raise AuthenticationError()
        token = encode_jwt({"sub": str(user.pk)}, duration=3600)
        set_jwt_cookie(response, token, max_age=3600)
        return {"detail": "Logged in"}


    @api.post("/auth/logout", auth=None)
    def logout(request, response: HttpResponse):
        delete_jwt_cookie(response)
        return {"detail": "Logged out"}
    ```

=== "Async"

    ```python title="blog/api.py"
    from django.contrib.auth import aauthenticate
    from django.http import HttpResponse
    from ninja import Schema
    from ninja.errors import AuthenticationError
    from ninja_aio.auth import delete_jwt_cookie, encode_jwt, set_jwt_cookie


    class LoginIn(Schema):
        username: str
        password: str


    @api.post("/auth/login", auth=None)
    async def login(request, data: LoginIn, response: HttpResponse):
        user = await aauthenticate(request, username=data.username, password=data.password)
        if user is None:
            raise AuthenticationError()
        token = encode_jwt({"sub": str(user.pk)}, duration=3600)
        set_jwt_cookie(response, token, max_age=3600)
        return {"detail": "Logged in"}


    @api.post("/auth/logout", auth=None)
    async def logout(request, response: HttpResponse):
        delete_jwt_cookie(response)
        return {"detail": "Logged out"}
    ```

The same `response` parameter works in custom actions of an `APIView`.

`set_jwt_cookie()` options:

| Parameter | Default | What it does |
| --- | --- | --- |
| `response` | required | The response to set the cookie on |
| `token` | required | The JWT token |
| `cookie_name` | `"access_token"` | Cookie name. Match `param_name` of your auth class |
| `max_age` | `None` | Cookie lifetime in seconds. `None` keeps it until the browser closes |
| `secure` | `None` | Send the cookie over HTTPS only. `None` means `True` when `DEBUG` is off and `False` when it is on |
| `httponly` | `True` | Hide the cookie from JavaScript |
| `samesite` | `"Lax"` | SameSite policy: `"Lax"`, `"Strict"` or `"None"` |
| `path` | `"/"` | Cookie path |
| `domain` | `None` | Cookie domain |

`delete_jwt_cookie(response, cookie_name="access_token", path="/", domain=None)`
removes the cookie. Pass the same `cookie_name`, `path` and `domain` you used
to set it.

## Send the CSRF token

The cookie auth class checks the Django CSRF token on `POST`, `PATCH`, `PUT`
and `DELETE` requests that carry the token cookie. Without a valid CSRF token
these requests return `403`. `GET` requests and requests without the cookie
skip the check.

<div class="nac-steps" markdown>

### Keep the CSRF middleware

`CsrfViewMiddleware` sets the `csrftoken` cookie. New Django projects have it
already:

```python title="project/settings.py"
MIDDLEWARE = [
    # ...
    "django.middleware.csrf.CsrfViewMiddleware",
    # ...
]

# Only when the frontend runs on another origin
CSRF_TRUSTED_ORIGINS = ["https://app.example.com"]
```

### Add an endpoint that returns the token

```python title="blog/api.py"
from django.middleware.csrf import get_token


@api.get("/auth/csrf", auth=None)
def csrf(request):
    return {"csrftoken": get_token(request)}
```

### Send the token from the browser

Call the endpoint once, then send the token in the `X-CSRFToken` header:

```javascript
const { csrftoken } = await fetch("/api/auth/csrf", {
  credentials: "include",
}).then((r) => r.json());

await fetch("/api/articles/", {
  method: "POST",
  credentials: "include",
  headers: {
    "Content-Type": "application/json",
    "X-CSRFToken": csrftoken,
  },
  body: JSON.stringify({ title: "Hello", body: "...", category_id: 1 }),
});
```

</div>

`credentials: "include"` makes the browser send the cookies. The header name
comes from Django's `CSRF_HEADER_NAME` setting.

### Turn off the CSRF check

```python
auth = [CookieAuth(csrf=False)]
```

!!! warning

    Without the CSRF check, other sites can send requests with your users'
    cookies. Turn it off only when no browser sends the cookie across sites.

## Accept a header or a cookie

List both classes. The first one that authenticates the request wins:

```python title="blog/api.py"
from .auth import CookieAuth, JWTAuth


@api.viewset(model=Article)
class ArticleViewSet(APIViewSet):
    auth = [JWTAuth(), CookieAuth()]
```

Mobile apps send the `Authorization` header, and the browser app sends the
cookie. A request with neither gets `401`.

## See also

- [JWT authentication](authentication.md)
- [Add authentication](../tutorial/authentication.md)
- [Permissions](permissions.md)
