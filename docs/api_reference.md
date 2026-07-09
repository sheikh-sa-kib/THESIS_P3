# API Reference

This document provides human-maintained API notes during early development.

Generated API documentation can be added later after public interfaces stabilize.

---

## Phase 1 Public Interfaces

### Configuration

- **`e3hybrid.config.ProjectConfig`**  
  Validated project configuration dataclass (experiment, simulation, logging,
  documentation sections).

- **`e3hybrid.config.load_project_config(path: Path) -> ProjectConfig`**  
  Load and validate a YAML configuration file.

### Logging

- **`e3hybrid.utils.logging.configure_logging(level, log_dir, max_bytes, backup_count) -> Path`**  
  Set up rotating file and console handlers. Returns the log file path.

### Reproducibility

- **`e3hybrid.utils.reproducibility.collect_environment_metadata(project_root: Path, random_seed: int) -> EnvironmentMetadata`**  
  Collect Python version, OS, CPU, packages, git commit, timestamp, seed.

- **`e3hybrid.utils.reproducibility.write_environment_metadata(metadata: EnvironmentMetadata, path: Path) -> None`**  
  Write environment metadata to a JSON file.

- **`e3hybrid.utils.reproducibility.SeededRandomFactory`**  
  Factory for deterministic random streams derived from one base seed.
  
  - `create(stream_name: str) -> random.Random`  
    Return a deterministic random generator for a named stream.

---

## Phase 2 Public Interfaces

### Graph Entities

- **`e3hybrid.network.Node`**  
  Frozen dataclass: `node_id`, `x`, `y`, `metadata`.
  
  - `to_dict() -> dict`  
  - `from_dict(data: dict) -> Node`

- **`e3hybrid.network.Edge`**  
  Frozen dataclass: `edge_id`, `source`, `target`, `length_m`, `speed_limit_mps`,
  `lane_count`, `state: MutableEdgeState`, `metadata`.
  
  - **`effective_speed_mps`** (property) — returns `state.current_speed_mps` or
    falls back to `speed_limit_mps`.
  - **`with_state(state: MutableEdgeState) -> Edge`** — return a copy with
    updated state.
  - **`with_dynamic_attributes(dynamic: MutableEdgeState) -> Edge`** —
    backward-compatible alias for `with_state`.
  - **`dynamic`** (property) — backward-compatible alias for `state`.
  - `to_dict() -> dict`  
  - `from_dict(data: dict) -> Edge`

- **`e3hybrid.network.MutableEdgeState`**  
  Frozen dataclass: `is_blocked`, `current_speed_mps`, `travel_time_override_s`,
  `congestion_factor`, `hazard_penalty_s`, `emergency_penalty_s`,
  `communication_penalty_s`, `metadata`.
  
  - `to_dict() -> dict`  
  - `from_dict(data: dict) -> MutableEdgeState`

- **`e3hybrid.network.EdgeDynamicAttributes`**  
  Backward-compatible alias for `MutableEdgeState`. New code should use
  `MutableEdgeState`.

### Graph

- **`e3hybrid.network.DirectedGraph`**  
  Mutable directed graph of nodes and edges.
  
  - **`add_node(node: Node) -> None`** — raises `NetworkError` on duplicate
    node_id.
  - **`add_edge(edge: Edge) -> None`** — raises `NetworkError` on duplicate
    edge_id or missing source/target.
  - **`update_edge_state(edge_id: EdgeId, state: MutableEdgeState) -> None`** —
    replace mutable state without changing structural fields.
  - **`update_edge_dynamic_attributes(edge_id, dynamic)`** — backward-compatible
    alias for `update_edge_state`.
  - **`has_node(node_id: NodeId) -> bool`**
  - **`has_edge(edge_id: EdgeId) -> bool`**
  - **`get_node(node_id: NodeId) -> Node`** — raises `NetworkError` if absent.
  - **`get_edge(edge_id: EdgeId) -> Edge`** — raises `NetworkError` if absent.
  - **`nodes() -> tuple[Node, ...]`** — deterministic insertion order.
  - **`edges() -> tuple[Edge, ...]`** — deterministic insertion order.
  - **`outgoing_edges(node_id: NodeId) -> tuple[Edge, ...]`**
  - **`incoming_edges(node_id: NodeId) -> tuple[Edge, ...]`**
  - **`neighbors(node_id: NodeId) -> tuple[NodeId, ...]`** — target IDs of
    outgoing edges.
  - **`set_metadata(key: str, value: object) -> None`** — attach graph-level
    metadata.
  - **`get_metadata(key: str) -> object | None`**
  - **`to_dict(validation_status="unvalidated") -> dict`** — versioned envelope
    serialization.
  - **`from_dict(data: dict) -> DirectedGraph`** — rejects future schema_version.

- **`e3hybrid.network.CURRENT_SCHEMA_VERSION: int`**  
  Current serialization schema version (1).

### Cost Providers

- **`e3hybrid.network.CostProvider`** (Protocol)  
  Interface that all edge-cost providers must satisfy.
  
  - `cost(edge: Edge) -> EdgeCost`

- **`e3hybrid.network.EdgeCost`**  
  Frozen dataclass: `value`, `is_blocked`, `components: dict`.

- **`e3hybrid.network.DistanceCostProvider`**  
  Edge cost = `length_m` (blocked edges return `inf`).
  
  - `cost(edge: Edge) -> EdgeCost`

- **`e3hybrid.network.TravelTimeCostProvider`**  
  Edge cost = travel time in seconds, computed from length/speed, congestion,
  and all penalty fields.
  
  - `cost(edge: Edge) -> EdgeCost`

### Validation

- **`e3hybrid.network.GraphValidator`**  
  Validate structural consistency.
  
  - **`__init__(allow_self_loops=False)`**
  - **`validate(graph: DirectedGraph) -> GraphValidationReport`** — returns a
    report without raising.
  - **`validate_or_raise(graph: DirectedGraph) -> GraphValidationReport`** —
    raises `NetworkError` if validation fails; emits warnings to logger.

- **`e3hybrid.network.GraphValidationReport`**  
  Frozen dataclass: `node_count`, `edge_count`, `errors: tuple[str, ...]`,
  `warnings: tuple[str, ...]`.
  
  - **`is_valid`** (property) — True when no hard errors.
  - **`log_warnings() -> None`** — emit warnings to the framework logger.

---

## Phase 3 Public Interfaces

### Vehicle Entities

- **`e3hybrid.vehicle.VehicleConstraints`**  
  Frozen dataclass: `min_soc_kwh`, `max_soc_kwh`, `max_speed_mps`, `max_payload_kg`.  
  - `from_dict(data: dict) -> VehicleConstraints`  
  - `to_dict() -> dict`

- **`e3hybrid.vehicle.VehicleState`**  
  Frozen dataclass: `current_node`, `current_edge`, `soc_kwh`, `speed_mps`,  
  `acceleration_mps2`, `distance_travelled_m`, `time_elapsed_s`, `is_charging`.  
  - `to_dict() -> dict`

- **`e3hybrid.vehicle.ElectricVehicle`**  
  Mutable entity (copy-on-update): `vehicle_id`, `constraints`, `battery`, `state`, `energy_model`, `metadata`.  
  - **`soc_kwh`** (property)  
  - **`soc_fraction`** (property)  
  - **`is_below_min_soc`** (property)  
  - **`can_depart`** (property)  
  - **`traverse_edge(...) -> ElectricVehicle`** — delegates to energy model, returns updated copy.  
  - **`update_state(state: VehicleState) -> ElectricVehicle`** — SUMO sync path.  
  - `to_state_dict() -> dict`

### Battery

- **`e3hybrid.vehicle.Battery`** (Protocol)  
  - `capacity_kwh` (property)  
  - `soc_kwh` (property)  
  - `soc_fraction` (property)  
  - `discharge(delta_kwh: float) -> Battery`  
  - `charge(delta_kwh: float) -> Battery`  
  - `can_discharge(delta_kwh: float) -> bool`  
  - `clone_with_soc(soc_kwh: float) -> Battery`

- **`e3hybrid.vehicle.SimpleBattery`**  
  Linear capacity battery (no degradation/temperature).  
  - `create(capacity_kwh, initial_soc_kwh) -> SimpleBattery`

### Energy Model

- **`e3hybrid.vehicle.EnergyModel`** (Protocol)  
  - `compute_energy_kwh(speed_mps, distance_m, acceleration_mps2, grade, duration_s) -> float`

- **`e3hybrid.vehicle.FioriEnergyModel`**  
  Physics-based model stub (Fiori et al., 2016). Parameters validated at construction.  
  `compute_energy_kwh` raises `NotImplementedError` until equations are approved.

### Vehicle Factory and Validator

- **`e3hybrid.vehicle.VehicleFactory`**  
  - `create_from_config(vehicle_id, initial_node, config) -> ElectricVehicle`

- **`e3hybrid.vehicle.VehicleValidator`**  
  - `validate(vehicle: ElectricVehicle) -> VehicleValidationReport`  
  - `validate_or_raise(vehicle: ElectricVehicle) -> VehicleValidationReport`

- **`e3hybrid.vehicle.VehicleValidationReport`**  
  Frozen dataclass: `vehicle_id`, `errors`, `warnings`, `is_valid` (property).

---

## Phase 4 Public Interfaces

### Message Entities

- **`e3hybrid.communication.Message`**  
  Frozen dataclass: `message_id`, `sender_id`, `receiver_id`, `message_type`,
  `priority`, `payload`, `is_broadcast`, `created_at_s`, `ttl_s`, `hop_count`,
  `max_hops`, `delivery_status`.
  - **`expiration_time_s`** (property)
  - **`is_expired(current_time_s: float) -> bool`**
  - **`can_relay() -> bool`**
  - **`with_status(status: DeliveryStatus) -> Message`**
  - **`with_incremented_hop() -> Message`**
  - **`create(...) -> Message`** — factory, auto-generates UUID if no id given.
  - `to_dict() -> dict`

- **`e3hybrid.communication.Packet`**  
  Frozen dataclass: `packet_id`, `message`, `sender_id`, `transmitted_at_s`,
  `latency_s`, `delivery_status`, `intended_receiver_id`, `is_relay`, `distance_m`.
  - **`arrival_time_s`** (property)
  - **`is_expired(current_time_s: float) -> bool`**
  - **`with_status(DeliveryStatus) -> Packet`**
  - **`with_latency(float) -> Packet`**
  - **`create(...) -> Packet`** — factory.
  - `to_dict() -> dict`

### Enumerations

- **`e3hybrid.communication.MessageType`** (StrEnum) — 13 types: `TRAFFIC_UPDATE`,
  `ROAD_CLOSURE`, `HAZARD`, `EMERGENCY_VEHICLE`, `PHEROMONE_UPDATE`,
  `SCOUT_REPORT`, `VEHICLE_STATE`, `HEARTBEAT`, `ACKNOWLEDGEMENT`,
  `ROUTE_REQUEST`, `ROUTE_OFFER`, `COORDINATION`, `CUSTOM`.
- **`e3hybrid.communication.Priority`** (IntEnum) — `LOW=1`, `NORMAL=2`, `HIGH=3`, `CRITICAL=4`.
- **`e3hybrid.communication.DeliveryStatus`** (StrEnum) — `PENDING`, `DELIVERED`,
  `DROPPED`, `EXPIRED`, `OUT_OF_RANGE`.

### Protocols (interfaces)

- **`e3hybrid.communication.PacketLossModel`** (Protocol) — `is_lost(Packet) -> bool`
- **`e3hybrid.communication.LatencyModel`** (Protocol) — `compute_latency_s(Packet) -> float`
- **`e3hybrid.communication.CommunicationRadiusModel`** (Protocol)
  - `in_range(VehicleId, VehicleId) -> bool`
  - `receivers_in_range(VehicleId, frozenset) -> frozenset`
- **`e3hybrid.communication.CommunicationProtocol`** (Protocol)
  - `loss_model` (property) → `PacketLossModel`
  - `latency_model` (property) → `LatencyModel`
  - `radius_model` (property) → `CommunicationRadiusModel`

### Baseline Models

- **`e3hybrid.communication.NoLossModel`** — never drops packets.
- **`e3hybrid.communication.ZeroLatencyModel`** — always returns 0.0 s.
- **`e3hybrid.communication.ConstantLatencyModel(latency_s)`** — fixed delay.
- **`e3hybrid.communication.InfiniteRadiusModel`** — all agents always in range.
- **`e3hybrid.communication.FixedRadiusModel(radius_m)`** — disk model.
  - `register_position(vehicle_id, x, y) -> None`
- **`e3hybrid.communication.DeterministicProtocol`** — bundles NoLoss + Zero + Infinite.

### Bus

- **`e3hybrid.communication.MessageBus`**
  - `register(receiver: Receiver) -> None`
  - `unregister(vehicle_id: VehicleId) -> None`
  - `create_broadcaster(vehicle_id: VehicleId) -> Broadcaster`
  - `create_receiver(vehicle_id: VehicleId) -> Receiver`
  - `submit(message: Message) -> None`
  - `tick(current_time_s: float) -> None`
  - `registered_ids() -> frozenset[VehicleId]`
  - `statistics` (property) → `CommunicationStatistics`
  - `packet_log() -> list[Packet]`
  - `pending_count() -> int`
  - `reset_log() -> None`

- **`e3hybrid.communication.Broadcaster`**
  - `send(message: Message) -> None`

- **`e3hybrid.communication.Receiver`**
  - `inbox: deque[Packet]`
  - `drain() -> list[Packet]`
  - `peek() -> list[Packet]`

### Statistics

- **`e3hybrid.communication.CommunicationStatistics`**  
  Fields: `messages_sent`, `messages_delivered`, `messages_dropped`,
  `messages_expired`, `messages_out_of_range`, `broadcast_count`,
  `unicast_count`, `total_latency_s`, `delivered_packet_count`, `relay_count`.  
  Properties: `delivery_ratio`, `drop_ratio`, `average_latency_s`.  
  Methods: `record_sent`, `record_delivered`, `record_dropped`,
  `record_expired`, `record_out_of_range`, `record_relay`, `reset`, `to_dict`.

---

## Phase 5 Public Interfaces

### Emergency Events

- **`e3hybrid.emergency.EmergencyEventType`** (StrEnum) — 7 Phase 5 types: `ROAD_CLOSURE`,
  `ROAD_BLOCK`, `TRAFFIC_ACCIDENT`, `EMERGENCY_VEHICLE`, `INFRASTRUCTURE_FAILURE`,
  `COMMUNICATION_BLACKOUT`, `HAZARD_ZONE`. 5 reserved future types.
- **`e3hybrid.emergency.EventStatus`** (StrEnum) — forward-only state machine:
  `CREATED`, `SCHEDULED`, `ACTIVATED`, `BROADCAST`, `OBSERVED`, `HANDLED`,
  `RESOLVED`, `EXPIRED`.
- **`e3hybrid.emergency.EventLocation`** — frozen dataclass: `edge_ids`, `center_node`,
  `radius_m`.
- **`e3hybrid.emergency.EventId`** — NewType for event identifiers.
- **`e3hybrid.emergency.BaseEmergencyEvent`** — shared mixin with validation and
  state transition enforcement.
- **`e3hybrid.emergency.EmergencyEvent`** (Protocol) — interface for all events.
- **`e3hybrid.emergency.RoadClosureEvent`** — blocks edges for a duration.
- **`e3hybrid.emergency.RoadBlockEvent`** — blocks edges with a physical obstacle.
- **`e3hybrid.emergency.TrafficAccidentEvent`** — adds congestion and hazard penalties.
- **`e3hybrid.emergency.EmergencyVehicleEvent`** — publishes corridor priority request.
- **`e3hybrid.emergency.InfrastructureFailureEvent`** — disables infrastructure.
- **`e3hybrid.emergency.CommunicationBlackoutEvent`** — raises communication penalty.
- **`e3hybrid.emergency.HazardZoneEvent`** — adds hazard penalty to a region.

### Network Effects

- **`e3hybrid.emergency.NetworkEffect`** (Protocol) — interface for edge state modifications.
- **`e3hybrid.emergency.RoadClosureEffect`** — sets `is_blocked=True`.
- **`e3hybrid.emergency.CongestionEffect`** — raises `congestion_factor`.
- **`e3hybrid.emergency.HazardEffect`** — adds `hazard_penalty_s`.
- **`e3hybrid.emergency.EmergencyPriorityEffect`** — adds `emergency_penalty_s`.
- **`e3hybrid.emergency.CommunicationEffect`** — adds `communication_penalty_s`.

### Emergency State Management

- **`e3hybrid.emergency.EmergencyState`** — tracks active effects per edge with additive
  composition and full recompute on resolution.
- **`e3hybrid.emergency.EmergencyEventBus`** — typed pub/sub with priority ordering,
  exception isolation, delivery statistics.
- **`e3hybrid.emergency.EmergencyBusStatistics`** — delivery metrics.
- **`e3hybrid.emergency.EmergencyRegistry`** — single source of truth for all events.
- **`e3hybrid.emergency.EventScheduler`** — deterministic scheduling (fixed, random,
  recurring, progressive modes).
- **`e3hybrid.emergency.ScenarioLoader`** — YAML → concrete event objects.
- **`e3hybrid.emergency.ScenarioMetadata`** — scenario metadata.
- **`e3hybrid.emergency.validate_scenario_dict(dict) -> None`** — 15 validation rules.
- **`e3hybrid.emergency.NetworkEffectSubscriber`** — the only module that calls
  `DirectedGraph.update_edge_state`.

---

## Phase 6 Public Interfaces

### Decision Types

- **`e3hybrid.decision.DecisionType`** (StrEnum) — action types: `KEEP_CURRENT_ROUTE`,
  `REQUEST_REROUTE`, `YIELD`, `WAIT`, `REDUCE_SPEED`, `BROADCAST_MESSAGE`,
  `REQUEST_EXPLORATION`, `IGNORE_EVENT`, `EMERGENCY_STOP`, `CHARGE`, `COORDINATE`.
- **`e3hybrid.decision.DecisionId`** — NewType for decision identifiers.
- **`e3hybrid.decision.RouteId`** — NewType for route identifiers.

### Decision Objects

- **`e3hybrid.decision.Decision`** — frozen dataclass: decision_id, vehicle_id,
  sim_time_s, decision_type, trigger, explanation, winning_policy, applied_policies,
  veto, confidence, payload, all_recommendations.
  - **`create(...) -> Decision`** — factory, auto-generates UUID.
  - **`to_dict() -> dict`** — CSV/JSON-compatible serialization.

### Observations

- **`e3hybrid.decision.VehicleObservation`** — frozen snapshot: vehicle_id, sim_time_s,
  vehicle_state, battery, constraints, graph_snapshot, routing_candidates,
  current_route, inbox_messages, active_events.
- **`e3hybrid.decision.GraphSnapshot`** — neighbourhood-scoped graph view: current_edge,
  neighbour_edges, blocked_edge_ids.
  - **`is_blocked(edge_id) -> bool`**
  - **`get_edge(edge_id) -> EdgeSnapshot | None`**
- **`e3hybrid.decision.EdgeSnapshot`** — minimal edge view: edge_id, source, target,
  length_m, speed_limit_mps, is_blocked, congestion_factor, hazard_penalty_s,
  emergency_penalty_s, communication_penalty_s, estimated_cost.
- **`e3hybrid.decision.BatterySnapshot`** — battery state: soc_kwh, capacity_kwh,
  soc_fraction.
- **`e3hybrid.decision.RouteSnapshot`** — route state: route_id, remaining_edge_ids,
  destination_node, estimated_remaining_cost, has_blocked_edge.
- **`e3hybrid.decision.ObservationAssembler`** — builds observations from subsystem state.
  - **`assemble(vehicle, graph, route_candidate_source, sim_time_s, active_events, inbox_messages) -> VehicleObservation`**

### Policies

- **`e3hybrid.decision.DecisionPolicy`** (Protocol) — interface for all policies.
  - **`name`** (property) — stable policy name.
  - **`enabled`** (property) — whether policy participates in evaluation.
  - **`evaluate(observation) -> PolicyRecommendation`**
- **`e3hybrid.decision.PolicyRecommendation`** — frozen dataclass: decision_type,
  priority, confidence, explanation, policy_name, veto, payload.
- **`e3hybrid.decision.DecisionAggregationPolicy`** — selects winning recommendation.
  - **`aggregate(vehicle_id, sim_time_s, recommendations) -> Decision`**

### Concrete Policies

- **`e3hybrid.decision.SafetyPolicy`** — hard-constraint safety checks (priority 100).
- **`e3hybrid.decision.EmergencyPolicy`** — react to active emergency events (priority 90).
- **`e3hybrid.decision.BatteryPolicy`** — protect against SoC violations (priority 70-95).
- **`e3hybrid.decision.CongestionPolicy`** — react to congestion and hazard (priority 60).
- **`e3hybrid.decision.CommunicationPolicy`** — decide when to broadcast (priority 50).
- **`e3hybrid.decision.RoutingCandidatePolicy`** — evaluate routing candidates (priority 40).

### Policy Management

- **`e3hybrid.decision.PolicyRegistry`** — central registry for policy factories.
  - **`register(name, factory) -> None`**
  - **`get_factory(name) -> PolicyFactory`**
  - **`list_registered() -> tuple[str, ...]`**
  - **`is_registered(name) -> bool`**
- **`e3hybrid.decision.PolicyManager`** — manages policy instances.
  - **`get_enabled_policies() -> tuple[DecisionPolicy, ...]`**
  - **`get_policy(name) -> DecisionPolicy`**
  - **`list_available() -> tuple[str, ...]`**
  - **`list_enabled() -> tuple[str, ...]`**
- **`e3hybrid.decision.register_policy(name, factory) -> None`** — register in global registry.
- **`e3hybrid.decision.register_all_policies() -> None`** — register all Phase 6 policies.
- **`e3hybrid.decision.get_global_registry() -> PolicyRegistry`**

### Decision Engine

- **`e3hybrid.decision.DecisionEngineConfig`** — engine configuration: config,
  enable_validation, enable_logging.
- **`e3hybrid.decision.DecisionEngine`** — main evaluation coordinator.
  - **`evaluate(observation) -> Decision`**
  - **`get_enabled_policy_names() -> tuple[str, ...]`**
  - **`get_available_policy_names() -> tuple[str, ...]`**

### Decision Logging

- **`e3hybrid.decision.DecisionLog`** — CSV-based decision logger with immediate writes.
  - **`log(decision) -> None`**
  - **`get_log_path(output_dir, run_id) -> Path`**

### Decision Validation

- **`e3hybrid.decision.DecisionValidator`** — validates Decision objects.
  - **`validate(decision) -> DecisionValidationReport`**
- **`e3hybrid.decision.DecisionValidationReport`** — validation report: is_valid, errors.
- **`e3hybrid.decision.DecisionValidationError`** — single validation error: field_name,
  error_message.

### Configuration

- **`e3hybrid.decision.DecisionConfig`** — complete configuration: max_candidates,
  neighbourhood_depth, safety, emergency, battery, congestion, communication, routing.
  - **`default() -> DecisionConfig`**
  - **`from_dict(data) -> DecisionConfig`**
- **`e3hybrid.decision.SafetyPolicyConfig`** — safety policy: enabled.
- **`e3hybrid.decision.EmergencyPolicyConfig`** — emergency policy: enabled, yield_duration_s,
  min_priority_value.
- **`e3hybrid.decision.BatteryPolicyConfig`** — battery policy: enabled,
  emergency_stop_threshold_fraction, wait_threshold_fraction,
  conservation_threshold_fraction.
- **`e3hybrid.decision.CongestionPolicyConfig`** — congestion policy: enabled,
  reroute_congestion_threshold, reroute_hazard_threshold_s.
- **`e3hybrid.decision.CommunicationPolicyConfig`** — communication policy: enabled,
  broadcast_new_closures, broadcast_hazards, stale_message_age_s.
- **`e3hybrid.decision.RoutingCandidatePolicyConfig`** — routing candidate policy: enabled,
  improvement_threshold.

### Routing Candidates

- **`e3hybrid.decision.RouteCandidate`** — frozen dataclass: route_id, node_sequence,
  edge_sequence, total_cost, algorithm, metadata.
- **`e3hybrid.decision.RouteCandidateSource`** (Protocol) — interface for routing algorithms.
  - **`get_candidates(vehicle_id, origin, destination, max_candidates) -> tuple[RouteCandidate, ...]`**
- **`e3hybrid.decision.NullRouteCandidateSource`** — Phase 6 placeholder (returns empty tuple).

---

## Phase 7B Public Interfaces (Dijkstra Baseline Complete)

**Note:** Phase 7B implements the baseline routing framework and Dijkstra algorithm.
All Phase 7A design documents are approved. Phase 7C (benchmark framework) is also complete.
Phase 7D (A* baseline) is also complete.

### Routing Algorithm Protocol

- **`e3hybrid.routing.RoutingAlgorithm`** (Protocol) — interface for all routing algorithms.
  - **`name`** (property) — stable algorithm name.
  - **`compute_route(request, context) -> RoutingResult`** — the ONLY method algorithms implement.

### Routing Context and Request

- **`e3hybrid.routing.RoutingContext`** — frozen dataclass: graph_snapshot, cost_provider,
  config, random_stream, sim_time_s.
- **`e3hybrid.routing.RoutingRequest`** — frozen dataclass: source_node, destination_node,
  vehicle_id, vehicle_constraints, battery_state, max_candidates, timeout_s, metadata.

### Routing Result

- **`e3hybrid.routing.RoutingResult`** — frozen dataclass: candidates, primary_route,
  success, failure_reason, statistics, runtime_s.

### Route and Cost

- **`e3hybrid.routing.Route`** — frozen dataclass: route_id, node_sequence, edge_sequence,
  total_distance_m, estimated_travel_time_s, estimated_energy_kwh.
- **`e3hybrid.routing.RouteSegment`** — frozen dataclass: edge_id, source, target,
  distance_m, travel_time_s, energy_kwh, cost.
- **`e3hybrid.routing.RouteCost`** — frozen dataclass: total, distance_cost, time_cost,
  energy_cost, congestion_penalty, hazard_penalty, emergency_penalty,
  communication_penalty, components.
- **`e3hybrid.routing.RouteCandidate`** — frozen dataclass: route_id, node_sequence,
  edge_sequence, total_cost, cost_breakdown, algorithm, metadata, runtime_s,
  search_statistics.

### Statistics and Validation

- **`e3hybrid.routing.RoutingStatistics`** — frozen dataclass: nodes_explored, edges_explored,
  candidates_generated, cache_hits, cache_misses, memory_bytes.
- **`e3hybrid.routing.SearchStatistics`** — frozen dataclass: iterations, convergence,
  diversity (for swarm algorithms).
- **`e3hybrid.routing.RouteValidator`** — validates routes: connectivity, blocked edges,
  cost consistency, battery feasibility.
  - **`validate(route, context) -> RouteValidationReport`**

### Caching

- **`e3hybrid.routing.RouteCache`** — cache for routing results.
  - **`get(key) -> RouteCandidate | None`**
  - **`put(key, candidate) -> None`**
  - **`invalidate(edge_ids) -> None`**
- **`e3hybrid.routing.CacheKey`** — frozen dataclass: source, destination, graph_state_hash,
  config_hash.

### Configuration

- **`e3hybrid.routing.RoutingAlgorithmConfig`** — frozen dataclass: cost_weights,
  hyperparameters, timeout_s, max_candidates.
- **`e3hybrid.routing.CostWeights`** — frozen dataclass: distance, time, energy,
  congestion, hazard, emergency, communication.

### Baseline Algorithms (Implemented)

- **`e3hybrid.routing.DijkstraRouting`** — classical shortest-path algorithm.
  Heap-based priority queue implementation. Uses `CostProvider` for edge costs.
  Returns multiple candidates via alternative-path search. 91% test coverage.
  - **`compute_route(request, context) -> RoutingResult`**

### Baseline Algorithm — A* (Implemented in Phase 7D)

- **`e3hybrid.routing.AStarRouting`** — Heuristic search algorithm.
  Heap-based priority queue with `f = g + h`. Uses `CostProvider` for edge costs.
  Returns multiple candidates via alternative-path search. Supports configurable
  heuristic via `heuristic` parameter.
  - **`__init__(heuristic: Heuristic = ZeroHeuristic())`**
  - **`heuristic`** (property) — current heuristic instance
  - **`compute_route(request, context) -> RoutingResult`**

### Heuristic Protocol and Implementations

- **`e3hybrid.routing.Heuristic`** (Protocol) — interface for A* heuristic functions.
  - **`name`** (property) — stable heuristic name
  - **`estimate(source, destination, graph) -> float`** — admissible cost estimate

- **`e3hybrid.routing.ZeroHeuristic`** — always returns 0.0. A* becomes Dijkstra.
  - **`name`** → `"zero"`
  - **`__init__(scale=1.0)`**

- **`e3hybrid.routing.EuclideanHeuristic`** — straight-line distance.
  - **`name`** → `"euclidean"`
  - **`__init__(scale=1.0)`**
  - `estimate(A, D, graph)` → `scale × √((x₂−x₁)² + (y₂−y₁)²)`

- **`e3hybrid.routing.ManhattanHeuristic`** — grid/taxicab distance.
  - **`name`** → `"manhattan"`
  - **`__init__(scale=1.0)`**
  - `estimate(A, D, graph)` → `scale × (|x₂−x₁| + |y₂−y₁|)`

- **`e3hybrid.routing.HeuristicFactory`** — heuristic creation by name.
  - **`create(name, **kwargs) -> Heuristic`** — `"zero"`, `"euclidean"`, `"manhattan"`
  - **`available_heuristics() -> dict[str, str]`**

- **`e3hybrid.routing.HeuristicValidator`** — admissibility and consistency checks.
  - **`check_admissibility(heuristic, graph) -> HeuristicValidationReport`**
  - **`check_consistency(heuristic, graph) -> HeuristicValidationReport`**

### Swarm Infrastructure (Implemented — Phase 8B)

**Note:** Phase 8B implements the common swarm architecture defined in Phase 8A.
All components are algorithm-agnostic and ready for ACO, BCO, PSO use.

- **`e3hybrid.swarm.SwarmAlgorithm`** (Protocol) — interface for all swarm optimization algorithms.
  - **`name`** (property) — stable algorithm name
  - **`optimize(context: SwarmContext) -> SwarmResult`** — the ONLY method algorithms implement

- **`e3hybrid.swarm.SwarmContext`** — frozen dataclass: cost_weights, config, random_seed, routing_request, sim_time_s, graph, cost_calculator.

- **`e3hybrid.swarm.SwarmState`** — frozen dataclass: iteration, population, best_solution, internal_state, statistics.

- **`e3hybrid.swarm.SwarmIteration`** — frozen dataclass: iteration_number, solutions_evaluated, best_score, average_score, midrange_score, worst_score, diversity_measure, runtime_s.

- **`e3hybrid.swarm.SwarmStatistics`** — frozen dataclass: total_iterations, total_runtime_s, best_score, average_score, worst_score, convergence_iteration, candidate_count, solutions_evaluated, diversity_history, score_history, termination_reason.

- **`e3hybrid.swarm.SwarmResult`** — frozen dataclass: best_solution, candidates, statistics, iterations, success, failure_reason.

- **`e3hybrid.swarm.SwarmConfig`** — frozen dataclass: algorithm_name, population_size, max_iterations, time_limit_s, convergence_threshold, no_improvement_limit, seed, hyperparameters, cost_weights.

- **`e3hybrid.swarm.SwarmValidator`** — algorithm-independent validation.
  - **`validate_config(config) -> SwarmValidationReport`**
  - **`validate_state(state) -> SwarmValidationReport`**
  - **`validate_result(result) -> SwarmValidationReport`**

- **`e3hybrid.swarm.SwarmFactory`** — creates swarm algorithms by name.
  - **`create_algorithm(name, config) -> SwarmAlgorithm`**
  - **`available_algorithms() -> dict[str, str]`**
  - **`register(name, algorithm_class) -> None`**
  - **`is_registered(name) -> bool`**
  - **`clear_registry() -> None`**

- **`e3hybrid.swarm.SwarmToRoutingAdapter`** — adapts SwarmAlgorithm to RoutingAlgorithm Protocol.
  - **`__init__(swarm_algorithm, swarm_config=None)`**
  - **`name`** (property) — delegates to underlying swarm algorithm
  - **`swarm_algorithm`** (property) — access the underlying algorithm
  - **`compute_route(request, graph=None) -> RoutingResult`** — builds SwarmContext with graph, runs optimize(), converts result

- **`e3hybrid.swarm.SwarmLifecycle`** — common optimization lifecycle.
  - **`__init__(config)`**
  - **`run(context, initialize_fn, update_fn, extract_best_fn) -> SwarmResult`**

- **`e3hybrid.swarm.TerminationChecker`** — evaluates stopping conditions.
  - **`__init__(config)`**
  - **`start() -> None`**
  - **`check(state) -> TerminationCondition`**
  - **`reset() -> None`**

- **`e3hybrid.swarm.TerminationCondition`** — frozen dataclass: should_stop, reason, iteration, elapsed_time_s.

### Shared Data Structures (Phase 8B, Implemented)

- **`e3hybrid.swarm.Solution`** — frozen dataclass: node_sequence, edge_sequence, metadata.
  Properties: source_node, destination_node, edge_count.
- **`e3hybrid.swarm.CandidateSolution`** — frozen dataclass: solution, score, cost_breakdown, iteration_created, algorithm_specific.
- **`e3hybrid.swarm.OptimizationScore`** — frozen dataclass: total, components, normalized, rank.
- **`e3hybrid.swarm.SearchState`** — frozen dataclass: iteration, best_score, previous_best_score, no_improvement_count, diversity, elapsed_time_s.
- **`e3hybrid.swarm.Population`** — frozen dataclass: individuals, diversity, iteration.
  Properties: size, best, average_score, worst_score.
- **`e3hybrid.swarm.SwarmState`** — frozen dataclass: iteration, population, best_solution, internal_state.
- **`e3hybrid.swarm.SwarmStatistics`** — frozen dataclass: total_iterations, total_runtime_s, best_score, average_score, worst_score, convergence_iteration, candidate_count, solutions_evaluated, diversity_history, score_history, termination_reason.
- **`e3hybrid.swarm.IterationStatistics`** — frozen dataclass: iteration, best_score, average_score, midrange_score, worst_score, std_dev, diversity, best_solution_changed, runtime_s.
- **`e3hybrid.swarm.SwarmResult`** — frozen dataclass: best_solution, candidates, statistics, iterations, success, failure_reason.

### Swarm Random (Phase 8B, Implemented)

- **`e3hybrid.swarm.SwarmRandom`** — deterministic random number generation for swarm algorithms.
  - **`__init__(base_seed: int)`**
  - **`get_stream(name: str) -> random.Random`**
  - **`reset() -> None`**
  - **`base_seed`** (property)

### Swarm Validation (Phase 8B, Implemented)

- **`e3hybrid.swarm.SwarmValidationReport`** — frozen dataclass: is_valid, errors, warnings, checks_performed, checks_passed.
- **`e3hybrid.swarm.SwarmValidator`** — algorithm-independent validation.
  - **`validate_config(config) -> SwarmValidationReport`**
  - **`validate_state(state) -> SwarmValidationReport`**
  - **`validate_result(result) -> SwarmValidationReport`**
  - **`validate_population(population) -> SwarmValidationReport`**

### Swarm Algorithms (Phase 9B — ACO Implemented)

- **`e3hybrid.swarm.ACORouting`** — Ant Colony System (ACS, Dorigo & Gambardella 1997). Implements `SwarmAlgorithm` Protocol.
  - **`name`** (property) — returns `"aco"`.
  - **`optimize(context: SwarmContext) -> SwarmResult`** — runs ACS optimization with pseudorandom proportional rule, local + global pheromone updates, bounds clamping, and elite reinforcement.

- **`e3hybrid.swarm.ACSConfiguration`** — frozen dataclass: alpha, beta, rho, q0, tau0, tau_min, tau_max, elitism, candidate_list_size.
  - **`from_swarm_config(config: SwarmConfig) -> ACSConfiguration`** — extract from generic config.

- **`e3hybrid.swarm.PheromoneMatrix`** — sparse pheromone storage with [tau_min, tau_max] clamping.
  - **`get(edge_id) -> float`**, **`set(edge_id, value)`**, **`decay(edge_id, rho, tau0)`**, **`reinforce(edge_id, rho, deposit)`**
  - **`values`** (property), **`edge_count`** (property), **`clone()`**

- **`e3hybrid.swarm.VisibilityMatrix`** — static heuristic desirability eta = 1/(cost + EPS).
  - **`get(edge_id) -> float`**, **`get_neighbours(node_id) -> list[EdgeId]`**

- **`e3hybrid.swarm.TransitionRule`** — ACS pseudorandom proportional rule.
  - **`select(candidates, pheromones, visibility, sel_stream, roulette_stream) -> EdgeId | None`**

- **`e3hybrid.swarm.PheromoneUpdater`** — local and global pheromone updates.
  - **`local_update(pheromones, edge_id)`**, **`global_update(pheromones, edges, cost)`**, **`global_update_elite(pheromones, edges, costs)`**

- **`e3hybrid.swarm.Ant`** — mutable dataclass: current_node, visited_nodes, node_sequence, edge_sequence, total_cost, is_complete, is_feasible, reached_dead_end.

- **`e3hybrid.swarm.AntColony`** — manages ant population per iteration.
  - **`initialize_population(count, start_node)`**, **`construct_routes(...)`**, **`evaluate_population()`**, **`compute_diversity()`**

- **`e3hybrid.swarm.ACOStatistics`** — frozen dataclass: best_cost, average_colony_cost, worst_colony_cost, best_iteration, convergence_iteration, total_runtime_s, route_length, travel_time, expanded_nodes, total_iterations, termination_reason, diversity_history, score_history.

- **`e3hybrid.swarm.ACOValidator`** — validates ACS configuration and context.
  - **`validate_config(config) -> list[str]`** — returns error messages.
  - **`validate_context(context) -> list[str]`** — checks graph, cost_calculator presence.

- **`e3hybrid.swarm.ACOFactory`** — factory for ACO instances.
  - **`create(config=None) -> ACORouting`**, **`create_from_swarm_config(config) -> ACORouting`**

- **`e3hybrid.routing.RoutingFactory.create_aco(config=None) -> RoutingAlgorithm`** — creates SwarmToRoutingAdapter wrapping ACORouting.

- **`e3hybrid.swarm.BCORouting`** — Bee Colony Optimization (Phase 10 — planned).
- **`e3hybrid.swarm.PSORouting`** — Particle Swarm Optimization (Phase 11 — planned).

### Hybrid Algorithm (Planned — Phase 12)

- **`e3hybrid.routing.E3HybridRouting`** — integrates ACO, BCO, PSO with Decision Engine. Built on the common swarm infrastructure defined in Phase 8A.

---

## Phase 7C Public Interfaces (Benchmark Framework Complete)

**Note:** Phase 7C implements algorithm-independent verification and benchmarking.
All components are reusable without modification for every routing algorithm.

### Verification

- **`e3hybrid.routing.RoutingVerifier`** — algorithm-independent route verification.
  - **`verify_route(route, graph, request, allow_blocked) -> VerificationReport`**
  - **`verify_result(result, graph, request) -> VerificationReport`**
  - **`verify_candidate(candidate, graph, request) -> VerificationReport`**
  - **`verify_graph_integrity(graph) -> VerificationReport`**
  - **`verify_deterministic_replay(algorithm, request, graph, num_runs) -> DeterministicReplayReport`**
  - **`verify_cost_breakdown(candidate) -> VerificationReport`**
  - **`compute_expected_distance(route, graph) -> float`**
  - **`compute_expected_travel_time(route, graph) -> float`**
  - **`compute_expected_cost(route, cost_calculator, graph) -> float`**

- **`e3hybrid.routing.VerificationReport`** — frozen dataclass: is_valid, errors, checks_performed, checks_passed.
- **`e3hybrid.routing.VerificationError`** — frozen dataclass: check_name, message.
- **`e3hybrid.routing.DeterministicReplayReport`** — frozen dataclass: is_deterministic, num_runs, has_route, primary_route_ids, cost_consistency, route_consistency, errors.

### Benchmark Configuration

- **`e3hybrid.routing.BenchmarkConfig`** — frozen dataclass: algorithm_names, num_requests, timeout_s, max_candidates, output_dir, seed, cost_weights, verify_routes, collect_memory, description, metadata.

### Benchmark Scenario and Requests

- **`e3hybrid.routing.BenchmarkScenario`** — frozen dataclass: graph, requests, name, description, metadata.
- **`e3hybrid.routing.BenchmarkRequest`** — frozen dataclass: request, description, expected_success, metadata.

### Benchmark Metrics and Results

- **`e3hybrid.routing.AlgorithmMetadata`** — frozen dataclass: name, version, description, parameters.
- **`e3hybrid.routing.BenchmarkMetrics`** — frozen dataclass: algorithm_name, runtime_s, expanded_nodes, visited_nodes, route_distance_m, travel_time_s, total_cost, route_valid, success, failure_reason, request_description, memory_bytes, candidates_generated.
- **`e3hybrid.routing.BenchmarkResult`** — frozen dataclass: algorithm, scenario, metrics, verification_reports, summary, config, timestamp, duration_s.
- **`e3hybrid.routing.BenchmarkSummary`** — frozen dataclass: total/successful/failed requests, avg/max/min runtime, avg distance/time/cost, expanded nodes, verification stats.

### Benchmark Lifecycle

- **`e3hybrid.routing.BenchmarkValidator`** — validates configurations, scenarios, metrics, and results.
  - **`validate_config(config) -> BenchmarkValidationReport`**
  - **`validate_scenario(scenario) -> BenchmarkValidationReport`**
  - **`validate_metrics(metrics) -> BenchmarkValidationReport`**
  - **`validate_result(result) -> BenchmarkValidationReport`**

- **`e3hybrid.routing.BenchmarkReporter`** — writes benchmark artifacts to disk.
  - **`write_all(results, config) -> Path`**
  - **`write_summary(results, path) -> None`**
  - **`write_routing_results(results, path) -> None`**
  - **`write_verification_report(results, path) -> None`**
  - **`write_metadata(results, config, path) -> None`**
  - **`write_config_snapshot(config, path) -> None`**

- **`e3hybrid.routing.BenchmarkRunner`** — orchestrates benchmark execution.
  - **`config`** (property) — the benchmark configuration.
  - **`run_scenario(scenario) -> list[BenchmarkResult]`**
