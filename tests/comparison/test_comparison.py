"""Framework comparison benchmarks.

This module runs identical operations across different Python REST frameworks
to provide a fair performance comparison. All frameworks are tested using
async operations (with sync_to_async wrappers where needed) against the
same Django models and database.
"""

import atexit
import json
import platform
from datetime import datetime
from pathlib import Path

from asgiref.sync import async_to_sync
from django.test import TestCase, tag

from tests.comparison.base import BenchmarkRunner
from tests.comparison.frameworks.adrf import ADRFBenchmark
from tests.comparison.frameworks.drf import DRFBenchmark
from tests.comparison.frameworks.fastapi import FastAPIBenchmark
from tests.comparison.frameworks.ninja import PureDjangoNinjaBenchmark
from tests.comparison.frameworks.ninja_aio import NinjaAIOBenchmark
from tests.test_app.models import (
    TestModelSerializer,
    TestModelSerializerForeignKey,
    TestModelSerializerReverseForeignKey,
    TestModelSerializerManyToMany,
    TestModelSerializerReverseManyToMany,
)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
RESULTS_FILE = (PROJECT_ROOT / "comparison_results.json").resolve()

if not str(RESULTS_FILE).startswith(str(PROJECT_ROOT)):
    raise RuntimeError(f"Results file path escapes project root: {RESULTS_FILE}")

DEFAULT_ITERATIONS = 100
REDUCED_ITERATIONS = 50  # For operations that create/delete data

_all_comparison_results: dict = {}


def _save_results():
    """Write all accumulated results to the JSON file once at process exit."""
    if not _all_comparison_results:
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
            "results": _all_comparison_results,
        }
    )
    existing["runs"] = runs
    RESULTS_FILE.write_text(json.dumps(existing, indent=2))


atexit.register(_save_results)


@tag("comparison")
class FrameworkComparisonTest(TestCase):
    """Compare django-ninja-aio-crud against other popular Python REST frameworks.

    This test suite measures the same CRUD operations across multiple frameworks:
    - django-ninja-aio-crud (this framework)
    - Django Ninja (pure, without AIO CRUD)
    - Django REST Framework (sync)
    - ADRF (Async Django REST Framework)
    - FastAPI

    All frameworks use the same Django models and database, ensuring a fair
    comparison focused on framework overhead rather than I/O performance.
    """

    frameworks = [
        NinjaAIOBenchmark,
        PureDjangoNinjaBenchmark,
        DRFBenchmark,
        ADRFBenchmark,
        FastAPIBenchmark,
    ]

    @classmethod
    def setUpTestData(cls):
        """Create test data used by all benchmarks."""
        TestModelSerializer.objects.bulk_create(
            [
                TestModelSerializer(
                    name=f"comparison_{i}",
                    description=f"desc_{i}",
                    age=i,
                    active=i % 2 == 0,
                )
                for i in range(200)
            ]
        )

        # Create data with FK relations for relation serialization benchmarks
        parent = TestModelSerializerReverseForeignKey.objects.create(
            name="parent", description="parent_desc"
        )
        TestModelSerializerForeignKey.objects.bulk_create(
            [
                TestModelSerializerForeignKey(
                    name=f"child_{i}",
                    description=f"child_desc_{i}",
                    test_model_serializer=parent,
                )
                for i in range(50)
            ]
        )

        # Create M2M test data - this is where async Django gets REALLY hard
        m2m_related_items = TestModelSerializerReverseManyToMany.objects.bulk_create(
            [
                TestModelSerializerReverseManyToMany(
                    name=f"m2m_related_{i}", description=f"m2m_desc_{i}"
                )
                for i in range(20)
            ]
        )
        m2m_item = TestModelSerializerManyToMany.objects.create(
            name="m2m_parent", description="m2m_parent_desc"
        )
        m2m_item.test_model_serializers.set(m2m_related_items[:10])

    def _record(self, framework_name: str, operation: str, stats: dict):
        """Record benchmark results for a framework and operation."""
        _all_comparison_results.setdefault(framework_name, {})[operation] = stats

    def test_create_operation(self):
        """Compare create operation performance across frameworks."""
        for framework_class in self.frameworks:
            framework = framework_class()
            counter = [0]

            async def create():
                counter[0] += 1
                await framework.create_item(
                    {
                        "name": f"create_bench_{counter[0]}",
                        "description": "benchmark item",
                    }
                )

            stats = async_to_sync(BenchmarkRunner.benchmark_async)(create, iterations=REDUCED_ITERATIONS)
            self._record(framework.name, "create", stats)

    def test_list_operation(self):
        """Compare list/pagination performance across frameworks."""
        for framework_class in self.frameworks:
            framework = framework_class()

            async def list_items():
                await framework.list_items(limit=20, offset=0)

            stats = async_to_sync(BenchmarkRunner.benchmark_async)(list_items, iterations=DEFAULT_ITERATIONS)
            self._record(framework.name, "list", stats)

    def test_retrieve_operation(self):
        """Compare single item retrieval performance across frameworks."""
        test_obj = TestModelSerializer.objects.first()

        for framework_class in self.frameworks:
            framework = framework_class()

            async def get_item():
                await framework.get_item(test_obj.pk)

            stats = async_to_sync(BenchmarkRunner.benchmark_async)(get_item, iterations=DEFAULT_ITERATIONS)
            self._record(framework.name, "retrieve", stats)

    def test_update_operation(self):
        """Compare update operation performance across frameworks."""
        test_obj = TestModelSerializer.objects.first()

        for framework_class in self.frameworks:
            framework = framework_class()

            async def update_item():
                await framework.update_item(
                    test_obj.pk, {"description": "updated description"}
                )

            stats = async_to_sync(BenchmarkRunner.benchmark_async)(update_item, iterations=REDUCED_ITERATIONS)
            self._record(framework.name, "update", stats)

    def test_delete_operation(self):
        """Compare delete operation performance across frameworks."""
        for framework_class in self.frameworks:
            framework = framework_class()

            # Pre-create items to delete
            objs = TestModelSerializer.objects.bulk_create(
                [
                    TestModelSerializer(
                        name=f"delete_{framework.name}_{i}",
                        description=f"to_delete_{i}",
                    )
                    for i in range(REDUCED_ITERATIONS)
                ]
            )
            pks = iter([o.pk for o in objs])

            async def delete_item():
                pk = next(pks)
                await framework.delete_item(pk)

            stats = async_to_sync(BenchmarkRunner.benchmark_async)(delete_item, iterations=REDUCED_ITERATIONS)
            self._record(framework.name, "delete", stats)

    def test_filter_operation(self):
        """Compare filter performance across frameworks."""
        for framework_class in self.frameworks:
            framework = framework_class()

            async def filter_items():
                await framework.filter_items(active=True, age=10)

            stats = async_to_sync(BenchmarkRunner.benchmark_async)(filter_items, iterations=DEFAULT_ITERATIONS)
            self._record(framework.name, "filter", stats)

    def test_relation_serialization(self):
        """Compare serialization performance with FK relations."""
        test_obj = TestModelSerializerForeignKey.objects.first()

        for framework_class in self.frameworks:
            framework = framework_class()

            async def serialize_with_relations():
                await framework.serialize_with_relations(test_obj.pk)

            stats = async_to_sync(BenchmarkRunner.benchmark_async)(
                serialize_with_relations, iterations=DEFAULT_ITERATIONS
            )
            self._record(framework.name, "relation_serialization", stats)

    def test_bulk_serialization_100(self):
        """Compare bulk serialization performance (100 items)."""
        for framework_class in self.frameworks:
            framework = framework_class()

            async def bulk_serialize():
                await framework.list_items(limit=100, offset=0)

            stats = async_to_sync(BenchmarkRunner.benchmark_async)(
                bulk_serialize, iterations=REDUCED_ITERATIONS
            )
            self._record(framework.name, "bulk_serialization_100", stats)

    def test_bulk_serialization_500(self):
        """Compare bulk serialization performance (500 items).

        Note: Only 200 items exist in test data, so this will serialize
        all available items. Useful for comparing overhead with larger datasets.
        """
        # Create additional items for this test
        TestModelSerializer.objects.bulk_create(
            [
                TestModelSerializer(
                    name=f"bulk_{i}",
                    description=f"bulk_desc_{i}",
                    age=i,
                    active=i % 2 == 0,
                )
                for i in range(200, 500)
            ]
        )

        for framework_class in self.frameworks:
            framework = framework_class()

            async def bulk_serialize():
                await framework.list_items(limit=500, offset=0)

            stats = async_to_sync(BenchmarkRunner.benchmark_async)(
                bulk_serialize, iterations=20  # Reduced iterations for large dataset
            )
            self._record(framework.name, "bulk_serialization_500", stats)

    def test_nested_relations(self):
        """Compare nested relation serialization - YOUR FRAMEWORK'S STRENGTH!

        This is where django-ninja-aio-crud truly shines. Other frameworks
        require manual nested dict construction or complex serializer setup.
        """
        test_obj = TestModelSerializerForeignKey.objects.first()

        for framework_class in self.frameworks:
            framework = framework_class()

            async def serialize_nested():
                await framework.serialize_nested_relations(test_obj.pk)

            stats = async_to_sync(BenchmarkRunner.benchmark_async)(
                serialize_nested, iterations=DEFAULT_ITERATIONS
            )
            self._record(framework.name, "nested_relations", stats)

    def test_reverse_relations(self):
        """Compare reverse FK serialization in ASYNC - VERY HARD WITHOUT YOUR FRAMEWORK!

        Async prefetch_related is notoriously difficult in Django.
        Your framework handles it automatically!
        """
        parent = TestModelSerializerReverseForeignKey.objects.first()

        for framework_class in self.frameworks:
            framework = framework_class()

            async def serialize_reverse():
                await framework.serialize_reverse_relations(parent.pk)

            stats = async_to_sync(BenchmarkRunner.benchmark_async)(
                serialize_reverse, iterations=DEFAULT_ITERATIONS
            )
            self._record(framework.name, "reverse_relations", stats)

    def test_many_to_many(self):
        """Compare M2M serialization in async - ANOTHER PAIN POINT!

        M2M in async Django requires careful prefetch_related handling.
        Your framework automates this completely.
        """
        m2m_obj = TestModelSerializerManyToMany.objects.first()

        for framework_class in self.frameworks:
            framework = framework_class()

            async def serialize_m2m():
                await framework.serialize_many_to_many(m2m_obj.pk)

            stats = async_to_sync(BenchmarkRunner.benchmark_async)(
                serialize_m2m, iterations=DEFAULT_ITERATIONS
            )
            self._record(framework.name, "many_to_many", stats)

    def test_complex_async_query(self):
        """Real-world async scenario: filters + relations + pagination.

        This is THE use case your framework optimizes for!
        Combining filters, relations, and pagination in async is painful
        without proper automation.
        """
        for framework_class in self.frameworks:
            framework = framework_class()

            async def complex_query():
                # Filtering by a related field's property in async
                await framework.complex_query_with_relations(
                    test_model_serializer__name="parent"
                )

            stats = async_to_sync(BenchmarkRunner.benchmark_async)(
                complex_query, iterations=DEFAULT_ITERATIONS
            )
            self._record(framework.name, "complex_async_query", stats)
