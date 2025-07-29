"""
Distribution detection utilities.
"""

# SPDX-License-Identifier: GPL-3.0-or-later

import os
import platform
import subprocess
from typing import Dict, List, Optional


class DistributionDetector:
    """Detects the current Linux distribution."""

    def __init__(self) -> None:
        """Initialize the distribution detector."""
        self.distribution_files = {
            "arch": ["/etc/arch-release"],
            "manjaro": ["/etc/manjaro-release"],
            "endeavouros": ["/etc/endeavouros-release"],
            "garuda": ["/etc/garuda-release"],
            "arcolinux": ["/etc/arcolinux-release"],
            "artix": ["/etc/artix-release"],
            "parabola": ["/etc/parabola-release"],
            "hyperbola": ["/etc/hyperbola-release"],
        }
        self.distribution = self.detect_distribution()
        self.version = self._detect_version()
        self.arch = self._detect_architecture()
        self.package_manager = self._detect_package_manager()

    def detect_distribution(self) -> str:
        """
        Detect the current Linux distribution.
        
        Returns:
            Distribution name (lowercase) or 'unknown'
        """
        from ..utils.logger import get_logger
        logger = get_logger(__name__)
        
        # First try to read /etc/os-release as it's the most reliable
        os_release_distro = self._read_os_release()
        if os_release_distro is not None:
            logger.debug(f"Detected {os_release_distro} via /etc/os-release")
            # Additional package checks for edge cases
            if os_release_distro == "arch":
                # Check for derivative-specific packages
                if self._check_package_exists("manjaro-release") or self._check_package_exists("manjaro-system"):
                    logger.info("Detected Manjaro via package check (was detected as arch)")
                    return "manjaro"
                if self._check_package_exists("endeavouros-mirrorlist") or self._check_package_exists("eos-hooks"):
                    logger.info("Detected EndeavourOS via package check (was detected as arch)")
                    return "endeavouros"
            return os_release_distro
        
        # Fallback: Check distribution-specific files
        # Check derivatives first before base Arch
        derivative_order = ["manjaro", "endeavouros", "garuda", "arcolinux", "artix", "parabola", "hyperbola"]
        for distro in derivative_order:
            if distro in self.distribution_files:
                for file_path in self.distribution_files[distro]:
                    if os.path.exists(file_path):
                        logger.debug(f"Detected {distro} via {file_path}")
                        return distro
        
        # Finally check for base Arch
        if "arch" in self.distribution_files:
            for file_path in self.distribution_files["arch"]:
                if os.path.exists(file_path):
                    logger.debug(f"Detected arch via {file_path}")
                    return "arch"

        # Platform detection fallback
        system = platform.system().lower()
        if system != "linux":
            return "unknown"

        logger.warning("Could not detect distribution, defaulting to 'unknown'")
        return "unknown"

    def _read_os_release(self) -> Optional[str]:
        """
        Read distribution from /etc/os-release.

        Returns:
            Distribution name or None
        """
        try:
            with open("/etc/os-release", "r", encoding="utf-8") as f:
                content = f.read()

            # Parse all fields into a dictionary
            os_release_data = {}
            for line in content.split("\n"):
                if "=" in line and not line.strip().startswith("#"):
                    key, value = line.split("=", 1)
                    key = key.strip()
                    value = value.strip().strip('"')
                    os_release_data[key] = value

            # Check ID field first
            if "ID" in os_release_data:
                distro = os_release_data["ID"].lower()
                # Check for known derivatives
                if distro in ["manjaro", "endeavouros", "garuda", "artix", "parabola", "hyperbola"]:
                    return distro
                elif distro == "arch":
                    # If identified as arch, check ID_LIKE and NAME to detect derivatives
                    if "ID_LIKE" in os_release_data and "arch" in os_release_data["ID_LIKE"]:
                        # Check NAME field for derivative names
                        if "NAME" in os_release_data:
                            name_lower = os_release_data["NAME"].lower()
                            for derivative in ["manjaro", "endeavouros", "garuda", "artix"]:
                                if derivative in name_lower:
                                    return derivative
                    return "arch"

            # Fallback to NAME field
            if "NAME" in os_release_data:
                return self._normalize_distro_name(os_release_data["NAME"])

        except (OSError, UnicodeDecodeError):
            pass

        return None

    def _normalize_distro_name(self, name: str) -> str:
        """
        Normalize distribution name.

        Args:
            name: Raw distribution name

        Returns:
            Normalized distribution name
        """
        name_lower = name.lower()

        if "arch" in name_lower:
            return "arch"
        elif "manjaro" in name_lower:
            return "manjaro"
        elif "endeavour" in name_lower:
            return "endeavouros"
        elif "garuda" in name_lower:
            return "garuda"
        elif "artix" in name_lower:
            return "artix"
        elif "parabola" in name_lower:
            return "parabola"
        elif "hyperbola" in name_lower:
            return "hyperbola"

        return "unknown"

    def get_distribution_feeds(self, distro: str) -> List[Dict[str, object]]:
        """
        Get distribution-specific RSS feeds.

        Args:
            distro: Distribution name

        Returns:
            List of feed configurations
        """
        feeds = []

        if distro == "manjaro":
            feeds.extend([
                {
                    "name": "Manjaro Announcements",
                    "url": "https://forum.manjaro.org/c/announcements.rss",
                    "priority": 2,
                    "type": "news",
                    "enabled": True,
                },
                {
                    "name": "Manjaro Stable Updates", 
                    "url": "https://forum.manjaro.org/c/announcements/stable-updates.rss",
                    "priority": 2,
                    "type": "news",
                    "enabled": True,
                }
            ])
        elif distro == "endeavouros":
            feeds.append(
                {
                    "name": "EndeavourOS News",
                    "url": "https://endeavouros.com/feed/",
                    "priority": 2,
                    "type": "news",
                    "enabled": True,
                }
            )

        return feeds

    def is_arch_based(self, distro: str) -> bool:
        """
        Check if distribution is Arch-based.

        Args:
            distro: Distribution name

        Returns:
            True if Arch-based
        """
        arch_based = {
            "arch",
            "manjaro",
            "endeavouros",
            "garuda",
            "artix",
            "parabola",
            "hyperbola",
        }
        return distro in arch_based

    def _detect_version(self) -> str:
        """Detect the distribution version."""
        version = self._read_file("/etc/os-release", "VERSION_ID")
        if version is None:
            version = self._read_file("/etc/arch-release")
        if version is None:
            version = "unknown"
        return str(version)

    def get_package_info(self) -> List[Dict[str, str]]:
        """Get information about installed packages."""
        try:
            result = subprocess.run(
                ["pacman", "-Q"], capture_output=True, text=True, check=True
            )
            packages: List[Dict[str, str]] = []
            for line in result.stdout.strip().split("\n"):
                if line:
                    parts = line.split()
                    if len(parts) >= 2:
                        packages.append(
                            {"name": str(parts[0]), "version": str(parts[1])}
                        )
            return packages
        except (subprocess.CalledProcessError, FileNotFoundError):
            return []

    def _detect_architecture(self) -> str:
        """Detect the system architecture."""
        return platform.machine()

    def _detect_package_manager(self) -> str:
        """Detect the package manager."""
        if self.is_arch_based(self.distribution):
            return "pacman"
        return "unknown"

    def _read_file(self, filepath: str, key: Optional[str] = None) -> Optional[str]:
        """Read a file and optionally extract a key-value."""
        try:
            with open(filepath, "r") as f:
                content = f.read().strip()
                if key:
                    for line in content.split("\n"):
                        if line.startswith(f"{key}="):
                            return line.split("=", 1)[1].strip('"')
                return content
        except (IOError, OSError):
            return None

    def _check_package_exists(self, package_name: str) -> bool:
        """
        Check if a package is installed.

        Args:
            package_name: Name of the package to check.

        Returns:
            True if the package is installed, False otherwise.
        """
        try:
            subprocess.run(
                ["pacman", "-Q", package_name],
                capture_output=True,
                text=True,
                check=True,
            )
            return True
        except subprocess.CalledProcessError:
            return False
