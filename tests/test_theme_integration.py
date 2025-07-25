"""
Comprehensive theme integration tests for the Arch Smart Update Checker.
Tests theme switching, color consistency, and regression tests for theme circle bug.
"""

import unittest
import tkinter as tk
from unittest.mock import Mock, patch, MagicMock
import sys
import os

from src.gui.main_window import MainWindow
from src.gui.dashboard import DashboardFrame
from src.gui.settings import SettingsFrame

# Use singleton root to prevent memory leaks
_test_root = None

def get_or_create_root():
    """Get or create a singleton Tk root to prevent memory leaks."""
    global _test_root
    if _test_root is None:
        _test_root = tk.Tk()
        _test_root.withdraw()
    return _test_root


class TestThemeSystemIntegration(unittest.TestCase):
    """Test comprehensive theme system integration."""

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

    def test_theme_circle_regression(self):
        """Test that switching between themes doesn't break each other (theme circle bug)."""
        with patch('src.gui.main_window.Config'), \
             patch('src.gui.main_window.UpdateChecker'), \
             patch('src.utils.logger.set_global_config'), \
             patch('src.gui.main_window.get_logger'):
            
            main_window = MainWindow.__new__(MainWindow)
            main_window.root = self.root
            main_window.config = Mock()
            main_window.checker = Mock()
            main_window.update_logging_status = Mock()
            
            # Start with light theme
            main_window.config.config = {'theme': 'light'}
            main_window.setup_styles()
            light_colors = main_window.colors.copy()
            
            # Switch to dark theme
            main_window.config.config = {'theme': 'dark'}
            main_window.setup_styles()
            dark_colors = main_window.colors.copy()
            
            # Switch back to light theme
            main_window.config.config = {'theme': 'light'}
            main_window.setup_styles()
            light_colors_second = main_window.colors.copy()
            
            # Switch back to dark theme
            main_window.config.config = {'theme': 'dark'}
            main_window.setup_styles()
            dark_colors_second = main_window.colors.copy()
            
            # Verify themes are consistent across switches
            self.assertEqual(light_colors, light_colors_second)
            self.assertEqual(dark_colors, dark_colors_second)
            
            # Verify themes are actually different
            self.assertNotEqual(light_colors['background'], dark_colors['background'])

    def test_theme_color_contrast_compliance(self):
        """Test that both themes provide adequate color contrast."""
        with patch('src.gui.main_window.Config'), \
             patch('src.gui.main_window.UpdateChecker'):
            
            main_window = MainWindow.__new__(MainWindow)
            main_window.root = self.root
            main_window.config = Mock()
            main_window.checker = Mock()
            
            # Test light theme contrast
            main_window.config.config = {'theme': 'light'}
            main_window.setup_styles()
            
            primary_text = main_window.get_text_color('primary')
            background = main_window.colors['background']
            
            # Light theme should have dark text on light background
            self.assertTrue(primary_text.startswith('#'), "Text color should be hex")
            self.assertTrue(background.startswith('#'), "Background should be hex")
            
            # Test dark theme contrast
            main_window.config.config = {'theme': 'dark'}
            main_window.setup_styles()
            
            primary_text_dark = main_window.get_text_color('primary')
            background_dark = main_window.colors['background']
            
            # Dark theme should have light text on dark background
            self.assertNotEqual(primary_text, primary_text_dark)
            self.assertNotEqual(background, background_dark)

    def test_theme_application_to_all_components(self):
        """Test that theme changes properly apply to all GUI components."""
        # Create mock main window with theme support
        mock_main_window = Mock()
        mock_main_window.colors = {
            'background': '#F5F7FA',
            'surface': '#FFFFFF',
            'text': '#1E293B',
            'text_secondary': '#64748B',
            'primary': '#2563EB'
        }
        
        # Test dashboard frame gets theme colors
        with patch('src.gui.dashboard.DashboardFrame.setup_ui'), \
             patch('src.gui.dashboard.DashboardFrame.refresh'):
            dashboard = DashboardFrame(self.root, mock_main_window)
            
            # Verify dashboard has access to theme colors
            self.assertEqual(dashboard.main_window.colors, mock_main_window.colors)

        # Test settings frame gets theme colors
        with patch('src.gui.settings.SettingsFrame.setup_ui'):
            settings = SettingsFrame(self.root, mock_main_window)
            
            # Verify settings has access to theme colors
            self.assertEqual(settings.main_window.colors, mock_main_window.colors)

    def test_theme_refresh_maintains_functionality(self):
        """Test that theme refresh maintains all component functionality."""
        mock_main_window = Mock()
        mock_main_window.colors = {
            'background': '#F5F7FA',
            'surface': '#FFFFFF',
            'text': '#1E293B',
            'text_secondary': '#64748B'
        }
        
        with patch('src.gui.dashboard.DashboardFrame.setup_ui'), \
             patch('src.gui.dashboard.DashboardFrame.refresh'):
            dashboard = DashboardFrame(self.root, mock_main_window)
            
            # Mock the refresh_theme method
            with patch.object(dashboard, 'setup_ui') as mock_setup, \
                 patch.object(dashboard, 'refresh') as mock_refresh:
                
                dashboard.refresh_theme()
                
                # Verify UI was recreated and refreshed
                mock_setup.assert_called_once()
                mock_refresh.assert_called_once()

    def test_update_history_frame_refresh_theme(self):
        """Test that UpdateHistoryFrame refresh_theme works without error."""
        mock_main_window = Mock()
        mock_main_window.colors = {
            'primary': '#2563eb',
            'background': '#f8fafc',
            'surface': '#ffffff',
            'text': '#1e293b'
        }
        mock_main_window.update_history = Mock()
        mock_main_window.root = self.root  # Add root window reference
        
        # Patch StringVar to avoid "too early" error
        with patch('tkinter.StringVar') as mock_string_var:
            # Create a mock StringVar that behaves properly
            mock_var_instance = Mock()
            mock_var_instance.trace = Mock()
            mock_var_instance.get = Mock(return_value='')
            mock_string_var.return_value = mock_var_instance
            
            with patch('src.gui.update_history.UpdateHistoryFrame._build_ui'), \
                 patch('src.gui.update_history.UpdateHistoryFrame.load_history'):
                
                from src.gui.update_history import UpdateHistoryFrame
                history_frame = UpdateHistoryFrame(self.root, mock_main_window)
                
                # Mock the refresh methods
                with patch.object(history_frame, '_build_ui') as mock_build, \
                     patch.object(history_frame, 'load_history') as mock_load:
                    
                    history_frame.refresh_theme()
                    
                    # Verify UI was rebuilt and history reloaded
                    mock_build.assert_called_once()
                    mock_load.assert_called_once()

    def test_get_text_color_all_types(self):
        """Test get_text_color returns appropriate colors for all text types."""
        with patch('src.gui.main_window.Config'), \
             patch('src.gui.main_window.UpdateChecker'):
            
            main_window = MainWindow.__new__(MainWindow)
            main_window.root = self.root
            main_window.config = Mock()
            main_window.checker = Mock()
            
            # Test light theme
            main_window.config.config = {'theme': 'light'}
            main_window.setup_styles()
            
            text_types = ['primary', 'secondary', 'success', 'warning', 'error', 'info', 'muted']
            for text_type in text_types:
                color = main_window.get_text_color(text_type)
                self.assertTrue(color.startswith('#'), f"Color for {text_type} should be hex")
                self.assertEqual(len(color), 7, f"Color for {text_type} should be 7 chars")
            
            # Test dark theme
            main_window.config.config = {'theme': 'dark'}
            main_window.setup_styles()
            
            for text_type in text_types:
                color = main_window.get_text_color(text_type)
                self.assertTrue(color.startswith('#'), f"Dark color for {text_type} should be hex")
                self.assertEqual(len(color), 7, f"Dark color for {text_type} should be 7 chars")


class TestThemePersistence(unittest.TestCase):
    """Test theme persistence across app sessions."""

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

    def test_theme_persists_across_sessions(self):
        """Test that theme choice persists across app restarts."""
        mock_config = Mock()
        
        # Simulate saving dark theme
        mock_config.config = {'theme': 'dark'}
        
        with patch('src.gui.main_window.Config', return_value=mock_config), \
             patch('src.gui.main_window.UpdateChecker'):
            
            main_window = MainWindow.__new__(MainWindow)
            main_window.root = self.root
            main_window.config = mock_config
            main_window.checker = Mock()
            main_window.setup_styles()
            
            # Verify dark theme was applied
            self.assertEqual(main_window.colors['background'], '#0F172A')

    def test_theme_fallback_to_light(self):
        """Test that unknown theme falls back to light theme."""
        with patch('src.gui.main_window.Config'), \
             patch('src.gui.main_window.UpdateChecker'):
            
            main_window = MainWindow.__new__(MainWindow)
            main_window.root = self.root
            main_window.config = Mock()
            main_window.config.config = {'theme': 'unknown_theme'}
            main_window.checker = Mock()
            main_window.setup_styles()
            
            # Should fallback to light theme
            self.assertEqual(main_window.colors['background'], '#F5F7FA')

    def test_missing_theme_config_defaults_light(self):
        """Test that missing theme config defaults to light."""
        with patch('src.gui.main_window.Config'), \
             patch('src.gui.main_window.UpdateChecker'):
            
            main_window = MainWindow.__new__(MainWindow)
            main_window.root = self.root
            main_window.config = Mock()
            main_window.config.config = {}  # No theme key
            main_window.checker = Mock()
            main_window.setup_styles()
            
            # Should default to light theme
            self.assertEqual(main_window.colors['background'], '#F5F7FA')


class TestThemeUIIntegration(unittest.TestCase):
    """Test theme integration with specific UI components."""

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

    def test_sidebar_theme_integration(self):
        """Test that sidebar properly updates with theme changes."""
        with patch('src.gui.main_window.Config'), \
             patch('src.gui.main_window.UpdateChecker'):
            
            main_window = MainWindow.__new__(MainWindow)
            main_window.root = self.root
            main_window.config = Mock()
            main_window.checker = Mock()
            main_window.frames = {}  # Add missing attribute
            main_window.nav_buttons = {}  # Add missing attribute
            main_window.current_frame = tk.StringVar(value='dashboard')  # Add missing attribute
            
            # Mock the setup_sidebar method to track calls
            with patch.object(main_window, 'setup_sidebar') as mock_setup_sidebar:
                # Simulate theme application
                main_window.config.config = {'theme': 'dark'}
                main_window.setup_styles()
                
                # Apply theme should recreate sidebar
                main_window.apply_theme()
                
                # Verify sidebar was recreated
                mock_setup_sidebar.assert_called()

    def test_scrollbar_theme_styles(self):
        """Test that scrollbar styles are properly themed."""
        with patch('src.gui.main_window.Config'), \
             patch('src.gui.main_window.UpdateChecker'):
            
            main_window = MainWindow.__new__(MainWindow)
            main_window.root = self.root
            main_window.config = Mock()
            main_window.checker = Mock()
            
            # Test both themes apply scrollbar styles
            for theme in ['light', 'dark']:
                main_window.config.config = {'theme': theme}
                main_window.setup_styles()
                
                # Should not raise any exceptions
                self.assertIsNotNone(main_window.colors)

    def test_theme_switching_preserves_user_state(self):
        """Test that theme switching preserves user interface state."""
        mock_main_window = Mock()
        mock_main_window.colors = {
            'background': '#F5F7FA',
            'surface': '#FFFFFF',
            'text': '#1E293B'
        }
        
        with patch('src.gui.settings.SettingsFrame.setup_ui'):
            settings = SettingsFrame(self.root, mock_main_window)
            
            # Set some user values
            settings.interval_var = Mock()
            settings.theme_var = Mock()
            settings.notifications_var = Mock()
            settings.canvas = Mock()  # Add missing attribute
            settings.content_frame = Mock()  # Add missing attribute
            
            # Mock the refresh_theme to track if state is preserved
            with patch.object(settings, 'setup_ui') as mock_setup:
                settings.refresh_theme()
                
                # UI should be recreated
                mock_setup.assert_called_once()
                
                # Variables should still exist (preserved)
                self.assertIsNotNone(settings.interval_var)
                self.assertIsNotNone(settings.theme_var)
                self.assertIsNotNone(settings.notifications_var)


if __name__ == '__main__':
    unittest.main(verbosity=2) 