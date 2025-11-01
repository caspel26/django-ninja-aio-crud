import base64
from ipaddress import IPv4Address, IPv6Address

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
