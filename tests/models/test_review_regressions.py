from asgiref.sync import async_to_sync
from django.test import TestCase
from pydantic import AliasChoices, AliasPath, Field

from ninja_aio import SchemaConfig, Serializer
from ninja_aio.exceptions import MultipleObjectsError
from tests.test_app import models


class ForeignKeyAliasRegressionTests(TestCase):
    def test_custom_aliases_survive_create_and_update_schema_generation(self):
        aliases = ["parent_key", AliasChoices("parent_key", "legacy_parent"), AliasPath("parent", "id")]
        for alias in aliases:
            with self.subTest(alias=alias):
                config = SchemaConfig(fields=[("test_model", int, Field(validation_alias=alias))])

                class CustomSerializer(Serializer[models.TestModelForeignKey]):
                    class Meta:
                        model = models.TestModelForeignKey

                    class Schemas:
                        create = config
                        update = config

                payloads = [{"test_model": 12}, {"test_model_id": 12}]
                if isinstance(alias, AliasPath):
                    payloads.append({"parent": {"id": 12}})
                else:
                    payloads.append({"parent_key": 12})
                    if isinstance(alias, AliasChoices):
                        payloads.append({"legacy_parent": 12})
                for schema in (CustomSerializer.create_schema, CustomSerializer.update_schema):
                    for payload in payloads:
                        self.assertEqual(schema.model_validate(payload).test_model, 12)

    def test_custom_serialization_alias_accepts_both_foreign_key_spellings(self):
        class CustomSerializer(Serializer[models.TestModelForeignKey]):
            class Meta:
                model = models.TestModelForeignKey

            class Schemas:
                create = SchemaConfig(fields=[("test_model", int, Field(alias="parent_key"))])

        for key in ("parent_key", "test_model", "test_model_id"):
            self.assertEqual(CustomSerializer.create_schema.model_validate({key: 12}).test_model, 12)
        self.assertIn("parent_key", CustomSerializer.create_schema.model_json_schema()["properties"])


class OrderedJoinLookupRegressionTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.parent = models.TestModelReverseForeignKey.objects.create(name="parent", description="d")
        for name in ("a", "b"):
            models.TestModelForeignKey.objects.create(name=name, description="child", test_model=cls.parent)

    class JoinedSerializer(Serializer[models.TestModelReverseForeignKey]):
        class Meta:
            model = models.TestModelReverseForeignKey

        class Schemas:
            read = SchemaConfig(fields=["id", "name"])

        @classmethod
        def queryset_request(cls, request):
            return cls.model.objects.filter(test_model_foreign_keys__description="child").order_by(
                "test_model_foreign_keys__name"
            )

        @classmethod
        async def aqueryset_request(cls, request):
            return cls.queryset_request(request)

    def test_ordered_join_returns_one_parent_in_both_modes(self):
        for get in (self.JoinedSerializer.get, async_to_sync(self.JoinedSerializer.aget)):
            self.assertEqual(get(self.parent.pk).pk, self.parent.pk)

    def test_ordered_join_still_rejects_two_distinct_parents(self):
        other = models.TestModelReverseForeignKey.objects.create(name="other", description="d")
        models.TestModelForeignKey.objects.create(name="c", description="child", test_model=other)
        for get in (self.JoinedSerializer.get, async_to_sync(self.JoinedSerializer.aget)):
            with self.assertRaises(MultipleObjectsError):
                get(description="d")
