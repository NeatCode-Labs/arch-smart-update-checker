"""
Dashboard frame for the Arch Smart Update Checker GUI.
"""

# SPDX-License-Identifier: GPL-3.0-or-later

import tkinter as tk
from tkinter import ttk, messagebox
from typing import Dict, Any, List, TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from .main_window import MainWindow
from datetime import datetime
import os

from ..checker import UpdateChecker
from ..config import Config
from ..utils.timer_manager import TimerResourceManager, create_delayed_callback, create_repeating_timer
from ..utils.pacman_runner import PacmanRunner
from ..utils.logger import get_logger
from .dimensions import get_dimensions

logger = get_logger(__name__)


class DashboardFrame(ttk.Frame):
    """Modern dashboard with overview cards and widgets."""

    def __init__(self, parent: tk.Widget, main_window: "MainWindow") -> None:
        """Initialize the dashboard frame."""
        # Some tests pass a Mock as parent which Tk cannot accept.
        try:
            super().__init__(parent)
        except Exception:
            temp_root = tk.Tk()
            temp_root.withdraw()
            super().__init__(temp_root)
        self.main_window = main_window
        self.checker = main_window.checker
        self._config = main_window.config
        self.dims = get_dimensions()

        # Stats file for non-update persistence (total packages, etc.)
        import os
        self.stats_file = os.path.expanduser("~/.cache/arch-smart-update-checker/dashboard_stats.json")

        # Session-only update count (not persisted across restarts)
        self.session_updates_count = None

        self.setup_ui()
        self.refresh()

    def setup_ui(self) -> None:
        """Setup the dashboard UI."""
        # Main container - no scroll needed for fixed window
        self.canvas = tk.Canvas(self, bg=self.main_window.colors['background'], highlightthickness=0)
        self.scrollable_frame = ttk.Frame(self.canvas, style='Content.TFrame')

        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        )

        self.canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")

        # Pack only the canvas - no scrollbar
        self.canvas.pack(fill="both", expand=True)

        # Create dashboard content
        self.create_header()
        self.create_stats_cards()
        self.create_quick_actions()
        self.create_system_info()

    def create_header(self) -> None:
        """Create the dashboard header."""
        # Use scaled font sizes - more compact for small screens
        title_font_size = self.dims.scale(20) if self.dims.window_size[0] < 1000 else self.dims.scale(24)
        subtitle_font_size = self.dims.scale(12) if self.dims.window_size[0] < 1000 else self.dims.scale(14)

        # Header container - directly on background, not in a card
        header_frame = ttk.Frame(self.scrollable_frame, style='Content.TFrame')
        header_frame.pack(fill='x', padx=self.dims.pad_large, pady=(self.dims.pad_large, self.dims.pad_medium))

        # Title
        title_label = tk.Label(header_frame,
                               text="📊 Dashboard",
                               font=('Segoe UI', title_font_size, 'bold'),
                               fg=self.main_window.colors['text'],
                               bg=self.main_window.colors['background'])
        title_label.pack(anchor='w', padx=self.dims.pad_large, pady=(self.dims.pad_large, self.dims.pad_medium))

        # Subtitle
        subtitle_label = tk.Label(header_frame,
                                  text="System overview and quick actions",
                                  font=('Segoe UI', subtitle_font_size, 'normal'),
                                  fg=self.main_window.colors['text_secondary'],
                                  bg=self.main_window.colors['background'])
        subtitle_label.pack(anchor='w', padx=self.dims.pad_large, pady=(0, self.dims.pad_large))

    def create_stats_cards(self) -> None:
        """Create statistics cards."""
        stats_frame = ttk.Frame(self.scrollable_frame, style='Content.TFrame')
        stats_frame.pack(fill='x', padx=0, pady=self.dims.pad_medium)

        # Stats cards container - align with other sections
        cards_frame = ttk.Frame(stats_frame, style='Content.TFrame')
        cards_frame.pack(fill='x', padx=(self.dims.pad_large, 20))  # Match right padding with other sections

        # Create stat cards with fixed layout
        self.stats_cards = {}
        self.cards_frame = cards_frame  # Store reference for card configuration
        stats = [
            ("📦 Total Packages", "0", "Total installed packages"),
            ("🔄 Available Updates", "—", "Packages with updates since last check"),
            ("⚠️ Issues Found", "0", "Potential update issues"),
            ("📰 News Items", "0", "Recent news articles"),
        ]

        for i, (title, value, description) in enumerate(stats):
            card = self.create_stat_card(cards_frame, title, value, description)
            # Consistent padding between cards
            padx = (0, 10) if i < len(stats) - 1 else (0, 0)  # No right padding on last card
            card.grid(row=0, column=i, sticky='nsew', padx=padx, pady=0)
            self.stats_cards[title] = card

        # Configure grid layout - make columns expand equally
        for i in range(len(stats)):
            # Smaller minimum size for compact layout
            min_card_width = self.dims.scale(180) if self.dims.window_size[0] < 1000 else self.dims.scale(225)
            cards_frame.grid_columnconfigure(i, weight=1, minsize=min_card_width)

        # Configure card layout
        self._configure_card_layout()

    def create_stat_card(self, parent: tk.Widget, title: str, value: str, description: str) -> ttk.Frame:
        """Create a single statistics card."""
        card = ttk.Frame(parent, style='Card.TFrame')

        CARD_H = self.dims.card_height
        PAD = self.dims.card_padding
        # Calculate wrap based on actual card width minus padding
        # Smaller wrap for compact layout
        base_wrap = 180 if self.dims.window_size[0] < 1000 else 225
        WRAP = max(120, self.dims.scale(base_wrap) - (2 * PAD))

        # Set a minimum height but allow expansion if needed
        card.configure(height=CARD_H)
        card.pack_propagate(False)  # Prevent frame from shrinking to fit content

        # Card content
        content_frame = ttk.Frame(card, style='Card.TFrame')
        content_frame.pack(fill='both', expand=True, padx=PAD, pady=PAD)

        # Title
        title_label = tk.Label(content_frame,
                               text=title,
                               font=self.dims.font('Segoe UI', 'small'),  # Reduced from medium
                               fg=self.main_window.colors['text_secondary'],
                               bg=self.main_window.colors['surface'],
                               wraplength=WRAP,
                               justify='left')
        title_label.pack(anchor='w')
        card.title_label = title_label  # type: ignore[attr-defined]  # store reference for wrap update

        # Value
        value_label = tk.Label(content_frame,
                               text=value,
                               font=self.dims.font('Segoe UI', 'large', 'bold'),  # Reduced from xlarge
                               fg=self.main_window.colors['primary'],
                               bg=self.main_window.colors['surface'])
        value_label.pack(anchor='w', pady=(5, 2))  # Reduced padding to make room

        # Description with consistent wraplength
        desc_label = tk.Label(content_frame,
                              text=description,
                              font=self.dims.font('Segoe UI', 'tiny'),  # Smaller font
                              fg=self.main_window.colors['text_secondary'],
                              bg=self.main_window.colors['surface'],
                              wraplength=WRAP,
                              anchor='nw',
                              justify='left')
        desc_label.pack(anchor='w', fill='x')

        # Store references for updates
        card.value_label = value_label  # type: ignore[attr-defined]
        card.desc_label = desc_label  # type: ignore[attr-defined]
        card.title = title  # type: ignore[attr-defined]

        # Make clickable for issues and news
        if "Issues Found" in title or "News Items" in title:
            # Change cursor and add click handler
            for widget in [card, content_frame, title_label, value_label, desc_label]:
                widget.configure(cursor='hand2')  # type: ignore[call-arg]
                widget.bind("<Button-1>", lambda e, t=title: self.on_card_click(t))  # type: ignore[misc]

        return card

    def create_quick_actions(self) -> None:
        """Create quick action buttons."""
        actions_frame = ttk.Frame(self.scrollable_frame, style='Card.TFrame')
        # Minimal right padding for maximum content space
        right_pad = 20  # Fixed small padding
        actions_frame.pack(fill='x', padx=(self.dims.pad_large, right_pad), pady=self.dims.pad_medium)

        # Header
        header_label = tk.Label(actions_frame,
                                text="Quick Actions",
                                font=self.dims.font('Segoe UI', 'large', 'bold'),
                                fg=self.main_window.colors['text'],
                                bg=self.main_window.colors['surface'])
        header_label.pack(anchor='w', padx=self.dims.pad_large, pady=(self.dims.pad_large, self.dims.pad_medium))

        # Buttons container - align with header text
        buttons_frame = ttk.Frame(actions_frame, style='Card.TFrame')
        buttons_frame.pack(fill='x', padx=self.dims.pad_large, pady=(0, self.dims.pad_large))

        # Create a grid layout for buttons with equal column widths
        buttons_container = ttk.Frame(buttons_frame, style='Card.TFrame')
        buttons_container.pack(fill='x', anchor='w')  # Left-align the container

        # Configure grid to have equal column widths
        buttons_container.grid_columnconfigure(0, weight=0)  # Left column - no expansion
        buttons_container.grid_columnconfigure(1, weight=1)  # Right column - expand to fill

        # Calculate button width based on screen size
        # Use smaller width for compact screens, larger for normal screens
        button_width = 18 if self.dims.window_size[0] < 1100 else 20  # Adaptive character width

        # Left column for Check and Update All buttons (stacked vertically) - aligned with text
        left_column = ttk.Frame(buttons_container, style='Card.TFrame')
        left_column.grid(row=0, column=0, sticky='nw', padx=(0, self.dims.pad_medium))

        # Check for Updates button
        self.check_button = tk.Button(left_column,
                                      text="🔄 Check for Updates",
                                      font=self.dims.font('Segoe UI', 'medium'),
                                      fg='white',
                                      bg=self.main_window.colors['primary'],
                                      activebackground=self.main_window.colors['primary'],
                                      activeforeground='white',
                                      bd=0,
                                      padx=self.dims.button_padx,
                                      pady=self.dims.button_pady,
                                      cursor='hand2',
                                      width=button_width,
                                      command=self.check_updates)
        self.check_button.pack(pady=(0, self.dims.pad_medium))

        # Update All button below Check for Updates
        # Add container to align with database sync info
        update_all_container = ttk.Frame(left_column, style='Card.TFrame')
        update_all_container.pack(fill='x', pady=(self.dims.pad_small, 0))  # Same padding as db_sync_container

        # Calculate vertical offset to center button with two-line text
        # Text has: small font label + normal font value + line spacing
        # Button should be centered with the midpoint of these two lines
        text_height_estimate = self.dims.font_small + self.dims.font_normal + self.dims.pad_small
        button_height_estimate = self.dims.font_medium + (2 * self.dims.button_pady)
        vertical_offset = max(0, (text_height_estimate - button_height_estimate) // 2)
        # Add extra offset to move button down more for better visual alignment
        vertical_offset += self.dims.pad_small

        self.update_all_button = tk.Button(update_all_container,
                                           text="⬆️ Update All",
                                           font=self.dims.font('Segoe UI', 'medium'),
                                           fg='white',
                                           bg=self.main_window.colors['primary'],
                                           activebackground=self.main_window.colors['primary'],
                                           activeforeground='white',
                                           bd=0,
                                           padx=self.dims.button_padx,
                                           pady=self.dims.button_pady,
                                           cursor='hand2',
                                           width=button_width,
                                           command=self.update_all_packages)
        self.update_all_button.pack(pady=(vertical_offset, 0))
        # Add tooltip to update all button with warning
        self._add_tooltip(
            self.update_all_button,
            "Update all packages on the system (pacman -Syu)\n\n⚠️ WARNING: This will directly update the system without\nretrieving or displaying potentially important news items.\nConsider using 'Check for Updates' first to see news.")

        # Right column for Last full update info (expands to fill remaining space)
        right_column = ttk.Frame(buttons_container, style='Card.TFrame')
        right_column.grid(row=0, column=1, sticky='new', padx=(self.dims.pad_medium, 0))

        # Last full update container (aligned with update all button)
        last_update_container = ttk.Frame(right_column, style='Card.TFrame')
        last_update_container.pack(fill='x', pady=(self.dims.pad_small, 0))  # Aligned below where sync button was

        # Last full update label (first line) - centered
        last_update_label_text = tk.Label(last_update_container,
                                      text="Last full update:",
                                      font=self.dims.font('Segoe UI', 'small'),
                                      fg=self.main_window.colors['text_secondary'],
                                      bg=self.main_window.colors['surface'])
        last_update_label_text.pack()

        # Last full update time value (second line) - centered
        self.last_full_update_label = tk.Label(last_update_container,
                                           text="Never",
                                           font=self.dims.font('Segoe UI', 'normal', 'bold'),
                                           fg=self.main_window.colors['text'],
                                           bg=self.main_window.colors['surface'])
        self.last_full_update_label.pack()

        # Status label below buttons (second row)
        self.status_label = tk.Label(buttons_frame,
                                     text="",
                                     font=self.dims.font('Segoe UI', 'normal'),
                                     fg=self.main_window.colors['text_secondary'],
                                     bg=self.main_window.colors['surface'])
        self.status_label.pack(anchor='w', pady=(self.dims.pad_small, 0))

        # Update database sync time
        self.update_database_sync_time()

        # Animation state
        self.dots_count = 0
        self.animation_timer_id: Optional[str] = None  # Store timer ID instead of raw timer
        self._component_id = f"dashboard_{id(self)}"  # Unique component ID for timer management

    def create_system_info(self) -> None:
        """Create system information section."""
        info_frame = ttk.Frame(self.scrollable_frame, style='Card.TFrame')
        right_pad = 20  # Fixed small padding
        info_frame.pack(
            fill='x', padx=(
                self.dims.pad_large, right_pad), pady=(
                self.dims.pad_large, self.dims.scale(30)))

        # Header
        header_label = tk.Label(info_frame,
                                text="System Information",
                                font=self.dims.font('Segoe UI', 'large', 'bold'),
                                fg=self.main_window.colors['text'],
                                bg=self.main_window.colors['surface'])
        header_label.pack(anchor='w', padx=self.dims.pad_large, pady=(self.dims.pad_large, self.dims.pad_medium))

        # Info content
        info_content = ttk.Frame(info_frame, style='Card.TFrame')
        info_content.pack(fill='x', padx=self.dims.pad_large, pady=(0, self.dims.pad_large))

        # System info labels
        self.system_labels = {}
        system_info = [
            ("System", "Arch Linux"),
            ("Last Check", "Never"),
            ("Cache Status", "Unknown"),
            ("Config File", "Default")
        ]

        for i, (label, value) in enumerate(system_info):
            row_frame = ttk.Frame(info_content, style='Card.TFrame')
            row_frame.pack(fill='x', pady=self.dims.scale(2))

            label_widget = tk.Label(row_frame,
                                    text=f"{label}:",
                                    font=self.dims.font('Segoe UI', 'normal', 'bold'),
                                    fg=self.main_window.colors['text'],
                                    bg=self.main_window.colors['surface'],
                                    width=self.dims.scale(15),
                                    anchor='w')
            label_widget.pack(side='left')

            value_widget = tk.Label(row_frame,
                                    text=value,
                                    font=self.dims.font('Segoe UI', 'normal'),
                                    fg=self.main_window.colors['text_secondary'],
                                    bg=self.main_window.colors['surface'],
                                    anchor='w')
            value_widget.pack(side='left', padx=(10, 0))

            self.system_labels[label] = value_widget

    def animate_dots(self) -> None:
        """Animate the dots in the status label."""
        if self.animation_timer_id is None:
            return

        dots = "." * (self.dots_count % 4)
        self.status_label.configure(text=f"Checking for updates{dots}")
        self.dots_count += 1

        # Schedule next animation using simple tkinter after()
        if self.animation_timer_id is not None:
            self.scrollable_frame.after(500, self.animate_dots)

    def start_checking_animation(self) -> None:
        """Start the checking animation."""
        self.dots_count = 0
        self.status_label.configure(text="Checking for updates")
        self.check_button.configure(state='disabled')
        # Use simple tkinter after() for animation - more reliable than timer system
        self.animation_timer_id = "simple_animation"  # Flag to indicate animation is running
        self.animate_dots()  # Start the animation

    def stop_checking_animation(self, message: str = "", success: bool = True) -> None:
        """Stop the checking animation."""
        # Stop animation
        self.animation_timer_id = None
        self.check_button.configure(state='normal')

        if message:
            color = self.main_window.colors['success'] if success else self.main_window.colors['error']
            self.status_label.configure(text=message, fg=color)
            # Clear message after 3 seconds using managed timer
            create_delayed_callback(
                root=self.scrollable_frame,
                delay_ms=3000,
                callback=lambda: self.status_label.configure(text=""),
                component_id=self._component_id
            )

    def check_updates(self) -> None:
        """Check for updates."""
        # Start animation
        self.start_checking_animation()

        # Update last check timestamp
        try:
            cache_dir = os.path.expanduser("~/.cache/arch-smart-update-checker")
            os.makedirs(cache_dir, exist_ok=True)
            last_check_file = os.path.join(cache_dir, "last_check")
            with open(last_check_file, 'w') as f:
                f.write(str(datetime.now().timestamp()))
        except Exception:
            pass

        self.main_window.run_check()

        # Refresh to show new last check time
        self.refresh()

        # No need to update database sync time anymore since it's integrated



        # Function to update progress (thread-safe)
        def update_progress(text):
            progress_text.insert('end', text + '\n')
            progress_text.see('end')
            progress_text.update_idletasks()

    def update_all_packages(self):
        """Update all packages on the system."""
        if messagebox.askyesno("Confirm Update",
                               "Are you sure you want to update all packages?\n\n"
                               "This will run 'sudo pacman -Syu' and may take some time."):
            # Track that a full update is being performed
            self._mark_full_update()
            
            # Get the package manager frame and call its run_pacman_update method
            if 'packages' in self.main_window.frames:
                package_frame = self.main_window.frames['packages']
                package_frame.run_pacman_update()
            else:
                # Fallback: create a temporary package manager instance
                from .package_manager import PackageManagerFrame
                temp_frame = PackageManagerFrame(self, self.main_window)
                temp_frame.run_pacman_update()

    def _mark_full_update(self):
        """Mark that a full update has been performed."""
        try:
            import time
            cache_dir = os.path.expanduser("~/.cache/arch-smart-update-checker")
            os.makedirs(cache_dir, exist_ok=True)
            last_update_file = os.path.join(cache_dir, "last_full_update")
            with open(last_update_file, 'w') as f:
                f.write(str(time.time()))
            # Update the display immediately
            self.update_last_full_update_time()
        except Exception as e:
            logger.warning(f"Failed to mark full update: {e}")

    def update_last_full_update_time(self):
        """Update the last full update time label."""
        try:
            logger.debug("Updating last full update time display...")
            # First check pacman log for external updates
            from ..utils.pacman_runner import PacmanRunner
            external_update_time = PacmanRunner.get_last_full_update_time()
            logger.debug(f"External update time from pacman log: {external_update_time}")
            
            # Then check our app's tracked update time
            cache_dir = os.path.expanduser("~/.cache/arch-smart-update-checker")
            last_update_file = os.path.join(cache_dir, "last_full_update")
            
            app_update_time = None
            if os.path.exists(last_update_file):
                with open(last_update_file, 'r') as f:
                    timestamp = float(f.read().strip())
                    app_update_time = datetime.fromtimestamp(timestamp)
            
            # Use the most recent update time from either source
            if external_update_time and app_update_time:
                # Both exist, use the more recent one
                update_time = max(external_update_time, app_update_time)
                logger.debug(f"External update: {external_update_time}, App update: {app_update_time}, Using: {update_time}")
            elif external_update_time:
                # Only external update exists
                update_time = external_update_time
                logger.debug(f"Using external update time: {update_time}")
            elif app_update_time:
                # Only app update exists
                update_time = app_update_time
                logger.debug(f"Using app update time: {update_time}")
            else:
                # No update found
                self.last_full_update_label.configure(text="Never")
                return
            
            # Format as ISO date and time (YYYY-MM-DD HH:MM:SS)
            iso_time = update_time.strftime('%Y-%m-%d %H:%M:%S')
            self.last_full_update_label.configure(text=iso_time)
            logger.debug(f"Updated last full update display to: {iso_time}")
            
        except Exception as e:
            logger.warning(f"Failed to update last full update time: {e}")
            self.last_full_update_label.configure(text="Never")

    def _post_sync_update(self):
        """Update status and database sync time after sync operation."""
        self.main_window.update_status("Ready", "info")
        self.update_database_sync_time()

        # Check if sync was successful by looking for marker file
        marker_file = "/tmp/asuc_sync_success_marker"
        if os.path.exists(marker_file):
            try:
                os.unlink(marker_file)
            except BaseException:
                pass

    def update_database_sync_time(self):
        """Update the database sync time label (kept for compatibility)."""
        # This is now a no-op since we track last full update instead
        pass

    def refresh(self):
        """Refresh all dashboard data."""
        # Update system info
        try:
            config_file = self._config.config_file or "Default"
            self.system_labels["Config File"].configure(text=config_file)

            # Update last check time
            last_check_file = os.path.join(os.path.expanduser("~/.cache/arch-smart-update-checker"), "last_check")
            last_check = "Never"
            try:
                if os.path.exists(last_check_file):
                    with open(last_check_file, 'r') as f:
                        timestamp = float(f.read().strip())
                        last_check_time = datetime.fromtimestamp(timestamp)
                        # Format as relative time
                        now = datetime.now()
                        diff = now - last_check_time
                        if diff.days > 0:
                            last_check = f"{diff.days} days ago"
                        elif diff.seconds > 3600:
                            last_check = f"{diff.seconds // 3600} hours ago"
                        elif diff.seconds > 60:
                            last_check = f"{diff.seconds // 60} minutes ago"
                        else:
                            last_check = "Just now"
            except Exception:
                pass
            self.system_labels["Last Check"].configure(text=last_check)

            # Update cache status
            cache_dir = os.path.expanduser("~/.cache/arch-smart-update-checker")
            cache_status = "Ready"
            try:
                if os.path.exists(cache_dir):
                    # Count feed cache files (JSON files excluding config/history files)
                    all_files = os.listdir(cache_dir)
                    feed_files = [f for f in all_files if f.endswith('.json') and 
                                 not f.startswith('config') and 
                                 not f.startswith('update_history') and
                                 not f.startswith('security_metrics')]
                    if feed_files:
                        cache_status = f"{len(feed_files)} cached feeds"
                    else:
                        cache_status = "Empty"
            except Exception:
                cache_status = "Error"
            self.system_labels["Cache Status"].configure(text=cache_status)

        except Exception:
            pass

        # Update stats cards with current data
        self.update_stats_cards()

    def update_stats(self):
        """Stub for test compatibility."""
        pass

    def refresh_theme(self):
        """Re-apply theme/colors to all widgets in this frame."""
        for widget in self.winfo_children():
            widget.destroy()
        self.setup_ui()
        self.refresh()

    def on_frame_shown(self):
        """Called when this frame is shown."""
        # Update last full update time whenever dashboard is shown
        self.update_last_full_update_time()
        # Also refresh other data
        self.refresh()

    def update_stats_cards(self, updates_count=None, news_count=None):
        """Update the values in the stats cards."""
        # For Available Updates, use session-only data - never persist across restarts
        if updates_count is not None:
            # Explicit update from check_updates - store in session
            self.session_updates_count = updates_count

        # Use session data or show "—" if no check has been performed this session
        display_updates_count = self.session_updates_count if self.session_updates_count is not None else "—"

        # If news_count is None, try to get from checker
        if news_count is None:
            news_count = len(getattr(self.checker, 'last_news_items', []) or [])

        # Get total packages count (always live)
        total_packages = self.get_total_packages_count()

        # Get issues count (always live)
        issues_count = self.get_issues_count()

        # Update the cards
        for title, card in self.stats_cards.items():
            if 'Available Updates' in title:
                card.value_label.config(text=str(display_updates_count))
            elif 'News Items' in title:
                card.value_label.config(text=str(news_count))
            elif 'Total Packages' in title:
                card.value_label.config(text=str(total_packages))
            elif 'Issues Found' in title:
                card.value_label.config(text=str(issues_count))

        # Only save non-update stats for persistence (total packages, etc.)
        # Never persist update counts across app restarts
        self.save_non_update_stats(total_packages)

    def open_link(self, url):
        """Open a link in the default web browser."""
        # Use secure URL opening with sandboxing
        from ..utils.subprocess_wrapper import SecureSubprocess
        if not SecureSubprocess.open_url_securely(url, sandbox=True):
            # Fallback to webbrowser if secure method fails
            import webbrowser
            webbrowser.open(url)

    def refresh_news(self):
        """No-op placeholder kept for test compatibility (news feature removed)."""
        pass

    def on_card_click(self, card_title):
        """Handle clicks on clickable cards (Issues Found, News Items)."""
        if card_title == "⚠️ Issues Found":
            self.main_window.show_issues_dialog()
        elif card_title == "📰 News Items":
            self.main_window.show_news_dialog()

    def load_persisted_non_update_stats(self):
        """Load non-update stats (like last check, cache status) from file."""
        try:
            import json
            import os

            if os.path.exists(self.stats_file):
                with open(self.stats_file, 'r') as f:
                    stats = json.load(f)

                # Update widgets with persisted stats
                for title, card in self.stats_cards.items():
                    if 'Last Check' in title and 'last_check_timestamp' in stats:
                        last_check_time = datetime.fromtimestamp(stats['last_check_timestamp'])
                        now = datetime.now()
                        diff = now - last_check_time
                        if diff.days > 0:
                            card.value_label.config(text=f"{diff.days} days ago")
                        elif diff.seconds > 3600:
                            card.value_label.config(text=f"{diff.seconds // 3600} hours ago")
                        elif diff.seconds > 60:
                            card.value_label.config(text=f"{diff.seconds // 60} minutes ago")
                        else:
                            card.value_label.config(text="Just now")
                    elif 'Cache Status' in title and 'last_check_timestamp' in stats:
                        cache_dir = os.path.expanduser("~/.cache/arch-smart-update-checker")
                        if os.path.exists(cache_dir):
                            # Count feed cache files only (URLs that start with http/https)
                            all_files = os.listdir(cache_dir)
                            feed_files = [f for f in all_files if f.endswith('.json') and 
                                         (f.startswith('https') or f.startswith('http'))]
                            if feed_files:
                                card.value_label.config(text=f"{len(feed_files)} cached feeds")
                            else:
                                card.value_label.config(text="Empty")
                        else:
                            card.value_label.config(text="Empty")
                    elif 'Config File' in title and 'config_file' in stats:
                        card.value_label.config(text=stats['config_file'])
                    elif 'System' in title:
                        card.value_label.config(text="Arch Linux")

        except Exception:
            pass  # Fail silently

    def get_total_packages_count(self):
        """Get total number of installed packages."""
        try:
            return len(self.checker.package_manager.get_installed_package_names())
        except Exception:
            return 0

    def get_issues_count(self):
        """Get number of potential issues (packages with known problems)."""
        try:
            # Check for packages with known issues
            issues_count = 0

            # Get critical packages that might have issues
            critical_packages = self._config.config.get('critical_packages', [])
            installed_packages = set(self.checker.package_manager.get_installed_package_names())

            # Check if critical packages have updates (potential issues)
            if hasattr(self.checker, 'last_updates'):
                updates_set = set(self.checker.last_updates or [])
                critical_with_updates = [
                    pkg for pkg in critical_packages if pkg in updates_set and pkg in installed_packages]
                issues_count = len(critical_with_updates)

            return issues_count
        except Exception:
            return 0

    def save_non_update_stats(self, total_packages=None):
        """Save non-update stats to file for persistence (excludes update counts)."""
        try:
            import json
            import os

            # Create cache directory if it doesn't exist
            cache_dir = os.path.dirname(self.stats_file)
            os.makedirs(cache_dir, exist_ok=True)

            # Load existing stats or create new
            stats = {}
            if os.path.exists(self.stats_file):
                try:
                    with open(self.stats_file, 'r') as f:
                        stats = json.load(f)
                except Exception:
                    stats = {}

            # Only save non-update related stats
            if total_packages is not None:
                stats['total_packages'] = total_packages

            # Save updated stats
            with open(self.stats_file, 'w') as f:
                json.dump(stats, f)

        except Exception:
            pass  # Fail silently

    def reset_update_counts(self):
        """Reset update counts (session-only, no persistence needed)."""
        # Reset session update count
        self.session_updates_count = None

        # Update the display to show unknown status
        for title, card in self.stats_cards.items():
            if 'Available Updates' in title:
                card.value_label.config(text="—")
            elif 'Issues Found' in title:
                card.value_label.config(text="0")

        # Clear stored updates in checker
        if hasattr(self.checker, 'last_updates'):
            self.checker.last_updates = []

    def _configure_card_layout(self):
        """Configure card layout with adaptive sizes for responsive design."""
        # Calculate adaptive wraplength matching create_stat_card logic
        base_wrap = 180 if self.dims.window_size[0] < 1000 else 225
        PAD = self.dims.card_padding
        wrap_length = max(120, self.dims.scale(base_wrap) - (2 * PAD))

        # Apply adaptive wraplength to all card descriptions and titles
        for title, card in self.stats_cards.items():
            if hasattr(card, 'desc_label'):
                card.desc_label.configure(wraplength=wrap_length)
            if hasattr(card, 'title_label'):
                card.title_label.configure(wraplength=wrap_length)

    def cleanup_timers(self):
        """Clean up all managed timers for this component."""
        # Cancel specific animation timer
        if hasattr(self, 'animation_timer_id') and self.animation_timer_id:
            TimerResourceManager.cancel_timer(self.animation_timer_id)
            self.animation_timer_id = None

        # Cancel all timers for this component
        if hasattr(self, '_component_id'):
            cancelled = TimerResourceManager.cancel_component_timers(self._component_id)
            if cancelled > 0:
                logger.debug(f"Cancelled {cancelled} timers for dashboard component")

    def _add_tooltip(self, widget, text):
        """Add a tooltip to a widget."""
        def on_enter(event):
            # Use after_idle to prevent interference with other event handlers
            widget.after_idle(lambda: self._show_tooltip(widget, text, event.x_root, event.y_root))

        def on_leave(event):
            # Use after_idle to prevent interference with other event handlers
            widget.after_idle(lambda: self._hide_tooltip(widget))

        widget.bind('<Enter>', on_enter, add='+')  # Use add='+' to not replace existing bindings
        widget.bind('<Leave>', on_leave, add='+')  # Use add='+' to not replace existing bindings

    def _show_tooltip(self, widget, text, x_root, y_root):
        """Show tooltip for a widget."""
        try:
            if hasattr(widget, 'tooltip'):
                return  # Tooltip already shown

            tooltip = tk.Toplevel()
            tooltip.wm_overrideredirect(True)
            tooltip.wm_geometry(f"+{x_root + 10}+{y_root + 10}")
            label = tk.Label(tooltip,
                             text=text,
                             background="#FFFACD",
                             foreground="#000000",
                             relief='solid',
                             borderwidth=1,
                             font=self.dims.font('Segoe UI', 'tiny'),
                             wraplength=self.dims.scale(300),
                             justify='left',
                             padx=self.dims.scale(8),
                             pady=self.dims.pad_small)
            label.pack()
            widget.tooltip = tooltip
        except Exception:
            pass

    def _hide_tooltip(self, widget):
        """Hide tooltip for a widget."""
        try:
            if hasattr(widget, 'tooltip'):
                widget.tooltip.destroy()
                del widget.tooltip
        except Exception:
            pass

    def destroy(self):
        """Override destroy to ensure proper timer cleanup."""
        self.cleanup_timers()
        super().destroy()

    def __del__(self):
        """Destructor to ensure timer cleanup even if destroy isn't called."""
        try:
            self.cleanup_timers()
        except Exception:
            pass  # Ignore errors during destruction
