from typing import Any

from ninja import Schema


class M2MDetailSchema(Schema):
    count: int
    details: list[str]


class M2MSchemaOut(Schema):
    errors: M2MDetailSchema
    results: M2MDetailSchema


class M2MAddSchemaIn(Schema):
    add: list = []


class M2MRemoveSchemaIn(Schema):
    remove: list = []


class M2MSchemaIn(Schema):
    add: list = []
    remove: list = []


class RelationFilterSchema(Schema):
    """
    Schema for configuring relation-based filters in RelationFilterViewSetMixin.

    Attributes:
        filter_type: A tuple of (type, default_value) used to generate the query parameter
            field in the filters schema. Example: (int, None) for optional integer filter.
        query_param: The name of the query parameter exposed in the API endpoint.
            This is what clients will use in requests (e.g., ?author_id=5).
        query_filter: The Django ORM lookup to apply (e.g., "author__id", "category__slug").
    """

    filter_type: tuple[type, Any]
    query_param: str
    query_filter: str