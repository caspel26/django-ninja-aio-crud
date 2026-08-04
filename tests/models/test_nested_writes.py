from django.test import TestCase, tag

from ninja_aio.models import ModelUtil
from tests.generics.request import Request
from tests.test_app import models as app_models


@tag("nested_writes", "model_util")
class NestedWritesTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.request = Request("nested-orders/")
        cls.util = ModelUtil(app_models.NestedOrder)
        cls.schema_in = app_models.NestedOrder.generate_create_s()
        cls.schema_out = app_models.NestedOrder.generate_read_s()

    async def test_create_with_nested_children(self):
        data = self.schema_in(
            name="order-1",
            description="d",
            items=[
                {"name": "item-1", "description": "d1", "quantity": 2},
                {"name": "item-2", "description": "d2", "quantity": 5},
            ],
        )
        result = await self.util.create_s(self.request.post(), data, self.schema_out)

        order = await app_models.NestedOrder.objects.aget(pk=result["id"])
        items = [item async for item in order.items.all()]
        self.assertEqual(len(items), 2)
        self.assertEqual({i.name for i in items}, {"item-1", "item-2"})
        self.assertEqual({i.quantity for i in items}, {2, 5})
        self.assertTrue(all(i.order_id == order.pk for i in items))

    async def test_create_without_nested_children_defaults_to_empty(self):
        data = self.schema_in(name="order-2", description="d")
        result = await self.util.create_s(self.request.post(), data, self.schema_out)

        order = await app_models.NestedOrder.objects.aget(pk=result["id"])
        self.assertEqual(await order.items.acount(), 0)

    async def test_nested_child_schema_excludes_injected_fk(self):
        # "order" must not be a required/accepted field on the nested child
        # schema -- it is injected by the parent, not supplied by the client.
        fields = self.schema_in.model_fields["items"].annotation
        child_schema = fields.__args__[0]
        self.assertNotIn("order", child_schema.model_fields)

    async def test_nested_child_without_explicit_fields_still_excludes_fk(self):
        # NestedOrderTag declares no CreateSerializer.fields at all -- the
        # fallback branch must still exclude the injected FK by adding it to
        # the generated exclude list rather than requiring it.
        fields = self.schema_in.model_fields["tags"].annotation
        child_schema = fields.__args__[0]
        self.assertNotIn("order", child_schema.model_fields)

    async def test_create_with_multiple_nested_relations(self):
        data = self.schema_in(
            name="order-4",
            description="d",
            items=[{"name": "item-1", "description": "d1", "quantity": 1}],
            tags=[{"name": "tag-1", "description": "t1"}],
        )
        result = await self.util.create_s(self.request.post(), data, self.schema_out)

        order = await app_models.NestedOrder.objects.aget(pk=result["id"])
        self.assertEqual(await order.items.acount(), 1)
        self.assertEqual(await order.tags.acount(), 1)

    async def test_nested_child_invalid_payload_rejected_before_persisting(self):
        # An invalid child value (non-numeric quantity) fails pydantic
        # validation on the parent's "In" schema itself -- nothing is
        # persisted since the parent object is never even constructed.
        with self.assertRaises(Exception):
            self.schema_in(
                name="order-3",
                description="d",
                items=[
                    {"name": "bad", "description": "d", "quantity": "not-a-number"}
                ],
            )
        self.assertFalse(
            await app_models.NestedOrder.objects.filter(name="order-3").aexists()
        )
