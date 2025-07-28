"""
Package management functionality for Arch Linux systems.
"""

# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path
from typing import List, Optional, Dict, Any, Set

from .exceptions import PackageManagerError
from .models import PackageUpdate, NewsItem
from .utils.logger import get_logger
from .utils.validators import validate_package_name
from .utils.subprocess_wrapper import SecureSubprocess

logger = get_logger(__name__)


class PackageManager:
    """Manages package operations for Arch Linux systems."""

    def __init__(self) -> None:
        """Initialize the package manager."""
        self._verify_pacman_available()

        # Cache for package info
        self._installed_packages_cache: Optional[List[Dict[str, str]]] = None
        self._installed_names_cache: Optional[Set[str]] = None

        logger.debug("Initialized PackageManager")

    def _verify_pacman_available(self) -> None:
        """Verify that pacman is available on the system."""
        # Skip verification if in test environment
        if os.environ.get('ASUC_SKIP_PACMAN_VERIFY') == '1':
            logger.debug("Skipping pacman verification (test environment)")
            return
            
        try:
            result = SecureSubprocess.run(
                ["pacman", "--version"],
                capture_output=True,
                text=True,
                check=False
            )
            if result.returncode != 0:
                raise PackageManagerError("pacman is not available on this system")
            logger.debug(f"Found pacman: {result.stdout.strip()}")
        except FileNotFoundError:
            raise PackageManagerError("pacman command not found - is this an Arch-based system?")
        except Exception as e:
            raise PackageManagerError(f"Failed to verify pacman availability: {e}")

    def get_installed_packages(self) -> List[Dict[str, str]]:
        """
        Get list of installed packages.

        Returns:
            List of dictionaries with package information

        Raises:
            PackageManagerError: If getting packages fails
        """
        if self._installed_packages_cache is not None:
            return self._installed_packages_cache

        try:
            # Get detailed info for all packages at once
            result = SecureSubprocess.run_pacman(
                ["-Qi"],
                capture_output=True,
                text=True,
                check=False,
                timeout=30
            )

            if result.returncode != 0:
                error_msg = result.stderr.strip() if result.stderr else "Unknown error"
                raise PackageManagerError(f"Failed to get installed packages: {error_msg}")

            packages = []
            current_package: dict[str, str] = {}

            # Parse the output
            for line in result.stdout.split('\n'):
                if not line.strip():
                    # Empty line indicates end of package info
                    if current_package and 'name' in current_package:
                        packages.append(current_package)
                        current_package = {}
                    continue

                if ':' in line and not line.startswith(' '):
                    # Split only on first colon to handle field names with spaces
                    parts = line.split(':', 1)
                    if len(parts) == 2:
                        key = parts[0].strip()
                        value = parts[1].strip()

                        if key == 'Name':
                            current_package['name'] = value
                        elif key == 'Version':
                            current_package['version'] = value
                        elif key == 'Installed Size':
                            current_package['size'] = value
                        elif key == 'Install Date':
                            current_package['install_date'] = value
                        elif key == 'Repository':
                            current_package['repository'] = value if value != 'None' else 'local'
                        elif key == 'Description':
                            current_package['description'] = value

            # Don't forget the last package
            if current_package and 'name' in current_package:
                packages.append(current_package)

            # Ensure all packages have required fields
            for pkg in packages:
                pkg.setdefault('size', 'Unknown')
                pkg.setdefault('install_date', 'Unknown')
                pkg.setdefault('repository', 'local')
                pkg.setdefault('description', '')
                pkg.setdefault('version', 'Unknown')

            self._installed_packages_cache = packages
            logger.info(f"Found {len(packages)} installed packages")
            return packages

        except ValueError as e:
            raise PackageManagerError(f"Invalid package name encountered: {e}")
        except Exception as e:
            logger.error(f"Error getting installed packages: {e}")
            raise PackageManagerError(f"Failed to get installed packages: {e}")

    def _get_package_details(self, package_name: str) -> Optional[Dict[str, str]]:
        """Get detailed information for a single package."""
        try:
            result = SecureSubprocess.run_pacman(
                ["-Qi", package_name],
                capture_output=True,
                text=True,
                check=False,
                timeout=5
            )

            if result.returncode != 0:
                return None

            # Parse the output
            info = {
                'name': package_name,
                'version': '',
                'repository': 'local',
                'size': 'Unknown',
                'install_date': 'Unknown',
                'description': ''
            }

            for line in result.stdout.split('\n'):
                if line.startswith('Version'):
                    info['version'] = line.split(':', 1)[1].strip()
                elif line.startswith('Installed Size'):
                    info['size'] = line.split(':', 1)[1].strip()
                elif line.startswith('Install Date'):
                    info['install_date'] = line.split(':', 1)[1].strip()
                elif line.startswith('Repository'):
                    repo = line.split(':', 1)[1].strip()
                    if repo and repo != 'None':
                        info['repository'] = repo
                elif line.startswith('Description'):
                    info['description'] = line.split(':', 1)[1].strip()

            return info

        except Exception:
            return None

    def clear_cache(self) -> None:
        """Clear the internal package caches."""
        logger.info("CACHE CLEARING: clear_cache() called!")  # Changed to INFO level
        self._installed_packages_cache = None
        self._installed_names_cache = None
        logger.info(
            f"CACHE CLEARED: installed_packages={self._installed_packages_cache}, names={self._installed_names_cache}")

    def get_package_dependencies(self, package_name: str) -> List[str]:
        """
        Get dependencies for a package.

        Args:
            package_name: Name of the package

        Returns:
            List of dependency names

        Raises:
            PackageManagerError: If getting dependencies fails
        """
        # Validate package name
        if not validate_package_name(package_name):
            raise PackageManagerError(f"Invalid package name: {package_name}")

        try:
            # Sanitize package name
            safe_name = SecureSubprocess.sanitize_package_name(package_name)

            result = SecureSubprocess.run_pacman(
                ["-Si", safe_name],
                capture_output=True,
                text=True,
                check=False,
                timeout=10
            )

            if result.returncode != 0:
                # Try local package
                result = SecureSubprocess.run_pacman(
                    ["-Qi", safe_name],
                    capture_output=True,
                    text=True,
                    check=False,
                    timeout=10
                )

                if result.returncode != 0:
                    return []

            dependencies = []
            for line in result.stdout.split('\n'):
                if line.startswith('Depends On'):
                    deps_str = line.split(':', 1)[1].strip()
                    if deps_str and deps_str != 'None':
                        # Parse dependencies (handle versions)
                        for dep in deps_str.split():
                            # Remove version constraints
                            dep_name = re.split(r'[<>=]', dep)[0]
                            if dep_name:
                                dependencies.append(dep_name)
                    break

            return dependencies

        except ValueError as e:
            raise PackageManagerError(f"Invalid package name: {e}")
        except Exception as e:
            logger.error(f"Error getting dependencies: {e}")
            raise PackageManagerError(f"Failed to get dependencies: {e}")

    def get_installed_package_names(self) -> Set[str]:
        """
        Get set of installed package names.

        Returns:
            Set of package names

        Raises:
            PackageManagerError: If getting packages fails
        """
        if self._installed_names_cache is not None:
            return self._installed_names_cache

        try:
            result = SecureSubprocess.run_pacman(
                ["-Qq"],
                capture_output=True,
                text=True,
                check=False,
                timeout=10
            )

            if result.returncode != 0:
                error_msg = result.stderr.strip() if result.stderr else "Unknown error"
                raise PackageManagerError(f"Failed to get package names: {error_msg}")

            package_names = set()
            for line in result.stdout.strip().split('\n'):
                if line:
                    package_names.add(line.strip())

            self._installed_names_cache = package_names
            logger.debug(f"Found {len(package_names)} installed package names")
            return package_names

        except Exception as e:
            logger.error(f"Error getting package names: {e}")
            raise PackageManagerError(f"Failed to get package names: {e}")

    def check_for_updates(self) -> List[PackageUpdate]:
        """
        Check for available package updates.

        Returns:
            List of PackageUpdate objects

        Raises:
            PackageManagerError: If checking for updates fails
        """
        try:
            # Use pacman -Qu instead of checkupdates to avoid bash dependency
            logger.info("Checking for package updates...")

            # Run pacman -Qu to check for updates
            result = SecureSubprocess.run_pacman(
                ["-Qu"],
                capture_output=True,
                text=True,
                check=False,
                timeout=30
            )

            if result.returncode not in [0, 1]:  # 1 means no updates
                error_msg = result.stderr.strip() if result.stderr else "Unknown error"
                logger.warning(f"Failed to check updates: {error_msg}")
                # Try without sync
                return []

            updates = []
            if result.stdout:
                for line in result.stdout.strip().split('\n'):
                    if line:
                        # pacman -Qu format: "package_name current_version -> new_version"
                        match = re.match(r'(\S+)\s+(\S+)\s+->\s+(\S+)', line)
                        if match:
                            updates.append(PackageUpdate(
                                name=match.group(1),
                                current_version=match.group(2),
                                new_version=match.group(3)
                            ))
                        else:
                            # Sometimes format is just "package_name new_version"
                            parts = line.split()
                            if len(parts) >= 2:
                                updates.append(PackageUpdate(
                                    name=parts[0],
                                    current_version='unknown',
                                    new_version=parts[1]
                                ))

            logger.info(f"Found {len(updates)} package updates")

            # Fetch size information for updates
            if updates:
                self._populate_update_sizes(updates)

            return updates

        except subprocess.CalledProcessError as e:
            logger.error(f"Error checking for updates: {e}")
            return []
        except Exception as e:
            logger.error(f"Unexpected error during update check: {e}")
            return []

    def sync_database(self) -> bool:
        """
        Sync pacman database by running pacman -Sy.

        Returns:
            True if sync was successful, False otherwise
        """
        try:
            logger.info("Syncing pacman database...")
            
            # Run pacman -Sy with sudo
            result = SecureSubprocess.run_pacman(
                ["-Sy"],
                require_sudo=True,
                capture_output=True,
                text=True,
                check=False,
                timeout=60  # Give it more time for database sync
            )

            if result.returncode == 0:
                logger.info("Database sync completed successfully")
                return True
            else:
                error_msg = result.stderr.strip() if result.stderr else "Unknown error"
                logger.error(f"Database sync failed: {error_msg}")
                return False

        except subprocess.TimeoutExpired:
            logger.error("Database sync timed out")
            return False
        except Exception as e:
            logger.error(f"Error during database sync: {e}")
            return False

    def _populate_update_sizes(self, updates: List[PackageUpdate]) -> None:
        """
        Populate size information for package updates.

        Args:
            updates: List of package updates to populate sizes for
        """
        logger.info(f"Fetching size information for {len(updates)} packages...")
        try:
            # Process in batches to avoid timeouts
            batch_size = 20
            total_fetched = 0

            for i in range(0, len(updates), batch_size):
                batch = updates[i:i + batch_size]
                package_names = [u.name for u in batch]

                # Query pacman for download sizes
                cmd = ['pacman', '-Si'] + package_names
                logger.debug(f"Fetching sizes for batch {i // batch_size + 1} ({len(package_names)} packages)")

                try:
                    result = SecureSubprocess.run(
                        cmd,
                        capture_output=True,
                        text=True,
                        check=False,
                        timeout=10  # Shorter timeout per batch
                    )

                    if result.returncode == 0:
                        lines = result.stdout.strip().split('\n')
                        current_package = None
                        current_download_size = None

                        for line in lines:
                            if line.startswith('Name'):
                                # If we have a previous package, save it
                                if current_package and current_download_size is not None:
                                    for update in batch:
                                        if update.name == current_package:
                                            update.size = current_download_size
                                            total_fetched += 1
                                            break

                                # Extract new package name
                                current_package = line.split(':', 1)[1].strip()
                                current_download_size = None

                            elif line.startswith('Download Size') and current_package:
                                # Extract download size
                                size_str = line.split(':', 1)[1].strip()
                                current_download_size = self._parse_size_string(size_str)

                            elif line.startswith('Installed Size') and current_package:
                                # Extract installed size
                                size_str = line.split(':', 1)[1].strip()
                                installed_size = self._parse_size_string(size_str)

                                # Find and update the corresponding update
                                for update in batch:
                                    if update.name == current_package:
                                        update.installed_size = installed_size
                                        break

                        # Don't forget the last package
                        if current_package and current_download_size is not None:
                            for update in batch:
                                if update.name == current_package:
                                    update.size = current_download_size
                                    total_fetched += 1
                                    break

                    else:
                        logger.debug(f"Batch {i // batch_size + 1} failed: {result.stderr}")

                except Exception as e:
                    logger.debug(f"Error processing batch {i // batch_size + 1}: {e}")
                    continue

            logger.info(f"Successfully fetched size information for {total_fetched} packages")

        except Exception as e:
            logger.warning(f"Error fetching package sizes: {e}")

    def _parse_size_string(self, size_str: str) -> Optional[int]:
        """
        Parse pacman size string to bytes.

        Args:
            size_str: Size string like "1.5 MiB" or "256.0 KiB" or "1,5 MiB"

        Returns:
            Size in bytes or None if parsing fails
        """
        try:
            # Remove any trailing comments
            parts = size_str.strip().split()
            if len(parts) < 2:
                return None

            number_str = parts[0]
            unit = parts[1]

            # Handle comma as decimal separator (European locale)
            number_str = number_str.replace(',', '.')

            number = float(number_str)

            # Convert to bytes based on unit
            unit = unit.upper()
            if unit in ['B', 'BYTES']:
                return int(number)
            elif unit in ['KIB', 'KB', 'K']:
                return int(number * 1024)
            elif unit in ['MIB', 'MB', 'M']:
                return int(number * 1024 * 1024)
            elif unit in ['GIB', 'GB', 'G']:
                return int(number * 1024 * 1024 * 1024)
            else:
                logger.warning(f"Unknown size unit: {unit}")
                return None

        except (ValueError, IndexError) as e:
            logger.warning(f"Could not parse size string '{size_str}': {e}")
            return None

    def get_package_info(self, package_name: str) -> Optional[str]:
        """
        Get detailed information about a package.

        Args:
            package_name: Name of the package

        Returns:
            Package information string or None if not found

        Raises:
            PackageManagerError: If getting package info fails
        """
        # Validate package name
        if not validate_package_name(package_name):
            raise PackageManagerError(f"Invalid package name: {package_name}")

        try:
            # Sanitize package name
            safe_name = SecureSubprocess.sanitize_package_name(package_name)

            # Try installed packages first
            result = SecureSubprocess.run_pacman(
                ["-Qi", safe_name],
                capture_output=True,
                text=True,
                check=False,
                timeout=10
            )

            if result.returncode == 0:
                return result.stdout

            # Try repository packages
            result = SecureSubprocess.run_pacman(
                ["-Si", safe_name],
                capture_output=True,
                text=True,
                check=False,
                timeout=10
            )

            if result.returncode == 0:
                return result.stdout

            logger.info(f"Package not found: {package_name}")
            return None

        except ValueError as e:
            raise PackageManagerError(f"Invalid package name: {e}")
        except Exception as e:
            logger.error(f"Error getting package info: {e}")
            raise PackageManagerError(f"Failed to get package info: {e}")

    def is_package_installed(self, package_name: str) -> bool:
        """
        Check if a package is installed.

        Args:
            package_name: Name of the package

        Returns:
            True if package is installed, False otherwise

        Raises:
            PackageManagerError: If checking fails
        """
        # Validate package name
        if not validate_package_name(package_name):
            raise PackageManagerError(f"Invalid package name: {package_name}")

        try:
            # Sanitize package name
            safe_name = SecureSubprocess.sanitize_package_name(package_name)

            result = SecureSubprocess.run_pacman(
                ["-Q", safe_name],
                capture_output=True,
                text=True,
                check=False,
                timeout=5
            )

            return result.returncode == 0

        except ValueError as e:
            raise PackageManagerError(f"Invalid package name: {e}")
        except Exception as e:
            logger.error(f"Error checking if package installed: {e}")
            raise PackageManagerError(f"Failed to check if package installed: {e}")

    def get_package_files(self, package_name: str) -> List[str]:
        """
        Get list of files provided by a package.

        Args:
            package_name: Name of the package

        Returns:
            List of file paths

        Raises:
            PackageManagerError: If getting files fails
        """
        # Validate package name
        if not validate_package_name(package_name):
            raise PackageManagerError(f"Invalid package name: {package_name}")

        try:
            # Sanitize package name
            safe_name = SecureSubprocess.sanitize_package_name(package_name)

            result = SecureSubprocess.run_pacman(
                ["-Ql", safe_name],
                capture_output=True,
                text=True,
                check=False,
                timeout=10
            )

            if result.returncode != 0:
                error_msg = result.stderr.strip() if result.stderr else "Package not found"
                raise PackageManagerError(f"Failed to get package files: {error_msg}")

            files = []
            for line in result.stdout.strip().split('\n'):
                if line:
                    # Format: package_name /path/to/file
                    parts = line.split(' ', 1)
                    if len(parts) == 2:
                        files.append(parts[1])

            return files

        except ValueError as e:
            raise PackageManagerError(f"Invalid package name: {e}")
        except Exception as e:
            logger.error(f"Error getting package files: {e}")
            raise PackageManagerError(f"Failed to get package files: {e}")

    def search_packages(self, query: str) -> List[Dict[str, str]]:
        """
        Search for packages in repositories.

        Args:
            query: Search query

        Returns:
            List of matching packages

        Raises:
            PackageManagerError: If search fails
        """
        try:
            result = SecureSubprocess.run_pacman(
                ["-Ss", query],
                capture_output=True,
                text=True,
                check=False,
                timeout=30
            )

            if result.returncode not in [0, 1]:  # 1 means no results
                error_msg = result.stderr.strip() if result.stderr else "Unknown error"
                raise PackageManagerError(f"Search failed: {error_msg}")

            packages = []
            lines = result.stdout.strip().split('\n')
            i = 0
            while i < len(lines):
                if lines[i].startswith((' ', '\t')):
                    # Description line
                    i += 1
                    continue

                # Package line: repo/name version
                match = re.match(r'(\S+)/(\S+)\s+(\S+)', lines[i])
                if match:
                    package = {
                        'repository': match.group(1),
                        'name': match.group(2),
                        'version': match.group(3),
                        'description': ''
                    }

                    # Next line should be description
                    if i + 1 < len(lines) and lines[i + 1].startswith((' ', '\t')):
                        package['description'] = lines[i + 1].strip()

                    packages.append(package)

                i += 1

            logger.info(f"Found {len(packages)} packages matching '{query}'")
            return packages

        except Exception as e:
            logger.error(f"Error searching packages: {e}")
            raise PackageManagerError(f"Package search failed: {e}")

    def get_package_size(self, package_name: str) -> Optional[int]:
        """
        Get the installed size of a package in bytes.

        Args:
            package_name: Name of the package

        Returns:
            Size in bytes or None if not found

        Raises:
            PackageManagerError: If getting size fails
        """
        info = self.get_package_info(package_name)
        if not info:
            return None

        # Parse size from info
        for line in info.split('\n'):
            if line.startswith('Installed Size'):
                size_str = line.split(':', 1)[1].strip()
                # Convert to bytes (handle units like KiB, MiB, etc)
                return self._parse_size_to_bytes(size_str)

        return None

    def _parse_size_to_bytes(self, size_str: str) -> int:
        """Convert size string to bytes."""
        units = {
            'B': 1,
            'KiB': 1024,
            'MiB': 1024**2,
            'GiB': 1024**3,
            'TiB': 1024**4
        }

        parts = size_str.split()
        if len(parts) == 2:
            try:
                value = float(parts[0])
                unit = parts[1]
                return int(value * units.get(unit, 1))
            except (ValueError, KeyError):
                pass

        return 0
