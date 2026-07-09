# Design Decisions

This document records why major design choices were made.

## DD-001: Separate Routing from Decision Making

Routing algorithms produce candidate routes. The Decision Engine selects final
vehicle behavior. This prevents routing algorithms from gaining privileged
control over yielding, waiting, communication, or emergency corridor behavior.

## DD-002: Keep SUMO Behind a Backend Boundary

SUMO and TraCI integration will be isolated in `src/e3hybrid/sumo/`. This keeps
core algorithms testable and prevents SUMO-specific state from leaking into
algorithm comparisons.

## DD-003: Maintain Research Documentation with Code

The `docs/` folder is part of the project architecture. It preserves design
rationale, assumptions, literature mappings, experiment protocol, API notes, and
development history for thesis defense and reproducibility.

## DD-004: Internal Graph as Source of Truth

The road network is represented by `DirectedGraph`, `Node`, and `Edge` inside
`src/e3hybrid/network/`. SUMO will later be an adapter, not the core model. This
keeps the simulator testable, backend-neutral, and scientifically auditable.

## DD-005: Deterministic Graph Traversal

Adjacency lists preserve insertion order. This avoids nondeterministic edge
ordering in future algorithms and supports reproducible experiment behavior.

## DD-006: Protocol-Based Interface Design Throughout

Every abstraction follows the same Protocol-based design as `CostProvider`:

- `EnergyModel` is a Protocol — routing algorithms never import a concrete model.
- `Battery` is a Protocol — battery chemistry can be swapped without changing vehicles.
- `CommunicationProtocol` will be a Protocol — future Phase.
- `EmergencyPolicy` will be a Protocol — future Phase.
- `DecisionStrategy` will be a Protocol — future Phase.

This makes the framework extensible, comparable, and defensible as a research
platform. Future implementations (`PolynomialEnergyModel`, `TemperatureAwareBattery`,
etc.) plug in through existing interfaces with no changes to dependent code.

## DD-007: Dependency Injection for Vehicle Entities

`ElectricVehicle` receives its `Battery` and `EnergyModel` at construction time
through dependency injection. It never imports a concrete implementation. This:

- Keeps the entity testable with stub models.
- Allows different vehicle classes to use different energy models.
- Ensures routing algorithms see only the Protocol interface.

## DD-008: Immutable State Transitions for Vehicles

`ElectricVehicle`, `VehicleState`, and `VehicleConstraints` are immutable
(or use the copy-on-update pattern for mutable fields). State transitions
produce new instances. This mirrors the `Edge.with_state()` pattern from the
network module and makes state history safe to log and replay.

## DD-009: Research Milestone Approval Policy

Each major design and implementation step requires explicit approval before
proceeding:

- Architecture milestone → approved before coding
- Mathematical model milestone → approved before coding
- Algorithm milestone → approved before coding
- SUMO integration milestone → approved before coding
- Experiment framework milestone → approved before coding
- Final evaluation milestone → approved before reporting

This prevents irreversible design decisions from being baked in without review.
Each milestone produces a design document that can be adapted into the
corresponding thesis chapter (Methodology, Implementation, Evaluation).

## DD-010: Fiori et al. (2016) Physics-Based Energy Model

The Fiori physics-based EV energy consumption model was selected over:

- Linear regression: requires per-regime calibration, no regenerative braking.
- Polynomial (NREL): empirical coefficients, less interpretable for thesis defense.
- Machine learning: requires large training dataset, black-box, unacceptable risk.

Fiori provides transparent physics (force balance), literature validation against
real EVs, O(1) computational cost, and grade support for future SUMO integration.
Full rationale and equations documented in `docs/energy_model_design.md`.

## DD-011: Communication Layer Knows Nothing About Routing or Swarm Logic

The `MessageBus` and all communication module classes never import from
`network`, `vehicle.energy`, routing, or swarm packages. The only shared type
is `VehicleId` from `vehicle.types`.

This separation means:
- The communication layer can be tested fully in isolation.
- Swarm algorithms (ACO, BCO, PSO) depend on `Broadcaster`/`Receiver`
  injection — they never access `MessageBus` directly.
- Changing the channel model (loss, latency, radius) requires no changes to
  any algorithm.
- The same bus instance can serve both swarm coordination messages
  (`PHEROMONE_UPDATE`, `SCOUT_REPORT`) and emergency messages
  (`EMERGENCY_VEHICLE`) without either knowing about the other.

## DD-012: Approved Development Order

The thesis roadmap follows this order, approved after Phase 4:

Road Network → Vehicle Model → Communication → Emergency Framework →
Decision Engine → Baseline Routing → ACO → BCO → PSO → E³-Hybrid →
SUMO Adapter → Experiments

Rationale: communication and emergency infrastructure must exist before swarm
algorithms because decentralized coordination (the primary thesis contribution)
requires a working transport layer. Building algorithms on a tested, stable
foundation reduces integration risk and keeps each phase independently
reviewable.

## DD-013: Additive Effect Composition (Decision 1)

Multiple simultaneous emergency events on the same edge compose additively:

    effective_travel_time = base_travel_time × congestion_factor
                            + hazard_penalty_s
                            + emergency_penalty_s
                            + communication_penalty_s

Blocked edges (``is_blocked = True``) take unconditional precedence. A blocked
edge returns ``inf`` cost from all ``CostProvider`` implementations regardless
of any additive penalties.

Congestion is multiplicative (scales base travel time). All penalty fields are
additive and stack across simultaneous events.

## DD-014: Event Resolution by Full Recompute (Decision 2)

When an event resolves, its owned ``NetworkEffect`` objects are removed from
``EmergencyState``. The composite state for each affected edge is then
recomputed from scratch from the remaining active effects against the stored
baseline. This prevents floating-point drift from incremental add/subtract cycles
over long simulation runs. The graph always returns exactly to its original state
when all events clear.

## DD-015: CommunicationBlackout via Effect Only (Decision 3)

``CommunicationBlackoutEvent`` sets ``communication_penalty_s`` on affected
edges via ``CommunicationEffect``. It never touches the ``MessageBus``.
A future ``CommunicationPolicySubscriber`` may observe the raised penalty and
adjust the channel model, but the emergency module has no knowledge of
``MessageBus`` internals.

## DD-016: EmergencyVehicle Publishes Request Only (Decision 4)

``EmergencyVehicleEvent`` publishes a corridor priority request. It contains
``origin_node`` and ``destination_node`` for future routing use, but performs
no route computation. Future routing algorithms react through the Decision Engine.
The emergency framework never imports routing modules.

## DD-017: Decision Engine as Pure Coordination Layer

The Decision Engine is not a routing algorithm. It evaluates observations and
produces Decision objects. It never calls routing algorithms directly, never
modifies the graph, never sends messages, and never knows about SUMO.

This separation means:
- Dijkstra, A*, ACO, BCO, PSO can be swapped without changing the DE.
- All algorithms are evaluated on equal terms by the same policy pipeline.
- The thesis evaluation chapter can attribute vehicle behaviour to specific
  policies with logged, human-readable explanations.

## DD-018: RouteCandidateSource Protocol (Algorithm-Agnostic Routing)

The Decision Engine requests routing candidates through `RouteCandidateSource`,
a Protocol that any algorithm can satisfy. The DE sees only `RouteCandidate`
objects with a `total_cost` field. It never knows whether the cost was computed
by Dijkstra, pheromone signals, or particle best-known positions.

This is the key design decision that makes ACO/BCO/PSO/E³-Hybrid comparable
on equal terms: the evaluation pipeline is identical for all algorithms.

## DD-019: VehicleObservation as Immutable Snapshot

The Decision Engine receives a frozen `VehicleObservation` snapshot assembled
by the simulation core. It never queries subsystems (graph, battery, inbox)
directly. This ensures the DE is a pure function from observation to decision,
making it fully deterministic and testable in isolation without a running
simulation.

## DD-020: Approved Development Order (Phases 6–13)

After the Decision Engine (Phase 6), the approved order is:
Phase 7: Baseline routing (SUMO baseline, Dijkstra, A*)
Phase 8: Swarm infrastructure
Phase 9: ACO
Phase 10: BCO
Phase 11: PSO
Phase 12: E³-Hybrid integration
Phase 13: SUMO/TraCI adapter
Phase 14: Experiment framework
Phase 15: Visualization and thesis evaluation

This order minimises refactoring by ensuring each advanced component builds on
a stable, tested foundation.

## DD-021: Tick-Based Decision Evaluation (Decision 1)

The Decision Engine evaluates exactly once per simulation tick, not continuously.
The simulation loop is: Simulation Tick → Collect Observations → Evaluate Policies
→ Generate Decision → Execute Decision → Advance Simulation. This guarantees
deterministic replay.

## DD-022: GraphSnapshot Abstraction (Decision 2)

The Decision Engine never receives the full DirectedGraph. It receives a
GraphSnapshot limited to the vehicle's current edge and configurable neighbourhood
depth. This encapsulates the graph and prevents policies from accessing the full
network state.

## DD-023: No Candidate Pre-Filtering (Decision 3)

Every routing algorithm submits its complete candidate set to the Decision Engine.
The DE is responsible for evaluation. This preserves fairness between SUMO Baseline,
Dijkstra, A*, ACO, BCO, PSO, and E³-Hybrid.

## DD-024: Immediate Decision Logging (Decision 4)

Decision logging is enabled for every simulation. Every decision is written
immediately to CSV with no buffering. This ensures decisions are preserved even
if the simulation crashes. Future versions may support SQLite or Parquet.

## DD-025: Algorithm-Agnostic Decision Engine

The Decision Engine evaluates candidate quality using objective values only. The
algorithm name exists only for logging, evaluation, and research analysis. The engine
itself never knows which algorithm produced a candidate.

## DD-026: Immutable Decision Objects

Every Decision, PolicyRecommendation, and Observation is immutable (frozen
dataclass). This ensures deterministic replay and makes state history safe to log
and analyze.

## DD-027: Mandatory Explanation Field

Every Decision must include a non-empty explanation field. This is critical for
debugging, evaluation, and thesis screenshots. The explanation field is validated
at construction time.

## DD-028: Pure Function Routing Algorithms

Every routing algorithm must be a pure function: given identical inputs, it produces
identical outputs. No global state, no hidden randomness, no side effects, no graph
modification, no vehicle modification. This ensures fair comparison between algorithms
and deterministic replay for reproducibility.

## DD-029: Common Routing Interface for Fair Comparison

All routing algorithms (SUMO Baseline, Dijkstra, A*, ACO, BCO, PSO, E³-Hybrid) must
implement the same `RoutingAlgorithm` Protocol and return identical `RoutingResult`
structures. Differences in performance are attributable to algorithm logic, not
interface advantages. This is essential for scientific validity and thesis defensibility.

## DD-030: Modular Cost Architecture

Cost computation is abstracted through `CostProvider` Protocol. Each cost component
(distance, time, energy, congestion, hazard, emergency, communication) is independently
configurable via weights. Total cost is a weighted sum. This allows different objective
functions without modifying algorithms and enables thesis analysis of which factors
most influence routing decisions.

## DD-031: Algorithm-Agnostic RouteCandidate

`RouteCandidate` is the structure passed to the Decision Engine. The Decision Engine
evaluates ONLY on `total_cost` — it never inspects how cost was computed or which
algorithm produced the candidate. The algorithm name exists only for logging and
analysis. This ensures the Decision Engine is completely routing-agnostic.

## DD-032: Routing Layer Never Modifies Graph or Vehicles

The routing layer is read-only. All graph access is through `GraphSnapshot`. All cost
queries go through `CostProvider`. No routing algorithm may call `DirectedGraph.update_edge_state`
or modify vehicle state. This preserves graph integrity and ensures routing is a pure
computational procedure.

## DD-033: Identical Benchmark Conditions

Every algorithm is benchmarked under identical conditions: same graph, same requests,
same seed, same scenarios, same hardware, same stopping criteria, same timeout, same
metrics. No algorithm-specific advantages. This ensures statistical validity and that
performance differences are attributable to algorithm logic.

## DD-034: Deferred Caching and Incremental Routing

Caching and incremental routing are designed in Phase 7A but implementation is deferred
until after baseline routing is stable. This allows focus on core algorithm correctness
before optimization. Cache key composition and invalidation strategy are defined to
ensure future implementation is consistent.

## DD-035: Separation of Routing and Decision Making

Routing algorithms compute paths from source to destination based on graph topology and
cost models. Decision Engine evaluates whether to accept, reject, or modify routing
recommendations based on vehicle state, battery, emergency conditions, and policy
constraints. This separation allows routing algorithms to remain pure functions and
enables independent evaluation of routing quality vs. decision quality.

## DD-036: Algorithm-Independent Verification

The `RoutingVerifier` operates only on `Route`, `RoutingResult`, `RouteCandidate`, and
`DirectedGraph`. It never imports algorithm-specific modules. This ensures verification
is fair and reusable across all algorithms, and that verification biases cannot
favor one algorithm over another.

## DD-037: Standardized Metric Collection

All metrics are collected by the `BenchmarkRunner` from `RoutingResult` and
`RoutingStatistics`. Algorithms do not report custom metrics. This prevents
algorithm-specific metric bias and ensures comparability across all algorithms.
The `BenchmarkMetrics` dataclass enforces a fixed schema that all algorithms share.

## DD-038: Separate Artifact Writing

The `BenchmarkReporter` is separate from `BenchmarkRunner`. This allows artifact formats
to change without modifying benchmark execution logic, and allows results to be
re-exported in different formats after the fact. The reporter writes five standard files
per run: benchmark_summary.csv, routing_results.csv, verification_report.csv,
metadata.json, configuration_snapshot.yaml.

## DD-039: Optional Memory Collection

Memory collection via `tracemalloc` is disabled by default because it adds overhead and
may perturb timing measurements. It can be enabled for specific memory profiling runs
via `BenchmarkConfig.collect_memory`. This ensures timing benchmarks are not distorted
by profiling infrastructure.

## DD-040: Verification During Benchmark

When `verify_routes=True` (the default), every route is verified immediately after
computation by the `BenchmarkRunner`. Any verification failure is recorded in the
`verification_report.csv` output. This catches implementation bugs early and ensures
data integrity before downstream analysis.

## DD-041: Heuristic Protocol for A*

A* separates heuristic logic from search logic via the `Heuristic` Protocol. This
allows:
- Heuristics to be independently tested, validated, and swapped.
- The search algorithm to work with any heuristic that satisfies the Protocol.
- Configuration-driven heuristic selection via `HeuristicFactory`.
- Future heuristics (e.g., landmark-based, ALT) to be added without modifying A*.
- The `ZeroHeuristic` to trivially verify A* equivalence with Dijkstra.

The alternative (hard-coding Euclidean distance inside A*) was rejected because it
would couple search and heuristic logic, preventing the ZeroHeuristic equivalence
check and making heuristic validation impossible without modifying the algorithm.

## DD-042: HeuristicFactory and HeuristicValidator as Separate Components

`HeuristicFactory` and `HeuristicValidator` are separate from both the Heuristic
Protocol and AStarRouting. This is intentional:
- `HeuristicFactory` provides a configuration entry point (YAML → heuristic instance).
- `HeuristicValidator` provides research-grade verification (admissibility proof checks).
- Neither imports AStarRouting; they operate only on the Heuristic Protocol.
- A new heuristic can be added, tested, validated, and used without touching A*.

This separation mirrors the existing design pattern: `RoutingFactory` + `RouteValidator`
are separate from `DijkstraRouting`/`AStarRouting`.

## DD-043: A* Shares Dijkstra's Alternative-Path Strategy

A* generates alternative candidates using the same strategy as Dijkstra: iteratively
blocking edges along the primary route and re-running the search. This ensures:
- Both algorithms produce the same number and structure of candidates.
- The Decision Engine receives comparable candidate sets regardless of algorithm.
- No algorithm-specific advantage in candidate generation.

The shared strategy is implemented via `_find_route()` — a private method in both
algorithms that follows the same pattern (priority queue → edge blocking → repeat).
The common logic is not extracted into a shared base class because the search
procedures differ (g-only vs. f = g + h) and a shared abstraction would add
complexity without clear benefit for only two algorithms.

## DD-044: Common Swarm Protocol for All Swarm Algorithms

ACO, BCO, and PSO share a `SwarmAlgorithm` Protocol with a single `optimize()`
method. This is preferred over three unrelated implementations because:
- Common lifecycle (Initialize → Observe → Evaluate → Update → Generate → Repeat)
  is captured once in the framework, not duplicated across algorithms.
- Termination, statistics, randomness, and validation are algorithm-independent
  components shared by all algorithms.
- A new swarm algorithm needs only to implement the Protocol — no framework
  modifications required.
- Benchmark fairness is guaranteed because all algorithms operate under identical
  infrastructure (same termination limits, same statistics, same validation).

The alternative (three independent implementations) was rejected because it would
lead to code duplication, inconsistent termination logic, and subtle differences
in statistics collection that would compromise benchmark fairness.

## DD-045: SwarmToRoutingAdapter Rather Than Direct RoutingAlgorithm

Swarm algorithms are exposed to the routing layer through `SwarmToRoutingAdapter`,
not by implementing `RoutingAlgorithm` directly. This is intentional because:
- Swarm algorithms are fundamentally iterative optimizers, not single-pass
  routing algorithms. The `optimize()` interface better represents their nature.
- The adapter converts `SwarmResult` → `RoutingResult` without swarm algorithms
  needing to know about `RoutingContext`, `RoutingStatistics`, or `Route`.
- The same adapter can be reused when integrating with SUMO or visualization tools.
- Swarm algorithms remain usable independently of the routing framework if needed
  for ablation studies or hyperparameter tuning.

A direct `RoutingAlgorithm` implementation would force swarm algorithms to pretend
they are single-pass algorithms, leaking iteration logic into `compute_route()`.

## DD-046: Named Random Sub-Streams for Swarm Determinism

`SwarmRandom` provides named sub-streams (`get_stream("aco.ant_selection")`) rather
than sharing one `random.Random` instance across all stochastic components. This
prevents cross-component interference:
- Adding a new stochastic component does not change random sequences of existing
  components (critical for reproducibility during development).
- Each component's behavior can be tested in isolation with a known seed.
- Bug reproduction is easier: the failing stream name identifies exactly which
  stochastic decision caused the issue.

The alternative (one shared `random.Random` instance) was rejected because adding
or removing a random call anywhere in the algorithm would change all subsequent
random sequences, making debugging and regression testing unreliable.
