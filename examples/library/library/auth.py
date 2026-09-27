from django.conf import settings

from ninja_aio.auth import AsyncJwtBearer, AsyncJwtCookie

from .models import Member

CLAIMS = {
    "iss": {"essential": True, "value": settings.JWT_ISSUER},
    "aud": {"essential": True, "value": settings.JWT_AUDIENCE},
    "sub": {"essential": True},
}


class MemberLookup:
    claims = CLAIMS

    async def auth_handler(self, request):
        return await (
            Member.objects.select_related("user")
            .filter(user_id=self.dcd.claims["sub"], user__is_active=True)
            .afirst()
        )


class BearerAuth(MemberLookup, AsyncJwtBearer):
    """``Authorization: Bearer <token>``."""


class CookieAuth(MemberLookup, AsyncJwtCookie):
    """The ``access_token`` cookie set by ``POST /auth/login``, with CSRF checks."""


AUTH = [BearerAuth(), CookieAuth()]
