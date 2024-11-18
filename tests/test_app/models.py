from ninja_aio.models import ModelSerializer
from django.db import models


class TestModelSerializer(ModelSerializer):
    name = models.CharField(max_length=30)
    description = models.TextField(max_length=255)

    class ReadSerializer:
        fields = ["id", "name", "description"]

    class CreateSerializer:
        fields = ["name", "description"]

    class UpdateSerializer:
        fields = ["name", "description"]
