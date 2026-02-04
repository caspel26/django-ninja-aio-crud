"""Async Django REST Framework (ADRF) implementation for framework comparison.

ADRF provides native async support for Django REST Framework, allowing async views
and serializers without sync_to_async wrappers. This is the async version of DRF.
"""

from typing import Any

from adrf.serializers import ModelSerializer as AsyncModelSerializer

from tests.comparison.base import FrameworkBenchmark
from tests.test_app.models import (
    TestModelSerializer,
    TestModelSerializerForeignKey,
    TestModelSerializerReverseForeignKey,
    TestModelSerializerManyToMany,
    TestModelSerializerReverseManyToMany,
)


class ItemSerializer(AsyncModelSerializer):
    """ADRF Serializer for TestModelSerializer."""

    class Meta:
        model = TestModelSerializer
        fields = ["id", "name", "description", "age", "active"]


class ItemCreateSerializer(AsyncModelSerializer):
    """ADRF Serializer for creating items."""

    class Meta:
        model = TestModelSerializer
        fields = ["name", "description"]


class ItemUpdateSerializer(AsyncModelSerializer):
    """ADRF Serializer for updating items."""

    class Meta:
        model = TestModelSerializer
        fields = ["description"]


class RelationSerializer(AsyncModelSerializer):
    """ADRF Serializer for items with FK relations."""

    test_model_serializer = ItemSerializer()

    class Meta:
        model = TestModelSerializerForeignKey
        fields = ["id", "name", "description", "test_model_serializer"]


class ReverseRelationChildSerializer(AsyncModelSerializer):
    """ADRF Serializer for child items."""

    class Meta:
        model = TestModelSerializerForeignKey
        fields = ["id", "name", "description"]


class ReverseRelationSerializer(AsyncModelSerializer):
    """ADRF Serializer for reverse FK relations."""

    test_model_serializer_foreign_keys = ReverseRelationChildSerializer(
        many=True, read_only=True
    )

    class Meta:
        model = TestModelSerializerReverseForeignKey
        fields = ["id", "name", "description", "test_model_serializer_foreign_keys"]


class ManyToManyRelatedSerializer(AsyncModelSerializer):
    """ADRF Serializer for M2M related items."""

    class Meta:
        model = TestModelSerializerReverseManyToMany
        fields = ["id", "name", "description"]


class ManyToManySerializer(AsyncModelSerializer):
    """ADRF Serializer for M2M relations."""

    test_model_serializers = ManyToManyRelatedSerializer(many=True, read_only=True)

    class Meta:
        model = TestModelSerializerManyToMany
        fields = ["id", "name", "description", "test_model_serializers"]


class ADRFBenchmark(FrameworkBenchmark):
    """Benchmark implementation for Async Django REST Framework (ADRF).

    ADRF provides native async support for DRF, eliminating the need for
    sync_to_async wrappers. This is the proper async version of DRF.
    """

    name = "ADRF"

    def __init__(self):
        self.serializer_class = ItemSerializer
        self.create_serializer_class = ItemCreateSerializer
        self.update_serializer_class = ItemUpdateSerializer
        self.setup_app()
        self.setup_endpoints()

    def setup_app(self):
        """ADRF doesn't require app initialization for this benchmark."""
        pass

    def setup_endpoints(self):
        """ADRF endpoints are defined via serializers (already set up in __init__)."""
        pass

    async def create_item(self, data: dict) -> Any:
        """Create a single item using ADRF serializer."""
        serializer = self.create_serializer_class(data=data)
        serializer.is_valid(raise_exception=True)
        instance = await serializer.asave()
        return await ItemSerializer(instance).adata

    async def list_items(self, limit: int = 10, offset: int = 0) -> list:
        """List items with pagination using ADRF serializer."""
        queryset = TestModelSerializer.objects.all()[offset : offset + limit]
        serializer = self.serializer_class(queryset, many=True)
        return await serializer.adata

    async def get_item(self, item_id: int) -> Any:
        """Retrieve a single item by ID using ADRF serializer."""
        instance = await TestModelSerializer.objects.aget(pk=item_id)
        serializer = self.serializer_class(instance)
        return await serializer.adata

    async def update_item(self, item_id: int, data: dict) -> Any:
        """Update an item using ADRF serializer."""
        instance = await TestModelSerializer.objects.aget(pk=item_id)
        serializer = self.update_serializer_class(instance, data=data, partial=True)
        serializer.is_valid(raise_exception=True)
        updated_instance = await serializer.asave()
        return await self.serializer_class(updated_instance).adata

    async def delete_item(self, item_id: int) -> None:
        """Delete an item by ID."""
        instance = await TestModelSerializer.objects.aget(pk=item_id)
        await instance.adelete()

    async def filter_items(self, **filters) -> list:
        """Apply filters to list query using ADRF serializer."""
        queryset = TestModelSerializer.objects.filter(**filters)
        serializer = self.serializer_class(queryset, many=True)
        return await serializer.adata

    async def serialize_with_relations(self, item_id: int) -> Any:
        """Serialize an item with its FK relations using ADRF."""
        instance = await TestModelSerializerForeignKey.objects.select_related(
            "test_model_serializer"
        ).aget(pk=item_id)
        serializer = RelationSerializer(instance)
        return await serializer.adata

    async def serialize_nested_relations(self, item_id: int) -> Any:
        """ADRF nested relations - native async support."""
        instance = await TestModelSerializerForeignKey.objects.select_related(
            "test_model_serializer"
        ).aget(pk=item_id)
        serializer = RelationSerializer(instance)
        return await serializer.adata

    async def serialize_reverse_relations(self, item_id: int) -> Any:
        """ADRF reverse relations - native async prefetch_related support."""
        instance = await TestModelSerializerReverseForeignKey.objects.prefetch_related(
            "test_model_serializer_foreign_keys"
        ).aget(pk=item_id)
        serializer = ReverseRelationSerializer(instance)
        return await serializer.adata

    async def serialize_many_to_many(self, item_id: int) -> Any:
        """ADRF M2M - native async M2M serialization."""
        instance = await TestModelSerializerManyToMany.objects.prefetch_related(
            "test_model_serializers"
        ).aget(pk=item_id)
        serializer = ManyToManySerializer(instance)
        return await serializer.adata

    async def complex_query_with_relations(self, **filters) -> list:
        """ADRF complex query - native async without wrapper overhead."""
        queryset = TestModelSerializerForeignKey.objects.filter(
            **filters
        ).select_related("test_model_serializer")[:20]
        serializer = RelationSerializer(queryset, many=True)
        return await serializer.adata
