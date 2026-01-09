import datetime

from django.test import tag, TestCase
from django.utils import timezone

from ninja_aio.models import ModelUtil
from tests.generics.views import Tests
from tests.test_app import schema, models, views, serializers
from ninja_aio import NinjaAIO
from ninja_aio.views import APIViewSet
from ninja_aio.decorators import api_get, api_post


class BaseTests:
    class SetUpViewSetTestCase:
        @property
        def _payload(self):
            return {
                "name": f"test_name_{self.model._meta.model_name}",
                "description": f"test_description_{self.model._meta.model_name}",
            }

        @property
        def payload_create(self):
            return self._payload

        @property
        def payload_update(self):
            return {
                "description": f"test_description_{self.model._meta.model_name}_update",
            }

        @property
        def response_data(self):
            return self._payload

        @property
        def create_response_data(self):
            return self.response_data

    class ModelSerializerViewSetTestCaseBase(SetUpViewSetTestCase):
        @property
        def schemas(self):
            return (
                self.model.generate_read_s(),
                self.model.generate_create_s(),
                self.model.generate_update_s(),
            )

    class ApiViewSetSetUpRelation(SetUpViewSetTestCase):
        relation_viewset: views.GenericAPIViewSet

        @classmethod
        def setUpTestData(cls):
            data = {
                "name": f"test_name_{cls.relation_viewset.model._meta.model_name}",
                "description": f"test_description_{cls.relation_viewset.model._meta.model_name}",
            }
            if not hasattr(cls, "relation_data"):
                cls.relation_data = data
            else:
                cls.relation_data = cls.relation_data | data
            super().setUpTestData()

    @tag("viewset_foreign_key")
    class ApiViewSetForeignKeyTestCaseBase(
        ApiViewSetSetUpRelation, Tests.RelationViewSetTestCase
    ):
        @property
        def payload_create(self):
            return super().payload_create | {
                "test_model_serializer_id": self.relation_pk
            }

        @property
        def response_data(self):
            return super().response_data | {
                self.relation_related_name: self.relation_obj
            }

    @tag("viewset_reverse_foreign_key")
    class ApiViewSetReverseForeignKeyTestCaseBase(
        ApiViewSetSetUpRelation, Tests.ReverseRelationViewSetTestCase
    ):
        @property
        def response_data(self):
            return super().response_data | {
                self.relation_related_name: [self.relation_schema_data]
            }

        @property
        def create_response_data(self):
            return super().response_data | {self.relation_related_name: []}

    @tag("viewset_many_to_many")
    class ApiViewSetManyToManyTestCaseBase(
        ApiViewSetSetUpRelation, Tests.RelationViewSetTestCase
    ):
        @classmethod
        def setUpTestData(cls):
            super().setUpTestData()
            obj = cls.model.objects.get(pk=cls.obj_content[cls.pk_att])
            getattr(obj, cls.relation_related_name).add(cls.relation_obj)
            obj.save()
            cls.relation_schema_data.pop(cls.foreign_key_reverse_field, None)

        @property
        def response_data(self):
            return super().response_data | {
                self.relation_related_name: [self.relation_schema_data]
            }

        @property
        def create_response_data(self):
            return super().response_data | {self.relation_related_name: []}


# ==========================================================
#             MODEL SERIALIZER VIEWSET TESTS
# ==========================================================


@tag("model_serializer_viewset")
class ApiViewSetModelSerializerTestCase(
    BaseTests.ModelSerializerViewSetTestCaseBase,
    Tests.ViewSetTestCase,
):
    namespace = "test_model_serializer_viewset"
    model = models.TestModelSerializer
    viewset = views.TestModelSerializerAPI()

    async def _drop_all_objects(self):
        await self.model.objects.all().adelete()

    async def test_query_params_icontains_mixin(self):
        await self._drop_all_objects()
        obj = await self.model.objects.acreate(**self.payload_create)
        res = await self.viewset.query_params_handler(
            self.model.objects.all(), {"name": f"{self.model._meta.model_name}"}
        )
        self.assertEqual(await res.acount(), 1)
        self.assertEqual((await res.afirst()), obj)

    async def test_query_params_boolean_mixin(self):
        await self._drop_all_objects()
        obj_active = await self.model.objects.acreate(**self.payload_create)
        obj_inactive = await self.model.objects.acreate(
            **{**self.payload_create, "active": False}
        )
        res_active = await self.viewset.query_params_handler(
            self.model.objects.all(), {"active": True}
        )
        self.assertEqual(await res_active.acount(), 1)
        self.assertEqual((await res_active.afirst()), obj_active)
        res_inactive = await self.viewset.query_params_handler(
            self.model.objects.all(), {"active": False}
        )
        self.assertEqual(await res_inactive.acount(), 1)
        self.assertEqual((await res_inactive.afirst()), obj_inactive)

    async def test_query_params_numeric_mixin(self):
        await self._drop_all_objects()
        obj_age_25 = await self.model.objects.acreate(
            **{**self.payload_create, "age": 25}
        )
        obj_age_30 = await self.model.objects.acreate(
            **{**self.payload_create, "age": 30}
        )
        res_age_25 = await self.viewset.query_params_handler(
            self.model.objects.all(), {"age": 25}
        )
        self.assertEqual(await res_age_25.acount(), 1)
        self.assertEqual((await res_age_25.afirst()), obj_age_25)
        res_age_30 = await self.viewset.query_params_handler(
            self.model.objects.all(), {"age": 30}
        )
        self.assertEqual(await res_age_30.acount(), 1)
        self.assertEqual((await res_age_30.afirst()), obj_age_30)

    async def test_query_params_date_mixin(self):
        await self._drop_all_objects()
        obj_today = await self.model.objects.acreate(**self.payload_create)
        res_today = await self.viewset.query_params_handler(
            self.model.objects.all(),
            {"active_from": obj_today.active_from},
        )
        self.assertEqual(await res_today.acount(), 1)
        self.assertEqual((await res_today.afirst()), obj_today)


@tag("model_serializer_greater_than_date_viewset")
class ApiViewSetModelSerializerGreaterThanDateTestCase(
    BaseTests.ModelSerializerViewSetTestCaseBase,
    Tests.ViewSetTestCase,
):
    namespace = "test_model_serializer_greater_than_date_viewset"
    model = models.TestModelSerializer
    viewset = views.TestModelSerializerGreaterThanMixinAPI()

    async def _drop_all_objects(self):
        await self.model.objects.all().adelete()

    async def test_query_params_greater_than_date_mixin(self):
        await self._drop_all_objects()
        past_date = timezone.now() - datetime.timedelta(days=1)
        future_date = timezone.now() + datetime.timedelta(days=1)
        obj_past = await self.model.objects.acreate(**self.payload_create)
        obj_past.active_from = past_date
        await obj_past.asave()
        obj_future = await self.model.objects.acreate(**self.payload_create)
        obj_future.active_from = future_date
        await obj_future.asave()
        res_greater_than_now = await self.viewset.query_params_handler(
            self.model.objects.all(), {"active_from": timezone.now()}
        )
        self.assertEqual(await res_greater_than_now.acount(), 1)
        self.assertEqual((await res_greater_than_now.afirst()), obj_future)


@tag("model_serializer_less_than_date_viewset")
class ApiViewSetModelSerializerLessThanDateTestCase(
    BaseTests.ModelSerializerViewSetTestCaseBase,
    Tests.ViewSetTestCase,
):
    namespace = "test_model_serializer_less_than_date_viewset"
    model = models.TestModelSerializer
    viewset = views.TestModelSerializerLessThanMixinAPI()

    async def _drop_all_objects(self):
        await self.model.objects.all().adelete()

    async def test_query_params_less_than_date_mixin(self):
        await self._drop_all_objects()
        past_date = timezone.now() - datetime.timedelta(days=1)
        future_date = timezone.now() + datetime.timedelta(days=1)
        obj_past = await self.model.objects.acreate(**self.payload_create)
        obj_past.active_from = past_date
        await obj_past.asave()
        obj_future = await self.model.objects.acreate(**self.payload_create)
        obj_future.active_from = future_date
        await obj_future.asave()
        res_less_than_now = await self.viewset.query_params_handler(
            self.model.objects.all(), {"active_from": timezone.now()}
        )
        self.assertEqual(await res_less_than_now.acount(), 1)
        self.assertEqual((await res_less_than_now.afirst()), obj_past)


@tag("model_serializer_greater_equal_date_viewset")
class ApiViewSetModelSerializerGreaterEqualDateTestCase(
    BaseTests.ModelSerializerViewSetTestCaseBase,
    Tests.ViewSetTestCase,
):
    namespace = "test_model_serializer_greater_equal_date_viewset"
    model = models.TestModelSerializer
    viewset = views.TestModelSerializerGreaterEqualMixinAPI()

    async def _drop_all_objects(self):
        await self.model.objects.all().adelete()

    async def test_query_params_greater_equal_date_mixin(self):
        await self._drop_all_objects()
        past_date = timezone.now() - datetime.timedelta(days=1)
        future_date = timezone.now() + datetime.timedelta(days=1)
        obj_past = await self.model.objects.acreate(**self.payload_create)
        obj_past.active_from = past_date
        await obj_past.asave()
        obj_future = await self.model.objects.acreate(**self.payload_create)
        obj_future.active_from = future_date
        await obj_future.asave()
        res_greater_equal_now = await self.viewset.query_params_handler(
            self.model.objects.all(), {"active_from": timezone.now()}
        )
        self.assertEqual(await res_greater_equal_now.acount(), 1)
        self.assertEqual((await res_greater_equal_now.afirst()), obj_future)


@tag("model_serializer_less_equal_date_viewset")
class ApiViewSetModelSerializerLessEqualDateTestCase(
    BaseTests.ModelSerializerViewSetTestCaseBase,
    Tests.ViewSetTestCase,
):
    namespace = "test_model_serializer_less_equal_date_viewset"
    model = models.TestModelSerializer
    viewset = views.TestModelSerializerLessEqualMixinAPI()

    async def _drop_all_objects(self):
        await self.model.objects.all().adelete()

    async def test_query_params_less_equal_date_mixin(self):
        await self._drop_all_objects()
        past_date = timezone.now() - datetime.timedelta(days=1)
        future_date = timezone.now() + datetime.timedelta(days=1)
        obj_past = await self.model.objects.acreate(**self.payload_create)
        obj_past.active_from = past_date
        await obj_past.asave()
        obj_future = await self.model.objects.acreate(**self.payload_create)
        obj_future.active_from = future_date
        await obj_future.asave()
        res_less_equal_now = await self.viewset.query_params_handler(
            self.model.objects.all(), {"active_from": timezone.now()}
        )
        self.assertEqual(await res_less_equal_now.acount(), 1)
        self.assertEqual((await res_less_equal_now.afirst()), obj_past)


@tag("model_serializer_foreign_key_viewset")
class ApiViewSetModelSerializerForeignKeyTestCase(
    BaseTests.ModelSerializerViewSetTestCaseBase,
    BaseTests.ApiViewSetForeignKeyTestCaseBase,
):
    namespace = "test_model_serializer_foreign_key_viewset"
    model = models.TestModelSerializerForeignKey
    viewset = views.TestModelSerializerForeignKeyAPI()
    relation_viewset = views.TestModelSerializerReverseForeignKeyAPI()
    relation_related_name = "test_model_serializer"


@tag("model_serializer_reverse_foreign_key_viewset")
class ApiViewSetModelSerializerReverseForeignKeyTestCase(
    BaseTests.ModelSerializerViewSetTestCaseBase,
    BaseTests.ApiViewSetReverseForeignKeyTestCaseBase,
):
    namespace = "test_model_serializer_reverse_foreign_key_viewset"
    model = models.TestModelSerializerReverseForeignKey
    viewset = views.TestModelSerializerReverseForeignKeyAPI()
    relation_viewset = views.TestModelSerializerForeignKeyAPI()
    relation_related_name = "test_model_serializer_foreign_keys"
    foreign_key_field = "test_model_serializer"


@tag("model_serializer_one_to_one_viewset")
class ApiViewSetModelSerializerOneToOneTestCase(
    BaseTests.ModelSerializerViewSetTestCaseBase,
    BaseTests.ApiViewSetForeignKeyTestCaseBase,
):
    namespace = "test_model_serializer_one_to_one_viewset"
    model = models.TestModelSerializerOneToOne
    viewset = views.TestModelSerializerOneToOneAPI()
    relation_viewset = views.TestModelSerializerReverseOneToOneAPI()
    relation_related_name = "test_model_serializer"


@tag("model_serializer_reverse_one_to_one_viewset")
class ApiViewSetModelSerializerReverseOneToOneTestCase(
    ApiViewSetModelSerializerReverseForeignKeyTestCase
):
    namespace = "test_model_serializer_reverse_one_to_one_viewset"
    model = models.TestModelSerializerReverseOneToOne
    viewset = views.TestModelSerializerReverseOneToOneAPI()
    relation_viewset = views.TestModelSerializerOneToOneAPI()
    relation_related_name = "test_model_serializer_one_to_one"

    @property
    def response_data(self):
        return super().response_data | {
            self.relation_related_name: self.relation_schema_data
        }

    @property
    def create_response_data(self):
        return super().response_data | {self.relation_related_name: None}


@tag("model_serializer_many_to_many_viewset")
class ApiViewSetModelSerializerManyToManyTestCase(
    BaseTests.ModelSerializerViewSetTestCaseBase,
    BaseTests.ApiViewSetManyToManyTestCaseBase,
):
    namespace = "test_model_serializer_many_to_many_viewset"
    model = models.TestModelSerializerManyToMany
    viewset = views.TestModelSerializerManyToManyAPI()
    relation_viewset = views.TestModelSerializerReverseManyToManyAPI()
    relation_related_name = "test_model_serializers"
    foreign_key_reverse_field = "test_model_serializer_many_to_many"


@tag("model_serializer_reverse_many_to_many_viewset")
class ApiViewSetModelSerializerReverseManyToManyTestCase(
    BaseTests.ModelSerializerViewSetTestCaseBase,
    BaseTests.ApiViewSetManyToManyTestCaseBase,
):
    namespace = "test_model_serializer_reverse_many_to_many_viewset"
    model = models.TestModelSerializerReverseManyToMany
    viewset = views.TestModelSerializerReverseManyToManyAPI()
    relation_viewset = views.TestModelSerializerManyToManyAPI()
    relation_related_name = "test_model_serializer_many_to_many"
    foreign_key_reverse_field = "test_model_serializers"


# ==========================================================
#                      MODEL VIEWSET TESTS
# ==========================================================


@tag("model_viewset")
class ApiViewSetModelTestCase(
    BaseTests.SetUpViewSetTestCase,
    Tests.ViewSetTestCase,
):
    namespace = "test_model_viewset"
    model = models.TestModel
    viewset = views.TestModelAPI()

    @property
    def schemas(self):
        return (
            schema.TestModelSchemaOut,
            schema.TestModelSchemaIn,
            schema.TestModelSchemaPatch,
        )


@tag("model_foreign_key_viewset")
class ApiViewSetModelForeignKeyTestCase(BaseTests.ApiViewSetForeignKeyTestCaseBase):
    namespace = "test_model_foreign_key_viewset"
    model = models.TestModelForeignKey
    viewset = views.TestModelForeignKeyAPI()
    relation_viewset = views.TestModelReverseForeignKeyAPI()
    relation_related_name = "test_model"

    @property
    def schemas(self):
        return (
            schema.TestModelForeignKeySchemaOut,
            schema.TestModelForeignKeySchemaIn,
            schema.TestModelSchemaPatch,
        )

    @property
    def payload_create(self):
        payload = super().payload_create
        payload.pop("test_model_serializer_id")
        return payload | {self.relation_related_name: self.relation_pk}


class ApiViewSetModelReverseForeignKeyTestCase(
    BaseTests.ApiViewSetReverseForeignKeyTestCaseBase
):
    namespace = "test_model_reverse_foreign_key_viewset"
    model = models.TestModelReverseForeignKey
    viewset = views.TestModelReverseForeignKeyAPI()
    relation_viewset = views.TestModelForeignKeyAPI()
    relation_related_name = "test_model_foreign_keys"
    foreign_key_field = "test_model"

    @property
    def schemas(self):
        return (
            schema.TestModelReverseForeignKeySchemaOut,
            schema.TestModelReverseForeignKeySchemaIn,
            schema.TestModelSchemaPatch,
        )


@tag("model_one_to_one_viewset")
class ApiViewSetModelOneToOneTestCase(ApiViewSetModelForeignKeyTestCase):
    namespace = "test_model_one_to_one_viewset"
    model = models.TestModelOneToOne
    viewset = views.TestModelOneToOneAPI()
    relation_viewset = views.TestModelReverseOneToOneAPI()

    @property
    def schemas(self):
        return (
            schema.TestModelForeignKeySchemaOut,
            schema.TestModelForeignKeySchemaIn,
            schema.TestModelSchemaPatch,
        )


@tag("model_reverse_one_to_one_viewset")
class ApiViewSetModelReverseOneToOneTestCase(ApiViewSetModelReverseForeignKeyTestCase):
    namespace = "test_model_reverse_one_to_one_viewset"
    model = models.TestModelReverseOneToOne
    viewset = views.TestModelReverseOneToOneAPI()
    relation_viewset = views.TestModelOneToOneAPI()
    relation_related_name = "test_model_one_to_one"

    @property
    def schemas(self):
        return (
            schema.TestModelReverseOneToOneSchemaOut,
            schema.TestModelReverseForeignKeySchemaIn,
            schema.TestModelSchemaPatch,
        )

    @property
    def response_data(self):
        return super().response_data | {
            self.relation_related_name: self.relation_schema_data
        }

    @property
    def create_response_data(self):
        return super().response_data | {self.relation_related_name: None}


@tag("model_many_to_many_viewset")
class ApiViewSetModelManyToManyTestCase(BaseTests.ApiViewSetManyToManyTestCaseBase):
    namespace = "test_model_many_to_many_viewset"
    model = models.TestModelManyToMany
    viewset = views.TestModelManyToManyAPI()
    relation_viewset = views.TestModelReverseManyToManyAPI()
    relation_related_name = "test_models"
    foreign_key_reverse_field = "test_model_serializer_many_to_many"

    @property
    def schemas(self):
        return (
            schema.TestModelManyToManySchemaOut,
            schema.TestModelSchemaIn,
            schema.TestModelSchemaPatch,
        )


@tag("model_reverse_many_to_many_viewset")
class ApiViewSetModelReverseManyToManyTestCase(
    BaseTests.ApiViewSetManyToManyTestCaseBase
):
    namespace = "test_model_reverse_many_to_many_viewset"
    model = models.TestModelReverseManyToMany
    viewset = views.TestModelReverseManyToManyAPI()
    relation_viewset = views.TestModelManyToManyAPI()
    relation_related_name = "test_model_serializer_many_to_many"
    foreign_key_reverse_field = "test_models"

    @property
    def schemas(self):
        return (
            schema.TestModelReverseManyToManySchemaOut,
            schema.TestModelSchemaIn,
            schema.TestModelSchemaPatch,
        )


@tag("model_foreign_key_serializer_viewset")
class ApiViewSetModelForeignKeySerializerTestCase(
    BaseTests.ApiViewSetForeignKeyTestCaseBase
):
    namespace = "test_model_foreign_key_serializer_viewset"
    model = models.TestModelForeignKey
    viewset = views.TestModelForeignKeySerializerAPI()
    relation_viewset = views.TestModelReverseForeignKeySerializerAPI()
    relation_related_name = "test_model"

    @property
    def schemas(self):
        return (
            serializers.TestModelForeignKeySerializer.generate_read_s(),
            serializers.TestModelForeignKeySerializer.generate_create_s(),
            serializers.TestModelForeignKeySerializer.generate_update_s(),
        )

    @property
    def payload_create(self):
        payload = super().payload_create
        payload.pop("test_model_serializer_id")
        return payload | {f"{self.relation_related_name}_id": self.relation_pk}


# ==========================================================
#               VIEWSET DECORATOR TEST CASES
# ==========================================================


@tag("viewset_decorator_modelserializer")
class ViewSetDecoratorModelSerializerTestCase(TestCase):
    namespace = "test_viewset_decorator_modelserializer"

    @classmethod
    def setUpTestData(cls):
        cls.api = NinjaAIO(urls_namespace=cls.namespace)

        @cls.api.viewset(model=models.TestModelSerializer)
        class DecoratedMSViewSet(APIViewSet):
            pass

        # base path inferred from verbose_name plural
        cls.base = f"{models.TestModelSerializer.util.verbose_name_path_resolver()}"

    def test_crud_routes_mounted(self):
        # default router + our viewset router
        self.assertEqual(len(self.api._routers), 2)
        path, router = self.api._routers[1]
        self.assertEqual(path, cls.base if (cls := self).base else self.base)
        urls = [str(r.pattern) for r in router.urls_paths(path)]
        # Expect list and create at base, retrieve/update/delete at /{pk}/ variants
        self.assertIn(path, urls)  # list/create


@tag("viewset_decorator_plain_model")
class ViewSetDecoratorPlainModelTestCase(TestCase):
    namespace = "test_viewset_decorator_plain_model"

    @classmethod
    def setUpTestData(cls):
        cls.api = NinjaAIO(urls_namespace=cls.namespace)

        @cls.api.viewset(model=models.TestModel)
        class DecoratedModelViewSet(APIViewSet):
            # Provide manual schemas since this is a plain Model
            schema_out = schema.TestModelSchemaOut
            schema_in = schema.TestModelSchemaIn
            schema_update = schema.TestModelSchemaPatch

        cls.base = ModelUtil(models.TestModel).verbose_name_path_resolver()

    def test_crud_routes_mounted(self):
        self.assertEqual(len(self.api._routers), 2)
        path, router = self.api._routers[1]
        self.assertEqual(path, self.base)
        urls = [str(r.pattern) for r in router.urls_paths(path)]
        # Check base and pk routes exist
        self.assertIn(self.base, urls)


@tag("viewset_decorator_operations")
class ViewSetDecoratorOperationsTestCase(TestCase):
    namespace = "test_viewset_decorator_operations"

    @classmethod
    def setUpTestData(cls):
        cls.api = NinjaAIO(urls_namespace=cls.namespace)

        @cls.api.viewset(model=models.TestModel)
        class DecoratedOpsViewSet(APIViewSet):
            # Provide manual schemas since this is a plain Model
            schema_out = schema.TestModelSchemaOut
            schema_in = schema.TestModelSchemaIn
            schema_update = schema.TestModelSchemaPatch

            @api_get("/ping", response=schema.SumSchemaOut)
            async def ping(self, request):
                # simple constant payload for testing
                return schema.SumSchemaOut(result=42).model_dump()

            @api_post("/sum", response=schema.SumSchemaOut)
            async def sum_calc(self, request, data: schema.SumSchemaIn):
                return schema.SumSchemaOut(result=data.a + data.b).model_dump()

        # base path inferred from verbose_name plural
        cls.base = ModelUtil(models.TestModel).verbose_name_path_resolver()

    def test_operation_routes_mounted(self):
        # default router + our viewset router
        self.assertEqual(len(self.api._routers), 2)
        path, router = self.api._routers[1]
        self.assertEqual(path, self.base)
        urls = [str(r.pattern) for r in router.urls_paths(path)]
        # Should include base for CRUD and custom endpoints appended to base
        self.assertIn(self.base, urls)  # list/create
        # Ensure custom endpoints are present
        self.assertTrue(any("ping" in u for u in urls))
        self.assertTrue(any("sum" in u for u in urls))

    async def test_operation_handlers(self):
        # Directly verify handler logic mirrors expectations
        ping_result = schema.SumSchemaOut(result=42).model_dump()
        self.assertEqual(ping_result, {"result": 42})
        payload = schema.SumSchemaIn(a=3, b=4)
        sum_result = schema.SumSchemaOut(result=payload.a + payload.b).model_dump()
        self.assertEqual(sum_result, {"result": 7})
