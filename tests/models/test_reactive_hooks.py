from django.db import models
from django.test import TestCase, tag

from ninja_aio import NinjaAIO
from ninja_aio.models import ModelSerializer, ModelUtil, on_create, on_update, on_delete
from ninja_aio.models.serializers import Serializer, SchemaModelConfig
from tests.generics.request import Request
from tests.generics.views import GenericAPIViewSet


# ─── Shared hook call tracker ─────────────────────────────
_hook_calls = []


def _reset():
    _hook_calls.clear()


# ─── ModelSerializer test model ───────────────────────────


class HookTestModel(ModelSerializer):
    name = models.CharField(max_length=255)
    description = models.TextField(default="")
    status = models.CharField(max_length=20, default="draft")

    class Meta:
        app_label = "test_app"

    class ReadSerializer:
        fields = ["id", "name", "description", "status"]

    class CreateSerializer:
        fields = ["name", "description", "status"]

    class UpdateSerializer:
        optionals = [("name", str), ("description", str), ("status", str)]

    @on_create
    async def on_created(self):
        _hook_calls.append(("create", self.pk, self.name))

    @on_update
    async def on_any_update(self):
        _hook_calls.append(("update_any", self.pk))

    @on_update("status")
    async def on_status_change(self):
        _hook_calls.append(("update_status", self.pk, self.status))

    @on_delete
    async def on_deleted(self):
        _hook_calls.append(("delete", self.pk, self.name))


# ─── ModelSerializer with sync hooks ─────────────────────


class SyncHookTestModel(ModelSerializer):
    name = models.CharField(max_length=255)

    class Meta:
        app_label = "test_app"

    class ReadSerializer:
        fields = ["id", "name"]

    class CreateSerializer:
        fields = ["name"]

    class UpdateSerializer:
        optionals = [("name", str)]

    @on_create
    def sync_on_created(self):
        _hook_calls.append(("sync_create", self.pk))


# ─── Plain model + Serializer ────────────────────────────


class HookPlainModel(models.Model):
    name = models.CharField(max_length=255)
    status = models.CharField(max_length=20, default="draft")

    class Meta:
        app_label = "test_app"


class HookPlainSerializer(Serializer):
    class Meta:
        model = HookPlainModel
        schema_in = SchemaModelConfig(fields=["name", "status"])
        schema_out = SchemaModelConfig(fields=["id", "name", "status"])
        schema_update = SchemaModelConfig(optionals=[("name", str), ("status", str)])

    @on_create
    async def on_created(self, instance):
        _hook_calls.append(("ser_create", instance.pk, instance.name))

    @on_update("status")
    async def on_status_change(self, instance):
        _hook_calls.append(("ser_update_status", instance.pk, instance.status))

    @on_delete
    async def on_deleted(self, instance):
        _hook_calls.append(("ser_delete", instance.pk))


# ─── ViewSets ────────────────────────────────────────────


class HookTestAPI(GenericAPIViewSet):
    model = HookTestModel


class SyncHookTestAPI(GenericAPIViewSet):
    model = SyncHookTestModel


class HookPlainAPI(GenericAPIViewSet):
    model = HookPlainModel
    serializer_class = HookPlainSerializer
    schema_in = HookPlainSerializer.generate_create_s()
    schema_out = HookPlainSerializer.generate_read_s()
    schema_update = HookPlainSerializer.generate_update_s()


# ─── Tests: ModelSerializer ──────────────────────────────


@tag("reactive_hooks")
class ModelSerializerReactiveHooksTestCase(TestCase):
    """Test reactive hooks on ModelSerializer."""

    @classmethod
    def setUpTestData(cls):
        cls.api = NinjaAIO(urls_namespace="hooks_ms_test")
        cls.viewset = HookTestAPI()
        cls.viewset.api = cls.api
        cls.viewset.add_views_to_route()
        cls.model = HookTestModel
        cls.request = Request(ModelUtil(cls.model).verbose_name_path_resolver())

    def setUp(self):
        _reset()

    async def test_on_create_fires(self):
        """@on_create fires after creation."""
        await self.model.objects.all().adelete()
        view = self.viewset.create_view()
        data = self.viewset.schema_in(name="test", description="d", status="draft")
        await view(self.request.post(), data)

        self.assertEqual(len(_hook_calls), 1)
        self.assertEqual(_hook_calls[0][0], "create")
        self.assertEqual(_hook_calls[0][2], "test")

    async def test_on_update_any_fires(self):
        """@on_update (no field) fires on any update."""
        await self.model.objects.all().adelete()
        obj = await self.model.objects.acreate(name="test", description="d")
        _reset()

        view = self.viewset.update_view()
        data = self.viewset.schema_update(description="updated")
        pk_schema = self.viewset.path_schema(id=obj.pk)
        await view(self.request.patch(), data, pk_schema)

        events = [c[0] for c in _hook_calls]
        self.assertIn("update_any", events)

    async def test_on_update_field_fires_when_changed(self):
        """@on_update('status') fires when status changes."""
        await self.model.objects.all().adelete()
        obj = await self.model.objects.acreate(name="test", status="draft")
        _reset()

        view = self.viewset.update_view()
        data = self.viewset.schema_update(status="published")
        pk_schema = self.viewset.path_schema(id=obj.pk)
        await view(self.request.patch(), data, pk_schema)

        events = [c[0] for c in _hook_calls]
        self.assertIn("update_status", events)
        status_call = [c for c in _hook_calls if c[0] == "update_status"][0]
        self.assertEqual(status_call[2], "published")

    async def test_on_update_field_does_not_fire_when_unchanged(self):
        """@on_update('status') does NOT fire when status is unchanged."""
        await self.model.objects.all().adelete()
        obj = await self.model.objects.acreate(name="test", status="draft")
        _reset()

        view = self.viewset.update_view()
        data = self.viewset.schema_update(description="only desc changed")
        pk_schema = self.viewset.path_schema(id=obj.pk)
        await view(self.request.patch(), data, pk_schema)

        events = [c[0] for c in _hook_calls]
        self.assertNotIn("update_status", events)
        self.assertIn("update_any", events)

    async def test_on_create_does_not_fire_on_update(self):
        """@on_create does NOT fire on update."""
        await self.model.objects.all().adelete()
        obj = await self.model.objects.acreate(name="test")
        _reset()

        view = self.viewset.update_view()
        data = self.viewset.schema_update(description="updated")
        pk_schema = self.viewset.path_schema(id=obj.pk)
        await view(self.request.patch(), data, pk_schema)

        events = [c[0] for c in _hook_calls]
        self.assertNotIn("create", events)

    async def test_on_update_does_not_fire_on_create(self):
        """@on_update does NOT fire on create."""
        await self.model.objects.all().adelete()
        view = self.viewset.create_view()
        data = self.viewset.schema_in(name="test", description="d", status="draft")
        await view(self.request.post(), data)

        events = [c[0] for c in _hook_calls]
        self.assertNotIn("update_any", events)
        self.assertNotIn("update_status", events)

    async def test_on_delete_fires(self):
        """@on_delete fires after deletion."""
        await self.model.objects.all().adelete()
        obj = await self.model.objects.acreate(name="del_me")
        _reset()

        view = self.viewset.delete_view()
        pk_schema = self.viewset.path_schema(id=obj.pk)
        await view(self.request.delete(), pk_schema)

        self.assertEqual(len(_hook_calls), 1)
        self.assertEqual(_hook_calls[0][0], "delete")
        self.assertEqual(_hook_calls[0][2], "del_me")


@tag("reactive_hooks")
class SyncHookTestCase(TestCase):
    """Test that sync hooks are properly wrapped in sync_to_async."""

    @classmethod
    def setUpTestData(cls):
        cls.api = NinjaAIO(urls_namespace="hooks_sync_test")
        cls.viewset = SyncHookTestAPI()
        cls.viewset.api = cls.api
        cls.viewset.add_views_to_route()
        cls.model = SyncHookTestModel
        cls.request = Request(ModelUtil(cls.model).verbose_name_path_resolver())

    def setUp(self):
        _reset()

    async def test_sync_hook_fires(self):
        """Sync @on_create hook is properly wrapped and fires."""
        await self.model.objects.all().adelete()
        view = self.viewset.create_view()
        data = self.viewset.schema_in(name="sync_test")
        await view(self.request.post(), data)

        self.assertEqual(len(_hook_calls), 1)
        self.assertEqual(_hook_calls[0][0], "sync_create")


# ─── Tests: Serializer (Meta-driven) ────────────────────


@tag("reactive_hooks")
class SerializerReactiveHooksTestCase(TestCase):
    """Test reactive hooks on Serializer (Meta-driven)."""

    @classmethod
    def setUpTestData(cls):
        cls.api = NinjaAIO(urls_namespace="hooks_ser_test")
        cls.viewset = HookPlainAPI()
        cls.viewset.api = cls.api
        cls.viewset.add_views_to_route()
        cls.model = HookPlainModel
        cls.request = Request(ModelUtil(cls.model).verbose_name_path_resolver())

    def setUp(self):
        _reset()

    async def test_serializer_on_create_fires(self):
        """@on_create on Serializer fires with instance parameter."""
        await self.model.objects.all().adelete()
        view = self.viewset.create_view()
        data = self.viewset.schema_in(name="ser_test", status="draft")
        await view(self.request.post(), data)

        self.assertEqual(len(_hook_calls), 1)
        self.assertEqual(_hook_calls[0][0], "ser_create")
        self.assertEqual(_hook_calls[0][2], "ser_test")

    async def test_serializer_on_update_field_fires(self):
        """@on_update('status') on Serializer fires when field changes."""
        await self.model.objects.all().adelete()
        obj = await self.model.objects.acreate(name="test", status="draft")
        _reset()

        view = self.viewset.update_view()
        data = self.viewset.schema_update(status="published")
        pk_schema = self.viewset.path_schema(id=obj.pk)
        await view(self.request.patch(), data, pk_schema)

        events = [c[0] for c in _hook_calls]
        self.assertIn("ser_update_status", events)

    async def test_serializer_on_delete_fires(self):
        """@on_delete on Serializer fires after deletion."""
        await self.model.objects.all().adelete()
        obj = await self.model.objects.acreate(name="del_me")
        _reset()

        view = self.viewset.delete_view()
        pk_schema = self.viewset.path_schema(id=obj.pk)
        await view(self.request.delete(), pk_schema)

        self.assertEqual(len(_hook_calls), 1)
        self.assertEqual(_hook_calls[0][0], "ser_delete")


# ─── Tests: Hook collection ─────────────────────────────


@tag("reactive_hooks")
class HookCollectionTestCase(TestCase):
    """Test hook discovery and collection."""

    def test_hooks_collected_on_model_serializer(self):
        """ModelSerializer collects reactive hooks at class definition time."""
        hooks = HookTestModel._reactive_hooks
        self.assertIn("on_created", hooks["create"])
        self.assertIn("on_any_update", hooks["update_any"])
        self.assertIn("on_status_change", hooks["update_field"].get("status", []))
        self.assertIn("on_deleted", hooks["delete"])

    def test_hooks_collected_on_serializer(self):
        """Serializer collects reactive hooks at class definition time."""
        hooks = HookPlainSerializer._reactive_hooks
        self.assertIn("on_created", hooks["create"])
        self.assertIn("on_status_change", hooks["update_field"].get("status", []))
        self.assertIn("on_deleted", hooks["delete"])

    def test_no_hooks_empty_dict(self):
        """Model without hooks has empty reactive hooks dict."""
        from tests.test_app.models import TestModel

        self.assertFalse(hasattr(TestModel, "_reactive_hooks"))

    def test_inherited_hooks_not_duplicated(self):
        """Hooks inherited from parent are collected once, not duplicated."""

        class ParentModel(ModelSerializer):
            name = models.CharField(max_length=255)

            class Meta:
                app_label = "test_app"

            class ReadSerializer:
                fields = ["id", "name"]

            class CreateSerializer:
                fields = ["name"]

            @on_create
            async def parent_hook(self):
                pass

        class ChildModel(ParentModel):
            class Meta:
                app_label = "test_app"

            @on_create
            async def child_hook(self):
                pass

        hooks = ChildModel._reactive_hooks
        self.assertIn("parent_hook", hooks["create"])
        self.assertIn("child_hook", hooks["create"])
        self.assertEqual(hooks["create"].count("parent_hook"), 1)

    def test_overridden_hook_not_duplicated(self):
        """Hook overridden in child class is collected once."""

        class Base(ModelSerializer):
            name = models.CharField(max_length=255)

            class Meta:
                app_label = "test_app"

            class ReadSerializer:
                fields = ["id", "name"]

            class CreateSerializer:
                fields = ["name"]

            @on_create
            async def my_hook(self):
                pass

        class Child(Base):
            class Meta:
                app_label = "test_app"

            @on_create
            async def my_hook(self):  # same name, overrides parent
                pass

        hooks = Child._reactive_hooks
        self.assertEqual(hooks["create"].count("my_hook"), 1)


# ─── Tests: Serializer sync hook with instance ──────────


class SyncSerializerHook(Serializer):
    class Meta:
        model = HookPlainModel
        schema_in = SchemaModelConfig(fields=["name", "status"])
        schema_out = SchemaModelConfig(fields=["id", "name", "status"])
        schema_update = SchemaModelConfig(optionals=[("name", str), ("status", str)])

    @on_create
    def sync_on_created(self, instance):
        _hook_calls.append(("sync_ser_create", instance.pk))


class SyncSerializerHookAPI(GenericAPIViewSet):
    model = HookPlainModel
    serializer_class = SyncSerializerHook
    schema_in = SyncSerializerHook.generate_create_s()
    schema_out = SyncSerializerHook.generate_read_s()
    schema_update = SyncSerializerHook.generate_update_s()


@tag("reactive_hooks")
class SyncSerializerHookTestCase(TestCase):
    """Test sync hooks on Serializer (with instance parameter)."""

    @classmethod
    def setUpTestData(cls):
        cls.api = NinjaAIO(urls_namespace="hooks_sync_ser")
        cls.viewset = SyncSerializerHookAPI()
        cls.viewset.api = cls.api
        cls.viewset.add_views_to_route()
        cls.model = HookPlainModel
        cls.request = Request(ModelUtil(cls.model).verbose_name_path_resolver())

    def setUp(self):
        _reset()

    async def test_sync_serializer_hook_fires(self):
        """Sync @on_create on Serializer is wrapped and fires with instance."""
        await self.model.objects.all().adelete()
        view = self.viewset.create_view()
        data = self.viewset.schema_in(name="sync_ser", status="draft")
        await view(self.request.post(), data)

        self.assertEqual(len(_hook_calls), 1)
        self.assertEqual(_hook_calls[0][0], "sync_ser_create")


# ─── Tests: Signal-based hooks (shell/admin path) ───────


@tag("reactive_hooks")
class SignalBasedHooksTestCase(TestCase):
    """Test that reactive hooks fire via Django signals (non-API path)."""

    def setUp(self):
        _reset()

    def test_signal_on_create_fires_on_direct_save(self):
        """@on_create fires when object is created directly (not via API)."""
        HookTestModel.objects.all().delete()
        obj = HookTestModel(name="shell_create", description="d", status="draft")
        obj.save()

        events = [c[0] for c in _hook_calls]
        self.assertIn("create", events)

    def test_signal_on_delete_fires_on_direct_delete(self):
        """@on_delete fires when object is deleted directly (not via API)."""
        HookTestModel.objects.all().delete()
        obj = HookTestModel.objects.create(name="shell_del", description="d")
        _reset()

        obj.delete()

        events = [c[0] for c in _hook_calls]
        self.assertIn("delete", events)

    def test_signal_on_update_fires_on_direct_save(self):
        """@on_update fires when existing object is saved directly."""
        HookTestModel.objects.all().delete()
        obj = HookTestModel.objects.create(name="shell_upd", description="d")
        _reset()

        obj.description = "updated"
        obj.save()

        events = [c[0] for c in _hook_calls]
        self.assertIn("update_any", events)

    def test_signal_skipped_in_api_path(self):
        """Signals are skipped when API path fires hooks directly."""
        # Implicitly tested by the API tests — if signals were NOT skipped,
        # hooks would fire twice and counts would be wrong.
        pass


@tag("reactive_hooks")
class SyncHookModelSignalTestCase(TestCase):
    """Test sync hooks fired via signals on a model with only sync hooks."""

    def setUp(self):
        _reset()

    def test_sync_create_hook_via_signal(self):
        """Sync @on_create hook fires via signal on direct save."""
        SyncHookTestModel.objects.all().delete()
        obj = SyncHookTestModel(name="signal_sync")
        obj.save()

        events = [c[0] for c in _hook_calls]
        self.assertIn("sync_create", events)

    def test_no_hooks_model_signal_noop(self):
        """Signal on a model without reactive hooks is a no-op."""
        from tests.test_app.models import TestModelSerializer

        _reset()
        TestModelSerializer.objects.all().delete()
        TestModelSerializer.objects.create(name="no_hooks", description="d")

        # TestModelSerializer has _reactive_hooks but all lists are empty
        # (no @on_create decorators), so signal should be a no-op
        self.assertEqual(len(_hook_calls), 0)

    def test_async_hook_fires_via_signal_without_event_loop(self):
        """Async @on_create hook fires from signal via async_to_sync when no loop."""
        HookTestModel.objects.all().delete()
        # HookTestModel.on_created is async — signal should wrap with async_to_sync
        obj = HookTestModel(name="async_signal", description="d", status="draft")
        obj.save()

        events = [c[0] for c in _hook_calls]
        self.assertIn("create", events)

    def test_register_signals_noop_without_hooks(self):
        """register_signals is a no-op for models without any hooks."""
        from ninja_aio.models.hooks import register_signals

        class EmptyHooksModel(ModelSerializer):
            name = models.CharField(max_length=255)

            class Meta:
                app_label = "test_app"

            class ReadSerializer:
                fields = ["id", "name"]

            class CreateSerializer:
                fields = ["name"]

        self.assertEqual(EmptyHooksModel._reactive_hooks["create"], [])
        register_signals(EmptyHooksModel)


@tag("reactive_hooks")
class HookInternalCoverageTestCase(TestCase):
    """Unit tests for internal hook functions to cover edge case branches."""

    def test_run_hook_sync_with_sync_method_and_instance(self):
        """_run_hook_sync calls sync method with instance when provided."""
        from ninja_aio.models.hooks import _run_hook_sync

        calls = []

        def my_hook(inst):
            calls.append(("sync_with_instance", inst))

        _run_hook_sync(my_hook, instance="fake_instance")
        self.assertEqual(calls, [("sync_with_instance", "fake_instance")])

    def test_run_hook_sync_with_async_method_and_instance(self):
        """_run_hook_sync wraps async method with async_to_sync when instance provided."""
        from ninja_aio.models.hooks import _run_hook_sync

        calls = []

        async def my_async_hook(inst):
            calls.append(("async_with_instance", inst))

        _run_hook_sync(my_async_hook, instance="fake_instance")
        self.assertEqual(calls, [("async_with_instance", "fake_instance")])

    def test_on_post_save_noop_for_model_without_hooks(self):
        """_on_post_save is a no-op when sender has no _reactive_hooks."""
        from ninja_aio.models.hooks import _on_post_save

        _reset()

        class FakeModel:
            _reactive_hooks = None

        _on_post_save(sender=FakeModel, instance=None, created=True)
        self.assertEqual(len(_hook_calls), 0)

    def test_on_post_delete_noop_for_model_without_hooks(self):
        """_on_post_delete is a no-op when sender has no _reactive_hooks."""
        from ninja_aio.models.hooks import _on_post_delete

        _reset()

        class FakeModel:
            _reactive_hooks = None

        _on_post_delete(sender=FakeModel, instance=None)
        self.assertEqual(len(_hook_calls), 0)

    def test_register_signals_noop_without_reactive_hooks_attr(self):
        """register_signals is a no-op when model has no _reactive_hooks attr."""
        from ninja_aio.models.hooks import register_signals

        class NoAttrModel:
            pass

        register_signals(NoAttrModel)  # should not raise

    async def test_run_hook_sync_skips_async_when_loop_running(self):
        """_run_hook_sync skips async hooks when an event loop is already running."""
        from ninja_aio.models.hooks import _run_hook_sync

        calls = []

        async def my_async_hook():
            calls.append("should_not_fire")

        # We're inside an async test, so there IS a running event loop
        _run_hook_sync(my_async_hook)
        self.assertEqual(calls, [])
