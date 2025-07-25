"""
Secure memory management utilities for handling sensitive data.
"""

# SPDX-License-Identifier: GPL-3.0-or-later

import gc
import sys
import ctypes
import platform
import mmap
import os
import threading
import secrets
import hashlib
from typing import Any, Optional, List, Dict, Union
import logging

from .logger import get_logger

logger = get_logger(__name__)


class PlatformMemoryManager:
    """Platform-specific memory management operations."""
    
    @staticmethod
    def get_platform_info() -> Dict[str, str]:
        """Get platform information for security decisions."""
        return {
            'system': platform.system(),
            'architecture': platform.architecture()[0],
            'python_version': platform.python_version(),
            'processor': platform.processor()
        }
    
    @staticmethod
    def secure_zero_memory(address: int, size: int) -> bool:
        """
        Platform-specific secure memory zeroing.
        
        Args:
            address: Memory address to zero
            size: Number of bytes to zero
            
        Returns:
            True if successful, False otherwise
        """
        try:
            if platform.system() == "Windows":
                # Use RtlSecureZeroMemory on Windows
                try:
                    kernel32 = ctypes.windll.kernel32
                    RtlSecureZeroMemory = kernel32.RtlSecureZeroMemory
                    RtlSecureZeroMemory.argtypes = [ctypes.c_void_p, ctypes.c_size_t]
                    RtlSecureZeroMemory(address, size)
                    return True
                except Exception:
                    # Fallback to explicit_bzero if available
                    return PlatformMemoryManager._fallback_zero_memory(address, size)
            
            elif platform.system() in ["Linux", "Darwin"]:
                # Try explicit_bzero on Unix-like systems
                try:
                    libc = ctypes.CDLL("libc.so.6" if platform.system() == "Linux" else "libc.dylib")
                    if hasattr(libc, 'explicit_bzero'):
                        explicit_bzero = libc.explicit_bzero
                        explicit_bzero.argtypes = [ctypes.c_void_p, ctypes.c_size_t]
                        explicit_bzero(address, size)
                        return True
                except Exception:
                    pass
                
                # Fallback to multiple overwrites
                return PlatformMemoryManager._fallback_zero_memory(address, size)
            
            else:
                # Unknown platform, use fallback
                return PlatformMemoryManager._fallback_zero_memory(address, size)
                
        except Exception as e:
            logger.error(f"Error in secure memory zeroing: {e}")
            return False
    
    @staticmethod
    def _fallback_zero_memory(address: int, size: int) -> bool:
        """
        Fallback memory zeroing using multiple overwrites.
        
        Args:
            address: Memory address to zero
            size: Number of bytes to zero
            
        Returns:
            True if successful
        """
        try:
            # Multiple pass overwrite with different patterns
            patterns = [b'\x00', b'\xFF', b'\xAA', b'\x55', b'\x00']
            
            for pattern in patterns:
                ctypes.memmove(address, pattern * size, size)
                
            return True
        except Exception as e:
            logger.error(f"Error in fallback memory zeroing: {e}")
            return False
    
    @staticmethod
    def lock_memory_pages(address: int, size: int) -> bool:
        """
        Lock memory pages to prevent swapping (platform-specific).
        
        Args:
            address: Memory address to lock
            size: Number of bytes to lock
            
        Returns:
            True if successful
        """
        try:
            if platform.system() == "Windows":
                kernel32 = ctypes.windll.kernel32
                VirtualLock = kernel32.VirtualLock
                VirtualLock.argtypes = [ctypes.c_void_p, ctypes.c_size_t]
                VirtualLock.restype = ctypes.c_bool
                return bool(VirtualLock(address, size))
            
            elif platform.system() in ["Linux", "Darwin"]:
                libc = ctypes.CDLL("libc.so.6" if platform.system() == "Linux" else "libc.dylib")
                mlock = libc.mlock
                mlock.argtypes = [ctypes.c_void_p, ctypes.c_size_t]
                mlock.restype = ctypes.c_int
                return mlock(address, size) == 0
            
            return False
            
        except Exception as e:
            logger.debug(f"Memory locking not available: {e}")
            return False
    
    @staticmethod
    def unlock_memory_pages(address: int, size: int) -> bool:
        """
        Unlock memory pages (platform-specific).
        
        Args:
            address: Memory address to unlock
            size: Number of bytes to unlock
            
        Returns:
            True if successful
        """
        try:
            if platform.system() == "Windows":
                kernel32 = ctypes.windll.kernel32
                VirtualUnlock = kernel32.VirtualUnlock
                VirtualUnlock.argtypes = [ctypes.c_void_p, ctypes.c_size_t]
                VirtualUnlock.restype = ctypes.c_bool
                return bool(VirtualUnlock(address, size))
            
            elif platform.system() in ["Linux", "Darwin"]:
                libc = ctypes.CDLL("libc.so.6" if platform.system() == "Linux" else "libc.dylib")
                munlock = libc.munlock
                munlock.argtypes = [ctypes.c_void_p, ctypes.c_size_t]
                munlock.restype = ctypes.c_int
                return munlock(address, size) == 0
            
            return False
            
        except Exception as e:
            logger.debug(f"Memory unlocking not available: {e}")
            return False


class SecureString:
    """A string-like object that clears its content from memory when destroyed."""
    
    def __init__(self, value: str = ""):
        """Initialize with a string value."""
        if not isinstance(value, str):
            value = str(value)
        self._value = value
        self._cleared = False
        self._locked = False
        self._memory_address = None
        self._memory_size = 0
        
        # Try to lock memory if the value contains sensitive data
        self._attempt_memory_lock()
    
    def _attempt_memory_lock(self):
        """Attempt to lock the memory containing sensitive data."""
        try:
            # Get memory address and size of the string object
            self._memory_address = id(self._value)
            self._memory_size = sys.getsizeof(self._value)
            
            # Attempt to lock memory pages
            if PlatformMemoryManager.lock_memory_pages(self._memory_address, self._memory_size):
                self._locked = True
                logger.debug(f"Locked {self._memory_size} bytes of secure string memory")
            else:
                logger.debug("Memory locking not available for secure string")
                
        except Exception as e:
            logger.debug(f"Could not lock secure string memory: {e}")
    
    def __str__(self) -> str:
        """Return the string value."""
        if self._cleared:
            return "[CLEARED]"
        return self._value
    
    def __repr__(self) -> str:
        """Return string representation."""
        if self._cleared:
            return "SecureString([CLEARED])"
        return f"SecureString({repr(self._value)})"
    
    def __len__(self) -> int:
        """Return length of string."""
        if self._cleared:
            return 0
        return len(self._value)
    
    def __bool__(self) -> bool:
        """Return True if string is not empty and not cleared."""
        return not self._cleared and bool(self._value)
    
    def get(self) -> str:
        """Get the string value."""
        if self._cleared:
            return ""
        return self._value
    
    def clear(self):
        """Clear the string value from memory using platform-specific secure methods."""
        if not self._cleared and self._value:
            # Overwrite the string multiple times using platform-specific methods
            try:
                # Use platform-specific secure memory zeroing
                if self._memory_address and self._memory_size:
                    success = PlatformMemoryManager.secure_zero_memory(
                        self._memory_address, self._memory_size
                    )
                    
                    if success:
                        logger.debug("Securely cleared string memory using platform-specific methods")
                    else:
                        # Fallback to standard clearing
                        self._fallback_clear()
                else:
                    self._fallback_clear()
                
                # Unlock memory if it was locked
                if self._locked and self._memory_address and self._memory_size:
                    PlatformMemoryManager.unlock_memory_pages(
                        self._memory_address, self._memory_size
                    )
                    self._locked = False
                
            except Exception as e:
                logger.debug(f"Could not securely clear string: {e}")
                self._fallback_clear()
            finally:
                self._value = ""
                self._cleared = True
                # Force garbage collection to increase chances of memory cleanup
                gc.collect()
    
    def _fallback_clear(self):
        """Fallback clearing method for when platform-specific methods fail."""
        try:
            # Get the string object's memory location
            string_obj = self._value
            
            # Try to overwrite memory (this is best-effort in Python)
            if hasattr(string_obj, '__len__') and len(string_obj) > 0:
                # Create multiple overwrite patterns
                patterns = ['\x00', '\xFF', '\xAA', '\x55', '\x00']
                
                for pattern in patterns:
                    self._value = pattern * len(string_obj)
                    
        except Exception as e:
            logger.debug(f"Fallback string clearing failed: {e}")
    
    def __del__(self):
        """Destructor - clear memory when object is destroyed."""
        self.clear()


class SecureList:
    """A list-like object that clears its content from memory when destroyed."""
    
    def __init__(self, items: List[Any] = None):
        """Initialize with list items."""
        self._items = items or []
        self._cleared = False
    
    def __iter__(self):
        """Iterate over items."""
        if self._cleared:
            return iter([])
        return iter(self._items)
    
    def __len__(self) -> int:
        """Return length of list."""
        if self._cleared:
            return 0
        return len(self._items)
    
    def __getitem__(self, index):
        """Get item by index."""
        if self._cleared:
            raise IndexError("List has been cleared")
        return self._items[index]
    
    def append(self, item):
        """Add item to list."""
        if not self._cleared:
            self._items.append(item)
    
    def extend(self, items):
        """Extend list with items."""
        if not self._cleared:
            self._items.extend(items)
    
    def clear(self):
        """Clear the list from memory."""
        if not self._cleared and self._items:
            try:
                # Clear each item if it has a clear method
                for item in self._items:
                    if hasattr(item, 'clear') and callable(item.clear):
                        try:
                            item.clear()
                        except:
                            pass
                
                # Overwrite with empty values
                for i in range(len(self._items)):
                    self._items[i] = None
                
            except Exception:
                pass
            finally:
                self._items.clear()
                self._cleared = True
                gc.collect()
    
    def get_copy(self) -> List[Any]:
        """Get a copy of the list."""
        if self._cleared:
            return []
        return self._items.copy()
    
    def __del__(self):
        """Destructor - clear memory when object is destroyed."""
        self.clear()


class SecureDict:
    """A dict-like object that clears its content from memory when destroyed."""
    
    def __init__(self, data: Dict[str, Any] = None):
        """Initialize with dict data."""
        self._data = data or {}
        self._cleared = False
    
    def __getitem__(self, key):
        """Get item by key."""
        if self._cleared:
            raise KeyError("Dict has been cleared")
        return self._data[key]
    
    def __setitem__(self, key, value):
        """Set item by key."""
        if not self._cleared:
            self._data[key] = value
    
    def get(self, key, default=None):
        """Get item with default."""
        if self._cleared:
            return default
        return self._data.get(key, default)
    
    def keys(self):
        """Get keys."""
        if self._cleared:
            return []
        return self._data.keys()
    
    def values(self):
        """Get values."""
        if self._cleared:
            return []
        return self._data.values()
    
    def items(self):
        """Get items."""
        if self._cleared:
            return []
        return self._data.items()
    
    def clear(self):
        """Clear the dict from memory."""
        if not self._cleared and self._data:
            try:
                # Clear each value if it has a clear method
                for key, value in self._data.items():
                    if hasattr(value, 'clear') and callable(value.clear):
                        try:
                            value.clear()
                        except:
                            pass
                
                # Overwrite with None
                for key in list(self._data.keys()):
                    self._data[key] = None
                
            except Exception:
                pass
            finally:
                self._data.clear()
                self._cleared = True
                gc.collect()
    
    def get_copy(self) -> Dict[str, Any]:
        """Get a copy of the dict."""
        if self._cleared:
            return {}
        return self._data.copy()
    
    def __del__(self):
        """Destructor - clear memory when object is destroyed."""
        self.clear()


class MemoryManager:
    """Manages secure memory operations and cleanup."""
    
    @staticmethod
    def secure_delete_variable(var_name: str, local_vars: Dict[str, Any] = None, 
                              global_vars: Dict[str, Any] = None):
        """
        Securely delete a variable from memory.
        
        Args:
            var_name: Name of the variable to delete
            local_vars: Local variables dict (usually locals())
            global_vars: Global variables dict (usually globals())
        """
        try:
            # Clear from local scope
            if local_vars and var_name in local_vars:
                value = local_vars[var_name]
                if hasattr(value, 'clear') and callable(value.clear):
                    value.clear()
                local_vars[var_name] = None
                del local_vars[var_name]
            
            # Clear from global scope
            if global_vars and var_name in global_vars:
                value = global_vars[var_name]
                if hasattr(value, 'clear') and callable(value.clear):
                    value.clear()
                global_vars[var_name] = None
                del global_vars[var_name]
            
            # Force garbage collection
            gc.collect()
            
        except Exception as e:
            logger.debug(f"Error during secure variable deletion: {e}")
    
    @staticmethod
    def clear_sensitive_data(*objects):
        """
        Clear sensitive data from multiple objects.
        
        Args:
            *objects: Objects to clear (should have clear() method)
        """
        for obj in objects:
            try:
                if hasattr(obj, 'clear') and callable(obj.clear):
                    obj.clear()
                elif isinstance(obj, (list, dict, set)):
                    obj.clear()
            except Exception as e:
                logger.debug(f"Error clearing object: {e}")
        
        # Force garbage collection
        gc.collect()
    
    @staticmethod
    def overwrite_memory_region(data: Union[str, bytes], overwrite_value: int = 0):
        """
        Attempt to overwrite memory region (best effort in Python).
        
        Args:
            data: Data to overwrite
            overwrite_value: Value to overwrite with (0-255)
        """
        try:
            if isinstance(data, str):
                data = data.encode('utf-8')
            
            if isinstance(data, bytes) and len(data) > 0:
                # This is a best-effort attempt - Python's memory management
                # makes it difficult to guarantee memory overwriting
                try:
                    # Try to get memory address (CPython specific)
                    if hasattr(ctypes, 'string_at') and hasattr(ctypes, 'memmove'):
                        # Create buffer of zeros
                        buffer = ctypes.create_string_buffer(len(data))
                        # Fill with overwrite value
                        ctypes.memset(buffer, overwrite_value, len(data))
                        
                except Exception:
                    pass  # Memory overwriting might not work in all Python implementations
            
        except Exception as e:
            logger.debug(f"Memory overwrite attempt failed: {e}")
    
    @staticmethod
    def force_garbage_collection():
        """Force aggressive garbage collection to clear memory."""
        try:
            # Multiple GC passes to ensure cleanup
            for _ in range(3):
                gc.collect()
            
            # Try to compact memory if available
            if hasattr(gc, 'compact'):
                gc.compact()
                
        except Exception as e:
            logger.debug(f"Garbage collection error: {e}")


class SecureDataStore:
    """
    Secure data store for managing configuration and sensitive data with 
    platform-specific memory protection and encryption.
    """
    
    def __init__(self, encryption_key: Optional[bytes] = None):
        """
        Initialize secure data store.
        
        Args:
            encryption_key: Optional encryption key for data at rest
        """
        self._data: Dict[str, Any] = {}
        self._encrypted_data: Dict[str, bytes] = {}
        self._cleared = False
        self._lock = threading.RLock()
        
        # Generate or use provided encryption key
        self._encryption_key = encryption_key or secrets.token_bytes(32)
        
        # Track memory locations for secure cleanup
        self._memory_locations: List[Dict[str, Any]] = []
        
        logger.debug("Initialized secure data store with memory protection")
    
    def store(self, key: str, value: Any, encrypt: bool = False) -> bool:
        """
        Store data securely with optional encryption.
        
        Args:
            key: Data key
            value: Data value
            encrypt: Whether to encrypt the data
            
        Returns:
            True if stored successfully
        """
        with self._lock:
            if self._cleared:
                logger.warning("Attempt to store data in cleared secure store")
                return False
            
            try:
                if encrypt and isinstance(value, (str, bytes)):
                    # Encrypt sensitive data
                    encrypted_value = self._encrypt_data(value)
                    self._encrypted_data[key] = encrypted_value
                    
                    # Track memory location for cleanup
                    self._memory_locations.append({
                        'key': key,
                        'type': 'encrypted',
                        'address': id(encrypted_value),
                        'size': sys.getsizeof(encrypted_value)
                    })
                else:
                    # Store as secure object
                    if isinstance(value, str):
                        secure_value = SecureString(value)
                    elif isinstance(value, list):
                        secure_value = SecureList(value)
                    elif isinstance(value, dict):
                        secure_value = SecureDict(value)
                    else:
                        secure_value = value
                    
                    self._data[key] = secure_value
                    
                    # Track memory location
                    self._memory_locations.append({
                        'key': key,
                        'type': 'secure_object',
                        'address': id(secure_value),
                        'size': sys.getsizeof(secure_value)
                    })
                
                return True
                
            except Exception as e:
                logger.error(f"Error storing secure data: {e}")
                return False
    
    def retrieve(self, key: str, decrypt: bool = False) -> Optional[Any]:
        """
        Retrieve data from secure store.
        
        Args:
            key: Data key
            decrypt: Whether to decrypt encrypted data
            
        Returns:
            Retrieved data or None if not found
        """
        with self._lock:
            if self._cleared:
                return None
            
            try:
                # Check encrypted data first
                if key in self._encrypted_data:
                    if decrypt:
                        return self._decrypt_data(self._encrypted_data[key])
                    else:
                        return self._encrypted_data[key]
                
                # Check regular secure data
                return self._data.get(key)
                
            except Exception as e:
                logger.error(f"Error retrieving secure data: {e}")
                return None
    
    def _encrypt_data(self, data: Union[str, bytes]) -> bytes:
        """Encrypt data using AES encryption."""
        try:
            from cryptography.fernet import Fernet
            import base64
            
            # Create Fernet key from our encryption key
            key = base64.urlsafe_b64encode(self._encryption_key[:32])
            fernet = Fernet(key)
            
            if isinstance(data, str):
                data = data.encode('utf-8')
            
            return fernet.encrypt(data)
            
        except ImportError:
            # Fallback to simple XOR encryption if cryptography not available
            logger.warning("Cryptography library not available, using fallback encryption")
            return self._xor_encrypt(data)
    
    def _decrypt_data(self, encrypted_data: bytes) -> bytes:
        """Decrypt data using AES decryption."""
        try:
            from cryptography.fernet import Fernet
            import base64
            
            # Create Fernet key from our encryption key
            key = base64.urlsafe_b64encode(self._encryption_key[:32])
            fernet = Fernet(key)
            
            return fernet.decrypt(encrypted_data)
            
        except ImportError:
            # Fallback to simple XOR decryption
            return self._xor_decrypt(encrypted_data)
    
    def _xor_encrypt(self, data: Union[str, bytes]) -> bytes:
        """Simple XOR encryption fallback."""
        if isinstance(data, str):
            data = data.encode('utf-8')
        
        key_bytes = self._encryption_key
        return bytes(a ^ key_bytes[i % len(key_bytes)] for i, a in enumerate(data))
    
    def _xor_decrypt(self, encrypted_data: bytes) -> bytes:
        """Simple XOR decryption fallback."""
        return self._xor_encrypt(encrypted_data)  # XOR is symmetric
    
    def clear_all(self):
        """Clear all data from the secure store."""
        with self._lock:
            if self._cleared:
                return
            
            try:
                # Clear all secure objects
                for key, value in list(self._data.items()):
                    if hasattr(value, 'clear'):
                        value.clear()
                
                # Securely clear encrypted data
                for key, encrypted_value in list(self._encrypted_data.items()):
                    # Get memory location
                    addr = id(encrypted_value)
                    size = sys.getsizeof(encrypted_value)
                    
                    # Use platform-specific secure clearing
                    PlatformMemoryManager.secure_zero_memory(addr, size)
                
                # Clear all memory locations
                for location in self._memory_locations:
                    try:
                        PlatformMemoryManager.secure_zero_memory(
                            location['address'], location['size']
                        )
                    except Exception:
                        pass
                
                # Clear dictionaries
                self._data.clear()
                self._encrypted_data.clear()
                self._memory_locations.clear()
                
                # Clear encryption key
                if self._encryption_key:
                    addr = id(self._encryption_key)
                    size = sys.getsizeof(self._encryption_key)
                    PlatformMemoryManager.secure_zero_memory(addr, size)
                    self._encryption_key = None
                
                self._cleared = True
                
                # Force garbage collection
                gc.collect()
                
                logger.debug("Cleared all data from secure store")
                
            except Exception as e:
                logger.error(f"Error clearing secure store: {e}")
    
    def __del__(self):
        """Destructor to ensure cleanup."""
        try:
            self.clear_all()
        except Exception:
            pass


# Convenience functions
def create_secure_string(value: str = "") -> SecureString:
    """Create a secure string that clears itself from memory."""
    return SecureString(value)


def create_secure_list(items: List[Any] = None) -> SecureList:
    """Create a secure list that clears itself from memory."""
    return SecureList(items)


def create_secure_dict(data: Dict[str, Any] = None) -> SecureDict:
    """Create a secure dict that clears itself from memory."""
    return SecureDict(data)


def secure_clear(*objects):
    """Clear multiple objects from memory."""
    MemoryManager.clear_sensitive_data(*objects)


def force_memory_cleanup():
    """Force memory cleanup and garbage collection."""
    MemoryManager.force_garbage_collection() 