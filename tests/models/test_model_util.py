from django.db.models import Q
from django.test import tag, TestCase
from unittest import mock

from ninja.errors import ConfigError
from ninja_aio.models import ModelUtil
from ninja_aio.schemas.helpers import ObjectQuerySchema, ObjectsQuerySchema
from tests.test_app import models, schema
from tests.generics.models import Tests


class BaseTests:
    class ModelUtilTestCaseBase(Tests.GenericModelUtilTestCase):
        @property
        def create_data(self):
            return {"name": "test", "description": "test"}

        @property
        def parsed_input_data(self):
            return {"payload": self.create_data}

        @property
        def read_data(self):
            return {"id": 1, "name": "test", "description": "test"}

        @property
        def additional_getters(self):
            return {"description": "test"}

        @property
        def additional_filters(self):
            return {"name": "test"}

    @tag("model_util_model_serializer")
    class ModelUtilModelSerializerTestCase(ModelUtilTestCaseBase):
        @property
        def serializable_fields(self):
            return self.model.ReadSerializer.fields

    @tag("model_util_model")
    class ModelUtilModelBaseTestCase(ModelUtilTestCaseBase):
        @property
        def serializable_fields(self):
            return ["id", "name", "description"]


@tag("model_util_model_serializer_base")
class ModelUtilModelSerializerBaseTestCase(BaseTests.ModelUtilModelSerializerTestCase):
    model = models.TestModelSerializer

    @property
    def model_verbose_name_path(self):
        return "test-model-serializers"

    @property
    def model_verbose_name_view(self):
        return "testmodelserializers"


@tag("model_util_model_base")
class ModelUtilModelBaseTestCase(BaseTests.ModelUtilModelBaseTestCase):
    model = models.TestModel
    schema_in = schema.TestModelSchemaIn
    schema_out = schema.TestModelSchemaOut
    schema_patch = schema.TestModelSchemaPatch

    @property
    def model_verbose_name_path(self):
        return "test-models"

    @property
    def model_verbose_name_view(self):
        return "testmodels"


@tag("model_util_config_error")
class ModelUtilConfigErrorTestCase(TestCase):

    def test_model_util_raises_config_error_for_model_serializer_with_serializer_class(
        self,
    ):
        """Test that ModelUtil raises ConfigError when both model is ModelSerializer and serializer_class is provided."""
        from tests.test_app.serializers import TestModelForeignKeySerializer

        with self.assertRaises(ConfigError) as ctx:
            ModelUtil(
                models.TestModelSerializer,
                serializer_class=TestModelForeignKeySerializer,
            )

        self.assertIn(
            "cannot accept both model and serializer_class", str(ctx.exception)
        )


@tag("model_util_pk_field_type")
class ModelUtilPkFieldTypeTestCase(TestCase):

    def test_pk_field_type_raises_config_error_for_unknown_type(self):
        """Test that pk_field_type raises ConfigError for unknown field types."""
        from ninja.orm import fields

        # Create a mock model with an unknown pk field type
        mock_pk_field = mock.Mock()
        mock_pk_field.get_internal_type.return_value = "UnknownFieldType"

        mock_meta = mock.Mock()
        mock_meta.pk = mock_pk_field

        mock_model = mock.Mock()
        mock_model._meta = mock_meta

        util = ModelUtil(mock_model)

        # Temporarily remove the key if it exists to ensure KeyError
        original_types = fields.TYPES.copy()
        fields.TYPES.pop("UnknownFieldType", None)

        try:
            with self.assertRaises(ConfigError) as ctx:
                _ = util.pk_field_type

            self.assertIn("Do not know how to convert", str(ctx.exception))
            self.assertIn("UnknownFieldType", str(ctx.exception))
        finally:
            # Restore original types
            fields.TYPES.update(original_types)


@tag("model_util_objects_query_default")
class ModelUtilObjectsQueryDefaultTestCase(TestCase):
    """Test ModelUtil get_objects with default ObjectsQuerySchema (covers line 351)."""

    async def test_get_objects_with_none_query_data_uses_default(self):
        """Test that get_objects uses default ObjectsQuerySchema when query_data is None."""
        # Create a test object
        obj = await models.TestModel.objects.acreate(name="test", description="desc")

        util = ModelUtil(models.TestModel)

        # Create a mock request
        request = mock.Mock()

        # Call get_objects with query_data=None (will use default ObjectsQuerySchema)
        qs = await util.get_objects(request, query_data=None)

        # Should return a queryset
        count = await qs.acount()
        self.assertGreaterEqual(count, 1)

        # Cleanup
        await obj.adelete()


@tag("model_util_q_object_filters")
class ModelUtilQObjectFiltersTestCase(TestCase):
    """Test ModelUtil with Q objects in filters and getters."""

    async def test_get_objects_with_q_filter(self):
        """Test _get_base_queryset applies Q object filters correctly."""
        await models.TestModel.objects.all().adelete()
        obj1 = await models.TestModel.objects.acreate(name="alpha", description="first")
        await models.TestModel.objects.acreate(name="beta", description="second")

        util = ModelUtil(models.TestModel)
        request = mock.Mock()
        query_data = ObjectsQuerySchema(filters=Q(name="alpha"))

        qs = await util.get_objects(request, query_data, with_qs_request=False)
        self.assertEqual(await qs.acount(), 1)
        self.assertEqual(await qs.afirst(), obj1)

    async def test_get_objects_with_q_filter_or(self):
        """Test _get_base_queryset applies Q object with OR logic."""
        await models.TestModel.objects.all().adelete()
        obj1 = await models.TestModel.objects.acreate(name="alpha", description="first")
        obj2 = await models.TestModel.objects.acreate(name="beta", description="second")
        await models.TestModel.objects.acreate(name="gamma", description="third")

        util = ModelUtil(models.TestModel)
        request = mock.Mock()
        query_data = ObjectsQuerySchema(filters=Q(name="alpha") | Q(name="beta"))

        qs = await util.get_objects(request, query_data, with_qs_request=False)
        self.assertEqual(await qs.acount(), 2)
        results = [obj async for obj in qs]
        self.assertIn(obj1, results)
        self.assertIn(obj2, results)

    async def test_get_object_with_q_getter(self):
        """Test get_object applies Q object getters correctly."""
        await models.TestModel.objects.all().adelete()
        obj = await models.TestModel.objects.acreate(
            name="target", description="find me"
        )
        await models.TestModel.objects.acreate(name="other", description="not me")

        util = ModelUtil(models.TestModel)
        request = mock.Mock()
        query_data = ObjectQuerySchema(getters=Q(name="target"))

        result = await util.get_object(
            request, pk=obj.pk, query_data=query_data, with_qs_request=False
        )
        self.assertEqual(result, obj)

    async def test_get_object_with_q_getter_no_pk(self):
        """Test get_object with Q getter and no pk uses Q filter only."""
        await models.TestModel.objects.all().adelete()
        obj = await models.TestModel.objects.acreate(
            name="unique", description="only one"
        )

        util = ModelUtil(models.TestModel)
        request = mock.Mock()
        query_data = ObjectQuerySchema(getters=Q(name="unique"))

        result = await util.get_object(
            request, pk=None, query_data=query_data, with_qs_request=False
        )
        self.assertEqual(result, obj)

    async def test_get_object_with_q_getter_not_found(self):
        """Test get_object with Q getter raises NotFoundError when no match."""
        from ninja_aio.exceptions import NotFoundError

        await models.TestModel.objects.all().adelete()

        util = ModelUtil(models.TestModel)
        request = mock.Mock()
        query_data = ObjectQuerySchema(getters=Q(name="nonexistent"))

        with self.assertRaises(NotFoundError):
            await util.get_object(
                request, pk=None, query_data=query_data, with_qs_request=False
            )


# ============================================================
# Coverage test for models/utils.py — line 791
# ============================================================


@tag("model_util", "coverage", "prefetch_forward_rels")
class PrefetchWithForwardRelsTestCase(TestCase):
    """Cover utils.py:791 — _prefetch_reverse_relations_on_instance with forward_rels."""

    @classmethod
    def setUpTestData(cls):
        from tests.test_app.models import (
            TestModelSerializerForeignKey,
            TestModelSerializerReverseForeignKey,
        )

        cls.reverse_fk = TestModelSerializerReverseForeignKey.objects.create(
            name="parent", description="parent"
        )
        cls.fk_obj = TestModelSerializerForeignKey.objects.create(
            name="child",
            description="child",
            test_model_serializer=cls.reverse_fk,
        )

    async def test_prefetch_with_both_forward_and_reverse_rels(self):
        """When both reverse and forward rels exist, select_related is applied."""
        from tests.test_app.models import TestModelSerializerForeignKey

        util = ModelUtil(TestModelSerializerForeignKey)
        obj = await TestModelSerializerForeignKey.objects.aget(
            pk=self.fk_obj.pk
        )
        # Mock reverse rels to be non-empty (triggers the prefetch path)
        # and forward rels to be non-empty (triggers line 791: select_related)
        # Use "test_model_serializer" which is a valid FK on this model
        with mock.patch.object(
            util, "get_reverse_relations",
            return_value=["test_model_serializer"]
        ), mock.patch.object(
            util, "get_select_relateds",
            return_value=["test_model_serializer"]
        ):
            result = await util._prefetch_reverse_relations_on_instance(obj, "read")
        self.assertEqual(result.pk, self.fk_obj.pk)


# ============================================================
# NinjaAIOMeta verbose name resolution tests
# ============================================================


@tag("model_util", "ninja_aio_meta")
class NinjaAIOMetaVerboseNameTestCase(TestCase):
    """Test that ModelUtil picks up verbose names from NinjaAIOMeta."""

    def test_model_verbose_name_from_ninja_aio_meta(self):
        """NinjaAIOMeta.verbose_name overrides Django Meta."""
        util = ModelUtil(models.TestModelWithNinjaAIOMeta)
        self.assertEqual(util.model_verbose_name, "Custom Entity")

    def test_model_verbose_name_plural_from_ninja_aio_meta(self):
        """NinjaAIOMeta.verbose_name_plural overrides Django Meta."""
        util = ModelUtil(models.TestModelWithNinjaAIOMeta)
        self.assertEqual(util.model_verbose_name_plural, "Custom Entities")

    def test_verbose_name_path_resolver_uses_ninja_aio_meta(self):
        """verbose_name_path_resolver uses NinjaAIOMeta.verbose_name_plural."""
        util = ModelUtil(models.TestModelWithNinjaAIOMeta)
        self.assertEqual(util.verbose_name_path_resolver(), "Custom-Entities")

    def test_verbose_name_view_resolver_uses_ninja_aio_meta(self):
        """verbose_name_view_resolver uses NinjaAIOMeta.verbose_name_plural."""
        util = ModelUtil(models.TestModelWithNinjaAIOMeta)
        self.assertEqual(util.verbose_name_view_resolver(), "CustomEntities")

    def test_partial_ninja_aio_meta_falls_back_to_django_meta(self):
        """Model with partial NinjaAIOMeta falls back to Django Meta for missing attrs."""
        util = ModelUtil(models.TestModelWithPartialNinjaAIOMeta)
        # verbose_name not in NinjaAIOMeta, should fall back to Django Meta
        self.assertEqual(
            util.model_verbose_name,
            models.TestModelWithPartialNinjaAIOMeta._meta.verbose_name,
        )
        self.assertEqual(
            util.model_verbose_name_plural,
            models.TestModelWithPartialNinjaAIOMeta._meta.verbose_name_plural,
        )

    def test_model_without_ninja_aio_meta_uses_django_meta(self):
        """Models without NinjaAIOMeta use Django Meta as before."""
        util = ModelUtil(models.TestModelSerializer)
        self.assertEqual(
            util.model_verbose_name,
            models.TestModelSerializer._meta.verbose_name,
        )
        self.assertEqual(
            util.model_verbose_name_plural,
            models.TestModelSerializer._meta.verbose_name_plural,
        )


@tag("model_util", "ninja_aio_meta", "get_ninja_aio_meta_attr")
class GetNinjaAIOMetaAttrTestCase(TestCase):
    """Test the get_ninja_aio_meta_attr helper function."""

    def test_returns_attr_when_present(self):
        from ninja_aio.types import get_ninja_aio_meta_attr

        result = get_ninja_aio_meta_attr(
            models.TestModelWithNinjaAIOMeta, "not_found_name"
        )
        self.assertEqual(result, "custom_entity")

    def test_returns_default_when_attr_missing(self):
        from ninja_aio.types import get_ninja_aio_meta_attr

        result = get_ninja_aio_meta_attr(
            models.TestModelWithPartialNinjaAIOMeta, "verbose_name"
        )
        self.assertIsNone(result)

    def test_returns_default_when_no_ninja_aio_meta(self):
        from ninja_aio.types import get_ninja_aio_meta_attr

        result = get_ninja_aio_meta_attr(models.TestModelSerializer, "not_found_name")
        self.assertIsNone(result)

    def test_custom_default(self):
        from ninja_aio.types import get_ninja_aio_meta_attr

        result = get_ninja_aio_meta_attr(
            models.TestModelSerializer, "not_found_name", default="fallback"
        )
        self.assertEqual(result, "fallback")
