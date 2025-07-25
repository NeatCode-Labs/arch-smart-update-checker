"""
Thread resource management for secure application-wide thread control with enhanced security.
"""

# SPDX-License-Identifier: GPL-3.0-or-later

import threading
import time
import os
import psutil
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Optional, Callable, Any, Dict, List, Set
from contextlib import contextmanager
from collections import deque, defaultdict

from .logger import get_logger

logger = get_logger(__name__)


class ThreadResourceError(Exception):
    """Raised when thread resource limits are exceeded."""
    pass


class ThreadSecurityMonitor:
    """Monitor thread security and resource usage."""

    def __init__(self):
        self.creation_times = deque(maxlen=100)  # Track recent thread creations
        self.failure_count = 0
        self.last_failure_time = 0
        self.suspicious_patterns = []

    def record_thread_creation(self, thread_id: str, is_background: bool) -> None:
        """Record a thread creation event."""
        current_time = time.time()
        self.creation_times.append((current_time, thread_id, is_background))

        # Check for suspicious creation patterns
        self._check_creation_rate()

    def record_thread_failure(self, reason: str) -> None:
        """Record a thread creation failure."""
        self.failure_count += 1
        self.last_failure_time = time.time()

        # Check for potential DoS patterns
        if self.failure_count > 10:
            logger.warning(f"High thread creation failure rate: {self.failure_count} failures")

    def _check_creation_rate(self) -> None:
        """Check if thread creation rate is suspicious."""
        current_time = time.time()
        recent_creations = [t for t, _, _ in self.creation_times if current_time - t < 10]

        if len(recent_creations) > 15:  # More than 15 threads in 10 seconds
            logger.warning(f"High thread creation rate detected: {len(recent_creations)} threads in 10 seconds")
            self.suspicious_patterns.append(('high_creation_rate', current_time))

    def is_suspicious_activity(self) -> bool:
        """Check if there's suspicious thread activity."""
        current_time = time.time()

        # Check recent suspicious patterns
        recent_patterns = [p for p in self.suspicious_patterns if current_time - p[1] < 60]

        return len(recent_patterns) > 0


class ThreadResourceManager:
    """
    Enhanced thread resource manager with security monitoring and intelligent limits.
    Provides secure, monitored thread creation with resource constraints and leak prevention.
    """

    # Enhanced resource limits for desktop application with startup considerations
    MAX_TOTAL_THREADS = 30        # Increased from 15 for desktop app needs
    MAX_BACKGROUND_THREADS = 20   # Increased from 8 for concurrent operations
    MAX_CONCURRENT_OPERATIONS = 8  # Increased from 3 for better performance
    MAX_THREADS_PER_COMPONENT = 10  # Increased from 5 for complex components
    THREAD_TIMEOUT_SECONDS = 180  # Reduced timeout (3 minutes)
    MAX_THREAD_MEMORY_MB = 100    # Memory limit per thread (increased for package operations)

    # Security thresholds with startup considerations
    MAX_CPU_PERCENT = 80          # Maximum CPU usage before blocking
    MAX_MEMORY_PERCENT = 85       # Maximum memory usage before blocking
    CLEANUP_INTERVAL = 30         # More frequent cleanup
    STARTUP_GRACE_PERIOD = 30     # Seconds to be more lenient after app start

    # Class-level tracking with enhanced monitoring
    _active_threads = 0
    _background_threads = 0
    _component_threads: Dict[str, int] = defaultdict(int)
    _thread_lock = threading.RLock()  # Reentrant lock for nested calls
    _thread_registry: Dict[str, Dict[str, Any]] = {}
    _thread_start_times: Dict[str, float] = {}
    _thread_memory_usage: Dict[str, float] = {}
    _last_cleanup = time.time()
    _security_monitor = ThreadSecurityMonitor()
    _blocked_components: Set[str] = set()
    _startup_time = time.time()  # Track when the thread manager was initialized

    @classmethod
    def can_create_thread(cls, is_background: bool = False, component_id: str = None) -> bool:
        """
        Enhanced thread creation validation with security checks.
        More lenient during startup grace period.

        Args:
            is_background: Whether this is a background/daemon thread
            component_id: Component identifier for tracking

        Returns:
            True if thread creation is allowed
        """
        with cls._thread_lock:
            # Always perform cleanup before checking limits
            cls._cleanup_dead_threads()

            # Check if we're in startup grace period for better user experience
            startup_grace_active = (time.time() - cls._startup_time) < cls.STARTUP_GRACE_PERIOD
            if startup_grace_active:
                logger.debug(f"Thread creation during startup grace period for {component_id or 'unknown'}")

            # Check system resource limits with context
            if not cls._check_system_resources(component_id):
                if startup_grace_active:
                    logger.info("Thread creation denied during startup - system under heavy load")
                else:
                    logger.warning("Thread creation denied: system resources exhausted")
                cls._security_monitor.record_thread_failure("system_resources")
                return False

            # Check for suspicious activity
            if cls._security_monitor.is_suspicious_activity():
                logger.warning("Thread creation denied: suspicious activity detected")
                cls._security_monitor.record_thread_failure("suspicious_activity")
                return False

            # Check total thread limit
            if cls._active_threads >= cls.MAX_TOTAL_THREADS:
                logger.warning(f"Thread creation denied: reached max total threads ({cls.MAX_TOTAL_THREADS})")
                logger.warning(f"Active threads: {cls._active_threads}, Registry size: {len(cls._thread_registry)}")
                logger.warning(f"Component breakdown: {dict(cls._component_threads)}")
                cls._security_monitor.record_thread_failure("total_limit")
                return False

            # Check background thread limit
            if is_background and cls._background_threads >= cls.MAX_BACKGROUND_THREADS:
                logger.warning(
                    f"Background thread creation denied: reached max background threads ({
                        cls.MAX_BACKGROUND_THREADS})")
                cls._security_monitor.record_thread_failure("background_limit")
                return False

            # Check component-specific limits
            if component_id:
                if component_id in cls._blocked_components:
                    logger.warning(f"Thread creation denied: component {component_id} is blocked")
                    cls._security_monitor.record_thread_failure("component_blocked")
                    return False

                if cls._component_threads[component_id] >= cls.MAX_THREADS_PER_COMPONENT:
                    logger.warning(
                        f"Thread creation denied: component {component_id} reached limit ({
                            cls.MAX_THREADS_PER_COMPONENT})")
                    cls._security_monitor.record_thread_failure("component_limit")
                    return False

            return True

    @classmethod
    def _check_system_resources(cls, component_id: str = None) -> bool:
        """
        Check if system has sufficient resources for thread creation.
        More lenient during startup grace period.

        Args:
            component_id: Component requesting thread creation

        Returns:
            True if system resources are available
        """
        try:
            # Check if we're in startup grace period
            startup_grace_active = (time.time() - cls._startup_time) < cls.STARTUP_GRACE_PERIOD

            # Check CPU usage with context awareness
            cpu_percent = psutil.cpu_percent(interval=0.1)

            # Be more lenient for legitimate update operations and during startup
            cpu_threshold = cls.MAX_CPU_PERCENT
            if startup_grace_active:
                # During startup, allow higher CPU usage
                cpu_threshold = min(95, cls.MAX_CPU_PERCENT + 15)
                logger.debug(f"Startup grace period active, using higher CPU threshold: {cpu_threshold}%")
            elif component_id and 'check_thread' in str(component_id):
                # Allow higher CPU usage for update checking operations
                cpu_threshold = min(95, cls.MAX_CPU_PERCENT + 15)  # Up to 95% for update checks

            if cpu_percent > cpu_threshold:
                if startup_grace_active:
                    logger.info(f"High CPU usage during startup ({cpu_percent}%), but within grace period")
                else:
                    logger.warning(f"High CPU usage: {cpu_percent}%")
                    # For update operations, only block if extremely high
                    if component_id and 'check_thread' in str(component_id) and cpu_percent < 98:
                        logger.info(f"Allowing update check thread despite high CPU ({cpu_percent}%)")
                        # Continue to memory check
                    else:
                        return False

            # Check memory usage (always enforce memory limits)
            memory = psutil.virtual_memory()
            if memory.percent > cls.MAX_MEMORY_PERCENT:
                logger.warning(f"High memory usage: {memory.percent}%")
                return False

            # Check available file descriptors (Unix only)
            if hasattr(os, 'getrlimit'):
                import resource
                soft_limit, hard_limit = resource.getrlimit(resource.RLIMIT_NOFILE)
                # Estimate current usage (rough approximation)
                if soft_limit > 0 and cls._active_threads > soft_limit * 0.8:
                    logger.warning("Approaching file descriptor limit")
                    return False

            return True

        except Exception as e:
            logger.warning(f"Error checking system resources: {e}")
            return True  # Allow on error, but log it

    @classmethod
    def register_thread(cls, thread_id: str, thread: threading.Thread,
                        is_background: bool = False, component_id: str = None):
        """
        Register a new thread with enhanced monitoring.

        Args:
            thread_id: Unique thread identifier
            thread: Thread object
            is_background: Whether this is a background thread
            component_id: Component identifier
        """
        with cls._thread_lock:
            current_time = time.time()

            # Store comprehensive thread information
            cls._thread_registry[thread_id] = {
                'thread': thread,
                'is_background': is_background,
                'component_id': component_id,
                'start_time': current_time,
                'cpu_time': 0.0,
                'memory_usage': 0.0,
                'alive': True,
            }

            cls._thread_start_times[thread_id] = current_time
            cls._active_threads += 1

            if is_background:
                cls._background_threads += 1

            if component_id:
                cls._component_threads[component_id] += 1

            # Record creation for security monitoring
            cls._security_monitor.record_thread_creation(thread_id, is_background)

            logger.debug(f"Registered thread {thread_id} (total: {cls._active_threads})")

    @classmethod
    def unregister_thread(cls, thread_id: str):
        """
        Unregister a thread and update counters.

        Args:
            thread_id: Thread identifier to unregister
        """
        with cls._thread_lock:
            if thread_id in cls._thread_registry:
                thread_info = cls._thread_registry[thread_id]

                cls._active_threads -= 1

                if thread_info['is_background']:
                    cls._background_threads -= 1

                component_id = thread_info.get('component_id')
                if component_id and cls._component_threads[component_id] > 0:
                    cls._component_threads[component_id] -= 1

                # Calculate runtime for monitoring
                start_time = cls._thread_start_times.get(thread_id, time.time())
                runtime = time.time() - start_time

                if runtime > cls.THREAD_TIMEOUT_SECONDS:
                    logger.warning(
                        f"Thread {thread_id} ran for {
                            runtime:.1f}s (timeout: {
                            cls.THREAD_TIMEOUT_SECONDS}s)")

                # Clean up tracking data
                del cls._thread_registry[thread_id]
                cls._thread_start_times.pop(thread_id, None)
                cls._thread_memory_usage.pop(thread_id, None)

                logger.debug(f"Unregistered thread {thread_id} (total: {cls._active_threads})")

    @classmethod
    def create_managed_thread(cls, thread_id: str, target: Callable,
                              args: tuple = (), kwargs: dict = None,
                              is_background: bool = False, component_id: str = None) -> Optional[threading.Thread]:
        """
        Create a managed thread with comprehensive security controls.

        Args:
            thread_id: Unique thread identifier
            target: Target function
            args: Function arguments
            kwargs: Function keyword arguments
            is_background: Whether this is a background thread
            component_id: Component identifier

        Returns:
            Thread object or None if creation denied
        """
        if kwargs is None:
            kwargs = {}

        # Check if thread creation is allowed
        if not cls.can_create_thread(is_background, component_id):
            return None

        def wrapped_target():
            """Wrapped target function with monitoring and cleanup."""
            thread_start_time = time.time()

            try:
                # Monitor thread resource usage
                cls._monitor_thread_resources(thread_id)

                # Execute the actual target function
                result = target(*args, **kwargs)

                logger.debug(f"Thread {thread_id} completed successfully")
                return result

            except Exception as e:
                logger.error(f"Thread {thread_id} failed: {e}")
                raise
            finally:
                # Clean up and unregister
                runtime = time.time() - thread_start_time
                logger.debug(f"Thread {thread_id} runtime: {runtime:.2f}s")
                cls.unregister_thread(thread_id)

        try:
            # Create the thread
            thread = threading.Thread(
                target=wrapped_target,
                name=f"managed_{thread_id}",
                daemon=is_background
            )

            # Register before starting
            cls.register_thread(thread_id, thread, is_background, component_id)

            return thread

        except Exception as e:
            logger.error(f"Failed to create thread {thread_id}: {e}")
            cls._security_monitor.record_thread_failure("creation_error")
            return None

    @classmethod
    def _monitor_thread_resources(cls, thread_id: str):
        """
        Monitor resource usage of a specific thread.

        Args:
            thread_id: Thread to monitor
        """
        try:
            import psutil
            current_process = psutil.Process()

            # Get thread-specific resource usage if available
            # thread_info = cls._thread_registry.get(thread_id, {})  # Reserved for future use

            # Monitor memory usage (approximate)
            memory_mb = current_process.memory_info().rss / 1024 / 1024
            cls._thread_memory_usage[thread_id] = memory_mb

            # Check if thread is using too much memory
            if memory_mb > cls.MAX_THREAD_MEMORY_MB:
                logger.warning(f"Thread {thread_id} using high memory: {memory_mb:.1f}MB")

        except Exception as e:
            logger.debug(f"Error monitoring thread {thread_id}: {e}")

    @classmethod
    def _cleanup_if_needed(cls):
        """Perform cleanup of dead threads if needed."""
        current_time = time.time()

        if current_time - cls._last_cleanup < cls.CLEANUP_INTERVAL:
            return

        cls._last_cleanup = current_time
        cls._cleanup_dead_threads()

    @classmethod
    def _cleanup_dead_threads(cls):
        """Clean up dead or timed-out threads."""
        current_time = time.time()
        dead_threads = []

        for thread_id, thread_info in list(cls._thread_registry.items()):
            thread = thread_info['thread']
            start_time = thread_info['start_time']

            # Check if thread is dead
            if not thread.is_alive():
                dead_threads.append(thread_id)
                continue

                # Check for timeout
                runtime = current_time - start_time
                if runtime > cls.THREAD_TIMEOUT_SECONDS:
                    logger.warning(f"Thread {thread_id} timed out after {runtime:.1f}s")
                    dead_threads.append(thread_id)

                    # Try to interrupt long-running threads (limited capability in Python)
                    try:
                        # Note: Python doesn't support thread interruption, but we can log it
                        logger.warning(f"Long-running thread {thread_id} should be manually stopped")
                    except Exception as e:
                        logger.debug(f"Error handling timeout for thread {thread_id}: {e}")

        # Clean up dead threads
        for thread_id in dead_threads:
            cls.unregister_thread(thread_id)

        if dead_threads:
            logger.debug(f"Cleaned up {len(dead_threads)} dead threads")

    @classmethod
    def get_thread_stats(cls) -> Dict[str, Any]:
        """
        Get comprehensive thread statistics.

        Returns:
            Dictionary with thread statistics
        """
        with cls._thread_lock:
            stats = {
                'total_active': cls._active_threads,
                'background': cls._background_threads,
                'foreground': cls._active_threads - cls._background_threads,
                'component_breakdown': dict(cls._component_threads),
                'registry_size': len(cls._thread_registry),
                'max_total_limit': cls.MAX_TOTAL_THREADS,
                'max_background_limit': cls.MAX_BACKGROUND_THREADS,
                'blocked_components': list(cls._blocked_components),
                'suspicious_activity': cls._security_monitor.is_suspicious_activity(),
                'failure_count': cls._security_monitor.failure_count,
            }

            # Add system resource info
            try:
                stats['cpu_percent'] = psutil.cpu_percent(interval=0.1)
                stats['memory_percent'] = psutil.virtual_memory().percent
            except Exception:
                pass

            return stats

    @classmethod
    def block_component(cls, component_id: str, reason: str = "security"):
        """
        Block a component from creating new threads.

        Args:
            component_id: Component to block
            reason: Reason for blocking
        """
        with cls._thread_lock:
            cls._blocked_components.add(component_id)
            logger.warning(f"Blocked component {component_id} from creating threads: {reason}")

    @classmethod
    def unblock_component(cls, component_id: str):
        """
        Unblock a component.

        Args:
            component_id: Component to unblock
        """
        with cls._thread_lock:
            cls._blocked_components.discard(component_id)
            logger.info(f"Unblocked component {component_id}")

    @classmethod
    def emergency_shutdown(cls):
        """Emergency shutdown of all managed threads."""
        logger.critical("Emergency thread shutdown initiated")

        with cls._thread_lock:
            # Mark all components as blocked
            for component_id in cls._component_threads:
                cls._blocked_components.add(component_id)

            # Try to clean up threads gracefully
            cls._cleanup_dead_threads()

            # Log final state
            logger.critical(f"Emergency shutdown complete. Remaining threads: {cls._active_threads}")


def create_managed_thread(thread_id: str, target: Callable,
                          args: tuple = (), kwargs: dict = None,
                          is_background: bool = False, component_id: str = None) -> Optional[threading.Thread]:
    """
    Convenience function to create a managed thread.

    Args:
        thread_id: Unique thread identifier
        target: Target function
        args: Function arguments
        kwargs: Function keyword arguments
        is_background: Whether this is a background thread
        component_id: Component identifier

    Returns:
        Thread object or None if creation denied
    """
    return ThreadResourceManager.create_managed_thread(
        thread_id, target, args, kwargs, is_background, component_id
    )


class SecureThreadPoolExecutor:
    """Secure thread pool executor with resource limits."""

    _executors: Dict[str, ThreadPoolExecutor] = {}
    _executor_lock = threading.Lock()

    @classmethod
    def get_executor(cls, max_workers: int = 3, pool_id: str = "default") -> ThreadPoolExecutor:
        """
        Get a managed thread pool executor.

        Args:
            max_workers: Maximum number of worker threads
            pool_id: Pool identifier

        Returns:
            ThreadPoolExecutor instance
        """
        # Enforce maximum worker limits
        max_workers = min(max_workers, ThreadResourceManager.MAX_CONCURRENT_OPERATIONS)

        with cls._executor_lock:
            if pool_id not in cls._executors:
                cls._executors[pool_id] = ThreadPoolExecutor(
                    max_workers=max_workers,
                    thread_name_prefix=f"pool_{pool_id}"
                )
                logger.debug(f"Created thread pool {pool_id} with {max_workers} workers")

            return cls._executors[pool_id]

    @classmethod
    def shutdown_all(cls):
        """Shutdown all thread pool executors."""
        with cls._executor_lock:
            for pool_id, executor in cls._executors.items():
                try:
                    executor.shutdown(wait=True, timeout=30)
                    logger.debug(f"Shutdown thread pool {pool_id}")
                except Exception as e:
                    logger.error(f"Error shutting down pool {pool_id}: {e}")

            cls._executors.clear()
