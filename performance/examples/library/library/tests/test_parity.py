"""Every HTTP scenario runs on /api/sync and /api/async with identical results."""

import datetime

from django.utils import timezone

from library.models import Book

from .base import ParityTestCase


class AuthorParityTests(ParityTestCase):
    def test_anyone_can_list_authors(self):
        result = self.both("get", "/authors", status=200)
        self.assertEqual(result["body"]["count"], 3)

    def test_detail_includes_reverse_books(self):
        result = self.both("get", f"/authors/{self.shelley.pk}", status=200)
        self.assertEqual(sorted(b["title"] for b in result["body"]["books"]), ["Frankenstein", "The Last Man"])

    def test_anonymous_and_reader_cannot_create(self):
        self.both("post", "/authors/", body={"name": "Anon"}, status=401)
        self.both("post", "/authors/", self.reader, body={"name": "Reader"}, status=403)

    def test_librarian_creates_author_with_nested_books(self):
        body = {
            "name": "Jane Austen",
            "books": [
                {"title": " Emma ", "isbn": "9780141439587", "pages": 474},
                {"title": "Persuasion", "isbn": "9780141439686"},
            ],
        }
        result = self.both("post", "/authors/", self.librarian, body=body, status=201)
        books = result["database"]["library.Book"]
        self.assertIn("Emma", [b["title"] for b in books])

    def test_nested_book_with_duplicate_isbn_saves_nothing(self):
        body = {"name": "Copycat", "books": [{"title": "Again", "isbn": self.dracula.isbn}]}
        result = self.both("post", "/authors/", self.librarian, body=body, status=409)
        self.assertNotIn("Copycat", [a["name"] for a in result["database"]["library.Author"]])

    def test_invalid_date_is_rejected(self):
        self.both("patch", f"/authors/{self.stoker.pk}/", self.librarian, body={"birth_date": "soon"}, status=422)

    def test_librarian_updates_author(self):
        result = self.both("patch", f"/authors/{self.stoker.pk}/", self.librarian, body={"bio": "Irish"}, status=200)
        self.assertEqual(result["body"]["name"], "Bram Stoker")

    def test_author_with_books_cannot_be_deleted(self):
        self.both("delete", f"/authors/{self.shelley.pk}/", self.librarian, status=409)

    def test_author_without_books_is_deleted(self):
        result = self.both("delete", f"/authors/{self.lonely.pk}/", self.librarian, status=204)
        self.assertIn("author_deleted", [log["event"] for log in result["database"]["library.ActivityLog"]])

    def test_missing_author_is_404(self):
        self.both("get", "/authors/999999", status=404)


class BookReadParityTests(ParityTestCase):
    def test_books_need_a_token(self):
        self.both("get", "/books", status=401)

    def test_reader_lists_books_with_nested_author(self):
        result = self.both("get", "/books", self.reader, status=200)
        first = result["body"]["items"][0]
        self.assertEqual(first["title"], "Dracula")
        self.assertEqual(first["author"]["name"], "Bram Stoker")
        self.assertEqual(sorted(result["body"]["items"][1]["tags"]), sorted([self.classics.pk, self.horror.pk]))

    def _titles(self, query):
        result = self.both("get", f"/books?{query}", self.reader, status=200)
        return [item["title"] for item in result["body"]["items"]]

    def test_filters(self):
        self.assertEqual(self._titles("title=frank"), ["Frankenstein"])
        self.assertEqual(self._titles("available=true"), ["Frankenstein"])
        self.assertEqual(self._titles("pages=418"), ["Dracula"])
        self.assertEqual(self._titles("published__gte=1820-01-01&published__lte=1890-01-01"), ["The Last Man"])
        self.assertEqual(self._titles(f"author={self.stoker.pk}"), ["Dracula"])
        self.assertEqual(self._titles("author_name=shel"), ["Frankenstein", "The Last Man"])
        self.assertEqual(self._titles("search=9780141439846"), ["Dracula"])

    def test_ordering_and_pagination(self):
        self.assertEqual(self._titles("ordering=-pages"), ["The Last Man", "Dracula", "Frankenstein"])
        self.assertEqual(self._titles("ordering=not_allowed"), ["Dracula", "Frankenstein", "The Last Man"])
        result = self.both("get", "/books?page=2&page_size=2", self.reader, status=200)
        self.assertEqual((result["body"]["count"], len(result["body"]["items"])), (3, 1))

    def test_field_selection(self):
        result = self.both("get", "/books?fields=id,title&ordering=title", self.reader, status=200)
        self.assertEqual(set(result["body"]["items"][0]), {"id", "title"})
        result = self.both("get", f"/books/{self.dracula.pk}?fields=isbn", self.reader, status=200)
        self.assertEqual(result["body"], {"isbn": self.dracula.isbn})

    def test_detail_and_missing(self):
        result = self.both("get", f"/books/{self.frankenstein.pk}", self.reader, status=200)
        self.assertIn("created_at", result["body"])
        self.both("get", "/books/999999", self.reader, status=404)

    def test_stats_action(self):
        result = self.both("get", "/books/stats", self.reader, status=200)
        self.assertEqual(result["body"], {"total": 3, "available": 1})

    def test_tags_of_a_book(self):
        result = self.both("get", f"/books/{self.frankenstein.pk}/tags", self.reader, status=200)
        self.assertEqual(sorted(t["name"] for t in result["body"]["items"]), ["classics", "horror"])
        result = self.both("get", f"/books/{self.frankenstein.pk}/tags?name=clas", self.reader, status=200)
        self.assertEqual([t["name"] for t in result["body"]["items"]], ["classics"])


class BookWriteParityTests(ParityTestCase):
    def _book(self, **extra):
        return {"title": "Carmilla", "isbn": "9781503278851", "author": self.stoker.pk, **extra}

    def test_reader_cannot_write(self):
        self.both("post", "/books/", self.reader, body=self._book(), status=403)
        self.both("patch", f"/books/{self.dracula.pk}/", self.reader, body={"pages": 1}, status=403)
        self.both("delete", f"/books/{self.dracula.pk}/", self.reader, status=403)

    def test_create_with_either_foreign_key_spelling(self):
        for body in (self._book(), {**self._book(), "author_id": self.stoker.pk, "author": None}):
            body = {k: v for k, v in body.items() if v is not None}
            result = self.both("post", "/books/", self.librarian, body=body, status=201)
            self.assertEqual(result["body"]["author"]["id"], self.stoker.pk)
            self.assertIn("book_created", [log["event"] for log in result["database"]["library.ActivityLog"]])

    def test_create_errors(self):
        self.both("post", "/books/", self.librarian, body=self._book(isbn=self.dracula.isbn), status=409)
        self.both("post", "/books/", self.librarian, body={"title": "No ISBN"}, status=422)
        self.both("post", "/books/", self.librarian, body=self._book(author=999999), status=404)

    def test_update_runs_the_field_hook(self):
        result = self.both("patch", f"/books/{self.frankenstein.pk}/", self.librarian, body={"available": False}, status=200)
        self.assertFalse(result["body"]["available"])
        self.assertIn("book_unavailable", [log["event"] for log in result["database"]["library.ActivityLog"]])

    def test_update_foreign_key(self):
        result = self.both("patch", f"/books/{self.dracula.pk}/", self.librarian, body={"author": self.shelley.pk}, status=200)
        self.assertEqual(result["body"]["author"]["id"], self.shelley.pk)

    def test_soft_delete_restore_and_hard_delete(self):
        path = f"/books/{self.frankenstein.pk}"
        result = self.both("delete", f"{path}/", self.librarian, status=204)
        self.assertTrue(next(b for b in result["database"]["library.Book"] if b["id"] == self.frankenstein.pk)["is_deleted"])
        Book.objects.filter(pk=self.frankenstein.pk).update(is_deleted=True)
        self.both("get", path, self.reader, status=404)
        self.assertEqual(self.both("get", "/books", self.reader)["body"]["count"], 2)
        self.both("post", f"{path}/restore", self.reader, status=403)
        self.both("post", f"{path}/restore", self.librarian, status=200)
        result = self.both("delete", f"{path}/hard-delete", self.librarian, status=204)
        self.assertNotIn(self.frankenstein.pk, [b["id"] for b in result["database"]["library.Book"]])

    def test_bulk_create(self):
        body = [self._book(), self._book(isbn=self.dracula.isbn, title="Dup")]
        result = self.both("post", "/books/bulk/", self.librarian, body=body, status=200)
        self.assertEqual((result["body"]["success"]["count"], result["body"]["errors"]["count"]), (1, 1))

    def test_bulk_update_and_delete(self):
        body = [{"id": self.frankenstein.pk, "pages": 300}, {"id": 999999, "pages": 1}]
        result = self.both("patch", "/books/bulk/", self.librarian, body=body, status=200)
        self.assertEqual((result["body"]["success"]["count"], result["body"]["errors"]["count"]), (1, 1))
        result = self.both("delete", "/books/bulk/", self.librarian, body={"ids": [self.frankenstein.pk, 999999]}, status=200)
        self.assertEqual(result["body"]["success"]["details"], [self.frankenstein.pk])
        self.both("delete", "/books/bulk/", self.reader, body={"ids": [self.frankenstein.pk]}, status=403)

    def test_add_and_remove_tags(self):
        body = {"add": [self.classics.pk, 999999], "remove": [self.horror.pk]}
        result = self.both("post", f"/books/{self.dracula.pk}/tags/", self.librarian, body=body, status=200)
        links = [(row["book_id"], row["tag_id"]) for row in result["database"]["library.Book_tags"]]
        self.assertIn((self.dracula.pk, self.classics.pk), links)
        self.assertNotIn((self.dracula.pk, self.horror.pk), links)

    def test_reader_cannot_change_tags(self):
        self.both("post", f"/books/{self.dracula.pk}/tags/", self.reader, body={"add": [self.classics.pk]}, status=403)


class TagParityTests(ParityTestCase):
    def test_crud(self):
        result = self.both("post", "/tags/", self.librarian, body={"name": "  Gothic "}, status=201)
        self.assertEqual(result["body"]["name"], "gothic")
        self.assertIn("tag_created", [log["event"] for log in result["database"]["library.ActivityLog"]])
        self.both("post", "/tags/", self.librarian, body={"name": "horror"}, status=409)
        self.both("patch", f"/tags/{self.classics.pk}/", self.librarian, body={"name": "Old"}, status=200)
        self.both("delete", f"/tags/{self.classics.pk}/", self.librarian, status=204)
        result = self.both("get", "/tags", self.reader, status=200)
        self.assertEqual([t["name"] for t in result["body"]["items"]], ["classics", "horror"])
        self.both("post", "/tags/", self.reader, body={"name": "nope"}, status=403)


class LoanParityTests(ParityTestCase):
    def test_reader_borrows_a_book_for_themselves(self):
        body = {"book": self.frankenstein.pk, "member": self.other.pk}
        result = self.both("post", "/loans/", self.reader, body=body, status=201)
        self.assertEqual(result["body"]["member"], self.reader.pk)
        self.assertEqual(result["body"]["due_date"], str(timezone.localdate() + datetime.timedelta(days=14)))
        book = next(b for b in result["database"]["library.Book"] if b["id"] == self.frankenstein.pk)
        self.assertFalse(book["available"])

    def test_librarian_lends_to_a_member(self):
        body = {"book_id": self.frankenstein.pk, "member": self.other.pk}
        result = self.both("post", "/loans/", self.librarian, body=body, status=201)
        self.assertEqual(result["body"]["member"], self.other.pk)

    def test_members_only_see_their_loans(self):
        result = self.both("get", "/loans", self.reader, status=200)
        self.assertEqual([loan["id"] for loan in result["body"]["items"]], [self.reader_loan.pk])
        result = self.both("get", "/loans?ordering=due_date", self.librarian, status=200)
        self.assertEqual([loan["id"] for loan in result["body"]["items"]], [self.other_loan.pk, self.reader_loan.pk])
        self.both("get", f"/loans/{self.other_loan.pk}", self.reader, status=403)
        self.both("get", f"/loans/{self.reader_loan.pk}", self.reader, status=200)

    def test_active_filter(self):
        self.both("post", f"/loans/{self.reader_loan.pk}/return", self.reader, status=200)
        result = self.both("get", "/loans?active=true", self.librarian, status=200)
        self.assertEqual(result["body"]["count"], 2)

    def test_renew(self):
        path = f"/loans/{self.reader_loan.pk}/renew"
        result = self.both("post", path, self.reader, body={"days": 5}, status=200)
        self.assertEqual(result["body"]["renewals"], 1)
        self.assertEqual(result["body"]["due_date"], str(self.reader_loan.due_date + datetime.timedelta(days=5)))
        self.both("post", f"/loans/{self.other_loan.pk}/renew", self.reader, body={"days": 5}, status=403)
        self.both("post", "/loans/999999/renew", self.reader, body={"days": 5}, status=404)
        self.both("post", path, self.reader, body={"days": "many"}, status=422)

    def test_renewal_limit(self):
        type(self.reader_loan).objects.filter(pk=self.reader_loan.pk).update(renewals=2)
        self.both("post", f"/loans/{self.reader_loan.pk}/renew", self.reader, body={}, status=409)

    def test_return(self):
        result = self.both("post", f"/loans/{self.reader_loan.pk}/return", self.reader, status=200)
        self.assertIsNotNone(result["body"]["returned_at"])
        book = next(b for b in result["database"]["library.Book"] if b["id"] == self.dracula.pk)
        self.assertTrue(book["available"])
        self.assertIn("loan_returned", [log["event"] for log in result["database"]["library.ActivityLog"]])
        self.both("post", f"/loans/{self.other_loan.pk}/return", self.reader, status=403)

    def test_only_librarians_update_and_delete(self):
        self.both("patch", f"/loans/{self.reader_loan.pk}/", self.reader, body={"renewals": 0}, status=403)
        self.both("patch", f"/loans/{self.reader_loan.pk}/", self.librarian, body={"due_date": "2030-01-01"}, status=200)
        result = self.both("delete", f"/loans/{self.reader_loan.pk}/", self.librarian, status=204)
        book = next(b for b in result["database"]["library.Book"] if b["id"] == self.dracula.pk)
        self.assertTrue(book["available"])


class MemberReportAuthParityTests(ParityTestCase):
    def test_members_are_for_librarians(self):
        result = self.both("get", "/members", self.librarian, status=200)
        self.assertEqual(result["body"]["count"], 3)
        self.both("get", "/members", self.reader, status=403)
        self.both("post", "/members/", self.librarian, body={}, status=404)

    def test_overdue_report(self):
        result = self.both("get", "/reports/overdue", self.librarian, status=200)
        self.assertEqual([loan["id"] for loan in result["body"]], [self.other_loan.pk])
        self.both("get", "/reports/overdue", self.reader, status=403)
        self.both("get", "/reports/overdue", status=401)

    def test_login(self):
        result = self.both("post", "/auth/login", body={"username": "rita", "password": "secret-rita"}, status=200)
        self.assertIn("access_token", result["body"])
        self.both("post", "/auth/login", body={"username": "rita", "password": "wrong"}, status=401)
        self.both("post", "/auth/login", body={"username": "rita"}, status=422)

    def test_expired_or_forged_tokens_are_rejected(self):
        for mode in ("sync", "async"):
            response = self.client.get(f"/api/{mode}/books", HTTP_AUTHORIZATION="Bearer not-a-token")
            self.assertEqual(response.status_code, 401)

    def test_inactive_user_is_rejected(self):
        self.reader_user.is_active = False
        self.reader_user.save()
        self.both("get", "/books", self.reader, status=401)
