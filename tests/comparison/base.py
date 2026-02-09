"""Base interface for framework comparison benchmarks.

This module defines the common interface that each framework implementation
must provide for fair comparison.
"""

import statistics
import time
from abc import ABC, abstractmethod
from typing import Any, Callable


class FrameworkBenchmark(ABC):
    """Base class defining the interface for framework comparison benchmarks.

    Each framework implementation must provide:
    - setup_app(): Initialize the framework app/router
    - setup_endpoints(): Create CRUD endpoints
    - create_item(data): Create a single item
    - list_items(limit, offset): List items with pagination
    - get_item(item_id): Retrieve a single item
    - update_item(item_id, data): Update an item
    - delete_item(item_id): Delete an item
    - filter_items(filters): Apply filters to list query
    """

    name: str = "Unknown"

    @abstractmethod
    def setup_app(self):
        """Initialize the framework application/router."""
        pass

    @abstractmethod
    def setup_endpoints(self):
        """Create CRUD endpoints for the test model."""
        pass

    @abstractmethod
    async def create_item(self, data: dict) -> Any:
        """Create a single item and return the created object."""
        pass

    @abstractmethod
    async def list_items(self, limit: int = 10, offset: int = 0) -> list:
        """List items with pagination."""
        pass

    @abstractmethod
    async def get_item(self, item_id: int) -> Any:
        """Retrieve a single item by ID."""
        pass

    @abstractmethod
    async def update_item(self, item_id: int, data: dict) -> Any:
        """Update an item and return the updated object."""
        pass

    @abstractmethod
    async def delete_item(self, item_id: int) -> None:
        """Delete an item by ID."""
        pass

    @abstractmethod
    async def filter_items(self, **filters) -> list:
        """Apply filters to list query."""
        pass

    @abstractmethod
    async def serialize_with_relations(self, item_id: int) -> Any:
        """Serialize an item with its related objects (FK relations)."""
        pass

    @abstractmethod
    async def serialize_nested_relations(self, item_id: int) -> Any:
        """Serialize an item with deep nested relations (2-3 levels).

        This tests the framework's ability to handle complex relationship graphs
        asynchronously, which is particularly challenging in Django's async context.
        """
        pass

    @abstractmethod
    async def serialize_reverse_relations(self, item_id: int) -> Any:
        """Serialize an item with reverse foreign key relations (prefetch_related).

        Tests async handling of one-to-many reverse relations, which requires
        prefetch_related in Django - notoriously difficult in async.
        """
        pass

    @abstractmethod
    async def serialize_many_to_many(self, item_id: int) -> Any:
        """Serialize an item with many-to-many relations.

        Tests async M2M serialization, which requires special handling in Django.
        """
        pass

    @abstractmethod
    async def complex_query_with_relations(self, **filters) -> list:
        """Perform a complex query with filters, relations, and pagination.

        Real-world scenario: list endpoint with filters, nested relations,
        and pagination - all in async context.
        """
        pass


class BenchmarkRunner:
    """Utility class to run benchmarks consistently across frameworks."""

    DEFAULT_ITERATIONS = 100

    @staticmethod
    def benchmark_sync(func: Callable, iterations: int = DEFAULT_ITERATIONS) -> dict:
        """Run a synchronous function multiple times and return timing statistics."""
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

    @staticmethod
    async def benchmark_async(func: Callable, iterations: int = DEFAULT_ITERATIONS) -> dict:
        """Run an async function multiple times and return timing statistics."""
        times = []
        for _ in range(iterations):
            start = time.perf_counter()
            await func()
            elapsed = (time.perf_counter() - start) * 1000
            times.append(elapsed)

        return {
            "iterations": iterations,
            "min_ms": round(min(times), 4),
            "max_ms": round(max(times), 4),
            "avg_ms": round(statistics.mean(times), 4),
            "median_ms": round(statistics.median(times), 4),
        }
