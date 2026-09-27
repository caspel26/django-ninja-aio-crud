"""Fill the database with sample data using the sync serializer methods."""

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

from library.models import Author, Book, Loan, Member
from library.serializers import TagSerializer


class Command(BaseCommand):
    help = "Create sample users, authors, books, tags and a loan."

    def handle(self, *args, **options):
        User = get_user_model()
        librarian_user = User.objects.create_user("librarian", password="librarian")
        reader_user = User.objects.create_user("reader", password="reader")
        Member.objects.create(user=librarian_user, name="Libby", role="librarian")
        reader = Member.objects.create(user=reader_user, name="Rita", role="member")

        tags = TagSerializer()
        classics = tags.create({"name": "Classics"})
        tags.create({"name": "Science"})

        # Nested write: the author and their books in one call.
        author = Author.create(
            {
                "name": "Mary Shelley",
                "books": [
                    {"title": "Frankenstein", "isbn": "9780141439471", "pages": 280},
                    {"title": "The Last Man", "isbn": "9780199552351", "pages": 480},
                ],
            }
        )
        result = Book.bulk_create(
            [
                {"title": "Dracula", "isbn": "9780141439846", "author": Author.create({"name": "Bram Stoker"}).pk},
                {"title": "Dracula", "isbn": "9780141439846", "author": author.pk},
            ]
        )
        frankenstein = Book.get(isbn="9780141439471")
        frankenstein.tags.add(classics.pk)
        Loan.create({"book": frankenstein.pk, "member": reader.pk})

        self.stdout.write(
            f"Created {Book.objects.count()} books; bulk create: "
            f"{len(result.succeeded)} saved, {len(result.failed)} failed."
        )
