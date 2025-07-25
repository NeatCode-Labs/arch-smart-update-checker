"""
Update history management for tracking package updates.
"""

# SPDX-License-Identifier: GPL-3.0-or-later

import json
import fcntl
import threading
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import List, Optional
import os
from concurrent.futures import ThreadPoolExecutor

from ..utils.logger import get_logger
from ..constants import get_cache_dir

logger = get_logger(__name__)


@dataclass
class UpdateHistoryEntry:
    """Represents a single update history entry."""
    timestamp: datetime            # when the update finished
    packages: List[str]            # updated package names
    succeeded: bool                # True if exit_code == 0
    exit_code: int                 # raw exit code from pacman
    duration_sec: float            # measured in monitor thread
    version_info: Optional[dict] = None  # { package: {"old": "1.0", "new": "2.0"} }

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "timestamp": self.timestamp.isoformat(),
            "packages": self.packages,
            "succeeded": self.succeeded,
            "exit_code": self.exit_code,
            "duration_sec": self.duration_sec,
            "version_info": self.version_info
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'UpdateHistoryEntry':
        """Create from dictionary."""
        return cls(
            timestamp=datetime.fromisoformat(data["timestamp"]),
            packages=data["packages"],
            succeeded=data["succeeded"],
            exit_code=data["exit_code"],
            duration_sec=data.get("duration_sec", 0.0),
            version_info=data.get("version_info")
        )


class UpdateHistoryManager:
    """Manages update history storage and retrieval."""

    def __init__(self, path: Optional[str] = None, retention_days: int = 365):
        """
        Initialize the update history manager.

        Args:
            path: Path to history file (defaults to cache dir)
            retention_days: Days to retain history entries
        """
        if path is None:
            path = str(get_cache_dir() / "update_history.json")
        self.path = Path(path)
        self.retention_days = retention_days
        self._lock = threading.Lock()
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="HistoryMgr")
        self._cached_entries: Optional[List[UpdateHistoryEntry]] = None
        self._shutdown = False

        # Ensure directory exists
        self.path.parent.mkdir(parents=True, exist_ok=True)

        logger.info(f"Initialized UpdateHistoryManager with path: {self.path}")

    def __del__(self):
        """Cleanup ThreadPoolExecutor on destruction."""
        self.shutdown()

    def shutdown(self, wait: bool = True):
        """
        Shutdown the thread pool executor.

        Args:
            wait: Whether to wait for running tasks to complete
        """
        if not self._shutdown and hasattr(self, '_executor'):
            try:
                self._executor.shutdown(wait=wait)
                self._shutdown = True
                logger.debug("UpdateHistoryManager thread pool shutdown")
            except Exception as e:
                logger.warning(f"Error shutting down UpdateHistoryManager thread pool: {e}")

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit with cleanup."""
        self.shutdown()

    def all(self) -> List[UpdateHistoryEntry]:
        """
        Get all update history entries.

        Returns:
            List of update history entries (newest first)
        """
        with self._lock:
            if self._cached_entries is None:
                self._cached_entries = self._load_entries()
            # Sort by timestamp descending (newest first)
            sorted_entries = sorted(self._cached_entries, key=lambda e: e.timestamp, reverse=True)
            return sorted_entries

    def add(self, entry: UpdateHistoryEntry) -> None:
        """
        Add a new update history entry.

        Args:
            entry: The update history entry to add
        """
        def _add_entry():
            with self._lock:
                try:
                    entries = self._load_entries()
                    entries.append(entry)
                    self._save_entries(entries)
                    self._cached_entries = entries
                    logger.info(
                        f"Added update history entry: {len(entry.packages)} packages, exit code: {entry.exit_code}")
                except Exception as e:
                    logger.error(f"Failed to add update history entry: {e}")
                    raise

        # Check if executor is still available
        if self._shutdown or not hasattr(self, '_executor'):
            logger.warning("UpdateHistoryManager is shutdown, cannot add entry")
            return

        try:
            # Run in executor to avoid blocking UI with timeout
            future = self._executor.submit(_add_entry)
            # Add timeout to prevent hanging
            future.result(timeout=30)  # 30 second timeout
        except Exception as e:
            logger.error(f"Failed to submit history entry: {e}")
            # Fallback: try to add synchronously
            try:
                _add_entry()
            except Exception as e2:
                logger.error(f"Failed to add history entry synchronously: {e2}")

    def add_entry(self, packages: List[str], succeeded: bool, output: str = "",
                  duration_seconds: float = 0.0, exit_code: int = 0,
                  version_info: Optional[dict] = None) -> None:
        """
        Helper method to add an update history entry with individual parameters.

        Args:
            packages: List of package names
            succeeded: Whether the update succeeded
            output: Command output (optional)
            duration_seconds: Duration in seconds
            exit_code: Exit code from pacman
            version_info: Version change information
        """
        entry = UpdateHistoryEntry(
            timestamp=datetime.now(),
            packages=packages,
            succeeded=succeeded,
            exit_code=exit_code,
            duration_sec=duration_seconds,
            version_info=version_info
        )
        self.add(entry)

    def clear(self) -> None:
        """Clear all update history entries."""
        with self._lock:
            try:
                self._save_entries([])
                self._cached_entries = []
                logger.info("Cleared update history")
            except Exception as e:
                logger.error(f"Failed to clear update history: {e}")
                raise

    def export(self, filename: str, format_: str = "json") -> None:
        """
        Export update history to file.

        Args:
            dst_path: Destination file path
            format_: Export format (json or csv)
        """
        entries = self.all()

        try:
            if format_ == "json":
                self._export_json(entries, filename)
            elif format_ == "csv":
                self._export_csv(entries, filename)
            else:
                raise ValueError(f"Unsupported export format: {format_}")

            logger.info(f"Exported {len(entries)} entries to {filename}")
        except Exception as e:
            logger.error(f"Failed to export update history: {e}")
            raise

    def _load_entries(self) -> List[UpdateHistoryEntry]:
        """Load entries from disk with file locking."""
        if not self.path.exists():
            return []

        try:
            with open(self.path, 'r') as f:
                # Acquire exclusive lock for reading
                fcntl.flock(f.fileno(), fcntl.LOCK_SH)
                try:
                    data = json.load(f)
                    entries = [UpdateHistoryEntry.from_dict(d) for d in data]

                    # Trim old entries and check file size
                    entries = self._trim_entries(entries)

                    return entries
                finally:
                    fcntl.flock(f.fileno(), fcntl.LOCK_UN)
        except (json.JSONDecodeError, KeyError) as e:
            logger.error(f"Corrupted history file: {e}")
            return []
        except Exception as e:
            logger.error(f"Failed to load update history: {e}")
            return []

    def _save_entries(self, entries: List[UpdateHistoryEntry]) -> None:
        """Save entries to disk with file locking."""
        # Trim before saving
        entries = self._trim_entries(entries)

        data = [entry.to_dict() for entry in entries]

        # Write to temporary file first
        temp_path = self.path.with_suffix('.tmp')

        try:
            with open(temp_path, 'w') as f:
                # Acquire exclusive lock for writing
                fcntl.flock(f.fileno(), fcntl.LOCK_EX)
                try:
                    json.dump(data, f, indent=2)
                    f.flush()
                    os.fsync(f.fileno())
                finally:
                    fcntl.flock(f.fileno(), fcntl.LOCK_UN)

            # Atomic rename
            temp_path.replace(self.path)

        except Exception as e:
            logger.error(f"Failed to save update history: {e}")
            if temp_path.exists():
                temp_path.unlink()
            raise

    def _trim_entries(self, entries: List[UpdateHistoryEntry]) -> List[UpdateHistoryEntry]:
        """
        Trim old entries and check file size.

        Args:
            entries: List of entries to trim

        Returns:
            Trimmed list of entries
        """
        # Remove entries older than retention_days
        cutoff_date = datetime.now().timestamp() - (self.retention_days * 24 * 60 * 60)
        entries = [e for e in entries if e.timestamp.timestamp() > cutoff_date]

        # Check approximate file size (100 bytes per entry as rough estimate)
        while len(entries) * 100 > 10 * 1024 * 1024:  # 10MB limit
            entries.pop(0)  # Remove oldest

        return entries

    def _export_json(self, entries: List[UpdateHistoryEntry], dst_path: str) -> None:
        """Export entries as JSON."""
        data = [entry.to_dict() for entry in entries]
        with open(dst_path, 'w') as f:
            json.dump(data, f, indent=2)

    def _export_csv(self, entries: List[UpdateHistoryEntry], dst_path: str) -> None:
        """Export entries as CSV."""
        import csv

        with open(dst_path, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['timestamp', 'packages', 'succeeded', 'exit_code', 'duration_sec'])

            for entry in entries:
                writer.writerow([
                    entry.timestamp.isoformat(),
                    ', '.join(entry.packages),
                    'Yes' if entry.succeeded else 'No',
                    entry.exit_code,
                    f"{entry.duration_sec:.1f}"
                ])
