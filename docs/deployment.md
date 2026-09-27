---
type: guide
title: Deployment
description: Run your API in production with the right server, settings and database setup.
---

# Deployment

This page shows how to run your API on a production server, what to check
before you go live, and how to keep it fast.

## Choose the server and the mode

Pick the execution mode that matches your server:

| Server | Examples | Use |
| --- | --- | --- |
| ASGI | Uvicorn, Daphne, Granian | `execution_mode = "async"` (default) |
| WSGI | Gunicorn, uWSGI | `execution_mode = "sync"` |

For a WSGI server, set the mode on each viewset:

```python title="blog/api.py"
@api.viewset(model=Article)
class ArticleViewSet(APIViewSet):
    execution_mode = "sync"
```

Both modes work on both servers. Matching them avoids switching between sync
and async code on every request. See [Sync and async](concepts/sync-and-async.md).

## Run the server

Django's `runserver` is for development only. In production, start one of
these servers:

=== "Uvicorn (ASGI)"

    ```bash
    pip install uvicorn
    uvicorn project.asgi:application --host 0.0.0.0 --port 8000 --workers 4
    ```

=== "Daphne (ASGI)"

    ```bash
    pip install daphne
    daphne -b 0.0.0.0 -p 8000 project.asgi:application
    ```

=== "Granian (ASGI)"

    ```bash
    pip install granian
    granian --interface asgi --host 0.0.0.0 --port 8000 --workers 4 project.asgi:application
    ```

=== "Gunicorn (WSGI)"

    ```bash
    pip install gunicorn
    gunicorn project.wsgi:application --bind 0.0.0.0:8000 --workers 4
    ```

=== "uWSGI (WSGI)"

    ```bash
    pip install uwsgi
    uwsgi --http :8000 --module project.wsgi:application --processes 4
    ```

Replace `project` with the name of your Django project. A good starting point
for `--workers` is the number of CPU cores.

## Build a Docker image

```dockerfile title="Dockerfile"
FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
RUN python manage.py collectstatic --noinput

EXPOSE 8000
CMD ["uvicorn", "project.asgi:application", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]
```

Pass secrets and database settings as environment variables when you start
the container, not in the image.

## Production checklist

Set the basic Django settings:

```python title="project/settings.py"
import os

DEBUG = False
ALLOWED_HOSTS = ["api.example.com"]
SECRET_KEY = os.environ["SECRET_KEY"]

SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_SSL_REDIRECT = True
```

Load the JWT keys from the environment instead of files in the repository:

```python title="project/settings.py"
from joserfc import jwk

JWT_PRIVATE_KEY = jwk.RSAKey.import_key(os.environ["JWT_PRIVATE_KEY"])
JWT_PUBLIC_KEY = jwk.RSAKey.import_key(os.environ["JWT_PUBLIC_KEY"])
JWT_ISSUER = "blog-api"
JWT_AUDIENCE = "blog-clients"
```

Hide the interactive docs, or allow only staff users:

```python title="blog/api.py"
from django.contrib.admin.views.decorators import staff_member_required

api = NinjaAIO(title="Blog API", docs_url=None)  # no docs
api = NinjaAIO(title="Blog API", docs_decorator=staff_member_required)  # staff only
```

`docs_url=None` removes the docs page. Add `openapi_url=None` to hide the
OpenAPI schema too.

Then run the checks:

```bash
python manage.py check --deploy
```

The check also validates every `Schemas` class, so a misspelled field fails
here with a code like `ninja_aio.E003`.

- [ ] `DEBUG = False` and `ALLOWED_HOSTS` is set
- [ ] `SECRET_KEY` and JWT keys come from the environment
- [ ] `python manage.py check --deploy` passes
- [ ] The docs are hidden or protected
- [ ] The execution mode matches your server
- [ ] Static files are served by a proxy or a CDN

## Set up the database

Use PostgreSQL in production. SQLite is fine for development only.

```python title="project/settings.py"
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.environ["DB_NAME"],
        "USER": os.environ["DB_USER"],
        "PASSWORD": os.environ["DB_PASSWORD"],
        "HOST": os.environ["DB_HOST"],
        "PORT": os.environ.get("DB_PORT", "5432"),
    }
}
```

With a WSGI server, reuse connections with `CONN_MAX_AGE`, for example
`"CONN_MAX_AGE": 60`.

With an ASGI server, keep `CONN_MAX_AGE = 0` (the default) and use a
connection pool instead. On Django 5.1 or later with `psycopg[pool]`
installed, turn on the built-in pool:

```python title="project/settings.py"
DATABASES["default"]["OPTIONS"] = {"pool": True}
```

A pooler like PgBouncer in front of the database works too.

## Keep it fast

- Load relations in the same query as the list. See
  [Query optimization](guides/query-optimization.md).
- Keep the list paginated and set a sensible page size. See
  [Pagination](guides/pagination.md).
- Add `db_index=True` to fields you filter or sort by often.
- JSON is rendered with orjson by default. See
  [ORJSONRenderer](api/renderers/orjson_renderer.md) for its options.

## Run behind a reverse proxy

Put Nginx, Caddy or a load balancer in front of the server for TLS and static
files. Make the proxy forward the original host and scheme:

```nginx title="nginx.conf"
location / {
    proxy_pass http://127.0.0.1:8000;
    proxy_set_header Host $host;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
}
```

Then tell Django to trust the forwarded scheme, so `request.is_secure()` is
correct and `SECURE_SSL_REDIRECT` does not loop:

```python title="project/settings.py"
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
```

!!! warning

    Set `SECURE_PROXY_SSL_HEADER` only when a proxy always sets or strips
    this header. Otherwise clients can fake it.

## See also

- [Go to production](tutorial/production.md)
- [Sync and async](concepts/sync-and-async.md)
- [Troubleshooting](troubleshooting.md)
