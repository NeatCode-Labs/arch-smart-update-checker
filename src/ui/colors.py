"""
Color utilities for terminal output.
"""

# SPDX-License-Identifier: GPL-3.0-or-later

from colorama import Fore, Back, Style, init  # type: ignore[import-untyped]

# Initialize colorama for cross-platform color support
init(autoreset=True)


class Colors:
    """Color constants for terminal output."""

    # Foreground colors
    RED = Fore.RED
    GREEN = Fore.GREEN
    YELLOW = Fore.YELLOW
    BLUE = Fore.BLUE
    MAGENTA = Fore.MAGENTA
    CYAN = Fore.CYAN
    WHITE = Fore.WHITE

    # Background colors
    BG_RED = Back.RED
    BG_GREEN = Back.GREEN
    BG_YELLOW = Back.YELLOW
    BG_BLUE = Back.BLUE

    # Styles
    BRIGHT = Style.BRIGHT
    DIM = Style.DIM
    NORMAL = Style.NORMAL
    RESET = Style.RESET_ALL

    # Semantic colors
    SUCCESS = GREEN + BRIGHT
    WARNING = YELLOW + BRIGHT
    ERROR = RED + BRIGHT
    INFO = CYAN + BRIGHT
    HEADER = MAGENTA + BRIGHT

    @staticmethod
    def colored(text: str, color: str) -> str:
        """
        Apply color to text.

        Args:
            text: Text to colorize
            color: Color to apply

        Returns:
            Colored text
        """
        return f"{color}{text}{Style.RESET_ALL}"

    @staticmethod
    def success(text: str) -> str:
        """Apply success color to text."""
        return Colors.colored(text, Colors.SUCCESS)

    @staticmethod
    def warning(text: str) -> str:
        """Apply warning color to text."""
        return Colors.colored(text, Colors.WARNING)

    @staticmethod
    def error(text: str) -> str:
        """Apply error color to text."""
        return Colors.colored(text, Colors.ERROR)

    @staticmethod
    def info(text: str) -> str:
        """Apply info color to text."""
        return Colors.colored(text, Colors.INFO)

    @staticmethod
    def header(text: str) -> str:
        """Apply header color to text."""
        return Colors.colored(text, Colors.HEADER)
