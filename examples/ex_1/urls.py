# Basic urls configuration for the example app

from django.contrib import admin
from django.urls import path

from examples.ex_1.views import api

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/v1/", api.urls),
]
