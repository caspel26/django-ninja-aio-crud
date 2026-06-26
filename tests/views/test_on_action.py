from django.test import TestCase, tag
from ninja import Status

from ninja_aio import NinjaAIO
from ninja_aio.decorators import on
from ninja_aio.decorators.actions import ActionConfig
from ninja_aio.models import ModelUtil
from ninja_aio.views import APIViewSet
from tests.generics.request import Request
from tests.test_app import models, schema, views


@tag("on_action")
class OnActionRegistrationTestCase(TestCase):
    """Test that @on endpoints are registered correctly."""

    @classmethod
    def setUpTestData(cls):
        cls.namespace = "on_action_test"
        cls.model = models.TestModel
        cls.api = NinjaAIO(urls_namespace=cls.namespace)
        cls.viewset = views.OnActionTestAPI()
        cls.viewset.api = cls.api
        cls.viewset.add_views_to_route()
        cls.test_util = ModelUtil(cls.model)
        cls.path = cls.test_util.verbose_name_path_resolver()

    def _get_registered_paths(self):
        test_router = self.api._routers[1][1]
        return [str(route.pattern) for route in test_router.urls_paths(self.path)]

    def test_on_action_registered_with_pk_in_path(self):
        """@on detail action is registered with pk in the URL path."""
        paths = self._get_registered_paths()
        pk_name = self.model._meta.pk.attname
        self.assertIn(f"{self.path}/<{pk_name}>/activate", paths)

    def test_on_action_sets_prefetch_object(self):
        """@on sets prefetch_object=True on the ActionConfig."""
        config = views.OnActionTestAPI.activate._action_config
        self.assertIsInstance(config, ActionConfig)
        self.assertTrue(config.prefetch_object)

    def test_on_action_forces_detail_true(self):
        """@on always marks the action as detail=True."""
        config = views.OnActionTestAPI.activate._action_config
        self.assertTrue(config.detail)

    def test_on_action_default_method_is_post(self):
        """@on defaults to ['post'] HTTP method."""
        config = views.OnActionTestAPI.activate._action_config
        self.assertEqual(config.methods, ["post"])

    def test_on_action_url_path_from_action_name(self):
        """@on uses action_name as the url_path by default."""
        config = views.OnActionTestAPI.activate._action_config
        self.assertEqual(config.url_path, "activate")

    def test_on_action_custom_method(self):
        """@on respects explicit methods parameter."""
        config = views.OnActionTestAPI.rename._action_config
        self.assertEqual(config.methods, ["patch"])

    def test_multiple_on_actions_registered(self):
        """Both @on actions are registered on the router."""
        paths = self._get_registered_paths()
        pk_name = self.model._meta.pk.attname
        self.assertIn(f"{self.path}/<{pk_name}>/activate", paths)
        self.assertIn(f"{self.path}/<{pk_name}>/rename", paths)


@tag("on_action")
class OnActionExecutionTestCase(TestCase):
    """Test that @on handlers receive the pre-fetched object and run correctly."""

    @classmethod
    def setUpTestData(cls):
        cls.namespace = "on_action_exec_test"
        cls.model = models.TestModel
        cls.api = NinjaAIO(urls_namespace=cls.namespace)
        cls.viewset = views.OnActionTestAPI()
        cls.viewset.api = cls.api
        cls.viewset.add_views_to_route()
        cls.test_util = ModelUtil(cls.model)
        cls.path = cls.test_util.verbose_name_path_resolver()
        cls.request = Request(cls.path)

    async def test_on_action_receives_object(self):
        """@on user method is called with a pre-fetched model instance."""
        await self.model.objects.all().adelete()
        obj = await self.model.objects.acreate(name="original", description="desc")

        # The raw user method receives (self, request, obj) — pass the instance directly
        result = await self.viewset.activate(self.request.post(), obj)

        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.value["message"], "activated")
        self.assertEqual(result.value["name"], "original_activated")

        await obj.arefresh_from_db()
        self.assertEqual(obj.name, "original_activated")

    async def test_on_action_patch_method(self):
        """@on action with PATCH method executes correctly."""
        await self.model.objects.all().adelete()
        obj = await self.model.objects.acreate(name="base", description="desc")

        result = await self.viewset.rename(self.request.patch(), obj)

        self.assertEqual(result.status_code, 200)
        await obj.arefresh_from_db()
        self.assertEqual(obj.name, "renamed_base")

    async def test_on_handler_calls_on_before_operation(self):
        """on_before_operation is called by the built on_handler."""
        await self.model.objects.all().adelete()
        obj = await self.model.objects.acreate(name="hook_test", description="d")

        called_operations = []

        class TrackingViewSet(views.OnActionTestAPI):
            async def on_before_operation(self, request, operation):
                called_operations.append(operation)

        vs = TrackingViewSet()
        vs.api = NinjaAIO(urls_namespace="on_tracking_test")
        vs.add_views_to_route()

        # Build and call the on_handler directly to test the full hook chain
        pk_name = vs.model_util.model_pk_name
        handler = vs._build_on_handler("activate", views.OnActionTestAPI.activate)
        await handler(self.request.post(), **{pk_name: obj.pk})

        self.assertIn("activate", called_operations)

    async def test_on_handler_fetches_object_by_pk(self):
        """The on_handler fetches the model instance by pk before calling the user method."""
        await self.model.objects.all().adelete()
        obj = await self.model.objects.acreate(name="fetch_me", description="d")

        pk_name = self.viewset.model_util.model_pk_name
        handler = self.viewset._build_on_handler("activate", views.OnActionTestAPI.activate)
        result = await handler(self.request.post(), **{pk_name: obj.pk})

        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.value["name"], "fetch_me_activated")

    async def test_on_handler_not_found_raises_404(self):
        """on_handler with invalid pk raises NotFoundError."""
        from ninja_aio.exceptions import NotFoundError

        pk_name = self.viewset.model_util.model_pk_name
        handler = self.viewset._build_on_handler("activate", views.OnActionTestAPI.activate)
        with self.assertRaises(NotFoundError):
            await handler(self.request.post(), **{pk_name: 999999})


@tag("on_action")
class OnDecoratorInterfaceTestCase(TestCase):
    """Test the @on decorator API surface."""

    def test_on_returns_decorator(self):
        """@on returns a callable decorator."""
        decorator = on("test_action")
        self.assertTrue(callable(decorator))

    def test_on_marks_function_with_action_config(self):
        """@on attaches _action_config to the decorated function."""

        @on("my_action")
        async def handler(self, request, obj):
            pass

        self.assertTrue(hasattr(handler, "_action_config"))
        self.assertIsInstance(handler._action_config, ActionConfig)

    def test_on_default_detail_is_true(self):
        """@on always produces a detail=True action."""

        @on("do_thing")
        async def handler(self, request, obj):
            pass

        self.assertTrue(handler._action_config.detail)

    def test_on_default_method_is_post(self):
        """@on defaults to POST."""

        @on("do_thing")
        async def handler(self, request, obj):
            pass

        self.assertEqual(handler._action_config.methods, ["post"])

    def test_on_custom_url_path(self):
        """@on url_path override is respected."""

        @on("my_action", url_path="custom-path")
        async def handler(self, request, obj):
            pass

        self.assertEqual(handler._action_config.url_path, "custom-path")

    def test_on_action_name_used_as_url_path_by_default(self):
        """@on uses action_name as url_path when url_path not specified."""

        @on("publish")
        async def handler(self, request, obj):
            pass

        self.assertEqual(handler._action_config.url_path, "publish")

    def test_on_prefetch_object_is_true(self):
        """@on always sets prefetch_object=True."""

        @on("archive")
        async def handler(self, request, obj):
            pass

        self.assertTrue(handler._action_config.prefetch_object)

    def test_on_custom_methods(self):
        """@on respects explicit methods list."""

        @on("toggle", methods=["get", "post"])
        async def handler(self, request, obj):
            pass

        self.assertEqual(handler._action_config.methods, ["get", "post"])
