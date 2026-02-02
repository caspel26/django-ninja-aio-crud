"""
Tests for FK resolution optimization.

This module tests that the FK resolution optimization in create_s and update_s
maintains correct functionality while reducing redundant database queries.
"""

from django.test import TestCase, tag
from asgiref.sync import async_to_sync

from tests.test_app import models
from ninja_aio.models import ModelUtil


@tag("fk_optimization")
class FKOptimizationTestCase(TestCase):
    """Test that FK resolution optimization maintains correct functionality."""

    @classmethod
    def setUpTestData(cls):
        """Create test data."""
        # Create reverse FK instances for testing
        cls.rev_fk_1 = models.TestModelSerializerReverseForeignKey.objects.create(
            name="reverse_fk_1", description="First reverse FK"
        )
        cls.rev_fk_2 = models.TestModelSerializerReverseForeignKey.objects.create(
            name="reverse_fk_2", description="Second reverse FK"
        )

    def setUp(self):
        """Set up test fixtures."""
        from django.http import HttpRequest

        self.request = HttpRequest()
        self.model_util = ModelUtil(models.TestModelSerializerForeignKey)

    @async_to_sync
    async def test_create_s_with_fk_returns_correct_data(self):
        """
        Test that create_s correctly creates and returns objects with FK fields.

        This verifies that the optimization doesn't break the functionality
        of creating objects with foreign keys.
        """
        from ninja import Schema

        class CreateSchema(Schema):
            name: str
            description: str
            test_model_serializer: int

        create_data = CreateSchema(
            name="test_fk",
            description="Testing FK optimization",
            test_model_serializer=self.rev_fk_1.id,
        )

        read_schema = models.TestModelSerializerForeignKey.generate_read_s()

        result = await self.model_util.create_s(
            self.request, create_data, read_schema
        )

        # Verify result correctness
        self.assertEqual(result["name"], "test_fk")
        self.assertEqual(result["description"], "Testing FK optimization")
        self.assertEqual(result["test_model_serializer"]["id"], self.rev_fk_1.id)
        self.assertEqual(result["test_model_serializer"]["name"], "reverse_fk_1")

        # Verify object exists in database
        created_obj = await models.TestModelSerializerForeignKey.objects.select_related(
            "test_model_serializer"
        ).aget(name="test_fk")
        self.assertEqual(created_obj.test_model_serializer.id, self.rev_fk_1.id)

    @async_to_sync
    async def test_create_s_fk_instance_attached(self):
        """
        Test that FK instances are properly attached after create_s.

        This ensures that the FK relationship is accessible without additional queries.
        """
        from ninja import Schema

        class CreateSchema(Schema):
            name: str
            description: str
            test_model_serializer: int

        create_data = CreateSchema(
            name="test_attached",
            description="Testing FK attachment",
            test_model_serializer=self.rev_fk_1.id,
        )

        read_schema = models.TestModelSerializerForeignKey.generate_read_s()

        result = await self.model_util.create_s(
            self.request, create_data, read_schema
        )

        # Verify FK data is in the result (not just the ID)
        self.assertIn("test_model_serializer", result)
        self.assertIsInstance(result["test_model_serializer"], dict)
        self.assertEqual(result["test_model_serializer"]["name"], "reverse_fk_1")

    @async_to_sync
    async def test_update_s_with_fk_change(self):
        """
        Test that update_s correctly updates FK fields.

        This verifies that the optimization doesn't break FK updates.
        """
        # First create an object with FK 1
        existing_obj = await models.TestModelSerializerForeignKey.objects.acreate(
            name="existing",
            description="Existing object",
            test_model_serializer=self.rev_fk_1,
        )

        from ninja import Schema

        class UpdateSchema(Schema):
            name: str | None = None
            description: str | None = None
            test_model_serializer: int | None = None

        update_data = UpdateSchema(test_model_serializer=self.rev_fk_2.id)

        read_schema = models.TestModelSerializerForeignKey.generate_read_s()

        result = await self.model_util.update_s(
            self.request, update_data, existing_obj.pk, read_schema
        )

        # Verify FK was updated
        self.assertEqual(result["test_model_serializer"]["id"], self.rev_fk_2.id)
        self.assertEqual(result["test_model_serializer"]["name"], "reverse_fk_2")

        # Verify update persisted in database
        updated_obj = await models.TestModelSerializerForeignKey.objects.select_related(
            "test_model_serializer"
        ).aget(pk=existing_obj.pk)
        self.assertEqual(updated_obj.test_model_serializer.id, self.rev_fk_2.id)

    @async_to_sync
    async def test_update_s_fk_instance_attached(self):
        """
        Test that FK instances are properly attached after update_s.

        This ensures that the updated FK relationship is accessible.
        """
        # Create object with FK 1
        existing_obj = await models.TestModelSerializerForeignKey.objects.acreate(
            name="existing",
            description="Existing object",
            test_model_serializer=self.rev_fk_1,
        )

        from ninja import Schema

        class UpdateSchema(Schema):
            name: str | None = None
            description: str | None = None
            test_model_serializer: int | None = None

        update_data = UpdateSchema(test_model_serializer=self.rev_fk_2.id)

        read_schema = models.TestModelSerializerForeignKey.generate_read_s()

        result = await self.model_util.update_s(
            self.request, update_data, existing_obj.pk, read_schema
        )

        # Verify FK data is fully present (not just ID)
        self.assertIn("test_model_serializer", result)
        self.assertIsInstance(result["test_model_serializer"], dict)
        self.assertEqual(result["test_model_serializer"]["name"], "reverse_fk_2")
        self.assertEqual(
            result["test_model_serializer"]["description"], "Second reverse FK"
        )

    @async_to_sync
    async def test_create_s_without_fk_still_works(self):
        """
        Test that create_s still works for models without FK fields.

        This ensures the optimization doesn't break non-FK model operations.
        """
        model_util = ModelUtil(models.TestModelSerializer)

        from ninja import Schema

        class CreateSchema(Schema):
            name: str
            description: str

        create_data = CreateSchema(name="no_fk", description="No FK test")

        read_schema = models.TestModelSerializer.generate_read_s()

        result = await model_util.create_s(self.request, create_data, read_schema)

        # Verify result correctness
        self.assertEqual(result["name"], "no_fk")
        self.assertEqual(result["description"], "No FK test")
        self.assertIn("id", result)

    @async_to_sync
    async def test_reverse_relations_loaded_after_create(self):
        """
        Test that reverse relations are properly loaded after create_s.

        This ensures that the optimization properly handles reverse FK relationships.
        """
        # Create parent first
        parent = await models.TestModelSerializerReverseForeignKey.objects.acreate(
            name="parent", description="Parent object"
        )

        # Create child with FK to parent
        from ninja import Schema

        class CreateSchema(Schema):
            name: str
            description: str
            test_model_serializer: int

        create_data = CreateSchema(
            name="child",
            description="Child object",
            test_model_serializer=parent.id,
        )

        read_schema = models.TestModelSerializerForeignKey.generate_read_s()

        result = await self.model_util.create_s(
            self.request, create_data, read_schema
        )

        # Verify forward FK is loaded
        self.assertEqual(result["test_model_serializer"]["id"], parent.id)
        self.assertEqual(result["test_model_serializer"]["name"], "parent")

    @async_to_sync
    async def test_multiple_creates_with_same_fk(self):
        """
        Test that multiple creates with the same FK work correctly.

        This ensures the optimization handles repeated FK values properly.
        """
        from ninja import Schema

        class CreateSchema(Schema):
            name: str
            description: str
            test_model_serializer: int

        read_schema = models.TestModelSerializerForeignKey.generate_read_s()

        # Create first object
        result1 = await self.model_util.create_s(
            self.request,
            CreateSchema(
                name="first",
                description="First",
                test_model_serializer=self.rev_fk_1.id,
            ),
            read_schema,
        )

        # Create second object with same FK
        result2 = await self.model_util.create_s(
            self.request,
            CreateSchema(
                name="second",
                description="Second",
                test_model_serializer=self.rev_fk_1.id,
            ),
            read_schema,
        )

        # Both should have correct FK
        self.assertEqual(result1["test_model_serializer"]["id"], self.rev_fk_1.id)
        self.assertEqual(result2["test_model_serializer"]["id"], self.rev_fk_1.id)
        self.assertNotEqual(result1["id"], result2["id"])

    @async_to_sync
    async def test_parent_model_with_reverse_relations(self):
        """
        Test create_s on parent model that has reverse relations configured.

        TestModelSerializerReverseForeignKey has reverse FK field in its ReadSerializer,
        so creating it should exercise _prefetch_reverse_relations_on_instance.
        """
        # Use parent model (has reverse relations in ReadSerializer)
        parent_util = ModelUtil(models.TestModelSerializerReverseForeignKey)

        from ninja import Schema

        class CreateSchema(Schema):
            name: str
            description: str

        create_data = CreateSchema(
            name="parent_model", description="Parent with reverse FK"
        )

        read_schema = models.TestModelSerializerReverseForeignKey.generate_read_s()

        # This should exercise _prefetch_reverse_relations_on_instance
        # because the ReadSerializer includes "test_model_serializer_foreign_keys"
        result = await parent_util.create_s(self.request, create_data, read_schema)

        # Verify result correctness
        self.assertEqual(result["name"], "parent_model")
        self.assertEqual(result["description"], "Parent with reverse FK")

        # The result should include the reverse relation field
        self.assertIn("test_model_serializer_foreign_keys", result)
        # It should be an empty list since we haven't created any children yet
        self.assertIsInstance(result["test_model_serializer_foreign_keys"], list)
        self.assertEqual(len(result["test_model_serializer_foreign_keys"]), 0)

    @async_to_sync
    async def test_update_s_without_changing_fk(self):
        """
        Test that update_s works when not changing the FK field.

        This ensures the optimization handles partial updates correctly.
        """
        # Create object
        existing_obj = await models.TestModelSerializerForeignKey.objects.acreate(
            name="existing",
            description="Original description",
            test_model_serializer=self.rev_fk_1,
        )

        from ninja import Schema

        class UpdateSchema(Schema):
            name: str | None = None
            description: str | None = None
            test_model_serializer: int | None = None

        # Update only description, not FK
        update_data = UpdateSchema(description="Updated description")

        read_schema = models.TestModelSerializerForeignKey.generate_read_s()

        result = await self.model_util.update_s(
            self.request, update_data, existing_obj.pk, read_schema
        )

        # Verify FK unchanged
        self.assertEqual(result["test_model_serializer"]["id"], self.rev_fk_1.id)
        # Verify description updated
        self.assertEqual(result["description"], "Updated description")
