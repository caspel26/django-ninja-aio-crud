# base example of a ViewSet using NinjaAIO and APIViewSet without any relation and auth.

from ninja_aio import NinjaAIO
from ninja_aio.views import APIViewSet

from examples.ex_1.models import User

api = NinjaAIO()


class UserViewSet(APIViewSet):
    model = User
    api = api


UserViewSet().add_views_to_route()
