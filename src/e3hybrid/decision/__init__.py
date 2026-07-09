"""Decision Engine — tick-based policy evaluation for electric vehicles.

Phase 6 Implementation
---------------------
The Decision Engine evaluates policies once per simulation tick and produces
decisions for vehicle actions.  It is completely unaware of which routing
algorithm produced candidate routes — it evaluates only on objective values.

Public Interfaces
-----------------
Core
  DecisionEngine          – Main evaluation coordinator
  DecisionEngineConfig     – Engine configuration
  DecisionLog              – CSV-based decision logger

Observations
  VehicleObservation       – Complete snapshot for one evaluation cycle
  GraphSnapshot            – Neighbourhood-scoped graph view
  BatterySnapshot          – Battery state snapshot
  EdgeSnapshot             – Edge state snapshot
  RouteSnapshot            – Current route snapshot
  ObservationAssembler     – Builds observations from subsystem state

Decisions
  Decision                 – Final decision output (immutable)
  DecisionType             – Enum of all possible decision types
  DecisionId               – Strongly-typed decision identifier
  DecisionValidator        – Validates decisions before logging
  DecisionValidationReport – Validation error report

Policies
  DecisionPolicy           – Protocol for policy implementations
  PolicyRecommendation      – Policy output (immutable)
  DecisionAggregationPolicy – Selects winning recommendation

Policy Management
  PolicyRegistry           – Central registry for policy factories
  PolicyManager            – Manages policy instances
  register_all_policies    – Registers all Phase 6 policies

Configuration
  DecisionConfig           – Complete decision engine configuration
  SafetyPolicyConfig       – Safety policy configuration
  EmergencyPolicyConfig    – Emergency policy configuration
  BatteryPolicyConfig      – Battery policy configuration
  CongestionPolicyConfig   – Congestion policy configuration
  CommunicationPolicyConfig – Communication policy configuration
  RoutingCandidatePolicyConfig – Routing candidate policy configuration

Routing Candidates
  RouteCandidate           – A single candidate route
  RouteCandidateSource     – Protocol for routing algorithm sources
  NullRouteCandidateSource – Phase 6 placeholder (returns empty tuple)

Concrete Policies
  SafetyPolicy             – Hard-constraint safety checks
  EmergencyPolicy          – React to active emergency events
  BatteryPolicy            – Protect against SoC violations
  CommunicationPolicy      – Decide when to broadcast information
  CongestionPolicy         – React to congestion and hazard penalties
  RoutingCandidatePolicy   – Evaluate routing candidates on cost only

Design Decisions (Approved)
----------------------------
1. Observation Frequency: Evaluate once per simulation tick (not continuous).
2. Graph Snapshot Scope: Never receive full graph; use GraphSnapshot abstraction.
3. Candidate Pre-Filtering: Never discard candidates before policy evaluation.
4. Decision Logging: Enable for every simulation; write immediately to CSV.
"""

from __future__ import annotations

# Core
from e3hybrid.decision.engine import DecisionEngine, DecisionEngineConfig
from e3hybrid.decision.decision_log import DecisionLog

# Observations
from e3hybrid.decision.observation import (
    BatterySnapshot,
    EdgeSnapshot,
    GraphSnapshot,
    RouteSnapshot,
    VehicleObservation,
)
from e3hybrid.decision.observation_assembler import ObservationAssembler

# Decisions
from e3hybrid.decision.decision import Decision
from e3hybrid.decision.types import DecisionId, DecisionType, RouteId
from e3hybrid.decision.validation import (
    DecisionValidationError,
    DecisionValidationReport,
    DecisionValidator,
)

# Policies
from e3hybrid.decision.policy import DecisionPolicy, PolicyRecommendation
from e3hybrid.decision.aggregation import DecisionAggregationPolicy

# Policy Management
from e3hybrid.decision.policy_registry import (
    PolicyManager,
    PolicyRegistry,
    get_global_registry,
    register_policy,
)
from e3hybrid.decision.policy_registration import register_all_policies

# Configuration
from e3hybrid.decision.config import (
    BatteryPolicyConfig,
    CommunicationPolicyConfig,
    CongestionPolicyConfig,
    DecisionConfig,
    EmergencyPolicyConfig,
    RoutingCandidatePolicyConfig,
    SafetyPolicyConfig,
)

# Routing Candidates
from e3hybrid.decision.route import (
    NullRouteCandidateSource,
    RouteCandidate,
    RouteCandidateSource,
)

# Concrete Policies
from e3hybrid.decision.policies import (
    BatteryPolicy,
    CommunicationPolicy,
    CongestionPolicy,
    EmergencyPolicy,
    RoutingCandidatePolicy,
    SafetyPolicy,
)

__all__ = [
    # Core
    "DecisionEngine",
    "DecisionEngineConfig",
    "DecisionLog",
    # Observations
    "BatterySnapshot",
    "EdgeSnapshot",
    "GraphSnapshot",
    "RouteSnapshot",
    "VehicleObservation",
    "ObservationAssembler",
    # Decisions
    "Decision",
    "DecisionId",
    "DecisionType",
    "RouteId",
    "DecisionValidationError",
    "DecisionValidationReport",
    "DecisionValidator",
    # Policies
    "DecisionPolicy",
    "PolicyRecommendation",
    "DecisionAggregationPolicy",
    # Policy Management
    "PolicyManager",
    "PolicyRegistry",
    "get_global_registry",
    "register_policy",
    "register_all_policies",
    # Configuration
    "DecisionConfig",
    "SafetyPolicyConfig",
    "EmergencyPolicyConfig",
    "BatteryPolicyConfig",
    "CongestionPolicyConfig",
    "CommunicationPolicyConfig",
    "RoutingCandidatePolicyConfig",
    # Routing Candidates
    "RouteCandidate",
    "RouteCandidateSource",
    "NullRouteCandidateSource",
    # Concrete Policies
    "SafetyPolicy",
    "EmergencyPolicy",
    "BatteryPolicy",
    "CommunicationPolicy",
    "CongestionPolicy",
    "RoutingCandidatePolicy",
]
