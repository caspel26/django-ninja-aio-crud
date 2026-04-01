"""Django Ninja AIO CRUD - Rest Framework"""

__version__ = "2.30.0"

from .api import NinjaAIO
from .admin import register_admin
from .docs import Branding

__all__ = ["NinjaAIO", "register_admin", "Branding"]
