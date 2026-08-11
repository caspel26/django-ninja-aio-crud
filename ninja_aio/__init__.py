"""Django Ninja AIO CRUD - Rest Framework"""

__version__ = "2.34.0"

__all__ = ["NinjaAIO", "NinjaAIORouter", "register_admin", "Branding"]

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
    if name == "NinjaAIO":
        from .api import NinjaAIO

        return NinjaAIO
    if name == "NinjaAIORouter":
        from .router import NinjaAIORouter

        return NinjaAIORouter
    if name == "register_admin":
        from .admin import register_admin

        return register_admin
    if name == "Branding":
        from .docs import Branding

        return Branding
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __dir__():
    return sorted(set(globals()) | set(__all__))
