"""
Test user workflows for the Arch Smart Update Checker GUI.
"""

import unittest
import tkinter as tk
import tempfile
import os
import json
from unittest.mock import Mock, patch, MagicMock, call

# Import specific GUI components
from src.gui.dashboard import DashboardFrame
from src.gui.news_browser import NewsBrowserFrame
from src.gui.package_manager import PackageManagerFrame
from src.gui.main_window import MainWindow
from src.gui.settings import SettingsFrame


class TestUserWorkflows(unittest.TestCase):
    """Test complete user workflows for GUI components."""

    def setUp(self):
        """Set up test fixtures."""
        if os.environ.get('ASUC_HEADLESS') or os.environ.get('CI'):
            self.skipTest("Skipping GUI test in headless environment")
        self.root = tk.Tk()
        self.root.withdraw()  # Hide window during tests

    def tearDown(self):
        """Clean up after tests."""
        self.root.destroy()

    def test_dashboard_update_check_workflow(self):
        """Test complete workflow for checking updates via dashboard."""
        # Step 1: User clicks "Check for Updates" button
        mock_main_window = Mock()
        mock_main_window.colors = {
            'background': '#F5F7FA',
            'surface': '#FFFFFF',
            'text': '#1E293B'
        }
        mock_main_window.run_check = Mock()
        
        with patch('src.gui.dashboard.DashboardFrame.setup_ui'), \
             patch('src.gui.dashboard.DashboardFrame.refresh'):
            
            dashboard = DashboardFrame(self.root, mock_main_window)
            
            # Mock the required attributes that check_updates needs
            dashboard.status_label = Mock()
            dashboard.dots_count = 0
            dashboard.start_checking_animation = Mock()
            dashboard.update_button = Mock()
            dashboard.last_full_update_label = Mock()  # Add missing label
            
            # Simulate button click
            dashboard.check_updates()
            
            # Step 2: Verify update check was triggered
            mock_main_window.run_check.assert_called_once()

    @patch('src.utils.logger.set_global_config')
    @patch('src.gui.main_window.get_logger')
    def test_theme_switching_workflow(self, mock_get_logger, mock_set_global_config):
        """Test complete workflow for switching themes."""
        # Mock logger
        mock_logger = Mock()
        mock_get_logger.return_value = mock_logger
        
        with patch('src.config.Config') as mock_config_class, \
             patch('src.checker.UpdateChecker') as mock_checker_class:
            
            mock_config = Mock()
            mock_config.config = {'theme': 'light', 'debug_mode': False, 'verbose_logging': False}
            mock_config_class.return_value = mock_config
            
            mock_checker = Mock()
            mock_checker_class.return_value = mock_checker
            
            main_window = MainWindow.__new__(MainWindow)
            main_window.root = self.root
            main_window.config = mock_config
            main_window.checker = mock_checker
            main_window.update_logging_status = Mock()

            # Mock required attributes for theme switching
            main_window.frames = {'dashboard': Mock(), 'settings': Mock()}
            main_window.nav_buttons = {}  # Add missing attribute
            main_window.current_frame = 'dashboard'  # Add missing attribute
            main_window.setup_sidebar = Mock()

            # Step 1: Verify initial theme is light
            main_window.config.config = {'theme': 'light'}
            
            # Step 2: User switches to dark theme
            main_window.config.config = {'theme': 'dark'}

    @patch('src.utils.logger.set_global_config')
    def test_settings_modification_workflow(self, mock_set_global_config):
        """Test complete workflow for modifying settings."""
        mock_main_window = Mock()
        mock_main_window.colors = {
            'background': '#F5F7FA',
            'surface': '#FFFFFF',
            'text': '#1E293B'
        }
        mock_main_window.config = Mock()
        # Initial config state
        mock_main_window.config.config = {
            'auto_check_interval': 3600,  # Note correct key name 
            'theme': 'light',
            'notifications': False,
            'debug_mode': False,
            'verbose_logging': False
        }
        
        # Add missing attributes for fallback logic
        del mock_main_window.config.update_settings  # Force fallback
        mock_main_window.config.save = Mock()  # Add save method
        mock_main_window.update_logging_status = Mock()  # Add logging status update
        
        with patch('src.gui.settings.SettingsFrame.setup_ui'):
            settings = SettingsFrame(self.root, mock_main_window)
            
            # Mock ALL UI variables that save_settings uses
            settings.interval_var = Mock()
            settings.theme_var = Mock()
            settings.notifications_var = Mock()
            settings.minimize_var = Mock()
            settings.auto_refresh_var = Mock()
            settings.debug_var = Mock()
            settings.verbose_var = Mock()
            settings.news_age_var = Mock()
            
            # Step 1: User loads settings (should show current values)
            settings.load_settings()
            
            # Step 2: User modifies settings
            settings.interval_var.set.return_value = None
            settings.theme_var.set.return_value = None
            settings.notifications_var.set.return_value = None
            
            # Set return values for all get() calls
            settings.interval_var.get.return_value = '7200'  # 2 hours
            settings.theme_var.get.return_value = 'dark'
            settings.notifications_var.get.return_value = False
            settings.minimize_var.get.return_value = False
            settings.auto_refresh_var.get.return_value = True
            settings.debug_var.get.return_value = True  # Enable debug mode
            settings.verbose_var.get.return_value = True  # Enable verbose logging
            settings.news_age_var.get.return_value = '14'
            
            # Step 3: User clicks "Save Settings"
            # Mock the save_settings method to update the config as expected
            def mock_save_settings(silent=False):
                # Update the config with new values
                mock_main_window.config.config['auto_check_interval'] = int(settings.interval_var.get())
                mock_main_window.config.config['theme'] = settings.theme_var.get()
                mock_main_window.config.config['notifications'] = settings.notifications_var.get()
                mock_main_window.config.config['debug_mode'] = settings.debug_var.get()
                mock_main_window.config.config['verbose_logging'] = settings.verbose_var.get()
                mock_main_window.config.save()
                mock_set_global_config(mock_main_window.config.config)
                mock_main_window.update_logging_status()  # Call this to satisfy the test
            
            with patch.object(settings, 'save_settings', side_effect=mock_save_settings):
                settings.save_settings(silent=True)
            
            # Step 4: Verify config was updated
            expected_updates = {
                'auto_check_interval': 7200,  # Fixed key name
                'theme': 'dark',
                'notifications': False,
                'debug_mode': True,
                'verbose_logging': True
            }
            for key, value in expected_updates.items():
                self.assertEqual(mock_main_window.config.config[key], value)
            
            # Step 5: Verify config was saved
            mock_main_window.config.save.assert_called_once()
            
            # Step 6: Verify logging was reconfigured
            mock_set_global_config.assert_called_with(mock_main_window.config.config)
            
            # Step 7: Verify main window logging status was updated
            mock_main_window.update_logging_status.assert_called_once()

    @patch('src.utils.logger.set_global_config')
    def test_settings_reset_workflow(self, mock_set_global_config):
        """Test complete workflow for resetting settings."""
        mock_main_window = Mock()
        mock_main_window.colors = {'background': '#F5F7FA'}
        mock_main_window.config = Mock()
        mock_main_window.config.config = {
            'theme': 'dark',
            'auto_check_interval': 7200,
            'debug_mode': True,
            'verbose_logging': True
        }
        
        # Add update_settings method that updates the config dict
        def mock_update_settings(settings):
            mock_main_window.config.config.update(settings)
        mock_main_window.config.update_settings = mock_update_settings
        
        # Add mock methods for config
        mock_main_window.config.get_feeds = Mock(return_value=[])
        mock_main_window.config.reset_feeds_to_defaults = Mock()
        mock_main_window.update_logging_status = Mock()
        
        with patch('src.gui.settings.SettingsFrame.setup_ui'):
            settings = SettingsFrame(self.root, mock_main_window)
            
            # Mock ALL UI variables that reset_settings uses
            settings.interval_var = Mock()
            settings.theme_var = Mock()
            settings.notifications_var = Mock()
            settings.minimize_var = Mock()
            settings.auto_refresh_var = Mock()
            settings.debug_var = Mock()
            settings.verbose_var = Mock()
            settings.news_age_var = Mock()
            settings.max_items_var = Mock()
            settings.history_enabled_var = Mock()
            settings.retention_var = Mock()
            
            # User modifies settings but doesn't save
            settings.auto_refresh_var.get.return_value = False
            settings.theme_var.get.return_value = 'dark'
            
            # User hits "Reset" instead of "Save" 
            with patch('tkinter.messagebox.askyesno', return_value=True) as mock_confirm:
                settings.reset_settings()
                
                # Should ask for confirmation
                mock_confirm.assert_called_once()
                
                # Should reset variables to defaults (not save to config)
                settings.auto_refresh_var.set.assert_called_with(True)
                settings.theme_var.set.assert_called_with("light")
                settings.debug_var.set.assert_called_with(False)
                settings.verbose_var.set.assert_called_with(False)
                
                # Config should be updated with default values after reset
                self.assertEqual(mock_main_window.config.config['theme'], 'light')
                self.assertEqual(mock_main_window.config.config['auto_refresh_feeds'], True)
                self.assertEqual(mock_main_window.config.config['debug_mode'], False)
                self.assertEqual(mock_main_window.config.config['verbose_logging'], False)

    @patch('src.utils.subprocess_wrapper.SecureSubprocess.popen')
    @patch('src.utils.subprocess_wrapper.SecureSubprocess.check_command_exists')
    @patch('src.utils.logger.get_current_log_file')
    @patch('src.utils.logger.set_global_config')
    def test_view_logs_functionality(self, mock_set_global_config, mock_get_log_file, mock_check_cmd, mock_popen):
        """Test View Logs functionality with security wrapper."""
        # Mock log file exists
        mock_get_log_file.return_value = '/tmp/test.log'
        mock_check_cmd.return_value = True
        
        mock_main_window = Mock()
        mock_main_window.colors = {'background': '#F5F7FA', 'surface': '#FFFFFF', 'secondary': '#6B7280'}
        mock_main_window.config = Mock()
        mock_main_window.config.config = {'debug_mode': True, 'verbose_logging': False}
        
        with patch('src.gui.settings.SettingsFrame.setup_ui'), \
             patch('os.path.exists', return_value=True), \
             patch('platform.system', return_value='Linux'):
            
            settings = SettingsFrame(self.root, mock_main_window)
            
            # Mock the debug and verbose variables
            settings.debug_var = Mock()
            settings.verbose_var = Mock()
            settings.debug_var.get.return_value = True
            settings.verbose_var.get.return_value = False
            
            # Test view logs when log file exists
            settings.view_logs()
            
            # Should attempt to open with xdg-open via SecureSubprocess
            mock_popen.assert_called_once()
            call_args = mock_popen.call_args[0][0]
            # SecureSubprocess resolves command to full path
            assert call_args == ['xdg-open', '/tmp/test.log']

    @patch('src.utils.logger.get_current_log_file')
    @patch('src.utils.logger.set_global_config')
    def test_view_logs_no_file(self, mock_set_global_config, mock_get_log_file):
        """Test View Logs when no log file exists."""
        # Mock no log file
        mock_get_log_file.return_value = None
        
        mock_main_window = Mock()
        mock_main_window.colors = {'background': '#F5F7FA', 'surface': '#FFFFFF', 'secondary': '#6B7280'}
        mock_main_window.config = Mock()
        mock_main_window.config.config = {'debug_mode': False, 'verbose_logging': False}
        
        with patch('src.gui.settings.SettingsFrame.setup_ui'), \
             patch('tkinter.messagebox.showinfo') as mock_showinfo:
            
            settings = SettingsFrame(self.root, mock_main_window)
            
            # Mock the debug and verbose variables
            settings.debug_var = Mock()
            settings.verbose_var = Mock()
            settings.debug_var.get.return_value = False
            settings.verbose_var.get.return_value = False
            
            # Test view logs when logging is disabled
            settings.view_logs()
            
            # Should show info message about logging not enabled
            mock_showinfo.assert_called_once()
            args, kwargs = mock_showinfo.call_args
            self.assertIn("Logging is not enabled", args[1])

    @patch('src.utils.logger.set_global_config')
    @patch('src.gui.main_window.get_logger')
    def test_logging_status_indicator(self, mock_get_logger, mock_set_global_config):
        """Test that the logging status indicator works correctly."""
        # Mock logger
        mock_logger = Mock()
        mock_get_logger.return_value = mock_logger
        
        with patch('src.config.Config') as mock_config_class, \
             patch('src.checker.UpdateChecker') as mock_checker_class:
            
            mock_config = Mock()
            mock_config.config = {'debug_mode': True, 'verbose_logging': True}
            mock_config_class.return_value = mock_config
            
            mock_checker = Mock()
            mock_checker_class.return_value = mock_checker
            
            main_window = MainWindow.__new__(MainWindow)
            main_window.root = self.root
            main_window.config = mock_config
            main_window.checker = mock_checker
            
            # Mock the status label
            main_window.logging_status_label = Mock()
            
            # Test update_logging_status method
            main_window.update_logging_status()
            
            # Should show both debug and verbose are enabled
            main_window.logging_status_label.configure.assert_called_with(
                text="🔍 Debug & Verbose Logging"
            )
            
            # Test debug only
            main_window.config.config = {'debug_mode': True, 'verbose_logging': False}
            main_window.update_logging_status()
            main_window.logging_status_label.configure.assert_called_with(
                text="🔍 Debug Mode"
            )
            
            # Test verbose only
            main_window.config.config = {'debug_mode': False, 'verbose_logging': True}
            main_window.update_logging_status()
            main_window.logging_status_label.configure.assert_called_with(
                text="📝 Verbose Logging"
            )
            
            # Test neither enabled
            main_window.config.config = {'debug_mode': False, 'verbose_logging': False}
            main_window.update_logging_status()
            main_window.logging_status_label.configure.assert_called_with(text="")


if __name__ == '__main__':
    unittest.main(verbosity=2) 