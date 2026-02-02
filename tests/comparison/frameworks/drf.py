"""Django REST Framework implementation for framework comparison.

Note: DRF does not have native async support, so all operations are
wrapped with sync_to_async for fair comparison.
"""

from typing import Any

from asgiref.sync import sync_to_async
from rest_framework import serializers

from tests.comparison.base import FrameworkBenchmark
from tests.test_app.models import (
    TestModelSerializer,
    TestModelSerializerForeignKey,
    TestModelSerializerReverseForeignKey,
    TestModelSerializerManyToMany,
    TestModelSerializerReverseManyToMany,
)


class ItemSerializer(serializers.ModelSerializer):
    """DRF Serializer for TestModelSerializer."""

    class Meta:
        model = TestModelSerializer
        fields = ["id", "name", "description", "age", "active"]


class ItemCreateSerializer(serializers.ModelSerializer):
    """DRF Serializer for creating items."""

    class Meta:
        model = TestModelSerializer
        fields = ["name", "description"]


class ItemUpdateSerializer(serializers.ModelSerializer):
    """DRF Serializer for updating items."""

    class Meta:
        model = TestModelSerializer
        fields = ["description"]


class RelationSerializer(serializers.ModelSerializer):
    """DRF Serializer for items with FK relations."""

    test_model_serializer = ItemSerializer()

    class Meta:
        model = TestModelSerializerForeignKey
        fields = ["id", "name", "description", "test_model_serializer"]


class ReverseRelationChildSerializer(serializers.ModelSerializer):
    """DRF Serializer for child items."""

    class Meta:
        model = TestModelSerializerForeignKey
        fields = ["id", "name", "description"]


class ReverseRelationSerializer(serializers.ModelSerializer):
    """DRF Serializer for reverse FK relations."""

    test_model_serializer_foreign_keys = ReverseRelationChildSerializer(many=True, read_only=True)

    class Meta:
        model = TestModelSerializerReverseForeignKey
        fields = ["id", "name", "description", "test_model_serializer_foreign_keys"]


class ManyToManyRelatedSerializer(serializers.ModelSerializer):
    """DRF Serializer for M2M related items."""

    class Meta:
        model = TestModelSerializerReverseManyToMany
        fields = ["id", "name", "description"]


class ManyToManySerializer(serializers.ModelSerializer):
    """DRF Serializer for M2M relations."""

    test_model_serializers = ManyToManyRelatedSerializer(many=True, read_only=True)

    class Meta:
        model = TestModelSerializerManyToMany
        fields = ["id", "name", "description", "test_model_serializers"]


class DRFBenchmark(FrameworkBenchmark):
    """Benchmark implementation for Django REST Framework.

    DRF is synchronous by design, so all operations are wrapped
    with sync_to_async to allow async benchmarking.
    """

    name = "Django REST Framework"

    def __init__(self):
        self.serializer_class = ItemSerializer
        self.create_serializer_class = ItemCreateSerializer
        self.update_serializer_class = ItemUpdateSerializer
        self.setup_app()
        self.setup_endpoints()

    def setup_app(self):
        """DRF doesn't require app initialization for this benchmark."""
        pass

    def setup_endpoints(self):
        """DRF endpoints are defined via serializers (already set up in __init__)."""
        pass

    async def create_item(self, data: dict) -> Any:
        """Create a single item using DRF serializer."""

        @sync_to_async
        def _create():
            serializer = self.create_serializer_class(data=data)
            serializer.is_valid(raise_exception=True)
            instance = serializer.save()
            return self.serializer_class(instance).data

        return await _create()

    async def list_items(self, limit: int = 10, offset: int = 0) -> list:
        """List items with pagination using DRF serializer."""

        @sync_to_async
        def _list():
            queryset = TestModelSerializer.objects.all()[offset : offset + limit]
            serializer = self.serializer_class(queryset, many=True)
            return serializer.data

        return await _list()

    async def get_item(self, item_id: int) -> Any:
        """Retrieve a single item by ID using DRF serializer."""

        @sync_to_async
        def _get():
            instance = TestModelSerializer.objects.get(pk=item_id)
            serializer = self.serializer_class(instance)
            return serializer.data

        return await _get()

    async def update_item(self, item_id: int, data: dict) -> Any:
        """Update an item using DRF serializer."""

        @sync_to_async
        def _update():
            instance = TestModelSerializer.objects.get(pk=item_id)
            serializer = self.update_serializer_class(instance, data=data, partial=True)
            serializer.is_valid(raise_exception=True)
            updated_instance = serializer.save()
            return self.serializer_class(updated_instance).data

        return await _update()

    async def delete_item(self, item_id: int) -> None:
        """Delete an item by ID."""

        @sync_to_async
        def _delete():
            instance = TestModelSerializer.objects.get(pk=item_id)
            instance.delete()

        await _delete()

    async def filter_items(self, **filters) -> list:
        """Apply filters to list query using DRF serializer."""

        @sync_to_async
        def _filter():
            queryset = TestModelSerializer.objects.filter(**filters)
            serializer = self.serializer_class(queryset, many=True)
            return serializer.data

        return await _filter()

    async def serialize_with_relations(self, item_id: int) -> Any:
        """Serialize an item with its FK relations using DRF."""

        @sync_to_async
        def _serialize():
            instance = TestModelSerializerForeignKey.objects.select_related(
                "test_model_serializer"
            ).get(pk=item_id)
            serializer = RelationSerializer(instance)
            return serializer.data

        return await _serialize()

    async def serialize_nested_relations(self, item_id: int) -> Any:
        """DRF nested relations - requires separate serializer classes."""

        @sync_to_async
        def _serialize():
            instance = TestModelSerializerForeignKey.objects.select_related(
                "test_model_serializer"
            ).get(pk=item_id)
            serializer = RelationSerializer(instance)
            return serializer.data

        return await _serialize()

    async def serialize_reverse_relations(self, item_id: int) -> Any:
        """DRF reverse relations - needs prefetch_related + separate serializer."""

        @sync_to_async
        def _serialize():
            # Must use prefetch_related for reverse FK
            instance = TestModelSerializerReverseForeignKey.objects.prefetch_related(
                "test_model_serializer_foreign_keys"
            ).get(pk=item_id)
            serializer = ReverseRelationSerializer(instance)
            return serializer.data

        return await _serialize()

    async def serialize_many_to_many(self, item_id: int) -> Any:
        """DRF M2M - separate serializer + sync_to_async overhead."""

        @sync_to_async
        def _serialize():
            instance = TestModelSerializerManyToMany.objects.prefetch_related(
                "test_model_serializers"
            ).get(pk=item_id)
            serializer = ManyToManySerializer(instance)
            return serializer.data

        return await _serialize()

    async def complex_query_with_relations(self, **filters) -> list:
        """DRF complex query - sync_to_async wrapper adds overhead."""

        @sync_to_async
        def _query():
            queryset = TestModelSerializerForeignKey.objects.filter(
                **filters
            ).select_related("test_model_serializer")[:20]
            serializer = RelationSerializer(queryset, many=True)
            return serializer.data

        return await _query()
