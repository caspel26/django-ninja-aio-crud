from ninja_aio.models import ModelUtil
from ninja_aio.types import ModelSerializerMeta
from ninja_aio.exceptions import SerializeError
from django.db.models import Model
from django.test import TestCase, tag
from django.test.client import AsyncRequestFactory


class Tests:
    @tag("model_util")
    class ModelUtilTestCaseBase(TestCase):
        model: Model | ModelSerializerMeta

        @classmethod
        def setUpTestData(cls):
            cls.afactory = AsyncRequestFactory()
            cls.model_util = ModelUtil(cls.model)
            cls.pk_att = cls.model._meta.pk.attname
            cls.obj = cls.model.objects.select_related().create(**cls().create_data)

        @property
        def serializable_fields(self) -> list:
            """
            Returns a list of serializable fields. Should be overridden in the subclass.
            """

        @property
        def model_verbose_name_path(self) -> str:
            """
            Returns the verbose name path of the model. Should be overridden in the subclass.
            """

        @property
        def model_verbose_name_view(self) -> str:
            """
            Returns the verbose name view of the model. Should be overridden in the subclass.
            """

        @property
        def get_request(self):
            return self.afactory.get(f"{self.model_verbose_name_path}/")

        @property
        def create_data(self) -> dict:
            """
            Should be implemented into the child class
            """

        @property
        def reverse_relations(self) -> list:
            """
            Should be implemented into the child class
            """
            return list()

        def test_serializable_fields(self):
            self.assertEqual(
                self.model_util.serializable_fields, self.serializable_fields
            )

        def test_verbose_name_path_resolver(self):
            self.assertEqual(
                self.model_util.verbose_name_path_resolver(),
                self.model_verbose_name_path,
            )

        def test_verbose_name_view_resolver(self):
            self.assertEqual(
                self.model_util.verbose_name_view_resolver(),
                self.model_verbose_name_view,
            )

        async def test_get_object_not_found(self):
            with self.assertRaises(SerializeError) as exc:
                await self.model_util.get_object(self.get_request, 0)
            self.assertEqual(
                exc.exception.error, {self.model._meta.model_name: "not found"}
            )
            self.assertEqual(exc.exception.status_code, 404)

        async def test_get_object(self):
            obj = await self.model_util.get_object(self.get_request, self.obj.pk)
            self.assertEqual(obj, self.obj)

        def test_get_reverse_relations(self):
            self.assertEqual(
                self.model_util.get_reverse_relations(), self.reverse_relations
            )
