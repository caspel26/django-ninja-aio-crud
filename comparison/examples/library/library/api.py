"""The library API, mounted twice with the same viewsets.

``/api/sync/...`` serves everything with ``execution_mode = "sync"`` and plain
``def`` actions; ``/api/async/...`` serves it with ``async def``. Responses,
database effects and query counts are the same (see ``tests/test_parity.py``).
"""

import datetime

from django.contrib.auth import aauthenticate, authenticate
from django.http import JsonResponse
from django.utils import timezone
from ninja import Schema

from ninja_aio import APIView, APIViewSet, NinjaAIO, NinjaAIORouter, action, on
from ninja_aio.auth import delete_jwt_cookie, encode_jwt, set_jwt_cookie
from ninja_aio.exceptions import AuthError, ForbiddenError, SerializeError
from ninja_aio.schemas import M2MRelationSchema, RelationFilterSchema
from ninja_aio.views.mixins import (
    BooleanFilterViewSetMixin,
    DateFilterViewSetMixin,
    FieldSelectionViewSetMixin,
    IcontainsFilterViewSetMixin,
    NumericFilterViewSetMixin,
    PermissionViewSetMixin,
    RelationFilterViewSetMixin,
    RoleBasedPermissionMixin,
    SearchViewSetMixin,
    SoftDeleteViewSetMixin,
)

from .auth import AUTH
from .models import Author, Book, Loan, Member, Tag
from .serializers import TagSerializer

MAX_RENEWALS = 2
TOKEN_SECONDS = 3600

LIBRARIAN = ["list", "retrieve", "create", "update", "delete", "bulk_create", "bulk_update",
             "bulk_delete", "restore", "hard_delete", "stats"]
READER = ["list", "retrieve", "stats"]


class LoginIn(Schema):
    username: str
    password: str


class TokenOut(Schema):
    access_token: str


class RenewIn(Schema):
    days: int = 7


class StatsOut(Schema):
    total: int
    available: int


def _is_librarian(request) -> bool:
    return getattr(request.auth, "role", None) == "librarian"


def _login_response(user) -> JsonResponse:
    if user is None:
        raise AuthError("invalid credentials")
    token = encode_jwt({"sub": str(user.pk)}, duration=TOKEN_SECONDS)
    return set_jwt_cookie(JsonResponse({"access_token": token}), token, max_age=TOKEN_SECONDS, secure=False)


def _renewed(loan: Loan, days: int) -> dict:
    if loan.returned_at is not None:
        raise SerializeError({"loan": "already returned"}, 409)
    if loan.renewals >= MAX_RENEWALS:
        raise SerializeError({"renewals": f"at most {MAX_RENEWALS} renewals"}, 409)
    return {"due_date": loan.due_date + datetime.timedelta(days=days), "renewals": loan.renewals + 1}


class LibrarianWrites(PermissionViewSetMixin):
    """Anyone reads; only librarians write."""

    read_operations = {"list", "retrieve"}

    def _allowed(self, request, operation):
        return operation in self.read_operations or _is_librarian(request)

    def has_permission(self, request, operation):
        return self._allowed(request, operation)

    async def ahas_permission(self, request, operation):
        return self._allowed(request, operation)


class OwnLoans(PermissionViewSetMixin):
    """Members see and change only their own loans; librarians see everything."""

    def get_permission_queryset(self, request, queryset):
        return queryset if _is_librarian(request) else queryset.filter(member=request.auth)

    def _may_touch(self, request, operation, obj):
        if operation in ("update", "delete"):
            return _is_librarian(request)
        return _is_librarian(request) or obj.member_id == request.auth.pk

    def has_permission(self, request, operation):
        return operation not in ("update", "delete", "bulk_delete") or _is_librarian(request)

    async def ahas_permission(self, request, operation):
        return self.has_permission(request, operation)

    def has_object_permission(self, request, operation, obj):
        return self._may_touch(request, operation, obj)

    async def ahas_object_permission(self, request, operation, obj):
        return self._may_touch(request, operation, obj)


def build(mode: str) -> NinjaAIORouter:
    """Register every viewset and view for one execution mode."""
    sync = mode == "sync"
    router = NinjaAIORouter()

    @router.viewset(Author, prefix="authors", tags=[f"Authors ({mode})"])
    class Authors(LibrarianWrites, APIViewSet):
        execution_mode = mode
        auth = AUTH
        get_auth = None

    @router.viewset(Tag, prefix="tags", tags=[f"Tags ({mode})"])
    class Tags(RoleBasedPermissionMixin, APIViewSet):
        execution_mode = mode
        serializer_class = TagSerializer
        auth = AUTH
        permission_roles = {"librarian": LIBRARIAN, "member": READER}

    @router.viewset(Book, prefix="books", tags=[f"Books ({mode})"])
    class Books(
        FieldSelectionViewSetMixin,
        SearchViewSetMixin,
        RelationFilterViewSetMixin,
        IcontainsFilterViewSetMixin,
        BooleanFilterViewSetMixin,
        NumericFilterViewSetMixin,
        DateFilterViewSetMixin,
        SoftDeleteViewSetMixin,
        RoleBasedPermissionMixin,
        APIViewSet,
    ):
        execution_mode = mode
        auth = AUTH
        permission_roles = {"librarian": LIBRARIAN, "member": READER}
        bulk_operations = ["create", "update", "delete"]
        query_params = {
            "title": (str, None),
            "available": (bool, None),
            "pages": (int, None),
            "published__gte": (datetime.date, None),
            "published__lte": (datetime.date, None),
        }
        relations_filters = [
            RelationFilterSchema(query_param="author", query_filter="author__id", filter_type=(int, None)),
            RelationFilterSchema(
                query_param="author_name", query_filter="author__name__icontains", filter_type=(str, None)
            ),
        ]
        search_fields = ["title", "isbn", "author__name"]
        ordering_fields = ["title", "pages", "published"]
        default_ordering = "title"
        m2m_relations = [
            M2MRelationSchema(
                model=Tag, related_name="tags", serializer_class=TagSerializer, filters={"name": (str, "")}
            ),
        ]

        def tags_query_params_handler(self, queryset, filters):
            if filters.get("name"):
                queryset = queryset.filter(name__icontains=filters["name"])
            return queryset

        if sync:

            @action(detail=False, response=StatsOut)
            def stats(self, request):
                books = Book.get_queryset(request=request).filter(is_deleted=False)
                return {"total": books.count(), "available": books.filter(available=True).count()}

        else:

            @action(detail=False, response=StatsOut)
            async def stats(self, request):
                books = (await Book.aget_queryset(request=request)).filter(is_deleted=False)
                return {"total": await books.acount(), "available": await books.filter(available=True).acount()}

    @router.viewset(Member, prefix="members", tags=[f"Members ({mode})"])
    class Members(RoleBasedPermissionMixin, APIViewSet):
        execution_mode = mode
        auth = AUTH
        disable = ["create", "update", "delete"]
        permission_roles = {"librarian": ["list", "retrieve"]}

    @router.viewset(Loan, prefix="loans", tags=[f"Loans ({mode})"])
    class Loans(OwnLoans, APIViewSet):
        execution_mode = mode
        auth = AUTH
        query_params = {"active": (bool, None)}
        ordering_fields = ["due_date", "borrowed_at"]
        default_ordering = "due_date"

        @staticmethod
        def _own(request, data):
            if not _is_librarian(request) or getattr(data, "member", None) is None:
                return data.model_copy(update={"member": request.auth.pk})
            return data

        def _active_filter(self, queryset, filters):
            if filters.get("active") is not None:
                queryset = queryset.filter(returned_at__isnull=filters["active"])
            return queryset

        if sync:

            def query_params_handler(self, queryset, filters):
                return self._active_filter(queryset, filters)

            def create(self, request, data):
                return super().create(request, self._own(request, data))

            @on("return", response=Loan.read_schema)
            def return_book(self, request, obj):
                return Loan.model_dump(Loan.update(obj, {"returned_at": timezone.now()}, request=request))

            @action(detail=True, methods=["post"], response=Loan.read_schema)
            def renew(self, request, pk: int, data: RenewIn):
                loan = Loan.get(pk, request=request)
                return Loan.model_dump(Loan.update(loan, _renewed(loan, data.days), request=request))

        else:

            async def aquery_params_handler(self, queryset, filters):
                return self._active_filter(queryset, filters)

            async def acreate(self, request, data):
                return await super().acreate(request, self._own(request, data))

            @on("return", response=Loan.read_schema)
            async def return_book(self, request, obj):
                return await Loan.amodel_dump(await Loan.aupdate(obj, {"returned_at": timezone.now()}, request=request))

            @action(detail=True, methods=["post"], response=Loan.read_schema)
            async def renew(self, request, pk: int, data: RenewIn):
                loan = await Loan.aget(pk, request=request)
                return await Loan.amodel_dump(await Loan.aupdate(loan, _renewed(loan, data.days), request=request))

    @router.view(prefix="auth", tags=[f"Auth ({mode})"])
    class Auth(APIView):
        if sync:

            @action(detail=False, methods=["post"], auth=None, response=TokenOut)
            def login(self, request, data: LoginIn):
                return _login_response(authenticate(request, username=data.username, password=data.password))

            @action(detail=False, methods=["post"], auth=None)
            def logout(self, request):
                return delete_jwt_cookie(JsonResponse({"logged_out": True}))

        else:

            @action(detail=False, methods=["post"], auth=None, response=TokenOut)
            async def login(self, request, data: LoginIn):
                user = await aauthenticate(request, username=data.username, password=data.password)
                return _login_response(user)

            @action(detail=False, methods=["post"], auth=None)
            async def logout(self, request):
                return delete_jwt_cookie(JsonResponse({"logged_out": True}))

    @router.view(prefix="reports", tags=[f"Reports ({mode})"])
    class Reports(APIView):
        auth = AUTH

        @staticmethod
        def _overdue_queryset(request, queryset):
            if not _is_librarian(request):
                raise ForbiddenError(details="Only librarians can read reports")
            return queryset.filter(returned_at__isnull=True, due_date__lt=timezone.localdate()).order_by("due_date")

        if sync:

            @action(detail=False)
            def overdue(self, request):
                return Loan.model_dumps(self._overdue_queryset(request, Loan.get_queryset(request=request)))

        else:

            @action(detail=False)
            async def overdue(self, request):
                queryset = await Loan.aget_queryset(request=request)
                return await Loan.amodel_dumps(self._overdue_queryset(request, queryset))

    return router


api = NinjaAIO(title="Library API", version="1.0.0", urls_namespace="library")
api.add_router("/sync", build("sync"))
api.add_router("/async", build("async"))
