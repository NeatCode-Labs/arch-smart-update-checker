"""
Unit tests for package pattern matching.
"""

import unittest

from src.utils.patterns import PackagePatternMatcher


class TestPackagePatternMatcher(unittest.TestCase):
    """Test package pattern matching functionality."""

    def setUp(self):
        """Set up test fixtures."""
        self.matcher = PackagePatternMatcher()
        # Common set of installed packages for testing
        self.installed_packages = {
            'firefox', 'chromium', 'nvidia', 'nvidia-utils', 'linux',
            'python', 'python-pip', 'gcc', 'glibc', 'vim', 'neovim',
            'lib32-glibc', 'systemd', 'grub', 'openssl', 'openssh',
            'pacman', 'git', 'base', 'base-devel', 'xorg-server',
            'python_example', 'package-with-dashes', 'package123'
        }

    def test_extract_package_names_basic(self):
        """Test basic package name extraction."""
        text = "Update firefox to version 100.0"
        packages = self.matcher.extract_package_names(text, self.installed_packages)
        self.assertIn("firefox", packages)

    def test_extract_package_names_with_versions(self):
        """Test extraction with version numbers."""
        text = "linux 5.10.0-1 and nvidia 470.86-1 have updates"
        packages = self.matcher.extract_package_names(text, self.installed_packages)
        self.assertIn("linux", packages)
        self.assertIn("nvidia", packages)

    def test_extract_package_names_with_arch(self):
        """Test extraction with architecture suffixes."""
        text = "Installing python for x86_64"
        packages = self.matcher.extract_package_names(text, self.installed_packages)
        self.assertIn("python", packages)

    def test_extract_package_names_mixed(self):
        """Test extraction from mixed content."""
        text = "Critical: Update glibc, gcc, and vim immediately!"
        packages = self.matcher.extract_package_names(text, self.installed_packages)
        self.assertIn("glibc", packages)
        self.assertIn("gcc", packages)
        self.assertIn("vim", packages)

    def test_extract_package_names_no_packages(self):
        """Test extraction when no packages are mentioned."""
        text = "This is just regular text without any package names"
        packages = self.matcher.extract_package_names(text, self.installed_packages)
        self.assertEqual(len(packages), 0)

    def test_extract_package_names_empty_string(self):
        """Test extraction from empty string."""
        packages = self.matcher.extract_package_names("", self.installed_packages)
        self.assertEqual(len(packages), 0)

    def test_extract_package_names_none(self):
        """Test extraction from None."""
        packages = self.matcher.extract_package_names(None, self.installed_packages)  # type: ignore
        self.assertEqual(len(packages), 0)

    def test_extract_package_names_special_characters(self):
        """Test extraction of packages with special characters."""
        text = "Updates for python-pip and lib32-glibc"
        packages = self.matcher.extract_package_names(text, self.installed_packages)
        self.assertIn("python-pip", packages)
        self.assertIn("lib32-glibc", packages)

    def test_extract_package_names_multiple_occurrences(self):
        """Test that duplicate mentions return unique packages."""
        text = "firefox update: firefox version 100. Install firefox now!"
        packages = self.matcher.extract_package_names(text, self.installed_packages)
        # Should return set, so firefox appears only once
        package_list = list(packages)
        self.assertEqual(package_list.count("firefox"), 1)

    def test_extract_package_names_with_numbers(self):
        """Test extraction of packages with numbers."""
        text = "package123 needs updating"
        packages = self.matcher.extract_package_names(text, self.installed_packages)
        self.assertIn("package123", packages)

    def test_extract_package_names_quoted(self):
        """Test extraction of quoted package names."""
        text = 'Install "firefox" and "chromium" browsers'
        packages = self.matcher.extract_package_names(text, self.installed_packages)
        self.assertIn("firefox", packages)
        self.assertIn("chromium", packages)

    def test_extract_package_names_backticks(self):
        """Test extraction of backtick-quoted package names."""
        text = "Run `pacman -S vim` to install"
        packages = self.matcher.extract_package_names(text, self.installed_packages)
        self.assertIn("vim", packages)
        self.assertIn("pacman", packages)

    def test_is_package_mentioned(self):
        """Test checking if a specific package is mentioned."""
        text = "The firefox browser needs an update"
        self.assertTrue(self.matcher.is_package_mentioned(text, "firefox"))
        self.assertFalse(self.matcher.is_package_mentioned(text, "chromium"))

    def test_find_affected_packages(self):
        """Test finding affected packages (legacy method)."""
        text = "Security update for firefox and nvidia drivers"
        installed = {"firefox", "nvidia-utils", "chromium"}
        affected = self.matcher.find_affected_packages(text, installed)
        
        self.assertIn("firefox", affected)
        # nvidia-utils is installed but only 'nvidia' is mentioned
        # The new implementation requires exact matches
        self.assertNotIn("nvidia-utils", affected)

    def test_add_custom_patterns(self):
        """Test adding custom patterns."""
        # Add a custom pattern for AUR packages
        self.matcher.add_custom_patterns([r'aur/([a-z0-9\-]+)'])
        text = "Install aur/yay and aur/paru"
        # For this test we need to have yay and paru in installed packages
        installed = {"yay", "paru"}
        packages = self.matcher.extract_package_names(text, installed)
        # The pattern extracts the names, but they need to be in installed
        self.assertIn("yay", packages)
        self.assertIn("paru", packages)

    def test_case_insensitive_matching(self):
        """Test case-insensitive package matching."""
        text = "Update FIREFOX and NVIDIA"
        packages = self.matcher.extract_package_names(text, self.installed_packages)
        self.assertIn("firefox", packages)
        self.assertIn("nvidia", packages)

    def test_generic_names_excluded(self):
        """Test that generic names are excluded."""
        text = "This package update is critical"
        # Even though 'package' and 'update' might match patterns,
        # they should be excluded as generic
        packages = self.matcher.extract_package_names(text, self.installed_packages)
        self.assertNotIn("package", packages)
        self.assertNotIn("update", packages)

    def test_package_with_dashes(self):
        """Test package names with dashes."""
        text = "Update package-with-dashes to latest version"
        packages = self.matcher.extract_package_names(text, self.installed_packages)
        self.assertIn("package-with-dashes", packages)

    def test_package_with_underscores(self):
        """Test package names with underscores."""
        text = "python_example needs attention"
        packages = self.matcher.extract_package_names(text, self.installed_packages)
        self.assertIn("python_example", packages)

    def test_not_installed_packages_ignored(self):
        """Test that packages not in installed set are ignored."""
        text = "Update firefox and notinstalled"
        packages = self.matcher.extract_package_names(text, self.installed_packages)
        self.assertIn("firefox", packages)
        self.assertNotIn("notinstalled", packages)

    def test_extract_version_info(self):
        """Test extraction of version information."""
        text = "firefox >= 100.0 and python < 3.11"
        version_info = self.matcher.extract_version_info(text)
        
        # Should find version constraints
        self.assertTrue(any(pkg == "firefox" and ">=100.0" in ver 
                          for pkg, ver in version_info))
        self.assertTrue(any(pkg == "python" and "<3.11" in ver 
                          for pkg, ver in version_info))

    def test_invalid_custom_pattern(self):
        """Test handling of invalid regex patterns."""
        # Add invalid pattern - should be ignored
        self.matcher.add_custom_patterns(["[invalid(regex"])
        # Should not raise exception, just skip the invalid pattern
        text = "firefox update"
        packages = self.matcher.extract_package_names(text, self.installed_packages)
        self.assertIn("firefox", packages)


if __name__ == "__main__":
    unittest.main()
