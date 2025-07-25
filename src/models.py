"""
Data models for Arch Smart Update Checker.
"""

# SPDX-License-Identifier: GPL-3.0-or-later

from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional, Dict, Any, Set
from enum import Enum


class FeedType(Enum):
    """Type of RSS feed."""
    NEWS = "news"
    PACKAGE = "package"


class UpdateStatus(Enum):
    """Status of update checking."""
    IDLE = "idle"
    CHECKING = "checking"
    SUCCESS = "success"
    ERROR = "error"


@dataclass
class NewsItem:
    """Represents a news item from an RSS feed."""
    title: str
    link: str
    date: datetime
    content: str
    source: str
    priority: int
    source_type: FeedType = FeedType.NEWS
    affected_packages: Set[str] = field(default_factory=set)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "title": self.title,
            "link": self.link,
            "date": self.date.isoformat() if isinstance(self.date, datetime) else str(self.date),
            "content": self.content,
            "source": self.source,
            "priority": self.priority,
            "source_type": self.source_type.value,
            "affected_packages": list(self.affected_packages)
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'NewsItem':
        """Create from dictionary."""
        date = data.get("date", datetime.min)
        if isinstance(date, str):
            try:
                date = datetime.fromisoformat(date)
            except (ValueError, TypeError):
                date = datetime.min

        return cls(
            title=data.get("title", ""),
            link=data.get("link", ""),
            date=date,
            content=data.get("content", ""),
            source=data.get("source", ""),
            priority=data.get("priority", 0),
            source_type=FeedType(data.get("source_type", "news")),
            affected_packages=set(data.get("affected_packages", []))
        )


@dataclass
class FeedConfig:
    """Configuration for an RSS feed."""
    name: str
    url: str
    priority: int = 1
    feed_type: FeedType = FeedType.NEWS
    enabled: bool = True

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "name": self.name,
            "url": self.url,
            "priority": self.priority,
            "type": self.feed_type.value,
            "enabled": self.enabled
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'FeedConfig':
        """Create from dictionary."""
        return cls(
            name=data.get("name", ""),
            url=data.get("url", ""),
            priority=data.get("priority", 1),
            feed_type=FeedType(data.get("type", "news")),
            enabled=data.get("enabled", True)
        )


@dataclass
class PackageUpdate:
    """Represents a package update."""

    name: str
    current_version: str
    new_version: str
    repository: Optional[str] = None
    size: Optional[int] = None  # Download size in bytes
    installed_size: Optional[int] = None  # Installed size in bytes

    def __post_init__(self) -> None:
        """Validate package update data."""
        if not self.name:
            raise ValueError("Package name cannot be empty")
        if not self.current_version:
            raise ValueError("Current version cannot be empty")
        if not self.new_version:
            raise ValueError("New version cannot be empty")

    def __str__(self) -> str:
        """String representation."""
        return f"{self.name} {self.current_version} -> {self.new_version}"


@dataclass
class UpdateCheckResult:
    """Result of an update check operation."""
    status: UpdateStatus
    updates: List[PackageUpdate] = field(default_factory=list)
    news_items: List[NewsItem] = field(default_factory=list)
    error_message: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.now)

    @property
    def update_count(self) -> int:
        """Get number of available updates."""
        return len(self.updates)

    @property
    def news_count(self) -> int:
        """Get number of news items."""
        return len(self.news_items)

    @property
    def has_updates(self) -> bool:
        """Check if there are any updates."""
        return len(self.updates) > 0

    @property
    def has_news(self) -> bool:
        """Check if there are any news items."""
        return len(self.news_items) > 0


@dataclass
class AppConfig:
    """Application configuration."""
    cache_ttl_hours: int = 1
    feeds: List[FeedConfig] = field(default_factory=list)
    extra_patterns: List[str] = field(default_factory=list)
    critical_packages: List[str] = field(default_factory=list)
    distribution: str = "arch"
    max_news_items: int = 10
    max_news_age_days: int = 30
    non_interactive: bool = False
    log_file: Optional[str] = None
    auto_refresh_feeds: bool = True
    theme: str = "light"
    debug_mode: bool = False
    verbose_logging: bool = False
    update_history_enabled: bool = False
    update_history_retention_days: int = 365

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "cache_ttl_hours": self.cache_ttl_hours,
            "feeds": [f.to_dict() for f in self.feeds],
            "extra_patterns": self.extra_patterns,
            "critical_packages": self.critical_packages,
            "distribution": self.distribution,
            "max_news_items": self.max_news_items,
            "max_news_age_days": self.max_news_age_days,
            "non_interactive": self.non_interactive,
            "log_file": self.log_file,
            "auto_refresh_feeds": self.auto_refresh_feeds,
            "theme": self.theme,
            "debug_mode": self.debug_mode,
            "verbose_logging": self.verbose_logging,
            "update_history_enabled": self.update_history_enabled,
            "update_history_retention_days": self.update_history_retention_days
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'AppConfig':
        """Create from dictionary."""
        feeds = [FeedConfig.from_dict(f) for f in data.get("feeds", [])]
        return cls(
            cache_ttl_hours=data.get("cache_ttl_hours", 1),
            feeds=feeds,
            extra_patterns=data.get("extra_patterns", []),
            critical_packages=data.get("critical_packages", []),
            distribution=data.get("distribution", "arch"),
            max_news_items=data.get("max_news_items", 10),
            max_news_age_days=data.get("max_news_age_days", 30),
            non_interactive=data.get("non_interactive", False),
            log_file=data.get("log_file"),
            auto_refresh_feeds=data.get("auto_refresh_feeds", True),
            theme=data.get("theme", "light"),
            debug_mode=data.get("debug_mode", False),
            verbose_logging=data.get("verbose_logging", False),
            update_history_enabled=data.get("update_history_enabled", False),
            update_history_retention_days=data.get("update_history_retention_days", 365)
        )
