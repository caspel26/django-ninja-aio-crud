from types import SimpleNamespace

from asgiref.sync import async_to_sync
from django.test import TestCase, tag

from ninja_aio import NinjaAIO
from ninja_aio.exceptions import ForbiddenError
from ninja_aio.models import ModelUtil
from ninja_aio.views.mixins import PermissionViewSetMixin, RoleBasedPermissionMixin
from tests.generics.request import Request
from tests.test_app import models, views


# ---------------------------------------------------------------------------
#  Helpers
# ---------------------------------------------------------------------------


def _request_with(request_obj, **attrs):
    """Attach arbitrary attributes to a Django request for test control."""
    for k, v in attrs.items():
        setattr(request_obj, k, v)
    return request_obj


def _find_view(router, path, method):
    """Find a view function in a ninja Router by path and HTTP method."""
    pv = router.path_operations.get(path)
    if pv is None:
        return None
    for op in pv.operations:
        if method in op.methods:
            return op.view_func
    return None


class _PermissionTestBase(TestCase):
    """Shared setup for permission test cases."""

    namespace: str = ""
    viewset_class = None

    @classmethod
    def _init_viewset(cls, namespace, viewset_instance):
        cls.api = NinjaAIO(urls_namespace=namespace)
        cls.viewset = viewset_instance
        cls.viewset.api = cls.api
        cls.viewset.add_views_to_route()
        cls.model = models.TestModelSerializer
        cls.test_util = ModelUtil(cls.model)
        cls.request = Request("/test/")
        cls.schema_in = cls.model.generate_create_s()
        cls.schema_out = cls.model.generate_read_s()
        cls.schema_update = cls.model.generate_update_s()

    @classmethod
    def _locate_views(cls):
        cls.create_view = _find_view(cls.viewset.router, "/", "POST")
        cls.list_view = _find_view(cls.viewset.router, "", "GET")
        cls.retrieve_view = _find_view(cls.viewset.router, "{id}", "GET")
        cls.update_view = _find_view(cls.viewset.router, "{id}/", "PATCH")
        cls.delete_view = _find_view(cls.viewset.router, "{id}/", "DELETE")

    def _create_instance(self):
        return async_to_sync(self.test_util.create_s)(
            self.request.post(),
            self.schema_in(name="perm_test", description="perm_test_desc"),
            self.schema_out,
        )

    def _pk_schema(self, pk):
        return self.viewset.path_schema(id=pk)


# ---------------------------------------------------------------------------
#  ForbiddenError tests
# ---------------------------------------------------------------------------


@tag("viewset", "permissions")
class ForbiddenErrorTestCase(TestCase):
    """Test ForbiddenError exception."""

    def test_default_error(self):
        err = ForbiddenError()
        self.assertEqual(err.status_code, 403)
        self.assertEqual(err.error, {"error": "forbidden"})

    def test_custom_error(self):
        err = ForbiddenError(error={"custom": "msg"})
        self.assertEqual(err.error, {"custom": "msg"})

    def test_with_details(self):
        err = ForbiddenError(details="extra info")
        self.assertEqual(err.error["details"], "extra info")

    def test_get_error(self):
        body, status = ForbiddenError().get_error()
        self.assertEqual(status, 403)
        self.assertIn("error", body)


# ---------------------------------------------------------------------------
#  PermissionViewSetMixin tests
# ---------------------------------------------------------------------------


@tag("viewset", "permissions")
class PermissionViewSetMixinTestCase(_PermissionTestBase):
    """Test PermissionViewSetMixin hooks on all CRUD operations."""

    @classmethod
    def setUpTestData(cls):
        cls._init_viewset("perm_test", views.PermissionTestAPI())
        cls._locate_views()

    # -- Default (allow all) --------------------------------------------------

    def test_create_allowed_by_default(self):
        req = _request_with(self.request.post(), _allow=True)
        data = self.schema_in(name="allowed", description="desc")
        result = async_to_sync(self.create_view)(req, data=data)
        self.assertEqual(result.status_code, 201)

    def test_list_allowed_by_default(self):
        req = _request_with(self.request.get(), _allow=True)
        result = async_to_sync(self.list_view)(req)
        self.assertEqual(result.status_code, 200)

    # -- has_permission denied ------------------------------------------------

    def test_create_denied(self):
        req = _request_with(self.request.post(), _allow=False)
        data = self.schema_in(name="denied", description="desc")
        with self.assertRaises(ForbiddenError) as ctx:
            async_to_sync(self.create_view)(req, data=data)
        self.assertEqual(ctx.exception.status_code, 403)

    def test_list_denied(self):
        req = _request_with(self.request.get(), _allow=False)
        with self.assertRaises(ForbiddenError):
            async_to_sync(self.list_view)(req)

    def test_retrieve_denied(self):
        created = self._create_instance()
        req = _request_with(self.request.get(), _allow=False)
        with self.assertRaises(ForbiddenError):
            async_to_sync(self.retrieve_view)(req, pk=self._pk_schema(created["id"]))

    def test_update_denied(self):
        created = self._create_instance()
        req = _request_with(self.request.patch(), _allow=False)
        data = self.schema_update(description="new")
        with self.assertRaises(ForbiddenError):
            async_to_sync(self.update_view)(
                req, data=data, pk=self._pk_schema(created["id"])
            )

    def test_delete_denied(self):
        created = self._create_instance()
        req = _request_with(self.request.delete(), _allow=False)
        with self.assertRaises(ForbiddenError):
            async_to_sync(self.delete_view)(req, pk=self._pk_schema(created["id"]))

    # -- has_object_permission denied -----------------------------------------

    def test_retrieve_object_permission_denied(self):
        created = self._create_instance()
        req = _request_with(self.request.get(), _allow=True, _allow_obj=False)
        with self.assertRaises(ForbiddenError):
            async_to_sync(self.retrieve_view)(req, pk=self._pk_schema(created["id"]))

    def test_update_object_permission_denied(self):
        created = self._create_instance()
        req = _request_with(self.request.patch(), _allow=True, _allow_obj=False)
        data = self.schema_update(description="new")
        with self.assertRaises(ForbiddenError):
            async_to_sync(self.update_view)(
                req, data=data, pk=self._pk_schema(created["id"])
            )

    def test_delete_object_permission_denied(self):
        created = self._create_instance()
        req = _request_with(self.request.delete(), _allow=True, _allow_obj=False)
        with self.assertRaises(ForbiddenError):
            async_to_sync(self.delete_view)(req, pk=self._pk_schema(created["id"]))

    # -- get_permission_queryset ----------------------------------------------

    def test_list_queryset_filtered(self):
        self._create_instance()
        req = _request_with(self.request.get(), _allow=True, _filter_qs=True)
        result = async_to_sync(self.list_view)(req)
        self.assertEqual(result.value["count"], 0)
        self.assertEqual(result.value["items"], [])

    def test_list_queryset_not_filtered(self):
        self._create_instance()
        req = _request_with(self.request.get(), _allow=True, _filter_qs=False)
        result = async_to_sync(self.list_view)(req)
        self.assertGreater(result.value["count"], 0)

    def test_default_hooks_allow_all(self):
        """Base mixin hooks return True by default (no override)."""
        mixin = PermissionViewSetMixin.__new__(PermissionViewSetMixin)
        req = self.request.get()
        self.assertTrue(async_to_sync(mixin.has_permission)(req, "create"))
        self.assertTrue(
            async_to_sync(mixin.has_object_permission)(req, "retrieve", None)
        )


# ---------------------------------------------------------------------------
#  RoleBasedPermissionMixin tests
# ---------------------------------------------------------------------------


@tag("viewset", "permissions")
class RoleBasedPermissionMixinTestCase(_PermissionTestBase):
    """Test RoleBasedPermissionMixin role-to-operations mapping."""

    @classmethod
    def setUpTestData(cls):
        cls._init_viewset("role_test", views.RoleBasedPermissionTestAPI())
        cls._locate_views()
        cls.bulk_create_view = _find_view(cls.viewset.router, "bulk/", "POST")
        cls.bulk_delete_view = _find_view(cls.viewset.router, "bulk/", "DELETE")

    def _req_with_role(self, method="get", role=None):
        req = getattr(self.request, method)()
        req.auth = SimpleNamespace(role=role) if role else None
        return req

    # -- Admin role: all allowed ----------------------------------------------

    def test_admin_create(self):
        req = self._req_with_role("post", "admin")
        data = self.schema_in(name="admin_c", description="desc")
        result = async_to_sync(self.create_view)(req, data=data)
        self.assertEqual(result.status_code, 201)

    def test_admin_list(self):
        req = self._req_with_role("get", "admin")
        result = async_to_sync(self.list_view)(req)
        self.assertEqual(result.status_code, 200)

    def test_admin_retrieve(self):
        created = self._create_instance()
        req = self._req_with_role("get", "admin")
        result = async_to_sync(self.retrieve_view)(
            req, pk=self._pk_schema(created["id"])
        )
        self.assertEqual(result.status_code, 200)

    def test_admin_update(self):
        created = self._create_instance()
        req = self._req_with_role("patch", "admin")
        data = self.schema_update(description="updated")
        result = async_to_sync(self.update_view)(
            req, data=data, pk=self._pk_schema(created["id"])
        )
        self.assertEqual(result.status_code, 200)

    def test_admin_delete(self):
        created = self._create_instance()
        req = self._req_with_role("delete", "admin")
        result = async_to_sync(self.delete_view)(
            req, pk=self._pk_schema(created["id"])
        )
        self.assertEqual(result.status_code, 204)

    # -- Reader role: only list + retrieve ------------------------------------

    def test_reader_create_denied(self):
        req = self._req_with_role("post", "reader")
        data = self.schema_in(name="reader", description="desc")
        with self.assertRaises(ForbiddenError):
            async_to_sync(self.create_view)(req, data=data)

    def test_reader_list_allowed(self):
        req = self._req_with_role("get", "reader")
        result = async_to_sync(self.list_view)(req)
        self.assertEqual(result.status_code, 200)

    def test_reader_retrieve_allowed(self):
        created = self._create_instance()
        req = self._req_with_role("get", "reader")
        result = async_to_sync(self.retrieve_view)(
            req, pk=self._pk_schema(created["id"])
        )
        self.assertEqual(result.status_code, 200)

    def test_reader_update_denied(self):
        created = self._create_instance()
        req = self._req_with_role("patch", "reader")
        data = self.schema_update(description="new")
        with self.assertRaises(ForbiddenError):
            async_to_sync(self.update_view)(
                req, data=data, pk=self._pk_schema(created["id"])
            )

    def test_reader_delete_denied(self):
        created = self._create_instance()
        req = self._req_with_role("delete", "reader")
        with self.assertRaises(ForbiddenError):
            async_to_sync(self.delete_view)(
                req, pk=self._pk_schema(created["id"])
            )

    # -- Editor role: no delete -----------------------------------------------

    def test_editor_create_allowed(self):
        req = self._req_with_role("post", "editor")
        data = self.schema_in(name="editor_c", description="desc")
        result = async_to_sync(self.create_view)(req, data=data)
        self.assertEqual(result.status_code, 201)

    def test_editor_delete_denied(self):
        created = self._create_instance()
        req = self._req_with_role("delete", "editor")
        with self.assertRaises(ForbiddenError):
            async_to_sync(self.delete_view)(
                req, pk=self._pk_schema(created["id"])
            )

    # -- Edge cases -----------------------------------------------------------

    def test_unknown_role_denied(self):
        req = self._req_with_role("post", "viewer")
        data = self.schema_in(name="unk", description="desc")
        with self.assertRaises(ForbiddenError):
            async_to_sync(self.create_view)(req, data=data)

    def test_no_auth_denied(self):
        req = self._req_with_role("post", role=None)
        data = self.schema_in(name="noauth", description="desc")
        with self.assertRaises(ForbiddenError):
            async_to_sync(self.create_view)(req, data=data)

    def test_missing_role_attribute_denied(self):
        req = self.request.post()
        req.auth = SimpleNamespace(level="admin")  # wrong attr name
        data = self.schema_in(name="norole", description="desc")
        with self.assertRaises(ForbiddenError):
            async_to_sync(self.create_view)(req, data=data)

    def test_empty_permission_roles_allows_all(self):
        mixin = RoleBasedPermissionMixin.__new__(RoleBasedPermissionMixin)
        mixin.permission_roles = {}
        result = async_to_sync(mixin.has_permission)(self.request.get(), "create")
        self.assertTrue(result)

    def test_dict_auth_support(self):
        mixin = RoleBasedPermissionMixin.__new__(RoleBasedPermissionMixin)
        mixin.permission_roles = {"admin": ["create"]}
        mixin.role_attribute = "role"
        req = self.request.post()
        req.auth = {"role": "admin"}
        result = async_to_sync(mixin.has_permission)(req, "create")
        self.assertTrue(result)

    # -- Bulk operations ------------------------------------------------------

    def test_admin_bulk_create(self):
        if self.bulk_create_view is None:
            self.skipTest("Bulk create not registered")
        req = self._req_with_role("post", "admin")
        data = [
            self.schema_in(name="b1", description="d1"),
            self.schema_in(name="b2", description="d2"),
        ]
        result = async_to_sync(self.bulk_create_view)(req, data=data)
        self.assertEqual(result.status_code, 200)

    def test_reader_bulk_create_denied(self):
        if self.bulk_create_view is None:
            self.skipTest("Bulk create not registered")
        req = self._req_with_role("post", "reader")
        data = [self.schema_in(name="b3", description="d3")]
        with self.assertRaises(ForbiddenError):
            async_to_sync(self.bulk_create_view)(req, data=data)

    def test_admin_bulk_delete(self):
        if self.bulk_delete_view is None:
            self.skipTest("Bulk delete not registered")
        created = self._create_instance()
        req = self._req_with_role("delete", "admin")
        delete_schema = self.viewset.bulk_delete_schema(ids=[created["id"]])
        result = async_to_sync(self.bulk_delete_view)(req, data=delete_schema)
        self.assertEqual(result.status_code, 200)

    def test_reader_bulk_delete_denied(self):
        if self.bulk_delete_view is None:
            self.skipTest("Bulk delete not registered")
        req = self._req_with_role("delete", "reader")
        delete_schema = self.viewset.bulk_delete_schema(ids=[999])
        with self.assertRaises(ForbiddenError):
            async_to_sync(self.bulk_delete_view)(req, data=delete_schema)

    # -- Bulk update ----------------------------------------------------------

    def test_admin_bulk_update(self):
        bulk_update_view = _find_view(self.viewset.router, "bulk/", "PATCH")
        if bulk_update_view is None:
            self.skipTest("Bulk update not registered")
        created = self._create_instance()
        req = self._req_with_role("patch", "admin")
        update_schema = self.viewset.bulk_update_schema(
            id=created["id"], description="bulk_updated"
        )
        result = async_to_sync(bulk_update_view)(req, data=[update_schema])
        self.assertEqual(result.status_code, 200)

    def test_reader_bulk_update_denied(self):
        bulk_update_view = _find_view(self.viewset.router, "bulk/", "PATCH")
        if bulk_update_view is None:
            self.skipTest("Bulk update not registered")
        created = self._create_instance()
        req = self._req_with_role("patch", "reader")
        update_schema = self.viewset.bulk_update_schema(
            id=created["id"], description="denied"
        )
        with self.assertRaises(ForbiddenError):
            async_to_sync(bulk_update_view)(req, data=[update_schema])

    # -- @action support ------------------------------------------------------

    def test_admin_custom_action(self):
        action_view = _find_view(self.viewset.router, "custom-action", "POST")
        if action_view is None:
            self.skipTest("Custom action not registered")
        req = self._req_with_role("post", "admin")
        result = async_to_sync(action_view)(req)
        self.assertEqual(result, {"status": "ok"})

    def test_reader_custom_action_denied(self):
        action_view = _find_view(self.viewset.router, "custom-action", "POST")
        if action_view is None:
            self.skipTest("Custom action not registered")
        req = self._req_with_role("post", "reader")
        with self.assertRaises(ForbiddenError):
            async_to_sync(action_view)(req)


# ---------------------------------------------------------------------------
#  Composition tests
# ---------------------------------------------------------------------------


@tag("viewset", "permissions")
class PermissionWithFilterMixinTestCase(_PermissionTestBase):
    """Test that PermissionViewSetMixin composes with filter mixins."""

    @classmethod
    def setUpTestData(cls):
        cls._init_viewset("perm_filter_test", views.PermissionWithFilterTestAPI())
        cls.list_view = _find_view(cls.viewset.router, "", "GET")

    def test_list_allowed_with_filter_mixin(self):
        async_to_sync(self.test_util.create_s)(
            self.request.post(),
            self.schema_in(name="findme", description="desc"),
            self.schema_out,
        )
        req = _request_with(self.request.get(), _allow=True)
        result = async_to_sync(self.list_view)(req)
        self.assertEqual(result.status_code, 200)

    def test_list_denied_with_filter_mixin(self):
        req = _request_with(self.request.get(), _allow=False)
        with self.assertRaises(ForbiddenError):
            async_to_sync(self.list_view)(req)
