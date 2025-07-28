"""Test external update detection from pacman log."""

import unittest
from unittest.mock import patch, mock_open
from datetime import datetime

from src.utils.pacman_runner import PacmanRunner


class TestExternalUpdateDetection(unittest.TestCase):
    """Test detection of external system updates from pacman log."""
    
    def test_parse_pacman_log_full_update(self):
        """Test parsing pacman log for full system updates."""
        # Sample pacman log content with full system upgrade
        log_content = b"""
[2024-01-15T10:30:00+0000] [PACMAN] Running 'pacman -Syu'
[2024-01-15T10:30:05+0000] [PACMAN] synchronizing package lists
[2024-01-15T10:30:10+0000] [PACMAN] starting full system upgrade
[2024-01-15T10:35:00+0000] [PACMAN] upgraded linux (6.1.0-1 -> 6.2.0-1)
[2024-01-15T10:35:30+0000] [PACMAN] upgraded firefox (100.0-1 -> 101.0-1)
[2024-01-20T14:20:00+0000] [PACMAN] Running 'pacman -S vim'
[2024-01-20T14:20:05+0000] [PACMAN] installed vim (9.0-1)
[2024-01-25T09:00:00+0000] [PACMAN] Running 'pacman -Syu'
[2024-01-25T09:00:05+0000] [PACMAN] synchronizing package lists
[2024-01-25T09:00:10+0000] [PACMAN] starting full system upgrade
[2024-01-25T09:05:00+0000] [PACMAN] upgraded gcc (12.0-1 -> 12.1-1)
"""
        
        # Create a properly configured mock file
        m_open = mock_open()
        m_file = m_open.return_value
        m_file.tell.return_value = len(log_content)
        m_file.read.return_value = log_content
        
        with patch('os.path.exists', return_value=True), \
             patch('builtins.open', m_open):
            
            result = PacmanRunner.get_last_full_update_time()
            
            # Should find the most recent full system upgrade (2024-01-25)
            self.assertIsNotNone(result)
            self.assertEqual(result.year, 2024)
            self.assertEqual(result.month, 1)
            self.assertEqual(result.day, 25)
            self.assertEqual(result.hour, 9)
            self.assertEqual(result.minute, 0)
    
    def test_no_full_updates_in_log(self):
        """Test when no full system updates are found in log."""
        # Log with only individual package installations
        log_content = b"""
[2024-01-15T10:30:00+0000] [PACMAN] Running 'pacman -S vim'
[2024-01-15T10:30:05+0000] [PACMAN] installed vim (9.0-1)
[2024-01-20T14:20:00+0000] [PACMAN] Running 'pacman -S emacs'
[2024-01-20T14:20:05+0000] [PACMAN] installed emacs (28.0-1)
"""
        
        # Create a properly configured mock file
        m_open = mock_open()
        m_file = m_open.return_value
        m_file.tell.return_value = len(log_content)
        m_file.read.return_value = log_content
        
        with patch('os.path.exists', return_value=True), \
             patch('builtins.open', m_open):
            
            result = PacmanRunner.get_last_full_update_time()
            
            # Should return None when no full updates found
            self.assertIsNone(result)
    
    def test_pacman_log_not_exists(self):
        """Test when pacman log doesn't exist."""
        with patch('os.path.exists', return_value=False):
            result = PacmanRunner.get_last_full_update_time()
            self.assertIsNone(result)
    
    def test_malformed_timestamp(self):
        """Test handling of malformed timestamps in log."""
        log_content = b"""
[INVALID-TIMESTAMP] [PACMAN] starting full system upgrade
[2024-01-15T10:30:00+0000] [PACMAN] starting full system upgrade
[2024-01-20TBROKEN] [PACMAN] starting full system upgrade
"""
        
        # Create a properly configured mock file
        m_open = mock_open()
        m_file = m_open.return_value
        m_file.tell.return_value = len(log_content)
        m_file.read.return_value = log_content
        
        with patch('os.path.exists', return_value=True), \
             patch('builtins.open', m_open):
            
            result = PacmanRunner.get_last_full_update_time()
            
            # Should parse the valid timestamp and ignore invalid ones
            self.assertIsNotNone(result)
            self.assertEqual(result.year, 2024)
            self.assertEqual(result.month, 1)
            self.assertEqual(result.day, 15)
    
    def test_large_log_file_efficiency(self):
        """Test that we only read the last portion of large log files."""
        # Create a very large log content
        old_entries = "[2023-01-01T00:00:00+0000] Old entry\n" * 10000
        recent_entry = "[2024-01-25T09:00:10+0000] [PACMAN] starting full system upgrade\n"
        log_content = (old_entries + recent_entry).encode()
        
        # Create a more complete file mock
        mock_file_handle = mock_open(read_data=log_content)()
        mock_file_handle.tell.return_value = len(log_content)
        mock_file_handle.seek = lambda pos, whence=0: None
        mock_file_handle.read.return_value = log_content[-10*1024*1024:]  # Last 10MB
        
        with patch('os.path.exists', return_value=True), \
             patch('builtins.open', return_value=mock_file_handle):
            
            result = PacmanRunner.get_last_full_update_time()
            
            # Should still find the recent update
            self.assertIsNotNone(result)
            self.assertEqual(result.year, 2024)


if __name__ == '__main__':
    unittest.main() 