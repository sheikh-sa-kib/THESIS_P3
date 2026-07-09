# Development Log

---

## Phase 1 (Complete)

Initial infrastructure phase:

- Project skeleton with `pyproject.toml`, editable install, `src/e3hybrid/`
  package structure.
- Configuration schema foundation: `ProjectConfig`, `ExperimentConfig`,
  `SimulationConfig`, `LoggingConfig`, `DocumentationConfig`.
- Logging setup with rotating file handler and ANSI-colored console output.
- Reproducibility utilities: `collect_environment_metadata`, `SeededRandomFactory`.
- CLI entry points: `e3hybrid validate-config`, `e3hybrid write-metadata`.
- Test framework: pytest, pytest-cov, mypy (strict), ruff, pre-commit.
- Research documentation framework: `docs/` scaffold with architecture, design
  decisions, algorithm notes, literature mapping, assumptions, experiment
  protocol, API reference, and development log.

Mandatory infrastructure improvements after Phase 1 approval:

- Added MIT license, `.editorconfig`, `.pre-commit-config.yaml`, coverage
  reporting, `VERSION` file.
- Centralized exception hierarchy: `E3HybridError`, `ConfigError`,
  `NetworkError`, `SimulationError`, `RoutingError`, `CommunicationError`,
  `EmergencyError`, `ExperimentError`, `ReproducibilityError`.
- Stricter configuration validation (rejects unknown keys, parent-traversal
  paths, negative integers, invalid enums).
- Expanded reproducibility metadata (git commit, CPU count, Python executable,
  OS release, installed packages).

---

## Phase 2 (Complete, approved with final review)

Road network core:

- Added simulator-agnostic directed graph representation (`DirectedGraph`).
- Added node model (`Node`): node_id, x, y, metadata.
- Added edge model (`Edge`): edge_id, source, target, length_m, speed_limit_mps,
  lane_count, state, metadata.
- Added mutable edge state model (`MutableEdgeState`, backward-compat alias
  `EdgeDynamicAttributes`): is_blocked, current_speed_mps,
  travel_time_override_s, congestion_factor, hazard_penalty_s,
  emergency_penalty_s, communication_penalty_s, metadata.
- Added cost-provider interface (`CostProvider` Protocol) and implementations:
  `DistanceCostProvider`, `TravelTimeCostProvider`.
- Added graph validation (`GraphValidator`, `GraphValidationReport`): detects
  duplicate IDs, self-loops, disconnected edges, invalid references, negative
  lengths, negative speed limits, negative capacities, isolated nodes (warning),
  duplicate adjacency entries.
- Added versioned serialization envelope: schema_version, created_at, metadata,
  validation_status, nodes, edges.
- Added internal synthetic test network fixture for unit tests only
  (`create_synthetic_test_network`).

Phase 2 final review changes:

- **Separated immutable/mutable edge attributes**: renamed
  `EdgeDynamicAttributes` to `MutableEdgeState` (with backward-compat alias
  retained). `Edge` now has immutable fields (edge_id, source, target, length_m,
  speed_limit_mps, lane_count) and one mutable slot (`state: MutableEdgeState`).
  Mutation is only via `DirectedGraph.update_edge_state(edge_id, new_state)` or
  the functional copy `edge.with_state(new_state)`.
- **Strengthened graph validation**: added self-loop detection (with
  `allow_self_loops` flag), isolated-node warnings, duplicate-adjacency checks.
- **Versioned serialization**: `to_dict()` now returns an envelope with
  `schema_version`, `created_at`, `metadata`, `validation_status`.
  `from_dict()` rejects future schema versions and accepts legacy graphs.
- **Cost-provider interface verified**: routing algorithms depend only on
  `CostProvider` Protocol; no direct edge-field access. Added
  `DistanceCostProvider` as a pure baseline.
- **Performance documentation**: recorded Big-O complexity for all graph
  operations, explained space trade-offs (adjacency lists vs matrix).
- **Architecture documentation**: comprehensive graph model documentation with
  diagrams, invariants, complexity analysis, and phase roadmap.

---

## Phase 3 (Complete, approved)

EV domain model — Stage 1 (architecture only; Fiori equations deferred):

- Added `VehicleId` NewType.
- Added `VehicleConstraints` (min/max SoC, max speed, max payload).
- Added `VehicleState` (current node/edge, SoC, speed, acceleration,
  distance, time, charging flag).
- Added `Battery` Protocol and `SimpleBattery` (linear capacity, no
  degradation). Operations: `discharge`, `charge`, `can_discharge`,
  `clone_with_soc`.
- Added `EnergyModel` Protocol with `compute_energy_kwh` interface designed
  for SUMO compatibility (speed, distance, acceleration, grade, duration args).
- Added `FioriEnergyModel` stub: validates all parameters, raises
  `NotImplementedError` for `compute_energy_kwh` until equations are approved.
  Full parameter documentation and SUMO integration plan in
  `docs/energy_model_design.md`.
- Added `ElectricVehicle` entity: dependency-injected battery and energy model,
  immutable state transitions, `traverse_edge`, `update_state`, `to_state_dict`.
- Added `VehicleFactory`: creates vehicles from YAML-compatible config dicts.
- Added `VehicleValidator` and `VehicleValidationReport`.
- Added `VehicleError` to centralized exception hierarchy.
- Added comprehensive unit tests.
- Added `docs/energy_model_design.md`: full technical design doc for Fiori
  equations, parameter inventory, data source mapping, YAML config example,
  computational analysis, validation strategy, limitations, extension strategy.

**Deferred:** Concrete Fiori energy equations — implementation proceeds only
after explicit approval of the design document. The energy model is a
supporting subsystem; the primary thesis contribution is decentralized
swarm routing.

---

## Phase 4 (Complete, awaiting approval)

Communication framework — architecture and infrastructure only:

- Added `src/e3hybrid/communication/` module.
- Added `MessageId` NewType and `DeliveryStatus` enum (`PENDING`, `DELIVERED`,
  `DROPPED`, `EXPIRED`, `OUT_OF_RANGE`).
- Added `MessageType` StrEnum: 13 types covering traffic, emergency, swarm
  coordination (ACO pheromones, BCO scouts, PSO vehicle state), and operational
  messages (heartbeat, acknowledgement). Extensible via `CUSTOM`.
- Added `Priority` IntEnum: `LOW`, `NORMAL`, `HIGH`, `CRITICAL`.
- Added `Message` (frozen dataclass): all required fields including message_id,
  sender_id, receiver_id, is_broadcast, created_at_s, ttl_s, priority, payload,
  hop_count, max_hops, delivery_status. Immutable copy-on-update transitions:
  `with_status`, `with_incremented_hop`. Factory: `Message.create`.
- Added `Packet` (frozen dataclass): wraps Message with transmission metadata
  (packet_id, transmitted_at_s, latency_s, delivery_status, is_relay,
  distance_m). Derived: `arrival_time_s`. Factory: `Packet.create`.
- Added `PacketLossModel`, `LatencyModel`, `CommunicationRadiusModel`,
  `CommunicationProtocol` as `typing.Protocol` interfaces.
- Added baseline implementations: `NoLossModel`, `ZeroLatencyModel`,
  `ConstantLatencyModel`, `InfiniteRadiusModel`, `FixedRadiusModel`
  (disk model with position injection), `DeterministicProtocol`.
- Added `MessageBus`: registration, broadcast/unicast delivery, TTL expiry,
  duplicate-id rejection, latency application, packet logging, `tick(t)` API.
- Added `Broadcaster` and `Receiver` as the only agent injection boundaries.
- Added `CommunicationStatistics`: messages_sent, delivered, dropped, expired,
  out_of_range, broadcast/unicast counts, average latency, delivery ratio.
- Added comprehensive unit tests (60+ cases).
- Added `docs/communication_architecture.md`: class diagrams, message lifecycle
  state machine, swarm/emergency/V2V/V2X/SUMO integration sections.


---

## Phase 5 (Complete, awaiting approval)

Emergency framework — no routing, swarm, SUMO, or vehicle movement:

- Added `EmergencyEventType` StrEnum (7 Phase 5 types + 5 reserved future types).
- Added `EventStatus` StrEnum (CREATED → SCHEDULED → ACTIVATED → BROADCAST →
  OBSERVED → HANDLED → RESOLVED/EXPIRED). Forward-only transitions enforced.
- Added `EventLocation` frozen dataclass (edge_ids, center_node, radius_m).
- Added `EmergencyEvent` Protocol + `BaseEmergencyEvent` shared mixin.
- Added 7 concrete event classes: `RoadClosureEvent`, `RoadBlockEvent`,
  `TrafficAccidentEvent`, `EmergencyVehicleEvent`, `InfrastructureFailureEvent`,
  `CommunicationBlackoutEvent`, `HazardZoneEvent`.
- Added `NetworkEffect` Protocol and 5 concrete effects: `RoadClosureEffect`,
  `CongestionEffect`, `HazardEffect`, `EmergencyPriorityEffect`,
  `CommunicationEffect`. Each records `event_id` ownership for ref-counted
  resolution cleanup.
- Added `EmergencyState` — tracks active effects per edge with additive
  composition (Decision 1); full recompute on event resolution (Decision 2).
  Blocked edges take unconditional precedence.
- Added `EmergencyEventBus` with typed subscribe/subscribe_all/unsubscribe,
  priority ordering (stable sort descending), exception isolation, delivery
  statistics, and `clear()` for between-run resets.
- Added `EmergencyRegistry` — single source of truth for all events with
  duplicate-id rejection and validated forward-only status transitions.
- Added `EventScheduler` with four scheduling modes: fixed, random (seeded
  via `random.Random(seed)`), recurring (expansion lazy on tick), progressive.
  All random modes are deterministic given same seed.
- Added `ScenarioLoader` + `ScenarioMetadata` — YAML → concrete event objects,
  dispatched to scheduler. Supports all event types and all scheduling modes.
- Added `validate_scenario_dict()` — 15 hard-error validation rules with
  descriptive error messages.
- Added `NetworkEffectSubscriber` — the ONLY module that calls
  `DirectedGraph.update_edge_state`. Emergency framework never imports the graph.
- Added `EmergencyError` to centralized exception hierarchy.
- Decision 3 honoured: `CommunicationBlackoutEvent` only sets
  `communication_penalty_s` via `CommunicationEffect`; never touches `MessageBus`.
- Decision 4 honoured: `EmergencyVehicleEvent` only publishes corridor request;
  no routing logic anywhere in the emergency module.
- 70+ comprehensive unit tests covering all requirements.

---

## Phase 6 (Complete, approved)

Decision Engine implementation:

- Added `DecisionType` StrEnum with 9 Phase 6 types and 2 reserved future types.
- Added `DecisionId` and `RouteId` NewTypes.
- Added `Decision` frozen dataclass: decision_id, vehicle_id, sim_time_s,
  decision_type, trigger, explanation (mandatory), winning_policy, applied_policies,
  veto, confidence, payload, all_recommendations. Factory: `Decision.create`.
- Added `VehicleObservation` frozen snapshot: vehicle_id, sim_time_s, vehicle_state,
  battery, constraints, graph_snapshot, routing_candidates, current_route,
  inbox_messages, active_events.
- Added `GraphSnapshot` neighbourhood-scoped graph view: current_edge,
  neighbour_edges, blocked_edge_ids. Methods: `is_blocked`, `get_edge`.
- Added `EdgeSnapshot`, `BatterySnapshot`, `RouteSnapshot` for scoped observations.
- Added `ObservationAssembler` — builds observations from subsystem state with
  BFS-based neighbour collection.
- Added `DecisionPolicy` Protocol with `name`, `enabled`, `evaluate` interface.
- Added `PolicyRecommendation` frozen dataclass: decision_type, priority [0,100],
  confidence [0.0,1.0], explanation (mandatory), policy_name, veto, payload.
- Added `DecisionAggregationPolicy` — selects winning recommendation with veto
  precedence, priority ordering, confidence tiebreaker.
- Implemented 6 concrete policies:
  - `SafetyPolicy` (priority 100): blocked edges, speed violations with veto.
  - `EmergencyPolicy` (priority 90): emergency vehicle events, road closures.
  - `BatteryPolicy` (priority 70-95): SoC thresholds with emergency stop/wait/speed.
  - `CongestionPolicy` (priority 60): congestion and hazard penalties.
  - `CommunicationPolicy` (priority 50): broadcast decisions for closures/hazards.
  - `RoutingCandidatePolicy` (priority 40): candidate route evaluation on cost only.
- Added `PolicyRegistry` and `PolicyManager` for policy lifecycle management.
- Added `register_all_policies()` to auto-register all Phase 6 policies.
- Added `DecisionEngine` with tick-based evaluation: evaluate policies → aggregate
  → validate → log → return decision.
- Added `DecisionLog` with CSV-based immediate writes (no buffering).
- Added `DecisionValidator` with comprehensive validation rules.
- Added `DecisionConfig` and all policy-specific config dataclasses with YAML loading.
- Added `RouteCandidate` frozen dataclass and `RouteCandidateSource` Protocol.
- Added `NullRouteCandidateSource` as Phase 6 placeholder.
- Added comprehensive unit tests (50+ cases): engine, validation, logging,
  policy registry, observation assembler, aggregation.
- Updated documentation: architecture.md, api_reference.md, development_log.md,
  design_decisions.md.

Approved design decisions honoured:
- Decision 1: Evaluate once per simulation tick (not continuous).
- Decision 2: GraphSnapshot abstraction (never receive full graph).
- Decision 3: No candidate pre-filtering (all algorithms submit full sets).
- Decision 4: Decision logging enabled for every simulation, immediate CSV writes.
- Decision Engine completely unaware of routing algorithm (evaluates objective values only).
- All decisions/recommendations/observations immutable (frozen dataclasses).
- Mandatory explanation field on every decision for debugging and thesis screenshots.

---

## Phase 7A (Design document complete, awaiting approval)

Routing architecture design document produced. No implementation yet.

Key design decisions documented:
- Pure function requirement: all routing algorithms must be pure functions (identical inputs → identical outputs).
- Common routing interface: `RoutingAlgorithm` Protocol with `compute_route()` as the ONLY method.
- Identical inputs/outputs: every algorithm receives `RoutingRequest` + `RoutingContext`, returns `RoutingResult`.
- Fair comparison: same graph, same requests, same seed, same scenarios, same hardware, same metrics.
- Modular cost architecture: `CostProvider` Protocol with independently configurable components (distance, time, energy, congestion, hazard, emergency, communication).
- Algorithm-agnostic `RouteCandidate`: Decision Engine evaluates ONLY on `total_cost`.
- Routing layer never modifies graph or vehicles: read-only through `GraphSnapshot` and `CostProvider`.
- Separation of routing and decision making: routing computes paths, Decision Engine evaluates recommendations.
- Caching and incremental routing designed but implementation deferred to Phase 7B+.
- Baseline algorithms planned: SUMO Baseline, Dijkstra, A*.
- Swarm algorithms planned: ACO (Phase 9), BCO (Phase 10), PSO (Phase 11).
- Hybrid algorithm planned: E³-Hybrid integrates ACO, BCO, PSO with Decision Engine (Phase 12).
- Performance analysis documented: time/space complexity, scalability, parallelization opportunities.
- Testing strategy documented: correctness, optimality, edge cases, performance, deterministic replay.
- No unresolved architectural questions.

Documentation updated:
- `docs/routing_architecture_design.md` — complete 18-section design document
- `docs/architecture.md` — Phase 7A marked as complete (awaiting approval)
- `docs/api_reference.md` — Phase 7A planned interfaces documented
- `docs/design_decisions.md` — DD-028 through DD-035 added

---

## Phase 7B (Complete, approved)

Baseline routing implementation — Dijkstra algorithm and routing framework:

- Added `src/e3hybrid/routing/` module with 12 components:
  - `RoutingAlgorithm` Protocol — single `compute_route(request, context) -> RoutingResult` interface.
  - `RoutingRequest` — frozen dataclass: source, destination, vehicle_id, constraints, battery, max_candidates, timeout, metadata.
  - `RoutingContext` — frozen dataclass: graph_snapshot, cost_provider, config, random_stream, sim_time_s.
  - `RoutingResult` — frozen dataclass: candidates, primary_route, success, failure_reason, statistics, runtime_s.
  - `Route` — frozen dataclass: route_id, node_sequence, edge_sequence, total_distance_m, estimated_travel_time_s, estimated_energy_kwh.
  - `RouteSegment` — frozen dataclass: edge_id, source, target, distance_m, travel_time_s, energy_kwh, cost.
  - `RouteCost` — frozen dataclass: total with breakdown (distance, time, energy, congestion, hazard, emergency, communication).
  - `RouteCandidate` — frozen dataclass: total_cost, cost_breakdown, algorithm, runtime_s, search_statistics.
  - `RoutingStatistics` — frozen dataclass: nodes_explored, edges_explored, candidates_generated, cache_hits, cache_misses, memory_bytes.
  - `RouteValidator` — validates connectivity, no blocked edges, cost consistency, battery feasibility.
  - `RoutingException` hierarchy — `RoutingError`, `NoPathFoundError`, `InvalidRequestError`, `RoutingTimeoutError`, `ConfigurationError`.
  - `RoutingFactory` — creates algorithms from config strings with validation.
- Added `CompositeCostCalculator` — weighted sum of cost components with `CostWeights` config.
- Added `DijkstraRouting` — heap-based priority queue implementation:
  - Standard Dijkstra with `CostProvider`-mediated edge costs.
  - Alternative-path generation by blocking primary route edges iteratively.
  - Timeout support with graceful failure.
  - Proper `RoutingStatistics` collection (nodes/edges explored, candidates).
  - Deterministic — identical inputs produce identical outputs.
- Added `SearchStatistics` — frozen dataclass: iterations, convergence, diversity (for swarm algorithms).
- Added exception hierarchy in `exceptions.py`: `RoutingError`, `NoPathFoundError`, `InvalidRequestError`, `RoutingTimeoutError`, `ConfigurationError`.
- Added `CostWeights` and `RoutingAlgorithmConfig` configuration dataclasses.
- Added `RouteCache` (design only, implementation deferred) and `CacheKey` dataclass.
- Added comprehensive unit tests (18 tests): simple graphs, alternative paths, blocked edges, no-path, unreachable destinations, single-node graph, disconnected graph, zero-length edges, multiple equal-cost routes, cycles, determinism, cost correctness, statistics reporting.
- All 18 tests pass. Dijkstra implementation achieves 91% code coverage.
- Documentation updated:
  - `docs/api_reference.md` — Phase 7B interfaces marked as implemented
  - `docs/architecture.md` — Phase 7B marked as approved
  - `docs/research_documentation.md` — Phase 7B status updated

---

## Phase 7C (Complete, approved)

Routing benchmark and verification framework:

- Added `RoutingVerifier` — algorithm-independent verification utilities:
  - `verify_route(route, graph)` — 8 checks: node sequence, edge connectivity, blocked edges, distance consistency, request matching.
  - `verify_result(result, graph)` — 5 checks: success/failure invariants, runtime, statistics, candidates, primary route.
  - `verify_candidate(candidate, graph)` — 8 checks: node/edge validity, connectivity, cost, algorithm name, request matching.
  - `verify_graph_integrity(graph)` — 4 checks: outgoing/incoming adjacency, edge references, source/target existence.
  - `verify_deterministic_replay(algorithm, request, graph)` — consistency checks across N runs.
  - `verify_cost_breakdown(candidate)` — validates cost_breakdown.total vs total_cost and component sum.
  - Compute helpers: `compute_expected_distance`, `compute_expected_travel_time`, `compute_expected_cost`.
- Added `VerificationReport`, `VerificationError`, `DeterministicReplayReport` dataclasses.
- Added 10 benchmark components:
  - `BenchmarkConfig` — configuration dataclass (algorithm_names, timeout, seed, cost_weights, etc.).
  - `BenchmarkScenario` — bundles a graph with routing requests.
  - `BenchmarkRequest` — single routing request with description and expected_success.
  - `BenchmarkMetrics` — per-request metrics: runtime, nodes, distance, cost, validity, success.
  - `AlgorithmMetadata` — name, version, description, parameters.
  - `BenchmarkResult` — complete result with metrics, verification reports, summary.
  - `BenchmarkSummary` — aggregate statistics across all requests.
  - `BenchmarkValidator` — validates configs, scenarios, metrics, and results.
  - `BenchmarkReporter` — writes benchmark_summary.csv, routing_results.csv, verification_report.csv, metadata.json, configuration_snapshot.yaml.
  - `BenchmarkRunner` — orchestrates lifecycle: validate → execute → verify → collect metrics → summarize.
- Fairness guarantees: same graph, requests, seed, cost provider, config, timeout, graph state for all algorithms.
- Added 53 comprehensive unit tests covering all components, verification edge cases, CSV/JSON/YAML generation, runner lifecycle, deterministic replay.
- New files: 8 source files in `src/e3hybrid/routing/`, 1 test file, 1 design document.
- Updated `docs/architecture.md` — Phase 7C marked as complete.
- Updated `docs/research_documentation.md` — Phase 7C status recorded.
- Created `docs/routing_benchmark_design.md` — full design document for the benchmark framework.

---

## Phase 7D (Complete, verified)

A* baseline routing with heuristic architecture:

- Added `Heuristic` Protocol — single-method interface (`estimate(source, destination, graph) -> float`) with `name` property.
- Added 3 heuristic implementations:
  - `ZeroHeuristic` — always returns 0.0 (A* degenerates to Dijkstra; verified by test suite).
  - `EuclideanHeuristic` — straight-line distance with configurable `scale` factor.
  - `ManhattanHeuristic` — grid distance with configurable `scale` factor.
- Added `HeuristicFactory` — creates heuristics by name (`"zero"`, `"euclidean"`, `"manhattan"`) with keyword arguments.
- Added `HeuristicValidator` — checks admissibility (`h(n) ≤ true cost`) and consistency (`h(n) ≤ c(n,n') + h(n')`) with `HeuristicValidationReport`.
- Added `AStarRouting` — heap-based priority queue A* search:
  - Accepts optional `heuristic` parameter (default `ZeroHeuristic()`).
  - Uses same `CostProvider`-mediated edge costs as Dijkstra.
  - Same timeout, blocked-edge, cycle, and disconnected-graph handling as Dijkstra.
  - Same alternative-path candidate generation strategy as Dijkstra.
  - Same `RoutingStatistics` collection (nodes_explored, edges_explored, candidates_generated).
  - Deterministic with tie-breaking.
- Updated `factory.py`: `create_astar(heuristic_name)` and `astar/heuristic_name` prefix syntax.
- Updated `__init__.py`: exports `AStarRouting`, all heuristics, `HeuristicFactory`, `HeuristicValidator`.
- Written 73 comprehensive tests:
  - Heuristic unit tests (18): correctness, scale factor, edge cases, zero-coordinate nodes.
  - HeuristicFactory tests (7): create by name, unknown name, factory with kwargs.
  - HeuristicValidator tests (6): admissibility, consistency, empty graph, missing coordinates.
  - A* basic correctness (9): simple graph, alternative paths, grid, blocked edges, no-path.
  - A* edge cases (14): disconnected graph, cycles, timeout, determinism, single-node, zero-length.
  - Heuristic-specific tests (4): Euclidean grid routing, Manhattan grid routing, same cost, fewer nodes.
  - Dijkstra comparison tests (9): same cost, same path length, same validity, algorithm-agnostic engine.
  - BenchmarkRunner integration (3): runs A* without modification, algorithm-agnostic.
  - ZeroHeuristic equivalence (3): identical route, cost, and statistics as Dijkstra.
- All 135 tests pass (A*: 73, Dijkstra: 18, Benchmark: 53).
- A* achieves 93% code coverage (astar.py).
- Documentation updated:
  - `docs/astar_algorithm_design.md` — full design document created
  - `docs/architecture.md` — Phase 7D marked as complete
  - `docs/api_reference.md` — Phase 7D interfaces documented
  - `docs/routing_architecture_design.md` — A* section updated with heuristic architecture
   - `docs/design_decisions.md` — DD-041 through DD-043 added

---

## Phase 8A (Design document approved)

Common swarm architecture design:
- Created `docs/swarm_architecture_design.md` — complete 12-section design document covering research motivation, common architecture, lifecycle, shared data structures, randomness, termination, benchmark fairness, statistics, extension strategy, routing relationship, testing strategy, and open questions.
- Documentation updated: architecture.md, api_reference.md, development_log.md, design_decisions.md (DD-044 through DD-046), research_documentation.md.

---

## Phase 8B (Complete, awaiting approval)

Common swarm infrastructure implementation:

- Created `src/e3hybrid/swarm/` package with 14 source files:
  - `protocol.py` — `SwarmAlgorithm` Protocol with single `optimize()` method
  - `context.py` — `SwarmContext` (frozen dataclass: cost_weights, config, random_seed, routing_request, sim_time_s)
  - `config.py` — `SwarmConfig` (frozen dataclass with validation: population_size, max_iterations, time_limit_s, convergence_threshold, stall_limit, target_score, seed, hyperparameters, cost_weights)
  - `models.py` — `Solution`, `CandidateSolution`, `OptimizationScore`, `SearchState`, `Population` (all frozen, with validation)
  - `state.py` — `SwarmState` (iteration, population, best_solution, internal_state)
  - `statistics.py` — `SwarmStatistics` (run-level) and `IterationStatistics` (per-iteration)
  - `result.py` — `SwarmResult` (best_solution as RouteCandidate, candidates, statistics, iterations, success, failure_reason)
  - `random.py` — `SwarmRandom` (deterministic named sub-streams, no direct random() calls)
  - `termination.py` — `TerminationCondition` and `TerminationChecker` (max iterations, time limit, target score, convergence, no improvement)
  - `lifecycle.py` — `SwarmLifecycle` (common iteration loop with callbacks for algorithm-specific initialize/update)
  - `validator.py` — `SwarmValidator` and `SwarmValidationReport` (algorithm-independent config/state/result/population validation)
  - `factory.py` — `SwarmFactory` (runtime registration, creation by name, clear_registry for testing)
  - `adapter.py` — `SwarmToRoutingAdapter` (converts SwarmResult → RoutingResult for BenchmarkRunner compatibility)
  - `__init__.py` — exports all public API symbols
- Written 99 comprehensive unit tests covering all components
- All 99 tests pass
- All 135 existing routing tests still pass (234 total)
- No references to ACO, BCO, PSO, or E³-Hybrid anywhere in the framework
- Documentation updated:
  - `docs/swarm_infrastructure_design.md` — created with implementation details
  - `docs/architecture.md` — Phase 8B marked as complete (awaiting approval)
  - `docs/api_reference.md` — Phase 8B interfaces documented as implemented
  - `docs/research_documentation.md` — Phase 8B status recorded

---

## Phase 9A (Design approved)

ACO algorithm design:
- Created `docs/aco_algorithm_design.md` — complete 15-section design document covering research motivation, literature review (ACS selected), architecture integration, state model, transition rule mathematics, pheromone updates, termination, YAML configuration, determinism, emergency behaviour, complexity analysis, testing strategy, benchmark plan, limitations, and open questions.
- Created `docs/literature_traceability.md` — maps every algorithm/equation/model to original academic source (Dijkstra 1959, Hart et al. 1968, Dorigo & Gambardella 1997, Teodorović & Dell'Orco 2005, Kennedy & Eberhart 1995, Fiori et al. 2016, Williams 1964, Matsumoto & Nishimura 1998).
- Updated `docs/routing_architecture_design.md` — A* section updated with heuristic architecture.

---

## Phase 9B (Complete)

Ant Colony System (ACS) implementation:

### Infrastructure Changes
- **`src/e3hybrid/swarm/context.py`** — Added `graph` (DirectedGraph) and `cost_calculator` (CompositeCostCalculator) fields for read-only graph access.
- **`src/e3hybrid/swarm/adapter.py`** — `compute_route(request, graph=None)` now accepts graph parameter and builds SwarmContext with graph and cost_calculator.
- **`src/e3hybrid/routing/factory.py`** — Added `create_aco()` for SwarmToRoutingAdapter-wrapped ACORouting registration.

### ACO Implementation (`src/e3hybrid/swarm/aco.py`)
Created a complete ACS implementation with 11 classes:
- **`ACSConfiguration`** — frozen dataclass with all 9 hyperparameters (alpha, beta, rho, q0, tau0, tau_min, tau_max, elitism, candidate_list_size), validated against literature ranges, with `from_swarm_config()` factory.
- **`PheromoneMatrix`** — sparse O(E) pheromone storage with [tau_min, tau_max] bounds clamping, NaN/inf protection, decay/reinforce operations, and clone() for deterministic replay checks.
- **`VisibilityMatrix`** — static heuristic desirability eta = 1/(cost + EPS). Blocked edges get eta = 0. Supports candidate list truncation.
- **`TransitionRule`** — ACS pseudorandom proportional rule with q0 exploitation/exploration balance. Argmax for exploitation, roulette-wheel for exploration. Fallback to uniform when all weights zero.
- **`PheromoneUpdater`** — local update (after each ant step) and global update (best-so-far ant only, after each iteration). Elite ant reinforcement with reduced decay rate.
- **`Ant`** — mutable per-ant state: current node, visited set, node/edge sequences, cost, completion/feasibility flags.
- **`AntColony`** — manages ant population, route construction (with tabu-based cycle prevention), population evaluation, and diversity computation.
- **`ACOStatistics`** — frozen dataclass with ACO-specific metrics (best cost, colony averages, convergence iteration, diversity/score histories).
- **`ACOValidator`** — validates ACS config (all hyperparameter ranges) and context (graph/cost_calculator presence).
- **`ACOFactory`** — creates ACORouting from config or SwarmConfig.
- **`ACORouting`** — main SwarmAlgorithm implementation. Uses SwarmRandom named streams ("aco.selection", "aco.roulette"), SwarmLifecycle-compatible iteration loop, and produces SwarmResult with RouteCandidate.

### Numerical Stability Safeguards
- EPS = 1e-10 prevents division by zero in visibility computation
- Pheromone bounds prevent underflow/overflow/inf/nan propagation
- Max steps = 2× node count prevents infinite loops (cycle-safe)
- Tabu list prevents revisiting nodes in same route
- Penalty cost (1e9) for ants that fail to reach destination
- Fallback uniform selection when all weights are zero

### Determinism
- All randomness from SwarmRandom named streams: `aco.selection` (q vs q0), `aco.roulette` (roulette wheel)
- Same seed → identical routes and statistics (verified by deterministic replay tests)
- Different seeds → reproducible differences

### Testing
- Created `tests/unit/test_aco.py` with 98 comprehensive tests:
  - ACSConfiguration tests (14): defaults, validation, from_swarm_config, immutability
  - PheromoneMatrix tests (10): initialization, bounds clamping, NaN/inf, decay, reinforce, clone
  - VisibilityMatrix tests (6): cost-derived visibility, blocked edges, candidate list truncation
  - TransitionRule tests (5): empty list, q0 exploitation, alpha=0, beta=0, all-zero weights
  - PheromoneUpdater tests (5): local decay, global reinforce, zero/inf cost, elite update
  - Ant tests (2): create, reset
  - AntColony tests (5): population init, route construction, evaluation, diversity
  - ACOValidator tests (6): valid config, invalid alpha/beta/rho, context validation
  - ACOFactory tests (3): create default, with config, from swarm_config
  - ACORouting integration tests (6): linear/diamond/grid graph, no-graph failure
  - Deterministic replay tests (3): same seed, different seed, 5-run consistency
  - Edge-case tests (8): unreachable, single node, all blocked, single edge, cycles, large alpha, q0=0
  - Property tests (5): non-increasing best score, pheromone bounds, solution validity, cost non-negative, diversity range
  - Stress tests (1): 20-node random graph
  - Benchmark regression tests (4): ACO vs Dijkstra cost ratio, adapter integration, factory integration, default config

### Verification
- All 98 ACO tests pass
- All 99 existing swarm infrastructure tests pass
- All 37 existing Dijkstra tests pass
- Total: 234 tests passing (not counting pre-existing A* timeout failure)

### Documentation updated
- `docs/architecture.md` — Phase 9B marked as complete
- `docs/api_reference.md` — Phase 9B interfaces documented
- `docs/development_log.md` — this entry
- `docs/algorithm_notes.md` — ACO implementation status
- `docs/literature_traceability.md` — ACO entry updated to "implemented"
