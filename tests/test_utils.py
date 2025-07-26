"""
Test utilities and basic functionality.
"""

import unittest
import os
import sys
import pytest
from unittest.mock import Mock, patch

class TestBasicFunctionality(unittest.TestCase):
    """Test basic functionality to verify test infrastructure works."""

    def test_imports_work(self):
        """Test that core imports work correctly."""
        try:
            from src.config import Config
            from src.checker import UpdateChecker
            from src.utils.validators import validate_package_name
            self.assertTrue(True, "All imports successful")
        except ImportError as e:
            self.fail(f"Import failed: {e}")

    def test_environment_setup(self):
        """Test that test environment is set up correctly."""
        self.assertEqual(os.environ.get('ASUC_SKIP_PACMAN_VERIFY'), '1')
        self.assertTrue(True, "Environment setup correct")

    def test_package_validation(self):
        """Test package name validation function."""
        from src.utils.validators import validate_package_name
        
        # Valid package names
        self.assertTrue(validate_package_name("firefox"))
        self.assertTrue(validate_package_name("package-name"))
        self.assertTrue(validate_package_name("test123"))
        
        # Invalid package names
        self.assertFalse(validate_package_name(""))
        self.assertFalse(validate_package_name("../invalid"))
        self.assertFalse(validate_package_name("pkg with spaces"))

    def test_config_creation(self):
        """Test basic config creation."""
        from src.config import Config
        import tempfile
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            f.write('{"theme": "light", "debug_mode": false}')
            config_file = f.name
        
        try:
            config = Config(config_file)
            self.assertIsNotNone(config)
            self.assertEqual(config.get('theme'), 'light')
        finally:
            os.unlink(config_file)

    @pytest.mark.timeout(10)
    def test_cache_operations(self):
        """Test cache operations work without hanging."""
        from src.utils.cache import CacheManager
        
        cache = CacheManager(ttl_hours=1)
        cache.set("test_key", "test_value")
        value = cache.get("test_key")
        self.assertEqual(value, "test_value")

if __name__ == '__main__':
    unittest.main() 