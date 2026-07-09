"""BenchmarkScenario and BenchmarkRequest — scenarios and requests for benchmarks."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from e3hybrid.routing.request import RoutingRequest

if TYPE_CHECKING:
    from e3hybrid.network.graph import DirectedGraph


@dataclass(frozen=True, slots=True)
class BenchmarkRequest:
    """A single routing request within a benchmark scenario.

    Attributes
    ----------
    request:
        The routing request to execute.
    description:
        Human-readable description of this request.
    expected_success:
        Whether this request is expected to succeed (for verification).
    metadata:
        Additional metadata for this request.
    """

    request: RoutingRequest
    description: str = ""
    expected_success: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class BenchmarkScenario:
    """A complete benchmark scenario.

    A scenario bundles a graph, a set of routing requests, and configuration
    into a single unit that can be executed by any routing algorithm.

    Attributes
    ----------
    graph:
        The graph to route on.
    requests:
        The routing requests to execute.
    name:
        Human-readable name for this scenario.
    description:
        Detailed description of what this scenario tests.
    metadata:
        Additional metadata for this scenario.
    """

    graph: "DirectedGraph"
    requests: tuple[BenchmarkRequest, ...]
    name: str = "unnamed_scenario"
    description: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
