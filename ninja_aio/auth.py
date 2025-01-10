from joserfc import jwt, jwk, errors
from django.http.request import HttpRequest
from ninja.security.http import HttpBearer

from .exceptions import AuthError, parse_jose_error


class AsyncJwtBearer(HttpBearer):
    jwt_public: jwk.RSAKey
    claims: dict[str, dict]
    algorithms: list[str] = ["RS256"]

    @classmethod
    def get_claims(cls):
        return jwt.JWTClaimsRegistry(**cls.claims)

    def validate_claims(self, claims: jwt.Claims):
        jwt_claims = self.get_claims()

        try:
            jwt_claims.validate(claims)
        except (
            errors.InvalidClaimError,
            errors.MissingClaimError,
            errors.ExpiredTokenError,
        ) as exc:
            raise AuthError(**parse_jose_error(exc), status_code=401)

    async def auth_handler(self, request: HttpRequest):
        """
        Override this method to make your own authentication
        """
        pass

    async def authenticate(self, request: HttpRequest, token: str):
        try:
            self.dcd = jwt.decode(token, self.jwt_public, algorithms=self.algorithms)
        except errors.BadSignatureError as exc:
            raise AuthError(**parse_jose_error(exc), status_code=401)
        except ValueError as exc:
            raise AuthError(", ".join(exc.args), 401)

        self.validate_claims(self.dcd.claims)

        return await self.auth_handler(request)
