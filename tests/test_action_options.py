from dataclasses import fields
from typing import get_type_hints

from django.test import SimpleTestCase, tag

from ninja_aio.decorators.actions import ActionConfig, ActionOptions, action, on
from ninja_aio.types import HttpMethod


@tag("actions")
class ActionOptionsTestCase(SimpleTestCase):
    def test_options_match_action_config_fields(self):
        """ActionOptions must list every user-settable ActionConfig field."""
        config_fields = {f.name for f in fields(ActionConfig)} - {"detail", "prefetch_object"}
        self.assertEqual(set(get_type_hints(ActionOptions)), config_fields)

    def test_unknown_method_is_rejected_at_decoration(self):
        with self.assertRaisesRegex(ValueError, "Unsupported action methods"):
            action(detail=False, methods=["fetch"])
        with self.assertRaisesRegex(ValueError, "Unsupported action methods"):
            on("toggle", methods=["GET"])

    def test_unknown_option_is_rejected(self):
        with self.assertRaises(TypeError):
            action(detail=False, url="x")

    def test_each_decorated_function_gets_its_own_config(self):
        decorator = action(detail=False, tags=["a"])

        @decorator
        def first(self, request):
            pass

        @decorator
        def second(self, request):
            pass

        self.assertEqual(first._action_config, second._action_config)
        self.assertIsNot(first._action_config, second._action_config)

    def test_defaults(self):
        self.assertEqual(action(detail=True, methods=None)(lambda: None)._action_config.methods, ["get"])
        config = on("publish")(lambda: None)._action_config
        self.assertEqual((config.methods, config.url_path, config.prefetch_object), (["post"], "publish", True))

    def test_methods_accept_enum_members_and_normalize_strings(self):
        config = action(detail=False, methods=[HttpMethod.PATCH, "delete"])(
            lambda: None
        )._action_config
        self.assertEqual(config.methods, [HttpMethod.PATCH, HttpMethod.DELETE])
        self.assertTrue(all(isinstance(m, HttpMethod) for m in config.methods))
        self.assertEqual(str(HttpMethod.PATCH), "patch")
        self.assertEqual(f"{HttpMethod.PATCH}", "patch")
