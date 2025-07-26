"""
Instance locking mechanism to prevent multiple instances of the application.

This module provides a secure, cross-process lock to ensure only one instance
of the Arch Smart Update Checker can run at a time, preventing race conditions
and security vulnerabilities from concurrent operations.
"""

# SPDX-License-Identifier: GPL-3.0-or-later

import os
import sys
import fcntl
import signal
import psutil  # type: ignore[import-untyped]
import time
import json
import hashlib
from pathlib import Path
from typing import Optional, Union, Dict, Any, TextIO
from contextlib import contextmanager

from .logger import get_logger, log_security_event

logger = get_logger(__name__)

# Security constants
MAX_LOCK_AGE_SECONDS = 86400  # 24 hours - auto-cleanup very old locks
LOCK_FILE_VERSION = "1.0"


class InstanceLockError(Exception):
    """Raised when instance lock operations fail."""
    pass


class InstanceAlreadyRunningError(InstanceLockError):
    """Raised when another instance is already running."""
    pass


class InstanceLock:
    """
    File-based instance lock to prevent multiple instances.

    Uses fcntl for atomic, cross-process locking on Linux/Unix systems.
    Handles stale locks from crashed processes automatically.
    """

    def __init__(self, app_name: str = "arch-smart-update-checker",
                 mode: str = "gui",
                 lock_dir: Optional[str] = None):
        """
        Initialize instance lock.

        Args:
            app_name: Application name for lock file
            mode: Application mode ('gui' or 'cli')
            lock_dir: Directory for lock files (defaults to /tmp)
        """
        self.app_name = app_name
        self.mode = mode
        self.lock_file_path = self._get_lock_file_path(lock_dir)
        self.lock_file: Optional[TextIO] = None
        self.lock_fd: Optional[int] = None
        self.locked = False
        self.pid = os.getpid()

        logger.debug(f"Initialized instance lock for {app_name} ({mode}) at {self.lock_file_path}")

    def _get_lock_file_path(self, lock_dir: Optional[Union[str, Path]] = None) -> Path:
        """
        Get the lock file path with proper permissions.

        Args:
            lock_dir: Directory for lock files

        Returns:
            Path to lock file
        """
        if lock_dir is None:
            # Use /var/run if available and writable, otherwise /tmp
            var_run = Path("/var/run/user") / str(os.getuid())
            if var_run.exists() and os.access(var_run, os.W_OK):
                lock_dir = var_run
            else:
                lock_dir = Path("/tmp")
        else:
            lock_dir = Path(lock_dir)

        # Create directory if it doesn't exist
        try:
            lock_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
        except Exception as e:
            logger.debug(f"Could not create lock directory {lock_dir}: {e}")
            lock_dir = Path("/tmp")

        # Lock file name includes app name and mode
        lock_file_name = f".{self.app_name}-{self.mode}.lock"
        return lock_dir / lock_file_name

    def acquire(self, timeout: float = 0.0, check_stale: bool = True) -> bool:
        """
        Acquire the instance lock.

        Args:
            timeout: Maximum time to wait for lock (0 = non-blocking)
            check_stale: Whether to check for and clean stale locks

        Returns:
            True if lock acquired, False otherwise

        Raises:
            InstanceAlreadyRunningError: If another instance is running
            InstanceLockError: If lock operation fails
        """
        if self.locked:
            return True

        try:
            # Try atomic file creation with secure permissions
            try:
                self.lock_fd = os.open(
                    str(self.lock_file_path),
                    os.O_CREAT | os.O_WRONLY | os.O_EXCL,
                    0o600
                )
                self.lock_file = os.fdopen(self.lock_fd, 'w')
                newly_created = True
            except FileExistsError:
                # File exists, open it normally
                self.lock_file = open(self.lock_file_path, 'r+')
                self.lock_fd = self.lock_file.fileno()
                newly_created = False

                # Ensure permissions are correct even for existing file
                try:
                    os.chmod(self.lock_file_path, 0o600)
                except BaseException:
                    pass

            # Try to acquire exclusive lock
            start_time = time.time()
            while True:
                try:
                    if self.lock_fd is None:
                        raise InstanceLockError("Lock file descriptor is None")
                    fcntl.flock(self.lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    break
                except BlockingIOError:
                    if timeout <= 0 or (time.time() - start_time) >= timeout:
                        # Check if the holding process is still alive
                        if check_stale and not newly_created and self._check_and_clean_stale_lock():
                            # Stale lock was cleaned, retry
                            self._close_lock_file()
                            return self.acquire(timeout=timeout, check_stale=False)

                        self._close_lock_file()
                        existing_pid = self._get_existing_pid()
                        log_security_event(
                            "MULTIPLE_INSTANCE_ATTEMPT",
                            {
                                "app_name": self.app_name,
                                "mode": self.mode,
                                "existing_pid": existing_pid,
                                "current_pid": self.pid
                            },
                            severity="warning"
                        )
                        raise InstanceAlreadyRunningError(
                            f"Another instance of {self.app_name} ({self.mode}) is already running "
                            f"(PID: {existing_pid or 'unknown'})"
                        )
                    time.sleep(0.1)

            # Write lock data with integrity check
            lock_data = {
                'pid': self.pid,
                'timestamp': time.time(),
                'version': LOCK_FILE_VERSION,
                'app_name': self.app_name,
                'mode': self.mode,
                'checksum': self._calculate_checksum()
            }

            if self.lock_file is None:
                raise InstanceLockError("Lock file is None")
            if self.lock_fd is None:
                raise InstanceLockError("Lock file descriptor is None")
            
            self.lock_file.seek(0)
            self.lock_file.truncate()
            json.dump(lock_data, self.lock_file)
            self.lock_file.flush()
            os.fsync(self.lock_fd)

            self.locked = True
            logger.info(f"Acquired instance lock for {self.app_name} ({self.mode}) - PID: {self.pid}")

            # Set up signal handlers for cleanup
            self._setup_signal_handlers()

            return True

        except Exception as e:
            self._close_lock_file()
            if isinstance(e, InstanceAlreadyRunningError):
                raise
            raise InstanceLockError(f"Failed to acquire instance lock: {e}")

    def release(self) -> None:
        """Release the instance lock."""
        if not self.locked:
            return

        try:
            if self.lock_fd is not None:
                # Release the lock
                try:
                    fcntl.flock(self.lock_fd, fcntl.LOCK_UN)
                except BaseException:
                    pass

            self._close_lock_file()

            # Remove lock file
            try:
                self.lock_file_path.unlink()
            except FileNotFoundError:
                pass
            except Exception as e:
                logger.debug(f"Could not remove lock file: {e}")

            self.locked = False
            logger.info(f"Released instance lock for {self.app_name} ({self.mode})")

        except Exception as e:
            logger.error(f"Error releasing instance lock: {e}")

    def _close_lock_file(self) -> None:
        """Close the lock file handle."""
        if self.lock_file:
            try:
                self.lock_file.close()
            except BaseException:
                pass
            self.lock_file = None
            self.lock_fd = None

    def _calculate_checksum(self) -> str:
        """Calculate a checksum for lock integrity."""
        data = f"{self.pid}{self.app_name}{self.mode}{os.getuid()}"
        return hashlib.sha256(data.encode()).hexdigest()[:16]

    def _get_lock_data(self) -> Optional[Dict[str, Any]]:
        """
        Get lock data from existing lock file.

        Returns:
            Lock data dict if valid, None otherwise
        """
        try:
            if self.lock_file_path.exists():
                with open(self.lock_file_path, 'r') as f:
                    data = json.load(f)
                    # Validate data structure
                    if isinstance(data, dict) and 'pid' in data:
                        return data
        except BaseException:
            pass
        return None

    def _get_existing_pid(self) -> Optional[int]:
        """
        Get PID of existing instance from lock file.

        Returns:
            PID if found and valid, None otherwise
        """
        data = self._get_lock_data()
        if data and isinstance(data.get('pid'), int):
            return data['pid']
        return None

    def _check_and_clean_stale_lock(self) -> bool:
        """
        Check if lock is stale and clean it up.

        Returns:
            True if stale lock was cleaned, False otherwise
        """
        lock_data = self._get_lock_data()
        if not lock_data:
            return False

        existing_pid = lock_data.get('pid')
        if existing_pid is None:
            return False

        # Check lock age
        lock_timestamp = lock_data.get('timestamp', 0)
        if time.time() - lock_timestamp > MAX_LOCK_AGE_SECONDS:
            logger.warning(f"Found very old lock (age: {time.time() - lock_timestamp:.0f}s), cleaning up")
            try:
                # Try to release the lock properly first
                if self.lock_fd is not None:
                    fcntl.flock(self.lock_fd, fcntl.LOCK_UN)
            except BaseException:
                pass
            try:
                self.lock_file_path.unlink()
                return True
            except Exception as e:
                logger.debug(f"Could not remove stale lock: {e}")
                return False

        # Check if process is still running
        try:
            if not psutil.pid_exists(existing_pid):
                logger.warning(f"Found stale lock from PID {existing_pid}, cleaning up")
                try:
                    self.lock_file_path.unlink()
                    return True
                except Exception as e:
                    logger.debug(f"Could not remove stale lock: {e}")
                    return False
            else:
                # Check if it's actually our application
                try:
                    proc = psutil.Process(existing_pid)
                    cmdline = ' '.join(proc.cmdline())

                    # More thorough check
                    if (self.app_name not in cmdline and
                        'asuc' not in cmdline and
                            lock_data.get('app_name') != self.app_name):
                        logger.warning(f"Lock held by different process (PID {existing_pid}), cleaning up")
                        self.lock_file_path.unlink()
                        return True
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    # Process disappeared or we can't access it
                    try:
                        self.lock_file_path.unlink()
                        return True
                    except BaseException:
                        pass
        except Exception as e:
            logger.debug(f"Error checking process {existing_pid}: {e}")

        return False

    def _setup_signal_handlers(self) -> None:
        """Set up signal handlers for cleanup on termination."""
        def cleanup_handler(signum, frame):
            logger.debug(f"Received signal {signum}, cleaning up instance lock")
            self.release()
            # Re-raise to allow normal signal handling
            signal.signal(signum, signal.SIG_DFL)
            os.kill(os.getpid(), signum)

        # Handle common termination signals
        for sig in [signal.SIGTERM, signal.SIGINT]:
            try:
                signal.signal(sig, cleanup_handler)
            except BaseException:
                pass  # Some signals may not be available on all platforms

    def __enter__(self):
        """Context manager entry."""
        self.acquire()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.release()

    def __del__(self):
        """Cleanup on object destruction."""
        self.release()


@contextmanager
def ensure_single_instance(app_name: str = "arch-smart-update-checker",
                           mode: str = "gui",
                           timeout: float = 0.0):
    """
    Context manager to ensure single instance execution.

    Args:
        app_name: Application name
        mode: Application mode ('gui' or 'cli')
        timeout: Maximum time to wait for lock

    Yields:
        InstanceLock object

    Raises:
        InstanceAlreadyRunningError: If another instance is running
    """
    lock = InstanceLock(app_name, mode)
    try:
        lock.acquire(timeout=timeout)
        yield lock
    finally:
        lock.release()


def check_single_instance(app_name: str = "arch-smart-update-checker",
                          mode: str = "gui") -> Optional[int]:
    """
    Check if another instance is running without acquiring lock.

    Args:
        app_name: Application name
        mode: Application mode

    Returns:
        PID of running instance, or None if no instance is running
    """
    lock = InstanceLock(app_name, mode)
    try:
        # Try to acquire lock non-blocking
        lock.acquire(timeout=0.0, check_stale=True)
        # If we got it, no other instance is running
        lock.release()
        return None
    except InstanceAlreadyRunningError:
        # Another instance is running
        return lock._get_existing_pid()
