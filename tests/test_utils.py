"""
Test utilities for Arch Smart Update Checker tests.
Provides common patches and helpers for testing with the new logging functionality.
"""

from unittest.mock import Mock, patch
from contextlib import contextmanager


@contextmanager
def patch_main_window_creation():
    """Context manager to patch MainWindow creation with logging support."""
    with patch('src.gui.main_window.Config') as mock_config_class, \
         patch('src.gui.main_window.UpdateChecker') as mock_checker_class, \
         patch('src.utils.logger.set_global_config') as mock_set_global_config, \
         patch('src.gui.main_window.get_logger') as mock_get_logger:
        
        # Mock logger
        mock_logger = Mock()
        mock_get_logger.return_value = mock_logger
        
        # Provide the mocks to the caller
        yield {
            'config_class': mock_config_class,
            'checker_class': mock_checker_class,
            'set_global_config': mock_set_global_config,
            'get_logger': mock_get_logger,
            'logger': mock_logger
        }


def create_mock_main_window(root_widget=None):
    """Create a mock main window with all necessary attributes for testing."""
    mock_main_window = Mock()
    mock_main_window.root = root_widget
    mock_main_window.colors = {
        'background': '#F5F7FA',
        'surface': '#FFFFFF',
        'text': '#1E293B',
        'text_secondary': '#64748B',
        'primary': '#2563EB',
        'secondary': '#6B7280',
        'success': '#10B981',
        'warning': '#F59E0B',
        'error': '#EF4444'
    }
    
    # Mock config with logging settings
    mock_main_window.config = Mock()
    mock_main_window.config.config = {
        'theme': 'light',
        'debug_mode': False,
        'verbose_logging': False,
        'auto_check_interval': 60,
        'notifications': True,
        'start_minimized': False,
        'auto_refresh_feeds': True,
        'max_news_age_days': 14
    }
    mock_main_window.config.get_feeds = Mock(return_value=[])
    mock_main_window.config.save = Mock()
    
    # Mock logging status update method
    mock_main_window.update_logging_status = Mock()
    
    # Mock other common methods
    mock_main_window.run_check = Mock()
    mock_main_window.update_status = Mock()
    mock_main_window.apply_theme = Mock()
    
    return mock_main_window


def patch_settings_frame_creation():
    """Context manager to patch SettingsFrame creation with logging support."""
    return patch('src.gui.settings.SettingsFrame.setup_ui')


def create_mock_settings_vars():
    """Create mock variables for settings frame testing."""
    vars_dict = {}
    var_names = [
        'interval_var', 'theme_var', 'notifications_var', 'minimize_var',
        'auto_refresh_var', 'debug_var', 'verbose_var',
        'news_age_var'
    ]
    
    for name in var_names:
        mock_var = Mock()
        mock_var.get.return_value = None
        mock_var.set.return_value = None
        vars_dict[name] = mock_var
    
    return vars_dict 