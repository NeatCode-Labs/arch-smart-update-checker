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
import signal
from pathlib import Path
from unittest.mock import patch, Mock
from concurrent.futures import ThreadPoolExecutor, Future

# Silence tkinter/asyncio deprecation warnings
pytestmark = pytest.mark.filterwarnings('ignore::DeprecationWarning')


# Global root window for all tests
_global_root = None
_original_thread_class = None


def pytest_configure(config):
    """Configure pytest - set up global resources."""
    global _global_root, _original_thread_class
    
    # Set up test environment variables
    os.environ['ASUC_SKIP_PACMAN_VERIFY'] = '1'
    os.environ['ASUC_TEST_MODE'] = '1'
    
    # Force headless mode in CI
    if os.environ.get('CI'):
        os.environ['ASUC_HEADLESS'] = '1'
    
    # MEMORY FIX: Create a single global root window
    # that will be reused across tests instead of creating new Tk() instances
    try:
        _global_root = tk.Tk()
        _global_root.withdraw()  # Hide the window
        tk._default_root = _global_root
        
        # Set up a timeout handler for GUI operations
        def timeout_handler():
            try:
                _global_root.update_idletasks()
            except:
                pass
        
        # Schedule periodic updates to prevent hanging
        _global_root.after(100, timeout_handler)
        
    except tk.TclError as e:
        if "no display name and no $DISPLAY" in str(e):
            # Running in headless environment (e.g., CI)
            # Skip Tk initialization and let individual tests handle it
            _global_root = None
            print("Warning: Running in headless environment - GUI tests will be skipped")
        else:
            raise
    
    # Store original thread class for restoration later
    _original_thread_class = threading.Thread
    
    # Mock ThreadPoolExecutor to run tasks synchronously
    class MockThreadPoolExecutor:
        def __init__(self, max_workers=None, thread_name_prefix="MockThread"):
            self.max_workers = max_workers
            self.thread_name_prefix = thread_name_prefix
            
        def submit(self, fn, *args, **kwargs):
            # Run synchronously and return a completed future
            future = Future()
            try:
                # Add timeout to prevent hanging
                import signal
                
                def timeout_handler(signum, frame):
                    raise TimeoutError("Task execution timed out")
                
                old_handler = signal.signal(signal.SIGALRM, timeout_handler)
                signal.alarm(30)  # 30 second timeout
                
                try:
                    result = fn(*args, **kwargs)
                    future.set_result(result)
                except Exception as e:
                    future.set_exception(e)
                finally:
                    signal.alarm(0)
                    signal.signal(signal.SIGALRM, old_handler)
                    
            except Exception as e:
                future.set_exception(e)
            return future
            
        def shutdown(self, wait=True):
            pass
            
        def __enter__(self):
            return self
            
        def __exit__(self, exc_type, exc_val, exc_tb):
            pass
    
    # Patch ThreadPoolExecutor globally and in specific modules
    import concurrent.futures
    concurrent.futures.ThreadPoolExecutor = MockThreadPoolExecutor
    
    # Import the utils modules that use ThreadPoolExecutor and patch them
    try:
        import src.utils.thread_manager
        src.utils.thread_manager.ThreadPoolExecutor = MockThreadPoolExecutor
    except ImportError:
        pass
    
    try:
        import src.utils.timer_manager  
        src.utils.timer_manager.ThreadPoolExecutor = MockThreadPoolExecutor
    except ImportError:
        pass
    
    # Mock PackageManager._verify_pacman_available globally to prevent pacman errors in CI
    try:
        patcher = patch('src.package_manager.PackageManager._verify_pacman_available')
        mock_verify = patcher.start()
        mock_verify.return_value = None  # Mock to always succeed (returns None)
        
        # Register cleanup function to stop the patcher
        import atexit
        atexit.register(patcher.stop)
    except Exception as e:
        print(f"Warning: Could not mock PackageManager._verify_pacman_available: {e}")
    
    # Mock SecureSubprocess for tests that don't have pacman
    def mock_secure_subprocess_run(cmd, *args, **kwargs):
        """Mock SecureSubprocess.run for testing."""
        from subprocess import CompletedProcess
        
        # Handle different commands
        cmd_str = ' '.join(cmd) if isinstance(cmd, list) else cmd
        
        if 'pacman --version' in cmd_str:
            return CompletedProcess(cmd, 0, 'pacman v6.0.0\n', '')
        elif 'checkupdates' in cmd_str:
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
    
    # Apply the mock
    patch('src.utils.subprocess_wrapper.SecureSubprocess.run', mock_secure_subprocess_run).start()
    patch('src.utils.subprocess_wrapper.SecureSubprocess.validate_command', lambda cmd: True).start()
    patch('src.utils.subprocess_wrapper.SecureSubprocess._find_command_path', lambda cmd: f'/usr/bin/{cmd}').start()


def pytest_unconfigure(config):
    """Clean up after all tests."""
    global _global_root, _original_thread_class
    
    # Restore original threading if we had patched it
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
        env['ASUC_SKIP_PACMAN_VERIFY'] = '1'  # Skip pacman verification in subprocess
        
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


@pytest.fixture
def mock_config():
    """Provide a properly mocked Config object for tests."""
    from unittest.mock import Mock
    
    config = Mock()
    config.config = {
        'debug_mode': False,
        'verbose_logging': False,
        'theme': 'light',
        'window_width': 1200,
        'window_height': 800,
        'auto_check_interval': 60
    }
    config.get.side_effect = lambda key, default=None: config.config.get(key, default)
    config.get_feeds.return_value = []
    config.load_settings.return_value = {}
    
    # Make batch_update work as a context manager
    config.batch_update.return_value.__enter__ = Mock(return_value=None)
    config.batch_update.return_value.__exit__ = Mock(return_value=None)
    
    return config


@pytest.fixture
def mock_checker():
    """Provide a properly mocked UpdateChecker object for tests."""
    from unittest.mock import Mock
    
    checker = Mock()
    checker.last_news_items = []
    checker.get_available_updates.return_value = []
    
    return checker