"""
Main entry point for the Arch Smart Update Checker.
"""

# SPDX-License-Identifier: GPL-3.0-or-later

import argparse
import sys
from pathlib import Path

from .checker import UpdateChecker
from .config import Config
from .exceptions import ArchSmartUpdateCheckerError


def create_parser() -> argparse.ArgumentParser:
    """
    Create command line argument parser.

    Returns:
        Configured argument parser
    """
    parser = argparse.ArgumentParser(
        description='Arch Smart Update Checker - Check Arch Linux news before updating'
    )
    parser.add_argument(
        '--config', 
        type=str,
        help='Path to custom configuration file'
    )
    parser.add_argument(
        '--gui',
        action='store_true',
        help='Launch graphical user interface'
    )
    parser.add_argument("--version", action="version", version="%(prog)s 2.2.0")
    
    args = parser.parse_args()

    return parser


def main():
    """Main entry point for CLI application."""
    parser = create_parser()
    args = parser.parse_args()

    try:
        # Handle init-config
        if args.init_config:
            config = Config(args.config) if args.config else Config()
            checker = UpdateChecker(config)
            # Config is automatically initialized during UpdateChecker creation
            return 0

        # Create checker with custom config if specified
        config = Config(args.config) if args.config else Config()
        checker = UpdateChecker(config)

        # Clear cache if requested
        if args.clear_cache:
            checker.clear_cache()
            
        # Run the checker
        result = checker.check_updates()
        
        # Log results if requested
        if args.log:
            with open(args.log, 'w') as f:
                f.write(f"Update check completed at {result.timestamp}\n")
                f.write(f"Updates available: {result.update_count}\n")
                f.write(f"News items: {result.news_count}\n")
        
        return 0

    except ArchSmartUpdateCheckerError as e:
        print(f"Error: {e}")
        return 1
    except KeyboardInterrupt:
        print("\nOperation cancelled by user")
        return 1
    except Exception as e:
        print(f"Unexpected error: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
