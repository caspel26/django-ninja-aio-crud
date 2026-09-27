from asgiref.sync import async_to_sync
from django.db import connection
from django.test import TestCase, tag
from django.test.utils import CaptureQueriesContext

from ninja_aio import NinjaAIO
from ninja_aio.exceptions import NotFoundError
from ninja_aio.models.serializers import SchemaModelConfig, Serializer
from ninja_aio.views import APIViewSet
from tests.test_app import models


@tag("schemas")
class ForeignKeyInputSpellingTestCase(TestCase):
    """Input schemas accept a foreign key as ``name`` or ``name_id``."""

    @classmethod
    def setUpTestData(cls):
        cls.parent = models.TestModelSerializerReverseForeignKey.objects.create(name="parent", description="d")
        cls.other = models.TestModelSerializerReverseForeignKey.objects.create(name="other", description="d")
        cls.model = models.TestModelSerializerForeignKey
        cls.create_schema = cls.model.get_schema("create")
        cls.fk = "test_model_serializer"

    def _payload(self, key):
        return {"name": "child", "description": "d", key: self.parent.pk}

    def test_create_accepts_both_spellings(self):
        for key in (self.fk, f"{self.fk}_id"):
            data = self.create_schema(**self._payload(key)).model_dump()
            self.assertEqual(data[self.fk], self.parent.pk, key)

    def test_facade_create_accepts_both_spellings(self):
        first = self.model.create(self._payload(self.fk))
        second = self.model.create(self._payload(f"{self.fk}_id"))
        self.assertEqual(first.test_model_serializer_id, self.parent.pk)
        self.assertEqual(second.test_model_serializer_id, self.parent.pk)

    def test_openapi_keeps_the_original_name(self):
        schema = self.create_schema.model_json_schema()
        self.assertIn(f"{self.fk}_id", schema["properties"])
        self.assertNotIn(self.fk, schema["properties"])


@tag("schemas")
class CreateParsesInputBeforeTransactionTestCase(TestCase):
    """Invalid input fails before the create transaction opens, in both modes."""

    class HookedSerializer(Serializer):
        class Meta:
            model = models.TestModelForeignKey
            schema_in = SchemaModelConfig(fields=["name", "description", "test_model"])

        def post_create(self, instance):
            pass

        async def apost_create(self, instance):
            pass

    def _queries(self, create):
        payload = {"name": "child", "description": "d", "test_model": 999999}
        with CaptureQueriesContext(connection) as ctx, self.assertRaises(NotFoundError):
            create(payload)
        return [query["sql"] for query in ctx.captured_queries]

    def test_async_create_matches_sync_on_missing_foreign_key(self):
        sync_sql = self._queries(self.HookedSerializer.create)
        async_sql = self._queries(async_to_sync(self.HookedSerializer.acreate))
        self.assertEqual(len(async_sql), len(sync_sql))
        self.assertFalse(any("SAVEPOINT" in sql for sql in async_sql))


@tag("openapi")
class UniqueOperationIdsTestCase(TestCase):
    def test_same_viewset_mounted_twice_gets_unique_operation_ids(self):
        class Items(APIViewSet):
            model = models.TestModelSerializer

        api = NinjaAIO(urls_namespace="unique_operation_ids")
        Items(api=api, prefix="v1/items").add_views_to_route()
        Items(api=api, prefix="v2/items").add_views_to_route()
        schema = api.get_openapi_schema(path_prefix="")
        ids = [
            operation["operationId"]
            for operations in schema["paths"].values()
            for operation in operations.values()
        ]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertEqual(len(ids), 10)
