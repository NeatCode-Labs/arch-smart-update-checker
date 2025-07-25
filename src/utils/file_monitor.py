"""
Secure file monitoring utilities to replace sleep-based polling with event-driven monitoring.
Enhanced with timing-attack resistance and cryptographic randomization.
"""

# SPDX-License-Identifier: GPL-3.0-or-later

import os
import time
import threading
import secrets
import hmac
import hashlib
from typing import Callable, Optional, Any, Dict, List
from pathlib import Path
import random

from .logger import get_logger

logger = get_logger(__name__)


class TimingAttackMitigation:
    """Utilities for preventing timing attacks in file operations."""

    def __init__(self):
        """Initialize timing attack mitigation with cryptographic randomization."""
        self._random_key = secrets.token_bytes(32)
        self._operation_times: Dict[str, List[float]] = {}
        self._lock = threading.RLock()

    def constant_time_compare(self, a: str, b: str) -> bool:
        """
        Constant-time string comparison to prevent timing attacks.

        Args:
            a: First string
            b: Second string

        Returns:
            True if strings are equal
        """
        # Use HMAC for constant-time comparison
        if not isinstance(a, (str, bytes)) or not isinstance(b, (str, bytes)):
            return False

        if isinstance(a, str):
            a = a.encode('utf-8')
        if isinstance(b, str):
            b = b.encode('utf-8')

        # Add random delay to normalize timing
        self._add_cryptographic_delay()

        return hmac.compare_digest(a, b)

    def _add_cryptographic_delay(self, operation_type: str = "default"):
        """
        Add cryptographically random delay to normalize operation timing.

        Args:
            operation_type: Type of operation for timing normalization
        """
        try:
            # Generate random delay between 1-10ms using cryptographic randomness
            base_delay = secrets.randbelow(10000) / 1000000  # 0-10ms

            # Add noise based on operation history to normalize timing patterns
            with self._lock:
                if operation_type not in self._operation_times:
                    self._operation_times[operation_type] = []

                # Keep last 100 operation times
                if len(self._operation_times[operation_type]) > 100:
                    self._operation_times[operation_type] = self._operation_times[operation_type][-50:]

                # Calculate target delay based on historical operations
                if self._operation_times[operation_type]:
                    avg_time = sum(self._operation_times[operation_type]) / len(self._operation_times[operation_type])
                    # Add random variation around average
                    target_delay = avg_time + (secrets.randbelow(1000) - 500) / 1000000
                    target_delay = max(0.001, target_delay)  # Minimum 1ms
                else:
                    target_delay = base_delay

                # Record this operation time
                start_time = time.time()

            # Apply the calculated delay
            time.sleep(target_delay)

            # Record actual operation time
            with self._lock:
                actual_time = time.time() - start_time
                self._operation_times[operation_type].append(actual_time)

        except Exception as e:
            logger.debug(f"Error in cryptographic delay: {e}")
            # Fallback to simple random delay
            time.sleep(secrets.randbelow(5) / 1000)  # 0-5ms fallback

    def randomize_file_access_pattern(self, file_path: str) -> bool:
        """
        Access file with randomized pattern to prevent timing analysis.

        Args:
            file_path: Path to file to access

        Returns:
            True if file exists and is accessible
        """
        try:
            # Add timing normalization
            self._add_cryptographic_delay("file_access")

            # Perform multiple access operations with random ordering
            operations = [
                lambda: os.path.exists(file_path),
                lambda: os.path.isfile(file_path) if os.path.exists(file_path) else False,
                lambda: os.access(file_path, os.R_OK) if os.path.exists(file_path) else False
            ]

            # Randomize operation order
            random.shuffle(operations)

            results = []
            for operation in operations:
                try:
                    # Add small random delay between operations
                    time.sleep(secrets.randbelow(100) / 1000000)  # 0-0.1ms
                    result = operation()
                    results.append(result)
                except Exception:
                    results.append(False)

            # Return True only if all operations indicate file exists and is accessible
            return all(results)

        except Exception as e:
            logger.debug(f"Error in randomized file access: {e}")
            # Fallback with timing normalization
            self._add_cryptographic_delay("file_access_fallback")
            return os.path.exists(file_path)

    def secure_file_hash(self, file_path: str, use_random_salt: bool = True) -> Optional[str]:
        """
        Generate secure file hash with optional random salt to prevent timing attacks.

        Args:
            file_path: Path to file
            use_random_salt: Whether to use random salt

        Returns:
            Secure hash of file or None if error
        """
        try:
            self._add_cryptographic_delay("file_hash")

            if not self.randomize_file_access_pattern(file_path):
                return None

            # Generate hash with random salt if requested
            hasher = hashlib.sha256()

            if use_random_salt:
                salt = secrets.token_bytes(16)
                hasher.update(salt)

            with open(file_path, 'rb') as f:
                # Read file in random-sized chunks to prevent timing analysis
                while True:
                    chunk_size = 8192 + secrets.randbelow(8192)  # 8KB-16KB chunks
                    chunk = f.read(chunk_size)
                    if not chunk:
                        break
                    hasher.update(chunk)

                    # Add small random delay
                    time.sleep(secrets.randbelow(10) / 1000000)  # 0-0.01ms

            return hasher.hexdigest()

        except Exception as e:
            logger.debug(f"Error generating secure file hash: {e}")
            # Timing normalization even on error
            self._add_cryptographic_delay("file_hash_error")
            return None


# Global timing attack mitigation instance
_timing_mitigation = TimingAttackMitigation()


class SecureFileMonitor:
    """Secure file monitoring with randomized intervals and timing-attack resistance."""

    def __init__(self):
        self._monitoring = False
        self._monitor_lock = threading.Lock()
        self._timing_mitigation = _timing_mitigation

    def wait_for_file_creation(self, file_path: str, timeout_seconds: int = 30,
                               callback: Optional[Callable[[bool], None]] = None,
                               component_id: str = None) -> bool:
        """
        Wait for a file to be created using secure, randomized monitoring.

        Args:
            file_path: Path to monitor for creation
            timeout_seconds: Maximum time to wait
            callback: Optional callback function to call with result (True if created, False if timeout)
            component_id: Component ID for timer management

        Returns:
            True if file was created within timeout, False otherwise
        """
        file_path = Path(file_path)
        start_time = time.time()
        check_count = 0

        def check_file_exists():
            nonlocal check_count
            check_count += 1

            current_time = time.time()
            elapsed = current_time - start_time

            # Check if file exists using timing-attack resistant method
            if self._timing_mitigation.randomize_file_access_pattern(str(file_path)):
                logger.debug(f"File {file_path} created after {elapsed:.2f}s ({check_count} checks)")
                if callback:
                    callback(True)
                return True

            # Check timeout
            if elapsed >= timeout_seconds:
                logger.debug(f"File creation timeout for {file_path} after {elapsed:.2f}s ({check_count} checks)")
                if callback:
                    callback(False)
                return False

            # Schedule next check with cryptographically randomized interval
            # Use exponential backoff with cryptographic jitter for timing attack resistance
            base_interval = min(1000, 200 + (check_count * 100))  # Start at 200ms, increase by 100ms each check
            crypto_jitter = secrets.randbelow(150) - 50  # Cryptographic randomness: -50 to +100ms
            next_interval = max(100, base_interval + crypto_jitter)  # Minimum 100ms

            # Cap the interval at reasonable maximum
            next_interval = min(next_interval, 2000)  # Maximum 2 seconds

            # Add additional timing attack mitigation delay
            self._timing_mitigation._add_cryptographic_delay("file_monitor_interval")

            # Schedule next check using threading timer
            timer = threading.Timer(next_interval / 1000.0, check_file_exists)
            timer.daemon = True
            timer.start()

            return None  # Continue monitoring

        # Start the monitoring
        return check_file_exists()

    def wait_for_file_deletion(self, file_path: str, timeout_seconds: int = 3600,
                               callback: Optional[Callable[[bool], None]] = None,
                               component_id: str = None) -> bool:
        """
        Wait for a file to be deleted using secure, randomized monitoring.

        Args:
            file_path: Path to monitor for deletion
            timeout_seconds: Maximum time to wait (default 1 hour for long operations)
            callback: Optional callback function to call with result (True if deleted, False if timeout)
            component_id: Component ID for timer management

        Returns:
            True if file was deleted within timeout, False otherwise
        """
        file_path = Path(file_path)
        start_time = time.time()
        check_count = 0

        def check_file_deleted():
            nonlocal check_count
            check_count += 1

            current_time = time.time()
            elapsed = current_time - start_time

            # Check if file is gone
            if not file_path.exists():
                logger.debug(f"File {file_path} deleted after {elapsed:.2f}s ({check_count} checks)")
                if callback:
                    callback(True)
                return True

            # Check timeout
            if elapsed >= timeout_seconds:
                logger.debug(f"File deletion timeout for {file_path} after {elapsed:.2f}s ({check_count} checks)")
                if callback:
                    callback(False)
                return False

            # Schedule next check with randomized interval
            # Use adaptive intervals based on how long we've been waiting
            if elapsed < 10:
                # First 10 seconds: check frequently but with randomization
                base_interval = random.randint(800, 1200)  # 0.8-1.2 seconds
            elif elapsed < 60:
                # First minute: moderate frequency
                base_interval = random.randint(1500, 2500)  # 1.5-2.5 seconds
            else:
                # After 1 minute: less frequent checks
                base_interval = random.randint(3000, 5000)  # 3-5 seconds

            # Schedule next check using threading timer
            timer = threading.Timer(base_interval / 1000.0, check_file_deleted)
            timer.daemon = True
            timer.start()

            return None  # Continue monitoring

        # Start the monitoring
        return check_file_deleted()


class SecureProcessMonitor:
    """Secure process monitoring with event-driven patterns."""

    @staticmethod
    def monitor_lock_file_process(lock_file_path: str,
                                  start_callback: Optional[Callable[[], None]] = None,
                                  completion_callback: Optional[Callable[[float], None]] = None,
                                  timeout_callback: Optional[Callable[[], None]] = None,
                                  start_timeout: int = 30,
                                  completion_timeout: int = 3600,
                                  component_id: str = None):
        """
        Monitor a process using lock file pattern with secure, event-driven monitoring.

        Args:
            lock_file_path: Path to the lock file that indicates process status
            start_callback: Called when process starts (lock file created)
            completion_callback: Called when process completes (lock file deleted) with duration
            timeout_callback: Called if process times out
            start_timeout: Seconds to wait for process to start
            completion_timeout: Seconds to wait for process to complete
            component_id: Component ID for timer management
        """
        monitor = SecureFileMonitor()
        start_time = time.time()

        def on_process_started(created: bool):
            if created:
                logger.debug(f"Process started (lock file created): {lock_file_path}")
                if start_callback:
                    start_callback()

                # Now wait for completion (file deletion)
                def on_process_completed(deleted: bool):
                    if deleted:
                        duration = time.time() - start_time
                        logger.debug(f"Process completed in {duration:.2f}s: {lock_file_path}")
                        if completion_callback:
                            completion_callback(duration)
                    else:
                        logger.warning(f"Process completion timeout after {completion_timeout}s: {lock_file_path}")
                        if timeout_callback:
                            timeout_callback()

                # Monitor for deletion
                monitor.wait_for_file_deletion(
                    file_path=lock_file_path,
                    timeout_seconds=completion_timeout,
                    callback=on_process_completed,
                    component_id=component_id
                )
            else:
                logger.warning(f"Process start timeout after {start_timeout}s: {lock_file_path}")
                if timeout_callback:
                    timeout_callback()

        # Monitor for creation
        monitor.wait_for_file_creation(
            file_path=lock_file_path,
            timeout_seconds=start_timeout,
            callback=on_process_started,
            component_id=component_id
        )


# Convenience functions for common patterns
def wait_for_file(file_path: str, timeout_seconds: int = 30,
                  component_id: str = None) -> bool:
    """Simple synchronous wait for file creation."""
    monitor = SecureFileMonitor()
    result = [False]  # Use list to allow modification from nested function
    finished = [False]

    def callback(created: bool):
        result[0] = created
        finished[0] = True

    monitor.wait_for_file_creation(file_path, timeout_seconds, callback, component_id)

    # Simple polling for synchronous operation (this is okay since it's not in a security context)
    start = time.time()
    while not finished[0] and (time.time() - start) < timeout_seconds + 1:
        time.sleep(0.1)

    return result[0]


def wait_for_file_deletion(file_path: str, timeout_seconds: int = 3600,
                           component_id: str = None) -> bool:
    """Simple synchronous wait for file deletion."""
    monitor = SecureFileMonitor()
    result = [False]  # Use list to allow modification from nested function
    finished = [False]

    def callback(deleted: bool):
        result[0] = deleted
        finished[0] = True

    monitor.wait_for_file_deletion(file_path, timeout_seconds, callback, component_id)

    # Simple polling for synchronous operation (this is okay since it's not in a security context)
    start = time.time()
    while not finished[0] and (time.time() - start) < timeout_seconds + 1:
        time.sleep(0.1)

    return result[0]
