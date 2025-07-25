"""
Unit tests for cache management.
"""

import unittest
import tempfile
import shutil
import json
import time
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch
from typing import Dict, Any
import os

from src.utils.cache import CacheManager
from src.utils.cache import CacheError


class TestCacheManager(unittest.TestCase):
    """Test cache management functionality."""

    def setUp(self) -> None:
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.cache_manager = CacheManager(cache_dir=self.temp_dir, ttl_hours=1)

    def tearDown(self) -> None:
        """Clean up test fixtures."""
        shutil.rmtree(self.temp_dir)

    def test_cache_set_and_get(self) -> None:
        """Test setting and getting cache data."""
        test_data: Dict[str, Any] = {"test": "data", "number": 42}
        self.cache_manager.set("test_key", test_data)

        retrieved_data = self.cache_manager.get("test_key")
        self.assertEqual(retrieved_data, test_data)

    def test_cache_expiration(self):
        """Test cache expiration."""
        # Create cache manager with very short TTL
        short_cache = CacheManager(cache_dir=self.temp_dir, ttl_hours=0.000001)  # ~0.0036 seconds

        test_data = {"test": "data"}
        short_cache.set("expire_key", test_data)

        # Data should be available immediately
        self.assertEqual(short_cache.get("expire_key"), test_data)

        # Wait for expiration
        time.sleep(0.05)  # 50ms should be enough

        # Data should be expired
        self.assertIsNone(short_cache.get("expire_key"))

    def test_cache_miss(self):
        """Test cache miss behavior."""
        result = self.cache_manager.get("nonexistent_key")
        self.assertIsNone(result)

    def test_cache_clear(self):
        """Test clearing cache."""
        self.cache_manager.set("key1", "data1")
        self.cache_manager.set("key2", "data2")

        # Verify data exists
        self.assertEqual(self.cache_manager.get("key1"), "data1")
        self.assertEqual(self.cache_manager.get("key2"), "data2")

        # Clear cache
        self.cache_manager.clear()

        # Verify data is gone
        self.assertIsNone(self.cache_manager.get("key1"))
        self.assertIsNone(self.cache_manager.get("key2"))

    def test_cache_is_valid(self):
        """Test cache validity checking."""
        test_data = {"test": "data"}
        self.cache_manager.set("valid_key", test_data)

        # Should be valid immediately
        self.assertTrue(self.cache_manager.is_valid("valid_key"))

        # Should be invalid for non-existent key
        self.assertFalse(self.cache_manager.is_valid("invalid_key"))

    def test_cache_file_sanitization(self):
        """Test cache key sanitization for filenames."""
        # Test with special characters
        self.cache_manager.set("test/key:with*chars", "data")

        # Should be retrievable
        result = self.cache_manager.get("test/key:with*chars")
        self.assertEqual(result, "data")

        # Check that file was created with sanitized name
        cache_files = list(Path(self.temp_dir).glob("*.json"))
        self.assertEqual(len(cache_files), 1)

    def test_cache_with_complex_data(self):
        """Test caching complex data structures."""
        complex_data = {
            "list": [1, 2, 3],
            "dict": {"nested": "value"},
            "string": "test",
            "number": 42,
            "boolean": True,
            "none": None
        }

        self.cache_manager.set("complex_key", complex_data)
        retrieved = self.cache_manager.get("complex_key")

        self.assertEqual(retrieved, complex_data)

    def test_cache_corruption_handling(self):
        """Test handling of corrupted cache files."""
        # Create a corrupted cache file
        cache_file = Path(self.temp_dir) / "corrupted.json"
        with open(cache_file, 'w') as f:
            f.write("invalid json content")

        # Should handle gracefully
        result = self.cache_manager.get("corrupted")
        self.assertIsNone(result)

        # Corrupted file should be removed
        self.assertFalse(cache_file.exists())

    def test_cache_directory_creation(self):
        """Test automatic cache directory creation."""
        new_cache_dir = Path(self.temp_dir) / "new_cache_dir"
        CacheManager(cache_dir=str(new_cache_dir))
        # Directory should be created
        self.assertTrue(new_cache_dir.exists())
        self.assertTrue(new_cache_dir.is_dir())

    def test_cache_write_error_handling(self):
        """Test handling of cache write errors."""
        # Mock permission error during set operation
        with patch("pathlib.Path.mkdir") as mock_mkdir:
            # Let initialization succeed
            cache_manager = CacheManager(cache_dir="/tmp/test_cache")
            
            # Make set operation fail
            with patch("builtins.open", side_effect=PermissionError("Permission denied")):
                # Should raise CacheError when trying to write
                with self.assertRaises(CacheError) as cm:
                    cache_manager.set("test_key", {"data": "value"})
                
                self.assertIn("Cannot write to cache", str(cm.exception))

    def test_cache_manager_cleanup(self):
        # Ensure cache directory is cleaned up after clear
        self.cache_manager.set("cleanup_key", "cleanup_data")
        self.cache_manager.clear()
        cache_files = list(Path(self.temp_dir).glob("*.json"))
        self.assertEqual(len(cache_files), 0)

    def test_cache_manager_thread_safety(self):
        # Placeholder: Thread safety test not implemented
        pass

    def test_cache_get_nonexistent(self) -> None:
        """Test getting non-existent cache data."""
        data = self.cache_manager.get("nonexistent_key")
        self.assertIsNone(data)

    def test_cache_ttl_expired(self) -> None:
        """Test cache TTL expiration."""
        test_data = {"test": "data"}
        self.cache_manager.set("test_key", test_data)

        # Manually expire the cache by modifying the timestamp
        cache_file = os.path.join(self.cache_manager.cache_dir, "test_key.json")
        with open(cache_file, 'r') as f:
            cache_data = json.load(f)

        # Set timestamp to 2 hours ago (beyond 1 hour TTL)
        cache_data['timestamp'] = (datetime.now() - timedelta(hours=2)).isoformat()

        with open(cache_file, 'w') as f:
            json.dump(cache_data, f)

        # Data should be expired
        data = self.cache_manager.get("test_key")
        self.assertIsNone(data)

    def test_cache_ttl_valid(self) -> None:
        """Test cache TTL when still valid."""
        test_data = {"test": "data"}
        self.cache_manager.set("test_key", test_data)

        # Data should still be valid
        data = self.cache_manager.get("test_key")
        self.assertEqual(data, test_data)

    def test_cache_invalid_json(self) -> None:
        """Test handling of invalid JSON in cache files."""
        # Create a cache file with invalid JSON
        cache_file = os.path.join(self.cache_manager.cache_dir, "invalid_key.json")
        with open(cache_file, 'w') as f:
            f.write("invalid json content")

        # Should return None for invalid JSON
        data = self.cache_manager.get("invalid_key")
        self.assertIsNone(data)

    def test_cache_missing_timestamp(self) -> None:
        """Test handling of cache files without timestamp."""
        test_data = {"test": "data"}
        self.cache_manager.set("test_key", test_data)

        # Manually remove timestamp from cache file
        cache_file = os.path.join(self.cache_manager.cache_dir, "test_key.json")
        with open(cache_file, 'r') as f:
            cache_data = json.load(f)

        del cache_data['timestamp']

        with open(cache_file, 'w') as f:
            json.dump(cache_data, f)

        # Should return None for missing timestamp
        data = self.cache_manager.get("test_key")
        self.assertIsNone(data)

    def test_cache_manager_initialization(self) -> None:
        """Test cache manager initialization."""
        # Test with custom TTL
        custom_cache = CacheManager(ttl_hours=2)
        self.assertEqual(custom_cache.ttl_hours, 2)

        # Test default TTL
        default_cache = CacheManager()
        self.assertEqual(default_cache.ttl_hours, 1)

    def test_cache_manager_with_temp_dir(self) -> None:
        """Test cache manager with temporary directory."""
        with tempfile.TemporaryDirectory() as temp_dir:
            cache_manager = CacheManager(cache_dir=temp_dir)
            test_data = {"test": "data"}
            cache_manager.set("test_key", test_data)

            retrieved_data = cache_manager.get("test_key")
            self.assertEqual(retrieved_data, test_data)


if __name__ == '__main__':
    unittest.main()
 