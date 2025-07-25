"""
Main entry point for the asuc-cli command-line tool.
"""

# SPDX-License-Identifier: GPL-3.0-or-later

import argparse
import sys
import os
import json
import subprocess
from typing import Optional, List, Dict, Any
from pathlib import Path
import csv

from ..config import Config
from ..checker import UpdateChecker
from ..package_manager import PackageManager
from ..utils.update_history import UpdateHistoryManager, UpdateHistoryEntry
from ..utils.pacman_runner import PacmanRunner
from ..models import FeedConfig, FeedType
from ..constants import get_cache_dir
from .output import OutputFormatter
from ..ui.pager import Pager


class AsucCLI:
    """Main CLI application class."""

    def __init__(self, config_path: Optional[str] = None):
        """Initialize CLI with configuration."""
        self.config = Config(config_path)
        self.checker = UpdateChecker(self.config)
        self.package_manager = PackageManager()
        retention_days = self.config.get('update_history_retention_days', 365)
        self.update_history = UpdateHistoryManager(
            retention_days=int(retention_days) if retention_days is not None else 365
        )
        self.formatter: Optional[OutputFormatter] = None

    def _get_single_key(self) -> str:
        """
        Get a single keystroke without requiring Enter.

        Returns:
            Single character pressed by user
        """
        try:
            import termios
            import tty

            # Save current terminal settings
            fd = sys.stdin.fileno()
            old_settings = termios.tcgetattr(fd)

            try:
                # Set terminal to raw mode
                tty.setraw(fd)
                # Read single character
                char = sys.stdin.read(1)

                # Handle special characters
                if ord(char) == 3:  # Ctrl+C
                    raise KeyboardInterrupt
                elif ord(char) == 4:  # Ctrl+D
                    raise EOFError

                return char
            finally:
                # Restore terminal settings
                termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)

        except (ImportError, termios.error):
            # Fallback for non-Unix systems or when raw mode fails
            response = input().strip()
            return response[0] if response else ' '

    def _display_with_pager(self, content: str) -> None:
        """
        Display content with pagination similar to v1.0 implementation.

        Args:
            content: Content to display
        """
        import textwrap

        # Process lines with proper wrapping
        raw_lines = content.split('\n')
        lines = []

        # Get terminal width for wrapping
        try:
            import shutil
            terminal_width = shutil.get_terminal_size().columns - 2
        except BaseException:
            terminal_width = 78

        # Wrap long lines
        wrapper = textwrap.TextWrapper(width=terminal_width)
        for line in raw_lines:
            if line:
                # Wrap long lines while preserving formatting
                # Check if line has special formatting (table borders, etc)
                if any(char in line for char in ['─', '━', '═', '│', '┃', '║']):
                    # Don't wrap table lines
                    lines.append(line)
                else:
                    wrapped = wrapper.wrap(line)
                    if wrapped:
                        lines.extend(wrapped)
                    else:
                        lines.append('')
            else:
                lines.append('')

        # Get terminal height for pagination
        try:
            import shutil
            import subprocess

            terminal_height = None

            # First check if user has manually set page size
            env_page_size = os.environ.get('ASUC_PAGE_SIZE', '').strip()
            if env_page_size.isdigit():
                terminal_height = int(env_page_size)
            else:
                # Try tput which is more reliable
                try:
                    result = subprocess.run(['tput', 'lines'], capture_output=True, text=True)
                    if result.returncode == 0 and result.stdout.strip().isdigit():
                        terminal_height = int(result.stdout.strip())
                except BaseException:
                    pass

                # Fallback to shutil method
                if not terminal_height or terminal_height < 10:
                    size = shutil.get_terminal_size()
                    terminal_height = size.lines

                # If we still get unrealistic values, try environment variables
                if terminal_height < 10:
                    # Try LINES environment variable
                    env_lines = os.environ.get('LINES', '').strip()
                    if env_lines.isdigit():
                        terminal_height = int(env_lines)

                # If still too small, use a reasonable default
                if terminal_height < 10:
                    terminal_height = 24  # Standard terminal height

                # Reserve lines for prompt (3 lines)
                terminal_height = terminal_height - 3

            # Ensure minimum reasonable height
            terminal_height = max(terminal_height, 10)

        except Exception:
            # Fallback to reasonable default
            terminal_height = 20

        # If content fits on screen, just print it
        if len(lines) <= terminal_height:
            print(content)
            return

        # Paginate the content
        current_line = 0
        total_lines = len(lines)

        while current_line < total_lines:
            # Clear screen for cleaner pagination
            os.system('clear' if os.name != 'nt' else 'cls')

            # Calculate line range for current display
            end_line = min(current_line + terminal_height, total_lines)

            # Show current page content
            for i in range(current_line, end_line):
                print(lines[i])

            # Check if we've reached the end
            if end_line >= total_lines:
                print("\n(END) Press any key to continue...")
                try:
                    self._get_single_key()
                except (EOFError, KeyboardInterrupt):
                    pass
                break

            # Show progress and navigation prompt
            progress = f"Lines {current_line + 1}-{end_line} of {total_lines}"
            print(f"\n{progress} -- Press SPACE for next, 'p' for previous, 'q' to quit")

            try:
                response = self._get_single_key().lower()

                if response == ' ':  # Space = next
                    current_line = end_line
                elif response == 'p':  # Previous page
                    if current_line > 0:
                        current_line = max(0, current_line - terminal_height)
                    # If already at first page, just redisplay
                elif response == 'q':  # Quit
                    break
                # Any other key = next page (like standard pagers)
                else:
                    current_line = end_line

            except (EOFError, KeyboardInterrupt):
                print()  # Clean line before exit
                break

    def run(self, args: argparse.Namespace) -> int:
        """
        Run the CLI with given arguments.

        Args:
            args: Parsed command line arguments

        Returns:
            Exit code
        """
        # Initialize formatter with global options
        self.formatter = OutputFormatter(
            use_color=not args.no_color,
            json_output=args.json
        )

        # Dispatch to sub-command handler
        if args.command is None:
            # Default behavior - run check
            return self.cmd_check(args)
        elif args.command == 'updates':
            return self.cmd_updates(args)
        elif args.command == 'news':
            return self.cmd_news(args)
        elif args.command == 'history':
            return self.cmd_history(args)
        elif args.command == 'config':
            return self.cmd_config(args)
        elif args.command == 'clear-cache':
            return self.cmd_clear_cache(args)
        else:
            self.formatter.error(f"Unknown command: {args.command}")
            return 1

    def cmd_check(self, args: argparse.Namespace) -> int:
        """Handle 'check' command - perform update & news check."""
        try:
            # Regular comprehensive check (updates + news)
            result = self.checker.check_updates()

            if args.json:
                # JSON output
                data = {
                    'updates': [
                        {
                            'name': u.name,
                            'current_version': u.current_version,
                            'new_version': u.new_version
                        }
                        for u in result.updates
                    ],
                    'news': [
                        {
                            'title': n.title,
                            'url': n.link,
                            'published': n.date,
                            'affected_packages': list(n.affected_packages) if n.affected_packages else []
                        }
                        for n in result.news_items
                    ],
                    'update_count': result.update_count,
                    'news_count': result.news_count
                }
                self.formatter.output_json(data)  # type: ignore[union-attr]
            else:
                # Prepare all content first to determine if pagination is needed
                has_updates = result.update_count > 0
                has_news = result.news_count > 0

                # Build complete output
                output_lines = []

                # Add initial status message
                if not args.quiet:
                    output_lines.append("Checking for updates and relevant news...")
                    output_lines.append("")

                # Add news section if present
                if has_news:
                    output_lines.append(f"Relevant news items: {result.news_count}")
                    output_lines.append("─" * (len(f"Relevant news items: {result.news_count}")))

                    news_dict = [
                        {
                            'title': n.title,
                            'published': n.date,
                            'content': n.content,
                            'affected_packages': n.affected_packages
                        }
                        for n in result.news_items
                    ]
                    news_formatted = self.formatter.format_news_items(news_dict)  # type: ignore[union-attr]
                    output_lines.extend(news_formatted.split('\n'))

                    if has_updates:
                        output_lines.append("")  # Add spacing
                elif not args.quiet and has_updates:
                    output_lines.append("No relevant news items")
                    output_lines.append("")

                # Add updates section if present
                if has_updates:
                    output_lines.append(f"Available updates: {result.update_count}")
                    output_lines.append("─" * (len(f"Available updates: {result.update_count}")))

                    updates_dict = [
                        {
                            'name': u.name,
                            'current_version': u.current_version,
                            'new_version': u.new_version
                        }
                        for u in result.updates
                    ]
                    updates_formatted = self.formatter.format_updates_table(updates_dict)  # type: ignore[union-attr]
                    output_lines.extend(updates_formatted.split('\n'))

                    # Add update summary information
                    output_lines.append("")
                    output_lines.append("Update Summary")
                    output_lines.append("─" * 14)

                    # Calculate totals
                    total_packages = len(result.updates)
                    packages_with_size = [u for u in result.updates if u.size is not None]
                    total_download_size = sum(u.size for u in packages_with_size if u.size is not None) if packages_with_size else None

                    # Get packages with installed size info
                    packages_with_installed_size = [u for u in result.updates if u.installed_size is not None]
                    total_installed_size = sum(
                        u.installed_size for u in packages_with_installed_size if u.installed_size is not None) if packages_with_installed_size else None

                    output_lines.append(f"  Total packages: {total_packages}")

                    # Helper function to format size
                    def format_size(size_bytes: int) -> str:
                        if size_bytes < 1024:
                            return f"{size_bytes} B"
                        elif size_bytes < 1024 * 1024:
                            return f"{size_bytes / 1024:.1f} KB"
                        elif size_bytes < 1024 * 1024 * 1024:
                            return f"{size_bytes / (1024 * 1024):.1f} MB"
                        else:
                            return f"{size_bytes / (1024 * 1024 * 1024):.2f} GB"

                    if total_download_size is not None and total_download_size > 0:
                        output_lines.append(f"  Download size: {format_size(total_download_size)}")

                        # Use actual installed size if available
                        if total_installed_size is not None and total_installed_size > 0:
                            output_lines.append(f"  Disk space required: {format_size(total_installed_size)}")

                            # Show coverage if not complete
                            if len(packages_with_installed_size) < total_packages:
                                output_lines.append(
                                    f"  (Size data available for {len(packages_with_installed_size)}/{total_packages} packages)")
                        else:
                            # Fallback to estimate only if no installed size data
                            estimated_installed = int(total_download_size * 2.5)
                            output_lines.append(f"  Estimated disk space required: ~{format_size(estimated_installed)}")
                            output_lines.append("  (Actual size data not available)")
                    else:
                        output_lines.append("  Download size: Calculating...")
                        output_lines.append("  Note: Run with --verbose to see size calculation progress")

                    # Add repository breakdown
                    repos: dict[str, int] = {}
                    for update in result.updates:
                        repo = update.repository or "unknown"
                        repos[repo] = repos.get(repo, 0) + 1

                    if len(repos) > 1 or "unknown" not in repos:
                        output_lines.append("")
                        output_lines.append("  By repository:")
                        for repo, count in sorted(repos.items()):
                            if repo != "unknown":
                                output_lines.append(f"    {repo}: {count} packages")

                    # Add upgrade command hint
                    output_lines.append("")
                    output_lines.append("  Use 'sudo pacman -Syu' to apply these updates")
                    output_lines.append("  Or answer 'y' when prompted after viewing this list")

                elif not has_news and not args.quiet:
                    output_lines.append("System is up to date")

                # Combine all content
                complete_output = '\n'.join(output_lines)

                # Determine if pagination is needed
                total_lines = len(output_lines)
                needs_pagination = (has_updates and result.update_count > 20) or total_lines > 30

                if needs_pagination and not args.quiet:
                    # Use pager for all content
                    self._display_with_pager(complete_output)
                else:
                    # Print normally
                    print(complete_output)

            # Offer upgrade if updates are available and not in quiet/json mode
            if result.update_count > 0 and not args.quiet and not args.json:
                print()  # Add spacing
                try:
                    response = input("Would you like to apply these updates? [y/N] ")
                    if response.lower() in ['y', 'yes']:
                        # Get list of packages to update
                        packages = [u.name for u in result.updates]

                        # Run the upgrade
                        print()
                        self.formatter.info("Starting system upgrade...")  # type: ignore[union-attr]
                        exit_code, duration, output = PacmanRunner.run_update_interactive(packages)

                        # Record history if enabled
                        if self.config.get('update_history_enabled', False):
                            entry = PacmanRunner.create_history_entry(packages, exit_code, duration)
                            self.update_history.add(entry)

                        if exit_code == 0:
                            self.formatter.success("Upgrade completed successfully")  # type: ignore[union-attr]
                            return 0
                        else:
                            self.formatter.error(f"Upgrade failed with exit code: {exit_code}")  # type: ignore[union-attr]
                            return 30
                    else:
                        self.formatter.info("System already up to date")  # type: ignore[union-attr]
                except (EOFError, KeyboardInterrupt):
                    print()  # Clean line
                    self.formatter.info("No packages to upgrade")  # type: ignore[union-attr]

            # Exit code 10 if updates available
            return 10 if result.update_count > 0 else 0

        except Exception as e:
            self.formatter.error(f"Update failed: {e}")  # type: ignore[union-attr]
            return 20

    def cmd_updates(self, args: argparse.Namespace) -> int:
        """Handle 'updates' command - list available package updates only."""
        if not args.quiet and not args.json:
            self.formatter.info("Checking for package updates only...")  # type: ignore[union-attr]

        try:
            updates = self.package_manager.check_for_updates()

            if args.json:
                data = [
                    {
                        'name': u.name,
                        'current_version': u.current_version,
                        'new_version': u.new_version
                    }
                    for u in updates
                ]
                self.formatter.output_json(data)  # type: ignore[union-attr]
            else:
                if updates:
                    self.formatter.header(f"Available updates: {len(updates)}")  # type: ignore[union-attr]
                    updates_dict = [
                        {
                            'name': u.name,
                            'current_version': u.current_version,
                            'new_version': u.new_version
                        }
                        for u in updates
                    ]

                    # Use pagination for large lists
                    if len(updates) > 20:
                        formatted_output = self.formatter.format_updates_table(updates_dict)  # type: ignore[union-attr]
                        self._display_with_pager(formatted_output)
                    else:
                        print(self.formatter.format_updates_table(updates_dict))  # type: ignore[union-attr]

                    if not args.quiet:
                        self.formatter.info("Note: Use 'asuc-cli check' to also see relevant news items")  # type: ignore[union-attr]
                else:
                    self.formatter.success("No updates available")  # type: ignore[union-attr]

            return 0

        except Exception as e:
            self.formatter.error(f"Failed to check updates: {str(e)}")  # type: ignore[union-attr]
            return 20

    def cmd_news(self, args: argparse.Namespace) -> int:
        """Handle 'news' command - show relevant news items."""
        try:
            # Fetch news
            feed_configs = [FeedConfig.from_dict(f) for f in self.config.get_feeds()]
            all_news = self.checker.news_fetcher.fetch_all_feeds(feed_configs)

            # Filter relevant news (only if packages have updates)
            updates = self.package_manager.check_for_updates()
            packages_with_updates = set([u.name for u in updates])

            relevant_news = []
            for item in all_news:
                if item.source_type == FeedType.PACKAGE:
                    continue  # Skip package feeds

                # Check if any affected packages have updates
                if item.affected_packages and item.affected_packages.intersection(packages_with_updates):
                    relevant_news.append(item)

            # Limit to max items with security enforcement
            max_items = self.config.get_max_news_items()
            # Double-check the limit for security (in case config was tampered with)
            safe_max_items = min(max_items, 1000)
            relevant_news = relevant_news[:safe_max_items]

            if args.json:
                data = [
                    {
                        'title': n.title,
                        'url': n.link,
                        'published': n.date,
                        'content': n.content,
                        'affected_packages': list(n.affected_packages) if n.affected_packages else []
                    }
                    for n in relevant_news
                ]
                self.formatter.output_json(data)  # type: ignore[union-attr]
            else:
                if relevant_news:
                    self.formatter.header(f"Relevant news items: {len(relevant_news)}")  # type: ignore[union-attr]
                    news_dict = [
                        {
                            'title': n.title,
                            'published': n.date,
                            'content': n.content,
                            'affected_packages': n.affected_packages
                        }
                        for n in relevant_news
                    ]
                    print(self.formatter.format_news_items(news_dict))  # type: ignore[union-attr]
                else:
                    self.formatter.info("No relevant news items")  # type: ignore[union-attr]

            return 0

        except Exception as e:
            self.formatter.error(f"Failed to fetch news: {str(e)}")  # type: ignore[union-attr]
            return 20

    def cmd_history(self, args: argparse.Namespace) -> int:
        """Handle 'history' command - display update history."""
        try:
            if args.clear:
                if not args.yes:
                    response = input("Clear all update history? [y/N] ")
                    if response.lower() not in ['y', 'yes']:
                        self.formatter.info("Clear cancelled")  # type: ignore[union-attr]
                        return 0

                self.update_history.clear()
                self.formatter.success("Update history cleared")  # type: ignore[union-attr]
                return 0

            if args.export:
                # Export history
                format_ = 'csv' if args.export.lower().endswith('.csv') else 'json'
                self.update_history.export(args.export, format_)
                self.formatter.success(f"History exported to {args.export}")  # type: ignore[union-attr]
                return 0

            # Display history
            entries = self.update_history.all()

            # Apply limit if specified
            if args.limit:
                entries = entries[:args.limit]

            if args.json:
                data = [entry.to_dict() for entry in entries]
                self.formatter.output_json  # type: ignore[union-attr](data)
            else:
                if entries:
                    self.formatter.header(f"Update History ({len(entries)} entries)")  # type: ignore[union-attr]
                    entries_dict = [entry.to_dict() for entry in entries]
                    print(self.formatter.format_history_table(entries_dict))  # type: ignore[union-attr]
                else:
                    self.formatter.info  # type: ignore[union-attr]("No update history recorded")

            return 0

        except Exception as e:
            self.formatter.error(f"Failed to access history: {str(e)}")
            return 20

    def cmd_config(self, args: argparse.Namespace) -> int:
        """Handle 'config' command - view/modify configuration."""
        try:
            if args.action == 'path':
                print(self.config.config_file)
                return 0

            elif args.action == 'get':
                if not args.key:
                    # Show all config
                    if args.json:
                        self.formatter.output_json(self.config.config)
                    else:
                        self.formatter.header("Configuration")
                        for key, value in self.config.config.items():
                            print(f"  {key}: {value}")
                else:
                    # Get specific key
                    value = self.config.get(args.key)
                    if args.json:
                        self.formatter.output_json({args.key: value})
                    else:
                        print(value)
                return 0

            elif args.action == 'set':
                if not args.key or args.value is None:
                    self.formatter.error("Both key and value are required for 'set'")
                    self.formatter.info("Available keys:")
                    for key in self.config.config.keys():
                        print(f"  • {key}")
                    self.formatter.info("Example: asuc-cli config set cache_ttl_hours 2")
                    return 1

                # Validate key exists
                if args.key not in self.config.config:
                    self.formatter.error(f"Unknown config key: {args.key}")
                    self.formatter.info("Available keys:")
                    for key in self.config.config.keys():
                        print(f"  • {key}")
                    return 1

                # Type inference
                value = args.value
                if value.lower() in ['true', 'false']:
                    value = value.lower() == 'true'
                elif value.isdigit():
                    value = int(value)

                self.config.set(args.key, value)
                self.config.save_config()
                self.formatter.success(f"Set {args.key} = {value}")
                return 0

            elif args.action == 'edit':
                from ..utils.subprocess_wrapper import SecureSubprocess
                from ..utils.validators import validate_config_path, validate_editor_command, get_safe_environment_variable

                # Validate config file path first
                try:
                    validate_config_path(self.config.config_file)
                except ValueError as e:
                    self.formatter.error(f"Config file path not allowed: {e}")
                    return 1

                # Get and validate editor from environment with enhanced security
                try:
                    editor_env = get_safe_environment_variable('EDITOR', 'nano', 'command')
                    editor_name = validate_editor_command(editor_env)
                except ValueError as e:
                    self.formatter.error(f"Editor validation failed: {e}")
                    return 1

                try:
                    SecureSubprocess.run([editor_name, self.config.config_file])
                except ValueError as e:
                    self.formatter.error(f"Invalid editor command: {e}")
                    return 1
                except Exception as e:
                    self.formatter.error(f"Failed to open editor: {e}")
                    return 1
                return 0

            else:
                self.formatter.error(f"Unknown config action: {args.action}")
                return 1

        except Exception as e:
            self.formatter.error(f"Config operation failed: {str(e)}")
            return 20

    def cmd_clear_cache(self, args: argparse.Namespace) -> int:
        """Handle 'clear-cache' command - clear feed & pacman caches."""
        try:
            cache_dir = get_cache_dir()

            # Clear feed cache
            feed_cache = cache_dir / "feeds"
            if feed_cache.exists():
                import shutil
                shutil.rmtree(feed_cache)
                self.formatter.success("Feed cache cleared")
            else:
                self.formatter.info("No feed cache to clear")

            # Clear pacman cache (requires sudo)
            if not args.json:
                self.formatter.info("Clearing pacman cache...")

            from ..utils.subprocess_wrapper import SecureSubprocess
            try:
                result = SecureSubprocess.run(
                    ["sudo", "paccache", "-r"],
                    capture_output=True,
                    text=True
                )

                if result.returncode == 0:
                    self.formatter.success("Pacman cache cleared")
                else:
                    self.formatter.warning("Failed to clear pacman cache (paccache may not be installed)")
            except (ValueError, subprocess.CalledProcessError) as e:
                self.formatter.warning(f"Failed to clear pacman cache: {e}")

            return 0

        except Exception as e:
            self.formatter.error(f"Failed to clear cache: {str(e)}")
            return 20


def create_parser() -> argparse.ArgumentParser:
    """Create the argument parser."""
    parser = argparse.ArgumentParser(
        prog='asuc-cli',
        description='Arch Smart Update Checker - Command Line Interface',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    # Global options
    parser.add_argument(
        '--config',
        metavar='PATH',
        help='Alternative config file path'
    )
    parser.add_argument(
        '--json',
        action='store_true',
        help='Output in JSON format'
    )
    parser.add_argument(
        '--no-color',
        action='store_true',
        help='Disable ANSI colors'
    )
    parser.add_argument(
        '--quiet',
        action='store_true',
        help='Minimal output (exit status only)'
    )
    parser.add_argument(
        '--debug',
        action='store_true',
        help='Enable debug logging'
    )

    # Create sub-commands
    subparsers = parser.add_subparsers(dest='command', help='Available commands')

    # updates command
    subparsers.add_parser(
        'updates',
        help='List available package updates only (no news)'
    )

    # news command
    subparsers.add_parser('news', help='Show relevant news items')

    # history command
    history_parser = subparsers.add_parser('history', help='Display update history')
    history_parser.add_argument(
        '--limit',
        type=int,
        metavar='N',
        help='Show at most N entries'
    )
    history_parser.add_argument(
        '--clear',
        action='store_true',
        help='Clear history'
    )
    history_parser.add_argument(
        '--export',
        metavar='FILE',
        help='Export history to file (json/csv)'
    )
    history_parser.add_argument(
        '--yes', '-y',
        action='store_true',
        help='Skip confirmation for clear'
    )

    # config command
    config_parser = subparsers.add_parser(
        'config',
        help='View/modify configuration',
        description='Manage configuration settings. Examples:\n'
        '  asuc-cli config get                 # Show all settings\n'
        '  asuc-cli config get cache_ttl_hours # Show specific setting\n'
        '  asuc-cli config set cache_ttl_hours 2  # Set a value\n'
        '  asuc-cli config path               # Show config file location\n'
        '  asuc-cli config edit               # Edit config file',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    config_parser.add_argument(
        'action',
        choices=['get', 'set', 'path', 'edit'],
        help='Config action: get (view), set (change), path (location), edit (open editor)'
    )
    config_parser.add_argument(
        'key',
        nargs='?',
        help='Config key (e.g. cache_ttl_hours, debug_mode, theme)'
    )
    config_parser.add_argument(
        'value',
        nargs='?',
        help='Config value to set (e.g. 2, true, false, dark, light)'
    )

    # clear-cache command
    subparsers.add_parser('clear-cache', help='Clear feed & pacman caches')

    return parser


def main() -> None:
    """Main entry point for the CLI."""
    parser = create_parser()
    args = parser.parse_args()

    # Set up logging levels based on CLI arguments
    import logging
    if args.debug:
        logging.basicConfig(level=logging.DEBUG)
    elif args.quiet:
        logging.basicConfig(level=logging.ERROR)
    else:
        logging.basicConfig(level=logging.WARNING)

    # Create and run CLI
    try:
        cli = AsucCLI(args.config)
        exit_code = cli.run(args)
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\nInterrupted", file=sys.stderr)
        sys.exit(130)
    except Exception as e:
        print(f"Fatal error: {str(e)}", file=sys.stderr)
        if args.debug:
            import traceback
            traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
