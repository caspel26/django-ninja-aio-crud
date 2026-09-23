import json
from pathlib import Path

from django.test import SimpleTestCase

from ninja_aio import NinjaAIO
from tests.test_app.views import (
    TestModelForeignKeySerializerAPI,
    TestModelSerializerAPI,
)


SNAPSHOT_DIR = Path(__file__).with_name("snapshots")


def _snapshot(schema):
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

    def test_representative_crud_openapi_contracts(self):
        for label, viewset_class, snapshot_name in self.cases:
            with self.subTest(serializer_style=label):
                api = NinjaAIO(urls_namespace=f"v3_baseline_{label}")
                viewset = viewset_class(
                    api=api,
                    prefix="/items",
                    tags=["baseline"],
                )
                viewset.add_views_to_route()
                actual = _snapshot(api.get_openapi_schema(path_prefix="/api"))
                expected = json.loads(
                    (SNAPSHOT_DIR / snapshot_name).read_text(encoding="utf-8")
                )
                self.assertEqual(actual, expected)
