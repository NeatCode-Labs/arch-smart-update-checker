"""
Application constants for Arch Smart Update Checker.
"""

# SPDX-License-Identifier: GPL-3.0-or-later

from pathlib import Path

# Application info
APP_NAME = "Arch Smart Update Checker"
APP_VERSION = "2.1.0"
APP_USER_AGENT = f"{APP_NAME}/{APP_VERSION}"

# File permissions (octal)
CONFIG_DIR_PERMISSIONS = 0o700  # rwx------
CONFIG_FILE_PERMISSIONS = 0o600  # rw-------
CACHE_DIR_PERMISSIONS = 0o700   # rwx------

# Default values
DEFAULT_CACHE_TTL_HOURS = 1
DEFAULT_MAX_NEWS_ITEMS = 10
DEFAULT_MAX_NEWS_AGE_DAYS = 30
DEFAULT_NEWS_FRESHNESS_DAYS = 14

# GUI dimensions
SIDEBAR_WIDTH = 250
WINDOW_MIN_WIDTH = 1024
WINDOW_MIN_HEIGHT = 768
POPUP_WIDTH = 500
POPUP_HEIGHT = 400
BRAND_HEADER_HEIGHT = 80

# Network timeouts (seconds)
FEED_FETCH_TIMEOUT = 30
DEFAULT_REQUEST_TIMEOUT = 10

# GUI update intervals (milliseconds)
STATUS_UPDATE_DELAY = 100
PROGRESS_UPDATE_INTERVAL = 100
AUTOSAVE_DELAY = 1000  # 1 second

# Package name validation (more restrictive)
PACKAGE_NAME_PATTERN = r'^[a-zA-Z0-9][a-zA-Z0-9\-_.+]*[a-zA-Z0-9]$'

# Critical packages list
DEFAULT_CRITICAL_PACKAGES = [
    "linux",
    "nvidia",
    "xorg",
    "systemd",
    "grub",
    "glibc",
    "gcc",
    "pacman",
]

# Trusted RSS feed domains
TRUSTED_FEED_DOMAINS = {
    "archlinux.org",
    "security.archlinux.org",
    "forum.manjaro.org",
    "endeavouros.com",
    "archlinux32.org",
}

# Feed URL validation pattern
FEED_URL_PATTERN = r'^https?://[a-zA-Z0-9\-._~:/?#[\]@!$&\'()*+,;=]+$'

# Generic package names to exclude from pattern matching
GENERIC_PACKAGE_NAMES = {
    "package",
    "update",
    "version",
    "release",
    "driver",
    "security",
    "critical",
    "important",
    "bugfix",
}

# Paths
def get_config_dir() -> Path:
    """Get the configuration directory path."""
    return Path.home() / ".config" / "arch-smart-update-checker"

def get_cache_dir() -> Path:
    """Get the cache directory path."""
    return Path.home() / ".cache" / "arch-smart-update-checker"

def get_default_config_path() -> Path:
    """Get the default configuration file path."""
    return get_config_dir() / "config.json"

def get_default_log_path() -> Path:
    """Get the default log file path."""
    return get_cache_dir() / "application.log"
