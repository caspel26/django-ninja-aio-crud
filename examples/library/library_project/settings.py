"""Settings for the django-ninja-aio-crud library example."""

import os
from pathlib import Path

from joserfc import jwk

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = os.environ.get("LIBRARY_SECRET_KEY", "library-example-not-a-secret")
DEBUG = True
ALLOWED_HOSTS = ["*"]

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "ninja_aio",
    "library",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
]

ROOT_URLCONF = "library_project.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

ASGI_APPLICATION = "library_project.asgi.application"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": os.environ.get("LIBRARY_SQLITE_PATH", str(BASE_DIR / "db.sqlite3")),
    }
}

if os.environ.get("LIBRARY_DATABASE_BACKEND") == "postgresql":
    DATABASES["default"] = {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.environ.get("PGDATABASE", "ninja_aio"),
        "USER": os.environ.get("PGUSER", "postgres"),
        "PASSWORD": os.environ.get("PGPASSWORD", ""),
        "HOST": os.environ.get("PGHOST", "127.0.0.1"),
        "PORT": os.environ.get("PGPORT", "5432"),
    }

USE_TZ = True
TIME_ZONE = "UTC"
STATIC_URL = "static/"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# One HMAC key signs and verifies tokens. Use RSA or EC keys in production.
_JWT_KEY = jwk.OctKey.import_key(
    os.environ.get("LIBRARY_JWT_SECRET", "library-example-signing-key-0123456789abcdef")
)
JWT_PRIVATE_KEY = _JWT_KEY
JWT_PUBLIC_KEY = _JWT_KEY
JWT_ALGORITHM = "HS256"
JWT_ISSUER = "library"
JWT_AUDIENCE = "library-clients"
