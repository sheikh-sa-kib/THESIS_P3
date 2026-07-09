"""Routing exception hierarchy."""

from __future__ import annotations

from e3hybrid.core.exceptions import E3HybridError


class RoutingError(E3HybridError):
    """Base exception for routing errors."""

    pass


class NoPathError(RoutingError):
    """No path exists between source and destination."""

    pass


class TimeoutError(RoutingError):
    """Routing exceeded timeout."""

    pass


class InvalidRequestError(RoutingError):
    """Invalid routing request."""

    pass
