"""Django Ninja AIO CRUD - Rest Framework"""

__version__ = "2.33.0"

from .api import NinjaAIO
from .admin import register_admin
from .docs import Branding
from .router import NinjaAIORouter

__all__ = ["NinjaAIO", "NinjaAIORouter", "register_admin", "Branding"]
