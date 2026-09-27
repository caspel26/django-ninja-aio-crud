"""Library domain: members, authors, books, tags and loans.

``Tag`` is a plain Django model served through a ``Serializer``; the others
are ``ModelSerializer``s. Hooks write to ``ActivityLog`` so tests can check
that sync and async endpoints run the same hooks.
"""

import datetime

from django.conf import settings
from django.db import models
from django.utils import timezone

from ninja_aio import ModelSerializer, SchemaConfig
from ninja_aio.models import hooks

LOAN_DAYS = 14


class ActivityLog(models.Model):
    event = models.CharField(max_length=50)
    ref = models.PositiveIntegerField()

    class Meta:
        ordering = ["pk"]


class Member(ModelSerializer):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="member")
    name = models.CharField(max_length=120)
    role = models.CharField(
        max_length=20,
        choices=[("librarian", "Librarian"), ("member", "Member")],
        default="member",
    )

    class Schemas:
        read = SchemaConfig(fields=["id", "name", "role"])


class Tag(models.Model):
    name = models.CharField(max_length=50, unique=True)

    class Meta:
        ordering = ["name"]


class Book(ModelSerializer):
    title = models.CharField(max_length=200)
    isbn = models.CharField(max_length=13, unique=True)
    author = models.ForeignKey("Author", on_delete=models.PROTECT, related_name="books")
    tags = models.ManyToManyField(Tag, related_name="books", blank=True)
    pages = models.PositiveIntegerField(default=0)
    published = models.DateField(null=True, blank=True)
    available = models.BooleanField(default=True)
    is_deleted = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Schemas:
        create = SchemaConfig(
            fields=["title", "isbn", "author"],
            optionals=[("pages", int), ("published", datetime.date)],
        )
        update = SchemaConfig(
            optionals=[
                ("title", str),
                ("pages", int),
                ("published", datetime.date),
                ("available", bool),
                ("author", int),
            ],
        )
        read = SchemaConfig(
            fields=["id", "title", "isbn", "author", "pages", "published", "available", "tags"],
            relations_as_id=["tags"],
        )
        detail = SchemaConfig(
            fields=["id", "title", "isbn", "author", "pages", "published", "available", "tags", "created_at"],
            relations_as_id=["tags"],
        )

    def post_create(self):
        ActivityLog.objects.create(event="book_created", ref=self.pk)

    async def apost_create(self):
        await ActivityLog.objects.acreate(event="book_created", ref=self.pk)

    def before_save(self):
        self.title = self.title.strip()

    @hooks.on_update("available")
    def availability_changed(self):
        ActivityLog.objects.create(event="book_available" if self.available else "book_unavailable", ref=self.pk)


class Author(ModelSerializer):
    name = models.CharField(max_length=120, unique=True)
    bio = models.TextField(blank=True, default="")
    birth_date = models.DateField(null=True, blank=True)

    class Schemas:
        create = SchemaConfig(
            fields=["name"],
            optionals=[("bio", str), ("birth_date", datetime.date)],
            nested={"books": Book},
        )
        update = SchemaConfig(optionals=[("name", str), ("bio", str), ("birth_date", datetime.date)])
        read = SchemaConfig(fields=["id", "name", "birth_date"])
        detail = SchemaConfig(fields=["id", "name", "bio", "birth_date", "books"])

    def on_delete(self):
        ActivityLog.objects.create(event="author_deleted", ref=self.pk or 0)


class Loan(ModelSerializer):
    book = models.ForeignKey(Book, on_delete=models.PROTECT, related_name="loans")
    member = models.ForeignKey(Member, on_delete=models.CASCADE, related_name="loans")
    borrowed_at = models.DateTimeField(default=timezone.now)
    due_date = models.DateField()
    returned_at = models.DateTimeField(null=True, blank=True)
    renewals = models.PositiveSmallIntegerField(default=0)

    class Schemas:
        create = SchemaConfig(fields=["book"], optionals=[("member", int)])
        update = SchemaConfig(
            optionals=[("due_date", datetime.date), ("returned_at", datetime.datetime), ("renewals", int)],
        )
        read = SchemaConfig(
            fields=["id", "book", "member", "borrowed_at", "due_date", "returned_at", "renewals"],
            relations_as_id=["member"],
        )

    def on_create_before_save(self):
        if not self.due_date:
            self.due_date = timezone.localdate() + datetime.timedelta(days=LOAN_DAYS)

    @hooks.on_create
    def book_borrowed(self):
        Book.objects.filter(pk=self.book_id).update(available=False)
        ActivityLog.objects.create(event="loan_created", ref=self.pk)

    @hooks.on_update("returned_at")
    def book_returned(self):
        if self.returned_at:
            Book.objects.filter(pk=self.book_id).update(available=True)
            ActivityLog.objects.create(event="loan_returned", ref=self.pk)

    @hooks.on_delete
    def loan_removed(self):
        Book.objects.filter(pk=self.book_id).update(available=True)
        ActivityLog.objects.create(event="loan_deleted", ref=self.book_id)
