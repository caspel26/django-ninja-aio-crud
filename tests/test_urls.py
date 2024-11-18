from django.urls import path

from tests.test_app.api import api

urlpatterns = [
    path("/", api.urls),
]
