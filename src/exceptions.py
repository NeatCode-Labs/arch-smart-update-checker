"""
Custom exceptions for the Arch Smart Update Checker.
"""

# SPDX-License-Identifier: GPL-3.0-or-later


class ArchSmartUpdateCheckerError(Exception):
    """Base exception for all Arch Smart Update Checker errors."""

    pass


class NetworkError(ArchSmartUpdateCheckerError):
    """Raised when network operations fail."""

    pass


class FeedParsingError(ArchSmartUpdateCheckerError):
    """Raised when there's an error parsing RSS feeds."""

    def __init__(self, message: str, feed_name: str = "", feed_url: str = "") -> None:
        """Initialize the error."""
        super().__init__(message)
        self.feed_name = feed_name
        self.feed_url = feed_url

    def __str__(self) -> str:
        return f"{self.args[0]} (Feed: {self.feed_name}, URL: {self.feed_url})"


class PackageManagerError(ArchSmartUpdateCheckerError):
    """Raised when package manager operations fail."""

    pass


class ConfigurationError(ArchSmartUpdateCheckerError):
    """Raised when configuration is invalid."""

    pass


class CacheError(ArchSmartUpdateCheckerError):
    """Raised when cache operations fail."""

    pass
