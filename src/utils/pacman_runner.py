"""
Shared utility for running pacman commands.
"""

# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations

import tempfile
import os
import time
import subprocess
from typing import List, Tuple, Optional
from datetime import datetime
from pathlib import Path

from ..utils.logger import get_logger
from ..utils.update_history import UpdateHistoryEntry
from .subprocess_wrapper import SecureSubprocess

logger = get_logger(__name__)


class PacmanRunner:
    """Handles execution of pacman commands."""

    @staticmethod
    def get_database_last_sync_time() -> Optional[datetime]:
        """
        Get the last time pacman database was synced by checking the modification
        time of sync database files.

        Returns:
            datetime of last sync or None if unable to determine
        """
        sync_dir = Path("/var/lib/pacman/sync")

        try:
            if not sync_dir.exists():
                logger.warning("Pacman sync directory does not exist")
                return None

            # Check for common db files (core.db, extra.db, multilib.db, etc.)
            db_files = list(sync_dir.glob("*.db"))

            if not db_files:
                logger.warning("No database files found in pacman sync directory")
                return None

            # Get the most recent modification time
            latest_mtime = max(db_file.stat().st_mtime for db_file in db_files)

            # Convert to datetime in local timezone
            # The file system stores timestamps in UTC, but fromtimestamp() converts to local time
            # This is the correct behavior - we want to display local time to the user
            sync_time = datetime.fromtimestamp(latest_mtime)

            # Log the detected time for debugging
            logger.debug(f"Database sync time detected: {sync_time} (timestamp: {latest_mtime})")

            return sync_time

        except Exception as e:
            logger.error(f"Error getting database sync time: {e}")
            return None

    @staticmethod
    def run_update_in_terminal(packages: List[str]) -> Optional[subprocess.Popen[str]]:
        """
        Run pacman update in a terminal emulator.

        Args:
            packages: List of packages to update

        Returns:
            Popen object if successful, None otherwise
        """
        # Validate all package names first
        for pkg in packages:
            try:
                SecureSubprocess.sanitize_package_name(pkg)
            except ValueError as e:
                logger.error(f"Invalid package name: {pkg} - {e}")
                return None

        # Use -Su to upgrade selected packages
        cmd_args = ["sudo", "pacman", "-Su", "--noconfirm"] + packages

        # Create a secure temporary file to capture output
        import stat
        output_fd, output_path = tempfile.mkstemp(suffix='.log', prefix='asuc_pacman_')
        os.close(output_fd)  # Close the file descriptor, we'll open by path

        # Set secure permissions (owner only)
        os.chmod(output_path, stat.S_IRUSR | stat.S_IWUSR)  # 0o600

        # Create secure script to avoid shell injection
        from ..utils.validators import validate_log_path

        # Validate output path for security
        try:
            validate_log_path(output_path)
        except ValueError as e:
            logger.error(f"Invalid output path: {e}")
            return None

        # Create secure script file instead of shell command construction
        script_fd, script_path = tempfile.mkstemp(suffix='.sh', prefix='asuc_pacman_')
        try:
            # Build secure script content with validated arguments
            script_content = f'''#!/bin/bash
set -e
set -o pipefail

echo "Starting package update..."
echo "Command: {' '.join(cmd_args)}"
echo

# Execute the command and capture exit code securely
if {' '.join(cmd_args)} 2>&1 | tee "{output_path}"; then
    EXIT_CODE=${{PIPESTATUS[0]}}
else
    EXIT_CODE=$?
fi

echo "$EXIT_CODE" > "{output_path}.exitcode"

echo
if [ "$EXIT_CODE" -eq 0 ]; then
    echo "Update completed successfully!"
else
    echo "Update failed with exit code: $EXIT_CODE"
fi

echo "Press Enter to close this window..."
read
'''

            with os.fdopen(script_fd, 'w') as f:
                f.write(script_content)

            # Set secure executable permissions (owner only)
            os.chmod(script_path, 0o700)

            # Use array-based terminal commands to avoid injection
            terminal_commands = [
                ['gnome-terminal', '--', 'bash', script_path],
                ['konsole', '-e', 'bash', script_path],
                ['xfce4-terminal', '-e', f'bash {script_path}'],
                ['xterm', '-e', 'bash', script_path],
                ['alacritty', '-e', 'bash', script_path],
                ['termite', '-e', f'bash {script_path}'],
                ['kitty', '--', 'bash', script_path],
                ['tilix', '-e', 'bash', script_path]
            ]

            for term_cmd in terminal_commands:
                try:
                    terminal = term_cmd[0]
                    # Check if terminal exists
                    if SecureSubprocess.check_command_exists(terminal):
                        proc = SecureSubprocess.popen(term_cmd)
                        logger.info(f"Started update in {terminal}")
                        return proc
                except (FileNotFoundError, OSError, ValueError):
                    continue

            return None

        finally:
            # Clean up script file
            try:
                os.unlink(script_path)
            except (OSError, FileNotFoundError):
                pass

    @staticmethod
    def run_update_interactive(packages: List[str], capture_output: bool = False) -> Tuple[int, float, Optional[str]]:
        """
        Run pacman update interactively in the current terminal.

        Args:
            packages: List of packages to update
            capture_output: Whether to capture output

        Returns:
            Tuple of (exit_code, duration_sec, output_text)
        """
        # Validate all package names first
        for pkg in packages:
            try:
                SecureSubprocess.sanitize_package_name(pkg)
            except ValueError as e:
                logger.error(f"Invalid package name: {pkg} - {e}")
                return 1, 0.0, str(e)

        cmd_args = ["-Su"] + packages

        start_time = time.time()

        try:
            if capture_output:
                # Capture output
                result = SecureSubprocess.run_pacman(
                    cmd_args,
                    require_sudo=True,
                    capture_output=True,
                    text=True,
                    check=False
                )
                exit_code = result.returncode
                output = result.stdout + result.stderr
            else:
                # Run interactively
                result = SecureSubprocess.run_pacman(
                    cmd_args,
                    require_sudo=True,
                    capture_output=False,
                    check=False
                )
                exit_code = result.returncode
                output = None

            duration = time.time() - start_time

            return exit_code, duration, output

        except Exception as e:
            logger.error(f"Error running pacman update: {e}")
            duration = time.time() - start_time
            return 1, duration, str(e)

    @staticmethod
    def create_history_entry(packages: List[str], exit_code: int, duration: float) -> UpdateHistoryEntry:
        """
        Create an update history entry.

        Args:
            packages: List of updated packages
            exit_code: Exit code from pacman
            duration: Duration in seconds

        Returns:
            UpdateHistoryEntry object
        """
        return UpdateHistoryEntry(
            timestamp=datetime.now(),
            packages=packages,
            succeeded=(exit_code == 0),
            exit_code=exit_code,
            duration_sec=duration
        )
