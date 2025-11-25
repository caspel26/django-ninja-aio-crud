from django.test import TestCase, tag
from django.http import HttpRequest
from pydantic import BaseModel, Field, ValidationError
from ninja_aio.api import NinjaAIO
from ninja_aio.exceptions import (
    BaseException,
    SerializeError,
    NotFoundError,
    PydanticValidationError,
    parse_jose_error,
    set_api_exception_handlers,
)
from joserfc.errors import JoseError
from tests.test_app import models as app_models


class DummyModel(BaseModel):
    a: int = Field(gt=0)


@tag("exceptions_base")
class BaseExceptionTestCase(TestCase):
    def test_string_error_conversion(self):
        exc = BaseException("bad", 418, details="info")
        self.assertEqual(exc.error["error"], "bad")
        self.assertEqual(exc.error["details"], "info")
        self.assertEqual(exc.status_code, 418)

    def test_dict_error_preserved_and_details_merge(self):
        exc = BaseException({"foo": "bar"}, details="more")
        self.assertEqual(exc.error["foo"], "bar")
        self.assertEqual(exc.error["details"], "more")
        self.assertEqual(exc.status_code, 400)

    def test_get_error(self):
        exc = BaseException("x")
        err, status = exc.get_error()
        self.assertEqual(status, 400)
        self.assertIn("error", err)


@tag("exceptions_subclasses")
class SubclassesTestCase(TestCase):
    def test_serialize_error(self):
        exc = SerializeError("serialize")
        self.assertEqual(exc.error["error"], "serialize")

    def test_not_found_error(self):
        app_models.TestModelSerializer.objects.create(name="n", description="d")
        exc = NotFoundError(app_models.TestModelSerializer)
        key = app_models.TestModelSerializer._meta.verbose_name.replace(" ", "_")
        self.assertIn(key, exc.error)
        self.assertEqual(exc.status_code, 404)

    def test_pydantic_validation_error(self):
        try:
            DummyModel(a=0)
        except ValidationError as ve:
            p_exc = PydanticValidationError(ve.errors())
            self.assertEqual(p_exc.error["error"], "Validation Error")
            self.assertTrue(p_exc.error["details"])  # details list present


@tag("exceptions_parse_jose")
class JoseParseTestCase(TestCase):
    class FakeJoseError(JoseError):
        def __init__(self, error: str, description: str | None = None):
            self.error = error
            self.description = description

    def test_parse_jose_error_with_description(self):
        fake = self.FakeJoseError("invalid_token", "expired")
        parsed = parse_jose_error(fake)
        self.assertEqual(parsed["error"], "invalid_token")
        self.assertEqual(parsed["details"], "expired")

    def test_parse_jose_error_without_description(self):
        fake = self.FakeJoseError("invalid_token", None)
        parsed = parse_jose_error(fake)
        self.assertEqual(parsed, {"error": "invalid_token"})


@tag("exceptions_handlers")
class ExceptionHandlersTestCase(TestCase):
    def test_set_api_exception_handlers(self):
        api = NinjaAIO()
        set_api_exception_handlers(api)
        self.assertIn(BaseException, api._exception_handlers)
        self.assertIn(JoseError, api._exception_handlers)
        self.assertIn(ValidationError, api._exception_handlers)

    def test_default_error_response(self):
        api = NinjaAIO()
        set_api_exception_handlers(api)
        exc = BaseException("boom", 499)
        request = HttpRequest()
        response = api._exception_handlers[BaseException](request, exc)
        self.assertEqual(response.status_code, 499)
        self.assertIn(b"boom", response.content)

    def test_pydantic_error_handler(self):
        api = NinjaAIO()
        set_api_exception_handlers(api)
        try:
            DummyModel(a=0)
        except ValidationError as ve:
            request = HttpRequest()
            response = api._exception_handlers[ValidationError](request, ve)
            self.assertEqual(response.status_code, 400)
            self.assertIn(b"Validation Error", response.content)


@tag("exceptions_handlers_jose")
class JoseErrorHandlerTestCase(TestCase):
    class FakeJoseError(JoseError):
        def __init__(self, error: str, description: str | None = None):
            self.error = error
            self.description = description

    def test_jose_error_handler_with_description(self):
        api = NinjaAIO()
        set_api_exception_handlers(api)
        exc = self.FakeJoseError("invalid_token", "expired")
        request = HttpRequest()
        response = api._exception_handlers[JoseError](request, exc)
        self.assertEqual(response.status_code, 401)
        self.assertIn(b"invalid_token", response.content)
        self.assertIn(b"expired", response.content)

    def test_jose_error_handler_without_description(self):
        api = NinjaAIO()
        set_api_exception_handlers(api)
        exc = self.FakeJoseError("invalid_signature", None)
        request = HttpRequest()
        response = api._exception_handlers[JoseError](request, exc)
        self.assertEqual(response.status_code, 401)
        self.assertIn(b"invalid_signature", response.content)
        self.assertNotIn(b"details", response.content)
