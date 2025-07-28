"""Integration tests for real pacman operations.

These tests are skipped in CI and only run in development environments
where pacman is available.
"""

# SPDX-License-Identifier: GPL-3.0-or-later

import unittest
import os
from unittest.mock import patch, Mock
import subprocess
from unittest import skipIf

from src.package_manager import PackageManager
from src.utils.pacman_runner import PacmanRunner
from src.checker import UpdateChecker


# Skip these tests in CI environment or if pacman is not available
IN_CI = os.environ.get('CI', 'false').lower() == 'true'
HAS_PACMAN = subprocess.run(['which', 'pacman'], capture_output=True).returncode == 0


@skipIf(IN_CI or not HAS_PACMAN, "Integration tests only run in development environments with pacman")
class TestPacmanIntegration(unittest.TestCase):
    """Integration tests with real pacman commands."""

    def setUp(self):
        """Set up test fixtures."""
        self.pkg_manager = PackageManager()

    def test_real_pacman_version(self):
        """Test getting real pacman version."""
        try:
            result = subprocess.run(
                ['pacman', '--version'],
                capture_output=True,
                text=True,
                check=True
            )
            self.assertIn('Pacman', result.stdout)
            self.assertEqual(result.returncode, 0)
        except subprocess.CalledProcessError:
            self.skipTest("pacman not available")

    def test_real_checkupdates(self):
        """Test real checkupdates command (read-only)."""
        try:
            # This is safe as it only checks, doesn't modify
            result = subprocess.run(
                ['checkupdates'],
                capture_output=True,
                text=True,
                check=False  # May return 2 if no updates
            )
            # Return code 0 = updates available, 2 = no updates
            self.assertIn(result.returncode, [0, 2])
        except FileNotFoundError:
            self.skipTest("checkupdates not available")

    def test_real_package_info(self):
        """Test getting info for a real package."""
        # Use a package that's almost certainly installed
        test_packages = ['pacman', 'glibc', 'bash']
        
        for pkg in test_packages:
            try:
                result = subprocess.run(
                    ['pacman', '-Qi', pkg],
                    capture_output=True,
                    text=True,
                    check=False
                )
                if result.returncode == 0:
                    self.assertIn('Name', result.stdout)
                    self.assertIn('Version', result.stdout)
                    return  # Success, test one package
            except subprocess.CalledProcessError:
                continue
        
        self.skipTest("No test packages found installed")

    def test_database_sync_time(self):
        """Test getting real database sync time."""
        sync_time = PacmanRunner.get_database_last_sync_time()
        
        if sync_time:
            # Just verify it returns a datetime
            from datetime import datetime
            self.assertIsInstance(sync_time, datetime)
        else:
            # It's OK if sync directory doesn't exist in test env
            self.assertIsNone(sync_time)

    def test_real_package_search(self):
        """Test searching for packages (read-only)."""
        try:
            result = subprocess.run(
                ['pacman', '-Ss', '^linux$'],
                capture_output=True,
                text=True,
                check=False
            )
            # Should find the linux package
            if result.returncode == 0:
                self.assertIn('linux', result.stdout.lower())
        except subprocess.CalledProcessError:
            self.skipTest("pacman search not available")

    def test_list_installed_packages(self):
        """Test listing installed packages."""
        try:
            result = subprocess.run(
                ['pacman', '-Q'],
                capture_output=True,
                text=True,
                check=True
            )
            lines = result.stdout.strip().split('\n')
            # Should have at least some packages installed
            self.assertGreater(len(lines), 10)
            
            # Each line should be "package version"
            for line in lines[:5]:  # Check first 5
                parts = line.split()
                self.assertGreaterEqual(len(parts), 2)
        except subprocess.CalledProcessError:
            self.skipTest("pacman -Q not available")

    def test_check_package_files(self):
        """Test checking package files (read-only)."""
        try:
            # Check files for pacman itself
            result = subprocess.run(
                ['pacman', '-Ql', 'pacman'],
                capture_output=True,
                text=True,
                check=True
            )
            # Should list files owned by pacman
            self.assertIn('/usr/bin/pacman', result.stdout)
        except subprocess.CalledProcessError:
            self.skipTest("pacman -Ql not available")


@skipIf(IN_CI, "Checker integration tests only run in development environments")
class TestUpdateCheckerIntegration(unittest.TestCase):
    """Integration tests for UpdateChecker with real data."""

    def setUp(self):
        """Set up test fixtures."""
        from src.config import Config
        self.config = Config()
        self.checker = UpdateChecker(self.config)

    @patch('src.package_manager.PackageManager.check_for_updates')
    @patch('src.news_fetcher.NewsFetcher.fetch_all_feeds')
    def test_real_update_check(self, mock_fetch_news, mock_check_updates):
        """Test update checking flow with mocked external calls."""
        # Mock package updates
        from src.models import PackageUpdate
        mock_updates = [
            PackageUpdate(name="linux", current_version="6.1.0", new_version="6.2.0", size=100000),
            PackageUpdate(name="firefox", current_version="100.0", new_version="101.0", size=50000)
        ]
        mock_check_updates.return_value = mock_updates
        
        # Mock news items
        from src.models import NewsItem, FeedType
        from datetime import datetime
        mock_news = [
            NewsItem(
                title='Important Update',
                link='https://archlinux.org/news/1',
                date=datetime(2024, 1, 1),
                content='Security update',
                source='Arch Linux News',
                priority=1,
                source_type=FeedType.NEWS,
                affected_packages={'linux'}
            )
        ]
        # Return NewsItem objects directly
        mock_fetch_news.return_value = mock_news
        
        # Run the check
        result = self.checker.check_updates()
        
        # Verify return type
        from src.models import UpdateCheckResult
        self.assertIsInstance(result, UpdateCheckResult)
        
        # Verify the mock data was processed correctly
        self.assertEqual(result.update_count, 2)
        self.assertEqual(len(result.updates), 2)
        self.assertEqual(result.updates[0].name, "linux")
        self.assertEqual(result.updates[1].name, "firefox")
        
        # Verify news
        self.assertEqual(result.news_count, 1)
        self.assertEqual(result.news_items[0].title, 'Important Update')




if __name__ == '__main__':
    # Only run if explicitly requested
    if os.environ.get('RUN_INTEGRATION_TESTS', False):
        unittest.main()
    else:
        print("Integration tests skipped. Set RUN_INTEGRATION_TESTS=1 to run.") 