"""
Basic tests to verify the testing infrastructure works.
"""

import os
import sys


def test_python_version():
    """Test that we're running Python 3.7+."""
    assert sys.version_info >= (3, 7)


def test_environment_variables():
    """Test that environment variables are set correctly."""
    assert os.environ.get('CI') == 'true'
    assert os.environ.get('ASUC_HEADLESS') == '1'


def test_basic_math():
    """Test basic functionality."""
    assert 1 + 1 == 2
    assert 2 * 3 == 6


def test_basic_imports():
    """Test that basic Python modules work."""
    import json
    import urllib
    import subprocess
    
    # These should all import without issues
    assert json is not None
    assert urllib is not None  
    assert subprocess is not None


def test_string_operations():
    """Test basic string operations."""
    test_str = "Hello, World!"
    assert len(test_str) == 13
    assert test_str.upper() == "HELLO, WORLD!"
    assert "Hello" in test_str