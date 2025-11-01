from django.test import TestCase, tag
from ninja_aio.decorators import unique_view
from tests.test_app import models
from ninja_aio.models import ModelUtil


class DummyViewSet:
    def __init__(self, model):
        self.model_util = ModelUtil(model)


@tag("decorators")
class UniqueViewDecoratorTestCase(TestCase):
    def setUp(self):
        self.viewset = DummyViewSet(models.TestModel)

    def test_unique_view_singular(self):
        @unique_view(self.viewset)
        def sample():
            return "ok"

        self.assertTrue(
            sample.__name__.endswith(f"_{self.viewset.model_util.model_name}")
        )

    def test_unique_view_plural(self):
        @unique_view(self.viewset, plural=True)
        def sample_plural():
            return "ok"

        self.assertTrue(
            sample_plural.__name__.endswith(
                f"_{self.viewset.model_util.verbose_name_view_resolver()}"
            )
        )

    def test_unique_view_string(self):
        @unique_view("custom_suffix")
        def sample_str():
            return "ok"

        self.assertTrue(sample_str.__name__.endswith("_custom_suffix"))
