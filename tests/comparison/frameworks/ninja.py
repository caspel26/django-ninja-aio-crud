"""Pure Django Ninja implementation for framework comparison."""

from typing import Any, List

from asgiref.sync import sync_to_async
from ninja import NinjaAPI, Schema
from pydantic import Field

from tests.comparison.base import FrameworkBenchmark
from tests.test_app.models import (
    TestModelSerializer,
    TestModelSerializerForeignKey,
    TestModelSerializerReverseForeignKey,
    TestModelSerializerManyToMany,
    TestModelSerializerReverseManyToMany,
)


class ItemCreate(Schema):
    """Schema for creating items."""

    name: str
    description: str


class ItemUpdate(Schema):
    """Schema for updating items."""

    description: str


class ItemOut(Schema):
    """Schema for item output."""

    id: int
    name: str
    description: str
    age: int = Field(default=0)
    active: bool = Field(default=True)


class PureDjangoNinjaBenchmark(FrameworkBenchmark):
    """Benchmark implementation for pure Django Ninja (without AIO CRUD)."""

    name = "Django Ninja"

    def __init__(self):
        self.api = None
        self.setup_app()
        self.setup_endpoints()

    def setup_app(self):
        """Initialize Django Ninja API."""
        self.api = NinjaAPI(urls_namespace="comparison_ninja")

    def setup_endpoints(self):
        """Create CRUD endpoints manually."""
        # Endpoints are defined as methods below and would normally be
        # registered with decorators, but for benchmarking we call them directly
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
                {
                    "id": item.pk,
                    "name": item.name,
                    "description": item.description,
                    "age": item.age,
                    "active": item.active,
                }
            )
        return items

    async def get_item(self, item_id: int) -> Any:
        """Retrieve a single item by ID."""
        instance = await TestModelSerializer.objects.aget(pk=item_id)
        return {
            "id": instance.pk,
            "name": instance.name,
            "description": instance.description,
            "age": instance.age,
            "active": instance.active,
        }

    async def update_item(self, item_id: int, data: dict) -> Any:
        """Update an item and return the updated object."""
        instance = await TestModelSerializer.objects.aget(pk=item_id)
        schema_data = ItemUpdate(**data)
        instance.description = schema_data.description
        await sync_to_async(instance.save)()
        return {
            "id": instance.pk,
            "name": instance.name,
            "description": instance.description,
            "age": instance.age,
            "active": instance.active,
        }

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
                {
                    "id": item.pk,
                    "name": item.name,
                    "description": item.description,
                    "age": item.age,
                    "active": item.active,
                }
            )
        return items

    async def serialize_with_relations(self, item_id: int) -> Any:
        """Serialize an item with its FK relations."""
        instance = await TestModelSerializerForeignKey.objects.select_related(
            "test_model_serializer"
        ).aget(pk=item_id)
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

    async def serialize_nested_relations(self, item_id: int) -> Any:
        """Serialize with deep nested relations - manually constructed."""
        instance = await TestModelSerializerForeignKey.objects.select_related(
            "test_model_serializer"
        ).aget(pk=item_id)
        # Manual nested dict construction - error-prone and verbose
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

    async def serialize_reverse_relations(self, item_id: int) -> Any:
        """Serialize reverse FK - VERY PAINFUL in async Django!"""
        instance = await TestModelSerializerReverseForeignKey.objects.prefetch_related(
            "test_model_serializer_foreign_keys"
        ).aget(pk=item_id)

        # Can't iterate async in dict comprehension easily!
        # Must manually construct the list
        children = []
        async for child in instance.test_model_serializer_foreign_keys.all():
            children.append({
                "id": child.pk,
                "name": child.name,
                "description": child.description,
            })

        return {
            "id": instance.pk,
            "name": instance.name,
            "description": instance.description,
            "test_model_serializer_foreign_keys": children,
        }

    async def serialize_many_to_many(self, item_id: int) -> Any:
        """Serialize M2M - also painful in async."""
        instance = await TestModelSerializerManyToMany.objects.prefetch_related(
            "test_model_serializers"
        ).aget(pk=item_id)

        # Manual async iteration for M2M
        related_items = []
        async for item in instance.test_model_serializers.all():
            related_items.append({
                "id": item.pk,
                "name": item.name,
                "description": item.description,
            })

        return {
            "id": instance.pk,
            "name": instance.name,
            "description": instance.description,
            "test_model_serializers": related_items,
        }

    async def complex_query_with_relations(self, **filters) -> list:
        """Complex query - lots of manual work!"""
        queryset = TestModelSerializerForeignKey.objects.filter(
            **filters
        ).select_related("test_model_serializer")[:20]

        # Manual async iteration and dict construction
        items = []
        async for item in queryset:
            items.append({
                "id": item.pk,
                "name": item.name,
                "description": item.description,
                "test_model_serializer": {
                    "id": item.test_model_serializer.pk,
                    "name": item.test_model_serializer.name,
                    "description": item.test_model_serializer.description,
                },
            })
        return items
