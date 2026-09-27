"""Print the catalogue and open loans as JSON using the sync serializer methods."""

import json

from django.core.management.base import BaseCommand

from library.models import Book, Loan


class Command(BaseCommand):
    help = "Print the catalogue and the open loans."

    def handle(self, *args, **options):
        books = Book.get_queryset(optimize_for="read").filter(is_deleted=False).order_by("title")
        loans = Loan.get_queryset().filter(returned_at__isnull=True).order_by("due_date")
        report = {
            "books": Book.model_dumps(list(books)),
            "open_loans": Loan.model_dumps(list(loans)),
        }
        self.stdout.write(json.dumps(report, default=str, indent=2))
