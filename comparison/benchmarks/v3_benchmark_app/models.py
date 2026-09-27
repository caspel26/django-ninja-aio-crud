"""Shared 2.36/v3 fixtures: legacy configs allow the same models on both versions."""
from django.db import models
from ninja_aio.models import ModelSerializer


class Author(ModelSerializer):
    name = models.CharField(max_length=120)

    class ReadSerializer:
        fields = ["id", "name"]


class Tag(ModelSerializer):
    name = models.CharField(max_length=120)

    class ReadSerializer:
        fields = ["id", "name"]


class Book(ModelSerializer):
    title = models.CharField(max_length=200)
    author = models.ForeignKey(Author, on_delete=models.CASCADE, related_name="books")
    tags = models.ManyToManyField(Tag, related_name="books")

    class ReadSerializer:
        fields = ["id", "title", "author", "tags"]

    class CreateSerializer:
        fields = ["title", "author"]


class Simple(ModelSerializer):
    title = models.CharField(max_length=200)

    class ReadSerializer:
        fields = ["id", "title"]

    class CreateSerializer:
        fields = ["title"]
