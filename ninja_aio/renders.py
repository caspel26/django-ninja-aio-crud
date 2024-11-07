import base64

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
    def parse_data(cls, data: dict):
        for k, v in data.items():
            if isinstance(v, bytes):
                data |= {k: base64.b64encode(v).decode()}
            if isinstance(v, dict):
                for k_rel, v_rel in v.items():
                    if not isinstance(v_rel, bytes):
                        continue
                    v |= {k_rel: base64.b64encode(v_rel).decode()}
                data |= {k: v}
            if isinstance(v, list):
                for index_rel, f_rel in enumerate(v):
                    for k_rel, v_rel in f_rel.items():
                        if isinstance(v_rel, bytes):
                            v[index_rel] |= {k_rel: base64.b64encode(v_rel).decode()}
                data |= {k: v}
        return data
