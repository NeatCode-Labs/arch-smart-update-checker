"""
Tests for the PacmanRunner utility.
"""

import pytest
import subprocess
import tempfile
import time
from datetime import datetime
from unittest.mock import patch, Mock, mock_open

from src.utils.pacman_runner import PacmanRunner
from src.utils.update_history import UpdateHistoryEntry


@pytest.fixture(autouse=True)
def mock_secure_subprocess():
    """Mock SecureSubprocess methods for all PacmanRunner tests."""
    with patch('src.utils.subprocess_wrapper.SecureSubprocess.validate_command') as mock_validate, \
         patch('src.utils.subprocess_wrapper.SecureSubprocess._find_command_path') as mock_find_path, \
         patch('src.utils.subprocess_wrapper.SecureSubprocess.check_command_exists') as mock_check_exists:
        
        mock_validate.return_value = True
        mock_find_path.return_value = '/usr/bin/fake_command'
        mock_check_exists.return_value = True
        yield


class TestPacmanRunner:
    """Test PacmanRunner functionality."""
    
    @patch('src.utils.subprocess_wrapper.SecureSubprocess.check_command_exists')
    @patch('src.utils.subprocess_wrapper.SecureSubprocess.popen')
    def test_run_update_in_terminal_success(self, mock_popen, mock_check_exists):
        """Test running update in terminal with successful terminal detection."""
        # Mock command exists check to return True for gnome-terminal
        mock_check_exists.return_value = True
        
        # Mock Popen to return a process
        mock_process = Mock()
        mock_popen.return_value = mock_process
        
        packages = ['python', 'firefox']
        result = PacmanRunner.run_update_in_terminal(packages)
        
        assert result == mock_process
        mock_check_exists.assert_called()
        mock_popen.assert_called_once()
        
        # Verify the command structure
        call_args = mock_popen.call_args[0][0]
        assert 'gnome-terminal' in call_args
        assert '--' in call_args
        assert 'bash' in call_args
    
    @patch('src.utils.subprocess_wrapper.SecureSubprocess.check_command_exists')
    @patch('src.utils.subprocess_wrapper.SecureSubprocess.popen')
    def test_run_update_in_terminal_fallback(self, mock_popen, mock_check_exists):
        """Test terminal fallback when preferred terminals are not available."""
        # Mock command exists to return False for first few terminals, True for xterm
        def mock_check_side_effect(cmd):
            if cmd in ['gnome-terminal', 'konsole', 'xfce4-terminal']:
                return False  # Not found
            else:
                return True  # Found
        
        mock_check_exists.side_effect = mock_check_side_effect
        mock_process = Mock()
        mock_popen.return_value = mock_process
        
        packages = ['vim']
        result = PacmanRunner.run_update_in_terminal(packages)
        
        assert result == mock_process
        # Should have tried multiple terminals
        assert mock_check_exists.call_count >= 3
    
    @patch('src.utils.subprocess_wrapper.SecureSubprocess.check_command_exists')
    def test_run_update_in_terminal_no_terminal(self, mock_check_exists):
        """Test when no terminal emulator is found."""
        # Mock all command exists checks to return False
        mock_check_exists.return_value = False
        
        packages = ['git']
        result = PacmanRunner.run_update_in_terminal(packages)
        
        assert result is None
    
    @patch('src.utils.subprocess_wrapper.SecureSubprocess.run_pacman')
    def test_run_update_interactive_success(self, mock_run_pacman):
        """Test interactive update with success."""
        packages = ['test-package']
        
        # Mock successful pacman execution
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = ""
        mock_result.stderr = ""
        mock_run_pacman.return_value = mock_result
        
        exit_code, duration, output = PacmanRunner.run_update_interactive(packages)
        
        assert exit_code == 0
        assert duration > 0
        assert output is None
        
        # Verify correct command was called
        mock_run_pacman.assert_called_once_with(
            ["-Su", "test-package"],
            require_sudo=True,
            capture_output=False,
            check=False
        )
    
    @patch('src.utils.subprocess_wrapper.SecureSubprocess.run_pacman')
    def test_run_update_interactive_failure(self, mock_run_pacman):
        """Test interactive update with failure."""
        packages = ['failing-package']
        
        # Mock failed pacman execution
        mock_result = Mock()
        mock_result.returncode = 1
        mock_result.stdout = ""
        mock_result.stderr = "Some error"
        mock_run_pacman.return_value = mock_result
        
        exit_code, duration, output = PacmanRunner.run_update_interactive(packages)
        
        assert exit_code == 1
        assert duration > 0
        assert output is None
    
    @patch('src.utils.subprocess_wrapper.SecureSubprocess.run_pacman')
    def test_run_update_interactive_with_capture(self, mock_run_pacman):
        """Test running update with output capture."""
        packages = ['test-package']
        
        # Mock successful result
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = "Update successful"
        mock_result.stderr = "Warning: something"
        mock_run_pacman.return_value = mock_result
        
        exit_code, duration, output = PacmanRunner.run_update_interactive(
            packages, capture_output=True
        )
        
        assert exit_code == 0
        assert duration > 0
        assert "Update successful" in output or "Warning: something" in output
        
        # Verify run_pacman was called with correct parameters
        mock_run_pacman.assert_called_once()
        call_args = mock_run_pacman.call_args[0]
        assert '-Su' in call_args[0]  # Command should contain -Su flag
        assert 'test-package' in call_args[0]  # Should include our package
    
    @patch('src.utils.subprocess_wrapper.SecureSubprocess.run_pacman')
    def test_run_update_interactive_exception(self, mock_run_pacman):
        """Test handling of exceptions during update."""
        packages = ['exception-package']
        
        # Mock exception during pacman execution
        mock_run_pacman.side_effect = OSError("Command not found")
        
        exit_code, duration, output = PacmanRunner.run_update_interactive(packages)
        
        assert exit_code == 1
        assert duration > 0
        assert "Command not found" in output
    
    def test_create_history_entry(self):
        """Test creation of history entries."""
        packages = ['kernel', 'systemd']
        exit_code = 0
        duration = 45.7
        
        # Mock datetime.now() to get predictable timestamp
        fixed_time = datetime(2024, 1, 15, 12, 30, 45)
        with patch('src.utils.pacman_runner.datetime') as mock_datetime:
            mock_datetime.now.return_value = fixed_time
            
            entry = PacmanRunner.create_history_entry(packages, exit_code, duration)
            
            assert isinstance(entry, UpdateHistoryEntry)
            assert entry.timestamp == fixed_time
            assert entry.packages == packages
            assert entry.succeeded is True
            assert entry.exit_code == exit_code
            assert entry.duration_sec == duration
    
    def test_create_history_entry_failure(self):
        """Test creation of history entry for failed update."""
        packages = ['failing-package']
        exit_code = 1
        duration = 10.2
        
        entry = PacmanRunner.create_history_entry(packages, exit_code, duration)
        
        assert entry.succeeded is False
        assert entry.exit_code == 1
        assert entry.packages == packages
        assert entry.duration_sec == duration
    
    @patch('tempfile.NamedTemporaryFile')
    @patch('src.utils.subprocess_wrapper.SecureSubprocess.popen')
    def test_terminal_command_construction(self, mock_popen, mock_tempfile):
        """Test that terminal commands are constructed correctly."""
        # Mock temporary file
        mock_file = Mock()
        mock_file.name = '/tmp/test.log'
        mock_tempfile.return_value.__enter__.return_value = mock_file
        mock_tempfile.return_value.name = '/tmp/test.log'
        
        # Mock Popen process
        mock_process = Mock()
        mock_popen.return_value = mock_process
        
        packages = ['package1', 'package2']
        result = PacmanRunner.run_update_in_terminal(packages)
        
        # Verify Popen was called
        assert mock_popen.called
        
        # Check that a bash script is being executed (packages are in the script content, not in the command)
        call_args = mock_popen.call_args[0][0]  # First positional argument (command list)
        command_str = ' '.join(call_args)
        # The command should be running bash with a script file
        assert 'bash' in command_str
        assert '/tmp/asuc_pacman_' in command_str
        assert '.sh' in command_str
        assert result == mock_process
    
    @patch('src.utils.subprocess_wrapper.SecureSubprocess.run_pacman')
    def test_multiple_packages_handling(self, mock_run_pacman):
        """Test handling of multiple packages in commands."""
        packages = ['pkg1', 'pkg2', 'pkg3', 'pkg4']
        
        # Mock successful pacman execution
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = ""
        mock_result.stderr = ""
        mock_run_pacman.return_value = mock_result
        
        exit_code, duration, output = PacmanRunner.run_update_interactive(packages)
        
        # Verify all packages are included in the command
        expected_args = ['-Su', 'pkg1', 'pkg2', 'pkg3', 'pkg4']
        mock_run_pacman.assert_called_once_with(
            expected_args,
            require_sudo=True,
            capture_output=False,
            check=False
        )
    
    @patch('src.utils.subprocess_wrapper.SecureSubprocess.run_pacman')
    def test_empty_packages_list(self, mock_run_pacman):
        """Test behavior with empty packages list."""
        packages = []
        
        # Mock successful pacman execution
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = ""
        mock_result.stderr = ""
        mock_run_pacman.return_value = mock_result
        
        exit_code, duration, output = PacmanRunner.run_update_interactive(packages)
        
        # Should still call pacman but with no package arguments
        expected_args = ['-Su']
        mock_run_pacman.assert_called_once_with(
            expected_args,
            require_sudo=True,
            capture_output=False,
            check=False
        )
    
    @patch('time.time')
    @patch('src.utils.subprocess_wrapper.SecureSubprocess.run_pacman')
    def test_duration_calculation(self, mock_run_pacman, mock_time):
        """Test that duration is calculated correctly."""
        # Mock time.time() to return predictable values
        mock_time.side_effect = [100.0, 145.5]  # Start and end times
        
        packages = ['test-pkg']
        
        # Mock successful pacman execution
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = ""
        mock_result.stderr = ""
        mock_run_pacman.return_value = mock_result
        
        exit_code, duration, output = PacmanRunner.run_update_interactive(packages)
        
        assert duration == 45.5  # 145.5 - 100.0
        assert exit_code == 0 