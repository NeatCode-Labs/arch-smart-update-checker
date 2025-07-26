"""
Advanced sandboxing profiles for different security contexts.
"""

# SPDX-License-Identifier: GPL-3.0-or-later

from typing import List, Dict, Any, Optional
from enum import Enum
import os

from .logger import get_logger

logger = get_logger(__name__)


class SandboxLevel(Enum):
    """Security levels for sandboxing."""
    NONE = "none"
    BASIC = "basic"
    STANDARD = "standard"
    STRICT = "strict"
    PARANOID = "paranoid"


class SandboxProfile:
    """Base class for sandbox profiles."""
    
    def __init__(self, name: str, level: SandboxLevel):
        self.name = name
        self.level = level
        self.firejail_args: List[str] = []
        self.bwrap_args: List[str] = []
    
    def get_firejail_args(self) -> List[str]:
        """Get Firejail arguments for this profile."""
        return self.firejail_args.copy()
    
    def get_bwrap_args(self) -> List[str]:
        """Get bubblewrap arguments for this profile."""
        return self.bwrap_args.copy()


class NetworkProfile(SandboxProfile):
    """Sandbox profile for network operations."""
    
    def __init__(self, level: SandboxLevel = SandboxLevel.STANDARD):
        super().__init__("network", level)
        
        if level == SandboxLevel.BASIC:
            # Basic network isolation
            self.firejail_args = [
                '--noprofile',
                '--private-tmp',
                '--nosound',
            ]
            self.bwrap_args = [
                '--unshare-pid',
                '--proc', '/proc',
                '--dev', '/dev',
                '--tmpfs', '/tmp',
            ]
            
        elif level == SandboxLevel.STANDARD:
            # Standard network isolation
            self.firejail_args = [
                '--noprofile',
                '--private-tmp',
                '--nosound',
                '--nogroups',
                '--nonewprivs',
                '--seccomp',
                '--caps.drop=all',
                '--protocol=unix,inet,inet6',
            ]
            self.bwrap_args = [
                '--unshare-all',
                '--share-net',
                '--proc', '/proc',
                '--dev', '/dev',
                '--tmpfs', '/tmp',
                '--new-session',
            ]
            
        elif level == SandboxLevel.STRICT:
            # Strict network isolation
            self.firejail_args = [
                '--noprofile',
                '--private',
                '--private-tmp',
                '--private-dev',
                '--nosound',
                '--nogroups',
                '--nonewprivs',
                '--seccomp.drop=@clock,@cpu-emulation,@debug,@module,@mount,@obsolete,@raw-io,@reboot,@resources,@swap',
                '--caps.drop=all',
                '--protocol=inet,inet6',
                '--nodbus',
                '--machine-id',
            ]
            self.bwrap_args = [
                '--unshare-all',
                '--share-net',
                '--proc', '/proc',
                '--dev', '/dev',
                '--tmpfs', '/tmp',
                '--tmpfs', '/var',
                '--tmpfs', '/home',
                '--new-session',
                '--die-with-parent',
            ]


class FileAccessProfile(SandboxProfile):
    """Sandbox profile for file access operations."""
    
    def __init__(self, level: SandboxLevel = SandboxLevel.STANDARD, 
                 allowed_paths: Optional[List[str]] = None):
        super().__init__("file_access", level)
        self.allowed_paths = allowed_paths or []
        
        if level == SandboxLevel.BASIC:
            # Basic file isolation
            self.firejail_args = [
                '--noprofile',
                '--net=none',
                '--nosound',
            ]
            # Add whitelisted paths
            for path in self.allowed_paths:
                self.firejail_args.extend(['--whitelist=' + path])
            
            self.bwrap_args = [
                '--unshare-pid',
                '--proc', '/proc',
                '--dev', '/dev',
            ]
            # Add read-only bind mounts for allowed paths
            for path in self.allowed_paths:
                self.bwrap_args.extend(['--ro-bind', path, path])
                
        elif level == SandboxLevel.STANDARD:
            # Standard file isolation
            self.firejail_args = [
                '--noprofile',
                '--net=none',
                '--nosound',
                '--nogroups',
                '--nonewprivs',
                '--seccomp',
                '--caps.drop=all',
                '--nodbus',
            ]
            for path in self.allowed_paths:
                self.firejail_args.extend(['--whitelist=' + path])
            
            self.bwrap_args = [
                '--unshare-all',
                '--proc', '/proc',
                '--dev', '/dev',
                '--tmpfs', '/tmp',
            ]
            for path in self.allowed_paths:
                self.bwrap_args.extend(['--ro-bind', path, path])
                
        elif level == SandboxLevel.STRICT:
            # Strict file isolation
            self.firejail_args = [
                '--noprofile',
                '--net=none',
                '--private',
                '--private-tmp',
                '--private-dev',
                '--nosound',
                '--nogroups',
                '--nonewprivs',
                '--seccomp.drop=@clock,@cpu-emulation,@debug,@module,@mount,@obsolete,@raw-io,@reboot,@resources,@swap',
                '--caps.drop=all',
                '--nodbus',
                '--machine-id',
                '--noroot',
            ]
            for path in self.allowed_paths:
                self.firejail_args.extend(['--whitelist=' + path])
            
            self.bwrap_args = [
                '--unshare-all',
                '--proc', '/proc',
                '--dev', '/dev',
                '--tmpfs', '/tmp',
                '--tmpfs', '/var',
                '--tmpfs', '/home',
                '--new-session',
                '--die-with-parent',
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
            self.firejail_args = [
                '--noprofile',
                '--nosound',
                '--nogroups',
                '--nonewprivs',
            ]
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
            self.firejail_args = [
                '--noprofile',
                '--nosound',
                '--nogroups',
                '--nonewprivs',
                '--seccomp',
                '--caps.drop=all',
                '--read-only=/var/lib/pacman',
            ]
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
                return profile_class(custom_level)
            
            return profile
        else:
            # Return generic profile for unknown operations
            logger.debug(f"No specific profile for operation '{operation}', using generic")
            return cls.DEFAULT_PROFILES['generic']
    
    @classmethod
    def get_sandbox_command(cls, base_cmd: List[str], profile: SandboxProfile,
                           sandbox_type: str = "firejail") -> List[str]:
        """
        Wrap a command with appropriate sandbox.
        
        Args:
            base_cmd: Original command
            profile: Sandbox profile to use
            sandbox_type: Type of sandbox (firejail or bwrap)
            
        Returns:
            Sandboxed command
        """
        if profile.level == SandboxLevel.NONE:
            return base_cmd
        
        if sandbox_type == "firejail":
            sandbox_cmd = ['firejail'] + profile.get_firejail_args() + ['--'] + base_cmd
        elif sandbox_type == "bwrap":
            sandbox_cmd = ['bwrap'] + profile.get_bwrap_args() + base_cmd
        else:
            logger.warning(f"Unknown sandbox type: {sandbox_type}")
            return base_cmd
        
        return sandbox_cmd
    
    @classmethod
    def create_custom_profile(cls, name: str, level: SandboxLevel,
                            network: bool = False,
                            filesystem: List[str] = None,
                            capabilities: List[str] = None) -> SandboxProfile:
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
        
        # Build Firejail arguments
        firejail_args = ['--noprofile']
        
        if not network:
            firejail_args.append('--net=none')
        
        if level >= SandboxLevel.STANDARD:
            firejail_args.extend([
                '--nosound',
                '--nogroups', 
                '--nonewprivs',
                '--seccomp',
            ])
        
        if level >= SandboxLevel.STRICT:
            firejail_args.extend([
                '--private',
                '--private-tmp',
                '--private-dev',
                '--nodbus',
                '--machine-id',
            ])
        
        # Add filesystem whitelist
        if filesystem:
            for path in filesystem:
                firejail_args.append(f'--whitelist={path}')
        
        # Handle capabilities
        if not capabilities:
            firejail_args.append('--caps.drop=all')
        else:
            dropped_caps = set([
                'cap_sys_admin', 'cap_sys_boot', 'cap_sys_module',
                'cap_sys_rawio', 'cap_sys_ptrace', 'cap_sys_pacct'
            ]) - set(capabilities)
            for cap in dropped_caps:
                firejail_args.append(f'--caps.drop={cap}')
        
        profile.firejail_args = firejail_args
        
        # Build bubblewrap arguments
        bwrap_args = []
        
        if level >= SandboxLevel.STANDARD:
            bwrap_args.extend([
                '--unshare-pid',
                '--proc', '/proc',
                '--dev', '/dev',
            ])
        
        if level >= SandboxLevel.STRICT:
            bwrap_args.extend([
                '--unshare-all',
                '--new-session',
                '--die-with-parent',
            ])
        
        if network:
            bwrap_args.append('--share-net')
        
        # Add filesystem binds
        if filesystem:
            for path in filesystem:
                if os.path.exists(path):
                    bwrap_args.extend(['--ro-bind', path, path])
        
        profile.bwrap_args = bwrap_args
        
        return profile 