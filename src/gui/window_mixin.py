"""
Window positioning mixin for GUI frames.
"""

# SPDX-License-Identifier: GPL-3.0-or-later

import tkinter as tk
from typing import Optional, Tuple
from ..utils.window_geometry import get_geometry_manager


class WindowPositionMixin:
    """Mixin class providing window positioning functionality to GUI frames."""

    def position_window(self, window: tk.Toplevel, width: Optional[int] = None,
                        height: Optional[int] = None, parent: Optional[tk.Widget] = None) -> None:
        """
        Position a window with persistence support.

        Args:
            window: The Toplevel window to position
            width: Optional width to set
            height: Optional height to set
            parent: Parent window for relative positioning (defaults to main window)
        """
        # Get geometry manager
        geometry_manager = get_geometry_manager()

        # Get unique ID for this window based on its title
        window_id = f"dialog_{window.title().replace(' ', '_').lower()}"

        # Withdraw window first to prevent flashing
        window.withdraw()

        # If width/height provided, set geometry
        if width and height:
            window.geometry(f"{width}x{height}")

        # Update to get actual dimensions
        window.update_idletasks()

        # Try to restore saved position
        saved_geometry = geometry_manager.get_geometry(window_id)

        if saved_geometry:
            parsed = geometry_manager.parse_geometry(saved_geometry)
            if parsed:
                saved_w, saved_h, saved_x, saved_y = parsed
                # Use saved position but allow size override
                if width and height:
                    window.geometry(f"{width}x{height}+{saved_x}+{saved_y}")
                else:
                    window.geometry(saved_geometry)

                # Validate position is still on screen
                win_width = window.winfo_width()
                win_height = window.winfo_height()
                screen_width = window.winfo_screenwidth()
                screen_height = window.winfo_screenheight()

                # Use minimum size constraints for dialogs (smaller than main window)
                min_width = max(400, width) if width else 400
                min_height = max(300, height) if height else 300

                x, y = geometry_manager.validate_position(
                    saved_x, saved_y, win_width, win_height,
                    screen_width, screen_height, min_width, min_height
                )

                if x != saved_x or y != saved_y:
                    # Position was adjusted, update it
                    window.geometry(f"+{x}+{y}")
            else:
                # Saved geometry is invalid, center window
                self._center_on_parent(window, parent)
        else:
            # No saved position, center window
            self._center_on_parent(window, parent)

        # Set up position saving on close
        original_protocol = window.protocol("WM_DELETE_WINDOW")

        def save_and_close():
            geometry = window.winfo_geometry()
            geometry_manager.save_geometry(window_id, geometry)
            if callable(original_protocol):
                original_protocol()
            else:
                window.destroy()

        window.protocol("WM_DELETE_WINDOW", save_and_close)

        # Make window transient if parent provided
        if parent:
            window.transient(parent)  # type: ignore[call-overload]

        # Show the window
        window.deiconify()

    def _center_on_parent(self, window: tk.Toplevel, parent: Optional[tk.Widget] = None) -> None:
        """Center window on parent or main window."""
        if parent is None:
            # Try to get main window
            if hasattr(self, 'main_window') and hasattr(self.main_window, 'root'):
                parent = self.main_window.root
            elif hasattr(self, 'winfo_toplevel'):
                parent = self.winfo_toplevel()
            else:
                # Center on screen
                self._center_on_screen(window)
                return

        # Calculate center position relative to parent
        parent_x = parent.winfo_x()
        parent_y = parent.winfo_y()
        parent_width = parent.winfo_width()
        parent_height = parent.winfo_height()

        win_width = window.winfo_width()
        win_height = window.winfo_height()

        x = parent_x + (parent_width - win_width) // 2
        y = parent_y + (parent_height - win_height) // 2

        # Ensure window doesn't go off screen
        screen_width = window.winfo_screenwidth()
        screen_height = window.winfo_screenheight()

        x = max(0, min(x, screen_width - win_width))
        y = max(0, min(y, screen_height - win_height))

        # Set position
        window.geometry(f"+{x}+{y}")

    def _center_on_screen(self, window: tk.Toplevel) -> None:
        """Center window on screen."""
        window.update_idletasks()

        win_width = window.winfo_width()
        win_height = window.winfo_height()
        screen_width = window.winfo_screenwidth()
        screen_height = window.winfo_screenheight()

        x = (screen_width - win_width) // 2
        y = (screen_height - win_height) // 2

        window.geometry(f"+{x}+{y}")
