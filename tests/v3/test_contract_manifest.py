from django.test import SimpleTestCase

from .contracts import (
    METHOD_CONTRACTS,
    SCHEMA_ATTRIBUTES,
    V2_CORE_METHODS,
    V2_MIGRATION_DECISIONS,
)


class V3ContractManifestTests(SimpleTestCase):
    def test_method_names_are_unique(self):
        names = [contract.name for contract in METHOD_CONTRACTS]
        self.assertEqual(len(names), len(set(names)))

    def test_every_sync_operation_has_an_async_pair(self):
        contracts = {contract.name: contract for contract in METHOD_CONTRACTS}
        for contract in METHOD_CONTRACTS:
            if contract.mode != "sync":
                continue
            async_name = f"a{contract.name}"
            with self.subTest(method=contract.name):
                self.assertIn(async_name, contracts)
                self.assertEqual(contracts[async_name].mode, "async")
                self.assertEqual(contracts[async_name].returns, contract.returns)

    def test_schema_attributes_use_schema_suffix(self):
        self.assertTrue(SCHEMA_ATTRIBUTES)
        for name in SCHEMA_ATTRIBUTES:
            with self.subTest(attribute=name):
                self.assertTrue(name.endswith("_schema"))

    def test_every_v2_core_method_has_a_migration_decision(self):
        self.assertEqual(V2_CORE_METHODS, V2_MIGRATION_DECISIONS.keys())
