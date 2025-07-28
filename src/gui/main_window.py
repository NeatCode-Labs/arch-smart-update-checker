"""
Main window for the Arch Smart Update Checker GUI application.
"""

# SPDX-License-Identifier: GPL-3.0-or-later

import tkinter as tk
from tkinter import ttk, messagebox
import threading
from typing import Optional, Dict, Any, List, Set, Callable, Union, Tuple
import time
import subprocess
import re
import webbrowser
import os
import tempfile
import logging
import json
import platform
from pathlib import Path
import importlib.util
import shutil

from .dashboard import DashboardFrame
from .news_browser import NewsBrowserFrame
from .package_manager import PackageManagerFrame
from .settings import SettingsFrame
from .update_history import UpdateHistoryFrame
from .secure_callback_manager import create_secure_callback_manager, cleanup_component_callbacks, emergency_callback_cleanup
from .window_mixin import WindowPositionMixin
from .layout_manager import get_layout_manager
from ..config import Config
from ..checker import UpdateChecker
from ..utils.logger import set_global_config, get_logger, log_security_event
from ..utils.update_history import UpdateHistoryManager, UpdateHistoryEntry
from ..utils.thread_manager import ThreadResourceManager
from ..utils.file_monitor import SecureProcessMonitor
from ..utils.window_geometry import get_geometry_manager
from datetime import datetime
from ..utils.subprocess_wrapper import SecureSubprocess
from ..constants import APP_VERSION
from ..news_fetcher import NewsFetcher
from .dimensions import get_dimensions
from ..utils.pacman_runner import PacmanRunner

logger = get_logger(__name__)

# Window size constants - kept for compatibility but will be overridden by layout manager
MIN_WINDOW_WIDTH = 1200   # Minimum width to prevent UI truncation (increased for dashboard cards)
MIN_WINDOW_HEIGHT = 800   # Minimum height to prevent UI truncation (increased for dashboard content)
DEFAULT_WINDOW_WIDTH = 1300
DEFAULT_WINDOW_HEIGHT = 850


class MainWindow(WindowPositionMixin):
    """Main application window with modern design."""

    def __init__(self, config_file: Optional[str] = None) -> None:
        """Initialize the main window."""
        logger.info("MainWindow.__init__ starting")
        self.root = tk.Tk()
        logger.info("Tk root created")
        
        # Check if running from AUR installation
        if os.environ.get('ASUC_AUR_INSTALL') == '1':
            logger.info("Detected AUR installation, forcing layout re-initialization")
        
        # Reset global singletons to ensure proper initialization with Tk root
        from .dimensions import reset_dimensions
        from .layout_manager import reset_layout_manager
        logger.info("Resetting layout manager and dimensions singletons")
        reset_layout_manager()
        reset_dimensions()
        
        # Get dimensions for all components BEFORE setup_window
        from .dimensions import get_dimensions
        self.dims = get_dimensions()
        logger.info(f"Got dimensions instance, window_size (early): {self.dims.window_size}")
        
        self.setup_window()

        # Initialize secure callback manager for memory protection
        self.callback_manager = create_secure_callback_manager("main_window")

        # Initialize configuration and backend components first
        self.config = Config(config_file)

        # Set up logging based on config
        set_global_config(self.config.config)

        self.checker = UpdateChecker(self.config)

        # Initialize update history manager
        retention_days = self.config.get('update_history_retention_days', 365)
        if not isinstance(retention_days, int):
            retention_days = 365
        self.update_history = UpdateHistoryManager(
            retention_days=retention_days
        )

        self.setup_styles()
        self.setup_variables()

        self.setup_components()
        self.setup_bindings()

        # Start with dashboard
        self.show_frame("dashboard")

        # Update status bar to show logging state
        self.update_logging_status()

        # Update database sync time on startup
        if hasattr(self.frames['dashboard'], 'update_database_sync_time'):
            self.frames['dashboard'].update_database_sync_time()

        # Schedule a sidebar width update after window is fully rendered
        secure_update_callback = self.callback_manager.register_callback(
            self._update_sidebar_width,
            sensitive_data=self.config
        )
        self.root.after(100, secure_update_callback)

        # Register cleanup callback for proper resource management
        self.callback_manager.register_cleanup_callback(self._cleanup_resources)

        # Thread safety lock for preventing concurrent update checks
        self._update_check_lock = threading.Lock()
        self._is_checking_simple = False  # Simple boolean instead of tkinter BooleanVar

    def show_issues_dialog(self) -> None:
        """Show dialog with critical package update issues."""
        # Create a popup window
        dialog = tk.Toplevel(self.root)
        dialog.title("Potential Update Issues")
        dialog.configure(bg=self.colors['background'])

        # Use position_window for persistent positioning [[memory:2371890]]
        dialog_w, dialog_h = self.dims.dialog_size
        self.position_window(dialog, width=dialog_w, height=dialog_h, parent=self.root)  # type: ignore[arg-type]

        # Header
        header_frame = ttk.Frame(dialog, style='Content.TFrame')
        header_frame.pack(fill='x', padx=self.dims.pad_large, pady=self.dims.pad_large)

        title_label = tk.Label(header_frame,
                               text="⚠️ Critical Package Updates",
                               font=self.dims.font('Segoe UI', 'large', 'bold'),
                               fg=self.colors['text'],
                               bg=self.colors['background'])
        title_label.pack(anchor='w')

        info_label = tk.Label(header_frame,
                              text="These critical packages have updates available and may require special attention:",
                              font=self.dims.font('Segoe UI', 'normal'),
                              fg=self.colors['text_secondary'],
                              bg=self.colors['background'],
                              wraplength=self.dims.scale(550))
        info_label.pack(anchor='w', pady=(self.dims.pad_medium, 0))

        # Content frame with scrollbar
        content_frame = ttk.Frame(dialog, style='Card.TFrame')
        content_frame.pack(fill='both', expand=True, padx=self.dims.pad_large, pady=(0, self.dims.pad_large))

        # Create text widget for issues
        text_widget = tk.Text(content_frame,
                              font=self.dims.font('Segoe UI', 'normal'),
                              fg=self.colors['text'],
                              bg=self.colors['surface'],
                              wrap='word',
                              height=10,
                              relief='flat',
                              padx=10,
                              pady=10)

        scrollbar = ttk.Scrollbar(content_frame, command=text_widget.yview)
        text_widget.configure(yscrollcommand=scrollbar.set)

        text_widget.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')

        # Get critical packages with updates
        critical_packages = self.config.config.get('critical_packages', [])
        installed_packages = set(self.checker.package_manager.get_installed_package_names())

        issues_found = False
        if hasattr(self.checker, 'last_updates') and self.checker.last_updates:
            # last_updates is a list of package names (strings)
            update_names = set(self.checker.last_updates)

            for pkg_name in critical_packages:
                if pkg_name in update_names and pkg_name in installed_packages:
                    issues_found = True
                    text_widget.insert('end', f"• {pkg_name}\n", 'package')
                    text_widget.insert('end', "  ⚠️ This is a critical system package. Review the ", 'warning')
                    text_widget.insert('end', "Arch Linux News", ('link', pkg_name))
                    text_widget.insert('end', " before updating.\n\n", 'warning')

        if not issues_found:
            text_widget.insert('end', "No critical packages with updates found.\n\n", 'info')
            text_widget.insert('end', "Critical packages being monitored:\n", 'info')
            for pkg in critical_packages:
                status = "✓ Installed" if pkg in installed_packages else "✗ Not installed"
                text_widget.insert('end', f"  • {pkg} - {status}\n", 'info')

        # Configure tags
        text_widget.tag_configure('package', font=('Segoe UI', 12, 'bold'), foreground=self.colors['primary'])
        text_widget.tag_configure('version', foreground=self.colors['text_secondary'])
        text_widget.tag_configure('info', foreground=self.colors['text_secondary'])
        text_widget.tag_configure('warning', foreground=self.colors['warning'])
        text_widget.tag_configure('link', foreground=self.colors['primary'], underline=True)

        # Make links clickable
        text_widget.tag_bind('link', '<Button-1>', 
                           lambda e: SecureSubprocess.open_url_securely("https://archlinux.org/news/", sandbox=True) 
                           or webbrowser.open("https://archlinux.org/news/"))

        # Make read-only
        text_widget.configure(state='disabled')

        # Close button
        close_btn = tk.Button(dialog,
                              text="Close",
                              font=('Segoe UI', 11, 'normal'),
                              fg='white',
                              bg=self.colors['primary'],
                              activebackground=self.colors['primary'],
                              activeforeground='white',
                              bd=0,
                              padx=20,
                              pady=8,
                              cursor='hand2',
                              command=dialog.destroy)
        close_btn.pack(pady=(0, 20))

        # Dialog positioning already handled by position_window [[memory:2371890]]

        # Make dialog modal after it's visible
        dialog.wait_visibility()
        dialog.grab_set()
        dialog.focus_set()

    def show_news_dialog(self) -> None:
        """Show dialog with recent news items."""
        # Create a popup window
        dialog = tk.Toplevel(self.root)
        dialog.title("Recent News Items")
        dialog.configure(bg=self.colors['background'])

        # Use position_window for persistent positioning [[memory:2371890]]
        self.position_window(dialog, width=900, height=600, parent=self.root)  # type: ignore[arg-type]

        # Header
        header_frame = ttk.Frame(dialog, style='Content.TFrame')
        header_frame.pack(fill='x', padx=20, pady=20)

        title_label = tk.Label(header_frame,
                               text="📰 Recent News",
                               font=('Segoe UI', 16, 'bold'),
                               fg=self.colors['text'],
                               bg=self.colors['background'])
        title_label.pack(anchor='w')

        info_label = tk.Label(header_frame,
                              text="Recent news from Arch Linux that may affect your system:",
                              font=('Segoe UI', 11, 'normal'),
                              fg=self.colors['text_secondary'],
                              bg=self.colors['background'])
        info_label.pack(anchor='w', pady=(10, 0))

        # Content frame with scrollbar
        content_frame = ttk.Frame(dialog, style='Card.TFrame')
        content_frame.pack(fill='both', expand=True, padx=20, pady=(0, 20))

        # Create text widget for news
        text_widget = tk.Text(content_frame,
                              font=('Segoe UI', 11, 'normal'),
                              fg=self.colors['text'],
                              bg=self.colors['surface'],
                              wrap='word',
                              relief='flat',
                              padx=10,
                              pady=10)

        scrollbar = ttk.Scrollbar(content_frame, command=text_widget.yview)
        text_widget.configure(yscrollcommand=scrollbar.set)

        text_widget.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')

        # Display news items
        if hasattr(self.checker, 'last_news_items') and self.checker.last_news_items:
            for item in self.checker.last_news_items[:5]:  # Show up to 5 items
                # News items are dictionaries - cast for type safety
                item_dict = item if isinstance(item, dict) else item.__dict__  # type: Dict[str, Any]
                title = item_dict.get('title', 'Untitled')
                link = item_dict.get('link', '#')
                date = item_dict.get('date', 'Unknown date')
                content = item_dict.get('content', '')

                text_widget.insert('end', f"{title}\n", 'title')
                text_widget.insert('end', f"Date: {date}\n", 'date')
                text_widget.insert('end', link, ('link', link))
                text_widget.insert('end', "\n\n", 'normal')

                # Show full content
                if content:
                    # Show complete content with proper formatting
                    text_widget.insert('end', content.strip(), 'content')
                    text_widget.insert('end', "\n\n", 'normal')

                text_widget.insert('end', "-" * 40 + "\n\n", 'separator')
        else:
            text_widget.insert('end', "No recent news items available.\n", 'info')

        # Configure tags
        text_widget.tag_configure('title', font=('Segoe UI', 14, 'bold'),
                                  foreground=self.colors['primary'])
        text_widget.tag_configure('date', font=('Segoe UI', 10, 'normal'),
                                  foreground=self.colors['text_secondary'])
        text_widget.tag_configure('content', font=('Segoe UI', 11, 'normal'))
        text_widget.tag_configure('info', font=('Segoe UI', 11, 'italic'),
                                  foreground=self.colors['text_secondary'])
        text_widget.tag_configure('link', foreground=self.colors['primary'],
                                  underline=True)
        text_widget.tag_configure('separator', foreground=self.colors['text_secondary'])

        # Import webbrowser at the top of the function if not already imported
        import webbrowser

        # Function to handle link clicks with secure callback management
        def on_link_click(event):
            # Get all tags at the clicked position
            tags = text_widget.tag_names(text_widget.index(f"@{event.x},{event.y}"))
            for tag in tags:
                if isinstance(tag, tuple) and tag[0] == 'link':
                    # Use secure URL opening with sandboxing
                    if not SecureSubprocess.open_url_securely(tag[1], sandbox=True):
                        # Fallback to webbrowser if secure method fails
                        webbrowser.open(tag[1])
                    return "break"  # Prevent text selection

        # Register secure link click handler
        secure_link_callback = self.callback_manager.register_callback(
            on_link_click,
            sensitive_data=None  # URLs are not sensitive in this context
        )
        text_widget.bind("<Button-1>", secure_link_callback)

        # Make read-only but keep link clicks working
        text_widget.bind('<Key>', lambda e: 'break')  # Prevent typing
        text_widget.bind('<Button-2>', lambda e: 'break')  # Prevent middle-click paste

        # Button frame
        button_frame = ttk.Frame(dialog, style='Content.TFrame')
        button_frame.pack(fill='x', padx=20, pady=(0, 20))

        # View in browser button
        browser_btn = tk.Button(button_frame,
                                text="View News Browser",
                                font=('Segoe UI', 11, 'normal'),
                                fg=self.colors['text'],
                                bg=self.colors['surface'],
                                activebackground=self.colors['primary_hover'],
                                activeforeground=self.colors['text'],
                                bd=1,
                                relief='solid',
                                padx=15,
                                pady=6,
                                cursor='hand2',
                                command=lambda: self._close_dialog_and_show_news(dialog))
        browser_btn.pack(side='left', padx=(0, 10))

        # Close button
        close_btn = tk.Button(button_frame,
                              text="Close",
                              font=('Segoe UI', 11, 'normal'),
                              fg='white',
                              bg=self.colors['primary'],
                              activebackground=self.colors['primary'],
                              activeforeground='white',
                              bd=0,
                              padx=20,
                              pady=8,
                              cursor='hand2',
                              command=dialog.destroy)
        close_btn.pack(side='right')

        # Dialog positioning already handled by position_window [[memory:2371890]]

        # Make dialog modal after it's visible
        dialog.wait_visibility()
        dialog.grab_set()
        dialog.focus_set()

    def setup_window(self) -> None:
        """Setup the main window properties with adaptive size."""
        from ..constants import get_config_dir

        logger.info("setup_window starting")
        self.root.title(f"Arch Smart Update Checker v{APP_VERSION}")

        # Initialize layout manager first
        self.layout_manager = get_layout_manager()
        logger.info("Got layout manager instance")

        # Check if screen is supported
        logger.info("Initializing layout manager for screen")
        if not self.layout_manager.initialize_for_screen(self.root):
            # Show error for unsupported screen size
            messagebox.showerror(
                "Screen Size Not Supported",
                "Your screen is too small for this application.\n\n"
                "Minimum required: 12.5-inch diagonal with 1366×768 resolution.\n\n"
                "The application will now exit."
            )
            self.root.destroy()
            import sys
            sys.exit(1)

        # Get dimensions from layout manager after initialization
        self.dimensions = self.layout_manager.get_dimensions()
        width, height = self.layout_manager.get_window_size()
        logger.info(f"Layout manager window size: {width}x{height}")
        
        # Now refresh the dimensions instance to get updated values
        self.dims.refresh()
        logger.info(f"Dimensions refreshed, window_size: {self.dims.window_size}")
        
        # Verify dimensions are consistent
        window_width, window_height = self.dims.window_size
        if (window_width, window_height) != (width, height):
            logger.warning(f"Dimension mismatch: layout_manager={width}x{height}, dims={window_width}x{window_height}")
            # Use layout manager dimensions as they are authoritative
            window_width, window_height = width, height
        
        # Set minimum window size based on detected screen dimensions
        window_min_width = min(window_width - 50, window_width)
        window_min_height = min(window_height - 50, window_height)
        self.root.minsize(window_min_width, window_min_height)

        # Get screen dimensions
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()

        # Ensure window fits on screen with some margin
        margin = 50  # pixels from edge
        max_width = screen_width - (2 * margin)
        max_height = screen_height - (2 * margin)

        # Adjust if window is too large
        if width > max_width:
            width = max_width
            logger.warning(f"Window width adjusted to fit screen: {width}")
        if height > max_height:
            height = max_height
            logger.warning(f"Window height adjusted to fit screen: {height}")

        # Initialize geometry manager
        self.geometry_manager = get_geometry_manager()

        # Set adaptive window size - no resizing allowed
        self.root.geometry(f"{width}x{height}")
        self.root.resizable(False, False)

        # Store fixed size
        self.min_width = width
        self.min_height = height

        # Calculate dynamic initial position
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()

        # Try to restore previous position from new system
        restored_geometry = self.geometry_manager.get_geometry("main_window")

        if restored_geometry:
            logger.debug(f"Found saved window geometry: {restored_geometry}")
            # Validate the restored geometry
            parsed = self.geometry_manager.parse_geometry(restored_geometry)
            if parsed:
                w, h, x, y = parsed
                logger.debug(f"Parsed geometry: width={w}, height={h}, x={x}, y={y}")
                # IMPORTANT: Always use adaptive size, NEVER use saved size
                w = width
                h = height
                logger.info(f"Overriding saved size {parsed[0]}x{parsed[1]} with adaptive size {w}x{h}")
                # Validate position is still on screen
                original_x, original_y = x, y
                x, y = self.geometry_manager.validate_position(x, y, w, h, screen_width, screen_height, width, height)
                if x != original_x or y != original_y:
                    logger.debug(f"Position adjusted from ({original_x}, {original_y}) to ({x}, {y})")
                self.root.geometry(f"{w}x{h}+{x}+{y}")
                logger.info(f"Restored window position to {x}+{y} with adaptive size {w}x{h}")
                # Force window manager to respect our position
                self.root.update()
                self.root.wm_geometry(f"+{x}+{y}")  # Set position again after update
            else:
                logger.warning(f"Failed to parse saved geometry: {restored_geometry}")
                # Fallback to centering
                x = (screen_width // 2) - (width // 2)
                y = (screen_height // 2) - (height // 2)
                self.root.geometry(f"{width}x{height}+{x}+{y}")
        else:
            # Check for legacy geometry file
            self.geometry_file = get_config_dir() / "last_window_size"
            legacy_geometry = self._load_window_geometry()

            if legacy_geometry:
                # Parse legacy geometry but use fixed size
                parsed = self.geometry_manager.parse_geometry(legacy_geometry)
                if parsed:
                    w, h, x, y = parsed
                    w = width
                    h = height
                    self.root.geometry(f"{w}x{h}+{x}+{y}")
                    # Save corrected geometry to new system
                    self.geometry_manager.save_geometry("main_window", f"{w}x{h}+{x}+{y}")
                else:
                    self.root.geometry(legacy_geometry)
                    # Save to new system
                    self.geometry_manager.save_geometry("main_window", legacy_geometry)
                # Optionally remove legacy file
                try:
                    self.geometry_file.unlink()
                except (OSError, FileNotFoundError):
                    pass
            else:
                # No saved geometry - center the window
                x = (screen_width // 2) - (width // 2)
                y = (screen_height // 2) - (height // 2)
                logger.debug(f"Centering calculation: screen={screen_width}x{screen_height}, window={width}x{height}")
                self.root.geometry(f"{width}x{height}+{x}+{y}")
                logger.info(f"No saved window position found, centering at {x}+{y}")

        # DPI scaling no longer needed for fixed window size

        # Set window icon if available
        try:
            # Use a proper icon path relative to the module
            icon_path = os.path.join(os.path.dirname(__file__), '..', '..', 'screenshots', 'icon.png')
            if os.path.exists(icon_path):
                self.root.iconbitmap(icon_path)
        except tk.TclError:
            # Icon loading failed, continue without icon
            pass

    def _load_window_geometry(self) -> Optional[str]:
        """Load saved window geometry from file."""
        try:
            if self.geometry_file.exists():
                with open(self.geometry_file, 'r') as f:
                    geometry = f.read().strip()
                    # Validate geometry string format
                    if 'x' in geometry and '+' in geometry:
                        return geometry
        except Exception as e:
            logger.warning(f"Failed to load window geometry: {e}")
        return None

    def _save_window_geometry(self) -> None:
        """Save current window geometry to file."""
        try:
            # Ensure config directory exists
            self.geometry_file.parent.mkdir(parents=True, exist_ok=True)

            geometry = self.root.winfo_geometry()
            with open(self.geometry_file, 'w') as f:
                f.write(geometry)

            logger.debug(f"Saved window geometry: {geometry}")
        except Exception as e:
            logger.warning(f"Failed to save window geometry: {e}")

    def setup_styles(self) -> None:
        """Setup color schemes and ttk styles."""
        # Modern color schemes with better contrast and visual hierarchy
        self.color_schemes = {
            'light': {
                'background': '#F5F7FA',
                'surface': '#FFFFFF',
                'primary': '#2563EB',      # Modern blue
                'primary_hover': '#1D4ED8',  # Darker blue
                'secondary': '#64748B',     # Slate gray
                'accent': '#06B6D4',        # Cyan
                'text': '#1E293B',          # Dark slate
                'text_secondary': '#64748B',  # Medium slate
                'border': '#E2E8F0',        # Light gray border
                'success': '#10B981',       # Emerald
                'warning': '#F59E0B',       # Amber
                'error': '#EF4444',         # Red
                'info': '#3B82F6'           # Blue
            },
            'dark': {
                'background': '#0F172A',    # Dark navy
                'surface': '#1E293B',       # Lighter navy
                'primary': '#3B82F6',       # Bright blue
                'primary_hover': '#2563EB',  # Lighter blue
                'secondary': '#64748B',     # Slate
                'accent': '#14B8A6',        # Teal
                'text': '#F1F5F9',          # Light gray
                'text_secondary': '#94A3B8',  # Medium gray
                'border': '#334155',        # Dark border
                'success': '#10B981',       # Emerald
                'warning': '#F59E0B',       # Amber
                'error': '#EF4444',         # Red
                'info': '#3B82F6'           # Blue
            }
        }

        # Set initial colors based on config
        theme = self.config.config.get('theme', 'light')
        self.colors = self.color_schemes.get(theme, self.color_schemes['light'])

        # Configure ttk styles with modern design
        style = ttk.Style()

        # Main frame style
        style.configure('Main.TFrame',
                        background=self.colors['background'],
                        relief='flat',
                        borderwidth=0)

        # Content frame style
        style.configure('Content.TFrame',
                        background=self.colors['background'],
                        relief='flat',
                        borderwidth=0)

        # Card frame style with subtle elevation
        style.configure('Card.TFrame',
                        background=self.colors['surface'],
                        relief='flat',
                        borderwidth=0)

        # Treeview styling
        style.configure('Treeview',
                        background=self.colors['surface'],
                        foreground=self.colors['text'],
                        fieldbackground=self.colors['surface'],
                        borderwidth=0)

        style.configure('Treeview.Heading',
                        background=self.colors['surface'],
                        foreground=self.colors['text'],
                        borderwidth=0)

        style.map('Treeview',
                  background=[('selected', self.colors['primary'])],
                  foreground=[('selected', 'white')])

        style.map('Treeview.Heading',
                  background=[('active', self.colors['primary'])],
                  foreground=[('active', 'white')])

        # Modern scrollbar styling
        style.configure('Vertical.TScrollbar',
                        background=self.colors['surface'],
                        troughcolor=self.colors['background'],
                        bordercolor=self.colors['surface'],
                        arrowcolor=self.colors['text_secondary'],
                        darkcolor=self.colors['surface'],
                        lightcolor=self.colors['surface'])

        style.map('Vertical.TScrollbar',
                  background=[('active', self.colors['border']),
                              ('pressed', self.colors['primary'])])

        # Configure scrollbar size
        style.configure('Vertical.TScrollbar', width=12)

        # Handle font scaling based on settings
        font_scale = self.config.config.get('font_size', 'medium')
        self.apply_font_size(font_scale)

    def setup_variables(self) -> None:
        """Setup application variables."""
        self.current_frame = tk.StringVar(value="dashboard")
        self.status_text = tk.StringVar(value="Ready")
        self.is_checking = tk.BooleanVar(value=False)

    def setup_components(self) -> None:
        """Setup UI components."""
        # Main container with modern layout
        self.main_frame = ttk.Frame(self.root, style='Main.TFrame')
        self.main_frame.pack(fill='both', expand=True)

        # Sidebar with fixed width
        self.sidebar = tk.Frame(self.main_frame, bg=self.colors['surface'])
        self.sidebar.pack(side='left', fill='y')
        self.sidebar.pack_propagate(False)

        # Set initial sidebar width
        self._update_sidebar_width()

        # Content area
        self.content_frame = ttk.Frame(self.main_frame, style='Content.TFrame')
        self.content_frame.pack(side='right', fill='both', expand=True)

        # Create frames lazily to conserve resources
        # Use batch mode to prevent config saves during initialization
        if hasattr(self.config, 'batch_update'):
            with self.config.batch_update():
                self.frames = {
                    'dashboard': DashboardFrame(self.content_frame, self),
                    'news': ttk.Frame(self.content_frame, style='Content.TFrame'),
                    'packages': PackageManagerFrame(self.content_frame, self),
                    'history': UpdateHistoryFrame(self.content_frame, self),
                    'settings': SettingsFrame(self.content_frame, self)
                }
        else:
            self.frames = {
                'dashboard': DashboardFrame(self.content_frame, self),
                'news': ttk.Frame(self.content_frame, style='Content.TFrame'),
                'packages': PackageManagerFrame(self.content_frame, self),
                'history': UpdateHistoryFrame(self.content_frame, self),
                'settings': SettingsFrame(self.content_frame, self)
            }

        # Setup sidebar navigation
        self.setup_sidebar()

    def setup_sidebar(self) -> None:
        """Setup the sidebar navigation with modern design."""
        # Clear existing widgets to avoid duplicates
        for child in self.sidebar.winfo_children():
            child.destroy()

        # Update sidebar background with current theme
        self.sidebar.configure(bg=self.colors['surface'])

        # App branding area - ensure minimum height
        brand_height = max(90, self.dims.scale(80))
        brand_frame = tk.Frame(self.sidebar, bg=self.colors['primary'], height=brand_height)
        brand_frame.pack(fill='x')
        brand_frame.pack_propagate(False)

        brand_content = tk.Frame(brand_frame, bg=self.colors['primary'])
        brand_content.pack(expand=True)

        app_icon = tk.Label(brand_content,
                            text="🔄",
                            font=self.dims.font('Segoe UI', size_name='large'),
                            fg='white',
                            bg=self.colors['primary'])
        app_icon.pack()

        app_name = tk.Label(brand_content,
                            text="Arch Smart Update Checker",
                            font=self.dims.font('Segoe UI', 'small', 'bold'),
                            fg='white',
                            bg=self.colors['primary'],
                            wraplength=170)  # Fixed wrap width
        app_name.pack(padx=3)

        # Navigation items with better organization
        nav_frame = tk.Frame(self.sidebar, bg=self.colors['surface'])
        nav_frame.pack(fill='both', expand=True, padx=self.dims.pad_medium, pady=self.dims.pad_large)

        # Navigation buttons with modern design
        nav_items = [
            ('dashboard', '📊', 'Dashboard', 'View system overview'),
            ('packages', '🔧', 'Package Manager', 'Manage packages and critical updates'),
            ('history', '📜', 'Update History', 'Review past updates'),
            ('settings', '🛠️', 'Settings', 'Configure application settings')
        ]

        self.nav_buttons = {}

        for key, icon, label, tooltip in nav_items:
            btn_frame = tk.Frame(nav_frame, bg=self.colors['surface'])
            btn_frame.pack(fill='x', pady=self.dims.pad_small)

            btn = tk.Button(
                btn_frame,
                text=f"{icon}  {label}",
                font=self.dims.font('Segoe UI', 'small'),  # Reduced from normal
                fg=self.colors['text'],
                bg=self.colors['surface'],
                activebackground=self.colors['background'],
                activeforeground=self.colors['primary'],
                bd=0,
                anchor='w',
                padx=10,  # Fixed smaller padding
                pady=8,   # Fixed smaller padding
                cursor='hand2',
                command=lambda k=key: self.show_frame(k)  # type: ignore[misc]
            )
            btn.pack(fill='x')

            # Add hover effect
            btn.bind('<Enter>', lambda e, b=btn: self.on_nav_hover(b, True))  # type: ignore[misc]
            btn.bind('<Leave>', lambda e, b=btn: self.on_nav_hover(b, False))  # type: ignore[misc]

            self.nav_buttons[key] = btn

        # Add separator
        separator = tk.Frame(nav_frame, bg=self.colors['border'], height=1)
        separator.pack(fill='x', pady=self.dims.pad_large)

        # Update Summary (only visible on updates screen)
        self.update_summary_frame = tk.Frame(nav_frame, bg=self.colors['surface'])
        # Don't pack it yet - will be shown/hidden dynamically

        # Summary content with smaller design to fit sidebar
        summary_bg = tk.Frame(self.update_summary_frame, bg=self.colors['background'], relief='ridge', bd=1)
        summary_bg.pack(fill='x', pady=(0, self.dims.pad_large))

        summary_title = tk.Label(summary_bg,
                                 text="Update Summary",
                                 font=self.dims.font('Segoe UI', 'normal', 'bold'),
                                 fg=self.colors['primary'],
                                 bg=self.colors['background'])
        summary_title.pack(pady=(self.dims.pad_medium, self.dims.pad_small))

        # Summary details
        self.sidebar_summary_labels = {}
        summary_items = [
            ('Packages:', '0'),
            ('Download:', '—'),
            ('Disk space:', '—')
        ]

        for label_text, initial_value in summary_items:
            row_frame = tk.Frame(summary_bg, bg=self.colors['background'])
            row_frame.pack(fill='x', padx=self.dims.pad_medium, pady=self.dims.scale(2))

            tk.Label(row_frame,
                     text=label_text,
                     font=self.dims.font('Segoe UI', 'tiny'),
                     fg=self.colors['text_secondary'],
                     bg=self.colors['background'],
                     width=self.dims.scale(10),
                     anchor='w').pack(side='left')

            value_label = tk.Label(row_frame,
                                   text=initial_value,
                                   font=self.dims.font('Segoe UI', 'tiny', 'bold'),
                                   fg=self.colors['text'],
                                   bg=self.colors['background'],
                                   anchor='w')
            value_label.pack(side='left', fill='x', expand=True)

            self.sidebar_summary_labels[label_text] = value_label

        # Add some padding at bottom
        tk.Frame(summary_bg, bg=self.colors['background'], height=self.dims.pad_medium).pack()

        # System info section
        info_frame = tk.Frame(self.sidebar, bg=self.colors['surface'])
        info_frame.pack(fill='x', padx=self.dims.pad_large, pady=(0, self.dims.pad_large))

        # Status area
        self.status_label = tk.Label(
            info_frame,
            textvariable=self.status_text,
            font=self.dims.font('Segoe UI', 'small'),
            fg=self.colors['text_secondary'],
            bg=self.colors['surface'],
            wraplength=self.dims.scale(300),  # Increased to prevent line breaking
            justify='left'  # Ensure multi-line text is left-aligned
        )
        self.status_label.pack(anchor='w')

        # Logging status indicator
        self.logging_status_label = tk.Label(
            info_frame,
            text="",
            font=self.dims.font('Segoe UI', 'tiny', 'italic'),
            fg=self.colors['warning'],
            bg=self.colors['surface']
        )
        self.logging_status_label.pack(anchor='w', pady=(self.dims.pad_small, 0))

        # Version info
        version_label = tk.Label(
            info_frame,
            text=f"Version {APP_VERSION}",
            font=self.dims.font('Segoe UI', 'tiny'),
            fg=self.colors['text_secondary'],
            bg=self.colors['surface']
        )
        version_label.pack(anchor='w', pady=(self.dims.pad_small, 0))

        # License info
        license_label = tk.Label(
            info_frame,
            text="GPL-3.0-or-later",
            font=self.dims.font('Segoe UI', 'tiny'),
            fg=self.colors['text_secondary'],
            bg=self.colors['surface']
        )
        license_label.pack(anchor='w', pady=(self.dims.scale(2), 0))

        # Made by info with line break
        made_by_label = tk.Label(
            info_frame,
            text="Made by NeatCode Labs",
            font=self.dims.font('Segoe UI', 'tiny', 'italic'),
            fg=self.colors['text_secondary'],
            bg=self.colors['surface']
        )
        made_by_label.pack(anchor='w', pady=(8, 0))

    def _update_sidebar_width(self) -> None:
        """Set adaptive sidebar width based on layout."""
        # Ensure sidebar is wide enough for content
        base_width = 210  # Slightly wider for button text
        sidebar_width = max(190, self.dims.scale(base_width))

        # Apply the width
        self.sidebar.configure(width=sidebar_width)

        # Update wraplength for status labels
        if hasattr(self, 'status_label'):
            self.status_label.configure(wraplength=sidebar_width - 30)

    def setup_bindings(self) -> None:
        """Setup event bindings."""
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

        # Bind navigation button hover effects
        for frame_name, btn in self.nav_buttons.items():
            if btn is None:
                continue
            btn.bind('<Enter>', lambda e, b=btn: self.on_nav_hover(b, True))  # type: ignore[misc]
            btn.bind('<Leave>', lambda e, b=btn: self.on_nav_hover(b, False))  # type: ignore[misc]

    def on_nav_hover(self, button: tk.Widget, entering: bool) -> None:
        """Handle navigation button hover effects."""
        if entering:
            button.configure(
                bg=self.colors['background'],
                fg=self.colors['primary']
            )  # type: ignore[call-arg]  # bg keyword arg for button styling
        else:
            # Check if this button is active
            active_frame = getattr(self, 'current_frame', 'dashboard')
            button_frame = None

            # Find which frame this button corresponds to
            for frame_name, btn in self.nav_buttons.items():
                if btn == button:
                    button_frame = frame_name
                    break

            if button_frame == active_frame:
                # Keep active state
                button.configure(
                    bg=self.colors['primary'],
                    fg='white'
                )  # type: ignore[call-arg]  # bg/fg for button styling
            else:
                # Return to normal state
                button.configure(
                    bg=self.colors['surface'],
                    fg=self.colors['text']
                )  # type: ignore[call-arg]  # bg/fg for button styling

    def show_frame(self, frame_name: str) -> None:
        """Show the specified frame and update navigation state."""
        # Store current frame
        self.current_frame.set(frame_name)

        # Update navigation button states
        for name, btn in self.nav_buttons.items():
            if btn:  # Check if button exists
                if name == frame_name:
                    # Active state
                    btn.configure(
                        bg=self.colors['primary'],
                        fg='white'
                    )
                else:
                    # Inactive state
                    btn.configure(
                        bg=self.colors['surface'],
                        fg=self.colors['text']
                    )

        # Show/hide update summary based on frame
        if frame_name == 'updates_news':
            self.update_summary_frame.pack(fill='x', pady=(0, 20))
        else:
            self.update_summary_frame.pack_forget()

        # Hide all frames
        for frame in self.frames.values():
            frame.pack_forget()

        # Show the selected frame
        if frame_name in self.frames:
            self.frames[frame_name].pack(fill='both', expand=True)

            # Call on_frame_shown if the frame has this method
            frame = self.frames[frame_name]
            if hasattr(frame, 'on_frame_shown'):
                frame.on_frame_shown()
            elif hasattr(frame, 'refresh'):
                # Call refresh method if on_frame_shown is not available
                frame.refresh()

            # Update window title
            titles = {
                'dashboard': 'Dashboard',
                'packages': 'Package Manager',
                'news': 'News Browser',
                'settings': 'Settings'
            }
            self.root.title(f"Arch Smart Update Checker - {titles.get(frame_name, frame_name.title())}")

        # Special handling removed for news frame (no longer present)

    def update_status(self, message: str, status_type: str = "info") -> None:
        """Update the status message."""
        self.status_text.set(message)

        # Update status color based on type
        if status_type == "success":
            self.status_label.configure(fg=self.colors['success'])
        elif status_type == "warning":
            self.status_label.configure(fg=self.colors['warning'])
        elif status_type == "error":
            self.status_label.configure(fg=self.colors['error'])
        else:
            self.status_label.configure(fg=self.colors['text_secondary'])

    def run_check(self) -> None:
        """Run the update check in a background thread."""
        # Use instance lock to prevent concurrent update checks
        with self._update_check_lock:
            if self._is_checking_simple:
                logger.debug("Update check already in progress, ignoring request")
                return

            self._is_checking_simple = True
            logger.info("Starting update check")

        # Also set the tkinter variable for UI state
        self.is_checking.set(True)
        self.update_status("Checking for updates...", "info")

        def check_thread():
            try:
                # Sync database first (integrate sync functionality into check)
                def update_sync_status():
                    self.update_status("Syncing package database...", "info")
                self.root.after(0, update_sync_status)
                
                sync_success = False
                try:
                    from ..utils.pacman_runner import PacmanRunner
                    logger.info("Syncing package database before checking for updates")
                    sync_result = PacmanRunner.sync_database(self.config)
                    if sync_result.get('success'):
                        sync_success = True
                        logger.info("Database sync completed successfully")
                        # Update dashboard sync time after successful sync
                        if 'dashboard' in self.frames and hasattr(self.frames['dashboard'], 'update_database_sync_time'):
                            self.root.after(0, self.frames['dashboard'].update_database_sync_time)
                    else:
                        error_msg = sync_result.get('error', 'Unknown error')
                        logger.warning(f"Database sync failed: {error_msg}")
                        
                        # Check if user cancelled authentication
                        if 'cancelled' in error_msg.lower() or 'dismissed' in error_msg.lower() or 'authentication' in error_msg.lower():
                            logger.info("User cancelled authentication, returning to dashboard")
                            self.root.after(0, lambda: self.update_status("Database sync cancelled by user", "info"))
                        else:
                            self.root.after(0, lambda: self.update_status(f"Database sync failed: {error_msg}", "error"))
                except Exception as e:
                    logger.error(f"Failed to sync database: {e}")
                    error_msg = str(e)
                    self.root.after(0, lambda: self.update_status(f"Database sync error: {error_msg}", "error"))
                
                # Only continue with update check if sync was successful
                if not sync_success:
                    logger.info("Skipping update check due to sync failure")
                    return
                
                def update_check_status():
                    self.update_status("Checking for updates...", "info")
                self.root.after(0, update_check_status)
                
                # Clear package manager cache BEFORE checking to free memory
                try:
                    self.checker.package_manager.clear_cache()
                    logger.debug("Cleared package manager cache before update check")
                except Exception as e:
                    logger.warning(f"Failed to clear cache before check: {e}")

                # Clear any cached update data first
                if hasattr(self.checker, 'last_updates'):
                    self.checker.last_updates = []
                if hasattr(self.checker, 'last_update_objects'):
                    self.checker.last_update_objects = {}
                if hasattr(self.checker, 'last_news_items'):
                    self.checker.last_news_items = []

                # Check for updates using package manager
                updates = self.checker.package_manager.check_for_updates()
                update_count = len(updates)

                # Store package names and full update info for GUI display
                self.checker.last_updates = [u.name for u in updates]
                self.checker.last_update_objects = {u.name: u for u in updates}  # Store full objects for version info

                # Get ALL installed packages for news matching
                all_installed_packages = set(self.checker.package_manager.get_installed_package_names())

                # Fetch news for ALL installed packages
                feeds = self.config.get_feeds()
                all_news = self.checker.news_fetcher.fetch_all_feeds_legacy(feeds)

                # Filter out package-type feeds, keep only news feeds
                news_only = [item for item in all_news if item.get('source_type', 'news') != 'package']

                # Find news relevant to packages with updates
                packages_with_updates = set([u.name for u in updates])
                relevant_news = []

                for item in news_only:
                    txt = f"{item.get('title', '')} {item.get('content', '')} {item.get('description', '')}"
                    # Check against ALL installed packages first
                    affected = self.checker.pattern_matcher.find_affected_packages(txt, all_installed_packages)
                    # Then see if any of the affected packages have updates
                    if affected and affected.intersection(packages_with_updates):
                        item['affected_packages'] = affected.intersection(packages_with_updates)
                        relevant_news.append(item)

                # Store news items count for dashboard
                self.checker.last_news_items = relevant_news

                # Update UI in main thread
                self.root.after(0, lambda: self.on_check_complete(update_count, updates, relevant_news))

            except Exception as exc:
                import traceback
                error_msg = f"Error: {str(exc)}"
                logger.error(f"Update check failed: {traceback.format_exc()}")
                self.root.after(0, lambda: self.on_check_error(error_msg))
            finally:
                # Clear package manager caches to free memory
                try:
                    self.checker.package_manager.clear_cache()
                    logger.debug("Cleared package manager cache after update check")
                except Exception as e:
                    logger.warning(f"Failed to clear cache: {e}")

                # Reset both flags
                with self._update_check_lock:
                    self._is_checking_simple = False
                self.root.after(0, lambda: self.is_checking.set(False))

        # Use secure thread management
        from ..utils.thread_manager import create_managed_thread
        import uuid
        thread_id = f"check_thread_{uuid.uuid4().hex[:8]}"

        thread = create_managed_thread(thread_id, check_thread, is_background=True, component_id=thread_id)
        if thread is None:
            self.on_check_error("Unable to start update check: thread limit reached")
            self.is_checking.set(False)
        else:
            thread.start()  # Start the thread!

    def on_check_error(self, error_msg: str) -> None:
        """Handle check error."""
        self.update_status(error_msg, "error")

        # Notify dashboard if it exists
        if 'dashboard' in self.frames and hasattr(self.frames['dashboard'], 'stop_checking_animation'):
            self.frames['dashboard'].stop_checking_animation(error_msg, success=False)

        messagebox.showerror("Update Check Error", error_msg)

    def on_check_complete(self, update_count: int, updates: list, news_items: list) -> None:
        """Handle check completion."""
        if update_count == 0:
            self.update_status("No updates available", "success")
            msg = "Your system is up to date."

            # Notify dashboard
            if 'dashboard' in self.frames and hasattr(self.frames['dashboard'], 'stop_checking_animation'):
                self.frames['dashboard'].stop_checking_animation("System is up to date", success=True)

            messagebox.showinfo("Update Check", msg)
            self.show_frame('dashboard')
        else:
            self.update_status(f"Found {update_count} updates", "warning")

            # Notify dashboard
            if 'dashboard' in self.frames and hasattr(self.frames['dashboard'], 'stop_checking_animation'):
                self.frames['dashboard'].stop_checking_animation(f"Found {update_count} updates", success=True)

            package_names = [u.name for u in updates]
            # Swap in the updates/news frame
            if 'updates_news' in self.frames:
                self.frames['updates_news'].destroy()
            # Pass both package names and full update objects for version info
            self.frames['updates_news'] = UpdatesNewsFrame(self.content_frame, self, package_names, news_items, updates)
            self.show_frame('updates_news')

        # Refresh dashboard
        if hasattr(self.frames['dashboard'], 'refresh'):
            self.frames['dashboard'].refresh()
        # Update stats cards with both updates and news count
        if hasattr(self.frames['dashboard'], 'update_stats_cards'):
            news_count = len(news_items) if news_items else 0
            self.frames['dashboard'].update_stats_cards(update_count, news_count)

    def on_closing(self) -> None:
        """Handle window closing."""
        # This method is kept for compatibility but actual closing is handled by _on_window_close
        # Directly exit the application without additional confirmation
        self.root.destroy()

    def apply_theme(self) -> None:
        """Apply the current theme to all components."""
        theme = self.config.config.get('theme', 'light')
        self.colors = self.color_schemes.get(theme, self.color_schemes['light'])

        # Update window background
        self.root.configure(bg=self.colors['background'])

        # Note: main_frame and content_frame are ttk.Frame widgets that use styles, not bg

        # Update ttk styles
        try:
            style = ttk.Style()

            # Update frame styles
            style.configure('Main.TFrame', background=self.colors['background'])
            style.configure('Content.TFrame', background=self.colors['background'])
            style.configure('Card.TFrame', background=self.colors['surface'])

            # Update Treeview styling
            style.configure('Treeview',
                            background=self.colors['surface'],
                            foreground=self.colors['text'],
                            fieldbackground=self.colors['surface'],
                            borderwidth=0)

            style.configure('Treeview.Heading',
                            background=self.colors['surface'],
                            foreground=self.colors['text'],
                            borderwidth=0)

            style.map('Treeview',
                      background=[('selected', self.colors['primary'])],
                      foreground=[('selected', 'white')])

            style.map('Treeview.Heading',
                      background=[('active', self.colors['primary'])],
                      foreground=[('active', 'white')])

            # Update scrollbar styles
            style.configure('Vertical.TScrollbar',
                            background=self.colors['surface'],
                            troughcolor=self.colors['background'],
                            bordercolor=self.colors['border'],
                            arrowcolor=self.colors['text_secondary'],
                            darkcolor=self.colors['surface'],
                            lightcolor=self.colors['surface'])

            style.map('Vertical.TScrollbar',
                      background=[('active', self.colors['border']),
                                  ('pressed', self.colors['primary'])])
        except Exception:
            pass  # Ignore TTK style errors

        # Recreate sidebar with new colors
        self.setup_sidebar()

        # Update all frames
        for frame_name, frame in self.frames.items():
            try:
                # Try refresh_theme first (if implemented)
                if hasattr(frame, 'refresh_theme'):
                    frame.refresh_theme()
                # Otherwise, recreate the frame to apply new theme
                else:
                    # Store current frame reference
                    old_frame = frame

                    # Create new frame with updated theme
                    if frame_name == 'dashboard':
                        from .dashboard import DashboardFrame
                        self.frames[frame_name] = DashboardFrame(self.content_frame, self)
                    elif frame_name == 'packages':
                        from .package_manager import PackageManagerFrame
                        self.frames[frame_name] = PackageManagerFrame(self.content_frame, self)
                    elif frame_name == 'history':
                        from .update_history import UpdateHistoryFrame
                        self.frames[frame_name] = UpdateHistoryFrame(self.content_frame, self)
                    elif frame_name == 'settings':
                        from .settings import SettingsFrame
                        self.frames[frame_name] = SettingsFrame(self.content_frame, self)
                    elif frame_name == 'news':
                        # News frame might not be initialized yet
                        pass

                    # Destroy old frame
                    old_frame.destroy()

            except Exception as e:
                logger.warning(f"Error refreshing frame {frame_name}: {e}")

        # Force refresh of current frame
        current = getattr(self, 'current_frame', 'dashboard')
        if isinstance(current, str):
            # Force re-initialization of package manager if it's the current frame
            if current == 'packages' and 'packages' in self.frames:
                # The new frame was just created with load_packages() in __init__
                pass  # No need to reload, it's already loading
            self.show_frame(current)
        else:
            self.show_frame('dashboard')

        # Force update
        self.root.update_idletasks()

        # Update logging status after theme change
        self.update_logging_status()

    def apply_font_size(self, size: str) -> None:
        """Scale default Tk fonts to small/medium/large."""
        try:
            import tkinter.font as tkfont
            scaling = {"small": 0.9, "medium": 1.0, "large": 1.2}.get(size, 1.0)
            for fname in tkfont.names():
                f = tkfont.nametofont(fname)
                current = f.cget('size')
                # Ignore symbolic sizes (negative) or zero
                if isinstance(current, int) and current > 0:
                    new_size = max(6, int(current * scaling))
                    f.configure(size=new_size)
        except Exception:
            pass

    def _cleanup_resources(self) -> None:
        """Cleanup resources and sensitive data when window is destroyed."""
        try:
            # Clear sensitive configuration data
            if hasattr(self, 'config') and self.config:
                self.config.clear_sensitive_data()

            # Clear update history manager
            if hasattr(self, 'update_history') and self.update_history:
                self.update_history.shutdown(wait=False)

            # Clear checker references
            if hasattr(self, 'checker'):
                delattr(self, 'checker')

            # Get logger fresh to avoid scope issues during cleanup
            from ..utils.logger import get_logger
            cleanup_logger = get_logger(__name__)
            cleanup_logger.debug("Completed main window resource cleanup")

        except Exception as e:
            # Get logger fresh to avoid scope issues during cleanup
            from ..utils.logger import get_logger
            cleanup_logger = get_logger(__name__)
            cleanup_logger.error(f"Error during main window cleanup: {e}")

    def run(self) -> None:
        """Start the GUI application."""
        try:
            # Register protocol handler for window close
            self.root.protocol("WM_DELETE_WINDOW", self._on_window_close)
            self.root.mainloop()
        finally:
            # Ensure cleanup happens even if mainloop exits unexpectedly
            self._perform_final_cleanup()

    def _on_window_close(self):
        """Handle window close event with secure cleanup."""
        try:
            # Save window position first
            # Get the actual current window position
            self.root.update()  # Force full update to get accurate position
            self.root.update_idletasks()  # Ensure window info is current

            x = self.root.winfo_x()
            y = self.root.winfo_y()
            width = self.root.winfo_width()
            height = self.root.winfo_height()

            # Build geometry string from actual window state
            geometry = f"{width}x{height}+{x}+{y}"
            logger.debug(f"Saving window geometry on close: {geometry}")

            self.geometry_manager.save_geometry("main_window", geometry)

            # Cleanup callback manager
            if hasattr(self, 'callback_manager'):
                self.callback_manager.cleanup_all()

            # Cleanup component callbacks
            cleanup_component_callbacks("main_window")

            # Destroy the window
            self.root.destroy()

        except Exception as e:
            logger.error(f"Error during window close: {e}")
            # Force destroy even if cleanup fails
            try:
                self.root.destroy()
            except BaseException:
                pass

    def _perform_final_cleanup(self):
        """Perform final cleanup of all resources."""
        try:
            # Emergency callback cleanup
            emergency_callback_cleanup()

            # Force garbage collection
            import gc
            gc.collect()

            logger.debug("Completed final cleanup")

        except Exception as e:
            logger.error(f"Error during final cleanup: {e}")

    # ----------------------------------
    # Update dialog
    # ----------------------------------

    def show_update_dialog(self, packages):
        """Display a dialog with package list and related news."""
        dialog = tk.Toplevel(self.root)
        dialog.title("Updates Available")
        dialog.configure(bg=self.colors['background'])

        # Use position_window for persistent positioning [[memory:2371890]]
        self.position_window(dialog, width=900, height=600, parent=self.root)

        # Split panes
        body = ttk.Frame(dialog, style='Content.TFrame')
        body.pack(fill='both', expand=True)
        left = ttk.Frame(body, style='Card.TFrame')
        right = ttk.Frame(body, style='Card.TFrame')
        left.pack(side='left', fill='both', expand=True, padx=10, pady=10)
        right.pack(side='right', fill='both', expand=True, padx=10, pady=10)

        ttk.Label(
            left,
            text="Packages",
            style='Card.TFrame',
            background=self.colors['surface'],
            foreground=self.colors['text']).pack(
            anchor='w')
        pkg_list = tk.Listbox(left, bg=self.colors['surface'], fg=self.colors['text'])
        pkg_list.pack(fill='both', expand=True)
        for p in packages:
            pkg_list.insert(tk.END, p)

        ttk.Label(
            right,
            text="Related News",
            style='Card.TFrame',
            background=self.colors['surface'],
            foreground=self.colors['text']).pack(
            anchor='w')
        news_text = tk.Text(right, wrap='word', bg=self.colors['surface'], fg=self.colors['text'])
        news_text.pack(fill='both', expand=True)
        news_text.insert('1.0', 'Fetching related news...')

        def load_news():
            feeds = self.config.get_feeds()
            all_news = self.checker.news_fetcher.fetch_all_feeds(feeds)
            installed = set(packages)
            relevant = []
            for item in all_news:
                txt = f"{item.get('title', '')} {item.get('content', '')} {item.get('description', '')}"
                affected = self.checker.pattern_matcher.find_affected_packages(txt, installed)
                if affected:
                    relevant.append(item)
            self.root.after(0, lambda: display_news(relevant))

        def display_news(items):
            news_text.config(state='normal')
            news_text.delete('1.0', tk.END)
            if not items:
                news_text.insert('1.0', 'No news related to these updates for your installed packages.')
            else:
                for it in items:
                    title = it.get('title', 'Unknown')
                    date = it.get('published', '')
                    news_text.insert(tk.END, f"{title} ({date})\n\n")
            news_text.config(state='disabled')

        # Use secure thread management instead of direct threading
        import uuid
        thread_id = f"load_news_{uuid.uuid4().hex[:8]}"
        thread = ThreadResourceManager.create_managed_thread(
            thread_id=thread_id,
            target=load_news,
            is_background=True
        )
        if thread:
            thread.start()
        else:
            logger.warning("Could not create thread for news loading - thread limit reached")

        try:
            btn_frame = tk.Frame(dialog, bg='red', bd=4, relief='solid')  # Red border for debug
            btn_frame.pack(side='bottom', fill='x', pady=20, padx=20)

            def apply_updates():
                dialog.destroy()
                # Use secure thread management for critical system operations
                import uuid
                thread_id = f"apply_updates_{uuid.uuid4().hex[:8]}"
                thread = ThreadResourceManager.create_managed_thread(
                    thread_id=thread_id,
                    target=lambda: subprocess.run(["sudo", "pacman", "-Syu"]),
                    is_background=True
                )
                if thread:
                    thread.start()
                else:
                    logger.warning("Could not create thread for system update - thread limit reached")
                    messagebox.showwarning("Thread Limit",
                                           "Cannot start update - thread limit reached. Please try again.")

            apply_btn = tk.Button(
                btn_frame,
                text="Apply Updates",
                bg=self.colors['primary'],
                fg='white',
                font=('Segoe UI', 14, 'bold'),
                activebackground=self.colors['primary_hover'],
                activeforeground='white',
                bd=0,
                padx=30,
                pady=15,
                cursor='hand2',
                command=apply_updates
            )
            apply_btn.pack(side='left', padx=20, pady=10, fill='x', expand=True)

            close_btn = tk.Button(
                btn_frame,
                text="Close",
                font=('Segoe UI', 12, 'normal'),
                command=dialog.destroy
            )
            close_btn.pack(side='right', padx=20, pady=10)
        except Exception:
            pass

    # --------------------
    # Utility
    # --------------------

    def _center_window(self, win, width=None, height=None):
        """Center a toplevel window over the main root before showing it."""
        # Get unique ID for this window based on its title
        window_id = f"dialog_{win.title().replace(' ', '_').lower()}"

        # Withdraw window first to prevent flashing
        win.withdraw()

        # If width/height provided, set geometry
        if width and height:
            win.geometry(f"{width}x{height}")

        # Update to get actual dimensions
        win.update_idletasks()

        # Try to restore saved position
        saved_geometry = self.geometry_manager.get_geometry(window_id)

        if saved_geometry:
            parsed = self.geometry_manager.parse_geometry(saved_geometry)
            if parsed:
                saved_w, saved_h, saved_x, saved_y = parsed
                # Use saved position but allow size override
                if width and height:
                    win.geometry(f"{width}x{height}+{saved_x}+{saved_y}")
                else:
                    win.geometry(saved_geometry)

                # Validate position is still on screen
                win_width = win.winfo_width()
                win_height = win.winfo_height()
                screen_width = win.winfo_screenwidth()
                screen_height = win.winfo_screenheight()

                x, y = self.geometry_manager.validate_position(
                    saved_x, saved_y, win_width, win_height,
                    screen_width, screen_height
                )

                if x != saved_x or y != saved_y:
                    # Position was adjusted, update it
                    win.geometry(f"+{x}+{y}")
            else:
                # Saved geometry is invalid, center window
                self._center_window_default(win)
        else:
            # No saved position, center window
            self._center_window_default(win)

        # Set up position saving on close
        def save_position():
            geometry = win.winfo_geometry()
            self.geometry_manager.save_geometry(window_id, geometry)

        win.protocol("WM_DELETE_WINDOW", lambda: [save_position(), win.destroy()])

        # Show the window
        win.deiconify()

    def _center_window_default(self, win):
        """Center window using default logic."""
        # Calculate center position relative to main window
        main_x = self.root.winfo_x()
        main_y = self.root.winfo_y()
        main_width = self.root.winfo_width()
        main_height = self.root.winfo_height()

        win_width = win.winfo_width()
        win_height = win.winfo_height()

        x = main_x + (main_width - win_width) // 2
        y = main_y + (main_height - win_height) // 2

        # Ensure window doesn't go off screen
        screen_width = win.winfo_screenwidth()
        screen_height = win.winfo_screenheight()

        x = max(0, min(x, screen_width - win_width))
        y = max(0, min(y, screen_height - win_height))

        # Set position
        win.geometry(f"+{x}+{y}")

    def get_text_color(self, text_type='primary'):
        """Get theme-appropriate text color for readability.

        Args:
            text_type: 'primary', 'secondary', 'success', 'warning', 'error', or 'info'

        Returns:
            Color string appropriate for current theme
        """
        theme = self.config.config.get('theme', 'light')

        if theme == 'dark':
            # Dark theme - use light colors for text
            color_map = {
                'primary': '#F1F5F9',      # Light gray
                'secondary': '#94A3B8',    # Medium gray
                'success': '#10B981',      # Emerald (same)
                'warning': '#F59E0B',      # Amber (same)
                'error': '#EF4444',        # Red (same)
                'info': '#60A5FA',         # Light blue
                'muted': '#64748B'         # Muted gray
            }
        else:
            # Light theme - use dark colors for text
            color_map = {
                'primary': '#1E293B',      # Dark slate
                'secondary': '#64748B',    # Medium slate
                'success': '#059669',      # Dark emerald
                'warning': '#D97706',      # Dark amber
                'error': '#DC2626',        # Dark red
                'info': '#2563EB',         # Dark blue
                'muted': '#9CA3AF'         # Muted gray
            }

        return color_map.get(text_type, color_map['primary'])

    def show_update_error_solutions(self, full_output: str):
        """Show solutions for common update errors."""
        # Analyze the output to determine the error type
        output_lower = full_output.lower()

        # Create solution dialog
        dialog = tk.Toplevel(self.root)
        dialog.title("Update Error - Solutions")
        dialog.configure(bg=self.colors['background'])

        # Use position_window for persistent positioning [[memory:2371890]]
        self.position_window(dialog, width=700, height=500, parent=self.root)  # type: ignore[arg-type]

        # Header
        header_frame = tk.Frame(dialog, bg=self.colors['error'], height=80)
        header_frame.pack(fill='x')
        header_frame.pack_propagate(False)

        tk.Label(header_frame, text="⚠️ Update Failed",
                 font=('Segoe UI', 18, 'bold'),
                 fg='white', bg=self.colors['error']).pack(pady=20)

        # Content
        content_frame = tk.Frame(dialog, bg=self.colors['background'])
        content_frame.pack(fill='both', expand=True, padx=20, pady=20)

        # Error type detection and solutions
        if "404" in output_lower and "failed retrieving file" in output_lower:
            # Mirror sync issues
            error_title = "Mirror Synchronization Issue"
            error_desc = "Some packages couldn't be found on the mirrors. This usually happens when:\n• Your mirror list is outdated\n• Mirrors haven't synced the latest packages yet"

            solutions = [
                ("🔄 Refresh Package Database",
                 "sudo pacman -Syy",
                 "Forces a refresh of all package databases"),
                ("🌐 Update Mirror List",
                 "sudo reflector --latest 20 --protocol https --sort rate --save /etc/pacman.d/mirrorlist",
                 "Updates your mirror list with the fastest, most up-to-date mirrors"),
                ("⏱️ Wait and Retry",
                 "Wait a few hours and try again",
                 "Sometimes mirrors need time to sync new packages")]

            # Extract failed packages
            failed_packages = re.findall(r"failed retrieving file '([^']+)'", full_output)
            if failed_packages:
                unique_packages = list(set([p.split('.pkg.tar')[0] for p in failed_packages]))
                error_desc += "\n\nFailed packages:\n• " + "\n• ".join(unique_packages[:5])
                if len(unique_packages) > 5:
                    error_desc += f"\n• ... and {len(unique_packages) - 5} more"

        elif "conflicting files" in output_lower:
            error_title = "File Conflict Error"
            error_desc = "Package installation conflicts with existing files on your system."
            solutions = [
                ("🔍 Check Conflicts", "sudo pacman -Qo /path/to/conflicting/file",
                 "Find which package owns the conflicting file"),
                ("⚡ Force Overwrite (Careful!)", "sudo pacman -Su --overwrite '*'",
                 "Force overwrite conflicts - use with caution!"),
                ("🗑️ Remove Conflicting Package", "sudo pacman -R conflicting-package",
                 "Remove the package causing conflicts")
            ]

        elif "failed to commit transaction" in output_lower:
            error_title = "Transaction Failed"
            error_desc = "The package transaction couldn't be completed. This might be due to:\n• Corrupted package database\n• Insufficient disk space\n• Interrupted previous update"
            solutions = [
                ("🔄 Refresh Database", "sudo pacman -Syy",
                 "Refresh all package databases"),
                ("🧹 Clear Package Cache", "sudo pacman -Scc",
                 "Clear old packages from cache to free space"),
                ("🔧 Fix Database", "sudo rm /var/lib/pacman/db.lck",
                 "Remove lock file if previous update was interrupted")
            ]
        else:
            error_title = "Update Error"
            error_desc = "An error occurred during the update process. Check the terminal output for specific details."
            solutions = [
                ("🔄 Refresh & Retry", "sudo pacman -Syyu",
                 "Force refresh databases and retry update"),
                ("📋 Check Pacman Log", "tail -50 /var/log/pacman.log",
                 "View recent pacman operations for clues"),
                ("🌐 Check Arch News", "https://archlinux.org/news/",
                 "Check for known issues or manual interventions")
            ]

        # Display error info
        tk.Label(content_frame, text=error_title,
                 font=('Segoe UI', 14, 'bold'),
                 fg=self.colors['text'], bg=self.colors['background']).pack(anchor='w')

        tk.Label(content_frame, text=error_desc,
                 font=('Segoe UI', 10),
                 fg=self.colors['text_secondary'], bg=self.colors['background'],
                 justify='left', wraplength=650).pack(anchor='w', pady=(5, 15))

        # Solutions frame
        tk.Label(content_frame, text="Recommended Solutions:",
                 font=('Segoe UI', 12, 'bold'),
                 fg=self.colors['text'], bg=self.colors['background']).pack(anchor='w', pady=(10, 5))

        solutions_frame = tk.Frame(content_frame, bg=self.colors['background'])
        solutions_frame.pack(fill='both', expand=True)

        for i, (title, command, desc) in enumerate(solutions):
            sol_frame = tk.Frame(solutions_frame, bg=self.colors['surface'],
                                 relief='ridge', bd=1)
            sol_frame.pack(fill='x', pady=5)

            # Solution content
            sol_content = tk.Frame(sol_frame, bg=self.colors['surface'])
            sol_content.pack(fill='x', padx=10, pady=10)

            tk.Label(sol_content, text=title,
                     font=('Segoe UI', 11, 'bold'),
                     fg=self.colors['primary'], bg=self.colors['surface']).pack(anchor='w')

            tk.Label(sol_content, text=desc,
                     font=('Segoe UI', 9),
                     fg=self.colors['text_secondary'], bg=self.colors['surface']).pack(anchor='w', pady=(2, 5))

            # Command frame with copy button
            if not command.startswith("http") and not command.startswith("Wait"):
                cmd_frame = tk.Frame(sol_content, bg=self.colors['background'])
                cmd_frame.pack(anchor='w', fill='x')

                cmd_text = tk.Text(cmd_frame, height=1, width=len(command),
                                   font=('Consolas', 9), fg=self.colors['text'],
                                   bg=self.colors['background'], bd=1, relief='solid',
                                   padx=5, pady=2)
                cmd_text.pack(side='left', fill='x', expand=True)
                cmd_text.insert('1.0', command)
                cmd_text.config(state='disabled')

                def copy_cmd(cmd=command):
                    self.root.clipboard_clear()
                    self.root.clipboard_append(cmd)
                    messagebox.showinfo("Copied", "Command copied to clipboard!")

                tk.Button(cmd_frame, text="📋 Copy",
                          font=('Segoe UI', 9), command=copy_cmd,
                          bg=self.colors['surface'], fg=self.colors['text'],
                          bd=1, padx=10, cursor='hand2').pack(side='left', padx=(5, 0))

        # Buttons
        btn_frame = tk.Frame(dialog, bg=self.colors['background'])
        btn_frame.pack(fill='x', padx=20, pady=20)

        tk.Button(btn_frame, text="Close",
                  font=('Segoe UI', 11),
                  bg=self.colors['surface'], fg=self.colors['text'],
                  padx=20, pady=8, bd=1, relief='solid',
                  command=dialog.destroy).pack(side='right')

        # Update main window status
        self.update_status("Update failed - see solutions dialog", "error")

    def update_logging_status(self):
        """Update the logging status indicator in the sidebar."""
        debug_mode = self.config.config.get('debug_mode', False)
        verbose_logging = self.config.config.get('verbose_logging', False)

        if debug_mode and verbose_logging:
            self.logging_status_label.configure(text="🔍 Debug & Verbose Logging")
        elif debug_mode:
            self.logging_status_label.configure(text="🔍 Debug Mode")
        elif verbose_logging:
            self.logging_status_label.configure(text="📝 Verbose Logging")
        else:
            self.logging_status_label.configure(text="")

    def _close_dialog_and_show_news(self, dialog: tk.Toplevel) -> None:
        """Helper method to close dialog and show news frame."""
        dialog.destroy()
        self.show_frame("news")

    def _detect_default_terminal(self) -> Optional[str]:
        """Detect the user's default terminal emulator."""
        # Method 1: Check for flatpak-installed terminals first (likely user preference)
        try:
            result = subprocess.run(['flatpak', 'list', '--app'], capture_output=True, check=False)
            if result.returncode == 0:
                flatpak_output = result.stdout.decode()
                # Prioritize modern terminals in flatpak
                priority_flatpak_terminals = [
                    ('org.wezfurlong.wezterm', 'wezterm'),
                    ('io.alacritty.Alacritty', 'alacritty'),
                    ('org.gnome.Terminal', 'gnome-terminal'),
                    ('org.kde.konsole', 'konsole')
                ]

                for app_id, terminal_name in priority_flatpak_terminals:
                    if app_id in flatpak_output:
                        logger.debug(f"Found priority flatpak terminal: {app_id} ({terminal_name})")
                        return f"flatpak run {app_id}"
        except Exception as e:
            logger.debug(f"Flatpak check failed: {e}")

        # Method 2: Check TERMINAL environment variable
        terminal_env = os.environ.get('TERMINAL')
        if terminal_env:
            # Validate that it's a safe terminal command
            terminal_name = os.path.basename(terminal_env)
            if self._is_safe_terminal(terminal_name):
                logger.debug(f"Found terminal from TERMINAL env var: {terminal_env}")
                return terminal_env

        # Method 3: Try x-terminal-emulator (Debian/Ubuntu systems)
        try:
            result = subprocess.run(['which', 'x-terminal-emulator'],
                                    capture_output=True, check=False)
            if result.returncode == 0:
                terminal_path = result.stdout.decode().strip()
                if terminal_path and self._is_safe_terminal(os.path.basename(terminal_path)):
                    logger.debug(f"Found terminal via x-terminal-emulator: {terminal_path}")
                    return terminal_path
        except Exception as e:
            logger.debug(f"x-terminal-emulator check failed: {e}")

        # Method 4: Check common desktop environment settings
        desktop_env = os.environ.get('XDG_CURRENT_DESKTOP', '').lower()
        # session_type = os.environ.get('XDG_SESSION_TYPE', '').lower()  # Reserved for future use

        if 'gnome' in desktop_env:
            return 'gnome-terminal'
        elif 'kde' in desktop_env or 'plasma' in desktop_env:
            return 'konsole'
        elif 'xfce' in desktop_env:
            return 'xfce4-terminal'
        elif 'mate' in desktop_env:
            return 'mate-terminal'
        elif 'cinnamon' in desktop_env:
            return 'gnome-terminal'  # Cinnamon uses gnome-terminal
        elif 'lxde' in desktop_env or 'lxqt' in desktop_env:
            return 'lxterminal'

        # Method 4: Check running processes to detect user's actual terminal preference
        try:
            result = subprocess.run(['ps', 'aux'], capture_output=True, check=False)
            if result.returncode == 0:
                ps_output = result.stdout.decode()
                # Look for running terminal processes (excluding this process check)
                terminal_processes = []
                for line in ps_output.split('\n'):
                    for term in ['wezterm', 'alacritty', 'kitty', 'gnome-terminal', 'konsole', 'foot']:
                        if term in line and 'ps aux' not in line and 'grep' not in line:
                            if self._is_safe_terminal(term):
                                terminal_processes.append(term)

                if terminal_processes:
                    # Use the most frequently running terminal
                    from collections import Counter
                    most_common = Counter(terminal_processes).most_common(1)
                    if most_common:
                        preferred_terminal = most_common[0][0]
                        logger.debug(f"Found preferred terminal from running processes: {preferred_terminal}")
                        return preferred_terminal
        except Exception as e:
            logger.debug(f"Process detection failed: {e}")

        # Method 5: Try to detect through gsettings (GNOME-based)
        try:
            result = subprocess.run(['gsettings', 'get', 'org.gnome.desktop.default-applications.terminal', 'exec'],
                                    capture_output=True, check=False, timeout=5)
            if result.returncode == 0:
                terminal = result.stdout.decode().strip().strip("'\"")
                if terminal and self._is_safe_terminal(terminal):
                    logger.debug(f"Found terminal via gsettings: {terminal}")
                    return terminal
        except Exception as e:
            logger.debug(f"gsettings check failed: {e}")

        # Method 6: Fallback to common terminals that exist on system
        # Prioritize modern terminals first, then traditional ones
        common_terminals = [
            'wezterm', 'alacritty', 'kitty', 'foot',  # Modern terminals
            'gnome-terminal', 'konsole', 'xfce4-terminal', 'mate-terminal',
            'terminator', 'tilix', 'terminology', 'contour', 'tabby',
            'xterm'  # Basic fallback
        ]

        for terminal in common_terminals:
            try:
                result = subprocess.run(['which', terminal],
                                        capture_output=True, check=False)
                if result.returncode == 0:
                    logger.debug(f"Found fallback terminal: {terminal}")
                    return terminal
            except Exception:
                continue

        logger.warning("No suitable terminal emulator found")
        return None

    def _is_safe_terminal(self, terminal_name: str) -> bool:
        """Check if a terminal name is safe to execute."""
        # Handle flatpak commands
        if isinstance(terminal_name, str) and terminal_name.startswith('flatpak run '):
            app_id = terminal_name.replace('flatpak run ', '')
            safe_flatpak_apps = {
                'org.wezfurlong.wezterm', 'io.alacritty.Alacritty',
                'org.gnome.Terminal', 'org.kde.konsole'
            }
            return app_id in safe_flatpak_apps

        # Only allow known safe terminal names
        safe_terminals = {
            'gnome-terminal', 'konsole', 'xfce4-terminal', 'mate-terminal',
            'xterm', 'alacritty', 'kitty', 'terminator', 'tilix', 'lxterminal',
            'qterminal', 'terminology', 'urxvt', 'rxvt', 'st', 'sakura',
            'wezterm', 'foot', 'contour', 'tabby'
        }
        return terminal_name in safe_terminals

    def _build_terminal_command(self, terminal: str, script_path: str) -> List[str]:
        """Build the appropriate terminal command for different terminal types."""
        # Handle flatpak applications
        if terminal.startswith('flatpak run '):
            app_id = terminal.replace('flatpak run ', '')
            if 'wezterm' in app_id:
                return ['flatpak', 'run', app_id, 'start', '--always-new-process', '--', 'bash', script_path]
            elif 'alacritty' in app_id:
                return ['flatpak', 'run', app_id, '--', 'bash', script_path]
            elif 'gnome' in app_id.lower() or 'Terminal' in app_id:
                return ['flatpak', 'run', app_id, '--', 'bash', script_path]
            elif 'konsole' in app_id:
                return ['flatpak', 'run', app_id, '-e', 'bash', script_path]
            else:
                # Generic flatpak fallback
                return ['flatpak', 'run', app_id, '-e', 'bash', script_path]

        # Handle regular system terminals
        terminal_name = os.path.basename(terminal)

        # Terminal-specific command structures
        if terminal_name == 'gnome-terminal':
            return [terminal, '--', 'bash', script_path]
        elif terminal_name == 'konsole':
            return [terminal, '-e', 'bash', script_path]
        elif terminal_name == 'wezterm':
            return [terminal, 'start', '--always-new-process', '--', 'bash', script_path]
        elif terminal_name in ['xfce4-terminal', 'mate-terminal']:
            return [terminal, '-e', f'bash {script_path}']
        elif terminal_name in ['xterm', 'urxvt', 'rxvt']:
            return [terminal, '-e', 'bash', script_path]
        elif terminal_name in ['alacritty', 'kitty']:
            return [terminal, '--', 'bash', script_path]
        elif terminal_name in ['terminator', 'tilix']:
            return [terminal, '-e', 'bash', script_path]
        elif terminal_name in ['terminology', 'lxterminal', 'qterminal']:
            return [terminal, '-e', f'bash {script_path}']
        elif terminal_name in ['st', 'sakura']:
            return [terminal, '-e', 'bash', script_path]
        elif terminal_name == 'foot':
            return [terminal, 'bash', script_path]
        elif terminal_name in ['contour', 'tabby']:
            return [terminal, '-e', 'bash', script_path]
        else:
            # Generic fallback
            return [terminal, '-e', 'bash', script_path]

    def update_sidebar_summary(self, total_packages, download_size, disk_space,
                               download_size_text=None, disk_space_text=None):
        """Update the sidebar summary display with package info."""
        # Update packages count
        self.sidebar_summary_labels['Packages:'].configure(text=str(total_packages))

        # Update download size
        if download_size_text:
            self.sidebar_summary_labels['Download:'].configure(text=download_size_text)
        elif download_size is not None:
            size_text = self._format_size(download_size)
            self.sidebar_summary_labels['Download:'].configure(text=size_text)
        else:
            self.sidebar_summary_labels['Download:'].configure(text="—")

        # Update disk space
        if disk_space_text:
            self.sidebar_summary_labels['Disk space:'].configure(text=disk_space_text)
        elif disk_space is not None:
            size_text = self._format_size(disk_space)
            self.sidebar_summary_labels['Disk space:'].configure(text=size_text)
        else:
            self.sidebar_summary_labels['Disk space:'].configure(text="—")

    def _format_size(self, size_bytes: Optional[int]) -> str:
        """Format size in bytes to human readable format."""
        if size_bytes is None:
            return "—"
        if size_bytes < 1024:
            return f"{size_bytes} B"
        elif size_bytes < 1024 * 1024:
            return f"{size_bytes / 1024:.1f} KB"
        elif size_bytes < 1024 * 1024 * 1024:
            return f"{size_bytes / (1024 * 1024):.1f} MB"
        else:
            return f"{size_bytes / (1024 * 1024 * 1024):.2f} GB"


class UpdatesNewsFrame(ttk.Frame, WindowPositionMixin):
    def __init__(self, parent: tk.Widget, main_window: "MainWindow", packages: List[str], news_items: List[Dict[str, Any]], updates: Optional[List[Any]] = None) -> None:
        super().__init__(parent, style='Content.TFrame')
        self.main_window = main_window
        self.packages = list(packages)  # Ensure it's a mutable list
        self.news_items = news_items
        self.updates = updates  # Full update objects with version info
        self.selected_packages: Set[str] = set(packages)  # Track selected packages
        self.current_news_items: List[Dict[str, Any]] = []  # Currently displayed news items
        
        # Declare canvas and scrollbar attributes
        self.pkg_list_canvas: tk.Canvas
        self.pkg_scrollbar: ttk.Scrollbar
        self.news_canvas: tk.Canvas
        self.news_scrollbar: ttk.Scrollbar
        self.pkg_frame: tk.Frame
        self.news_frame: tk.Frame
        self.pkg_vars: Dict[str, tk.BooleanVar] = {}
        self.header_count_label: tk.Label
        self.news_count: tk.Label
        
        self._build_ui()

    def _build_ui(self) -> None:
        """Build simple responsive UI."""
        # Clear any existing widgets
        for widget in self.winfo_children():
            widget.destroy()

        # Configure self for expansion
        self.rowconfigure(1, weight=1)
        self.columnconfigure(0, weight=1)

        # Header (row 0)
        header = tk.Frame(self, bg=self.main_window.colors['primary'], height=80)
        header.grid(row=0, column=0, sticky='ew')
        header.grid_propagate(False)
        header.columnconfigure(0, weight=1)
        header.rowconfigure(0, weight=1)

        header_content = tk.Frame(header, bg=self.main_window.colors['primary'])
        header_content.grid(row=0, column=0)

        tk.Label(header_content,
                 text="Updates Available",
                 font=('Segoe UI', 24, 'bold'),
                 fg='white',
                 bg=self.main_window.colors['primary']).pack()

        self.header_count_label = tk.Label(header_content,
                                           text=f"{len(self.packages)} packages need updating",
                                           font=('Segoe UI', 12, 'normal'),
                                           fg='white',
                                           bg=self.main_window.colors['primary'])
        self.header_count_label.pack()

        # Content area (row 1)
        content = tk.Frame(self, bg=self.main_window.colors['background'])
        content.grid(row=1, column=0, sticky='nsew', padx=20, pady=20)
        content.rowconfigure(0, weight=1)
        content.columnconfigure(0, weight=1)
        content.columnconfigure(1, weight=2)

        # Left: Packages
        pkg_frame = tk.Frame(content, bg=self.main_window.colors['surface'], relief='ridge', bd=2)
        pkg_frame.grid(row=0, column=0, sticky='nsew', padx=(0, 10))
        pkg_frame.rowconfigure(1, weight=1)
        pkg_frame.columnconfigure(0, weight=1)

        # Package header
        pkg_hdr = tk.Frame(pkg_frame, bg=self.main_window.colors['surface'])
        pkg_hdr.grid(row=0, column=0, sticky='ew', padx=10, pady=5)
        pkg_hdr.columnconfigure(0, weight=1)

        tk.Label(pkg_hdr, text="Packages with Updates",
                 font=('Segoe UI', 14, 'bold'),
                 fg=self.main_window.get_text_color('primary'),
                 bg=self.main_window.colors['surface']).grid(row=0, column=0, sticky='w')

        btn_frame = tk.Frame(pkg_hdr, bg=self.main_window.colors['surface'])
        btn_frame.grid(row=0, column=1, sticky='e')

        tk.Button(btn_frame, text="All", command=self.select_all_packages,
                  fg=self.main_window.get_text_color('info'),
                  bg=self.main_window.colors['surface'], bd=0, cursor='hand2').pack(side='left', padx=2)
        tk.Button(btn_frame, text="None", command=self.select_no_packages,
                  fg=self.main_window.get_text_color('info'),
                  bg=self.main_window.colors['surface'], bd=0, cursor='hand2').pack(side='left', padx=2)

        # Package list
        list_frame = tk.Frame(pkg_frame, bg=self.main_window.colors['surface'])
        list_frame.grid(row=1, column=0, sticky='nsew', padx=5, pady=(0, 5))
        list_frame.rowconfigure(0, weight=1)
        list_frame.columnconfigure(0, weight=1)

        self.pkg_list_canvas = tk.Canvas(list_frame, bg=self.main_window.colors['background'])
        self.pkg_list_canvas.grid(row=0, column=0, sticky='nsew')

        pkg_scroll = ttk.Scrollbar(list_frame, orient='vertical', command=self.pkg_list_canvas.yview)
        pkg_scroll.grid(row=0, column=1, sticky='ns')
        self.pkg_list_canvas.configure(yscrollcommand=pkg_scroll.set)

        self.pkg_frame = tk.Frame(self.pkg_list_canvas, bg=self.main_window.colors['background'])
        self.pkg_list_canvas.create_window((0, 0), window=self.pkg_frame, anchor='nw')

        # Add packages
        safe_pattern = re.compile(r'^[A-Za-z0-9_.+-]+$')
        self.pkg_vars = {}

        # Create a map of package names to version info if updates provided
        version_map = {}
        if self.updates:
            for update in self.updates:
                if hasattr(update, 'current_version') and hasattr(update, 'new_version'):
                    version_map[update.name] = {
                        'old': update.current_version,
                        'new': update.new_version
                    }

        for pkg in sorted(self.packages):
            if not safe_pattern.match(pkg):
                continue
            var = tk.BooleanVar(value=True)
            self.pkg_vars[pkg] = var

            # Create display text with version info if available
            display_text = pkg
            if pkg in version_map:
                v_info = version_map[pkg]
                display_text = f"{pkg} ({v_info['old']} → {v_info['new']})"

            tk.Checkbutton(self.pkg_frame, text=display_text, variable=var,
                           font=('Segoe UI', 10, 'normal'),  # Standardize with Package Manager
                           fg=self.main_window.get_text_color('primary'),
                           bg=self.main_window.colors['background'],
                           selectcolor=self.main_window.colors['surface'],
                           activebackground=self.main_window.colors['background'],
                           activeforeground=self.main_window.get_text_color('primary'),
                           anchor='w', command=self.update_news_display).pack(fill='x', padx=5, pady=1)

        # Right: News
        news_frame = tk.Frame(content, bg=self.main_window.colors['surface'], relief='ridge', bd=2)
        news_frame.grid(row=0, column=1, sticky='nsew', padx=(10, 0))
        news_frame.rowconfigure(1, weight=1)
        news_frame.columnconfigure(0, weight=1)

        # News header
        news_hdr = tk.Frame(news_frame, bg=self.main_window.colors['surface'])
        news_hdr.grid(row=0, column=0, sticky='ew', padx=10, pady=5)

        tk.Label(news_hdr, text="Related News & Advisories",
                 font=('Segoe UI', 14, 'bold'),
                 fg=self.main_window.get_text_color('primary'),
                 bg=self.main_window.colors['surface']).pack(side='left')

        self.news_count = tk.Label(news_hdr, text="",
                                   font=('Segoe UI', 11),
                                   fg=self.main_window.get_text_color('secondary'),
                                   bg=self.main_window.colors['surface'])
        self.news_count.pack(side='left', padx=(10, 0))

        # News list
        news_list_frame = tk.Frame(news_frame, bg=self.main_window.colors['surface'])
        news_list_frame.grid(row=1, column=0, sticky='nsew', padx=5, pady=(0, 5))
        news_list_frame.rowconfigure(0, weight=1)
        news_list_frame.columnconfigure(0, weight=1)

        self.news_canvas = tk.Canvas(news_list_frame, bg=self.main_window.colors['background'])
        self.news_canvas.grid(row=0, column=0, sticky='nsew')

        news_scroll = ttk.Scrollbar(news_list_frame, orient='vertical', command=self.news_canvas.yview)
        news_scroll.grid(row=0, column=1, sticky='ns')
        self.news_canvas.configure(yscrollcommand=news_scroll.set)

        self.news_frame = tk.Frame(self.news_canvas, bg=self.main_window.colors['background'])
        self.news_canvas.create_window((0, 0), window=self.news_frame, anchor='nw')

        # Buttons (row 2)
        btn_bar = tk.Frame(self, bg=self.main_window.colors['surface'], height=60)
        btn_bar.grid(row=2, column=0, sticky='ew')
        btn_bar.grid_propagate(False)
        btn_bar.columnconfigure(0, weight=1)
        btn_bar.rowconfigure(0, weight=1)

        btn_container = tk.Frame(btn_bar, bg=self.main_window.colors['surface'])
        btn_container.grid(row=0, column=0)

        tk.Button(btn_container, text="Apply Selected Updates",
                  bg=self.main_window.colors['primary'], fg='white',
                  font=('Segoe UI', 11, 'bold'), padx=20, pady=8,
                  command=self.apply_updates).pack(side='left', padx=(0, 10))

        tk.Button(btn_container, text="Back to Dashboard",
                  fg=self.main_window.get_text_color('primary'),
                  bg=self.main_window.colors['background'],
                  font=('Segoe UI', 11), padx=20, pady=8,
                  command=self.go_back).pack(side='left')

        # Configure scroll regions
        def update_pkg_scroll(event):
            self.pkg_list_canvas.configure(scrollregion=self.pkg_list_canvas.bbox("all"))

        def update_news_scroll(event):
            self.news_canvas.configure(scrollregion=self.news_canvas.bbox("all"))
            # Update text wrapping when news area is resized
            self._update_news_wrapping()

        self.pkg_frame.bind("<Configure>", update_pkg_scroll)
        self.news_frame.bind("<Configure>", update_news_scroll)

        # Mouse wheel - bind to canvases and set up global interception
        self.pkg_list_canvas.bind("<MouseWheel>", self._on_mousewheel)
        self.pkg_list_canvas.bind("<Button-4>", self._on_mousewheel)
        self.pkg_list_canvas.bind("<Button-5>", self._on_mousewheel)

        self.news_canvas.bind("<MouseWheel>", self._on_mousewheel)
        self.news_canvas.bind("<Button-4>", self._on_mousewheel)
        self.news_canvas.bind("<Button-5>", self._on_mousewheel)

        # Set up global mouse wheel interception for news area
        self.bind_all("<MouseWheel>", self._intercept_news_mousewheel)
        self.bind_all("<Button-4>", self._intercept_news_mousewheel)
        self.bind_all("<Button-5>", self._intercept_news_mousewheel)

        # Initial news display
        self.update_news_display()

        # Calculate sizes asynchronously after UI is built
        self.after(100, self._calculate_sizes_async)

    def _format_size(self, size_bytes: Optional[int]) -> str:
        """Format size in bytes to human readable format."""
        if size_bytes is None:
            return "Unknown"
        if size_bytes < 1024:
            return f"{size_bytes} B"
        elif size_bytes < 1024 * 1024:
            return f"{size_bytes / 1024:.1f} KB"
        elif size_bytes < 1024 * 1024 * 1024:
            return f"{size_bytes / (1024 * 1024):.1f} MB"
        else:
            return f"{size_bytes / (1024 * 1024 * 1024):.2f} GB"

    def _calculate_sizes_async(self) -> None:
        """Calculate sizes asynchronously to avoid blocking UI."""
        def calculate():
            try:
                # Get update objects with size info
                if not self.updates:
                    return

                # Create a map of package names to update objects
                update_map = {u.name: u for u in self.updates}

                # Calculate totals for selected packages
                selected = self.get_selected_packages()
                selected_updates = [update_map[pkg] for pkg in selected if pkg in update_map]

                total_download = 0
                total_installed = 0
                packages_with_download_size = 0
                packages_with_installed_size = 0

                for update in selected_updates:
                    if hasattr(update, 'size') and update.size is not None:
                        total_download += update.size
                        packages_with_download_size += 1
                    if hasattr(update, 'installed_size') and update.installed_size is not None:
                        total_installed += update.installed_size
                        packages_with_installed_size += 1

                # Update UI in main thread
                self.after(0, lambda: self._update_summary_display(
                    len(selected),
                    total_download if packages_with_download_size > 0 else None,
                    total_installed if packages_with_installed_size > 0 else None,
                    packages_with_download_size,
                    packages_with_installed_size
                ))

            except Exception:
                import traceback
                logger.error(f"Error calculating sizes: {traceback.format_exc()}")

        # Run in background thread
        from ..utils.thread_manager import create_managed_thread
        import uuid
        thread_id = f"calc_sizes_{uuid.uuid4().hex[:8]}"

        thread = create_managed_thread(thread_id, calculate, is_background=True, component_id=thread_id)
        if thread:
            thread.start()

    def _update_summary_display(self, total_packages, download_size, installed_size,
                                packages_with_download_size, packages_with_installed_size):
        """Update the summary display with calculated values."""
        # Build text for download size
        download_text = None
        if download_size is not None:
            download_text = self._format_size(download_size)
            if packages_with_download_size < total_packages:
                # Show partial data in a compact way for sidebar
                download_text = f"{self._format_size(download_size)}"

        # Build text for disk space
        disk_text = None
        if installed_size is not None:
            disk_text = self._format_size(installed_size)
            if packages_with_installed_size < total_packages:
                # Show partial data in a compact way for sidebar
                disk_text = f"{self._format_size(installed_size)}"
        elif download_size is not None:
            # Fallback to estimate if no installed size data
            estimated = int(download_size * 2.5)
            disk_text = f"~{self._format_size(estimated)}"

        # Update sidebar summary via main window
        self.main_window.update_sidebar_summary(
            total_packages,
            download_size,
            installed_size,
            download_text,
            disk_text
        )

    def get_selected_packages(self) -> List[str]:
        """Get list of currently selected packages."""
        selected = []
        for pkg, var in self.pkg_vars.items():
            if var.get():
                selected.append(pkg)
        return selected

    def select_all_packages(self) -> None:
        """Select all packages."""
        for var in self.pkg_vars.values():
            var.set(True)
        self.update_news_display()

    def select_no_packages(self) -> None:
        """Deselect all packages."""
        for var in self.pkg_vars.values():
            var.set(False)
        self.update_news_display()

    def _on_frame_resize(self, event: tk.Event) -> None:
        """Handle frame resize events."""
        if event.widget == self:
            self._current_width = event.width
            # Update news item wrapping
            self.after_idle(self._update_news_wrapping)

    def _update_news_wrapping(self) -> None:
        """Update news item text wrapping based on current width."""
        try:
            # Get the current width of the news canvas
            news_width = self.news_canvas.winfo_width()
            if news_width > 100:  # Only update if we have a reasonable width
                # Leave some padding for scrollbar and margins
                wrap_width = max(300, news_width - 60)

                # Update all news items
                for widget in self.news_frame.winfo_children():
                    if hasattr(widget, '_title_label'):
                        widget._title_label.configure(wraplength=wrap_width)
                    if hasattr(widget, '_affects_label'):
                        widget._affects_label.configure(wraplength=wrap_width)
        except Exception:
            # Fallback to fixed width if there's any issue
            for widget in self.news_frame.winfo_children():
                if hasattr(widget, '_title_label'):
                    widget._title_label.configure(wraplength=400)
                if hasattr(widget, '_affects_label'):
                    widget._affects_label.configure(wraplength=400)

    def _configure_pkg_scroll(self, event: tk.Event) -> None:
        """Configure package scrollbar visibility."""
        self.pkg_list_canvas.configure(scrollregion=self.pkg_list_canvas.bbox("all"))
        # Only show scrollbar if content is larger than canvas
        if self.pkg_frame.winfo_reqheight() > self.pkg_list_canvas.winfo_height():
            self.pkg_scrollbar.pack(side="right", fill="y")
        else:
            self.pkg_scrollbar.pack_forget()

    def _configure_news_scroll(self, event: tk.Event) -> None:
        """Configure news scrollbar visibility."""
        self.news_canvas.configure(scrollregion=self.news_canvas.bbox("all"))
        # Always show scrollbar for news since content is usually longer
        self.news_scrollbar.pack(side="right", fill="y")

    def _intercept_news_mousewheel(self, event: tk.Event) -> Optional[str]:
        """Intercept mouse wheel events and delegate to appropriate canvas."""
        try:
            # Get mouse position relative to this frame
            x = self.main_window.root.winfo_pointerx() - self.winfo_rootx()
            y = self.main_window.root.winfo_pointery() - self.winfo_rooty()

            # Check if mouse is over this frame
            if (0 <= x <= self.winfo_width() and 0 <= y <= self.winfo_height()):
                # Get relative position within the content area
                content_x = x - 20  # Account for padding
                # content_y = y - 100  # Account for header height (reserved for future use)

                # If mouse is in the news area (right side), scroll news
                if content_x > self.winfo_width() // 2:
                    self._scroll_canvas(self.news_canvas, event)
                    return "break"
                # If mouse is in the package area (left side), scroll packages
                elif content_x > 0:
                    self._scroll_canvas(self.pkg_list_canvas, event)
                    return "break"
        except Exception:
            pass
        return None

    def _scroll_canvas(self, canvas: tk.Canvas, event: tk.Event) -> None:
        """Scroll the specified canvas."""
        try:
            if hasattr(event, 'delta') and event.delta:
                canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
            else:
                if event.num == 4:
                    canvas.yview_scroll(-1, "units")
                elif event.num == 5:
                    canvas.yview_scroll(1, "units")
        except Exception:
            pass

    def _on_mousewheel(self, event: tk.Event) -> None:
        """Handle mouse wheel scrolling for individual canvases."""
        # This is called when mouse wheel events are specifically bound to canvases
        widget = event.widget
        if hasattr(widget, 'yview_scroll') and isinstance(widget, tk.Canvas):
            self._scroll_canvas(widget, event)

    def update_news_display(self) -> None:
        """Update news display based on selected packages."""
        # Update header count
        selected = self.get_selected_packages()
        self.selected_packages = set(selected)
        count = len(selected)
        self.header_count_label.configure(text=f"{count} packages selected for update")

        # Recalculate sizes when selection changes
        self._calculate_sizes_async()

        # Clear news frame
        for widget in self.news_frame.winfo_children():
            widget.destroy()

        if not self.selected_packages:
            # No packages selected - create helpful message
            message = "📦 Select packages to view related news\n\n👈 Check packages on the left to see relevant\nnews and security advisories"

            # Create centered container with same background as news_frame
            container = tk.Frame(self.news_frame, bg=self.main_window.colors['background'])
            container.pack(expand=True, fill='both')

            no_selection = tk.Label(container,
                                    text=message,
                                    font=('Segoe UI', 11, 'normal'),
                                    fg=self.main_window.get_text_color('secondary'),
                                    bg=self.main_window.colors['background'],
                                    justify='center')
            no_selection.pack(expand=True)  # Center the label in the container
            self.news_count.configure(text="")
            return

        # Filter news items for selected packages
        relevant_news = []
        for item in self.news_items:
            news_text = f"{item.get('title', '')} {item.get('content', '')}"
            affected = self.main_window.checker.pattern_matcher.find_affected_packages(
                news_text, self.selected_packages
            )
            if affected:
                item['affected_packages'] = affected
                relevant_news.append(item)

        self.current_news_items = relevant_news
        self.news_count.configure(text=f"({len(relevant_news)} items)")

        if not relevant_news:
            # No relevant news - create dynamic message with freshness period
            freshness_days = self.main_window.checker.news_fetcher.max_news_age_days

            # Create a contextual and informative message
            if freshness_days == 1:
                period_text = "the last 24 hours"
            elif freshness_days <= 7:
                period_text = f"the last {freshness_days} days"
            elif freshness_days <= 30:
                period_text = f"the last {freshness_days} days"
            else:
                weeks = freshness_days // 7
                if weeks == 1:
                    period_text = "the last week"
                else:
                    period_text = f"the last {weeks} weeks"

            # Create the enhanced message with proper formatting
            message_lines = [
                "🔍 No news found for selected packages",
                "💡 Try adjusting news freshness in Settings",
                "",
                f"📅 Searched period: {period_text}"
            ]

            # Create centered container with same background as news_frame
            container = tk.Frame(self.news_frame, bg=self.main_window.colors['background'])
            container.pack(expand=True, fill='both')

            # Add all lines in a single label with left alignment, but center the label
            message_text = "\n".join(message_lines)
            label = tk.Label(container,
                             text=message_text,
                             font=('Segoe UI', 11, 'normal'),
                             fg=self.main_window.get_text_color('secondary'),
                             bg=self.main_window.colors['background'],
                             justify='left')  # Left-aligned text
            label.pack(expand=True)  # Center the label in the container
            return

        # Display news items with modern cards
        for i, item in enumerate(relevant_news):
            self.create_news_item(item, i)

    def create_news_item(self, item: Dict[str, Any], index: int) -> None:
        """Create a simple responsive news item."""
        # Simple card frame
        card = tk.Frame(self.news_frame, bg=self.main_window.colors['surface'],
                        relief='solid', bd=1)
        card.pack(fill='x', padx=5, pady=3)

        # Content frame
        content = tk.Frame(card, bg=self.main_window.colors['surface'])
        content.pack(fill='x', padx=8, pady=6)

        # Store reference for dynamic resizing
        card._content_frame = content  # type: ignore[attr-defined]

        # Title - with proper text wrapping
        title = tk.Label(content,
                         text=item.get('title', 'Unknown Title'),
                         font=('Segoe UI', 11, 'bold'),
                         fg=self.main_window.get_text_color('primary'),
                         bg=self.main_window.colors['surface'],
                         justify='left',
                         anchor='w',
                         wraplength=400)
        title.pack(fill='x', anchor='w')

        # Store reference for dynamic resizing
        card._title_label = title  # type: ignore[attr-defined]

        # Meta info
        meta = tk.Frame(content, bg=self.main_window.colors['surface'])
        meta.pack(fill='x', pady=(4, 0))

        # Date and source
        date = item.get('date')
        if date:
            date_str = date.strftime('%m-%d %H:%M') if hasattr(date, 'strftime') else str(date)
            tk.Label(meta, text=f"📅 {date_str}",
                     font=('Segoe UI', 9),
                     fg=self.main_window.get_text_color('secondary'),
                     bg=self.main_window.colors['surface']).pack(side='left', padx=(0, 10))

        source = item.get('source', 'Unknown')
        tk.Label(meta, text=f"📡 {source}",
                 font=('Segoe UI', 9),
                 fg=self.main_window.get_text_color('secondary'),
                 bg=self.main_window.colors['surface']).pack(side='left')

        # Affected packages (if any)
        if 'affected_packages' in item and item['affected_packages']:
            affected = list(item['affected_packages'])
            if len(affected) <= 3:
                pkg_text = "📦 " + ", ".join(affected)
            else:
                pkg_text = f"📦 {', '.join(affected[:2])} +{len(affected) - 2} more"

            affects_label = tk.Label(content, text=pkg_text,
                                     font=('Segoe UI', 9),
                                     fg=self.main_window.get_text_color('warning'),
                                     bg=self.main_window.colors['surface'],
                                     justify='left',
                                     anchor='w',
                                     wraplength=400)
            affects_label.pack(fill='x', anchor='w', pady=(3, 0))

            # Store reference for dynamic resizing
            card._affects_label = affects_label  # type: ignore[attr-defined]

        # Click handler
        def on_click(e):
            self.show_news_detail(item)

        for widget in [card, content, title]:
            widget.bind("<Button-1>", on_click)
            try:
                widget.configure(cursor='hand2')  # type: ignore[call-arg]
            except tk.TclError:
                pass  # Some widgets don't support cursor configuration

    def show_news_detail(self, news_item: Dict[str, Any]) -> None:
        """Show detailed view of a news item."""
        detail_window = tk.Toplevel(self)
        detail_window.title(news_item.get('title', 'News Detail'))
        detail_window.configure(bg=self.main_window.colors['background'])

        # Use position_window for persistent positioning [[memory:2371890]]
        self.position_window(detail_window, width=800, height=600, parent=self.main_window.root)  # type: ignore[arg-type]

        # Main container
        main_frame = ttk.Frame(detail_window, style='Content.TFrame')
        main_frame.pack(fill='both', expand=True, padx=20, pady=20)

        # Title
        title_label = tk.Label(main_frame,
                               text=news_item.get('title', 'Unknown Title'),
                               font=('Segoe UI', 16, 'bold'),
                               fg=self.main_window.colors['text'],
                               bg=self.main_window.colors['background'],
                               wraplength=750,
                               justify='left')
        title_label.pack(anchor='w', pady=(0, 10))

        # Meta info
        meta_frame = ttk.Frame(main_frame, style='Content.TFrame')
        meta_frame.pack(fill='x', pady=(0, 20))

        date = news_item.get('date')
        if date:
            date_str = date.strftime('%Y-%m-%d %H:%M') if hasattr(date, 'strftime') else str(date)
            tk.Label(meta_frame,
                     text=f"📅 {date_str}",
                     font=('Segoe UI', 11, 'normal'),
                     fg=self.main_window.colors['text_secondary'],
                     bg=self.main_window.colors['background']).pack(side='left', padx=(0, 20))

        tk.Label(meta_frame,
                 text=f"📡 {news_item.get('source', 'Unknown')}",
                 font=('Segoe UI', 11, 'normal'),
                 fg=self.main_window.colors['text_secondary'],
                 bg=self.main_window.colors['background']).pack(side='left')

        # Content
        content_frame = ttk.Frame(main_frame, style='Card.TFrame')
        content_frame.pack(fill='both', expand=True)

        content_text = tk.Text(content_frame,
                               wrap='word',
                               font=('Segoe UI', 11, 'normal'),
                               bg=self.main_window.colors['surface'],
                               fg=self.main_window.colors['text'],
                               relief='flat',
                               padx=20,
                               pady=20)
        content_text.pack(fill='both', expand=True)

        # Add content
        content = news_item.get('content', 'No content available.')
        content_text.insert('1.0', content)
        content_text.config(state='disabled')

        # Buttons
        btn_frame = ttk.Frame(main_frame, style='Content.TFrame')
        btn_frame.pack(fill='x', pady=(20, 0))

        if news_item.get('link'):
            # Create a function for the button command
            def open_link_command() -> None:
                link = news_item['link']
                SecureSubprocess.open_url_securely(str(link), sandbox=True) or webbrowser.open(str(link))
            
            open_btn = tk.Button(btn_frame,
                                 text="Open Link",
                                 font=('Segoe UI', 11, 'normal'),
                                 padx=15,
                                 pady=8,
                                 cursor='hand2',
                                 command=open_link_command)
            open_btn.pack(side='left', padx=(0, 10))

        close_btn = tk.Button(btn_frame,
                              text="Close",
                              font=('Segoe UI', 11, 'normal'),
                              fg=self.main_window.colors['text'],
                              bg=self.main_window.colors['surface'],
                              bd=1,
                              relief='solid',
                              padx=15,
                              pady=8,
                              cursor='hand2',
                              command=detail_window.destroy)
        close_btn.pack(side='left')

    def apply_updates(self) -> None:
        """Apply selected updates."""
        # Get only the selected packages from checkboxes
        selected = [pkg for pkg, var in self.pkg_vars.items() if var.get()]
        if not selected:
            messagebox.showwarning("No Selection", "Please select at least one package to update.")
            return

        # Validate package names to prevent command injection
        import string
        valid_chars = string.ascii_letters + string.digits + '-_+.'
        for pkg in selected:
            if not all(c in valid_chars for c in pkg):
                messagebox.showerror("Invalid Package", f"Invalid package name: {pkg}")
                return

        # No confirmation dialog - start update immediately
        self.main_window.update_status("Starting update process...", "info")

        # Try to open in a terminal emulator
        def run_in_terminal():
            import subprocess
            # First, get current versions of all packages before updating
            pre_update_versions = {}
            for pkg in selected:
                try:
                    # Query current installed version
                    logger.debug(f"Running pacman -Q {pkg}")
                    result = subprocess.run(
                        ["pacman", "-Q", pkg],
                        capture_output=True,
                        text=True,
                        check=False
                    )
                    logger.debug(
                        f"pacman -Q {pkg} returned: {result.returncode}, stdout: {result.stdout}, stderr: {result.stderr}")
                    if result.returncode == 0 and result.stdout:
                        # Format: "package-name version"
                        parts = result.stdout.strip().split(' ', 1)
                        if len(parts) == 2:
                            pre_update_versions[pkg] = parts[1]
                            logger.info(f"Pre-update version for {pkg}: {parts[1]}")
                        else:
                            logger.warning(f"Unexpected pacman -Q output format for {pkg}: {result.stdout}")
                    else:
                        logger.warning(f"pacman -Q {pkg} failed with code {result.returncode}")
                except Exception as e:
                    logger.error(f"Exception getting pre-update version for {pkg}: {e}", exc_info=True)

            # Log collected versions for debugging
            if pre_update_versions:
                logger.info(
                    f"Successfully collected pre-update versions for {len(pre_update_versions)} packages: {pre_update_versions}")
            else:
                logger.warning("Failed to collect any pre-update versions!")

            # Use -S to install/upgrade only selected packages
            # This avoids triggering a full system upgrade
            cmd_args = ["pacman", "-S", "--noconfirm"] + selected

            # Create a secure temporary file to capture output
            import stat
            output_fd, output_path = tempfile.mkstemp(suffix='.log', prefix='asuc_update_')
            os.close(output_fd)  # Close the file descriptor, we'll open by path

            # Set secure permissions (owner only)
            os.chmod(output_path, stat.S_IRUSR | stat.S_IWUSR)  # 0o600

            # Validate paths for security
            from ..utils.validators import validate_log_path
            try:
                validate_log_path(output_path)
            except ValueError as e:
                logger.error(f"Invalid path for update monitoring: {e}")
                self.main_window.update_status("Update failed: security validation error", "error")
                return

            # Build the command with pkexec
            full_cmd = ["pkexec"] + cmd_args

            logger.info(f"Starting package update with pkexec for packages: {selected}")
            logger.debug(f"Command: {' '.join(full_cmd)}")

            self.main_window.update_status(f"🔄 Installing {len(selected)} package(s)...", "info")

            # Execute the update command using SecureSubprocess
            try:
                from ..utils.subprocess_wrapper import SecureSubprocess

                # Create a progress dialog
                progress_dialog = tk.Toplevel(self.main_window.root)
                progress_dialog.title("Installing Updates")
                progress_dialog.geometry("700x500")  # Increased size to match other dialogs
                progress_dialog.transient(self.main_window.root)

                # Center the dialog
                progress_dialog.update_idletasks()
                x = (progress_dialog.winfo_screenwidth() // 2) - (350)  # Adjusted for 700 width
                y = (progress_dialog.winfo_screenheight() // 2) - (250)  # Adjusted for 500 height
                progress_dialog.geometry(f"+{x}+{y}")

                # Create UI elements
                info_label = ttk.Label(progress_dialog,
                                       text=f"Installing {len(selected)} package(s) with system privileges...",
                                       font=('Arial', 12))
                info_label.pack(pady=10)

                # Package list
                pkg_frame = ttk.Frame(progress_dialog)
                pkg_frame.pack(fill='x', padx=20, pady=5)
                ttk.Label(pkg_frame, text="Packages:", font=('Arial', 10, 'bold')).pack(anchor='w')
                for pkg in selected[:10]:  # Show first 10 packages
                    ttk.Label(pkg_frame, text=f"  • {pkg}").pack(anchor='w')
                if len(selected) > 10:
                    ttk.Label(pkg_frame, text=f"  ... and {len(selected) - 10} more").pack(anchor='w')

                # Progress text
                progress_text = tk.Text(progress_dialog, height=10, width=70, wrap='word')
                progress_text.pack(fill='both', expand=True, padx=20, pady=10)

                # Status label
                status_label = ttk.Label(progress_dialog, text="Waiting for authentication...")
                status_label.pack(pady=5)

                # Close button (disabled initially)
                close_btn = ttk.Button(progress_dialog, text="Close",
                                       command=progress_dialog.destroy, state='disabled')
                close_btn.pack(pady=10)

                # Function to update progress
                def update_progress(line):
                    progress_text.insert('end', line + '\n')
                    progress_text.see('end')
                    progress_dialog.update()

                # Run the command with real-time output
                success = False
                try:
                    # Create process with output capture
                    import subprocess
                    start_time = time.time()  # Track update duration

                    process = subprocess.Popen(
                        full_cmd,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.STDOUT,
                        text=True,
                        bufsize=1,
                        universal_newlines=True
                    )

                    self.main_window.root.after(0, lambda: status_label.config(text="Installing packages..."))

                    # Read output line by line
                    full_output = []
                    while True:
                        line = process.stdout.readline()
                        if not line and process.poll() is not None:
                            break
                        if line:
                            # Store output
                            full_output.append(line)
                            # Update progress dialog
                            self.main_window.root.after(0, lambda line_text=line.strip(): update_progress(line_text))
                            # Also log to file for history
                            with open(output_path, 'a') as f:
                                f.write(line)

                    # Get exit code
                    exit_code = process.poll()
                    success = (exit_code == 0)

                    # Check output for errors even if exit code is 0
                    output_text = '\n'.join([line for line in open(output_path, 'r')])
                    has_errors = False
                    error_patterns = [
                        'error:', 'failed', 'failure', 'could not', 'unable to',
                        'permission denied', 'file exists', 'corrupted',
                        'invalid or corrupted', 'signature from', 'unknown trust'
                    ]

                    for pattern in error_patterns:
                        if pattern.lower() in output_text.lower():
                            has_errors = True
                            logger.warning(f"Found error pattern '{pattern}' in output despite exit code {exit_code}")
                            break

                    # Override success if errors found in output
                    if has_errors and success:
                        success = False
                        logger.warning("Marking update as failed due to error patterns in output")

                    # Calculate duration
                    duration = time.time() - start_time

                    # Write exit code for history
                    with open(f"{output_path}.exitcode", 'w') as f:
                        f.write(str(exit_code))

                    # Update UI based on result
                    if success:
                        self.main_window.root.after(0, lambda: status_label.config(text="✅ Installation completed successfully!", foreground='green'))
                        self.main_window.update_status(
                            f"✅ Successfully installed {len(selected)} package(s)", "success")

                        # Refresh the updates list
                        logger.info(f"Update successful, refreshing UI for packages: {selected}")
                        self.main_window.root.after(0, lambda: self.refresh_after_update(selected))

                        # Clear package manager cache
                        try:
                            self.main_window.checker.package_manager.clear_cache()
                        except BaseException:
                            pass
                    else:
                        if exit_code == 126 or exit_code == 127:
                            # Authentication cancelled or pkexec not found
                            self.main_window.root.after(0, lambda: status_label.config(
                                text="❌ Authentication cancelled or pkexec not available", foreground='red'))
                            self.main_window.update_status("Update cancelled", "warning")
                        else:
                            self.main_window.root.after(0, lambda: status_label.config(text="❌ Installation failed", foreground='red'))
                            self.main_window.update_status(f"❌ Update failed with exit code {exit_code}", "error")

                    # Record update history if enabled
                    if self.main_window.config.get('update_history_enabled', False) and success:
                        from ..utils.update_history import UpdateHistoryManager

                        history_mgr = UpdateHistoryManager()

                        # Get pre-update version info if available
                        pre_update_version_info = {}

                        # First, try to use the versions we collected before the update
                        logger.info(f"Building version info - selected packages: {selected}")
                        logger.info(f"Pre-update versions available: {pre_update_versions}")

                        for pkg_name in selected:
                            if pkg_name in pre_update_versions:
                                pre_update_version_info[pkg_name] = {
                                    'old': pre_update_versions[pkg_name],
                                    'new': 'unknown'  # Will be filled in below
                                }
                                logger.debug(
                                    f"Added pre-update version for {pkg_name}: {pre_update_versions[pkg_name]}")

                        # If we still don't have old versions, try from last_update_objects
                        if hasattr(self.main_window.checker, 'last_update_objects'):
                            for pkg_name in selected:
                                if pkg_name not in pre_update_version_info and pkg_name in self.main_window.checker.last_update_objects:
                                    update_obj = self.main_window.checker.last_update_objects[pkg_name]
                                    if hasattr(update_obj, 'current_version') and hasattr(update_obj, 'new_version'):
                                        pre_update_version_info[pkg_name] = {
                                            'old': update_obj.current_version,
                                            'new': update_obj.new_version
                                        }

                        # Also try to extract version info from output
                        output_text = ''.join(full_output)

                        # Pattern for lines like "upgrading package (1.2.3-1 -> 1.2.4-1)..."
                        version_pattern = re.compile(r'upgrading\s+(\S+)\s*\((\S+)\s*->\s*(\S+)\)', re.IGNORECASE)
                        for match in version_pattern.finditer(output_text):
                            pkg_name = match.group(1)
                            if pkg_name in selected:
                                pre_update_version_info[pkg_name] = {
                                    'old': match.group(2),
                                    'new': match.group(3)
                                }

                        # Extract new versions from download/install lines
                        # Pattern for "downloading package-version..." or "installing package-version..."
                        download_pattern = re.compile(
                            r'(?:downloading|installing)\s+(\S+)-(\d+[^\s-]+(?:-\d+)?)\s*\.\.\.', re.IGNORECASE)
                        for match in download_pattern.finditer(output_text):
                            pkg_name = match.group(1)
                            new_version = match.group(2)
                            if pkg_name in selected:
                                if pkg_name in pre_update_version_info:
                                    # Update the new version
                                    pre_update_version_info[pkg_name]['new'] = new_version
                                else:
                                    # Create entry with unknown old version
                                    pre_update_version_info[pkg_name] = {
                                        'old': 'unknown',
                                        'new': new_version
                                    }

                        # Query post-update versions for packages we're still missing
                        for pkg_name in selected:
                            if pkg_name in pre_update_version_info and pre_update_version_info[pkg_name]['new'] == 'unknown':
                                try:
                                    # Query new installed version
                                    result = subprocess.run(
                                        ["pacman", "-Q", pkg_name],
                                        capture_output=True,
                                        text=True,
                                        check=False
                                    )
                                    if result.returncode == 0 and result.stdout:
                                        # Format: "package-name version"
                                        parts = result.stdout.strip().split(' ', 1)
                                        if len(parts) == 2:
                                            pre_update_version_info[pkg_name]['new'] = parts[1]
                                            logger.debug(f"Post-update version for {pkg_name}: {parts[1]}")
                                except Exception as e:
                                    logger.warning(f"Failed to get post-update version for {pkg_name}: {e}")

                        # Check for reinstalls
                        reinstall_pattern = re.compile(
                            r'warning:\s+(\S+)-(\S+)\s+is up to date\s*--\s*reinstalling', re.IGNORECASE)
                        reinstalled_packages = []
                        for match in reinstall_pattern.finditer(output_text):
                            pkg_name = match.group(1)
                            if pkg_name in selected:
                                reinstalled_packages.append(pkg_name)
                                logger.info(f"Skipping history record for reinstalled package: {pkg_name}")

                        # Filter out reinstalled packages from the list
                        packages_to_record = [pkg for pkg in selected if pkg not in reinstalled_packages]

                        # Only record if there are actual updates (not just reinstalls)
                        if packages_to_record:
                            # Pattern for "Packages (n) package-version package2-version2"
                            packages_pattern = re.compile(r'Packages\s*\(\d+\)\s+(.+)', re.IGNORECASE)
                            for match in packages_pattern.finditer(output_text):
                                pkg_list = match.group(1).strip()
                                # Parse each package-version pair
                                for pkg_ver in pkg_list.split():
                                    if '-' in pkg_ver:
                                        # Split on last hyphen to separate name from version
                                        parts = pkg_ver.rsplit('-', 1)
                                        if len(parts) == 2:
                                            pkg_name, new_version = parts
                                            if pkg_name in packages_to_record and pkg_name not in pre_update_version_info:
                                                # Try to get old version from last_update_objects
                                                if hasattr(
                                                        self.main_window.checker,
                                                        'last_update_objects') and pkg_name in self.main_window.checker.last_update_objects:
                                                    update_obj = self.main_window.checker.last_update_objects[pkg_name]
                                                    if hasattr(update_obj, 'current_version'):
                                                        pre_update_version_info[pkg_name] = {
                                                            'old': update_obj.current_version,
                                                            'new': new_version
                                                        }
                                                else:
                                                    # At least record the new version
                                                    pre_update_version_info[pkg_name] = {
                                                        'old': 'unknown',
                                                        'new': new_version
                                                    }

                            # Filter version info to only include packages we're recording
                            filtered_version_info = {k: v for k, v in pre_update_version_info.items()
                                                     if k in packages_to_record}

                            # Read output for history
                            with open(output_path, 'r') as f:
                                full_output_str = f.read()

                            logger.info(f"Recording history with version info: {filtered_version_info}")

                            history_mgr.add_entry(
                                packages=packages_to_record,
                                succeeded=success,
                                output=full_output_str,
                                duration_seconds=duration,  # Track duration
                                exit_code=exit_code,
                                version_info=filtered_version_info
                            )
                            logger.info(
                                f"Recorded update history for {len(packages_to_record)} packages (excluded {len(reinstalled_packages)} reinstalls)")

                            # Refresh update history panel if it exists and is visible
                            if 'history' in self.main_window.frames:
                                history_frame = self.main_window.frames['history']
                                # Force refresh to show new entry immediately
                                self.main_window.root.after(100, lambda: history_frame.load_history())
                                logger.info("Scheduled refresh of update history panel")
                        else:
                            logger.info("No update history recorded - all packages were reinstalls")

                except subprocess.TimeoutExpired:
                    self.main_window.root.after(0, lambda: status_label.config(text="❌ Installation timed out", foreground='red'))
                    self.main_window.update_status("Update timed out", "error")
                    try:
                        process.kill()
                    except BaseException:
                        pass
                except Exception as e:
                    logger.error(f"Error during pkexec update: {e}")
                    self.main_window.root.after(0, lambda e=e: status_label.config(text=f"❌ Error: {str(e)}", foreground='red'))
                    self.main_window.update_status(f"Update error: {str(e)}", "error")

                # Enable close button (schedule on main thread)
                self.main_window.root.after(0, lambda: close_btn.config(state='normal'))

                # Don't auto-close - let users read the output and close manually
                # This was previously auto-closing after 3 seconds which was too fast

            except Exception as e:
                logger.error(f"Failed to execute update with pkexec: {e}")
                error_msg = str(e)
                try:
                    self.main_window.root.after(0, lambda: messagebox.showerror("Update Error",
                                         f"Failed to execute update: {error_msg}\n\n"
                                         "Make sure pkexec is installed (polkit package)"))
                except Exception:
                    # In test environment, skip UI updates
                    pass
                def update_error_status():
                    self.main_window.update_status("Update failed: pkexec error", "error")
                try:
                    self.main_window.root.after(0, update_error_status)
                except Exception:
                    pass

        # Run in separate thread to avoid blocking UI using secure thread management
        import uuid
        thread_id = f"run_in_terminal_{uuid.uuid4().hex[:8]}"
        thread = ThreadResourceManager.create_managed_thread(
            thread_id=thread_id,
            target=run_in_terminal,
            is_background=True
        )
        if thread:
            thread.start()
        else:
            logger.warning("Could not create thread for terminal execution - thread limit reached")

    def go_back(self) -> None:
        """Return to dashboard."""
        self.main_window.show_frame('dashboard')

    def refresh_after_update(self, installed_packages: List[str]) -> None:
        """Remove successfully installed packages from the updates list.

        Args:
            installed_packages: List of package names that were successfully installed
        """
        logger.info(f"Refreshing updates list after installing: {installed_packages}")

        # Remove installed packages from our tracking
        for pkg in installed_packages:
            if pkg in self.packages:
                self.packages.remove(pkg)
            if pkg in self.selected_packages:
                self.selected_packages.discard(pkg)

        # If all packages have been installed, go back to dashboard
        if not self.packages:
            logger.info("All packages updated, returning to dashboard")
            
            # Mark that a full update was performed
            if 'dashboard' in self.main_window.frames:
                self.main_window.frames['dashboard']._mark_full_update()
            
            # Clear the update counts in checker
            if hasattr(self.main_window.checker, 'last_updates'):
                self.main_window.checker.last_updates = []
            if hasattr(self.main_window.checker, 'last_update_objects'):
                self.main_window.checker.last_update_objects = {}

            # Update dashboard to show no updates
            if 'dashboard' in self.main_window.frames:
                self.main_window.frames['dashboard'].update_stats_cards(0, 0)  # type: ignore[attr-defined]
                self.main_window.frames['dashboard'].refresh()  # type: ignore[attr-defined]

            # Show success message and go back
            self.main_window.update_status("✅ All updates installed successfully!", "success")
            self.go_back()
        else:
            # Some packages remain, rebuild the UI
            logger.info(f"Remaining packages to update: {self.packages}")

            # Update the checker's last_updates to reflect remaining packages
            if hasattr(self.main_window.checker, 'last_updates'):
                self.main_window.checker.last_updates = list(self.packages)

            # Update last_update_objects to remove installed packages
            if hasattr(self.main_window.checker, 'last_update_objects'):
                for pkg in installed_packages:
                    self.main_window.checker.last_update_objects.pop(pkg, None)

            # Update dashboard stats with new count
            if 'dashboard' in self.main_window.frames:
                remaining_count = len(self.packages)
                news_count = len(self.news_items) if self.news_items else 0
                self.main_window.frames['dashboard'].update_stats_cards(remaining_count, news_count)  # type: ignore[attr-defined]

            # Update the header count without rebuilding entire UI
            if hasattr(self, 'header_count_label'):
                self.header_count_label.config(text=f"{len(self.packages)} packages need updating")

            # Remove the package widgets for installed packages
            for widget in self.pkg_frame.winfo_children():
                if isinstance(widget, tk.Checkbutton):
                    # Extract package name from the widget text
                    widget_text = widget.cget('text')
                    pkg_name = widget_text.split(' (')[0]  # Remove version info if present
                    if pkg_name in installed_packages:
                        widget.destroy()
                        # Also remove from pkg_vars
                        self.pkg_vars.pop(pkg_name, None)

            # Update news display to reflect new selection
            self.update_news_display()

            # Show success message for partial update
            installed_count = len(installed_packages)
            remaining_count = len(self.packages)
            # Create two-line status message
            # Using ✓ instead of emoji for consistent rendering
            status_msg = f"✓ {installed_count} package(s) updated\n    {remaining_count} remaining"
            self.main_window.update_status(status_msg, "success")

    def refresh_theme(self) -> None:
        """Refresh the frame with new theme colors."""
        self._build_ui()
