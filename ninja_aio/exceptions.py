from functools import partial
from joserfc.errors import JoseError
from ninja import NinjaAPI
from django.http import HttpRequest, HttpResponse
from pydantic import ValidationError
from django.db.models import Model


class BaseException(Exception):
    """Base application exception carrying a serializable error payload and status code."""

    error: str | dict = ""
    status_code: int = 400

    def __init__(
        self,
        error: str | dict = None,
        status_code: int | None = None,
        details: str | None = None,
    ) -> None:
        """Initialize the exception with error content, optional HTTP status, and details.

        If `error` is a string, it is wrapped into a dict under the `error` key.
        If `error` is a dict, it is used directly. Optional `details` are merged.
        """
        if isinstance(error, str):
            self.error = {"error": error}
        if isinstance(error, dict):
            self.error = error
        self.error |= {"details": details} if details else {}
        self.status_code = status_code or self.status_code

    def get_error(self):
        """Return the error body and HTTP status code tuple for response creation."""
        return self.error, self.status_code


class SerializeError(BaseException):
    """Raised when serialization to or from request/response payloads fails."""

    pass


class AuthError(BaseException):
    """Raised when authentication or authorization fails."""

    pass


class NotFoundError(BaseException):
    """Raised when a requested model instance cannot be found."""

    status_code = 404
    error = "not found"

    def __init__(self, model: Model, details=None):
        """Build a not-found error referencing the model's verbose name."""
        super().__init__(
            error={model._meta.verbose_name.replace(" ", "_"): self.error},
            status_code=self.status_code,
            details=details,
        )


class PydanticValidationError(BaseException):
    """Wrapper for pydantic ValidationError to normalize the API error response."""

    def __init__(self, details=None):
        """Create a validation error with 400 status and provided details list."""
        super().__init__("Validation Error", 400, details)


def _default_error(
    request: HttpRequest, exc: BaseException, api: type[NinjaAPI]
) -> HttpResponse:
    """Default handler: convert BaseException to an API response."""
    return api.create_response(request, exc.error, status=exc.status_code)


def _pydantic_validation_error(
    request: HttpRequest, exc: ValidationError, api: type[NinjaAPI]
) -> HttpResponse:
    """Translate a pydantic ValidationError into a normalized API error response."""
    error = PydanticValidationError(exc.errors(include_input=False))
    return api.create_response(request, error.error, status=error.status_code)


def _jose_error(
    request: HttpRequest, exc: JoseError, api: type[NinjaAPI]
) -> HttpResponse:
    """Translate a JOSE library error into an unauthorized API response."""
    error = BaseException(**parse_jose_error(exc), status_code=401)
    return api.create_response(request, error.error, status=error.status_code)


def set_api_exception_handlers(api: type[NinjaAPI]) -> None:
    """Register exception handlers for common error types on the NinjaAPI instance."""
    api.add_exception_handler(BaseException, partial(_default_error, api=api))
    api.add_exception_handler(JoseError, partial(_jose_error, api=api))
    api.add_exception_handler(
        ValidationError, partial(_pydantic_validation_error, api=api)
    )


def parse_jose_error(jose_exc: JoseError) -> dict:
    """Extract error and optional description from a JoseError into a dict."""
    error_msg = {"error": jose_exc.error}
    return (
        error_msg | {"details": jose_exc.description}
        if jose_exc.description
        else error_msg
    )
