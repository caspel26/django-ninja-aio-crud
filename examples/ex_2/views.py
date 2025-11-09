# base example of a ViewSet using NinjaAIO and APIViewSet without any relation and auth.

from ninja_aio import NinjaAIO
from ninja_aio.views import APIViewSet

from examples.ex_2 import models
from examples.ex_2.auth import JwtAuth

api = NinjaAIO()


class BaseAPIViewSet(APIViewSet):
    api = api
    auth = [JwtAuth()]


class CustomerViewSet(BaseAPIViewSet):
    model = models.Customer


class UserViewSet(BaseAPIViewSet):
    model = models.User


CustomerViewSet().add_views_to_route()
UserViewSet().add_views_to_route()
