import warnings

from django.core.exceptions import ImproperlyConfigured
from django.test import SimpleTestCase, TestCase, tag

from ninja_aio import SchemaConfig
from ninja_aio.exceptions import OperationValidationError
from ninja_aio.models import ModelSerializer, serializers
from ninja_aio.models.checks import check_serializer_schemas
from tests.test_app import models


def _check_ids(serializer_class) -> list[str]:
    return sorted(e.id for e in check_serializer_schemas() if e.obj is serializer_class)


@tag("schema_config")
class ModelSerializerSchemasTests(TestCase):
    def test_generated_schemas_follow_schema_configs(self):
        parent = models.SchemasParent
        self.assertEqual(
            set(parent.create_schema.model_fields), {"name", "owner", "description", "children"}
        )
        self.assertEqual(set(parent.update_schema.model_fields), {"name", "description"})
        self.assertEqual(set(parent.read_schema.model_fields), {"id", "name", "owner", "children"})
        self.assertEqual(set(parent.detail_schema.model_fields), {"id", "name", "description", "label"})

    def test_omitted_detail_reuses_read(self):
        self.assertEqual(
            set(models.SchemasChild.detail_schema.model_fields),
            set(models.SchemasChild.read_schema.model_fields),
        )

    async def test_nested_create_model_config_and_relations_as_id(self):
        owner = await models.TestModel.objects.acreate(name="owner", description="d")
        parent = await models.SchemasParent.acreate(
            {"name": "  parent  ", "owner_id": owner.pk, "children": [{"name": "kid"}]}
        )
        self.assertEqual(parent.name, "parent")
        self.assertEqual(parent.owner_id, owner.pk)
        data = await models.SchemasParent.amodel_dump(
            parent, schema=models.SchemasParent.read_schema
        )
        self.assertEqual(data["owner"], owner.pk)
        self.assertEqual([child["name"] for child in data["children"]], ["kid"])

    async def test_validators_class_applies_to_create(self):
        with self.assertRaises(OperationValidationError):
            await models.SchemasParent.acreate({"name": "   "})


@tag("schema_config")
class SerializerSchemasTests(SimpleTestCase):
    def test_meta_serializer_uses_schemas_and_honors_excludes(self):
        class FKSerializer(serializers.Serializer):
            class Meta:
                model = models.TestModelForeignKey

            class Schemas:
                create = SchemaConfig(fields=["name", "description", "test_model"])
                update = SchemaConfig(excludes=["id", "test_model"])
                read = SchemaConfig(fields=["id", "name", "test_model"], relations_as_id=["test_model"])

        self.assertEqual(
            set(FKSerializer.create_schema.model_fields), {"name", "description", "test_model"}
        )
        self.assertEqual(set(FKSerializer.update_schema.model_fields), {"name", "description"})
        self.assertEqual(FKSerializer._schema_config("detail").relations_as_id, ["test_model"])
        self.assertEqual(_check_ids(FKSerializer), [])


@tag("schema_config")
class LegacyConfigurationTests(SimpleTestCase):
    def test_legacy_meta_schemas_warn(self):
        with self.assertWarnsRegex(DeprecationWarning, r"Meta\.schema_in is deprecated"):

            class LegacySerializer(serializers.Serializer):
                class Meta:
                    model = models.TestModelForeignKey
                    schema_in = serializers.SchemaModelConfig(fields=["name"])

    def test_legacy_inner_classes_warn(self):
        with self.assertWarnsRegex(DeprecationWarning, "ReadSerializer is deprecated"):

            class LegacyAbstract(ModelSerializer):
                class Meta:
                    abstract = True
                    app_label = "test_app"

                class ReadSerializer:
                    fields = ["id"]

    def test_schemas_without_legacy_do_not_warn(self):
        with warnings.catch_warnings():
            warnings.simplefilter("error", DeprecationWarning)

            class ModernSerializer(serializers.Serializer):
                class Meta:
                    model = models.TestModelForeignKey

                class Schemas:
                    read = SchemaConfig(fields=["id"])

    def test_mixing_schemas_and_legacy_is_rejected(self):
        with self.assertRaisesRegex(ImproperlyConfigured, "both Schemas and legacy"):

            class MixedSerializer(serializers.Serializer):
                class Meta:
                    model = models.TestModelForeignKey
                    schema_out = serializers.SchemaModelConfig(fields=["id"])

                class Schemas:
                    read = SchemaConfig(fields=["id"])


@tag("schema_config")
class SchemasSystemCheckTests(SimpleTestCase):
    def test_unknown_kind_and_non_schema_config_value(self):
        class BadKinds(serializers.Serializer):
            class Meta:
                model = models.TestModelForeignKey

            class Schemas:
                craete = SchemaConfig(fields=["name"])
                read = ["id"]

        self.assertEqual(_check_ids(BadKinds), ["ninja_aio.E001", "ninja_aio.E002"])

    def test_field_and_option_errors(self):
        class BadFields(serializers.Serializer):
            class Meta:
                model = models.TestModelForeignKey

            class Schemas:
                create = SchemaConfig(
                    fields=["name", "nope", ("computed", str)],
                    optionals=[("name", str)],
                    relations_as_id=["test_model"],
                    nested={"missing": object},
                )
                read = SchemaConfig(fields=["id"], relations_as_id=["name"])

        self.assertEqual(
            _check_ids(BadFields),
            [
                "ninja_aio.E003",
                "ninja_aio.E003",
                "ninja_aio.E004",
                "ninja_aio.E005",
                "ninja_aio.E005",
                "ninja_aio.E006",
            ],
        )

    def test_reverse_accessor_is_a_valid_relation(self):
        self.assertEqual(_check_ids(models.SchemasParent), [])

    def test_app_configs_filter(self):
        class Filtered(serializers.Serializer):
            class Meta:
                model = models.TestModelForeignKey

            class Schemas:
                craete = SchemaConfig()

        self.assertEqual(
            [e for e in check_serializer_schemas(app_configs=[]) if e.obj is Filtered], []
        )
