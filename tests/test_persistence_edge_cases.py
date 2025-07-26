"""
Persistence edge cases and error scenario tests for dashboard stats and cache.
Tests file corruption, permission issues, disk space, and graceful failure handling.
"""

import unittest
import tkinter as tk
import json
import tempfile
import shutil
import os
from unittest.mock import Mock, patch, mock_open
import sys
from pathlib import Path

# Imports are handled by pytest and the src/ structure

from src.gui.dashboard import DashboardFrame

# Use singleton root to prevent memory leaks
_test_root = None

def get_or_create_root():
    """Get or create a singleton Tk root to prevent memory leaks."""
    global _test_root
    if _test_root is None:
        # Skip GUI setup in headless environment
        if os.environ.get('ASUC_HEADLESS') or os.environ.get('CI'):
            return None
        _test_root = tk.Tk()
        _test_root.withdraw()
    return _test_root


class TestPersistenceErrorHandling(unittest.TestCase):
    """Test error handling in persistence operations."""

    def setUp(self):
        """Set up test fixtures."""
        # Skip GUI setup in headless environment
        if os.environ.get('ASUC_HEADLESS') or os.environ.get('CI'):
            self.skipTest("Skipping GUI test in headless environment")
        parent = get_or_create_root()
        self.root = tk.Toplevel(parent)
        self.root.withdraw()
        
        # Create mock main window
        self.mock_main_window = Mock()
        self.mock_main_window.colors = {
            'background': '#F5F7FA',
            'surface': '#FFFFFF',
            'text': '#1E293B',
            'text_secondary': '#64748B'
        }
        
        self.mock_checker = Mock()
        self.mock_checker.last_news_items = [] # Fix for len() calls
        self.mock_config = Mock()
        self.mock_main_window.checker = self.mock_checker
        self.mock_main_window.config = self.mock_config

    def tearDown(self):
        """Clean up test fixtures."""
        try:
            self.root.destroy()
        except tk.TclError:
            pass

    def test_corrupted_json_file_recovery(self):
        """Test recovery from corrupted JSON persistence file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            stats_file = os.path.join(tmpdir, 'stats.json')
            
            # Create corrupted JSON file
            with open(stats_file, 'w') as f:
                f.write('{ "corrupted": json content without closing brace')
            
            with patch('src.gui.dashboard.DashboardFrame.setup_ui'), \
                 patch('src.gui.dashboard.DashboardFrame.refresh'), \
                 patch('os.path.expanduser', return_value=stats_file):
                
                dashboard = DashboardFrame(self.root, self.mock_main_window)
                dashboard.stats_cards = {}  # Mock to avoid AttributeError
                
                # Loading corrupted file should not crash
                result = dashboard.load_persisted_non_update_stats()
                self.assertIsNone(result)  # Should return None gracefully
                
                # Should be able to save new stats after corruption
                dashboard.save_non_update_stats(total_packages=1500)
                
                # Verify file was overwritten with valid JSON
                with open(stats_file, 'r') as f:
                    data = json.load(f)
                self.assertEqual(data['total_packages'], 1500)

    def test_permission_denied_on_save(self):
        """Test graceful handling of permission denied errors."""
        with patch('src.gui.dashboard.DashboardFrame.setup_ui'), \
             patch('src.gui.dashboard.DashboardFrame.refresh'):
            
            dashboard = DashboardFrame(self.root, self.mock_main_window)
            
            # Mock open to raise PermissionError
            with patch('builtins.open', side_effect=PermissionError("Permission denied")):
                # Should not crash on permission error
                dashboard.save_non_update_stats(total_packages=1000)
                # Should complete without raising exception
                self.assertTrue(True)

    def test_disk_full_error_handling(self):
        """Test handling of disk full errors during save."""
        with patch('src.gui.dashboard.DashboardFrame.setup_ui'), \
             patch('src.gui.dashboard.DashboardFrame.refresh'):
            
            dashboard = DashboardFrame(self.root, self.mock_main_window)
            
            # Mock open to raise OSError (disk full)
            with patch('builtins.open', side_effect=OSError("No space left on device")):
                # Should not crash on disk full error
                dashboard.save_non_update_stats(total_packages=1000)
                # Should complete without raising exception
                self.assertTrue(True)

    def test_directory_creation_failure(self):
        """Test handling of directory creation failures."""
        with patch('src.gui.dashboard.DashboardFrame.setup_ui'), \
             patch('src.gui.dashboard.DashboardFrame.refresh'):
            
            dashboard = DashboardFrame(self.root, self.mock_main_window)
            
            # Mock os.makedirs to raise PermissionError
            with patch('os.makedirs', side_effect=PermissionError("Permission denied")):
                # Should not crash on directory creation failure
                dashboard.save_non_update_stats(total_packages=1000)
                # Should complete without raising exception
                self.assertTrue(True)

    def test_invalid_json_structure_handling(self):
        """Test handling of valid JSON with invalid structure."""
        with tempfile.TemporaryDirectory() as tmpdir:
            stats_file = os.path.join(tmpdir, 'stats.json')
            
            # Create valid JSON but wrong structure (list instead of dict)
            with open(stats_file, 'w') as f:
                json.dump(["not", "a", "dict"], f)
            
            with patch('src.gui.dashboard.DashboardFrame.setup_ui'), \
                 patch('src.gui.dashboard.DashboardFrame.refresh'), \
                 patch('os.path.expanduser', return_value=stats_file):
                
                dashboard = DashboardFrame(self.root, self.mock_main_window)
                dashboard.stats_cards = {}
                
                # Should handle invalid structure gracefully
                result = dashboard.load_persisted_non_update_stats()
                self.assertIsNone(result)

    def test_empty_file_handling(self):
        """Test handling of empty stats file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            stats_file = os.path.join(tmpdir, 'stats.json')
            
            # Create empty file
            Path(stats_file).touch()
            
            with patch('src.gui.dashboard.DashboardFrame.setup_ui'), \
                 patch('src.gui.dashboard.DashboardFrame.refresh'), \
                 patch('os.path.expanduser', return_value=stats_file):
                
                dashboard = DashboardFrame(self.root, self.mock_main_window)
                dashboard.stats_cards = {}
                
                # Should handle empty file gracefully
                result = dashboard.load_persisted_non_update_stats()
                self.assertIsNone(result)

    def test_update_history_corruption_handling(self):
        """Test handling of corrupted update_history.json file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            history_file = os.path.join(tmpdir, 'update_history.json')
            
            # Create corrupted JSON file
            with open(history_file, 'w') as f:
                f.write('{"invalid": json content without closing brace')
            
            from src.utils.update_history import UpdateHistoryManager
            
            # Manager should handle corruption gracefully
            manager = UpdateHistoryManager(history_file)
            entries = manager.all()
            
            # Should return empty list and log warning
            self.assertEqual(entries, [])
            
            # Should be able to add new entries after corruption
            from src.utils.update_history import UpdateHistoryEntry
            from datetime import datetime
            
            new_entry = UpdateHistoryEntry(
                timestamp=datetime.now(),
                packages=['test-pkg'],
                succeeded=True,
                exit_code=0,
                duration_sec=30.0
            )
            
            # Should not raise exception
            manager.add(new_entry)
            manager._executor.shutdown(wait=True)
            
            # Should be able to load the new entry
            entries = manager.all()
            self.assertEqual(len(entries), 1)
            self.assertEqual(entries[0].packages, ['test-pkg'])

    def test_unicode_error_handling(self):
        """Test handling of unicode encoding errors."""
        with tempfile.TemporaryDirectory() as tmpdir:
            stats_file = os.path.join(tmpdir, 'stats.json')
            
            # Create file with invalid UTF-8
            with open(stats_file, 'wb') as f:
                f.write(b'\xff\xfe{"invalid": "utf8"}')
            
            with patch('src.gui.dashboard.DashboardFrame.setup_ui'), \
                 patch('src.gui.dashboard.DashboardFrame.refresh'), \
                 patch('os.path.expanduser', return_value=stats_file):
                
                dashboard = DashboardFrame(self.root, self.mock_main_window)
                dashboard.stats_cards = {}
                
                # Should handle unicode errors gracefully
                result = dashboard.load_persisted_non_update_stats()
                self.assertIsNone(result)


class TestCacheDirectoryEdgeCases(unittest.TestCase):
    """Test edge cases for cache directory operations."""

    def setUp(self):
        """Set up test fixtures."""
        if os.environ.get('ASUC_HEADLESS') or os.environ.get('CI'):
            self.skipTest("Skipping GUI test in headless environment")
        parent = get_or_create_root()
        self.root = tk.Toplevel(parent)
        self.root.withdraw()
        
        # Create mock main window
        self.mock_main_window = Mock()
        self.mock_main_window.colors = {
            'background': '#F5F7FA',
            'surface': '#FFFFFF',
            'text': '#1E293B'
        }
        
        # Mock checker with last_news_items
        self.mock_checker = Mock()
        self.mock_checker.last_news_items = []  # Fix for len() calls
        self.mock_main_window.checker = self.mock_checker

    def tearDown(self):
        """Clean up test fixtures."""
        try:
            self.root.destroy()
        except tk.TclError:
            pass

    def test_cache_directory_is_file_not_directory(self):
        """Test handling when cache path exists as file instead of directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_path = os.path.join(tmpdir, 'cache')
            
            # Create file instead of directory
            with open(cache_path, 'w') as f:
                f.write("I'm a file, not a directory")
            
            mock_label = Mock()
            
            with patch('src.gui.dashboard.DashboardFrame.setup_ui'), \
                 patch('src.gui.dashboard.DashboardFrame.update_stats_cards'), \
                 patch('os.path.expanduser', return_value=cache_path):
                
                dashboard = DashboardFrame(self.root, self.mock_main_window)
                dashboard.system_labels = {"Cache Status": mock_label, "Last Check": Mock(), "Config File": Mock()}
                
                # Mock other methods to isolate test
                with patch.object(dashboard, 'update_stats_cards'):
                    dashboard.refresh()
                    
                    # Should handle gracefully and show error status
                    mock_label.configure.assert_called_with(text="Error")

    def test_cache_directory_permission_denied(self):
        """Test handling of permission denied when accessing cache directory."""
        mock_label = Mock()
        
        with patch('src.gui.dashboard.DashboardFrame.setup_ui'), \
             patch('src.gui.dashboard.DashboardFrame.update_stats_cards'), \
             patch('os.path.expanduser', return_value='/root/no-permission'), \
             patch('os.path.exists', return_value=True), \
             patch('os.listdir', side_effect=PermissionError("Permission denied")):
            
            dashboard = DashboardFrame(self.root, self.mock_main_window)
            dashboard.system_labels = {"Cache Status": mock_label, "Last Check": Mock(), "Config File": Mock()}
            
            # Mock other methods to isolate test
            with patch.object(dashboard, 'update_stats_cards'):
                dashboard.refresh()
                
                # Should handle gracefully and show error status
                mock_label.configure.assert_called_with(text="Error")

    def test_mixed_cache_files(self):
        """Test handling of cache directory with mixed file types."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_dir = os.path.join(tmpdir, 'cache')
            os.makedirs(cache_dir)
            
            # Create mix of JSON and non-JSON files
            with open(os.path.join(cache_dir, 'feed1.json'), 'w') as f:
                json.dump({'test': 'data1'}, f)
            with open(os.path.join(cache_dir, 'feed2.json'), 'w') as f:
                json.dump({'test': 'data2'}, f)
            with open(os.path.join(cache_dir, 'not_json.txt'), 'w') as f:
                f.write('not json')
            with open(os.path.join(cache_dir, 'last_check'), 'w') as f:
                f.write('1234567890')
            
            mock_label = Mock()
            
            with patch('src.gui.dashboard.DashboardFrame.setup_ui'), \
                 patch('src.gui.dashboard.DashboardFrame.update_stats_cards'), \
                 patch('os.path.expanduser', return_value=cache_dir):
                
                dashboard = DashboardFrame(self.root, self.mock_main_window)
                dashboard.system_labels = {"Cache Status": mock_label, "Last Check": Mock(), "Config File": Mock()}
                
                # Mock stats_cards for update_stats_cards method
                mock_stats_cards = {}
                for title in ["📦 Total Packages", "🔄 Available Updates", "⚠️ Issues Found", "📰 News Items"]:
                    mock_card = Mock()
                    mock_card.value_label = Mock()
                    mock_stats_cards[title] = mock_card
                dashboard.stats_cards = mock_stats_cards
                
                # Mock data sources for update_stats_cards
                with patch.object(dashboard, 'get_total_packages_count', return_value=1000), \
                     patch.object(dashboard, 'get_issues_count', return_value=0), \
                     patch.object(dashboard, 'save_non_update_stats'):
                    
                    dashboard.refresh()
                    
                    # Should count only JSON files
                    mock_label.configure.assert_called_with(text="2 cached feeds")


class TestTimestampFileEdgeCases(unittest.TestCase):
    """Test edge cases for timestamp file operations."""

    def setUp(self):
        """Set up test fixtures."""
        if os.environ.get('ASUC_HEADLESS') or os.environ.get('CI'):
            self.skipTest("Skipping GUI test in headless environment")
        parent = get_or_create_root()
        self.root = tk.Toplevel(parent)
        self.root.withdraw()
        
        # Create mock main window
        self.mock_main_window = Mock()
        self.mock_main_window.colors = {'background': '#F5F7FA'}
        
        # Mock checker with last_news_items
        self.mock_checker = Mock()
        self.mock_checker.last_news_items = []  # Fix for len() calls
        self.mock_main_window.checker = self.mock_checker

    def tearDown(self):
        """Clean up test fixtures."""
        try:
            self.root.destroy()
        except tk.TclError:
            pass

    def test_invalid_timestamp_format(self):
        """Test handling of invalid timestamp format in last_check file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_dir = os.path.join(tmpdir, 'cache')
            os.makedirs(cache_dir)
            
            # Create file with invalid timestamp
            last_check_file = os.path.join(cache_dir, 'last_check')
            with open(last_check_file, 'w') as f:
                f.write('not_a_timestamp')
            
            mock_label = Mock()
            
            with patch('src.gui.dashboard.DashboardFrame.setup_ui'), \
                 patch('src.gui.dashboard.DashboardFrame.update_stats_cards'), \
                 patch('os.path.expanduser', return_value=cache_dir):
                
                dashboard = DashboardFrame(self.root, self.mock_main_window)
                dashboard.system_labels = {"Last Check": mock_label, "Cache Status": Mock(), "Config File": Mock()}
                
                # Mock other methods to isolate test
                with patch.object(dashboard, 'update_stats_cards'):
                    dashboard.refresh()
                    
                    # Should fallback to "Never" on invalid timestamp
                    mock_label.configure.assert_called_with(text="Never")

    def test_future_timestamp_handling(self):
        """Test handling of timestamp from the future."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_dir = os.path.join(tmpdir, 'cache')
            os.makedirs(cache_dir)
            
            # Create file with future timestamp (1 year from now)
            from datetime import datetime, timedelta
            future_time = datetime.now() + timedelta(days=365)
            last_check_file = os.path.join(cache_dir, 'last_check')
            with open(last_check_file, 'w') as f:
                f.write(str(future_time.timestamp()))
            
            mock_label = Mock()
            
            with patch('src.gui.dashboard.DashboardFrame.setup_ui'), \
                 patch('src.gui.dashboard.DashboardFrame.update_stats_cards'), \
                 patch('os.path.expanduser', return_value=cache_dir):
                
                dashboard = DashboardFrame(self.root, self.mock_main_window)
                dashboard.system_labels = {"Last Check": mock_label, "Cache Status": Mock(), "Config File": Mock()}
                
                # Mock other methods to isolate test
                with patch.object(dashboard, 'update_stats_cards'):
                    dashboard.refresh()
                    
                    # Should handle future timestamps gracefully (will show some relative time)
                    mock_label.configure.assert_called()

    def test_empty_timestamp_file(self):
        """Test handling of empty timestamp file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_dir = os.path.join(tmpdir, 'cache')
            os.makedirs(cache_dir)
            
            # Create empty timestamp file
            last_check_file = os.path.join(cache_dir, 'last_check')
            Path(last_check_file).touch()
            
            mock_label = Mock()
            
            with patch('src.gui.dashboard.DashboardFrame.setup_ui'), \
                 patch('src.gui.dashboard.DashboardFrame.update_stats_cards'), \
                 patch('os.path.expanduser', return_value=cache_dir):
                
                dashboard = DashboardFrame(self.root, self.mock_main_window)
                dashboard.system_labels = {"Last Check": mock_label, "Cache Status": Mock(), "Config File": Mock()}
                
                # Mock other methods to isolate test
                with patch.object(dashboard, 'update_stats_cards'):
                    dashboard.refresh()
                    
                    # Should fallback to "Never" on empty file
                    mock_label.configure.assert_called_with(text="Never")


class TestConcurrentAccess(unittest.TestCase):
    """Test concurrent access scenarios for persistence."""

    def setUp(self):
        """Set up test fixtures."""
        parent = get_or_create_root()
        self.root = tk.Toplevel(parent)
        self.root.withdraw()

    def tearDown(self):
        """Clean up test fixtures."""
        try:
            self.root.destroy()
        except tk.TclError:
            pass

    def test_concurrent_stats_file_access(self):
        """Test concurrent access to stats file from multiple instances."""
        with tempfile.TemporaryDirectory() as tmpdir:
            stats_file = os.path.join(tmpdir, 'stats.json')
            
            # Create initial stats file
            initial_data = {'total_packages': 1000}
            with open(stats_file, 'w') as f:
                json.dump(initial_data, f)
            
            # Create mock main windows
            mock_main_window1 = Mock()
            mock_main_window1.colors = {'background': '#F5F7FA'}
            mock_main_window1.checker = Mock()
            mock_main_window1.checker.last_news_items = []
            
            mock_main_window2 = Mock()
            mock_main_window2.colors = {'background': '#F5F7FA'}
            mock_main_window2.checker = Mock()
            mock_main_window2.checker.last_news_items = []
            
            with patch('src.gui.dashboard.DashboardFrame.setup_ui'), \
                 patch('src.gui.dashboard.DashboardFrame.refresh'), \
                 patch('os.path.expanduser', return_value=stats_file):
                
                # Create two dashboard instances
                dashboard1 = DashboardFrame(self.root, mock_main_window1)
                dashboard2 = DashboardFrame(self.root, mock_main_window2)
                
                # Both save different data (simulating race condition)
                dashboard1.save_non_update_stats(total_packages=1500)
                dashboard2.save_non_update_stats(total_packages=2000)
                
                # File should contain one of the values (last writer wins)
                with open(stats_file, 'r') as f:
                    data = json.load(f)
                    
                # Should be valid JSON with one of the expected values
                self.assertIn(data['total_packages'], [1500, 2000])

    def test_file_locked_during_write(self):
        """Test handling when file is locked by another process."""
        mock_main_window = Mock()
        mock_main_window.checker = Mock()
        mock_main_window.checker.last_news_items = []
        
        with patch('src.gui.dashboard.DashboardFrame.setup_ui'), \
             patch('src.gui.dashboard.DashboardFrame.refresh'):
            
            dashboard = DashboardFrame(self.root, mock_main_window)
            
            # Mock open to raise PermissionError (file locked)
            with patch('builtins.open', side_effect=PermissionError("The process cannot access the file because it is being used by another process")):
                # Should handle locked file gracefully
                dashboard.save_non_update_stats(total_packages=1000)
                # Should complete without raising exception
                self.assertTrue(True)


if __name__ == '__main__':
    unittest.main(verbosity=2) 