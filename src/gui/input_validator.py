"""
Comprehensive GUI input validation system to prevent injection attacks and validate user inputs.
"""

# SPDX-License-Identifier: GPL-3.0-or-later

import re
import html
import string
import unicodedata
from typing import Any, Callable, Dict, List, Optional, Union, Tuple
import tkinter as tk
from tkinter import ttk

from ..utils.logger import get_logger
from ..utils.validators import SecurityFilter

logger = get_logger(__name__)


class GUIInputValidator:
    """Comprehensive input validator for GUI components."""

    # Input type validation patterns
    VALIDATION_PATTERNS = {
        'package_name': re.compile(r'^[a-zA-Z0-9][a-zA-Z0-9\-_.+]{0,127}$'),
        'config_key': re.compile(r'^[a-zA-Z][a-zA-Z0-9_]{0,63}$'),
        'file_path': re.compile(r'^[/]?[a-zA-Z0-9._/-]{1,255}$'),
        'url': re.compile(r'^https?://[a-zA-Z0-9.-]+(?:\:[0-9]+)?(?:/[a-zA-Z0-9._/-]*)?$'),
        'numeric': re.compile(r'^\d+$'),
        'alphanumeric': re.compile(r'^[a-zA-Z0-9]+$'),
        'safe_text': re.compile(r'^[a-zA-Z0-9\s\-_.(),!?]{0,255}$')
    }

    # Dangerous input patterns to block
    DANGEROUS_PATTERNS = [
        re.compile(r'[<>&"\'\x00-\x1f\x7f-\x9f]'),  # HTML/XML/Control chars
        re.compile(r'[\\\x00\|\$\`\;]'),            # Shell injection chars
        re.compile(r'(?:javascript|vbscript|data):', re.IGNORECASE),  # Script protocols
        re.compile(r'(?:eval|exec|import|open|file|input)\s*\(', re.IGNORECASE),  # Python dangerous functions
        re.compile(r'(?:union|select|insert|update|delete|drop|create)\s+', re.IGNORECASE),  # SQL injection
        re.compile(r'(?:\.\./|\.\.\\|/etc/|/proc/|c:\\)', re.IGNORECASE),  # Path traversal
        re.compile(r'(?:alert|confirm|prompt)\s*\(', re.IGNORECASE),  # JavaScript dialogs
    ]

    # Maximum lengths for different input types
    MAX_LENGTHS = {
        'package_name': 128,
        'config_key': 64,
        'file_path': 255,
        'url': 2048,
        'safe_text': 255,
        'search_term': 100,
        'setting_value': 512
    }

    def __init__(self):
        """Initialize the GUI input validator."""
        self.security_filter = SecurityFilter()
        self._validation_cache = {}  # Cache validation results
        logger.debug("Initialized GUI input validator")

    def validate_input(self, value: str, input_type: str,
                       custom_pattern: Optional[re.Pattern] = None,
                       allow_empty: bool = False) -> Tuple[bool, str]:
        """
        Validate input value against security patterns and type constraints.

        Args:
            value: Input value to validate
            input_type: Type of input (package_name, config_key, etc.)
            custom_pattern: Optional custom validation pattern
            allow_empty: Whether to allow empty strings

        Returns:
            Tuple of (is_valid, error_message)
        """
        try:
            # Check for empty input
            if not value:
                if allow_empty:
                    return True, ""
                return False, "Input cannot be empty"

            # Check type of input
            if not isinstance(value, str):
                return False, "Input must be a string"

            # Check maximum length
            max_length = self.MAX_LENGTHS.get(input_type, 255)
            if len(value) > max_length:
                return False, f"Input too long (max {max_length} characters)"

            # Normalize unicode to prevent bypass attempts
            normalized_value = unicodedata.normalize('NFKC', value)

            # Check for dangerous patterns
            for pattern in self.DANGEROUS_PATTERNS:
                if pattern.search(normalized_value):
                    logger.warning(f"Blocked dangerous input pattern: {value[:50]}...")
                    return False, "Input contains potentially dangerous characters"

            # Validate against specific input type pattern
            if input_type in self.VALIDATION_PATTERNS:
                pattern = self.VALIDATION_PATTERNS[input_type]
                if not pattern.match(normalized_value):
                    return False, f"Input format invalid for {input_type}"

            # Validate against custom pattern if provided
            if custom_pattern and not custom_pattern.match(normalized_value):
                return False, "Input does not match required format"

            # Additional security filtering
            if not self.security_filter.validate_input_safety(normalized_value):
                return False, "Input failed security validation"

            logger.debug(f"Input validation passed for {input_type}: {value[:20]}...")
            return True, ""

        except Exception as e:
            logger.error(f"Error during input validation: {e}")
            return False, "Validation error occurred"

    def sanitize_input(self, value: str, input_type: str, escape_html: bool = True) -> str:
        """
        Sanitize input value for safe usage.

        Args:
            value: Input value to sanitize
            input_type: Type of input
            escape_html: Whether to escape HTML characters

        Returns:
            Sanitized input value
        """
        try:
            if not isinstance(value, str):
                value = str(value)

            # Normalize unicode
            sanitized = unicodedata.normalize('NFKC', value)

            # Remove null bytes and control characters
            sanitized = ''.join(char for char in sanitized
                                if ord(char) >= 32 and char != '\x7f')

            # Escape HTML if requested
            if escape_html:
                sanitized = html.escape(sanitized, quote=True)

            # Type-specific sanitization
            if input_type == 'package_name':
                # Keep only valid package name characters
                sanitized = re.sub(r'[^a-zA-Z0-9\-_.+]', '', sanitized)
            elif input_type == 'config_key':
                # Keep only valid config key characters
                sanitized = re.sub(r'[^a-zA-Z0-9_]', '', sanitized)
            elif input_type == 'file_path':
                # Sanitize file path
                sanitized = re.sub(r'[^a-zA-Z0-9._/-]', '', sanitized)
                # Remove path traversal attempts
                sanitized = re.sub(r'\.\./', '', sanitized)
                sanitized = re.sub(r'\.\.\\', '', sanitized)
            elif input_type == 'safe_text':
                # Keep safe text characters
                sanitized = re.sub(r'[^a-zA-Z0-9\s\-_.(),!?]', '', sanitized)

            # Trim to maximum length
            max_length = self.MAX_LENGTHS.get(input_type, 255)
            if len(sanitized) > max_length:
                sanitized = sanitized[:max_length]

            logger.debug(f"Sanitized {input_type} input: {value[:20]}... -> {sanitized[:20]}...")
            return sanitized

        except Exception as e:
            logger.error(f"Error during input sanitization: {e}")
            return ""


class ValidatedEntry(ttk.Entry):
    """Enhanced Entry widget with built-in input validation."""

    def __init__(self, parent, input_type: str = 'safe_text',
                 custom_validator: Optional[Callable[[str], bool]] = None,
                 on_validation_error: Optional[Callable[[str], None]] = None,
                 **kwargs):
        """
        Initialize validated entry widget.

        Args:
            parent: Parent widget
            input_type: Type of input validation to apply
            custom_validator: Optional custom validation function
            on_validation_error: Callback for validation errors
            **kwargs: Additional tkinter Entry arguments
        """
        super().__init__(parent, **kwargs)

        self.input_type = input_type
        self.validator = GUIInputValidator()
        self.custom_validator = custom_validator
        self.on_validation_error = on_validation_error
        self._last_valid_value = ""

        # Set up validation
        self._setup_validation()

        logger.debug(f"Created validated entry for {input_type}")

    def _setup_validation(self):
        """Set up real-time input validation."""
        # Register validation command
        vcmd = (self.register(self._validate_input), '%P', '%V')
        self.configure(validate='key', validatecommand=vcmd)

        # Also validate on focus out
        self.bind('<FocusOut>', self._on_focus_out)

    def _validate_input(self, value: str, validation_type: str) -> bool:
        """
        Internal validation method called by tkinter.

        Args:
            value: Current input value
            validation_type: Type of validation event

        Returns:
            True if input is valid
        """
        try:
            # Always allow empty input during typing
            if not value:
                return True

            # Validate input
            is_valid, error_msg = self.validator.validate_input(
                value, self.input_type, allow_empty=True
            )

            # Apply custom validator if provided
            if is_valid and self.custom_validator:
                try:
                    is_valid = self.custom_validator(value)
                    if not is_valid:
                        error_msg = "Custom validation failed"
                except Exception as e:
                    logger.error(f"Custom validator error: {e}")
                    is_valid = False
                    error_msg = "Validation error"

            if is_valid:
                self._last_valid_value = value
                self._clear_error_styling()
            else:
                self._apply_error_styling()
                if self.on_validation_error:
                    try:
                        self.on_validation_error(error_msg)
                    except Exception as e:
                        logger.error(f"Error callback failed: {e}")

            return is_valid

        except Exception as e:
            logger.error(f"Validation error in ValidatedEntry: {e}")
            return False

    def _on_focus_out(self, event):
        """Handle focus out event for final validation."""
        current_value = self.get()

        # Final validation on focus out
        is_valid, error_msg = self.validator.validate_input(
            current_value, self.input_type, allow_empty=False
        )

        if not is_valid:
            logger.warning(f"Invalid input on focus out: {error_msg}")
            if self.on_validation_error:
                try:
                    self.on_validation_error(error_msg)
                except Exception:
                    pass

            # Optionally revert to last valid value
            if hasattr(self, '_revert_on_invalid') and self._revert_on_invalid:
                self.delete(0, tk.END)
                self.insert(0, self._last_valid_value)

    def _apply_error_styling(self):
        """Apply error styling to the entry."""
        try:
            self.configure(style='Error.TEntry')
        except tk.TclError:
            # Style might not exist, create it
            try:
                style = ttk.Style()
                style.configure('Error.TEntry', fieldbackground='#ffcccc')
                self.configure(style='Error.TEntry')
            except Exception:
                pass

    def _clear_error_styling(self):
        """Clear error styling from the entry."""
        try:
            self.configure(style='TEntry')
        except tk.TclError:
            pass

    def get_sanitized_value(self) -> str:
        """Get the sanitized value of the entry."""
        raw_value = self.get()
        return self.validator.sanitize_input(raw_value, self.input_type)

    def set_revert_on_invalid(self, revert: bool = True):
        """Set whether to revert to last valid value on invalid input."""
        self._revert_on_invalid = revert


class ValidatedText(tk.Text):
    """Enhanced Text widget with built-in input validation."""

    def __init__(self, parent, input_type: str = 'safe_text',
                 max_chars: Optional[int] = None,
                 on_validation_error: Optional[Callable[[str], None]] = None,
                 **kwargs):
        """
        Initialize validated text widget.

        Args:
            parent: Parent widget
            input_type: Type of input validation to apply
            max_chars: Maximum number of characters allowed
            on_validation_error: Callback for validation errors
            **kwargs: Additional tkinter Text arguments
        """
        super().__init__(parent, **kwargs)

        self.input_type = input_type
        self.validator = GUIInputValidator()
        self.max_chars = max_chars or self.validator.MAX_LENGTHS.get(input_type, 1000)
        self.on_validation_error = on_validation_error

        # Set up validation
        self._setup_validation()

        logger.debug(f"Created validated text widget for {input_type}")

    def _setup_validation(self):
        """Set up real-time input validation."""
        # Bind to key events for validation
        self.bind('<KeyRelease>', self._on_text_change)
        self.bind('<FocusOut>', self._on_focus_out)

    def _on_text_change(self, event):
        """Handle text change events."""
        current_text = self.get('1.0', tk.END).rstrip('\n')

        # Check character limit
        if len(current_text) > self.max_chars:
            # Truncate text
            self.delete(f'1.{self.max_chars}', tk.END)
            if self.on_validation_error:
                try:
                    self.on_validation_error(f"Text exceeds maximum length of {self.max_chars} characters")
                except Exception:
                    pass
            return

        # Validate current content
        is_valid, error_msg = self.validator.validate_input(
            current_text, self.input_type, allow_empty=True
        )

        if not is_valid and self.on_validation_error:
            try:
                self.on_validation_error(error_msg)
            except Exception:
                pass

    def _on_focus_out(self, event):
        """Handle focus out event."""
        current_text = self.get('1.0', tk.END).rstrip('\n')

        # Final validation
        is_valid, error_msg = self.validator.validate_input(
            current_text, self.input_type, allow_empty=False
        )

        if not is_valid:
            logger.warning(f"Invalid text content: {error_msg}")

    def get_sanitized_value(self) -> str:
        """Get the sanitized value of the text widget."""
        raw_value = self.get('1.0', tk.END).rstrip('\n')
        return self.validator.sanitize_input(raw_value, self.input_type)


def create_validation_error_handler(parent_widget, error_label: Optional[ttk.Label] = None):
    """
    Create a validation error handler function.

    Args:
        parent_widget: Parent widget for error display
        error_label: Optional label to display errors in

    Returns:
        Error handler function
    """
    def handle_error(error_message: str):
        """Handle validation error by displaying message."""
        try:
            if error_label:
                error_label.config(text=error_message, foreground='red')
                # Clear error after 3 seconds
                parent_widget.after(3000, lambda: error_label.config(text=""))
            else:
                # Log error if no label provided
                logger.warning(f"Validation error: {error_message}")
        except Exception as e:
            logger.error(f"Error displaying validation message: {e}")

    return handle_error


# Global validator instance for convenience
gui_validator = GUIInputValidator()
