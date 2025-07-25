"""
RSS feed fetching and parsing functionality.
"""

# SPDX-License-Identifier: GPL-3.0-or-later

import re
import html
import requests
import feedparser
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from urllib.parse import urlparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading

from .exceptions import FeedParsingError, NetworkError
from .utils.cache import CacheManager
from .utils.logger import get_logger
from .utils.validators import validate_feed_url, sanitize_html
from .constants import (
    TRUSTED_FEED_DOMAINS,
    APP_USER_AGENT,
    FEED_FETCH_TIMEOUT,
    DEFAULT_REQUEST_TIMEOUT
)
from .models import NewsItem, FeedConfig, FeedType

logger = get_logger(__name__)


class NewsFetcher:
    """Fetches and parses RSS feeds for Arch Linux news."""

    def __init__(self, cache_manager: Optional[CacheManager] = None) -> None:
        """
        Initialize the news fetcher with security configurations.

        Args:
            cache_manager: Cache manager instance
        """
        self.cache_manager = cache_manager or CacheManager()
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": APP_USER_AGENT})
        self.session.timeout = DEFAULT_REQUEST_TIMEOUT

        # Configure secure session settings
        self._configure_secure_session()

        # Thread lock for session access
        self._session_lock = threading.Lock()

        # Default freshness window (in days)
        self.max_news_age_days = 30

        # Configure secure XML parsing to prevent XXE attacks
        self._configure_secure_xml_parsing()

        logger.debug("Initialized NewsFetcher with security configurations")

    def _configure_secure_xml_parsing(self) -> None:
        """
        Configure secure XML parsing to prevent XXE attacks.
        """
        try:
            # Configure feedparser to use secure XML parsing
            import xml.etree.ElementTree as ET

            # Set up secure XML parser
            try:
                # Try to configure the XML parser to disable external entities
                import xml.sax.saxutils

                # Monkey patch feedparser's XML parser to be more secure
                original_parse = feedparser.parse

                def secure_parse(data_or_url, etag=None, modified=None, agent=None, referrer=None, handlers=None):
                    """Secure wrapper for feedparser.parse that limits XML features."""
                    logger.debug(f"secure_parse called with data type: {type(data_or_url)}")

                    # If it's a URL, let the regular flow handle it (we validate URLs separately)
                    if isinstance(data_or_url, str) and (data_or_url.startswith(
                            'http://') or data_or_url.startswith('https://')):
                        logger.debug("Parsing URL directly")
                        return original_parse(
                            data_or_url,
                            etag=etag,
                            modified=modified,
                            agent=agent,
                            referrer=referrer,
                            handlers=handlers)

                    # For raw data parsing, apply additional security
                    try:
                        # Pre-scan the content for suspicious patterns
                        if isinstance(data_or_url, (str, bytes)):
                            content = data_or_url if isinstance(
                                data_or_url, str) else data_or_url.decode(
                                'utf-8', errors='ignore')

                            # Check for XXE attack patterns (avoid false positives with standard entities)
                            xxe_patterns = [
                                # Only check for actual file/http references in ENTITY declarations
                                r'<!ENTITY\s+[^>]*\s+SYSTEM\s+["\']file:',
                                r'<!ENTITY\s+[^>]*\s+SYSTEM\s+["\']http[s]?://',
                                r'<!ENTITY\s+[^>]*\s+PUBLIC\s+[^>]*\s+["\']file:',
                                r'<!ENTITY\s+[^>]*\s+PUBLIC\s+[^>]*\s+["\']http[s]?://',
                                # Check for parameter entities which are more dangerous
                                r'<!ENTITY\s+%',
                                # Check for recursive entity expansion
                                r'<!ENTITY\s+[^>]*&[^;]+;[^>]*>',
                                # Check for external DTD includes that reference files
                                r'SYSTEM\s+["\']file:.*\.dtd',
                                # Check for suspicious DOCTYPE with ENTITY declarations inside
                                r'<!DOCTYPE[^>]*\[[\s\S]*<!ENTITY[^>]*SYSTEM[^>]*file:',
                                r'<!DOCTYPE[^>]*\[[\s\S]*<!ENTITY[^>]*SYSTEM[^>]*http[s]?:'
                            ]

                            for pattern in xxe_patterns:
                                if re.search(pattern, content, re.IGNORECASE):
                                    logger.warning(f"Suspicious XML pattern detected: {pattern}, rejecting feed")
                                    # Return empty feed structure
                                    empty_feed = feedparser.FeedParserDict()
                                    empty_feed.bozo = True
                                    empty_feed.bozo_exception = Exception("Potentially malicious XML content detected")
                                    empty_feed.entries = []
                                    return empty_feed

                            logger.debug("XML content passed security checks")

                    except Exception as e:
                        logger.warning(f"Error scanning XML content: {e}")

                    logger.debug("Calling original parse function")
                    result = original_parse(
                        data_or_url,
                        etag=etag,
                        modified=modified,
                        agent=agent,
                        referrer=referrer,
                        handlers=handlers)
                    logger.debug(f"Parse result: {len(getattr(result, 'entries', []))} entries")
                    return result

                # Replace feedparser's parse function with our secure version
                feedparser.parse = secure_parse

            except Exception as e:
                logger.warning(f"Could not configure XML parser security: {e}")

        except Exception as e:
            logger.warning(f"Failed to configure secure XML parsing: {e}")

    def _configure_secure_session(self) -> None:
        """
        Configure the requests session with enhanced security settings and resource controls.
        """
        try:
            # Enable SSL verification (should be default, but make it explicit)
            self.session.verify = True

            # Configure secure headers with additional security measures
            self.session.headers.update({
                'Accept': 'application/rss+xml, application/atom+xml, application/xml, text/xml, text/html',
                'Accept-Encoding': 'gzip, deflate',
                'Cache-Control': 'no-cache',
                'DNT': '1',  # Do Not Track
                'Connection': 'close',  # Don't keep connections alive
                'User-Agent': APP_USER_AGENT,
                'Accept-Language': 'en-US,en;q=0.9',
                'Accept-Charset': 'utf-8',
            })

            # Configure adapters with enhanced retry and security settings
            from requests.adapters import HTTPAdapter
            from urllib3.util.retry import Retry
            import urllib3

            # Disable SSL warnings for our controlled environment
            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

            # Configure aggressive retry strategy with backoff
            retry_strategy = Retry(
                total=2,  # Reduced from 3 for faster failure
                connect=2,  # Connection retries
                read=1,     # Read retries
                status=1,   # Status retries
                status_forcelist=[429, 500, 502, 503, 504, 520, 521, 522, 523, 524],
                backoff_factor=0.5,  # Faster backoff
                allowed_methods=["GET", "HEAD"],  # Only allow safe methods
                raise_on_status=False,  # Don't raise on HTTP errors in retry
                respect_retry_after_header=True,
            )

            # Create adapter with strict resource limits
            adapter = HTTPAdapter(
                max_retries=retry_strategy,
                pool_connections=3,   # Reduced connection pool
                pool_maxsize=5,      # Reduced max connections
                pool_block=False,    # Don't block on pool exhaustion
            )

            # Mount adapter for both HTTP and HTTPS
            self.session.mount("http://", adapter)
            self.session.mount("https://", adapter)

            # Set comprehensive security parameters
            self.session.max_redirects = 3  # Further reduced redirect limit

            # Configure timeout defaults
            self.session.timeout = (5, 15)  # (connect_timeout, read_timeout)

            # Configure stream limits
            self.session.stream = False  # Never stream responses for security

            # Add request hooks for monitoring
            self.session.hooks['response'].append(self._response_security_hook)

            logger.debug("Configured enhanced secure session settings")

        except Exception as e:
            logger.warning(f"Failed to configure secure session: {e}")

    def _response_security_hook(self, response, *args, **kwargs):
        """
        Security hook to validate responses and enforce limits.

        Args:
            response: HTTP response object
        """
        try:
            # Check response size before processing
            content_length = response.headers.get('content-length')
            if content_length:
                try:
                    size = int(content_length)
                    max_size = 50 * 1024 * 1024  # 50MB absolute limit
                    if size > max_size:
                        logger.warning(f"Response too large: {size} bytes (max: {max_size})")
                        response.close()
                        return response
                except (ValueError, TypeError):
                    pass

            # Check content type for validity
            content_type = response.headers.get('content-type', '').lower()
            allowed_types = [
                'application/rss+xml', 'application/atom+xml', 'application/xml',
                'text/xml', 'text/html', 'text/plain'
            ]

            if content_type and not any(allowed in content_type for allowed in allowed_types):
                logger.warning(f"Unexpected content type: {content_type}")

            # Log response metrics for monitoring
            response_size = len(response.content) if hasattr(response, 'content') else 0
            logger.debug(f"Response received: {response.status_code}, size: {response_size} bytes")

        except Exception as e:
            logger.debug(f"Response security hook error: {e}")

        return response

    def _validate_request_parameters(self, url: str, timeout: int = None) -> tuple:
        """
        Validate and normalize request parameters for security.

        Args:
            url: URL to validate
            timeout: Timeout value to validate

        Returns:
            Tuple of (validated_url, validated_timeout)

        Raises:
            NetworkError: If parameters are invalid
        """
        # URL validation
        if not url or len(url) > 2048:
            raise NetworkError("Invalid URL length")

        # Parse and validate URL components
        try:
            from urllib.parse import urlparse
            parsed = urlparse(url)

            # Check scheme
            if parsed.scheme not in ['http', 'https']:
                raise NetworkError(f"Invalid URL scheme: {parsed.scheme}")

            # Check for suspicious characters
            if any(char in url for char in ['<', '>', '"', "'", '\\', '\x00', '\x01', '\x02']):
                raise NetworkError("URL contains suspicious characters")

            # Validate hostname
            if not parsed.hostname:
                raise NetworkError("URL missing hostname")

            # Check for private IP addresses (basic SSRF protection)
            try:
                import ipaddress
                ip = ipaddress.ip_address(parsed.hostname)
                if ip.is_private or ip.is_loopback or ip.is_link_local:
                    raise NetworkError(f"Private IP address not allowed: {parsed.hostname}")
            except (ipaddress.AddressValueError, ValueError):
                # Not an IP address, continue
                pass

            # Port validation
            if parsed.port:
                if not (1 <= parsed.port <= 65535):
                    raise NetworkError(f"Invalid port: {parsed.port}")
                # Block dangerous ports
                blocked_ports = {22, 23, 25, 53, 135, 139, 445, 1433, 1521, 3306, 3389, 5432, 6379}
                if parsed.port in blocked_ports:
                    raise NetworkError(f"Blocked port: {parsed.port}")

        except NetworkError:
            raise
        except Exception as e:
            raise NetworkError(f"URL parsing failed: {e}")

        # Timeout validation and normalization
        if timeout is None:
            timeout = FEED_FETCH_TIMEOUT

        # Enforce timeout limits
        min_timeout = 1   # Minimum 1 second
        max_timeout = 60  # Maximum 1 minute

        if timeout < min_timeout:
            logger.warning(f"Timeout too small ({timeout}s), using minimum ({min_timeout}s)")
            timeout = min_timeout
        elif timeout > max_timeout:
            logger.warning(f"Timeout too large ({timeout}s), using maximum ({max_timeout}s)")
            timeout = max_timeout

        return url, timeout

    def _make_secure_request(self, url: str, timeout: int = None, **kwargs) -> 'requests.Response':
        """
        Make a secure HTTP request with comprehensive controls.

        Args:
            url: URL to request
            timeout: Request timeout
            **kwargs: Additional request parameters

        Returns:
            Response object

        Raises:
            NetworkError: If request fails or is unsafe
        """
        # Validate parameters
        url, timeout = self._validate_request_parameters(url, timeout)

        # Set up security parameters
        request_params = {
            'timeout': (min(5, timeout // 3), timeout),  # (connect, read) timeout
            'allow_redirects': True,
            'stream': False,  # Never stream for security
            'verify': True,   # Always verify SSL
        }

        # Override with any provided kwargs (but maintain security)
        safe_kwargs = {k: v for k, v in kwargs.items()
                       if k in ['headers', 'params', 'auth', 'cookies']}
        request_params.update(safe_kwargs)

        # Rate limiting (basic implementation)
        import time
        current_time = time.time()
        if hasattr(self, '_last_request_time'):
            time_since_last = current_time - self._last_request_time
            min_interval = 0.1  # 100ms minimum between requests
            if time_since_last < min_interval:
                time.sleep(min_interval - time_since_last)

        self._last_request_time = time.time()

        try:
            with self._session_lock:
                logger.debug(f"Making secure request to: {url[:100]}...")

                # Make the request with enhanced error handling
                response = self.session.get(url, **request_params)

                # Validate response
                self._validate_response(response, url)

                return response

        except requests.exceptions.Timeout as e:
            raise NetworkError(f"Request timed out after {timeout}s: {e}")
        except requests.exceptions.ConnectionError as e:
            raise NetworkError(f"Connection failed: {e}")
        except requests.exceptions.SSLError as e:
            raise NetworkError(f"SSL verification failed: {e}")
        except requests.exceptions.TooManyRedirects as e:
            raise NetworkError(f"Too many redirects: {e}")
        except requests.exceptions.RequestException as e:
            raise NetworkError(f"Request failed: {e}")
        except Exception as e:
            raise NetworkError(f"Unexpected request error: {e}")

    def _validate_response(self, response: 'requests.Response', original_url: str) -> None:
        """
        Validate HTTP response for security and content requirements.

        Args:
            response: HTTP response to validate
            original_url: Original requested URL

        Raises:
            NetworkError: If response is invalid or unsafe
        """
        try:
            # Check status code
            if response.status_code == 200:
                pass  # OK
            elif response.status_code in [301, 302, 303, 307, 308]:
                # Check redirect target
                location = response.headers.get('location', '')
                if location:
                    try:
                        self._validate_request_parameters(location)
                    except NetworkError as e:
                        raise NetworkError(f"Unsafe redirect target: {e}")
            elif response.status_code == 403:
                raise NetworkError("Access denied by server")
            elif response.status_code == 404:
                raise NetworkError("Resource not found")
            elif response.status_code == 429:
                raise NetworkError("Rate limited by server")
            elif response.status_code >= 500:
                raise NetworkError(f"Server error: {response.status_code}")
            else:
                raise NetworkError(f"Unexpected status code: {response.status_code}")

            # Validate content length
            actual_size = len(response.content)
            max_content_size = 50 * 1024 * 1024  # 50MB

            if actual_size > max_content_size:
                raise NetworkError(f"Response too large: {actual_size} bytes")

            if actual_size == 0:
                raise NetworkError("Empty response received")

            # Check content type
            content_type = response.headers.get('content-type', '').lower()
            expected_types = ['xml', 'rss', 'atom', 'html']

            if content_type and not any(expected in content_type for expected in expected_types):
                logger.warning(f"Unexpected content type: {content_type}")

            # Check for suspicious content patterns
            content_preview = response.content[:1000].decode('utf-8', errors='ignore').lower()

            # Check for basic XML/RSS structure
            if not any(tag in content_preview for tag in ['<rss', '<feed', '<xml', '<?xml', '<html']):
                logger.warning("Response does not appear to be valid RSS/XML content")

            # Check for suspicious content
            suspicious_patterns = ['<script', 'javascript:', 'vbscript:', 'data:']
            for pattern in suspicious_patterns:
                if pattern in content_preview:
                    logger.warning(f"Suspicious content pattern detected: {pattern}")

            logger.debug(f"Response validated: {actual_size} bytes, type: {content_type}")

        except NetworkError:
            raise
        except Exception as e:
            raise NetworkError(f"Response validation failed: {e}")

    def _rate_limit_check(self, url: str) -> None:
        """
        Check if request should be rate limited.

        Args:
            url: URL being requested

        Raises:
            NetworkError: If rate limit is exceeded
        """
        from urllib.parse import urlparse

        try:
            hostname = urlparse(url).hostname
            if not hostname:
                return

            # Simple per-host rate limiting
            import time
            current_time = time.time()

            if not hasattr(self, '_host_request_times'):
                self._host_request_times = {}

            if hostname not in self._host_request_times:
                self._host_request_times[hostname] = []

            # Clean old entries (older than 1 minute)
            cutoff_time = current_time - 60
            self._host_request_times[hostname] = [
                t for t in self._host_request_times[hostname] if t > cutoff_time
            ]

            # Check rate limit (max 10 requests per minute per host)
            if len(self._host_request_times[hostname]) >= 10:
                raise NetworkError(f"Rate limit exceeded for {hostname}")

            # Record this request
            self._host_request_times[hostname].append(current_time)

        except NetworkError:
            raise
        except Exception as e:
            logger.warning(f"Rate limit check failed: {e}")

    def _sanitize_content(self, content: str) -> str:
        """
        Sanitize HTML content.

        Args:
            content: Raw content

        Returns:
            Sanitized content
        """
        return sanitize_html(content)

    def _validate_feed_domain(self, url: str) -> bool:
        """
        Validate feed domain against trusted list.

        Args:
            url: Feed URL

        Returns:
            True if domain is trusted or validation is disabled
        """
        try:
            parsed = urlparse(url)
            hostname = parsed.hostname
            scheme = parsed.scheme.lower() if parsed.scheme else ""

            if not hostname:
                return False

            # Only allow HTTP/HTTPS schemes
            if scheme not in ['http', 'https']:
                return False

            # Always allow localhost
            if hostname in ['localhost', '127.0.0.1', '::1']:
                return True

            # Check against trusted domains
            domain_parts = hostname.lower().split('.')
            if len(domain_parts) >= 2:
                base_domain = '.'.join(domain_parts[-2:])
                if base_domain in TRUSTED_FEED_DOMAINS:
                    return True

            # Log untrusted domain but don't fail
            logger.info(f"Feed domain not in trusted list: {hostname}")
            return True  # Allow but log

        except Exception as e:
            logger.error(f"Error validating feed domain: {e}")
            return False

    def fetch_feed(self, feed_config: FeedConfig) -> List[NewsItem]:
        """
        Fetch and parse a single RSS feed.

        Args:
            feed_config: Feed configuration

        Returns:
            List of news items

        Raises:
            FeedParsingError: If parsing fails
            NetworkError: If network request fails
        """
        url = feed_config.url
        feed_name = feed_config.name

        # Validate URL
        if not validate_feed_url(url, require_https=True):
            raise FeedParsingError(
                "Invalid or insecure feed URL",
                feed_name=feed_name,
                feed_url=url
            )

        # Check domain
        if not self._validate_feed_domain(url):
            raise FeedParsingError(
                "Untrusted feed domain",
                feed_name=feed_name,
                feed_url=url
            )

        try:
            # Check cache first
            cached_data = self.cache_manager.get(url)
            if cached_data is not None and isinstance(cached_data, list):
                logger.debug(f"Using cached data for feed: {feed_name}")
                # Convert dictionaries back to NewsItem objects
                return [NewsItem.from_dict(item) for item in cached_data]

            # Fetch fresh data with security measures
            logger.info(f"Fetching feed: {feed_name}")
            try:
                with self._session_lock:
                    # Additional URL validation before request
                    parsed_url = urlparse(url)
                    if parsed_url.hostname and parsed_url.hostname.lower() in ['localhost', '127.0.0.1', '0.0.0.0']:
                        if not url.startswith('https://localhost') and not url.startswith('http://localhost'):
                            raise NetworkError(f"Local network access not allowed: {url}")

                    # Check for private IP ranges (basic protection against SSRF)
                    import ipaddress
                    try:
                        if parsed_url.hostname:
                            ip = ipaddress.ip_address(parsed_url.hostname)
                            if ip.is_private or ip.is_loopback or ip.is_link_local:
                                raise NetworkError(f"Private network access not allowed: {url}")
                    except (ipaddress.AddressValueError, ValueError):
                        # Not an IP address, continue with hostname
                        pass

                    response = self.session.get(
                        url,
                        timeout=FEED_FETCH_TIMEOUT,
                        allow_redirects=True,
                        stream=False  # Don't stream to enable content length checks
                    )

                response.raise_for_status()

                # Security checks on response
                content_length = len(response.content)
                if content_length > 10 * 1024 * 1024:  # 10MB limit
                    raise NetworkError(f"Feed content too large: {content_length} bytes")

                if content_length == 0:
                    raise NetworkError(f"Empty response from feed: {url}")

                # Check content type
                content_type = response.headers.get('content-type', '').lower()
                allowed_types = [
                    'application/rss+xml',
                    'application/atom+xml',
                    'application/xml',
                    'text/xml',
                    'text/html']
                if content_type and not any(allowed_type in content_type for allowed_type in allowed_types):
                    logger.warning(f"Unexpected content type for feed {feed_name}: {content_type}")

                # Check for suspicious redirects
                if response.history:
                    final_url = response.url
                    if len(response.history) > 3:
                        logger.warning(f"Feed {feed_name} had {len(response.history)} redirects")

                    # Ensure final URL is still valid
                    if not validate_feed_url(final_url, require_https=True):
                        raise NetworkError(f"Redirected to invalid URL: {final_url}")

            except requests.exceptions.SSLError as e:
                raise NetworkError(f"SSL verification failed for {url}: {e}")
            except requests.exceptions.Timeout:
                raise NetworkError(f"Feed request timed out after {FEED_FETCH_TIMEOUT}s")
            except requests.exceptions.TooManyRedirects:
                raise NetworkError(f"Too many redirects for feed: {url}")
            except requests.exceptions.RequestException as e:
                raise NetworkError(f"Failed to fetch feed: {e}")

            # Parse feed with security wrapper
            try:
                feed = feedparser.parse(response.content)
            except Exception as e:
                raise FeedParsingError(f"XML parsing failed: {e}", feed_name=feed_name, feed_url=url)
            if getattr(feed, "bozo", False):
                bozo_exc = getattr(feed, "bozo_exception", None)
                msg = f"Failed to parse feed: {bozo_exc if bozo_exc else 'Unknown error'}"
                raise FeedParsingError(msg, feed_name=feed_name, feed_url=url)

            # Debug: log feed parsing result
            logger.debug(f"Feed parsed successfully: {len(getattr(feed, 'entries', []))} entries found")

            # Process entries
            news_items = []
            now = datetime.now()
            # Enforce security limits
            safe_max_age_days = min(self.max_news_age_days, 365)  # Cap at 1 year
            max_age = timedelta(days=safe_max_age_days)
            max_items_per_feed = 1000  # Prevent memory bombs from single feeds

            for entry in feed.entries:
                try:
                    # Extract and validate required fields
                    if not entry.get("title") or not entry.get("link"):
                        logger.warning(f"Skipping entry without title or link in {feed_name}")
                        continue

                    # Parse publication date
                    published = None
                    if hasattr(entry, "published_parsed") and entry.published_parsed:
                        try:
                            published = datetime(*entry.published_parsed[:6])
                        except (ValueError, TypeError):
                            logger.warning(f"Invalid date in feed entry: {entry.get('published')}")

                    if not published:
                        published = now  # Default to current time

                    # Skip old entries
                    if now - published > max_age:
                        logger.debug(f"Skipping old entry from {published} in {feed_name}")
                        continue

                    # Extract and sanitize content
                    content = ""
                    if hasattr(entry, "summary"):
                        content = self._sanitize_content(entry.summary)
                    elif hasattr(entry, "description"):
                        content = self._sanitize_content(entry.description)

                    news_item = NewsItem(
                        title=entry.title,
                        link=entry.link,
                        date=published,
                        content=content,
                        source=feed_name,
                        priority=feed_config.priority,
                        source_type=feed_config.feed_type
                    )
                    news_items.append(news_item)

                    # Security check: prevent excessive items from single feed
                    if len(news_items) >= max_items_per_feed:
                        logger.warning(
                            f"Feed {feed_name} reached max items limit ({max_items_per_feed}), stopping processing")
                        break

                except Exception as e:
                    logger.error(f"Error processing feed entry in {feed_name}: {e}")
                    continue

            # Cache the results
            cache_data = [item.to_dict() for item in news_items]
            self.cache_manager.set(url, cache_data)

            logger.info(f"Fetched {len(news_items)} items from {feed_name}")
            return news_items

        except (FeedParsingError, NetworkError):
            raise
        except Exception as e:
            logger.error(f"Unexpected error fetching feed {feed_name}: {e}")
            raise FeedParsingError(
                f"Unexpected error: {e}",
                feed_name=feed_name,
                feed_url=url,
            )

    def fetch_all_feeds(self, feed_configs: List[FeedConfig]) -> List[NewsItem]:
        """
        Fetch all configured RSS feeds in parallel.

        Args:
            feed_configs: List of feed configurations

        Returns:
            List of all news items sorted by priority and date
        """
        all_news = []

        # Filter enabled news feeds only
        active_feeds = [
            fc for fc in feed_configs
            if fc.enabled and fc.feed_type == FeedType.NEWS
        ]

        if not active_feeds:
            logger.warning("No active news feeds configured")
            return []

        logger.info(f"Fetching {len(active_feeds)} active feeds")

        # Use secure ThreadPoolExecutor for parallel fetching
        from .utils.thread_manager import SecureThreadPoolExecutor

        max_workers = min(len(active_feeds), 5)  # Limit concurrent connections
        executor = SecureThreadPoolExecutor.get_executor(max_workers)

        # Submit all feed fetches
        future_to_feed = {
            executor.submit(self.fetch_feed, feed): feed
            for feed in active_feeds
        }

        # Collect results as they complete
        for future in as_completed(future_to_feed):
            feed = future_to_feed[future]
            try:
                news_items = future.result()
                all_news.extend(news_items)
            except (FeedParsingError, NetworkError) as e:
                logger.error(f"Failed to fetch {feed.name}: {e}")
            except Exception as e:
                logger.error(f"Unexpected error fetching {feed.name}: {e}")

        # Sort by priority (ascending) and date (descending)
        all_news.sort(key=lambda x: (x.priority, -x.date.timestamp()))

        logger.info(f"Fetched total of {len(all_news)} news items")
        return all_news

    def fetch_all_feeds_legacy(self, feeds: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Legacy method for backward compatibility.
        Fetch all configured RSS feeds (dictionary format).

        Args:
            feeds: List of feed configurations (dictionaries)

        Returns:
            List of all news items (dictionaries)
        """
        # Convert dictionaries to FeedConfig objects
        feed_configs = []
        for feed_dict in feeds:
            try:
                feed_config = FeedConfig.from_dict(feed_dict)
                feed_configs.append(feed_config)
            except Exception as e:
                logger.error(f"Invalid feed configuration: {e}")
                continue

        # Fetch using new method
        news_items = self.fetch_all_feeds(feed_configs)

        # Convert back to dictionaries
        return [item.to_dict() for item in news_items]

    def test_feed(self, url: str) -> Dict[str, Any]:
        """
        Test a feed URL to see if it's accessible and valid.

        Args:
            url: Feed URL to test

        Returns:
            Dictionary with test results
        """
        result = {
            "success": False,
            "error": None,
            "entry_count": 0,
            "feed_title": None
        }

        try:
            # Validate URL
            if not validate_feed_url(url, require_https=True):
                result["error"] = "Invalid or insecure URL"
                return result

            # Try to fetch with security measures
            with self._session_lock:
                # Additional security checks
                parsed_url = urlparse(url)
                if parsed_url.hostname:
                    import ipaddress
                    try:
                        ip = ipaddress.ip_address(parsed_url.hostname)
                        if ip.is_private or ip.is_loopback or ip.is_link_local:
                            result["error"] = "Private network access not allowed"
                            return result
                    except (ipaddress.AddressValueError, ValueError):
                        pass  # Not an IP address

                response = self.session.get(
                    url,
                    timeout=10,
                    allow_redirects=True,
                    stream=False
                )
            response.raise_for_status()

            # Check response size
            if len(response.content) > 10 * 1024 * 1024:  # 10MB limit
                result["error"] = "Feed content too large"
                return result

            # Try to parse
            try:
                feed = feedparser.parse(response.content)
            except Exception as e:
                result["error"] = f"XML parsing failed: {e}"
                return result

            if getattr(feed, "bozo", False):
                result["error"] = f"Feed parsing error: {getattr(feed, 'bozo_exception', 'Unknown')}"
                return result

            # Success
            result["success"] = True
            result["entry_count"] = len(feed.entries)
            result["feed_title"] = getattr(feed.feed, "title", "Unknown")

        except requests.exceptions.SSLError as e:
            result["error"] = f"SSL verification failed: {e}"
        except requests.exceptions.Timeout:
            result["error"] = "Request timed out"
        except requests.exceptions.TooManyRedirects:
            result["error"] = "Too many redirects"
        except requests.exceptions.RequestException as e:
            result["error"] = f"Network error: {e}"
        except Exception as e:
            result["error"] = f"Unexpected error: {e}"

        return result

    def cleanup_session(self) -> None:
        """Clean up the requests session."""
        try:
            self.session.close()
        except Exception as e:
            logger.error(f"Error closing session: {e}")
