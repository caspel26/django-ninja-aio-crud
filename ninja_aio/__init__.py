"""Django Ninja AIO CRUD - Rest Framework"""

from importlib import import_module

__version__ = "2.36.0"

_EXPORTS = {
    "NinjaAIO": ".api",
    "NinjaAIORouter": ".router",
    "register_admin": ".admin",
    "Branding": ".docs",
    "APIView": ".views",
    "APIViewSet": ".views",
    "ModelSerializer": ".models",
    "Serializer": ".models.serializers",
    "SchemaConfig": ".models.config",
    "action": ".decorators",
    "on": ".decorators",
    "HttpMethod": ".types",
}

__all__ = list(_EXPORTS)

# Public names are resolved lazily (PEP 562) instead of imported eagerly here.
#
# `ninja_aio.models.ModelSerializer` is a `django.db.models.Model` subclass,
# defined as soon as `.api` -> `.views` -> `.models` gets imported. If this
# module imported `.api` eagerly like it used to, merely doing
# `import ninja_aio` (which Django does to locate `ninja_aio.apps.NinjaAioConfig`
# whenever `"ninja_aio"` is listed in INSTALLED_APPS — see `ninja_aio/apps.py`
# and `ninja_aio/management/commands/mcp_server.py`) would define that model
# *before* Django's app registry is ready, raising AppRegistryNotReady. Lazy
# resolution keeps `import ninja_aio` itself side-effect-free; Django's own
# app-loading sequence then imports `ninja_aio.models` at the correct time.
def __getattr__(name):
    module = _EXPORTS.get(name)
    if module is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    return getattr(import_module(module, __name__), name)


def __dir__():
    return sorted(globals().keys() | _EXPORTS.keys())
