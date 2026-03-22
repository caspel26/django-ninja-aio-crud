import logging
from collections.abc import Callable
from typing import List, TypeVar

from ninja import Schema, Path, Query, Status
from django.db.models import Model, QuerySet, Q
from django.http import HttpRequest
from pydantic import create_model

from ninja_aio.views.api import APIViewSet
from ninja_aio.exceptions import ForbiddenError
from ninja_aio.schemas import (
    RelationFilterSchema,
    MatchCaseFilterSchema,
    GenericMessageSchema,
    BulkResultSchema,
)
from ninja_aio.decorators import unique_view, decorate_view, aatomic

logger = logging.getLogger("ninja_aio.views")

# TypeVar for generic model typing in mixins
ModelT = TypeVar("ModelT", bound=Model)


class IcontainsFilterViewSetMixin(APIViewSet[ModelT]):
    """
    Mixin providing a convenience method to apply case-insensitive substring filters
    to a Django queryset based on request query parameters.

    This mixin is intended for use with viewsets that support asynchronous handling
    and dynamic filtering. It converts string-type filter values into Django ORM
    `__icontains` lookups, enabling partial, case-insensitive matches.

    Usage:
        - Include this mixin in a viewset class that exposes a queryset and
          passes a dictionary of filters (e.g., from request query params) to
          `query_params_handler`.
        - Only string values are considered; non-string values are ignored.

    Example:
        filters = {"name": "john", "email": "example.com", "age": 30}
        # Resulting queryset filter:
        # queryset.filter(name__icontains="john", email__icontains="example.com")
        # Note: "age" is ignored because its value is not a string.

        Apply `__icontains` filters to the provided queryset based on the given filter
        dictionary.

        Parameters:
            queryset (django.db.models.QuerySet):
                The base queryset to filter.
            filters (dict[str, Any]):
                A mapping of field names to desired filter values. Only entries with
                string values will be transformed into `field__icontains=value`
                filters. Non-string values are ignored.

        Returns:
            django.db.models.QuerySet:
                A queryset filtered with `__icontains` lookups for all string-valued
                keys in `filters`.

        Notes:
            - This method is asynchronous to align with async view workflows, but it
              performs a synchronous queryset filter call typical in Django ORM usage.
            - Ensure that the fields referenced in `filters` exist on the model
              associated with `queryset`, otherwise a FieldError may be raised at
              evaluation time.
    """

    async def query_params_handler(self, queryset, filters):
        """
        Apply icontains filter to the queryset based on provided filters.
        """
        base_qs = await super().query_params_handler(queryset, filters)
        return base_qs.filter(
            **{
                f"{key}__icontains": value
                for key, value in filters.items()
                if isinstance(value, str)
                and not self._is_special_filter(key)
                and self._validate_filter_field(key)
            }
        )


class BooleanFilterViewSetMixin(APIViewSet[ModelT]):
    """
    Mixin providing boolean-based filtering for Django QuerySets.

    This mixin defines a helper to apply boolean filters from a dictionary of query
    parameters, selecting only those values that are strictly boolean (True/False)
    and ignoring any non-boolean entries. It is intended to be used with viewsets
    that expose queryable endpoints.

    Methods:
        query_params_handler(queryset, filters):
            Apply boolean filters to the given queryset based on the provided
            dictionary. Only keys with boolean values are included in the filter.

            Parameters:
                queryset (QuerySet): A Django QuerySet to be filtered.
                filters (dict): A mapping of field names to potential filter values.

            Returns:
                QuerySet: A new QuerySet filtered by the boolean entries in `filters`.

            Notes:
                - Non-boolean values in `filters` are ignored.
                - Keys should correspond to valid model fields or lookups.
                - This method does not mutate the original queryset; it returns a
                  filtered clone.
    """

    async def query_params_handler(self, queryset, filters):
        """
        Apply boolean filter to the queryset based on provided filters.
        """
        base_qs = await super().query_params_handler(queryset, filters)
        return base_qs.filter(
            **{
                key: value
                for key, value in filters.items()
                if isinstance(value, bool)
                and not self._is_special_filter(key)
                and self._validate_filter_field(key)
            }
        )


class NumericFilterViewSetMixin(APIViewSet[ModelT]):
    """
    Mixin providing numeric filtering for Django QuerySets.

    This mixin defines a helper to apply numeric filters from a dictionary of query
    parameters, selecting only those values that are of numeric type (int or float)
    and ignoring any non-numeric entries. It is intended to be used with viewsets
    that expose queryable endpoints.

    Methods:
        query_params_handler(queryset, filters):
            Apply numeric filters to the given queryset based on the provided
            dictionary. Only keys with numeric values are included in the filter.

            Parameters:
                queryset (QuerySet): A Django QuerySet to be filtered.
                filters (dict): A mapping of field names to potential filter values.

            Returns:
                QuerySet: A new QuerySet filtered by the numeric entries in `filters`.

            Notes:
                - Non-numeric values in `filters` are ignored.
                - Keys should correspond to valid model fields or lookups.
                - This method does not mutate the original queryset; it returns a
                  filtered clone.
    """

    async def query_params_handler(self, queryset, filters):
        """
        Apply numeric filter to the queryset based on provided filters.
        """
        base_qs = await super().query_params_handler(queryset, filters)
        return base_qs.filter(
            **{
                key: value
                for key, value in filters.items()
                if isinstance(value, (int, float))
                and not self._is_special_filter(key)
                and self._validate_filter_field(key)
            }
        )


class DateFilterViewSetMixin(APIViewSet[ModelT]):
    """
    Mixin enabling date/datetime-based filtering for Django QuerySets.

    Purpose:
    - Apply dynamic date/datetime filters based on incoming query parameters.
    - Support customizable comparison operators via `_compare_attr` (e.g., "__gt", "__lt", "__gte", "__lte").

    Behavior:
    - Filters only entries whose values implement `isoformat` (dates or datetimes).
    - Builds lookups as "<field><_compare_attr>" with the provided value.

    Attributes:
    - _compare_attr (str): Django ORM comparison operator suffix to append to field names.

    Notes:
    - Ensure provided filter values are compatible with the target model fields.
    - Subclasses should set `_compare_attr` to control comparison semantics.
    """

    _compare_attr: str = ""

    async def query_params_handler(self, queryset, filters):
        """
        Apply date/datetime filters using `_compare_attr`.

        - Delegates to `super().query_params_handler` first.
        - Applies filters for keys whose values implement `isoformat`.

        Returns:
        - QuerySet filtered with lookups in the form: field<_compare_attr>=value.
        """
        base_qs = await super().query_params_handler(queryset, filters)
        return base_qs.filter(
            **{
                f"{key}{self._compare_attr}": value
                for key, value in filters.items()
                if hasattr(value, "isoformat")
                and not self._is_special_filter(key)
                and self._validate_filter_field(key)
            }
        )


class GreaterDateFilterViewSetMixin(DateFilterViewSetMixin):
    """
    Mixin that configures date filtering to return records with dates strictly greater than a given value.
    This class extends DateFilterViewSetMixin and sets the internal comparison attribute to `__gt`,
    ensuring that any date-based filtering uses the "greater than" operation.
    Attributes:
        _compare_attr (str): The Django ORM comparison operator used for filtering, set to "__gt".
    Usage:
        - Include this mixin in a ViewSet to filter queryset results where the specified date field is
          greater than the provided date value.
        - Typically used in endpoints that need to fetch items created/updated after a certain timestamp.
    Example:
        class MyViewSet(GreaterDateFilterViewSetMixin, ModelViewSet):
            date_filter_field = "created_at"
            ...
        # Filtering will apply: queryset.filter(created_at__gt=<provided_date>)
    """

    _compare_attr = "__gt"


class LessDateFilterViewSetMixin(DateFilterViewSetMixin):
    """
    Mixin that configures date filtering to return records with dates strictly less than a given value.
    This class extends DateFilterViewSetMixin and sets the internal comparison attribute to `__lt`,
    ensuring that any date-based filtering uses the "less than" operation.
    Attributes:
        _compare_attr (str): The Django ORM comparison operator used for filtering, set to "__lt".
    Usage:
        - Include this mixin in a ViewSet to filter queryset results where the specified date field is
          less than the provided date value.
        - Typically used in endpoints that need to fetch items created/updated before a certain timestamp.
    Example:
        class MyViewSet(LessDateFilterViewSetMixin, ModelViewSet):
            date_filter_field = "created_at"
            ...
        # Filtering will apply: queryset.filter(created_at__lt=<provided_date>)
    """

    _compare_attr = "__lt"


class GreaterEqualDateFilterViewSetMixin(DateFilterViewSetMixin):
    """
    Mixin for date-based filtering that uses a "greater than or equal to" comparison.

    This mixin extends DateFilterViewSetMixin by setting the internal comparison
    attribute to "__gte", enabling querysets to be filtered to include records whose
    date or datetime fields are greater than or equal to the provided value.

    Intended Use:
    - Apply to Django Ninja or DRF viewsets that support date filtering.
    - Combine with DateFilterViewSetMixin to standardize date filter behavior.

    Behavior:
    - When a date filter parameter is present, the queryset is filtered using
        Django's "__gte" lookup, e.g., MyModel.objects.filter(created_at__gte=value).

    Attributes:
    - _compare_attr: str
        The Django ORM comparison operator used for filtering; set to "__gte".

    Notes:
    - Ensure the target field and provided filter value are compatible (date or datetime).
    - Timezone-aware comparisons should be handled consistently within the project settings.
    """

    _compare_attr = "__gte"


class LessEqualDateFilterViewSetMixin(DateFilterViewSetMixin):
    """
    Mixin for date-based filtering that uses a "less than or equal to" comparison.
    This mixin extends DateFilterViewSetMixin by setting the internal comparison
    attribute to "__lte", enabling querysets to be filtered to include records whose
    date or datetime fields are less than or equal to the provided value.
    Intended Use:
    - Apply to Django Ninja or DRF viewsets that support date filtering.
    - Combine with DateFilterViewSetMixin to standardize date filter behavior.
    Behavior:
    - When a date filter parameter is present, the queryset is filtered using
        Django's "__lte" lookup, e.g., MyModel.objects.filter(created_at__lte=value).
    Attributes:
    - _compare_attr: str
        The Django ORM comparison operator used for filtering; set to "__lte".
    Notes:
    - Ensure the target field and provided filter value are compatible (date or datetime).
    - Timezone-aware comparisons should be handled consistently within the project settings.
    """

    _compare_attr = "__lte"


class RelationFilterViewSetMixin(APIViewSet[ModelT]):
    """
    Mixin providing filtering for related fields in Django QuerySets.

    This mixin applies filters on related fields based on configured RelationFilterSchema
    entries. Each entry maps a query parameter name to a Django ORM lookup path.

    Attributes:
        relations_filters: List of RelationFilterSchema defining the relation filters.
            Each schema specifies:
            - query_param: The API query parameter name (e.g., "author_id")
            - query_filter: The Django ORM lookup (e.g., "author__id")
            - filter_type: Tuple of (type, default) for schema generation

    Example:
        class BookViewSet(RelationFilterViewSetMixin, APIViewSet):
            relations_filters = [
                RelationFilterSchema(
                    query_param="author_id",
                    query_filter="author__id",
                    filter_type=(int, None),
                ),
                RelationFilterSchema(
                    query_param="category_slug",
                    query_filter="category__slug",
                    filter_type=(str, None),
                ),
            ]

        # GET /books?author_id=5 -> queryset.filter(author__id=5)
        # GET /books?category_slug=fiction -> queryset.filter(category__slug="fiction")

    Notes:
        - Filter values that are None or falsy are skipped.
        - This mixin automatically registers query_params from relations_filters.
    """

    relations_filters: list[RelationFilterSchema] = []

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        cls.query_params = {
            **cls.query_params,
            **{
                rel_filter.query_param: rel_filter.filter_type
                for rel_filter in cls.relations_filters
            },
        }

    @property
    def relations_filters_fields(self):
        return [rel_filter.query_param for rel_filter in self.relations_filters]

    async def query_params_handler(self, queryset, filters):
        """
        Apply relation filters to the queryset based on configured relations_filters.
        """
        base_qs = await super().query_params_handler(queryset, filters)
        rel_filters = {}
        for rel_filter in self.relations_filters:
            value = filters.get(rel_filter.query_param)
            # Validate the configured query_filter path for security
            if value is not None and self._validate_filter_field(
                rel_filter.query_filter
            ):
                rel_filters[rel_filter.query_filter] = value
        return base_qs.filter(**rel_filters) if rel_filters else base_qs


class MatchCaseFilterViewSetMixin(APIViewSet[ModelT]):
    """
    Mixin providing match-case filtering for Django QuerySets.
    This mixin applies filters based on boolean query parameters defined in
    MatchCaseFilterSchema entries. Each entry specifies different filter conditions
    for True and False cases.
    Attributes:
        filters_match_cases: List of MatchCaseFilterSchema defining the match-case filters.
            Each schema specifies:
            - query_param: The API query parameter name (e.g., "is_active")
            - cases: A BooleanMatchFilterSchema with 'true' and 'false' MatchConditionFilterSchema
    Example:
        class UserViewSet(MatchCaseFilterViewSetMixin, APIViewSet):
            filters_match_cases = [
                MatchCaseFilterSchema(
                    query_param="is_active",
                    cases=BooleanMatchFilterSchema(
                        true=MatchConditionFilterSchema(
                            query_filter={"status": "active"},
                            include=True,
                        ),
                        false=MatchConditionFilterSchema(
                            query_filter={"status": "inactive"},
                            include=True,
                        ),
                    ),
                ),
            ]
        # GET /users?is_active=true -> queryset.filter(status="active")
        # GET /users?is_active=false -> queryset.filter(status="inactive")
    Notes:
        - If the query parameter is not provided, no filtering is applied for that case.
        - This mixin automatically registers query_params from filters_match_cases.
    """

    filters_match_cases: list[MatchCaseFilterSchema] = []

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        cls.query_params = {
            **cls.query_params,
            **{
                filter_match.query_param: filter_match.filter_type
                for filter_match in cls.filters_match_cases
            },
        }

    @property
    def filters_match_cases_fields(self):
        return [filter_match.query_param for filter_match in self.filters_match_cases]

    def _apply_case_filter(self, queryset, case_filter):
        lookup = case_filter.query_filter
        qs_method = queryset.filter if case_filter.include else queryset.exclude
        if isinstance(lookup, Q):
            return qs_method(lookup)
        validated_lookup = {
            k: v for k, v in lookup.items() if self._validate_filter_field(k)
        }
        if not validated_lookup:
            return queryset
        return qs_method(**validated_lookup)

    async def query_params_handler(self, queryset, filters):
        base_qs = await super().query_params_handler(queryset, filters)
        for filter_match in self.filters_match_cases:
            value = filters.get(filter_match.query_param)
            if value is None:
                continue
            case_filter = (
                filter_match.cases.true if value else filter_match.cases.false
            )
            base_qs = self._apply_case_filter(base_qs, case_filter)
        return base_qs


class PermissionViewSetMixin(APIViewSet[ModelT]):
    """
    Mixin adding async permission checks to all CRUD operations.

    Provides three overridable hooks:

    - ``has_permission(request, operation)`` — view-level check executed
      before any DB query. Return ``False`` to deny (raises 403).
    - ``has_object_permission(request, operation, obj)`` — object-level
      check executed after fetching the instance but before mutation.
      Only called for retrieve / update / delete. Return ``False`` to deny.
    - ``get_permission_queryset(request, queryset)`` — row-level filtering
      for list views. Return a filtered queryset to restrict visible rows.

    All hooks default to *allow-all* so the mixin is safe to add without
    immediately locking out any operations.

    Usage::

        class BookAPI(PermissionViewSetMixin, APIViewSet):
            model = Book

            async def has_permission(self, request, operation):
                if operation in ("create", "update", "delete"):
                    return request.auth.is_staff
                return True

            async def has_object_permission(self, request, operation, obj):
                return obj.owner_id == request.auth.id

    The mixin works with filter mixins, bulk views, and ``@action``
    endpoints. Permission is checked using the action name as the
    ``operation`` string for custom actions.
    """

    async def has_permission(
        self, request: HttpRequest, operation: str
    ) -> bool:
        """View-level permission check. Override for custom logic."""
        return True

    async def has_object_permission(
        self, request: HttpRequest, operation: str, obj: ModelT
    ) -> bool:
        """Object-level permission check. Override for custom logic."""
        return True

    def get_permission_queryset(
        self, request: HttpRequest, queryset: QuerySet
    ) -> QuerySet:
        """Row-level filtering for list views. Override to restrict visible rows."""
        return queryset

    async def _check_permission(
        self, request: HttpRequest, operation: str
    ) -> None:
        """Run has_permission and raise ForbiddenError if denied."""
        if not await self.has_permission(request, operation):
            raise ForbiddenError(
                details=f"Permission denied for operation: {operation}"
            )

    async def _check_object_permission(
        self, request: HttpRequest, operation: str, obj: ModelT
    ) -> None:
        """Run has_object_permission and raise ForbiddenError if denied."""
        if not await self.has_object_permission(request, operation, obj):
            raise ForbiddenError(
                details=f"Permission denied for operation: {operation}"
            )

    def create_view(self) -> Callable:
        """Register create endpoint with permission check."""
        viewset = self

        @self.router.post(
            self.path,
            auth=self.post_view_auth(),
            summary=f"Create {self.model_verbose_name}",
            description=self.create_docs,
            response={201: self.schema_out, self.error_codes: GenericMessageSchema},
        )
        @decorate_view(aatomic, unique_view(self), *self.extra_decorators.create)
        async def create(request: HttpRequest, data: self.schema_in):  # type: ignore
            await viewset._check_permission(request, "create")
            return Status(
                201, await viewset.model_util.create_s(request, data, viewset.schema_out)
            )

        return create

    def list_view(self) -> Callable:
        """Register list endpoint with permission check and row-level filtering."""
        viewset = self
        _paginator = self.pagination_class()
        _pk_name = self.model_util.model_pk_name
        _input_class = self.pagination_class.Input
        _default_pagination = _input_class()
        _paginated_schema = create_model(
            f"Paginated{self.schema_out.__name__}",
            __base__=Schema,
            items=(List[self.schema_out], ...),
            count=(int, ...),
        )

        @self.router.get(
            self.get_path,
            auth=self.get_view_auth(),
            summary=f"List {self.model_verbose_name_plural}",
            description=self.list_docs,
            response={
                200: _paginated_schema,
                self.error_codes: GenericMessageSchema,
            },
        )
        @decorate_view(
            unique_view(self, plural=True),
            *self.extra_decorators.list,
        )
        async def list(
            request: HttpRequest,
            filters: Query[self.filters_schema] = None,  # type: ignore
            ninja_pagination: _input_class = Query(_default_pagination),  # type: ignore
        ):
            if not isinstance(ninja_pagination, _input_class):
                ninja_pagination = _default_pagination

            await viewset._check_permission(request, "list")

            qs = await viewset.model_util.get_objects(
                request,
                query_data=viewset._get_query_data(),
                is_for="read",
            )
            qs = viewset.get_permission_queryset(request, qs)
            qs = await viewset._apply_list_filters(qs, filters)

            count = await qs.values(_pk_name).acount()

            offset, page_size = viewset._get_page_params(
                _paginator, ninja_pagination
            )
            sliced_qs = qs[offset : offset + page_size]

            items = await viewset.model_util.list_read_s(
                viewset.schema_out, request, sliced_qs, is_for="read"
            )
            return Status(200, {"items": items, "count": count})

        return list

    def retrieve_view(self) -> Callable:
        """Register retrieve endpoint with permission + object permission check."""
        viewset = self
        retrieve_schema = self._get_retrieve_schema()

        @self.router.get(
            self.get_path_retrieve,
            auth=self.get_view_auth(),
            summary=f"Retrieve {self.model_verbose_name}",
            description=self.retrieve_docs,
            response={200: retrieve_schema, self.error_codes: GenericMessageSchema},
        )
        @decorate_view(unique_view(self), *self.extra_decorators.retrieve)
        async def retrieve(request: HttpRequest, pk: Path[self.path_schema]):  # type: ignore
            await viewset._check_permission(request, "retrieve")
            obj = await viewset.model_util.get_object(
                request, viewset._get_pk(pk), is_for="detail" if viewset.schema_detail else "read"
            )
            await viewset._check_object_permission(request, "retrieve", obj)
            return Status(
                200,
                await viewset.model_util.read_s(retrieve_schema, request, obj),
            )

        return retrieve

    def update_view(self) -> Callable:
        """Register update endpoint with permission + object permission check."""
        viewset = self

        @self.router.patch(
            self.path_retrieve,
            auth=self.patch_view_auth(),
            summary=f"Update {self.model_verbose_name}",
            description=self.update_docs,
            response={200: self.schema_out, self.error_codes: GenericMessageSchema},
        )
        @decorate_view(aatomic, unique_view(self), *self.extra_decorators.update)
        async def update(
            request: HttpRequest,
            data: self.schema_update,  # type: ignore
            pk: Path[self.path_schema],  # type: ignore
        ):
            await viewset._check_permission(request, "update")
            obj = await viewset.model_util.get_object(
                request, viewset._get_pk(pk)
            )
            await viewset._check_object_permission(request, "update", obj)
            return Status(
                200,
                await viewset.model_util.update_s(
                    request,
                    data,
                    viewset._get_pk(pk),
                    viewset.schema_out,
                    viewset.require_update_fields,
                ),
            )

        return update

    def delete_view(self) -> Callable:
        """Register delete endpoint with permission + object permission check."""
        viewset = self

        @self.router.delete(
            self.path_retrieve,
            auth=self.delete_view_auth(),
            summary=f"Delete {self.model_verbose_name}",
            description=self.delete_docs,
            response={204: None, self.error_codes: GenericMessageSchema},
        )
        @decorate_view(aatomic, unique_view(self), *self.extra_decorators.delete)
        async def delete(request: HttpRequest, pk: Path[self.path_schema]):  # type: ignore
            await viewset._check_permission(request, "delete")
            obj = await viewset.model_util.get_object(
                request, viewset._get_pk(pk)
            )
            await viewset._check_object_permission(request, "delete", obj)
            return Status(
                204, await viewset.model_util.delete_s(request, viewset._get_pk(pk))
            )

        return delete

    def bulk_create_view(self) -> Callable:
        """Register bulk create endpoint with permission check."""
        viewset = self

        @self.router.post(
            self.bulk_path,
            auth=self.post_view_auth(),
            summary=f"Bulk Create {self.model_verbose_name_plural}",
            description=self.bulk_create_docs,
            response={200: BulkResultSchema, self.error_codes: GenericMessageSchema},
        )
        @decorate_view(
            unique_view(self, plural=True), *self.extra_decorators.bulk_create
        )
        async def bulk_create(
            request: HttpRequest, data: List[self.schema_in]  # type: ignore
        ):
            await viewset._check_permission(request, "bulk_create")
            success, errors = await viewset.model_util.bulk_create_s(
                request, data, viewset._get_bulk_detail_extractor()
            )
            return Status(
                200,
                {
                    "success": {"count": len(success), "details": success},
                    "errors": {"count": len(errors), "details": errors},
                },
            )

        return bulk_create

    def bulk_update_view(self) -> Callable:
        """Register bulk update endpoint with permission check."""
        viewset = self
        pk_name = self.model_util.model_pk_name

        @self.router.patch(
            self.bulk_path,
            auth=self.patch_view_auth(),
            summary=f"Bulk Update {self.model_verbose_name_plural}",
            description=self.bulk_update_docs,
            response={
                200: BulkResultSchema,
                self.error_codes: GenericMessageSchema,
            },
        )
        @decorate_view(
            unique_view(self, plural=True), *self.extra_decorators.bulk_update
        )
        async def bulk_update(
            request: HttpRequest,
            data: List[self.bulk_update_schema],  # type: ignore
        ):
            await viewset._check_permission(request, "bulk_update")
            data_list = []
            for item in data:
                pk = getattr(item, pk_name)
                update_fields = {
                    k: v for k, v in item.model_dump().items() if k != pk_name
                }
                update_data = viewset.schema_update(**update_fields)
                data_list.append((pk, update_data))
            success, errors = await viewset.model_util.bulk_update_s(
                request,
                data_list,
                viewset._get_bulk_detail_extractor(),
                viewset.require_update_fields,
            )
            return Status(
                200,
                {
                    "success": {"count": len(success), "details": success},
                    "errors": {"count": len(errors), "details": errors},
                },
            )

        return bulk_update

    def bulk_delete_view(self) -> Callable:
        """Register bulk delete endpoint with permission check."""
        viewset = self

        @self.router.delete(
            self.bulk_path,
            auth=self.delete_view_auth(),
            summary=f"Bulk Delete {self.model_verbose_name_plural}",
            description=self.bulk_delete_docs,
            response={200: BulkResultSchema, self.error_codes: GenericMessageSchema},
        )
        @decorate_view(
            unique_view(self, plural=True), *self.extra_decorators.bulk_delete
        )
        async def bulk_delete(
            request: HttpRequest, data: self.bulk_delete_schema  # type: ignore
        ):
            await viewset._check_permission(request, "bulk_delete")
            deleted_pks, errors = await viewset.model_util.bulk_delete_s(
                request, data.ids, viewset._get_bulk_detail_fields()
            )
            return Status(
                200,
                {
                    "success": {"count": len(deleted_pks), "details": deleted_pks},
                    "errors": {"count": len(errors), "details": errors},
                },
            )

        return bulk_delete

    def _register_single_action(
        self, name: str, method: Callable, config
    ) -> None:
        """Wrap action handler with permission check before delegating to base."""
        import functools

        original_method = method
        viewset = self

        @functools.wraps(original_method)
        async def permission_wrapped(self_arg, request: HttpRequest, *args, **kwargs):
            await viewset._check_permission(request, name)
            return await original_method(self_arg, request, *args, **kwargs)

        super()._register_single_action(name, permission_wrapped, config)


class RoleBasedPermissionMixin(PermissionViewSetMixin[ModelT]):
    """
    Permission mixin using a role-to-operations mapping.

    Maps user roles to lists of allowed operations. The role is read from
    ``request.auth`` using the attribute named by ``role_attribute``.

    Usage::

        class BookAPI(RoleBasedPermissionMixin, APIViewSet):
            model = Book
            permission_roles = {
                "admin": ["create", "list", "retrieve", "update", "delete"],
                "editor": ["create", "list", "retrieve", "update"],
                "reader": ["list", "retrieve"],
            }
            role_attribute = "role"  # default

    When ``permission_roles`` is empty, all operations are allowed (opt-in).
    When ``request.auth`` is ``None`` or the role attribute is missing,
    all operations are denied.
    """

    permission_roles: dict[str, list[str]] = {}
    role_attribute: str = "role"

    async def has_permission(
        self, request: HttpRequest, operation: str
    ) -> bool:
        """Check if the user's role allows the requested operation."""
        if not self.permission_roles:
            return True
        auth = getattr(request, "auth", None)
        if auth is None:
            return False
        role = (
            auth.get(self.role_attribute)
            if isinstance(auth, dict)
            else getattr(auth, self.role_attribute, None)
        )
        if role is None:
            return False
        return operation in self.permission_roles.get(role, [])
