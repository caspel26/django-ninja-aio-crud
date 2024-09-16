from joserfc import jwt, jwk, errors

from django.conf import settings
from django.http.request import HttpRequest
from django.contrib.auth.models import User

from ninja.security.http import HttpBearer

JWT_PUBLIC = settings.JWT_PUBLIC


class AsyncJwtBearer(HttpBearer):
    jwt_public: jwk.RSAKey
    claims: dict[str, dict]

    def get_claims(self):
       return jwt.JWTClaimsRegistry(**self.claims)  

    async def authenticate(self, request: HttpRequest, token: str) -> User | None:
        try:
            dcd = jwt.decode(token, self.jwt_public, algorithms=["RS256"])
        except (
            errors.BadSignatureError,
            ValueError,
        ):
            return None

        jwt_claims = self.get_claims()

        try:
            jwt_claims.validate(dcd.claims)
        except (
            errors.InvalidClaimError,
            errors.MissingClaimError,
            errors.ExpiredTokenError,
        ):
            return None