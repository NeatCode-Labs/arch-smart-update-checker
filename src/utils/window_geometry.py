"""
Window geometry persistence utilities for the Arch Smart Update Checker.
"""

# SPDX-License-Identifier: GPL-3.0-or-later

import json
import os
from pathlib import Path
from typing import Dict, Optional, Tuple
import logging

from ..constants import get_config_dir
from ..utils.logger import get_logger

logger = get_logger(__name__)


class WindowGeometryManager:
    """Manages persistent window positioning for all application windows."""

    def __init__(self):
        """Initialize the geometry manager."""
        self.geometry_file = get_config_dir() / "window_geometry.json"
        self.geometry_data = self._load_geometry_data()

    def _load_geometry_data(self) -> Dict[str, str]:
        """Load saved window geometry data from file."""
        try:
            if self.geometry_file.exists():
                with open(self.geometry_file, 'r') as f:
                    data = json.load(f)
                    if isinstance(data, dict):
                        return data
        except Exception as e:
            logger.warning(f"Failed to load window geometry data: {e}")
        return {}

    def _save_geometry_data(self) -> None:
        """Save window geometry data to file."""
        try:
            # Ensure config directory exists
            self.geometry_file.parent.mkdir(parents=True, exist_ok=True)

            with open(self.geometry_file, 'w') as f:
                json.dump(self.geometry_data, f, indent=2)

            logger.debug(f"Saved window geometry data to {self.geometry_file}")
        except Exception as e:
            logger.warning(f"Failed to save window geometry data: {e}")

    def save_geometry(self, window_id: str, geometry: str) -> None:
        """
        Save geometry for a specific window.

        Args:
            window_id: Unique identifier for the window
            geometry: Tkinter geometry string (e.g., "800x600+100+50")
        """
        logger.debug(f"Saving geometry for {window_id}: {geometry}")
        self.geometry_data[window_id] = geometry
        self._save_geometry_data()

    def get_geometry(self, window_id: str) -> Optional[str]:
        """
        Get saved geometry for a specific window.

        Args:
            window_id: Unique identifier for the window

        Returns:
            Saved geometry string or None if not found
        """
        return self.geometry_data.get(window_id)

    def parse_geometry(self, geometry: str) -> Optional[Tuple[int, int, int, int]]:
        """
        Parse a Tkinter geometry string.

        Args:
            geometry: Tkinter geometry string (e.g., "800x600+100+50")

        Returns:
            Tuple of (width, height, x, y) or None if invalid
        """
        try:
            # Handle both formats: "WxH+X+Y" and "WxH-X-Y" (negative positions)
            import re
            match = re.match(r'(\d+)x(\d+)([\+\-]\d+)([\+\-]\d+)', geometry)
            if match:
                width = int(match.group(1))
                height = int(match.group(2))
                x = int(match.group(3))
                y = int(match.group(4))
                return (width, height, x, y)
        except Exception as e:
            logger.warning(f"Failed to parse geometry string '{geometry}': {e}")
        return None

    def validate_position(self, x: int, y: int, width: int, height: int,
                          screen_width: int, screen_height: int,
                          min_width: int = 1200, min_height: int = 800) -> Tuple[int, int]:
        """
        Validate and adjust window position to ensure it's visible and user-friendly.

        Args:
            x: Proposed X position
            y: Proposed Y position
            width: Window width
            height: Window height
            screen_width: Screen width
            screen_height: Screen height
            min_width: Minimum required width (default 1100)
            min_height: Minimum required height (default 700)

        Returns:
            Tuple of (adjusted_x, adjusted_y)
        """
        # Ensure window meets minimum size requirements
        if width < min_width:
            logger.warning(f"Window width {width} below minimum {min_width}, adjusting")
            width = min_width
        if height < min_height:
            logger.warning(f"Window height {height} below minimum {min_height}, adjusting")
            height = min_height

        # Define comfortable margins from screen edges
        # Minimum distance from screen edges - reduced from 100 to allow more flexibility [[memory:2371890]]
        margin = 20
        min_visible = 100  # Minimum pixels that must be visible - increased to ensure window is grabbable

        # Check if window would be too close to bottom-right corner
        right_edge = x + width
        bottom_edge = y + height

        # Ensure window doesn't go off screen edges
        if right_edge > screen_width - margin:
            x = screen_width - width - margin
        if bottom_edge > screen_height - margin:
            y = screen_height - height - margin

        # Ensure window isn't too close to top-left
        if x < margin:
            x = margin
        if y < margin:
            y = margin

        # Final safety check - ensure at least min_visible pixels are on screen
        if x + min_visible > screen_width:
            x = screen_width - min_visible
        if x + width - min_visible < 0:
            x = min_visible - width
        if y + min_visible > screen_height:
            y = screen_height - min_visible
        if y + height - min_visible < 0:
            y = min_visible - height

        # Ensure non-negative positions
        x = max(0, x)
        y = max(0, y)

        return (x, y)


# Global instance
_geometry_manager = None


def get_geometry_manager() -> WindowGeometryManager:
    """Get the global geometry manager instance."""
    global _geometry_manager
    if _geometry_manager is None:
        _geometry_manager = WindowGeometryManager()
    return _geometry_manager
