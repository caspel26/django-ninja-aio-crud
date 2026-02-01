import base64
from ipaddress import IPv4Address, IPv6Address

from django.http import HttpResponse, StreamingHttpResponse
from django.test import TestCase, tag
import orjson
from ninja_aio.renders import ORJSONRenderer
from ninja_aio.parsers import ORJSONParser


class DummyRequest:
    def __init__(self, body: bytes = b"{}") -> None:
        self.body = body


@tag("renderer_parser")
class ORJSONRendererParserTestCase(TestCase):
    def setUp(self):
        self.renderer = ORJSONRenderer()
        self.parser = ORJSONParser()

    def test_parser(self):
        payload = {"a": 1, "b": [1, 2, 3], "c": {"d": "x"}}
        request = DummyRequest(orjson.dumps(payload))
        parsed = self.parser.parse_body(request)
        self.assertEqual(parsed, payload)

    def test_renderer_transformations(self):
        data = {
            "bytes": b"test-bytes",
            "ip_list": [IPv4Address("127.0.0.1"), IPv6Address("::1")],
            "nested": {"inner_bytes": b"nested-bytes", "list": [b"a", b"b"]},
            "plain": "value",
        }
        rendered = self.renderer.render(DummyRequest(), data, response_status=200)
        # Decode back to python
        decoded = orjson.loads(rendered)
        # bytes should be base64 encoded

        self.assertEqual(decoded["bytes"], base64.b64encode(b"test-bytes").decode())
        # ip addresses stringified
        self.assertEqual(decoded["ip_list"], ["127.0.0.1", "::1"])
        # nested bytes transformed
        self.assertEqual(
            decoded["nested"]["inner_bytes"], base64.b64encode(b"nested-bytes").decode()
        )
        self.assertEqual(
            decoded["nested"]["list"],
            [base64.b64encode(b"a").decode(), base64.b64encode(b"b").decode()],
        )
        self.assertEqual(decoded["plain"], "value")

    def test_renderer_non_dict_data(self):
        """Test that renderer handles non-dict data (covers lines 23-24)."""
        # When data is not a dict, it triggers the AttributeError branch
        # and falls back to self.dumps(data)
        non_dict_data = "plain string"
        rendered = self.renderer.render(DummyRequest(), non_dict_data, response_status=200)
        decoded = orjson.loads(rendered)
        self.assertEqual(decoded, "plain string")

    def test_renderer_list_data(self):
        """Test that renderer handles list data directly."""
        # A list doesn't have .items() method
        list_data = [1, 2, 3]
        rendered = self.renderer.render(DummyRequest(), list_data, response_status=200)
        decoded = orjson.loads(rendered)
        self.assertEqual(decoded, [1, 2, 3])

    def test_renderer_primitive_data(self):
        """Test that renderer handles primitive data."""
        # An integer doesn't have .items() method
        int_data = 42
        rendered = self.renderer.render(DummyRequest(), int_data, response_status=200)
        decoded = orjson.loads(rendered)
        self.assertEqual(decoded, 42)

    def test_renderer_http_response_passthrough(self):
        """Test that renderer returns HttpResponse as-is without serialization."""
        response = HttpResponse(
            b"-----BEGIN PUBLIC KEY-----\ntest\n-----END PUBLIC KEY-----",
            content_type="application/x-pem-file",
            status=200,
        )
        rendered = self.renderer.render(DummyRequest(), response, response_status=200)
        self.assertIs(rendered, response)
        self.assertEqual(rendered.content, b"-----BEGIN PUBLIC KEY-----\ntest\n-----END PUBLIC KEY-----")
        self.assertEqual(rendered["Content-Type"], "application/x-pem-file")

    def test_renderer_streaming_http_response_passthrough(self):
        """Test that renderer returns StreamingHttpResponse as-is."""
        response = StreamingHttpResponse(
            iter([b"chunk1", b"chunk2"]),
            content_type="application/octet-stream",
        )
        rendered = self.renderer.render(DummyRequest(), response, response_status=200)
        self.assertIs(rendered, response)
        self.assertEqual(rendered["Content-Type"], "application/octet-stream")
