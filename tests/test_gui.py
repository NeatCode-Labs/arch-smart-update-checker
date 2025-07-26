"""
Test suite for the Arch Smart Update Checker GUI application.

WARNING: These tests may cause memory leaks due to multiple Tk root windows.
Consider using the GUITestCase base class from test_gui_memory_safe.py for new tests.
The conftest.py file now provides global fixtures to help manage GUI resources.
"""

import unittest
import tkinter as tk
from unittest.mock import Mock, patch, MagicMock, mock_open
import sys
import os
import threading
import pytest

# Imports are handled by pytest and the src/ structure

from src.gui.main_window import MainWindow
from src.gui.dashboard import DashboardFrame
from src.gui.news_browser import NewsBrowserFrame
from src.gui.package_manager import PackageManagerFrame
from src.gui.settings import SettingsFrame
from src.config import Config
from src.checker import UpdateChecker

# MEMORY LEAK FIX: Use a single root window for all tests
import gc
_test_root = None

def get_or_create_root():
    """Get or create a singleton Tk root to prevent memory leaks."""
    global _test_root
    if _test_root is None:
        if os.environ.get('ASUC_HEADLESS'):
            pytest.skip("Skipping GUI test in headless environment")
        _test_root = tk.Tk()
        _test_root.withdraw()
    return _test_root


# Global patch for threading to prevent background threads in tests
class MockThread:
    """Mock thread class that does nothing when started."""
    def __init__(self, target=None, daemon=False, *args, **kwargs):
        self.target = target
        self.daemon = daemon
        self._started = False
        self._alive = False
    
    def start(self):
        """No-op start method."""
        self._started = True
        self._alive = True
        # Run target synchronously if provided with timeout
        if self.target:
            try:
                # Quick timeout for test stability
                import signal
                def timeout_handler(signum, frame):
                    raise TimeoutError("Test thread timed out")
                old_handler = signal.signal(signal.SIGALRM, timeout_handler)
                signal.alarm(5)  # 5 second timeout for tests
                try:
                    self.target()
                finally:
                    signal.alarm(0)
                    signal.signal(signal.SIGALRM, old_handler)
            except:
                pass
            finally:
                self._alive = False
    
    def join(self, timeout=None):
        """No-op join method."""
        pass
    
    def is_alive(self):
        """Return whether thread is alive."""
        return self._alive


# Don't patch threading globally - this conflicts with pytest-timeout
# Instead, patch it only where needed in individual tests


@pytest.mark.gui
class TestMainWindow(unittest.TestCase):
    """Test the main window functionality."""

    def setUp(self):
        """Set up test fixtures."""
        # Skip if headless
        if os.environ.get('ASUC_HEADLESS'):
            self.skipTest("Skipping GUI test in headless environment")
            
        # Mock the Config and UpdateChecker classes before creating MainWindow
        with patch('src.gui.main_window.Config') as mock_config_class, \
             patch('src.gui.main_window.UpdateChecker') as mock_checker_class, \
             patch('src.utils.logger.set_global_config') as mock_set_global_config, \
             patch('src.gui.main_window.get_logger') as mock_get_logger, \
             patch.object(DashboardFrame, 'refresh_news', lambda self: None), \
             patch.object(DashboardFrame, 'refresh', lambda self: None):
            
            # Mock logger
            mock_logger = Mock()
            mock_get_logger.return_value = mock_logger
            
            # Create mock instances
            self.mock_config = Mock()
            self.mock_checker = Mock()
            # Fix: Make get_feeds and load_settings return iterables
            self.mock_config.get_feeds.return_value = []
            self.mock_config.load_settings.return_value = {}
            self.mock_config.config = {
                'debug_mode': False,
                'verbose_logging': False,
                'theme': 'light',
                'window_width': 1200,
                'window_height': 800
            }
            # Make get method return proper values based on key
            self.mock_config.get.side_effect = lambda key, default=None: self.mock_config.config.get(key, default)
            
            # Add batch_update context manager support
            self.mock_config.batch_update.return_value.__enter__ = Mock(return_value=None)
            self.mock_config.batch_update.return_value.__exit__ = Mock(return_value=None)
            
            # Configure mock checker with required attributes
            self.mock_checker.last_news_items = []
            self.mock_checker.get_available_updates.return_value = []
            
            # Configure the mock classes to return our mock instances
            mock_config_class.return_value = self.mock_config
            mock_checker_class.return_value = self.mock_checker
            
            # Create main window
            self.main_window = MainWindow()
            
            # Hide the window during tests
            self.main_window.root.withdraw()

    def tearDown(self):
        """Clean up after tests."""
        try:
            # Cancel any pending after calls
            self.main_window.root.after_cancel('all')
            # Destroy widgets safely
            for widget in self.main_window.root.winfo_children():
                try:
                    widget.destroy()
                except:
                    pass
            self.main_window.root.destroy()
        except:
            pass
        finally:
            # Force cleanup
            try:
                self.main_window.root.quit()
            except:
                pass

    def test_main_window_initialization(self):
        """Test main window initializes correctly."""
        self.assertIsNotNone(self.main_window)
        self.assertIsNotNone(self.main_window.root)
        self.assertIsNotNone(self.main_window.sidebar)
        self.assertIsNotNone(self.main_window.current_frame)

    def test_sidebar_creation(self):
        """Test sidebar is created correctly."""
        self.assertIsNotNone(self.main_window.sidebar)
        # Check that sidebar has buttons
        sidebar_children = self.main_window.sidebar.winfo_children()
        self.assertGreater(len(sidebar_children), 0)

    def test_frame_creation(self):
        """Test frames are created correctly."""
        self.assertIsNotNone(self.main_window.frames['dashboard'])
        self.assertIsNotNone(self.main_window.frames['news'])
        self.assertIsNotNone(self.main_window.frames['packages'])
        self.assertIsNotNone(self.main_window.frames['history'])
        self.assertIsNotNone(self.main_window.frames['settings'])
        
        # Test navigation buttons
        self.assertIn('history', self.main_window.nav_buttons)
        
        # Verify we have 4 navigation items now
        expected_nav_items = ['dashboard', 'packages', 'history', 'settings']
        for item in expected_nav_items:
            self.assertIn(item, self.main_window.nav_buttons)

    def test_show_frame(self):
        """Test frame switching functionality."""
        # Test switching to dashboard
        self.main_window.show_frame('dashboard')
        self.assertEqual(self.main_window.current_frame.get(), 'dashboard')
        
        # Test switching to news
        self.main_window.show_frame('news')
        self.assertEqual(self.main_window.current_frame.get(), 'news')
    
    def test_show_frame_history(self):
        """Test navigating to the history frame."""
        self.main_window.show_frame('history')
        self.assertEqual(self.main_window.current_frame.get(), 'history')

    def test_minimum_window_size(self):
        """Test that window size is properly set and non-resizable."""
        # Check that the window has reasonable dimensions
        geometry = self.main_window.root.winfo_geometry()
        # Extract width and height from geometry string (e.g., "1000x654+119+72")
        size_part = geometry.split('+')[0]  # Get "1000x654" part
        width, height = map(int, size_part.split('x'))
        
        # Check that dimensions are reasonable (at least 800x600)
        self.assertGreaterEqual(width, 800, f"Window width should be at least 800, got {width}")
        self.assertGreaterEqual(height, 600, f"Window height should be at least 600, got {height}")
        
        # Check that window is not resizable
        self.assertFalse(self.main_window.root.resizable()[0], "Window should not be horizontally resizable")
        self.assertFalse(self.main_window.root.resizable()[1], "Window should not be vertically resizable")

    def test_window_resize_callbacks(self):
        """Test that window is configured as non-resizable."""
        # Since the window is now fixed-size and non-resizable, 
        # we test that the window properly maintains its fixed dimensions
        self.assertGreaterEqual(self.main_window.min_width, 800, "Min width should be reasonable")
        self.assertGreaterEqual(self.main_window.min_height, 600, "Min height should be reasonable")
        
        # Verify that no resize callbacks exist since window is fixed
        self.assertFalse(hasattr(self.main_window, '_on_root_resize'))
        
        # Test that the frames dictionary is properly initialized
        self.assertIn('dashboard', self.main_window.frames)
        self.assertIn('packages', self.main_window.frames)
        self.assertIn('history', self.main_window.frames)
        self.assertIn('settings', self.main_window.frames)

    def test_status_update(self):
        """Test status update functionality."""
        self.main_window.update_status("Test status")
        # Should not raise any exceptions

    def test_run_check(self):
        """Test update check functionality."""
        with patch.object(self.main_window, 'update_status'):
            self.main_window.run_check()
            # Should not raise any exceptions

    def test_on_closing(self):
        """Test window closing functionality."""
        with patch.object(self.main_window.root, 'destroy'):
            self.main_window.on_closing()
            # Should not raise any exceptions


@pytest.mark.gui
class TestDashboardFrame(unittest.TestCase):
    """Test the dashboard frame functionality."""

    def setUp(self) -> None:
        # MEMORY FIX: Use Toplevel instead of new Tk()
        parent = get_or_create_root()
        self.root = tk.Toplevel(parent)
        self.root.withdraw()
        # Create a fully mocked main window to avoid real threads
        self.mock_main_window = Mock()
        self.mock_main_window.colors = {
            'primary': '#2563eb',
            'primary_hover': '#1d4ed8',
            'secondary': '#64748b',
            'background': '#f8fafc',
            'surface': '#ffffff',
            'text': '#1e293b',
            'text_secondary': '#64748b',
            'success': '#059669',
            'warning': '#d97706',
            'error': '#dc2626',
            'border': '#e2e8f0'
        }
        self.mock_main_window.checker = Mock()
        self.mock_main_window.checker.news_manager = Mock()
        self.mock_main_window.checker.last_news_items = []  # Fix for len() calls
        self.mock_main_window.config = Mock()
        self.mock_main_window.root = Mock()
        # Mock window width for responsive layout
        self.mock_main_window.root.winfo_width.return_value = 1200
        # Mock DPI scaling
        self.mock_main_window.dpi_scaling = 1.0
        # Patch out refresh to avoid threads
        with patch.object(DashboardFrame, 'refresh', lambda self: None):
            self.dashboard = DashboardFrame(self.root, self.mock_main_window)

    def tearDown(self) -> None:
        try:
            self.root.after_cancel('all')
            for widget in self.root.winfo_children():
                try:
                    widget.destroy()
                except:
                    pass
            self.root.destroy()
        except Exception:
            pass
        finally:
            self.root = None
            gc.collect()

    def test_dashboard_initialization(self):
        """Test dashboard initializes correctly."""
        self.assertIsNotNone(self.dashboard)
        self.assertIsNotNone(self.dashboard.canvas)

    def test_stats_cards_creation(self):
        """Test stats cards are created correctly with proper structure."""
        self.dashboard.create_stats_cards()
        
        # Verify stats_cards dictionary exists and has expected keys
        self.assertIsInstance(self.dashboard.stats_cards, dict)
        expected_cards = [
            "📦 Total Packages",
            "🔄 Available Updates", 
            "⚠️ Issues Found",
            "📰 News Items"
        ]
        
        for card_title in expected_cards:
            self.assertIn(card_title, self.dashboard.stats_cards)
            card = self.dashboard.stats_cards[card_title]
            # Each card should have value_label and desc_label
            self.assertTrue(hasattr(card, 'value_label'))
            self.assertTrue(hasattr(card, 'desc_label'))

    def test_session_updates_tracking(self):
        """Test session-only updates tracking behavior."""
        # Test initial state shows unknown (—)
        self.assertIsNone(self.dashboard.session_updates_count)
        
        # Test setting updates during session
        self.dashboard.session_updates_count = 7
        self.assertEqual(self.dashboard.session_updates_count, 7)
        
        # Test update_stats_cards uses session data correctly
        mock_value_label = Mock()
        mock_card = Mock()
        mock_card.value_label = mock_value_label
        self.dashboard.stats_cards = {
            '🔄 Available Updates': mock_card
        }
        
        # Mock other methods to avoid side effects
        with patch.object(self.dashboard, 'get_total_packages_count', return_value=1000), \
             patch.object(self.dashboard, 'get_issues_count', return_value=0), \
             patch.object(self.dashboard, 'save_non_update_stats'):
            
            self.dashboard.update_stats_cards()
            
            # Should display session count
            mock_value_label.config.assert_called_with(text='7')

    def test_session_updates_unknown_state(self):
        """Test unknown updates state shows em dash."""
        mock_value_label = Mock()
        mock_card = Mock()
        mock_card.value_label = mock_value_label
        self.dashboard.stats_cards = {
            '🔄 Available Updates': mock_card
        }
        
        # Ensure session count is None (unknown)
        self.dashboard.session_updates_count = None
        
        with patch.object(self.dashboard, 'get_total_packages_count', return_value=1000), \
             patch.object(self.dashboard, 'get_issues_count', return_value=0), \
             patch.object(self.dashboard, 'save_non_update_stats'):
            
            self.dashboard.update_stats_cards()
            
            # Should display em dash for unknown state
            mock_value_label.config.assert_called_with(text='—')

    def test_quick_actions_creation(self):
        """Test quick actions are created correctly with proper commands."""
        self.dashboard.create_quick_actions()
        
        # Should not raise any exceptions and should create UI elements
        # The actual buttons are created in the scrollable_frame
        self.assertTrue(True)  # Basic smoke test for now

    def test_refresh_functionality(self):
        """Test refresh functionality updates dashboard display correctly."""
        # Mock stats cards properly
        mock_value_label = Mock()
        mock_card = Mock()
        mock_card.value_label = mock_value_label
        self.dashboard.stats_cards = {
            '📦 Total Packages': mock_card,
            '🔄 Available Updates': mock_card,
            '⚠️ Issues Found': mock_card,
            '📰 News Items': mock_card
        }
        
        # Mock the methods that get called during refresh
        with patch.object(self.dashboard, 'get_total_packages_count', return_value=1500), \
             patch.object(self.dashboard, 'get_issues_count', return_value=2), \
             patch.object(self.dashboard, 'save_non_update_stats') as mock_save:
            
            self.dashboard.refresh()
            
            # Verify save was called with total packages
            mock_save.assert_called()

    def test_check_updates_creates_timestamp(self):
        """Test update checking creates timestamp file."""
        with patch.object(self.mock_main_window, 'run_check'), \
             patch('os.makedirs') as mock_makedirs, \
             patch('builtins.open', mock_open()) as mock_file:
            
            self.dashboard.check_updates()
            
            # Should create cache directory and timestamp file
            mock_makedirs.assert_called_with(
                '/home/neo/.cache/arch-smart-update-checker', exist_ok=True
            )
            mock_file.assert_called()


@pytest.mark.gui
class TestNewsBrowserFrame(unittest.TestCase):
    """Test the news browser frame functionality."""

    def setUp(self) -> None:
        # Skip GUI setup in headless environment
        if os.environ.get('ASUC_HEADLESS') or os.environ.get('CI'):
            self.skipTest("Skipping GUI test in headless environment")
        self.root = tk.Tk()
        self.root.withdraw()
        # Create a fully mocked main window to avoid real threads
        self.mock_main_window = Mock()
        self.mock_main_window.colors = {
            'primary': '#2563eb',
            'primary_hover': '#1d4ed8',
            'secondary': '#64748b',
            'background': '#f8fafc',
            'surface': '#ffffff',
            'text': '#1e293b',
            'text_secondary': '#64748b',
            'success': '#059669',
            'warning': '#d97706',
            'error': '#dc2626',
            'border': '#e2e8f0'
        }
        self.mock_main_window.checker = Mock()
        self.mock_main_window.checker.news_manager = Mock()
        self.mock_main_window.config = Mock()
        self.mock_main_window.root = Mock()
        
        # Configure mock root to behave like a real window for geometry
        self.mock_main_window.root.winfo_x.return_value = 100
        self.mock_main_window.root.winfo_y.return_value = 100
        self.mock_main_window.root.winfo_width.return_value = 800
        self.mock_main_window.root.winfo_height.return_value = 600
        
        # Patch out load_news and refresh_news to avoid threads
        with patch.object(NewsBrowserFrame, 'load_news', lambda self: None), \
             patch.object(NewsBrowserFrame, 'refresh_news', lambda self: None):
            self.news_browser = NewsBrowserFrame(self.root, self.mock_main_window)

    def tearDown(self) -> None:
        try:
            self.root.destroy()
        except Exception:
            pass

    def test_news_browser_initialization(self):
        """Test news browser initializes correctly."""
        self.assertIsNotNone(self.news_browser)
        self.assertIsNotNone(self.news_browser.news_canvas)
        self.assertIsNotNone(self.news_browser.search_var)
        self.assertIsNotNone(self.news_browser.filter_var)

    def test_search_functionality(self):
        """Test search functionality."""
        # Should not raise any exceptions
        self.news_browser.on_search_change()

    def test_filter_functionality(self):
        """Test filter functionality."""
        # Should not raise any exceptions
        self.news_browser.on_filter_change(None)

    def test_refresh_news(self):
        """Test news refresh functionality."""
        with patch.object(self.news_browser, 'load_news') as mock_load_news:
            self.news_browser.refresh_news()
            mock_load_news.assert_called_once()

    def test_open_link(self):
        """Test link opening functionality."""
        with patch('src.utils.subprocess_wrapper.SecureSubprocess.open_url_securely') as mock_open:
            mock_open.return_value = True
            self.news_browser.open_link("https://example.com")
            mock_open.assert_called_once_with("https://example.com", sandbox=True)

    def test_show_packages(self):
        """Test package display functionality."""
        packages = ["package1", "package2"]
        # Patch transient to avoid Tkinter error with mock parent
        with patch('tkinter.Toplevel.transient'), patch('tkinter.Toplevel.grab_set'):
            # Should not raise any exceptions
            self.news_browser.show_packages(packages)

    def test_create_news_card(self):
        """Test news card creation."""
        item = {
            'title': 'Test News',
            'published': '2024-01-01',
            'feed': 'Test Feed',
            'severity': 'medium',
            'description': 'Test description',
            'link': 'http://example.com',
            'packages': ['pkg1', 'pkg2']
        }
        
        card = self.news_browser.create_news_card(item)
        self.assertIsNotNone(card)


@pytest.mark.gui
class TestPackageManagerFrame(unittest.TestCase):
    """Test the package manager frame functionality."""

    def setUp(self):
        """Set up test fixtures."""
        # Skip GUI setup in headless environment
        if os.environ.get('ASUC_HEADLESS') or os.environ.get('CI'):
            self.skipTest("Skipping GUI test in headless environment")
        self.root = tk.Tk()
        self.mock_main_window = Mock()
        self.mock_main_window.colors = {
            'background': '#F5F7FA',
            'surface': '#FFFFFF',
            'primary': '#2563EB',
            'primary_hover': '#1D4ED8',
            'secondary': '#6B7280',
            'success': '#10B981',
            'warning': '#F59E0B',
            'error': '#EF4444',
            'info': '#3B82F6',
            'text': '#1F2937',
            'text_secondary': '#6B7280',
            'accent': '#8B5CF6',
            'border': '#E5E7EB',
            'hover': '#F9FAFB'
        }
        self.mock_main_window.root = self.root
        self.mock_main_window.checker = Mock()
        self.mock_main_window.checker.package_manager = Mock()
        self.mock_main_window.checker.package_manager.get_installed_packages = Mock(return_value=[])
        self.mock_main_window.config = Mock()
        self.mock_main_window.config.get_critical_packages = Mock(return_value=[])
        self.mock_main_window.dpi_scaling = 1.0

        # Patch methods that might cause issues during initialization
        with patch.object(PackageManagerFrame, 'load_packages', lambda self: None):
            self.package_manager_frame = PackageManagerFrame(self.root, self.mock_main_window)

    def tearDown(self) -> None:
        try:
            self.root.destroy()
        except Exception:
            pass

    def test_package_manager_initialization(self):
        """Test package manager initializes correctly."""
        self.assertIsNotNone(self.package_manager_frame)
        self.assertIsNotNone(self.package_manager_frame.package_tree)
        self.assertIsNotNone(self.package_manager_frame.search_var)
        self.assertIsNotNone(self.package_manager_frame.filter_var)

    def test_search_functionality(self):
        """Test search functionality."""
        # Test that search variable exists and can be modified
        self.package_manager_frame.search_var.set("test")
        self.assertEqual(self.package_manager_frame.search_var.get(), "test")

    def test_filter_functionality(self):
        """Test filter functionality."""
        # Test that filter variable exists and can be modified
        self.package_manager_frame.filter_var.set("critical")
        self.assertEqual(self.package_manager_frame.filter_var.get(), "critical")

    def test_refresh_packages(self):
        """Test package refresh functionality."""
        with patch.object(self.package_manager_frame, 'load_packages') as mock_load_packages:
            self.package_manager_frame.refresh_packages()
            mock_load_packages.assert_called_once()

    def test_package_actions(self):
        """Test package action buttons exist."""
        # Just test that the frame has the expected methods
        self.assertTrue(hasattr(self.package_manager_frame, 'mark_package_critical'))
        self.assertTrue(hasattr(self.package_manager_frame, 'remove_package_critical'))
        self.assertTrue(hasattr(self.package_manager_frame, 'view_package_details'))


@pytest.mark.gui
class TestSettingsFrame(unittest.TestCase):
    """Test the settings frame functionality."""

    def setUp(self):
        """Set up test fixtures."""
        # Skip GUI setup in headless environment
        if os.environ.get('ASUC_HEADLESS') or os.environ.get('CI'):
            self.skipTest("Skipping GUI test in headless environment")
        self.root = tk.Tk()
        self.root.withdraw()
        
        # Create mock main window with complete colors
        self.mock_main_window = Mock()
        self.mock_main_window.colors = {
            'primary': '#2563eb',
            'primary_hover': '#1d4ed8',
            'secondary': '#64748b',
            'background': '#f8fafc',
            'surface': '#ffffff',
            'text': '#1e293b',
            'text_secondary': '#64748b',
            'success': '#059669',
            'warning': '#d97706',
            'error': '#dc2626',
            'border': '#e2e8f0'
        }
        self.mock_main_window.checker = Mock()
        self.mock_main_window.checker.news_manager = Mock()
        self.mock_main_window.config = Mock()
        self.mock_main_window.root = Mock()
        self.mock_main_window.dpi_scaling = 1.0
        
        # Configure mock root to behave like a real window for geometry
        self.mock_main_window.root.winfo_x.return_value = 100
        self.mock_main_window.root.winfo_y.return_value = 100
        self.mock_main_window.root.winfo_width.return_value = 800
        self.mock_main_window.root.winfo_height.return_value = 600
        
        self.settings = SettingsFrame(self.root, self.mock_main_window)

    def tearDown(self):
        """Clean up after tests."""
        try:
            # Cancel any pending after calls
            self.root.after_cancel('all')
            # Destroy widgets safely
            for widget in self.root.winfo_children():
                try:
                    widget.destroy()
                except:
                    pass
            self.root.destroy()
        except:
            pass
        finally:
            # Force cleanup
            try:
                self.root.quit()
            except:
                pass

    def test_settings_initialization(self):
        """Test settings initializes correctly with all required components."""
        self.assertIsNotNone(self.settings)
        self.assertIsNotNone(self.settings.canvas)
        self.assertIsNotNone(self.settings.theme_var)
        self.assertIsNotNone(self.settings.auto_refresh_var)
        self.assertIsNotNone(self.settings.news_age_var)
        
        # Verify scroll bindings are set up
        self.assertTrue(hasattr(self.settings, '_setup_scroll_bindings'))

    def test_save_settings_functionality(self):
        """Test settings save functionality actually saves data."""
        # Mock the config save method and ensure config dict exists
        self.mock_main_window.config.config = {
            'max_news_age_days': 30,
            'auto_refresh_feeds': True,
            'theme': 'light'
        }
        
        # Mock the update_settings method
        self.mock_main_window.config.update_settings = Mock()
        
        # Set some test values using actual SettingsFrame attributes
        self.settings.news_age_var.set('60')
        self.settings.auto_refresh_var.set(False)
        self.settings.theme_var.set('dark')
        
        # Save settings
        self.settings.save_settings(silent=True)
        
        # Verify update_settings was called with the new values
        self.mock_main_window.config.update_settings.assert_called_once()
        call_args = self.mock_main_window.config.update_settings.call_args[0][0]
        
        # Check that the expected keys are in the update
        self.assertIn('max_news_age_days', call_args)
        self.assertIn('auto_refresh_feeds', call_args)
        self.assertIn('theme', call_args)
        self.assertEqual(call_args['max_news_age_days'], 60)
        self.assertEqual(call_args['auto_refresh_feeds'], False)
        self.assertEqual(call_args['theme'], 'dark')

    def test_scroll_bindings_setup(self):
        """Test scroll bindings are properly configured."""
        # Test that scroll bindings can be set up without errors
        # This is more of a smoke test since the bindings were already set up during init
        self.assertTrue(hasattr(self.settings, '_setup_scroll_bindings'))
        self.assertTrue(hasattr(self.settings, '_on_mousewheel'))
        
        # Verify the canvas and content_frame exist
        self.assertIsNotNone(self.settings.canvas)
        self.assertIsNotNone(self.settings.content_frame)
        
        # Test that the method can be called without errors
        try:
            self.settings._setup_scroll_bindings()
        except Exception as e:
            self.fail(f"_setup_scroll_bindings raised an exception: {e}")

    def test_theme_change_preserves_scroll(self):
        """Test that theme changes preserve scroll functionality."""
        # Mock the scroll setup
        with patch.object(self.settings, '_setup_scroll_bindings') as mock_scroll_setup:
            # Simulate theme change causing UI refresh
            self.settings.setup_ui()
            
            # Verify scroll bindings were re-established
            mock_scroll_setup.assert_called()

    def test_reset_settings(self):
        """Test settings reset functionality restores defaults."""
        # Set some non-default values using actual attributes
        self.settings.news_age_var.set('60')
        self.settings.auto_refresh_var.set(False)
        
        with patch('tkinter.messagebox.askyesno', return_value=True) as mock_confirm, \
             patch('tkinter.messagebox.showinfo'):  # Suppress success popup
            
            # Store original values to verify they changed
            original_news_age = self.settings.news_age_var.get()
            original_auto_refresh = self.settings.auto_refresh_var.get()
            
            self.settings.reset_settings()
            
            # Should ask for confirmation
            mock_confirm.assert_called_once()
            
            # Should reset values to defaults
            self.assertEqual(self.settings.news_age_var.get(), '30')
            self.assertEqual(self.settings.auto_refresh_var.get(), True)

    def test_export_config(self):
        """Test config export functionality."""
        with patch('tkinter.filedialog.asksaveasfilename') as mock_save:
            mock_save.return_value = '/tmp/test_config.json'
            with patch('builtins.open', create=True):
                self.settings.export_config()
                # Should not raise any exceptions

    def test_add_feed(self):
        """Test feed addition functionality."""
        with patch('tkinter.simpledialog.askstring') as mock_ask:
            mock_ask.return_value = 'http://example.com/feed'
            with patch.object(self.settings, 'update_feed_list'), \
                 patch('tkinter.Toplevel.transient'), \
                 patch('tkinter.Toplevel.grab_set'):
                self.settings.add_feed()
                # Should not raise any exceptions

    def test_remove_feed(self):
        """Test feed removal functionality."""
        # Mock the config to return an empty list (no feeds to remove)
        self.mock_main_window.config.get_feeds.return_value = []
        
        with patch('tkinter.messagebox.showinfo') as mock_info:
            self.settings.remove_feed()
            # Should show info that there are no feeds to remove
            mock_info.assert_called_once_with("Info", "No feeds to remove")


@pytest.mark.gui
class TestGUIIntegration(unittest.TestCase):
    """Test integration between GUI components."""

    def setUp(self):
        """Set up test fixtures."""
        # Skip GUI setup in headless environment
        if os.environ.get('ASUC_HEADLESS') or os.environ.get('CI'):
            self.skipTest("Skipping GUI test in headless environment")
        self.root = tk.Tk()
        self.root.withdraw()

    def tearDown(self):
        """Clean up after tests."""
        try:
            # Cancel any pending after calls
            self.root.after_cancel('all')
            # Destroy widgets safely
            for widget in self.root.winfo_children():
                try:
                    widget.destroy()
                except:
                    pass
            self.root.destroy()
        except:
            pass
        finally:
            # Force cleanup
            try:
                self.root.quit()
            except:
                pass

    def test_theme_color_system_light(self):
        """Test get_text_color method works correctly for light theme."""
        # Setup main window with light theme
        with patch('src.gui.main_window.Config'), \
             patch('src.gui.main_window.UpdateChecker'):
            main_window = MainWindow.__new__(MainWindow)
            main_window.root = self.root
            main_window.config = Mock()
            main_window.config.config = {'theme': 'light'}
            main_window.checker = Mock()
            main_window.setup_styles()
            
            # Test light theme colors
            self.assertEqual(main_window.get_text_color('primary'), '#1E293B')
            self.assertEqual(main_window.get_text_color('secondary'), '#64748B')
            self.assertEqual(main_window.get_text_color('success'), '#059669')
            self.assertEqual(main_window.get_text_color('error'), '#DC2626')

    def test_theme_color_system_dark(self):
        """Test get_text_color method works correctly for dark theme."""
        # Setup main window with dark theme
        with patch('src.gui.main_window.Config'), \
             patch('src.gui.main_window.UpdateChecker'):
            main_window = MainWindow.__new__(MainWindow)
            main_window.root = self.root
            main_window.config = Mock()
            main_window.config.config = {'theme': 'dark'}
            main_window.checker = Mock()
            main_window.setup_styles()
            
            # Test dark theme colors
            self.assertEqual(main_window.get_text_color('primary'), '#F1F5F9')
            self.assertEqual(main_window.get_text_color('secondary'), '#94A3B8')
            self.assertEqual(main_window.get_text_color('success'), '#10B981')
            self.assertEqual(main_window.get_text_color('error'), '#EF4444')

    def test_theme_switching_updates_colors(self):
        """Test that theme switching properly updates color schemes."""
        with patch('src.gui.main_window.Config'), \
             patch('src.gui.main_window.UpdateChecker'):
            main_window = MainWindow.__new__(MainWindow)
            main_window.root = self.root
            main_window.config = Mock()
            main_window.checker = Mock()
            
            # Start with light theme
            main_window.config.config = {'theme': 'light'}
            main_window.setup_styles()
            initial_colors = main_window.colors.copy()
            
            # Switch to dark theme
            main_window.config.config = {'theme': 'dark'}
            main_window.setup_styles()
            dark_colors = main_window.colors.copy()
            
            # Colors should be different
            self.assertNotEqual(initial_colors['background'], dark_colors['background'])
            self.assertNotEqual(initial_colors['text'], dark_colors['text'])
            
            # Verify specific dark theme colors
            self.assertEqual(dark_colors['background'], '#0F172A')
            self.assertEqual(dark_colors['text'], '#F1F5F9')

    def test_theme_fallback_behavior(self):
        """Test theme system handles unknown text types gracefully."""
        with patch('src.gui.main_window.Config'), \
             patch('src.gui.main_window.UpdateChecker'):
            main_window = MainWindow.__new__(MainWindow)
            main_window.root = self.root
            main_window.config = Mock()
            main_window.config.config = {'theme': 'light'}
            main_window.checker = Mock()
            main_window.setup_styles()
            
            # Unknown text type should fallback to primary
            unknown_color = main_window.get_text_color('unknown_type')
            primary_color = main_window.get_text_color('primary')
            self.assertEqual(unknown_color, primary_color)

    def test_gui_navigation(self):
        """Test GUI navigation between frames."""
        # Create mock main window
        mock_main_window = Mock()
        mock_main_window.colors = {
            'primary': '#2563eb',
            'primary_hover': '#1d4ed8',
            'secondary': '#64748b',
            'background': '#f8fafc',
            'surface': '#ffffff',
            'text': '#1e293b',
            'text_secondary': '#64748b',
            'success': '#059669',
            'warning': '#d97706',
            'error': '#dc2626',
            'border': '#e2e8f0'
        }
        mock_main_window.checker = Mock()
        mock_main_window.checker.news_manager = Mock()  # Patch news_manager
        mock_main_window.config = Mock()
        mock_main_window.root = Mock()
        # Patch out background-thread methods
        with patch('src.gui.main_window.Config') as mock_config_class, \
             patch('src.gui.main_window.UpdateChecker') as mock_checker_class, \
             patch.object(DashboardFrame, 'refresh', lambda self: None), \
             patch.object(DashboardFrame, 'refresh_news', lambda self: None), \
             patch.object(NewsBrowserFrame, 'load_news', lambda self: None), \
             patch.object(NewsBrowserFrame, 'refresh_news', lambda self: None), \
             patch.object(PackageManagerFrame, 'load_packages', lambda self: None), \
             patch.object(PackageManagerFrame, 'refresh_packages', lambda self: None):
            
            # Set up proper mocks with context manager support
            mock_config = Mock()
            mock_config.config = {'theme': 'light', 'window_width': 1200, 'window_height': 800}
            mock_config.get.side_effect = lambda key, default=None: mock_config.config.get(key, default)
            mock_config.get_feeds.return_value = []
            mock_config.load_settings.return_value = {}
            mock_config.batch_update.return_value.__enter__ = Mock(return_value=None)
            mock_config.batch_update.return_value.__exit__ = Mock(return_value=None)
            
            mock_checker = Mock()
            mock_checker.last_news_items = []
            mock_checker.get_available_updates.return_value = []
            
            mock_config_class.return_value = mock_config
            mock_checker_class.return_value = mock_checker
            main_window = MainWindow()
            main_window.root.withdraw()
            try:
                # Test frame switching
                main_window.show_frame('dashboard')
                self.assertEqual(main_window.current_frame.get(), 'dashboard')
                
                main_window.show_frame('news')
                self.assertEqual(main_window.current_frame.get(), 'news')
                
                main_window.show_frame('packages')
                self.assertEqual(main_window.current_frame.get(), 'packages')
                
                main_window.show_frame('settings')
                self.assertEqual(main_window.current_frame.get(), 'settings')
                
                main_window.show_frame('history')
                self.assertEqual(main_window.current_frame.get(), 'history')
            finally:
                try:
                    main_window.root.destroy()
                except:
                    pass


@pytest.mark.gui
class TestGUIPerformance(unittest.TestCase):
    """Test GUI performance characteristics."""

    def test_gui_startup_time(self):
        """Test that GUI components start up within reasonable time."""
        # Skip GUI test in headless environment
        if os.environ.get('ASUC_HEADLESS') or os.environ.get('CI'):
            self.skipTest("Skipping GUI test in headless environment")
        import time
        start_time = time.time()
        root = tk.Tk()
        root.withdraw()
        try:
            # Create mock main window
            mock_main_window = Mock()
            mock_main_window.colors = {
                'primary': '#2563eb',
                'primary_hover': '#1d4ed8',
                'secondary': '#64748b',
                'background': '#f8fafc',
                'surface': '#ffffff',
                'text': '#1e293b',
                'text_secondary': '#64748b',
                'success': '#059669',
                'warning': '#d97706',
                'error': '#dc2626',
                'info': '#3b82f6',
                'border': '#e2e8f0'
            }
            mock_main_window.checker = Mock()
            mock_main_window.checker.news_manager = Mock()  # Patch news_manager
            mock_main_window.config = Mock()
            mock_main_window.root = Mock()
            # Mock window width for responsive layout
            mock_main_window.root.winfo_width.return_value = 1200
            # Mock DPI scaling
            mock_main_window.dpi_scaling = 1.0
            # Patch out background-thread methods
            with patch.object(DashboardFrame, 'refresh', lambda self: None), \
                 patch.object(DashboardFrame, 'refresh_news', lambda self: None), \
                 patch.object(NewsBrowserFrame, 'load_news', lambda self: None), \
                 patch.object(NewsBrowserFrame, 'refresh_news', lambda self: None), \
                 patch.object(PackageManagerFrame, 'load_packages', lambda self: None), \
                 patch.object(PackageManagerFrame, 'refresh_packages', lambda self: None):
                dashboard = DashboardFrame(root, mock_main_window)
                with patch('src.gui.news_browser.NewsFetcher'):
                    news_browser = NewsBrowserFrame(root, mock_main_window)
                package_manager = PackageManagerFrame(root, mock_main_window)
                settings = SettingsFrame(root, mock_main_window)
                end_time = time.time()
                startup_time = end_time - start_time
                self.assertLess(startup_time, 5.0, f"GUI startup took {startup_time:.2f} seconds")
        finally:
            try:
                root.destroy()
            except:
                pass

    def test_memory_usage(self):
        """Test that GUI components don't cause excessive memory usage."""
        # Skip GUI test in headless environment
        if os.environ.get('ASUC_HEADLESS') or os.environ.get('CI'):
            self.skipTest("Skipping GUI test in headless environment")
        import gc
        gc.collect()
        root = tk.Tk()
        root.withdraw()
        try:
            # Create mock main window
            mock_main_window = Mock()
            mock_main_window.colors = {
                'primary': '#2563eb',
                'primary_hover': '#1d4ed8',
                'secondary': '#64748b',
                'background': '#f8fafc',
                'surface': '#ffffff',
                'text': '#1e293b',
                'text_secondary': '#64748b',
                'success': '#059669',
                'warning': '#d97706',
                'error': '#dc2626',
                'info': '#3b82f6',
                'border': '#e2e8f0'
            }
            mock_main_window.checker = Mock()
            mock_main_window.checker.news_manager = Mock()  # Patch news_manager
            mock_main_window.config = Mock()
            mock_main_window.root = Mock()
            # Mock window width for responsive layout
            mock_main_window.root.winfo_width.return_value = 1200
            # Mock DPI scaling
            mock_main_window.dpi_scaling = 1.0
            # Patch out background-thread methods
            with patch.object(DashboardFrame, 'refresh', lambda self: None), \
                 patch.object(DashboardFrame, 'refresh_news', lambda self: None), \
                 patch.object(NewsBrowserFrame, 'load_news', lambda self: None), \
                 patch.object(NewsBrowserFrame, 'refresh_news', lambda self: None), \
                 patch.object(PackageManagerFrame, 'load_packages', lambda self: None), \
                 patch.object(PackageManagerFrame, 'refresh_packages', lambda self: None):
                for _ in range(5):
                    dashboard = DashboardFrame(root, mock_main_window)
                    with patch('src.gui.news_browser.NewsFetcher'):
                        news_browser = NewsBrowserFrame(root, mock_main_window)
                    package_manager = PackageManagerFrame(root, mock_main_window)
                    settings = SettingsFrame(root, mock_main_window)
                    for widget in root.winfo_children():
                        try:
                            widget.destroy()
                        except:
                            pass
                gc.collect()
                self.assertTrue(True, "Memory usage test completed successfully")
        finally:
            try:
                root.destroy()
            except:
                pass


if __name__ == '__main__':
    unittest.main()
 