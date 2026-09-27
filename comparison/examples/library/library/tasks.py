"""Background jobs that use the async serializer methods (``a``-prefixed)."""

import datetime

from django.utils import timezone

from .models import ActivityLog, Loan


async def send_due_reminders(within_days: int = 2) -> list[dict]:
    """Log a reminder for each open loan due within ``within_days`` and return them."""
    limit = timezone.localdate() + datetime.timedelta(days=within_days)
    queryset = (await Loan.aget_queryset()).filter(returned_at__isnull=True, due_date__lte=limit)
    loans = [loan async for loan in queryset.order_by("due_date")]
    for loan in loans:
        await ActivityLog.objects.acreate(event="reminder_sent", ref=loan.pk)
    return await Loan.amodel_dumps(loans)


async def extend_all_open_loans(days: int) -> int:
    """Push the due date of every open loan by ``days``, through the serializer hooks."""
    queryset = (await Loan.aget_queryset()).filter(returned_at__isnull=True)
    count = 0
    async for loan in queryset:
        await Loan.aupdate(loan, {"due_date": loan.due_date + datetime.timedelta(days=days)})
        count += 1
    return count
