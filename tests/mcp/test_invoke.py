import dataclasses

from django.test import TestCase, tag
from ninja import Schema

from ninja_aio import NinjaAIO
from ninja_aio.decorators import action
from ninja_aio.mcp import ToolInvocationError, describe_viewset, invoke_tool
from ninja_aio.mcp.invoke import _invoke_bulk, _invoke_crud
from ninja_aio.views import APIViewSet
from tests.test_app import models
from tests.test_app import views as test_views


@tag("mcp")
class InvokeCrudTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.api = NinjaAIO(urls_namespace="mcp_invoke_crud")
        cls.viewset = test_views.TestModelSerializerAPI(
            api=cls.api, prefix="mcp-invoke-test-model-serializers"
        )
        cls.viewset.add_views_to_route()
        cls.by_name = {s.name: s for s in describe_viewset(cls.viewset)}

    async def test_create_then_retrieve(self):
        create_spec = self.by_name["testmodelserializer_create"]
        created = await invoke_tool(
            create_spec, {"name": "mcp-name", "description": "mcp-description"}
        )
        self.assertEqual(created["name"], "mcp-name")
        pk = created["id"]

        retrieve_spec = self.by_name["testmodelserializer_retrieve"]
        fetched = await invoke_tool(retrieve_spec, {"pk": pk})
        self.assertEqual(fetched["id"], pk)
        self.assertEqual(fetched["name"], "mcp-name")

    async def test_list_returns_created_objects(self):
        create_spec = self.by_name["testmodelserializer_create"]
        await invoke_tool(create_spec, {"name": "listed", "description": "d"})

        list_spec = self.by_name["testmodelserializer_list"]
        result = await invoke_tool(list_spec, {"name": "listed"})
        self.assertGreaterEqual(result["count"], 1)
        self.assertTrue(all(item["name"] == "listed" for item in result["items"]))

    async def test_update_changes_object(self):
        create_spec = self.by_name["testmodelserializer_create"]
        created = await invoke_tool(
            create_spec, {"name": "to-update", "description": "old"}
        )
        pk = created["id"]

        update_spec = self.by_name["testmodelserializer_update"]
        updated = await invoke_tool(update_spec, {"pk": pk, "description": "new"})
        self.assertEqual(updated["description"], "new")

    async def test_delete_removes_object(self):
        create_spec = self.by_name["testmodelserializer_create"]
        created = await invoke_tool(
            create_spec, {"name": "to-delete", "description": "d"}
        )
        pk = created["id"]

        delete_spec = self.by_name["testmodelserializer_delete"]
        await invoke_tool(delete_spec, {"pk": pk})

        self.assertFalse(
            await models.TestModelSerializer.objects.filter(pk=pk).aexists()
        )

    async def test_retrieve_missing_pk_raises_tool_invocation_error(self):
        retrieve_spec = self.by_name["testmodelserializer_retrieve"]
        with self.assertRaises(ToolInvocationError) as ctx:
            await invoke_tool(retrieve_spec, {"pk": 999999})
        self.assertEqual(ctx.exception.status_code, 404)

    async def test_create_missing_required_field_raises_tool_invocation_error(self):
        create_spec = self.by_name["testmodelserializer_create"]
        with self.assertRaises(ToolInvocationError) as ctx:
            await invoke_tool(create_spec, {"name": "no-description"})
        self.assertEqual(ctx.exception.status_code, 400)
        self.assertEqual(ctx.exception.payload["error"], "Validation Error")
        self.assertIn(str(ctx.exception.payload), str(ctx.exception))

    async def test_unregistered_crud_operation_raises_key_error(self):
        spec = self.by_name["testmodelserializer_create"]
        bogus_spec = dataclasses.replace(spec, operation="bogus")
        with self.assertRaises(KeyError):
            await _invoke_crud(bogus_spec, None, {})


@tag("mcp")
class InvokeBulkTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.api = NinjaAIO(urls_namespace="mcp_invoke_bulk")
        cls.viewset = test_views.TestModelSerializerBulkAPI(
            api=cls.api, prefix="mcp-invoke-test-model-serializers-bulk"
        )
        cls.viewset.add_views_to_route()
        cls.by_name = {s.name: s for s in describe_viewset(cls.viewset)}

    async def test_bulk_create(self):
        spec = self.by_name["testmodelserializer_bulk_create"]
        result = await invoke_tool(
            spec,
            {
                "items": [
                    {"name": "bulk-1", "description": "d1"},
                    {"name": "bulk-2", "description": "d2"},
                ]
            },
        )
        self.assertEqual(result["success"]["count"], 2)

    async def test_bulk_delete(self):
        obj1 = await models.TestModelSerializer.objects.acreate(
            name="del-1", description="d"
        )
        obj2 = await models.TestModelSerializer.objects.acreate(
            name="del-2", description="d"
        )
        spec = self.by_name["testmodelserializer_bulk_delete"]
        result = await invoke_tool(spec, {"ids": [obj1.pk, obj2.pk]})
        self.assertEqual(result["success"]["count"], 2)

    async def test_bulk_update(self):
        obj = await models.TestModelSerializer.objects.acreate(
            name="bulk-upd", description="old"
        )
        spec = self.by_name["testmodelserializer_bulk_update"]
        result = await invoke_tool(
            spec, {"items": [{"id": obj.pk, "description": "new"}]}
        )
        self.assertEqual(result["success"]["count"], 1)
        await obj.arefresh_from_db()
        self.assertEqual(obj.description, "new")

    async def test_unregistered_bulk_operation_raises_key_error(self):
        spec = self.by_name["testmodelserializer_bulk_create"]
        bogus_spec = dataclasses.replace(spec, operation="bogus")
        with self.assertRaises(KeyError):
            await _invoke_bulk(bogus_spec, None, {})


@tag("mcp")
class InvokeActionTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.api = NinjaAIO(urls_namespace="mcp_invoke_actions")
        cls.viewset = test_views.OnActionTestAPI(
            api=cls.api, prefix="mcp-invoke-on-action-test-model"
        )
        cls.viewset.add_views_to_route()
        cls.by_name = {s.name: s for s in describe_viewset(cls.viewset)}

    async def test_on_action_invocation(self):
        obj = await models.TestModel.objects.acreate(name="obj", description="d")
        spec = self.by_name["testmodel_activate"]
        result = await invoke_tool(spec, {"pk": obj.pk})
        self.assertEqual(result["message"], "activated")
        self.assertEqual(result["name"], "obj_activated")


class _EchoSchema(Schema):
    message: str


@tag("mcp")
class InvokePlainActionWithExtraParamsTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        class EchoActionAPI(APIViewSet):
            model = models.TestModel

            @action(detail=False, methods=["post"])
            async def echo(self, request, note: str):
                return {"note": note}

            @action(detail=False, methods=["post"])
            async def echo_schema(self, request, data: _EchoSchema):
                return {"message": data.message}

            @action(detail=False, methods=["post"])
            async def echo_optional(self, request, note: str = "default"):
                return {"note": note}

        cls.api = NinjaAIO(urls_namespace="mcp_invoke_action_params")
        cls.viewset = EchoActionAPI(api=cls.api, prefix="mcp-invoke-echo-action-test-model")
        cls.viewset.add_views_to_route()
        cls.by_name = {s.name: s for s in describe_viewset(cls.viewset)}

    async def test_action_with_primitive_extra_param(self):
        spec = self.by_name["testmodel_echo"]
        result = await invoke_tool(spec, {"note": "hi"})
        self.assertEqual(result["note"], "hi")

    async def test_action_with_omitted_optional_extra_param_uses_default(self):
        spec = self.by_name["testmodel_echo_optional"]
        result = await invoke_tool(spec, {})
        self.assertEqual(result["note"], "default")

    async def test_action_with_schema_extra_param(self):
        spec = self.by_name["testmodel_echo_schema"]
        result = await invoke_tool(spec, {"data": {"message": "hello"}})
        self.assertEqual(result["message"], "hello")
