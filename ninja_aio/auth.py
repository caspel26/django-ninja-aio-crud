from joserfc import jwt, jwk, errors

from django.conf import settings
from django.http.request import HttpRequest

from ninja.security.http import HttpBearer

JWT_PUBLIC = settings.JWT_PUBLIC


class AsyncJwtBearer(HttpBearer):
    jwt_public: jwk.RSAKey
    claims: dict[str, dict]
    algorithms: list[str] = ["RS256"]

    def get_claims(self):
        return jwt.JWTClaimsRegistry(**self.claims)

    async def authenticate(self, request: HttpRequest, token: str):
        try:
            self.dcd = jwt.decode(token, self.jwt_public, algorithms=self.algorithms)
        except (
            errors.BadSignatureError,
            ValueError,
        ):
            return None

        jwt_claims = self.get_claims()

        try:
            jwt_claims.validate(self.dcd.claims)
        except (
            errors.InvalidClaimError,
            errors.MissingClaimError,
            errors.ExpiredTokenError,
        ):
            return None
