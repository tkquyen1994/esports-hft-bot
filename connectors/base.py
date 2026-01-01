"""
Base Connector - Foundation class for all data connectors.

All data feed connectors inherit from this class.
It provides common functionality like:
- Starting and stopping
- Registering callbacks for data updates
- Notifying callbacks when new data arrives
"""

import asyncio
import logging
from abc import ABC, abstractmethod
from typing import List, Callable, Any

logger = logging.getLogger(__name__)


class BaseConnector(ABC):
    """
    Abstract base class for data connectors.
    
    All connectors (PandaScore, simulated, etc.) inherit from this.
    
    Usage pattern:
        connector = SomeConnector()
        connector.register_callback(my_handler_function)
        await connector.start()
        # ... connector sends data to my_handler_function ...
        await connector.stop()
    """
    
    def __init__(self):
        """Initialize the connector."""
        self._running: bool = False
        self._callbacks: List[Callable] = []
    
    @abstractmethod
    async def start(self):
        """
        Start the connector.
        
        Must be implemented by subclasses.
        """
        pass
    
    @abstractmethod
    async def stop(self):
        """
        Stop the connector.
        
        Must be implemented by subclasses.
        """
        pass
    
    def register_callback(self, callback: Callable):
        """
        Register a callback function to receive data.
        
        When new data arrives, all registered callbacks are called.
        
        Args:
            callback: Function to call with new data.
                     Can be sync or async.
        
        Example:
            def handle_event(event):
                print(f"Got event: {event}")
            
            connector.register_callback(handle_event)
        """
        self._callbacks.append(callback)
        logger.debug(f"Registered callback: {callback.__name__}")
    
    def unregister_callback(self, callback: Callable):
        """
        Remove a callback.
        
        Args:
            callback: The callback function to remove.
        """
        if callback in self._callbacks:
            self._callbacks.remove(callback)
            logger.debug(f"Unregistered callback: {callback.__name__}")
    
    async def _notify_callbacks(self, data: Any):
        """
        Notify all registered callbacks with new data.
        
        Handles both sync and async callbacks.
        
        Args:
            data: The data to send to callbacks.
        """
        for callback in self._callbacks:
            try:
                # Check if callback is async
                if asyncio.iscoroutinefunction(callback):
                    await callback(data)
                else:
                    callback(data)
            except Exception as e:
                logger.error(f"Callback error in {callback.__name__}: {e}")
    
    @property
    def is_running(self) -> bool:
        """Whether the connector is currently running."""
        return self._running
    
    @property
    def callback_count(self) -> int:
        """Number of registered callbacks."""
        return len(self._callbacks)