from django.test import SimpleTestCase
from ninja import Schema

from ninja_aio.exceptions import SerializeError
from ninja_aio.models import transformations as model_transformations
from ninja_aio.schemas.helpers import ObjectQuerySchema
from tests.generics.request import Request
from tests.test_app.models import (
    TestModel,
    TestModelForeignKey,
    TestModelManyToMany,
    TestModelReverseForeignKey,
)


class _InputSchema(Schema):
    name: str
    nested: list[dict[str, str]] = []


class _OutputSchema(Schema):
    name: str


class _FieldPolicy:
    def is_custom(self, name: str) -> bool:
        return name == "custom"

    def is_optional(self, name: str) -> bool:
        return name == "optional"


class TransformationRuleTests(SimpleTestCase):
    def test_schema_payload_and_input_plan_are_database_independent(self) -> None:
        payload = model_transformations.schema_to_payload(
            _InputSchema(name="book", nested=[{"name": "chapter"}]),
            nested_fields=("nested",),
        )
        payload.update(custom="value", optional=None)

        plan = model_transformations.plan_input_payload(
            payload,
            model_fields=("name", "optional"),
            field_policy=_FieldPolicy(),
        )

        self.assertEqual(plan.customs, {"custom": "value"})
        self.assertEqual(plan.optionals, ("optional",))
        self.assertEqual(plan.fields_to_process, [("name", "book")])
        # Preserve the v2 rule: when customs exist, optional model values remain.
        self.assertEqual(plan.model_payload(), {"name": "book", "optional": None})

    def test_plain_payload_plan_preserves_every_field(self) -> None:
        payload = {"name": "book", "optional": None}

        plan = model_transformations.plan_input_payload(
            payload,
            model_fields=("name", "optional"),
            field_policy=None,
        )

        self.assertEqual(plan.model_payload(), payload)
        self.assertEqual(plan.fields_to_process, list(payload.items()))

    def test_serializer_payload_preserves_dict_and_dumps_schema(self) -> None:
        payload = {"name": "book"}

        self.assertIs(model_transformations.serializer_payload(payload), payload)
        self.assertEqual(
            model_transformations.serializer_payload(_InputSchema(name="book"))["name"],
            "book",
        )

    def test_lookup_and_read_validation_do_not_execute_queries(self) -> None:
        request = Request("transformations").get()

        self.assertEqual(
            model_transformations.build_lookup_query("id", 1, {"name": "book"}),
            {"id": 1, "name": "book"},
        )
        model_transformations.validate_read_params(
            request, ObjectQuerySchema(getters={"id": 1})
        )

        with self.assertRaises(SerializeError):
            model_transformations.validate_read_params(
                None, ObjectQuerySchema(getters={"id": 1})
            )

    def test_binary_decoding_preserves_error_contract(self) -> None:
        self.assertEqual(
            model_transformations.decode_binary_value("content", "aGVsbG8="),
            b"hello",
        )

        with self.assertRaises(SerializeError) as error:
            model_transformations.decode_binary_value("content", object())
        self.assertIn("content", error.exception.error)

    def test_model_field_inspection_is_database_independent(self) -> None:
        fields = model_transformations.resolve_model_fields(
            TestModelForeignKey, ("name", "test_model")
        )

        self.assertEqual([field.name for field in fields], ["name", "test_model"])

    def test_relation_discovery_covers_forward_and_reverse_descriptors(self) -> None:
        forward = model_transformations.discover_relation_plan(
            TestModelForeignKey, ("test_model",)
        )
        reverse = model_transformations.discover_relation_plan(
            TestModelReverseForeignKey, ("test_model_foreign_keys",)
        )
        many = model_transformations.discover_relation_plan(
            TestModelManyToMany, ("test_models",)
        )

        self.assertEqual(forward.select_related, ("test_model",))
        self.assertEqual(reverse.prefetch_related, ("test_model_foreign_keys",))
        self.assertEqual(many.prefetch_related, ("test_models",))

    def test_configured_relation_kinds_override_discovery_independently(self) -> None:
        plan = model_transformations.discover_relation_plan(
            TestModelForeignKey,
            ("test_model",),
            configured_select=("configured_fk",),
        )

        self.assertEqual(plan.select_related, ("configured_fk",))
        self.assertEqual(plan.prefetch_related, ())

    def test_schema_relation_plan_skips_non_model_fields(self) -> None:
        class _RelatedOutput(Schema):
            name: str
            test_model: dict
            computed: str

        plan = model_transformations.schema_relation_plan(
            TestModelForeignKey, _RelatedOutput
        )

        self.assertEqual(plan.select_related, ("test_model",))
        self.assertEqual(plan.prefetch_related, ())

    def test_relation_plans_compose_without_evaluating_queryset(self) -> None:
        plan = model_transformations.combine_relation_plans(
            model_transformations.RelationPlan(select_related=("test_model",)),
            model_transformations.RelationPlan(
                prefetch_related=("test_model__test_model_foreign_keys",)
            ),
        )
        queryset = model_transformations.apply_relation_plan(
            TestModelForeignKey.objects.all(), plan
        )

        self.assertEqual(queryset.query.select_related, {"test_model": {}})
        self.assertEqual(
            queryset._prefetch_related_lookups,
            ("test_model__test_model_foreign_keys",),
        )

    def test_output_transformations_work_on_loaded_instances(self) -> None:
        first = TestModel(name="first", description="one")
        second = TestModel(name="second", description="two")

        self.assertEqual(
            model_transformations.dump_model(first, _OutputSchema), {"name": "first"}
        )
        self.assertEqual(
            model_transformations.dump_models((first, second), _OutputSchema),
            [{"name": "first"}, {"name": "second"}],
        )
