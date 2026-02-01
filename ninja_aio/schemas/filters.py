from typing import Any

from ninja import Schema


class FilterSchema(Schema):
    """
    Schema for configuring basic filters in FilterViewSetMixin.

    Attributes:
        filter_type: A tuple of (type, default_value) used to generate the query parameter
            field in the filters schema. Example: (str, None) for optional string filter.
        query_param: The name of the query parameter exposed in the API endpoint.
            This is what clients will use in requests (e.g., ?name=example).
    """

    filter_type: tuple[type, Any]
    query_param: str


class MatchConditionFilterSchema(Schema):
    """
    Schema for configuring match condition filters in MatchConditionFilterViewSetMixin.
    Attributes:
        query_filter: The Django ORM lookup to apply (e.g., "status", "category__name").
        include: Whether to include records matching the condition (default: True).
    """
    query_filter: dict[str, Any]
    include: bool = True


class BooleanMatchFilterSchema(Schema):
    """
    Schema for configuring boolean match filters in BooleanMatchFilterViewSetMixin.

    Attributes:
        true: MatchConditionFilterSchema for when the boolean filter is True.
        false: MatchConditionFilterSchema for when the boolean filter is False.
    """

    true: MatchConditionFilterSchema
    false: MatchConditionFilterSchema


class RelationFilterSchema(FilterSchema):
    """
    Schema for configuring relation-based filters in RelationFilterViewSetMixin.

    Attributes:
        filter_type: A tuple of (type, default_value) used to generate the query parameter
            field in the filters schema. Example: (int, None) for optional integer filter.
        query_param: The name of the query parameter exposed in the API endpoint.
            This is what clients will use in requests (e.g., ?author_id=5).
        query_filter: The Django ORM lookup to apply (e.g., "author__id", "category__slug").
    """

    query_filter: str


class MatchCaseFilterSchema(FilterSchema):
    """
    Schema for configuring match-case filters in MatchCaseFilterViewSetMixin.

    Attributes:
        filter_type: A tuple of (type, default_value) used to generate the query parameter
            field in the filters schema. Defaults to (bool, None) for optional boolean filter.
        query_param: The name of the query parameter exposed in the API endpoint.
            This is what clients will use in requests (e.g., ?is_active=true).
        cases: A BooleanMatchFilterSchema defining the filter conditions for True and False cases.
    """

    filter_type: tuple[type, Any] = (bool, None)
    cases: BooleanMatchFilterSchema
