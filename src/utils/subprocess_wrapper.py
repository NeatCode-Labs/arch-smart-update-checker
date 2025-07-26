"""
Secure subprocess wrapper to prevent command injection and handle errors properly.
"""

# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations

import subprocess
import shlex
import os
import stat
from typing import List, Tuple, Optional, Union, Dict, Any
import logging
from pathlib import Path
import threading
import re

from ..exceptions import PackageManagerError
from ..utils.logger import get_logger, log_security_event

logger = get_logger(__name__)


class SecureSubprocess:
    """Enhanced secure wrapper for subprocess operations with dynamic command discovery."""

    # Essential commands that must be available for core functionality
    ESSENTIAL_COMMANDS: Dict[str, Dict[str, Any]] = {
        'pacman': {
            'description': 'Package manager',
            'required': True,
            'search_paths': ['/usr/bin', '/bin', '/usr/local/bin'],
            'alternatives': [],
        },
        'sudo': {
            'description': 'Privilege escalation',
            'required': True,
            'search_paths': ['/usr/bin', '/bin', '/usr/local/bin'],
            'alternatives': ['doas', 'pkexec'],
        }
    }

    # Optional commands for enhanced functionality
    OPTIONAL_COMMANDS: Dict[str, Dict[str, Any]] = {
        'checkupdates': {
            'description': 'Check for package updates',
            'required': False,
            'search_paths': ['/usr/bin', '/usr/local/bin'],
            'alternatives': [],
        },
        'bwrap': {
            'description': 'Bubblewrap sandboxing tool',
            'alternatives': []
        },
        'pacman': {
            'description': 'Package manager',
            'required': True,
            'search_paths': ['/usr/bin', '/bin', '/usr/local/bin'],
            'alternatives': [],
        },
        'which': {
            'description': 'Command location finder',
            'required': False,
            'search_paths': ['/usr/bin', '/bin', '/usr/local/bin'],
            'alternatives': ['whereis', 'command'],
        },
        'bash': {
            'description': 'Bash shell',
            'required': False,
            'search_paths': ['/usr/bin', '/bin', '/usr/local/bin'],
            'alternatives': ['sh', 'dash', 'zsh'],
        },
        'sh': {
            'description': 'POSIX shell',
            'required': False,
            'search_paths': ['/usr/bin', '/bin'],
            'alternatives': ['bash', 'dash'],
        },
        'xdg-open': {
            'description': 'Open files/URLs with default application (Linux)',
            'required': False,
            'search_paths': ['/usr/bin', '/usr/local/bin'],
            'alternatives': [],
        }
    }

    # Terminal emulators (platform-specific)
    TERMINAL_EMULATORS = {
        'linux': [
            'gnome-terminal', 'konsole', 'xfce4-terminal', 'xterm',
            'alacritty', 'termite', 'kitty', 'tilix', 'terminator',
            'mate-terminal', 'lxterminal', 'rxvt-unicode'
        ],
        'darwin': ['Terminal', 'iTerm', 'Alacritty'],
        'windows': ['cmd', 'powershell', 'wt']
    }

    # Text editors (platform-specific)
    TEXT_EDITORS = {
        'linux': [
            'xdg-open', 'gedit', 'kate', 'mousepad', 'leafpad',
            'xed', 'pluma', 'nano', 'vim', 'emacs'
        ],
        'darwin': ['open', 'TextEdit', 'nano', 'vim'],
        'windows': ['notepad', 'code', 'nano']
    }

    # Commands that are allowed to run with privilege escalation
    # Note: systemctl, mount, and umount now have dedicated secure wrappers
    PRIVILEGE_ALLOWED = {'pacman', 'paccache'}

    # Cache for validated command paths and system info
    _command_path_cache: Dict[str, str] = {}
    _system_info_cache: Dict[str, Any] = {}
    _validation_lock = threading.Lock()

    @classmethod
    def _get_system_info(cls) -> Dict[str, Any]:
        """
        Get cached system information for command discovery.

        Returns:
            Dictionary with system information
        """
        if not cls._system_info_cache:
            import platform
            system = platform.system().lower()

            cls._system_info_cache = {
                'platform': system,
                'architecture': platform.machine(),
                'paths': cls._get_system_paths(),
                'shell': os.environ.get('SHELL', '/bin/sh'),
                'user_id': os.getuid() if hasattr(os, 'getuid') else 0,
                'home_dir': os.path.expanduser('~'),
            }

        return cls._system_info_cache

    @classmethod
    def _get_system_paths(cls) -> List[str]:
        """
        Get system PATH directories with security validation.

        Returns:
            List of validated PATH directories
        """
        path_env = os.environ.get('PATH', '')
        paths = []

        for path_dir in path_env.split(os.pathsep):
            path_dir = path_dir.strip()
            if not path_dir:
                continue

            try:
                # Security validation
                if cls._is_safe_directory(path_dir):
                    paths.append(path_dir)
                else:
                    logger.debug(f"Skipping unsafe path directory: {path_dir}")
            except Exception as e:
                logger.debug(f"Error validating path directory {path_dir}: {e}")

        # Add standard system paths if not already included
        standard_paths = ['/usr/bin', '/bin', '/usr/local/bin', '/usr/sbin', '/sbin']
        for std_path in standard_paths:
            if std_path not in paths and os.path.isdir(std_path):
                if cls._is_safe_directory(std_path):
                    paths.append(std_path)

        return paths

    @classmethod
    def _is_safe_directory(cls, directory: str) -> bool:
        """
        Validate if a directory is safe for command execution.

        Args:
            directory: Directory path to validate

        Returns:
            True if directory is safe
        """
        try:
            # Must exist and be a directory
            if not os.path.isdir(directory):
                return False

            # Get directory stats
            stat_info = os.stat(directory)

            # Should not be writable by others (security check)
            if stat_info.st_mode & stat.S_IWOTH:
                logger.warning(f"Directory {directory} is world-writable, skipping")
                return False

            # Check ownership (should be root or current user on Unix systems)
            if hasattr(os, 'getuid'):
                current_uid = os.getuid()
                if stat_info.st_uid != 0 and stat_info.st_uid != current_uid:
                    logger.debug(f"Directory {directory} has suspicious ownership")
                    # Don't fail here, just log it

            # Additional platform-specific checks
            import platform
            current_platform = platform.system().lower()
            if current_platform == 'windows':
                # On Windows, check if path is in system or program directories
                windows_safe_prefixes = ['c:\\windows', 'c:\\program files', 'c:\\users']
                return any(directory.lower().startswith(prefix) for prefix in windows_safe_prefixes)

            return True

        except (OSError, PermissionError) as e:
            logger.debug(f"Cannot access directory {directory}: {e}")
            return False

    @classmethod
    def _find_command_path(cls, command: str) -> Optional[str]:
        """
        Find the absolute path of a command with enhanced security validation.

        Args:
            command: Command name to find

        Returns:
            Absolute path if found and valid, None otherwise
        """
        with cls._validation_lock:
            # Check cache first
            if command in cls._command_path_cache:
                cached_path = cls._command_path_cache[command]
                # Validate cached path is still valid
                if cached_path and os.path.exists(cached_path) and cls._validate_command_security(cached_path):
                    return cached_path
                else:
                    # Remove invalid cached entry
                    del cls._command_path_cache[command]

            # Get system paths (avoid circular dependency during initialization)
            if cls._system_info_cache:
                # System info is already initialized, use it
                system_info = cls._get_system_info()
                paths = system_info['paths']
            else:
                # System info not yet initialized, use basic PATH directly
                # This prevents circular dependency during initialization
                path_env = os.environ.get('PATH', '')
                paths = [p.strip() for p in path_env.split(os.pathsep) if p.strip()]
                # Add standard system paths
                standard_paths = ['/usr/bin', '/bin', '/usr/local/bin', '/usr/sbin', '/sbin']
                for std_path in standard_paths:
                    if std_path not in paths and os.path.isdir(std_path):
                        paths.append(std_path)

            # Look for command in system paths
            for path_dir in paths:
                full_path = os.path.join(path_dir, command)

                # Check for executable file
                if os.path.isfile(full_path) and os.access(full_path, os.X_OK):
                    if cls._validate_command_security(full_path):
                        cls._command_path_cache[command] = full_path
                        logger.debug(f"Found command {command} at {full_path}")
                        return full_path

            # Try using system 'which' or 'where' command as fallback
            try:
                # Get system info if not already available
                if not hasattr(cls, '_system_info_cache') or not cls._system_info_cache:
                    system_info = cls._get_system_info()
                else:
                    system_info = cls._system_info_cache
                which_cmd = 'where' if system_info['platform'] == 'windows' else 'which'
                result = subprocess.run([which_cmd, command],
                                        capture_output=True, text=True, timeout=5)
                if result.returncode == 0 and result.stdout.strip():
                    found_path = result.stdout.strip().split('\n')[0]
                    if cls._validate_command_security(found_path):
                        cls._command_path_cache[command] = found_path
                        logger.debug(f"Found command {command} using {which_cmd}: {found_path}")
                        return found_path
            except Exception as e:
                logger.debug(f"Error using {which_cmd} to find {command}: {e}")

            # Command not found
            logger.warning(f"Command {command} not found in system PATH")
            return None

    @classmethod
    def _validate_command_security(cls, command_path: str) -> bool:
        """
        Validate command security properties.

        Args:
            command_path: Full path to command

        Returns:
            True if command passes security validation
        """
        try:
            # Must exist and be executable
            if not (os.path.isfile(command_path) and os.access(command_path, os.X_OK)):
                return False

            # Get file stats
            stat_info = os.stat(command_path)

            # Security checks for Unix systems
            if hasattr(os, 'getuid'):
                # Should not be writable by group or others
                if stat_info.st_mode & (stat.S_IWGRP | stat.S_IWOTH):
                    logger.warning(f"Command {command_path} has unsafe permissions")
                    return False

                # Check ownership (should be root or current user)
                current_uid = os.getuid()
                if stat_info.st_uid != 0 and stat_info.st_uid != current_uid:
                    logger.warning(f"Command {command_path} has suspicious ownership")
                    # Don't fail here for flexibility, but log it

            # Check if command is in a safe directory
            command_dir = os.path.dirname(command_path)
            if not cls._is_safe_directory(command_dir):
                logger.warning(f"Command {command_path} is in unsafe directory")
                return False

            # Additional file type checks
            if not cls._is_safe_executable(command_path):
                return False

            return True

        except (OSError, PermissionError) as e:
            logger.warning(f"Error validating command {command_path}: {e}")
            return False

    @classmethod
    def _is_safe_executable(cls, file_path: str) -> bool:
        """
        Check if executable file is safe to run.

        Args:
            file_path: Path to executable file

        Returns:
            True if file appears safe
        """
        try:
            # Check file type using file command if available (avoid recursion during init)
            file_cmd_path = None
            if cls._system_info_cache:
                # Only try to find 'file' command if system is already initialized
                file_cmd_path = cls._find_command_path('file')

            if file_cmd_path:
                result = subprocess.run([file_cmd_path, file_path],
                                        capture_output=True, text=True, timeout=5)
                if result.returncode == 0:
                    file_type = result.stdout.lower()
                    # Should be an executable
                    if 'executable' not in file_type and 'script' not in file_type:
                        logger.debug(f"File {file_path} may not be executable: {file_type}")

            # Basic checks for script files
            if file_path.endswith(('.py', '.sh', '.bash', '.pl', '.rb')):
                # Read first line to check shebang
                try:
                    with open(file_path, 'rb') as f:
                        first_line = f.readline(100).decode('utf-8', errors='ignore')
                        if not first_line.startswith('#!'):
                            logger.debug(f"Script {file_path} missing shebang")
                except Exception:
                    pass

            return True

        except Exception as e:
            logger.debug(f"Error checking executable {file_path}: {e}")
            return True  # Allow by default, but log the error

    @classmethod
    def run_systemctl(
        cls,
        action: str,
        service: str,
        user_mode: bool = False,
        timeout: int = 30,
        **kwargs: Any
    ) -> subprocess.CompletedProcess:
        """
        Run systemctl command with strict validation.

        Args:
            action: Action to perform (start, stop, enable, disable, is-active, is-enabled)
            service: Service name to act on
            user_mode: Whether to use --user flag
            timeout: Command timeout
            **kwargs: Additional arguments for subprocess.run

        Returns:
            CompletedProcess instance

        Raises:
            ValueError: If action or service is invalid
        """
        # Whitelist of allowed systemctl actions
        ALLOWED_ACTIONS = {
            'start', 'stop', 'restart', 'enable', 'disable',
            'is-active', 'is-enabled', 'status', 'show'
        }
        
        # Whitelist of allowed services (extend as needed)
        ALLOWED_SERVICES = {
            'apparmor', 'apparmor.service',
            'arch-smart-update-checker.service',
            'arch-smart-update-checker.timer',
            # Add more services as needed
        }
        
        # Validate action
        if action not in ALLOWED_ACTIONS:
            raise ValueError(f"Systemctl action '{action}' not allowed")
        
        # Validate service name
        if not re.match(r'^[a-zA-Z0-9\-_.]+$', service):
            raise ValueError(f"Invalid service name format: {service}")
        
        # For non-query actions, enforce service whitelist
        if action not in {'is-active', 'is-enabled', 'status', 'show'}:
            if service not in ALLOWED_SERVICES:
                log_security_event(
                    "SYSTEMCTL_SERVICE_NOT_WHITELISTED",
                    {"service": service, "action": action},
                    severity="warning"
                )
                raise ValueError(f"Service '{service}' not in allowed list")
        
        # Build command
        cmd = ['systemctl']
        if user_mode:
            cmd.append('--user')
        cmd.extend([action, service])
        
        # Log the action
        log_security_event(
            "SYSTEMCTL_COMMAND",
            {
                "action": action,
                "service": service,
                "user_mode": user_mode
            },
            severity="info"
        )
        
        return cls.run(cmd, timeout=timeout, **kwargs)

    @classmethod
    def run_mount(
        cls,
        source: str,
        target: str,
        mount_type: Optional[str] = None,
        options: Optional[List[str]] = None,
        bind: bool = False,
        timeout: int = 30,
        **kwargs: Any
    ) -> subprocess.CompletedProcess:
        """
        Run mount command with strict validation.

        Args:
            source: Source device or directory
            target: Target mount point
            mount_type: Filesystem type
            options: Mount options
            bind: Whether this is a bind mount
            timeout: Command timeout
            **kwargs: Additional arguments for subprocess.run

        Returns:
            CompletedProcess instance

        Raises:
            ValueError: If arguments are invalid
        """
        # Validate paths
        if not os.path.isabs(source) or not os.path.isabs(target):
            raise ValueError("Mount paths must be absolute")
        
        # Validate mount type if specified
        if mount_type:
            ALLOWED_FS_TYPES = {
                'ext4', 'ext3', 'ext2', 'xfs', 'btrfs', 'vfat', 'ntfs',
                'tmpfs', 'proc', 'sysfs', 'devtmpfs', 'overlay'
            }
            if mount_type not in ALLOWED_FS_TYPES:
                raise ValueError(f"Filesystem type '{mount_type}' not allowed")
        
        # Validate mount options
        if options:
            ALLOWED_OPTIONS = {
                'ro', 'rw', 'noexec', 'nosuid', 'nodev', 'relatime',
                'noatime', 'nodiratime', 'sync', 'async', 'defaults'
            }
            for opt in options:
                if opt not in ALLOWED_OPTIONS:
                    raise ValueError(f"Mount option '{opt}' not allowed")
        
        # Build command
        cmd = ['sudo', 'mount']
        
        if bind:
            cmd.append('--bind')
        
        if mount_type:
            cmd.extend(['-t', mount_type])
        
        if options:
            cmd.extend(['-o', ','.join(options)])
        
        cmd.extend([source, target])
        
        # Log the action
        log_security_event(
            "MOUNT_COMMAND",
            {
                "source": source,
                "target": target,
                "type": mount_type,
                "options": options,
                "bind": bind
            },
            severity="info"
        )
        
        return cls.run(cmd, timeout=timeout, **kwargs)

    @classmethod
    def run_umount(
        cls,
        target: str,
        force: bool = False,
        lazy: bool = False,
        timeout: int = 30,
        **kwargs: Any
    ) -> subprocess.CompletedProcess:
        """
        Run umount command with strict validation.

        Args:
            target: Mount point to unmount
            force: Force unmount
            lazy: Lazy unmount
            timeout: Command timeout
            **kwargs: Additional arguments for subprocess.run

        Returns:
            CompletedProcess instance

        Raises:
            ValueError: If arguments are invalid
        """
        # Validate path
        if not os.path.isabs(target):
            raise ValueError("Unmount path must be absolute")
        
        # Additional safety check - prevent unmounting critical paths
        PROTECTED_PATHS = {
            '/', '/boot', '/home', '/usr', '/var', '/etc', '/dev',
            '/proc', '/sys', '/run', '/tmp'
        }
        
        normalized_target = os.path.normpath(target)
        if normalized_target in PROTECTED_PATHS:
            raise ValueError(f"Cannot unmount protected path: {target}")
        
        # Build command
        cmd = ['sudo', 'umount']
        
        if force:
            cmd.append('-f')
        
        if lazy:
            cmd.append('-l')
        
        cmd.append(target)
        
        # Log the action
        log_security_event(
            "UMOUNT_COMMAND",
            {
                "target": target,
                "force": force,
                "lazy": lazy
            },
            severity="info"
        )
        
        return cls.run(cmd, timeout=timeout, **kwargs)

    @classmethod
    def validate_command(cls, cmd: List[str]) -> bool:
        """
        Validate that a command is safe to execute with enhanced security checks.

        Args:
            cmd: Command as list of arguments

        Returns:
            True if command is valid

        Raises:
            ValueError: If command is invalid
        """
        if not cmd:
            raise ValueError("Empty command")

        # Extract the actual command (handle sudo)
        actual_cmd = cmd[0]
        if actual_cmd == 'sudo' and len(cmd) > 1:
            actual_cmd = cmd[1]
            if actual_cmd not in cls.PRIVILEGE_ALLOWED:
                log_security_event(
                    "UNAUTHORIZED_SUDO_COMMAND",
                    {"command": actual_cmd, "full_command": ' '.join(cmd)},
                    severity="warning"
                )
                raise ValueError(f"Command '{actual_cmd}' not allowed with sudo")

        # Check if command is in whitelist
        cmd_name = os.path.basename(actual_cmd)
        if cmd_name not in cls.ESSENTIAL_COMMANDS and cmd_name not in cls.OPTIONAL_COMMANDS:
            log_security_event(
                "UNAUTHORIZED_COMMAND",
                {"command": actual_cmd, "full_command": ' '.join(cmd)},
                severity="warning"
            )
            raise ValueError(f"Command '{actual_cmd}' not in allowed list")

        # Validate command path exists and is secure
        if actual_cmd.startswith('/'):
            # Absolute path provided, validate it
            if not os.path.exists(actual_cmd):
                raise ValueError(f"Command path does not exist: {actual_cmd}")

            try:
                stat_info = os.stat(actual_cmd)
                if not (stat_info.st_mode & stat.S_IXUSR):
                    raise ValueError(f"Command not executable: {actual_cmd}")

                # Security check: verify ownership
                current_uid = os.getuid()
                if stat_info.st_uid != 0 and stat_info.st_uid != current_uid:
                    raise ValueError(f"Command owned by untrusted user: {actual_cmd}")

            except OSError as e:
                raise ValueError(f"Cannot validate command {actual_cmd}: {e}")
        else:
            # Command name provided, find secure path
            secure_path = cls._find_command_path(cmd_name)
            if not secure_path:
                raise ValueError(f"Cannot find secure path for command: {cmd_name}")

            # Replace command name with absolute path for security
            if cmd[0] == 'sudo' and len(cmd) > 1:
                cmd[1] = secure_path
            else:
                cmd[0] = secure_path

        return True

    @classmethod
    def get_secure_command_path(cls, command: str) -> Optional[str]:
        """
        Get the secure absolute path for a command.

        Args:
            command: Command name

        Returns:
            Absolute path if command is valid and secure, None otherwise
        """
        return cls._find_command_path(command)

    @staticmethod
    def sanitize_package_name(name: str) -> str:
        """
        Sanitize a package name to prevent injection.

        Args:
            name: Package name to sanitize

        Returns:
            Sanitized package name

        Raises:
            ValueError: If package name is invalid
        """
        # Valid package name pattern: alphanumeric, dash, underscore, plus, dot
        import re
        if not re.match(r'^[a-zA-Z0-9\-_+.]+$', name):
            raise ValueError(f"Invalid package name: {name}")

        # Additional length check
        if len(name) > 255:
            raise ValueError(f"Package name too long: {name}")

        return name

    @classmethod
    def _create_sandbox_command(cls, cmd: List[str], sandbox_type: str, cwd: Optional[str] = None) -> List[str]:
        """
        Create a sandboxed command using bubblewrap.

        Args:
            cmd: Original command to sandbox
            sandbox_type: Type of sandbox ('bwrap')
            cwd: Working directory for the command

        Returns:
            Sandboxed command list
        """
        if sandbox_type != 'bwrap':
            raise ValueError(f"Unsupported sandbox type: {sandbox_type}")

        # Check if sandbox tool is available
        sandbox_path = cls._find_command_path(sandbox_type)
        if not sandbox_path:
            logger.warning(f"Sandbox tool {sandbox_type} not found, running without sandbox")
            return cmd

        # Extract the actual command for analysis
        actual_cmd = cmd[0]
        if actual_cmd == 'sudo' and len(cmd) > 1:
            # Don't sandbox sudo commands directly
            return cmd

        if sandbox_type == 'bwrap':
            # Bubblewrap configuration
            sandbox_cmd = [sandbox_path]
            
            # Basic isolation
            sandbox_cmd.extend([
                '--ro-bind', '/usr', '/usr',
                '--ro-bind', '/lib', '/lib',
                '--ro-bind', '/lib64', '/lib64',
                '--ro-bind', '/bin', '/bin',
                '--ro-bind', '/sbin', '/sbin',
                '--ro-bind', '/etc', '/etc',
                '--proc', '/proc',
                '--dev', '/dev',
                '--tmpfs', '/tmp',
            ])
            
            # Allow access to package database (read-only)
            sandbox_cmd.extend(['--ro-bind', '/var/lib/pacman', '/var/lib/pacman'])
            sandbox_cmd.extend(['--ro-bind', '/var/cache/pacman/pkg', '/var/cache/pacman/pkg'])
            
            # If running package management commands, allow more access
            cmd_name = os.path.basename(actual_cmd)
            if cmd_name in ['pacman', 'checkupdates', 'paccache']:
                # Allow network access for package downloads
                sandbox_cmd.extend(['--share-net'])
                # Allow DNS resolution
                sandbox_cmd.extend(['--ro-bind', '/etc/resolv.conf', '/etc/resolv.conf'])
            
            # Set working directory if specified
            if cwd:
                sandbox_cmd.extend(['--chdir', cwd])
            
            # Add the original command
            sandbox_cmd.extend(['--'] + cmd)
        
        logger.debug(f"Created sandboxed command using {sandbox_type}")
        return sandbox_cmd

    @classmethod
    def run(
        cls,
        cmd: Union[List[str], str],
        capture_output: bool = True,
        text: bool = True,
        check: bool = False,
        timeout: Optional[int] = None,
        cwd: Optional[str] = None,
        env: Optional[Dict[str, str]] = None,
        sandbox: Optional[str] = None,
        sandbox_profile: Optional[str] = None,
        **kwargs: Any
    ) -> subprocess.CompletedProcess:
        """
        Run a command securely with validation and sandboxing.

        Args:
            cmd: Command to run
            capture_output: Whether to capture output
            text: Whether to decode output as text
            check: Whether to raise exception on non-zero exit
            timeout: Timeout in seconds
            cwd: Working directory
            env: Environment variables
            sandbox: Sandbox type ('bwrap')
            sandbox_profile: Name of sandbox profile to use
            **kwargs: Additional arguments for subprocess.run

        Returns:
            CompletedProcess instance
        """
        # Convert string to list if needed
        if isinstance(cmd, str):
            cmd = shlex.split(cmd)

        # Validate command
        cls.validate_command(cmd)
        
        # Apply sandboxing if requested
        if sandbox:
            original_cmd = cmd.copy()
            
            # Get sandbox profile
            if sandbox_profile:
                from .sandbox_profiles import SandboxManager
                profile = SandboxManager.get_profile(sandbox_profile)
                cmd = SandboxManager.get_sandbox_command(cmd, profile, sandbox)
            else:
                # Use legacy sandboxing method
                cmd = cls._create_sandbox_command(cmd, sandbox, cwd)
                
            if cmd != original_cmd:
                log_security_event(
                    "SANDBOXED_COMMAND_EXECUTION",
                    {
                        "sandbox_type": sandbox,
                        "profile": sandbox_profile or "legacy",
                        "command": original_cmd[0],
                        "sandboxed": True
                    },
                    severity="info"
                )
        
        # Log successful validation for security auditing
        if cmd[0] == 'sudo' or (len(cmd) > 1 and cmd[1] in ['pacman', 'paccache']):
            log_security_event(
                "PRIVILEGED_COMMAND_EXECUTION",
                {"command": cmd[0] if cmd[0] != 'sudo' else cmd[1], "args_count": len(cmd)},
                severity="info"
            )

        # Log the command for debugging (sanitized)
        from .logger import sanitize_debug_message
        sanitized_cmd = sanitize_debug_message(f"Running command: {' '.join(cmd)}")
        logger.debug(sanitized_cmd)

        # Never use shell=True
        if 'shell' in kwargs:
            del kwargs['shell']

        try:
            result = subprocess.run(
                cmd,
                capture_output=capture_output,
                text=text,
                check=check,
                timeout=timeout,
                cwd=cwd,
                env=env,
                **kwargs
            )

            if result.returncode != 0:
                logger.debug(f"Command returned non-zero: {result.returncode}")

            return result

        except subprocess.TimeoutExpired:
            logger.error(f"Command timed out after {timeout}s: {' '.join(cmd)}")
            raise
        except subprocess.CalledProcessError as e:
            logger.error(f"Command failed with code {e.returncode}: {' '.join(cmd)}")
            if e.stderr:
                logger.error(f"Error output: {e.stderr}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error running command: {e}")
            raise

    @classmethod
    def run_pacman(
        cls,
        args: List[str],
        require_sudo: bool = False,
        timeout: int = 30,
        use_sandbox: bool = True,
        **kwargs: Any
    ) -> subprocess.CompletedProcess:
        """
        Run pacman command with proper validation.

        Args:
            args: Pacman arguments
            require_sudo: Whether to run with sudo
            timeout: Command timeout
            **kwargs: Additional arguments for subprocess.run

        Returns:
            CompletedProcess instance
        """
        # Build command
        cmd = ['sudo', 'pacman'] if require_sudo else ['pacman']

        # Validate and add arguments
        for arg in args:
            if arg.startswith('-'):
                # It's a flag, allow it
                cmd.append(arg)
            else:
                # It's likely a package name, sanitize it
                try:
                    cmd.append(cls.sanitize_package_name(arg))
                except ValueError:
                    # Might be a different argument, add as-is but log
                    logger.warning(f"Adding unvalidated argument to pacman: {arg}")
                    cmd.append(arg)

        # Force English locale for consistent output parsing
        env = kwargs.get('env', os.environ.copy())
        env['LC_ALL'] = 'C'
        env['LC_TIME'] = 'C'
        kwargs['env'] = env
        
        # Determine sandbox type based on availability
        sandbox = None
        if use_sandbox and not require_sudo:  # Don't sandbox sudo commands
            if cls.check_command_exists('bwrap'):
                sandbox = 'bwrap'

        return cls.run(cmd, timeout=timeout, sandbox=sandbox, **kwargs)

    @classmethod
    def check_command_exists(cls, command: str) -> bool:
        """
        Check if a command exists and is accessible.

        Args:
            command: Command name to check

        Returns:
            True if command exists and is valid
        """
        return cls._find_command_path(command) is not None

    @classmethod
    def get_available_commands(cls) -> Dict[str, str]:
        """
        Get all available commands and their paths.

        Returns:
            Dictionary mapping command names to their paths
        """
        available = {}

        # Check essential commands
        for cmd_name in cls.ESSENTIAL_COMMANDS:
            path = cls._find_command_path(cmd_name)
            if path:
                available[cmd_name] = path

        # Check optional commands
        for cmd_name in cls.OPTIONAL_COMMANDS:
            path = cls._find_command_path(cmd_name)
            if path:
                available[cmd_name] = path

        return available

    @classmethod
    def find_terminal_emulator(cls) -> Optional[str]:
        """
        Find an available terminal emulator.

        Returns:
            Path to terminal emulator or None
        """
        system_info = cls._get_system_info()
        platform = system_info['platform']

        terminal_list = cls.TERMINAL_EMULATORS.get(platform, [])

        for terminal in terminal_list:
            path = cls._find_command_path(terminal)
            if path:
                logger.debug(f"Found terminal emulator: {terminal} at {path}")
                return path

        logger.warning("No terminal emulator found")
        return None

    @classmethod
    def find_text_editor(cls) -> Optional[str]:
        """
        Find an available text editor.

        Returns:
            Path to text editor or None
        """
        system_info = cls._get_system_info()
        platform = system_info['platform']

        editor_list = cls.TEXT_EDITORS.get(platform, [])

        for editor in editor_list:
            path = cls._find_command_path(editor)
            if path:
                logger.debug(f"Found text editor: {editor} at {path}")
                return path

        logger.warning("No text editor found")
        return None

    @classmethod
    def validate_runtime_environment(cls) -> Dict[str, Any]:
        """
        Validate the runtime environment for security and functionality.

        Returns:
            Dictionary with validation results
        """
        results: Dict[str, Any] = {
            'valid': True,
            'warnings': [],
            'errors': [],
            'essential_commands': {},
            'optional_commands': {},
            'system_info': cls._get_system_info()
        }

        # Check essential commands
        for cmd_name, cmd_info in cls.ESSENTIAL_COMMANDS.items():
            path = cls._find_command_path(cmd_name)
            if path:
                results['essential_commands'][cmd_name] = {
                    'path': path,
                    'available': True,
                    'description': cmd_info['description']
                }
            else:
                results['essential_commands'][cmd_name] = {
                    'path': None,
                    'available': False,
                    'description': cmd_info['description']
                }

                if cmd_info['required']:
                    results['valid'] = False
                    results['errors'].append(f"Required command '{cmd_name}' not found")
                else:
                    results['warnings'].append(f"Optional command '{cmd_name}' not found")

        # Check optional commands
        for cmd_name, cmd_info in cls.OPTIONAL_COMMANDS.items():
            path = cls._find_command_path(cmd_name)
            results['optional_commands'][cmd_name] = {
                'path': path,
                'available': path is not None,
                'description': cmd_info['description']
            }

        # Check system paths
        safe_paths = [p for p in results['system_info']['paths'] if cls._is_safe_directory(p)]
        if len(safe_paths) < len(results['system_info']['paths']):
            results['warnings'].append("Some PATH directories were excluded for security reasons")

        # Platform-specific checks
        platform = results['system_info']['platform']
        if platform not in ['linux', 'darwin', 'windows']:
            results['warnings'].append(f"Unsupported platform: {platform}")

        return results

    @classmethod
    def get_command_alternatives(cls, command: str) -> List[str]:
        """
        Get alternative commands for a given command.

        Args:
            command: Command to find alternatives for

        Returns:
            List of alternative command names
        """
        # Check in essential commands
        if command in cls.ESSENTIAL_COMMANDS:
            return cls.ESSENTIAL_COMMANDS[command]['alternatives']

        # Check in optional commands
        if command in cls.OPTIONAL_COMMANDS:
            return cls.OPTIONAL_COMMANDS[command]['alternatives']

        return []

    @classmethod
    def resolve_command(cls, command: str, allow_alternatives: bool = True) -> Optional[str]:
        """
        Resolve a command to its full path, trying alternatives if needed.

        Args:
            command: Command name to resolve
            allow_alternatives: Whether to try alternative commands

        Returns:
            Full path to command or None
        """
        # Try the primary command first
        path = cls._find_command_path(command)
        if path:
            return path

        # Try alternatives if allowed
        if allow_alternatives:
            alternatives = cls.get_command_alternatives(command)
            for alt_cmd in alternatives:
                alt_path = cls._find_command_path(alt_cmd)
                if alt_path:
                    logger.info(f"Using alternative command {alt_cmd} for {command}")
                    return alt_path

        return None

    @classmethod
    def popen(
        cls,
        cmd: Union[List[str], str],
        **kwargs: Any
    ) -> subprocess.Popen[str]:
        """
        Create a Popen instance securely.

        Args:
            cmd: Command to run
            **kwargs: Arguments for subprocess.Popen

        Returns:
            Popen instance
        """
        # Convert string to list if needed
        if isinstance(cmd, str):
            cmd = shlex.split(cmd)

        # Validate command
        cls.validate_command(cmd)

        # Never use shell=True
        if 'shell' in kwargs:
            del kwargs['shell']

        logger.debug(f"Creating Popen for: {' '.join(cmd)}")

        return subprocess.Popen(cmd, **kwargs)

    @classmethod
    def open_url_securely(
        cls,
        url: str,
        sandbox: bool = True,
        timeout: int = 10
    ) -> bool:
        """
        Open a URL in the default browser with security validation and sandboxing.

        Args:
            url: URL to open
            sandbox: Whether to use sandboxing
            timeout: Command timeout

        Returns:
            True if successful, False otherwise

        Raises:
            ValueError: If URL is invalid
        """
        from ..utils.validators import validate_url_enhanced
        
        # Validate URL
        if not validate_url_enhanced(url, require_https=True, allow_private=False):
            raise ValueError(f"Invalid or unsafe URL: {url}")
        
        # Log the action
        log_security_event(
            "OPEN_URL",
            {"url": url, "sandboxed": sandbox},
            severity="info"
        )
        
        # Find the appropriate command for opening URLs
        xdg_open = cls._find_command_path('xdg-open')
        if not xdg_open:
            logger.warning("xdg-open not found, falling back to webbrowser module")
            try:
                import webbrowser
                return webbrowser.open(url)
            except Exception as e:
                logger.error(f"Failed to open URL with webbrowser: {e}")
                return False
        
        # Build command
        cmd = [xdg_open, url]
        
        try:
            # Open URL in sandboxed browser
            if sandbox and cls.check_command_exists('bwrap'):
                # Create custom file access profile
                from .sandbox_profiles import FileAccessProfile, SandboxLevel
                profile = FileAccessProfile(
                    level=SandboxLevel.STRICT,
                    allowed_paths=[url]
                )
                
                from .sandbox_profiles import SandboxManager
                sandboxed_cmd = SandboxManager.get_sandbox_command(
                    cmd,
                    profile,
                    sandbox='bwrap',
                    allow_network=True  # Browser needs network
                )
                
                result = subprocess.run(
                    sandboxed_cmd,
                    timeout=timeout,
                    capture_output=True,
                    check=False
                )
            else:
                result = cls.run(cmd, timeout=timeout, capture_output=True, check=False)
                
            return result.returncode == 0
        except Exception as e:
            logger.error(f"Failed to open URL: {e}")
            return False

    @classmethod
    def open_file_securely(
        cls,
        filepath: str,
        sandbox: bool = True,
        timeout: int = 10
    ) -> bool:
        """
        Open a file with the default application using security validation and sandboxing.

        Args:
            filepath: Path to file to open
            sandbox: Whether to use sandboxing
            timeout: Command timeout

        Returns:
            True if successful, False otherwise

        Raises:
            ValueError: If file path is invalid
        """
        from ..utils.validators import validate_file_path_enhanced
        
        # Validate file path
        if not validate_file_path_enhanced(filepath, must_exist=True):
            raise ValueError(f"Invalid or unsafe file path: {filepath}")
        
        # Log the action
        log_security_event(
            "OPEN_FILE",
            {"filepath": filepath, "sandboxed": sandbox},
            severity="info"
        )
        
        # Find the appropriate command for opening files
        xdg_open = cls._find_command_path('xdg-open')
        if not xdg_open:
            logger.warning("xdg-open not found, cannot open file")
            return False
        
        # Build command
        cmd = [xdg_open, filepath]
        
        try:
            # Run the command with advanced sandboxing
            if sandbox and cls.check_command_exists('bwrap'):
                # Create custom file access profile
                from .sandbox_profiles import FileAccessProfile, SandboxLevel
                profile = FileAccessProfile(
                    level=SandboxLevel.STRICT,
                    allowed_paths=[filepath]
                )
                
                from .sandbox_profiles import SandboxManager
                sandboxed_cmd = SandboxManager.get_sandbox_command(cmd, profile, 'bwrap')
                
                result = subprocess.run(
                    sandboxed_cmd,
                    timeout=timeout,
                    capture_output=True,
                    check=False
                )
            else:
                result = cls.run(cmd, timeout=timeout, capture_output=True, check=False)
                
            return result.returncode == 0
        except Exception as e:
            logger.error(f"Failed to open file: {e}")
            return False
