"""
GUI package for Arch Smart Update Checker.
"""

# SPDX-License-Identifier: GPL-3.0-or-later

from .main_window import MainWindow
from .dashboard import DashboardFrame
from .news_browser import NewsBrowserFrame
from .settings import SettingsFrame
from .package_manager import PackageManagerFrame
from .update_history import UpdateHistoryFrame
from .window_mixin import WindowPositionMixin

__all__ = [
    "MainWindow",
    "DashboardFrame",
    "NewsBrowserFrame",
    "SettingsFrame",
    "PackageManagerFrame",
    "UpdateHistoryFrame",
    "WindowPositionMixin",
]
