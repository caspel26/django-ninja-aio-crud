from django.test import TestCase, tag
from ninja_aio.decorators import aatomic, unique_view, decorate_view
from ninja_aio.models import ModelUtil
from tests.test_app import models as app_models


@tag("decorators_aatomic")
class AAtomicDecoratorTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.model = app_models.TestModelSerializer

    async def _count(self):
        return await self.model.objects.acount()

    @aatomic
    async def _create_ok(self, name):
        await self.model.objects.acreate(name=name, description="ok")

    @aatomic
    async def _create_fail(self, name):
        await self.model.objects.acreate(name=name, description="fail")
        raise RuntimeError("boom")

    async def test_commit_on_success(self):
        before = await self._count()
        await self._create_ok("ok1")
        after = await self._count()
        self.assertEqual(after, before + 1)

    async def test_rollback_on_exception(self):
        before = await self._count()
        with self.assertRaises(RuntimeError):
            await self._create_fail("fail1")
        after = await self._count()
        self.assertEqual(after, before)  # no new row persisted


@tag("decorators_unique_view")
class UniqueViewDecoratorTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.model = app_models.TestModelSerializer
        cls.util = ModelUtil(cls.model)

        class Stub:
            def __init__(self, util):
                self.model_util = util

        cls.stub = Stub(cls.util)

    def test_unique_view_with_string_suffix(self):
        def base():
            pass

        fn = unique_view("stringSuffix")(base)
        self.assertEqual(fn.__name__, "base_stringSuffix")

    def test_unique_view_with_object_singular(self):
        def do():
            pass

        fn = unique_view(self.stub)(do)
        self.assertTrue(fn.__name__.endswith(f"_{self.model._meta.model_name}"))

    def test_unique_view_with_object_plural(self):
        def list_items():
            pass

        fn = unique_view(self.stub, plural=True)(list_items)
        # plural form removes spaces
        expected_plural = self.util.verbose_name_view_resolver()
        self.assertEqual(fn.__name__, f"list_items_{expected_plural}")

    def test_unique_view_no_suffix_if_missing(self):
        class Empty:  # no model_util attribute
            pass

        def func():
            pass

        original_name = func.__name__
        fn = unique_view(Empty())(func)
        self.assertEqual(fn.__name__, original_name)


@tag("decorators_decorate_view")
class DecorateViewTestCase(TestCase):
    """Tests for the decorate_view decorator."""

    def test_decorate_view_applies_decorators(self):
        """Test that decorators are applied in correct order."""
        call_order = []

        def dec1(fn):
            def wrapper(*args, **kwargs):
                call_order.append("dec1_before")
                result = fn(*args, **kwargs)
                call_order.append("dec1_after")
                return result
            return wrapper

        def dec2(fn):
            def wrapper(*args, **kwargs):
                call_order.append("dec2_before")
                result = fn(*args, **kwargs)
                call_order.append("dec2_after")
                return result
            return wrapper

        @decorate_view(dec1, dec2)
        def my_view():
            call_order.append("view")
            return "result"

        result = my_view()
        self.assertEqual(result, "result")
        # dec1 wraps dec2 wraps view: dec1_before -> dec2_before -> view -> dec2_after -> dec1_after
        self.assertEqual(call_order, ["dec1_before", "dec2_before", "view", "dec2_after", "dec1_after"])

    def test_decorate_view_skips_none_decorators(self):
        """Test that None decorators are skipped (covers line 215)."""
        call_order = []

        def dec1(fn):
            def wrapper(*args, **kwargs):
                call_order.append("dec1")
                return fn(*args, **kwargs)
            return wrapper

        @decorate_view(dec1, None, None)
        def my_view():
            call_order.append("view")
            return "ok"

        result = my_view()
        self.assertEqual(result, "ok")
        self.assertEqual(call_order, ["dec1", "view"])

    def test_decorate_view_with_all_none(self):
        """Test decorate_view when all decorators are None."""
        @decorate_view(None, None)
        def my_view():
            return "unchanged"

        self.assertEqual(my_view(), "unchanged")

    async def test_decorate_view_with_async_view(self):
        """Test that decorate_view works with async views."""
        def dec(fn):
            async def wrapper(*args, **kwargs):
                return await fn(*args, **kwargs)
            return wrapper

        @decorate_view(dec, None)
        async def async_view():
            return "async_result"

        result = await async_view()
        self.assertEqual(result, "async_result")
