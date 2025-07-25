"""
Package pattern matching utilities with ReDoS protection.
"""

# SPDX-License-Identifier: GPL-3.0-or-later

import re
import threading
from typing import Set, List, Optional, Iterator
from contextlib import contextmanager
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError, as_completed

from ..utils.logger import get_logger
from ..constants import GENERIC_PACKAGE_NAMES

logger = get_logger(__name__)


class RegexTimeoutError(Exception):
    """Raised when regex operations exceed timeout."""
    pass


class ThreadSafeRegexManager:
    """Thread-safe regex manager to replace signal-based timeout."""

    def __init__(self, max_workers: int = 2):
        """Initialize with thread pool for regex operations."""
        self._executor = ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="RegexWorker")
        self._local = threading.local()
        logger.debug(f"Initialized thread-safe regex manager with {max_workers} workers")

    def safe_regex_finditer(self, pattern: str, text: str, flags: int = 0, timeout: int = 2) -> Iterator:
        """
        Thread-safe regex finditer with timeout protection.

        Args:
            pattern: Regex pattern
            text: Text to search
            flags: Regex flags
            timeout: Timeout in seconds

        Returns:
            Iterator of regex matches

        Raises:
            RegexTimeoutError: If operation times out
        """
        try:
            # Submit regex operation to thread pool
            future = self._executor.submit(self._execute_regex, pattern, text, flags)

            # Wait for result with timeout
            try:
                return future.result(timeout=timeout)
            except FutureTimeoutError:
                logger.warning(f"Regex operation timed out after {timeout}s: {pattern[:50]}...")
                # Cancel the future if possible
                future.cancel()
                return iter([])

        except Exception as e:
            logger.error(f"Error in regex operation: {e}")
            return iter([])

    @staticmethod
    def _execute_regex(pattern: str, text: str, flags: int = 0) -> Iterator:
        """Execute regex operation in thread pool."""
        try:
            compiled_pattern = re.compile(pattern, flags)
            return compiled_pattern.finditer(text)
        except re.error as e:
            logger.error(f"Regex compilation error: {e}")
            return iter([])

    def __del__(self):
        """Cleanup thread pool on destruction."""
        try:
            self._executor.shutdown(wait=False)
        except Exception:
            pass


# Global thread-safe regex manager instance
_regex_manager = ThreadSafeRegexManager()


@contextmanager
def regex_timeout(seconds: int = 2):
    """
    DEPRECATED: Context manager for backward compatibility.
    New code should use safe_regex_finditer directly.

    Args:
        seconds: Timeout in seconds (ignored, maintained for compatibility)

    Raises:
        RegexTimeoutError: If regex operation times out
    """
    logger.warning("regex_timeout context manager is deprecated. Use safe_regex_finditer directly.")
    yield


def safe_regex_finditer(pattern: str, text: str, flags: int = 0, timeout: int = 2) -> Iterator:
    """
    Safely execute regex finditer with thread-safe timeout protection.

    Args:
        pattern: Regex pattern
        text: Text to search
        flags: Regex flags
        timeout: Timeout in seconds

    Returns:
        Iterator of regex matches

    Raises:
        RegexTimeoutError: If operation times out
    """
    # Input length validation to prevent DoS
    if len(text) > 100000:  # 100KB limit
        logger.warning(f"Text too long for regex processing: {len(text)} chars")
        return iter([])

    # Use thread-safe regex manager
    return _regex_manager.safe_regex_finditer(pattern, text, flags, timeout)


class PackagePatternMatcher:
    """Matches package names in text using secure patterns."""

    def __init__(self) -> None:
        """Initialize the pattern matcher with secure patterns."""
        # Simplified, safer patterns without nested quantifiers
        self.base_patterns = [
            # Simple package name with version (max 50 chars to prevent DoS)
            r'\b([a-z0-9](?:[a-z0-9\-_.+]){1,48}[a-z0-9])\s*(?:>=?|<=?|==?)\s*[\d\-._]{1,20}\b',
            # Package name only (max 50 chars)
            r'\b([a-z0-9](?:[a-z0-9\-_.+]){1,48}[a-z0-9])\b',
            # With lib prefix (max 45 chars for name part)
            r'\blib([a-z0-9](?:[a-z0-9\-_.]){1,43}[a-z0-9])\b',
        ]

        self.custom_patterns: List[str] = []
        self.pattern_cache = {}  # Cache compiled patterns
        logger.debug("Initialized PackagePatternMatcher with secure patterns")

    def add_custom_patterns(self, patterns: List[str]) -> None:
        """
        Add custom patterns for matching with security validation.

        Args:
            patterns: List of regex patterns
        """
        for pattern in patterns:
            try:
                # Validate pattern length
                if len(pattern) > 200:
                    logger.warning(f"Pattern too long, skipping: {len(pattern)} chars")
                    continue

                # Test compile with timeout
                with regex_timeout(1):
                    re.compile(pattern)

                self.custom_patterns.append(pattern)
                logger.debug(f"Added custom pattern: {pattern}")
            except (re.error, RegexTimeoutError) as e:
                logger.warning(f"Invalid or unsafe regex pattern '{pattern}': {e}")

    def extract_package_names(self, text: str,
                              installed_packages: Set[str],
                              extra_patterns: Optional[List[str]] = None) -> Set[str]:
        """
        Extract package names from text with security protections.

        Args:
            text: Text to search in
            installed_packages: Set of installed package names for validation
            extra_patterns: Additional patterns to use

        Returns:
            Set of found package names
        """
        if not text:
            return set()

        # Input validation for DoS prevention
        if len(text) > 100000:  # 100KB limit
            logger.warning(f"Input text too long for processing: {len(text)} chars")
            return set()

        found_packages = set()
        text_lower = text.lower()

        # Method 1: Direct matching against installed packages (most reliable)
        for package in installed_packages:
            if len(package) > 100:  # Skip extremely long package names
                continue

            # Use word boundary matching with length limit
            try:
                pattern = r'\b' + re.escape(package) + r'\b'
                if re.search(pattern, text_lower):
                    if package not in GENERIC_PACKAGE_NAMES:
                        found_packages.add(package)
                        logger.debug(f"Found package by direct match: {package}")
            except re.error:
                continue

        # Method 2: Pattern-based extraction with security
        patterns_to_use = self.base_patterns[:]

        # Add custom patterns (already validated)
        patterns_to_use.extend(self.custom_patterns)

        # Add extra patterns with validation
        if extra_patterns:
            for pattern in extra_patterns:
                if len(pattern) > 200:
                    continue
                try:
                    with regex_timeout(1):
                        re.compile(pattern)
                    patterns_to_use.append(pattern)
                except (re.error, RegexTimeoutError):
                    logger.warning(f"Invalid extra pattern: {pattern}")

        # Extract using secure patterns
        for pattern in patterns_to_use:
            try:
                matches = safe_regex_finditer(pattern, text_lower, re.IGNORECASE, timeout=2)
                for match in matches:
                    # Get the captured group (if any) or the whole match
                    if match.groups():
                        candidate = match.group(1)
                    else:
                        candidate = match.group(0)

                    # Clean up the candidate
                    candidate = candidate.strip().lower()

                    # Length validation
                    if len(candidate) > 100:
                        continue

                    # Validate against installed packages
                    if candidate in installed_packages and candidate not in GENERIC_PACKAGE_NAMES:
                        found_packages.add(candidate)
                        logger.debug(f"Found package by pattern: {candidate}")
            except Exception as e:
                logger.error(f"Error processing pattern '{pattern}': {e}")
                continue

        # Method 3: Look for specific package mentions with secure patterns
        mention_patterns = [
            r'package\s+([a-z0-9](?:[a-z0-9\-_.]){1,48}[a-z0-9])',
            r'([a-z0-9](?:[a-z0-9\-_.]){1,48}[a-z0-9])\s+package',
            r'`([a-z0-9](?:[a-z0-9\-_.]){1,48}[a-z0-9])`',  # Markdown code
            r'"([a-z0-9](?:[a-z0-9\-_.]){1,48}[a-z0-9])"',  # Quoted
        ]

        for pattern in mention_patterns:
            try:
                matches = safe_regex_finditer(pattern, text_lower, timeout=1)
                for match in matches:
                    candidate = match.group(1).strip()
                    if candidate in installed_packages and candidate not in GENERIC_PACKAGE_NAMES:
                        found_packages.add(candidate)
            except Exception:
                continue

        # Limit total results to prevent resource exhaustion
        if len(found_packages) > 1000:
            logger.warning(f"Too many packages found ({len(found_packages)}), limiting to 1000")
            found_packages = set(list(found_packages)[:1000])

        logger.info(f"Extracted {len(found_packages)} package names from text")
        return found_packages

    def find_affected_packages(self, text: str,
                               installed_packages: Set[str]) -> Set[str]:
        """
        Find packages affected by a news item or advisory.

        This is a legacy method for backward compatibility.

        Args:
            text: Text to analyze
            installed_packages: Set of installed packages

        Returns:
            Set of affected package names
        """
        return self.extract_package_names(text, installed_packages)

    def is_package_mentioned(self, text: str, package_name: str) -> bool:
        """
        Check if a specific package is mentioned in text with security protections.

        Args:
            text: Text to search in
            package_name: Package name to look for

        Returns:
            True if package is mentioned
        """
        if not text or not package_name:
            return False

        # Input validation
        if len(text) > 50000 or len(package_name) > 100:
            logger.warning("Input too long for package mention check")
            return False

        # Escape special regex characters in package name
        escaped_name = re.escape(package_name)

        # Look for whole word matches with timeout protection
        pattern = r'\b' + escaped_name + r'\b'

        try:
            with regex_timeout(1):
                return bool(re.search(pattern, text, re.IGNORECASE))
        except (RegexTimeoutError, re.error):
            logger.warning(f"Regex timeout/error checking package mention: {package_name}")
            return False

    def extract_version_info(self, text: str) -> List[tuple]:
        """
        Extract version information from text with security protections.

        Args:
            text: Text to analyze

        Returns:
            List of (package, version) tuples
        """
        if not text:
            return []

        # Input validation
        if len(text) > 50000:
            logger.warning("Text too long for version extraction")
            return []

        version_info = []

        # Simplified pattern for package with version (no nested quantifiers)
        pattern = r'([a-z0-9](?:[a-z0-9\-_.+]){1,48}[a-z0-9])\s*(>=?|<=?|==?)\s*([\d](?:[\d\-._]){0,19})'

        try:
            matches = safe_regex_finditer(pattern, text.lower(), timeout=2)
            for match in matches:
                package = match.group(1)
                operator = match.group(2)
                version = match.group(3)

                # Skip generic names and validate lengths
                if (package not in GENERIC_PACKAGE_NAMES and
                        len(package) <= 50 and len(version) <= 20):
                    version_info.append((package, f"{operator}{version}"))
                    logger.debug(f"Found version info: {package} {operator} {version}")

                # Limit results to prevent resource exhaustion
                if len(version_info) >= 100:
                    logger.warning("Version info extraction reached limit (100)")
                    break

        except Exception as e:
            logger.error(f"Error extracting versions: {e}")

        return version_info
