"""
Update history frame for the Arch Smart Update Checker GUI.
"""

# SPDX-License-Identifier: GPL-3.0-or-later

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from datetime import datetime
from typing import Optional, List

from ..utils.update_history import UpdateHistoryManager, UpdateHistoryEntry
from ..utils.logger import get_logger
from .window_mixin import WindowPositionMixin
from .dimensions import get_dimensions

logger = get_logger(__name__)


class UpdateHistoryFrame(ttk.Frame, WindowPositionMixin):
    """Frame for viewing and managing update history."""

    def __init__(self, parent, main_window):
        """Initialize the update history frame."""
        super().__init__(parent, style='Content.TFrame')
        self.main_window = main_window
        self.update_history = main_window.update_history
        self.dims = get_dimensions()
        self.search_var = tk.StringVar()
        self.search_var.trace('w', self._on_search_changed)

        self._build_ui()
        self.load_history()

    def _build_ui(self):
        """Build the UI components."""
        # Configure self for expansion
        self.rowconfigure(1, weight=1)
        self.columnconfigure(0, weight=1)

        # Calculate font sizes for fixed layout
        font_scale = 1.0  # Standard scaling for fixed window
        title_font_size = max(int(24 * font_scale), 20)  # Min 20px, scaled up
        subtitle_font_size = max(int(14 * font_scale), 12)  # Min 12px, scaled up

        # Header container - directly on background, not in a card
        header_frame = ttk.Frame(self, style='Content.TFrame')
        header_frame.grid(row=0, column=0, sticky='ew', padx=20, pady=(20, 10))

        # Title
        title_label = tk.Label(header_frame,
                               text="📜 Update History",
                               font=('Segoe UI', title_font_size, 'bold'),
                               fg=self.main_window.colors['text'],
                               bg=self.main_window.colors['background'])
        title_label.pack(anchor='w', padx=20, pady=(20, 10))

        # Subtitle
        subtitle_label = tk.Label(header_frame,
                                  text="Track your system update activities",
                                  font=('Segoe UI', subtitle_font_size, 'normal'),
                                  fg=self.main_window.colors['text_secondary'],
                                  bg=self.main_window.colors['background'])
        subtitle_label.pack(anchor='w', padx=20, pady=(0, 10))

        # Since label (smaller, below subtitle)
        self.since_label = tk.Label(header_frame,
                                    text="",
                                    font=('Segoe UI', 11, 'normal'),
                                    fg=self.main_window.colors['text_secondary'],
                                    bg=self.main_window.colors['background'])
        self.since_label.pack(anchor='w', padx=20, pady=(0, 10))

        # Main content area
        content = tk.Frame(self, bg=self.main_window.colors['background'])
        content.grid(row=1, column=0, sticky='nsew', padx=20, pady=20)
        content.rowconfigure(1, weight=1)
        content.columnconfigure(0, weight=1)

        # Search bar
        search_frame = tk.Frame(content, bg=self.main_window.colors['background'])
        search_frame.grid(row=0, column=0, sticky='ew', pady=(0, 10))

        tk.Label(search_frame,
                 text="🔍 Search:",
                 font=('Segoe UI', 11),
                 bg=self.main_window.colors['background'],
                 fg=self.main_window.colors['text']).pack(side='left', padx=(0, 10))

        search_entry = tk.Entry(search_frame,
                                textvariable=self.search_var,
                                font=('Segoe UI', 11),
                                bg=self.main_window.colors['surface'],
                                fg=self.main_window.colors['text'],
                                insertbackground=self.main_window.colors['text'])
        search_entry.pack(side='left', fill='x', expand=True)

        # Treeview for history
        tree_frame = tk.Frame(content, bg=self.main_window.colors['surface'])
        tree_frame.grid(row=1, column=0, sticky='nsew')

        # Configure treeview style
        style = ttk.Style()

        # Use standard font sizes for fixed window (matching Package Manager)
        scaled_font_size = 10  # Standard font size
        heading_font_size = 11  # Slightly larger for headings

        # Calculate row height for fixed layout
        base_row_height = int(scaled_font_size * 2.2)  # Font size * 2.2 for good readability
        min_height = 22  # Standard minimum height
        row_height = max(base_row_height, min_height)

        style.configure('UpdateHistory.Treeview',
                        background=self.main_window.colors['surface'],
                        foreground=self.main_window.colors['text'],
                        fieldbackground=self.main_window.colors['surface'],
                        borderwidth=1,
                        relief='solid',
                        font=('Segoe UI', scaled_font_size, 'normal'),  # Set font for data rows
                        rowheight=row_height)  # Set row height
        style.configure('UpdateHistory.Treeview.Heading',
                        background=self.main_window.colors['primary'],
                        foreground='white',
                        font=('Segoe UI', heading_font_size, 'bold'),  # Added font configuration
                        relief='raised',  # Add raised relief for visual separation
                        borderwidth=1)    # Add border for column headers
        style.map('UpdateHistory.Treeview',
                  background=[('selected', self.main_window.colors['accent'])],
                  foreground=[('selected', 'white')])

        # Sort state tracking
        self.sort_column = None
        self.sort_reverse = False

        # Create treeview with fixed columns
        self.all_columns = ('date', 'packages', 'versions', 'duration', 'status')
        self.tree = ttk.Treeview(tree_frame, columns=self.all_columns, show='tree headings',
                                 style='UpdateHistory.Treeview', height=15)

        # Configure columns
        self.tree.heading('#0', text='')
        self.tree.heading('date', text='Date/Time', anchor='c', command=lambda: self.sort_entries('date'))
        self.tree.heading('packages', text='Packages', anchor='c', command=lambda: self.sort_entries('packages'))
        self.tree.heading('versions', text='Version Changes', anchor='c', command=lambda: self.sort_entries('versions'))
        self.tree.heading('duration', text='Duration', anchor='c', command=lambda: self.sort_entries('duration'))
        self.tree.heading('status', text='Status', anchor='c', command=lambda: self.sort_entries('status'))

        # Configure column properties
        self.tree.column('#0', width=0, stretch=False)
        self._configure_columns()

        # Create scrollbar
        scrollbar = ttk.Scrollbar(tree_frame, orient='vertical', command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)

        # Pack components with proper scrollbar padding
        self.tree.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')

        # Bind double-click to show details
        self.tree.bind('<Double-Button-1>', self._on_item_double_click)

        # Button frame
        btn_frame = tk.Frame(content, bg=self.main_window.colors['background'])
        btn_frame.grid(row=2, column=0, sticky='ew', pady=(10, 0))

        # Left side buttons
        left_buttons = tk.Frame(btn_frame, bg=self.main_window.colors['background'])
        left_buttons.pack(side='left')

        tk.Button(left_buttons,
                  text="Export...",
                  font=('Segoe UI', 11),
                  bg=self.main_window.colors['accent'],
                  fg='white',
                  activebackground=self.main_window.colors['primary'],
                  activeforeground='white',
                  bd=0,
                  padx=15,
                  pady=8,
                  cursor='hand2',
                  command=self.export_history).pack(side='left', padx=(0, 10))

        tk.Button(left_buttons,
                  text="Clear History",
                  font=('Segoe UI', 11),
                  bg=self.main_window.colors['error'],
                  fg='white',
                  activebackground='#d32f2f',
                  activeforeground='white',
                  bd=0,
                  padx=15,
                  pady=8,
                  cursor='hand2',
                  command=self.clear_history).pack(side='left')

        # Right side button
        self.toggle_btn = tk.Button(btn_frame,
                                    text="",
                                    font=('Segoe UI', 11),
                                    bg=self.main_window.colors['surface'],
                                    fg=self.main_window.colors['text'],
                                    bd=1,
                                    relief='solid',
                                    padx=15,
                                    pady=8,
                                    cursor='hand2',
                                    command=self.toggle_recording)
        self.toggle_btn.pack(side='right')
        self._update_toggle_button()

        # Empty state label
        self.empty_label = tk.Label(
            tree_frame,
            text="No update history yet.\nUpdates will be recorded here when history is enabled.",
            font=(
                'Segoe UI',
                12),
            bg=self.main_window.colors['surface'],
            fg=self.main_window.colors['text_secondary'],
            justify='center')

    def load_history(self):
        """Load and display update history."""
        logger.info(f"Loading update history from {self.update_history.path}")

        # Clear cache to force reload from disk
        self.update_history._cached_entries = None

        # Clear existing items
        for item in self.tree.get_children():
            self.tree.delete(item)

        # Get all history entries
        entries = self.update_history.all()
        logger.info(f"Found {len(entries)} history entries")

        # Update "since" label
        if entries:
            oldest_date = entries[-1].timestamp.strftime('%Y-%m-%d')
            self.since_label.configure(text=f"Recording since {oldest_date}")
        else:
            self.since_label.configure(text="")

        # Apply search filter if active
        search_term = self.search_var.get().lower()
        if search_term:
            filtered_entries = []
            for e in entries:
                # Search in packages
                if search_term in ' '.join(e.packages).lower():
                    filtered_entries.append(e)
                    continue
                # Search in version info
                if e.version_info:
                    for pkg, v_info in e.version_info.items():
                        if (search_term in v_info.get('old', '').lower() or
                                search_term in v_info.get('new', '').lower()):
                            filtered_entries.append(e)
                            break
            entries = filtered_entries

        # Show empty state if no entries
        if not entries:
            self.empty_label.place(relx=0.5, rely=0.5, anchor='center')
        else:
            self.empty_label.place_forget()

            # Add entries to tree (newest first)
            for entry in entries:
                # Format values - use shorter date format
                date_str = entry.timestamp.strftime('%Y-%m-%d %H:%M')

                # Show first 3 packages + count
                if len(entry.packages) <= 3:
                    packages_str = ', '.join(entry.packages)
                else:
                    packages_str = f"{', '.join(entry.packages[:3])} +{len(entry.packages) - 3}"

                # Format version changes
                versions_str = ""
                if entry.version_info:
                    # Show first package's version info
                    first_pkg = entry.packages[0] if entry.packages else None
                    if first_pkg and first_pkg in entry.version_info:
                        v_info = entry.version_info[first_pkg]
                        if 'old' in v_info and 'new' in v_info:
                            versions_str = f"{v_info['old']} → {v_info['new']}"
                        else:
                            # Fallback if structure is different
                            versions_str = str(v_info)
                        if len(entry.packages) > 1:
                            versions_str += f" (+{len(entry.packages) - 1})"
                    else:
                        # Show raw version info for debugging
                        versions_str = f"Data: {entry.version_info}"
                else:
                    versions_str = "N/A"

                # Format duration
                if entry.duration_sec < 60:
                    duration_str = f"{entry.duration_sec:.1f}s"
                else:
                    minutes = int(entry.duration_sec / 60)
                    seconds = int(entry.duration_sec % 60)
                    duration_str = f"{minutes}m {seconds}s"

                # Status
                status_str = "✅ Success" if entry.succeeded else "❌ Failed"

                # Insert with tag for coloring
                tag = 'success' if entry.succeeded else 'error'
                self.tree.insert('', 'end', values=(
                    date_str,
                    packages_str,
                    versions_str,
                    duration_str,
                    status_str
                ), tags=(tag,))

            # Configure tags
            self.tree.tag_configure('success', foreground=self.main_window.colors['success'])
            self.tree.tag_configure('error', foreground=self.main_window.colors['error'])

    def _on_search_changed(self, *args):
        """Handle search text change."""
        self.load_history()

    def sort_entries(self, column):
        """Sort entries by the specified column."""
        # Get all items
        items = []
        for item in self.tree.get_children():
            values = self.tree.item(item)['values']
            col_index = {
                'date': 0,
                'packages': 1,
                'versions': 2,
                'duration': 3,
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
        if column == 'date':
            # Sort by timestamp (already in sortable format)
            items.sort(key=lambda x: x[0], reverse=self.sort_reverse)
        elif column == 'packages':
            # Sort by package count and names
            items.sort(key=lambda x: x[0].lower() if isinstance(x[0], str) else str(x[0]),
                       reverse=self.sort_reverse)
        elif column == 'duration':
            # Parse duration for proper numeric sorting
            def parse_duration(dur_str):
                if isinstance(dur_str, str):
                    if 'm' in dur_str:
                        parts = dur_str.replace('m', '').replace('s', '').split()
                        if len(parts) == 2:
                            return float(parts[0]) * 60 + float(parts[1])
                    elif 's' in dur_str:
                        return float(dur_str.replace('s', ''))
                return 0
            items.sort(key=lambda x: parse_duration(x[0]), reverse=self.sort_reverse)
        else:
            # Text-based sorting for other columns
            items.sort(key=lambda x: x[0].lower() if isinstance(x[0], str) else str(x[0]),
                       reverse=self.sort_reverse)

        # Re-insert items in sorted order
        for index, (_, item) in enumerate(items):
            self.tree.move(item, '', index)

        # Update column heading to show sort indicator
        for col in self.all_columns:
            if col == column:
                # Add sort indicator
                heading_text = self.tree.heading(col)['text'].rstrip(' ▲▼')
                indicator = ' ▼' if self.sort_reverse else ' ▲'
                self.tree.heading(col, text=heading_text + indicator)
            else:
                # Remove sort indicator from other columns
                heading_text = self.tree.heading(col)['text'].rstrip(' ▲▼')
                self.tree.heading(col, text=heading_text)

    def _on_item_double_click(self, event):
        """Handle double-click on history item."""
        selection = self.tree.selection()
        if not selection:
            return

        # Get the selected item's index
        item = selection[0]
        item_index = self.tree.index(item)

        # Get the corresponding entry
        entries = self.update_history.all()
        search_term = self.search_var.get().lower()
        if search_term:
            entries = [e for e in entries if search_term in ' '.join(e.packages).lower()]

        if item_index < len(entries):
            entry = entries[item_index]
            self._show_entry_details(entry)

    def _show_entry_details(self, entry: UpdateHistoryEntry):
        """Show detailed view of a history entry."""
        dialog = tk.Toplevel(self.main_window.root)
        dialog.title("Update Details")
        dialog.configure(bg=self.main_window.colors['background'])

        # Use position_window for persistent positioning [[memory:2371890]]
        self.position_window(dialog, width=600, height=400, parent=self.main_window.root)

        # Content
        content = tk.Frame(dialog, bg=self.main_window.colors['background'])
        content.pack(fill='both', expand=True, padx=20, pady=20)

        # Title
        tk.Label(content,
                 text="Update Details",
                 font=('Segoe UI', 16, 'bold'),
                 bg=self.main_window.colors['background'],
                 fg=self.main_window.colors['text']).pack(pady=(0, 20))

        # Details frame
        details = tk.Frame(content, bg=self.main_window.colors['surface'], bd=1, relief='solid')
        details.pack(fill='both', expand=True, pady=(0, 10))

        # Create text widget for details
        text = tk.Text(details,
                       wrap='word',
                       font=('Segoe UI', 11),
                       bg=self.main_window.colors['surface'],
                       fg=self.main_window.colors['text'],
                       bd=0,
                       padx=15,
                       pady=15)
        text.pack(fill='both', expand=True)

        # Add details
        text.insert('end', f"Date/Time: {entry.timestamp.strftime('%Y-%m-%d %H:%M:%S')}\n")
        text.insert('end', f"Duration: {entry.duration_sec:.1f} seconds\n")
        text.insert('end', f"Exit Code: {entry.exit_code}\n")
        text.insert(
            'end', f"Result: {
                '✅ Success' if entry.succeeded else f'❌ Failed (exit code {
                    entry.exit_code})'}\n\n")
        text.insert('end', f"Packages ({len(entry.packages)}):\n")
        for pkg in entry.packages:
            # Include version info if available
            if entry.version_info and pkg in entry.version_info:
                v_info = entry.version_info[pkg]
                text.insert('end', f"  • {pkg}: {v_info['old']} → {v_info['new']}\n")
            else:
                text.insert('end', f"  • {pkg}\n")

        text.configure(state='disabled')

        # Close button
        tk.Button(content,
                  text="Close",
                  font=('Segoe UI', 11),
                  bg=self.main_window.colors['primary'],
                  fg='white',
                  bd=0,
                  padx=20,
                  pady=8,
                  cursor='hand2',
                  command=dialog.destroy).pack()

    def export_history(self):
        """Export update history to file."""
        # Ask for file location
        filename = filedialog.asksaveasfilename(
            title="Export Update History",
            defaultextension=".json",
            filetypes=[
                ("JSON files", "*.json"),
                ("CSV files", "*.csv"),
                ("All files", "*.*")
            ]
        )

        if not filename:
            return

        try:
            # Determine format from extension
            format_ = 'csv' if filename.lower().endswith('.csv') else 'json'
            self.update_history.export(filename, format_)

            messagebox.showinfo("Export Complete",
                                f"Update history exported successfully to:\n{filename}")
        except Exception as e:
            logger.error(f"Failed to export history: {e}")
            messagebox.showerror("Export Error",
                                 f"Failed to export update history:\n{str(e)}")

    def clear_history(self):
        """Clear all update history."""
        if not messagebox.askyesno("Confirm Clear",
                                   "Are you sure you want to clear all update history?\n\n"
                                   "This action cannot be undone."):
            return

        try:
            self.update_history.clear()
            self.load_history()
            messagebox.showinfo("History Cleared",
                                "Update history has been cleared.")
        except Exception as e:
            logger.error(f"Failed to clear history: {e}")
            messagebox.showerror("Clear Error",
                                 f"Failed to clear update history:\n{str(e)}")

    def toggle_recording(self):
        """Toggle update history recording."""
        current = self.main_window.config.get('update_history_enabled', False)
        new_value = not current

        # Update config
        self.main_window.config.set('update_history_enabled', new_value)
        self.main_window.config.save_config()

        # Sync with settings panel if it exists
        if 'settings' in self.main_window.frames:
            settings_frame = self.main_window.frames['settings']
            if hasattr(settings_frame, 'history_enabled_var'):
                settings_frame.history_enabled_var.set(new_value)

        # Update button
        self._update_toggle_button()

        # Show message
        status = "enabled" if new_value else "disabled"
        messagebox.showinfo("Recording Updated",
                            f"Update history recording has been {status}.")

    def _update_toggle_button(self):
        """Update the toggle button text based on current state."""
        # Get the current state from config
        enabled = self.main_window.config.get('update_history_enabled', False)
        logger.debug(f"Update History: Updating toggle button, enabled={enabled}")

        if enabled:
            self.toggle_btn.configure(text="Disable Recording",
                                      bg=self.main_window.colors['warning'])
        else:
            self.toggle_btn.configure(text="Enable Recording",
                                      bg=self.main_window.colors['success'])

    def refresh_theme(self):
        """Refresh the frame with updated theme colors."""
        self._build_ui()
        self.load_history()

    def refresh(self):
        """Refresh the update history display and sync state."""
        logger.debug("Update History: refresh() called")
        # Update toggle button to match current config
        self._update_toggle_button()
        # Reload history entries
        self.load_history()

    def on_frame_shown(self):
        """Called when this frame is shown - refreshes the history."""
        logger.info("Update History: on_frame_shown() called - refreshing display")
        self.refresh()

    def _configure_columns(self):
        """Configure treeview columns with fixed layout for our fixed window size."""
        # Fixed column configuration for 1200px window width
        # Available width: ~870px (1200 - sidebar(250) - scrollbar(20) - padding(60))
        # Total allocated: 870px to ensure all columns are visible
        column_config = {
            'date': {'width': 140, 'min': 120},      # Date/Time
            'packages': {'width': 200, 'min': 150},  # Packages
            'versions': {'width': 220, 'min': 180},  # Version Changes
            'duration': {'width': 80, 'min': 60},    # Duration
            'status': {'width': 100, 'min': 80},     # Status
        }

        # Show all columns for fixed layout
        self.tree.configure(displaycolumns=self.all_columns)

        # Apply fixed column widths
        for col_id, config in column_config.items():
            self.tree.column(col_id, width=config['width'], minwidth=config['min'],
                             stretch=True, anchor='c')  # Center alignment
