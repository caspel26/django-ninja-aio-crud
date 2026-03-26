from django.test import TestCase, tag
from ninja import Schema, Status

from ninja_aio import NinjaAIO
from ninja_aio.decorators import action, aatomic
from ninja_aio.models import ModelUtil
from ninja_aio.views import APIViewSet
from tests.generics.request import Request
from tests.test_app import models, schema


class CountSchema(Schema):
    count: int


class MessageSchema(Schema):
    message: str


class ActionTestViewSet(APIViewSet):
    model = models.TestModel
    schema_in = schema.TestModelSchemaIn
    schema_out = schema.TestModelSchemaOut
    schema_update = schema.TestModelSchemaPatch

    @action(detail=True, methods=["post"], url_path="activate")
    async def activate(self, request, pk):
        obj = await self.model_util.get_object(request, pk)
        obj.name = f"{obj.name}_activated"
        await obj.asave()
        return Status(200, {"message": "activated"})

    @action(detail=False, methods=["get"], url_path="count", response=CountSchema)
    async def count(self, request):
        total = await self.model.objects.acount()
        return {"count": total}

    @action(detail=True, methods=["get", "post"], url_path="multi")
    async def multi_method(self, request, pk):
        return {"message": "ok"}

    @action(detail=False, methods=["get"], url_path="custom-path")
    async def my_custom_endpoint(self, request):
        return {"message": "custom"}

    @action(
        detail=False,
        methods=["get"],
        url_path="documented",
        summary="My Custom Summary",
        description="My custom description",
    )
    async def documented_action(self, request):
        return {"message": "documented"}

    @action(detail=False, methods=["post"], url_path="with-body")
    async def with_body(self, request, data: schema.TestModelSchemaIn):
        return Status(200, {"message": f"received {data.name}"})

    @action(
        detail=False,
        methods=["post"],
        url_path="with-decorators",
        decorators=[aatomic],
    )
    async def with_decorators(self, request):
        return {"message": "decorated"}

    @action(detail=False, methods=["get"])
    async def auto_path(self, request):
        return {"message": "auto"}


@tag("actions")
class ActionRegistrationTestCase(TestCase):
    """Test that @action endpoints are registered correctly."""

    @classmethod
    def setUpTestData(cls):
        cls.namespace = "action_test"
        cls.model = models.TestModel
        cls.api = NinjaAIO(urls_namespace=cls.namespace)
        cls.viewset = ActionTestViewSet()
        cls.viewset.api = cls.api
        cls.viewset.add_views_to_route()
        cls.test_util = ModelUtil(cls.model)
        cls.path = cls.test_util.verbose_name_path_resolver()

    def _get_registered_paths(self):
        test_router = self.api._routers[1][1]
        return [str(route.pattern) for route in test_router.urls_paths(self.path)]

    def test_detail_action_registered(self):
        """Detail action registers with pk in path."""
        paths = self._get_registered_paths()
        pk_name = self.model._meta.pk.attname
        expected = f"{self.path}/<{pk_name}>/activate"
        self.assertIn(expected, paths)

    def test_list_action_registered(self):
        """List action registers without pk in path."""
        paths = self._get_registered_paths()
        expected = f"{self.path}/count"
        self.assertIn(expected, paths)

    def test_multiple_methods_registered(self):
        """Multiple methods register separate routes."""
        paths = self._get_registered_paths()
        pk_name = self.model._meta.pk.attname
        expected = f"{self.path}/<{pk_name}>/multi"
        count = paths.count(expected)
        self.assertEqual(count, 2, f"Expected 2 routes for multi, got {count}")

    def test_custom_url_path(self):
        """Custom url_path is used instead of method name."""
        paths = self._get_registered_paths()
        expected = f"{self.path}/custom-path"
        self.assertIn(expected, paths)

    def test_auto_url_path(self):
        """Default url_path uses method name with hyphens."""
        paths = self._get_registered_paths()
        expected = f"{self.path}/auto-path"
        self.assertIn(expected, paths)


@tag("actions")
class ActionExecutionTestCase(TestCase):
    """Test that @action endpoints execute correctly."""

    @classmethod
    def setUpTestData(cls):
        cls.namespace = "action_exec_test"
        cls.model = models.TestModel
        cls.api = NinjaAIO(urls_namespace=cls.namespace)
        cls.viewset = ActionTestViewSet()
        cls.viewset.api = cls.api
        cls.viewset.add_views_to_route()
        cls.test_util = ModelUtil(cls.model)
        cls.path = cls.test_util.verbose_name_path_resolver()
        cls.request = Request(cls.path)

    @property
    def get_request(self):
        return self.request.get()

    @property
    def post_request(self):
        return self.request.post()

    async def test_detail_action_executes(self):
        """Detail action receives pk and operates on the object."""
        await self.model.objects.all().adelete()
        obj = await self.model.objects.acreate(name="test", description="desc")

        result = await self.viewset.activate(self.post_request, obj.pk)

        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.value["message"], "activated")

        await obj.arefresh_from_db()
        self.assertEqual(obj.name, "test_activated")

    async def test_list_action_executes(self):
        """List action operates on the collection."""
        await self.model.objects.all().adelete()
        await self.model.objects.acreate(name="a", description="d")
        await self.model.objects.acreate(name="b", description="d")

        result = await self.viewset.count(self.get_request)

        self.assertEqual(result["count"], 2)

    async def test_action_with_request_body(self):
        """Action with request body schema receives data."""
        data = schema.TestModelSchemaIn(name="hello", description="world")

        result = await self.viewset.with_body(self.post_request, data)

        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.value["message"], "received hello")

    async def test_action_with_decorators(self):
        """Action with extra decorators works correctly."""
        result = await self.viewset.with_decorators(self.post_request)

        self.assertEqual(result["message"], "decorated")


@tag("actions")
class ActionDisableTestCase(TestCase):
    """Test that @action is NOT affected by disable=['all']."""

    @classmethod
    def setUpTestData(cls):
        cls.namespace = "action_disable_test"
        cls.model = models.TestModel
        cls.api = NinjaAIO(urls_namespace=cls.namespace)

        class DisabledCrudWithAction(APIViewSet):
            model = models.TestModel
            schema_in = schema.TestModelSchemaIn
            schema_out = schema.TestModelSchemaOut
            schema_update = schema.TestModelSchemaPatch
            disable = ["all"]

            @action(detail=False, methods=["get"], url_path="custom")
            async def custom(self, request):
                return {"message": "still here"}

        cls.viewset = DisabledCrudWithAction()
        cls.viewset.api = cls.api
        cls.viewset.add_views_to_route()
        cls.test_util = ModelUtil(cls.model)
        cls.path = cls.test_util.verbose_name_path_resolver()

    def test_action_survives_disable_all(self):
        """Actions are still registered when CRUD is disabled."""
        test_router = self.api._routers[1][1]
        paths = [str(route.pattern) for route in test_router.urls_paths(self.path)]
        expected = f"{self.path}/custom"
        self.assertIn(expected, paths)

    def test_crud_disabled(self):
        """CRUD endpoints are not registered."""
        test_router = self.api._routers[1][1]
        paths = [str(route.pattern) for route in test_router.urls_paths(self.path)]
        # list view path (empty suffix)
        self.assertNotIn(f"{self.path}/", paths)


@tag("actions")
class ActionAuthTestCase(TestCase):
    """Test auth inheritance and override for @action."""

    @classmethod
    def setUpTestData(cls):
        cls.namespace = "action_auth_test"
        cls.api = NinjaAIO(urls_namespace=cls.namespace)

        def mock_auth(request):
            return True

        class AuthViewSet(APIViewSet):
            model = models.TestModel
            schema_in = schema.TestModelSchemaIn
            schema_out = schema.TestModelSchemaOut
            schema_update = schema.TestModelSchemaPatch
            auth = [mock_auth]

            @action(detail=False, methods=["get"], url_path="inherit-auth")
            async def inherit_auth(self, request):
                return {"message": "inherited"}

            @action(detail=False, methods=["get"], url_path="no-auth", auth=None)
            async def no_auth(self, request):
                return {"message": "public"}

        cls.viewset = AuthViewSet()
        cls.viewset.api = cls.api
        cls.viewset.add_views_to_route()

    def test_action_inherits_auth(self):
        """Action with NOT_SET auth inherits from viewset."""
        inherit_config = self.viewset.inherit_auth._action_config
        # auth=NOT_SET means it should use viewset auth during registration
        from ninja.constants import NOT_SET

        self.assertIs(inherit_config.auth, NOT_SET)

    def test_action_override_auth(self):
        """Action with explicit auth uses the override."""
        no_auth_config = self.viewset.no_auth._action_config
        self.assertIsNone(no_auth_config.auth)


# ---------------------------------------------------------------------------
# @on decorator tests
# ---------------------------------------------------------------------------


from ninja_aio.decorators import on


class OnDecoratorViewSet(APIViewSet):
    model = models.TestModel
    schema_in = schema.TestModelSchemaIn
    schema_out = schema.TestModelSchemaOut
    schema_update = schema.TestModelSchemaPatch

    @on("publish")
    async def publish(self, request, obj):
        obj.name = f"{obj.name}_published"
        await obj.asave()
        return Status(200, {"message": "published", "name": obj.name})

    @on("archive", methods=["patch"], url_path="archive-item")
    async def archive(self, request, obj):
        return Status(200, {"message": "archived"})


_hook_log = []


class OnHookTrackingViewSet(APIViewSet):
    model = models.TestModel
    schema_in = schema.TestModelSchemaIn
    schema_out = schema.TestModelSchemaOut
    schema_update = schema.TestModelSchemaPatch

    @on("do_action")
    async def do_action(self, request, obj):
        return Status(200, {"pk": obj.pk})

    async def on_before_operation(self, request, operation):
        _hook_log.append(("before_op", operation))

    async def on_before_object_operation(self, request, operation, obj):
        _hook_log.append(("before_obj_op", operation, obj.pk))


@tag("on_decorator")
class OnDecoratorRegistrationTestCase(TestCase):
    """Test @on decorator endpoint registration."""

    @classmethod
    def setUpTestData(cls):
        cls.api = NinjaAIO(urls_namespace="on_reg_test")
        cls.viewset = OnDecoratorViewSet()
        cls.viewset.api = cls.api
        cls.viewset.add_views_to_route()

    def test_on_registers_post_by_default(self):
        """@on registers POST method by default."""
        config = self.viewset.publish._action_config
        self.assertEqual(config.methods, ["post"])
        self.assertTrue(config.detail)

    def test_on_custom_method_and_url(self):
        """@on supports custom methods and url_path."""
        config = self.viewset.archive._action_config
        self.assertEqual(config.methods, ["patch"])
        self.assertEqual(config.url_path, "archive-item")

    def test_on_has_on_config_marker(self):
        """@on-decorated method has _on_config attribute."""
        self.assertTrue(hasattr(self.viewset.publish, "_on_config"))
        self.assertEqual(self.viewset.publish._on_config.action_name, "publish")


@tag("on_decorator")
class OnDecoratorExecutionTestCase(TestCase):
    """Test @on decorator execution — object fetching and mutation."""

    @classmethod
    def setUpTestData(cls):
        cls.api = NinjaAIO(urls_namespace="on_exec_test")
        cls.viewset = OnDecoratorViewSet()
        cls.viewset.api = cls.api
        cls.viewset.add_views_to_route()
        cls.model = models.TestModel
        cls.test_util = ModelUtil(cls.model)
        cls.request = Request(cls.test_util.verbose_name_path_resolver())

    async def test_on_handler_receives_object(self):
        """@on handler receives the fetched model instance, not pk."""
        await self.model.objects.all().adelete()
        obj = await self.model.objects.acreate(name="test_on", description="d")

        ops = self.viewset.router.path_operations
        publish_path = f"{{{self.test_util.model_pk_name}}}/publish"
        publish_op = ops.get(publish_path)
        self.assertIsNotNone(publish_op, f"Publish endpoint not found at {publish_path}")
        publish_view = publish_op.operations[0].view_func

        pk_schema = self.viewset.path_schema(id=obj.pk)
        result = await publish_view(self.request.post(), pk_schema)

        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.value["name"], "test_on_published")

        await obj.arefresh_from_db()
        self.assertEqual(obj.name, "test_on_published")


@tag("on_decorator")
class OnDecoratorHooksTestCase(TestCase):
    """Test @on decorator fires both operation hooks."""

    @classmethod
    def setUpTestData(cls):
        cls.api = NinjaAIO(urls_namespace="on_hooks_test")
        cls.viewset = OnHookTrackingViewSet()
        cls.viewset.api = cls.api
        cls.viewset.add_views_to_route()
        cls.model = models.TestModel
        cls.test_util = ModelUtil(cls.model)
        cls.request = Request(cls.test_util.verbose_name_path_resolver())

    def setUp(self):
        _hook_log.clear()

    async def test_on_fires_both_hooks(self):
        """@on fires on_before_operation AND on_before_object_operation."""
        await self.model.objects.all().adelete()
        obj = await self.model.objects.acreate(name="hooks_test", description="d")

        ops = self.viewset.router.path_operations
        action_path = f"{{{self.test_util.model_pk_name}}}/do-action"
        action_op = ops.get(action_path)
        self.assertIsNotNone(action_op)
        action_view = action_op.operations[0].view_func

        pk_schema = self.viewset.path_schema(id=obj.pk)
        result = await action_view(self.request.post(), pk_schema)

        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.value["pk"], obj.pk)

        events = [c[0] for c in _hook_log]
        self.assertIn("before_op", events)
        self.assertIn("before_obj_op", events)

        op_call = [c for c in _hook_log if c[0] == "before_op"][0]
        self.assertEqual(op_call[1], "do_action")

        obj_call = [c for c in _hook_log if c[0] == "before_obj_op"][0]
        self.assertEqual(obj_call[1], "do_action")
        self.assertEqual(obj_call[2], obj.pk)
