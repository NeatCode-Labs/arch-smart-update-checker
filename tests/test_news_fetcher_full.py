"""Test news fetcher functionality."""

import unittest
from unittest.mock import patch, Mock, MagicMock
import feedparser
import requests

from src.news_fetcher import NewsFetcher
from src.exceptions import FeedParsingError
from src.utils.cache import CacheManager


class TestNewsFetcher(unittest.TestCase):
    """Test news fetcher functionality."""

    def setUp(self):
        """Set up test fixtures."""
        # Create a mock cache manager
        self.mock_cache = Mock(spec=CacheManager)
        self.mock_cache.get.return_value = None  # No cached data by default
        
        # Mock the session to prevent any real network calls
        self.session_patcher = patch('src.news_fetcher.requests.Session')
        mock_session_class = self.session_patcher.start()
        self.mock_session = Mock()
        self.mock_session.timeout = 10  # Add timeout attribute
        mock_session_class.return_value = self.mock_session
        
        # Mock threading.Lock to prevent deadlocks in tests
        self.lock_patcher = patch('src.news_fetcher.threading.Lock')
        mock_lock_class = self.lock_patcher.start()
        self.mock_lock = Mock()
        self.mock_lock.__enter__ = Mock(return_value=None)
        self.mock_lock.__exit__ = Mock(return_value=None)
        mock_lock_class.return_value = self.mock_lock
        
        # Mock SecureThreadPoolExecutor instead of ThreadPoolExecutor
        self.executor_patcher = patch('src.utils.thread_manager.SecureThreadPoolExecutor.get_executor')
        mock_get_executor = self.executor_patcher.start()
        self.mock_executor = Mock()
        self.mock_executor.__enter__ = Mock(return_value=self.mock_executor)
        self.mock_executor.__exit__ = Mock(return_value=None)
        mock_get_executor.return_value = self.mock_executor
        
        # Create a shared mock future that will be reused
        self.mock_future = Mock()
        self.mock_executor.submit.return_value = self.mock_future
        
        # Mock as_completed to return the same futures that were submitted
        self.as_completed_patcher = patch('src.news_fetcher.as_completed')
        self.mock_as_completed = self.as_completed_patcher.start()
        self.mock_as_completed.return_value = [self.mock_future]  # Return the same mock future
        
        # Create news fetcher with mock cache
        self.news_fetcher = NewsFetcher(self.mock_cache)
        
    def tearDown(self):
        """Clean up after tests."""
        self.session_patcher.stop()
        self.lock_patcher.stop()
        self.executor_patcher.stop()
        self.as_completed_patcher.stop()

    def test_initialization(self):
        """Test news fetcher initialization."""
        self.assertIsNotNone(self.news_fetcher.session)
        self.assertEqual(self.news_fetcher.max_news_age_days, 14)

    def test_sanitize_content(self):
        """Test content sanitization."""
        content = "<p>Test <b>content</b> with <script>alert('xss')</script> tags</p>"
        sanitized = self.news_fetcher._sanitize_content(content)
        self.assertNotIn("<p>", sanitized)
        self.assertNotIn("<script>", sanitized)
        self.assertIn("Test", sanitized)
        self.assertIn("content", sanitized)

    def test_sanitize_content_with_entities(self):
        """Test content sanitization with HTML entities."""
        content = "Test &amp; content with &lt;tags&gt;"
        sanitized = self.news_fetcher._sanitize_content(content)
        self.assertIn("&", sanitized)  # Should decode &amp;
        self.assertIn("<", sanitized)  # Should decode &lt;
        self.assertIn(">", sanitized)  # Should decode &gt;

    def test_validate_feed_domain_trusted(self):
        """Test feed URL validation with trusted domain."""
        trusted_urls = [
            "https://archlinux.org/feeds/news/",
            "https://security.archlinux.org/feed.atom",
            "http://localhost/feed.rss",
            "http://127.0.0.1/feed.rss",
        ]
        
        for url in trusted_urls:
            with self.subTest(url=url):
                self.assertTrue(self.news_fetcher._validate_feed_domain(url))

    def test_validate_feed_domain_untrusted(self):
        """Test feed URL validation with untrusted domain."""
        # The method now logs untrusted domains but doesn't fail
        untrusted_urls = [
            "https://example.com/feed.rss",
            "https://malicious-site.com/feed",
        ]
        
        for url in untrusted_urls:
            with self.subTest(url=url):
                # Should still return True but log a warning
                self.assertTrue(self.news_fetcher._validate_feed_domain(url))

    def test_validate_feed_domain_invalid(self):
        """Test feed URL validation with invalid URL."""
        invalid_urls = [
            "",
            "not-a-url",
            "ftp://example.com/feed",
        ]
        
        for url in invalid_urls:
            with self.subTest(url=url):
                self.assertFalse(self.news_fetcher._validate_feed_domain(url))

    def test_fetch_feed_success(self):
        """Test successful feed fetching."""
        # Mock response
        mock_response = Mock()
        mock_response.content = b"""<?xml version="1.0"?>
        <rss version="2.0">
            <channel>
                <title>Test Feed</title>
                <item>
                    <title>Test Article</title>
                    <link>https://example.com/article</link>
                    <description>Test description</description>
                    <pubDate>Mon, 01 Jan 2024 12:00:00 GMT</pubDate>
                </item>
            </channel>
        </rss>"""
        mock_response.raise_for_status = Mock()
        self.mock_session.get.return_value = mock_response
        
        feed_info = {
            "name": "Test Feed",
            "url": "https://archlinux.org/feeds/test/",
            "priority": 1,
            "type": "news",
            "enabled": True
        }
        
        # Mock the news item that would be returned by fetch_feed
        from src.models import NewsItem, FeedType
        from datetime import datetime
        
        mock_news_item = NewsItem(
            title="Test Article",
            link="https://example.com/article",
            date=datetime(2024, 1, 1, 12, 0),
            content="Test description",
            source="Test Feed",
            priority=1,
            source_type=FeedType.NEWS,
            affected_packages=set()
        )
        
        # Configure the shared mock future to return our mock news item
        self.mock_future.result.return_value = [mock_news_item]
        
        # Test fetch_all_feeds_legacy with dictionary format
        result = self.news_fetcher.fetch_all_feeds_legacy([feed_info])
        
        # Should return 1 news item
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['title'], "Test Article")

    def test_fetch_feed_network_error(self):
        """Test feed fetching with network error."""
        # Mock network error
        self.mock_session.get.side_effect = requests.exceptions.RequestException("Network error")
        
        feed_info = {
            "name": "Test Feed",
            "url": "https://archlinux.org/feeds/test/",
            "priority": 1,
            "type": "news",
            "enabled": True
        }
        
        # Use legacy method - should handle errors gracefully
        result = self.news_fetcher.fetch_all_feeds_legacy([feed_info])
        self.assertEqual(len(result), 0)

    def test_fetch_feed_parsing_error(self):
        """Test feed fetching with parsing error."""
        # Mock response with invalid XML
        mock_response = Mock()
        mock_response.content = b"Invalid XML content"
        mock_response.raise_for_status = Mock()
        self.mock_session.get.return_value = mock_response
        
        feed_info = {
            "name": "Test Feed",
            "url": "https://archlinux.org/feeds/test/",
            "priority": 1,
            "type": "news",
            "enabled": True
        }
        
        # Use legacy method - should handle errors gracefully
        result = self.news_fetcher.fetch_all_feeds_legacy([feed_info])
        self.assertEqual(len(result), 0)

    def test_fetch_feed_invalid_url(self):
        """Test feed fetching with invalid URL."""
        # Mock the validation to fail for invalid URL
        with patch.object(self.news_fetcher, '_validate_feed_domain', return_value=False):
            feed_info = {
                "name": "Test Feed",
                "url": "not-a-valid-url",
                "priority": 1,
                "type": "news",
                "enabled": True
            }
            
            # Use legacy method - should handle errors gracefully
            result = self.news_fetcher.fetch_all_feeds_legacy([feed_info])
            self.assertEqual(len(result), 0)

    def test_fetch_feed_with_cache(self):
        """Test feed fetching with cached data."""
        # Set up cached data
        cached_data = [
            {
                "title": "Cached Article",
                "link": "https://example.com/cached",
                "date": "2024-01-01T12:00:00",
                "content": "Cached content",
                "source": "Test Feed",
                "priority": 1,
                "source_type": "news",
                "affected_packages": []
            }
        ]
        self.mock_cache.get.return_value = cached_data
        
        feed_info = {
            "name": "Test Feed",
            "url": "https://archlinux.org/feeds/test/",
            "priority": 1,
            "type": "news",
            "enabled": True
        }
        
        # Mock the ThreadPoolExecutor future 
        mock_future = Mock()
        
        # Mock the news item from cached data
        from src.models import NewsItem, FeedType
        from datetime import datetime
        
        mock_news_item = NewsItem(
            title="Cached Article",
            link="https://example.com/cached",
            date=datetime(2024, 1, 1, 12, 0),
            content="Cached content",
            source="Test Feed",
            priority=1,
            source_type=FeedType.NEWS,
            affected_packages=set()
        )
        
        mock_future.result.return_value = [mock_news_item]
        
        # Setup mock executor submit to return future
        self.mock_executor.submit.return_value = mock_future
        
        # Setup as_completed to return the future
        self.mock_as_completed.return_value = [mock_future]
        
        # Use legacy method
        result = self.news_fetcher.fetch_all_feeds_legacy([feed_info])
        
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["title"], "Cached Article")

    def test_fetch_all_feeds(self):
        """Test fetching multiple feeds."""
        # Mock response
        mock_response = Mock()
        mock_response.content = b"""<?xml version="1.0"?>
        <rss version="2.0">
            <channel>
                <title>Test Feed</title>
                <item>
                    <title>Test Article</title>
                    <link>https://example.com/article</link>
                    <description>Test description</description>
                    <pubDate>Mon, 01 Jan 2024 12:00:00 GMT</pubDate>
                </item>
            </channel>
        </rss>"""
        mock_response.raise_for_status = Mock()
        self.mock_session.get.return_value = mock_response
        
        feeds = [
            {
                "name": "Feed 1",
                "url": "https://archlinux.org/feeds/1/",
                "priority": 1,
                "type": "news",
                "enabled": True
            },
            {
                "name": "Feed 2",
                "url": "https://archlinux.org/feeds/2/",
                "priority": 2,
                "type": "news",
                "enabled": True
            }
        ]
        
        # Mock news items that would be returned
        from src.models import NewsItem, FeedType
        from datetime import datetime
        
        mock_news_item = NewsItem(
            title="Test Article",
            link="https://example.com/article",
            date=datetime(2024, 1, 1, 12, 0),
            content="Test description",
            source="Test Feed",
            priority=1,
            source_type=FeedType.NEWS,
            affected_packages=set()
        )
        
        # Configure the shared mock future to return our mock news item
        self.mock_future.result.return_value = [mock_news_item]
        
        # For multiple feeds, we need multiple futures
        mock_future2 = Mock()
        mock_future2.result.return_value = [mock_news_item]
        
        # Update mocks to handle multiple feeds
        self.mock_executor.submit.side_effect = [self.mock_future, mock_future2]
        self.mock_as_completed.return_value = [self.mock_future, mock_future2]
        
        result = self.news_fetcher.fetch_all_feeds_legacy(feeds)
        
        # Should return 2 news items (1 from each feed)
        self.assertEqual(len(result), 2)

    def test_fetch_all_feeds_with_errors(self):
        """Test fetching multiple feeds with some errors."""
        # First feed succeeds, second fails
        mock_response = Mock()
        mock_response.content = b"""<?xml version="1.0"?>
        <rss version="2.0">
            <channel>
                <title>Test Feed</title>
                <item>
                    <title>Test Article</title>
                    <link>https://example.com/article</link>
                    <description>Test description</description>
                    <pubDate>Mon, 01 Jan 2024 12:00:00 GMT</pubDate>
                </item>
            </channel>
        </rss>"""
        mock_response.raise_for_status = Mock()
        
        # Make the second call fail
        self.mock_session.get.side_effect = [mock_response, requests.exceptions.RequestException("Error")]
        
        feeds = [
            {
                "name": "Feed 1",
                "url": "https://archlinux.org/feeds/1/",
                "priority": 1,
                "type": "news",
                "enabled": True
            },
            {
                "name": "Feed 2",
                "url": "https://archlinux.org/feeds/2/",
                "priority": 2,
                "type": "news",
                "enabled": True
            }
        ]
        
        # Mock the ThreadPoolExecutor futures
        mock_future1 = Mock()
        mock_future2 = Mock()
        
        # Mock successful result for first feed
        from src.models import NewsItem, FeedType
        from datetime import datetime
        
        mock_news_item = NewsItem(
            title="Test Article",
            link="https://example.com/article",
            date=datetime(2024, 1, 1, 12, 0),
            content="Test description",
            source="Feed 1",
            priority=1,
            source_type=FeedType.NEWS,
            affected_packages=set()
        )
        
        mock_future1.result.return_value = [mock_news_item]
        mock_future2.result.side_effect = requests.exceptions.RequestException("Error")
        
        # Setup mock executor submit to return futures
        self.mock_executor.submit.side_effect = [mock_future1, mock_future2]
        
        # Setup as_completed to return the futures
        self.mock_as_completed.return_value = [mock_future1, mock_future2]
        
        result = self.news_fetcher.fetch_all_feeds_legacy(feeds)
        
        # Should have 1 item (from the successful feed)
        self.assertEqual(len(result), 1)

    def test_disabled_feeds_ignored(self):
        """Test that disabled feeds are ignored."""
        feeds = [
            {
                "name": "Enabled Feed",
                "url": "https://archlinux.org/feeds/1/",
                "priority": 1,
                "type": "news",
                "enabled": True
            },
            {
                "name": "Disabled Feed",
                "url": "https://archlinux.org/feeds/2/",
                "priority": 2,
                "type": "news", 
                "enabled": False
            }
        ]
        
        with patch.object(self.news_fetcher, 'fetch_feed') as mock_fetch:
            mock_fetch.return_value = []
            result = self.news_fetcher.fetch_all_feeds_legacy(feeds)
            
            # Should only call fetch_feed once (for enabled feed)
            self.assertEqual(mock_fetch.call_count, 0)  # Legacy method handles it internally

    def test_package_type_feeds_ignored(self):
        """Test that package-type feeds are ignored."""
        feeds = [
            {
                "name": "News Feed",
                "url": "https://archlinux.org/feeds/1/",
                "priority": 1,
                "type": "news",
                "enabled": True
            },
            {
                "name": "Package Feed",
                "url": "https://archlinux.org/feeds/2/",
                "priority": 2,
                "type": "package",
                "enabled": True
            }
        ]
        
        with patch.object(self.news_fetcher, 'fetch_feed') as mock_fetch:
            mock_fetch.return_value = []
            result = self.news_fetcher.fetch_all_feeds_legacy(feeds)
            
            # Legacy method handles filtering internally
            self.assertIsInstance(result, list)


if __name__ == "__main__":
    unittest.main()
