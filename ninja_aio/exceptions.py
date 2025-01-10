from functools import partial

from joserfc.errors import JoseError
from ninja import NinjaAPI
from django.http import HttpRequest, HttpResponse


class BaseException(Exception):
    error: str | dict = ""
    status_code: int = 400

    def __init__(
        self,
        error: str | dict = None,
        status_code: int | None = None,
        is_critical: bool = False,
    ) -> None:
        self.error = error or self.error
        self.status_code = status_code or self.status_code
        self.is_critical = is_critical

    def get_error(self):
        return self.error, self.status_code


class SerializeError(BaseException):
    pass


class AuthError(BaseException):
    pass


def _default_error(
    request: HttpRequest, exc: BaseException, api: type[NinjaAPI]
) -> HttpResponse:
    return api.create_response(request, exc.error, status=exc.status_code)


def set_api_exception_handlers(api: type[NinjaAPI]) -> None:
    api.add_exception_handler(BaseException, partial(_default_error, api=api))


def parse_jose_error(jose_exc: JoseError) -> dict:
    error_msg = {"error": jose_exc.error}
    return (
        error_msg | {"details": jose_exc.description}
        if jose_exc.description
        else error_msg
    )
