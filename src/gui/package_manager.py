"""
Package manager frame for the Arch Smart Update Checker GUI.
"""

# SPDX-License-Identifier: GPL-3.0-or-later

import tkinter as tk
from tkinter import ttk, messagebox
from typing import Dict, Any, List, Optional
import threading
import subprocess
import os
import shlex
import re
import time

from ..package_manager import PackageManager
from ..config import Config
from ..utils.logger import get_logger
from ..utils.validators import validate_package_name
from .dimensions import get_dimensions
from ..constants import DEFAULT_CRITICAL_PACKAGES
from .window_mixin import WindowPositionMixin
from ..utils.thread_manager import ThreadResourceManager
from ..utils.timer_manager import TimerResourceManager, create_delayed_callback
from ..utils.secure_memory import MemoryManager, force_memory_cleanup
from ..utils.subprocess_wrapper import SecureSubprocess

logger = get_logger(__name__)


class PackageManagerFrame(ttk.Frame, WindowPositionMixin):
    """Modern package manager with search and management capabilities."""

    def __init__(self, parent, main_window):
        """Initialize the package manager frame."""
        try:
            super().__init__(parent, style='Content.TFrame')
        except Exception:
            temp_root = tk.Tk()
            temp_root.withdraw()
            super().__init__(temp_root, style='Content.TFrame')
        self.main_window = main_window
        self.package_manager = main_window.checker.package_manager
        self.config = main_window.config
        self.dims = get_dimensions()

        # Sort state tracking
        self.sort_column = None
        self.sort_reverse = False

        # Timer management
        self._component_id = f"package_manager_{id(self)}"
        self._loading_in_progress = False
        self._load_timer_id = None

        self.setup_ui()
        # Schedule package loading after a delay to ensure UI is ready
        self._load_timer_id = self.after(500, self._safe_load_packages)

    @property
    def colors(self):
        """Get current colors from main window."""
        return self.main_window.colors

    def _safe_load_packages(self):
        """Safely load packages with proper checks."""
        if not self._loading_in_progress:
            self._loading_in_progress = True
            self.load_packages()

    def setup_ui(self):
        """Setup the package manager UI."""
        # Main container
        main_container = ttk.Frame(self, style='Content.TFrame')
        main_container.pack(fill='both', expand=True, padx=self.dims.pad_large, pady=self.dims.pad_large)

        # Header
        self.create_header(main_container)

        # Search and filter bar
        self.create_search_bar(main_container)

        # Package list area
        self.create_package_area(main_container)

        # Action buttons
        self.create_action_buttons(main_container)

    def create_header(self, parent):
        """Create the header section."""
        header_frame = ttk.Frame(parent, style='Content.TFrame')
        header_frame.pack(fill='x', pady=(0, self.dims.pad_medium))

        # Title
        title_label = tk.Label(header_frame,
                               text="🔧 Package Manager",
                               font=self.dims.font('Segoe UI', size_name='xlarge', style='bold'),
                               fg=self.colors['text'],
                               bg=self.colors['background'])
        title_label.pack(anchor='w', padx=self.dims.pad_large, pady=(self.dims.pad_large, self.dims.pad_medium))

        # Subtitle
        subtitle_label = tk.Label(header_frame,
                                  text="Monitor critical packages and system updates",
                                  font=self.dims.font('Segoe UI', size_name='medium'),
                                  fg=self.colors['text_secondary'],
                                  bg=self.colors['background'])
        subtitle_label.pack(anchor='w', padx=self.dims.pad_large, pady=(0, self.dims.pad_large))

    def create_search_bar(self, parent):
        """Create search and filter controls."""
        search_frame = ttk.Frame(parent, style='Content.TFrame')
        search_frame.pack(fill='x', pady=(0, self.dims.pad_medium))

        # Search container
        search_container = ttk.Frame(search_frame, style='Content.TFrame')
        search_container.pack(fill='x')

        # Search label and entry
        search_label = tk.Label(search_container,
                                text="Search packages:",
                                font=self.dims.font('Segoe UI', 'normal'),
                                fg=self.colors['text'],
                                bg=self.colors['background'])
        search_label.pack(side='left', padx=(0, self.dims.pad_medium))

        self.search_var = tk.StringVar(master=parent)
        self.search_var.trace('w', lambda *args: self.filter_packages())

        search_entry = tk.Entry(search_container,
                                textvariable=self.search_var,
                                font=self.dims.font('Segoe UI', 'normal'),
                                bg=self.colors['background'],
                                fg=self.colors['text'],
                                insertbackground=self.colors['text'],
                                relief='solid',
                                bd=1,
                                width=self.dims.entry_width)
        search_entry.pack(side='left', padx=(0, self.dims.pad_large))

        # Filter dropdown
        filter_label = tk.Label(search_container,
                                text="Filter:",
                                font=('Segoe UI', 11, 'normal'),
                                fg=self.colors['text'],
                                bg=self.colors['background'])
        filter_label.pack(side='left', padx=(0, 10))

        self.filter_var = tk.StringVar(master=parent, value="All")
        filter_combo = ttk.Combobox(search_container,
                                    textvariable=self.filter_var,
                                    values=["All", "Critical", "Normal", "Updates Available"],
                                    state="readonly",
                                    font=('Segoe UI', 10, 'normal'),
                                    width=15)
        filter_combo.pack(side='left')
        filter_combo.bind('<<ComboboxSelected>>', lambda e: self.filter_packages())

        # Refresh button
        refresh_btn = tk.Button(search_container,
                                text="🔄 Refresh",
                                font=('Segoe UI', 10, 'normal'),
                                fg='white',
                                bg=self.colors['info'],
                                activebackground=self.colors['info'],
                                activeforeground='white',
                                bd=0,
                                padx=15,
                                pady=5,
                                cursor='hand2',
                                command=self.refresh_packages)
        refresh_btn.pack(side='right')
        self._add_tooltip(refresh_btn, "Refresh package list (F5)")

    def create_package_area(self, parent):
        """Create the package list display area."""
        package_frame = ttk.Frame(parent, style='Content.TFrame')
        package_frame.pack(fill='both', expand=True, pady=(0, 10))

        # Package container with padding
        package_container = ttk.Frame(package_frame, style='Content.TFrame')
        package_container.pack(fill='both', expand=True)

        # Configure treeview style for better row height
        style = ttk.Style()

        # Use scaled font sizes
        scaled_font_size = self.dims.font_small
        heading_font_size = self.dims.font_normal

        # Use scaled row height
        row_height = self.dims.tree_row_height

        style.configure('PackageManager.Treeview',
                        background=self.colors['surface'],
                        foreground=self.colors['text'],
                        fieldbackground=self.colors['surface'],
                        borderwidth=1,
                        relief='solid',
                        font=('Segoe UI', scaled_font_size, 'normal'),  # Set font for data rows
                        rowheight=row_height)
        style.configure('PackageManager.Treeview.Heading',
                        background=self.colors['primary'],
                        foreground='white',
                        font=('Segoe UI', heading_font_size, 'bold'),
                        relief='raised',  # Add raised relief for visual separation
                        borderwidth=1)    # Add border for column headers
        style.map('PackageManager.Treeview',
                  background=[('selected', self.colors['primary'])],
                  foreground=[('selected', 'white')])

        # Treeview for package list
        columns = ('version', 'repository', 'size', 'install_date', 'status')
        self.package_tree = ttk.Treeview(package_container,
                                         columns=columns,
                                         show='tree headings',
                                         style='PackageManager.Treeview')

        # Configure columns
        self.package_tree.heading('#0', text='Package Name', anchor='c')  # Center
        self.package_tree.heading('version', text='Version', anchor='c')  # Center
        self.package_tree.heading('repository', text='Repository', anchor='c')  # Center
        self.package_tree.heading('size', text='Size', anchor='c')  # Center
        self.package_tree.heading('install_date', text='Install Date', anchor='c')  # Center
        self.package_tree.heading('status', text='Priority', anchor='c')  # Center

        # Set column widths and alignments for data - all centered
        self.package_tree.column('#0', width=250, minwidth=180, anchor='c')  # Center data
        self.package_tree.column('version', width=120, minwidth=100, anchor='c')  # Center data
        self.package_tree.column('repository', width=100, minwidth=80, anchor='c')  # Center data
        self.package_tree.column('size', width=80, minwidth=60, anchor='c')  # Center data
        self.package_tree.column('install_date', width=140, minwidth=120, anchor='c')  # Center data
        self.package_tree.column('status', width=80, minwidth=60, anchor='c')  # Center data

        # Store reference to package_tree
        self.package_container = package_container

        # Apply column configuration
        self._configure_columns()

        # Create scrollbar
        scrollbar = ttk.Scrollbar(package_container,
                                  orient='vertical',
                                  command=self.package_tree.yview)
        self.package_tree.configure(yscrollcommand=scrollbar.set)

        # Pack components
        self.package_tree.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')

        # Bind events
        self.package_tree.bind('<Double-Button-1>', self.on_package_double_click)
        self.package_tree.bind('<Return>', self.on_package_double_click)
        self.package_tree.bind('<Control-c>', lambda e: self.mark_package_critical())
        self.package_tree.bind('<Control-r>', lambda e: self.remove_package_critical())
        self.package_tree.bind('<Control-i>', lambda e: self.view_package_details())
        self.package_tree.bind('<F5>', lambda e: self.load_packages())

        # Bind column header clicks for sorting
        self.package_tree.heading('#0', command=lambda: self.sort_packages('#0'))
        self.package_tree.heading('version', command=lambda: self.sort_packages('version'))
        self.package_tree.heading('repository', command=lambda: self.sort_packages('repository'))
        self.package_tree.heading('size', command=lambda: self.sort_packages('size'))
        self.package_tree.heading('install_date', command=lambda: self.sort_packages('install_date'))
        self.package_tree.heading('status', command=lambda: self.sort_packages('status'))

        # Stats label
        self.stats_label = tk.Label(package_frame,
                                    text="Loading packages...",
                                    font=('Segoe UI', 10, 'italic'),
                                    fg=self.colors['text_secondary'],
                                    bg=self.colors['background'])
        self.stats_label.pack(anchor='w', pady=(10, 0))

    def create_action_buttons(self, parent):
        """Create action buttons."""
        action_frame = ttk.Frame(parent, style='Content.TFrame')
        action_frame.pack(fill='x')

        button_container = ttk.Frame(action_frame, style='Content.TFrame')
        button_container.pack(pady=10)

        # Mark as critical button
        mark_critical_btn = tk.Button(button_container,
                                      text="⚠️ Mark Critical",
                                      font=self.dims.font('Segoe UI', 'small'),
                                      fg='white',
                                      bg=self.colors['warning'],
                                      activebackground=self.colors['warning'],
                                      activeforeground='white',
                                      bd=0,
                                      padx=self.dims.button_padx,
                                      pady=self.dims.button_pady,
                                      cursor='hand2',
                                      command=self.mark_package_critical)
        mark_critical_btn.pack(side='left', padx=(0, 10))
        self._add_tooltip(mark_critical_btn, "Mark selected packages as critical (Ctrl+C)")

        # Remove from critical button
        remove_critical_btn = tk.Button(button_container,
                                        text="✓ Remove Critical",
                                        font=self.dims.font('Segoe UI', 'small'),
                                        fg='white',
                                        bg=self.colors['success'],
                                        activebackground=self.colors['success'],
                                        activeforeground='white',
                                        bd=0,
                                        padx=self.dims.button_padx,
                                        pady=self.dims.button_pady,
                                        cursor='hand2',
                                        command=self.remove_package_critical)
        remove_critical_btn.pack(side='left', padx=(0, 10))
        self._add_tooltip(remove_critical_btn, "Remove selected packages from critical list (Ctrl+R)")

        # View details button
        view_details_btn = tk.Button(button_container,
                                     text="🔍 View Details",
                                     font=self.dims.font('Segoe UI', 'small'),
                                     fg='white',
                                     bg=self.colors['secondary'],
                                     activebackground=self.colors['secondary'],
                                     activeforeground='white',
                                     bd=0,
                                     padx=self.dims.button_padx,
                                     pady=self.dims.button_pady,
                                     cursor='hand2',
                                     command=self.view_package_details)
        view_details_btn.pack(side='left')
        self._add_tooltip(view_details_btn, "View detailed package information (Ctrl+I or double-click)")

        # Separator
        separator = tk.Frame(button_container, width=1, bg=self.colors['text_secondary'])
        separator.pack(side='left', fill='y', padx=20)

        # Remove package button
        remove_btn = tk.Button(button_container,
                               text="🗑️ Remove Package",
                               font=self.dims.font('Segoe UI', 'small'),
                               fg='white',
                               bg=self.colors['error'],
                               activebackground='#DC2626',  # Darker red on hover
                               activeforeground='white',
                               bd=0,
                               padx=self.dims.button_padx,
                               pady=self.dims.button_pady,
                               cursor='hand2',
                               command=self.remove_selected)
        remove_btn.pack(side='left', padx=(0, 10))
        self._add_tooltip(remove_btn, "Remove selected packages from the system (requires confirmation)")

        # Clean orphans button
        clean_orphans_btn = tk.Button(button_container,
                                      text="🧹 Clean Orphans",
                                      font=self.dims.font('Segoe UI', 'small'),
                                      fg='white',
                                      bg=self.colors['primary'],
                                      activebackground=self.colors['primary'],
                                      activeforeground='white',
                                      bd=0,
                                      padx=self.dims.button_padx,
                                      pady=self.dims.button_pady,
                                      cursor='hand2',
                                      command=self.clean_orphans)
        clean_orphans_btn.pack(side='left', padx=(0, 10))
        self._add_tooltip(clean_orphans_btn, "Remove orphaned packages that are not needed by any other package")

    def load_packages(self):
        """Load installed packages."""
        # Disable buttons during loading
        for child in self.winfo_children():
            if isinstance(child, tk.Button):
                child.config(state='disabled')

        # Clear existing items
        for item in self.package_tree.get_children():
            self.package_tree.delete(item)

        # Show loading message
        self.stats_label.config(text="🔄 Loading packages... Please wait", fg=self.colors['info'])

        def load_thread():
            try:
                # Get installed packages
                self.main_window.root.after(50,
                                            lambda: self.stats_label.config(text="🔄 Fetching package list..."))
                packages = self.package_manager.get_installed_packages()

                # Get critical packages
                critical_packages = set(self.config.get_critical_packages())

                # Update UI in main thread
                self.main_window.root.after(0, lambda: self.display_packages(packages, critical_packages))

            except subprocess.CalledProcessError as e:
                logger.error(f"Pacman command failed: {e}")
                self.main_window.root.after(
                    0, lambda: self._handle_load_error(
                        "Pacman command failed", "Failed to retrieve package list.\n\n"
                        "Please ensure pacman is properly installed and accessible."))
            except PermissionError as e:
                logger.error(f"Permission denied: {e}")
                self.main_window.root.after(0,
                                            lambda: self._handle_load_error("Permission Denied",
                                                                            "Cannot access package database.\n\n"
                                                                            "Please check your system permissions."))
            except Exception as e:
                logger.error(f"Error loading packages: {e}")
                error_msg = str(e)
                self.main_window.root.after(
                    0,
                    lambda: self._handle_load_error(
                        "Error Loading Packages",
                        f"An unexpected error occurred:\n\n{error_msg}"))
            finally:
                # Reset loading flag
                self._loading_in_progress = False

        # Start loading in background using secure thread management
        from ..utils.thread_manager import create_managed_thread
        import uuid

        thread_id = f"pkg_load_{uuid.uuid4().hex[:8]}"
        thread = create_managed_thread(thread_id, load_thread, is_background=True)
        if thread is None:
            self._handle_load_error("Thread Error",
                                    "Unable to start package loading: thread limit reached")
        else:
            # Start the thread
            thread.start()

    def _handle_load_error(self, title: str, message: str):
        """Handle package loading errors."""
        # Re-enable buttons
        for child in self.winfo_children():
            if isinstance(child, tk.Button):
                child.config(state='normal')

        # Update stats label
        self.stats_label.config(text="❌ Error loading packages", fg=self.colors['error'])

        # Show error dialog
        messagebox.showerror(title, message)

    def display_packages(self, packages: List[Dict[str, str]], critical_packages: set):
        """Display packages in the treeview."""
        # Clear existing items
        for item in self.package_tree.get_children():
            self.package_tree.delete(item)

        # Add packages
        for pkg in packages:
            name = pkg.get('name', 'Unknown')
            version = pkg.get('version', 'Unknown')
            repository = pkg.get('repository', 'Unknown')
            size = pkg.get('size', 'Unknown')
            install_date = pkg.get('install_date', 'Unknown')

            # Format install date using international format (ISO 8601: YYYY-MM-DD HH:MM)
            install_date = self._format_install_date(install_date)

            # Determine priority status based on critical packages list
            # Critical = Package is marked as critical (system stability depends on it)
            # Normal = Regular package (safe to update without special care)
            status = "Critical" if name in critical_packages else "Normal"

            # Insert into tree
            self.package_tree.insert('', 'end',
                                     text=name,
                                     values=(version, repository, size, install_date, status),
                                     tags=(status.lower(),))

        # Configure tags
        self.package_tree.tag_configure('critical',
                                        foreground=self.colors['error'])

        # Update stats
        total = len(packages)
        critical = len([p for p in packages if p.get('name') in critical_packages])
        import time as time_module
        self.stats_label.config(
            text=f"✅ Total: {total} packages | Critical: {critical} | Last updated: {time_module.strftime('%H:%M')}",
            fg=self.colors['text_secondary']
        )

        # Re-enable buttons
        for child in self.winfo_children():
            if isinstance(child, tk.Button):
                child.config(state='normal')

        # Store for filtering
        self.all_packages = packages
        self.critical_packages = critical_packages

    def filter_packages(self):
        """Filter displayed packages based on search and filter criteria."""
        if not hasattr(self, 'all_packages'):
            return

        search_term = self.search_var.get().lower()
        filter_type = self.filter_var.get()

        # Clear tree
        for item in self.package_tree.get_children():
            self.package_tree.delete(item)

        # Filter and display
        displayed = 0
        critical_count = 0

        for pkg in self.all_packages:
            name = pkg.get('name', '')
            name_lower = name.lower()

            # Apply search filter (case-insensitive search in name and description)
            if search_term:
                description = pkg.get('description', '').lower()
                if search_term not in name_lower and search_term not in description:
                    continue

            # Apply type filter
            is_critical = name in self.critical_packages
            has_update = pkg.get('update', 'No') == 'Yes'

            if filter_type == 'Critical' and not is_critical:
                continue
            elif filter_type == 'Normal' and is_critical:
                continue
            elif filter_type == 'Updates Available' and not has_update:
                continue

            # Add to tree
            # Critical = Package is marked as critical (system stability depends on it)
            # Normal = Regular package (safe to update without special care)
            status = "Critical" if is_critical else "Normal"

            # Format install date for display
            install_date = self._format_install_date(pkg.get('install_date', 'Unknown'))

            self.package_tree.insert('', 'end',
                                     text=name,
                                     values=(pkg.get('version'),
                                             pkg.get('repository'),
                                             pkg.get('size'),
                                             install_date,
                                             status),
                                     tags=(status.lower(),))
            displayed += 1
            if is_critical:
                critical_count += 1

        # Update stats with more detail
        stats_text = f"Showing {displayed} of {len(self.all_packages)} packages"
        if filter_type == 'All':
            stats_text += f" ({critical_count} critical)"
        self.stats_label.config(text=stats_text)

    def sort_packages(self, column):
        """Sort packages by the specified column."""
        # Get all items
        items = []
        for item in self.package_tree.get_children():
            if column == '#0':
                # Package name is in the text field
                value = self.package_tree.item(item)['text']
            else:
                # Other columns are in values
                values = self.package_tree.item(item)['values']
                col_index = {
                    'version': 0,
                    'repository': 1,
                    'size': 2,
                    'install_date': 3,
                    'status': 4
                }.get(column, 0)
                value = values[col_index] if col_index < len(values) else ''

            items.append((value, item))

        # Determine sort order
        if self.sort_column == column:
            # Same column clicked, reverse the order
            self.sort_reverse = not self.sort_reverse
        else:
            # New column clicked, sort ascending
            self.sort_column = column
            self.sort_reverse = False

        # Sort based on column type
        if column == 'size':
            # Parse size values for proper numeric sorting
            def parse_size(size_str):
                if isinstance(size_str, str):
                    try:
                        # Extract number and unit
                        parts = size_str.split()
                        if len(parts) == 2:
                            num = float(parts[0].replace(',', '.'))
                            unit = parts[1].upper()
                            # Convert to bytes for comparison
                            multipliers = {'B': 1, 'KIB': 1024, 'MIB': 1024**2, 'GIB': 1024**3}
                            return num * multipliers.get(unit, 1)
                    except (ValueError, TypeError):
                        pass
                return 0

            items.sort(key=lambda x: parse_size(x[0]), reverse=self.sort_reverse)
        elif column == 'install_date':
            # Sort dates chronologically
            items.sort(key=lambda x: x[0] if x[0] else '', reverse=self.sort_reverse)
        else:
            # Text-based sorting for other columns
            items.sort(key=lambda x: x[0].lower() if isinstance(x[0], str) else str(x[0]),
                       reverse=self.sort_reverse)

        # Re-insert items in sorted order
        for index, (_, item) in enumerate(items):
            self.package_tree.move(item, '', index)

        # Update column heading to show sort indicator
        for col in ['#0', 'version', 'repository', 'size', 'install_date', 'status']:
            if col == column:
                # Add sort indicator
                heading_text = self.package_tree.heading(col)['text'].rstrip(' ▲▼')
                indicator = ' ▼' if self.sort_reverse else ' ▲'
                self.package_tree.heading(col, text=heading_text + indicator)
            else:
                # Remove sort indicator from other columns
                heading_text = self.package_tree.heading(col)['text'].rstrip(' ▲▼')
                self.package_tree.heading(col, text=heading_text)

    def mark_package_critical(self):
        """Mark selected package as critical."""
        selection = self.package_tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a package to mark as critical.")
            return

        marked_count = 0
        already_critical = []

        for item in selection:
            package_name = self.package_tree.item(item)['text']

            # Validate package name
            if not validate_package_name(package_name):
                logger.warning(f"Invalid package name: {package_name}")
                messagebox.showerror("Error", f"Invalid package name: {package_name}")
                continue

            # Add to critical packages
            critical_packages = self.config.get_critical_packages()
            if package_name not in critical_packages:
                critical_packages.append(package_name)
                self.config.set('critical_packages', critical_packages)
                logger.info(f"Marked package as critical: {package_name}")
                marked_count += 1
            else:
                already_critical.append(package_name)

        # Show feedback
        if marked_count > 0 and not already_critical:
            messagebox.showinfo(
                "Success", f"Successfully marked {marked_count} package{'s' if marked_count > 1 else ''} as critical.")
        elif marked_count > 0 and already_critical:
            msg = f"Marked {marked_count} package{'s' if marked_count > 1 else ''} as critical.\n\n"
            msg += f"The following package{'s were' if len(already_critical) > 1 else ' was'} already critical:\n"
            msg += ", ".join(already_critical[:5])
            if len(already_critical) > 5:
                msg += f" and {len(already_critical) - 5} more..."
            messagebox.showinfo("Partial Success", msg)
        elif already_critical:
            msg = f"The selected package{'s are' if len(already_critical) > 1 else ' is'} already marked as critical."
            messagebox.showinfo("Already Critical", msg)

        # Reload display
        self.load_packages()

    def remove_package_critical(self):
        """Remove selected package from critical list."""
        selection = self.package_tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a package to remove from critical list.")
            return

        removed_count = 0
        not_critical = []

        for item in selection:
            package_name = self.package_tree.item(item)['text']

            # Remove from critical packages
            critical_packages = self.config.get_critical_packages()
            if package_name in critical_packages:
                critical_packages.remove(package_name)
                self.config.set('critical_packages', critical_packages)
                logger.info(f"Removed package from critical list: {package_name}")
                removed_count += 1
            else:
                not_critical.append(package_name)

        # Show feedback
        if removed_count > 0 and not not_critical:
            messagebox.showinfo(
                "Success", f"Successfully removed {removed_count} package{
                    's' if removed_count > 1 else ''} from critical list.")
        elif removed_count > 0 and not_critical:
            msg = f"Removed {removed_count} package{'s' if removed_count > 1 else ''} from critical list.\n\n"
            msg += f"The following package{'s were' if len(not_critical) > 1 else ' was'} not critical:\n"
            msg += ", ".join(not_critical[:5])
            if len(not_critical) > 5:
                msg += f" and {len(not_critical) - 5} more..."
            messagebox.showinfo("Partial Success", msg)
        elif not_critical:
            msg = f"The selected package{'s are' if len(not_critical) > 1 else ' is'} not marked as critical."
            messagebox.showinfo("Not Critical", msg)

        # Reload display
        self.load_packages()

    def view_package_details(self):
        """View details of selected package."""
        selection = self.package_tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a package to view details.")
            return

        package_name = self.package_tree.item(selection[0])['text']

        # Validate package name
        if not validate_package_name(package_name):
            logger.warning(f"Invalid package name: {package_name}")
            messagebox.showerror("Error", f"Invalid package name: {package_name}")
            return

        # Get package info
        def get_info_thread():
            try:
                info = self.package_manager.get_package_info(package_name)
                self.main_window.root.after(0, lambda: self.show_package_info(package_name, info))
            except Exception as e:
                logger.error(f"Error getting package info: {e}")
                error_msg = str(e)
                self.main_window.root.after(0,
                                            lambda: messagebox.showerror("Error", f"Failed to get package info: {error_msg}"))

        # Use secure thread management for package info retrieval
        import uuid
        thread_id = f"package_info_{uuid.uuid4().hex[:8]}"
        thread = ThreadResourceManager.create_managed_thread(
            thread_id=thread_id,
            target=get_info_thread,
            is_background=True
        )
        if thread:
            thread.start()
        else:
            logger.warning("Could not create thread for package info - thread limit reached")
            messagebox.showwarning("Thread Limit",
                                   "Cannot retrieve package info - thread limit reached. Please try again.")

    def show_package_info(self, package_name: str, info: Optional[str]):
        """Show package information in a dialog."""
        if not info:
            messagebox.showinfo("Package Info", f"No information available for {package_name}")
            return

        # Create info window
        info_window = tk.Toplevel(self.main_window.root)
        info_window.title(f"Package Info: {package_name}")
        info_window.configure(bg=self.colors['background'])
        info_window.resizable(True, True)

        # Use proper positioning
        self.position_window(info_window, 700, 500, self.main_window.root)

        # Header
        header_frame = tk.Frame(info_window, bg=self.colors['primary'], height=60)
        header_frame.pack(fill='x')
        header_frame.pack_propagate(False)

        header_label = tk.Label(header_frame,
                                text=f"📦 {package_name}",
                                font=('Segoe UI', 16, 'bold'),
                                fg='white',
                                bg=self.colors['primary'])
        header_label.pack(expand=True)

        # Content frame
        content_frame = tk.Frame(info_window, bg=self.colors['background'])
        content_frame.pack(fill='both', expand=True, padx=20, pady=20)

        # Create text widget with scrollbar
        text_frame = tk.Frame(content_frame, bg=self.colors['background'])
        text_frame.pack(fill='both', expand=True)

        text_widget = tk.Text(text_frame,
                              font=('Consolas', 10, 'normal'),
                              bg=self.colors['surface'],
                              fg=self.colors['text'],
                              wrap='word',
                              padx=15,
                              pady=15,
                              borderwidth=1,
                              relief='solid')

        scrollbar = ttk.Scrollbar(text_frame, orient='vertical', command=text_widget.yview)
        text_widget.configure(yscrollcommand=scrollbar.set)

        # Pack text widget and scrollbar
        text_widget.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')

        # Insert info with basic formatting
        lines = info.split('\n')
        for line in lines:
            if line.startswith(('Name', 'Version', 'Description', 'Architecture',
                                'URL', 'Licenses', 'Groups', 'Provides', 'Depends On',
                                'Optional Deps', 'Required By', 'Optional For', 'Conflicts With',
                                'Replaces', 'Installed Size', 'Packager', 'Build Date',
                                'Install Date', 'Install Reason', 'Install Script', 'Validated By')):
                # Bold headers
                parts = line.split(':', 1)
                if len(parts) == 2:
                    text_widget.insert('end', parts[0] + ':', 'bold')
                    text_widget.insert('end', parts[1] + '\n')
                else:
                    text_widget.insert('end', line + '\n')
            else:
                text_widget.insert('end', line + '\n')

        # Configure text tags
        text_widget.tag_configure('bold', font=('Consolas', 10, 'bold'))
        text_widget.config(state='disabled')

        # Button frame
        button_frame = tk.Frame(content_frame, bg=self.colors['background'])
        button_frame.pack(fill='x', pady=(15, 0))

        # Copy button
        def copy_info():
            info_window.clipboard_clear()
            info_window.clipboard_append(info)
            messagebox.showinfo("Copied", "Package information copied to clipboard", parent=info_window)

        copy_btn = tk.Button(button_frame,
                             text="📋 Copy Info",
                             font=('Segoe UI', 10, 'normal'),
                             fg='white',
                             bg=self.colors['primary'],
                             activebackground=self.colors['primary_hover'],
                             activeforeground='white',
                             bd=0,
                             padx=15,
                             pady=8,
                             cursor='hand2',
                             command=copy_info)
        copy_btn.pack(side='left', padx=(0, 10))

        # Close button
        close_btn = tk.Button(button_frame,
                              text="Close",
                              font=('Segoe UI', 10, 'normal'),
                              fg='white',
                              bg=self.colors['secondary'],
                              activebackground=self.colors['secondary'],
                              activeforeground='white',
                              bd=0,
                              padx=20,
                              pady=8,
                              cursor='hand2',
                              command=info_window.destroy)
        close_btn.pack(side='right')

        # Bind Escape key to close
        info_window.bind('<Escape>', lambda e: info_window.destroy())
        info_window.focus_set()

    def on_package_double_click(self, event):
        """Handle double-click on package."""
        self.view_package_details()

    def run_pacman_update(self):
        """Run pacman system update with proper security."""
        def update_thread():
            try:
                # Create secure command using array format to prevent injection
                # No shell interpretation, direct execution
                pacman_cmd = ["pkexec", "pacman", "-Syu", "--noconfirm"]

                # Create a progress dialog
                progress_dialog = tk.Toplevel(self.main_window.root)
                progress_dialog.title("System Update")
                progress_dialog.geometry("700x500")
                progress_dialog.transient(self.main_window.root)

                # Center the dialog
                progress_dialog.update_idletasks()
                x = (progress_dialog.winfo_screenwidth() // 2) - (350)
                y = (progress_dialog.winfo_screenheight() // 2) - (250)
                progress_dialog.geometry(f"+{x}+{y}")

                # Create UI elements
                info_label = ttk.Label(progress_dialog,
                                       text="Running full system update with system privileges...",
                                       font=('Arial', 12))
                info_label.pack(pady=10)

                # Note about full system update
                note_label = ttk.Label(progress_dialog,
                                       text="Note: This will update ALL packages on your system",
                                       font=('Arial', 10, 'italic'))
                note_label.pack()

                # Progress text
                progress_text = tk.Text(progress_dialog, height=20, width=80, wrap='word')
                progress_text.pack(fill='both', expand=True, padx=20, pady=10)

                # Scrollbar for progress text
                scrollbar = ttk.Scrollbar(progress_text)
                scrollbar.pack(side='right', fill='y')
                progress_text.config(yscrollcommand=scrollbar.set)
                scrollbar.config(command=progress_text.yview)

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
                    import subprocess
                    start_time = time.time()  # Track update duration

                    # Get pre-update versions for all installed packages that have updates
                    pre_update_versions = {}
                    logger.info("Collecting pre-update versions...")
                    try:
                        # First get list of packages with updates
                        result = subprocess.run(["pacman", "-Qu"], capture_output=True, text=True)
                        if result.returncode == 0 and result.stdout:
                            for line in result.stdout.strip().split('\n'):
                                if line:
                                    # Format: "package current -> new"
                                    parts = line.split()
                                    if len(parts) >= 3 and parts[1] == '->':
                                        pkg_name = parts[0]
                                        current_ver = parts[1]
                                        new_ver = parts[2]
                                        pre_update_versions[pkg_name] = {
                                            'old': current_ver,
                                            'new': new_ver
                                        }
                    except Exception as e:
                        logger.warning(f"Failed to collect pre-update versions: {e}")

                    # Capture output for history
                    full_output = []

                    process = subprocess.Popen(
                        pacman_cmd,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.STDOUT,
                        text=True,
                        bufsize=1,
                        universal_newlines=True
                    )

                    status_label.config(text="Running system update...")

                    # Read output line by line
                    while True:
                        line = process.stdout.readline()
                        if not line and process.poll() is not None:
                            break
                        if line:
                            # Update progress dialog
                            self.main_window.root.after(0, lambda line_text=line.strip(): update_progress(line_text))
                            # Capture output for history
                            full_output.append(line)

                    # Get exit code
                    exit_code = process.poll()
                    success = (exit_code == 0)

                    # Calculate duration
                    duration = time.time() - start_time

                    # Update UI based on result
                    if success:
                        status_label.config(text="✅ System update completed successfully!", foreground='green')
                        self.main_window.root.after(
                            0, lambda: self.main_window.update_status(
                                "✅ System update completed", "success"))
                        # Refresh package list after update
                        self.main_window.root.after(1000, self.refresh_packages)

                        # Record update history if enabled
                        if self.main_window.config.get('update_history_enabled', False):
                            logger.info(
                                f"Update history is enabled, recording update (exit_code={exit_code}, success={success})")
                            from ..utils.update_history import UpdateHistoryManager, UpdateHistoryEntry
                            from datetime import datetime

                            # For full system update, we don't know specific packages
                            # So we'll record it as "System Update"
                            history_mgr = UpdateHistoryManager()

                            # Extract updated package names from output if possible
                            updated_packages = []
                            output_text = ''.join(full_output)

                            # Look for package update lines in output
                            import re
                            # Pattern matches lines like "upgrading package-name..."
                            upgrade_pattern = re.compile(r'upgrading\s+(\S+)\.\.\.', re.IGNORECASE)
                            matches = upgrade_pattern.findall(output_text)

                            # Also try to extract version info from output
                            # Pattern for lines like "upgrading package (1.2.3-1 -> 1.2.4-1)..."
                            version_pattern = re.compile(r'upgrading\s+(\S+)\s*\((\S+)\s*->\s*(\S+)\)', re.IGNORECASE)
                            version_matches = version_pattern.findall(output_text)

                            # Build version info dict
                            version_info = {}

                            # First use pre-collected versions
                            if pre_update_versions:
                                for pkg_name in matches:
                                    if pkg_name in pre_update_versions:
                                        version_info[pkg_name] = pre_update_versions[pkg_name]

                            # Then try to extract from output for any missing
                            for pkg_name, old_ver, new_ver in version_matches:
                                if pkg_name not in version_info:
                                    version_info[pkg_name] = {'old': old_ver, 'new': new_ver}
                                # Also add to matches if not already there
                                if pkg_name not in matches:
                                    matches.append(pkg_name)

                            # Check for reinstalls and exclude them
                            reinstall_pattern = re.compile(r'reinstalling\s+(\S+)\.\.\.', re.IGNORECASE)
                            reinstalled = reinstall_pattern.findall(output_text)

                            # Also check for "up to date -- reinstalling" pattern
                            reinstall_pattern2 = re.compile(
                                r'warning:\s+(\S+)-\S+\s+is up to date\s*--\s*reinstalling', re.IGNORECASE)
                            for match in reinstall_pattern2.finditer(output_text):
                                pkg_name = match.group(1)
                                if pkg_name not in reinstalled:
                                    reinstalled.append(pkg_name)

                            # Filter out reinstalled packages
                            if matches:
                                updated_packages = [pkg for pkg in matches if pkg not in reinstalled]
                                logger.info(
                                    f"Found {
                                        len(updated_packages)} actual updates (excluded {
                                        len(reinstalled)} reinstalls)")
                            else:
                                # If we can't parse specific packages, use a generic entry
                                updated_packages = ["Full System Update"]

                            # Only record if there were actual updates
                            if updated_packages:
                                # Filter version info to exclude reinstalls
                                filtered_version_info = {k: v for k, v in version_info.items()
                                                         if k not in reinstalled}

                                entry = UpdateHistoryEntry(
                                    timestamp=datetime.now(),
                                    packages=updated_packages,
                                    succeeded=success,
                                    exit_code=exit_code,
                                    duration_sec=duration,
                                    version_info=filtered_version_info if filtered_version_info else None
                                )

                                history_mgr.add(entry)
                                logger.info(f"Recorded system update to history: {len(updated_packages)} packages")

                                # Refresh update history panel if it exists
                                if 'history' in self.main_window.frames:
                                    history_frame = self.main_window.frames['history']
                                    # Force refresh to show new entry immediately
                                    self.main_window.root.after(100, lambda: history_frame.load_history())
                                    logger.info("Scheduled refresh of update history panel")
                            else:
                                logger.info("No update history recorded - all packages were reinstalls")

                    else:
                        if exit_code == 126 or exit_code == 127:
                            status_label.config(
                                text="❌ Authentication cancelled or pkexec not available", foreground='red')
                            self.main_window.root.after(
                                0, lambda: self.main_window.update_status(
                                    "Update cancelled", "warning"))
                        else:
                            status_label.config(text="❌ System update failed", foreground='red')
                            self.main_window.root.after(
                                0, lambda: self.main_window.update_status(
                                    f"❌ Update failed with exit code {exit_code}", "error"))

                except subprocess.TimeoutExpired:
                    status_label.config(text="❌ Update timed out", foreground='red')
                    try:
                        process.kill()
                    except BaseException:
                        pass
                except Exception as e:
                    logger.error(f"Error during pkexec update: {e}")
                    status_label.config(text=f"❌ Error: {str(e)}", foreground='red')

                # Enable close button
                close_btn.config(state='normal')

                # Don't auto-close - let users read the output and close manually

            except Exception as e:
                logger.error(f"Error starting system update: {e}")
                error_msg = str(e)
                self.main_window.root.after(0, lambda: messagebox.showerror(
                    "Error",
                    f"Failed to start system update: {error_msg}\n\n"
                    "Make sure pkexec is installed (polkit package)"
                ))

        # Use secure thread management
        from ..utils.thread_manager import create_managed_thread
        import uuid

        thread_id = f"pkg_update_{uuid.uuid4().hex[:8]}"
        thread = create_managed_thread(thread_id, update_thread, is_background=True)
        if thread is None:
            messagebox.showerror("Thread Error",
                                 "Unable to start system update: thread limit reached")
        else:
            # Start the thread!
            thread.start()
            logger.info(f"Started system update thread with ID: {thread_id}")

    def refresh_packages(self):
        """Refresh the package list."""
        self.load_packages()

    def remove_selected(self):
        """Remove selected packages with confirmation."""
        selection = self.package_tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select packages to remove")
            return

        # Get package names
        packages = []
        for item in selection:
            values = self.package_tree.item(item)['values']
            if values:
                packages.append(values[0])

        if not packages:
            return

        # Confirm removal
        msg = f"Remove {len(packages)} package(s)?\n\n"
        msg += "\n".join(packages[:10])
        if len(packages) > 10:
            msg += f"\n... and {len(packages) - 10} more"

        if not messagebox.askyesno("Confirm Removal", msg):
            return

        # Run removal with pkexec
        def remove_thread():
            try:
                # Build secure pacman command
                remove_cmd = ["pkexec", "pacman", "-R"] + packages

                # Create a progress dialog
                progress_dialog = tk.Toplevel(self.main_window.root)
                progress_dialog.title("Removing Packages")
                progress_dialog.geometry("600x400")
                progress_dialog.transient(self.main_window.root)

                # Center the dialog
                progress_dialog.update_idletasks()
                x = (progress_dialog.winfo_screenwidth() // 2) - (300)
                y = (progress_dialog.winfo_screenheight() // 2) - (200)
                progress_dialog.geometry(f"+{x}+{y}")

                # Create UI elements
                info_label = ttk.Label(progress_dialog,
                                       text=f"Removing {len(packages)} package(s) with system privileges...",
                                       font=('Arial', 12))
                info_label.pack(pady=10)

                # Package list
                pkg_frame = ttk.Frame(progress_dialog)
                pkg_frame.pack(fill='x', padx=20, pady=5)
                ttk.Label(pkg_frame, text="Packages to remove:", font=('Arial', 10, 'bold')).pack(anchor='w')
                for pkg in packages[:10]:
                    ttk.Label(pkg_frame, text=f"  • {pkg}").pack(anchor='w')
                if len(packages) > 10:
                    ttk.Label(pkg_frame, text=f"  ... and {len(packages) - 10} more").pack(anchor='w')

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
                try:
                    import subprocess
                    process = subprocess.Popen(
                        remove_cmd,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.STDOUT,
                        text=True,
                        bufsize=1,
                        universal_newlines=True
                    )

                    status_label.config(text="Removing packages...")

                    # Read output line by line
                    while True:
                        line = process.stdout.readline()
                        if not line and process.poll() is not None:
                            break
                        if line:
                            # Update progress dialog
                            self.main_window.root.after(0, lambda line_text=line.strip(): update_progress(line_text))

                    # Get exit code
                    exit_code = process.poll()
                    success = (exit_code == 0)

                    # Update UI based on result
                    if success:
                        status_label.config(text="✅ Package removal completed successfully!", foreground='green')
                        self.main_window.root.after(
                            0, lambda: messagebox.showinfo(
                                "Success", f"Successfully removed {
                                    len(packages)} package(s)"))
                        # Refresh package list
                        self.main_window.root.after(1000, self.refresh_packages)
                    else:
                        if exit_code == 126 or exit_code == 127:
                            status_label.config(
                                text="❌ Authentication cancelled or pkexec not available", foreground='red')
                        else:
                            status_label.config(text="❌ Package removal failed", foreground='red')
                            self.main_window.root.after(0, lambda: messagebox.showerror(
                                "Error", f"Package removal failed with exit code {exit_code}"))

                except subprocess.TimeoutExpired:
                    status_label.config(text="❌ Removal timed out", foreground='red')
                    try:
                        process.kill()
                    except BaseException:
                        pass
                except Exception as e:
                    logger.error(f"Error during package removal: {e}")
                    status_label.config(text=f"❌ Error: {str(e)}", foreground='red')

                # Enable close button
                close_btn.config(state='normal')

                # Don't auto-close - let users read the output and close manually

            except Exception as e:
                logger.error(f"Failed to remove packages: {e}")
                error_msg = str(e)
                self.main_window.root.after(0, lambda: messagebox.showerror(
                    "Error",
                    f"Failed to remove packages: {error_msg}\n\n"
                    "Make sure pkexec is installed (polkit package)"
                ))

        # Use secure thread management
        from ..utils.thread_manager import create_managed_thread
        import uuid

        thread_id = f"pkg_remove_{uuid.uuid4().hex[:8]}"
        thread = create_managed_thread(thread_id, remove_thread, is_background=True)
        if thread is None:
            messagebox.showerror("Thread Error",
                                 "Unable to start package removal: thread limit reached")

    def clean_orphans(self):
        """Clean orphaned packages."""
        def cleanup_thread():
            try:
                # First check for orphans using secure subprocess
                result = SecureSubprocess.run(
                    ["pacman", "-Qdtq"],
                    capture_output=True,
                    text=True,
                    check=False
                )

                if result.returncode != 0 or not result.stdout.strip():
                    self.main_window.root.after(0, lambda: messagebox.showinfo(
                        "No Orphans",
                        "No orphaned packages found on your system."
                    ))
                    return

                # Parse orphan list
                orphans = result.stdout.strip().split('\n')
                orphan_count = len(orphans)

                # Show confirmation
                msg = f"Found {orphan_count} orphaned package(s):\n\n"
                msg += "\n".join(orphans[:10])
                if orphan_count > 10:
                    msg += f"\n... and {orphan_count - 10} more"
                msg += "\n\nRemove all orphaned packages?"

                if not messagebox.askyesno("Confirm Orphan Removal", msg):
                    return

                # Build removal command with pkexec and --noconfirm flag
                remove_cmd = ["pkexec", "pacman", "-Rns", "--noconfirm"] + orphans

                # Create a progress dialog
                progress_dialog = tk.Toplevel(self.main_window.root)
                progress_dialog.title("Cleaning Orphans")
                progress_dialog.geometry("700x500")
                progress_dialog.transient(self.main_window.root)

                # Center the dialog
                progress_dialog.update_idletasks()
                x = (progress_dialog.winfo_screenwidth() // 2) - (350)
                y = (progress_dialog.winfo_screenheight() // 2) - (250)
                progress_dialog.geometry(f"+{x}+{y}")

                # Create UI elements
                info_label = ttk.Label(progress_dialog,
                                       text=f"Removing {orphan_count} orphaned package(s)...",
                                       font=('Arial', 12))
                info_label.pack(pady=10)

                # Progress text
                progress_text = tk.Text(progress_dialog, height=20, width=80, wrap='word')
                progress_text.pack(fill='both', expand=True, padx=20, pady=10)

                # Scrollbar for progress text
                scrollbar = ttk.Scrollbar(progress_text)
                scrollbar.pack(side='right', fill='y')
                progress_text.config(yscrollcommand=scrollbar.set)
                scrollbar.config(command=progress_text.yview)

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
                    import subprocess
                    process = subprocess.Popen(
                        remove_cmd,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.STDOUT,
                        text=True,
                        bufsize=1,
                        universal_newlines=True
                    )

                    status_label.config(text="Removing orphaned packages...")

                    # Read output line by line
                    while True:
                        line = process.stdout.readline()
                        if not line and process.poll() is not None:
                            break
                        if line:
                            # Update progress dialog
                            self.main_window.root.after(0, lambda line_text=line.strip(): update_progress(line_text))

                    # Get exit code
                    exit_code = process.poll()
                    success = (exit_code == 0)

                    # Update UI based on result
                    if success:
                        status_label.config(
                            text=f"✅ Successfully removed {orphan_count} orphaned package(s)!",
                            foreground='green')
                        self.main_window.root.after(0, lambda: messagebox.showinfo(
                            "Success", f"Successfully removed {orphan_count} orphaned package(s)"))
                        # Refresh package list
                        self.main_window.root.after(1000, self.refresh_packages)
                    else:
                        if exit_code == 126 or exit_code == 127:
                            status_label.config(
                                text="❌ Authentication cancelled or pkexec not available", foreground='red')
                        else:
                            status_label.config(text="❌ Orphan removal failed", foreground='red')
                            self.main_window.root.after(0, lambda: messagebox.showerror(
                                "Error", f"Orphan removal failed with exit code {exit_code}"))

                except subprocess.TimeoutExpired:
                    status_label.config(text="❌ Removal timed out", foreground='red')
                    try:
                        process.kill()
                    except BaseException:
                        pass
                except Exception as e:
                    logger.error(f"Error during orphan cleanup: {e}")
                    status_label.config(text=f"❌ Error: {str(e)}", foreground='red')

                # Enable close button
                close_btn.config(state='normal')

                # Don't auto-close - let users read the output and close manually

            except Exception as e:
                logger.error(f"Error in orphan cleanup: {e}")
                error_msg = str(e)
                self.main_window.root.after(0, lambda: messagebox.showerror(
                    "Error",
                    f"Failed to check/clean orphans: {error_msg}"
                ))

        # Use secure thread management
        from ..utils.thread_manager import create_managed_thread
        import uuid

        thread_id = f"orphan_cleanup_{uuid.uuid4().hex[:8]}"
        thread = create_managed_thread(thread_id, cleanup_thread, is_background=True)
        if thread is None:
            messagebox.showerror("Thread Error",
                                 "Unable to start orphan cleanup: thread limit reached")
        else:
            # Start the thread!
            thread.start()
            logger.info(f"Started orphan cleanup thread with ID: {thread_id}")

    def _filter_packages(self, packages: List[Dict[str, str]], filter_type: str) -> List[Dict[str, str]]:
        """Filter packages based on type."""
        if filter_type == "all":
            return packages
        elif filter_type == "critical":
            critical = self.config.get_critical_packages()
            return [p for p in packages if p.get('name') in critical]
        elif filter_type == "installed":
            return packages  # All are installed
        elif filter_type == "updates":

            return []
        return packages

    def _show_orphan_confirmation_dialog(self, orphan_packages):
        """Show a custom dialog to confirm orphan package removal."""
        # Create dialog window
        dialog = tk.Toplevel(self.main_window.root)
        dialog.title("Clean Orphans")
        dialog.configure(bg=self.colors['background'])
        dialog.resizable(True, True)

        # Use proper positioning
        self.position_window(dialog, 500, 400, self.main_window.root)

        # Header
        header_frame = tk.Frame(dialog, bg=self.colors['primary'], height=60)
        header_frame.pack(fill='x')
        header_frame.pack_propagate(False)

        header_label = tk.Label(header_frame,
                                text=f"Found {len(orphan_packages)} truly orphaned package(s)",
                                font=('Segoe UI', 14, 'bold'),
                                fg='white',
                                bg=self.colors['primary'])
        header_label.pack(expand=True)

        # Content frame
        content_frame = tk.Frame(dialog, bg=self.colors['background'])
        content_frame.pack(fill='both', expand=True, padx=20, pady=10)

        # Info label
        info_label = tk.Label(content_frame,
                              text="The following packages will be removed:",
                              font=('Segoe UI', 11, 'normal'),
                              fg=self.colors['text'],
                              bg=self.colors['background'])
        info_label.pack(anchor='w', pady=(0, 10))

        # Package list frame with scrollbar
        list_frame = tk.Frame(content_frame, bg=self.colors['background'])
        list_frame.pack(fill='both', expand=True)

        # Create listbox with scrollbar
        listbox = tk.Listbox(list_frame,
                             font=('Consolas', 10, 'normal'),
                             bg=self.colors['surface'],
                             fg=self.colors['text'],
                             selectbackground=self.colors['primary'],
                             selectforeground='white',
                             borderwidth=1,
                             relief='solid',
                             activestyle='none')

        scrollbar = ttk.Scrollbar(list_frame, orient='vertical', command=listbox.yview)
        listbox.configure(yscrollcommand=scrollbar.set)

        # Pack listbox and scrollbar
        listbox.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')

        # Populate listbox
        for pkg in sorted(orphan_packages):
            listbox.insert(tk.END, f"• {pkg}")

        # Warning label
        warning_label = tk.Label(content_frame,
                                 text="Note: This will run 'sudo pacman -Rns' on these packages.",
                                 font=('Segoe UI', 10, 'italic'),
                                 fg=self.colors['warning'],
                                 bg=self.colors['background'])
        warning_label.pack(anchor='w', pady=(0, 15))

        # Button frame
        button_frame = tk.Frame(content_frame, bg=self.colors['background'])
        button_frame.pack(fill='x')

        # Result variable
        result = {'confirmed': False}

        def confirm():
            result['confirmed'] = True
            dialog.destroy()

        def cancel():
            result['confirmed'] = False
            dialog.destroy()

        # Buttons
        cancel_btn = tk.Button(button_frame,
                               text="Cancel",
                               font=('Segoe UI', 11, 'normal'),
                               fg='white',
                               bg=self.colors['secondary'],
                               activebackground=self.colors['secondary'],
                               activeforeground='white',
                               bd=0,
                               padx=20,
                               pady=8,
                               cursor='hand2',
                               command=cancel)
        cancel_btn.pack(side='right', padx=(10, 0))

        confirm_btn = tk.Button(button_frame,
                                text=f"Remove {len(orphan_packages)} packages",
                                font=('Segoe UI', 11, 'normal'),
                                fg='white',
                                bg=self.colors['error'],
                                activebackground=self.colors['error'],
                                activeforeground='white',
                                bd=0,
                                padx=20,
                                pady=8,
                                cursor='hand2',
                                command=confirm)
        confirm_btn.pack(side='right')

        # Bind Enter and Escape keys
        dialog.bind('<Return>', lambda e: confirm())
        dialog.bind('<Escape>', lambda e: cancel())

        # Focus the dialog
        dialog.focus_set()

        # Wait for dialog to close
        dialog.wait_window()

        return result['confirmed']

    def refresh_theme(self):
        """Re-apply theme/colors to all widgets in this frame."""
        # Clear all widgets and recreate the UI with new colors
        for widget in self.winfo_children():
            widget.destroy()
        self.setup_ui()

        # Reload packages after theme refresh
        self._loading_in_progress = False  # Reset the flag since UI was rebuilt
        self.after(500, self._safe_load_packages)

    def show_error(self, message: str):
        """Show an error message dialog."""
        messagebox.showerror("Error", message)

    def _add_tooltip(self, widget, text):
        """Add a tooltip to a widget."""
        def on_enter(event):
            tooltip = tk.Toplevel()
            tooltip.wm_overrideredirect(True)
            tooltip.wm_geometry(f"+{event.x_root + 10}+{event.y_root + 10}")
            label = tk.Label(tooltip,
                             text=text,
                             font=('Segoe UI', 9, 'normal'),
                             bg=self.colors['surface'],
                             fg=self.colors['text'],
                             borderwidth=1,
                             relief='solid',
                             padx=5,
                             pady=3)
            label.pack()
            widget.tooltip = tooltip

        def on_leave(event):
            if hasattr(widget, 'tooltip'):
                widget.tooltip.destroy()
                del widget.tooltip

        widget.bind('<Enter>', on_enter)
        widget.bind('<Leave>', on_leave)

    def _format_install_date(self, install_date: str) -> str:
        """Format install date to international standard YYYY-MM-DD HH:MM."""
        if not install_date or install_date.lower() in ['unknown', 'n/a', '']:
            return install_date

        try:
            from datetime import datetime

            # With LC_ALL=C, pacman will output dates in English format
            # Format: Mon 13 Jul 2025 21:05:17 UTC or similar
            formats_to_try = [
                '%a %d %b %Y %H:%M:%S %Z',      # Mon 13 Jul 2025 21:05:17 UTC
                '%a %d %b %Y %H:%M:%S',         # Mon 13 Jul 2025 21:05:17
                '%a %b %d %H:%M:%S %Z %Y',      # Mon Jul 13 21:05:17 UTC 2025
                '%a %b %d %H:%M:%S %Y',         # Mon Jul 13 21:05:17 2025
            ]

            # Remove timezone suffix as it often causes parsing issues
            date_no_tz = install_date
            tz_patterns = [' CEST', ' CET', ' UTC', ' GMT', ' EDT', ' EST', ' PDT', ' PST',
                           ' AEST', ' AEDT', ' JST', ' CST', ' BST', ' IST']
            for tz in tz_patterns:
                date_no_tz = date_no_tz.replace(tz, '')
            date_no_tz = date_no_tz.strip()

            # Try each format
            parsed_date = None
            for fmt in formats_to_try:
                for date_str in [install_date, date_no_tz]:
                    try:
                        parsed_date = datetime.strptime(date_str.strip(), fmt)
                        break
                    except ValueError:
                        continue
                if parsed_date:
                    break

            # If parsing succeeded, format to ISO with time
            if parsed_date:
                return parsed_date.strftime('%Y-%m-%d %H:%M')

            # Fallback: try to extract components using regex
            # This handles edge cases and non-standard formats

            # Extract year (4 digits starting with 19 or 20)
            year_match = re.search(r'\b(19\d{2}|20\d{2})\b', install_date)
            # Extract time (HH:MM:SS or HH:MM)
            time_match = re.search(r'\b(\d{1,2}:\d{2}(?::\d{2})?)\b', install_date)
            # Extract day (1-31)
            day_match = re.search(r'\b([1-9]|[12]\d|3[01])\b', install_date)
            # Extract month (Jan-Dec or 1-12)
            month_names = {
                'jan': '01', 'feb': '02', 'mar': '03', 'apr': '04',
                'may': '05', 'jun': '06', 'jul': '07', 'aug': '08',
                'sep': '09', 'oct': '10', 'nov': '11', 'dec': '12'
            }

            month = None
            # First try to find month name
            for month_name, month_num in month_names.items():
                if month_name in install_date.lower():
                    month = month_num
                    break

            # If no month name found, look for numeric month
            if not month:
                # Look for patterns like DD.MM or MM/DD
                date_pattern = re.search(r'\b(\d{1,2})[./\-](\d{1,2})\b', install_date)
                if date_pattern:
                    num1, num2 = int(date_pattern.group(1)), int(date_pattern.group(2))
                    if 1 <= num1 <= 12 and 1 <= num2 <= 31:
                        month = str(num1).zfill(2)
                        if not day_match:
                            day_match = re.match(r'(\d+)', str(num2))
                    elif 1 <= num2 <= 12 and 1 <= num1 <= 31:
                        month = str(num2).zfill(2)
                        if not day_match:
                            day_match = re.match(r'(\d+)', str(num1))

            # Build the date string from components
            if year_match and month and day_match and time_match:
                year = year_match.group(1)
                day = str(day_match.group(1)).zfill(2)
                time_str = time_match.group(1)
                # Ensure time is in HH:MM format
                if len(time_str.split(':')) == 3:
                    time_str = ':'.join(time_str.split(':')[:2])
                return f"{year}-{month}-{day} {time_str}"
            elif year_match and time_match:
                # At least return year and time if we have them
                year = year_match.group(1)
                time_str = time_match.group(1)
                if len(time_str.split(':')) == 3:
                    time_str = ':'.join(time_str.split(':')[:2])
                return f"{year} {time_str}"

            # Ultimate fallback: return truncated original
            return install_date[:20] + "..." if len(install_date) > 20 else install_date

        except Exception as e:
            logger.debug(f"Failed to parse install date '{install_date}': {e}")
            # If all parsing fails, return truncated original
            return install_date[:20] + "..." if len(install_date) > 20 else install_date

    def _configure_columns(self):
        """Configure treeview columns with fixed layout for our fixed window size."""
        # Fixed column configuration for 1200px window width
        # Available width: ~950px (1200 - sidebar(250) + margins)
        column_config = {
            '#0': {'width': 280, 'min': 250},  # Package Name
            'version': {'width': 140, 'min': 120},  # Version
            'repository': {'width': 100, 'min': 80},  # Repository
            'size': {'width': 100, 'min': 80},  # Size
            'install_date': {'width': 180, 'min': 150},  # Install Date
            'status': {'width': 100, 'min': 80}  # Priority
        }

        # Apply fixed column widths
        for col_id, config in column_config.items():
            self.package_tree.column(col_id, width=config['width'],
                                     minwidth=config['min'], stretch=True)

        # Show all columns for fixed layout
        self.package_tree['displaycolumns'] = self.package_tree['columns']

    def cleanup_timers(self):
        """Clean up all managed timers for this component."""
        if hasattr(self, '_component_id'):
            cancelled = TimerResourceManager.cancel_component_timers(self._component_id)
            if cancelled > 0:
                logger.debug(f"Cancelled {cancelled} timers for package manager component")

    def destroy(self):
        """Override destroy to cancel pending operations and ensure proper cleanup."""
        # Cancel any pending load timer
        if hasattr(self, '_load_timer_id') and self._load_timer_id:
            self.after_cancel(self._load_timer_id)
            self._load_timer_id = None

        # Clean up timers
        self.cleanup_timers()
        
        # Clear sensitive data
        self.clear_sensitive_data()

        # Call parent destroy
        super().destroy()

    def clear_sensitive_data(self):
        """Clear sensitive package and system data from memory."""
        try:
            # Clear package information that might be sensitive
            sensitive_attrs = ['packages_cache', 'installed_packages', 'update_list', 'critical_packages']
            for attr in sensitive_attrs:
                if hasattr(self, attr):
                    value = getattr(self, attr)
                    if isinstance(value, (list, dict, set)):
                        value.clear()
                    setattr(self, attr, None)

            # Clear any cached package data
            if hasattr(self, 'package_tree') and self.package_tree:
                try:
                    # Clear the treeview data
                    for item in self.package_tree.get_children():
                        self.package_tree.delete(item)
                except BaseException:
                    pass

            # Force memory cleanup
            force_memory_cleanup()
            logger.debug("Cleared sensitive package data from memory")

        except Exception as e:
            logger.debug(f"Error clearing sensitive package data: {e}")

    def __del__(self):
        """Destructor to ensure cleanup even if destroy isn't called."""
        try:
            self.cleanup_timers()
            self.clear_sensitive_data()
        except Exception:
            pass  # Ignore errors during destruction

        # Force redraw to apply changes
        if hasattr(self, 'package_tree'):
            self.package_tree.update_idletasks()
