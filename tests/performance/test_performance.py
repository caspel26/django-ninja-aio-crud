import atexit
import json
import platform
import statistics
import time
from datetime import datetime
from pathlib import Path

from asgiref.sync import async_to_sync
from django.test import TestCase, tag

from ninja_aio import NinjaAIO
from ninja_aio.models import ModelUtil
from tests.generics.request import Request
from tests.test_app import models, serializers
from tests.test_app.views import (
    TestModelSerializerAPI,
    TestModelSerializerForeignKeyRelationFilterAPI,
    TestModelSerializerMatchCaseFilterAPI,
)

RESULTS_FILE = Path(__file__).resolve().parents[2] / "performance_results.json"
DEFAULT_ITERATIONS = 100
BULK_SIZES = [100, 500]

_all_perf_results: dict = {}


def _save_results():
    """Write all accumulated results to the JSON file once at process exit."""
    if not _all_perf_results:
        return
    existing = {}
    if RESULTS_FILE.exists():
        try:
            existing = json.loads(RESULTS_FILE.read_text())
        except (json.JSONDecodeError, OSError):
            existing = {}

    runs = existing.get("runs", [])
    runs.append(
        {
            "timestamp": datetime.now().isoformat(),
            "python_version": platform.python_version(),
            "results": _all_perf_results,
        }
    )
    existing["runs"] = runs
    RESULTS_FILE.write_text(json.dumps(existing, indent=2))


atexit.register(_save_results)


class PerformanceMixin:
    """Shared benchmarking utilities for all performance test cases."""

    @classmethod
    def _benchmark(cls, func, iterations=DEFAULT_ITERATIONS):
        """Run *func* multiple times and return timing statistics in milliseconds."""
        times = []
        for _ in range(iterations):
            start = time.perf_counter()
            func()
            elapsed = (time.perf_counter() - start) * 1000
            times.append(elapsed)
        return {
            "iterations": iterations,
            "min_ms": round(min(times), 4),
            "max_ms": round(max(times), 4),
            "avg_ms": round(statistics.mean(times), 4),
            "median_ms": round(statistics.median(times), 4),
        }

    @classmethod
    def _benchmark_async(cls, func, iterations=DEFAULT_ITERATIONS):
        """Same as _benchmark but wraps an async callable."""
        return cls._benchmark(async_to_sync(func), iterations)

    def _record(self, test_name, stats):
        cls_name = self.__class__.__name__
        _all_perf_results.setdefault(cls_name, {})[test_name] = stats


# ---------------------------------------------------------------------------
# Schema Generation Benchmarks
# ---------------------------------------------------------------------------


@tag("performance")
class SchemaGenerationPerformanceTest(PerformanceMixin, TestCase):
    """Benchmark schema generation for ModelSerializer and Meta-driven Serializer."""

    def test_model_serializer_schema_generation(self):
        """Benchmark generating all schema types from a ModelSerializer."""

        def gen():
            models.TestModelSerializer.generate_read_s()
            models.TestModelSerializer.generate_create_s()
            models.TestModelSerializer.generate_update_s()
            models.TestModelSerializer.generate_detail_s()

        stats = self._benchmark(gen)
        self._record("model_serializer_schema_generation", stats)

    def test_meta_serializer_schema_generation(self):
        """Benchmark generating schemas from a Meta-driven Serializer."""

        def gen():
            serializers.TestModelForeignKeySerializer.generate_read_s()
            serializers.TestModelForeignKeySerializer.generate_create_s()
            serializers.TestModelForeignKeySerializer.generate_update_s()

        stats = self._benchmark(gen)
        self._record("meta_serializer_schema_generation", stats)

    def test_schema_with_relations(self):
        """Benchmark schema generation for models with FK relations."""

        def gen():
            models.TestModelSerializerForeignKey.generate_read_s()
            models.TestModelSerializerReverseForeignKey.generate_read_s()

        stats = self._benchmark(gen)
        self._record("schema_with_relations", stats)

    def test_schema_with_validators(self):
        """Benchmark schema generation including validator collection."""

        def gen():
            serializers.TestModelWithValidatorsMetaSerializer.generate_create_s()
            serializers.TestModelWithValidatorsMetaSerializer.generate_read_s()
            serializers.TestModelWithValidatorsMetaSerializer.generate_update_s()

        stats = self._benchmark(gen)
        self._record("schema_with_validators", stats)


# ---------------------------------------------------------------------------
# Serialization Benchmarks
# ---------------------------------------------------------------------------


@tag("performance")
class SerializationPerformanceTest(PerformanceMixin, TestCase):
    """Benchmark object serialization throughput."""

    @classmethod
    def setUpTestData(cls):
        cls.api = NinjaAIO(urls_namespace="perf_serialization")
        cls.util = ModelUtil(models.TestModelSerializer)
        cls.request = Request("test-model-serializers").get()
        cls.schema_out = models.TestModelSerializer.generate_read_s()
        cls.obj = models.TestModelSerializer.objects.create(
            name="perf_test", description="perf_desc"
        )
        models.TestModelSerializer.objects.bulk_create(
            [
                models.TestModelSerializer(name=f"perf_{i}", description=f"desc_{i}")
                for i in range(max(BULK_SIZES))
            ]
        )

    def test_single_object_serialization(self):
        """Benchmark serializing a single model instance."""

        async def serialize():
            await self.util.read_s(
                schema=self.schema_out, request=self.request, instance=self.obj
            )

        stats = self._benchmark_async(serialize)
        self._record("single_object_serialization", stats)

    def test_bulk_serialization(self):
        """Benchmark serializing multiple objects at various batch sizes."""
        for size in BULK_SIZES:
            qs = models.TestModelSerializer.objects.all()[:size]

            async def serialize(queryset=qs):
                await self.util.list_read_s(
                    schema=self.schema_out,
                    request=self.request,
                    instances=queryset,
                )

            stats = self._benchmark_async(serialize, iterations=50)
            self._record(f"bulk_serialization_{size}", stats)

    def test_input_parsing(self):
        """Benchmark parsing inbound request data."""
        schema_in = models.TestModelSerializer.generate_create_s()
        data = schema_in(name="parse_test", description="parse_desc")

        async def parse():
            await self.util.parse_input_data(self.request, data)

        stats = self._benchmark_async(parse)
        self._record("input_parsing", stats)

    def test_relation_serialization(self):
        """Benchmark serializing objects with FK relations."""
        parent = models.TestModelSerializerReverseForeignKey.objects.create(
            name="parent", description="parent_desc"
        )
        models.TestModelSerializerForeignKey.objects.create(
            name="child",
            description="child_desc",
            test_model_serializer=parent,
        )
        util = ModelUtil(models.TestModelSerializerForeignKey)
        schema = models.TestModelSerializerForeignKey.generate_read_s()
        child = models.TestModelSerializerForeignKey.objects.select_related(
            "test_model_serializer"
        ).first()

        async def serialize():
            await util.read_s(schema=schema, request=self.request, instance=child)

        stats = self._benchmark_async(serialize)
        self._record("relation_serialization", stats)


# ---------------------------------------------------------------------------
# CRUD Endpoint Benchmarks
# ---------------------------------------------------------------------------


@tag("performance")
class CRUDPerformanceTest(PerformanceMixin, TestCase):
    """Benchmark CRUD operations via viewset methods."""

    @classmethod
    def setUpTestData(cls):
        cls.api = NinjaAIO(urls_namespace="perf_crud")
        cls.viewset = TestModelSerializerAPI(
            api=cls.api, prefix="test-model-serializers", tags=["perf"]
        )
        cls.viewset.add_views_to_route()
        cls.request = Request("test-model-serializers")
        models.TestModelSerializer.objects.bulk_create(
            [
                models.TestModelSerializer(name=f"crud_{i}", description=f"desc_{i}")
                for i in range(100)
            ]
        )

    def test_create_performance(self):
        """Benchmark create endpoint throughput."""
        view = self.viewset.create_view()
        schema_in = self.viewset.schema_in
        counter = [0]

        async def create():
            counter[0] += 1
            data = schema_in(
                name=f"create_perf_{counter[0]}", description="create_desc"
            )
            await view(self.request.post(), data)

        stats = self._benchmark_async(create)
        self._record("create", stats)

    def test_list_performance(self):
        """Benchmark list endpoint with pagination."""
        view = self.viewset.list_view()
        pagination = self.viewset.pagination_class.Input(page=1)
        filters = self.viewset.filters_schema()

        async def list_view():
            await view(
                self.request.get(),
                ninja_pagination=pagination,
                filters=filters,
            )

        stats = self._benchmark_async(list_view)
        self._record("list", stats)

    def test_retrieve_performance(self):
        """Benchmark single object retrieval."""
        obj = models.TestModelSerializer.objects.first()
        view = self.viewset.retrieve_view()
        path_schema = self.viewset.path_schema(id=obj.pk)

        async def retrieve():
            await view(self.request.get(), path_schema)

        stats = self._benchmark_async(retrieve)
        self._record("retrieve", stats)

    def test_update_performance(self):
        """Benchmark update endpoint."""
        obj = models.TestModelSerializer.objects.first()
        view = self.viewset.update_view()
        schema_update = self.viewset.schema_update
        path_schema = self.viewset.path_schema(id=obj.pk)
        data = schema_update(description="updated_desc")

        async def update():
            await view(self.request.patch(), data, path_schema)

        stats = self._benchmark_async(update)
        self._record("update", stats)

    def test_delete_performance(self):
        """Benchmark delete endpoint throughput."""
        view = self.viewset.delete_view()
        objs = models.TestModelSerializer.objects.bulk_create(
            [
                models.TestModelSerializer(
                    name=f"del_{i}", description=f"del_desc_{i}"
                )
                for i in range(DEFAULT_ITERATIONS)
            ]
        )
        pks = iter([o.pk for o in objs])

        async def delete():
            pk = next(pks)
            path_schema = self.viewset.path_schema(id=pk)
            await view(self.request.delete(), path_schema)

        stats = self._benchmark(async_to_sync(delete), iterations=DEFAULT_ITERATIONS)
        self._record("delete", stats)


# ---------------------------------------------------------------------------
# Filter Benchmarks
# ---------------------------------------------------------------------------


@tag("performance")
class FilterPerformanceTest(PerformanceMixin, TestCase):
    """Benchmark filter mixin performance with various query param combinations."""

    @classmethod
    def setUpTestData(cls):
        cls.api = NinjaAIO(urls_namespace="perf_filters")

        cls.viewset = TestModelSerializerAPI(
            api=cls.api, prefix="test-model-serializers", tags=["perf"]
        )
        cls.viewset.add_views_to_route()

        cls.relation_viewset = TestModelSerializerForeignKeyRelationFilterAPI(
            api=cls.api, prefix="test-model-serializer-fk-filter", tags=["perf"]
        )
        cls.relation_viewset.add_views_to_route()

        cls.match_viewset = TestModelSerializerMatchCaseFilterAPI(
            api=cls.api, prefix="test-model-serializer-match", tags=["perf"]
        )
        cls.match_viewset.add_views_to_route()

        cls.request = Request("test-model-serializers")

        models.TestModelSerializer.objects.bulk_create(
            [
                models.TestModelSerializer(
                    name=f"filter_{i}",
                    description=f"desc_{i}",
                    age=i,
                    active=i % 2 == 0,
                    status="approved" if i % 3 == 0 else "pending",
                )
                for i in range(200)
            ]
        )
        parent = models.TestModelSerializerReverseForeignKey.objects.create(
            name="rel_parent", description="parent"
        )
        for i in range(50):
            models.TestModelSerializerForeignKey.objects.create(
                name=f"rel_child_{i}",
                description=f"child_desc_{i}",
                test_model_serializer=parent,
            )

    def test_icontains_filter(self):
        """Benchmark icontains string filtering."""
        view = self.viewset.list_view()
        pagination = self.viewset.pagination_class.Input(page=1)
        filters = self.viewset.filters_schema(name="filter_5")

        async def filter_view():
            await view(
                self.request.get(),
                ninja_pagination=pagination,
                filters=filters,
            )

        stats = self._benchmark_async(filter_view)
        self._record("icontains_filter", stats)

    def test_boolean_filter(self):
        """Benchmark boolean field filtering."""
        view = self.viewset.list_view()
        pagination = self.viewset.pagination_class.Input(page=1)
        filters = self.viewset.filters_schema(active=True)

        async def filter_view():
            await view(
                self.request.get(),
                ninja_pagination=pagination,
                filters=filters,
            )

        stats = self._benchmark_async(filter_view)
        self._record("boolean_filter", stats)

    def test_numeric_filter(self):
        """Benchmark numeric field filtering."""
        view = self.viewset.list_view()
        pagination = self.viewset.pagination_class.Input(page=1)
        filters = self.viewset.filters_schema(age=50)

        async def filter_view():
            await view(
                self.request.get(),
                ninja_pagination=pagination,
                filters=filters,
            )

        stats = self._benchmark_async(filter_view)
        self._record("numeric_filter", stats)

    def test_relation_filter(self):
        """Benchmark relation-based filtering."""
        view = self.relation_viewset.list_view()
        pagination = self.relation_viewset.pagination_class.Input(page=1)
        filters = self.relation_viewset.filters_schema(test_model_serializer=1)

        async def filter_view():
            await view(
                self.request.get(),
                ninja_pagination=pagination,
                filters=filters,
            )

        stats = self._benchmark_async(filter_view)
        self._record("relation_filter", stats)

    def test_match_case_filter(self):
        """Benchmark match case conditional filtering."""
        view = self.match_viewset.list_view()
        pagination = self.match_viewset.pagination_class.Input(page=1)
        filters = self.match_viewset.filters_schema(is_approved=True)

        async def filter_view():
            await view(
                self.request.get(),
                ninja_pagination=pagination,
                filters=filters,
            )

        stats = self._benchmark_async(filter_view)
        self._record("match_case_filter", stats)

    def test_combined_filters(self):
        """Benchmark multiple filters applied simultaneously."""
        view = self.viewset.list_view()
        pagination = self.viewset.pagination_class.Input(page=1)
        filters = self.viewset.filters_schema(
            name="filter", active=True, age=10
        )

        async def filter_view():
            await view(
                self.request.get(),
                ninja_pagination=pagination,
                filters=filters,
            )

        stats = self._benchmark_async(filter_view)
        self._record("combined_filters", stats)
