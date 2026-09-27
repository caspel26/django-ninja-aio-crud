import ast
from contextlib import contextmanager
import sys
from types import ModuleType
from unittest.mock import patch
from uuid import uuid4

from asgiref.sync import async_to_sync
from django.test import SimpleTestCase, TestCase
from ninja import Schema
from ninja.testing import TestAsyncClient, TestClient
from ninja_aio import APIViewSet, NinjaAIO

from examples import ROOT, blocks
from docs_quick_app import models as quick_models
from docs_model_app import models as tutorial_models
from docs_plain_app import models as plain_models


@contextmanager
def blog_modules(models):
    blog = ModuleType("blog")
    blog.__path__ = []
    blog.models = models
    with patch.dict(sys.modules, {"blog": blog, "blog.models": models}):
        yield


def execute(path, index, namespace):
    example = blocks(path)[index]
    code = compile(example.code, example.filename, "exec", flags=ast.PyCF_ALLOW_TOP_LEVEL_AWAIT)
    result = eval(code, namespace)
    if result is not None:
        async def finish():
            await result
        async_to_sync(finish)()


class DocumentationSyntaxTests(SimpleTestCase):
    def test_every_public_python_block_compiles(self):
        count = 0
        for path in sorted((ROOT / "docs").rglob("*.md")):
            for example in blocks(path):
                with self.subTest(example=example.filename):
                    compile(example.code, example.filename, "exec", flags=ast.PyCF_ALLOW_TOP_LEVEL_AWAIT)
                    count += 1
        self.assertGreater(count, 300)


class DocumentationRuntimeTests(TestCase):
    def namespace(self, models):
        return {"__name__": "blog.api", "__package__": "blog", "Article": models.Article,
                "api": NinjaAIO(urls_namespace=f"docs_{uuid4().hex}"), "APIViewSet": APIViewSet, "Schema": Schema}

    def test_quick_start_python_snippets_run_in_both_modes(self):
        for index in (4, 5):
            with self.subTest(block=index), blog_modules(quick_models):
                namespace = self.namespace(quick_models)
                execute("docs/getting_started/quick_start.md", index, namespace)
                self.assertTrue(namespace["data"]["is_published"])
                self.assertEqual(namespace["data"]["title"], "Draft")

    def test_quick_start_http_api_and_urls(self):
        with blog_modules(quick_models):
            namespace = self.namespace(quick_models)
            execute("docs/getting_started/quick_start.md", 1, namespace)
            namespace["api"].urls_namespace = f"docs_quick_{uuid4().hex}"
            module = ModuleType("blog.api")
            module.api = namespace["api"]
            with patch.dict(sys.modules, {"blog.api": module}):
                urls = {}
                execute("docs/getting_started/quick_start.md", 2, urls)
                self.assertEqual(len(urls["urlpatterns"]), 1)
            client = TestAsyncClient(namespace["api"])
            async def exercise():
                response = await client.post("/articles/", json={"title": "Hello", "body": "My first article"})
                self.assertEqual(response.status_code, 201, response.content)
                pk = response.json()["id"]
                listing = await client.get("/articles")
                self.assertEqual(listing.json()["count"], 1)
                patch_response = await client.patch(f"/articles/{pk}/", json={"is_published": True})
                self.assertTrue(patch_response.json()["is_published"])
                self.assertEqual(patch_response.json()["body"], "My first article")
                self.assertEqual((await client.delete(f"/articles/{pk}/")).status_code, 204)
            async_to_sync(exercise)()

    def test_tutorial_model_and_standalone_serializer_examples(self):
        with blog_modules(plain_models):
            namespace = self.namespace(plain_models)
            namespace.update(__name__="blog.serializers")
            execute("docs/tutorial/model.md", 2, namespace)
            serializer = namespace["ArticleSerializer"]
            for facade in (tutorial_models.Article, serializer):
                for create, dump in ((facade.create, facade.model_dump), (async_to_sync(facade.acreate), async_to_sync(facade.amodel_dump))):
                    instance = create({"title": "Documented", "body": "Example"})
                    data = dump(instance)
                    self.assertEqual(data["body"], "Example")
                    self.assertEqual(data["views"], 0)
            namespace["__name__"] = "blog.api"
            execute("docs/getting_started/choosing-a-serializer.md", 4, namespace)
            self.assertIs(namespace["ArticleViewSet"].serializer_class, serializer)

    def test_tutorial_publish_action_snippets_in_both_modes(self):
        for index, client_type in ((3, TestClient), (4, TestAsyncClient)):
            with self.subTest(block=index), blog_modules(tutorial_models):
                namespace = self.namespace(tutorial_models)
                execute("docs/tutorial/crud.md", index, namespace)
                obj = tutorial_models.Article.create({"title": "Draft", "body": "Text"})
                client = client_type(namespace["api"])
                if client_type is TestAsyncClient:
                    response = async_to_sync(client.post)(f"/articles/{obj.pk}/publish")
                else:
                    response = client.post(f"/articles/{obj.pk}/publish")
                self.assertEqual(response.status_code, 200, response.content)
                self.assertTrue(response.json()["is_published"])
                obj.refresh_from_db()
                self.assertTrue(obj.is_published)
