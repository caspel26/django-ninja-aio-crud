from joserfc import jwt, jwk, errors
from django.http.request import HttpRequest
from ninja.security.http import HttpBearer

from .exceptions import AuthError


class AsyncJwtBearer(HttpBearer):
    """
    AsyncJwtBearer provides asynchronous JWT-based authentication for Django Ninja endpoints
    using HTTP Bearer tokens. It decodes and validates JWTs against a configured public key
    and claim registry, then delegates user retrieval to an overridable async handler.
    Attributes:
        jwt_public (jwk.RSAKey):
            The RSA public key (JWK format) used to verify the JWT signature.
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
