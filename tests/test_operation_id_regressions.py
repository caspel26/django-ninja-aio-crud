from django.test import TestCase

from ninja_aio import NinjaAIO


class ExplicitOperationIdRegressionTests(TestCase):
    def test_generated_ids_reserve_explicit_ids_in_either_registration_order(self):
        for explicit_first in (True, False):
            api = NinjaAIO(urls_namespace=f"reserved_ids_{explicit_first}")

            def generated(request):
                return {}

            def explicit(request):
                return {}

            base = f"{generated.__module__}_{generated.__name__}".replace(".", "_")
            routes = [("/explicit", explicit, {"operation_id": base}), ("/generated", generated, {})]
            for path, handler, options in routes if explicit_first else reversed(routes):
                api.get(path, **options)(handler)
            first = api.get_openapi_schema(path_prefix="")
            self.assertEqual(first["paths"]["/explicit"]["get"]["operationId"], base)
            self.assertEqual(first["paths"]["/generated"]["get"]["operationId"], f"{base}_2")
            self.assertEqual(api.get_openapi_schema(path_prefix=""), first)
