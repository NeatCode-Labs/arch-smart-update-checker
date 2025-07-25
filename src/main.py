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
        prog="asuc",
        description="Arch Smart Update Checker - Check for updates and relevant news",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  asuc                    # Run interactive update check
  asuc --non-interactive  # Run without user interaction
  asuc --all-news         # Show all news, not just relevant ones
  asuc --clear-cache      # Clear cache before running
  asuc --init-config      # Initialize configuration file
  asuc --log /tmp/updates.log  # Log results to file
        """,
    )

    parser.add_argument(
        "--all-news",
        action="store_true",
        help="Show all news items, not just those relevant to installed packages",
    )

    parser.add_argument(
        "--non-interactive",
        action="store_true",
        help="Run without user interaction (useful for scripts)",
    )

    parser.add_argument(
        "--clear-cache", action="store_true", help="Clear cache before running"
    )

    parser.add_argument(
        "--init-config", action="store_true", help="Initialize configuration file"
    )

    parser.add_argument("--config", type=str, help="Use custom configuration file")

    parser.add_argument("--log", type=str, help="Log results to specified file")

    parser.add_argument("--version", action="version", version="%(prog)s 2.1.0")

    return parser


def main() -> int:
    """
    Main entry point.

    Returns:
        Exit code
    """
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

        # Run the checker
        return checker.run(
            all_news=args.all_news,
            non_interactive=args.non_interactive,
            clear_cache=args.clear_cache,
            log_file=args.log,
        )

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
