"""
Configuration management for the Arch Smart Update Checker.
"""

# SPDX-License-Identifier: GPL-3.0-or-later

import json
import os
from pathlib import Path
from typing import Dict, List, Any, Optional

from .exceptions import ConfigurationError
from .utils.distribution import DistributionDetector
from .utils.logger import get_logger
from .utils.secure_memory import SecureDict, MemoryManager, force_memory_cleanup
from .constants import (
    CONFIG_DIR_PERMISSIONS, CONFIG_FILE_PERMISSIONS,
    DEFAULT_CACHE_TTL_HOURS, DEFAULT_MAX_NEWS_ITEMS,
    DEFAULT_MAX_NEWS_AGE_DAYS,
    DEFAULT_CRITICAL_PACKAGES, get_default_config_path
)
from .models import AppConfig, FeedConfig, FeedType

logger = get_logger(__name__)


class Config:
    """Manages configuration for the Arch Smart Update Checker."""

    def __init__(self, config_file: Optional[str] = None) -> None:
        """
        Initialize configuration.

        Args:
            config_file: Path to configuration file
        """
        from .utils.validators import validate_config_path
        
        self._batch_mode = False  # Prevent saves during batch updates
        
        if config_file:
            try:
                validate_config_path(config_file)
                self.config_file = config_file
            except ValueError as e:
                logger.error(f"Invalid config file path: {e}")
                logger.info("Falling back to default config path")
                self.config_file = str(get_default_config_path())
        else:
            self.config_file = str(get_default_config_path())
            
        self.distribution_detector = DistributionDetector()
        self._app_config = self._load_config()
        # Keep the old dict interface for backward compatibility
        self.config = self._app_config.to_dict()

    def _get_default_config_path(self) -> str:
        """
        Get the default configuration file path.

        Returns:
            Path to default configuration file
        """
        return str(get_default_config_path())

    def _load_config(self) -> AppConfig:
        """
        Load configuration from file or create default with security validation.

        Returns:
            AppConfig instance
        """
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, "r", encoding="utf-8") as f:
                    # Load JSON with size limit to prevent memory exhaustion
                    file_size = os.path.getsize(self.config_file)
                    if file_size > 1024 * 1024:  # 1MB limit
                        raise ValueError(f"Config file too large: {file_size} bytes")
                    
                    data = json.load(f)
                    
                    # Validate and sanitize the configuration
                    from .utils.validators import validate_config_json, sanitize_config_json
                    
                    try:
                        validate_config_json(data)
                        sanitized_data = sanitize_config_json(data)
                        logger.info(f"Loaded and validated configuration from {self.config_file}")
                        return AppConfig.from_dict(sanitized_data)
                    except ValueError as e:
                        logger.error(f"Invalid configuration structure: {e}")
                        logger.info("Using default configuration due to validation failure")
                        return self._get_default_app_config()
                        
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in config file {self.config_file}: {e}")
        except PermissionError as e:
            logger.error(f"Permission denied reading config file {self.config_file}: {e}")
        except OSError as e:
            logger.error(f"Error reading config file {self.config_file}: {e}")
        except ValueError as e:
            logger.error(f"Config file validation error: {e}")

        logger.info("Using default configuration")
        return self._get_default_app_config()

    def _get_default_app_config(self) -> AppConfig:
        """
        Get default application configuration.

        Returns:
            Default AppConfig instance
        """
        # Detect distribution
        distro = self.distribution_detector.detect_distribution()
        distro_feeds = self.distribution_detector.get_distribution_feeds(distro)

        # Base feeds
        feeds = [
            FeedConfig(
                name="Arch Linux News",
                url="https://archlinux.org/feeds/news/",
                priority=1,
                feed_type=FeedType.NEWS,
                enabled=True
            ),
            FeedConfig(
                name="Arch Linux Security Advisories",
                url="https://security.archlinux.org/advisory/feed.atom",
                priority=1,
                feed_type=FeedType.NEWS,
                enabled=True
            ),
        ]

        # Add distribution-specific feeds
        for feed_dict in distro_feeds:
            feeds.append(FeedConfig.from_dict(feed_dict))

        return AppConfig(
            cache_ttl_hours=DEFAULT_CACHE_TTL_HOURS,
            feeds=feeds,
            extra_patterns=[],
            critical_packages=DEFAULT_CRITICAL_PACKAGES.copy(),
            distribution=distro,
            max_news_items=DEFAULT_MAX_NEWS_ITEMS,
            max_news_age_days=DEFAULT_MAX_NEWS_AGE_DAYS,
            non_interactive=False,
            log_file=None,
            update_history_enabled=False,
            update_history_retention_days=365
        )

    def _get_default_config(self) -> Dict[str, Any]:
        """
        Get default configuration dictionary.

        Returns:
            Default configuration dictionary
        """
        return self._get_default_app_config().to_dict()

    def save_config(self) -> None:
        """
        Save current configuration to file.

        Raises:
            ConfigurationError: If saving fails
        """
        # Skip saving if in batch mode
        if getattr(self, '_batch_mode', False):
            return
            
        try:
            config_dir = Path(self.config_file).parent
            config_dir.mkdir(parents=True, exist_ok=True)

            # Set secure permissions on config directory
            try:
                os.chmod(config_dir, CONFIG_DIR_PERMISSIONS)
            except OSError as e:
                logger.warning(f"Failed to set permissions on config directory: {e}")

            with open(self.config_file, "w", encoding="utf-8") as f:
                json.dump(self.config, f, indent=2, ensure_ascii=False)

            # Set secure permissions on config file
            try:
                os.chmod(self.config_file, CONFIG_FILE_PERMISSIONS)
            except OSError as e:
                logger.warning(f"Failed to set permissions on config file: {e}")

            logger.info(f"Saved configuration to {self.config_file}")

        except PermissionError as e:
            raise ConfigurationError(f"Permission denied saving config: {e}")
        except OSError as e:
            raise ConfigurationError(f"Failed to save config: {e}")

    def get(self, key: str, default: Optional[Any] = None) -> Optional[Any]:
        """
        Get configuration value.

        Args:
            key: Configuration key
            default: Default value if key not found

        Returns:
            Configuration value
        """
        return self.config.get(key, default)

    def set(self, key: str, value: Any) -> None:
        """
        Set configuration value.

        Args:
            key: Configuration key
            value: Configuration value
        """
        self.config[key] = value
        # Update the AppConfig instance
        self._app_config = AppConfig.from_dict(self.config)
        self.save_config()

    def get_feeds(self) -> List[Dict[str, Any]]:
        """Get the news feeds configuration."""
        feeds = self.config.get("feeds", [])
        if isinstance(feeds, list):
            return feeds
        logger.warning("Invalid feeds configuration, using empty list")
        return []

    def get_cache_ttl(self) -> int:
        """Get the cache TTL in hours."""
        value = self.config.get("cache_ttl_hours", DEFAULT_CACHE_TTL_HOURS)
        if isinstance(value, int) and value > 0:
            return value
        logger.warning(f"Invalid cache TTL {value}, using default {DEFAULT_CACHE_TTL_HOURS}")
        return DEFAULT_CACHE_TTL_HOURS

    def get_extra_patterns(self) -> List[str]:
        """Get extra package patterns."""
        patterns = self.config.get("extra_patterns", [])
        if isinstance(patterns, list):
            return patterns
        logger.warning("Invalid extra_patterns configuration, using empty list")
        return []

    def get_critical_packages(self) -> List[str]:
        """Get critical packages list."""
        packages = self.config.get("critical_packages", DEFAULT_CRITICAL_PACKAGES)
        if isinstance(packages, list):
            return packages
        logger.warning("Invalid critical_packages configuration, using defaults")
        return DEFAULT_CRITICAL_PACKAGES.copy()

    def get_max_news_items(self) -> int:
        """Get maximum number of news items to display."""
        value = self.config.get("max_news_items", DEFAULT_MAX_NEWS_ITEMS)
        if isinstance(value, int) and value > 0:
            # Enforce security limit: maximum 1000 items
            if value > 1000:
                logger.warning(f"Max news items {value} exceeds security limit (1000), capping to 1000")
                return 1000
            return value
        logger.warning(f"Invalid max_news_items {value}, using default {DEFAULT_MAX_NEWS_ITEMS}")
        return DEFAULT_MAX_NEWS_ITEMS

    def get_max_news_age_days(self) -> int:
        """Get maximum age of news items in days."""
        value = self.config.get("max_news_age_days", DEFAULT_MAX_NEWS_AGE_DAYS)
        if isinstance(value, int) and value > 0:
            # Enforce security limit: maximum 365 days (1 year)
            if value > 365:
                logger.warning(f"Max news age {value} exceeds security limit (365 days), capping to 365")
                return 365
            return value
        logger.warning(f"Invalid max_news_age_days {value}, using default {DEFAULT_MAX_NEWS_AGE_DAYS}")
        return DEFAULT_MAX_NEWS_AGE_DAYS

    def init_config(self) -> None:
        """Initialize configuration file with defaults."""
        if os.path.exists(self.config_file):
            logger.info(f"Configuration file already exists: {self.config_file}")
            return

        try:
            self.save_config()
            logger.info(f"Created configuration file: {self.config_file}")
        except ConfigurationError as e:
            logger.error(f"Failed to create configuration file: {e}")
            raise

    def update_settings(self, settings: Dict[str, Any]) -> None:
        """
        Update multiple settings at once.

        Args:
            settings: Dictionary of settings to update
        """
        self.config.update(settings)
        self._app_config = AppConfig.from_dict(self.config)
        self.save_config()

    def get_all_settings(self) -> Dict[str, Any]:
        """Get all settings as a dictionary."""
        return self.config.copy()

    def add_feed(self, name: str, url: str, priority: int = 2, feed_type: str = "news") -> None:
        """
        Add a new feed to the configuration.

        Args:
            name: Feed name
            url: Feed URL
            priority: Feed priority
            feed_type: Type of feed (news or package)
        """
        feeds = self.get_feeds()

        # Check if feed already exists
        for feed in feeds:
            if feed.get("url") == url:
                logger.warning(f"Feed already exists: {url}")
                return

        new_feed = FeedConfig(
            name=name,
            url=url,
            priority=priority,
            feed_type=FeedType(feed_type),
            enabled=True
        )

        feeds.append(new_feed.to_dict())
        self.config["feeds"] = feeds
        self.save_config()
        logger.info(f"Added new feed: {name}")

    def batch_update(self):
        """Context manager for batch updates without intermediate saves."""
        from contextlib import contextmanager
        
        @contextmanager
        def _batch_context():
            self._batch_mode = True
            try:
                yield
            finally:
                self._batch_mode = False
                # Save once at the end
                self.save_config()
                
        return _batch_context()
            
    def set_feeds(self, feeds: List[Dict[str, Any]]) -> None:
        """
        Set the entire feeds list.

        Args:
            feeds: List of feed configurations
        """
        # Validate feeds
        validated_feeds = []
        for feed in feeds:
            try:
                feed_config = FeedConfig.from_dict(feed)
                validated_feeds.append(feed_config.to_dict())
            except Exception as e:
                logger.error(f"Invalid feed configuration: {e}")

        self.config["feeds"] = validated_feeds
        self.save_config()

    def reset_feeds_to_defaults(self) -> None:
        """Reset feeds to default configuration."""
        default_config = self._get_default_app_config()
        self.config["feeds"] = [f.to_dict() for f in default_config.feeds]
        self.save_config()
        logger.info("Reset feeds to defaults")

    def clear_sensitive_data(self):
        """Clear sensitive configuration data from memory."""
        try:
            # Clear configuration data that might be sensitive
            if hasattr(self, 'config') and self.config:
                # Create a secure dict for sensitive data clearing
                sensitive_keys = ['feeds', 'user_settings', 'api_keys', 'credentials']
                for key in sensitive_keys:
                    if key in self.config:
                        value = self.config[key]
                        if isinstance(value, (list, dict)):
                            # Clear the data structure
                            if isinstance(value, list):
                                for i in range(len(value)):
                                    value[i] = None
                                value.clear()
                            elif isinstance(value, dict):
                                for k in list(value.keys()):
                                    value[k] = None
                                value.clear()
                
                # Force memory cleanup
                force_memory_cleanup()
                logger.debug("Cleared sensitive configuration data from memory")
                
        except Exception as e:
            logger.debug(f"Error clearing sensitive config data: {e}")

    def __del__(self):
        """Destructor - clear sensitive data when config object is destroyed."""
        try:
            self.clear_sensitive_data()
        except Exception:
            pass  # Ignore errors during destruction
