"""django-ninja-aio-crud implementation for framework comparison."""

from typing import Any

from ninja_aio import NinjaAIO
from ninja_aio.models import ModelUtil
from tests.comparison.base import FrameworkBenchmark
from tests.generics.request import Request
from tests.test_app.models import (
    TestModelSerializer,
    TestModelSerializerForeignKey,
    TestModelSerializerReverseForeignKey,
    TestModelSerializerManyToMany,
    TestModelSerializerReverseManyToMany,
)


class NinjaAIOBenchmark(FrameworkBenchmark):
    """Benchmark implementation for django-ninja-aio-crud."""

    name = "Django Ninja AIO"

    def __init__(self):
        self.api = None
        self.util = None
        self.request = None
        self.schema_in = None
        self.schema_out = None
        self.schema_update = None
        self.setup_app()
        self.setup_endpoints()

    def setup_app(self):
        """Initialize NinjaAIO application."""
        self.api = NinjaAIO(urls_namespace="comparison_ninja_aio")
        self.util = ModelUtil(TestModelSerializer)
        self.request = Request("test-model-serializers")

    def setup_endpoints(self):
        """Generate schemas for CRUD operations."""
        self.schema_in = TestModelSerializer.generate_create_s()
        self.schema_out = TestModelSerializer.generate_read_s()
        self.schema_update = TestModelSerializer.generate_update_s()

    async def create_item(self, data: dict) -> Any:
        """Create a single item via ModelUtil."""
        schema_data = self.schema_in(**data)
        return await self.util.create_s(
            request=self.request.post(),
            data=schema_data,
            obj_schema=self.schema_out,
        )

    async def list_items(self, limit: int = 10, offset: int = 0) -> list:
        """List items with pagination."""
        queryset = TestModelSerializer.objects.all()[offset : offset + limit]
        items = await self.util.list_read_s(
            schema=self.schema_out,
            request=self.request.get(),
            instances=queryset,
        )
        return items

    async def get_item(self, item_id: int) -> Any:
        """Retrieve a single item by ID."""
        instance = await TestModelSerializer.objects.aget(pk=item_id)
        return await self.util.read_s(
            schema=self.schema_out,
            request=self.request.get(),
            instance=instance,
        )

    async def update_item(self, item_id: int, data: dict) -> Any:
        """Update an item and return the updated object."""
        schema_data = self.schema_update(**data)
        return await self.util.update_s(
            request=self.request.patch(),
            data=schema_data,
            pk=item_id,
            obj_schema=self.schema_out,
        )

    async def delete_item(self, item_id: int) -> None:
        """Delete an item by ID."""
        await self.util.delete_s(request=self.request.delete(), pk=item_id)

    async def filter_items(self, **filters) -> list:
        """Apply filters to list query."""
        queryset = TestModelSerializer.objects.filter(**filters)
        items = await self.util.list_read_s(
            schema=self.schema_out,
            request=self.request.get(),
            instances=queryset,
        )
        return items

    async def serialize_with_relations(self, item_id: int) -> Any:
        """Serialize an item with its FK relations."""
        from ninja_aio.models import ModelUtil

        util = ModelUtil(TestModelSerializerForeignKey)
        schema = TestModelSerializerForeignKey.generate_read_s()
        instance = await TestModelSerializerForeignKey.objects.select_related(
            "test_model_serializer"
        ).aget(pk=item_id)
        return await util.read_s(
            schema=schema,
            request=self.request.get(),
            instance=instance,
        )

    async def serialize_nested_relations(self, item_id: int) -> Any:
        """Serialize with deep nested relations (2+ levels).

        Your framework handles this automatically with QuerySet configuration.
        """
        from ninja_aio.models import ModelUtil

        util = ModelUtil(TestModelSerializerForeignKey)
        schema = TestModelSerializerForeignKey.generate_read_s()
        # Your framework's QuerySet config automatically handles select_related
        instance = await util.get_object(self.request.get(), item_id, is_for="read")
        return await util.read_s(
            schema=schema,
            request=self.request.get(),
            instance=instance,
        )

    async def serialize_reverse_relations(self, item_id: int) -> Any:
        """Serialize with reverse FK relations (one-to-many).

        Your framework handles prefetch_related automatically in async!
        This is notoriously difficult in Django async.
        """
        from ninja_aio.models import ModelUtil

        util = ModelUtil(TestModelSerializerReverseForeignKey)
        schema = TestModelSerializerReverseForeignKey.generate_read_s()
        # Your framework's _prefetch_reverse_relations handles this automatically
        instance = await util.get_object(self.request.get(), item_id, is_for="read")
        return await util.read_s(
            schema=schema,
            request=self.request.get(),
            instance=instance,
        )

    async def serialize_many_to_many(self, item_id: int) -> Any:
        """Serialize with M2M relations.

        Your framework's QuerySet config handles prefetch_related for M2M.
        """
        from ninja_aio.models import ModelUtil

        util = ModelUtil(TestModelSerializerManyToMany)
        schema = TestModelSerializerManyToMany.generate_read_s()
        instance = await util.get_object(self.request.get(), item_id, is_for="read")
        return await util.read_s(
            schema=schema,
            request=self.request.get(),
            instance=instance,
        )

    async def complex_query_with_relations(self, **filters) -> list:
        """Complex query: filters + relations + pagination in async.

        Your framework makes this trivial. Other frameworks struggle here.
        """
        from ninja_aio.models import ModelUtil

        util = ModelUtil(TestModelSerializerForeignKey)
        schema = TestModelSerializerForeignKey.generate_read_s()
        # Filters + select_related + pagination - all async
        queryset = TestModelSerializerForeignKey.objects.filter(**filters).select_related(
            "test_model_serializer"
        )[:20]
        return await util.list_read_s(
            schema=schema,
            request=self.request.get(),
            instances=queryset,
        )
