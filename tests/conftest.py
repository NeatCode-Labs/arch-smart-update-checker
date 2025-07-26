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
    
    # Set up common config methods
    def config_get(section, option, fallback=None):
        defaults = {
            ('settings', 'retention_days'): '365',
            ('settings', 'check_interval'): '60',
            ('settings', 'auto_download'): 'false',
            ('settings', 'enable_history'): 'true',
            ('network', 'timeout'): '30',
            ('network', 'retries'): '3',
            ('ui', 'theme'): 'default',
        }
        return defaults.get((section, option), fallback or "default_value")
    
    def config_getboolean(section, option, fallback=False):
        value = config_get(section, option, str(fallback).lower())
        return value.lower() in ('true', '1', 'yes', 'on')
    
    def config_getint(section, option, fallback=0):
        value = config_get(section, option, str(fallback))
        try:
            return int(value)
        except (ValueError, TypeError):
            return fallback
    
    def config_getfloat(section, option, fallback=0.0):
        value = config_get(section, option, str(fallback))
        try:
            return float(value)
        except (ValueError, TypeError):
            return fallback
    
    config.get.side_effect = config_get
    config.getboolean.side_effect = config_getboolean
    config.getint.side_effect = config_getint
    config.getfloat.side_effect = config_getfloat
    config.sections.return_value = ['settings', 'network', 'ui']
    config.options.return_value = ['check_interval', 'auto_download', 'enable_history', 'retention_days']
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