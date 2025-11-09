# Base usage example with a User model with Customer ForeignKey.

from django.db import models
from ninja_aio.models import ModelSerializer


class Customer(ModelSerializer):
    name = models.CharField(max_length=255)
    email = models.EmailField(unique=True)

    users: models.QuerySet["User"]

    class ReadSerializer:
        # Note: 'users' field will represent related User instances as list of their RelatedSerializer data
        # This is automatically handled by NinjaAIO's ModelSerializer
        fields = ["id", "name", "email", "users"]

    class CreateSerializer:
        fields = ["name", "email"]

    class UpdateSerializer:
        optionals = [
            ("name", str),
            ("email", str),
        ]

    def __str__(self):
        return self.name


class User(ModelSerializer):
    username = models.CharField(max_length=150, unique=True)
    email = models.EmailField(unique=True)
    first_name = models.CharField(max_length=30, blank=True)
    last_name = models.CharField(max_length=30, blank=True)
    customer = models.ForeignKey(
        Customer, on_delete=models.CASCADE, related_name="users"
    )

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}"

    class ReadSerializer:
        fields = ["id", "username", "email", "customer"]
        customs = [
            ("full_name", str, ""),
        ]

    class CreateSerializer:
        fields = ["username", "email", "customer"]
        optionals = [("first_name", str), ("last_name", str)]

    class UpdateSerializer:
        optionals = [
            ("email", str),
            ("first_name", str),
            ("last_name", str),
        ]

    def __str__(self):
        return self.username
