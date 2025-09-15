from joserfc import jwt, jwk, errors
from django.http.request import HttpRequest
from ninja.security.http import HttpBearer

from .exceptions import AuthError


class AsyncJwtBearer(HttpBearer):
    jwt_public: jwk.RSAKey
    claims: dict[str, dict]
    algorithms: list[str] = ["RS256"]

    @classmethod
    def get_claims(cls):
        return jwt.JWTClaimsRegistry(**cls.claims)

    def validate_claims(self, claims: jwt.Claims):
        jwt_claims = self.get_claims()
        jwt_claims.validate(claims)

    async def auth_handler(self, request: HttpRequest):
        """
        Override this method to make your own authentication
        """
        pass

    async def authenticate(self, request: HttpRequest, token: str):
        """
        Authenticate the request and return the user if authentication is successful.
        If authentication fails, returns false.
        """
        try:
            self.dcd = jwt.decode(token, self.jwt_public, algorithms=self.algorithms)
        except ValueError as exc:
            # raise AuthError(", ".join(exc.args), 401)
            return False

        try:
            self.validate_claims(self.dcd.claims)
        except errors.JoseError as exc:
            return False

        return await self.auth_handler(request)
