"""
Secure callback management for GUI components to prevent memory disclosure.
"""

# SPDX-License-Identifier: GPL-3.0-or-later

import weakref
import threading
from typing import Callable, Any, Optional, Dict, Set
import gc

# For Python 3.13+ compatibility - WeakSet moved from typing to weakref
try:
    from typing import WeakSet  # type: ignore[attr-defined]
except ImportError:
    from weakref import WeakSet

from ..utils.logger import get_logger

logger = get_logger(__name__)


class SecureCallbackManager:
    """Manages GUI callbacks with secure memory handling and automatic cleanup."""

    def __init__(self, component_name: str = "unknown"):
        """
        Initialize secure callback manager.

        Args:
            component_name: Name of the component for debugging
        """
        self.component_name = component_name
        self._callbacks: WeakSet = weakref.WeakSet()
        self._sensitive_refs: Set[weakref.ref] = set()
        self._cleanup_callbacks: Set[Callable] = set()
        self._lock = threading.RLock()
        self._is_destroyed = False

        logger.debug(f"Initialized secure callback manager for {component_name}")

    def register_callback(self, callback: Callable, sensitive_data: Any = None,
                          auto_cleanup: bool = True) -> Callable:
        """
        Register a callback with optional sensitive data protection.

        Args:
            callback: Callback function to register
            sensitive_data: Sensitive data to protect with weak references
            auto_cleanup: Whether to automatically clean up the callback

        Returns:
            Wrapped callback function
        """
        if self._is_destroyed:
            logger.warning(f"Attempt to register callback on destroyed manager: {self.component_name}")
            return callback

        with self._lock:
            if sensitive_data is not None:
                # Create weak reference to sensitive data
                try:
                    weak_data = weakref.ref(sensitive_data)
                    self._sensitive_refs.add(weak_data)

                    # Create wrapper that checks if sensitive data still exists
                    def secure_wrapper(*args, **kwargs):
                        if self._is_destroyed:
                            return None

                        data = weak_data()
                        if data is None:
                            logger.debug("Sensitive data garbage collected, skipping callback")
                            return None

                        try:
                            return callback(*args, **kwargs)
                        except Exception as e:
                            logger.error(f"Error in secure callback: {e}")
                            return None

                    if auto_cleanup:
                        self._callbacks.add(secure_wrapper)

                    logger.debug("Registered secure callback with sensitive data protection")
                    return secure_wrapper

                except TypeError:
                    # Object doesn't support weak references
                    logger.warning("Cannot create weak reference for sensitive data, using regular callback")

            # Regular callback without sensitive data protection
            if auto_cleanup:
                self._callbacks.add(callback)

            return callback

    def register_cleanup_callback(self, cleanup_func: Callable):
        """
        Register a cleanup function to be called during destruction.

        Args:
            cleanup_func: Function to call during cleanup
        """
        with self._lock:
            if not self._is_destroyed:
                self._cleanup_callbacks.add(cleanup_func)

    def clear_sensitive_references(self):
        """Clear all sensitive data references."""
        with self._lock:
            # Clear weak references to sensitive data
            for weak_ref in list(self._sensitive_refs):
                try:
                    # Try to get the object and clear it if it's clearable
                    obj = weak_ref()
                    if obj is not None and hasattr(obj, 'clear'):
                        obj.clear()
                except Exception:
                    pass

            self._sensitive_refs.clear()

            # Force garbage collection to clean up references
            gc.collect()

            logger.debug(f"Cleared sensitive references for {self.component_name}")

    def cleanup_all(self):
        """Clean up all callbacks and references."""
        with self._lock:
            if self._is_destroyed:
                return

            self._is_destroyed = True

            # Call cleanup callbacks first
            for cleanup_func in list(self._cleanup_callbacks):
                try:
                    cleanup_func()
                except Exception as e:
                    # Get logger fresh to avoid scope issues during cleanup
                    from ..utils.logger import get_logger
                    cleanup_logger = get_logger(__name__)
                    cleanup_logger.error(f"Error in cleanup callback: {e}")

            self._cleanup_callbacks.clear()

            # Clear sensitive references
            self.clear_sensitive_references()

            # Clear regular callbacks
            self._callbacks.clear()

            # Force garbage collection
            gc.collect()

            # Get logger fresh to avoid scope issues during cleanup
            from ..utils.logger import get_logger
            cleanup_logger = get_logger(__name__)
            cleanup_logger.debug(f"Completed cleanup for {self.component_name}")

    def get_callback_count(self) -> int:
        """Get the number of active callbacks."""
        with self._lock:
            return len(self._callbacks)

    def is_destroyed(self) -> bool:
        """Check if the manager has been destroyed."""
        return self._is_destroyed

    def __del__(self):
        """Destructor to ensure cleanup."""
        try:
            self.cleanup_all()
        except Exception:
            pass  # Ignore errors during destruction


class GlobalCallbackRegistry:
    """Global registry for tracking callback managers across the application."""

    _instance = None
    _lock = threading.RLock()
    _managers: Dict[str, 'SecureCallbackManager']

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._managers: Dict[str, 'SecureCallbackManager'] = {}
                cls._instance._initialized = True
            return cls._instance

    def register_manager(self, component_id: str, manager: SecureCallbackManager):
        """Register a callback manager."""
        with self._lock:
            if hasattr(self, '_initialized'):
                self._managers[component_id] = manager
                logger.debug(f"Registered callback manager: {component_id}")

    def unregister_manager(self, component_id: str):
        """Unregister and cleanup a callback manager."""
        with self._lock:
            if hasattr(self, '_initialized') and component_id in self._managers:
                manager = self._managers.pop(component_id)
                manager.cleanup_all()
                logger.debug(f"Unregistered callback manager: {component_id}")

    def cleanup_all_managers(self):
        """Emergency cleanup of all managers."""
        with self._lock:
            if hasattr(self, '_initialized'):
                for component_id, manager in list(self._managers.items()):
                    try:
                        manager.cleanup_all()
                    except Exception as e:
                        # Get logger fresh to avoid scope issues during cleanup
                        from ..utils.logger import get_logger
                        cleanup_logger = get_logger(__name__)
                        cleanup_logger.error(f"Error cleaning up manager {component_id}: {e}")

                self._managers.clear()
                # Get logger fresh to avoid scope issues during cleanup
                from ..utils.logger import get_logger
                cleanup_logger = get_logger(__name__)
                cleanup_logger.info("Cleaned up all callback managers")

    def get_manager_count(self) -> int:
        """Get the number of registered managers."""
        with self._lock:
            if hasattr(self, '_initialized'):
                return len(self._managers)
            return 0


# Global instance
callback_registry = GlobalCallbackRegistry()


def create_secure_callback_manager(component_name: str) -> SecureCallbackManager:
    """
    Create and register a secure callback manager.

    Args:
        component_name: Name of the component

    Returns:
        SecureCallbackManager instance
    """
    manager = SecureCallbackManager(component_name)
    callback_registry.register_manager(component_name, manager)
    return manager


def cleanup_component_callbacks(component_name: str):
    """
    Cleanup callbacks for a specific component.

    Args:
        component_name: Name of the component to cleanup
    """
    callback_registry.unregister_manager(component_name)


def emergency_callback_cleanup():
    """Emergency cleanup of all callback managers."""
    callback_registry.cleanup_all_managers()
