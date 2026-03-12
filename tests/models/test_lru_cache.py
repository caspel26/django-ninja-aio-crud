from django.test import tag, TestCase

from ninja_aio.models.utils import LRUCache


@tag("lru_cache")
class LRUCacheTestCase(TestCase):
    def test_basic_set_and_get(self):
        cache = LRUCache(maxsize=10)
        cache.set("a", [1, 2, 3])
        self.assertEqual(cache.get("a"), [1, 2, 3])

    def test_get_missing_key_returns_none(self):
        cache = LRUCache(maxsize=10)
        self.assertIsNone(cache.get("missing"))

    def test_contains(self):
        cache = LRUCache(maxsize=10)
        cache.set("x", "value")
        self.assertIn("x", cache)
        self.assertNotIn("y", cache)

    def test_len(self):
        cache = LRUCache(maxsize=10)
        self.assertEqual(len(cache), 0)
        cache.set("a", 1)
        cache.set("b", 2)
        self.assertEqual(len(cache), 2)

    def test_clear(self):
        cache = LRUCache(maxsize=10)
        cache.set("a", 1)
        cache.set("b", 2)
        cache.clear()
        self.assertEqual(len(cache), 0)
        self.assertIsNone(cache.get("a"))

    def test_eviction_when_maxsize_exceeded(self):
        cache = LRUCache(maxsize=3)
        cache.set("a", 1)
        cache.set("b", 2)
        cache.set("c", 3)
        # Adding a 4th entry should evict "a" (oldest)
        cache.set("d", 4)
        self.assertEqual(len(cache), 3)
        self.assertIsNone(cache.get("a"))
        self.assertEqual(cache.get("b"), 2)
        self.assertEqual(cache.get("d"), 4)

    def test_get_promotes_to_most_recent(self):
        cache = LRUCache(maxsize=3)
        cache.set("a", 1)
        cache.set("b", 2)
        cache.set("c", 3)
        # Access "a" to promote it
        cache.get("a")
        # Now "b" is the least recently used
        cache.set("d", 4)
        self.assertIsNone(cache.get("b"))
        self.assertEqual(cache.get("a"), 1)

    def test_update_existing_key(self):
        cache = LRUCache(maxsize=3)
        cache.set("a", 1)
        cache.set("b", 2)
        cache.set("c", 3)
        # Update "a" — should promote it and change value
        cache.set("a", 10)
        self.assertEqual(cache.get("a"), 10)
        # "b" is now the oldest
        cache.set("d", 4)
        self.assertIsNone(cache.get("b"))
        self.assertEqual(cache.get("a"), 10)
        self.assertEqual(len(cache), 3)

    def test_default_maxsize(self):
        cache = LRUCache()
        self.assertEqual(cache._maxsize, 512)

    def test_returns_copy_safe_values(self):
        cache = LRUCache(maxsize=10)
        original = [1, 2, 3]
        cache.set("key", original)
        retrieved = cache.get("key")
        # Verify it returns the same reference (copy is caller's responsibility)
        self.assertIs(retrieved, original)
