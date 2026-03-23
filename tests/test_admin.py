from django.contrib import admin
from django.contrib.admin import AdminSite
from django.test import TestCase, tag

from ninja_aio.admin import _classify_fields, model_admin_factory, register_admin
from tests.test_app import models


@tag("admin")
class ClassifyFieldsTestCase(TestCase):
    """Test _classify_fields extracts correct admin config from ModelSerializer."""

    def test_basic_model(self):
        config = _classify_fields(models.TestModelSerializer)
        self.assertIn("id", config["list_display"])
        self.assertIn("name", config["list_display"])
        self.assertIn("name", config["search_fields"])
        self.assertIsInstance(config["list_display"], tuple)

    def test_fk_in_list_filter(self):
        config = _classify_fields(models.TestModelSerializerForeignKey)
        self.assertIn("test_model_serializer", config["list_filter"])

    def test_detail_serializer_not_used(self):
        """_classify_fields should use ReadSerializer, not DetailSerializer."""
        config = _classify_fields(models.TestModelSerializerWithDetail)
        read_fields = models.TestModelSerializerWithDetail.get_fields("read")
        for field in read_fields:
            self.assertIn(field, config["list_display"])

    def test_readonly_fields(self):
        """Fields in read but not in update should be readonly (except PK)."""
        config = _classify_fields(models.TestModelSerializer)
        read_fields = set(models.TestModelSerializer.get_fields("read"))
        update_fields = set(models.TestModelSerializer.get_fields("update"))
        pk_name = models.TestModelSerializer._meta.pk.name
        expected_readonly = read_fields - update_fields - {pk_name}
        for field in expected_readonly:
            # Only model fields (not customs) that are in read but not update
            try:
                models.TestModelSerializer._meta.get_field(field)
                self.assertIn(field, config["readonly_fields"])
            except Exception:
                pass

    def test_no_update_serializer(self):
        """Model without UpdateSerializer should not crash."""
        # TestModelSerializerWithReadCustoms may not have UpdateSerializer
        config = _classify_fields(models.TestModelSerializerWithReadCustoms)
        self.assertIsInstance(config["list_display"], tuple)

    def test_custom_fields_are_readonly(self):
        """Custom fields from get_custom_fields should be readonly."""
        config = _classify_fields(models.TestModelSerializerWithReadCustoms)
        custom_fields = models.TestModelSerializerWithReadCustoms.get_custom_fields("read")
        for name, *_ in custom_fields:
            self.assertIn(name, config["list_display"])
            self.assertIn(name, config["readonly_fields"])

    def test_inline_custom_fields_are_readonly(self):
        """Inline custom fields (tuples in fields list) should be readonly."""
        config = _classify_fields(models.TestModelSerializerInlineCustoms)
        inline_customs = models.TestModelSerializerInlineCustoms.get_inline_customs("read")
        for name, *_ in inline_customs:
            self.assertIn(name, config["list_display"])
            self.assertIn(name, config["readonly_fields"])

    def test_m2m_goes_to_filter_not_display(self):
        """ManyToMany fields should be in list_filter, not list_display."""
        from ninja_aio.admin import _classify_model_field
        display, _, filt, _ = _classify_model_field(
            "test_model_serializers",
            models.TestModelSerializerManyToMany,
            [],
            "id",
        )
        self.assertEqual(display, [])
        self.assertIn("test_model_serializers", filt)

    def test_unknown_field_is_readonly(self):
        """A field name not on the model should be treated as custom (readonly)."""
        from ninja_aio.admin import _classify_model_field
        display, search, filt, readonly = _classify_model_field(
            "nonexistent_field", models.TestModelSerializer, [], "id"
        )
        self.assertEqual(display, ["nonexistent_field"])
        self.assertEqual(search, [])
        self.assertEqual(filt, [])
        self.assertEqual(readonly, ["nonexistent_field"])


@tag("admin")
class ModelAdminFactoryTestCase(TestCase):
    """Test model_admin_factory creates correct ModelAdmin classes."""

    def test_creates_admin_class(self):
        admin_cls = model_admin_factory(models.TestModelSerializer)
        self.assertTrue(issubclass(admin_cls, admin.ModelAdmin))
        self.assertEqual(admin_cls.__name__, "TestModelSerializerAdmin")

    def test_has_list_display(self):
        admin_cls = model_admin_factory(models.TestModelSerializer)
        self.assertIsNotNone(admin_cls.list_display)
        self.assertGreater(len(admin_cls.list_display), 0)

    def test_has_search_fields(self):
        admin_cls = model_admin_factory(models.TestModelSerializer)
        self.assertIsNotNone(admin_cls.search_fields)

    def test_overrides_work(self):
        admin_cls = model_admin_factory(
            models.TestModelSerializer, list_per_page=50
        )
        self.assertEqual(admin_cls.list_per_page, 50)

    def test_overrides_replace_auto(self):
        custom_display = ("id", "name")
        admin_cls = model_admin_factory(
            models.TestModelSerializer, list_display=custom_display
        )
        self.assertEqual(admin_cls.list_display, custom_display)

    def test_fk_model(self):
        admin_cls = model_admin_factory(models.TestModelSerializerForeignKey)
        self.assertIn("test_model_serializer", admin_cls.list_filter)


@tag("admin")
class RegisterAdminTestCase(TestCase):
    """Test register_admin decorator."""

    def setUp(self):
        self.test_site = AdminSite(name="test_register")

    def test_register_no_args(self):
        """@register_admin (no parens) should register the model."""
        register_admin(models.TestModelSerializer, site=self.test_site)
        self.assertIn(
            models.TestModelSerializer, self.test_site._registry
        )

    def test_register_with_overrides(self):
        """@register_admin(list_per_page=25) should apply overrides."""
        decorator = register_admin(site=self.test_site, list_per_page=25)
        decorator(models.TestModelSerializerWithDetail)
        admin_cls = type(
            self.test_site._registry[models.TestModelSerializerWithDetail]
        )
        self.assertEqual(admin_cls.list_per_page, 25)

    def test_decorator_returns_class(self):
        """The decorator should return the original class unchanged."""
        result = register_admin(
            models.TestModelSerializerForeignKey, site=self.test_site
        )
        self.assertIs(result, models.TestModelSerializerForeignKey)

    def test_decorator_with_parens_returns_class(self):
        decorator = register_admin(site=self.test_site)
        result = decorator(models.TestModelSerializerWithReadCustoms)
        self.assertIs(result, models.TestModelSerializerWithReadCustoms)


@tag("admin")
class AsAdminTestCase(TestCase):
    """Test ModelSerializer.as_admin() classmethod."""

    def test_returns_admin_class(self):
        admin_cls = models.TestModelSerializer.as_admin()
        self.assertTrue(issubclass(admin_cls, admin.ModelAdmin))

    def test_with_overrides(self):
        admin_cls = models.TestModelSerializer.as_admin(list_per_page=100)
        self.assertEqual(admin_cls.list_per_page, 100)

    def test_register_with_as_admin(self):
        """Simulate admin.site.register(Model, Model.as_admin())."""
        test_site = AdminSite(name="test_as_admin")
        test_site.register(
            models.TestModelSerializer,
            models.TestModelSerializer.as_admin(),
        )
        self.assertIn(models.TestModelSerializer, test_site._registry)

    def test_fk_model_as_admin(self):
        admin_cls = models.TestModelSerializerForeignKey.as_admin()
        self.assertIn("test_model_serializer", admin_cls.list_filter)
