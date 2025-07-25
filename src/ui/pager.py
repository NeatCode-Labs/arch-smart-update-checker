"""
Pager utility for handling long output in terminal.
"""

# SPDX-License-Identifier: GPL-3.0-or-later

import os
import sys
from typing import List, Optional, Any, Dict


class Pager:
    """Handles pagination of long output."""

    def __init__(self, page_size: Optional[int] = None) -> None:
        """
        Initialize the pager.

        Args:
            page_size: Number of lines per page (None for auto-detect)
        """
        self.page_size = page_size or self._get_terminal_height()



    def _get_terminal_height(self) -> int:
        """
        Get terminal height for pagination.

        Returns:
            Terminal height in lines
        """
        try:
            # Try to get terminal size
            import shutil

            size = shutil.get_terminal_size()
            return size.lines - 5  # Leave more space for headers and prompt
        except (AttributeError, OSError):
            return 20  # Default fallback

    def paginate(
        self, content: List[str], prompt: str = "Press SPACE (or ENTER) for more, q to quit: "
    ) -> bool:
        """
        Paginate content with user interaction.

        Args:
            content: List of content lines
            prompt: Prompt message

        Returns:
            True if user completed viewing, False if quit early
        """
        if not content:
            return True

        total_lines = len(content)
        current_line = 0
        total_pages = (total_lines + self.page_size - 1) // self.page_size

        while current_line < total_lines:
            # Display current page
            end_line = min(current_line + self.page_size, total_lines)
            page_content = content[current_line:end_line]
            current_page = (current_line // self.page_size) + 1

            # Print page content
            for line in page_content:
                print(line)

            # Show page indicator
            if total_pages > 1:
                print(f"\n--- Page {current_page} of {total_pages} ---")

            # Check if we've reached the end
            if end_line >= total_lines:
                return True

            # Show prompt and get user input
            try:
                user_input = input(f"\n{prompt}").strip().lower()
                
                if user_input in ["q", "quit"]:
                    return False
                elif user_input in ["n", "next", "", " "]:  # Empty string (Enter) or space = next
                    current_line = end_line
                elif user_input in ["p", "prev", "previous"]:
                    # Go back one page
                    current_line = max(0, current_line - self.page_size)
                elif user_input.isdigit():
                    # Jump to specific page
                    page_num = int(user_input)
                    if 1 <= page_num <= total_pages:
                        current_line = (page_num - 1) * self.page_size
                    else:
                        print(f"Invalid page number. Enter 1-{total_pages}")
                        continue
                else:
                    # Show help for unrecognized input
                    print("Navigation: SPACE/ENTER/n=next, p=previous, [page#]=jump, q=quit")
                    continue
            except (EOFError, KeyboardInterrupt):
                return False

        return True

    def paginate_text(
        self, text: str, prompt: str = "Press SPACE (or ENTER) for next, q to quit: "
    ) -> bool:
        """
        Paginate text content.

        Args:
            text: Text content to paginate
            prompt: Prompt message

        Returns:
            True if user completed viewing, False if quit early
        """
        lines = text.split("\n")
        return self.paginate(lines, prompt)

    def paginate_news(self, news_items: List[Dict[str, Any]], formatter: Any) -> bool:
        """
        Paginate news items with formatting.

        Args:
            news_items: List of news item dictionaries
            formatter: OutputFormatter instance

        Returns:
            True if user completed viewing, False if quit early
        """
        if not news_items:
            return True

        formatted_items = []
        for i, news in enumerate(news_items, 1):
            # Add item number for better navigation
            formatted_items.append(f"--- News Item {i} of {len(news_items)} ---")
            formatted_items.append(formatter.format_news_item(news))
            formatted_items.append("")  # Empty line between items

        return self.paginate(
            formatted_items, "Press SPACE (or ENTER) for next, p for prev, q to quit: "
        )

    def paginate_packages(
        self, packages: List[str], title: str, formatter: Any
    ) -> bool:
        """
        Paginate package list with formatting.

        Args:
            packages: List of package names
            title: Section title
            formatter: OutputFormatter instance

        Returns:
            True if user completed viewing, False if quit early
        """
        if not packages:
            return True

        # Format packages with numbers for better navigation
        formatted_items = [f"--- {title} ({len(packages)} packages) ---"]
        for i, package in enumerate(sorted(packages), 1):
            formatted_items.append(f"  {i:3d}. {package}")

        return self.paginate(
            formatted_items, "Press SPACE (or ENTER) for next, p for prev, [page#] to jump, q to quit: "
        )

    def _display_page(self, items: List[str], page: int, total_pages: int) -> None:
        """Display a single page of items."""
        start_idx = page * self.page_size
        end_idx = start_idx + self.page_size
        page_items = items[start_idx:end_idx]

        for item in page_items:
            print(item)

        if total_pages > 1:
            print(f"\nPage {page + 1} of {total_pages}")
