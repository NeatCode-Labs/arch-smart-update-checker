"""
Timer resource management for GUI components to prevent resource leaks.
"""

# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations

import tkinter as tk
from typing import Dict, Set, Optional, Callable, Any
from contextlib import contextmanager
import uuid
import threading
import time
from collections import deque, defaultdict

from .logger import get_logger

logger = get_logger(__name__)


class TimerResourceManager:
    """Manages GUI timer resources to prevent leaks and ensure proper cleanup."""

    # Global timer tracking
    _active_timers: Dict[str, Any] = {}  # timer_id -> timer_info
    _timer_lock = threading.RLock()  # Use reentrant lock for nested calls

    # Enhanced security limits
    MAX_TIMERS_PER_COMPONENT = 10
    MAX_TOTAL_TIMERS = 100
    DEFAULT_TIMEOUT_MS = 300000  # 5 minutes default timeout

    # Rate limiting for timer creation
    MAX_TIMERS_PER_SECOND = 5
    TIMER_CREATION_WINDOW = 10  # seconds

    # Rate limiting tracking
    _creation_history: deque[tuple[float, str]] = deque(maxlen=100)  # Track recent timer creations
    _component_creation_count: Dict[str, int] = defaultdict(int)
    _last_cleanup = time.time()
    _suspicious_activity_count = 0

    @classmethod
    def _check_rate_limit(cls, component_id: str) -> bool:
        """
        Check if timer creation should be rate limited.

        Args:
            component_id: Component requesting timer creation

        Returns:
            True if timer creation is allowed, False if rate limited
        """
        current_time = time.time()

        # Clean up old entries from creation history
        while cls._creation_history and current_time - cls._creation_history[0][0] > cls.TIMER_CREATION_WINDOW:
            old_time, old_component = cls._creation_history.popleft()
            if old_component in cls._component_creation_count:
                cls._component_creation_count[old_component] = max(0, cls._component_creation_count[old_component] - 1)

        # Check global rate limit
        recent_count = len(cls._creation_history)
        if recent_count >= cls.MAX_TIMERS_PER_SECOND * cls.TIMER_CREATION_WINDOW:
            logger.warning(f"Global timer rate limit exceeded: {recent_count} timers in {cls.TIMER_CREATION_WINDOW}s")
            cls._suspicious_activity_count += 1
            return False

        # Check per-component rate limit
        component_recent_count = cls._component_creation_count.get(component_id, 0)
        if component_recent_count >= cls.MAX_TIMERS_PER_SECOND:
            logger.warning(f"Component timer rate limit exceeded for {component_id}: {component_recent_count} timers")
            cls._suspicious_activity_count += 1
            return False

        # Record this timer creation
        cls._creation_history.append((current_time, component_id))
        cls._component_creation_count[component_id] += 1

        return True

    @classmethod
    def _cleanup_expired_timers(cls):
        """Clean up expired timers to prevent resource leaks."""
        current_time = time.time()
        expired_timers = []

        for timer_id, timer_info in list(cls._active_timers.items()):
            # Check if timer has exceeded its timeout
            creation_time = timer_info.get('creation_time', current_time)
            timeout_ms = timer_info.get('timeout_ms', cls.DEFAULT_TIMEOUT_MS)

            if (current_time - creation_time) * 1000 > timeout_ms:
                expired_timers.append(timer_id)
                logger.debug(f"Timer {timer_id} expired after {timeout_ms}ms")

        # Clean up expired timers
        for timer_id in expired_timers:
            cls._cleanup_timer(timer_id)

        if expired_timers:
            logger.info(f"Cleaned up {len(expired_timers)} expired timers")

        cls._last_cleanup = current_time

    @classmethod
    def create_timer(cls, root: tk.Widget, delay_ms: int, callback: Callable,
                     component_id: Optional[str] = None, timeout_ms: Optional[int] = None,
                     repeat: bool = False) -> Optional[str]:
        """
        Create a managed timer with automatic cleanup and resource limits.

        Args:
            root: Tkinter widget to schedule timer on
            delay_ms: Delay in milliseconds
            callback: Function to call when timer fires
            component_id: Optional component identifier for grouping
            timeout_ms: Maximum lifetime of timer (default: 5 minutes)
            repeat: Whether timer should repeat

        Returns:
            Timer ID if successful, None if limits exceeded
        """
        with cls._timer_lock:
            # Periodic cleanup of expired timers
            current_time = time.time()
            if current_time - cls._last_cleanup > 30:  # Cleanup every 30 seconds
                cls._cleanup_expired_timers()

            # Check rate limiting
            if component_id and not cls._check_rate_limit(component_id):
                return None

            # Check global timer limit
            if len(cls._active_timers) >= cls.MAX_TOTAL_TIMERS:
                logger.warning(f"Timer creation denied: global limit reached ({cls.MAX_TOTAL_TIMERS})")
                # Force cleanup if we're at the limit
                cls._cleanup_expired_timers()
                if len(cls._active_timers) >= cls.MAX_TOTAL_TIMERS:
                    return None

            # Check per-component limit if component_id provided
            if component_id:
                component_count = sum(1 for info in cls._active_timers.values()
                                      if info.get('component_id') == component_id)
                if component_count >= cls.MAX_TIMERS_PER_COMPONENT:
                    logger.warning(f"Timer creation denied: component limit reached for {component_id}")
                    return None

            # Generate unique timer ID
            timer_id = f"timer_{uuid.uuid4().hex[:8]}"
            timeout_ms = timeout_ms or cls.DEFAULT_TIMEOUT_MS

            # Create wrapper function that handles cleanup
            def timer_wrapper():
                try:
                    callback()
                finally:
                    if not repeat:
                        cls._cleanup_timer(timer_id)

            # Schedule the timer
            try:
                after_id = root.after(delay_ms, timer_wrapper)

                # Create timeout protection
                def timeout_cleanup():
                    cls._cleanup_timer(timer_id)
                    logger.warning(f"Timer {timer_id} timed out after {timeout_ms}ms")

                timeout_id = root.after(timeout_ms, timeout_cleanup)

                # Store timer information
                timer_info = {
                    'after_id': after_id,
                    'timeout_id': timeout_id,
                    'root': root,
                    'component_id': component_id,
                    'delay_ms': delay_ms,
                    'repeat': repeat,
                    'callback': callback,
                    'created_at': threading.get_ident(),
                    'creation_time': current_time,
                    'timeout_ms': timeout_ms
                }

                cls._active_timers[timer_id] = timer_info

                logger.debug(f"Created timer {timer_id} with {delay_ms}ms delay, component: {component_id}")
                return timer_id

            except Exception as e:
                logger.error(f"Failed to create timer: {e}")
                return None

    @classmethod
    def cancel_timer(cls, timer_id: str) -> bool:
        """
        Cancel a specific timer.

        Args:
            timer_id: Timer ID returned by create_timer

        Returns:
            True if timer was cancelled, False if not found
        """
        return cls._cleanup_timer(timer_id)

    @classmethod
    def cancel_component_timers(cls, component_id: str) -> int:
        """
        Cancel all timers for a specific component.

        Args:
            component_id: Component identifier

        Returns:
            Number of timers cancelled
        """
        with cls._timer_lock:
            timer_ids = [tid for tid, info in cls._active_timers.items()
                         if info.get('component_id') == component_id]

            cancelled = 0
            for timer_id in timer_ids:
                if cls._cleanup_timer(timer_id):
                    cancelled += 1

            logger.debug(f"Cancelled {cancelled} timers for component {component_id}")
            return cancelled

    @classmethod
    def cancel_all_timers(cls) -> int:
        """
        Cancel all active timers. Use with caution.

        Returns:
            Number of timers cancelled
        """
        with cls._timer_lock:
            timer_ids = list(cls._active_timers.keys())

            cancelled = 0
            for timer_id in timer_ids:
                if cls._cleanup_timer(timer_id):
                    cancelled += 1

            logger.debug(f"Cancelled all {cancelled} active timers")
            return cancelled

    @classmethod
    def get_active_timer_count(cls, component_id: Optional[str] = None) -> int:
        """
        Get count of active timers.

        Args:
            component_id: Optional component to filter by

        Returns:
            Number of active timers
        """
        with cls._timer_lock:
            if component_id:
                return sum(1 for info in cls._active_timers.values()
                           if info.get('component_id') == component_id)
            return len(cls._active_timers)

    @classmethod
    def _cleanup_timer(cls, timer_id: str) -> bool:
        """
        Internal method to cleanup a timer.

        Args:
            timer_id: Timer ID to cleanup

        Returns:
            True if timer was found and cleaned up
        """
        try:
            timer_info = cls._active_timers.pop(timer_id, None)
            if timer_info:
                # Cancel both the main timer and timeout timer
                try:
                    timer_info['root'].after_cancel(timer_info['after_id'])
                except BaseException:
                    pass  # Timer may have already fired

                try:
                    timer_info['root'].after_cancel(timer_info['timeout_id'])
                except BaseException:
                    pass  # Timeout may have already fired

                logger.debug(f"Cleaned up timer {timer_id}")
                return True
        except Exception as e:
            logger.error(f"Error cleaning up timer {timer_id}: {e}")

        return False

    @classmethod
    def detect_suspicious_activity(cls) -> bool:
        """
        Detect suspicious timer activity that might indicate an attack.

        Returns:
            True if suspicious activity detected
        """
        # Check for excessive suspicious activity count
        if cls._suspicious_activity_count > 10:
            logger.error(f"Excessive suspicious timer activity detected: {cls._suspicious_activity_count} incidents")
            return True

        # Check for too many timers from single component
        component_counts: dict[str, int] = {}
        for timer_info in cls._active_timers.values():
            component_id = timer_info.get('component_id', 'unknown')
            component_counts[component_id] = component_counts.get(component_id, 0) + 1

        for component_id, count in component_counts.items():
            if count > cls.MAX_TIMERS_PER_COMPONENT * 0.8:  # 80% of limit
                logger.warning(
                    f"Component {component_id} approaching timer limit: {count}/{cls.MAX_TIMERS_PER_COMPONENT}")
                return True

        return False

    @classmethod
    def emergency_cleanup(cls):
        """Emergency cleanup of all timers - use only in crisis situations."""
        with cls._timer_lock:
            logger.critical("Performing emergency timer cleanup")

            # Cancel all timers
            for timer_id in list(cls._active_timers.keys()):
                cls._cleanup_timer(timer_id)

            # Reset counters
            cls._creation_history.clear()
            cls._component_creation_count.clear()
            cls._suspicious_activity_count = 0

            logger.info("Emergency timer cleanup completed")

    @classmethod
    def get_stats(cls) -> Dict[str, Any]:
        """Get timer statistics for monitoring."""
        with cls._timer_lock:
            component_counts: dict[str, int] = {}
            for timer_info in cls._active_timers.values():
                component_id = timer_info.get('component_id', 'unknown')
                component_counts[component_id] = component_counts.get(component_id, 0) + 1

            return {
                'total_timers': len(cls._active_timers),
                'component_counts': component_counts,
                'max_total_timers': cls.MAX_TOTAL_TIMERS,
                'max_per_component': cls.MAX_TIMERS_PER_COMPONENT,
                'suspicious_activity_count': cls._suspicious_activity_count,
                'recent_creation_count': len(cls._creation_history),
                'suspicious_activity_detected': cls.detect_suspicious_activity()
            }

    @classmethod
    @contextmanager
    def component_context(cls, component_id: str):
        """
        Context manager that automatically cleans up component timers.

        Args:
            component_id: Component identifier
        """
        try:
            yield component_id
        finally:
            cls.cancel_component_timers(component_id)


# Convenience functions for common timer patterns
def create_delayed_callback(root: tk.Widget, delay_ms: int, callback: Callable,
                            component_id: Optional[str] = None) -> Optional[str]:
    """Create a one-time delayed callback."""
    return TimerResourceManager.create_timer(root, delay_ms, callback, component_id)


def create_repeating_timer(root: tk.Widget, interval_ms: int, callback: Callable,
                           component_id: Optional[str] = None, max_lifetime_ms: Optional[int] = None) -> Optional[str]:
    """Create a repeating timer with automatic cleanup."""
    return TimerResourceManager.create_timer(
        root, interval_ms, callback, component_id,
        timeout_ms=max_lifetime_ms, repeat=True
    )


def create_autosave_timer(root: tk.Widget, save_callback: Callable,
                          component_id: Optional[str] = None, delay_ms: int = 1000) -> Optional[str]:
    """Create an autosave timer with standard delay."""
    return create_delayed_callback(root, delay_ms, save_callback, component_id)


@contextmanager
def managed_component(component_id: str):
    """Context manager for component-level timer management."""
    with TimerResourceManager.component_context(component_id):
        yield component_id
