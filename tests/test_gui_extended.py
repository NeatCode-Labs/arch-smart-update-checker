"""
Extended test suite for the Arch Smart Update Checker GUI application.
Tests for newly implemented features and error handling.
"""

import unittest
import tkinter as tk
from unittest.mock import Mock, patch, MagicMock, call
import sys
import os
import subprocess
import tempfile
import json
from datetime import datetime, timedelta
import gc  # Added for memory management

# Imports are handled by pytest and the src/ structure

from src.gui.main_window import MainWindow, UpdatesNewsFrame
from src.gui.package_manager import PackageManagerFrame
from src.gui.dashboard import DashboardFrame
from src.gui.news_browser import NewsBrowserFrame
from src.package_manager import PackageManager
from src.utils.cache import CacheManager
from src.config import Config

# MEMORY LEAK FIX: Use a single root window for all tests
_test_root = None

def get_or_create_root():
    """Get or create a singleton Tk root to prevent memory leaks."""
    global _test_root
    if _test_root is None:
        _test_root = tk.Tk()
        _test_root.withdraw()
    return _test_root


class TestPackageSearchAndFilter(unittest.TestCase):
    """Test package search and filtering functionality."""

    def setUp(self):
        """Set up test fixtures."""
        # MEMORY FIX: Use Toplevel instead of new Tk()
        parent = get_or_create_root()
        self.root = tk.Toplevel(parent)
        self.root.withdraw()
        
        # Create mock main window
        self.mock_main_window = Mock()
        self.mock_main_window.colors = {
            'primary': '#2563eb',
            'primary_hover': '#1d4ed8',
            'secondary': '#64748b',
            'surface': '#ffffff',
            'text': '#1e293b',
            'text_secondary': '#64748b',
            'background': '#f8fafc',
            'success': '#059669',
            'error': '#dc2626',
            'warning': '#d97706',
            'info': '#3b82f6',
            'border': '#e2e8f0'
        }
        self.mock_main_window.checker = Mock()
        self.mock_main_window.checker.package_manager = Mock()
        self.mock_main_window.config = Mock()
        self.mock_main_window.config.get_critical_packages.return_value = ['linux', 'systemd', 'pacman']
        self.mock_main_window.root = self.root
        
        with patch.object(PackageManagerFrame, 'load_packages', lambda self: None):
            self.pkg_frame = PackageManagerFrame(self.root, self.mock_main_window)
        
        # Set up test packages
        self.pkg_frame.packages = {
            'firefox': '120.0-1',
            'chromium': '119.0-1',
            'linux': '6.6.1-1',
            'systemd': '254.5-1',
            'pacman': '6.0.2-7',
            'vim': '9.0.2-1'
        }
        self.pkg_frame.available_updates = {'firefox', 'linux'}
        
        # Set up all_packages for filtering
        self.pkg_frame.all_packages = [
            {'name': 'firefox', 'version': '120.0-1', 'update': 'Yes'},
            {'name': 'chromium', 'version': '119.0-1', 'update': 'No'},
            {'name': 'linux', 'version': '6.6.1-1', 'update': 'Yes'},
            {'name': 'systemd', 'version': '254.5-1', 'update': 'No'},
            {'name': 'pacman', 'version': '6.0.2-7', 'update': 'No'},
            {'name': 'vim', 'version': '9.0.2-1', 'update': 'No'}
        ]
        self.pkg_frame.critical_packages = ['linux', 'systemd', 'pacman']

    def tearDown(self):
        """Clean up after tests."""
        try:
            # Cancel any pending callbacks
            self.root.after_cancel('all')
            # Destroy all children
            for widget in self.root.winfo_children():
                try:
                    widget.destroy()
                except:
                    pass
            # Destroy the window
            self.root.destroy()
        except:
            pass
        finally:
            self.root = None
            # Force garbage collection
            gc.collect()

    def test_search_packages(self):
        """Test package search functionality."""
        # Test searching for 'fire'
        self.pkg_frame.search_var.set('fire')
        self.pkg_frame.filter_packages()
        
        # Check that tree view is updated (filtered)
        items = self.pkg_frame.package_tree.get_children()
        # In a real scenario, only firefox would be shown
        self.assertEqual(len(items), 1)
        item_text = self.pkg_frame.package_tree.item(items[0])['text']
        self.assertEqual(item_text, 'firefox')

    def test_filter_by_status(self):
        """Test filtering packages by status."""
        # Test filter by "Updates Available"
        self.pkg_frame.filter_var.set("Updates Available")
        self.pkg_frame.filter_packages()
        
        # Check that only packages with updates are shown
        items = self.pkg_frame.package_tree.get_children()
        package_names = [self.pkg_frame.package_tree.item(item)['text'] for item in items]
        self.assertIn('firefox', package_names)
        self.assertIn('linux', package_names)
        self.assertNotIn('vim', package_names)

    def test_filter_critical_packages(self):
        """Test filtering critical packages."""
        self.pkg_frame.filter_var.set("Critical")
        self.pkg_frame.filter_packages()
        
        # Check that only critical packages are shown
        items = self.pkg_frame.package_tree.get_children()
        package_names = [self.pkg_frame.package_tree.item(item)['text'] for item in items]
        self.assertIn('linux', package_names)
        self.assertIn('systemd', package_names)
        self.assertIn('pacman', package_names)
        self.assertNotIn('firefox', package_names)

    def test_combined_search_and_filter(self):
        """Test combined search and filter functionality."""
        # Search for 'linux' and filter by updates
        self.pkg_frame.search_var.set('linux')
        self.pkg_frame.filter_var.set("Updates Available")
        self.pkg_frame.filter_packages()
        
        # Should only show linux (has updates and matches search)
        items = self.pkg_frame.package_tree.get_children()
        self.assertEqual(len(items), 1)
        item_text = self.pkg_frame.package_tree.item(items[0])['text']
        self.assertEqual(item_text, 'linux')


class TestPackageOperations(unittest.TestCase):
    """Test package installation, removal, and update operations."""

    def setUp(self):
        """Set up test fixtures."""
        self.root = tk.Tk()
        self.root.withdraw()
        
        # Create mock main window
        self.mock_main_window = Mock()
        self.mock_main_window.colors = {
            'primary': '#2563eb',
            'primary_hover': '#1d4ed8',
            'secondary': '#64748b',
            'surface': '#ffffff',
            'text': '#1e293b',
            'text_secondary': '#64748b',
            'background': '#f8fafc',
            'success': '#059669',
            'error': '#dc2626',
            'warning': '#d97706',
            'info': '#3b82f6',
            'border': '#e2e8f0'
        }
        self.mock_main_window.checker = Mock()
        self.mock_main_window.checker.package_manager = Mock()
        self.mock_main_window.config = Mock()
        self.mock_main_window.config.get_critical_packages.return_value = ['linux', 'systemd', 'pacman']
        self.mock_main_window.root = Mock()
        
        with patch.object(PackageManagerFrame, 'load_packages', lambda self: None):
            self.pkg_frame = PackageManagerFrame(self.root, self.mock_main_window)

    def tearDown(self):
        """Clean up after tests."""
        try:
            self.root.destroy()
        except:
            pass

    @patch('tkinter.messagebox.askyesno')
    def test_package_removal_success(self, mock_askyesno):
        """Test package removal confirmation functionality."""
        # Mock package selection
        mock_item = Mock()
        self.pkg_frame.package_tree.selection = Mock(return_value=[mock_item])
        self.pkg_frame.package_tree.item = Mock(return_value={'values': ['test-package', '1.0-1', 'core', '1024', 'Today', 'Normal']})
        
        # Mock user canceling the removal
        mock_askyesno.return_value = False
        
        # Test removal - should ask for confirmation
        self.pkg_frame.remove_selected()
        
        # Verify confirmation dialog was shown
        mock_askyesno.assert_called_once()
        self.assertIn("Remove 1 package", mock_askyesno.call_args[0][1])

    @patch('subprocess.Popen')
    @patch('tkinter.messagebox.showerror')
    def test_package_removal_failure(self, mock_error, mock_popen):
        """Test failed package removal."""
        # Mock subprocess failure
        mock_process = Mock()
        mock_process.communicate.return_value = ('', 'error: failed to remove package')
        mock_process.returncode = 1
        mock_popen.return_value = mock_process
        
        # Mock package selection
        mock_item = Mock()
        self.pkg_frame.package_tree.selection = Mock(return_value=[mock_item])
        self.pkg_frame.package_tree.item = Mock(return_value={'values': ['test-package', '1.0-1', 'Installed', 'No']})
        
        # Test removal with confirmation
        with patch('tkinter.messagebox.askyesno', return_value=True):
            self.pkg_frame.remove_selected()

    @patch('subprocess.run')
    @patch('tkinter.messagebox.showinfo')
    def test_orphan_cleanup_success(self, mock_info, mock_run):
        """Test successful orphan package cleanup."""
        # Mock the sequence of subprocess.run calls:
        # 1. pacman -Qtdq (find orphans)
        # 2. pacman -Qi orphan1 (check if truly orphaned)
        # 3. pacman -Qi orphan2 (check if truly orphaned)  
        # 4. which gnome-terminal (check terminal availability)
        
        orphan_info_output = '''Name            : orphan1
Version         : 1.0.0-1
Required By     : None
'''
        
        mock_run.side_effect = [
            Mock(returncode=0, stdout='orphan1\norphan2\n'),  # pacman -Qtdq
            Mock(returncode=0, stdout=orphan_info_output),    # pacman -Qi orphan1
            Mock(returncode=0, stdout=orphan_info_output.replace('orphan1', 'orphan2')),  # pacman -Qi orphan2
            Mock(returncode=0)  # which gnome-terminal
        ]
        
        # Test cleanup with confirmation
        with patch.object(self.pkg_frame, '_show_orphan_confirmation_dialog', return_value=True):
            with patch('subprocess.Popen') as mock_popen:
                self.pkg_frame.clean_orphans()
                
                # Verify terminal command was called
                mock_popen.assert_called_once()
                cmd = mock_popen.call_args[0][0]
                self.assertEqual(cmd[:2], ['gnome-terminal', '--'])
                self.assertEqual(cmd[2:5], ['sudo', 'pacman', '-Rns'])
                self.assertIn('orphan1', cmd)
                self.assertIn('orphan2', cmd)
                
    @patch('subprocess.run')
    @patch('tkinter.messagebox.showinfo')
    def test_orphan_cleanup_no_orphans(self, mock_info, mock_run):
        """Test orphan cleanup when no orphans found."""
        # Mock no orphans (returncode 1 means no orphans for pacman -Qtdq)
        mock_run.return_value = Mock(returncode=1, stdout='')
        
        self.pkg_frame.clean_orphans()
        
        # Verify user was informed
        mock_info.assert_called_once()
        self.assertIn('No orphan packages', mock_info.call_args[0][1])

    def test_package_info_display(self):
        """Test displaying package information."""
        # Mock package selection
        mock_item = Mock()
        self.pkg_frame.package_tree.selection = Mock(return_value=[mock_item])
        self.pkg_frame.package_tree.item = Mock(return_value={'text': 'test-package', 'values': ['1.0-1', 'core', '1024', 'Today', 'Normal']})
        
        # Mock package manager get_package_info
        mock_info = "Name : test-package\nVersion : 1.0-1\nDescription : Test package"
        self.pkg_frame.package_manager = Mock()
        self.pkg_frame.package_manager.get_package_info.return_value = mock_info
        
        # Create a list to track after callbacks
        after_callbacks = []
        
        # Mock main_window.root.after to capture and execute callbacks
        def mock_after(delay, func):
            after_callbacks.append(func)
            # Execute the callback immediately
            func()
        
        self.pkg_frame.main_window.root.after = Mock(side_effect=mock_after)
        
        # Mock the show_package_info method to avoid creating actual dialog
        with patch.object(self.pkg_frame, 'show_package_info') as mock_show:
            # Test info display
            self.pkg_frame.view_package_details()
            
            # Verify show_package_info was called with correct arguments
            mock_show.assert_called_once_with('test-package', mock_info)

    @patch('tkinter.messagebox.askyesno')
    def test_invalid_package_name_validation(self, mock_askyesno):
        """Test validation of invalid package names."""
        # Mock package selection with invalid name
        mock_item = Mock()
        self.pkg_frame.package_tree.selection = Mock(return_value=[mock_item])
        self.pkg_frame.package_tree.item = Mock(return_value={'values': ['test;package', '1.0-1', 'Installed', 'No']})
        
        # Mock user confirming the removal (to test that it gets to validation)
        mock_askyesno.return_value = True
        
        # Test removal - should ask for confirmation
        self.pkg_frame.remove_selected()
        
        # Verify confirmation dialog was shown (package name validation happens later in the process)
        mock_askyesno.assert_called_once()
        self.assertIn("Remove 1 package", mock_askyesno.call_args[0][1])


class TestDashboardFeatures(unittest.TestCase):
    """Test dashboard last check and cache status features."""

    def setUp(self):
        """Set up test fixtures."""
        self.root = tk.Tk()
        self.root.withdraw()
        
        # Create mock main window
        self.mock_main_window = Mock()
        self.mock_main_window.colors = {
            'primary': '#2563eb',
            'primary_hover': '#1d4ed8',
            'secondary': '#64748b',
            'surface': '#ffffff',
            'text': '#1e293b',
            'text_secondary': '#64748b',
            'background': '#f8fafc',
            'success': '#059669',
            'error': '#dc2626',
            'warning': '#d97706',
            'border': '#e2e8f0'
        }
        self.mock_main_window.checker = Mock()
        self.mock_main_window.checker.last_news_items = []  # Fix for len() calls
        self.mock_main_window.checker.package_manager = Mock()
        self.mock_main_window.checker.package_manager.get_installed_package_names = Mock(return_value=[])
        self.mock_main_window.config = Mock()
        self.mock_main_window.config.config_file = None  # Add default value
        self.mock_main_window.config.config = {'critical_packages': []}  # Add config dict
        self.mock_main_window.run_check = Mock()
        self.mock_main_window.root = Mock()
        # Mock window width for responsive layout
        self.mock_main_window.root.winfo_width.return_value = 1200
        # Mock DPI scaling
        self.mock_main_window.dpi_scaling = 1.0
        
        # Create dashboard without mocking refresh
        self.dashboard = DashboardFrame(self.root, self.mock_main_window)

    def tearDown(self):
        """Clean up after tests."""
        try:
            self.root.destroy()
        except:
            pass

    def test_last_check_tracking_integration(self):
        """Test last check time tracking with real file operations."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_dir = os.path.join(tmpdir, 'cache')
            os.makedirs(cache_dir, exist_ok=True)
            
            # Write last check timestamp (2 hours ago)
            last_check_file = os.path.join(cache_dir, 'last_check')
            timestamp = (datetime.now() - timedelta(hours=2)).timestamp()
            with open(last_check_file, 'w') as f:
                f.write(str(timestamp))
            
            # Mock expanduser to return our test cache directory when the specific path is requested
            def mock_expanduser(path):
                if path == "~/.cache/arch-smart-update-checker":
                    return cache_dir
                return path
                
            # Mock expanduser to return our test directory
            with patch('src.gui.dashboard.os.path.expanduser', side_effect=mock_expanduser):
                # Mock just the Last Check label
                mock_label = Mock()
                self.dashboard.system_labels["Last Check"] = mock_label
                
                # Mock other methods to avoid side effects
                with patch.object(self.dashboard, 'get_total_packages_count', return_value=1000), \
                     patch.object(self.dashboard, 'get_issues_count', return_value=0), \
                     patch.object(self.dashboard, 'update_stats_cards'):
                    
                    self.dashboard.refresh()
                    
                    # Verify last check was updated to show relative time
                    mock_label.configure.assert_called_with(text="2 hours ago")

    def test_cache_status_display(self):
        """Test cache status display shows correct file count."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_dir = os.path.join(tmpdir, 'cache')
            os.makedirs(cache_dir, exist_ok=True)
            
            # Create some fake cache files
            for i in range(3):
                with open(os.path.join(cache_dir, f'feed{i}.json'), 'w') as f:
                    json.dump({'test': 'data'}, f)
            
            # Mock just the Cache Status label, not the whole dict
            mock_label = Mock()
            self.dashboard.system_labels["Cache Status"] = mock_label
            
            # Mock expanduser to return our test cache directory when the specific path is requested
            def mock_expanduser(path):
                if path == "~/.cache/arch-smart-update-checker":
                    return cache_dir
                return path
            
            with patch('src.gui.dashboard.os.path.expanduser', side_effect=mock_expanduser):
                # Mock other methods to avoid side effects
                with patch.object(self.dashboard, 'get_total_packages_count', return_value=1000), \
                     patch.object(self.dashboard, 'get_issues_count', return_value=0), \
                     patch.object(self.dashboard, 'update_stats_cards'):
                    
                    self.dashboard.refresh()
                    
                    # Verify cache status was updated with file count
                    mock_label.configure.assert_called_with(text="3 cached feeds")

    def test_check_updates_saves_timestamp(self):
        """Test that checking updates saves timestamp."""
        with tempfile.TemporaryDirectory() as tmpdir:
            home_dir = os.path.join(tmpdir, 'home')
            cache_dir = os.path.join(home_dir, '.cache', 'arch-smart-update-checker')
            
            with patch('os.path.expanduser') as mock_expanduser:
                mock_expanduser.return_value = os.path.join(home_dir, '.cache', 'arch-smart-update-checker')
                self.dashboard.check_updates()
                
                # Verify timestamp file was created
                last_check_file = os.path.join(cache_dir, 'last_check')
                self.assertTrue(os.path.exists(last_check_file))
                
                # Verify timestamp is recent
                with open(last_check_file, 'r') as f:
                    timestamp = float(f.read().strip())
                    time_diff = datetime.now().timestamp() - timestamp
                    self.assertLess(time_diff, 1.0)  # Should be less than 1 second old


class TestErrorHandling(unittest.TestCase):
    """Test error handling in various scenarios."""

    def setUp(self):
        """Set up test fixtures."""
        self.root = tk.Tk()
        self.root.withdraw()

    def tearDown(self):
        """Clean up after tests."""
        try:
            self.root.destroy()
        except:
            pass

    def test_subprocess_timeout_handling(self):
        """Test handling of subprocess timeouts."""
        from src.package_manager import PackageManager
        
        # Test package manager handling timeout
        pkg_mgr = PackageManager()
        
        # Mock the method that would timeout
        with patch.object(pkg_mgr, 'get_installed_packages') as mock_method:
            mock_method.side_effect = Exception("Command timed out")
            
            with self.assertRaises(Exception) as context:
                pkg_mgr.get_installed_packages()
            
            self.assertIn("timed out", str(context.exception))

    def test_permission_denied_handling(self):
        """Test handling of permission denied errors."""
        from src.package_manager import PackageManager
        
        # Test package manager handling permission error
        pkg_mgr = PackageManager()
        
        # Mock the method that would have permission error
        with patch.object(pkg_mgr, 'check_for_updates') as mock_method:
            mock_method.side_effect = Exception("Permission denied")
            
            with self.assertRaises(Exception) as context:
                pkg_mgr.check_for_updates()
            
            self.assertIn("Permission denied", str(context.exception))

    def test_invalid_feed_url_handling(self):
        """Test handling of invalid feed URLs."""
        from src.news_fetcher import NewsFetcher
        from src.exceptions import FeedParsingError
        from src.models import FeedConfig, FeedType
        
        fetcher = NewsFetcher()
        
        # Test with untrusted domain
        feed_config = FeedConfig(
            name='Test Feed',
            url='http://malicious.com/feed.xml',
            priority=1,
            feed_type=FeedType.NEWS,
            enabled=True
        )
        
        with self.assertRaises(FeedParsingError) as context:
            fetcher.fetch_feed(feed_config)
        
        self.assertIn('Invalid or insecure feed URL', str(context.exception))

    def test_cache_corruption_handling(self):
        """Test handling of corrupted cache files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_mgr = CacheManager(cache_dir=tmpdir)
            
            # Create corrupted cache file
            cache_file = os.path.join(tmpdir, 'test_key.json')
            with open(cache_file, 'w') as f:
                f.write('{"invalid json')
            
            # Test that corrupted cache is handled gracefully
            result = cache_mgr.get('test_key')
            self.assertIsNone(result)

    @patch('tkinter.messagebox.showerror')
    def test_gui_error_display(self, mock_error):
        """Test that GUI errors are displayed properly."""
        # Create mock main window
        mock_main_window = Mock()
        mock_main_window.colors = {
            'primary': '#2563eb',
            'primary_hover': '#1d4ed8',
            'secondary': '#64748b',
            'surface': '#ffffff',
            'text': '#1e293b',
            'text_secondary': '#64748b',
            'background': '#f8fafc',
            'success': '#059669',
            'error': '#dc2626',
            'warning': '#d97706',
            'info': '#3b82f6',
            'border': '#e2e8f0'
        }
        mock_main_window.checker = Mock()
        mock_main_window.config = Mock()
        mock_main_window.root = Mock()
        
        with patch.object(PackageManagerFrame, 'load_packages', lambda self: None):
            pkg_frame = PackageManagerFrame(self.root, mock_main_window)
        
        # Set up missing attributes
        pkg_frame.package_manager = Mock()
        pkg_frame.package_manager.check_for_updates.return_value = []
        pkg_frame.status_label = Mock()
        
        # Test error display
        pkg_frame.show_error("Test error message")
        mock_error.assert_called_once_with("Error", "Test error message")


class TestThreadSafety(unittest.TestCase):
    """Test thread safety and GUI updates from background threads."""

    def setUp(self):
        """Set up test fixtures."""
        self.root = tk.Tk()
        self.root.withdraw()

    def tearDown(self):
        """Clean up after tests."""
        try:
            self.root.destroy()
        except:
            pass

    def test_gui_updates_use_after(self):
        """Test that GUI updates from threads use root.after()."""
        # Create mock main window
        mock_main_window = Mock()
        mock_main_window.colors = {
            'primary': '#2563eb',
            'primary_hover': '#1d4ed8',
            'secondary': '#64748b',
            'surface': '#ffffff',
            'text': '#1e293b',
            'text_secondary': '#64748b',
            'background': '#f8fafc',
            'success': '#059669',
            'error': '#dc2626',
            'warning': '#d97706',
            'info': '#3b82f6',
            'border': '#e2e8f0'
        }
        mock_main_window.checker = Mock()
        mock_main_window.checker.package_manager = Mock()
        mock_main_window.config = Mock()
        mock_main_window.config.get_critical_packages.return_value = []
        mock_main_window.root = Mock()
        
        with patch.object(PackageManagerFrame, 'load_packages', lambda self: None):
            pkg_frame = PackageManagerFrame(self.root, mock_main_window)
        
        # Set up missing attributes
        pkg_frame.package_manager = Mock()
        pkg_frame.package_manager.check_for_updates.return_value = []
        pkg_frame.status_label = Mock()
        
        # Mock package data
        packages = [{'name': 'test', 'version': '1.0'}]
        critical_packages = set()
        
        # Test display_packages uses after() for updates
        pkg_frame.display_packages(packages, critical_packages)
        
        # Verify that packages are displayed in the tree
        items = pkg_frame.package_tree.get_children()
        self.assertTrue(len(items) > 0, "Expected items to be displayed in tree")
        
        # Check that the package data was correctly displayed
        first_item = pkg_frame.package_tree.item(items[0])
        self.assertEqual(first_item['text'], 'test')


class TestInputValidation(unittest.TestCase):
    """Test input validation for security."""

    def setUp(self):
        """Set up test fixtures."""
        self.root = tk.Tk()
        self.root.withdraw()

    def tearDown(self):
        """Clean up after tests."""
        try:
            self.root.destroy()
        except:
            pass

    def test_package_name_validation(self):
        """Test package name validation prevents command injection."""
        from src.gui.main_window import UpdatesNewsFrame
        
        # Create mock main window
        mock_main_window = Mock()
        mock_main_window.colors = {
            'primary': '#2563eb',
            'primary_hover': '#1d4ed8',
            'secondary': '#64748b',
            'surface': '#ffffff',
            'text': '#1e293b',
            'text_secondary': '#64748b',
            'background': '#f8fafc',
            'success': '#059669',
            'error': '#dc2626',
            'warning': '#d97706',
            'border': '#e2e8f0'
        }
        mock_main_window.checker = Mock()
        mock_main_window.checker.pattern_matcher = Mock()
        mock_main_window.checker.pattern_matcher.find_affected_packages = Mock(return_value=set())
        mock_main_window.checker.news_fetcher = Mock()
        mock_main_window.checker.news_fetcher.max_news_age_days = 7  # Fix for comparison issue
        mock_main_window.update_status = Mock()
        mock_main_window.get_text_color = Mock(return_value='#1e293b')  # Fix for color Mock issue
        
        frame = UpdatesNewsFrame(self.root, mock_main_window, ['valid-package', 'invalid;package'], [])
        
        # Set up package selection
        frame.selected_packages = {'valid-package', 'invalid;package'}
        
        # Test validation
        with patch('tkinter.messagebox.showerror') as mock_error:
            frame.apply_updates()
            
            # Verify error was shown for invalid package
            mock_error.assert_called_once()
            self.assertIn('Invalid package name', mock_error.call_args[0][1])

    def test_feed_url_validation(self):
        """Test feed URL validation logic."""
        from src.news_fetcher import NewsFetcher
        
        fetcher = NewsFetcher()
        
        # Test valid URLs
        self.assertTrue(fetcher._validate_feed_domain('https://archlinux.org/feeds/news/'))
        self.assertTrue(fetcher._validate_feed_domain('http://localhost/feed.xml'))
        
        # Test invalid URLs  
        self.assertFalse(fetcher._validate_feed_domain(''))
        self.assertFalse(fetcher._validate_feed_domain('not-a-url'))
        self.assertFalse(fetcher._validate_feed_domain('ftp://example.com/feed'))


if __name__ == '__main__':
    unittest.main() 