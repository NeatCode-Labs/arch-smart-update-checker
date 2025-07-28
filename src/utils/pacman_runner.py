"""
Shared utility for running pacman commands.
"""

# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations

import tempfile
import os
import time
import subprocess
from typing import List, Tuple, Optional, Dict, Any
from datetime import datetime
from pathlib import Path
import re

from ..utils.logger import get_logger, log_security_event
from ..utils.update_history import UpdateHistoryEntry
from .subprocess_wrapper import SecureSubprocess

logger = get_logger(__name__)


class PacmanRunner:
    """Handles execution of pacman commands."""

    @staticmethod
    def get_database_last_sync_time() -> Optional[datetime]:
        """Get the last time the package database was synced."""
        try:
            # Check multiple possible locations for pacman database
            db_paths = [
                "/var/lib/pacman/sync/core.db",
                "/var/lib/pacman/sync/extra.db",
                "/var/lib/pacman/sync/multilib.db"
            ]
            
            latest_time = None
            for db_path in db_paths:
                if os.path.exists(db_path):
                    mtime = os.path.getmtime(db_path)
                    db_time = datetime.fromtimestamp(mtime)
                    if latest_time is None or db_time > latest_time:
                        latest_time = db_time
            
            return latest_time
            
        except Exception as e:
            logger.error(f"Failed to get database sync time: {e}")
            return None

    @staticmethod
    def get_last_full_update_time() -> Optional[datetime]:
        """Get the last time a full system update was performed (from pacman log)."""
        try:
            pacman_log = "/var/log/pacman.log"
            if not os.path.exists(pacman_log):
                return None
            
            # We'll look for patterns that indicate a full system update
            # Full updates typically have "starting full system upgrade" in the log
            full_update_pattern = re.compile(r'\[(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}[+-]\d{4})\].*starting full system upgrade')
            
            last_update_time = None
            
            # Read the log file from the end for efficiency (most recent entries first)
            # We'll read the last 10MB of the log to find recent updates
            max_bytes = 10 * 1024 * 1024  # 10MB
            
            with open(pacman_log, 'rb') as f:
                # Seek to the end
                f.seek(0, 2)
                file_size = f.tell()
                
                # Read from max_bytes before end, or from start if file is smaller
                start_pos = max(0, file_size - max_bytes)
                f.seek(start_pos)
                
                # Read the content
                content = f.read().decode('utf-8', errors='ignore')
                
                # Find all full system upgrade entries
                for match in full_update_pattern.finditer(content):
                    timestamp_str = match.group(1)
                    try:
                        # Parse the timestamp
                        update_time = datetime.strptime(timestamp_str, '%Y-%m-%dT%H:%M:%S%z')
                        # Remove timezone info for comparison
                        update_time = update_time.replace(tzinfo=None)
                        
                        if last_update_time is None or update_time > last_update_time:
                            last_update_time = update_time
                    except Exception as e:
                        logger.debug(f"Failed to parse timestamp {timestamp_str}: {e}")
                        continue
            
            return last_update_time
            
        except Exception as e:
            logger.error(f"Failed to get last full update time from pacman log: {e}")
            return None

    @staticmethod
    def sync_database(config) -> Dict[str, Any]:
        """
        Sync pacman database using secure subprocess execution.
        
        Returns:
            Dict with 'success' (bool), 'output' (str), and 'error' (str if failed)
        """
        try:
            logger.info("Syncing pacman database...")
            
            # Use pkexec for privilege elevation (more secure than sudo)
            result = SecureSubprocess.run(
                ["pkexec", "pacman", "-Sy"],
                capture_output=True,
                text=True,
                check=False,
                timeout=300  # 5 minute timeout for sync
            )
            
            if result.returncode == 0:
                logger.info("Database sync completed successfully")
                return {
                    'success': True,
                    'output': result.stdout,
                    'error': None
                }
            else:
                error_msg = result.stderr if result.stderr else f"Exit code: {result.returncode}"
                logger.error(f"Database sync failed: {error_msg}")
                return {
                    'success': False,
                    'output': result.stdout,
                    'error': error_msg
                }
                
        except subprocess.TimeoutExpired:
            logger.error("Database sync timed out")
            return {
                'success': False,
                'output': '',
                'error': 'Sync operation timed out after 5 minutes'
            }
        except Exception as e:
            logger.error(f"Failed to sync database: {e}")
            return {
                'success': False,
                'output': '',
                'error': str(e)
            }

    @staticmethod
    def run_update_in_terminal(packages: List[str]) -> Optional[subprocess.Popen]:
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
        
        # Log package update operation for security auditing
        log_security_event(
            "PACKAGE_UPDATE_INITIATED",
            {
                "packages": packages[:10],  # Log first 10 packages
                "package_count": len(packages),
                "update_type": "selected_packages"
            },
            severity="info"
        )

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
