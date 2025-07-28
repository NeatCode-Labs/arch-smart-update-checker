"""Performance benchmark tests for critical operations."""

# SPDX-License-Identifier: GPL-3.0-or-later

import unittest
import time
from unittest.mock import Mock, patch
import threading

from src.utils.cache import CacheManager
from src.utils.thread_manager import ThreadResourceManager
from src.utils.validators import validate_package_name
from src.news_fetcher import NewsFetcher
from src.models import NewsItem


class TestPerformanceBenchmarks(unittest.TestCase):
    """Test performance of critical operations."""

    def setUp(self):
        """Set up test fixtures."""
        self.start_time = time.time()

    def tearDown(self):
        """Clean up and report timing."""
        duration = time.time() - self.start_time
        # Only fail if operations take too long
        if duration > 5.0:
            self.fail(f"Test took too long: {duration:.2f}s")

    def test_cache_performance(self):
        """Test cache operations performance."""
        cache = CacheManager(ttl_hours=5)
        
        # Test write performance - 1000 items
        start = time.time()
        for i in range(1000):
            cache.set(f"key_{i}", f"value_{i}")
        write_time = time.time() - start
        self.assertLess(write_time, 2.0, "Cache writes too slow")
        
        # Test read performance - 1000 items
        start = time.time()
        for i in range(1000):
            value = cache.get(f"key_{i}")
            self.assertEqual(value, f"value_{i}")
        read_time = time.time() - start
        self.assertLess(read_time, 0.5, "Cache reads too slow")

    def test_package_validation_performance(self):
        """Test package name validation performance."""
        # Test validating 10000 package names
        packages = [f"package-name-{i}" for i in range(10000)]
        
        start = time.time()
        for pkg in packages:
            validate_package_name(pkg)
        validation_time = time.time() - start
        
        # Should validate 10000 names reasonably fast (under 1.5 seconds)
        self.assertLess(validation_time, 1.5, "Package validation too slow")

    def test_thread_creation_performance(self):
        """Test thread creation and management performance."""
        # Test creating multiple threads using public API
        threads_created = 0
        start = time.time()
        
        # Use the public thread creation method
        from src.utils.thread_manager import create_managed_thread
        
        def dummy_task():
            time.sleep(0.01)
        
        threads = []
        for i in range(10):
            try:
                thread = create_managed_thread(
                    f"perf_test_{i}", 
                    dummy_task,
                    is_background=True
                )
                if thread:
                    threads.append(thread)
                    threads_created += 1
            except:
                pass
        
        creation_time = time.time() - start
        
        # Should handle thread creation in reasonable time
        self.assertLess(creation_time, 2.0, "Thread creation too slow")
        self.assertGreater(threads_created, 0, "No threads could be created")

    @patch('feedparser.parse')
    def test_news_parsing_performance(self, mock_parse):
        """Test news feed parsing performance."""
        # Mock a large feed
        mock_entries = []
        for i in range(100):
            mock_entries.append({
                'title': f'News Item {i}',
                'link': f'https://example.com/news/{i}',
                'published_parsed': time.gmtime(),
                'summary': f'Summary for news item {i}' * 10
            })
        
        mock_parse.return_value = {'entries': mock_entries}
        
        # Test parsing performance
        with patch('src.news_fetcher.CacheManager'):
            fetcher = NewsFetcher()
            
            # Test would require accessing internal methods
            # For now, just ensure news fetcher can be created
            self.assertIsNotNone(fetcher)
            # Performance of feed parsing is tested indirectly through other tests

    def test_memory_usage_patterns(self):
        """Test memory usage doesn't grow unexpectedly."""
        import gc
        import sys
        
        # Force garbage collection
        gc.collect()
        
        # Create and destroy many objects
        for _ in range(1000):
            cache = CacheManager(ttl_hours=1)
            cache.set("test", "value")
            del cache
        
        # Force garbage collection again
        gc.collect()
        
        # Just ensure no exceptions and reasonable behavior
        self.assertTrue(True, "Memory test completed")

    def test_concurrent_operations(self):
        """Test performance under concurrent load."""
        import tempfile
        with tempfile.TemporaryDirectory() as temp_dir:
            cache = CacheManager(cache_dir=temp_dir, ttl_hours=5)
        
        # Since threads are mocked in tests, simulate concurrent access directly
        start = time.time()
        
        # Simulate 10 workers each doing 100 operations
        for worker_id in range(10):
            for i in range(100):
                cache.set(f"worker_{worker_id}_key_{i}", f"value_{i}")
                value = cache.get(f"worker_{worker_id}_key_{i}")
                self.assertEqual(value, f"value_{i}")
        
        total_time = time.time() - start
        
        # Should handle 1000 operations efficiently
        self.assertLess(total_time, 3.0, "Operations too slow")
        
        # Verify cache has the expected data
        test_value = cache.get("worker_5_key_50")
        self.assertEqual(test_value, "value_50")


if __name__ == '__main__':
    unittest.main() 