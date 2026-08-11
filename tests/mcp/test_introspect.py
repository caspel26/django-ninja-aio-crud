from django.test import TestCase, tag
from ninja import Schema

from ninja_aio import NinjaAIO
from ninja_aio.decorators import action
from ninja_aio.mcp import describe_viewset
from ninja_aio.mcp import introspect
from ninja_aio.views import APIViewSet
from tests.test_app import models
from tests.test_app import views as test_views


@tag("mcp")
class DescribeViewsetCrudTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.api = NinjaAIO(urls_namespace="mcp_introspect_crud")
        cls.viewset = test_views.TestModelSerializerAPI(
            api=cls.api, prefix="mcp-test-model-serializers"
        )
        cls.viewset.add_views_to_route()
        cls.specs = describe_viewset(cls.viewset)
        cls.by_name = {s.name: s for s in cls.specs}

    def test_crud_tools_present(self):
        for op in ("create", "list", "retrieve", "update", "delete"):
            self.assertIn(f"testmodelserializer_{op}", self.by_name)

    def test_create_tool_input_schema_matches_create_serializer(self):
        spec = self.by_name["testmodelserializer_create"]
        self.assertEqual(spec.kind, "crud")
        self.assertFalse(spec.detail)
        self.assertEqual(set(spec.input_schema["properties"]), {"name", "description"})
        self.assertEqual(set(spec.input_schema["required"]), {"name", "description"})

    def test_update_tool_requires_pk_plus_update_fields(self):
        spec = self.by_name["testmodelserializer_update"]
        self.assertTrue(spec.detail)
        self.assertEqual(set(spec.input_schema["properties"]), {"pk", "description"})
        self.assertEqual(spec.input_schema["required"], ["pk"])

    def test_retrieve_and_delete_tools_only_take_pk(self):
        for name in ("testmodelserializer_retrieve", "testmodelserializer_delete"):
            spec = self.by_name[name]
            self.assertTrue(spec.detail)
            self.assertEqual(set(spec.input_schema["properties"]), {"pk"})
            self.assertEqual(spec.input_schema["required"], ["pk"])

    def test_list_tool_exposes_query_params_as_filters(self):
        spec = self.by_name["testmodelserializer_list"]
        self.assertFalse(spec.detail)
        for field in ("name", "description", "active", "age", "active_from"):
            self.assertIn(field, spec.input_schema["properties"])


@tag("mcp")
class DescribeViewsetBulkTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.api = NinjaAIO(urls_namespace="mcp_introspect_bulk")
        cls.viewset = test_views.TestModelSerializerBulkAPI(
            api=cls.api, prefix="mcp-test-model-serializers-bulk"
        )
        cls.viewset.add_views_to_route()
        cls.specs = describe_viewset(cls.viewset)
        cls.by_name = {s.name: s for s in cls.specs}

    def test_bulk_tools_present_when_configured(self):
        for op in ("bulk_create", "bulk_update", "bulk_delete"):
            self.assertIn(f"testmodelserializer_{op}", self.by_name)
            self.assertEqual(self.by_name[f"testmodelserializer_{op}"].kind, "bulk")

    def test_bulk_delete_tool_takes_ids_array(self):
        spec = self.by_name["testmodelserializer_bulk_delete"]
        self.assertEqual(spec.input_schema["properties"]["ids"]["type"], "array")


@tag("mcp")
class DescribeViewsetBulkNotConfiguredTests(TestCase):
    def test_bulk_tools_absent_when_not_configured(self):
        api = NinjaAIO(urls_namespace="mcp_introspect_no_bulk")
        viewset = test_views.TestModelSerializerAPI(
            api=api, prefix="mcp-test-model-serializers-no-bulk"
        )
        viewset.add_views_to_route()
        names = {s.name for s in describe_viewset(viewset)}
        for op in ("bulk_create", "bulk_update", "bulk_delete"):
            self.assertNotIn(f"testmodelserializer_{op}", names)


@tag("mcp")
class DescribeViewsetDisabledOperationsTests(TestCase):
    def test_disabled_operations_excluded(self):
        class ReadOnlyTestModelSerializerAPI(APIViewSet):
            model = models.TestModelSerializer
            disable = ["create", "update", "delete"]

        api = NinjaAIO(urls_namespace="mcp_introspect_disabled")
        viewset = ReadOnlyTestModelSerializerAPI(
            api=api, prefix="mcp-readonly-test-model-serializer"
        )
        viewset.add_views_to_route()
        names = {s.name for s in describe_viewset(viewset)}

        self.assertIn("testmodelserializer_list", names)
        self.assertIn("testmodelserializer_retrieve", names)
        for op in ("create", "update", "delete"):
            self.assertNotIn(f"testmodelserializer_{op}", names)


@tag("mcp")
class DescribeViewsetActionTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.api = NinjaAIO(urls_namespace="mcp_introspect_actions")
        cls.viewset = test_views.OnActionTestAPI(
            api=cls.api, prefix="mcp-on-action-test-model"
        )
        cls.viewset.add_views_to_route()
        cls.specs = describe_viewset(cls.viewset)
        cls.by_name = {s.name: s for s in cls.specs}

    def test_on_actions_exposed_as_tools(self):
        for name in ("testmodel_activate", "testmodel_rename"):
            self.assertIn(name, self.by_name)

    def test_on_action_tool_only_takes_pk(self):
        spec = self.by_name["testmodel_activate"]
        self.assertEqual(spec.kind, "action")
        self.assertTrue(spec.detail)
        self.assertEqual(set(spec.input_schema["properties"]), {"pk"})
        self.assertEqual(spec.input_schema["required"], ["pk"])


class _EchoSchema(Schema):
    message: str


@tag("mcp")
class DescribeViewsetPlainActionWithExtraParamsTests(TestCase):
    """A plain @action (not @on) forwards its extra parameters to the tool
    input schema, unlike @on-shorthand actions which only ever take `pk`.
    """

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

        cls.api = NinjaAIO(urls_namespace="mcp_introspect_action_params")
        cls.viewset = EchoActionAPI(api=cls.api, prefix="mcp-echo-action-test-model")
        cls.viewset.add_views_to_route()
        cls.by_name = {s.name: s for s in describe_viewset(cls.viewset)}

    def test_primitive_extra_param_is_required_string_field(self):
        spec = self.by_name["testmodel_echo"]
        self.assertEqual(spec.input_schema["properties"]["note"], {"type": "string"})
        self.assertEqual(spec.input_schema["required"], ["note"])
        self.assertEqual(spec.action_params["note"], {"schema": None})

    def test_schema_extra_param_is_nested_object(self):
        spec = self.by_name["testmodel_echo_schema"]
        self.assertEqual(spec.input_schema["properties"]["data"]["type"], "object")
        self.assertIn("message", spec.input_schema["properties"]["data"]["properties"])
        self.assertIs(spec.action_params["data"]["schema"], _EchoSchema)

    def test_required_schema_extra_param_is_marked_required(self):
        spec = self.by_name["testmodel_echo_schema"]
        self.assertEqual(spec.input_schema["required"], ["data"])


@tag("mcp")
class IntrospectHelperTests(TestCase):
    def test_schema_properties_returns_empty_dict_for_none(self):
        self.assertEqual(introspect._schema_properties(None), {})
