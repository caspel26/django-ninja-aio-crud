from django.contrib import admin

from ninja_aio.admin import register_admin

from .models import ActivityLog, Author, Book, Loan, Member, Tag

register_admin(Author)
register_admin(Book)
register_admin(Loan)
register_admin(Member)


@admin.register(Tag)
class TagAdmin(admin.ModelAdmin):
    search_fields = ["name"]


@admin.register(ActivityLog)
class ActivityLogAdmin(admin.ModelAdmin):
    list_display = ["event", "ref"]
