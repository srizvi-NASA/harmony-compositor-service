"""Custom exceptions used by the Harmony Compositor Service."""


class CompositorError(Exception):
    """Base exception for service configuration or processing failures."""


class ConfigurationError(CompositorError):
    """Raised when a compositor configuration cannot be loaded or validated."""


class GranuleProcessingError(CompositorError):
    """Raised when the configured composition cannot be produced from a granule."""
