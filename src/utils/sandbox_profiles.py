"""
Advanced sandboxing profiles for different security contexts.
"""

# SPDX-License-Identifier: GPL-3.0-or-later

from typing import List, Dict, Any, Optional
from enum import IntEnum
import os

from .logger import get_logger

logger = get_logger(__name__)


class SandboxLevel(IntEnum):
    """Security levels for sandboxing."""
    NONE = 0
    BASIC = 1
    STANDARD = 2
    STRICT = 3
    PARANOID = 4


class SandboxProfile:
    """Base class for sandbox profiles."""
    
    def __init__(self, name: str, level: SandboxLevel = SandboxLevel.STANDARD):
        """Initialize a sandbox profile."""
        self.name = name
        self.level = level
        self.bwrap_args: List[str] = []
    
    def get_bwrap_args(self) -> List[str]:
        """Get bubblewrap arguments for this profile."""
        return self.bwrap_args.copy()


class NetworkProfile(SandboxProfile):
    """Sandbox profile for network operations."""
    
    def __init__(self, level: SandboxLevel = SandboxLevel.STANDARD):
        super().__init__("network", level)
        
        if level == SandboxLevel.BASIC:
            # Basic network isolation
            self.bwrap_args = [
                '--share-net',
                '--ro-bind', '/etc/resolv.conf', '/etc/resolv.conf',
                '--ro-bind', '/etc/hosts', '/etc/hosts',
            ]
        elif level == SandboxLevel.STANDARD:
            # Standard network isolation with more restrictions
            self.bwrap_args = [
                '--share-net',
                '--ro-bind', '/etc/resolv.conf', '/etc/resolv.conf',
                '--ro-bind', '/etc/hosts', '/etc/hosts',
                '--ro-bind', '/etc/ssl', '/etc/ssl',
                '--ro-bind', '/etc/ca-certificates', '/etc/ca-certificates',
            ]
        else:  # STRICT
            # No network access
            self.bwrap_args = [
                '--unshare-net',
            ]


class FileAccessProfile(SandboxProfile):
    """Sandbox profile for file access operations."""
    
    def __init__(self, level: SandboxLevel = SandboxLevel.STANDARD, 
                 allowed_paths: Optional[List[str]] = None):
        super().__init__("file_access", level)
        self.allowed_paths = allowed_paths or []
        
        if level == SandboxLevel.BASIC:
            # Basic file isolation
            self.bwrap_args = [
                '--ro-bind', '/usr', '/usr',
                '--ro-bind', '/lib', '/lib',
                '--ro-bind', '/lib64', '/lib64',
                '--proc', '/proc',
                '--dev', '/dev',
            ]
            # Add whitelisted paths
            for path in self.allowed_paths:
                self.bwrap_args.extend(['--ro-bind', path, path])
        
        elif level == SandboxLevel.STANDARD:
            # Standard file isolation
            self.bwrap_args = [
                '--ro-bind', '/usr', '/usr',
                '--ro-bind', '/lib', '/lib',
                '--ro-bind', '/lib64', '/lib64',
                '--ro-bind', '/bin', '/bin',
                '--ro-bind', '/sbin', '/sbin',
                '--proc', '/proc',
                '--dev', '/dev',
                '--tmpfs', '/tmp',
            ]
            for path in self.allowed_paths:
                self.bwrap_args.extend(['--ro-bind', path, path])
        
        else:  # STRICT
            # Strict file isolation
            self.bwrap_args = [
                '--ro-bind', '/usr', '/usr',
                '--ro-bind', '/lib', '/lib',
                '--ro-bind', '/lib64', '/lib64',
                '--tmpfs', '/tmp',
                '--tmpfs', '/var',
                '--tmpfs', '/home',
                '--proc', '/proc',
                '--dev', '/dev',
            ]
            for path in self.allowed_paths:
                self.bwrap_args.extend(['--ro-bind', path, path])


class PackageManagerProfile(SandboxProfile):
    """Sandbox profile for package manager operations."""
    
    def __init__(self, level: SandboxLevel = SandboxLevel.BASIC):
        super().__init__("package_manager", level)
        
        # Package managers need more access, so sandboxing is limited
        if level == SandboxLevel.BASIC:
            # Basic isolation for package queries
            self.bwrap_args = [
                '--ro-bind', '/usr', '/usr',
                '--ro-bind', '/etc', '/etc',
                '--ro-bind', '/var/lib/pacman', '/var/lib/pacman',
                '--ro-bind', '/var/cache/pacman', '/var/cache/pacman',
                '--proc', '/proc',
                '--dev', '/dev',
                '--tmpfs', '/tmp',
            ]
            
        elif level in [SandboxLevel.STANDARD, SandboxLevel.STRICT]:
            # More restrictive for read-only operations
            self.bwrap_args = [
                '--unshare-pid',
                '--ro-bind', '/usr', '/usr',
                '--ro-bind', '/etc', '/etc',
                '--ro-bind', '/var/lib/pacman', '/var/lib/pacman',
                '--ro-bind', '/var/cache/pacman/pkg', '/var/cache/pacman/pkg',
                '--proc', '/proc',
                '--dev', '/dev',
                '--tmpfs', '/tmp',
                '--new-session',
            ]


class TerminalProfile(SandboxProfile):
    """Sandbox profile for terminal operations."""
    
    def __init__(self, level: SandboxLevel = SandboxLevel.BASIC):
        super().__init__("terminal", level)
        
        if level == SandboxLevel.BASIC:
            # Basic terminal isolation
            self.bwrap_args = [
                '--share-net',
                '--ro-bind', '/etc', '/etc',
                '--ro-bind', '/usr', '/usr',
                '--ro-bind', '/lib', '/lib',
                '--ro-bind', '/lib64', '/lib64',
                '--ro-bind', '/bin', '/bin',
                '--proc', '/proc',
                '--dev', '/dev',
                '--bind', os.path.expanduser('~'), os.path.expanduser('~'),
            ]
        
        elif level == SandboxLevel.STANDARD:
            # Standard terminal isolation
            self.bwrap_args = [
                '--share-net',
                '--ro-bind', '/etc', '/etc',
                '--ro-bind', '/usr', '/usr',
                '--ro-bind', '/lib', '/lib',
                '--ro-bind', '/lib64', '/lib64',
                '--ro-bind', '/bin', '/bin',
                '--proc', '/proc',
                '--dev', '/dev',
                '--tmpfs', '/tmp',
                '--bind', os.path.expanduser('~'), os.path.expanduser('~'),
            ]


class SandboxManager:
    """Manages sandbox profiles and profile selection."""
    
    # Default profiles for different operations
    DEFAULT_PROFILES: Dict[str, SandboxProfile] = {
        'url_open': NetworkProfile(SandboxLevel.STANDARD),
        'file_open': FileAccessProfile(SandboxLevel.STANDARD),
        'package_query': PackageManagerProfile(SandboxLevel.BASIC),
        'package_update': PackageManagerProfile(SandboxLevel.NONE),  # Can't sandbox actual updates
        'generic': SandboxProfile("generic", SandboxLevel.BASIC),
    }
    
    @classmethod
    def get_profile(cls, operation: str, custom_level: Optional[SandboxLevel] = None) -> SandboxProfile:
        """
        Get appropriate sandbox profile for an operation.
        
        Args:
            operation: Type of operation
            custom_level: Override default security level
            
        Returns:
            Sandbox profile
        """
        if operation in cls.DEFAULT_PROFILES:
            profile = cls.DEFAULT_PROFILES[operation]
            
            # Create new profile with custom level if requested
            if custom_level and custom_level != profile.level:
                profile_class = type(profile)
                return profile_class(profile.name, custom_level)
            
            return profile
        else:
            # Return generic profile for unknown operations
            logger.debug(f"No specific profile for operation '{operation}', using generic")
            return cls.DEFAULT_PROFILES['generic']
    
    @classmethod
    def get_sandbox_command(cls, base_cmd: List[str], profile: SandboxProfile,
                           sandbox_type: str = "bwrap", allow_network: bool = False) -> List[str]:
        """
        Wrap a command with appropriate sandbox.
        
        Args:
            base_cmd: Original command
            profile: Sandbox profile to use
            sandbox_type: Type of sandbox (bwrap)
            allow_network: Override to allow network access
            
        Returns:
            Sandboxed command
        """
        if profile.level == SandboxLevel.NONE:
            return base_cmd
        
        if sandbox_type == "bwrap":
            sandbox_cmd = ['bwrap'] + profile.get_bwrap_args()
            
            # Add network access if requested
            if allow_network and '--unshare-net' in sandbox_cmd:
                sandbox_cmd.remove('--unshare-net')
                sandbox_cmd.extend(['--share-net'])
            
            sandbox_cmd.extend(base_cmd)
        else:
            logger.warning(f"Unknown sandbox type: {sandbox_type}")
            return base_cmd
        
        return sandbox_cmd
    
    @classmethod
    def create_custom_profile(cls, name: str, level: SandboxLevel,
                            network: bool = False,
                            filesystem: Optional[List[str]] = None,
                            capabilities: Optional[List[str]] = None) -> SandboxProfile:
        """
        Create a custom sandbox profile.
        
        Args:
            name: Profile name
            level: Security level
            network: Allow network access
            filesystem: List of allowed filesystem paths
            capabilities: List of allowed capabilities
            
        Returns:
            Custom sandbox profile
        """
        profile = SandboxProfile(name, level)
        
        # Build bubblewrap arguments
        bwrap_args = []
        
        if not network:
            bwrap_args.append('--unshare-net')
        else:
            bwrap_args.extend(['--share-net'])
        
        if level >= SandboxLevel.STANDARD:
            bwrap_args.extend([
                '--ro-bind', '/usr', '/usr',
                '--ro-bind', '/lib', '/lib',
                '--ro-bind', '/lib64', '/lib64',
                '--proc', '/proc',
                '--dev', '/dev',
            ])
        
        if level >= SandboxLevel.STRICT:
            bwrap_args.extend([
                '--tmpfs', '/tmp',
                '--tmpfs', '/var',
                '--tmpfs', '/home',
            ])
        
        # Add filesystem whitelist
        if filesystem:
            for path in filesystem:
                bwrap_args.extend(['--ro-bind', path, path])
        
        profile.bwrap_args = bwrap_args
        
        return profile 