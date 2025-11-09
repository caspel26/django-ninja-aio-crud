# Base usage example with a User model without any relation.

from django.db import models
from ninja_aio.models import ModelSerializer


class User(ModelSerializer):
    username = models.CharField(max_length=150, unique=True)
    email = models.EmailField(unique=True)
    first_name = models.CharField(max_length=30, blank=True)
    last_name = models.CharField(max_length=30, blank=True)

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}"

    class ReadSerializer:
        fields = ["id", "username", "email"]
        customs = [
            ("full_name", str, ""),
        ]

    class CreateSerializer:
        fields = ["username", "email"]
        optionals = [("first_name", str), ("last_name", str)]

    class UpdateSerializer:
        optionals = [
            ("email", str),
            ("first_name", str),
            ("last_name", str),
        ]

    def __str__(self):
        return self.username
