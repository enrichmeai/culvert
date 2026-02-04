"""
Custom exception classes for GDW Data Core.
"""


class GDWError(Exception):
    """Base exception for all GDW errors"""
    pass


class GDWValidationError(GDWError):
    """Raised when data validation fails"""
    pass


class GDWTransformError(GDWError):
    """Raised when data transformation fails"""
    pass


class GDWIntegrationError(GDWError):
    """Raised when integration with external services fails"""
    pass


class GDWResourceError(GDWError):
    """Raised when resource exhaustion occurs"""
    pass

