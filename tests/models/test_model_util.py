from django.db.models import Q
from django.test import tag, TestCase
from unittest import mock

from ninja.errors import ConfigError
from ninja_aio.models import ModelUtil
from ninja_aio.schemas.helpers import ObjectQuerySchema, ObjectsQuerySchema
from tests.test_app import models, schema, serializers
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
        qs = await util.aget_objects(request, query_data=None)

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

        qs = await util.aget_objects(request, query_data, with_qs_request=False)
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

        qs = await util.aget_objects(request, query_data, with_qs_request=False)
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

        result = await util.aget_object(
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

        result = await util.aget_object(
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
            await util.aget_object(
                request, pk=None, query_data=query_data, with_qs_request=False
            )


@tag("model_util_delete_s_instance")
class ModelUtilDeleteSInstanceTestCase(TestCase):
    """delete_s(instance=...) must delete the given instance directly, without
    an extra lookup query, while still running the normal delete hooks."""

    async def test_delete_s_with_instance_skips_lookup(self):
        obj = await models.TestModel.objects.acreate(name="x", description="d")
        util = ModelUtil(models.TestModel)
        request = mock.Mock()

        with mock.patch.object(
            util, "get_object", side_effect=AssertionError("should not be called")
        ):
            await util.delete_s(request, obj.pk, instance=obj)

        self.assertFalse(
            await models.TestModel.objects.filter(pk=obj.pk).aexists()
        )

    async def test_delete_s_without_instance_still_looks_up(self):
        """Backward-compatible default: no instance -> falls back to get_object."""
        obj = await models.TestModel.objects.acreate(name="y", description="d")
        util = ModelUtil(models.TestModel)
        request = mock.Mock()

        await util.delete_s(request, obj.pk)

        self.assertFalse(
            await models.TestModel.objects.filter(pk=obj.pk).aexists()
        )


@tag("model_util_facade")
class ModelUtilFacadeTestCase(TestCase):
    """ModelUtil exposes the serializer CRUD facade for schema-only viewsets."""

    def setUp(self):
        self.util = ModelUtil(models.TestModel)
        self.request = mock.Mock()

    def test_sync_facade_round_trip(self):
        obj = self.util.create(
            schema.TestModelSchemaIn(name="sync", description="before"),
            request=self.request,
        )
        self.util.update(
            obj.pk, schema.TestModelSchemaPatch(description="after"), request=self.request
        )
        obj.refresh_from_db()
        self.assertEqual(
            self.util.model_dumps([obj], schema=schema.TestModelSchemaOut),
            [{"id": obj.pk, "name": "sync", "description": "after"}],
        )
        self.util.destroy(obj, request=self.request)
        self.assertFalse(models.TestModel.objects.filter(pk=obj.pk).exists())

    async def test_async_facade_round_trip(self):
        obj = await self.util.acreate(
            schema.TestModelSchemaIn(name="async", description="before"),
            request=self.request,
        )
        obj = await self.util.aupdate(
            obj, schema.TestModelSchemaPatch(description="after"), request=self.request
        )
        self.assertEqual(
            await self.util.amodel_dump(obj, schema=schema.TestModelSchemaOut),
            {"id": obj.pk, "name": "async", "description": "after"},
        )
        await self.util.adestroy(obj.pk, request=self.request)
        self.assertFalse(await models.TestModel.objects.filter(pk=obj.pk).aexists())

    async def test_legacy_crud_methods_emit_deprecation_warnings(self):
        obj = await models.TestModel.objects.acreate(name="legacy", description="d")
        calls = {
            "create_s": lambda: self.util.create_s(
                self.request,
                schema.TestModelSchemaIn(name="new", description="d"),
                schema.TestModelSchemaOut,
            ),
            "read_s": lambda: self.util.read_s(
                schema.TestModelSchemaOut, self.request, obj
            ),
            "list_read_s": lambda: self.util.list_read_s(
                schema.TestModelSchemaOut, self.request, [obj]
            ),
            "update_s": lambda: self.util.update_s(
                self.request,
                schema.TestModelSchemaPatch(description="x"),
                obj.pk,
                schema.TestModelSchemaOut,
            ),
            "delete_s": lambda: self.util.delete_s(self.request, obj.pk),
        }
        for name, call in calls.items():
            with self.subTest(method=name):
                with self.assertWarnsRegex(DeprecationWarning, f"ModelUtil.{name}"):
                    await call()

    async def test_legacy_bulk_methods_warn_and_keep_tuple_format(self):
        first = await models.TestModel.objects.acreate(name="a", description="d")
        patch = schema.TestModelSchemaPatch(description="u")

        with self.assertWarnsRegex(DeprecationWarning, "bulk_create_s"):
            success, errors = await self.util.bulk_create_s(
                self.request,
                [schema.TestModelSchemaIn(name="b", description="d"), object()],
            )
        self.assertEqual((len(success), len(errors)), (1, 1))

        with self.assertWarnsRegex(DeprecationWarning, "bulk_update_s"):
            success, errors = await self.util.bulk_update_s(
                self.request, [(first.pk, patch), (10**9, patch), (first.pk, object())]
            )
        self.assertEqual((success, len(errors)), ([first.pk], 2))

        with self.assertWarnsRegex(DeprecationWarning, "bulk_delete_s"):
            success, errors = await self.util.bulk_delete_s(
                self.request, [first.pk, 10**9], ["name"]
            )
        self.assertEqual((success, len(errors)), (["a"], 1))

        with self.assertWarns(DeprecationWarning):
            self.assertEqual(await self.util.bulk_delete_s(self.request, []), ([], []))

        other = await models.TestModel.objects.acreate(name="c", description="d")
        with self.assertWarns(DeprecationWarning):
            self.assertEqual(
                await self.util.bulk_delete_s(self.request, [other.pk]), ([other.pk], [])
            )

        fk_util = ModelUtil(models.TestModelForeignKey)
        with self.assertWarns(DeprecationWarning):
            success, errors = await fk_util.bulk_create_s(
                self.request,
                [schema.TestModelForeignKeySchemaIn(name="x", description="d", test_model=10**9)],
            )
        self.assertEqual((success, len(errors)), ([], 1))


@tag("model_util_facade", "facade_reads")
class FacadeReadTestCase(TestCase):
    """get/aget and get_queryset/aget_queryset honor optimize_for on every backend."""

    @classmethod
    def setUpTestData(cls):
        parent = models.TestModelSerializerReverseForeignKey.objects.create(
            name="parent", description="d"
        )
        cls.child = models.TestModelSerializerForeignKey.objects.create(
            name="child", description="d", test_model_serializer=parent
        )
        cls.plain = models.TestModel.objects.create(name="plain", description="d")
        cls.request = mock.Mock()

    def _assert_joined(self, obj):
        self.assertIn("test_model_serializer", obj._state.fields_cache)

    def test_model_serializer_sync_reads(self):
        serializer = models.TestModelSerializerForeignKey
        obj = serializer.get(self.child.pk, request=self.request, optimize_for="read")
        self._assert_joined(obj)
        qs = serializer.get_queryset(request=self.request, optimize_for="read")
        self.assertIn("test_model_serializer", qs.query.select_related)
        self.assertEqual(list(qs), [self.child])

    async def test_model_serializer_async_reads(self):
        serializer = models.TestModelSerializerForeignKey
        obj = await serializer.aget(
            self.child.pk, request=self.request, optimize_for="read"
        )
        self._assert_joined(obj)
        qs = await serializer.aget_queryset(request=self.request, optimize_for="read")
        self.assertIn("test_model_serializer", qs.query.select_related)
        self.assertEqual([o async for o in qs], [self.child])

    def test_model_util_sync_reads(self):
        util = ModelUtil(models.TestModel)
        self.assertEqual(util.get(self.plain.pk, request=self.request), self.plain)
        self.assertEqual(
            list(util.get_queryset(request=self.request, optimize_for="read")),
            [self.plain],
        )

    async def test_model_util_async_reads(self):
        util = ModelUtil(models.TestModel)
        self.assertEqual(
            await util.aget(self.plain.pk, request=self.request, optimize_for="detail"),
            self.plain,
        )
        qs = await util.aget_queryset(request=self.request)
        self.assertEqual([o async for o in qs], [self.plain])

    async def test_meta_serializer_forwards_optimize_for(self):
        fk_serializer = serializers.TestModelForeignKeySerializer
        with mock.patch.object(
            fk_serializer.util, "aget_object", mock.AsyncMock(return_value="obj")
        ) as aget_object:
            self.assertEqual(
                await fk_serializer.aget(1, request=self.request, optimize_for="detail"),
                "obj",
            )
        self.assertEqual(aget_object.await_args.kwargs["is_for"], "detail")
        with mock.patch.object(
            fk_serializer.util, "get_object", return_value="obj"
        ) as get_object:
            self.assertEqual(
                fk_serializer.get(1, request=self.request, optimize_for="read"), "obj"
            )
        self.assertEqual(get_object.call_args.kwargs["is_for"], "read")


@tag("model_util_queryset_optimizations_preserved")
class ModelUtilQuerysetOptimizationsPreservedTestCase(TestCase):
    """Regression test for ninja_aio/models/utils.py `_get_base_queryset`.

    `select_related`/`prefetch_related` declared under `QuerySet.read`/`QuerySet.detail`
    must survive the default `queryset_request` hook. Previously, the read/detail-scoped
    optimizations were applied and then unconditionally discarded by replacing the
    queryset with whatever the (default, unrelated-scope) `queryset_request` hook
    returned — causing an N+1 query per row for any relation field in the output schema.
    """

    @classmethod
    def setUpTestData(cls):
        cls.parent = models.TestModelSerializerReverseForeignKey.objects.create(
            name="parent", description="parent_desc"
        )
        models.TestModelSerializerForeignKey.objects.bulk_create(
            [
                models.TestModelSerializerForeignKey(
                    name=f"child_{i}",
                    description="d",
                    test_model_serializer=cls.parent,
                )
                for i in range(5)
            ]
        )

    async def test_select_related_survives_default_queryset_request_hook(self):
        """select_related declared in QuerySet.read must be applied to the queryset
        returned by get_objects, even though the default queryset_request hook runs
        (with_qs_request defaults to True for list/retrieve)."""
        util = models.TestModelSerializerForeignKey.util
        request = mock.Mock()

        qs = await util.aget_objects(request, is_for="read")

        self.assertIn("test_model_serializer", qs.query.select_related)

    async def test_relation_access_does_not_trigger_extra_queries(self):
        """Rows from get_objects() must come back with the FK relation already
        cached by the JOIN (select_related), so accessing it needs no extra query
        (N+1) now that the optimization survives the queryset_request hook."""
        util = models.TestModelSerializerForeignKey.util
        request = mock.Mock()

        qs = await util.aget_objects(request, is_for="read")
        objs = [obj async for obj in qs]

        self.assertEqual(len(objs), 5)
        for obj in objs:
            # Populated by the JOIN only if select_related actually ran;
            # otherwise Django would need a fresh query to resolve this.
            self.assertIn("test_model_serializer", obj._state.fields_cache)


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


@tag("model_util")
class AgetAttrTestCase(TestCase):
    """Test the async getattr utility function."""

    async def test_agetattr_existing_attribute(self):
        from ninja_aio.models.utils import agetattr

        result = await agetattr(models.TestModel, "__name__")
        self.assertEqual(result, "TestModel")

    async def test_agetattr_missing_with_default(self):
        from ninja_aio.models.utils import agetattr

        result = await agetattr(models.TestModel, "nonexistent", "fallback")
        self.assertEqual(result, "fallback")
