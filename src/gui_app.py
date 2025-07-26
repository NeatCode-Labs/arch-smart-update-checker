"""
GUI application entry point for Arch Smart Update Checker.
"""

# SPDX-License-Identifier: GPL-3.0-or-later

import sys
import argparse
from pathlib import Path

from .gui import MainWindow
from .config import Config
from .exceptions import ArchSmartUpdateCheckerError


def create_parser() -> argparse.ArgumentParser:
    """
    Create command line argument parser for GUI.

    Returns:
        Configured argument parser
    """
    parser = argparse.ArgumentParser(
        description='Arch Smart Update Checker GUI - Modern graphical interface'
    )
    parser.add_argument(
        '--config',
        type=str,
        help='Path to custom configuration file'
    )
    return parser


def main():
    """Main entry point for GUI application."""
    parser = create_parser()
    parser.add_argument("--version", action="version", version="%(prog)s 2.2.0")
    
    args = parser.parse_args()

    try:
        # Create and run the GUI
        app = MainWindow(config_file=args.config)
        app.run()
        return 0

    except ArchSmartUpdateCheckerError as e:
        print(f"Error: {e}")
        return 1
    except KeyboardInterrupt:
        print("\nApplication cancelled by user")
        return 1
    except Exception as e:
        print(f"Unexpected error: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
