from unittest.mock import AsyncMock, patch

from django.core.exceptions import ImproperlyConfigured
from django.db import IntegrityError
from django.test import TestCase, tag
from ninja.testing import TestAsyncClient
from ninja import Schema
from pydantic import ValidationError

from ninja_aio import NinjaAIO
from ninja_aio.exceptions import NotFoundError
from ninja_aio.models import ModelUtil
from ninja_aio.views import APIViewSet
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

    def test_sync_bulk_nested_child_failure_rolls_back_only_its_parent(self):
        valid = self.payload("valid", items=[{"name": "good", "description": "d"}])
        invalid = self.payload("invalid", items=[{"name": "bad", "description": "d"}])

        def fail_bad_child(obj):
            if obj.name == "bad":
                raise ValueError("child failed")

        with patch.object(
            app_models.NestedOrderItem, "post_create", autospec=True
        ) as hook:
            hook.side_effect = fail_bad_child
            result = app_models.NestedOrder.bulk_create([valid, invalid])
        self.assertEqual([obj.name for obj in result.succeeded], ["valid"])
        self.assertEqual(result.failure_count, 1)
        self.assertEqual(
            list(app_models.NestedOrder.objects.values_list("name", flat=True)),
            ["valid"],
        )
        self.assertEqual(
            list(app_models.NestedOrderItem.objects.values_list("name", flat=True)),
            ["good"],
        )

    def test_sync_nested_child_dict_is_validated(self):
        payload = self.payload("raw")
        payload.items.append({"name": "child", "description": "d"})
        result = app_models.NestedOrder.bulk_create([payload])
        self.assertEqual(result.failed, [])
        self.assertEqual(result.success_count, 1)
        self.assertEqual(app_models.NestedOrderItem.objects.get().name, "child")

    def test_sync_cross_database_graph_is_rejected_before_writes(self):
        with patch(
            "ninja_aio.models.utils.router.db_for_write",
            side_effect=lambda model: "other"
            if model is app_models.NestedOrderItem
            else "default",
        ):
            result = app_models.NestedOrder.bulk_create([self.payload()])
        self.assertEqual(result.succeeded, [])
        self.assertIn("one database", result.failed[0].message)
        self.assertFalse(app_models.NestedOrder.objects.exists())

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
        with self.assertRaises(ValidationError):
            self.schema_in(
                name="order-3",
                description="d",
                items=[{"name": "bad", "description": "d", "quantity": "not-a-number"}],
            )
        self.assertFalse(
            await app_models.NestedOrder.objects.filter(name="order-3").aexists()
        )

    def payload(self, name="order", **kwargs):
        return self.schema_in(name=name, description="d", **kwargs)

    async def test_parsing_preserves_public_two_tuple_contract(self):
        payload, customs = await self.util.parse_input_data(
            self.request.post(), self.payload(items=[{"name": "i", "description": "d"}])
        )
        self.assertNotIn("items", payload)
        self.assertNotIn("tags", payload)
        self.assertEqual(customs, {})

    def test_nested_validators_and_model_config_are_preserved(self):
        data = self.payload(items=[{"name": " trimmed ", "description": "d"}])
        self.assertEqual(data.items[0].name, "trimmed")
        with self.assertRaises(ValidationError):
            self.payload(items=[{"name": "i", "description": "d", "quantity": 0}])
        with self.assertRaises(ValidationError):
            self.payload(items=[{"name": "i", "description": "d", "order": 999}])

    def test_nested_defaults_are_independent(self):
        first, second = self.payload("first"), self.payload("second")
        first.items.append({"name": "i"})
        self.assertEqual(second.items, [])

    def test_standalone_child_schema_retains_parent_fk(self):
        standalone = app_models.NestedOrderItem.generate_create_s()
        self.assertIn("order", standalone.model_fields)

    async def test_nested_children_run_lifecycle_hooks(self):
        with patch.object(
            app_models.NestedOrderItem, "custom_actions", new_callable=AsyncMock
        ) as custom:
            with patch.object(
                app_models.NestedOrderItem, "post_create", new_callable=AsyncMock
            ) as post:
                await self.util.create_s(
                    self.request.post(),
                    self.payload(
                        items=[
                            {"name": "i", "description": "d", "note": "custom-value"}
                        ]
                    ),
                    self.schema_out,
                )
        custom.assert_awaited_once_with({"note": "custom-value"})
        post.assert_awaited_once()
        item = await app_models.NestedOrderItem.objects.aget(name="i")
        self.assertTrue(item.hooked)

    async def test_create_grandchildren_and_resolve_other_fk(self):
        linked = await app_models.NestedLinkedObject.objects.acreate(
            name="linked", description="d"
        )
        await self.util.create_s(
            self.request.post(),
            self.payload(
                items=[
                    {
                        "name": "i",
                        "description": "d",
                        "linked_id": linked.pk,
                        "notes": [{"name": "note", "description": "d"}],
                    }
                ]
            ),
            self.schema_out,
        )
        item = await app_models.NestedOrderItem.objects.aget(name="i")
        self.assertEqual(item.linked_id, linked.pk)
        note = await app_models.NestedItemNote.objects.aget(name="note")
        self.assertEqual(note.item_id, item.pk)

    async def test_nested_fk_lookup_preserves_request_scope(self):
        linked = await app_models.NestedLinkedObject.objects.acreate(
            name="outside-scope", description="d"
        )
        scoped = AsyncMock(return_value=app_models.NestedLinkedObject.objects.none())
        with patch.object(app_models.NestedLinkedObject, "queryset_request", scoped):
            with self.assertRaises(NotFoundError):
                await self.util.create_s(
                    self.request.post(),
                    self.payload(
                        items=[
                            {"name": "i", "description": "d", "linked_id": linked.pk}
                        ]
                    ),
                    self.schema_out,
                )
        scoped.assert_awaited_once()
        self.assertFalse(await app_models.NestedOrder.objects.aexists())
        self.assertFalse(await app_models.NestedOrderItem.objects.aexists())

    async def test_cross_database_graph_is_rejected_before_writes(self):
        with patch(
            "ninja_aio.models.utils.router.db_for_write",
            side_effect=lambda model: "other"
            if model is app_models.NestedOrderItem
            else "default",
        ):
            with self.assertRaisesRegex(ImproperlyConfigured, "one database"):
                await self.util.create_s(
                    self.request.post(), self.payload(), self.schema_out
                )
        self.assertFalse(await app_models.NestedOrder.objects.aexists())

    async def test_injected_parent_fk_overrides_raw_id_alias(self):
        owner = await app_models.NestedOrder.objects.acreate(
            name="owner", description="d"
        )
        other = await app_models.NestedOrder.objects.acreate(
            name="other", description="d"
        )
        child_util = ModelUtil(app_models.NestedOrderItem)
        schema = app_models.NestedOrderItem.generate_nested_child_schema("order")
        parsed = AsyncMock(
            return_value=({"name": "i", "description": "d", "order_id": other.pk}, {})
        )
        with patch.object(child_util, "parse_input_data", parsed):
            item = await child_util._create_instance(
                self.request.post(),
                schema(name="i", description="d"),
                extra_fields={"order": owner},
            )
        self.assertEqual(item.order_id, owner.pk)

    async def test_direct_create_rolls_back_parent_and_earlier_children(self):
        with self.assertRaises(IntegrityError):
            await self.util.create_s(
                self.request.post(),
                self.payload(
                    items=[
                        {"name": "duplicate", "description": "d"},
                        {"name": "duplicate", "description": "d"},
                    ]
                ),
                self.schema_out,
            )
        self.assertFalse(await app_models.NestedOrder.objects.aexists())
        self.assertFalse(await app_models.NestedOrderItem.objects.aexists())

    async def test_child_hook_failure_rolls_back_whole_graph(self):
        with patch.object(
            app_models.NestedOrderItem,
            "post_create",
            new=AsyncMock(side_effect=RuntimeError("hook failed")),
        ):
            with self.assertRaisesRegex(RuntimeError, "hook failed"):
                await self.util.create_s(
                    self.request.post(),
                    self.payload(items=[{"name": "i", "description": "d"}]),
                    self.schema_out,
                )
        self.assertFalse(await app_models.NestedOrder.objects.aexists())
        self.assertFalse(await app_models.NestedOrderItem.objects.aexists())

    async def test_bulk_failure_rolls_back_only_failed_graph(self):
        # A failed parent's savepoint must not poison the next parent graph.
        success, errors = await self.util.bulk_create_s(
            self.request.post(),
            [
                self.payload(
                    "bad",
                    items=[
                        {"name": "duplicate", "description": "d"},
                        {"name": "duplicate", "description": "d"},
                    ],
                ),
                self.payload("good", items=[{"name": "i", "description": "d"}]),
            ],
        )
        self.assertEqual(len(success), 1)
        self.assertEqual(len(errors), 1)
        self.assertFalse(
            await app_models.NestedOrder.objects.filter(name="bad").aexists()
        )
        self.assertTrue(
            await app_models.NestedOrder.objects.filter(name="good").aexists()
        )
        self.assertEqual(await app_models.NestedOrderItem.objects.acount(), 1)

    async def test_async_bulk_facade_rolls_back_only_failed_graph(self):
        result = await app_models.NestedOrder.abulk_create(
            [
                self.payload(
                    "bad",
                    items=[
                        {"name": "duplicate", "description": "d"},
                        {"name": "duplicate", "description": "d"},
                    ],
                ),
                self.payload("good", items=[{"name": "item", "description": "d"}]),
            ]
        )
        self.assertEqual([obj.name for obj in result.succeeded], ["good"])
        self.assertEqual(result.failure_count, 1)
        self.assertEqual(
            [
                name
                async for name in app_models.NestedOrder.objects.values_list(
                    "name", flat=True
                )
            ],
            ["good"],
        )
        self.assertEqual(await app_models.NestedOrderItem.objects.acount(), 1)

    async def test_failing_nested_hook_does_not_schedule_later_hook(self):
        with patch.object(
            app_models.NestedOrderItem,
            "custom_actions",
            new=AsyncMock(side_effect=RuntimeError("custom failed")),
        ):
            with patch.object(
                app_models.NestedOrderItem, "post_create", new_callable=AsyncMock
            ) as post:
                with self.assertRaisesRegex(RuntimeError, "custom failed"):
                    await self.util.create_s(
                        self.request.post(),
                        self.payload(items=[{"name": "i", "description": "d"}]),
                        self.schema_out,
                    )
        post.assert_not_awaited()
        self.assertFalse(await app_models.NestedOrder.objects.aexists())
        self.assertFalse(await app_models.NestedOrderItem.objects.aexists())

    def test_invalid_relation_configuration_has_clear_errors(self):
        with patch.object(app_models.NestedOrder.CreateSerializer, "nested", ["items"]):
            with self.assertRaisesRegex(ImproperlyConfigured, "must be a dict"):
                app_models.NestedOrder.get_nested_fields()
        with patch.object(
            app_models.NestedOrder.CreateSerializer,
            "nested",
            {"missing": app_models.NestedOrderItem},
        ):
            with self.assertRaisesRegex(ImproperlyConfigured, "unknown relation"):
                app_models.NestedOrder.get_nested_customs()
        with patch.object(
            app_models.NestedOrder.CreateSerializer,
            "nested",
            {"name": app_models.NestedOrderItem},
        ):
            with self.assertRaisesRegex(ImproperlyConfigured, "reverse ForeignKey"):
                app_models.NestedOrder.get_nested_customs()
        with patch.object(
            app_models.NestedOrder.CreateSerializer,
            "nested",
            {"items": app_models.NestedOrderTag},
        ):
            with self.assertRaisesRegex(ImproperlyConfigured, "reverse ForeignKey"):
                app_models.NestedOrder.get_nested_customs()

    def test_distinct_query_name_does_not_replace_reverse_accessor(self):
        self.assertEqual(app_models.NestedOrder._get_nested_fk_field("items"), "order")
        with patch.object(
            app_models.NestedOrder.CreateSerializer,
            "nested",
            {"order_items": app_models.NestedOrderItem},
        ):
            with self.assertRaisesRegex(ImproperlyConfigured, "reverse ForeignKey"):
                app_models.NestedOrder.get_nested_customs()

    async def test_custom_input_schema_children_are_revalidated(self):
        class CustomOrderInput(Schema):
            name: str
            description: str
            items: list[dict]

        result = await self.util.create_s(
            self.request.post(),
            CustomOrderInput(
                name="custom",
                description="d",
                items=[{"name": " trimmed ", "description": "d"}],
            ),
            self.schema_out,
        )
        self.assertEqual(result["items"][0]["name"], "trimmed")
        with self.assertRaises(ValidationError):
            await self.util.create_s(
                self.request.post(),
                CustomOrderInput(
                    name="bad",
                    description="d",
                    items=[{"name": "i", "description": "d", "quantity": 0}],
                ),
                self.schema_out,
            )
        self.assertFalse(
            await app_models.NestedOrder.objects.filter(name="bad").aexists()
        )

    async def test_custom_child_schema_is_normalized_before_creation(self):
        class CustomChild(Schema):
            name: str
            description: str

        class CustomParent(Schema):
            name: str
            description: str
            items: list[CustomChild]

        result = await self.util.create_s(
            self.request.post(),
            CustomParent(
                name="custom",
                description="d",
                items=[CustomChild(name=" trimmed ", description="d")],
            ),
            self.schema_out,
        )
        self.assertEqual(result["items"][0]["name"], "trimmed")

    def test_cyclic_configuration_is_rejected_and_state_is_reset(self):
        with self.assertRaisesRegex(ImproperlyConfigured, "Cyclic"):
            app_models.NestedNode.generate_create_s()
        self.assertTrue(app_models.NestedOrder.get_nested_customs())

    def test_update_schema_does_not_accept_nested_collections(self):
        self.assertNotIn(
            "items", app_models.NestedOrder.generate_update_s().model_fields
        )

    async def test_http_create_validates_and_serializes_nested_children(self):
        api = NinjaAIO(urls_namespace="nested_writes_http")

        @api.viewset(app_models.NestedOrder)
        class NestedOrderViewSet(APIViewSet):
            pass

        client = TestAsyncClient(api)
        response = await client.post(
            "/nested-orders/",
            json={
                "name": "http",
                "description": "d",
                "items": [{"name": "i", "description": "d", "quantity": 2}],
            },
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["items"][0]["quantity"], 2)
        invalid = await client.post(
            "/nested-orders/",
            json={
                "name": "invalid",
                "description": "d",
                "items": [{"name": "i", "description": "d", "quantity": 0}],
            },
        )
        self.assertEqual(invalid.status_code, 422)
        self.assertFalse(
            await app_models.NestedOrder.objects.filter(name="invalid").aexists()
        )
