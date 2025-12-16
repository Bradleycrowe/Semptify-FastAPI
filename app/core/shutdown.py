"""
Graceful Shutdown Handler for Semptify.

Ensures clean shutdown of background tasks, database connections,
and other resources when the application receives a termination signal.
"""

import asyncio
import logging
import signal
from typing import Callable, Coroutine, Any
from contextlib import asynccontextmanager

logger = logging.getLogger(__name__)

# Registry of shutdown handlers
_shutdown_handlers: list[Callable[[], Coroutine[Any, Any, None]]] = []
_shutdown_timeout: float = 30.0  # seconds


def register_shutdown_handler(handler: Callable[[], Coroutine[Any, Any, None]] | None = None) -> None:
    """
    Register an async function to be called during graceful shutdown.
    If no handler provided, sets up default signal handlers.
    
    Usage:
        # Register custom handler
        async def cleanup_my_service():
            await my_service.close()
        
        register_shutdown_handler(cleanup_my_service)
        
        # Or just set up signal handling
        register_shutdown_handler()
    """
    if handler is None:
        # Set up default signal handlers
        try:
            loop = asyncio.get_event_loop()
            for sig in (signal.SIGTERM, signal.SIGINT):
                try:
                    loop.add_signal_handler(sig, lambda s=sig: logger.info("Received %s", s))
                except NotImplementedError:
                    pass  # Windows doesn't support add_signal_handler
            logger.debug("Signal handlers registered")
        except RuntimeError:
            pass  # No event loop yet
        return
    
    _shutdown_handlers.append(handler)
    logger.debug("Registered shutdown handler: %s", handler.__name__)


def set_shutdown_timeout(timeout: float) -> None:
    """Set the timeout for graceful shutdown (default: 30 seconds)."""
    global _shutdown_timeout
    _shutdown_timeout = timeout


async def run_shutdown_handlers() -> None:
    """
    Execute all registered shutdown handlers.
    Called automatically during application shutdown.
    """
    if not _shutdown_handlers:
        return
    
    logger.info("Running %d shutdown handlers...", len(_shutdown_handlers))
    
    for handler in reversed(_shutdown_handlers):
        try:
            logger.debug("Running shutdown handler: %s", handler.__name__)
            await asyncio.wait_for(handler(), timeout=_shutdown_timeout / len(_shutdown_handlers))
            logger.debug("Completed shutdown handler: %s", handler.__name__)
        except asyncio.TimeoutError:
            logger.error("Shutdown handler timed out: %s", handler.__name__)
        except Exception as e:
            logger.error("Shutdown handler failed: %s - %s", handler.__name__, e)
    
    logger.info("All shutdown handlers completed")


class GracefulShutdown:
    """
    Manages graceful shutdown for the application.
    
    Usage in FastAPI lifespan:
        @asynccontextmanager
        async def lifespan(app: FastAPI):
            shutdown = GracefulShutdown()
            shutdown.setup_signal_handlers()
            
            yield
            
            await shutdown.shutdown()
    """
    
    def __init__(self):
        self._shutdown_event = asyncio.Event()
        self._shutting_down = False
    
    def setup_signal_handlers(self) -> None:
        """Set up signal handlers for graceful shutdown."""
        loop = asyncio.get_event_loop()
        
        for sig in (signal.SIGTERM, signal.SIGINT):
            try:
                loop.add_signal_handler(sig, self._handle_signal, sig)
                logger.debug("Registered signal handler for %s", sig.name)
            except NotImplementedError:
                # Windows doesn't support add_signal_handler
                signal.signal(sig, lambda s, f: self._handle_signal(s))
                logger.debug("Registered signal handler (fallback) for %s", sig)
    
    def _handle_signal(self, sig) -> None:
        """Handle shutdown signal."""
        sig_name = sig.name if hasattr(sig, 'name') else str(sig)
        logger.info("Received signal %s, initiating graceful shutdown...", sig_name)
        self._shutdown_event.set()
    
    @property
    def is_shutting_down(self) -> bool:
        """Check if shutdown has been initiated."""
        return self._shutting_down
    
    async def wait_for_shutdown(self) -> None:
        """Wait for shutdown signal."""
        await self._shutdown_event.wait()
    
    async def shutdown(self) -> None:
        """Perform graceful shutdown."""
        if self._shutting_down:
            return
        
        self._shutting_down = True
        logger.info("=" * 50)
        logger.info("GRACEFUL SHUTDOWN INITIATED")
        logger.info("=" * 50)
        
        try:
            await asyncio.wait_for(
                run_shutdown_handlers(),
                timeout=_shutdown_timeout
            )
        except asyncio.TimeoutError:
            logger.error("Shutdown timed out after %s seconds", _shutdown_timeout)
        
        logger.info("Graceful shutdown complete")


# Background task manager with graceful shutdown support
class BackgroundTaskManager:
    """
    Manages background tasks with graceful shutdown support.
    
    Usage:
        task_manager = BackgroundTaskManager()
        
        # Start a background task
        task_manager.create_task(my_async_function())
        
        # On shutdown, all tasks will be cancelled gracefully
    """
    
    def __init__(self):
        self._tasks: set[asyncio.Task] = set()
        # Note: Don't register automatically to avoid circular calls
    
    def create_task(self, coro: Coroutine, name: str | None = None) -> asyncio.Task:
        """Create and track a background task."""
        task = asyncio.create_task(coro, name=name)
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)
        return task
    
    async def wait_for_completion(self, timeout: float = 10.0) -> None:
        """Wait for all background tasks to complete or timeout."""
        if not self._tasks:
            return
        
        logger.info("Waiting for %d background tasks to complete (timeout: %.1fs)...", len(self._tasks), timeout)
        
        try:
            # Wait for tasks to complete naturally
            done, pending = await asyncio.wait(
                self._tasks,
                timeout=timeout,
                return_when=asyncio.ALL_COMPLETED
            )
            
            if pending:
                logger.warning("%d tasks did not complete in time, cancelling...", len(pending))
                for task in pending:
                    task.cancel()
                await asyncio.gather(*pending, return_exceptions=True)
            
            logger.info("All background tasks completed")
        except Exception as e:
            logger.error("Error waiting for background tasks: %s", e)
    
    async def _shutdown_tasks(self) -> None:
        """Cancel all running tasks."""
        if not self._tasks:
            return
        
        logger.info("Cancelling %d background tasks...", len(self._tasks))
        
        for task in self._tasks:
            task.cancel()
        
        # Wait for all tasks to complete
        results = await asyncio.gather(*self._tasks, return_exceptions=True)
        
        for task, result in zip(self._tasks, results):
            if isinstance(result, asyncio.CancelledError):
                logger.debug("Task cancelled: %s", task.get_name())
            elif isinstance(result, Exception):
                logger.error("Task failed during shutdown: %s - %s", task.get_name(), result)
        
        self._tasks.clear()
        logger.info("All background tasks cancelled")


# Global task manager instance
task_manager = BackgroundTaskManager()
