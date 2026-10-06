"""Django Ninja AIO CRUD - Rest Framework"""

import warnings
from importlib import import_module
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .api import NinjaAIO as NinjaAIO
    from .router import NinjaAIORouter as NinjaAIORouter
    from .views import APIView as APIView, APIViewSet as APIViewSet
    from .models import ModelSerializer as ModelSerializer
    from .models.serializers import Serializer as Serializer
    from .models.config import SchemaConfig as SchemaConfig
    from .decorators import action as action, on as on
    from .types import HttpMethod as HttpMethod

__version__ = "3.0.1"

_EXPORTS = {
    "NinjaAIO": ".api",
    "NinjaAIORouter": ".router",
    "APIView": ".views",
    "APIViewSet": ".views",
    "ModelSerializer": ".models",
    "Serializer": ".models.serializers",
    "SchemaConfig": ".models.config",
    "action": ".decorators",
    "on": ".decorators",
    "HttpMethod": ".types",
}

# Still importable from the top level until version 4.
_DEPRECATED_EXPORTS = {
    "register_admin": "ninja_aio.admin",
    "Branding": "ninja_aio.docs",
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
    if name in _DEPRECATED_EXPORTS:
        module = _DEPRECATED_EXPORTS[name]
        warnings.warn(
            f"Importing {name} from ninja_aio is deprecated; import it from {module}.",
            DeprecationWarning,
            stacklevel=2,
        )
        return getattr(import_module(module), name)
    module = _EXPORTS.get(name)
    if module is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    return getattr(import_module(module, __name__), name)


def __dir__():
    return sorted(globals().keys() | _EXPORTS.keys())
