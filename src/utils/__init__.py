"""
Utils package for Arch Smart Update Checker.
"""

# SPDX-License-Identifier: GPL-3.0-or-later

from .cache import CacheManager
from .logger import get_logger, set_global_config
from .distribution import DistributionDetector
from .validators import (
    validate_package_name,
    validate_feed_url,
)
from .pacman_runner import PacmanRunner
from .patterns import PackagePatternMatcher
from .update_history import UpdateHistoryManager, UpdateHistoryEntry
from .window_geometry import WindowGeometryManager, get_geometry_manager
from .subprocess_wrapper import SecureSubprocess
from .instance_lock import (
    InstanceLock,
    InstanceLockError,
    InstanceAlreadyRunningError,
    ensure_single_instance,
    check_single_instance,
)

__all__ = [
    "CacheManager",
    "get_logger",
    "set_global_config",
    "DistributionDetector",
    "validate_package_name",
    "validate_feed_url",
    "PacmanRunner",
    "PackagePatternMatcher",
    "UpdateHistoryManager",
    "UpdateHistoryEntry",
    "WindowGeometryManager",
    "get_geometry_manager",
    "SecureSubprocess",
    "InstanceLock",
    "InstanceLockError",
    "InstanceAlreadyRunningError",
    "ensure_single_instance",
    "check_single_instance",
]
