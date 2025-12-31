from django.test import TestCase, override_settings
from django.http import HttpRequest
from asgiref.sync import async_to_sync

from joserfc import jwk, errors
from ninja_aio.auth import (
    validate_key,
    validate_mandatory_claims,
    encode_jwt,
    decode_jwt,
    AsyncJwtBearer,
)


class JwtAuthTests(TestCase):
    def setUp(self):
        # Generate an RSA keypair for signing/verification
        # If your joserfc version uses a different signature, adjust "size" accordingly.
        self.private_jwk = jwk.RSAKey.generate_key(key_size=2048)
        self.private_jwk.ensure_kid()
        # Try common public conversion names to keep compatibility across joserfc versions
        self.public_jwk = getattr(self.private_jwk, "as_public_key", None)
        if callable(self.public_jwk):
            self.public_jwk = self.public_jwk()
        else:
            as_public = getattr(self.private_jwk, "as_public", None)
            self.public_jwk = as_public() if callable(as_public) else self.private_jwk
        self.public_jwk.ensure_kid()

        self._settings = override_settings(
            JWT_PRIVATE_KEY=self.private_jwk,
            JWT_PUBLIC_KEY=self.public_jwk,
            JWT_ISSUER="test-issuer",
            JWT_AUDIENCE="test-audience",
        )
        self._settings.enable()

    def tearDown(self):
        self._settings.disable()

    def test_encode_decode_roundtrip(self):
        token = encode_jwt({"sub": "u1"}, duration=60)
        dcd = decode_jwt(token)
        self.assertEqual(dcd.claims.get("sub"), "u1")
        self.assertEqual(dcd.claims.get("iss"), "test-issuer")
        self.assertEqual(dcd.claims.get("aud"), "test-audience")
        # time-based claims present and consistent
        self.assertIn("iat", dcd.claims)
        self.assertIn("nbf", dcd.claims)
        self.assertIn("exp", dcd.claims)
        self.assertTrue(dcd.claims["exp"] > dcd.claims["iat"])

    def test_decode_with_wrong_key_fails(self):
        other_key = jwk.RSAKey.generate_key(key_size=2048)
        token = encode_jwt({"sub": "u1"}, duration=60)
        with self.assertRaises(errors.JoseError):
            decode_jwt(token, public_key=other_key)

    def test_validate_key(self):
        # Accepts a valid key instance
        self.assertIs(validate_key(self.public_jwk, "JWT_PUBLIC_KEY"), self.public_jwk)
        # Rejects invalid type
        with self.assertRaises(ValueError):
            validate_key("not-a-key", "JWT_PUBLIC_KEY")
        # Missing setting raises
        ctx = override_settings(JWT_PUBLIC_KEY=None)
        ctx.enable()
        try:
            with self.assertRaises(ValueError):
                validate_key(None, "JWT_PUBLIC_KEY")
        finally:
            ctx.disable()

    def test_validate_mandatory_claims_uses_settings(self):
        claims = validate_mandatory_claims({})
        self.assertEqual(claims["iss"], "test-issuer")
        self.assertEqual(claims["aud"], "test-audience")

    def test_validate_mandatory_claims_missing_settings_raises(self):
        ctx = override_settings(JWT_ISSUER=None, JWT_AUDIENCE=None)
        ctx.enable()
        try:
            with self.assertRaises(ValueError):
                validate_mandatory_claims({})
        finally:
            ctx.disable()

    def test_async_bearer_authenticate_success(self):
        token = encode_jwt({"sub": "42"}, duration=60)
        pub = self.public_jwk

        class TB(AsyncJwtBearer):
            jwt_public = pub
            claims = {
                "iss": {"value": "test-issuer"},
                "aud": {"value": "test-audience"},
            }

            async def auth_handler(self, request):
                # Return something derived from validated claims
                return self.dcd.claims.get("sub")

        bearer = TB()
        result = async_to_sync(bearer.authenticate)(HttpRequest(), token)
        self.assertEqual(result, "42")

    def test_async_bearer_authenticate_invalid_claims_returns_false(self):
        token = encode_jwt({"sub": "42"}, duration=60)
        pub = self.public_jwk

        class TBWrongAud(AsyncJwtBearer):
            jwt_public = pub
            # Force a mismatch to trigger claim validation failure
            claims = {
                "iss": {"value": "test-issuer"},
                "aud": {"value": "wrong-audience"},
            }

            async def auth_handler(self, request):
                return "should-not-happen"

        bearer = TBWrongAud()
        result = async_to_sync(bearer.authenticate)(HttpRequest(), token)
        self.assertFalse(result)
