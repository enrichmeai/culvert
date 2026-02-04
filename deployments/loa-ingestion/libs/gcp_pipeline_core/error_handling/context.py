"""
Context manager for error handling in pipelines.
"""

from typing import Callable, TYPE_CHECKING
import logging

if TYPE_CHECKING:
    from .handler import ErrorHandler

logger = logging.getLogger(__name__)


class ErrorContext:
    """Context manager for error handling in pipelines"""

    def __init__(self,
                 error_handler: 'ErrorHandler',
                 operation_name: str,
                 auto_retry: bool = True):
        self.error_handler = error_handler
        self.operation_name = operation_name
        self.auto_retry = auto_retry
        self.error = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is None:
            return False

        # Handle the exception
        self.error = self.error_handler.handle_exception(
            exc_val,
            metadata={"operation": self.operation_name}
        )

        # Auto-retry if configured
        if self.auto_retry:
            if self.error_handler.prepare_retry(self.error):
                logger.info(f"Will retry {self.operation_name}")
                return True  # Suppress exception to retry

        return False  # Don't suppress, raise exception


def with_error_handling(error_handler: 'ErrorHandler', auto_retry: bool = True):
    """Decorator for error handling"""
    def decorator(func: Callable):
        def wrapper(*args, **kwargs):
            with ErrorContext(error_handler, func.__name__, auto_retry) as ctx:
                return func(*args, **kwargs)
        return wrapper
    return decorator

