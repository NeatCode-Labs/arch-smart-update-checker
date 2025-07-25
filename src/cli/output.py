"""
Output formatting utilities for the CLI.
"""

# SPDX-License-Identifier: GPL-3.0-or-later

import json
from typing import Any, Dict, List
from datetime import datetime
import sys

from colorama import init, Fore, Style

# Initialize colorama for cross-platform color support
init(autoreset=True)


class OutputFormatter:
    """Handles output formatting for the CLI."""

    def __init__(self, use_color: bool = True, json_output: bool = False):
        """
        Initialize output formatter.

        Args:
            use_color: Whether to use ANSI colors
            json_output: Whether to output JSON
        """
        self.use_color = use_color
        self.json_output = json_output

        # Color shortcuts
        self.green = Fore.GREEN if use_color else ''
        self.yellow = Fore.YELLOW if use_color else ''
        self.red = Fore.RED if use_color else ''
        self.cyan = Fore.CYAN if use_color else ''
        self.white = Fore.WHITE if use_color else ''
        self.reset = Style.RESET_ALL if use_color else ''
        self.bright = Style.BRIGHT if use_color else ''

    def success(self, message: str) -> None:
        """Print success message."""
        if not self.json_output:
            print(f"{self.green}✅ {message}{self.reset}")

    def warning(self, message: str) -> None:
        """Print warning message."""
        if not self.json_output:
            print(f"{self.yellow}⚠️  {message}{self.reset}")

    def error(self, message: str) -> None:
        """Print error message."""
        if not self.json_output:
            print(f"{self.red}❌ {message}{self.reset}", file=sys.stderr)

    def info(self, message: str) -> None:
        """Print info message."""
        if not self.json_output:
            print(f"{self.cyan}ℹ️  {message}{self.reset}")

    def header(self, message: str) -> None:
        """Print header message."""
        if not self.json_output:
            print(f"\n{self.cyan}{self.bright}{message}{self.reset}")
            print(f"{self.cyan}{'─' * len(message)}{self.reset}")

    def format_updates_table(self, updates: List[Dict[str, str]]) -> str:
        """
        Format package updates as a table.

        Args:
            updates: List of update dictionaries

        Returns:
            Formatted table string
        """
        if not updates:
            return "No updates available"

        # Calculate column widths
        max_name = max(len(u.get('name', '')) for u in updates)
        max_current = max(len(u.get('current_version', '')) for u in updates)
        max_new = max(len(u.get('new_version', '')) for u in updates)

        # Ensure minimum widths
        max_name = max(max_name, 10)
        max_current = max(max_current, 15)
        max_new = max(max_new, 15)

        lines = []

        # Header
        header = f"  {'Package':<{max_name}}  {'Current':<{max_current}}  {'New':<{max_new}}"
        lines.append(header)
        lines.append(f"  {'─' * max_name}  {'─' * max_current}  {'─' * max_new}")

        # Rows
        for update in updates:
            name = update.get('name', 'unknown')
            current = update.get('current_version', 'unknown')
            new = update.get('new_version', 'unknown')

            if self.use_color:
                row = f"  {self.white}{name:<{max_name}}{self.reset}  {current:<{max_current}}  {self.green}{new:<{max_new}}{self.reset}"
            else:
                row = f"  {name:<{max_name}}  {current:<{max_current}}  {new:<{max_new}}"

            lines.append(row)

        return '\n'.join(lines)

    def format_news_items(self, news_items: List[Dict[str, Any]]) -> str:
        """
        Format news items.

        Args:
            news_items: List of news item dictionaries

        Returns:
            Formatted news string
        """
        if not news_items:
            return "No relevant news items"

        lines = []

        for item in news_items:
            date = item.get('published', 'unknown date')
            title = item.get('title', 'Untitled')
            content = item.get('content', '')
            affected = item.get('affected_packages', [])

            if self.use_color:
                lines.append(f"  {self.yellow}[{date}]{self.reset} {self.white}{title}{self.reset}")
            else:
                lines.append(f"  [{date}] {title}")

            # Add news content if available
            if content:
                # Clean and format the content
                import re
                # Remove HTML tags
                clean_content = re.sub('<[^<]+?>', '', content)
                # Wrap long lines
                import textwrap
                wrapper = textwrap.TextWrapper(width=78, initial_indent='    ', subsequent_indent='    ')
                wrapped_content = wrapper.fill(clean_content.strip())
                lines.append(wrapped_content)

            if affected:
                packages_str = ', '.join(list(affected)[:5])
                if len(affected) > 5:
                    packages_str += f" +{len(affected) - 5} more"
                lines.append(f"    Affects: {packages_str}")

            lines.append("")  # Empty line between items

        return '\n'.join(lines).strip()

    def format_history_table(self, entries: List[Dict[str, Any]]) -> str:
        """
        Format update history entries as a table.

        Args:
            entries: List of history entry dictionaries

        Returns:
            Formatted table string
        """
        if not entries:
            return "No update history"

        lines = []

        # Header
        header = f"  {'Date/Time':<20}  {'Packages':<30}  {'Result':<8}  {'Duration':<10}"
        lines.append(header)
        lines.append(f"  {'─' * 20}  {'─' * 30}  {'─' * 8}  {'─' * 10}")

        # Rows
        for entry in entries:
            timestamp = entry.get('timestamp', '')
            if timestamp:
                try:
                    dt = datetime.fromisoformat(timestamp)
                    date_str = dt.strftime('%Y-%m-%d %H:%M:%S')
                except:
                    date_str = timestamp[:19]  # First 19 chars
            else:
                date_str = 'unknown'

            packages = entry.get('packages', [])
            if len(packages) <= 3:
                packages_str = ', '.join(packages)
            else:
                packages_str = f"{', '.join(packages[:3])} +{len(packages) - 3}"

            # Truncate if too long
            if len(packages_str) > 30:
                packages_str = packages_str[:27] + '...'

            succeeded = entry.get('succeeded', False)
            if self.use_color:
                result_str = f"{self.green}✅ Pass{self.reset}" if succeeded else f"{self.red}❌ Fail{self.reset}"
            else:
                result_str = "Pass" if succeeded else "Fail"

            duration = entry.get('duration_sec', 0)
            duration_str = f"{duration:.1f}s"

            lines.append(f"  {date_str:<20}  {packages_str:<30}  {result_str:<8}  {duration_str:<10}")

        return '\n'.join(lines)

    def output_json(self, data: Any) -> None:
        """
        Output data as JSON.

        Args:
            data: Data to output
        """
        print(json.dumps(data, indent=2, default=str))
