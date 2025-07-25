"""
Update checker for Arch Linux systems.
"""

# SPDX-License-Identifier: GPL-3.0-or-later

import os
import time
from datetime import datetime
from typing import List, Optional, Set

from .config import Config
from .news_fetcher import NewsFetcher
from .package_manager import PackageManager
from .utils.cache import CacheManager
from .utils.patterns import PackagePatternMatcher
from .utils.logger import get_logger
from .constants import get_cache_dir
from .models import NewsItem, UpdateCheckResult, UpdateStatus, FeedConfig

logger = get_logger(__name__)


class UpdateChecker:
    """Main update checker for Arch Linux systems."""

    def __init__(self, config: Config) -> None:
        """
        Initialize the update checker.

        Args:
            config: Configuration instance
        """
        self.config = config
        self.cache_manager = CacheManager(
            cache_dir=str(get_cache_dir()),
            ttl_hours=config.get_cache_ttl()
        )
        self.news_fetcher = NewsFetcher(self.cache_manager)
        self.package_manager = PackageManager()
        self.pattern_matcher = PackagePatternMatcher()

        # Configure news fetcher with max age setting
        self.news_fetcher.max_news_age_days = config.get_max_news_age_days()

        # Last check tracking
        self.last_check_file = get_cache_dir() / "last_check"

        # Last results for GUI
        self.last_news_items: List[NewsItem] = []
        self.last_update_result: Optional[UpdateCheckResult] = None

        logger.info("Initialized UpdateChecker")

    def check_updates(self) -> UpdateCheckResult:
        """
        Check for system updates and relevant news.

        Returns:
            UpdateCheckResult with updates and news items
        """
        logger.info("Starting update check...")
        result = UpdateCheckResult(status=UpdateStatus.CHECKING)

        try:
            # Get available updates
            logger.debug("Checking for package updates...")
            package_updates = self.package_manager.check_for_updates()
            result.updates = package_updates

            # Get installed packages for matching
            logger.debug("Getting installed packages...")
            installed_packages = self.package_manager.get_installed_package_names()

            # Fetch news
            logger.debug("Fetching news feeds...")
            feed_configs = [FeedConfig.from_dict(f) for f in self.config.get_feeds()]
            all_news = self.news_fetcher.fetch_all_feeds(feed_configs)

            # Filter relevant news
            logger.debug("Filtering relevant news...")
            relevant_news = self._filter_relevant_news(all_news, installed_packages)

            # Limit to max items with security enforcement
            max_items = self.config.get_max_news_items()
            # Double-check the limit for security (in case config was tampered with)
            safe_max_items = min(max_items, 1000)
            result.news_items = relevant_news[:safe_max_items]

            # Update last check time
            self._update_last_check_time()

            # Update status
            result.status = UpdateStatus.SUCCESS

            # Store results for GUI access
            self.last_news_items = result.news_items
            self.last_update_result = result

            logger.info(f"Update check complete: {result.update_count} updates, {result.news_count} news items")

        except Exception as e:
            logger.error(f"Error during update check: {e}")
            result.status = UpdateStatus.ERROR
            result.error_message = str(e)

        return result

    def _filter_relevant_news(self, all_news: List[NewsItem],
                            installed_packages: Set[str]) -> List[NewsItem]:
        """
        Filter news items based on relevance to installed packages.

        Args:
            all_news: All news items
            installed_packages: Set of installed package names

        Returns:
            List of relevant news items
        """
        # Get critical packages
        critical_packages = set(self.config.get_critical_packages())

        # Get extra patterns
        extra_patterns = self.config.get_extra_patterns()

        # Process each news item
        relevant_news = []
        for news_item in all_news:
            # Extract affected packages
            affected = self.pattern_matcher.extract_package_names(
                news_item.title + " " + news_item.content,
                installed_packages,
                extra_patterns
            )
            news_item.affected_packages = affected

            # Check relevance
            if self._is_news_relevant(news_item, installed_packages, critical_packages):
                relevant_news.append(news_item)

        return relevant_news

    def _is_news_relevant(self, news_item: NewsItem,
                         installed_packages: Set[str],
                         critical_packages: Set[str]) -> bool:
        """
        Check if a news item is relevant.

        Args:
            news_item: News item to check
            installed_packages: Set of installed packages
            critical_packages: Set of critical packages

        Returns:
            True if news item is relevant
        """
        # Always include security advisories
        if "security" in news_item.source.lower():
            return True

        # Check if any affected packages are installed
        if news_item.affected_packages & installed_packages:
            return True

        # Check for critical package mentions
        if news_item.affected_packages & critical_packages:
            return True

        # Check for general importance keywords
        important_keywords = [
            "breaking", "critical", "urgent", "security",
            "vulnerability", "exploit", "manual intervention"
        ]

        combined_text = (news_item.title + " " + news_item.content).lower()
        if any(keyword in combined_text for keyword in important_keywords):
            return True

        return False

    def _update_last_check_time(self) -> None:
        """Update the last check timestamp."""
        try:
            self.last_check_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.last_check_file, 'w') as f:
                f.write(str(time.time()))
            logger.debug("Updated last check time")
        except Exception as e:
            logger.error(f"Failed to update last check time: {e}")

    def get_last_check_time(self) -> Optional[datetime]:
        """
        Get the last check timestamp.

        Returns:
            Last check datetime or None
        """
        try:
            # Use atomic operation - try to open directly instead of checking existence
            with open(self.last_check_file, 'r') as f:
                timestamp = float(f.read().strip())
                return datetime.fromtimestamp(timestamp)
        except FileNotFoundError:
            # File doesn't exist, return None
            return None
        except Exception as e:
            logger.error(f"Failed to read last check time: {e}")

        return None

    def clear_cache(self) -> None:
        """Clear all caches."""
        try:
            self.cache_manager.clear()
            self.package_manager.clear_cache()
            logger.info("Cleared all caches")
        except Exception as e:
            logger.error(f"Failed to clear cache: {e}")

    def get_news_items(self) -> List[NewsItem]:
        """
        Get news items (legacy method for backward compatibility).

        Returns:
            List of news items from last check
        """
        if not self.last_news_items:
            # Run a check if no cached results
            result = self.check_updates()
            return result.news_items
        return self.last_news_items

    def get_critical_updates(self) -> List[str]:
        """
        Get list of critical package updates.

        Returns:
            List of critical package names that have updates
        """
        if not self.last_update_result:
            return []

        critical_packages = set(self.config.get_critical_packages())
        critical_updates = []

        for update in self.last_update_result.updates:
            if update.name in critical_packages:
                critical_updates.append(update.name)

        return critical_updates

    def check_news_only(self) -> UpdateCheckResult:
        """
        Check for news items only (no package updates).
        
        Returns:
            UpdateCheckResult with only news items
        """
        logger.info("Checking for news only...")
        result = UpdateCheckResult(status=UpdateStatus.CHECKING)
        
        try:
            # Get installed packages for matching
            logger.debug("Getting installed packages...")
            installed_packages = self.package_manager.get_installed_package_names()
            
            # Fetch news
            logger.debug("Fetching news feeds...")
            feed_configs = [FeedConfig.from_dict(f) for f in self.config.get_feeds()]
            all_news = self.news_fetcher.fetch_all_feeds(feed_configs)
            
            # Filter relevant news
            logger.debug("Filtering relevant news...")
            relevant_news = self._filter_relevant_news(all_news, installed_packages)
            
            # Limit to max items
            max_items = self.config.get_max_news_items()
            safe_max_items = min(max_items, 1000)
            result.news_items = relevant_news[:safe_max_items]
            
            # No updates in news-only mode
            result.updates = []
            
            # Update status
            result.status = UpdateStatus.SUCCESS
            
            # Store results for GUI access
            self.last_news_items = result.news_items
            self.last_update_result = result
            
            logger.info(f"News check complete: {result.news_count} news items")
            
        except Exception as e:
            logger.error(f"Error during news check: {e}")
            result.status = UpdateStatus.ERROR
            result.error_message = str(e)
            
        return result

    def has_critical_news(self) -> bool:
        """
        Check if there are any critical news items.

        Returns:
            True if critical news exists
        """
        if not self.last_news_items:
            return False

        for news_item in self.last_news_items:
            # Check source
            if "security" in news_item.source.lower():
                return True

            # Check content
            if any(word in news_item.title.lower()
                   for word in ["critical", "security", "urgent"]):
                return True

        return False

    def get_update_summary(self) -> dict:
        """
        Get a summary of the current update status.

        Returns:
            Dictionary with update summary
        """
        if not self.last_update_result:
            return {
                "status": "unknown",
                "update_count": 0,
                "news_count": 0,
                "critical_updates": [],
                "has_critical_news": False,
                "last_check": None
            }

        return {
            "status": self.last_update_result.status.value,
            "update_count": self.last_update_result.update_count,
            "news_count": self.last_update_result.news_count,
            "critical_updates": self.get_critical_updates(),
            "has_critical_news": self.has_critical_news(),
            "last_check": self.get_last_check_time()
        }
