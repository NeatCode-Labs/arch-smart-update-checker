"""
Layout manager for adaptive window sizing based on screen dimensions.
Handles multiple layouts for different screen sizes while maintaining aspect ratio.
"""

# SPDX-License-Identifier: GPL-3.0-or-later

import tkinter as tk
from typing import Dict, Tuple, Optional, NamedTuple
import math
import logging

logger = logging.getLogger(__name__)


class ScreenLayout(NamedTuple):
    """Define layout parameters for a specific screen size."""
    diagonal: float  # Screen diagonal in inches
    resolution: Tuple[int, int]  # Width x Height
    window_width: int
    window_height: int
    scale_factor: float
    font_scale: float


class LayoutDimensions(NamedTuple):
    """Scaled dimensions for UI components."""
    # Window
    window_width: int
    window_height: int

    # Padding and spacing
    pad_small: int  # 5px base
    pad_medium: int  # 10px base
    pad_large: int  # 20px base

    # Card dimensions
    card_height: int  # 120px base
    card_padding: int  # 15px base

    # Font sizes
    font_tiny: int  # 9px base
    font_small: int  # 10px base
    font_normal: int  # 11px base
    font_medium: int  # 12px base
    font_large: int  # 16px base
    font_xlarge: int  # 20px base

    # Component sizes
    button_padx: int  # 15px base
    button_pady: int  # 8px base
    entry_width: int  # 30 chars base
    tree_row_height: int  # 22px base

    # Dialog sizes
    dialog_width: int  # 600px base
    dialog_height: int  # 400px base
    progress_dialog_width: int  # 500px base
    progress_dialog_height: int  # 300px base


class LayoutManager:
    """Manages adaptive layouts for different screen sizes."""

    # Base dimensions from current app (1300x850)
    BASE_WIDTH = 1300
    BASE_HEIGHT = 850
    BASE_ASPECT_RATIO = BASE_WIDTH / BASE_HEIGHT  # ~1.53

    # Minimum supported screen size
    MIN_DIAGONAL = 12.5
    MIN_RESOLUTION = (1366, 768)

    # Screen layouts from most common sizes
    # Proportional sizing based on successful 12.5" layout (1000x654, scale 0.769)
    SCREEN_LAYOUTS = [
        # Laptop sizes - using 12.5" as reference for good proportions
        ScreenLayout(11.6, (1366, 768), 1000, 654, 0.769, 1.0),     # 11.6" - common netbook (below min)
        ScreenLayout(12.5, (1366, 768), 1000, 654, 0.769, 1.0),     # 12.5" - minimum supported (reference)
        ScreenLayout(13.3, (1920, 1080), 1050, 687, 0.808, 1.0),    # 13.3" - ultrabook (slightly larger)
        ScreenLayout(14.0, (1920, 1080), 1100, 719, 0.846, 1.0),    # 14" - business laptop
        ScreenLayout(15.6, (1920, 1080), 1150, 752, 0.885, 1.0),    # 15.6" - mainstream
        ScreenLayout(17.0, (1920, 1080), 1200, 785, 0.923, 1.0),    # 17" - desktop replacement

        # Desktop monitor sizes - scale up proportionally for larger screens
        ScreenLayout(21.5, (1920, 1080), 1150, 752, 0.885, 1.0),    # 21.5-22" - entry level
        ScreenLayout(24.0, (1920, 1080), 1200, 785, 0.923, 1.0),    # 24" - common desktop
        ScreenLayout(27.0, (2560, 1440), 1250, 817, 0.962, 1.05),   # 27" - productivity (QHD)
        ScreenLayout(32.0, (2560, 1440), 1300, 850, 1.0, 1.1),      # 32" - large display (full base)
        ScreenLayout(34.0, (3440, 1440), 1300, 850, 1.0, 1.15),     # 34" ultrawide - use full base size
    ]

    def __init__(self):
        """Initialize the layout manager."""
        self.current_layout: Optional[ScreenLayout] = None
        self.current_dimensions: Optional[LayoutDimensions] = None

    def detect_screen_size(self, root: tk.Tk) -> Tuple[int, int, float]:
        """
        Detect current screen size and calculate diagonal.

        Returns:
            Tuple of (width, height, diagonal_inches)
        """
        # Get screen dimensions in pixels
        screen_width = root.winfo_screenwidth()
        screen_height = root.winfo_screenheight()

        # Get screen dimensions in mm (more accurate if available)
        try:
            width_mm = root.winfo_screenmmwidth()
            height_mm = root.winfo_screenmmheight()

            # Calculate diagonal in inches
            width_in = width_mm / 25.4
            height_in = height_mm / 25.4
            diagonal_in = math.sqrt(width_in**2 + height_in**2)
        except BaseException:
            # Fallback: estimate based on common DPI (96)
            # This is less accurate but works when mm dimensions aren't available
            dpi = 96
            width_in = screen_width / dpi
            height_in = screen_height / dpi
            diagonal_in = math.sqrt(width_in**2 + height_in**2)

        logger.info(f"Detected screen: {screen_width}x{screen_height} pixels, ~{diagonal_in:.1f}\" diagonal")

        return screen_width, screen_height, diagonal_in

    def select_layout(self, screen_width: int, screen_height: int, diagonal: float) -> Optional[ScreenLayout]:
        """
        Select the appropriate layout based on screen characteristics.

        Returns:
            Selected ScreenLayout or None if screen is too small
        """
        # Check minimum requirements
        if diagonal < self.MIN_DIAGONAL or screen_width < self.MIN_RESOLUTION[0] or screen_height < self.MIN_RESOLUTION[1]:
            logger.warning(f"Screen too small: {diagonal:.1f}\" diagonal, {screen_width}x{screen_height}")
            return None

        # Find the best matching layout
        # Prioritize exact resolution matches, then similar resolutions
        best_layout = None
        best_score = float('inf')

        for layout in self.SCREEN_LAYOUTS:
            # Calculate resolution difference
            res_diff = abs(layout.resolution[0] - screen_width) + abs(layout.resolution[1] - screen_height)

            # Exact resolution match gets highest priority
            if res_diff == 0:
                best_layout = layout
                break

            # For non-exact matches, also consider diagonal
            diag_diff = abs(layout.diagonal - diagonal)

            # Don't use layouts designed for much larger screens
            if layout.resolution[0] > screen_width * 1.5:
                continue

            # Weighted score (resolution match is much more important)
            score = res_diff + diag_diff * 50

            if score < best_score:
                best_score = score
                best_layout = layout

        # If no suitable layout found, use the one with closest resolution
        if best_layout is None:
            best_layout = min(self.SCREEN_LAYOUTS,
                              key=lambda layout: abs(layout.resolution[0] - screen_width) + abs(layout.resolution[1] - screen_height))

        logger.info(
            f"Selected layout: {best_layout.diagonal}\" ({best_layout.resolution[0]}x{best_layout.resolution[1]})")
        return best_layout

    def calculate_dimensions(self, layout: ScreenLayout) -> LayoutDimensions:
        """Calculate scaled dimensions for all UI components."""
        s = layout.scale_factor  # General scale
        f = layout.font_scale    # Font-specific scale

        return LayoutDimensions(
            # Window
            window_width=layout.window_width,
            window_height=layout.window_height,

            # Padding and spacing - reduced for compact layout
            pad_small=max(3, int(5 * s)),
            pad_medium=max(6, int(10 * s)),
            pad_large=max(10, int(20 * s)),

            # Card dimensions - ensure minimum height for content
            card_height=max(140, int(150 * s)),  # Increased for descriptions
            card_padding=max(12, int(15 * s)),

            # Font sizes - slightly smaller for compact display
            font_tiny=max(8, int(9 * f)),
            font_small=max(9, int(10 * f)),
            font_normal=max(10, int(11 * f)),
            font_medium=max(11, int(12 * f)),
            font_large=max(13, int(16 * f)),
            font_xlarge=max(16, int(20 * f)),

            # Component sizes
            button_padx=max(8, int(15 * s)),
            button_pady=max(4, int(8 * s)),
            entry_width=max(20, int(30 * s)),
            tree_row_height=max(18, int(22 * s)),

            # Dialog sizes
            dialog_width=max(400, int(600 * s)),
            dialog_height=max(300, int(400 * s)),
            progress_dialog_width=max(350, int(500 * s)),
            progress_dialog_height=max(200, int(300 * s)),
        )

    def initialize_for_screen(self, root: tk.Tk) -> bool:
        """
        Initialize layout manager for the current screen.

        Returns:
            True if initialization successful, False if screen too small
        """
        # Detect screen
        width, height, diagonal = self.detect_screen_size(root)

        # Select layout
        self.current_layout = self.select_layout(width, height, diagonal)
        if self.current_layout is None:
            return False

        # Calculate dimensions
        self.current_dimensions = self.calculate_dimensions(self.current_layout)

        return True

    def get_window_size(self) -> Tuple[int, int]:
        """Get the window size for current layout."""
        if not self.current_dimensions:
            # Fallback to minimum supported
            return 683, 447
        return self.current_dimensions.window_width, self.current_dimensions.window_height

    def get_dimensions(self) -> LayoutDimensions:
        """Get all scaled dimensions for current layout."""
        if not self.current_dimensions:
            # Return minimum supported dimensions
            min_layout = self.SCREEN_LAYOUTS[1]  # 12.5" layout
            return self.calculate_dimensions(min_layout)
        return self.current_dimensions

    def scale_value(self, base_value: int) -> int:
        """Scale a base value according to current layout."""
        if not self.current_layout:
            return base_value
        return max(1, int(base_value * self.current_layout.scale_factor))


# Global instance
_layout_manager = None


def get_layout_manager() -> LayoutManager:
    """Get or create the global layout manager instance."""
    global _layout_manager
    if _layout_manager is None:
        _layout_manager = LayoutManager()
    return _layout_manager
