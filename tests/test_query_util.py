from unittest import mock
from django.test import TestCase, tag
from tests.test_app import models as app_models


@tag("query_util_dedicated")
class QueryUtilDedicatedTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        # Configure queryset_request (prefetch_related) on M2M serializer (ManyToMany -> prefetch_related)
        cls.query_util_fk = app_models.TestModelSerializerForeignKey.query_util
        cls.query_util_m2m = app_models.TestModelSerializerManyToMany.query_util
        # Create FK related objects
        cls.rev_fk = app_models.TestModelSerializerReverseForeignKey.objects.create(
            name="rev_fk", description="rev_fk"
        )
        cls.obj_fk = app_models.TestModelSerializerForeignKey.objects.create(
            name="fk", description="fk", test_model_serializer=cls.rev_fk
        )
        # Create M2M related objects
        cls.rev_m2m = app_models.TestModelSerializerReverseManyToMany.objects.create(
            name="rev_m2m", description="rev_m2m"
        )
        cls.obj_m2m = app_models.TestModelSerializerManyToMany.objects.create(
            name="m2m", description="m2m"
        )
        cls.obj_m2m.test_model_serializers.add(cls.rev_m2m)

    def test_scopes(self):
        self.assertIn("read", self.query_util_fk._configs)
        self.assertIn("queryset_request", self.query_util_fk._configs)
        self.assertIn("custom_scope", self.query_util_fk._configs)
        self.assertEqual(
            self.query_util_fk.SCOPES.READ, "read"
        )
        self.assertEqual(
            self.query_util_fk.SCOPES.QUERYSET_REQUEST, "queryset_request"
        )
        self.assertEqual(
            self.query_util_fk.SCOPES.custom_scope, "custom_scope"
        )

    def test_read_scope_select_related_applied(self):
        qs = app_models.TestModelSerializerForeignKey.objects.all()
        with mock.patch(
            "django.db.models.query.QuerySet.select_related",
            side_effect=lambda self, *args: self,
            autospec=True,
        ) as m_sel:
            _ = self.query_util_fk.apply_queryset_optimizations(
                qs, app_models.TestModelSerializerForeignKey.query_util.SCOPES.READ
            )
            sel_args = m_sel.call_args[0][1:]
            self.assertEqual(sel_args, ("test_model_serializer",))

    def test_queryset_request_scope_prefetch_applied_m2m(self):
        qs = app_models.TestModelSerializerManyToMany.objects.all()
        with mock.patch(
            "django.db.models.query.QuerySet.prefetch_related",
            side_effect=lambda self, *args: self,
            autospec=True,
        ) as m_pref:
            _ = self.query_util_m2m.apply_queryset_optimizations(
                qs,
                app_models.TestModelSerializerManyToMany.query_util.SCOPES.QUERYSET_REQUEST,
            )
            pref_args = m_pref.call_args[0][1:]
            self.assertEqual(pref_args, ("test_model_serializers",))

    def test_invalid_scope_raises(self):
        with self.assertRaises(ValueError):
            self.query_util_fk.apply_queryset_optimizations(
                app_models.TestModelSerializerForeignKey.objects.all(), "bad"
            )

    def test_missing_configuration_fallback(self):
        # Use a serializer model without modifying its QuerySet config
        util_simple = app_models.TestModelSerializer.query_util
        self.assertEqual(util_simple.read_config.select_related, [])
        self.assertEqual(util_simple.read_config.prefetch_related, [])
        qs = app_models.TestModelSerializer.objects.all()
        # Patching methods to assert they are NOT called
        with (
            mock.patch(
                "django.db.models.query.QuerySet.select_related",
                autospec=True,
            ) as m_sel,
            mock.patch(
                "django.db.models.query.QuerySet.prefetch_related",
                autospec=True,
            ) as m_pref,
        ):
            _ = util_simple.apply_queryset_optimizations(qs, util_simple.SCOPES.READ)
            m_sel.assert_not_called()
            m_pref.assert_not_called()
