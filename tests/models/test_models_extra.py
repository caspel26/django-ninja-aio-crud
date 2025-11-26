from django.test import TestCase, tag
from ninja_aio.models import ModelUtil, ModelSerializer
from ninja_aio.exceptions import SerializeError
from tests.test_app import models as app_models
from ninja_aio.schemas.helpers import QuerySchema
from django.db import models
import base64
from unittest import mock


class CustomOptionalSerializer(ModelSerializer):
    name = models.CharField(max_length=50)
    description = models.TextField(max_length=50, null=True)

    class ReadSerializer:
        fields = ["id", "name", "description"]

    class CreateSerializer:
        fields = ["name", "description"]
        customs = [("extra", str, "DEF")]  # custom removable field

    class UpdateSerializer:
        optionals = [("description", str)]  # optional => can be None

    class Meta:
        app_label = app_models.TestModelSerializer._meta.app_label


@tag("model_util_relations", "model_util")
class ModelUtilRelationsTestCase(TestCase):
    def test_select_relateds_foreign_key(self):
        util = ModelUtil(app_models.TestModelSerializerForeignKey)
        self.assertIn("test_model_serializer", util.get_select_relateds())
        self.assertEqual(util.get_reverse_relations(), [])

    def test_reverse_relations_many_to_one(self):
        util = ModelUtil(app_models.TestModelSerializerReverseForeignKey)
        revs = util.get_reverse_relations()
        self.assertIn("test_model_serializer_foreign_keys", revs)


@tag("model_util_pk_field_type", "model_util")
class ModelUtilPKFieldTypeTestCase(TestCase):
    def test_pk_field_type_is_int(self):
        util = ModelUtil(app_models.TestModelSerializer)
        self.assertIn(util.pk_field_type, (int,))  # BigAutoField maps to int


@tag("model_util_parse_input", "model_util")
class ModelUtilParseInputTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.custom_obj = CustomOptionalSerializer.objects.create(
            name="c1", description="d1"
        )
        cls.fk_rev = app_models.TestModelSerializerReverseForeignKey.objects.create(
            name="rev", description="rev"
        )
        cls.schema_create = CustomOptionalSerializer.generate_create_s()
        cls.schema_update = CustomOptionalSerializer.generate_update_s()
        cls.fk_schema_in = app_models.TestModelSerializerForeignKey.generate_create_s()
        cls.util_custom = ModelUtil(CustomOptionalSerializer)
        cls.util_fk = ModelUtil(app_models.TestModelSerializerForeignKey)

    async def test_parse_input_custom_and_optional(self):
        data = self.schema_create(name="n", description="d", extra="Z")
        payload, customs = await self.util_custom.parse_input_data(None, data)
        self.assertNotIn("extra", payload)
        self.assertEqual(customs["extra"], "Z")
        # optional exclusion when None on update
        upd = self.schema_update()
        payload_u, customs_u = await self.util_custom.parse_input_data(None, upd)
        self.assertNotIn("description", payload_u)
        self.assertEqual(customs_u, {})

    async def test_parse_input_foreign_key_resolution(self):
        data = self.fk_schema_in(
            name="fk", description="fk", test_model_serializer_id=self.fk_rev.pk
        )
        payload, _ = await self.util_fk.parse_input_data(None, data)
        self.assertIsInstance(
            payload["test_model_serializer"],
            app_models.TestModelSerializerReverseForeignKey,
        )

    async def test_decode_binary_success_and_failure(self):
        class BinSerializer(ModelSerializer):
            data = models.BinaryField()

            class CreateSerializer:
                fields = ["data"]

            class ReadSerializer:
                fields = ["id", "data"]

            class Meta:
                app_label = app_models.TestModelSerializer._meta.app_label

        schema_in = BinSerializer.generate_create_s()
        util = ModelUtil(BinSerializer)
        good_bytes = b"hello"
        b64 = base64.b64encode(good_bytes).decode()
        data_good = schema_in(data=b64)
        payload, _ = await util.parse_input_data(None, data_good)
        self.assertEqual(payload["data"], good_bytes)
        # bad base64
        data_bad = schema_in(data="$$invalid$$")
        with self.assertRaises(SerializeError):
            await util.parse_input_data(None, data_bad)


@tag("model_serializer_get_custom_fields", "model_serializer")
class ModelSerializerGetCustomFieldsTestCase(TestCase):
    def test_invalid_custom_field_spec_raises(self):
        class BadSpec(ModelSerializer):
            a = models.CharField(max_length=10)

            class CreateSerializer:
                customs = [("x", int, 1, "extra")]  # invalid length

            class Meta:
                app_label = app_models.TestModelSerializer._meta.app_label

        with self.assertRaises(ValueError):
            BadSpec.get_custom_fields("create")


@tag("model_serializer_verbose_name_path", "model_serializer")
class ModelSerializerVerboseNamePathTestCase(TestCase):
    def test_verbose_name_path_generation(self):
        class VNModelSerializer(ModelSerializer):
            title = models.CharField(max_length=50)

            class Meta:
                app_label = app_models.TestModelSerializer._meta.app_label

        self.assertEqual(
            VNModelSerializer.verbose_name_path_resolver(),
            "vn-model-serializers",
        )


@tag("model_serializer_has_changed", "model_serializer")
class ModelSerializerHasChangedTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.obj = app_models.TestModelSerializer.objects.create(
            name="original", description="original"
        )

    def test_has_changed_detection(self):
        self.obj.name = "new"
        self.assertTrue(self.obj.has_changed("name"))
    
    def test_has_changed_before_create(self):
        new_obj = app_models.TestModelSerializer(
            name="new", description="new"
        )
        self.assertFalse(new_obj.has_changed("name"))
        self.assertFalse(new_obj.has_changed("description"))


@tag("model_util_read_s_queryset_error", "model_util")
class ModelUtilReadSQuerysetErrorTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.obj = app_models.TestModelSerializer.objects.create(
            name="a", description="b"
        )
        cls.schema_out = app_models.TestModelSerializer.generate_read_s()
        cls.util = ModelUtil(app_models.TestModelSerializer)

    async def test_read_s_without_lookup_raises(self):
        # Expect a failure because queryset passed to schema.from_orm
        with self.assertRaises(Exception):  # broad: underlying may vary
            await self.util.read_s(
                self.schema_out,
                request=None,
                obj=None,
                query_data=QuerySchema(),
                is_for_read=True,
            )


@tag("model_serializer_update_hooks", "model_serializer")
class ModelSerializerUpdateHooksTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.order = []

        def mk(name):
            def _fn(self):
                cls.order.append(name)

            return _fn

        app_models.TestModelSerializer.before_save = mk("before")
        app_models.TestModelSerializer.after_save = mk("after")
        app_models.TestModelSerializer.on_create_before_save = mk("on_create_before")
        app_models.TestModelSerializer.on_create_after_save = mk("on_create_after")
        cls.obj = app_models.TestModelSerializer.objects.create(
            name="x", description="y"
        )
        cls.obj.description = "y2"
        cls.obj.save()  # update path

    def test_update_hooks_order(self):
        # For update path, create hooks should not repeat
        self.assertEqual(
            self.order,
            [
                "on_create_before",
                "before",
                "on_create_after",
                "after",
                "before",
                "after",
            ],
        )


@tag("model_util_apply_query_opts", "model_util")
class ModelUtilApplyQueryOptimizationsTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.util_fk = ModelUtil(
            app_models.TestModelSerializerForeignKey
        )  # has forward FK
        cls.util_rev = ModelUtil(
            app_models.TestModelSerializerReverseForeignKey
        )  # has reverse rel

    def test_select_related_merge_on_read(self):
        qs = app_models.TestModelSerializerForeignKey.objects.all()
        custom_list = ["custom_sel"]
        query_data = QuerySchema(select_related=custom_list, prefetch_related=[])
        with (
            mock.patch(
                "django.db.models.query.QuerySet.select_related",
                side_effect=lambda self, *args: self,
                autospec=True,
            ) as m_sel,
            mock.patch(
                "django.db.models.query.QuerySet.prefetch_related",
                side_effect=lambda self, *args: self,
                autospec=True,
            ) as m_pref,
        ):
            _ = self.util_fk._apply_query_optimizations(
                qs, query_data, is_for_read=True
            )
            sel_args = m_sel.call_args[0][1:]
            self.assertEqual(sel_args[0], "custom_sel")
            # auto discovered forward relation appended
            for rel in self.util_fk.get_select_relateds():
                self.assertIn(rel, sel_args)
            m_pref.assert_not_called()  # no prefetch list provided / reverse rel absent

    def test_select_related_no_merge_when_not_read(self):
        qs = app_models.TestModelSerializerForeignKey.objects.all()
        query_data = QuerySchema(select_related=["only_custom"], prefetch_related=[])
        with mock.patch(
            "django.db.models.query.QuerySet.select_related",
            side_effect=lambda self, *args: self,
            autospec=True,
        ) as m_sel:
            _ = self.util_fk._apply_query_optimizations(
                qs, query_data, is_for_read=False
            )
            sel_args = m_sel.call_args[0][1:]
            self.assertEqual(sel_args, ("only_custom",))

    def test_prefetch_related_merge_on_read(self):
        qs = app_models.TestModelSerializerReverseForeignKey.objects.all()
        query_data = QuerySchema(
            select_related=[], prefetch_related=["custom_prefetch"]
        )
        with (
            mock.patch(
                "django.db.models.query.QuerySet.prefetch_related",
                side_effect=lambda self, *args: self,
                autospec=True,
            ) as m_pref,
            mock.patch(
                "django.db.models.query.QuerySet.select_related",
                side_effect=lambda self, *args: self,
                autospec=True,
            ) as m_sel,
        ):
            _ = self.util_rev._apply_query_optimizations(
                qs, query_data, is_for_read=True
            )
            pref_args = m_pref.call_args[0][1:]
            self.assertEqual(pref_args[0], "custom_prefetch")
            for rel in self.util_rev.get_reverse_relations():
                self.assertIn(rel, pref_args)
            m_sel.assert_not_called()

    def test_prefetch_related_no_merge_when_not_read(self):
        qs = app_models.TestModelSerializerReverseForeignKey.objects.all()
        query_data = QuerySchema(
            select_related=[], prefetch_related=["only_custom_prefetch"]
        )
        with mock.patch(
            "django.db.models.query.QuerySet.prefetch_related",
            side_effect=lambda self, *args: self,
            autospec=True,
        ) as m_pref:
            _ = self.util_rev._apply_query_optimizations(
                qs, query_data, is_for_read=False
            )
            pref_args = m_pref.call_args[0][1:]
            self.assertEqual(pref_args, ("only_custom_prefetch",))
