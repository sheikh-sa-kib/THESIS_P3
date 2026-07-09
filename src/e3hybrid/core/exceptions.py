"""Centralized project-specific exception hierarchy."""


class E3HybridError(Exception):
    """Base exception for all framework-specific errors."""


class ConfigurationError(E3HybridError):
    """Raised when configuration files are missing, invalid, or incomplete."""


class ConfigError(ConfigurationError):
    """Backward-compatible alias class for configuration failures."""


class NetworkError(E3HybridError):
    """Raised when a road-network graph is invalid or cannot be processed."""


class VehicleError(E3HybridError):
    """Raised when vehicle construction, validation, or state updates fail."""


class SimulationError(E3HybridError):
    """Raised when simulation lifecycle or state transitions fail."""


class RoutingError(E3HybridError):
    """Raised when route candidate generation fails."""


class CommunicationError(E3HybridError):
    """Raised when communication protocol or delivery handling fails."""


class EmergencyError(E3HybridError):
    """Raised when emergency event construction, validation, or scheduling fails."""


class ExperimentError(E3HybridError):
    """Raised when experiment setup, execution, or artifact writing fails."""


class ReproducibilityError(E3HybridError):
    """Raised when reproducibility metadata cannot be collected safely."""
