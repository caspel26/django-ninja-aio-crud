import orjson
from ninja.parser import Parser


class ORJSONParser(Parser):
    def parse_body(self, request):
        return orjson.loads(request.body)
