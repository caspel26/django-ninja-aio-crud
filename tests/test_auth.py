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
    AsyncJwtCookie,
    set_jwt_cookie,
    delete_jwt_cookie,
)


class JwtTestBase(TestCase):
    """Shared setUp/tearDown for JWT auth tests."""

    def setUp(self):
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


class JwtAuthTests(JwtTestBase):

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

    def test_async_bearer_authenticate_invalid_token_returns_false(self):
        pub = self.public_jwk

        class TB(AsyncJwtBearer):
            jwt_public = pub
            claims = {
                "iss": {"value": "test-issuer"},
                "aud": {"value": "test-audience"},
            }

            async def auth_handler(self, request):
                return "should-not-happen"

        bearer = TB()

        import unittest.mock as mock

        with mock.patch("ninja_aio.auth.jwt.decode") as mock_decode:
            mock_decode.side_effect = errors.JoseError("invalid token")
            result = async_to_sync(bearer.authenticate)(HttpRequest(), "fake-token")
            self.assertFalse(result)

    def test_async_bearer_base_auth_handler_returns_none(self):
        """Test that the base auth_handler returns None (covers line 101)."""
        pub = self.public_jwk

        class TB(AsyncJwtBearer):
            jwt_public = pub
            claims = {
                "iss": {"value": "test-issuer"},
                "aud": {"value": "test-audience"},
            }
            # Don't override auth_handler, use base implementation

        token = encode_jwt({"sub": "42"}, duration=60)
        bearer = TB()
        result = async_to_sync(bearer.authenticate)(HttpRequest(), token)
        # Base auth_handler returns None (pass statement)
        self.assertIsNone(result)

    def test_validate_mandatory_claims_skips_preset_claims(self):
        """Test that validate_mandatory_claims skips claims already present (covers line 137)."""
        # Pre-set both mandatory claims
        claims = {"iss": "custom-issuer", "aud": "custom-audience"}
        result = validate_mandatory_claims(claims)
        # Should keep the pre-set values, not override with settings
        self.assertEqual(result["iss"], "custom-issuer")
        self.assertEqual(result["aud"], "custom-audience")


class JwtCookieAuthTests(JwtTestBase):

    def test_async_cookie_authenticate_success(self):
        token = encode_jwt({"sub": "42"}, duration=60)
        pub = self.public_jwk

        class TC(AsyncJwtCookie):
            jwt_public = pub
            claims = {
                "iss": {"value": "test-issuer"},
                "aud": {"value": "test-audience"},
            }

            async def auth_handler(self, request):
                return self.dcd.claims.get("sub")

        cookie_auth = TC()
        result = async_to_sync(cookie_auth.authenticate)(HttpRequest(), token)
        self.assertEqual(result, "42")

    def test_async_cookie_authenticate_invalid_claims_returns_false(self):
        token = encode_jwt({"sub": "42"}, duration=60)
        pub = self.public_jwk

        class TC(AsyncJwtCookie):
            jwt_public = pub
            claims = {
                "iss": {"value": "test-issuer"},
                "aud": {"value": "wrong-audience"},
            }

            async def auth_handler(self, request):
                return "should-not-happen"

        cookie_auth = TC()
        result = async_to_sync(cookie_auth.authenticate)(HttpRequest(), token)
        self.assertFalse(result)

    def test_async_cookie_authenticate_invalid_token_returns_false(self):
        pub = self.public_jwk

        class TC(AsyncJwtCookie):
            jwt_public = pub
            claims = {
                "iss": {"value": "test-issuer"},
                "aud": {"value": "test-audience"},
            }

            async def auth_handler(self, request):
                return "should-not-happen"

        cookie_auth = TC()

        import unittest.mock as mock

        with mock.patch("ninja_aio.auth.jwt.decode") as mock_decode:
            mock_decode.side_effect = errors.JoseError("invalid token")
            result = async_to_sync(cookie_auth.authenticate)(
                HttpRequest(), "fake-token"
            )
            self.assertFalse(result)

    def test_async_cookie_base_auth_handler_returns_none(self):
        pub = self.public_jwk

        class TC(AsyncJwtCookie):
            jwt_public = pub
            claims = {
                "iss": {"value": "test-issuer"},
                "aud": {"value": "test-audience"},
            }

        token = encode_jwt({"sub": "42"}, duration=60)
        cookie_auth = TC()
        result = async_to_sync(cookie_auth.authenticate)(HttpRequest(), token)
        self.assertIsNone(result)

    def test_async_cookie_authenticate_missing_token_returns_false(self):
        pub = self.public_jwk

        class TC(AsyncJwtCookie):
            jwt_public = pub
            claims = {
                "iss": {"value": "test-issuer"},
                "aud": {"value": "test-audience"},
            }

        cookie_auth = TC()
        result = async_to_sync(cookie_auth.authenticate)(HttpRequest(), None)
        self.assertFalse(result)

    def test_async_cookie_custom_param_name(self):
        pub = self.public_jwk

        class TC(AsyncJwtCookie):
            jwt_public = pub
            param_name = "my_jwt"
            claims = {
                "iss": {"value": "test-issuer"},
                "aud": {"value": "test-audience"},
            }

        cookie_auth = TC()
        self.assertEqual(cookie_auth.param_name, "my_jwt")

    def test_async_cookie_default_param_name(self):
        pub = self.public_jwk

        class TC(AsyncJwtCookie):
            jwt_public = pub
            claims = {
                "iss": {"value": "test-issuer"},
                "aud": {"value": "test-audience"},
            }

        cookie_auth = TC()
        self.assertEqual(cookie_auth.param_name, "access_token")

    def test_async_cookie_csrf_enabled_by_default(self):
        pub = self.public_jwk

        class TC(AsyncJwtCookie):
            jwt_public = pub
            claims = {
                "iss": {"value": "test-issuer"},
                "aud": {"value": "test-audience"},
            }

        cookie_auth = TC()
        self.assertTrue(cookie_auth.csrf)

    def test_async_cookie_csrf_can_be_disabled(self):
        pub = self.public_jwk

        class TC(AsyncJwtCookie):
            jwt_public = pub
            claims = {
                "iss": {"value": "test-issuer"},
                "aud": {"value": "test-audience"},
            }

        cookie_auth = TC(csrf=False)
        self.assertFalse(cookie_auth.csrf)

    def test_async_cookie_missing_cookie_skips_csrf(self):
        """No cookie present should return None without CSRF error."""
        pub = self.public_jwk

        class TC(AsyncJwtCookie):
            jwt_public = pub
            claims = {
                "iss": {"value": "test-issuer"},
                "aud": {"value": "test-audience"},
            }

        cookie_auth = TC()
        request = HttpRequest()
        # No cookie set, no CSRF token — should not raise 403
        key = cookie_auth._get_key(request)
        self.assertIsNone(key)

    def test_async_cookie_present_without_csrf_raises_403(self):
        """Cookie present but no CSRF token should raise 403."""
        from ninja.errors import HttpError

        pub = self.public_jwk

        class TC(AsyncJwtCookie):
            jwt_public = pub
            claims = {
                "iss": {"value": "test-issuer"},
                "aud": {"value": "test-audience"},
            }

        cookie_auth = TC()
        request = HttpRequest()
        request.COOKIES["access_token"] = "some.jwt.token"
        request.META["REQUEST_METHOD"] = "POST"
        with self.assertRaises(HttpError) as ctx:
            cookie_auth._get_key(request)
        self.assertEqual(ctx.exception.status_code, 403)

    def test_async_cookie_csrf_disabled_skips_check(self):
        """With csrf=False, cookie present without CSRF token should not raise."""
        pub = self.public_jwk

        class TC(AsyncJwtCookie):
            jwt_public = pub
            claims = {
                "iss": {"value": "test-issuer"},
                "aud": {"value": "test-audience"},
            }

        cookie_auth = TC(csrf=False)
        request = HttpRequest()
        request.COOKIES["access_token"] = "some.jwt.token"
        request.META["REQUEST_METHOD"] = "POST"
        key = cookie_auth._get_key(request)
        self.assertEqual(key, "some.jwt.token")


class JwtCookieHelperTests(TestCase):
    def test_set_jwt_cookie_defaults_production(self):
        """secure defaults to True when DEBUG=False."""
        from django.http import HttpResponse

        with self.settings(DEBUG=False):
            response = HttpResponse()
            result = set_jwt_cookie(response, "my.jwt.token")
            self.assertIs(result, response)
            cookie = response.cookies["access_token"]
            self.assertEqual(cookie.value, "my.jwt.token")
            self.assertTrue(cookie["httponly"])
            self.assertTrue(cookie["secure"])
            self.assertEqual(cookie["samesite"], "Lax")
            self.assertEqual(cookie["path"], "/")

    def test_set_jwt_cookie_defaults_development(self):
        """secure defaults to False when DEBUG=True."""
        from django.http import HttpResponse

        with self.settings(DEBUG=True):
            response = HttpResponse()
            set_jwt_cookie(response, "my.jwt.token")
            cookie = response.cookies["access_token"]
            self.assertEqual(cookie["secure"], "")

    def test_set_jwt_cookie_custom_params(self):
        from django.http import HttpResponse

        response = HttpResponse()
        set_jwt_cookie(
            response,
            "my.jwt.token",
            cookie_name="session_jwt",
            max_age=3600,
            secure=False,
            httponly=False,
            samesite="Strict",
            path="/api",
            domain="example.com",
        )
        cookie = response.cookies["session_jwt"]
        self.assertEqual(cookie.value, "my.jwt.token")
        self.assertEqual(cookie["max-age"], 3600)
        self.assertEqual(cookie["samesite"], "Strict")
        self.assertEqual(cookie["path"], "/api")
        self.assertEqual(cookie["domain"], "example.com")

    def test_delete_jwt_cookie(self):
        from django.http import HttpResponse

        response = HttpResponse()
        response.set_cookie("access_token", "my.jwt.token")
        result = delete_jwt_cookie(response)
        self.assertIs(result, response)
        cookie = response.cookies["access_token"]
        self.assertEqual(cookie["max-age"], 0)

    def test_delete_jwt_cookie_custom_name(self):
        from django.http import HttpResponse

        response = HttpResponse()
        response.set_cookie("my_token", "my.jwt.token")
        delete_jwt_cookie(response, cookie_name="my_token")
        cookie = response.cookies["my_token"]
        self.assertEqual(cookie["max-age"], 0)
