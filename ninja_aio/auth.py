import datetime
from typing import Optional

from joserfc import jwt, jwk, errors
from django.http.request import HttpRequest
from django.utils import timezone
from django.conf import settings
from ninja.security.http import HttpBearer

from ninja_aio.types import JwtKeys

JWT_MANDATORY_CLAIMS = [
    ("iss", "JWT_ISSUER"),
    ("aud", "JWT_AUDIENCE"),
]


class AsyncJwtBearer(HttpBearer):
    """
    AsyncJwtBearer provides asynchronous JWT-based authentication for Django Ninja endpoints
    using HTTP Bearer tokens. It decodes and validates JWTs against a configured public key
    and claim registry, then delegates user retrieval to an overridable async handler.
    Attributes:
        jwt_public (jwk.RSAKey | jwk.ECKey):
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
    Class Methods:
        get_claims() -> jwt.JWTClaimsRegistry:
            Constructs and returns a claims registry from the class-level claims definition.
    Instance Methods:
        validate_claims(claims: jwt.Claims) -> None:
            Validates the provided claims object against the registry. Raises jose.errors.JoseError
            or ValueError-derived exceptions if validation fails.
        auth_handler(request: HttpRequest) -> Any:
            Asynchronous hook to be overridden by subclasses to implement application-specific
            user resolution (e.g., fetching a user model instance). Must return a user-like object
            on success or raise / return False on failure.
        authenticate(request: HttpRequest, token: str) -> Any | bool:
            Orchestrates authentication:
                1. Attempts to decode the JWT using the configured public key and algorithms.
                2. Validates claims via validate_claims.
                3. Delegates to auth_handler for domain-specific user retrieval.
            Returns the user object on success; returns False if decoding or claim validation fails.
    Usage Notes:
        - You must assign jwt_public (jwk.RSAKey) and populate claims before calling authenticate.
        - Override auth_handler to integrate with your user persistence layer.
        - Token decoding failures (e.g., signature mismatch, malformed token) result in False.
        - Claim validation errors (e.g., expired token, issuer mismatch) result in False.
        - This class does not itself raise HTTP errors; caller may translate False into an HTTP response.
    Example Extension:
        class MyBearer(AsyncJwtBearer):
            jwt_public = jwk.RSAKey.import_key(open("pub.pem").read())
            claims = {
                "iss": {"value": "https://auth.example"},
                "aud": {"value": "my-api"},
            }
            async def auth_handler(self, request):
                sub = self.dcd.claims.get("sub")
                return await get_user_by_id(sub)
    Thread Safety:
        - Instances are not inherently thread-safe if mutable shared state is attached.
        - Prefer per-request instantiation or ensure read-only shared configuration.
    Security Considerations:
        - Ensure jwt_public key rotation strategy is in place.
        - Validate critical claims (exp, nbf, iss, aud) via the claims registry configuration.
        - Avoid logging raw tokens or sensitive claim contents.
    Raises:
        jose.errors.JoseError:
            Propagated from validate_claims if claim checks fail.
        ValueError:
            May occur during token decoding (e.g., invalid structure) but is internally caught
            and converted to a False return value.
    Return Semantics:
        - authenticate -> user object (success) | False (failure)
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
        except ValueError:
            # raise AuthError(", ".join(exc.args), 401)
            return False

        try:
            self.validate_claims(self.dcd.claims)
        except errors.JoseError:
            return False

        return await self.auth_handler(request)


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
    return jwt.decode(
        token,
        validate_key(public_key, "JWT_PUBLIC_KEY"),
        algorithms=algorithms or ["RS256"],
    )
