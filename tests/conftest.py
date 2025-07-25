"""
Pytest configuration for GUI tests.
This file manages global test resources to prevent memory leaks.
"""

import pytest
import tkinter as tk
import gc
import threading
import sys
import os
import subprocess
import tempfile
from pathlib import Path
from unittest.mock import patch
from concurrent.futures import ThreadPoolExecutor, Future

# Silence tkinter/asyncio deprecation warnings
pytestmark = pytest.mark.filterwarnings('ignore::DeprecationWarning')


# Global root window for all tests
_global_root = None
_original_thread_class = None


def pytest_configure(config):
    """Configure pytest - set up global resources."""
    global _global_root, _original_thread_class
    
    # MEMORY FIX: Create a single global root window
    # that will be reused across tests instead of creating new Tk() instances
    try:
        _global_root = tk.Tk()
        _global_root.withdraw()  # Hide the window
        tk._default_root = _global_root
    except tk.TclError as e:
        if "no display name and no $DISPLAY" in str(e):
            # Running in headless environment (e.g., CI)
            # Skip Tk initialization and let individual tests handle it
            _global_root = None
            print("Warning: Running in headless environment - GUI tests will be skipped")
        else:
            raise
    
    # Mock threading globally to prevent background threads in tests
    class MockThread:
        def __init__(self, target=None, daemon=False, args=(), kwargs={}, *extra_args, **extra_kwargs):
            self.target = target
            self.daemon = daemon
            self.args = args
            self.kwargs = kwargs
            self._started = False
            self._alive = False
        
        def start(self):
            self._started = True
            self._alive = True
            # Actually run the target function to allow ThreadPoolExecutor to work
            if self.target:
                try:
                    self.target(*self.args, **self.kwargs)
                finally:
                    self._alive = False
        
        def join(self, timeout=None):
            pass
        
        def is_alive(self):
            return self._alive
    
    # Mock ThreadPoolExecutor to run tasks synchronously
    class MockThreadPoolExecutor:
        def __init__(self, max_workers=None, thread_name_prefix="MockThread"):
            self.max_workers = max_workers
            self.thread_name_prefix = thread_name_prefix
            
        def submit(self, fn, *args, **kwargs):
            # Run synchronously and return a completed future
            future = Future()
            try:
                result = fn(*args, **kwargs)
                future.set_result(result)
            except Exception as e:
                future.set_exception(e)
            return future
            
        def shutdown(self, wait=True):
            pass
            
        def __enter__(self):
            return self
            
        def __exit__(self, exc_type, exc_val, exc_tb):
            pass
    
    _original_thread_class = threading.Thread
    threading.Thread = MockThread
    
    # Patch ThreadPoolExecutor globally and in specific modules
    patch('concurrent.futures.ThreadPoolExecutor', MockThreadPoolExecutor).start()
    # Patch the ThreadPoolExecutor import in update_history module
    patch('src.utils.update_history.ThreadPoolExecutor', MockThreadPoolExecutor).start()
    # Patch ThreadPoolExecutor in thread manager
    patch('src.utils.thread_manager.ThreadPoolExecutor', MockThreadPoolExecutor).start()


def pytest_unconfigure(config):
    """Clean up after all tests."""
    global _global_root, _original_thread_class
    
    # Restore original threading
    if _original_thread_class:
        threading.Thread = _original_thread_class
    
    # Destroy global root
    if _global_root:
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


@pytest.fixture(scope='function')
def gui_root():
    """Provide a root window for GUI tests."""
    global _global_root
    
    # Skip GUI tests in headless environment
    if _global_root is None:
        pytest.skip("Skipping GUI test - no display available")
    
    # Create a toplevel for this test
    test_window = tk.Toplevel(_global_root)
    test_window.withdraw()
    
    yield test_window
    
    # Cleanup
    try:
        test_window.after_cancel('all')
        for widget in test_window.winfo_children():
            try:
                widget.destroy()
            except:
                pass
        test_window.destroy()
    except:
        pass
    
    # Force garbage collection
    gc.collect()


@pytest.fixture
def tmp_cache_dir(tmp_path, monkeypatch):
    """Provide a temporary cache directory and patch get_cache_dir()."""
    cache_dir = tmp_path / "asuc_cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    
    # Patch environment variables
    monkeypatch.setenv('ASUC_CACHE_DIR', str(cache_dir))
    
    # Patch the get_cache_dir function
    with patch('src.constants.get_cache_dir', return_value=cache_dir):
        yield cache_dir


@pytest.fixture
def history_enabled_config(tmp_cache_dir):
    """Provide a Config instance with update history enabled."""
    from src.config import Config
    import tempfile
    
    # Create a temporary config file
    config_file = tmp_cache_dir / "test_config.json"
    config_content = {
        "update_history_enabled": True,
        "update_history_retention_days": 3,
        "cache_ttl_hours": 1,
        "max_news_items": 10,
        "max_news_age_days": 14
    }
    
    import json
    with open(config_file, 'w') as f:
        json.dump(config_content, f)
    
    config = Config(str(config_file))
    return config


@pytest.fixture
def cli_runner(tmp_cache_dir, monkeypatch):
    """Wrapper for running CLI commands in tests."""
    def run_cli(*args, **kwargs):
        """Run CLI command with proper environment setup."""
        # Set up environment
        env = os.environ.copy()
        env['ASUC_CACHE_DIR'] = str(tmp_cache_dir)
        
        # Build command
        cmd = [sys.executable, '-m', 'src.cli.main'] + list(args)
        
        # Set defaults
        kwargs.setdefault('capture_output', True)
        kwargs.setdefault('text', True)
        kwargs.setdefault('env', env)
        
        # Run command
        return subprocess.run(cmd, **kwargs)
    
    return run_cli


@pytest.fixture(autouse=True)
def cleanup_after_test():
    """Automatically clean up after each test."""
    yield
    
    # Force garbage collection after each test
    gc.collect()
    
    # Clear any tkinter internal caches
    try:
        tk._default_root = None
    except:
        pass 