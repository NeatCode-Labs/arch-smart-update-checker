"""
Centralized dimensions provider for adaptive UI scaling.
All GUI components should use this module to get scaled dimensions.
"""

# SPDX-License-Identifier: GPL-3.0-or-later

from typing import Tuple, Optional
from .layout_manager import get_layout_manager, LayoutDimensions


class Dimensions:
    """Provides scaled dimensions for all UI components."""

    def __init__(self):
        """Initialize with layout manager dimensions."""
        self._layout_manager = get_layout_manager()
        self._dims: Optional[LayoutDimensions] = None
        self._initialized = False

    def _ensure_initialized(self):
        """Ensure dimensions are initialized."""
        if not self._initialized:
            try:
                self._dims = self._layout_manager.get_dimensions()
                self._initialized = True
            except RuntimeError:
                # Layout manager not yet initialized, use safe defaults
                # This should only happen during early initialization
                pass

    def refresh(self):
        """Refresh dimensions from layout manager."""
        try:
            self._dims = self._layout_manager.get_dimensions()
            self._initialized = True
        except RuntimeError:
            # Layout manager not ready yet
            self._initialized = False

    # Window dimensions
    @property
    def window_size(self) -> Tuple[int, int]:
        """Get window width and height."""
        self._ensure_initialized()
        if self._dims:
            return self._dims.window_width, self._dims.window_height
        # Fallback for early initialization
        return 1300, 850

    # Padding values
    @property
    def pad_small(self) -> int:
        """Small padding (5px base)."""
        self._ensure_initialized()
        if self._dims:
            return self._dims.pad_small
        return 5

    @property
    def pad_medium(self) -> int:
        """Medium padding (10px base)."""
        self._ensure_initialized()
        if self._dims:
            return self._dims.pad_medium
        return 10

    @property
    def pad_large(self) -> int:
        """Large padding (20px base)."""
        self._ensure_initialized()
        if self._dims:
            return self._dims.pad_large
        return 20

    # Card dimensions
    @property
    def card_height(self) -> int:
        """Dashboard card height (120px base)."""
        self._ensure_initialized()
        if self._dims:
            return self._dims.card_height
        return 120

    @property
    def card_padding(self) -> int:
        """Card internal padding (15px base)."""
        self._ensure_initialized()
        if self._dims:
            return self._dims.card_padding
        return 15

    # Font sizes
    @property
    def font_tiny(self) -> int:
        """Tiny font size (9px base)."""
        self._ensure_initialized()
        if self._dims:
            return self._dims.font_tiny
        return 9

    @property
    def font_small(self) -> int:
        """Small font size (10px base)."""
        self._ensure_initialized()
        if self._dims:
            return self._dims.font_small
        return 10

    @property
    def font_normal(self) -> int:
        """Normal font size (11px base)."""
        self._ensure_initialized()
        if self._dims:
            return self._dims.font_normal
        return 11

    @property
    def font_medium(self) -> int:
        """Medium font size (12px base)."""
        self._ensure_initialized()
        if self._dims:
            return self._dims.font_medium
        return 12

    @property
    def font_large(self) -> int:
        """Large font size (16px base)."""
        self._ensure_initialized()
        if self._dims:
            return self._dims.font_large
        return 16

    @property
    def font_xlarge(self) -> int:
        """Extra large font size (20px base)."""
        self._ensure_initialized()
        if self._dims:
            return self._dims.font_xlarge
        return 20

    # Component sizes
    @property
    def button_padx(self) -> int:
        """Button horizontal padding (15px base)."""
        self._ensure_initialized()
        if self._dims:
            return self._dims.button_padx
        return 15

    @property
    def button_pady(self) -> int:
        """Button vertical padding (8px base)."""
        self._ensure_initialized()
        if self._dims:
            return self._dims.button_pady
        return 8

    @property
    def entry_width(self) -> int:
        """Entry widget width in characters (30 base)."""
        self._ensure_initialized()
        if self._dims:
            return self._dims.entry_width
        return 30

    @property
    def tree_row_height(self) -> int:
        """Treeview row height (22px base)."""
        self._ensure_initialized()
        if self._dims:
            return self._dims.tree_row_height
        return 22

    # Dialog sizes
    @property
    def dialog_size(self) -> Tuple[int, int]:
        """Standard dialog size (600x400 base)."""
        self._ensure_initialized()
        if self._dims:
            return self._dims.dialog_width, self._dims.dialog_height
        return 600, 400

    @property
    def progress_dialog_size(self) -> Tuple[int, int]:
        """Progress dialog size (500x300 base)."""
        self._ensure_initialized()
        if self._dims:
            return self._dims.progress_dialog_width, self._dims.progress_dialog_height
        return 500, 300

    # Helper methods for common patterns
    def scale(self, value: int) -> int:
        """Scale a value according to current layout."""
        return self._layout_manager.scale_value(value)

    def font(self, family: str, size_name: str = 'normal', style: str = 'normal') -> Tuple[str, int, str]:
        """Get a font tuple with scaled size."""
        size_map = {
            'tiny': self.font_tiny,
            'small': self.font_small,
            'normal': self.font_normal,
            'medium': self.font_medium,
            'large': self.font_large,
            'xlarge': self.font_xlarge
        }
        size = size_map.get(size_name, self.font_normal)
        return (family, size, style)

    def padx(self, size: str = 'medium') -> int:
        """Get horizontal padding by size name."""
        pad_map = {
            'small': self.pad_small,
            'medium': self.pad_medium,
            'large': self.pad_large
        }
        return pad_map.get(size, self.pad_medium)

    def pady(self, size: str = 'medium') -> int:
        """Get vertical padding by size name."""
        return self.padx(size)  # Same as padx for consistency


# Global instance
_dimensions = None


def get_dimensions() -> Dimensions:
    """Get the global dimensions instance."""
    global _dimensions
    if _dimensions is None:
        _dimensions = Dimensions()
    return _dimensions


def reset_dimensions() -> None:
    """Reset the global dimensions instance. Used for re-initialization after Tk root is created."""
    global _dimensions
    _dimensions = None
