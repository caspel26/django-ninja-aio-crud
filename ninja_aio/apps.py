from django.apps import AppConfig


class NinjaAioConfig(AppConfig):
    """Makes ``ninja_aio`` discoverable as a Django app.

    django-ninja-aio-crud works perfectly well without this — ``NinjaAIO``,
    ``APIViewSet``, etc. are plain importable classes, and nothing else in
    the framework requires ``"ninja_aio"`` to be listed in ``INSTALLED_APPS``.
    Adding it is only needed to pick up app-provided management commands,
    e.g. ``python manage.py mcp_server`` (see ``ninja_aio.mcp``).
    """

    name = "ninja_aio"
    verbose_name = "Ninja AIO"
