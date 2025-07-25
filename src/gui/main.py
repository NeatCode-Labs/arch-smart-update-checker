#!/usr/bin/env python3
"""
Main entry point for the Arch Smart Update Checker GUI application.
"""

# SPDX-License-Identifier: GPL-3.0-or-later

import sys
import os

# Add the src directory to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from .main_window import MainWindow


def main():
    """Main function to start the GUI application."""
    try:
        app = MainWindow()
        app.run()
    except KeyboardInterrupt:
        print("\nApplication interrupted by user")
    except Exception as exc:
        print(f"Error starting application: {exc}")
        sys.exit(1)


if __name__ == "__main__":
    main()
