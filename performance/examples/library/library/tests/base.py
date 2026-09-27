"""Shared fixtures and the sync/async parity harness."""

import datetime
import json
import re

from django.contrib.auth import get_user_model
from django.core.management.color import no_style
from django.db import connection, transaction
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from ninja_aio.auth import encode_jwt

from library.models import ActivityLog, Author, Book, Loan, Member, Tag

MODES = ("sync", "async")
_TIMESTAMP = re.compile(r"\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})?")
_JWT = re.compile(r"eyJ[\w-]+\.[\w-]+\.[\w-]+")
_SNAPSHOT_MODELS = (Member, Author, Tag, Book, Book.tags.through, Loan, ActivityLog)


class _Rollback(Exception):
    """Undo everything a scenario did, so the next mode starts from the same data."""


def normalize(value):
    """JSON-compatible copy with timestamps replaced, since the two runs happen at different instants."""
    text = json.dumps(value, default=str, sort_keys=True)
    return json.loads(_JWT.sub("<jwt>", _TIMESTAMP.sub("<datetime>", text)))


def snapshot() -> dict:
    return {
        model._meta.label: normalize(list(model.objects.order_by("pk").values()))
        for model in _SNAPSHOT_MODELS
    }


class LibraryTestCase(TestCase):
    """Users, members and a small catalogue shared by every test."""

    @classmethod
    def setUpTestData(cls):
        User = get_user_model()
        cls.librarian_user = User.objects.create_user("libby", password="secret-libby")
        cls.reader_user = User.objects.create_user("rita", password="secret-rita")
        cls.other_user = User.objects.create_user("otto", password="secret-otto")
        cls.librarian = Member.objects.create(user=cls.librarian_user, name="Libby", role="librarian")
        cls.reader = Member.objects.create(user=cls.reader_user, name="Rita", role="member")
        cls.other = Member.objects.create(user=cls.other_user, name="Otto", role="member")

        cls.shelley = Author.objects.create(name="Mary Shelley", birth_date=datetime.date(1797, 8, 30))
        cls.stoker = Author.objects.create(name="Bram Stoker")
        cls.lonely = Author.objects.create(name="No Books Yet")
        cls.classics = Tag.objects.create(name="classics")
        cls.horror = Tag.objects.create(name="horror")

        cls.frankenstein = Book.objects.create(
            title="Frankenstein", isbn="9780141439471", author=cls.shelley, pages=280,
            published=datetime.date(1818, 1, 1),
        )
        cls.last_man = Book.objects.create(
            title="The Last Man", isbn="9780199552351", author=cls.shelley, pages=480,
            published=datetime.date(1826, 1, 1),
        )
        cls.dracula = Book.objects.create(
            title="Dracula", isbn="9780141439846", author=cls.stoker, pages=418,
            published=datetime.date(1897, 5, 26),
        )
        cls.frankenstein.tags.add(cls.classics, cls.horror)
        cls.dracula.tags.add(cls.horror)

        today = timezone.localdate()
        cls.reader_loan = Loan.objects.create(
            book=cls.dracula, member=cls.reader, due_date=today + datetime.timedelta(days=3)
        )
        cls.other_loan = Loan.objects.create(
            book=cls.last_man, member=cls.other, due_date=today - datetime.timedelta(days=2)
        )
        Book.objects.filter(pk__in=[cls.dracula.pk, cls.last_man.pk]).update(available=False)

    @staticmethod
    def token(member: Member) -> str:
        return encode_jwt({"sub": str(member.user_id)}, duration=600)

    def auth(self, member: Member | None) -> dict:
        return {"HTTP_AUTHORIZATION": f"Bearer {self.token(member)}"} if member else {}

    def request(self, mode: str, method: str, path: str, member=None, body=None):
        kwargs = self.auth(member)
        if body is not None:
            kwargs.update(data=json.dumps(body), content_type="application/json")
        return getattr(self.client, method)(f"/api/{mode}{path}", **kwargs)


class ParityTestCase(LibraryTestCase):
    """Run a request against both mounts and require the same outcome."""

    def both(self, method: str, path: str, member=None, body=None, status: int | None = None):
        outcomes = {}
        for mode in MODES:
            try:
                with transaction.atomic():
                    with CaptureQueriesContext(connection) as queries:
                        response = self.request(mode, method, path, member, body)
                    is_json = response.get("Content-Type", "").startswith("application/json")
                    content = response.json() if response.content and is_json else None
                    outcomes[mode] = {
                        "status": response.status_code,
                        "body": normalize(content),
                        "database": snapshot(),
                        "queries": [q["sql"] for q in queries.captured_queries],
                    }
                    raise _Rollback
            except _Rollback:
                pass
            # PostgreSQL does not roll sequences back. Recreate the same initial
            # allocation state so response IDs and database snapshots can match.
            with connection.cursor() as cursor:
                for sql in connection.ops.sequence_reset_sql(no_style(), _SNAPSHOT_MODELS):
                    cursor.execute(sql)
        sync, async_ = outcomes["sync"], outcomes["async"]
        label = f"{method.upper()} {path}"
        self.assertEqual(sync["status"], async_["status"], f"{label}: status differs")
        self.assertEqual(sync["body"], async_["body"], f"{label}: body differs")
        self.assertEqual(sync["database"], async_["database"], f"{label}: database differs")
        self.assertEqual(
            len(sync["queries"]), len(async_["queries"]),
            f"{label}: query count differs\nsync:\n  " + "\n  ".join(sync["queries"])
            + "\nasync:\n  " + "\n  ".join(async_["queries"]),
        )
        if status is not None:
            self.assertEqual(sync["status"], status, f"{label}: {sync['body']}")
        return sync
