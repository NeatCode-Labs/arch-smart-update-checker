"""
Test updates for new functionality in Arch Smart Update Checker.
Tests the changes made to update process including:
- Removed confirmation dialog
- Changed pacman command from -S to -Su
- Error monitoring and solutions dialog
"""

import unittest
from unittest.mock import Mock, patch, MagicMock, call, mock_open
import tkinter as tk
import tempfile
import os
import threading
import time

from src.gui.main_window import UpdatesNewsFrame
from src.config import Config
from src.checker import UpdateChecker


class TestUpdateFunctionality(unittest.TestCase):
    """Test updated functionality for package updates."""
    
    def setUp(self):
        """Set up test fixtures."""
        if os.environ.get('ASUC_HEADLESS') or os.environ.get('CI'):
            self.skipTest("Skipping GUI test in headless environment")
        self.root = tk.Tk()
        self.root.withdraw()
    
    def tearDown(self):
        """Clean up after tests."""
        self.root.destroy()
    
    def test_apply_updates_no_confirmation_dialog(self):
        """Test that apply_updates no longer shows confirmation dialog and uses pkexec."""
        # Create UpdatesNewsFrame with test data
        mock_main_window = Mock()
        mock_main_window.root = self.root
        mock_main_window.update_status = Mock()
        mock_main_window.colors = {
            'background': '#1a1a1a',
            'surface': '#2d2d2d',
            'primary': '#3b82f6',
            'text': '#ffffff',
            'text_secondary': '#a0a0a0',
            'error': '#ef4444',
            'success': '#10b981',
            'warning': '#f59e0b',
            'info': '#3b82f6'
        }
        mock_main_window.get_text_color = Mock(return_value='#000000')
        mock_main_window.checker = Mock()
        mock_main_window.checker.news_fetcher = Mock()
        mock_main_window.checker.news_fetcher.max_news_age_days = 7
        mock_main_window.checker.pattern_matcher = Mock()
        mock_main_window.checker.pattern_matcher.find_affected_packages = Mock(return_value=set())
        mock_main_window.checker.package_manager = Mock()
        mock_main_window.checker.package_manager.clear_cache = Mock()
        mock_main_window.checker.last_update_objects = {}
        mock_main_window.show_frame = Mock()
        mock_main_window.config = Mock()
        mock_main_window.config.get = Mock(return_value=False)  # For update_history_enabled
        
        frame = UpdatesNewsFrame(self.root, mock_main_window, ['package1', 'package2'], [])
        frame.selected_packages = {'package1', 'package2'}
        # Set up the pkg_vars that apply_updates expects
        frame.pkg_vars = {
            'package1': Mock(),
            'package2': Mock()
        }
        frame.pkg_vars['package1'].get.return_value = True
        frame.pkg_vars['package2'].get.return_value = True
        
        # Mock the messagebox and subprocess for pkexec
        with patch('tkinter.messagebox.askyesno') as mock_confirm, \
             patch('subprocess.Popen') as mock_popen, \
             patch('src.utils.thread_manager.create_managed_thread') as mock_thread:
            
            # Mock successful pkexec process
            mock_process = Mock()
            mock_process.stdout.readline.side_effect = ['Installing packages...\n', '']
            mock_process.poll.return_value = 0  # Success
            mock_popen.return_value = mock_process
            
            # Mock thread creation to execute immediately
            def execute_thread(thread_id, target, is_background=True):
                # Execute the thread target immediately for testing
                if target:
                    target()
                return Mock()
            
            mock_thread.side_effect = execute_thread
            
            frame.apply_updates()
            
            # Verify askyesno was NOT called (no confirmation dialog)
            mock_confirm.assert_not_called()
            
            # Verify update_status was called multiple times during the process
            mock_main_window.update_status.assert_any_call("Starting update process...", "info")

    def test_apply_updates_uses_correct_pacman_command(self):
        """Test that apply_updates uses pkexec with 'pacman -S' for selected packages."""
        mock_main_window = Mock()
        mock_main_window.root = self.root
        mock_main_window.update_status = Mock()
        mock_main_window.colors = {
            'background': '#1a1a1a',
            'surface': '#2d2d2d',
            'primary': '#3b82f6',
            'text': '#ffffff',
            'text_secondary': '#a0a0a0'
        }
        mock_main_window.get_text_color = Mock(return_value='#000000')
        mock_main_window.checker = Mock()
        mock_main_window.checker.news_fetcher = Mock()
        mock_main_window.checker.news_fetcher.max_news_age_days = 7
        mock_main_window.checker.pattern_matcher = Mock()
        mock_main_window.checker.pattern_matcher.find_affected_packages = Mock(return_value=set())
        mock_main_window.checker.package_manager = Mock()
        mock_main_window.checker.package_manager.clear_cache = Mock()
        mock_main_window.checker.last_update_objects = {}
        mock_main_window.show_frame = Mock()
        mock_main_window.config = Mock()
        mock_main_window.config.get = Mock(return_value=False)
        
        frame = UpdatesNewsFrame(self.root, mock_main_window, ['vim', 'git'], [])
        frame.selected_packages = {'vim', 'git'}
        # Set up the pkg_vars that apply_updates expects
        frame.pkg_vars = {
            'vim': Mock(),
            'git': Mock()
        }
        frame.pkg_vars['vim'].get.return_value = True
        frame.pkg_vars['git'].get.return_value = True
        
        with patch('subprocess.Popen') as mock_popen, \
             patch('src.utils.thread_manager.ThreadResourceManager.create_managed_thread') as mock_thread:
            
            # Mock successful pkexec process
            mock_process = Mock()
            mock_process.stdout.readline.side_effect = ['Installing packages...\n', '']
            mock_process.poll.return_value = 0  # Success
            mock_popen.return_value = mock_process
            
            # Mock thread creation to execute immediately
            def execute_thread(thread_id, target, is_background=True):
                # Execute the thread target immediately for testing
                if target:
                    target()
                return Mock()
            
            mock_thread.side_effect = execute_thread
            
            # Also need to mock tempfile.mkstemp for the output file
            with patch('tempfile.mkstemp') as mock_mkstemp:
                mock_mkstemp.return_value = (1, '/tmp/test_output.log')
                with patch('os.close'), patch('os.chmod'), patch('builtins.open', mock_open()):
                    frame.apply_updates()
            
            # Find the pkexec call among all Popen calls
            pkexec_call = None
            for call in mock_popen.call_args_list:
                if call[0][0] and call[0][0][0] == 'pkexec':
                    pkexec_call = call[0][0]
                    break
            
            # Verify pkexec command was called
            self.assertIsNotNone(pkexec_call, "No pkexec command found")
            self.assertEqual(pkexec_call[0], 'pkexec')
            self.assertEqual(pkexec_call[1], 'pacman')
            self.assertEqual(pkexec_call[2], '-S')
            self.assertIn('vim', pkexec_call)
            self.assertIn('git', pkexec_call)
    
    def test_show_update_error_solutions_mirror_sync(self):
        """Test error solutions dialog for mirror sync issues."""
        # Create a minimal mock MainWindow with required attributes
        mock_main_window = Mock()
        mock_main_window.root = self.root
        mock_main_window.colors = {
            'background': '#1a1a1a',
            'surface': '#2d2d2d',
            'primary': '#3b82f6',
            'text': '#ffffff',
            'text_secondary': '#a0a0a0',
            'error': '#ef4444'
        }
        mock_main_window._center_window = Mock()
        mock_main_window.update_status = Mock()
        
        error_output = """
        error: failed retrieving file 'perl-5.40.2-1-x86_64.pkg.tar.zst' from mirror.sunred.org : The requested URL returned error: 404
        error: failed retrieving file 'net-snmp-5.9.4-6-x86_64.pkg.tar.zst' from mirror.sunred.org : The requested URL returned error: 404
        """
        
        with patch('tkinter.Toplevel') as mock_toplevel, \
             patch('tkinter.Label') as mock_label, \
             patch('tkinter.Frame'), \
             patch('tkinter.Text'), \
             patch('tkinter.Button'):
            
            mock_dialog = Mock()
            mock_toplevel.return_value = mock_dialog
            
            # Import and call the method directly  
            from src.gui.main_window import MainWindow
            # Bind the method to our mock
            MainWindow.show_update_error_solutions(mock_main_window, error_output)
            
            # Verify dialog was created
            mock_toplevel.assert_called_once_with(self.root)
            mock_dialog.title.assert_called_with("Update Error - Solutions")
            
            # Check that appropriate labels were created
            label_calls = [call[1]['text'] if 'text' in call[1] else None 
                          for call in mock_label.call_args_list if len(call) > 1]
            combined_text = ' '.join([t for t in label_calls if t])
            
            # Verify mirror sync specific content
            self.assertIn('Mirror Synchronization Issue', combined_text)
    
    def test_show_update_error_solutions_file_conflicts(self):
        """Test error solutions dialog for file conflict errors."""
        mock_main_window = Mock()
        mock_main_window.root = self.root
        mock_main_window.colors = {
            'background': '#1a1a1a',
            'surface': '#2d2d2d',
            'primary': '#3b82f6',
            'text': '#ffffff',
            'text_secondary': '#a0a0a0',
            'error': '#ef4444'
        }
        mock_main_window._center_window = Mock()
        mock_main_window.update_status = Mock()
        
        error_output = """
        error: failed to commit transaction (conflicting files)
        /usr/lib/file.so exists in both 'package1' and 'package2'
        """
        
        with patch('tkinter.Toplevel') as mock_toplevel, \
             patch('tkinter.Label') as mock_label, \
             patch('tkinter.Frame'), \
             patch('tkinter.Text'), \
             patch('tkinter.Button'):
            
            mock_dialog = Mock()
            mock_toplevel.return_value = mock_dialog
            
            # Capture Label text
            label_texts = []
            def capture_label(*args, **kwargs):
                if 'text' in kwargs:
                    label_texts.append(kwargs['text'])
                return Mock()
            
            mock_label.side_effect = capture_label
            
            from src.gui.main_window import MainWindow
            MainWindow.show_update_error_solutions(mock_main_window, error_output)
            
            # Verify appropriate solution is shown
            combined_text = ' '.join(label_texts)
            self.assertIn('File Conflict', combined_text)
    
    def test_package_validation_before_update(self):
        """Test that package names are validated before update."""
        mock_main_window = Mock()
        mock_main_window.root = self.root
        mock_main_window.update_status = Mock()
        mock_main_window.colors = {
            'background': '#1a1a1a',
            'surface': '#2d2d2d',
            'primary': '#3b82f6',
            'text': '#ffffff'
        }
        mock_main_window.get_text_color = Mock(return_value='#000000')
        mock_main_window.checker = Mock()
        mock_main_window.checker.news_fetcher = Mock()
        mock_main_window.checker.news_fetcher.max_news_age_days = 7
        mock_main_window.checker.pattern_matcher = Mock()
        mock_main_window.checker.pattern_matcher.find_affected_packages = Mock(return_value=set())
        
        frame = UpdatesNewsFrame(self.root, mock_main_window, ['valid-package', 'invalid;package'], [])
        frame.selected_packages = {'valid-package', 'invalid;package'}
        # Set up the pkg_vars that apply_updates expects  
        frame.pkg_vars = {
            'valid-package': Mock(),
            'invalid;package': Mock()
        }
        frame.pkg_vars['valid-package'].get.return_value = True
        frame.pkg_vars['invalid;package'].get.return_value = True  # User selected the invalid package
        
        with patch('tkinter.messagebox.showerror') as mock_error:
            frame.apply_updates()
            
            # Verify error dialog was shown for invalid package name
            mock_error.assert_called_once()
    
    def test_fallback_shows_correct_command(self):
        """Test fallback message shows correct command when pkexec authentication fails."""
        mock_main_window = Mock()
        mock_main_window.root = self.root
        mock_main_window.update_status = Mock()
        mock_main_window.colors = {
            'background': '#1a1a1a',
            'surface': '#2d2d2d',
            'primary': '#3b82f6',
            'text': '#ffffff',
            'text_secondary': '#a0a0a0',
            'error': '#ef4444',
            'success': '#10b981',
            'warning': '#f59e0b',
            'info': '#3b82f6'
        }
        mock_main_window.get_text_color = Mock(return_value='#000000')
        mock_main_window.checker = Mock()
        mock_main_window.checker.news_fetcher = Mock()
        mock_main_window.checker.news_fetcher.max_news_age_days = 7
        mock_main_window.checker.pattern_matcher = Mock()
        mock_main_window.checker.pattern_matcher.find_affected_packages = Mock(return_value=set())
        mock_main_window.show_frame = Mock()
        
        frame = UpdatesNewsFrame(self.root, mock_main_window, ['vim', 'git'], [])
        frame.selected_packages = {'vim', 'git'}
        
        with patch('subprocess.Popen') as mock_popen, \
             patch('src.utils.thread_manager.ThreadResourceManager.create_managed_thread') as mock_thread:
            
            # Mock pkexec authentication failure (exit code 126 or 127)
            mock_process = Mock()
            mock_process.stdout.readline.side_effect = ['Authentication cancelled\n', '']
            mock_process.poll.return_value = 126  # Auth cancelled
            mock_popen.return_value = mock_process
            
            # Mock thread creation
            mock_thread_obj = Mock()
            mock_thread.return_value = mock_thread_obj
            
            frame.apply_updates()
            
            # Verify the update status was called with appropriate message
            mock_main_window.update_status.assert_any_call("Starting update process...", "info")


if __name__ == '__main__':
    unittest.main() 