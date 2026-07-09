"""Routing Framework — baseline routing algorithms.

Phase 7B Implementation
----------------------
Baseline routing framework with Dijkstra algorithm.

Phase 7C Implementation
----------------------
Routing benchmark and verification framework.

Phase 7D Implementation
----------------------
A* heuristic search algorithm with configurable heuristics.

Public Interfaces
-----------------
Core
  RoutingAlgorithm          – Protocol for all routing algorithms
  RoutingRequest            – Immutable routing request
  RoutingResult             – Immutable routing result
  RoutingFactory            – Factory for creating routing instances

Routes
  Route                     – Immutable ordered sequence of edges
  RouteSegment              – Immutable segment of a route
  RouteCost                 – Immutable cost breakdown
  RouteCandidate            – Immutable candidate route

Validation
  RouteValidator            – Validates routes before return
  RouteValidationReport     – Validation result

Statistics
  RoutingStatistics          – Exploration and performance metrics

Cost
  CompositeCostCalculator   – Computes weighted cost components

Verification
  RoutingVerifier           – Algorithm-independent route verification
  VerificationReport        – Route verification result
  VerificationError         – Single verification error
  DeterministicReplayReport – Deterministic replay verification

Heuristics
  Heuristic                 – Protocol for A* heuristic functions
  ZeroHeuristic             – Always returns 0 (A* = Dijkstra)
  EuclideanHeuristic        – Straight-line distance heuristic
  ManhattanHeuristic        – Manhattan distance heuristic
  HeuristicFactory          – Creates heuristics from config
  HeuristicValidator        – Validates heuristic admissibility

Benchmark
  BenchmarkConfig           – Benchmark configuration
  BenchmarkScenario         – Benchmark scenario (graph + requests)
  BenchmarkRequest          – Single benchmark routing request
  BenchmarkMetrics          – Per-request benchmark metrics
  AlgorithmMetadata         – Algorithm metadata
  BenchmarkResult           – Complete benchmark result
  BenchmarkSummary          – Summary statistics
  BenchmarkValidator        – Validates benchmarks
  BenchmarkReporter         – Writes benchmark artifacts
  BenchmarkRunner           – Orchestrates benchmark execution

Algorithms
  DijkstraRouting            – Classical shortest-path algorithm
  AStarRouting               – Heuristic search algorithm

Exceptions
  RoutingError              – Base exception for routing errors
  NoPathError               – No path exists between source and destination
  TimeoutError              – Routing exceeded timeout
  InvalidRequestError       – Invalid routing request

Design Decisions (Approved)
----------------------------
- Pure function requirement: identical inputs → identical outputs
- Common routing interface: all algorithms implement RoutingAlgorithm Protocol
- Algorithm-agnostic: Decision Engine evaluates only on total_cost
- Read-only routing: no graph or vehicle modification
- Modular cost: independently configurable components
- Benchmark fairness: identical conditions for all algorithms
- Verification: algorithm-independent utilities for route correctness
- Heuristic independence: A* depends only on Heuristic Protocol
"""

from __future__ import annotations

# Core
from e3hybrid.routing.protocol import RoutingAlgorithm
from e3hybrid.routing.request import RoutingRequest
from e3hybrid.routing.result import RoutingResult
from e3hybrid.routing.factory import RoutingFactory

# Routes
from e3hybrid.routing.route import Route, RouteSegment
from e3hybrid.routing.cost import RouteCost
from e3hybrid.routing.candidate import RouteCandidate

# Validation
from e3hybrid.routing.validator import RouteValidator, RouteValidationReport

# Statistics
from e3hybrid.routing.statistics import RoutingStatistics

# Cost
from e3hybrid.routing.cost_calculator import CompositeCostCalculator

# Verification
from e3hybrid.routing.verifier import (
    DeterministicReplayReport,
    VerificationError,
    VerificationReport,
    RoutingVerifier,
)

# Benchmark
from e3hybrid.routing.benchmark_config import BenchmarkConfig
from e3hybrid.routing.benchmark_scenario import BenchmarkRequest, BenchmarkScenario
from e3hybrid.routing.benchmark_metrics import AlgorithmMetadata, BenchmarkMetrics
from e3hybrid.routing.benchmark_result import BenchmarkResult, BenchmarkSummary
from e3hybrid.routing.benchmark_validator import BenchmarkValidator
from e3hybrid.routing.benchmark_reporter import BenchmarkReporter
from e3hybrid.routing.benchmark_runner import BenchmarkRunner

# Heuristics
from e3hybrid.routing.heuristic import (
    EuclideanHeuristic,
    Heuristic,
    ManhattanHeuristic,
    ZeroHeuristic,
)
from e3hybrid.routing.heuristic_factory import HeuristicFactory
from e3hybrid.routing.heuristic_validator import HeuristicValidator

# Algorithms
from e3hybrid.routing.dijkstra import DijkstraRouting
from e3hybrid.routing.astar import AStarRouting

# Exceptions
from e3hybrid.routing.exceptions import (
    RoutingError,
    NoPathError,
    TimeoutError,
    InvalidRequestError,
)

__all__ = [
    # Core
    "RoutingAlgorithm",
    "RoutingRequest",
    "RoutingResult",
    "RoutingFactory",
    # Routes
    "Route",
    "RouteSegment",
    "RouteCost",
    "RouteCandidate",
    # Validation
    "RouteValidator",
    "RouteValidationReport",
    # Statistics
    "RoutingStatistics",
    # Cost
    "CompositeCostCalculator",
    # Verification
    "DeterministicReplayReport",
    "VerificationError",
    "VerificationReport",
    "RoutingVerifier",
    # Heuristics
    "Heuristic",
    "ZeroHeuristic",
    "EuclideanHeuristic",
    "ManhattanHeuristic",
    "HeuristicFactory",
    "HeuristicValidator",
    # Benchmark
    "BenchmarkConfig",
    "BenchmarkRequest",
    "BenchmarkScenario",
    "AlgorithmMetadata",
    "BenchmarkMetrics",
    "BenchmarkResult",
    "BenchmarkSummary",
    "BenchmarkValidator",
    "BenchmarkReporter",
    "BenchmarkRunner",
    # Algorithms
    "DijkstraRouting",
    "AStarRouting",
    # Exceptions
    "RoutingError",
    "NoPathError",
    "TimeoutError",
    "InvalidRequestError",
]
