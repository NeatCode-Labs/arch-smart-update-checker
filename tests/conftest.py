"""
Pytest configuration for GUI tests.
This file manages global test resources to prevent memory leaks.
"""

import pytest
import gc
import threading
import sys
import os
import subprocess
import tempfile
import signal
from pathlib import Path
from unittest.mock import patch, Mock
from concurrent.futures import ThreadPoolExecutor, Future

# Try to import tkinter but handle gracefully if not available
try:
    import tkinter as tk
    TKINTER_AVAILABLE = True
except ImportError:
    TKINTER_AVAILABLE = False
    # Create a mock tkinter module for tests that might import it
    class MockTk:
        def __init__(self):
            pass
        def withdraw(self):
            pass
        def destroy(self):
            pass
        def quit(self):
            pass
        def after_cancel(self, *args):
            pass
        def winfo_children(self):
            return []
    
    tk = type('tk', (), {'Tk': MockTk})()

# Silence tkinter/asyncio deprecation warnings
pytestmark = pytest.mark.filterwarnings('ignore::DeprecationWarning')


# Global root window for all tests
_global_root = None
_original_thread_class = None


def pytest_configure(config):
    """Configure pytest - set up global resources."""
    global _global_root, _original_thread_class
    
    # Set up test environment variables
    os.environ['ASUC_SKIP_PACMAN_VALIDATION'] = '1'
    os.environ['ASUC_TEST_MODE'] = '1'
    
    # Skip GUI tests in headless environments
    if os.environ.get('ASUC_HEADLESS') or os.environ.get('CI'):
        print("Running in headless/CI environment - GUI tests will be skipped")

    # Create a mock for subprocess operations to prevent actual system calls
    def mock_subprocess_run(*args, **kwargs):
        """Mock subprocess.run to prevent actual system calls during tests."""
        from subprocess import CompletedProcess
        cmd = args[0] if args else kwargs.get('args', [])
        cmd_str = ' '.join(cmd) if isinstance(cmd, list) else str(cmd)
        
        # Mock common pacman commands
        if 'pacman -Sy' in cmd_str:
            return CompletedProcess(cmd, 0, '', '')
        elif 'pacman -Qu' in cmd_str:
            return CompletedProcess(cmd, 0, '', '')
        elif 'pacman -Si' in cmd_str:
            return CompletedProcess(cmd, 0, '', '')
        elif 'pacman -Qi' in cmd_str:
            return CompletedProcess(cmd, 0, '', '')
        elif 'pacman -Q' in cmd_str:
            return CompletedProcess(cmd, 0, '', '')
        else:
            # Default mock response
            return CompletedProcess(cmd, 0, '', '')
    
    # Apply safer mocks
    patch('subprocess.run', mock_subprocess_run).start()
    patch('subprocess.check_output', lambda *args, **kwargs: b'').start()
    patch('subprocess.Popen', Mock).start()
    
    # Store original thread class for restoration later
    _original_thread_class = threading.Thread
    
    # Mock ThreadPoolExecutor to run tasks synchronously in tests
    class MockThreadPoolExecutor:
        """Mock executor that runs tasks synchronously to prevent threading issues."""
        
        def __init__(self, *args, **kwargs):
            pass
            
        def __enter__(self):
            return self
            
        def __exit__(self, *args):
            pass
            
        def submit(self, fn, *args, **kwargs):
            """Execute function synchronously and return a mock Future."""
            try:
                result = fn(*args, **kwargs)
                future = Future()
                future.set_result(result)
                return future
            except Exception as e:
                future = Future()
                future.set_exception(e)
                return future
        
        def shutdown(self, wait=True):
            pass
    
    # Apply the ThreadPoolExecutor mock
    patch('concurrent.futures.ThreadPoolExecutor', MockThreadPoolExecutor).start()


def pytest_unconfigure(config):
    """Clean up after all tests."""
    global _global_root, _original_thread_class
    
    # Restore original threading if we had patched it
    if _original_thread_class:
        threading.Thread = _original_thread_class
    
    # Destroy global root
    if _global_root and TKINTER_AVAILABLE:
        try:
            _global_root.after_cancel('all')
            for widget in _global_root.winfo_children():
                try:
                    widget.destroy()
                except:
                    pass
            _global_root.destroy()
            _global_root.quit()
        except:
            pass
        finally:
            _global_root = None
    
    # Force garbage collection
    gc.collect()


@pytest.fixture
def temp_config_file():
    """Create a temporary config file for testing."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.conf', delete=False) as f:
        f.write("""
[settings]
check_interval = 1440
auto_download = false
notification_enabled = true
log_level = INFO

[network]
timeout = 30
retries = 3
parallel_downloads = 5

[ui]
theme = light
show_news = true
show_packages = true
""")
        temp_path = f.name
    
    yield temp_path
    
    # Cleanup
    try:
        os.unlink(temp_path)
    except FileNotFoundError:
        pass


@pytest.fixture
def mock_config():
    """Create a mock config object for testing."""
    from unittest.mock import Mock
    
    config = Mock()
    config.get.return_value = "default_value"
    config.getboolean.return_value = False
    config.getint.return_value = 0
    config.getfloat.return_value = 0.0
    config.sections.return_value = ['settings', 'network', 'ui']
    config.options.return_value = ['check_interval', 'auto_download']
    
    return config


@pytest.fixture
def gui_root():
    """Create a test GUI root window if running in a GUI environment."""
    if not TKINTER_AVAILABLE or os.environ.get('ASUC_HEADLESS') or os.environ.get('CI'):
        # Skip GUI tests in headless environments
        pytest.skip("Skipping GUI test in headless environment")
    
    # Use the global root if available
    if _global_root:
        return _global_root
    
    # Create a new root for this test
    root = tk.Tk()
    root.withdraw()
    
    yield root
    
    # Clean up
    try:
        for widget in root.winfo_children():
            widget.destroy()
        root.destroy()
    except:
        pass


# Helper function for GUI tests
def get_global_root():
    """Get the global root window for GUI tests."""
    global _global_root
    if not TKINTER_AVAILABLE or os.environ.get('ASUC_HEADLESS') or os.environ.get('CI'):
        return None
    return _global_root