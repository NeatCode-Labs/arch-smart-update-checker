"""
Dashboard frame for the Arch Smart Update Checker GUI.
"""

# SPDX-License-Identifier: GPL-3.0-or-later

import tkinter as tk
from tkinter import ttk, messagebox
from typing import Dict, Any, List, TYPE_CHECKING

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

    def create_stat_card(self, parent: tk.Widget, title: str, value: str, description: str) -> tk.Frame:
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
        card.title_label = title_label  # store reference for wrap update

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
        card.value_label = value_label
        card.desc_label = desc_label
        card.title = title

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

        # Right column for Sync Database button (expands to fill remaining space)
        right_column = ttk.Frame(buttons_container, style='Card.TFrame')
        right_column.grid(row=0, column=1, sticky='new', padx=(self.dims.pad_medium, 0))

        # Sync Database button with same dimensions as Check for Updates
        self.sync_button = tk.Button(right_column,
                                     text="🔁 Sync Database",
                                     font=self.dims.font('Segoe UI', 'medium'),
                                     fg='white',
                                     bg=self.main_window.colors['secondary'],
                                     activebackground=self.main_window.colors['secondary'],
                                     activeforeground='white',
                                     bd=0,
                                     padx=self.dims.button_padx,
                                     pady=self.dims.button_pady,
                                     cursor='hand2',
                                     width=button_width,  # Same fixed width
                                     command=self.sync_database)
        self.sync_button.pack(pady=(0, self.dims.pad_medium))  # Match the Check for Updates button padding
        # Add tooltip to sync button
        self._add_tooltip(
            self.sync_button,
            "Refresh the package database (sudo pacman -Sy)\nRecommended: Run this before checking for updates\nAlso run if packages seem out of date or missing")

        # Database sync status container below sync button (aligned with sync button)
        db_sync_container = ttk.Frame(right_column, style='Card.TFrame')
        db_sync_container.pack(fill='x', pady=(self.dims.pad_small, 0))  # Aligned below sync button

        # Database sync label (first line) - centered with sync button
        db_sync_label_text = tk.Label(db_sync_container,
                                      text="Database last synced:",
                                      font=self.dims.font('Segoe UI', 'small'),
                                      fg=self.main_window.colors['text_secondary'],
                                      bg=self.main_window.colors['surface'])
        db_sync_label_text.pack()  # Centered alignment

        # Database sync time (second line) - centered with sync button
        self.db_sync_time_label = tk.Label(db_sync_container,
                                           text="Checking...",
                                           font=self.dims.font('Segoe UI', 'normal'),
                                           fg=self.main_window.colors['text'],
                                           bg=self.main_window.colors['surface'])
        self.db_sync_time_label.pack()  # Centered alignment

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
        self.animation_timer_id = None  # Store timer ID instead of raw timer
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

        # Update database sync time after check
        self.update_database_sync_time()

    def sync_database(self) -> None:
        """Sync package database with progress indication."""
        if not messagebox.askyesno("Sync Database",
                                   "This will sync the package database with the latest from mirrors.\n\n"
                                   "Continue?"):
            return

        # Create a progress dialog first (in main thread)
        progress_dialog = tk.Toplevel(self.main_window.root)
        progress_dialog.title("Syncing Database")
        dialog_w, dialog_h = self.dims.dialog_size
        progress_dialog.geometry(f"{dialog_w}x{dialog_h}")
        progress_dialog.transient(self.main_window.root)

        # Center the dialog
        progress_dialog.update_idletasks()
        x = (progress_dialog.winfo_screenwidth() // 2) - (dialog_w // 2)
        y = (progress_dialog.winfo_screenheight() // 2) - (dialog_h // 2)
        progress_dialog.geometry(f"+{x}+{y}")

        # Create UI elements
        info_label = ttk.Label(progress_dialog,
                               text="Syncing package database with mirrors...",
                               font=self.dims.font('Arial', 'medium'))
        info_label.pack(pady=self.dims.pad_medium)

        # Progress text
        text_height = self.dims.scale(8)
        text_width = self.dims.scale(70)
        progress_text = tk.Text(progress_dialog, height=text_height, width=text_width, wrap='word')
        progress_text.pack(fill='both', expand=True, padx=self.dims.pad_large, pady=self.dims.pad_medium)

        # Status label
        status_label = ttk.Label(progress_dialog, text="Waiting for authentication...")
        status_label.pack(pady=5)

        # Close button (disabled initially)
        close_btn = ttk.Button(progress_dialog, text="Close",
                               command=progress_dialog.destroy, state='disabled')
        close_btn.pack(pady=10)

        # Function to update progress (thread-safe)
        def update_progress(line):
            try:
                progress_text.insert('end', line + '\n')
                progress_text.see('end')
                progress_dialog.update()
            except tk.TclError:
                pass  # Dialog was closed

        # Run sync with pkexec in thread
        def sync_thread():
            try:
                logger.info("=== SYNC THREAD STARTED ===")
                print("DEBUG: sync_thread started", flush=True)

                # Build secure pacman command
                sync_cmd = ["pkexec", "pacman", "-Sy", "--noconfirm"]

                # Run the command with real-time output
                success = False
                exit_code = -1

                try:
                    import subprocess

                    logger.info(f"Starting sync with command: {sync_cmd}")

                    # Check if we're on a hardened kernel
                    uname_result = subprocess.run(["uname", "-r"], capture_output=True, text=True)
                    is_hardened = "hardened" in uname_result.stdout.lower()
                    logger.info(f"Kernel: {uname_result.stdout.strip()}, hardened: {is_hardened}")

                    # First check if we're already root or have passwordless sudo
                    check_cmd = ["sudo", "-n", "true"]
                    check_result = subprocess.run(check_cmd, capture_output=True)

                    if check_result.returncode == 0:
                        # We have passwordless sudo, use it instead of pkexec
                        sync_cmd = ["sudo", "pacman", "-Sy", "--noconfirm"]
                        logger.info("Using sudo instead of pkexec (passwordless available)")
                    elif is_hardened:
                        # On hardened kernels, skip pkexec entirely and go to zenity
                        logger.info("Hardened kernel detected, skipping pkexec")

                        # Update status
                        self.main_window.root.after(0, lambda: status_label.config(
                            text="Using alternative authentication for hardened kernel..."))

                        # Use zenity for password prompt
                        zenity_cmd = [
                            "zenity", "--password",
                            "--title=Authentication Required",
                            "--text=Enter your password to sync package database:"
                        ]

                        logger.info("Showing zenity password dialog...")
                        zenity_result = subprocess.run(
                            zenity_cmd,
                            capture_output=True,
                            text=True
                        )

                        if zenity_result.returncode == 0 and zenity_result.stdout:
                            password = zenity_result.stdout.strip()
                            logger.info("Got password from zenity")

                            # Test sudo with password
                            test_sudo = subprocess.Popen(
                                ["sudo", "-S", "true"],
                                stdin=subprocess.PIPE,
                                stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE,
                                text=True
                            )
                            test_out, test_err = test_sudo.communicate(input=password + '\n')

                            if test_sudo.returncode == 0:
                                sync_cmd = ["sudo", "-S", "pacman", "-Sy", "--noconfirm"]
                                self._sudo_password = password
                                logger.info("Authentication successful with zenity")
                            else:
                                logger.error(f"sudo test failed: {test_err}")
                                raise Exception("Invalid password")
                        else:
                            raise Exception("Password dialog cancelled")
                    else:
                        # Try normal pkexec flow
                        logger.info("Trying standard pkexec authentication...")

                        # Try pkexec with a timeout - on hardened kernels it might hang
                        try:
                            # Use subprocess without pipes first to allow authentication dialog
                            # This is critical - pipes block the auth dialog!
                            auth_process = subprocess.Popen(
                                ["pkexec", "true"],
                                stdin=None,
                                stdout=None,
                                stderr=None
                            )

                            # Wait for up to 3 seconds for pkexec to complete
                            # On hardened kernels, it might hang indefinitely
                            try:
                                auth_result = auth_process.wait(timeout=3)
                                logger.info(f"pkexec completed with code: {auth_result}")
                            except subprocess.TimeoutExpired:
                                logger.warning("pkexec timed out - likely blocked on hardened kernel")
                                auth_process.kill()
                                auth_result = -1

                            if auth_result == 0:
                                logger.info("pkexec authentication successful")
                            else:
                                raise Exception("pkexec failed or timed out")

                        except Exception as e:
                            logger.warning(f"pkexec failed: {e}, trying zenity fallback...")

                            # On hardened kernels, pkexec might not work properly
                            # Fallback to sudo with zenity for password if available
                            if subprocess.run(["which", "zenity"], capture_output=True).returncode == 0:
                                logger.info("Using zenity for password prompt")

                                # Update status to show we're using zenity
                                self.main_window.root.after(0, lambda: status_label.config(
                                    text="pkexec not available, using alternative authentication..."))

                                # Create a zenity password prompt
                                zenity_cmd = [
                                    "zenity", "--password",
                                    "--title=Authentication Required",
                                    "--text=Enter your password to sync package database:"
                                ]

                                try:
                                    zenity_result = subprocess.run(
                                        zenity_cmd,
                                        capture_output=True,
                                        text=True,
                                        timeout=60
                                    )

                                    if zenity_result.returncode == 0 and zenity_result.stdout:
                                        # Got password, use it with sudo
                                        password = zenity_result.stdout.strip()

                                        # Test sudo with password
                                        test_sudo = subprocess.Popen(
                                            ["sudo", "-S", "true"],
                                            stdin=subprocess.PIPE,
                                            stdout=subprocess.PIPE,
                                            stderr=subprocess.PIPE,
                                            text=True
                                        )
                                        test_sudo.communicate(input=password + '\n')

                                        if test_sudo.returncode == 0:
                                            # Password worked, switch to sudo
                                            sync_cmd = ["sudo", "-S", "pacman", "-Sy", "--noconfirm"]
                                            logger.info("Switched to sudo with zenity authentication")

                                            # Store password temporarily for the actual command
                                            self._sudo_password = password
                                        else:
                                            raise Exception("Invalid password")
                                    else:
                                        raise Exception("Password entry cancelled")

                                except Exception as e:
                                    logger.error(f"Zenity authentication failed: {e}")
                                    exit_code = 1
                                    success = False
                                    raise Exception(f"Authentication failed: {str(e)}")
                            else:
                                exit_code = 1
                                success = False
                                raise Exception("No authentication method available")

                    # Update status
                    self.main_window.root.after(0, lambda: status_label.config(text="Syncing database..."))

                    # Run the actual sync command with output capture
                    # Now we can safely capture output since we're already authenticated
                    if sync_cmd[0] == "sudo" and sync_cmd[1] == "-S":
                        # Use the stored password for sudo -S
                        process = subprocess.Popen(
                            sync_cmd,
                            stdin=subprocess.PIPE,
                            stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT,
                            text=True,
                            bufsize=1,
                            universal_newlines=True
                        )
                        # Send password
                        process.stdin.write(self._sudo_password + '\n')
                        process.stdin.flush()
                        # Clear password from memory
                        self._sudo_password = None
                    else:
                        process = subprocess.Popen(
                            sync_cmd,
                            stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT,
                            text=True,
                            bufsize=1,
                            universal_newlines=True
                        )

                    logger.info(f"Process started with PID: {process.pid}")

                    # Read output line by line
                    while True:
                        line = process.stdout.readline()
                        if not line and process.poll() is not None:
                            break
                        if line:
                            line = line.strip()
                            if line:
                                logger.info(f"Output: {line}")
                                self.main_window.root.after(0, lambda line_text=line: update_progress(line_text))

                    # Get exit code
                    exit_code = process.poll()
                    success = (exit_code == 0)
                    logger.info(f"Sync process completed with exit code: {exit_code}")

                    # Update sync time if successful
                    if success:
                        # Create marker file to indicate successful sync
                        marker_file = "/tmp/asuc_sync_success_marker"
                        try:
                            with open(marker_file, 'w') as f:
                                f.write(str(datetime.now().timestamp()))
                        except BaseException:
                            pass

                except subprocess.TimeoutExpired:
                    logger.error("Sync command timed out")
                    success = False
                    exit_code = -1
                    try:
                        process.kill()
                    except BaseException:
                        pass
                except Exception as e:
                    logger.error(f"Error during sync execution: {e}")
                    success = False
                    if exit_code == -1:  # Only set if not already set
                        exit_code = 1

                # Update UI based on result (in main thread)
                if success:
                    def on_success():
                        status_label.config(text="✅ Database sync completed successfully!", foreground='green')
                        self.main_window.update_status("✅ Database synced successfully", "success")
                        self._post_sync_update()

                        # Force refresh the sync time after a short delay to ensure files are updated
                        self.main_window.root.after(500, self.update_database_sync_time)
                    self.main_window.root.after(0, on_success)
                    # Don't auto-close - let users read the output and close manually
                else:
                    if exit_code == 126 or exit_code == 127:
                        def on_cancelled():
                            error_msg = ("❌ Authentication failed\n\n"
                                         "No polkit authentication agent found.\n"
                                         "Please ensure a polkit agent is running.\n\n"
                                         "For Cinnamon, try running:\n"
                                         "/usr/lib/polkit-gnome/polkit-gnome-authentication-agent-1")
                            update_progress(error_msg)
                            status_label.config(text="❌ Authentication failed - see details above", foreground='red')
                            self.main_window.update_status("Sync failed - no auth agent", "error")
                        self.main_window.root.after(0, on_cancelled)
                    else:
                        def on_failed():
                            status_label.config(text="❌ Database sync failed", foreground='red')
                            self.main_window.update_status(f"❌ Sync failed with exit code {exit_code}", "error")
                        self.main_window.root.after(0, on_failed)

            except Exception as e:
                logger.error(f"Failed to sync database: {e}")
                error_msg = str(e)

                def on_error():
                    update_progress(f"Error: {error_msg}")
                    status_label.config(text=f"❌ Error: {error_msg}", foreground='red')
                self.main_window.root.after(0, on_error)

            # Enable close button (in main thread)
            self.main_window.root.after(0, lambda: close_btn.config(state='normal'))

        # Use secure thread management
        from ..utils.thread_manager import create_managed_thread
        import uuid

        thread_id = f"db_sync_{uuid.uuid4().hex[:8]}"
        thread = create_managed_thread(thread_id, sync_thread, is_background=True)
        if thread is None:
            progress_dialog.destroy()
            messagebox.showerror("Thread Error",
                                 "Unable to start database sync: thread limit reached")
        else:
            # Start the thread!
            thread.start()
            logger.info(f"Started sync thread with ID: {thread_id}")

    def update_all_packages(self):
        """Update all packages on the system."""
        if messagebox.askyesno("Confirm Update",
                               "Are you sure you want to update all packages?\n\n"
                               "This will run 'sudo pacman -Syu' and may take some time."):
            # Get the package manager frame and call its run_pacman_update method
            if 'packages' in self.main_window.frames:
                package_frame = self.main_window.frames['packages']
                package_frame.run_pacman_update()
            else:
                # Fallback: create a temporary package manager instance
                from .package_manager import PackageManagerFrame
                temp_frame = PackageManagerFrame(self, self.main_window)
                temp_frame.run_pacman_update()

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
        """Update the database sync time label."""
        sync_time = PacmanRunner.get_database_last_sync_time()

        if sync_time:
            # Format as ISO date and time (YYYY-MM-DD HH:MM:SS)
            iso_time = sync_time.strftime('%Y-%m-%d %H:%M:%S')
            self.db_sync_time_label.configure(text=iso_time)

            # Log for debugging
            logger.debug(f"Updated database sync time display to: {iso_time}")
        else:
            self.db_sync_time_label.configure(text="Unknown")

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
                    # Count cache files
                    cache_files = [f for f in os.listdir(cache_dir) if f.endswith('.json')]
                    if cache_files:
                        cache_status = f"{len(cache_files)} cached feeds"
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
        # Update database sync time whenever dashboard is shown
        self.update_database_sync_time()
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
                        cache_files = [f for f in os.listdir(cache_dir) if f.endswith('.json')]
                        if cache_files:
                            card.value_label.config(text=f"{len(cache_files)} cached feeds")
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
