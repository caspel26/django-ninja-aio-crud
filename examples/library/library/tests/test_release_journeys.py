"""Release checks that combine real HTTP authentication, hooks and persistent state."""

import asyncio
import datetime
import json
from unittest.mock import patch

from django.middleware.csrf import get_token
from django.test import AsyncClient, Client, RequestFactory

from ninja_aio.auth import encode_jwt

from library.models import ActivityLog, Book, Loan

from .base import LibraryTestCase, MODES, ParityTestCase, snapshot


class UserJourneyTests(LibraryTestCase):
    async def test_login_catalogue_borrow_return_and_delete_across_mounts(self):
        client = AsyncClient()

        async def send(mode, method, path, token=None, body=None, status=200):
            kwargs = {"headers": {"Authorization": f"Bearer {token}"}} if token else {}
            if body is not None:
                kwargs.update(data=json.dumps(body), content_type="application/json")
            response = await getattr(client, method)(f"/api/{mode}{path}", **kwargs)
            self.assertEqual(response.status_code, status, response.content)
            return response.json() if response.content else None

        librarian = await send("sync", "post", "/auth/login", body={
            "username": "libby", "password": "secret-libby",
        })
        reader = await send("async", "post", "/auth/login", body={
            "username": "rita", "password": "secret-rita",
        })
        staff_token, reader_token = librarian["access_token"], reader["access_token"]
        for index, mode in enumerate(MODES):
            other_mode = MODES[1 - index]
            book = await send(mode, "post", "/books/", staff_token, {
                "title": "  Journey  ", "isbn": f"900000000000{index}",
                "author_id": self.shelley.pk,
                "published": "2020-01-01" if index == 0 else None, "pages": 123,
            }, status=201)
            book_id = book["id"]
            updated = await send(other_mode, "patch", f"/books/{book_id}/", staff_token,
                                 {"published": None})
            self.assertEqual((updated["title"], updated["pages"], updated["published"]),
                             ("Journey", 123, None))
            await send(mode, "post", f"/books/{book_id}/tags/", staff_token,
                       {"add": [self.classics.pk]})
            detail = await send(other_mode, "get", f"/books/{book_id}", reader_token)
            self.assertEqual(detail["tags"], [self.classics.pk])
            loan = await send(other_mode, "post", "/loans/", reader_token,
                              {"book_id": book_id, "member": self.other.pk}, status=201)
            self.assertEqual(loan["member"], self.reader.pk)
            persisted = await Book.objects.aget(pk=book_id)
            self.assertFalse(persisted.available)
            renewed = await send(mode, "post", f"/loans/{loan['id']}/renew", reader_token, {"days": 3})
            self.assertEqual(renewed["renewals"], 1)
            await send(other_mode, "post", f"/loans/{loan['id']}/return", reader_token)
            await send(mode, "post", f"/loans/{loan['id']}/renew", reader_token, {}, status=409)
            persisted = await Book.objects.aget(pk=book_id)
            self.assertTrue(persisted.available)
            await send(mode, "delete", f"/books/{book_id}/", staff_token, status=204)
            await send(other_mode, "get", f"/books/{book_id}", reader_token, status=404)
            await send(other_mode, "post", f"/books/{book_id}/restore", staff_token)
            await send(mode, "delete", f"/loans/{loan['id']}/", staff_token, status=204)
            await send(other_mode, "delete", f"/books/{book_id}/hard-delete", staff_token, status=204)
            self.assertFalse(await Book.objects.filter(pk=book_id).aexists())
            self.assertFalse(await Loan.objects.filter(pk=loan["id"]).aexists())
            for event, ref in (("book_created", book_id), ("loan_created", loan["id"]),
                               ("loan_returned", loan["id"]), ("loan_deleted", book_id)):
                self.assertEqual(await ActivityLog.objects.filter(event=event, ref=ref).acount(), 1)

    async def test_concurrent_users_keep_their_own_loan_scope(self):
        reader_token, other_token = self.token(self.reader), self.token(self.other)

        async def loans(mode, token, expected):
            response = await AsyncClient().get(
                f"/api/{mode}/loans", headers={"Authorization": f"Bearer {token}"},
            )
            self.assertEqual(response.status_code, 200)
            self.assertEqual([loan["id"] for loan in response.json()["items"]], [expected])

        await asyncio.gather(*[
            loans(mode, token, expected)
            for _ in range(3) for mode in MODES
            for token, expected in ((reader_token, self.reader_loan.pk), (other_token, self.other_loan.pk))
        ])


class FailureJourneyTests(ParityTestCase):
    def test_author_can_be_created_with_an_explicit_null_date(self):
        result = self.both("post", "/authors/", self.librarian,
                           body={"name": "Undated Author", "birth_date": None}, status=201)
        self.assertIsNone(result["body"]["birth_date"])

    def test_nullable_author_date_can_be_cleared_without_changing_name(self):
        result = self.both("patch", f"/authors/{self.shelley.pk}/", self.librarian,
                           body={"birth_date": None}, status=200)
        self.assertIsNone(result["body"]["birth_date"])
        self.assertEqual(result["body"]["name"], "Mary Shelley")

    def test_bulk_hook_failure_rolls_back_item_and_log_then_continues(self):
        original_sync, original_async = Book.post_create, Book.apost_create

        def sync_hook(book):
            original_sync(book)
            if book.title == "Fail after log":
                raise RuntimeError("injected hook failure")

        async def async_hook(book):
            await original_async(book)
            if book.title == "Fail after log":
                raise RuntimeError("injected hook failure")

        body = [{"title": title, "isbn": isbn, "author": self.shelley.pk}
                for title, isbn in (("Before", "9100000000001"),
                                    ("Fail after log", "9100000000002"),
                                    ("After", "9100000000003"))]
        with patch.object(Book, "post_create", sync_hook), patch.object(Book, "apost_create", async_hook):
            result = self.both("post", "/books/bulk/", self.librarian, body=body, status=200)
        self.assertEqual((result["body"]["success"]["count"], result["body"]["errors"]["count"]), (2, 1))
        books = result["database"]["library.Book"]
        self.assertNotIn("Fail after log", [book["title"] for book in books])
        saved_ids = {book["id"] for book in books if book["title"] in ("Before", "After")}
        self.assertEqual({log["ref"] for log in result["database"]["library.ActivityLog"]
                          if log["event"] == "book_created"}, saved_ids)

    def test_expired_and_wrong_audience_tokens_leave_database_unchanged(self):
        before = snapshot()
        for mode in MODES:
            for claims, duration in (({"sub": str(self.reader.user_id)}, -60),
                                     ({"sub": str(self.reader.user_id), "aud": "another-app"}, 600)):
                token = encode_jwt(claims, duration=duration)
                response = self.client.post(
                    f"/api/{mode}/loans/", data=json.dumps({"book": self.frankenstein.pk}),
                    content_type="application/json", HTTP_AUTHORIZATION=f"Bearer {token}",
                )
                self.assertEqual(response.status_code, 401)
        self.assertEqual(Loan.objects.count(), 2)
        self.frankenstein.refresh_from_db()
        self.assertTrue(self.frankenstein.available)
        self.assertEqual(snapshot(), before)

    def test_catalogue_query_count_stays_constant_as_relations_grow(self):
        baseline = self.both("get", "/books?page_size=100", self.reader, status=200)
        for index in range(20):
            book = Book.objects.create(title=f"Scale {index}", isbn=f"920000000{index:04}",
                                       author=self.shelley, published=datetime.date(2020, 1, 1))
            book.tags.add(self.classics, self.horror)
        expanded = self.both("get", "/books?page_size=100", self.reader, status=200)
        self.assertEqual(len(expanded["body"]["items"]), 23)
        self.assertEqual(len(expanded["queries"]), len(baseline["queries"]))


class CookieWriteJourneyTests(LibraryTestCase):
    def test_cookie_write_succeeds_with_matching_csrf_token(self):
        for index, mode in enumerate(MODES):
            browser = Client(enforce_csrf_checks=True)
            response = browser.post(f"/api/{mode}/auth/login", data=json.dumps({
                "username": "rita", "password": "secret-rita",
            }), content_type="application/json")
            self.assertEqual(response.status_code, 200)
            request = RequestFactory().get("/")
            token = get_token(request)
            browser.cookies["csrftoken"] = request.META["CSRF_COOKIE"]
            book = Book.objects.create(title=f"Cookie {index}", isbn=f"930000000000{index}",
                                       author=self.shelley)
            response = browser.post(f"/api/{mode}/loans/", data=json.dumps({"book": book.pk}),
                                    content_type="application/json", HTTP_X_CSRFTOKEN=token)
            self.assertEqual(response.status_code, 201, response.content)
            self.assertEqual(response.json()["member"], self.reader.pk)
