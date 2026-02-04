"""FastAPI implementation for framework comparison."""

from typing import Any

from asgiref.sync import sync_to_async
from fastapi import FastAPI
from pydantic import BaseModel, Field

from tests.comparison.base import FrameworkBenchmark
from tests.test_app.models import (
    TestModelSerializer,
    TestModelSerializerForeignKey,
    TestModelSerializerReverseForeignKey,
    TestModelSerializerManyToMany,
)


class ItemCreate(BaseModel):
    """Pydantic schema for creating items."""

    name: str
    description: str


class ItemUpdate(BaseModel):
    """Pydantic schema for updating items."""

    description: str


class ItemOut(BaseModel):
    """Pydantic schema for item output."""

    id: int
    name: str
    description: str
    age: int = Field(default=0)
    active: bool = Field(default=True)

    class Config:
        from_attributes = True  # Pydantic v2 compatibility


class ItemWithRelation(BaseModel):
    """Pydantic schema for item with FK relation."""

    id: int
    name: str
    description: str
    test_model_serializer: ItemOut

    class Config:
        from_attributes = True


class ReverseChild(BaseModel):
    """Schema for reverse FK children."""

    id: int
    name: str
    description: str

    class Config:
        from_attributes = True


class ItemWithReverse(BaseModel):
    """Schema for reverse FK relations."""

    id: int
    name: str
    description: str
    test_model_serializer_foreign_keys: list[ReverseChild]

    class Config:
        from_attributes = True


class M2MRelated(BaseModel):
    """Schema for M2M related items."""

    id: int
    name: str
    description: str

    class Config:
        from_attributes = True


class ItemWithM2M(BaseModel):
    """Schema for M2M relations."""

    id: int
    name: str
    description: str
    test_model_serializers: list[M2MRelated]

    class Config:
        from_attributes = True


class FastAPIBenchmark(FrameworkBenchmark):
    """Benchmark implementation for FastAPI.

    FastAPI has async support but needs to wrap Django ORM calls
    with sync_to_async since Django ORM operations are synchronous.
    """

    name = "FastAPI"

    def __init__(self):
        self.app = None
        self.setup_app()
        self.setup_endpoints()

    def setup_app(self):
        """Initialize FastAPI application."""
        self.app = FastAPI()

    def setup_endpoints(self):
        """FastAPI endpoints are defined as methods for benchmarking."""
        pass

    async def create_item(self, data: dict) -> Any:
        """Create a single item."""
        schema_data = ItemCreate(**data)
        instance = await sync_to_async(TestModelSerializer.objects.create)(
            name=schema_data.name,
            description=schema_data.description,
        )
        return {
            "id": instance.pk,
            "name": instance.name,
            "description": instance.description,
            "age": instance.age,
            "active": instance.active,
        }

    async def list_items(self, limit: int = 10, offset: int = 0) -> list:
        """List items with pagination."""
        queryset = TestModelSerializer.objects.all()[offset : offset + limit]
        items = []
        async for item in queryset:
            items.append(
                ItemOut(
                    id=item.pk,
                    name=item.name,
                    description=item.description,
                    age=item.age,
                    active=item.active,
                ).model_dump()
            )
        return items

    async def get_item(self, item_id: int) -> Any:
        """Retrieve a single item by ID."""
        instance = await TestModelSerializer.objects.aget(pk=item_id)
        return ItemOut(
            id=instance.pk,
            name=instance.name,
            description=instance.description,
            age=instance.age,
            active=instance.active,
        ).model_dump()

    async def update_item(self, item_id: int, data: dict) -> Any:
        """Update an item and return the updated object."""
        instance = await TestModelSerializer.objects.aget(pk=item_id)
        schema_data = ItemUpdate(**data)
        instance.description = schema_data.description
        await sync_to_async(instance.save)()
        return ItemOut(
            id=instance.pk,
            name=instance.name,
            description=instance.description,
            age=instance.age,
            active=instance.active,
        ).model_dump()

    async def delete_item(self, item_id: int) -> None:
        """Delete an item by ID."""
        instance = await TestModelSerializer.objects.aget(pk=item_id)
        await sync_to_async(instance.delete)()

    async def filter_items(self, **filters) -> list:
        """Apply filters to list query."""
        queryset = TestModelSerializer.objects.filter(**filters)
        items = []
        async for item in queryset:
            items.append(
                ItemOut(
                    id=item.pk,
                    name=item.name,
                    description=item.description,
                    age=item.age,
                    active=item.active,
                ).model_dump()
            )
        return items

    async def serialize_with_relations(self, item_id: int) -> Any:
        """Serialize an item with its FK relations."""
        instance = await TestModelSerializerForeignKey.objects.select_related(
            "test_model_serializer"
        ).aget(pk=item_id)
        return ItemWithRelation.model_validate(instance).model_dump()

    async def serialize_nested_relations(self, item_id: int) -> Any:
        """FastAPI nested - Pydantic handles it but needs select_related."""
        instance = await TestModelSerializerForeignKey.objects.select_related(
            "test_model_serializer"
        ).aget(pk=item_id)
        return ItemWithRelation.model_validate(instance).model_dump()

    async def serialize_reverse_relations(self, item_id: int) -> Any:
        """FastAPI reverse FK - must manually iterate in async!"""
        instance = await TestModelSerializerReverseForeignKey.objects.prefetch_related(
            "test_model_serializer_foreign_keys"
        ).aget(pk=item_id)

        # Pydantic can't handle RelatedManager - must convert to list manually
        children = []
        async for child in instance.test_model_serializer_foreign_keys.all():
            children.append(ReverseChild.model_validate(child))

        return {
            "id": instance.pk,
            "name": instance.name,
            "description": instance.description,
            "test_model_serializer_foreign_keys": [c.model_dump() for c in children],
        }

    async def serialize_many_to_many(self, item_id: int) -> Any:
        """FastAPI M2M - must manually iterate async relations!"""
        instance = await TestModelSerializerManyToMany.objects.prefetch_related(
            "test_model_serializers"
        ).aget(pk=item_id)

        # Pydantic can't handle M2M managers - must convert to list manually
        related = []
        async for item in instance.test_model_serializers.all():
            related.append(M2MRelated.model_validate(item))

        return {
            "id": instance.pk,
            "name": instance.name,
            "description": instance.description,
            "test_model_serializers": [r.model_dump() for r in related],
        }

    async def complex_query_with_relations(self, **filters) -> list:
        """FastAPI complex query - manual async iteration needed."""
        queryset = TestModelSerializerForeignKey.objects.filter(
            **filters
        ).select_related("test_model_serializer")[:20]
        items = []
        async for item in queryset:
            items.append(ItemWithRelation.model_validate(item).model_dump())
        return items
