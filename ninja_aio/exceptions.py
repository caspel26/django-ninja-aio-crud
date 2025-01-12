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
        details: str | None = None,
    ) -> None:
        if isinstance(error, str):
            self.error = {"error": error}
        if isinstance(error, dict):
            self.error = error
        self.error |= {"details": details} if details else {}
        self.status_code = status_code or self.status_code

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
