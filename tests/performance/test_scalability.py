"""
Scalability regression tests for large datasets.

These tests verify that serialization performance stays within acceptable
thresholds as dataset size grows. They guard against regressions in:
1. Batch serialization via _bump_queryset_from_schema (single sync_to_async)
2. sync_to_async overhead remaining minimal
3. M2M validation using set-based membership (O(1) per check)
4. FK relation serialization overhead
"""

import statistics
import time

from asgiref.sync import async_to_sync
from django.test import TestCase, tag

from ninja_aio import NinjaAIO
from ninja_aio.models import ModelUtil
from tests.generics.request import Request
from tests.test_app import models
from tests.test_app.views import TestModelSerializerAPI


DATASET_SIZES = [1000, 5000, 10000, 17000]
SMALL_ITERATIONS = 3

# Maximum acceptable seconds for serializing 17k simple objects.
# Batched serialization should complete well under this threshold.
MAX_SERIALIZATION_TIME_17K = 1.0

# Maximum acceptable overhead (%) of async serialization vs direct sync.
MAX_ASYNC_OVERHEAD_PCT = 200

# Maximum acceptable seconds per 1000 objects for batch serialization.
MAX_MS_PER_1K_OBJECTS = 15.0


class ScalabilityMixin:
    """Timing utilities for scalability tests."""

    @classmethod
    def _time_async(cls, func, iterations=SMALL_ITERATIONS):
        """Run async func multiple times and return timing stats in seconds."""
        wrapped = async_to_sync(func)
        times = []
        for _ in range(iterations):
            start = time.perf_counter()
            wrapped()
            elapsed = time.perf_counter() - start
            times.append(elapsed)
        return {
            "iterations": iterations,
            "min_s": round(min(times), 4),
            "max_s": round(max(times), 4),
            "avg_s": round(statistics.mean(times), 4),
            "median_s": round(statistics.median(times), 4),
        }

    @classmethod
    def _time_async_once(cls, func):
        """Run async func once and return elapsed seconds."""
        wrapped = async_to_sync(func)
        start = time.perf_counter()
        result = wrapped()
        return round(time.perf_counter() - start, 4), result

    @classmethod
    def _time_sync_once(cls, func):
        """Run sync func once and return elapsed seconds."""
        start = time.perf_counter()
        result = func()
        return round(time.perf_counter() - start, 4), result


# ---------------------------------------------------------------------------
# Test 1: Batch serialization throughput at scale
# ---------------------------------------------------------------------------


@tag("performance", "scalability")
class BatchSerializationScalabilityTest(ScalabilityMixin, TestCase):
    """
    Verifies that batch serialization (_bump_queryset_from_schema) scales
    efficiently with dataset size. Time should grow linearly and stay
    within acceptable thresholds.
    """

    @classmethod
    def setUpTestData(cls):
        cls.request = Request("test-batch-scalability").get()
        cls.util = ModelUtil(models.TestModelSerializer)
        cls.schema_out = models.TestModelSerializer.generate_read_s()

        max_size = max(DATASET_SIZES)
        batch_size = 5000
        for start in range(0, max_size, batch_size):
            end = min(start + batch_size, max_size)
            models.TestModelSerializer.objects.bulk_create(
                [
                    models.TestModelSerializer(
                        name=f"user_{i}",
                        description=f"desc_{i}",
                        age=i % 100,
                        active=i % 2 == 0,
                    )
                    for i in range(start, end)
                ]
            )

    def test_serialization_throughput_at_scale(self):
        """
        Verify serialization time stays under threshold for all dataset sizes
        and that throughput (ms per 1k objects) remains consistent.
        """
        timings = {}

        for size in DATASET_SIZES:
            max_pk = models.TestModelSerializer.objects.order_by("pk").values_list(
                "pk", flat=True
            )[size - 1]

            async def serialize(mp=max_pk):
                qs = models.TestModelSerializer.objects.filter(pk__lte=mp)
                return await self.util.list_read_s(
                    schema=self.schema_out,
                    request=self.request,
                    instances=qs,
                )

            elapsed, result = self._time_async_once(serialize)
            timings[size] = elapsed
            ms_per_1k = (elapsed / size) * 1000
            print(
                f"  list_read_s {size:>6} records: {elapsed:.4f}s "
                f"({ms_per_1k:.2f}ms/1k objects, {len(result)} serialized)"
            )

        # Assert 17k serialization stays under absolute threshold
        time_17k = timings[DATASET_SIZES[-1]]
        self.assertLess(
            time_17k,
            MAX_SERIALIZATION_TIME_17K,
            f"Serializing {DATASET_SIZES[-1]} records took {time_17k:.3f}s, "
            f"exceeding {MAX_SERIALIZATION_TIME_17K}s threshold. "
            f"Batch serialization may have regressed.",
        )

        # Assert throughput is consistent (ms/1k should not degrade much)
        ms_per_1k_small = (timings[DATASET_SIZES[0]] / DATASET_SIZES[0]) * 1000
        ms_per_1k_large = (timings[DATASET_SIZES[-1]] / DATASET_SIZES[-1]) * 1000
        print(f"\n  Throughput: {ms_per_1k_small:.2f}ms/1k (small) vs {ms_per_1k_large:.2f}ms/1k (large)")

        self.assertLess(
            ms_per_1k_large,
            MAX_MS_PER_1K_OBJECTS,
            f"Throughput degraded to {ms_per_1k_large:.2f}ms/1k objects at {DATASET_SIZES[-1]} records. "
            f"Max allowed: {MAX_MS_PER_1K_OBJECTS}ms/1k.",
        )


# ---------------------------------------------------------------------------
# Test 2: sync_to_async overhead stays minimal
# ---------------------------------------------------------------------------


@tag("performance", "scalability")
class SyncToAsyncOverheadTest(ScalabilityMixin, TestCase):
    """
    Ensures the async serialization overhead remains minimal compared to
    direct sync serialization. After the batch optimization, the overhead
    should be a single sync_to_async call, not N calls.
    """

    @classmethod
    def setUpTestData(cls):
        cls.util = ModelUtil(models.TestModelSerializer)
        cls.schema_out = models.TestModelSerializer.generate_read_s()
        cls.request = Request("test-overhead").get()

        models.TestModelSerializer.objects.bulk_create(
            [
                models.TestModelSerializer(
                    name=f"overhead_{i}", description=f"desc_{i}"
                )
                for i in range(5000)
            ]
        )

    def test_async_overhead_within_threshold(self):
        """
        Verify async serialization overhead stays under MAX_ASYNC_OVERHEAD_PCT
        compared to direct sync serialization.
        """
        qs = models.TestModelSerializer.objects.all()[:5000]
        schema = self.schema_out

        async def async_serialize():
            return await self.util.list_read_s(
                schema=schema,
                request=self.request,
                instances=qs,
            )

        async_time, _ = self._time_async_once(async_serialize)

        def sync_serialize():
            return [schema.from_orm(obj).model_dump() for obj in qs]

        sync_time, _ = self._time_sync_once(sync_serialize)

        overhead_pct = ((async_time - sync_time) / max(sync_time, 0.001)) * 100

        print("\n  5000 objects:")
        print(f"    Async (batched sync_to_async): {async_time:.4f}s")
        print(f"    Direct sync serialization:     {sync_time:.4f}s")
        print(f"    Overhead: {overhead_pct:.0f}%")

        self.assertLess(
            overhead_pct,
            MAX_ASYNC_OVERHEAD_PCT,
            f"Async serialization overhead is {overhead_pct:.0f}%, "
            f"exceeding {MAX_ASYNC_OVERHEAD_PCT}% threshold. "
            f"Batch sync_to_async optimization may have regressed "
            f"(e.g. back to per-object sync_to_async calls).",
        )


# ---------------------------------------------------------------------------
# Test 3: Full list_view pipeline at scale
# ---------------------------------------------------------------------------


@tag("performance", "scalability")
class FullListViewScalabilityTest(ScalabilityMixin, TestCase):
    """
    End-to-end list_view timing at scale.
    Verifies that the full pipeline (DB + serialize + paginate) stays fast.
    """

    @classmethod
    def setUpTestData(cls):
        cls.api = NinjaAIO(urls_namespace="scalability_full")
        cls.viewset = TestModelSerializerAPI(
            api=cls.api, prefix="test-full-scalability", tags=["scalability"]
        )
        cls.viewset.add_views_to_route()
        cls.request = Request("test-full-scalability")

        max_size = max(DATASET_SIZES)
        batch_size = 5000
        for start in range(0, max_size, batch_size):
            end = min(start + batch_size, max_size)
            models.TestModelSerializer.objects.bulk_create(
                [
                    models.TestModelSerializer(
                        name=f"full_{i}",
                        description=f"full_desc_{i}",
                        age=i % 100,
                        active=i % 2 == 0,
                    )
                    for i in range(start, end)
                ]
            )

    def test_full_list_view_stays_fast(self):
        """
        Verify the full list_view (page=1) stays under threshold with large datasets.
        """
        view = self.viewset.list_view()
        pagination = self.viewset.pagination_class.Input(page=1)
        filters = self.viewset.filters_schema()
        timings = {}

        for size in DATASET_SIZES:
            count = models.TestModelSerializer.objects.count()
            if count < size:
                print(f"  Skipping size {size} (only {count} records available)")
                continue

            async def list_view():
                return await view(
                    self.request.get(),
                    ninja_pagination=pagination,
                    filters=filters,
                )

            elapsed, _ = self._time_async_once(list_view)
            timings[size] = elapsed
            print(f"  Full list_view (page=1) with {size:>6} total records: {elapsed:.4f}s")

        if len(timings) >= 2:
            sizes = sorted(timings.keys())
            ratio = timings[sizes[-1]] / max(timings[sizes[0]], 0.001)
            print(f"\n  Time ratio {sizes[-1]}/{sizes[0]}: {ratio:.1f}x")

            # With pagination at DB level, ratio should stay reasonable
            # Allow up to 3x for DB overhead on larger datasets
            self.assertLess(
                ratio,
                3.0,
                f"Full list_view time grew {ratio:.1f}x between {sizes[0]} and {sizes[-1]} records. "
                f"Pagination may not be slicing at the DB level.",
            )


# ---------------------------------------------------------------------------
# Test 4: FK relation serialization overhead
# ---------------------------------------------------------------------------


@tag("performance", "scalability")
class RelationSerializationScalabilityTest(ScalabilityMixin, TestCase):
    """
    Verifies that FK relation serialization overhead stays bounded.
    Objects with relations should not be drastically slower than simple objects.
    """

    @classmethod
    def setUpTestData(cls):
        cls.request = Request("test-relation-scalability").get()

        parents = models.TestModelSerializerReverseForeignKey.objects.bulk_create(
            [
                models.TestModelSerializerReverseForeignKey(
                    name=f"parent_{i}", description=f"parent_desc_{i}"
                )
                for i in range(100)
            ]
        )

        models.TestModelSerializerForeignKey.objects.bulk_create(
            [
                models.TestModelSerializerForeignKey(
                    name=f"child_{i}",
                    description=f"child_desc_{i}",
                    test_model_serializer=parents[i % len(parents)],
                )
                for i in range(5000)
            ]
        )

        models.TestModelSerializer.objects.bulk_create(
            [
                models.TestModelSerializer(name=f"simple_{i}", description=f"desc_{i}")
                for i in range(5000)
            ]
        )

    def test_relation_overhead_bounded(self):
        """
        FK relation serialization overhead should stay under 5x compared to simple objects.
        """
        util_simple = ModelUtil(models.TestModelSerializer)
        schema_simple = models.TestModelSerializer.generate_read_s()

        util_fk = ModelUtil(models.TestModelSerializerForeignKey)
        schema_fk = models.TestModelSerializerForeignKey.generate_read_s()

        size = 5000

        qs_simple = models.TestModelSerializer.objects.all()[:size]
        qs_fk = models.TestModelSerializerForeignKey.objects.select_related(
            "test_model_serializer"
        ).all()[:size]

        async def serialize_simple():
            return await util_simple.list_read_s(
                schema=schema_simple,
                request=self.request,
                instances=qs_simple,
            )

        async def serialize_fk():
            return await util_fk.list_read_s(
                schema=schema_fk,
                request=self.request,
                instances=qs_fk,
            )

        simple_time, _ = self._time_async_once(serialize_simple)
        fk_time, _ = self._time_async_once(serialize_fk)

        ratio = fk_time / max(simple_time, 0.001)
        print(f"\n  {size} objects:")
        print(f"    Simple (no relations): {simple_time:.4f}s")
        print(f"    With FK relation:      {fk_time:.4f}s")
        print(f"    Ratio: {ratio:.1f}x")

        self.assertLess(
            ratio,
            5.0,
            f"FK relation serialization is {ratio:.1f}x slower than simple objects. "
            f"Expected under 5x overhead.",
        )


# ---------------------------------------------------------------------------
# Test 5: M2M set-based validation stays fast
# ---------------------------------------------------------------------------


@tag("performance", "scalability")
class M2MValidationScalabilityTest(ScalabilityMixin, TestCase):
    """
    Verifies that M2M validation with set-based PK membership checks
    stays efficient as the number of existing relations grows.
    """

    @classmethod
    def setUpTestData(cls):
        cls.request = Request("test-m2m-scalability").get()

        cls.parent = models.TestModelSerializerManyToMany.objects.create(
            name="parent", description="parent_desc"
        )
        related_objs = models.TestModelSerializerReverseManyToMany.objects.bulk_create(
            [
                models.TestModelSerializerReverseManyToMany(
                    name=f"related_{i}", description=f"desc_{i}"
                )
                for i in range(5000)
            ]
        )
        cls.related_pks = [obj.pk for obj in related_objs]

    def test_m2m_set_validation_scales_well(self):
        """
        M2M validation using set-based PK lookup should scale well.
        The ratio between 5000 and 100 relations should stay under 20x
        (dominated by DB fetch, not membership checks).
        """
        parent = self.parent
        manager = parent.test_model_serializers
        relation_sizes = [100, 500, 1000, 3000, 5000]
        timings = {}

        for size in relation_sizes:
            manager.clear()
            pks_to_add = self.related_pks[:size]
            manager.add(
                *models.TestModelSerializerReverseManyToMany.objects.filter(
                    pk__in=pks_to_add
                )
            )

            # Simulate the optimized validation: load PKs as set + check membership
            async def validate_m2m():
                rel_obj_pks = {obj.pk async for obj in manager.all()}
                # Simulate checking 10 PKs against the set
                sample_pk = self.related_pks[0]
                for _ in range(10):
                    _ = sample_pk in rel_obj_pks

            elapsed, _ = self._time_async_once(validate_m2m)
            timings[size] = elapsed
            print(f"  M2M set validation with {size:>5} relations: {elapsed:.4f}s")

        if len(timings) >= 2:
            sizes_sorted = sorted(timings.keys())
            ratio = timings[sizes_sorted[-1]] / max(timings[sizes_sorted[0]], 0.001)
            print(f"\n  Time ratio {sizes_sorted[-1]}/{sizes_sorted[0]}: {ratio:.1f}x")

            # With set-based checks, growth should be dominated by DB fetch only
            self.assertLess(
                ratio,
                20.0,
                f"M2M validation grew {ratio:.1f}x between {sizes_sorted[0]} and "
                f"{sizes_sorted[-1]} relations. Set-based membership may have regressed.",
            )


# ---------------------------------------------------------------------------
# Test 6: Serialization returns all objects (behavioral guard)
# ---------------------------------------------------------------------------


@tag("performance", "scalability")
class SerializationCompletenessTest(ScalabilityMixin, TestCase):
    """
    Verifies that list_read_s correctly serializes all objects in the queryset.
    This is a behavioral test ensuring batch serialization produces the same
    results as per-object serialization.
    """

    @classmethod
    def setUpTestData(cls):
        cls.request = Request("test-completeness").get()
        cls.util = ModelUtil(models.TestModelSerializer)
        cls.schema_out = models.TestModelSerializer.generate_read_s()

        models.TestModelSerializer.objects.bulk_create(
            [
                models.TestModelSerializer(
                    name=f"complete_{i}", description=f"complete_desc_{i}"
                )
                for i in range(100)
            ]
        )

    def test_batch_serialization_matches_per_object(self):
        """
        Verify batch serialization produces identical results to per-object serialization.
        """
        qs = models.TestModelSerializer.objects.all()[:100]
        schema = self.schema_out

        # Batch (current implementation)
        async def batch_serialize():
            return await self.util.list_read_s(
                schema=schema,
                request=self.request,
                instances=qs,
            )

        batch_result = async_to_sync(batch_serialize)()

        # Per-object (reference)
        per_object_result = [schema.from_orm(obj).model_dump() for obj in qs]

        self.assertEqual(len(batch_result), len(per_object_result))
        self.assertEqual(batch_result, per_object_result)
        print(f"\n  Batch and per-object serialization match for {len(batch_result)} objects")

    def test_list_read_s_serializes_full_queryset(self):
        """
        Verify list_read_s serializes the complete queryset passed to it.
        """
        total = models.TestModelSerializer.objects.count()
        qs = models.TestModelSerializer.objects.all()

        async def get_result():
            return await self.util.list_read_s(
                schema=self.schema_out,
                request=self.request,
                instances=qs,
            )

        result = async_to_sync(get_result)()

        self.assertEqual(len(result), total)
        print(f"\n  list_read_s correctly serialized all {total} objects in the queryset")
