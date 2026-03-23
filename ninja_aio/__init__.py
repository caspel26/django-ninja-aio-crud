"""Django Ninja AIO CRUD - Rest Framework"""

__version__ = "2.28.0"

from .api import NinjaAIO
from .admin import register_admin

__all__ = ["NinjaAIO", "register_admin"]
