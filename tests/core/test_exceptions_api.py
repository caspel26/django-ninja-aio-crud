from django.test import TestCase, tag
from joserfc.errors import JoseError
from ninja_aio.exceptions import NotFoundError, parse_jose_error, BaseException
from ninja_aio import NinjaAIO

from tests.test_app import models


class DummyJoseError(JoseError):
    # JoseError is abstract-like; we simulate minimal attributes
    def __init__(self, error: str, description: str | None = None):
        self.error = error
        self.description = description


@tag("exceptions_api")
class ExceptionsAndAPITestCase(TestCase):
    def setUp(self):
        self.api = NinjaAIO()

    def test_not_found_error(self):
        exc = NotFoundError(models.TestModel)
        self.assertEqual(exc.status_code, 404)
        self.assertEqual(
            exc.error,
            {models.TestModel._meta.verbose_name.replace(" ", "_"): "not found"},
        )

    def test_parse_jose_error(self):
        jose_exc = DummyJoseError("bad_token", "signature invalid")
        parsed = parse_jose_error(jose_exc)
        self.assertEqual(parsed["error"], "bad_token")
        self.assertEqual(parsed["details"], "signature invalid")

    def test_api_uses_custom_parser_renderer(self):
        self.assertEqual(self.api.parser.__class__.__name__, "ORJSONParser")
        self.assertEqual(self.api.renderer.__class__.__name__, "ORJSONRenderer")

    def test_api_exception_handlers_registered(self):
        # set_default_exception_handlers should add our handlers
        self.api.set_default_exception_handlers()
        handlers = getattr(self.api, "_exception_handlers", {})
        self.assertIn(BaseException, handlers)
