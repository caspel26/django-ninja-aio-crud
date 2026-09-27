"""Run with each checkout's Python; print comparable timings and query counts."""
# ruff: noqa: E402 — Django must initialize before importing model modules.
import argparse
import gc
import importlib.metadata
import json
import os
import platform
import statistics
import time
import warnings

warnings.filterwarnings("ignore", category=DeprecationWarning)
from django.conf import settings

database = {"ENGINE": "django.db.backends.sqlite3", "NAME": ":memory:"}
if os.environ.get("BENCHMARK_PGDATABASE"):
    database = {"ENGINE": "django.db.backends.postgresql", "NAME": os.environ["BENCHMARK_PGDATABASE"],
                "USER": os.environ.get("PGUSER", "postgres"), "PASSWORD": os.environ.get("PGPASSWORD", ""),
                "HOST": os.environ.get("PGHOST", "127.0.0.1"), "PORT": os.environ.get("PGPORT", "5432")}
settings.configure(SECRET_KEY="benchmark", INSTALLED_APPS=["django.contrib.auth", "django.contrib.contenttypes", "ninja_aio", "v3_benchmark_app"],
                   DATABASES={"default": database},
                   DEFAULT_AUTO_FIELD="django.db.models.BigAutoField")
import django

django.setup()
from asgiref.sync import async_to_sync
from django.db import connection
from django.test import RequestFactory
from django.test.utils import CaptureQueriesContext
import ninja_aio
from ninja_aio.models import ModelUtil
from ninja_aio.schemas import ObjectQuerySchema
from ninja.orm.factory import factory
from v3_benchmark_app.models import Author, Book, Simple, Tag

V3 = hasattr(Simple, "amodel_dumps")
request = RequestFactory().get("/benchmark/")
request.auth = None
with connection.schema_editor() as editor:
    for model in (Author, Tag, Book, Simple):
        editor.create_model(model)
author = Author.objects.create(name="Writer")
tags = [Tag.objects.create(name=f"tag-{i}") for i in range(3)]
books = Book.objects.bulk_create([Book(title=f"Book {i}", author=author) for i in range(500)])
Book.tags.through.objects.bulk_create([Book.tags.through(book_id=book.pk, tag_id=tag.pk) for book in books for tag in tags])
read_schema = Book.read_schema if V3 else Book.generate_read_s()
create_schema = Simple.create_schema if V3 else Simple.generate_create_s()
book_util, simple_util = ModelUtil(Book), ModelUtil(Simple)


def warm_schema():
    return Simple.create_schema if V3 else Simple.generate_create_s()


def cold_schema(model=Simple):
    factory.schemas.clear()
    factory.schema_names.clear()
    if V3:
        model.clear_schema_cache()
        Author.clear_schema_cache()
        return model.create_schema
    model.generate_create_s.cache_clear()
    Author.generate_related_s.cache_clear()
    return model.generate_create_s()


async def single_read():
    if V3:
        book = await Book.aget(books[0].pk, optimize_for="read")
        result = await Book.amodel_dump(book, schema=read_schema)
    else:
        result = await book_util.read_s(read_schema, request, query_data=ObjectQuerySchema(getters={"id": books[0].pk}), is_for="read")
    assert result["title"] == "Book 0" and len(result["tags"]) == 3
    return result


def batch_read(size):
    async def read():
        queryset = Book.objects.order_by("pk").select_related("author").prefetch_related("tags")[:size]
        result = await Book.amodel_dumps(queryset, schema=read_schema) if V3 else await book_util.list_read_s(read_schema, request, queryset, is_for="read")
        assert len(result) == size and all(len(item["tags"]) == 3 for item in result)
        return result
    return read


async def bulk_write():
    data = [{"title": f"bulk-{i}"} for i in range(100)]
    if V3:
        result = await Simple.abulk_create(data, request=request)
        assert len(result.succeeded) == 100 and not result.failed
    else:
        succeeded, failed = await simple_util.bulk_create_s(request, [create_schema(**item) for item in data])
        assert len(succeeded) == 100 and not failed


def measure(function, iterations, cleanup=lambda: None):
    cleanup()
    function()
    cleanup()
    gc.collect()
    with CaptureQueriesContext(connection) as queries:
        function()
    query_count = len(queries)
    cleanup()
    times = []
    for _ in range(iterations):
        start = time.perf_counter_ns()
        function()
        times.append((time.perf_counter_ns() - start) / 1_000_000)
        cleanup()
    return {"iterations": iterations, "median_ms": statistics.median(times), "queries": query_count}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    cases = {
        "warm_create_schema": measure(warm_schema, 10000),
        "cold_create_schema": measure(cold_schema, 100),
        "cold_fk_create_schema": measure(lambda: cold_schema(Book), 100),
        "single_read_with_relations": measure(async_to_sync(single_read), 30),
        "batch_read_100": measure(async_to_sync(batch_read(100)), 15),
        "batch_read_500": measure(async_to_sync(batch_read(500)), 10),
        "bulk_create_100": measure(async_to_sync(bulk_write), 5, lambda: Simple.objects.all().delete()),
    }
    result = {"implementation": "v3" if V3 else "2.36", "module": ninja_aio.__file__, "python": platform.python_version(), "backend": connection.vendor,
              "dependencies": {name: importlib.metadata.version(name) for name in ("Django", "django-ninja", "pydantic", "asgiref", "orjson")}, "results": cases}
    with open(args.output, "w") as file:
        json.dump(result, file, indent=2)


if __name__ == "__main__":
    main()
