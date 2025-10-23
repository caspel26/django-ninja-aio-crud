# Base usage example of a JWT authentication setup with NinjaAIO.

from ninja_aio.auth import AsyncJwtBearer
from ninja_aio.models import ModelUtil
from django.conf import settings
from joserfc import jwk

from examples.ex_2.models import Customer


PUBLIC_KEY: jwk.RSAKey = settings.JWT_PUBLIC_KEY
ESSENTIAL_CLAIM = {"essential": True}
MANDATORY_CLAIMS = {
    "iat": ESSENTIAL_CLAIM,
    "exp": ESSENTIAL_CLAIM,
    "nbf": ESSENTIAL_CLAIM,
    "aud": ESSENTIAL_CLAIM,
    "sub": ESSENTIAL_CLAIM,
}


class JwtAuth(AsyncJwtBearer):
    jwt_public = PUBLIC_KEY
    claims = MANDATORY_CLAIMS

    async def auth_handler(self, request):
        try:
            request.user = await ModelUtil(Customer).get_object(
                request, self.dcd.claims.get("sub", ""), with_qs_request=False
            )
        except Customer.DoesNotExist:
            return False
        return True
