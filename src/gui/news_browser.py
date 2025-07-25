"""
News browser frame for the Arch Smart Update Checker GUI.
"""

# SPDX-License-Identifier: GPL-3.0-or-later

import tkinter as tk
import os
from tkinter import ttk, messagebox, scrolledtext
from typing import Dict, Any, List, Optional
import threading
from datetime import datetime
import webbrowser

# Add src to path for imports
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from ..news_fetcher import NewsFetcher
from ..config import Config
from .window_mixin import WindowPositionMixin
from ..utils.logger import get_logger
from .dimensions import get_dimensions

logger = get_logger(__name__)


class NewsBrowserFrame(ttk.Frame, WindowPositionMixin):
    """Modern news browser with filtering and search capabilities."""

    def __init__(self, parent, main_window):
        """Initialize the news browser frame."""
        try:
            super().__init__(parent)
        except Exception:
            temp_root = tk.Tk()
            temp_root.withdraw()
            super().__init__(temp_root)
        self.main_window = main_window
        self.news_fetcher = main_window.checker.news_fetcher
        self.config = main_window.config
        self.dims = get_dimensions()

        # Check if we're in a test environment
        self.is_testing = 'pytest' in sys.modules or 'unittest' in sys.modules

        # Initialize news items storage
        self.all_news_items = []
        self.news_items = []

        self.setup_ui()
        self.load_news()

    def setup_ui(self):
        """Setup the news browser UI."""
        # Main container
        main_container = ttk.Frame(self, style='Content.TFrame')
        main_container.pack(fill='both', expand=True, padx=20, pady=20)

        # Header
        self.create_header(main_container)

        # Search and filter bar
        self.create_search_bar(main_container)

        # News content area
        self.create_news_area(main_container)

    def create_header(self, parent):
        """Create the header section."""
        header_frame = ttk.Frame(parent, style='Card.TFrame')
        header_frame.pack(fill='x', pady=(0, 20))

        # Title and controls
        title_frame = ttk.Frame(header_frame, style='Card.TFrame')
        title_frame.pack(fill='x', padx=20, pady=20)

        title_label = tk.Label(title_frame,
                              text="📰 News Browser",
                              font=('Segoe UI', 20, 'bold'),
                              fg=self.main_window.colors['text'],
                              bg=self.main_window.colors['surface'])
        title_label.pack(side='left')

        # Status label
        self.status_label = tk.Label(title_frame,
                                    text="Ready",
                                    font=('Segoe UI', 10, 'normal'),
                                    fg=self.main_window.colors['text_secondary'],
                                    bg=self.main_window.colors['surface'])
        self.status_label.pack(side='right', padx=(0, 20))

        # Control buttons
        controls_frame = ttk.Frame(title_frame, style='Card.TFrame')
        controls_frame.pack(side='right')

        refresh_btn = tk.Button(controls_frame,
                               text="🔄 Refresh",
                               font=self.dims.font('Segoe UI', 'normal'),
                               fg='white',
                               bg=self.main_window.colors['primary'],
                               activebackground=self.main_window.colors['primary_hover'],
                               activeforeground='white',
                               bd=0,
                               padx=self.dims.button_padx,
                               pady=self.dims.button_pady,
                               cursor='hand2',
                               command=self.refresh_news)
        refresh_btn.pack(side='left', padx=(0, 10))

        settings_btn = tk.Button(controls_frame,
                                text="⚙️ Feeds",
                                font=('Segoe UI', 11, 'normal'),
                                fg=self.main_window.colors['text'],
                                bg=self.main_window.colors['surface'],
                                activebackground=self.main_window.colors['border'],
                                bd=1,
                                relief='solid',
                                padx=15,
                                pady=8,
                                cursor='hand2',
                                command=self.show_feed_settings)
        settings_btn.pack(side='left')

    def create_search_bar(self, parent):
        """Create the search and filter bar."""
        search_frame = ttk.Frame(parent, style='Card.TFrame')
        search_frame.pack(fill='x', pady=(0, 20))

        # Search input
        search_container = ttk.Frame(search_frame, style='Card.TFrame')
        search_container.pack(fill='x', padx=20, pady=15)

        search_label = tk.Label(search_container,
                               text="🔍 Search:",
                               font=('Segoe UI', 12, 'normal'),
                               fg=self.main_window.colors['text'],
                               bg=self.main_window.colors['surface'])
        search_label.pack(side='left', padx=(0, 10))

        self.search_var = tk.StringVar(master=self)
        self.search_var.trace('w', self.on_search_change)

        search_entry = tk.Entry(search_container,
                               textvariable=self.search_var,
                               font=('Segoe UI', 11, 'normal'),
                               bg=self.main_window.colors['surface'],
                               fg=self.main_window.colors['text'],
                               insertbackground=self.main_window.colors['text'],
                               relief='solid',
                               bd=1)
        search_entry.pack(side='left', fill='x', expand=True, padx=(0, 10))

        # Filter options
        filter_frame = ttk.Frame(search_container, style='Card.TFrame')
        filter_frame.pack(side='right')

        filter_label = tk.Label(filter_frame,
                               text="Filter:",
                               font=('Segoe UI', 11, 'normal'),
                               fg=self.main_window.colors['text_secondary'],
                               bg=self.main_window.colors['surface'])
        filter_label.pack(side='left', padx=(0, 5))

        self.filter_var = tk.StringVar(master=self, value="all")
        filter_combo = ttk.Combobox(filter_frame,
                                   textvariable=self.filter_var,
                                   values=["all", "critical", "high", "medium", "low"],
                                   state="readonly",
                                   font=('Segoe UI', 10, 'normal'),
                                   width=10)
        filter_combo.pack(side='left')
        filter_combo.bind('<<ComboboxSelected>>', self.on_filter_change)

    def create_news_area(self, parent):
        """Create the news display area."""
        # News container with scroll
        news_container = ttk.Frame(parent, style='Card.TFrame')
        news_container.pack(fill='both', expand=True)

        # Create canvas for scrolling
        self.news_canvas = tk.Canvas(news_container, bg=self.main_window.colors['background'])
        self.news_scrollbar = ttk.Scrollbar(news_container, orient="vertical", command=self.news_canvas.yview)
        self.news_frame = ttk.Frame(self.news_canvas, style='Content.TFrame')

        self.news_frame.bind(
            "<Configure>",
            lambda e: (self.news_canvas.configure(scrollregion=self.news_canvas.bbox("all")), self._update_scrollbar_visibility())
        )

        self.news_canvas.create_window((0, 0), window=self.news_frame, anchor="nw")
        self.news_canvas.configure(yscrollcommand=self.news_scrollbar.set)

        # Pack scroll components
        self.news_canvas.pack(side="left", fill="both", expand=True)
        self.news_scrollbar.pack(side="right", fill="y")

        # Bind mouse wheel (cross-platform)
        self.news_canvas.bind("<Enter>", lambda e: self.news_canvas.focus_set())
        self.news_canvas.bind("<MouseWheel>", self._on_mousewheel)
        self.news_canvas.bind("<Button-4>", self._on_mousewheel)
        self.news_canvas.bind("<Button-5>", self._on_mousewheel)

    def load_news(self):
        """Load news items from feeds."""
        if os.getenv('PYTEST_CURRENT_TEST') is not None:
            # Skip heavy network calls during tests
            self.news_items = []
            self.all_news_items = []  # Store all items for filtering
            return
        feeds = self.main_window.config.get_feeds()
        active_feeds = [feed for feed in feeds if feed.get('enabled', True)]

        def load_thread():
            try:
                news_fetcher = NewsFetcher(self.main_window.config, self.main_window.checker)
                news_items = news_fetcher.fetch_news()
                self.all_news_items = news_items  # Store all items for filtering
                self.news_items = news_items
                self.main_window.root.after(0, lambda: self.display_filtered_news())
            except Exception as e:
                logger.error(f"Failed to load news: {e}")
                self.main_window.root.after(0, lambda: self.status_label.configure(text=f"Error loading news: {str(e)}"))

        self.status_label.configure(text=f"Loading news from {len(active_feeds)} feeds...")
        
        # Use secure thread management
        from ..utils.thread_manager import create_managed_thread
        import uuid
        
        thread_id = f"news_load_{uuid.uuid4().hex[:8]}"
        thread = create_managed_thread(thread_id, load_thread, is_background=True)
        if thread is None:
            self.status_label.configure(text="Error: Unable to load news - thread limit reached")

    def display_filtered_news(self):
        """Display news items with search and severity filtering applied."""
        # Get filter criteria
        search_text = self.search_var.get().lower().strip()
        severity_filter = self.filter_var.get()
        
        # Filter news items
        filtered_items = []
        for item in self.all_news_items:
            # Apply search filter
            if search_text:
                # Search in title, description, and link
                searchable_text = (
                    item.get('title', '').lower() + ' ' +
                    item.get('description', '').lower() + ' ' +
                    item.get('link', '').lower()
                )
                if search_text not in searchable_text:
                    continue
            
            # Apply severity filter
            if severity_filter != 'all':
                item_severity = self._determine_severity(item)
                if item_severity.lower() != severity_filter.lower():
                    continue
            
            filtered_items.append(item)
        
        # Update status
        if self.all_news_items:
            status_text = f"Showing {len(filtered_items)} of {len(self.all_news_items)} news items"
            if search_text:
                status_text += f" matching '{search_text}'"
            if severity_filter != 'all':
                status_text += f" ({severity_filter} severity)"
            self.status_label.configure(text=status_text)
        
        # Display filtered items
        self.display_news(filtered_items)

    def _determine_severity(self, item: Dict[str, Any]) -> str:
        """Determine the severity of a news item based on keywords."""
        title = item.get('title', '').lower()
        description = item.get('description', '').lower()
        combined_text = title + ' ' + description
        
        # Keywords for different severity levels
        critical_keywords = ['critical', 'urgent', 'emergency', 'vulnerability', 'exploit', 'zero-day', 'breach']
        high_keywords = ['important', 'security', 'update required', 'mandatory', 'breaking change']
        medium_keywords = ['update', 'change', 'deprecated', 'migration', 'upgrade']
        low_keywords = ['announcement', 'release', 'available', 'feature']
        
        # Check for severity keywords
        for keyword in critical_keywords:
            if keyword in combined_text:
                return 'Critical'
        
        for keyword in high_keywords:
            if keyword in combined_text:
                return 'High'
        
        for keyword in medium_keywords:
            if keyword in combined_text:
                return 'Medium'
        
        # Default to low
        return 'Low'

    def display_news(self, news_items: List[Dict[str, Any]]):
        """Display news items in the UI."""
        # Clear existing content
        for widget in self.news_frame.winfo_children():
            widget.destroy()

        if not news_items:
            no_items_label = tk.Label(self.news_frame,
                                     text="No news items found",
                                     font=('Segoe UI', 12, 'normal'),
                                     fg=self.main_window.colors['text_secondary'],
                                     bg=self.main_window.colors['background'])
            no_items_label.pack(pady=50)
            return

        # Display news items
        for i, item in enumerate(news_items):
            news_card = self.create_news_card(item)
            news_card.pack(fill='x', padx=20, pady=10)

            # Add separator
            if i < len(news_items) - 1:
                separator = ttk.Frame(self.news_frame, height=1, style='Card.TFrame')
                separator.pack(fill='x', padx=40, pady=5)

    def create_news_card(self, item: Dict[str, Any]) -> ttk.Frame:
        """Create a news item card."""
        card = ttk.Frame(self.news_frame, style='Card.TFrame')

        # Card content
        content_frame = ttk.Frame(card, style='Card.TFrame')
        content_frame.pack(fill='x', padx=20, pady=15)

        # Header row
        header_frame = ttk.Frame(content_frame, style='Card.TFrame')
        header_frame.pack(fill='x', pady=(0, 10))

        # Title
        title = item.get('title', 'Unknown Title')
        title_label = tk.Label(header_frame,
                              text=title,
                              font=('Segoe UI', 14, 'bold'),
                              fg=self.main_window.colors['text'],
                              bg=self.main_window.colors['surface'],
                              wraplength=600,
                              justify='left')
        title_label.pack(anchor='w')

        # Meta information
        meta_frame = ttk.Frame(content_frame, style='Card.TFrame')
        meta_frame.pack(fill='x', pady=(0, 10))

        # Date
        published = item.get('published', 'Unknown date')
        date_label = tk.Label(meta_frame,
                             text=f"📅 {published}",
                             font=('Segoe UI', 10, 'normal'),
                             fg=self.main_window.colors['text_secondary'],
                             bg=self.main_window.colors['surface'])
        date_label.pack(side='left')

        # Feed source
        feed = item.get('feed', 'Unknown feed')
        feed_label = tk.Label(meta_frame,
                             text=f"📡 {feed}",
                             font=('Segoe UI', 10, 'normal'),
                             fg=self.main_window.colors['text_secondary'],
                             bg=self.main_window.colors['surface'])
        feed_label.pack(side='left', padx=(20, 0))

        # Severity indicator
        severity = self._determine_severity(item)
        severity_colors = {
            'Critical': self.main_window.colors['error'],
            'High': self.main_window.colors['warning'],
            'Medium': self.main_window.colors['secondary'],
            'Low': self.main_window.colors['success']
        }
        severity_color = severity_colors.get(severity, self.main_window.colors['secondary'])
        
        severity_label = tk.Label(meta_frame,
                                 text=f"● {severity}",
                                 font=('Segoe UI', 10, 'bold'),
                                 fg=severity_color,
                                 bg=self.main_window.colors['surface'])
        severity_label.pack(side='left', padx=(20, 0))

        # Description
        description = item.get('description', 'No description available')
        desc_label = tk.Label(content_frame,
                             text=description,
                             font=('Segoe UI', 11, 'normal'),
                             fg=self.main_window.colors['text'],
                             bg=self.main_window.colors['surface'],
                             wraplength=600,
                             justify='left')
        desc_label.pack(anchor='w', pady=(0, 10))

        # Action buttons
        actions_frame = ttk.Frame(content_frame, style='Card.TFrame')
        actions_frame.pack(fill='x')

        # Link button
        link = item.get('link', '')
        if link:
            link_btn = tk.Button(actions_frame,
                                text="🔗 Open Link",
                                font=('Segoe UI', 10, 'normal'),
                                fg=self.main_window.colors['primary'],
                                bg=self.main_window.colors['surface'],
                                activebackground=self.main_window.colors['border'],
                                bd=1,
                                relief='solid',
                                padx=12,
                                pady=4,
                                cursor='hand2',
                                command=lambda: self.open_link(link))
            link_btn.pack(side='left')

        # Package info button
        packages = item.get('packages', [])
        if packages:
            pkg_btn = tk.Button(actions_frame,
                               text=f"📦 {len(packages)} Packages",
                               font=('Segoe UI', 10, 'normal'),
                               fg=self.main_window.colors['success'],
                               bg=self.main_window.colors['surface'],
                               activebackground=self.main_window.colors['border'],
                               bd=1,
                               relief='solid',
                               padx=12,
                               pady=4,
                               cursor='hand2',
                               command=lambda: self.show_packages(packages))
            pkg_btn.pack(side='left', padx=(10, 0))

        return card

    def refresh_news(self):
        """Refresh the news feed."""
        self.status_label.configure(text="Refreshing news...")
        self.load_news()

    def on_search_change(self, *args):
        """Handle search text changes."""
        # Apply filtering when search text changes
        if hasattr(self, 'all_news_items'):
            self.display_filtered_news()

    def on_filter_change(self, event):
        """Handle filter selection changes."""
        # Apply filtering when severity filter changes
        if hasattr(self, 'all_news_items'):
            self.display_filtered_news()

    def show_feed_settings(self):
        """Show feed configuration dialog."""
        messagebox.showinfo("Feed Settings", "Feed configuration will be available in the Settings panel.")

    def open_link(self, url: str):
        """Open a news link in the default browser."""
        import webbrowser
        try:
            webbrowser.open(url)
        except Exception as exc:
            messagebox.showerror("Error", f"Failed to open link: {exc}")

    def show_packages(self, packages: List[str]):
        """Show package information."""
        if not packages:
            return

        # Create package info window
        pkg_window = tk.Toplevel(self)
        pkg_window.title("Affected Packages")
        pkg_window.configure(bg=self.main_window.colors['background'])

        # Use proper positioning
        self.position_window(pkg_window, 500, 400, self.main_window.root)

        # Package list
        listbox = tk.Listbox(pkg_window,
                            font=('Segoe UI', 11, 'normal'),
                            bg=self.main_window.colors['surface'],
                            fg=self.main_window.colors['text'],
                            selectbackground=self.main_window.colors['primary'],
                            selectforeground='white')
        listbox.pack(fill='both', expand=True, padx=20, pady=20)

        for pkg in packages:
            listbox.insert(tk.END, pkg)

    def show_error(self, message: str):
        """Show error message."""
        self.status_label.configure(text=f"Error: {message}")

    def _on_mousewheel(self, event):
        """Handle mouse wheel scrolling."""
        if hasattr(event, 'delta') and event.delta:
            self.news_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        else:
            if event.num == 4:
                self.news_canvas.yview_scroll(-1, "units")
            elif event.num == 5:
                self.news_canvas.yview_scroll(1, "units")

    def refresh_theme(self):
        """Re-apply theme/colors to all widgets in this frame."""
        for widget in self.winfo_children():
            widget.destroy()
        self.setup_ui()
        self.load_news()

    # -----------------------
    # Scrollbar visibility helper
    # -----------------------

    def _update_scrollbar_visibility(self):
        try:
            bbox = self.news_canvas.bbox("all")
            if not bbox:
                return
            content_height = bbox[3]
            visible_height = self.news_canvas.winfo_height()
            if content_height <= visible_height:
                self.news_scrollbar.pack_forget()
            else:
                if not self.news_scrollbar.winfo_ismapped():
                    self.news_scrollbar.pack(side="right", fill="y")
        except Exception:
            pass
