"""Reusable facade contract assertions for future implementation steps."""

import inspect

from .contracts import METHOD_CONTRACTS, SCHEMA_ATTRIBUTES, SCHEMA_METHODS


class SerializerFacadeContractMixin:
    """Apply the version 3 surface checks to either serializer style.

    Concrete test cases added by implementation steps must set
    ``serializer_class`` to a ModelSerializer or Serializer subclass.
    """

    serializer_class = None

    def test_public_method_surface(self):
        serializer_class = self.serializer_class
        self.assertIsNotNone(serializer_class)
        for contract in METHOD_CONTRACTS:
            with self.subTest(method=contract.name):
                method = getattr(serializer_class, contract.name)
                self.assertTrue(callable(method))
                self.assertEqual(
                    inspect.iscoroutinefunction(method),
                    contract.mode == "async",
                )

    def test_schema_surface(self):
        serializer_class = self.serializer_class
        self.assertIsNotNone(serializer_class)
        for name in SCHEMA_ATTRIBUTES:
            with self.subTest(attribute=name):
                self.assertTrue(hasattr(serializer_class, name))
        for name in SCHEMA_METHODS:
            with self.subTest(method=name):
                self.assertTrue(callable(getattr(serializer_class, name)))
