"""Simple test for news fetcher to avoid hanging issues."""

import unittest
from unittest.mock import Mock, patch

from src.news_fetcher import NewsFetcher
from src.utils.cache import CacheManager


class TestNewsFetcherSimple(unittest.TestCase):
    """Simplified news fetcher tests."""

    def setUp(self):
        """Set up test fixtures."""
        self.mock_cache = Mock(spec=CacheManager)
        self.mock_cache.get.return_value = None
        
        # Patch the entire fetch_feed method to avoid network calls
        self.fetch_patcher = patch.object(NewsFetcher, 'fetch_feed')
        self.mock_fetch = self.fetch_patcher.start()
        
        self.news_fetcher = NewsFetcher(self.mock_cache)

    def tearDown(self):
        """Clean up."""
        self.fetch_patcher.stop()

    def test_initialization(self):
        """Test news fetcher initialization."""
        self.assertIsNotNone(self.news_fetcher.session)
        self.assertEqual(self.news_fetcher.max_news_age_days, 30)

    def test_sanitize_content(self):
        """Test content sanitization."""
        content = "<p>Test <b>content</b> with <script>alert('xss')</script> tags</p>"
        sanitized = self.news_fetcher._sanitize_content(content)
        self.assertNotIn("<p>", sanitized)
        self.assertNotIn("<script>", sanitized)
        self.assertIn("Test", sanitized)
        self.assertIn("content", sanitized)

    def test_validate_feed_domain_trusted(self):
        """Test feed domain validation with trusted domain."""
        trusted_urls = [
            "https://archlinux.org/feeds/news/",
            "https://security.archlinux.org/feed.atom",
            "http://localhost/feed.rss",
        ]
        
        for url in trusted_urls:
            with self.subTest(url=url):
                self.assertTrue(self.news_fetcher._validate_feed_domain(url))

    def test_validate_feed_domain_invalid(self):
        """Test feed domain validation with invalid URL."""
        # Invalid URLs return False
        for url in ["", "not-a-url", "ftp://example.com/feed"]:
            with self.subTest(url=url):
                self.assertFalse(self.news_fetcher._validate_feed_domain(url))
        

if __name__ == "__main__":
    unittest.main() 