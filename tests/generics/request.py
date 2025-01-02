from django.test.client import AsyncRequestFactory


class Request:
    def __init__(self, path: str) -> None:
        self.afactory = AsyncRequestFactory()
        self.path = path

    def get(self, path: str = None):
        return self.afactory.get(path or self.path)

    def post(self, path: str = None, body: dict = None):
        return self.afactory.post(path or self.path, body or {})

    def patch(self, path: str = None, body: dict = None):
        return self.afactory.patch(path or self.path, body or {})

    def delete(self, path: str = None):
        return self.afactory.delete(path or self.path)
