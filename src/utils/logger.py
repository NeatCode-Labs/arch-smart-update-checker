"""
Logging configuration for Arch Smart Update Checker.
"""

# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations

import logging
import os
import threading
from pathlib import Path
from typing import Optional, Dict, Any
import sys
from datetime import datetime
import re  # Added for sanitize_log_message
import json  # Added for security log formatting


class ColoredFormatter(logging.Formatter):
    """Custom formatter with colors for terminal output."""

    COLORS = {
        'DEBUG': '\033[36m',    # Cyan
        'INFO': '\033[32m',     # Green
        'WARNING': '\033[33m',  # Yellow
        'ERROR': '\033[31m',    # Red
        'CRITICAL': '\033[35m',  # Magenta
        'RESET': '\033[0m'      # Reset
    }

    def format(self, record: logging.LogRecord) -> str:
        """Format log record with colors."""
        log_color = self.COLORS.get(record.levelname, self.COLORS['RESET'])
        reset_color = self.COLORS['RESET']

        # Apply color to the level name
        record.levelname = f"{log_color}{record.levelname}{reset_color}"

        return super().format(record)


# Global configuration for logging with thread synchronization
_global_config: Optional[Dict[str, Any]] = None
_log_file_path: Optional[str] = None
_security_log_path: Optional[str] = None  # Dedicated security log
_configured_loggers: set[str] = set()  # Track configured loggers to prevent duplicates
_logger_instances: Dict[str, logging.Logger] = {}  # Cache logger instances
_global_state_lock = threading.RLock()  # Reentrant lock for global state synchronization

# Rate limiting for security events
_security_event_counts: Dict[str, Dict[str, Any]] = {}  # event_type -> {count, first_time, last_time}
_security_rate_limit_window = 60  # seconds
_security_rate_limit_max = 10  # max events per window

# Configure root logger to prevent interference
logging.getLogger().handlers = []
logging.getLogger().setLevel(logging.WARNING)
logging.getLogger().propagate = False


def set_global_config(config: Dict[str, Any]) -> None:
    """
    Set global configuration for logging with thread safety.

    Args:
        config: Configuration dictionary
    """
    global _global_config, _log_file_path, _security_log_path
    with _global_state_lock:
        _global_config = config

        # Determine if we need file logging
        if config.get('verbose_logging') or config.get('debug_mode'):
            from ..constants import get_config_dir
            log_dir = get_config_dir() / 'logs'
            log_dir.mkdir(parents=True, exist_ok=True)

            # Create timestamped log file
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            _log_file_path = str(log_dir / f'asuc_{timestamp}.log')
            
            # Create dedicated security log file
            security_log_dir = Path('/var/log/asuc')
            try:
                # Try to create system security log directory
                security_log_dir.mkdir(parents=True, exist_ok=True)
                _security_log_path = str(security_log_dir / f'security_{timestamp}.log')
            except (OSError, PermissionError):
                # Fall back to user log directory
                _security_log_path = str(log_dir / f'security_{timestamp}.log')

            # Create a symlink to latest log with race condition protection
            latest_log = log_dir / 'latest.log'
            temp_symlink = log_dir / f'latest.log.tmp.{os.getpid()}'

            try:
                # Create temporary symlink first (atomic operation)
                temp_symlink.symlink_to(Path(_log_file_path).name)

                # Atomically replace the symlink
                try:
                    latest_log.unlink()
                except FileNotFoundError:
                    # File didn't exist, which is fine
                    pass
                temp_symlink.replace(latest_log)

            except (OSError, FileNotFoundError):
                # Clean up temp symlink on failure
                try:
                    temp_symlink.unlink()
                except (OSError, FileNotFoundError):
                    pass
                # Symlinks might not work on all systems, continue without error
                pass

            # Reconfigure all existing loggers
            _reconfigure_all_loggers()


def get_current_log_file() -> Optional[str]:
    """Get the current log file path if file logging is active."""
    with _global_state_lock:
        return _log_file_path


def _reconfigure_all_loggers() -> None:
    """Reconfigure all existing loggers with new settings."""
    # Note: This function is called from within set_global_config which already holds the lock
    if not _global_config:
        return

    debug = _global_config.get('verbose_logging', False) or _global_config.get('debug_mode', False)
    level = logging.DEBUG if debug else logging.INFO

    # Update all cached logger instances
    for logger in _logger_instances.values():
        logger.setLevel(level)

        # Add file handler if file logging is enabled
        if _log_file_path:
            # Check if file handler already exists
            file_handler = logging.FileHandler(_log_file_path)
            file_handler.setLevel(level)
            file_formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            file_handler.setFormatter(file_formatter)
            logger.addHandler(file_handler)


def setup_logging(name: str, log_file: Optional[str] = None, debug: bool = False) -> logging.Logger:
    """
    Set up logging configuration with thread safety.

    Args:
        name: Logger name
        log_file: Optional log file path
        debug: Enable debug logging

    Returns:
        Configured logger instance
    """
    with _global_state_lock:
        # Determine debug level from global config if not specified
        if not debug and _global_config:
            debug = _global_config.get('verbose_logging', False) or _global_config.get('debug_mode', False)

        # Use global log file if no explicit file provided
        if not log_file and _log_file_path:
            log_file = _log_file_path

        level = logging.DEBUG if debug else logging.INFO

        # Get or create logger
        logger = logging.getLogger(name)
        logger.setLevel(level)
        logger.handlers.clear()  # Clear existing handlers

        # Console handler with colors (use stderr for logs)
        console_handler = logging.StreamHandler(sys.stderr)
        console_handler.setLevel(level)
        console_formatter = ColoredFormatter(
            '%(levelname)s - %(name)s - %(message)s'
        )
        console_handler.setFormatter(console_formatter)
        logger.addHandler(console_handler)

        # File handler if specified
        if log_file:
            try:
                # Validate log file path for security
                from .validators import validate_log_path
                try:
                    validate_log_path(log_file)
                except ValueError as e:
                    logger.error(f"Invalid log file path: {e}")
                    return logger

                log_dir = Path(log_file).parent
                log_dir.mkdir(parents=True, exist_ok=True)

                # Set secure permissions on log directory
                os.chmod(log_dir, 0o700)

                file_handler = logging.FileHandler(log_file)
                file_handler.setLevel(level)
                file_formatter = logging.Formatter(
                    '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
                )
                file_handler.setFormatter(file_formatter)
                logger.addHandler(file_handler)

                # Set secure permissions on log file
                os.chmod(log_file, 0o600)

            except Exception as e:
                logger.error(f"Failed to create log file handler: {e}")

        # Prevent propagation to avoid duplicate messages
        logger.propagate = False

        # Mark as configured and cache
        _configured_loggers.add(name)
        return logger


def get_logger(name: str) -> logging.Logger:
    """
    Get or create a logger instance with thread safety.

    Args:
        name: Logger name

    Returns:
        Logger instance
    """
    with _global_state_lock:
        # Return cached instance if available
        if name in _logger_instances:
            return _logger_instances[name]

        # Create new logger if not in configured set
        if name in _configured_loggers:
            logger = logging.getLogger(name)
            _logger_instances[name] = logger
            return logger

        # Create fresh logger with global settings
        debug = _global_config.get('verbose_logging', False) if _global_config else False
        debug = debug or (_global_config.get('debug_mode', False) if _global_config else False)

        level = logging.DEBUG if debug else logging.INFO

        logger = logging.getLogger(name)
        logger.setLevel(level)
        logger.handlers.clear()

        # Console handler (use stderr for logs)
        console_handler = logging.StreamHandler(sys.stderr)
        console_handler.setLevel(level)
        console_formatter = ColoredFormatter(
            '%(levelname)s - %(name)s - %(message)s'
        )
        console_handler.setFormatter(console_formatter)
        logger.addHandler(console_handler)

        # File handler if global file logging is enabled
        if _log_file_path:
            try:
                file_handler = logging.FileHandler(_log_file_path)
                file_handler.setLevel(level)
                file_formatter = logging.Formatter(
                    '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
                )
                file_handler.setFormatter(file_formatter)
                logger.addHandler(file_handler)
            except Exception:
                # Don't log this error to avoid recursion
                pass

        logger.propagate = False

        # Cache the logger
        _configured_loggers.add(name)
        _logger_instances[name] = logger

        return logger


def sanitize_log_message(message: str, sensitive_patterns: Optional[list[str]] = None, debug_level: bool = False) -> str:
    """
    Enhanced log message sanitization to prevent information disclosure.

    Args:
        message: Original log message
        sensitive_patterns: Additional patterns to redact
        debug_level: If True, apply more aggressive sanitization for debug logs

    Returns:
        Sanitized log message
    """
    if not isinstance(message, str):
        return str(message)

    # Default sensitive patterns to redact
    default_patterns = [
        # File paths - redact home directory and username
        (r'/home/[^/\s]+', '/home/[USER]'),
        (r'C:[/\\]+Users[/\\]+[^/\\\\s]+', 'C:/Users/[USER]'),
        (r'/Users/[^/\s]+', '/Users/[USER]'),  # macOS

        # Email addresses
        (r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', '[EMAIL]'),

        # IP addresses (all ranges)
        (
            r'\b(?:192\.168\.\d{1,3}\.\d{1,3}|10\.\d{1,3}\.\d{1,3}\.\d{1,3}|172\.(?:1[6-9]|2[0-9]|3[0-1])\.\d{1,3}\.\d{1,3})\b',
            '[PRIVATE_IP]'),
        (
            r'\b(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\b',
            '[IP_ADDRESS]'),
        (r'\b(?:[0-9a-fA-F]{1,4}:){7}[0-9a-fA-F]{1,4}\b', '[IPV6_ADDRESS]'),

        # URLs with authentication
        (r'https?://[^:]+:[^@]+@', 'https://[CREDENTIALS]@'),
        (r'(?:ftp|sftp)://[^:]+:[^@]+@', '[PROTOCOL]://[CREDENTIALS]@'),

        # Credentials and secrets (enhanced patterns)
        (r'(?i)password["\s]*[:=]["\s]*[^\s"\']+', 'password="[REDACTED]"'),
        (r'(?i)passwd["\s]*[:=]["\s]*[^\s"\']+', 'passwd="[REDACTED]"'),
        (r'(?i)token["\s]*[:=]["\s]*[^\s"\']+', 'token="[REDACTED]"'),
        (r'(?i)api_?key["\s]*[:=]["\s]*[^\s"\']+', 'api_key="[REDACTED]"'),
        (r'(?i)secret["\s]*[:=]["\s]*[^\s"\']+', 'secret="[REDACTED]"'),
        (r'(?i)auth["\s]*[:=]["\s]*[^\s"\']+', 'auth="[REDACTED]"'),
        (r'(?i)authorization["\s]*[:=]["\s]*[^\s"\']+', 'authorization="[REDACTED]"'),
        (r'(?i)bearer["\s]+[^\s"\']+', 'bearer [REDACTED]'),

        # Cryptographic material
        (r'\b[a-fA-F0-9]{32,}\b', '[HEX_STRING]'),  # Hashes, keys
        (r'-----BEGIN [^-]+-----[^-]+-----END [^-]+-----', '[CERTIFICATE/KEY]'),
        (r'\b[A-Za-z0-9+/]{40,}={0,2}\b', '[BASE64_DATA]'),  # Base64 encoded data

        # Session and security tokens
        (r'(?i)session["\s]*[:=]["\s]*[^\s"\']+', 'session="[REDACTED]"'),
        (r'(?i)cookie["\s]*[:=]["\s]*[^\s"\']+', 'cookie="[REDACTED]"'),
        (r'(?i)csrf["\s]*[:=]["\s]*[^\s"\']+', 'csrf="[REDACTED]"'),
        (r'(?i)nonce["\s]*[:=]["\s]*[^\s"\']+', 'nonce="[REDACTED]"'),

        # Database connection strings
        (r'(?i)(?:mysql|postgresql|sqlite|mongodb)://[^\s]+', '[DATABASE_URL]'),
        (r'(?i)(?:user|username)["\s]*[:=]["\s]*[^\s"\']+', 'user="[USER]"'),

        # System identifiers
        (r'(?i)hostname["\s]*[:=]["\s]*[^\s"\']+', 'hostname="[HOSTNAME]"'),
        (r'(?i)machine["\s]*[:=]["\s]*[^\s"\']+', 'machine="[MACHINE]"'),
        (r'(?i)uuid["\s]*[:=]["\s]*[0-9a-fA-F-]{32,}', 'uuid="[UUID]"'),

        # Process and system info
        (r'\bpid["\s]*[:=]?\s*\d+', 'pid=[PID]'),
        (r'\btid["\s]*[:=]?\s*\d+', 'tid=[TID]'),
        (r'(?i)thread[_-]?id["\s]*[:=]["\s]*[^\s"\']+', 'thread_id="[THREAD_ID]"'),
    ]

    # Enhanced debug-level sanitization patterns
    debug_patterns = [
        # Package and system information
        (r'packages=\[[^\]]*\]', 'packages=[LIST_REDACTED]'),
        (r'selected=\[[^\]]*\]', 'selected=[LIST_REDACTED]'),
        (r'installed=\[[^\]]*\]', 'installed=[LIST_REDACTED]'),
        (r'dependencies=\[[^\]]*\]', 'dependencies=[LIST_REDACTED]'),

        # Command outputs and system info
        (r'(?i)(?:update|command|full)\s+output(?:\s+for[^:]+)?:\s*.*', 'Output: [CONTENT_REDACTED]'),
        (r'(?i)Running\s+command:\s+.*', 'Running command: [COMMAND_REDACTED]'),
        (r'(?i)Executing:\s+.*', 'Executing: [EXECUTION_REDACTED]'),
        (r'(?i)Shell\s+command:\s+.*', 'Shell command: [SHELL_REDACTED]'),

        # System and environment details
        (r'(?i)environment:\s*\{[^}]*\}', 'environment: {[ENV_REDACTED]}'),
        (r'(?i)env_vars?:\s*\{[^}]*\}', 'env_vars: {[ENV_REDACTED]}'),
        (r'(?i)system_info:\s*\{[^}]*\}', 'system_info: {[SYS_REDACTED]}'),

        # Version and architecture information
        (r'\b\d+\.\d+\.\d+[\w.-]*\b', '[VERSION]'),
        (r'(?i)arch(?:itecture)?["\s]*[:=]["\s]*[^\s"\']+', 'arch="[ARCH]"'),
        (r'(?i)platform["\s]*[:=]["\s]*[^\s"\']+', 'platform="[PLATFORM]"'),
        (r'(?i)kernel["\s]*[:=]["\s]*[^\s"\']+', 'kernel="[KERNEL]"'),

        # File system paths and details
        (r'/usr/[^\s]+', '/usr/[PATH]'),
        (r'/etc/[^\s]+', '/etc/[PATH]'),
        (r'/var/[^\s]+', '/var/[PATH]'),
        (r'/tmp/[^\s]+', '/tmp/[PATH]'),
        (r'/opt/[^\s]+', '/opt/[PATH]'),
        (r'/lib[^/]*[^\s]*', '/lib[PATH]'),
        (r'/bin/[^\s]+', '/bin/[PATH]'),
        (r'/sbin/[^\s]+', '/sbin/[PATH]'),

        # Network and connection details
        (r'(?i)port["\s]*[:=]?\s*\d+', 'port=[PORT]'),
        (r'(?i)socket["\s]*[:=]["\s]*[^\s"\']+', 'socket="[SOCKET]"'),
        (r'(?i)interface["\s]*[:=]["\s]*[^\s"\']+', 'interface="[INTERFACE]"'),

        # Process identifiers and thread info
        (r'thread_[a-f0-9]{8,}', 'thread_[ID]'),
        (r'process_[a-f0-9]{8,}', 'process_[ID]'),
        (r'job_[a-f0-9]{8,}', 'job_[ID]'),
        (r'task_[a-f0-9]{8,}', 'task_[ID]'),

        # Timing and performance data
        (r'(?i)execution_time["\s]*[:=]["\s]*[\d.]+', 'execution_time="[TIME]"'),
        (r'(?i)duration["\s]*[:=]["\s]*[\d.]+', 'duration="[TIME]"'),
        (r'(?i)elapsed["\s]*[:=]["\s]*[\d.]+', 'elapsed="[TIME]"'),
        (r'(?i)latency["\s]*[:=]["\s]*[\d.]+', 'latency="[TIME]"'),

        # Memory and resource usage
        (r'(?i)memory["\s]*[:=]["\s]*[\d.]+[^\s]*', 'memory="[MEMORY]"'),
        (r'(?i)cpu["\s]*[:=]["\s]*[\d.]+%?', 'cpu="[CPU]"'),
        (r'(?i)disk["\s]*[:=]["\s]*[\d.]+[^\s]*', 'disk="[DISK]"'),
        (r'(?i)load["\s]*[:=]["\s]*[\d.]+', 'load="[LOAD]"'),

        # Configuration details
        (r'(?i)config["\s]*[:=]\s*\{[^}]*\}', 'config={[CONFIG_REDACTED]}'),
        (r'(?i)settings["\s]*[:=]\s*\{[^}]*\}', 'settings={[SETTINGS_REDACTED]}'),
        (r'(?i)options["\s]*[:=]\s*\{[^}]*\}', 'options={[OPTIONS_REDACTED]}'),

        # Error context and stack traces
        (r'(?i)traceback["\s]*[:=][^,}]+', 'traceback="[TRACEBACK_REDACTED]"'),
        (r'(?i)stack["\s]*[:=][^,}]+', 'stack="[STACK_REDACTED]"'),
        (r'(?i)backtrace["\s]*[:=][^,}]+', 'backtrace="[BACKTRACE_REDACTED]"'),

        # User and session context
        (r'(?i)current_user["\s]*[:=]["\s]*[^\s"\']+', 'current_user="[USER]"'),
        (r'(?i)logged_in_user["\s]*[:=]["\s]*[^\s"\']+', 'logged_in_user="[USER]"'),
        (r'(?i)active_session["\s]*[:=]["\s]*[^\s"\']+', 'active_session="[SESSION]"'),

        # Application state
        (r'(?i)state["\s]*[:=]\s*\{[^}]*\}', 'state={[STATE_REDACTED]}'),
        (r'(?i)context["\s]*[:=]\s*\{[^}]*\}', 'context={[CONTEXT_REDACTED]}'),
        (r'(?i)metadata["\s]*[:=]\s*\{[^}]*\}', 'metadata={[METADATA_REDACTED]}'),
    ]

    # Production-safe patterns (always applied regardless of debug level)
    production_patterns = [
        # Credit card numbers
        (r'\b(?:\d{4}[-\s]?){3}\d{4}\b', '[CREDIT_CARD]'),

        # Social security numbers
        (r'\b\d{3}-\d{2}-\d{4}\b', '[SSN]'),

        # Phone numbers
        (r'\b(?:\+?1[-.\s]?)?\(?[0-9]{3}\)?[-.\s]?[0-9]{3}[-.\s]?[0-9]{4}\b', '[PHONE]'),

        # More generic credentials
        (r'(?i)(?:key|pass|secret|token|auth)[_-]?[a-zA-Z0-9]{16,}', '[CREDENTIAL]'),

        # JSON Web Tokens
        (r'\beyJ[A-Za-z0-9_-]*\.[A-Za-z0-9_-]*\.[A-Za-z0-9_-]*\b', '[JWT_TOKEN]'),

        # AWS/Cloud credentials
        (r'\bAKIA[0-9A-Z]{16}\b', '[AWS_ACCESS_KEY]'),
        (r'\b[0-9a-zA-Z/+]{40}\b', '[AWS_SECRET_KEY]'),

        # Private keys and certificates (additional patterns)
        (r'(?i)private[_-]?key["\s]*[:=]["\s]*[^\s"\']+', 'private_key="[REDACTED]"'),
        (r'(?i)public[_-]?key["\s]*[:=]["\s]*[^\s"\']+', 'public_key="[REDACTED]"'),
        (r'(?i)certificate["\s]*[:=]["\s]*[^\s"\']+', 'certificate="[REDACTED]"'),
    ]

    # Combine patterns based on debug level
    patterns = default_patterns + production_patterns
    if debug_level:
        patterns.extend(debug_patterns)

    if sensitive_patterns:
        patterns.extend([(pattern, '[CUSTOM_REDACTED]') for pattern in sensitive_patterns])

    sanitized = message
    for pattern, replacement in patterns:
        try:
            sanitized = re.sub(pattern, replacement, sanitized, flags=re.IGNORECASE)
        except Exception as e:
            # If regex fails, log it but continue with next pattern
            logger = get_logger(__name__)
            logger.debug(f"Sanitization pattern failed: {e}")
            continue

    # Additional security measures
    sanitized = _apply_additional_sanitization(sanitized, debug_level)

    return sanitized


def _apply_additional_sanitization(message: str, debug_level: bool = False) -> str:
    """
    Apply additional sanitization measures.

    Args:
        message: Message to sanitize
        debug_level: Whether this is for debug logging

    Returns:
        Further sanitized message
    """
    # Limit message length to prevent log flooding
    max_length = 2000 if debug_level else 1000
    if len(message) > max_length:
        message = message[:max_length] + '... [TRUNCATED]'

    # Remove control characters that might cause issues
    message = re.sub(r'[\x00-\x08\x0B-\x0C\x0E-\x1F\x7F]', '[CTRL]', message)

    # Normalize whitespace
    message = re.sub(r'\s+', ' ', message).strip()

    # Remove repeated patterns that might indicate attempts to bypass sanitization
    message = re.sub(r'(\[REDACTED\][\s,]*){3,}', '[MULTIPLE_REDACTED]', message)
    message = re.sub(r'(\[CREDENTIAL\][\s,]*){3,}', '[MULTIPLE_CREDENTIALS]', message)

    return message


def sanitize_debug_message(message: str, extra_patterns: Optional[list[str]] = None) -> str:
    """
    Enhanced debug message sanitization with stricter controls.

    Args:
        message: Debug message to sanitize
        extra_patterns: Additional patterns to redact

    Returns:
        Sanitized debug message
    """
    return sanitize_log_message(message, extra_patterns, debug_level=True)


def create_secure_debug_logger(name: str, enable_debug: bool = False) -> Any:
    """
    Create a logger with automatic debug message sanitization.

    Args:
        name: Logger name
        enable_debug: Whether to enable debug logging

    Returns:
        Logger with enhanced security
    """
    logger = get_logger(name)

    # Create a wrapper that automatically sanitizes debug messages
    class SecureDebugLogger:
        def __init__(self, base_logger: logging.Logger) -> None:
            self._logger = base_logger
            self._debug_enabled = enable_debug

        def debug(self, msg: Any, *args: Any, **kwargs: Any) -> None:
            if self._debug_enabled and self._logger.isEnabledFor(logging.DEBUG):
                sanitized_msg = sanitize_debug_message(str(msg))
                self._logger.debug(sanitized_msg, *args, **kwargs)

        def info(self, msg: Any, *args: Any, **kwargs: Any) -> None:
            sanitized_msg = sanitize_log_message(str(msg))
            self._logger.info(sanitized_msg, *args, **kwargs)

        def warning(self, msg: Any, *args: Any, **kwargs: Any) -> None:
            sanitized_msg = sanitize_log_message(str(msg))
            self._logger.warning(sanitized_msg, *args, **kwargs)

        def error(self, msg: Any, *args: Any, **kwargs: Any) -> None:
            sanitized_msg = sanitize_log_message(str(msg))
            self._logger.error(sanitized_msg, *args, **kwargs)

        def critical(self, msg: Any, *args: Any, **kwargs: Any) -> None:
            sanitized_msg = sanitize_log_message(str(msg))
            self._logger.critical(sanitized_msg, *args, **kwargs)

        def __getattr__(self, name: str) -> Any:
            # Forward other attributes to the base logger
            return getattr(self._logger, name)

    return SecureDebugLogger(logger)


def log_security_event(event_type: str, details: Optional[dict[str, Any]] = None, severity: str = "warning") -> None:
    """
    Log a security event with rate limiting and metrics.
    
    Args:
        event_type: Type of security event
        details: Event details (will be sanitized)
        severity: Log severity level
    """
    
    # Check rate limiting
    with _global_state_lock:
        current_time = datetime.now()
        event_info = _security_event_counts.get(event_type, {})
        
        if event_info:
            time_since_first = (current_time - event_info['first_time']).total_seconds()
            
            # Reset window if expired
            if time_since_first > _security_rate_limit_window:
                event_info = {'count': 0, 'first_time': current_time, 'last_time': current_time}
            
            # Check if rate limit exceeded
            if event_info['count'] >= _security_rate_limit_max:
                if event_info.get('rate_limit_logged', False) is False:
                    # Log once that we're rate limiting
                    security_logger = get_logger("security")
                    security_logger.warning(
                        f"RATE_LIMIT: Suppressing further {event_type} events for {_security_rate_limit_window}s"
                    )
                    event_info['rate_limit_logged'] = True
                return
        else:
            event_info = {'count': 0, 'first_time': current_time, 'last_time': current_time}
        
        # Update event count
        event_info['count'] += 1
        event_info['last_time'] = current_time
        _security_event_counts[event_type] = event_info
    
    security_logger = get_logger("security")

    # Gather enriched context
    context = {
        'timestamp': datetime.now().isoformat(),
        'event_type': event_type,
        'severity': severity,
        'pid': os.getpid(),
        'uid': os.getuid() if hasattr(os, 'getuid') else 'N/A',
        'user': os.environ.get('USER', 'unknown'),
    }
    
    # Add thread info if in multi-threaded context
    current_thread = threading.current_thread()
    if current_thread.name != 'MainThread':
        context['thread'] = current_thread.name
    
    # Sanitize event details
    if details:
        sanitized_details = {}
        for key, value in details.items():
            # Sanitize both key and value
            safe_key = sanitize_log_message(str(key))
            safe_value = sanitize_log_message(str(value))
            sanitized_details[safe_key] = safe_value
    else:
        sanitized_details = {}

    # Create structured log message
    log_msg = f"SECURITY_EVENT: {event_type}"
    if sanitized_details:
        detail_str = ", ".join(f"{k}={v}" for k, v in sanitized_details.items())
        log_msg += f" - {detail_str}"
    
    # Add context to message
    context_str = f" [pid={context['pid']}, uid={context['uid']}, user={context['user']}]"
    log_msg += context_str

    # Log with appropriate severity
    if severity == "critical":
        security_logger.critical(log_msg)
    elif severity == "error":
        security_logger.error(log_msg)
    elif severity == "warning":
        security_logger.warning(log_msg)
    else:
        security_logger.info(log_msg)
    
    # Also write to dedicated security log if available
    if _security_log_path:
        try:
            with open(_security_log_path, 'a') as f:
                # Write JSON formatted entry for easier parsing
                security_entry = {
                    **context,
                    'message': log_msg,
                    'details': sanitized_details
                }
                f.write(json.dumps(security_entry) + '\n')
        except (OSError, IOError) as e:
            # Don't fail if we can't write to security log
            security_logger.debug(f"Failed to write to security log: {e}")
    
    # Record metrics
    try:
        from .security_metrics import record_security_metric
        record_security_metric(
            event_type=event_type,
            severity=severity,
            details=sanitized_details
        )
    except Exception as e:
        # Don't fail if metrics recording fails
        security_logger.debug(f"Failed to record security metric: {e}")


class ContextualSanitizer:
    """Context-aware log sanitization for different application components."""

    def __init__(self, component_name: str):
        self.component_name = component_name
        self.component_patterns = self._get_component_patterns()

    def _get_component_patterns(self) -> list[tuple[str, str]]:
        """Get sanitization patterns specific to component."""
        patterns = []

        if self.component_name in ['network', 'feed', 'http']:
            patterns.extend([
                (r'(?i)url["\s]*[:=]["\s]*[^\s"\']+', 'url="[URL_REDACTED]"'),
                (r'(?i)endpoint["\s]*[:=]["\s]*[^\s"\']+', 'endpoint="[ENDPOINT_REDACTED]"'),
                (r'(?i)response["\s]*[:=][^,}]+', 'response="[RESPONSE_REDACTED]"'),
                (r'(?i)request["\s]*[:=][^,}]+', 'request="[REQUEST_REDACTED]"'),
                (r'(?i)headers["\s]*[:=]\s*\{[^}]*\}', 'headers={[HEADERS_REDACTED]}'),
            ])

        elif self.component_name in ['package', 'pacman', 'system']:
            patterns.extend([
                (r'(?i)package[_\s]list["\s]*[:=][^,}]+', 'package_list="[PACKAGES_REDACTED]"'),
                (r'(?i)installed[_\s]packages["\s]*[:=][^,}]+', 'installed_packages="[PACKAGES_REDACTED]"'),
                (r'(?i)system[_\s]info["\s]*[:=][^,}]+', 'system_info="[SYSTEM_REDACTED]"'),
                (r'(?i)dependencies["\s]*[:=][^,}]+', 'dependencies="[DEPS_REDACTED]"'),
            ])

        elif self.component_name in ['gui', 'ui', 'interface']:
            patterns.extend([
                (r'(?i)user[_\s]input["\s]*[:=][^,}]+', 'user_input="[INPUT_REDACTED]"'),
                (r'(?i)form[_\s]data["\s]*[:=][^,}]+', 'form_data="[FORM_REDACTED]"'),
                (r'(?i)selection["\s]*[:=][^,}]+', 'selection="[SELECTION_REDACTED]"'),
                (r'(?i)widget[_\s]state["\s]*[:=][^,}]+', 'widget_state="[STATE_REDACTED]"'),
            ])

        elif self.component_name in ['config', 'settings']:
            patterns.extend([
                (r'(?i)configuration["\s]*[:=]\s*\{[^}]*\}', 'configuration={[CONFIG_REDACTED]}'),
                (r'(?i)preferences["\s]*[:=]\s*\{[^}]*\}', 'preferences={[PREFS_REDACTED]}'),
                (r'(?i)user[_\s]settings["\s]*[:=]\s*\{[^}]*\}', 'user_settings={[SETTINGS_REDACTED]}'),
            ])

        return patterns

    def sanitize(self, message: str, debug_level: bool = False) -> str:
        """
        Sanitize message with component-specific patterns.

        Args:
            message: Message to sanitize
            debug_level: Whether this is debug-level logging

        Returns:
            Sanitized message
        """
        # Apply component-specific patterns first
        sanitized = message
        for pattern, replacement in self.component_patterns:
            try:
                sanitized = re.sub(pattern, replacement, sanitized, flags=re.IGNORECASE)
            except Exception:
                continue

        # Apply general sanitization
        return sanitize_log_message(sanitized, debug_level=debug_level)


def get_contextual_sanitizer(component_name: str) -> ContextualSanitizer:
    """
    Get a context-aware sanitizer for a specific component.

    Args:
        component_name: Name of the component

    Returns:
        ContextualSanitizer instance
    """
    return ContextualSanitizer(component_name)
