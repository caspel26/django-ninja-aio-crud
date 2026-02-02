#!/usr/bin/env python3
"""
Helper script to add complex async benchmark implementations to all frameworks.
This showcases where django-ninja-aio-crud excels: complex relations in async.
"""

# This file documents what needs to be added to FastAPI and Flask-RESTX
# implementations. The actual implementations are verbose, showing the pain
# of handling complex async relations without django-ninja-aio-crud.

FASTAPI_ADDITIONS = """
# Add to fastapi.py imports:
from tests.test_app.models import (
    TestModelSerializerManyToMany,
    TestModelSerializerReverseManyToMany,
)

# Add new schemas:
class ItemNested(BaseModel):
    id: int
    name: str
    description: str
    test_model_serializer: ItemOut
    class Config:
        from_attributes = True

class ReverseChild(BaseModel):
    id: int
    name: str
    description: str
    class Config:
        from_attributes = True

class ItemWithReverse(BaseModel):
    id: int
    name: str
    description: str
    test_model_serializer_foreign_keys: list[ReverseChild]
    class Config:
        from_attributes = True

class M2MRelated(BaseModel):
    id: int
    name: str
    description: str
    class Config:
        from_attributes = True

class ItemWithM2M(BaseModel):
    id: int
    name: str
    description: str
    test_model_serializers: list[M2MRelated]
    class Config:
        from_attributes = True

# Add methods showing async pain:
async def serialize_nested_relations(self, item_id: int):
    instance = await TestModelSerializerForeignKey.objects.select_related(
        "test_model_serializer"
    ).aget(pk=item_id)
    return ItemNested.model_validate(instance).model_dump()

async def serialize_reverse_relations(self, item_id: int):
    instance = await TestModelSerializerReverseForeignKey.objects.prefetch_related(
        "test_model_serializer_foreign_keys"
    ).aget(pk=item_id)
    # Pydantic v2 handles this better than manual iteration,
    # but still requires prefetch setup
    return ItemWithReverse.model_validate(instance).model_dump()

async def serialize_many_to_many(self, item_id: int):
    instance = await TestModelSerializerManyToMany.objects.prefetch_related(
        "test_model_serializers"
    ).aget(pk=item_id)
    return ItemWithM2M.model_validate(instance).model_dump()

async def complex_query_with_relations(self, **filters):
    queryset = TestModelSerializerForeignKey.objects.filter(
        **filters
    ).select_related("test_model_serializer")[:20]
    items = []
    async for item in queryset:
        items.append(ItemNested.model_validate(item).model_dump())
    return items
"""

FLASK_RESTX_ADDITIONS = """
# Flask-RESTX is the most painful - sync only, wrapped with sync_to_async
# Manual dict construction + sync_to_async overhead

async def serialize_nested_relations(self, item_id: int):
    @sync_to_async
    def _serialize():
        instance = TestModelSerializerForeignKey.objects.select_related(
            "test_model_serializer"
        ).get(pk=item_id)
        return {
            "id": instance.pk,
            "name": instance.name,
            "description": instance.description,
            "test_model_serializer": {
                "id": instance.test_model_serializer.pk,
                "name": instance.test_model_serializer.name,
                "description": instance.test_model_serializer.description,
            },
        }
    return await _serialize()

async def serialize_reverse_relations(self, item_id: int):
    @sync_to_async
    def _serialize():
        instance = TestModelSerializerReverseForeignKey.objects.prefetch_related(
            "test_model_serializer_foreign_keys"
        ).get(pk=item_id)
        children = [
            {"id": c.pk, "name": c.name, "description": c.description}
            for c in instance.test_model_serializer_foreign_keys.all()
        ]
        return {
            "id": instance.pk,
            "name": instance.name,
            "description": instance.description,
            "test_model_serializer_foreign_keys": children,
        }
    return await _serialize()

# Similar for M2M and complex query...
"""

print("Documentation of what needs to be added to each framework.")
print("FastAPI and Flask-RESTX implementations show the complexity")
print("of async relations without django-ninja-aio-crud.")
print("\nSee FASTAPI_ADDITIONS and FLASK_RESTX_ADDITIONS strings above.")
