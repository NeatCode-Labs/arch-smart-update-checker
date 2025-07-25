"""
Input validation and security utilities with enhanced protections.
"""

# SPDX-License-Identifier: GPL-3.0-or-later

import re
import os
import unicodedata
from typing import Optional, List, Union, Any, Dict
from urllib.parse import urlparse
import ipaddress
import string

from ..constants import (
    PACKAGE_NAME_PATTERN,
    FEED_URL_PATTERN,
    TRUSTED_FEED_DOMAINS
)
from ..utils.logger import get_logger

logger = get_logger(__name__)


class ValidationError(Exception):
    """Raised when input validation fails."""
    pass


class SecurityFilter:
    """Centralized security filtering and validation."""

    # Maximum lengths for various input types (security limits)
    MAX_PACKAGE_NAME_LENGTH = 100
    MAX_URL_LENGTH = 2048
    MAX_FILENAME_LENGTH = 255
    MAX_PATH_LENGTH = 4096
    MAX_COMMAND_LENGTH = 1024
    MAX_CONFIG_VALUE_LENGTH = 10000
    MAX_LOG_MESSAGE_LENGTH = 50000

    # Dangerous characters by context
    SHELL_DANGEROUS_CHARS = set(';|&$`\\"\'\n\r\t<>()*?[]{}')
    PATH_DANGEROUS_CHARS = set('<>:"|?*\x00-\x1f\x7f-\x9f')
    FILENAME_DANGEROUS_CHARS = set('<>:"/\\|?*\x00-\x1f\x7f-\x9f')

    # Common injection patterns
    INJECTION_PATTERNS = [
        r'(?:union|select|insert|update|delete|drop|create|alter)\s+',
        r'(?:script|javascript|vbscript|onload|onerror|onclick)',
        r'(?:eval|exec|system|shell_exec|passthru|popen)\s*\(',
        r'(?:\$\(|\$\{|`[^`]*`)',
        r'(?:<!--|\*/|/\*|-->)',
        r'(?:&lt;|&gt;|&quot;|&#)',
    ]

    @classmethod
    def validate_input_length(cls, value: str, input_type: str, max_length: Optional[int] = None) -> None:
        """
        Validate input length against security limits.

        Args:
            value: Input value to check
            input_type: Type of input for context
            max_length: Custom maximum length

        Raises:
            ValidationError: If input exceeds length limits
        """
        if not isinstance(value, str):
            raise ValidationError(f"Expected string for {input_type}, got {type(value)}")

        actual_length = len(value)

        # Use provided max_length or default based on type
        if max_length is None:
            type_limits = {
                'package_name': cls.MAX_PACKAGE_NAME_LENGTH,
                'url': cls.MAX_URL_LENGTH,
                'filename': cls.MAX_FILENAME_LENGTH,
                'path': cls.MAX_PATH_LENGTH,
                'command': cls.MAX_COMMAND_LENGTH,
                'config_value': cls.MAX_CONFIG_VALUE_LENGTH,
                'log_message': cls.MAX_LOG_MESSAGE_LENGTH,
            }
            max_length = type_limits.get(input_type, 1000)  # Default 1KB

        if actual_length > max_length:
            raise ValidationError(
                f"{input_type} too long: {actual_length} chars (max: {max_length})"
            )

    @classmethod
    def validate_encoding(cls, value: str, input_type: str) -> str:
        """
        Validate and normalize text encoding.

        Args:
            value: Input string
            input_type: Type of input for context

        Returns:
            Normalized string

        Raises:
            ValidationError: If encoding is invalid
        """
        try:
            # Check for null bytes and control characters
            if '\x00' in value:
                raise ValidationError(f"{input_type} contains null bytes")

            # Normalize Unicode (NFC form for consistent representation)
            normalized = unicodedata.normalize('NFC', value)

            # Check for dangerous Unicode categories
            dangerous_categories = {'Cc', 'Cf', 'Co', 'Cs'}  # Control chars, format chars, private use
            for char in normalized:
                if unicodedata.category(char) in dangerous_categories and char not in '\t\n\r':
                    raise ValidationError(f"{input_type} contains dangerous Unicode character: U+{ord(char):04X}")

            return normalized

        except UnicodeError as e:
            raise ValidationError(f"Invalid Unicode in {input_type}: {e}")

    @classmethod
    def check_injection_patterns(cls, value: str, input_type: str) -> None:
        """
        Check for common injection attack patterns.

        Args:
            value: Input to check
            input_type: Type of input for context

        Raises:
            ValidationError: If injection patterns are detected
        """
        value_lower = value.lower()

        for pattern in cls.INJECTION_PATTERNS:
            if re.search(pattern, value_lower, re.IGNORECASE):
                logger.warning(f"Injection pattern detected in {input_type}: {pattern}")
                raise ValidationError(f"Potentially malicious content detected in {input_type}")

    @classmethod
    def sanitize_for_context(cls, value: str, context: str) -> str:
        """
        Sanitize input for specific security context.

        Args:
            value: Input to sanitize
            context: Security context (shell, path, filename, etc.)

        Returns:
            Sanitized string
        """
        if context == 'shell':
            # Remove shell metacharacters
            return ''.join(c for c in value if c not in cls.SHELL_DANGEROUS_CHARS)
        elif context == 'path':
            # Remove path dangerous characters
            return ''.join(c for c in value if c not in cls.PATH_DANGEROUS_CHARS)
        elif context == 'filename':
            # Remove filename dangerous characters
            sanitized = ''.join(c for c in value if c not in cls.FILENAME_DANGEROUS_CHARS)
            # Additional filename sanitization
            sanitized = re.sub(r'\.\.+', '.', sanitized)  # Multiple dots
            sanitized = sanitized.strip('. ')  # Leading/trailing dots and spaces
            return sanitized
        elif context == 'html':
            # Basic HTML entity encoding
            html_escapes = {
                '&': '&amp;',
                '<': '&lt;',
                '>': '&gt;',
                '"': '&quot;',
                "'": '&#x27;',
            }
            for char, escape in html_escapes.items():
                value = value.replace(char, escape)
            return value
        else:
            # Generic sanitization - remove control characters
            return re.sub(r'[\x00-\x1f\x7f-\x9f]', '', value)


def validate_package_name(name: str) -> bool:
    """
    Validate a package name for security with enhanced checks.

    Args:
        name: Package name to validate

    Returns:
        True if package name is valid and safe
    """
    if not name:
        return False

    try:
        # Length validation
        SecurityFilter.validate_input_length(name, 'package_name')

        # Encoding validation
        name = SecurityFilter.validate_encoding(name, 'package_name')

        # Check for injection patterns
        SecurityFilter.check_injection_patterns(name, 'package_name')

    except ValidationError as e:
        logger.warning(f"Package name validation failed: {e}")
        return False

    # Check against enhanced pattern
    if not re.match(PACKAGE_NAME_PATTERN, name):
        logger.warning(f"Invalid package name format: {name}")
        return False

    # Additional security checks
    suspicious_patterns = [
        r'\.\.', r'/', r'\\', r'\$', r'`', r';', r'&', r'\|',
        r'<', r'>', r'"', r"'", r'\s', r'\x00-\x1f', r'\x7f-\x9f'
    ]

    for pattern in suspicious_patterns:
        if re.search(pattern, name):
            logger.warning(f"Suspicious character in package name: {name}")
            return False

    # Check for reserved names
    reserved_names = {
        'con', 'prn', 'aux', 'nul', 'com1', 'com2', 'com3', 'com4', 'com5',
        'com6', 'com7', 'com8', 'com9', 'lpt1', 'lpt2', 'lpt3', 'lpt4',
        'lpt5', 'lpt6', 'lpt7', 'lpt8', 'lpt9', '.', '..'
    }

    if name.lower() in reserved_names:
        logger.warning(f"Reserved package name: {name}")
        return False

    # Check for consecutive special characters
    if re.search(r'[-_.+]{3,}', name):
        logger.warning(f"Too many consecutive special characters in package name: {name}")
        return False

    return True


def validate_numeric_input_enhanced(value: Union[str, int, float],
                                    input_type: str,
                                    min_val: Optional[Union[int, float]] = None,
                                    max_val: Optional[Union[int, float]] = None,
                                    allow_float: bool = False) -> Union[int, float]:
    """
    Enhanced numeric input validation with strict security checks.

    Args:
        value: Value to validate
        input_type: Type of input for context
        min_val: Minimum allowed value
        max_val: Maximum allowed value
        allow_float: Whether to allow floating point numbers

    Returns:
        Validated numeric value

    Raises:
        ValidationError: If value is invalid
    """
    try:
        # Convert to string for initial validation
        str_value = str(value).strip()

        # Length check to prevent DoS
        if len(str_value) > 50:
            raise ValidationError(f"{input_type} numeric string too long")

        # Check for dangerous patterns
        if re.search(r'[^\d\-+.eE]', str_value):
            raise ValidationError(f"{input_type} contains non-numeric characters")

        # Check for multiple signs or dots
        if str_value.count('+') + str_value.count('-') > 1:
            raise ValidationError(f"{input_type} has multiple signs")

        if str_value.count('.') > 1:
            raise ValidationError(f"{input_type} has multiple decimal points")

        # Convert to appropriate type
        if allow_float:
            num_value = float(str_value)
            # Check for special float values
            if not (num_value == num_value):  # NaN check
                raise ValidationError(f"{input_type} is NaN")
            if num_value == float('inf') or num_value == float('-inf'):
                raise ValidationError(f"{input_type} is infinite")
        else:
            num_value = int(str_value)

        # Range validation
        if min_val is not None and num_value < min_val:
            raise ValidationError(f"{input_type} below minimum: {num_value} < {min_val}")

        if max_val is not None and num_value > max_val:
            raise ValidationError(f"{input_type} above maximum: {num_value} > {max_val}")

        return num_value

    except (ValueError, OverflowError) as e:
        raise ValidationError(f"Invalid {input_type} numeric value: {e}")


def validate_url_enhanced(url: str,
                          require_https: bool = True,
                          allow_private: bool = False,
                          check_domain_whitelist: bool = True) -> bool:
    """
    Enhanced URL validation with comprehensive security checks.

    Args:
        url: URL to validate
        require_https: Whether to require HTTPS
        allow_private: Whether to allow private IP addresses
        check_domain_whitelist: Whether to check against trusted domains

    Returns:
        True if URL is valid and safe

    Raises:
        ValidationError: If URL is invalid or unsafe
    """
    if not url:
        raise ValidationError("URL cannot be empty")

    try:
        # Length validation
        SecurityFilter.validate_input_length(url, 'url')

        # Encoding validation
        url = SecurityFilter.validate_encoding(url, 'url')

        # Check for injection patterns
        SecurityFilter.check_injection_patterns(url, 'url')

    except ValidationError:
        return False

    # Parse URL
    try:
        parsed = urlparse(url)
    except Exception as e:
        logger.warning(f"Failed to parse URL {url}: {e}")
        return False

    # Scheme validation
    if parsed.scheme not in ['http', 'https']:
        logger.warning(f"Invalid URL scheme: {parsed.scheme}")
        return False

    # HTTPS requirement
    if require_https and parsed.scheme != 'https':
        # Allow HTTP for localhost
        if parsed.hostname not in ['localhost', '127.0.0.1', '::1']:
            logger.warning(f"HTTPS required for non-localhost URL: {url}")
            return False

    # Hostname validation
    if not parsed.hostname:
        logger.warning(f"No hostname in URL: {url}")
        return False

    # Check for suspicious characters in hostname
    if re.search(r'[<>"\'\\\x00-\x1f\x7f-\x9f]', parsed.hostname):
        logger.warning(f"Suspicious characters in hostname: {parsed.hostname}")
        return False

    # IP address validation
    try:
        ip = ipaddress.ip_address(parsed.hostname)
        if not allow_private and (ip.is_private or ip.is_loopback or ip.is_link_local):
            logger.warning(f"Private IP address not allowed: {parsed.hostname}")
            return False
    except ipaddress.AddressValueError:
        # Not an IP address, continue with hostname validation
        pass

    # Port validation
    if parsed.port is not None:
        if not (1 <= parsed.port <= 65535):
            logger.warning(f"Invalid port number: {parsed.port}")
            return False
        # Block dangerous ports
        dangerous_ports = {22, 23, 25, 53, 135, 139, 445, 1433, 1521, 3306, 3389, 5432, 6379}
        if parsed.port in dangerous_ports:
            logger.warning(f"Dangerous port blocked: {parsed.port}")
            return False

    # Domain whitelist check
    if check_domain_whitelist and parsed.hostname:
        domain_parts = parsed.hostname.lower().split('.')
        if len(domain_parts) >= 2:
            base_domain = '.'.join(domain_parts[-2:])
            if base_domain not in TRUSTED_FEED_DOMAINS:
                logger.info(f"URL domain not in trusted list: {base_domain}")

    return True


def validate_file_path_enhanced(path: str,
                                allowed_extensions: Optional[List[str]] = None,
                                must_exist: bool = False,
                                allow_create: bool = True) -> bool:
    """
    Enhanced file path validation with security checks.

    Args:
        path: File path to validate
        allowed_extensions: List of allowed file extensions
        must_exist: Whether file must already exist
        allow_create: Whether file creation is allowed

    Returns:
        True if path is valid and safe

    Raises:
        ValidationError: If path is invalid or unsafe
    """
    if not path:
        raise ValidationError("File path cannot be empty")

    try:
        # Length validation
        SecurityFilter.validate_input_length(path, 'path')

        # Encoding validation
        path = SecurityFilter.validate_encoding(path, 'path')

    except ValidationError:
        return False

    # Convert to absolute path
    try:
        abs_path = os.path.abspath(path)
    except (OSError, ValueError) as e:
        logger.warning(f"Invalid file path: {e}")
        return False

    # Check for path traversal
    if '..' in path or abs_path != os.path.normpath(abs_path):
        logger.warning(f"Path traversal detected: {path}")
        return False

    # Check against dangerous characters
    dangerous_chars = set('<>:"|?*\x00-\x1f\x7f-\x9f')
    if any(char in path for char in dangerous_chars):
        logger.warning(f"Dangerous characters in path: {path}")
        return False

    # Directory boundary check (must be under user home or system temp)
    try:
        import pathlib
        abs_path_obj = pathlib.Path(abs_path).resolve()
        home_dir = pathlib.Path.home().resolve()
        temp_dir = pathlib.Path('/tmp').resolve()

        # Check if path is under allowed directories
        try:
            abs_path_obj.relative_to(home_dir)
        except ValueError:
            try:
                abs_path_obj.relative_to(temp_dir)
            except ValueError:
                logger.warning(f"Path outside allowed directories: {abs_path}")
                return False

    except (OSError, ValueError) as e:
        logger.warning(f"Path resolution failed: {e}")
        return False

    # Extension validation
    if allowed_extensions:
        file_ext = os.path.splitext(path)[1].lower()
        if file_ext not in [ext.lower() for ext in allowed_extensions]:
            logger.warning(f"File extension not allowed: {file_ext}")
            return False

    # Existence checks
    if must_exist and not os.path.exists(abs_path):
        logger.warning(f"Required file does not exist: {abs_path}")
        return False

    if not allow_create and not os.path.exists(abs_path):
        logger.warning(f"File creation not allowed: {abs_path}")
        return False

    return True


def sanitize_command_argument(arg: str) -> str:
    """
    Sanitize a command line argument to prevent injection with enhanced security.

    Args:
        arg: Argument to sanitize

    Returns:
        Sanitized argument
    """
    if not isinstance(arg, str):
        raise ValidationError("Command argument must be a string")

    try:
        # Length validation
        SecurityFilter.validate_input_length(arg, 'command')

        # Encoding validation
        arg = SecurityFilter.validate_encoding(arg, 'command')

        # Check for injection patterns
        SecurityFilter.check_injection_patterns(arg, 'command')

    except ValidationError as e:
        logger.warning(f"Command argument validation failed: {e}")
        # Return empty string for safety
        return ""

    # Use context-specific sanitization
    sanitized = SecurityFilter.sanitize_for_context(arg, 'shell')

    # Additional length limit after sanitization
    if len(sanitized) > 1024:
        sanitized = sanitized[:1024]
        logger.warning("Command argument truncated due to length")

    return sanitized


def validate_feed_url(url: str, require_https: bool = True) -> bool:
    """
    Validate an RSS feed URL for security.

    Args:
        url: URL to validate
        require_https: Whether to require HTTPS (can be False for localhost)

    Returns:
        True if URL is valid and safe
    """
    if not url:
        return False

    # Basic URL format check
    if not re.match(FEED_URL_PATTERN, url):
        logger.warning(f"Invalid URL format: {url}")
        return False

    # Parse URL
    try:
        parsed = urlparse(url)
    except Exception as e:
        logger.warning(f"Failed to parse URL {url}: {e}")
        return False

    # Check scheme
    if parsed.scheme not in ['http', 'https']:
        logger.warning(f"Invalid URL scheme: {parsed.scheme}")
        return False

    # Check for HTTPS requirement
    if require_https and parsed.scheme != 'https':
        # Allow HTTP for localhost/127.0.0.1
        if parsed.hostname not in ['localhost', '127.0.0.1', '::1']:
            logger.warning(f"HTTPS required for non-localhost URL: {url}")
            return False

    # Validate hostname
    if not parsed.hostname:
        logger.warning(f"No hostname in URL: {url}")
        return False

    # Check against trusted domains (optional)
    domain_parts = parsed.hostname.lower().split('.')
    if len(domain_parts) >= 2:
        base_domain = '.'.join(domain_parts[-2:])
        if base_domain not in TRUSTED_FEED_DOMAINS:
            logger.info(f"URL domain not in trusted list: {base_domain}")
            # This is just informational, not a hard failure

    return True


def validate_json_structure(data: dict[str, Any], required_keys: List[str]) -> bool:
    """
    Validate JSON data structure.

    Args:
        data: Dictionary to validate
        required_keys: List of required keys

    Returns:
        True if structure is valid
    """
    if not isinstance(data, dict):
        logger.warning("Data is not a dictionary")
        return False

    for key in required_keys:
        if key not in data:
            logger.warning(f"Missing required key: {key}")
            return False

    return True


def sanitize_html(text: str) -> str:
    """
    Remove potentially dangerous HTML from text.

    Args:
        text: Text to sanitize

    Returns:
        Sanitized text
    """
    if not text:
        return ""

    # Remove all HTML tags
    text = re.sub(r'<[^>]+>', '', text)

    # Decode HTML entities manually (basic ones)
    html_entities = {
        '&amp;': '&',
        '&lt;': '<',
        '&gt;': '>',
        '&quot;': '"',
        '&#39;': "'",
        '&nbsp;': ' ',
    }

    for entity, char in html_entities.items():
        text = text.replace(entity, char)

    # Remove multiple whitespaces
    text = re.sub(r'\s+', ' ', text).strip()

    return text


def validate_config_value(key: str, value: Any, value_type: type,
                          min_value: Optional[Any] = None,
                          max_value: Optional[Any] = None) -> bool:
    """
    Validate a configuration value.

    Args:
        key: Configuration key
        value: Value to validate
        value_type: Expected type
        min_value: Minimum allowed value
        max_value: Maximum allowed value

    Returns:
        True if value is valid
    """
    # Type check
    if not isinstance(value, value_type):
        logger.warning(f"Invalid type for {key}: expected {value_type.__name__}, got {type(value).__name__}")
        return False

    # Range check for numeric types
    if value_type in (int, float):
        if min_value is not None and value < min_value:
            logger.warning(f"Value for {key} below minimum: {value} < {min_value}")
            return False
        if max_value is not None and value > max_value:
            logger.warning(f"Value for {key} above maximum: {value} > {max_value}")
            return False

    # Length check for strings
    if value_type == str and isinstance(value, str):
        if min_value is not None and len(value) < min_value:
            logger.warning(f"String {key} too short: {len(value)} < {min_value}")
            return False
        if max_value is not None and len(value) > max_value:
            logger.warning(f"String {key} too long: {len(value)} > {max_value}")
            return False

    return True


def validate_config_path(path: str) -> bool:
    """
    Validate a configuration file path for security.

    Args:
        path: Path to validate

    Returns:
        True if path is valid and safe

    Raises:
        ValueError: If path is unsafe
    """
    if not path:
        raise ValueError("Empty path not allowed")

    import os
    from pathlib import Path

    try:
        # Convert to absolute path and resolve symlinks
        resolved_path = Path(path).resolve()

        # Check for path traversal attempts
        if '..' in str(resolved_path) or '..' in path:
            raise ValueError(f"Path traversal detected: {path}")

        # Only allow paths under user's home directory or /tmp
        home_dir = Path.home().resolve()
        tmp_dir = Path('/tmp').resolve()
        config_dir = home_dir / '.config'

        allowed_parents = [home_dir, tmp_dir, config_dir]

        # Check if path is under any allowed parent
        is_allowed = False
        for parent in allowed_parents:
            try:
                resolved_path.relative_to(parent)
                is_allowed = True
                break
            except ValueError:
                continue

        if not is_allowed:
            raise ValueError(f"Config file must be under home directory or /tmp: {path}")

        # Check file extension
        if resolved_path.suffix.lower() not in ['.json', '.conf', '.cfg']:
            raise ValueError(f"Invalid config file extension: {resolved_path.suffix}")

        # Check parent directory accessibility using atomic operations
        parent_dir = resolved_path.parent
        try:
            # Try to create a temporary file to test writability atomically
            import tempfile
            with tempfile.NamedTemporaryFile(dir=parent_dir, delete=True):
                pass  # Successfully created and deleted temp file
        except (OSError, PermissionError) as e:
            raise ValueError(f"Parent directory not accessible: {parent_dir} - {e}")

        # If file exists, validate it using atomic operations
        try:
            if resolved_path.is_file():
                # Test readability by attempting to open
                with open(resolved_path, 'r'):
                    pass  # Successfully opened for reading
            elif resolved_path.exists():
                # Path exists but is not a regular file
                raise ValueError(f"Path is not a regular file: {path}")
        except FileNotFoundError:
            # File doesn't exist - this is fine for config validation
            pass
        except (OSError, PermissionError) as e:
            raise ValueError(f"File not accessible: {path} - {e}")

        logger.info(f"Config path validated: {resolved_path}")
        return True

    except Exception as e:
        logger.error(f"Config path validation failed: {e}")
        raise ValueError(f"Invalid config path: {str(e)}")


def validate_log_path(path: str) -> bool:
    """
    Validate a log file path for security.

    Args:
        path: Path to validate

    Returns:
        True if path is valid and safe

    Raises:
        ValueError: If path is unsafe
    """
    if not path:
        raise ValueError("Empty path not allowed")

    import os
    from pathlib import Path

    try:
        # Convert to absolute path and resolve symlinks
        resolved_path = Path(path).resolve()

        # Check for path traversal attempts
        if '..' in str(resolved_path) or '..' in path:
            raise ValueError(f"Path traversal detected: {path}")

        # Only allow paths under user's home directory, /tmp, or /var/log (if writable)
        home_dir = Path.home().resolve()
        tmp_dir = Path('/tmp').resolve()
        log_dir = Path('/var/log').resolve()

        allowed_parents = [home_dir, tmp_dir]

        # Add /var/log if it's writable (using atomic test)
        try:
            import tempfile
            with tempfile.NamedTemporaryFile(dir=log_dir, delete=True):
                allowed_parents.append(log_dir)
        except (OSError, PermissionError):
            # /var/log not writable or doesn't exist, skip it
            pass

        # Check if path is under any allowed parent
        is_allowed = False
        for parent in allowed_parents:
            try:
                resolved_path.relative_to(parent)
                is_allowed = True
                break
            except ValueError:
                continue

        if not is_allowed:
            raise ValueError(f"Log file must be under allowed directories: {path}")

        # Check file extension
        if resolved_path.suffix.lower() not in ['.log', '.txt', '']:
            raise ValueError(f"Invalid log file extension: {resolved_path.suffix}")

        # Check parent directory accessibility using atomic operations
        parent_dir = resolved_path.parent
        try:
            # Try to create a temporary file to test writability atomically
            import tempfile
            with tempfile.NamedTemporaryFile(dir=parent_dir, delete=True):
                pass  # Successfully created and deleted temp file
        except (OSError, PermissionError) as e:
            raise ValueError(f"Parent directory not accessible: {parent_dir} - {e}")

        logger.info(f"Log path validated: {resolved_path}")
        return True

    except Exception as e:
        logger.error(f"Log path validation failed: {e}")
        raise ValueError(f"Invalid log path: {str(e)}")


def validate_config_json(data: dict[str, Any]) -> bool:
    """
    Validate configuration JSON structure and content for security.

    Args:
        data: Parsed JSON data to validate

    Returns:
        True if data is valid

    Raises:
        ValueError: If data structure is invalid or unsafe
    """
    if not isinstance(data, dict):
        raise ValueError("Configuration must be a JSON object")

    # Define allowed configuration keys and their types
    allowed_keys: Dict[str, Union[type, tuple[type, ...]]] = {
        'cache_ttl_hours': int,
        'feeds': list,
        'extra_patterns': list,
        'critical_packages': list,
        'distribution': str,
        'max_news_items': int,
        'max_news_age_days': int,
        'non_interactive': bool,
        'log_file': (str, type(None)),
        'auto_refresh_feeds': bool,
        'theme': str,
        'debug_mode': bool,
        'verbose_logging': bool,
        'update_history_enabled': bool,
        'update_history_retention_days': int
    }

    # Check for unknown keys
    for key in data.keys():
        if key not in allowed_keys:
            logger.warning(f"Unknown configuration key ignored: {key}")

    # Validate known keys
    for key, expected_type in allowed_keys.items():
        if key in data:
            value = data[key]
            if not isinstance(value, expected_type):
                expected_name = getattr(expected_type, '__name__', str(expected_type))
                raise ValueError(
                    f"Invalid type for '{key}': expected {expected_name}, got {type(value).__name__}")

            # Additional validation for specific keys
            if key == 'theme' and value not in ['light', 'dark']:
                raise ValueError(f"Invalid theme value: {value}")

            elif key == 'distribution' and not re.match(r'^[a-zA-Z0-9_-]+$', value):
                raise ValueError(f"Invalid distribution name: {value}")

            elif key in ['max_news_items', 'max_news_age_days', 'cache_ttl_hours', 'update_history_retention_days']:
                if value <= 0:
                    raise ValueError(f"'{key}' must be positive")

                # Security limits
                if key == 'max_news_items' and value > 1000:
                    raise ValueError(f"'{key}' exceeds security limit (1000)")
                elif key == 'max_news_age_days' and value > 365:
                    raise ValueError(f"'{key}' exceeds security limit (365 days)")
                elif key == 'cache_ttl_hours' and value > 168:  # 1 week max
                    raise ValueError(f"'{key}' exceeds security limit (168 hours)")
                elif key == 'update_history_retention_days' and value > 3650:  # 10 years max
                    raise ValueError(f"'{key}' exceeds security limit (3650 days)")

    # Validate feeds array structure
    if 'feeds' in data:
        feeds = data['feeds']
        if not isinstance(feeds, list):
            raise ValueError(f"Invalid type for 'feeds': expected list, got {type(feeds).__name__}")

        for i, feed in enumerate(feeds):
            if not isinstance(feed, dict):
                raise ValueError(f"Feed {i} must be an object")

            # Validate required feed fields
            required_feed_keys = ['name', 'url']
            for req_key in required_feed_keys:
                if req_key not in feed:
                    raise ValueError(f"Feed {i} missing required field: {req_key}")
                if not isinstance(feed[req_key], str):
                    raise ValueError(f"Feed {i} field '{req_key}' must be a string")

            # Validate feed URL
            if not validate_feed_url(feed['url'], require_https=True):
                raise ValueError(f"Feed {i} has invalid URL: {feed['url']}")

            # Validate optional feed fields
            if 'priority' in feed:
                if not isinstance(feed['priority'], int) or feed['priority'] < 1:
                    raise ValueError(f"Feed {i} priority must be positive integer")

            if 'type' in feed:
                if feed['type'] not in ['news', 'package']:
                    raise ValueError(f"Feed {i} has invalid type: {feed['type']}")

            if 'enabled' in feed:
                if not isinstance(feed['enabled'], bool):
                    raise ValueError(f"Feed {i} 'enabled' must be boolean")

    # Validate string arrays
    for key in ['extra_patterns', 'critical_packages']:
        if key in data:
            arr = data[key]
            if not isinstance(arr, list):
                raise ValueError(f"'{key}' must be an array")

            for i, item in enumerate(arr):
                if not isinstance(item, str):
                    raise ValueError(f"'{key}[{i}]' must be a string")

                # Validate package names
                if key == 'critical_packages':
                    if not validate_package_name(item):
                        raise ValueError(f"Invalid package name in '{key}': {item}")

                # Validate patterns
                elif key == 'extra_patterns':
                    if len(item) > 100:  # Reasonable limit
                        raise ValueError(f"Pattern too long in '{key}': {item}")

    logger.info("Configuration JSON validation passed")
    return True


def sanitize_config_json(data: dict[str, Any]) -> dict[str, Any]:
    """
    Sanitize and normalize configuration JSON data.

    Args:
        data: Raw configuration data

    Returns:
        Sanitized configuration data
    """
    if not isinstance(data, dict):
        raise ValueError("Configuration must be a JSON object")

    # Create a clean copy with only allowed keys
    allowed_keys = {
        'cache_ttl_hours': int,
        'feeds': list,
        'extra_patterns': list,
        'critical_packages': list,
        'distribution': str,
        'max_news_items': int,
        'max_news_age_days': int,
        'non_interactive': bool,
        'log_file': (str, type(None)),
        'auto_refresh_feeds': bool,
        'theme': str,
        'debug_mode': bool,
        'verbose_logging': bool,
        'update_history_enabled': bool,
        'update_history_retention_days': int
    }

    sanitized: dict[str, Any] = {}
    for key, expected_type in allowed_keys.items():
        if key in data:
            value = data[key]

            # Type conversion with validation
            try:
                if expected_type is int:
                    sanitized[key] = int(value)
                elif expected_type is bool:
                    sanitized[key] = bool(value)
                elif expected_type is str:
                    sanitized[key] = str(value)
                elif expected_type is list:
                    if isinstance(value, list):
                        sanitized[key] = value.copy()
                elif expected_type == (str, type(None)):
                    sanitized[key] = str(value) if value is not None else None
            except (ValueError, TypeError) as e:
                logger.warning(f"Failed to convert '{key}': {e}")

    return sanitized


def sanitize_input(input_str: str, input_type: str = "generic") -> str:
    """
    Sanitize user input based on input type.

    Args:
        input_str: Input string to sanitize
        input_type: Type of input (generic, filename, url, etc.)

    Returns:
        Sanitized string

    Raises:
        ValueError: If input cannot be sanitized safely
    """
    if not isinstance(input_str, str):
        raise ValueError("Input must be a string")

    # Remove null bytes and control characters
    sanitized = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', input_str)

    # Normalize unicode
    import unicodedata
    sanitized = unicodedata.normalize('NFKC', sanitized)

    # Type-specific sanitization
    if input_type == "filename":
        # Remove path separators and dangerous characters
        sanitized = re.sub(r'[<>:"/\\|?*]', '', sanitized)
        sanitized = re.sub(r'\.\.+', '.', sanitized)  # Remove multiple dots
        sanitized = sanitized.strip('. ')  # Remove leading/trailing dots and spaces

        if not sanitized or sanitized in {'.', '..'}:
            raise ValueError("Invalid filename after sanitization")

    elif input_type == "url":
        # Basic URL validation and sanitization
        if not re.match(r'^https?://', sanitized):
            raise ValueError("URL must start with http:// or https://")

        # Remove dangerous URL characters
        sanitized = re.sub(r'[<>"\'\\]', '', sanitized)

    elif input_type == "package_name":
        # Use existing package name validation
        if not validate_package_name(sanitized):
            raise ValueError("Invalid package name")

    elif input_type == "feed_name":
        # Sanitize feed names
        sanitized = re.sub(r'[<>"/\\|?*\x00-\x1f]', '', sanitized)
        sanitized = sanitized.strip()

        if len(sanitized) > 100:
            sanitized = sanitized[:100]

        if not sanitized:
            raise ValueError("Feed name cannot be empty")

    elif input_type == "search_term":
        # Sanitize search terms
        sanitized = re.sub(r'[<>"/\\|*\x00-\x1f]', '', sanitized)
        sanitized = re.sub(r'\s+', ' ', sanitized).strip()  # Normalize whitespace

        if len(sanitized) > 200:
            sanitized = sanitized[:200]

    # Generic sanitization for all types
    sanitized = sanitized.strip()

    # Final length check
    if len(sanitized) > 1000:  # Global maximum
        raise ValueError("Input too long after sanitization")

    return sanitized


def validate_boolean_input(value: str) -> bool:
    """
    Validate and convert boolean input.

    Args:
        value: String value to validate

    Returns:
        Boolean value

    Raises:
        ValueError: If value is invalid
    """
    if not isinstance(value, str):
        raise ValueError("Value must be a string")

    value = value.strip().lower()

    if value in {'true', '1', 'yes', 'on', 'enabled'}:
        return True
    elif value in {'false', '0', 'no', 'off', 'disabled'}:
        return False
    else:
        raise ValueError("Invalid boolean value")


def create_safe_error_message(error_type: str, details: Optional[str] = None, safe_details: Optional[str] = None) -> str:
    """
    Create error messages that don't disclose sensitive information.

    Args:
        error_type: Type of error (validation, permission, etc.)
        details: Full error details (will be sanitized)
        safe_details: Pre-sanitized safe details to include

    Returns:
        Safe error message for user display
    """
    from .logger import sanitize_log_message

    base_messages = {
        'validation': 'Input validation failed',
        'permission': 'Permission denied',
        'file_not_found': 'File not found',
        'network': 'Network operation failed',
        'security': 'Security policy violation',
        'configuration': 'Configuration error',
        'parsing': 'Data parsing failed',
        'authentication': 'Authentication failed',
        'timeout': 'Operation timed out',
        'resource': 'Resource limit exceeded',
        'encoding': 'Text encoding error',
        'format': 'Invalid format',
        'range': 'Value out of range',
        'type': 'Invalid data type',
        'regex': 'Pattern matching failed',
        'command': 'Command execution error',
        'path': 'Path access error',
        'url': 'URL processing error',
    }

    base_msg = base_messages.get(error_type, 'Operation failed')

    if safe_details:
        return f"{base_msg}: {safe_details}"
    elif details:
        # Sanitize the details
        sanitized = sanitize_log_message(details)
        # Further remove any remaining sensitive patterns
        sanitized = re.sub(r'/[^/]*\.json', '/[CONFIG_FILE]', sanitized)
        sanitized = re.sub(r'/[^/]*\.log', '/[LOG_FILE]', sanitized)
        sanitized = re.sub(r'/[^/]*\.py', '/[SCRIPT_FILE]', sanitized)
        sanitized = re.sub(r'/home/[^/]+', '/home/[USER]', sanitized)
        sanitized = re.sub(r'line \d+', 'line [NUMBER]', sanitized)
        sanitized = re.sub(r'pid \d+', 'pid [NUMBER]', sanitized)
        return f"{base_msg}: {sanitized}"
    else:
        return base_msg


class SecureErrorHandler:
    """
    Centralized secure error handling that prevents information disclosure.
    """

    # Error codes for internal tracking (not shown to users)
    ERROR_CODES = {
        'VALIDATION_FAILED': 'VAL001',
        'PATH_TRAVERSAL': 'SEC001',
        'INJECTION_DETECTED': 'SEC002',
        'LENGTH_EXCEEDED': 'SEC003',
        'ENCODING_ERROR': 'SEC004',
        'PERMISSION_DENIED': 'SEC005',
        'NETWORK_ERROR': 'NET001',
        'TIMEOUT_ERROR': 'NET002',
        'RESOURCE_LIMIT': 'RES001',
        'FORMAT_ERROR': 'FMT001',
        'TYPE_ERROR': 'TYP001',
        'REGEX_ERROR': 'REG001',
        'CONFIG_ERROR': 'CFG001',
        'COMMAND_ERROR': 'CMD001',
    }

    @classmethod
    def handle_validation_error(cls, context: str, original_error: Exception,
                                user_input: Optional[str] = None) -> str:
        """
        Handle validation errors securely.

        Args:
            context: Context where error occurred
            original_error: Original exception
            user_input: User input that caused error (will be sanitized)

        Returns:
            Safe error message for display
        """
        # Log full error details for debugging (sanitized)
        from .logger import get_logger
        logger = get_logger(__name__)

        error_code = cls._get_error_code(original_error)

        # Sanitize user input for logging
        if user_input:
            safe_input = cls._sanitize_for_logging(user_input)
            logger.warning(f"Validation error in {context} [{error_code}]: {original_error} (input: {safe_input})")
        else:
            logger.warning(f"Validation error in {context} [{error_code}]: {original_error}")

        # Return safe message to user
        if isinstance(original_error, ValidationError):
            return create_safe_error_message('validation', str(original_error))
        elif 'path' in context.lower() or 'traversal' in str(original_error).lower():
            return create_safe_error_message('path', safe_details='Invalid file path')
        elif 'inject' in str(original_error).lower():
            return create_safe_error_message('security', safe_details='Input contains invalid characters')
        elif 'length' in str(original_error).lower() or 'too long' in str(original_error).lower():
            return create_safe_error_message('validation', safe_details='Input too long')
        elif 'encoding' in str(original_error).lower() or 'unicode' in str(original_error).lower():
            return create_safe_error_message('encoding', safe_details='Invalid text encoding')
        else:
            return create_safe_error_message('validation', safe_details='Invalid input format')

    @classmethod
    def handle_network_error(cls, context: str, original_error: Exception,
                             url: Optional[str] = None) -> str:
        """
        Handle network errors securely.

        Args:
            context: Context where error occurred
            original_error: Original exception
            url: URL that caused error (will be sanitized)

        Returns:
            Safe error message for display
        """
        from .logger import get_logger
        logger = get_logger(__name__)

        error_code = cls._get_error_code(original_error)

        # Sanitize URL for logging
        if url:
            safe_url = cls._sanitize_url_for_logging(url)
            logger.warning(f"Network error in {context} [{error_code}]: {original_error} (url: {safe_url})")
        else:
            logger.warning(f"Network error in {context} [{error_code}]: {original_error}")

        # Return safe message based on error type
        error_str = str(original_error).lower()
        if 'timeout' in error_str:
            return create_safe_error_message('timeout', safe_details='Network request timed out')
        elif 'connection' in error_str or 'refused' in error_str:
            return create_safe_error_message('network', safe_details='Cannot connect to server')
        elif 'ssl' in error_str or 'certificate' in error_str:
            return create_safe_error_message('network', safe_details='SSL/TLS connection failed')
        elif 'dns' in error_str or 'resolve' in error_str:
            return create_safe_error_message('network', safe_details='Cannot resolve hostname')
        elif '404' in error_str:
            return create_safe_error_message('network', safe_details='Resource not found')
        elif '403' in error_str:
            return create_safe_error_message('permission', safe_details='Access denied')
        elif '500' in error_str or '502' in error_str or '503' in error_str:
            return create_safe_error_message('network', safe_details='Server error')
        else:
            return create_safe_error_message('network', safe_details='Network operation failed')

    @classmethod
    def handle_file_error(cls, context: str, original_error: Exception,
                          file_path: Optional[str] = None) -> str:
        """
        Handle file operation errors securely.

        Args:
            context: Context where error occurred
            original_error: Original exception
            file_path: File path that caused error (will be sanitized)

        Returns:
            Safe error message for display
        """
        from .logger import get_logger
        logger = get_logger(__name__)

        error_code = cls._get_error_code(original_error)

        # Sanitize file path for logging
        if file_path:
            safe_path = cls._sanitize_path_for_logging(file_path)
            logger.warning(f"File error in {context} [{error_code}]: {original_error} (path: {safe_path})")
        else:
            logger.warning(f"File error in {context} [{error_code}]: {original_error}")

        # Return safe message based on error type
        error_str = str(original_error).lower()
        if 'permission' in error_str or 'access' in error_str:
            return create_safe_error_message('permission', safe_details='File access denied')
        elif 'not found' in error_str or 'no such file' in error_str:
            return create_safe_error_message('file_not_found', safe_details='File not found')
        elif 'directory' in error_str:
            return create_safe_error_message('file_not_found', safe_details='Directory not found')
        elif 'space' in error_str or 'disk' in error_str:
            return create_safe_error_message('resource', safe_details='Insufficient disk space')
        elif 'readonly' in error_str or 'read-only' in error_str:
            return create_safe_error_message('permission', safe_details='File is read-only')
        else:
            return create_safe_error_message('file_not_found', safe_details='File operation failed')

    @classmethod
    def handle_command_error(cls, context: str, original_error: Exception,
                             command: Optional[str] = None) -> str:
        """
        Handle command execution errors securely.

        Args:
            context: Context where error occurred
            original_error: Original exception
            command: Command that caused error (will be sanitized)

        Returns:
            Safe error message for display
        """
        from .logger import get_logger
        logger = get_logger(__name__)

        error_code = cls._get_error_code(original_error)

        # Sanitize command for logging
        if command:
            safe_command = cls._sanitize_command_for_logging(command)
            logger.warning(f"Command error in {context} [{error_code}]: {original_error} (cmd: {safe_command})")
        else:
            logger.warning(f"Command error in {context} [{error_code}]: {original_error}")

        # Return safe message based on error type
        error_str = str(original_error).lower()
        if 'timeout' in error_str:
            return create_safe_error_message('timeout', safe_details='Command execution timed out')
        elif 'permission' in error_str or 'denied' in error_str:
            return create_safe_error_message('permission', safe_details='Insufficient privileges')
        elif 'not found' in error_str or 'command not found' in error_str:
            return create_safe_error_message('command', safe_details='Command not available')
        elif 'cancelled' in error_str or 'interrupted' in error_str:
            return create_safe_error_message('command', safe_details='Operation cancelled')
        else:
            return create_safe_error_message('command', safe_details='Command execution failed')

    @classmethod
    def _get_error_code(cls, error: Exception) -> str:
        """Get internal error code for tracking."""
        error_str = str(error).lower()
        error_type = type(error).__name__.lower()

        if 'validation' in error_str or isinstance(error, ValidationError):
            return cls.ERROR_CODES['VALIDATION_FAILED']
        elif 'traversal' in error_str or 'path' in error_str:
            return cls.ERROR_CODES['PATH_TRAVERSAL']
        elif 'inject' in error_str:
            return cls.ERROR_CODES['INJECTION_DETECTED']
        elif 'length' in error_str or 'too long' in error_str:
            return cls.ERROR_CODES['LENGTH_EXCEEDED']
        elif 'encoding' in error_str or 'unicode' in error_str:
            return cls.ERROR_CODES['ENCODING_ERROR']
        elif 'permission' in error_str:
            return cls.ERROR_CODES['PERMISSION_DENIED']
        elif 'timeout' in error_str:
            return cls.ERROR_CODES['TIMEOUT_ERROR']
        elif 'network' in error_str or 'connection' in error_str:
            return cls.ERROR_CODES['NETWORK_ERROR']
        elif 'resource' in error_str or 'limit' in error_str:
            return cls.ERROR_CODES['RESOURCE_LIMIT']
        elif 'format' in error_str:
            return cls.ERROR_CODES['FORMAT_ERROR']
        elif 'type' in error_type:
            return cls.ERROR_CODES['TYPE_ERROR']
        elif 'regex' in error_str or 'pattern' in error_str:
            return cls.ERROR_CODES['REGEX_ERROR']
        elif 'config' in error_str:
            return cls.ERROR_CODES['CONFIG_ERROR']
        elif 'command' in error_str:
            return cls.ERROR_CODES['COMMAND_ERROR']
        else:
            return 'UNK001'  # Unknown error

    @classmethod
    def _sanitize_for_logging(cls, text: str, max_length: int = 100) -> str:
        """Sanitize text for safe logging."""
        if not text:
            return '[EMPTY]'

        # Truncate if too long
        if len(text) > max_length:
            text = text[:max_length] + '...'

        # Remove sensitive patterns
        sanitized = re.sub(r'/home/[^/\s]+', '/home/[USER]', text)
        sanitized = re.sub(r'password[=:]\s*\S+', 'password=[REDACTED]', sanitized, flags=re.IGNORECASE)
        sanitized = re.sub(r'token[=:]\s*\S+', 'token=[REDACTED]', sanitized, flags=re.IGNORECASE)
        sanitized = re.sub(r'api_?key[=:]\s*\S+', 'api_key=[REDACTED]', sanitized, flags=re.IGNORECASE)

        # Remove control characters
        sanitized = re.sub(r'[\x00-\x1f\x7f-\x9f]', '[CTRL]', sanitized)

        return sanitized

    @classmethod
    def _sanitize_url_for_logging(cls, url: str) -> str:
        """Sanitize URL for safe logging."""
        try:
            parsed = urlparse(url)
            # Remove credentials if present
            safe_url = f"{parsed.scheme}://[HOST]{parsed.path}"
            if parsed.query:
                safe_url += "?[QUERY]"
            if parsed.fragment:
                safe_url += "#[FRAGMENT]"
            return safe_url
        except BaseException:
            return '[INVALID_URL]'

    @classmethod
    def _sanitize_path_for_logging(cls, path: str) -> str:
        """Sanitize file path for safe logging."""
        if not path:
            return '[EMPTY_PATH]'

        # Replace sensitive parts
        sanitized = re.sub(r'/home/[^/\s]+', '/home/[USER]', path)
        sanitized = re.sub(r'\.json$', '.[CONFIG]', sanitized)
        sanitized = re.sub(r'\.log$', '.[LOG]', sanitized)

        # Show only filename if path is very long
        if len(sanitized) > 50:
            import os
            return f"[PATH]/{os.path.basename(sanitized)}"

        return sanitized

    @classmethod
    def _sanitize_command_for_logging(cls, command: str) -> str:
        """Sanitize command for safe logging."""
        if not command:
            return '[EMPTY_CMD]'

        # Only show the base command, not arguments
        parts = command.split()
        if parts:
            import os
            base_cmd = os.path.basename(parts[0])
            if len(parts) > 1:
                return f"{base_cmd} [ARGS]"
            else:
                return base_cmd

        return '[INVALID_CMD]'


def safe_str_conversion(value: Any, context: str = "unknown") -> str:
    """
    Safely convert any value to string for display purposes.

    Args:
        value: Value to convert
        context: Context for error handling

    Returns:
        Safe string representation
    """
    try:
        if value is None:
            return "[NULL]"
        elif isinstance(value, str):
            # Sanitize string content
            sanitized = re.sub(r'[\x00-\x1f\x7f-\x9f]', '[CTRL]', value)
            if len(sanitized) > 200:
                sanitized = sanitized[:200] + "..."
            return sanitized
        elif isinstance(value, bytes):
            try:
                return value.decode('utf-8', errors='replace')[:200]
            except BaseException:
                return "[BINARY_DATA]"
        elif isinstance(value, (int, float, bool)):
            return str(value)
        elif isinstance(value, (list, tuple)):
            if len(value) > 10:
                return f"[{type(value).__name__} with {len(value)} items]"
            else:
                return f"[{type(value).__name__}]"
        elif isinstance(value, dict):
            return f"[dict with {len(value)} keys]"
        else:
            return f"[{type(value).__name__}]"
    except Exception:
        return f"[{context.upper()}_VALUE]"


def validate_and_set_locale(locale_string: str, category: Optional[int] = None) -> bool:
    """
    Validate and safely set locale to prevent injection attacks.

    Args:
        locale_string: Locale string from environment variable
        category: Locale category (e.g., locale.LC_TIME)

    Returns:
        True if locale was successfully set, False otherwise
    """
    import locale
    from ..utils.logger import get_logger

    logger = get_logger(__name__)
    
    if category is None:
        category = locale.LC_TIME

    # Whitelist of safe, known locales
    SAFE_LOCALES = {
        'C', 'POSIX', 'en_US', 'en_GB', 'en_CA', 'en_AU', 'en_NZ',
        'de_DE', 'de_AT', 'de_CH', 'fr_FR', 'fr_CA', 'fr_CH',
        'es_ES', 'es_MX', 'es_AR', 'it_IT', 'pt_PT', 'pt_BR',
        'ru_RU', 'ja_JP', 'ko_KR', 'zh_CN', 'zh_TW', 'zh_HK',
        'nl_NL', 'sv_SE', 'no_NO', 'da_DK', 'fi_FI', 'pl_PL',
        'cs_CZ', 'hu_HU', 'tr_TR', 'ar_SA', 'he_IL', 'th_TH'
    }

    if not locale_string:
        logger.debug("Empty locale string provided")
        return False

    # Extract base locale (e.g., 'en_US.UTF-8' -> 'en_US')
    try:
        base_locale = locale_string.split('.')[0].split('@')[0]

        # Additional validation: check for suspicious characters
        if not re.match(r'^[a-zA-Z_]+$', base_locale):
            logger.warning(f"Locale contains suspicious characters: {locale_string}")
            return False

        # Length check to prevent buffer overflow attempts
        if len(base_locale) > 32:
            logger.warning(f"Locale string too long: {locale_string}")
            return False

    except Exception as e:
        logger.warning(f"Failed to parse locale string: {locale_string} - {e}")
        return False

    # Check against whitelist
    if base_locale not in SAFE_LOCALES:
        logger.warning(f"Unsafe locale rejected: {locale_string} (base: {base_locale})")
        return False

    # Attempt to set the locale safely
    try:
        # Try with UTF-8 encoding first
        locale.setlocale(category, (base_locale, 'UTF-8'))
        logger.debug(f"Successfully set locale to: {base_locale}.UTF-8")
        return True

    except locale.Error:
        # Fallback: try without explicit encoding
        try:
            locale.setlocale(category, base_locale)
            logger.debug(f"Successfully set locale to: {base_locale}")
            return True
        except locale.Error as e2:
            logger.warning(f"Failed to set locale {locale_string}: {e2}")
            return False

    except Exception as e:
        logger.error(f"Unexpected error setting locale {locale_string}: {e}")
        return False


def get_safe_system_locale() -> str:
    """
    Get a safe system locale from environment variables with validation.

    Returns:
        Validated locale string or 'C' as safe fallback
    """
    import os
    from ..utils.logger import get_logger

    logger = get_logger(__name__)

    # Try environment variables in order of preference
    env_vars = ['LC_TIME', 'LC_ALL', 'LANG']

    for env_var in env_vars:
        locale_string = os.environ.get(env_var)
        if locale_string:
            # Validate the locale string
            if validate_and_set_locale(locale_string, None):  # Just validate, don't set
                logger.debug(f"Using validated locale from {env_var}: {locale_string}")
                return locale_string
            else:
                logger.warning(f"Invalid locale in {env_var}: {locale_string}")

    # Fallback to safe default
    logger.info("Using fallback locale: C")
    return 'C'


def validate_environment_variable(env_var: str, value: str, var_type: str = "string") -> bool:
    """
    Validate environment variable values for security.

    Args:
        env_var: Environment variable name
        value: Environment variable value
        var_type: Expected type (string, path, command, locale)

    Returns:
        True if value is safe to use

    Raises:
        ValueError: If value is unsafe
    """
    from ..utils.logger import get_logger
    logger = get_logger(__name__)

    if not value:
        raise ValueError(f"Environment variable {env_var} is empty")

    # Length check to prevent buffer overflow attempts
    if len(value) > 4096:
        raise ValueError(f"Environment variable {env_var} too long: {len(value)} chars")

    # Check for suspicious characters
    if '\x00' in value:
        raise ValueError(f"Environment variable {env_var} contains null bytes")

    # Check for control characters that could be used for injection
    import re
    if re.search(r'[\x01-\x08\x0B-\x0C\x0E-\x1F\x7F]', value):
        raise ValueError(f"Environment variable {env_var} contains control characters")

    # Type-specific validation
    if var_type == "path":
        # Path validation
        if not re.match(r'^[a-zA-Z0-9/._-]+$', value):
            raise ValueError(f"Environment variable {env_var} contains invalid path characters")

        # Prevent path traversal
        if '..' in value:
            raise ValueError(f"Environment variable {env_var} contains path traversal")

    elif var_type == "command":
        # Command validation
        if not re.match(r'^[a-zA-Z0-9/_.-]+$', value.split()[0]):
            raise ValueError(f"Environment variable {env_var} contains invalid command characters")

        # Check for shell metacharacters
        shell_chars = ['|', '&', ';', '(', ')', '<', '>', '`', '$', '*', '?', '[', ']', '{', '}']
        if any(char in value for char in shell_chars):
            raise ValueError(f"Environment variable {env_var} contains shell metacharacters")

    elif var_type == "locale":
        # Locale validation
        if not re.match(r'^[a-zA-Z_.-]+$', value):
            raise ValueError(f"Environment variable {env_var} contains invalid locale characters")

        # Check reasonable length for locale
        if len(value) > 32:
            raise ValueError(f"Environment variable {env_var} locale string too long")

    logger.debug(f"Validated environment variable {env_var}")
    return True


def get_safe_environment_variable(env_var: str, default: Optional[str] = None, var_type: str = "string") -> str:
    """
    Get environment variable with validation and safe fallback.

    Args:
        env_var: Environment variable name
        default: Default value if not set or invalid
        var_type: Expected type for validation

    Returns:
        Validated environment variable value or default
    """
    import os
    from ..utils.logger import get_logger
    logger = get_logger(__name__)

    value = os.environ.get(env_var)

    if value is None:
        if default is not None:
            logger.debug(f"Environment variable {env_var} not set, using default")
            return default
        else:
            raise ValueError(f"Required environment variable {env_var} not set")

    try:
        validate_environment_variable(env_var, value, var_type)
        return value
    except ValueError as e:
        logger.warning(f"Invalid environment variable {env_var}: {e}")
        if default is not None:
            logger.info(f"Using safe default for {env_var}")
            return default
        else:
            raise


def validate_editor_command(editor_env: str) -> str:
    """
    Validate and sanitize editor command from environment.

    Args:
        editor_env: EDITOR environment variable value

    Returns:
        Safe editor command name

    Raises:
        ValueError: If no safe editor found
    """
    from ..utils.logger import get_logger
    logger = get_logger(__name__)

    # Whitelist of safe editors
    SAFE_EDITORS = {
        'nano', 'vim', 'nvim', 'emacs', 'gedit', 'kate',
        'mousepad', 'leafpad', 'xed', 'pluma', 'code', 'subl',
        'vi', 'micro', 'joe'
    }

    # Fallback editors in order of preference
    FALLBACK_EDITORS = ['nano', 'vim', 'vi', 'emacs']

    try:
        # Validate the environment variable
        validate_environment_variable('EDITOR', editor_env, 'command')

        # Extract just the command name (no arguments)
        editor_cmd = editor_env.split()[0] if editor_env else 'nano'
        editor_name = os.path.basename(editor_cmd)

        # Check against whitelist
        if editor_name in SAFE_EDITORS:
            # Verify command exists and is secure
            from ..utils.subprocess_wrapper import SecureSubprocess
            if SecureSubprocess.check_command_exists(editor_name):
                logger.debug(f"Using validated editor: {editor_name}")
                return editor_name
            else:
                logger.warning(f"Editor {editor_name} not found or not secure")
        else:
            logger.warning(f"Editor {editor_name} not in safe list")

    except ValueError as e:
        logger.warning(f"Invalid EDITOR environment variable: {e}")

    # Try fallback editors
    from ..utils.subprocess_wrapper import SecureSubprocess
    for fallback in FALLBACK_EDITORS:
        if SecureSubprocess.check_command_exists(fallback):
            logger.info(f"Using fallback editor: {fallback}")
            return fallback

    raise ValueError("No safe text editor found")


def sanitize_environment_for_subprocess(env_dict: Optional[dict[str, str]] = None) -> dict[str, str]:
    """
    Sanitize environment dictionary for safe subprocess execution.

    Args:
        env_dict: Environment dictionary to sanitize (defaults to os.environ)

    Returns:
        Sanitized environment dictionary
    """
    import os
    from ..utils.logger import get_logger
    logger = get_logger(__name__)

    if env_dict is None:
        env_dict = os.environ.copy()

    sanitized_env = {}

    # Whitelist of safe environment variables
    SAFE_ENV_VARS = {
        'PATH', 'HOME', 'USER', 'USERNAME', 'LOGNAME', 'SHELL',
        'TERM', 'LANG', 'LC_ALL', 'LC_TIME', 'LC_CTYPE', 'LC_NUMERIC',
        'LC_COLLATE', 'LC_MONETARY', 'LC_MESSAGES', 'LC_PAPER',
        'LC_NAME', 'LC_ADDRESS', 'LC_TELEPHONE', 'LC_MEASUREMENT',
        'LC_IDENTIFICATION', 'TZ', 'TMPDIR', 'DISPLAY', 'XDG_RUNTIME_DIR'
    }

    for key, value in env_dict.items():
        # Only include whitelisted variables
        if key in SAFE_ENV_VARS:
            try:
                # Validate the value based on variable type
                var_type = "locale" if key.startswith('LC_') or key == 'LANG' else "string"
                if key == 'PATH':
                    # Special validation for PATH
                    validate_path_environment(value)
                else:
                    validate_environment_variable(key, value, var_type)

                sanitized_env[key] = value
            except ValueError as e:
                logger.warning(f"Excluding invalid environment variable {key}: {e}")
        else:
            logger.debug(f"Excluding non-whitelisted environment variable: {key}")

    return sanitized_env


def validate_path_environment(path_value: str) -> bool:
    """
    Validate PATH environment variable for security.

    Args:
        path_value: PATH environment variable value

    Returns:
        True if PATH is safe

    Raises:
        ValueError: If PATH contains unsafe elements
    """
    if not path_value:
        raise ValueError("PATH is empty")

    # Split PATH and validate each component
    paths = path_value.split(':')

    for path in paths:
        if not path:
            continue  # Empty path component is allowed

        # Check for suspicious characters
        if not re.match(r'^[a-zA-Z0-9/._-]+$', path):
            raise ValueError(f"PATH contains invalid characters: {path}")

        # Prevent relative paths in PATH
        if not path.startswith('/'):
            raise ValueError(f"PATH contains relative path: {path}")

        # Check for common unsafe directories
        unsafe_dirs = ['/tmp', '/var/tmp', '.']
        if any(unsafe in path for unsafe in unsafe_dirs):
            raise ValueError(f"PATH contains unsafe directory: {path}")

    return True
