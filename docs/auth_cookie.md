# :material-cookie-lock: Cookie Authentication (BFF)

This page documents `AsyncJwtCookie` and the cookie helper functions for implementing JWT authentication via HttpOnly cookies, designed for **BFF (Backend for Frontend)** patterns.

## :material-information-outline: Overview

In a BFF architecture, the backend acts as a proxy between the frontend and external services. JWTs are stored in **HttpOnly cookies** — the browser sends them automatically, and JavaScript cannot access them. This eliminates an entire class of XSS-based token theft.

```
┌──────────┐    Cookie (auto)    ┌──────────┐    Bearer Token    ┌──────────┐
│ Frontend │ ─────────────────── │   BFF    │ ─────────────────── │ Services │
│  (SPA)   │                     │ (Django) │                     │          │
└──────────┘                     └──────────┘                     └──────────┘
```

### Why Cookies for BFF?

| Concern | Bearer Header | HttpOnly Cookie |
|---------|--------------|-----------------|
| **XSS token theft** | Vulnerable (JS can read localStorage) | Protected (JS cannot access) |
| **Token management** | Frontend must store and attach tokens | Browser handles automatically |
| **CSRF** | Not needed | Needed (built-in with Django) |
| **Logout** | Client-side only (delete from storage) | Server-side (clear cookie) |

---

## :material-rocket-launch: Quick Start

### 1. Create Cookie Authentication Class

```python
# auth.py
from ninja_aio.auth import AsyncJwtCookie
from joserfc import jwk
from django.conf import settings


class CookieAuth(AsyncJwtCookie):
    jwt_public = jwk.RSAKey.import_key(settings.JWT_PUBLIC_KEY)
    # param_name = "access_token"  # default cookie name
    claims = {
        "iss": {"essential": True, "value": settings.JWT_ISSUER},
        "aud": {"essential": True, "value": settings.JWT_AUDIENCE},
    }

    async def auth_handler(self, request):
        user_id = self.dcd.claims.get("sub")
        user = await User.objects.aget(id=user_id, is_active=True)
        return user
```

### 2. Create Login/Logout Endpoints

```python
# views.py
from ninja_aio.auth import encode_jwt, set_jwt_cookie, delete_jwt_cookie
from .auth import CookieAuth

# Login — sets the JWT cookie
@api.post("/auth/login/")
async def login(request, data: LoginSchema):
    user = await authenticate_user(data)
    token = encode_jwt(claims={"sub": str(user.id)}, duration=900)

    response = api.create_response(request, {"message": "ok"})
    set_jwt_cookie(response, token, max_age=900)
    return response


# Logout — clears the JWT cookie
@api.post("/auth/logout/")
async def logout(request):
    response = api.create_response(request, {"message": "logged out"})
    delete_jwt_cookie(response)
    return response


# Protected endpoint
@api.get("/auth/me/", auth=CookieAuth())
async def me(request):
    return {"user_id": request.auth.id, "username": request.auth.username}
```

### 3. Apply to ViewSet

```python
@api.viewset(model=Article)
class ArticleViewSet(APIViewSet):
    get_auth = None  # Public read
    post_auth = [CookieAuth()]
    patch_auth = [CookieAuth()]
    delete_auth = [CookieAuth()]
```

---

## :material-cog: Configuration

### Cookie Name

The default cookie name is `"access_token"`. Override via `param_name`:

```python
class MyCookieAuth(AsyncJwtCookie):
    param_name = "session_jwt"  # reads from this cookie
    # ...
```

!!! note
    Make sure `set_jwt_cookie(..., cookie_name="session_jwt")` matches the `param_name`.

### CSRF Protection

CSRF is **enabled by default**. The browser must send a valid CSRF token alongside the cookie. Django's built-in `CsrfViewMiddleware` handles this.

To disable CSRF (e.g., for mobile API clients that also use cookies):

```python
auth = CookieAuth(csrf=False)
```

!!! warning
    Disabling CSRF removes protection against cross-site request forgery. Only disable when you have alternative mitigations in place (e.g., custom origin checking, SameSite=Strict).

---

## :material-cookie-plus: set_jwt_cookie

Sets a JWT as an HttpOnly cookie on a Django response.

```python
from ninja_aio.auth import set_jwt_cookie

set_jwt_cookie(
    response,
    token,
    cookie_name="access_token",  # match AsyncJwtCookie.param_name
    max_age=900,                 # 15 minutes
    secure=None,                 # auto: not settings.DEBUG
    httponly=True,                # inaccessible to JS
    samesite="Lax",              # CSRF mitigation
    path="/",
    domain=None,
)
```

**Secure defaults:** `httponly=True`, `secure=not settings.DEBUG` (auto-safe), `samesite="Lax"`.

---

## :material-cookie-remove: delete_jwt_cookie

Removes the JWT cookie (for logout).

```python
from ninja_aio.auth import delete_jwt_cookie

delete_jwt_cookie(
    response,
    cookie_name="access_token",  # match AsyncJwtCookie.param_name
    path="/",
    domain=None,
)
```

---

## :material-shield-star: Security Best Practices

1. **`secure` defaults to `not settings.DEBUG`** — automatically secure in production, works over HTTP in development. Override with `secure=True` or `secure=False` if needed.

2. **Keep `httponly=True`** — this is the whole point of cookie-based auth.

3. **Use `samesite="Lax"` or `"Strict"`** for CSRF mitigation:
    - `"Lax"`: Cookies sent on top-level navigations and same-site requests (recommended).
    - `"Strict"`: Cookies only sent on same-site requests.

4. **Keep tokens short-lived** — use `max_age` matching the JWT `exp` claim:
    ```python
    duration = 900  # 15 minutes
    token = encode_jwt(claims={...}, duration=duration)
    set_jwt_cookie(response, token, max_age=duration)
    ```

5. **Implement token refresh** via a separate refresh cookie or endpoint.

6. **Set `domain`** explicitly in multi-subdomain setups:
    ```python
    set_jwt_cookie(response, token, domain=".example.com")
    ```

---

## :material-compass: See Also

<div class="grid cards" markdown>

- :material-shield-lock: **JWT & AsyncJwtBearer** — Bearer token auth and JWT helpers

    [:octicons-arrow-right-24: JWT Authentication](auth.md)

- :material-shield-lock: **API Authentication** — Authentication levels and ViewSet integration

    [:octicons-arrow-right-24: API Authentication](api/authentication.md)

- :material-school: **Tutorial: Authentication** — Step-by-step auth setup guide

    [:octicons-arrow-right-24: Authentication Tutorial](tutorial/authentication.md)

</div>
