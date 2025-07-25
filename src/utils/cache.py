"""
Cache management for RSS feeds and other data.
"""

# SPDX-License-Identifier: GPL-3.0-or-later

import hashlib
import json
import os
import secrets
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, Optional

from ..exceptions import CacheError
from ..utils.logger import get_logger
from ..constants import CACHE_DIR_PERMISSIONS, get_cache_dir

logger = get_logger(__name__)


class CacheManager:
    """Manages caching of RSS feeds and other data."""

    def __init__(self, cache_dir: Optional[str] = None, ttl_hours: int = 1) -> None:
        """
        Initialize cache manager.

        Args:
            cache_dir: Cache directory path
            ttl_hours: Time to live in hours
        """
        if cache_dir:
            self.cache_dir = Path(cache_dir)
        else:
            self.cache_dir = get_cache_dir()

        try:
            self.cache_dir.mkdir(parents=True, exist_ok=True)

            # Set secure permissions
            try:
                os.chmod(self.cache_dir, CACHE_DIR_PERMISSIONS)
            except OSError as e:
                logger.warning(f"Failed to set permissions on cache directory: {e}")
        except PermissionError as e:
            logger.error(f"Permission denied creating cache directory: {e}")
            raise CacheError(f"Cannot create cache directory: {e}")
        except OSError as e:
            logger.error(f"Failed to create cache directory: {e}")
            raise CacheError(f"Cannot create cache directory: {e}")

        self.ttl_hours = ttl_hours

        # Initialize cryptographic salt for secure cache key generation
        self._cache_salt = secrets.token_hex(16)

        logger.debug(f"Initialized cache manager with TTL={ttl_hours} hours and secure key generation")

    def _ensure_cache_dir(self) -> None:
        """Ensure cache directory exists."""
        try:
            self.cache_dir.mkdir(parents=True, exist_ok=True)
        except (PermissionError, OSError) as e:
            logger.error(f"Failed to ensure cache directory exists: {e}")
            raise CacheError(f"Cannot access cache directory: {e}")

    def _get_cache_file(self, key: str) -> Path:
        """Get the cache file path for a given key with secure hashing."""
        # Sanitize key for filename
        safe_key = "".join(c for c in key if c.isalnum() or c in ("-", "_")).rstrip()
        if not safe_key:
            # Use cryptographically secure hash with salt to prevent collision attacks
            salted_key = (key + self._cache_salt).encode('utf-8')
            secure_hash = hashlib.sha256(salted_key).hexdigest()[:16]
            safe_key = f"cache_{secure_hash}"
        return self.cache_dir / f"{safe_key}.json"

    def _json_encoder(self, obj: Any) -> Any:
        """Custom JSON encoder for datetime objects."""
        if isinstance(obj, datetime):
            return {"__datetime__": obj.isoformat()}
        return str(obj)

    def _json_decoder(self, dct: Dict[str, Any]) -> Any:
        """Custom JSON decoder for datetime objects."""
        if "__datetime__" in dct:
            try:
                return datetime.fromisoformat(dct["__datetime__"])
            except (ValueError, TypeError) as e:
                logger.warning(f"Failed to decode datetime: {e}")
                return datetime.min
        return dct

    def get(self, key: str) -> Optional[Any]:
        """
        Get cached data for a key.

        Args:
            key: Cache key

        Returns:
            Cached data or None if not found/expired
        """
        cache_file = self._get_cache_file(key)

        # Use atomic operation - try to open directly instead of checking existence
        try:
            with open(cache_file, "r", encoding="utf-8") as f:
                data = json.load(f, object_hook=self._json_decoder)
        except FileNotFoundError:
            logger.debug(f"Cache miss for key: {key}")
            return None
        except json.JSONDecodeError as e:
            logger.warning(f"Corrupted cache file {cache_file}: {e}")
            # Remove corrupted file
            try:
                cache_file.unlink()
            except OSError:
                pass
            return None
        except PermissionError as e:
            logger.error(f"Permission denied reading cache file {cache_file}: {e}")
            return None
        except OSError as e:
            logger.error(f"Error reading cache file {cache_file}: {e}")
            return None

        # Check if data is valid
        if not self._is_valid(data):
            logger.debug(f"Cache expired for key: {key}")
            # Remove expired file
            try:
                cache_file.unlink()
            except OSError:
                pass
            return None

        # Verify data integrity if hash is present
        if "integrity_hash" in data:
            import hashlib
            cached_data = data.get("data")
            if cached_data is not None:
                try:
                    data_str = json.dumps(cached_data, default=self._json_encoder, sort_keys=True, ensure_ascii=False)
                    computed_hash = hashlib.sha256(data_str.encode('utf-8')).hexdigest()
                    stored_hash = data.get("integrity_hash")

                    if computed_hash != stored_hash:
                        logger.warning(f"Cache integrity check failed for key: {key}")
                        # Remove corrupted file
                        try:
                            cache_file.unlink()
                        except OSError:
                            pass
                        return None
                except Exception as e:
                    logger.warning(f"Error verifying cache integrity for key {key}: {e}")
                    # Remove potentially corrupted file
                    try:
                        cache_file.unlink()
                    except OSError:
                        pass
                    return None

        logger.debug(f"Cache hit for key: {key}")
        return data.get("data")

    def set(self, key: str, value: Any) -> None:
        """
        Set cached data for a key with integrity protection.

        Args:
            key: Cache key
            value: Data to cache
        """
        self._ensure_cache_dir()
        cache_file = self._get_cache_file(key)

        # Generate integrity hash for the data
        import hashlib
        data_str = json.dumps(value, default=self._json_encoder, sort_keys=True, ensure_ascii=False)
        data_hash = hashlib.sha256(data_str.encode('utf-8')).hexdigest()

        data = {
            "timestamp": datetime.now(),
            "data": value,
            "integrity_hash": data_hash,
            "cache_version": "1.0"
        }

        try:
            # Write to temporary file first
            temp_file = cache_file.with_suffix('.tmp')
            with open(temp_file, "w", encoding="utf-8") as f:
                json.dump(data, f, default=self._json_encoder, ensure_ascii=False)

            # Set secure permissions on temp file
            os.chmod(temp_file, 0o600)  # Owner read/write only

            # Atomic rename
            temp_file.replace(cache_file)
            logger.debug(f"Cached data for key: {key}")
        except PermissionError as e:
            logger.error(f"Permission denied writing cache file {cache_file}: {e}")
            # Clean up temp file
            try:
                temp_file.unlink()
            except (OSError, FileNotFoundError):
                pass
            raise CacheError(f"Cannot write to cache: {e}")
        except OSError as e:
            logger.error(f"Error writing cache file {cache_file}: {e}")
            # Clean up temp file
            try:
                temp_file.unlink()
            except (OSError, FileNotFoundError):
                pass
            raise CacheError(f"Cannot write to cache: {e}")

    def _is_valid(self, data: Dict[str, Any]) -> bool:
        """
        Check if cached data is still valid.

        Args:
            data: Cached data

        Returns:
            True if data is valid
        """
        timestamp = data.get("timestamp")
        if not isinstance(timestamp, datetime):
            return False

        age = datetime.now() - timestamp
        max_age = timedelta(hours=self.ttl_hours)
        return age < max_age

    def clear(self) -> None:
        """Clear all cached data."""
        try:
            cache_files = list(self.cache_dir.glob("*.json"))
            cleared_count = 0

            for cache_file in cache_files:
                try:
                    cache_file.unlink()
                    cleared_count += 1
                except OSError as e:
                    logger.warning(f"Failed to remove cache file {cache_file}: {e}")

            logger.info(f"Cleared {cleared_count} cache files")
        except OSError as e:
            logger.error(f"Failed to list cache files: {e}")
            raise CacheError(f"Failed to clear cache: {e}")

    def is_valid(self, key: str) -> bool:
        """
        Check if cache entry is valid without loading data.

        Args:
            key: Cache key

        Returns:
            True if cache entry exists and is valid
        """
        cache_file = self._get_cache_file(key)

        # Use atomic operation - try to open directly instead of checking existence
        try:
            with open(cache_file, "r", encoding="utf-8") as f:
                data = json.load(f, object_hook=self._json_decoder)
            return self._is_valid(data)
        except FileNotFoundError:
            return False
        except (json.JSONDecodeError, PermissionError, OSError):
            return False

    def cleanup(self) -> None:
        """Clean up expired cache entries."""
        try:
            cache_files = list(self.cache_dir.glob("*.json"))
            cleaned_count = 0

            for cache_file in cache_files:
                try:
                    with open(cache_file, "r", encoding="utf-8") as f:
                        data = json.load(f, object_hook=self._json_decoder)

                    if not self._is_valid(data):
                        cache_file.unlink()
                        cleaned_count += 1
                except (json.JSONDecodeError, OSError):
                    # Remove corrupted or inaccessible files
                    try:
                        cache_file.unlink()
                        cleaned_count += 1
                    except OSError:
                        pass

            logger.info(f"Cleaned up {cleaned_count} expired cache files")
        except OSError as e:
            logger.error(f"Failed to cleanup cache: {e}")

    def get_cache_size(self) -> int:
        """
        Get total size of cache in bytes.

        Returns:
            Total cache size in bytes
        """
        total_size = 0
        try:
            for cache_file in self.cache_dir.glob("*.json"):
                try:
                    total_size += cache_file.stat().st_size
                except OSError:
                    pass
        except OSError as e:
            logger.error(f"Failed to calculate cache size: {e}")

        return total_size

    def get_cache_stats(self) -> Dict[str, Any]:
        """
        Get cache statistics.

        Returns:
            Dictionary with cache statistics
        """
        stats = {
            "directory": str(self.cache_dir),
            "ttl_hours": self.ttl_hours,
            "file_count": 0,
            "total_size": 0,
            "expired_count": 0
        }

        try:
            cache_files = list(self.cache_dir.glob("*.json"))
            stats["file_count"] = len(cache_files)

            for cache_file in cache_files:
                try:
                    stats["total_size"] += cache_file.stat().st_size

                    # Check if expired
                    with open(cache_file, "r", encoding="utf-8") as f:
                        data = json.load(f, object_hook=self._json_decoder)
                    if not self._is_valid(data):
                        stats["expired_count"] += 1
                except (OSError, json.JSONDecodeError):
                    pass
        except OSError as e:
            logger.error(f"Failed to get cache stats: {e}")

        return stats
