import inspect
import json
import re
from dataclasses import dataclass
from typing import Any, Callable

from asgiref.sync import async_to_sync
from django.core.exceptions import ImproperlyConfigured
from django.db import transaction
from django.test import TestCase, tag
from ninja import Schema, Status

from ninja_aio.decorators.actions import action, on
from ninja_aio.exceptions import ForbiddenError
from ninja_aio.models import ModelUtil
from ninja_aio.models.serializers import BaseSerializer, SchemaModelConfig, Serializer
from ninja_aio.views import APIViewSet, mixins
from tests.generics.request import Request
from tests.helpers.test_many_to_many_api import (
    TestM2MViewSet,
    TestM2MWithSerializerClassViewSet,
)
from tests.test_app import models, views

MODES = ("sync", "async")


def _in_mode(viewset_class: type[APIViewSet], mode: str) -> type[APIViewSet]:
    return type(
        f"{viewset_class.__name__}{mode.title()}",
        (viewset_class,),
        {"execution_mode": mode},
    )


async def _await(awaitable):
    return await awaitable


def _resolve(result):
    return async_to_sync(_await)(result) if inspect.isawaitable(result) else result


def _strip_ids(value: Any) -> Any:
    """Drop primary keys, which differ between runs, from response bodies."""
    if isinstance(value, dict):
        return {k: _strip_ids(v) for k, v in value.items() if k != "id"}
    if isinstance(value, list):
        return [_strip_ids(v) for v in value]
    return value


def _outcome(call: Callable[[], Any]) -> tuple:
    try:
        result = _resolve(call())
    except Exception as exc:
        return ("raised", type(exc).__name__, getattr(exc, "status_code", None))
    body = result.value if hasattr(result, "value") else json.loads(result.content)
    if isinstance(body, Schema):
        body = body.model_dump()
    return (result.status_code, _strip_ids(body))


@dataclass(frozen=True)
class CrudCase:
    viewset: type[APIViewSet]
    create: Callable[[], dict]
    update: dict
    relate: Callable[[Any], None] = lambda pk: None


def _plain_payload() -> dict:
    return {"name": "parity", "description": "created"}


def _model_serializer_fk_payload() -> dict:
    parent = models.TestModelSerializerReverseForeignKey.objects.create(
        name="parent", description="p"
    )
    return {**_plain_payload(), "test_model_serializer_id": parent.pk}


def _model_fk_payload(fk_key: str) -> Callable[[], dict]:
    def payload() -> dict:
        parent = models.TestModelReverseForeignKey.objects.create(
            name="parent", description="p"
        )
        return {**_plain_payload(), fk_key: parent.pk}

    return payload


def _add_serializer_children(pk) -> None:
    for name in ("child-1", "child-2"):
        models.TestModelSerializerForeignKey.objects.create(
            name=name, description="c", test_model_serializer_id=pk
        )


def _add_model_children(pk) -> None:
    for name in ("child-1", "child-2"):
        models.TestModelForeignKey.objects.create(
            name=name, description="c", test_model_id=pk
        )


def _add_m2m_targets(pk) -> None:
    obj = models.TestModelSerializerManyToMany.objects.get(pk=pk)
    obj.test_model_serializers.add(
        *(
            models.TestModelSerializerReverseManyToMany.objects.create(
                name=name, description="t"
            )
            for name in ("target-1", "target-2")
        )
    )


CRUD_CASES = {
    "model_serializer": CrudCase(
        views.TestModelSerializerAPI, _plain_payload, {"description": "updated"}
    ),
    "model_serializer_fk": CrudCase(
        views.TestModelSerializerForeignKeyAPI,
        _model_serializer_fk_payload,
        {"description": "updated"},
    ),
    "model_serializer_reverse_fk": CrudCase(
        views.TestModelSerializerReverseForeignKeyAPI,
        _plain_payload,
        {"description": "updated"},
        _add_serializer_children,
    ),
    "model_serializer_m2m": CrudCase(
        views.TestModelSerializerManyToManyAPI,
        _plain_payload,
        {"description": "updated"},
        _add_m2m_targets,
    ),
    "serializer_fk": CrudCase(
        views.TestModelForeignKeySerializerAPI,
        _model_fk_payload("test_model_id"),
        {"description": "updated"},
    ),
    "serializer_reverse_fk": CrudCase(
        views.TestModelReverseForeignKeySerializerAPI,
        _plain_payload,
        {"description": "updated"},
        _add_model_children,
    ),
    "plain_model": CrudCase(
        views.TestModelAPI, _plain_payload, {"description": "updated"}
    ),
    "plain_model_fk": CrudCase(
        views.TestModelForeignKeyAPI,
        _model_fk_payload("test_model"),
        {"description": "updated"},
    ),
    "plain_model_reverse_fk": CrudCase(
        views.TestModelReverseForeignKeyAPI,
        _plain_payload,
        {"description": "updated"},
        _add_model_children,
    ),
    "plain_model_delete_out": CrudCase(
        views.TestModelDeleteOutAPI, _plain_payload, {"description": "updated"}
    ),
}


class RecordingHooksAPI(views.TestModelSerializerAPI):
    _has_object_hooks = True

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.calls = []

    async def aon_before_operation(self, request, operation):
        self.calls.append(("operation", operation))

    def on_before_operation(self, request, operation):
        self.calls.append(("operation", operation))

    async def aon_before_object_operation(self, request, operation, obj):
        self.calls.append(("object", operation, obj.name))

    def on_before_object_operation(self, request, operation, obj):
        self.calls.append(("object", operation, obj.name))


class DualPermissionAPI(views.GenericAPIViewSet, mixins.PermissionViewSetMixin):
    model = models.TestModelSerializer

    async def ahas_permission(self, request, operation):
        return getattr(request, "_allow", True)

    def has_permission(self, request, operation):
        return getattr(request, "_allow", True)

    async def ahas_object_permission(self, request, operation, obj):
        return getattr(request, "_allow_obj", True)

    def has_object_permission(self, request, operation, obj):
        return getattr(request, "_allow_obj", True)


class SyncActionsAPI(views.RoleBasedPermissionTestAPI):
    bulk_operations = []
    permission_roles = {
        **views.RoleBasedPermissionTestAPI.permission_roles,
        "admin": [*views.RoleBasedPermissionTestAPI.permission_roles["admin"], "ping", "rename"],
    }

    @action(detail=False, methods=["get"])
    def ping(self, request):
        return {"pong": True}

    @on("rename", methods=["post"])
    def rename(self, request, obj):
        obj.name = f"renamed-{obj.name}"
        obj.save(update_fields=["name"])
        return Status(200, {"name": obj.name})


def _request(method: str, **attrs):
    request = getattr(Request("parity"), method)()
    for key, value in attrs.items():
        setattr(request, key, value)
    return request


def _route(viewset: APIViewSet, suffix: str) -> Callable:
    path = f"{viewset.path_retrieve}/{suffix}"
    return viewset.router.path_operations[path].operations[0].view_func


@tag("execution_mode_parity")
class ExecutionModeParityTests(TestCase):
    """Sync and async generated endpoints must produce identical HTTP results."""

    def _isolated(self, run: Callable[[], Any]) -> Any:
        with transaction.atomic():
            result = run()
            transaction.set_rollback(True)
        return result

    def _crud_scenario(self, case: CrudCase, mode: str) -> list[tuple]:
        viewset = _in_mode(case.viewset, mode)()
        viewset._add_views()
        ops = viewset._operations
        request = Request("parity")
        pagination = viewset.pagination_class.Input(page=1, page_size=10)

        created = _resolve(
            ops["create"](request.post(), viewset.schema_in(**case.create()))
        )
        pk = viewset.path_schema(id=created.value["id"])
        case.relate(created.value["id"])
        missing = viewset.path_schema(id=10**9)
        return [
            (created.status_code, _strip_ids(created.value)),
            _outcome(
                lambda: ops["list"](
                    request.get(), filters=None, ninja_pagination=pagination
                )
            ),
            _outcome(lambda: ops["retrieve"](request.get(), pk)),
            _outcome(
                lambda: ops["update"](
                    request.patch(), viewset.schema_update(**case.update), pk
                )
            ),
            _outcome(lambda: ops["retrieve"](request.get(), missing)),
            _outcome(lambda: ops["delete"](request.delete(), pk)),
            _outcome(lambda: ops["retrieve"](request.get(), pk)),
        ]

    def test_crud_results_match_across_modes(self):
        for name, case in CRUD_CASES.items():
            with self.subTest(case=name):
                sync_result, async_result = (
                    self._isolated(lambda mode=mode: self._crud_scenario(case, mode))
                    for mode in MODES
                )
                self.assertEqual(sync_result, async_result)
                self.assertEqual(sync_result[4], ("raised", "NotFoundError", 404))

    def test_ordering_and_pagination_match_across_modes(self):
        def scenario(mode):
            for name in ("b", "c", "a"):
                models.TestModelSerializer.objects.create(name=name, description=name)
            viewset = _in_mode(views.TestModelSerializerOrderingAPI, mode)()
            viewset._add_views()
            request = Request("parity").get()
            return [
                _outcome(
                    lambda ordering=ordering: viewset._operations["list"](
                        request,
                        filters=viewset.filters_schema(ordering=ordering),
                        ninja_pagination=viewset.pagination_class.Input(
                            page=1, page_size=2
                        ),
                    )
                )
                for ordering in ("name", "-name", "unknown")
            ]

        sync_result, async_result = (
            self._isolated(lambda mode=mode: scenario(mode)) for mode in MODES
        )
        self.assertEqual(sync_result, async_result)
        self.assertEqual(
            [item["name"] for item in sync_result[0][1]["items"]], ["a", "b"]
        )

    def test_hooks_run_in_the_same_order_across_modes(self):
        def scenario(mode):
            viewset = _in_mode(RecordingHooksAPI, mode)()
            viewset._add_views()
            ops = viewset._operations
            request = Request("parity")
            created = _resolve(
                ops["create"](
                    request.post(), viewset.schema_in(name="hooked", description="d")
                )
            )
            pk = viewset.path_schema(id=created.value["id"])
            _resolve(ops["retrieve"](request.get(), pk))
            _resolve(
                ops["update"](
                    request.patch(), viewset.schema_update(description="u"), pk
                )
            )
            _resolve(ops["delete"](request.delete(), pk))
            return viewset.calls

        sync_calls, async_calls = (
            self._isolated(lambda mode=mode: scenario(mode)) for mode in MODES
        )
        self.assertEqual(sync_calls, async_calls)
        self.assertEqual(
            sync_calls,
            [
                ("operation", "create"),
                ("operation", "retrieve"),
                ("object", "retrieve", "hooked"),
                ("operation", "update"),
                ("object", "update", "hooked"),
                ("operation", "delete"),
                ("object", "delete", "hooked"),
            ],
        )


@tag("execution_mode_parity")
class MixinExecutionModeParityTests(TestCase):
    """Built-in mixins must behave identically in sync and async mode."""

    def _both_modes(self, scenario: Callable[[str], Any]) -> list:
        results = []
        for mode in MODES:
            with transaction.atomic():
                results.append(scenario(mode))
                transaction.set_rollback(True)
        return results

    def _list_parity(self, viewset_class, row_model, filters: dict) -> tuple:
        def scenario(mode):
            for name in ("alpha", "beta", "gamma"):
                row_model.objects.create(name=name, description=name)
            viewset = _in_mode(viewset_class, mode)()
            viewset._add_views()
            return _outcome(
                lambda: viewset._operations["list"](
                    Request("parity").get(),
                    filters=viewset.filters_schema(**filters),
                    ninja_pagination=viewset.pagination_class.Input(page=1),
                )
            )

        sync_result, async_result = self._both_modes(scenario)
        self.assertEqual(sync_result, async_result)
        return sync_result

    def test_filter_mixins(self):
        status, body = self._list_parity(
            views.TestModelSerializerAPI, models.TestModelSerializer, {"name": "bet"}
        )
        self.assertEqual((status, body["count"]), (200, 1))

    def test_search_mixin(self):
        status, body = self._list_parity(
            views.SearchTestAPI, models.TestModel, {"search": "bet"}
        )
        self.assertEqual((status, body["count"]), (200, 1))

    def test_field_selection_mixin(self):
        status, body = self._list_parity(
            views.FieldSelectionTestAPI, models.TestModel, {"fields": "name"}
        )
        self.assertEqual(status, 200)
        self.assertEqual(body["items"][0], {"name": "alpha"})

    def _list_with(self, viewset_class, mode, **filters):
        viewset = _in_mode(viewset_class, mode)()
        viewset._add_views()
        return _outcome(
            lambda: viewset._operations["list"](
                Request("parity").get(),
                filters=viewset.filters_schema(**filters),
                ninja_pagination=viewset.pagination_class.Input(page=1),
            )
        )

    def test_relation_filter_mixin(self):
        def scenario(mode):
            for name in ("target", "other"):
                parent = models.TestModelSerializerReverseForeignKey.objects.create(
                    name=name, description="p"
                )
                models.TestModelSerializerForeignKey.objects.create(
                    name=f"child-{name}", description="c", test_model_serializer=parent
                )
            return self._list_with(
                views.TestModelSerializerForeignKeyRelationFilterAPI,
                mode,
                test_model_serializer_name="targ",
            )

        sync_result, async_result = self._both_modes(scenario)
        self.assertEqual(sync_result, async_result)
        self.assertEqual(
            [item["name"] for item in sync_result[1]["items"]], ["child-target"]
        )

    def test_match_case_filter_mixin(self):
        def scenario(mode):
            for status in ("approved", "pending"):
                models.TestModelSerializer.objects.create(
                    name=status, description="d", status=status
                )
            return self._list_with(
                views.TestModelSerializerMatchCaseFilterAPI, mode, is_approved=True
            )

        sync_result, async_result = self._both_modes(scenario)
        self.assertEqual(sync_result, async_result)
        self.assertEqual([item["name"] for item in sync_result[1]["items"]], ["approved"])

    def test_soft_delete_without_object_hooks(self):
        class NoObjectHooksSoftDeleteAPI(views.SoftDeleteTestAPI):
            _has_object_hooks = False

        def scenario(mode):
            obj = models.SoftDeleteTestModel.objects.create(name="soft", description="d")
            viewset = _in_mode(NoObjectHooksSoftDeleteAPI, mode)()
            viewset._add_views()
            result = _outcome(
                lambda: viewset._operations["delete"](
                    Request("parity").delete(), viewset.path_schema(id=obj.pk)
                )
            )
            obj.refresh_from_db()
            return result, obj.is_deleted

        sync_result, async_result = self._both_modes(scenario)
        self.assertEqual(sync_result, async_result)
        self.assertEqual(sync_result, ((204, None), True))

    def test_field_selection_retrieve(self):
        def scenario(mode):
            obj = models.TestModel.objects.create(name="picked", description="d")
            viewset = _in_mode(views.FieldSelectionTestAPI, mode)()
            viewset._add_views()
            return _outcome(
                lambda: viewset._operations["retrieve"](
                    Request("parity").get(), viewset.path_schema(id=obj.pk), "name"
                )
            )

        sync_result, async_result = self._both_modes(scenario)
        self.assertEqual(sync_result, async_result)
        self.assertEqual(sync_result, (200, {"name": "picked"}))

    def test_soft_delete_mixin(self):
        def scenario(mode):
            obj = models.SoftDeleteTestModel.objects.create(name="soft", description="d")
            viewset = _in_mode(views.SoftDeleteTestAPI, mode)()
            viewset._add_views()
            pk = viewset.path_schema(id=obj.pk)
            request = Request("parity")
            return [
                _outcome(lambda: viewset._operations["delete"](request.delete(), pk)),
                models.SoftDeleteTestModel.objects.filter(pk=obj.pk).exists(),
                _outcome(lambda: viewset._operations["retrieve"](request.get(), pk)),
                _outcome(lambda: _route(viewset, "restore")(request.post(), pk)),
                _outcome(lambda: viewset._operations["retrieve"](request.get(), pk)),
                _outcome(lambda: _route(viewset, "hard-delete")(request.delete(), pk)),
                models.SoftDeleteTestModel.objects.filter(pk=obj.pk).exists(),
            ]

        sync_result, async_result = self._both_modes(scenario)
        self.assertEqual(sync_result, async_result)
        self.assertEqual(
            sync_result,
            [
                (204, None),
                True,
                ("raised", "NotFoundError", 404),
                (200, {"name": "soft", "description": "d"}),
                (200, {"name": "soft", "description": "d"}),
                (204, None),
                False,
            ],
        )

    def test_soft_delete_extra_endpoints_follow_execution_mode(self):
        for mode in MODES:
            with self.subTest(mode=mode):
                viewset = _in_mode(views.SoftDeleteTestAPI, mode)()
                viewset._add_views()
                for suffix in ("restore", "hard-delete"):
                    self.assertEqual(
                        inspect.iscoroutinefunction(_route(viewset, suffix)),
                        mode == "async",
                    )

    def test_permission_mixin(self):
        def scenario(mode):
            obj = models.TestModelSerializer.objects.create(name="perm", description="d")
            viewset = _in_mode(DualPermissionAPI, mode)()
            viewset._add_views()
            ops = viewset._operations
            pk = viewset.path_schema(id=obj.pk)
            return [
                _outcome(
                    lambda: ops["create"](
                        _request("post", _allow=False),
                        viewset.schema_in(name="x", description="d"),
                    )
                ),
                _outcome(lambda: ops["retrieve"](_request("get", _allow_obj=False), pk)),
                _outcome(lambda: ops["retrieve"](_request("get"), pk)),
            ]

        sync_result, async_result = self._both_modes(scenario)
        self.assertEqual(sync_result, async_result)
        self.assertEqual(sync_result[0], ("raised", "ForbiddenError", 403))
        self.assertEqual(sync_result[1], ("raised", "ForbiddenError", 403))
        self.assertEqual(sync_result[2][0], 200)

    def test_permission_defaults_allow_all(self):
        class DefaultPermissionAPI(views.GenericAPIViewSet, mixins.PermissionViewSetMixin):
            model = models.TestModelSerializer

        def scenario(mode):
            viewset = _in_mode(DefaultPermissionAPI, mode)()
            viewset._add_views()
            created = _resolve(
                viewset._operations["create"](
                    _request("post"), viewset.schema_in(name="open", description="d")
                )
            )
            return _outcome(
                lambda: viewset._operations["retrieve"](
                    _request("get"), viewset.path_schema(id=created.value["id"])
                )
            )

        sync_result, async_result = self._both_modes(scenario)
        self.assertEqual(sync_result, async_result)
        self.assertEqual(sync_result, (200, {"name": "open", "description": "d"}))

    def test_role_based_permission_mixin(self):
        def scenario(mode):
            obj = models.TestModelSerializer.objects.create(name="visible", description="d")
            viewset = _in_mode(SyncActionsAPI, mode)()
            viewset._add_views()
            ops = viewset._operations
            reader = {"role": "reader"}
            return [
                _outcome(
                    lambda: ops["create"](
                        _request("post", auth=reader),
                        viewset.schema_in(name="x", description="d"),
                    )
                ),
                _outcome(
                    lambda: ops["list"](
                        _request("get", auth=reader),
                        filters=None,
                        ninja_pagination=viewset.pagination_class.Input(page=1),
                    )
                ),
                _outcome(
                    lambda: ops["retrieve"](
                        _request("get", auth=reader), viewset.path_schema(id=obj.pk)
                    )
                ),
            ]

        sync_result, async_result = self._both_modes(scenario)
        self.assertEqual(sync_result, async_result)
        self.assertEqual(sync_result[0], ("raised", "ForbiddenError", 403))
        self.assertEqual(sync_result[1][0], 200)
        self.assertEqual(sync_result[2][0], 200)


class OptionalDescriptionSchema(Schema):
    description: str | None = None


class RequireFieldsBulkAPI(views.TestModelSerializerBulkAPI):
    require_update_fields = True
    schema_update = OptionalDescriptionSchema


MISSING_PK = 10**9


def _label_pks(value: Any, labels: dict) -> Any:
    """Replace known primary keys in bulk ``details`` with stable labels."""
    if isinstance(value, tuple):
        return tuple(_label_pks(v, labels) for v in value)
    if isinstance(value, dict):
        return {
            k: [labels.get(d, d) if isinstance(d, int) else d for d in v]
            if k == "details"
            else _label_pks(v, labels)
            for k, v in value.items()
        }
    return value


@tag("execution_mode_parity")
class BulkExecutionModeParityTests(TestCase):
    """Bulk endpoints must return the same (legacy) wire payloads in both modes."""

    def _scenario(self, viewset_class, mode: str) -> list:
        viewset = _in_mode(viewset_class, mode)()
        viewset._add_views()
        ops = viewset._operations
        model = viewset.model
        request = Request("parity")

        created = _outcome(
            lambda: ops["bulk_create"](
                request.post(),
                [viewset.schema_in(name=name, description="d") for name in ("a", "b")],
            )
        )
        pks = {obj.name: obj.pk for obj in model.objects.filter(name__in=["a", "b"])}
        labels = {pk: f"pk-{name}" for name, pk in pks.items()}
        update_item = viewset.bulk_update_schema
        updated = _outcome(
            lambda: ops["bulk_update"](
                request.patch(),
                [
                    update_item(id=pks["a"], description="u"),
                    update_item(id=MISSING_PK, description="u"),
                ],
            )
        )
        deleted = _outcome(
            lambda: ops["bulk_delete"](
                request.delete(), viewset.bulk_delete_schema(ids=[pks["b"], MISSING_PK])
            )
        )
        remaining = sorted(model.objects.values_list("name", "description"))
        return [_label_pks(r, labels) for r in (created, updated, deleted)] + [remaining]

    def _assert_parity(self, viewset_class) -> list:
        results = []
        for mode in MODES:
            with transaction.atomic():
                results.append(self._scenario(viewset_class, mode))
                transaction.set_rollback(True)
        self.assertEqual(results[0], results[1])
        return results[0]

    def test_bulk_model_serializer(self):
        created, updated, deleted, remaining = self._assert_parity(
            views.TestModelSerializerBulkAPI
        )
        self.assertEqual(created, (200, _bulk_body(["pk-a", "pk-b"], [])))
        self.assertEqual(updated[1]["success"]["details"], ["pk-a"])
        self.assertEqual(updated[1]["errors"]["count"], 1)
        self.assertEqual(deleted[1]["success"]["details"], ["pk-b"])
        self.assertEqual(deleted[1]["errors"]["count"], 1)
        self.assertEqual(remaining, [("a", "u")])

    def test_bulk_plain_model(self):
        self._assert_parity(views.TestModelBulkAPI)

    def test_bulk_single_response_field(self):
        created, _, deleted, _ = self._assert_parity(views.TestModelBulkSingleFieldAPI)
        self.assertEqual(created[1]["success"]["details"], ["a", "b"])
        self.assertEqual(deleted[1]["success"]["details"], ["b"])

    def test_bulk_multi_response_fields(self):
        _, _, deleted, _ = self._assert_parity(views.TestModelBulkMultiFieldAPI)
        # _outcome strips "id" keys; the remaining field proves the per-field extraction.
        self.assertEqual(deleted[1]["success"]["details"], [{"name": "b"}])

    def test_bulk_soft_delete(self):
        _, _, deleted, remaining = self._assert_parity(views.SoftDeleteTestAPI)
        self.assertEqual(deleted[1]["success"]["details"], ["pk-b"])
        self.assertEqual(len(remaining), 2)

    def test_bulk_update_rejects_empty_items_in_order(self):
        def scenario(mode):
            first = models.TestModelSerializer.objects.create(name="a", description="d")
            second = models.TestModelSerializer.objects.create(name="b", description="d")
            viewset = _in_mode(RequireFieldsBulkAPI, mode)()
            viewset._add_views()
            item = viewset.bulk_update_schema
            result = _outcome(
                lambda: viewset._operations["bulk_update"](
                    Request("parity").patch(),
                    [item(id=second.pk), item(id=MISSING_PK, description="x"), item(id=first.pk, description="x")],
                )
            )
            return _label_pks(result, {first.pk: "pk-a", second.pk: "pk-b"})

        results = []
        for mode in MODES:
            with transaction.atomic():
                results.append(scenario(mode))
                transaction.set_rollback(True)
        self.assertEqual(results[0], results[1])
        self.assertEqual(results[0][0], 200, results[0])
        status, body = results[0]
        self.assertEqual(body["success"]["details"], ["pk-a"])
        self.assertEqual(body["errors"]["details"][0], {"error": "No fields provided for update."})
        self.assertEqual(body["errors"]["count"], 2)


def _bulk_body(success: list, errors: list) -> dict:
    return {
        "success": {"count": len(success), "details": success},
        "errors": {"count": len(errors), "details": errors},
    }


class SyncQueryHandlerM2MAPI(TestM2MViewSet):
    execution_mode = "sync"

    def test_model_serializers_query_handler(self, request, pk, instance):
        return models.TestModelSerializerReverseManyToMany.objects.filter(pk=pk)


class AsyncQueryHandlerM2MAPI(TestM2MViewSet):
    async def test_model_serializers_query_handler(self, request, pk, instance):
        return models.TestModelSerializerReverseManyToMany.objects.filter(pk=pk)


@tag("execution_mode_parity")
class M2MExecutionModeParityTests(TestCase):
    """M2M endpoints must follow execution_mode and return identical payloads."""

    def _routes(self, viewset: APIViewSet, related_model) -> tuple[Callable, Callable]:
        rel_path = ModelUtil(related_model).verbose_name_path_resolver()
        operations = viewset.router.path_operations[
            f"{viewset.path_retrieve}/{rel_path}/"
        ].operations
        return operations[0].view_func, operations[1].view_func

    def _scenario(self, viewset: APIViewSet, related_model) -> list:
        base = viewset.model.objects.create(name="base", description="b")
        related = [
            related_model.objects.create(name=name, description=name)
            for name in ("r1", "r2", "r3")
        ]
        labels = {str(obj.pk): obj.name for obj in related}
        get_view, manage_view = self._routes(viewset, related_model)
        request = Request("parity")
        pk = viewset.path_schema(id=base.pk)
        schema_in = viewset.m2m_api.views_action_map[(True, True)][1]
        filters_schema = next(iter(viewset.m2m_api.relations_filters_schemas.values()))

        def manage(add=(), remove=()):
            return _outcome(
                lambda: manage_view(
                    request.post(), pk, schema_in(add=list(add), remove=list(remove))
                )
            )

        def listing(**filters):
            return _outcome(
                lambda: get_view(
                    request.get(),
                    pk,
                    filters=filters_schema(**filters) if filters else None,
                    ninja_pagination=viewset.pagination_class.Input(page=1),
                )
            )

        r1, r2, r3 = (obj.pk for obj in related)
        steps = [
            manage(add=[r1, r2, 10**9]),
            manage(add=[r1], remove=[r3]),
            listing(),
            listing(name="r2"),
            manage(remove=[r1]),
            listing(),
        ]
        text = json.dumps(steps)
        return json.loads(
            re.sub(r"pk (\d+)", lambda m: f"pk {labels.get(m.group(1), m.group(1))}", text)
        )

    def _assert_parity(self, classes: dict[str, type[APIViewSet]], related_model) -> list:
        results = []
        for mode in MODES:
            with transaction.atomic():
                viewset = classes[mode]()
                viewset._add_views()
                results.append(self._scenario(viewset, related_model))
                transaction.set_rollback(True)
        self.assertEqual(results[0], results[1])
        return results[0]

    def test_model_serializer_relation(self):
        steps = self._assert_parity(
            {mode: _in_mode(TestM2MViewSet, mode) for mode in MODES},
            models.TestModelSerializerReverseManyToMany,
        )
        added, mixed, full, filtered, _, after_remove = steps
        self.assertEqual((added[1]["results"]["count"], added[1]["errors"]["count"]), (2, 1))
        self.assertEqual(mixed[1]["errors"]["count"], 2)
        self.assertEqual([item["name"] for item in full[1]["items"]], ["r1", "r2"])
        self.assertEqual([item["name"] for item in filtered[1]["items"]], ["r2"])
        self.assertEqual([item["name"] for item in after_remove[1]["items"]], ["r2"])

    def test_serializer_class_relation(self):
        self._assert_parity(
            {mode: _in_mode(TestM2MWithSerializerClassViewSet, mode) for mode in MODES},
            models.TestModelReverseManyToMany,
        )

    def test_custom_query_handler(self):
        steps = self._assert_parity(
            {"sync": SyncQueryHandlerM2MAPI, "async": AsyncQueryHandlerM2MAPI},
            models.TestModelSerializerReverseManyToMany,
        )
        self.assertEqual(steps[0][1]["results"]["count"], 2)

    def test_handlers_follow_execution_mode(self):
        for mode in MODES:
            with self.subTest(mode=mode):
                viewset = _in_mode(TestM2MViewSet, mode)()
                viewset._add_views()
                for view in self._routes(viewset, models.TestModelSerializerReverseManyToMany):
                    self.assertEqual(inspect.iscoroutinefunction(view), mode == "async")

    def test_query_handler_kind_must_match_mode(self):
        with self.assertRaisesRegex(ImproperlyConfigured, "regular function"):
            _in_mode(AsyncQueryHandlerM2MAPI, "sync")()
        with self.assertRaisesRegex(ImproperlyConfigured, "coroutine function"):
            _in_mode(SyncQueryHandlerM2MAPI, "async")()

    def test_async_query_params_handler_is_rejected_in_sync_mode(self):
        class AsyncFiltersAPI(TestM2MViewSet):
            execution_mode = "sync"

            async def test_model_serializers_query_params_handler(self, queryset, filters):
                return queryset

        with self.assertRaisesRegex(ImproperlyConfigured, "query_params_handler"):
            AsyncFiltersAPI()


@tag("execution_mode_parity")
class SyncActionTests(TestCase):
    def setUp(self):
        self.viewset = SyncActionsAPI()
        self.viewset._add_views()

    def test_actions_register_handlers_matching_their_declaration(self):
        for name in ("ping", "rename"):
            with self.subTest(action=name):
                self.assertFalse(
                    inspect.iscoroutinefunction(self.viewset._operations[name])
                )
        self.assertTrue(
            inspect.iscoroutinefunction(self.viewset._operations["custom_action"])
        )

    def test_sync_action_runs_sync_permission_hook(self):
        ping = self.viewset._operations["ping"]
        self.assertEqual(ping(_request("get", auth={"role": "admin"})), {"pong": True})
        with self.assertRaises(ForbiddenError):
            ping(_request("get", auth={"role": "reader"}))

    def test_sync_on_action_fetches_object_and_runs_hooks(self):
        obj = models.TestModelSerializer.objects.create(name="obj", description="d")
        rename = self.viewset._operations["rename"]
        with self.assertRaises(ForbiddenError):
            rename(_request("post", auth={"role": "reader"}), id=obj.pk)
        result = rename(_request("post", auth={"role": "admin"}), id=obj.pk)
        self.assertEqual(result.value, {"name": "renamed-obj"})


@tag("execution_mode_parity")
class HookModeValidationTests(TestCase):
    def test_async_only_permission_override_is_rejected_in_sync_mode(self):
        with self.assertRaisesRegex(ImproperlyConfigured, "has_permission"):
            _in_mode(views.PermissionTestAPI, "sync")()

    def test_sync_only_hook_override_is_rejected_in_async_mode(self):
        class SyncOnlyHookAPI(views.TestModelAPI):
            def on_before_operation(self, request, operation):
                pass

        with self.assertRaisesRegex(ImproperlyConfigured, r"aon_before_operation\(\)"):
            SyncOnlyHookAPI()

    def test_sync_action_requires_sync_hooks_in_async_viewset(self):
        class MixedAPI(views.TestModelAPI):
            async def aon_before_operation(self, request, operation):
                pass

            @action(detail=False)
            def ping(self, request):
                return {}

        with self.assertRaisesRegex(ImproperlyConfigured, "on_before_operation"):
            MixedAPI()

    def test_bulk_endpoints_follow_execution_mode(self):
        class SyncBulkAPI(views.TestModelBulkAPI):
            execution_mode = "sync"

            def on_before_operation(self, request, operation):
                pass

        viewset = SyncBulkAPI()
        viewset._add_views()
        for operation in ("bulk_create", "bulk_update", "bulk_delete"):
            with self.subTest(operation=operation):
                self.assertFalse(
                    inspect.iscoroutinefunction(viewset._operations[operation])
                )

    def test_overriding_both_variants_is_accepted(self):
        for mode in MODES:
            with self.subTest(mode=mode):
                _in_mode(DualPermissionAPI, mode)()

    def test_unknown_execution_mode_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "execution_mode"):
            _in_mode(views.TestModelAPI, "threaded")()

    def test_v2_async_hook_name_is_rejected_with_new_name(self):
        class LegacyAPI(views.TestModelAPI):
            async def on_before_operation(self, request, operation):
                pass

        with self.assertRaisesRegex(ImproperlyConfigured, "rename it to aon_before_operation"):
            LegacyAPI()

    def test_async_hook_name_must_be_async(self):
        class WrongAPI(views.TestModelAPI):
            def aon_before_operation(self, request, operation):
                pass

        with self.assertRaisesRegex(ImproperlyConfigured, "aon_before_operation must be async"):
            WrongAPI()


_HOOK_CALLS: list[tuple[str, str]] = []


class AsyncOnlyHookSerializer(Serializer):
    class Meta:
        model = models.TestModel
        schema_in = SchemaModelConfig(fields=["name", "description"])
        schema_out = SchemaModelConfig(fields=["id", "name", "description"])

    async def apost_create(self, instance):
        _HOOK_CALLS.append(("async", instance.name))


class SyncOnlyHookSerializer(Serializer):
    class Meta:
        model = models.TestModel
        schema_in = SchemaModelConfig(fields=["name", "description"])
        schema_out = SchemaModelConfig(fields=["id", "name", "description"])

    def post_create(self, instance):
        _HOOK_CALLS.append(("sync", instance.name))


def _fail_on(instance) -> None:
    if instance.name == "fail-create" or instance.description == "boom":
        raise RuntimeError(f"hook failed for {instance.name}")


class FailingHooksSerializer(Serializer):
    class Meta:
        model = models.TestModel
        schema_in = SchemaModelConfig(fields=["name", "description"])
        schema_out = SchemaModelConfig(fields=["id", "name", "description"])
        schema_update = SchemaModelConfig(optionals=[("description", str)])

    def post_create(self, instance):
        _fail_on(instance)

    async def apost_create(self, instance):
        _fail_on(instance)

    def custom_actions(self, payload, instance):
        _fail_on(instance)

    async def acustom_actions(self, payload, instance):
        _fail_on(instance)


class FailingHooksAPI(views.GenericAPIViewSet):
    model = models.TestModel
    serializer_class = FailingHooksSerializer
    bulk_operations = ["create", "update"]


@tag("execution_mode_parity")
class TransactionParityTests(TestCase):
    """A failing hook must roll back the same writes in both modes."""

    def _scenario(self, mode: str) -> list:
        viewset = _in_mode(FailingHooksAPI, mode)()
        viewset._add_views()
        ops = viewset._operations
        request = Request("parity")
        names = lambda: sorted(models.TestModel.objects.values_list("name", "description"))  # noqa: E731

        failed_create = _outcome(
            lambda: ops["create"](
                request.post(), viewset.schema_in(name="fail-create", description="d")
            )
        )
        after_failed_create = names()
        created = _resolve(
            ops["create"](request.post(), viewset.schema_in(name="kept", description="d"))
        )
        pk = viewset.path_schema(id=created.value["id"])
        failed_update = _outcome(
            lambda: ops["update"](
                request.patch(), viewset.schema_update(description="boom"), pk
            )
        )
        after_failed_update = names()
        bulk = _outcome(
            lambda: ops["bulk_create"](
                request.post(),
                [
                    viewset.schema_in(name="bulk-ok", description="d"),
                    viewset.schema_in(name="fail-create", description="d"),
                ],
            )
        )
        bulk_update = _outcome(
            lambda: ops["bulk_update"](
                request.patch(),
                [
                    viewset.bulk_update_schema(id=created.value["id"], description="boom"),
                ],
            )
        )
        return [
            failed_create,
            after_failed_create,
            failed_update,
            after_failed_update,
            bulk,
            bulk_update,
            names(),
        ]

    def test_hook_failures_roll_back_identically(self):
        results = []
        for mode in MODES:
            with transaction.atomic():
                results.append(self._scenario(mode))
                transaction.set_rollback(True)
        self.assertEqual(results[0], results[1])
        (
            failed_create,
            after_failed_create,
            failed_update,
            after_failed_update,
            bulk,
            bulk_update,
            final,
        ) = results[0]
        self.assertEqual(failed_create, ("raised", "RuntimeError", None))
        self.assertEqual(after_failed_create, [])
        self.assertEqual(failed_update, ("raised", "RuntimeError", None))
        self.assertEqual(after_failed_update, [("kept", "d")])
        self.assertEqual(
            bulk[1]["errors"]["details"], [{"error": "hook failed for fail-create"}]
        )
        self.assertEqual(bulk_update[1]["errors"]["count"], 1)
        self.assertEqual(final, [("bulk-ok", "d"), ("kept", "d")])


@tag("execution_mode_parity")
class SerializerHookNamingTests(TestCase):
    def setUp(self):
        _HOOK_CALLS.clear()

    def test_v2_async_serializer_hook_is_rejected_with_new_name(self):
        with self.assertRaisesRegex(ImproperlyConfigured, "rename it to apost_create"):

            class LegacySerializer(Serializer):
                class Meta:
                    model = models.TestModel

                async def post_create(self, instance):
                    pass

    def test_async_serializer_hook_name_must_be_async(self):
        with self.assertRaisesRegex(ImproperlyConfigured, "aqueryset_request must be async"):

            class WrongSerializer(Serializer):
                class Meta:
                    model = models.TestModel

                @classmethod
                def aqueryset_request(cls, request):
                    return cls.model.objects.all()

    def test_sync_path_runs_async_only_override(self):
        AsyncOnlyHookSerializer.create({"name": "bridged", "description": "d"})
        self.assertEqual(_HOOK_CALLS, [("async", "bridged")])

    def test_async_path_runs_sync_only_override(self):
        async_to_sync(SyncOnlyHookSerializer.acreate)({"name": "bridged", "description": "d"})
        self.assertEqual(_HOOK_CALLS, [("sync", "bridged")])

    def test_base_queryset_request_hooks_are_abstract(self):
        with self.assertRaises(NotImplementedError):
            BaseSerializer.queryset_request(None)
        with self.assertRaises(NotImplementedError):
            async_to_sync(BaseSerializer.aqueryset_request)(None)
