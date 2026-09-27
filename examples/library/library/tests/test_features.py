"""Features outside the HTTP parity suite: cookies, MCP, admin, commands and tasks."""

import datetime
import io
import json

from asgiref.sync import async_to_sync
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import Client, TestCase

from ninja_aio.mcp import NinjaAIOMCPServer, invoke_tool

from library.api import api
from library.models import ActivityLog, Author, Book, Loan, Member, Tag
from library.tasks import extend_all_open_loans, send_due_reminders

from .base import LibraryTestCase


class CookieAuthTests(LibraryTestCase):
    def setUp(self):
        self.browser = Client(enforce_csrf_checks=True)

    def _login(self, mode):
        response = self.browser.post(
            f"/api/{mode}/auth/login",
            data=json.dumps({"username": "rita", "password": "secret-rita"}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.cookies["access_token"]["httponly"])

    def test_cookie_authenticates_safe_requests(self):
        for mode in ("sync", "async"):
            self._login(mode)
            self.assertEqual(self.browser.get(f"/api/{mode}/books").status_code, 200)

    def test_cookie_writes_need_a_csrf_token(self):
        for mode in ("sync", "async"):
            self._login(mode)
            body = json.dumps({"book": self.frankenstein.pk})
            response = self.browser.post(f"/api/{mode}/loans/", data=body, content_type="application/json")
            self.assertEqual(response.status_code, 403)

    def test_logout_removes_the_cookie(self):
        self._login("sync")
        response = self.browser.post("/api/sync/auth/logout")
        self.assertEqual(response.cookies["access_token"].value, "")


class McpTests(LibraryTestCase):
    def test_both_mounts_become_distinct_tools(self):
        tools = NinjaAIOMCPServer(api, name="library")._tools
        self.assertIn("sync_books_book_list", tools)
        self.assertIn("async_books_book_list", tools)
        self.assertIn("async_loans_loan_return_book", tools)

    def test_list_tool_returns_the_same_page_in_both_modes(self):
        tools = NinjaAIOMCPServer(api, name="library")._tools
        results = [
            async_to_sync(invoke_tool)(tools[f"{mode}_authors_author_list"], {"page_size": 2})
            for mode in ("sync", "async")
        ]
        self.assertEqual(results[0], results[1])
        self.assertEqual((results[0]["count"], len(results[0]["items"])), (3, 2))


class AdminTests(LibraryTestCase):
    def test_generated_admin_pages_render(self):
        admin = get_user_model().objects.create_superuser("admin", password="admin-secret")
        self.client.force_login(admin)
        for path in ("book", "author", "loan", "member", "tag"):
            self.assertEqual(self.client.get(f"/admin/library/{path}/").status_code, 200, path)
        response = self.client.get(f"/admin/library/book/{self.frankenstein.pk}/change/")
        self.assertEqual(response.status_code, 200)


class CommandTests(TestCase):
    def test_seed_and_report_use_the_sync_facade(self):
        out = io.StringIO()
        call_command("seed_library", stdout=out)
        self.assertIn("bulk create: 1 saved, 1 failed", out.getvalue())
        self.assertEqual(Author.objects.get(name="Mary Shelley").books.count(), 2)
        self.assertEqual(Tag.objects.filter(name__in=["classics", "science"]).count(), 2)
        self.assertEqual(Loan.objects.count(), 1)
        self.assertFalse(Book.objects.get(isbn="9780141439471").available)

        out = io.StringIO()
        call_command("library_report", stdout=out)
        report = json.loads(out.getvalue())
        self.assertEqual(len(report["books"]), 3)
        self.assertEqual(report["open_loans"][0]["book"]["title"], "Frankenstein")


class TaskTests(LibraryTestCase):
    async def test_reminders_use_the_async_facade(self):
        loans = await send_due_reminders(within_days=5)
        self.assertEqual({loan["id"] for loan in loans}, {self.reader_loan.pk, self.other_loan.pk})
        self.assertEqual(await ActivityLog.objects.filter(event="reminder_sent").acount(), 2)

    async def test_extend_runs_update_hooks(self):
        count = await extend_all_open_loans(days=3)
        self.assertEqual(count, 2)
        loan = await Loan.objects.aget(pk=self.reader_loan.pk)
        self.assertEqual(loan.due_date, self.reader_loan.due_date + datetime.timedelta(days=3))

    def test_members_exist(self):
        self.assertEqual(Member.objects.count(), 3)


class MCPMemberContextTests(LibraryTestCase):
    async def test_selected_reader_can_list_books_but_cannot_create_them(self):
        from library.mcp_server import member_request_factory
        from ninja_aio.mcp.invoke import ToolInvocationError

        factory = await member_request_factory("rita")
        tools = NinjaAIOMCPServer(api, name="library", request_factory=factory)._tools
        for mode in ("sync", "async"):
            result = await invoke_tool(tools[f"{mode}_books_book_list"], {"page_size": 2}, factory)
            self.assertEqual((result["count"], len(result["items"])), (3, 2))
            with self.assertRaises(ToolInvocationError) as refused:
                await invoke_tool(tools[f"{mode}_books_book_create"],
                                  {"title": "Forbidden", "isbn": "0000000000000", "author": self.shelley.pk}, factory)
            self.assertEqual(refused.exception.status_code, 403)

    async def test_missing_member_fails_before_starting_stdio(self):
        from library.mcp_server import member_request_factory
        with self.assertRaisesRegex(ValueError, "No active library member"):
            await member_request_factory("does-not-exist")
