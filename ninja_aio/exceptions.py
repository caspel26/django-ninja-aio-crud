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
