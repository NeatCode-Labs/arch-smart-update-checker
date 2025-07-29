"""Tests for distribution detection and feed management."""

import unittest
from unittest.mock import Mock, patch, mock_open
import tempfile
import json
import os
from pathlib import Path

from src.utils.distribution import DistributionDetector
from src.config import Config
from src.models import FeedConfig


class TestDistributionDetection(unittest.TestCase):
    """Test distribution detection functionality."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.detector = DistributionDetector()
    
    def test_parse_os_release_manjaro(self):
        """Test parsing Manjaro os-release file."""
        manjaro_os_release = '''NAME="Manjaro Linux"
ID=manjaro
ID_LIKE=arch
BUILD_ID=rolling
ANSI_COLOR="32;1;24;144;200"
HOME_URL="https://manjaro.org/"
LOGO=manjarolinux'''
        
        with patch('builtins.open', mock_open(read_data=manjaro_os_release)):
            result = self.detector._read_os_release()
            self.assertEqual(result, "manjaro")
    
    def test_parse_os_release_endeavouros(self):
        """Test parsing EndeavourOS os-release file."""
        endeavour_os_release = '''NAME="EndeavourOS"
PRETTY_NAME="EndeavourOS"
ID=endeavouros
ID_LIKE=arch
BUILD_ID=rolling
ANSI_COLOR="38;2;23;147;209"
HOME_URL="https://endeavouros.com"
LOGO=endeavouros'''
        
        with patch('builtins.open', mock_open(read_data=endeavour_os_release)):
            result = self.detector._read_os_release()
            self.assertEqual(result, "endeavouros")
    
    def test_parse_os_release_arch(self):
        """Test parsing base Arch os-release file."""
        arch_os_release = '''NAME="Arch Linux"
PRETTY_NAME="Arch Linux"
ID=arch
BUILD_ID=rolling
ANSI_COLOR="38;2;23;147;209"
HOME_URL="https://archlinux.org/"
LOGO=archlinux-logo'''
        
        with patch('builtins.open', mock_open(read_data=arch_os_release)):
            result = self.detector._read_os_release()
            self.assertEqual(result, "arch")
    
    def test_get_distribution_feeds_manjaro(self):
        """Test that Manjaro gets both announcement feeds."""
        feeds = self.detector.get_distribution_feeds("manjaro")
        
        self.assertEqual(len(feeds), 2)
        
        # Check first feed
        self.assertEqual(feeds[0]["name"], "Manjaro Announcements")
        self.assertEqual(feeds[0]["url"], "https://forum.manjaro.org/c/announcements.rss")
        self.assertEqual(feeds[0]["enabled"], True)
        
        # Check second feed
        self.assertEqual(feeds[1]["name"], "Manjaro Stable Updates")
        self.assertEqual(feeds[1]["url"], "https://forum.manjaro.org/c/announcements/stable-updates.rss")
        self.assertEqual(feeds[1]["enabled"], True)
    
    def test_get_distribution_feeds_endeavouros(self):
        """Test that EndeavourOS gets its news feed."""
        feeds = self.detector.get_distribution_feeds("endeavouros")
        
        self.assertEqual(len(feeds), 1)
        self.assertEqual(feeds[0]["name"], "EndeavourOS News")
        self.assertEqual(feeds[0]["url"], "https://endeavouros.com/feed/")
        self.assertEqual(feeds[0]["enabled"], True)
    
    def test_get_distribution_feeds_arch(self):
        """Test that base Arch gets no extra feeds."""
        feeds = self.detector.get_distribution_feeds("arch")
        self.assertEqual(len(feeds), 0)
    
    @patch('os.path.exists')
    @patch('subprocess.run')
    def test_package_based_detection_manjaro(self, mock_run, mock_exists):
        """Test fallback package-based detection for Manjaro."""
        # Simulate os-release reporting "arch"
        with patch.object(self.detector, '_read_os_release', return_value="arch"):
            # Simulate manjaro-release package exists
            mock_run.return_value = Mock(returncode=0)
            
            result = self.detector.detect_distribution()
            self.assertEqual(result, "manjaro")
            
            # Verify it checked for manjaro packages
            mock_run.assert_any_call(
                ["pacman", "-Q", "manjaro-release"],
                capture_output=True,
                text=True,
                check=True
            )


class TestFirstRunFeedBehavior(unittest.TestCase):
    """Test first-run feed addition behavior."""
    
    def setUp(self):
        """Set up test environment."""
        self.temp_dir = tempfile.mkdtemp()
        self.config_file = os.path.join(self.temp_dir, "config.json")
    
    def tearDown(self):
        """Clean up test environment."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    @patch('src.utils.distribution.DistributionDetector.detect_distribution')
    def test_first_run_manjaro_feeds(self, mock_detect):
        """Test that Manjaro feeds are added on first run."""
        mock_detect.return_value = "manjaro"
        
        # Create config (simulating first run)
        config = Config(self.config_file)
        
        # Check that all 4 feeds are present (2 Arch + 2 Manjaro)
        feeds = config._app_config.feeds
        self.assertEqual(len(feeds), 4)
        
        # Check feed URLs
        feed_urls = [feed.url for feed in feeds]
        self.assertIn("https://archlinux.org/feeds/news/", feed_urls)
        self.assertIn("https://security.archlinux.org/advisory/feed.atom", feed_urls)
        self.assertIn("https://forum.manjaro.org/c/announcements.rss", feed_urls)
        self.assertIn("https://forum.manjaro.org/c/announcements/stable-updates.rss", feed_urls)
    
    @patch('src.utils.distribution.DistributionDetector.detect_distribution')
    def test_first_run_endeavouros_feeds(self, mock_detect):
        """Test that EndeavourOS feed is added on first run."""
        mock_detect.return_value = "endeavouros"
        
        # Create config (simulating first run)
        config = Config(self.config_file)
        
        # Check that all 3 feeds are present (2 Arch + 1 EndeavourOS)
        feeds = config._app_config.feeds
        self.assertEqual(len(feeds), 3)
        
        # Check feed URLs
        feed_urls = [feed.url for feed in feeds]
        self.assertIn("https://archlinux.org/feeds/news/", feed_urls)
        self.assertIn("https://security.archlinux.org/advisory/feed.atom", feed_urls)
        self.assertIn("https://endeavouros.com/feed/", feed_urls)
    
    @patch('src.utils.distribution.DistributionDetector.detect_distribution')
    def test_subsequent_run_no_feed_addition(self, mock_detect):
        """Test that feeds are not re-added on subsequent runs."""
        mock_detect.return_value = "manjaro"
        
        # First run - create config with Manjaro feeds
        config1 = Config(self.config_file)
        config1.save_config()
        
        # Manually remove one Manjaro feed to simulate user preference
        config_data = json.loads(Path(self.config_file).read_text())
        # Remove the Manjaro Stable Updates feed
        config_data["feeds"] = [
            feed for feed in config_data["feeds"] 
            if feed["url"] != "https://forum.manjaro.org/c/announcements/stable-updates.rss"
        ]
        Path(self.config_file).write_text(json.dumps(config_data, indent=2))
        
        # Second run - feeds should not be re-added
        config2 = Config(self.config_file)
        
        # Check that the removed feed was not re-added
        feeds = config2._app_config.feeds
        feed_urls = [feed.url for feed in feeds]
        self.assertNotIn("https://forum.manjaro.org/c/announcements/stable-updates.rss", feed_urls)
        
        # Should still have only 3 feeds (2 Arch + 1 Manjaro that wasn't removed)
        self.assertEqual(len(feeds), 3)
    
    @patch('src.utils.distribution.DistributionDetector.detect_distribution')
    def test_distribution_change_updates_config(self, mock_detect):
        """Test that distribution field is updated when system changes."""
        # First run as Arch
        mock_detect.return_value = "arch"
        config1 = Config(self.config_file)
        config1.save_config()
        
        # Verify it saved as arch
        config_data = json.loads(Path(self.config_file).read_text())
        self.assertEqual(config_data["distribution"], "arch")
        
        # Second run as Manjaro (simulating system change)
        mock_detect.return_value = "manjaro"
        config2 = Config(self.config_file)
        
        # Verify distribution was updated but no feeds added (not first run)
        self.assertEqual(config2._app_config.distribution, "manjaro")
        feeds = config2._app_config.feeds
        # Should still have only 2 Arch feeds since it's not first run
        self.assertEqual(len(feeds), 2)


if __name__ == '__main__':
    unittest.main()