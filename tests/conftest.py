"""
Minimal pytest configuration to avoid import errors.
"""

import pytest
import os
from pathlib import Path
from unittest.mock import Mock
import subprocess
import sys


def pytest_configure(config):
    """Configure pytest with minimal setup."""
    # Set up test environment variables
    os.environ['ASUC_SKIP_PACMAN_VALIDATION'] = '1'
    os.environ['ASUC_SKIP_PACMAN_VERIFY'] = '1'  # Used by PackageManager
    os.environ['ASUC_TEST_MODE'] = '1'
    
    # Skip GUI tests in headless environments
    if os.environ.get('ASUC_HEADLESS') or os.environ.get('CI'):
        print("Running in headless/CI environment - GUI tests will be skipped")


@pytest.fixture
def mock_config():
    """Create a simple mock config object for testing."""
    config = Mock()
    config.get.return_value = "default_value"
    config.getboolean.return_value = False
    config.getint.return_value = 0
    config.getfloat.return_value = 0.0
    config.sections.return_value = ['settings', 'network', 'ui']
    config.options.return_value = ['check_interval', 'auto_download']
    
    return config


@pytest.fixture
def tmp_cache_dir(tmp_path):
    """Create a temporary cache directory for testing."""
    cache_dir = tmp_path / "cache"
    cache_dir.mkdir(exist_ok=True)
    return cache_dir


@pytest.fixture
def history_enabled_config():
    """Create a mock config with history enabled for testing."""
    config = Mock()
    
    # Mock config data
    config_data = {
        'cache_ttl_hours': 2,
        'check_interval': 60,
        'auto_download': False,
        'enable_history': True,
        'retention_days': 365,
        'timeout': 30,
        'retries': 3,
        'theme': 'default',
        'news_limit': 10,
        'show_packages': True,
    }
    
    # Set up the config property to return the mock data
    config.config = config_data
    config.config_file = "/tmp/test_config.json"
    
    # Set up common config methods
    def config_get(key, fallback=None):
        return config_data.get(key, fallback)
    
    def config_getboolean(key, fallback=False):
        value = config_data.get(key, fallback)
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            return value.lower() in ('true', '1', 'yes', 'on')
        return bool(value)
    
    def config_getint(key, fallback=0):
        value = config_data.get(key, fallback)
        if isinstance(value, int):
            return value
        try:
            return int(value)
        except (ValueError, TypeError):
            return fallback
    
    def config_getfloat(key, fallback=0.0):
        value = config_data.get(key, fallback)
        if isinstance(value, float):
            return value
        try:
            return float(value)
        except (ValueError, TypeError):
            return fallback
    
    def config_set(key, value):
        config_data[key] = value
    
    config.get.side_effect = config_get
    config.getboolean.side_effect = config_getboolean
    config.getint.side_effect = config_getint
    config.getfloat.side_effect = config_getfloat
    config.set.side_effect = config_set
    config.save_config.return_value = None
    config.sections.return_value = ['settings', 'network', 'ui']
    config.options.return_value = list(config_data.keys())
    config.has_section.return_value = True
    config.has_option.return_value = True
    
    return config


@pytest.fixture
def cli_runner():
    """Create a CLI runner for testing command-line functionality."""
    def run_cli(*args):
        """Run the CLI with the given arguments and return the result."""
        cmd = [sys.executable, '-m', 'src.cli.main'] + list(args)
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30,
                cwd=Path(__file__).parent.parent
            )
            return result
        except subprocess.TimeoutExpired:
            # Return a mock result for timeout
            mock_result = Mock()
            mock_result.returncode = 1
            mock_result.stdout = ""
            mock_result.stderr = "Command timed out"
            return mock_result
        except Exception as e:
            # Return a mock result for other errors
            mock_result = Mock()
            mock_result.returncode = 1
            mock_result.stdout = ""
            mock_result.stderr = str(e)
            return mock_result
    
    return run_cli