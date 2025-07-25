"""
Output formatting utilities for terminal display.
"""

# SPDX-License-Identifier: GPL-3.0-or-later

import textwrap
from typing import List, Dict, Any, Optional
from .colors import Colors


class OutputFormatter:
    """Formats output for terminal display."""

    def __init__(self, width: int = 80):
        """
        Initialize the formatter.

        Args:
            width: Terminal width for wrapping
        """
        self.width = width

    def format_header(self, title: str) -> str:
        """
        Format a section header.

        Args:
            title: Header title

        Returns:
            Formatted header
        """
        return f"\n{Colors.header('=' * self.width)}\n{Colors.header(title.center(self.width))}\n{Colors.header('=' * self.width)}"

    def format_subheader(self, title: str) -> str:
        """
        Format a subsection header.

        Args:
            title: Subheader title

        Returns:
            Formatted subheader
        """
        return (
            f"\n{Colors.info('─' * 40)}\n{Colors.info(title)}\n{Colors.info('─' * 40)}"
        )

    def format_news_item(self, news: Dict[str, Any]) -> str:
        """
        Format a news item for display.

        Args:
            news: News item dictionary

        Returns:
            Formatted news item
        """
        title = news.get("title", "No title")
        source = news.get("source", "Unknown source")
        date = news.get("date")
        content = news.get("content", "")

        # Format date
        date_str = ""
        if date:
            try:
                if hasattr(date, 'strftime'):
                    date_str = f" ({date.strftime('%Y-%m-%d %H:%M')})"
                else:
                    date_str = f" ({str(date)})"
            except (AttributeError, TypeError):
                date_str = f" ({str(date)})"

        # Format title and source
        header = f"{Colors.warning('📰')} {Colors.header(title)}"
        source_line = f"{Colors.info('Source:')} {source}{date_str}"

        # Format content
        content_lines = []
        if content:
            wrapped_content = textwrap.fill(content, width=self.width - 4)
            content_lines = [f"  {line}" for line in wrapped_content.split("\n")]

        # Combine all parts
        parts = [header, source_line]
        if content_lines:
            parts.append("")
            parts.extend(content_lines)

        return "\n".join(parts)

    def format_info(self, message: str) -> str:
        """Format an info message."""
        return f"{Colors.info('ℹ')} {Colors.info(message)}"

    def format_package_list(self, packages: List[Dict[str, str]]) -> str:
        """Format a list of packages for display."""
        if not packages:
            return self.format_info("No packages to display.")

        header = f"{Colors.warning('📦')} {Colors.header('Packages')} ({len(packages)} total)"
        package_lines = [
            f"  • {Colors.info(pkg['name'])}"
            for pkg in sorted(packages, key=lambda x: x["name"])
        ]

        return f"{header}\n" + "\n".join(package_lines)

    def format_summary(
        self, updates_count: int, news_count: int, affected_packages: List[str]
    ) -> str:
        """
        Format a summary of findings.

        Args:
            updates_count: Number of available updates
            news_count: Number of relevant news items
            affected_packages: List of affected packages

        Returns:
            Formatted summary
        """
        summary_parts = []

        # Updates summary
        if updates_count > 0:
            summary_parts.append(
                f"{Colors.success('✅')} {Colors.success(f'{updates_count} updates available')}"
            )
        else:
            summary_parts.append(
                f"{Colors.info('ℹ️')} {Colors.info('No updates available')}"
            )

        # News summary
        if news_count > 0:
            summary_parts.append(
                f"{Colors.warning('⚠️')} {Colors.warning(f'{news_count} relevant news items found')}"
            )
        else:
            summary_parts.append(
                f"{Colors.success('✅')} {Colors.success('No relevant news found')}"
            )

        # Affected packages
        if affected_packages:
            affected_count = len(affected_packages)
            if affected_count > 50:
                severity = "🚨"
                severity_text = "CRITICAL"
            elif affected_count > 20:
                severity = "⚠️"
                severity_text = "HIGH"
            elif affected_count > 10:
                severity = "🔶"
                severity_text = "MEDIUM"
            else:
                severity = "🔵"
                severity_text = "LOW"

            summary_parts.append(
                f"{severity} {Colors.error(f'{affected_count} packages may be affected ({severity_text} impact)')}"
            )

        return "\n".join(summary_parts)

    def format_prompt(self, message: str, options: Optional[List[str]] = None) -> str:
        """
        Format a user prompt.

        Args:
            message: Prompt message
            options: Available options

        Returns:
            Formatted prompt
        """
        prompt = f"\n{Colors.info('❓')} {Colors.info(message)}"

        if options:
            option_lines = [f"  {i+1}. {option}" for i, option in enumerate(options)]
            prompt += "\n" + "\n".join(option_lines)

        prompt += f"\n{Colors.info('Enter your choice:')} "
        return prompt

    def format_error(self, message: str) -> str:
        """
        Format an error message.

        Args:
            message: Error message

        Returns:
            Formatted error
        """
        return f"{Colors.error('❌')} {Colors.error(message)}"

    def format_success(self, message: str) -> str:
        """
        Format a success message.

        Args:
            message: Success message

        Returns:
            Formatted success message
        """
        return f"{Colors.success('✅')} {Colors.success(message)}"

    def format_warning(self, message: str) -> str:
        """
        Format a warning message.

        Args:
            message: Warning message

        Returns:
            Formatted warning
        """
        return f"{Colors.warning('⚠️')} {Colors.warning(message)}"

    def format_news(
        self, news_items: List[Dict[str, Any]], options: Optional[List[str]] = None
    ) -> str:
        """Format news items for display."""
        if not news_items:
            return self.format_info("No news items to display.")

        header = f"{Colors.warning('📰')} {Colors.header('News')}"
        news_lines = []

        for item in news_items:
            title = item.get("title", "No title")
            link = item.get("link", "")
            published = item.get("published", "")

            news_lines.append(f"  • {Colors.info(title)}")
            if link:
                news_lines.append(f"    {Colors.info(link)}")
            if published:
                news_lines.append(f"    {Colors.colored(published, Colors.DIM)}")
            news_lines.append("")

        return f"{header}\n" + "\n".join(news_lines)
