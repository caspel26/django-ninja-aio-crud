from tests import test_settings as base

SECRET_KEY = base.SECRET_KEY
DATABASES = base.DATABASES
DEFAULT_AUTO_FIELD = base.DEFAULT_AUTO_FIELD
ALLOWED_HOSTS = base.ALLOWED_HOSTS
TEMPLATES = base.TEMPLATES
LOGGING = base.LOGGING
NINJA_AIO_RAISE_SERIALIZATION_WARNINGS = base.NINJA_AIO_RAISE_SERIALIZATION_WARNINGS

INSTALLED_APPS = [
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "ninja_aio",
    "docs_quick_app",
    "docs_model_app",
    "docs_plain_app",
]
