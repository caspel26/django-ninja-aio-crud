"""Machine-readable version 3 public API contract.

Production methods are introduced in later implementation steps. Keeping the
contract data in tests lets each step activate the same assertions for both
serializer styles without duplicating naming and return-shape expectations.
"""

from dataclasses import dataclass
from typing import Literal


ExecutionMode = Literal["sync", "async"]


@dataclass(frozen=True)
class MethodContract:
    name: str
    mode: ExecutionMode
    returns: str
    implementation_step: int


METHOD_CONTRACTS = (
    MethodContract("create", "sync", "model", 5),
    MethodContract("acreate", "async", "model", 4),
    MethodContract("get", "sync", "model", 5),
    MethodContract("aget", "async", "model", 4),
    MethodContract("update", "sync", "model", 5),
    MethodContract("aupdate", "async", "model", 4),
    MethodContract("destroy", "sync", "none", 5),
    MethodContract("adestroy", "async", "none", 4),
    MethodContract("model_dump", "sync", "dict", 6),
    MethodContract("amodel_dump", "async", "dict", 6),
    MethodContract("model_dumps", "sync", "list[dict]", 6),
    MethodContract("amodel_dumps", "async", "list[dict]", 6),
    MethodContract("bulk_create", "sync", "bulk_result[model]", 8),
    MethodContract("abulk_create", "async", "bulk_result[model]", 8),
    MethodContract("bulk_update", "sync", "bulk_result[model]", 8),
    MethodContract("abulk_update", "async", "bulk_result[model]", 8),
    MethodContract("bulk_destroy", "sync", "bulk_result[pk]", 8),
    MethodContract("abulk_destroy", "async", "bulk_result[pk]", 8),
)

SCHEMA_ATTRIBUTES = (
    "create_schema",
    "update_schema",
    "read_schema",
    "detail_schema",
    "related_schema",
)

SCHEMA_METHODS = ("get_schema", "clear_schema_cache")

V2_CORE_METHODS = frozenset(
    {
        "generate_create_s",
        "generate_update_s",
        "generate_read_s",
        "generate_detail_s",
        "generate_related_s",
        "generate_nested_child_schema",
        "create",
        "update",
        "save",
        "model_dump",
        "models_dump",
        "get_object",
        "get_objects",
        "create_s",
        "read_s",
        "list_read_s",
        "update_s",
        "delete_s",
        "bulk_create_s",
        "bulk_update_s",
        "bulk_delete_s",
        "aparse_input_data",
        "get_reverse_relations",
        "get_select_relateds",
        "get_fields",
        "get_schema_out_data",
        "get_related_schema_data",
        "queryset_request",
        "has_changed",
        "ahas_changed",
        "as_admin",
        "delete",
    }
)

V2_MIGRATION_DECISIONS = {
    "generate_create_s": "create_schema",
    "generate_update_s": "update_schema",
    "generate_read_s": "read_schema",
    "generate_detail_s": "detail_schema",
    "generate_related_s": "related_schema",
    "generate_nested_child_schema": "internal",
    "create": "create/acreate",
    "update": "update/aupdate",
    "save": "internal-or-django-instance",
    "model_dump": "model_dump/amodel_dump",
    "models_dump": "model_dumps/amodel_dumps",
    "get_object": "get/aget",
    "get_objects": "django-queryset",
    "create_s": "create/acreate",
    "read_s": "model_dump/amodel_dump",
    "list_read_s": "model_dumps/amodel_dumps",
    "update_s": "update/aupdate",
    "delete_s": "destroy/adestroy",
    "bulk_create_s": "bulk_create/abulk_create",
    "bulk_update_s": "bulk_update/abulk_update",
    "bulk_delete_s": "bulk_destroy/abulk_destroy",
    "aparse_input_data": "internal",
    "get_reverse_relations": "internal",
    "get_select_relateds": "internal",
    "get_fields": "internal",
    "get_schema_out_data": "internal",
    "get_related_schema_data": "internal",
    "queryset_request": "keep-hook",
    "has_changed": "keep",
    "ahas_changed": "keep",
    "as_admin": "keep",
    "delete": "keep-django-instance",
}
