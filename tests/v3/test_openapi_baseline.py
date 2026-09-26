import json
from pathlib import Path
from typing import Any, Mapping, TypeAlias

from django.test import SimpleTestCase

from ninja_aio import NinjaAIO
from tests.helpers.test_many_to_many_api import (
    TestM2MViewSet,
    TestM2MWithSerializerClassViewSet,
)
from tests.test_app.views import (
    FieldSelectionTestAPI,
    RoleBasedPermissionTestAPI,
    SoftDeleteTestAPI,
    TestModelForeignKeySerializerAPI,
    TestModelSerializerAPI,
    TestModelSerializerBulkAPI,
)


SNAPSHOT_DIR = Path(__file__).with_name("snapshots")
OpenAPISnapshot: TypeAlias = dict[str, Any]


def _snapshot(schema: Mapping[str, Any]) -> OpenAPISnapshot:
    return {
        "paths": {
            path: {
                method: {
                    "operationId": operation.get("operationId"),
                    "responses": sorted(map(str, operation.get("responses", {}))),
                }
                for method, operation in sorted(methods.items())
            }
            for path, methods in sorted(schema["paths"].items())
        },
        "schemas": sorted(schema.get("components", {}).get("schemas", {})),
    }


def _normalize_generated_suffixes(
    actual: OpenAPISnapshot,
    expected: OpenAPISnapshot,
) -> OpenAPISnapshot:
    """Remove Ninja's order-dependent numeric suffixes from known schema names."""
    expected_names = expected["schemas"]
    normalized_names = []
    for actual_name in actual["schemas"]:
        canonical = next(
            (
                expected_name
                for expected_name in expected_names
                if actual_name.startswith(expected_name)
                and actual_name.removeprefix(expected_name).isdigit()
            ),
            actual_name,
        )
        normalized_names.append(canonical)
    return actual | {"schemas": sorted(normalized_names)}


class V2OpenAPIBaselineTests(SimpleTestCase):
    cases = (
        (
            "model_serializer",
            TestModelSerializerAPI,
            "model_serializer_openapi.json",
        ),
        (
            "standalone_serializer",
            TestModelForeignKeySerializerAPI,
            "standalone_serializer_openapi.json",
        ),
    )

    def test_representative_crud_openapi_contracts(self) -> None:
        for label, viewset_class, snapshot_name in self.cases:
            for mode in ("async", "sync"):
                with self.subTest(serializer_style=label, execution_mode=mode):
                    api = NinjaAIO(urls_namespace=f"v3_baseline_{label}_{mode}")
                    mode_class = type(
                        viewset_class.__name__, (viewset_class,), {"execution_mode": mode}
                    )
                    viewset = mode_class(api=api, prefix="/items", tags=["baseline"])
                    viewset.add_views_to_route()
                    actual = _snapshot(api.get_openapi_schema(path_prefix="/api"))
                    expected = json.loads(
                        (SNAPSHOT_DIR / snapshot_name).read_text(encoding="utf-8")
                    )
                    actual = _normalize_generated_suffixes(actual, expected)
                    self.assertEqual(actual, expected)


class ExecutionModeOpenAPIParityTests(SimpleTestCase):
    """Sync and async viewsets must publish the exact same OpenAPI document."""

    cases = {
        "bulk": TestModelSerializerBulkAPI,
        "m2m": TestM2MViewSet,
        "m2m_serializer_class": TestM2MWithSerializerClassViewSet,
        "soft_delete": SoftDeleteTestAPI,
        "field_selection": FieldSelectionTestAPI,
        "permissions_and_actions": RoleBasedPermissionTestAPI,
    }

    def _document(self, label: str, viewset_class, mode: str) -> dict:
        api = NinjaAIO(urls_namespace=f"v3_parity_{label}_{mode}")
        mode_class = type(viewset_class.__name__, (viewset_class,), {"execution_mode": mode})
        mode_class(api=api, prefix="/items", tags=["parity"]).add_views_to_route()
        return api.get_openapi_schema(path_prefix="/api")

    def test_full_openapi_document_matches_across_modes(self) -> None:
        for label, viewset_class in self.cases.items():
            with self.subTest(case=label):
                sync_doc = self._document(label, viewset_class, "sync")
                async_doc = self._document(label, viewset_class, "async")
                self.assertEqual(sync_doc["paths"], async_doc["paths"])
                self.assertEqual(sync_doc.get("components"), async_doc.get("components"))
                self.assertGreater(len(sync_doc["paths"]), 2)
