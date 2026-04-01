import datetime
import logging
from typing import Optional

from joserfc import jwt, jwk, errors
from django.http.request import HttpRequest
from django.utils import timezone
from django.conf import settings
from ninja.security.apikey import APIKeyCookie
from ninja.security.http import HttpBearer

from ninja_aio.types import JwtKeys

logger = logging.getLogger("ninja_aio.auth")

JWT_MANDATORY_CLAIMS = [
    ("iss", "JWT_ISSUER"),
    ("aud", "JWT_AUDIENCE"),
]


class JwtAuthMixin:
    """
    Mixin providing JWT decode, claim validation, and async auth dispatch.

    Subclasses must be combined with a Django Ninja auth base that provides
    the token extraction mechanism (HttpBearer, APIKeyCookie, etc.).

    Attributes:
        jwt_public (jwk.RSAKey | jwk.ECKey | jwk.OctKey):
            The public key (JWK format) used to verify the JWT signature.
            Must be set externally before authentication occurs.
        claims (dict[str, dict]):
            A mapping defining expected JWT claims passed to jwt.JWTClaimsRegistry.
            Each key corresponds to a claim name; values configure validation rules
            (e.g., {'iss': {'value': 'https://issuer.example'}}).
        algorithms (list[str]):
            List of permitted JWT algorithms for signature verification. Defaults to ["RS256"].
        dcd (jwt.Token | None):
            Set after successful decode; holds the decoded token object (assigned dynamically).
    """

    jwt_public: JwtKeys
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
            self.validate_claims(self.dcd.claims)
        except errors.JoseError as exc:
            logger.debug(f"JWT authentication failed: {exc}")
            return False

        logger.debug("JWT authentication successful")
        return await self.auth_handler(request)


class AsyncJwtBearer(JwtAuthMixin, HttpBearer):
    """
    Asynchronous JWT authentication via Authorization: Bearer header.

    Decodes and validates JWTs against a configured public key and claim registry,
    then delegates user retrieval to an overridable async handler.

    Example:
        class MyBearer(AsyncJwtBearer):
            jwt_public = jwk.RSAKey.import_key(open("pub.pem").read())
            claims = {
                "iss": {"value": "https://auth.example"},
                "aud": {"value": "my-api"},
            }
            async def auth_handler(self, request):
                sub = self.dcd.claims.get("sub")
                return await get_user_by_id(sub)
    """

    pass


class AsyncJwtCookie(JwtAuthMixin, APIKeyCookie):
    """
    Asynchronous JWT authentication via HttpOnly cookie.

    For BFF (Backend for Frontend) patterns where JWTs are stored
    in HttpOnly cookies instead of Authorization headers.
    CSRF protection is enabled by default.

    Attributes:
        param_name (str): Cookie name. Defaults to "access_token".

    Example:
        class MyCookieAuth(AsyncJwtCookie):
            jwt_public = jwk.RSAKey.import_key(open("pub.pem").read())
            claims = {
                "iss": {"value": "https://auth.example"},
                "aud": {"value": "my-api"},
            }
            async def auth_handler(self, request):
                sub = self.dcd.claims.get("sub")
                return await get_user_by_id(sub)

        # CSRF disabled (not recommended):
        auth = MyCookieAuth(csrf=False)
    """

    param_name: str = "access_token"


def validate_key(key: Optional[JwtKeys], setting_name: str) -> JwtKeys:
    if key is None:
        key = getattr(settings, setting_name, None)
    if key is None:
        raise ValueError(f"{setting_name} is required")
    if not isinstance(key, (jwk.RSAKey, jwk.ECKey, jwk.OctKey)):
        raise ValueError(
            f"{setting_name} must be an instance of jwk.RSAKey or jwk.ECKey"
        )
    return key


def validate_mandatory_claims(claims: dict) -> dict:
    for claim_key, setting_name in JWT_MANDATORY_CLAIMS:
        if claims.get(claim_key) is not None:
            continue
        value = getattr(settings, setting_name, None)
        if value is None:
            raise ValueError(f"jwt {claim_key} is required")
        claims[claim_key] = value
    return claims


def encode_jwt(
    claims: dict, duration: int, private_key: JwtKeys = None, algorithm: str = None
) -> str:
    """
    Encode and sign a JWT.

    Adds time-based claims and ensures mandatory issuer/audience:
      - iat: current time (timezone-aware)
      - nbf: current time
      - exp: current time + duration (seconds)
      - iss/aud: from claims if provided; otherwise from settings.JWT_ISSUER and settings.JWT_AUDIENCE

    Parameters:
      - claims (dict): additional claims to merge into the payload (can override defaults)
      - duration (int): token lifetime in seconds
      - private_key (jwk.RSAKey): RSA/EC JWK for signing; defaults to settings.JWT_PRIVATE_KEY
      - algorithm (str): JWS algorithm (default "RS256")

    Returns:
      - str: JWT compact string

    Raises:
      - ValueError: if private_key is missing or not jwk.RSAKey/jwk.ECKey
      - ValueError: if mandatory claims (iss, aud) are missing and not in settings

    Notes:
      - Header includes alg, typ=JWT, and kid from the private key (if available).
      - Uses timezone-aware timestamps from django.utils.timezone.
    """
    now = timezone.now()
    nbf = now
    pkey = validate_key(private_key, "JWT_PRIVATE_KEY")
    algorithm = algorithm or "RS256"
    claims = validate_mandatory_claims(claims)
    kid_h = {"kid": pkey.kid} if pkey.kid else {}
    logger.debug(f"Encoding JWT (algorithm={algorithm}, duration={duration}s)")
    return jwt.encode(
        header={"alg": algorithm, "typ": "JWT"} | kid_h,
        claims={
            "iat": now,
            "nbf": nbf,
            "exp": now + datetime.timedelta(seconds=duration),
        }
        | claims,
        key=pkey,
        algorithms=[algorithm],
    )


def decode_jwt(
    token: str,
    public_key: JwtKeys = None,
    algorithms: list[str] = None,
) -> jwt.Token:
    """
    Decode and verify a JSON Web Token (JWT) using the provided RSA public key.
    This function decodes the JWT, verifies its signature, and returns the decoded token object.
    Parameters:
    - token (str): The JWT string to decode.
    - public_key (jwk.RSAKey, optional): RSA public key used to verify the token's signature.
        If not provided, settings.JWT_PUBLIC_KEY will be used. Must be an instance of jwk.RSAKey.
    - algorithms (list[str], optional): List of permitted algorithms for signature verification.
        Defaults to ["RS256"] if not provided.
    Returns:
    - jwt.Token: The decoded JWT token object containing header and claims.
    Raises:
    - ValueError: If no public key is provided or if the provided key is not an instance of jwk.RSAKey.
    - jose.errors.JoseError: If the token is invalid or fails verification.
    Notes:
    - The function uses the specified algorithms to restrict acceptable signing methods.
    Example:
        decoded_token = decode_jwt(
            token=my_jwt,
            public_key=my_rsa_jwk,
            algorithms=["RS256"],
        )
    """
    logger.debug("Decoding JWT")
    return jwt.decode(
        token,
        validate_key(public_key, "JWT_PUBLIC_KEY"),
        algorithms=algorithms or ["RS256"],
    )


def set_jwt_cookie(
    response,
    token: str,
    cookie_name: str = "access_token",
    max_age: int = None,
    secure: bool = None,
    httponly: bool = True,
    samesite: str = "Lax",
    path: str = "/",
    domain: str = None,
):
    """
    Set a JWT as an HttpOnly cookie on a Django response.

    Pairs with AsyncJwtCookie for BFF authentication patterns.

    Parameters:
      - response: Django HttpResponse (or subclass)
      - token (str): The JWT compact string
      - cookie_name (str): Cookie name, should match AsyncJwtCookie.param_name
      - max_age (int): Cookie lifetime in seconds
      - secure (bool): HTTPS only. Defaults to ``not settings.DEBUG``
        (secure in production, permissive in development)
      - httponly (bool): Inaccessible to JavaScript. Defaults to True
      - samesite (str): SameSite policy. Defaults to "Lax"
      - path (str): Cookie path. Defaults to "/"
      - domain (str): Cookie domain. Defaults to None
    """
    if secure is None:
        secure = not settings.DEBUG
    response.set_cookie(
        key=cookie_name,
        value=token,
        max_age=max_age,
        secure=secure,
        httponly=httponly,
        samesite=samesite,
        path=path,
        domain=domain,
    )
    return response


def delete_jwt_cookie(
    response,
    cookie_name: str = "access_token",
    path: str = "/",
    domain: str = None,
):
    """
    Remove the JWT cookie from a Django response (for logout).

    Parameters:
      - response: Django HttpResponse (or subclass)
      - cookie_name (str): Cookie name, should match AsyncJwtCookie.param_name
      - path (str): Cookie path. Defaults to "/"
      - domain (str): Cookie domain. Defaults to None
    """
    response.delete_cookie(key=cookie_name, path=path, domain=domain)
    return response
