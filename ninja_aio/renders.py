import base64
from ipaddress import IPv4Address, IPv6Address
from typing import Any

import orjson
from django.http import HttpRequest
from ninja.renderers import BaseRenderer


class ORJSONRenderer(BaseRenderer):
    media_type = "application/json"

    def render(self, request: HttpRequest, data: dict, *, response_status):
        try:
            old_d = data
            for k, v in old_d.items():
                if isinstance(v, list):
                    data |= {k: self.render_list(v)}
            return orjson.dumps(self.render_dict(data))
        except AttributeError:
            return orjson.dumps(data)

    @classmethod
    def render_list(cls, data: list[dict]) -> list[dict]:
        return [cls.parse_data(d) for d in data]

    @classmethod
    def render_dict(cls, data: dict):
        return cls.parse_data(data)

    @classmethod
    def transform(cls, value):
        if isinstance(value, bytes):
            return base64.b64encode(value).decode()
        if isinstance(value, (IPv4Address, IPv6Address)):
            return str(value)
        if isinstance(value, dict):
            return {k: cls.transform(v) for k, v in value.items()}
        if isinstance(value, list):
            return [cls.transform(item) for item in value]
        return value

    @classmethod
    def parse_data(cls, data: dict | Any):
        if not isinstance(data, dict):
            return cls.transform(data)
        return {k: cls.transform(v) for k, v in data.items()}
