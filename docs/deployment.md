# :material-rocket-launch: Deployment

How to deploy Django Ninja AIO to production.

---

## :material-server: ASGI Server

Django Ninja AIO is async-first, so you need an ASGI server. Django's built-in `runserver` is for development only.

=== "Uvicorn (Recommended)"

    ```bash
    pip install uvicorn
    uvicorn myproject.asgi:application --host 0.0.0.0 --port 8000 --workers 4
    ```

    !!! tip
        Uvicorn is the most popular ASGI server with excellent performance. Use `--workers` to match your CPU cores.

=== "Daphne"

    ```bash
    pip install daphne
    daphne -b 0.0.0.0 -p 8000 myproject.asgi:application
    ```

=== "Hypercorn"

    ```bash
    pip install hypercorn
    hypercorn myproject.asgi:application --bind 0.0.0.0:8000 --workers 4
    ```

### ASGI Configuration

Make sure your `asgi.py` is set up correctly:

```python
# myproject/asgi.py
import os
from django.core.asgi import get_asgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "myproject.settings")
application = get_asgi_application()
```

---

## :material-docker: Docker

A production-ready Dockerfile:

```dockerfile
FROM python:3.12-slim

WORKDIR /app

# Install dependencies
COPY pyproject.toml .
RUN pip install --no-cache-dir .

# Copy application code
COPY . .

# Collect static files
RUN python manage.py collectstatic --noinput

# Run with Uvicorn
EXPOSE 8000
CMD ["uvicorn", "myproject.asgi:application", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]
```

With Docker Compose:

```yaml
# docker-compose.yml
services:
  web:
    build: .
    ports:
      - "8000:8000"
    environment:
      - DJANGO_SETTINGS_MODULE=myproject.settings
      - DATABASE_URL=postgres://user:pass@db:5432/mydb
    depends_on:
      - db

  db:
    image: postgres:16
    environment:
      POSTGRES_DB: mydb
      POSTGRES_USER: user
      POSTGRES_PASSWORD: pass
    volumes:
      - pgdata:/var/lib/postgresql/data

volumes:
  pgdata:
```

---

## :material-shield-check: Production Checklist

Before deploying, make sure you've addressed these items:

### Django settings

```python
# settings.py

DEBUG = False
ALLOWED_HOSTS = ["yourdomain.com"]
SECRET_KEY = os.environ["SECRET_KEY"]  # Never hardcode!

# Security headers
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_SSL_REDIRECT = True
```

### Database

!!! warning "Don't use SQLite in production"
    SQLite is great for development but not suitable for production workloads. Use PostgreSQL for best async Django performance.

```python
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

### Static files

```bash
python manage.py collectstatic --noinput
```

Serve static files via a CDN or reverse proxy (Nginx, Caddy), not through Django.

---

## :material-speedometer: Performance Tips

<div class="grid cards" markdown>

-   :material-database:{ .lg .middle } **Query Optimization**

    ---

    Use `QuerySet` config on models for automatic `select_related` / `prefetch_related`

-   :material-page-next:{ .lg .middle } **Pagination**

    ---

    Always keep pagination enabled — never return unbounded querysets

-   :material-magnify:{ .lg .middle } **Database Indexes**

    ---

    Add `db_index=True` to frequently filtered fields

-   :material-code-json:{ .lg .middle } **ORJSON**

    ---

    Already enabled via `NinjaAIO` — fast JSON serialization out of the box

</div>

### Connection pooling

For high-traffic applications, use a connection pooler:

```bash
pip install django-pgpool
```

```python
DATABASES = {
    "default": {
        "ENGINE": "django_pgpool.backends.postgresql",
        # ... other settings
        "POOL_OPTIONS": {
            "max_size": 20,
            "min_size": 5,
        },
    }
}
```

---

## :material-swap-horizontal: Reverse Proxy

Run behind Nginx or Caddy for TLS termination, static file serving, and load balancing:

=== "Nginx"

    ```nginx
    upstream django {
        server 127.0.0.1:8000;
    }

    server {
        listen 443 ssl http2;
        server_name yourdomain.com;

        ssl_certificate /path/to/cert.pem;
        ssl_certificate_key /path/to/key.pem;

        location /static/ {
            alias /app/staticfiles/;
        }

        location / {
            proxy_pass http://django;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
        }
    }
    ```

=== "Caddy"

    ```caddyfile
    yourdomain.com {
        handle /static/* {
            root * /app/staticfiles
            file_server
        }

        handle {
            reverse_proxy localhost:8000
        }
    }
    ```

    !!! tip
        Caddy handles TLS certificates automatically via Let's Encrypt.

---

## :material-arrow-right-circle: See Also

<div class="grid cards" markdown>

-   :material-speedometer:{ .lg .middle } **Performance Benchmarks**

    ---

    See how Django Ninja AIO performs under load

    [:octicons-arrow-right-24: View Benchmarks](performance.md)

-   :material-code-json:{ .lg .middle } **ORJSON Renderer**

    ---

    Configure JSON serialization options

    [:octicons-arrow-right-24: Learn more](api/renderers/orjson_renderer.md)

-   :material-frequently-asked-questions:{ .lg .middle } **Troubleshooting**

    ---

    Common issues and solutions

    [:octicons-arrow-right-24: FAQ](troubleshooting.md)

</div>
