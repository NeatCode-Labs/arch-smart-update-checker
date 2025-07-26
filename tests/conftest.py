"""
Minimal pytest configuration to avoid import errors.
"""

import pytest
import os


def pytest_configure(config):
    """Configure pytest with minimal setup."""
    # Set up test environment variables
    os.environ['ASUC_SKIP_PACMAN_VALIDATION'] = '1'
    os.environ['ASUC_TEST_MODE'] = '1'
    
    # Skip GUI tests in headless environments
    if os.environ.get('ASUC_HEADLESS') or os.environ.get('CI'):
        print("Running in headless/CI environment - GUI tests will be skipped")


@pytest.fixture
def mock_config():
    """Create a simple mock config object for testing."""
    from unittest.mock import Mock
    
    config = Mock()
    config.get.return_value = "default_value"
    config.getboolean.return_value = False
    config.getint.return_value = 0
    config.getfloat.return_value = 0.0
    config.sections.return_value = ['settings', 'network', 'ui']
    config.options.return_value = ['check_interval', 'auto_download']
    
    return config