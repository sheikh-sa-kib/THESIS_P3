# E3-Hybrid: Electric Vehicle Routing with Triple-Swarm Intelligence — Build Guide

> **Comprehensive guide to rebuild the E3-Hybrid thesis simulation from scratch.**
> Last updated: 2026-07-12

---

## Table of Contents

1. [Project Overview](#project-overview)
2. [System Requirements & Dependencies](#system-requirements-&-dependencies)
3. [Installation & Setup](#installation-&-setup)
4. [Architecture Overview](#architecture-overview)
5. [Core Data Model](#core-data-model)
6. [Routing Framework](#routing-framework)
7. [Baseline Routing Algorithms (Dijkstra, A*)](#baseline-routing-algorithms-dijkstra-a)
8. [Swarm Infrastructure Framework](#swarm-infrastructure-framework)
9. [Swarm Algorithms (ACO, BCO, PSO, E3-Hybrid)](#swarm-algorithms-aco-bco-pso-e3-hybrid)
10. [Communication Framework](#communication-framework)
11. [Decision Engine](#decision-engine)
12. [Emergency Framework](#emergency-framework)
13. [Vehicle & Energy Model](#vehicle-&-energy-model)
14. [SUMO/TraCI Integration](#sumo-traci-integration)
15. [Experiment Pipeline](#experiment-pipeline)
16. [Plot Generation](#plot-generation)
17. [Configuration System](#configuration-system)
18. [Testing](#testing)
19. [Key Bug Fixes & Design Decisions](#key-bug-fixes-&-design-decisions)
20. [Parameter Values & Justification](#parameter-values-&-justification)
21. [Profiling Results](#profiling-results)
22. [Reproducibility](#reproducibility)
23. [How to Reproduce the Full Experiment](#how-to-reproduce-the-full-experiment)

## 1. Project Overview

### 1.1 What This Project Does

This simulation framework evaluates **electric vehicle (EV) routing algorithms** in a dynamic urban environment using the **SUMO (Simulation of Urban Mobility)** traffic simulator. It compares **6 routing algorithms** (2 classical + 4 swarm intelligence) on the **Midtown Manhattan road network (715 nodes, 1636 edges)** under emergency scenarios.

### 1.2 The Six Algorithms

| # | Algorithm | Type | Source |
|---|-----------|------|--------|
| 1 | **Dijkstra** | Classical shortest-path | Dijkstra (1959) |
| 2 | **A*** | Heuristic shortest-path | Hart, Nilsson & Raphael (1968) |
| 3 | **ACO** | Ant Colony Optimization | Dorigo & Gambardella (1997) |
| 4 | **BCO** | Bee Colony Optimization | Teodorovic (2009) |
| 5 | **PSO** | Particle Swarm Optimization | Mohemmed et al. (2008) |
| 6 | **E3-Hybrid** | Triple-swarm hybrid (ACO+BCO+PSO) | Novel - this thesis |

### 1.3 Key Research Questions
1. How do swarm intelligence algorithms compare to classical shortest-path algorithms for EV routing?
2. Can a triple-swarm hybrid (ACO+BCO+PSO) outperform individual swarm algorithms?
3. How do emergency events affect routing performance across algorithms?
4. What is the computational cost of swarm-based routing vs classical approaches?

### 1.4 Package Metadata
- **Name**: e3hybrid, **Version**: 0.1.0, **License**: MIT
- **Python**: 3.12+, **SUMO**: 1.27.1


## 2. System Requirements & Dependencies

### 2.1 Hardware Requirements
| Component | Minimum | Recommended |
|-----------|---------|-------------|
| RAM | 4 GB | 16 GB |
| Disk | 5 GB free | 20 GB free |
| CPU | 4 cores | 8+ cores |
| OS | Windows 10/11 | Windows 10/11 |

### 2.2 Software Requirements
| Software | Version | Purpose |
|----------|---------|---------|
| Python | 3.12+ | Runtime |
| SUMO | 1.27.1 | Traffic simulation |
| Git | Any | Version control |

### 2.3 Python Packages
**Runtime** (requirements.txt): PyYAML>=6.0 (YAML parsing), matplotlib>=3.8 (plots), psutil>=5.9 (system monitoring)
**Development** (requirements-dev.txt): pytest>=8.0, mypy>=1.8, ruff>=0.3, pre-commit>=3.6, types-PyYAML>=6.0
**SUMO bundled**: traci (TraCI interface), sumolib (SUMO library), randomTrips.py (trip generation)

### 2.4 Important Notes
- SUMO must be installed BEFORE Python packages depending on traci/sumolib
- Set SUMO_HOME environment variable to SUMO install directory (e.g., C:\Program Files (x86)\Eclipse\Sumo)
- All paths use pathlib.Path (handles Windows backslashes)


## 3. Installation & Setup

### 3.1 Step-by-Step from Scratch
```powershell
# STEP 1: Install SUMO 1.27.1 from https://sumo.dlr.de/docs/Downloads.php
# Default path: C:\Program Files (x86)\Eclipse\Sumo

# STEP 2: Set environment variable
[Environment]::SetEnvironmentVariable("SUMO_HOME", "C:\Program Files (x86)\Eclipse\Sumo", "User")
sumo --version  # Verify "SUMO 1.27.1"

# STEP 3: Clone and setup
git clone <repo-url> && cd THESIS_NEW
python -m venv .venv
.venv\Scripts\Activate.ps1
python "%SUMO_HOME%\tools\build_supplementary.py"
pip install -r requirements.txt
pip install -r requirements-dev.txt  # Optional
pip install -e .

# STEP 4: Verify
python preflight.py
python run_thesis.py --preset smoke
```

### 3.2 Preflight Check
preflight.py checks: OS (Windows), Python (3.12+), RAM (>=4GB), Disk (>=5GB), SUMO (>=1.20, targets 1.27.1), Python packages (PyYAML, matplotlib, psutil, pytest), project files, network file loadability, SUMO process start/stop. Exits 0 on PASS, 1 on FAIL.

### 3.3 Development Commands
```powershell
pre-commit install       # Install git hooks (ruff, mypy, pytest)
pytest                   # Run all tests (201 pass)
pytest --cov=src         # With coverage
mypy src                 # Static type checking
ruff check src           # Linting
```


## 4. Architecture Overview

### 4.1 Clean Architecture Layers
```
Layer 0: External - sumo/ (connection, import, simulation)
Layer 1: Infrastructure - core/ (types, exceptions), config/ (YAML), utils/ (logging, reproducibility)
Layer 2: Domain Models - network/ (graph, edge, node), vehicle/ (entity, battery, energy), routing/ (protocols, cost)
Layer 3: Algorithms - routing/dijkstra.py, astar.py, swarm/ (aco, bco, pso, hybrid)
Layer 4: Business Logic - decision/ (engine, policies), emergency/ (events, registry), communication/ (bus, protocols)
Layer 5: Application - cli/, scripts/, run_thesis.py, preflight.py
```

### 4.2 Key Design Principles
1. **Protocol-based interfaces**: All major abstractions use typing.Protocol - RoutingAlgorithm, SwarmAlgorithm, CostProvider, EnergyModel, DecisionPolicy, CommunicationProtocol.
2. **Immutable data**: All core data structures are frozen dataclasses. State transitions use the immutable copy pattern (with_* methods).
3. **Pure functions**: Every routing algorithm is a pure function - identical inputs produce identical outputs.
4. **Deterministic execution**: All RNG uses seeded sub-streams via SwarmRandom. SUMO is seeded. Entire experiment reproducible given same git commit + seed.
5. **Algorithm-agnostic evaluation**: Decision Engine evaluates candidates only on total_cost.

### 4.3 Data Flow
```
preflight.py -> run_thesis.py (--preset X)
  -> [1/5] Preflight check
  -> [2/5] Pipeline validation (all 6 algorithms)
  -> [3/5] Full experiment: per-algorithm SUMO simulation with step loop, rerouting, emergencies
  -> [4/5] Plot generation (34 figures)
  -> [5/5] Final summary (metrics, routing benchmarks, artifacts)
  Output: metrics_summary.csv, simulation_log.csv, routing_log.csv, config_snapshot.yaml, experiment_manifest.json, environment.json, plots/png/*
```


## 5. Core Data Model

### 5.1 DirectedGraph (src/e3hybrid/network/graph.py)
Four parallel dictionaries: _nodes (NodeId->Node), _edges (EdgeId->Edge), _outgoing (NodeId->{EdgeId->Edge}), _incoming (NodeId->{EdgeId->Edge}). Plus _edge_successors (EdgeId->list[EdgeId]) for lane-level connectivity.
Methods: add_node/edge, has_node/edge, get_node/edge, outgoing_edges, incoming_edges, neighbors, update_edge_state, set/get/has_successors, to_dict/from_dict (schema_version 1).

### 5.2 Edge (src/e3hybrid/network/edge.py)
**Edge** (immutable frozen dataclass, ~343 lines): edge_id, source, target, length_m, speed_limit_mps, lane_count, state (MutableEdgeState), metadata. Property: effective_speed_mps.
**MutableEdgeState** (frozen dataclass): is_blocked, current_speed_mps (float|None), travel_time_override_s (float|None), congestion_factor (default 1.0), hazard_penalty_s, emergency_penalty_s, communication_penalty_s, metadata.

### 5.3 Node (src/e3hybrid/network/node.py)
Frozen dataclass: node_id (NodeId), x (float|None), y (float|None), metadata.

### 5.4 Type Aliases (src/e3hybrid/network/types.py)
NodeId = NewType("NodeId", str), EdgeId = NewType("EdgeId", str)

### 5.5 Cost Providers (src/e3hybrid/network/cost.py)
**CostProvider** Protocol: cost(edge) -> EdgeCost(value, is_blocked, components)
- DistanceCostProvider: cost = edge.length_m
- TravelTimeCostProvider: cost = travel_time_s (incorporates congestion_factor, hazard/emergency/communication penalties, travel_time_override. Blocked edges -> inf)

### 5.6 Graph Validation (src/e3hybrid/network/validation.py)
GraphValidator checks: empty graphs, disconnected edges (source/target missing), self-loops, negative/speed limits, duplicate adjacencies, isolated nodes (warning).


## 6. Routing Framework

### 6.1 RoutingAlgorithm Protocol (src/e3hybrid/routing/protocol.py)
```python
class RoutingAlgorithm(Protocol):
    @property
    def name(self) -> str: ...
    def compute_route(self, request: RoutingRequest, graph: DirectedGraph) -> RoutingResult: ...
```

### 6.2 RoutingRequest (src/e3hybrid/routing/request.py)
Frozen dataclass: source_node, destination_node (NodeId), vehicle_id (VehicleId), vehicle_constraints, battery_state, max_candidates (>0), timeout_s (>0), metadata (dict with optional source_edge_id for lane-level queries). Validates source != destination.

### 6.3 RoutingResult (src/e3hybrid/routing/result.py)
Frozen: candidates (tuple[RouteCandidate]), primary_route (Route|None), success (bool), failure_reason (str|None), statistics (RoutingStatistics), runtime_s (float). Validates success+primary_route / failure+no_primary consistency.

### 6.4 Route & RouteSegment (src/e3hybrid/routing/route.py)
**Route** frozen: route_id, node_sequence (>=2 nodes), edge_sequence (len=nodes-1), total_distance_m, estimated_travel_time_s, estimated_energy_kwh. Properties: source_node, destination_node, edge_count.
**RouteSegment** frozen: edge_id, source, target, distance_m, travel_time_s, energy_kwh, cost.

### 6.5 RouteCost (src/e3hybrid/routing/cost.py)
Frozen: total, distance_cost, time_cost, energy_cost, congestion_penalty, hazard_penalty, emergency_penalty, communication_penalty, components. Validates total == sum(components) within 1e-6.

### 6.6 CostWeights & CompositeCostCalculator (src/e3hybrid/routing/cost_calculator.py)
CostWeights: distance, time, energy, congestion, hazard, emergency, communication (all float, default 1.0).
CompositeCostCalculator: compute_edge_cost(edge) -> (total, breakdown), compute_route_cost(edges) -> (total, breakdown). Formula: base_time = length / effective_speed, congested_time = base_time * congestion_factor, add penalties, apply weights.

### 6.7 RouteCandidate & SearchStatistics (src/e3hybrid/routing/candidate.py)
RouteCandidate: route_id, node_sequence, edge_sequence, total_cost, cost_breakdown, algorithm, metadata, runtime_s, search_statistics. Invariant: cost_breakdown.total == total_cost.
SearchStatistics: iterations, convergence, diversity.

### 6.8 RoutingStatistics (src/e3hybrid/routing/statistics.py)
Frozen: nodes_explored, edges_explored, candidates_generated, cache_hits, cache_misses, memory_bytes.

### 6.9 RoutingFactory (src/e3hybrid/routing/factory.py)
Static methods: create_dijkstra(), create_astar(heuristic="zero"), create_aco(config=None), create_bco(config=None), create_pso(config=None), create_e3hybrid(config=None), create_algorithm(name). Dispatches: "dijkstra", "astar"/"astar/<heuristic>", "aco", "bco", "pso", "e3hybrid"/"hybrid"/"e3-hybrid".

### 6.10 RouteValidator & RoutingVerifier
RouteValidator: validate(route, graph, allow_blocked) -> RouteValidationReport (connectivity, blocking checks).
RoutingVerifier: verify_route/candidate/result, verify_determinism (N runs compare outputs), compare_results, compute_optimality_gap.

### 6.11 Heuristic System (src/e3hybrid/routing/heuristic.py)
Heuristic Protocol: estimate(node, dest, graph) -> float. Implementations: ZeroHeuristic (always 0), EuclideanHeuristic (straight-line), ManhattanHeuristic (|dx|+|dy|). HeuristicFactory creates by name. HeuristicValidator checks admissibility (never overestimates).

### 6.12 Exception Hierarchy
RoutingError -> NoPathError (no path exists), TimeoutError (exceeded time budget), InvalidRequestError


## 7. Baseline Routing Algorithms

### 7.1 DijkstraRouting (src/e3hybrid/routing/dijkstra.py)
Classical Dijkstra (1959). Priority queue (heapq), distance array, predecessor tracking. Uses TravelTimeCostProvider. O(E log V). Name: "dijkstra". Avg: ~4ms per request.

Algorithm:
1. Initialize distances[source]=0, predecessors={}
2. Priority queue with (0, source)
3. Pop smallest, if node==destination -> reconstruct path
4. For each outgoing edge: new_dist = dist[node] + edge_cost. If new_dist < dist[neighbor]: update + push
5. If destination not reached return failure

### 7.2 AStarRouting (src/e3hybrid/routing/astar.py)
A* (Hart, Nilsson & Raphael, 1968). Same structure as Dijkstra but f = g + h. With ZeroHeuristic = Dijkstra. Configurable heuristic. Name: "astar". Avg: ~5ms per request.


## 8. Swarm Infrastructure Framework

### 8.1 SwarmAlgorithm Protocol (src/e3hybrid/swarm/protocol.py)
```python
class SwarmAlgorithm(Protocol):
    @property
    def name(self) -> str: ...
    def optimize(self, context: SwarmContext) -> SwarmResult: ...
```

### 8.2 SwarmContext (src/e3hybrid/swarm/context.py)
Frozen dataclass: graph (DirectedGraph), cost_calculator (CompositeCostCalculator), config (SwarmConfig), routing_request (RoutingRequest), random_seed (int >=0), sim_time_s (float >=0, default 0), cost_weights (CostWeights).

### 8.3 SwarmConfig (src/e3hybrid/swarm/config.py)
Frozen dataclass: algorithm_name, population_size (default 20), max_iterations (default 100), time_limit_s (default 30.0), convergence_threshold (default 1e-6), stall_limit (default 10), target_score (float|None), seed (default 42), hyperparameters (dict), cost_weights (CostWeights).

### 8.4 Data Models (src/e3hybrid/swarm/models.py)
**Solution**: node_sequence, edge_sequence, metadata. **CandidateSolution**: solution, score (OptimizationScore), cost_breakdown, iteration_created, algorithm_specific. **OptimizationScore**: total, components, normalized, rank. **SearchState**: iteration, best_score, previous_best_score, no_improvement_count, diversity, elapsed_time_s. **Population**: individuals (list[CandidateSolution]), diversity, iteration. Properties: size, best, average_score, worst_score.

### 8.5 SwarmState (src/e3hybrid/swarm/state.py)
Immutable snapshot: iteration, population, best_solution (CandidateSolution|None), internal_state (dict).

### 8.6 SwarmStatistics & IterationStatistics (src/e3hybrid/swarm/statistics.py)
**IterationStatistics** (per-iteration): iteration, best/average/midrange/worst/std_dev scores, diversity, best_solution_changed, runtime.
**SwarmStatistics** (aggregate): total_iterations, total_runtime, best/average/worst scores, convergence_iteration, candidate_count, solutions_evaluated, diversity/score history, termination_reason.

### 8.7 SwarmResult (src/e3hybrid/swarm/result.py)
Frozen: best_solution (RouteCandidate), candidates (tuple[RouteCandidate]), statistics (SwarmStatistics), solutions_explored, iterations (tuple[IterationStatistics]), success, failure_reason.

### 8.8 SwarmRandom (src/e3hybrid/swarm/random.py)
Deterministic RNG with named sub-streams: get_stream(name) derives a sub-RNG via SHA-256(name + str(seed)). reset() clears cache. Each algorithm component uses a unique name: "aco_ant_0", "bee_3", "particle_5", etc.

### 8.9 Termination Conditions (src/e3hybrid/swarm/termination.py)
TerminationChecker evaluates in order: (1) max_iterations reached, (2) time_limit exceeded, (3) target_score achieved, (4) convergence_threshold (|prev-best| < threshold for stall_limit iterations), (5) stall_limit (no improvement for N iterations). Returns TerminationCondition(should_stop, reason, iteration, elapsed_time_s).

### 8.10 SwarmLifecycle (src/e3hybrid/swarm/lifecycle.py)
Common optimization loop: run(context, initialize_fn, update_fn, extract_best_fn). Calls initialize_fn -> loop: update_fn -> extract_best_fn -> compute stats -> check termination -> build SwarmResult. All algorithms share this loop via callbacks.

### 8.11 SwarmValidator (src/e3hybrid/swarm/validator.py)
Validates config, state, result, population: algorithm_name non-empty, population_size>0, max_iterations>0, time_limit_s>0, convergence_threshold>0, stall_limit>0, success/failure_reason consistency, statistics validity.

### 8.12 SwarmFactory (src/e3hybrid/swarm/factory.py)
Registry pattern: register(name, algorithm_class), create_algorithm(name, config), available_algorithms(), is_registered(), clear_registry(). Auto-registered: "aco", "bco", "pso", "e3hybrid".

### 8.13 SwarmToRoutingAdapter (src/e3hybrid/swarm/adapter.py)
Adapts SwarmAlgorithm to RoutingAlgorithm Protocol. compute_route(request, graph): builds SwarmContext, runs optimize(), converts SwarmResult to RoutingResult (Route from best_solution node/edge sequences, candidates mapping).

### 8.14 HybridPheromoneMatrix (src/e3hybrid/swarm/pheromone.py)
Sparse pheromone matrix with [tau_min, tau_max] clamping. Methods: get(edge_id), set(edge_id, value), local_update(edge_id, rho) -> tau = tau*(1-rho) + tau0*rho, clone(). Used by E3HybridRouting.


## 9. Swarm Algorithms (Detailed)

### 9.1 ACO - Ant Colony System (src/e3hybrid/swarm/aco.py, 999 lines)
**Reference**: Dorigo & Gambardella (1997), Stutzle & Hoos (2000) MMAS

```python
class ACSConfiguration:
    alpha: float = 1.0       # Pheromone exponent
    beta: float = 2.0        # Visibility exponent
    rho: float = 0.1         # Evaporation rate
    q0: float = 0.9          # Exploitation rate
    tau0: float = 1.0        # Initial pheromone
    tau_min: float = 0.01    # MMAS lower bound
    tau_max: float = 10.0    # MMAS upper bound
    elitism: int = 2         # Elite ants
    candidate_list_size: int = 10
    forward_steps: int = vehicle_count
```

Core components:
- **PheromoneMatrix**: sparse dict-based, get/set/add/decay/reinforce/clamp to [tau_min, tau_max]
- **VisibilityMatrix**: eta(e) = 1/(cost+EPS), candidate list (top-K by visibility)
- **TransitionRule**: if random() < q0: argmax(tau^alpha * eta^beta), else: roulette wheel
- **Ant**: current_node, visited (set), node_sequence, edge_sequence, total_cost, status (CONSTRUCTING|REACHED|STUCK)
- **PheromoneUpdater**: local_update (evaporation toward tau0), global_update (reinforce best), elite_update

Algorithm flow:
1. Initialize VisibilityMatrix (static heuristic) and PheromoneMatrix (tau0 for all edges)
2. For each iteration:
   a. Each ant constructs route: get candidates (outgoing not visited), apply TransitionRule, local_update
   b. Evaluate all ants, find best + iteration best
   c. Global pheromone update on best ant's edges: tau = tau*(1-rho) + rho*Q/cost
   d. Elite pheromone update on elite ants
   e. Evaporation, clamp to [tau_min, tau_max]
   f. Compute diversity (unique_edges/total_edges)
   g. Check termination (timeout via perf_counter, stall via no_improvement_count, convergence)
3. Return best solution

Profiling: tracks time per component (_profile_data). Timeout: checked each iteration. Stall: stops if no improvement after stall_limit.

### 9.2 BCO - Bee Colony Optimization (src/e3hybrid/swarm/bco.py, 879 lines)
**Reference**: Teodorovic (2009)

```python
class BCOConfiguration:
    forward_steps: int = vehicle_count  # Edges per forward pass
    beta: float = 1.0       # Visibility weight
    delta: float = 0.5      # Template strength
    elite_count: int = 3     # Elite bees
    loyalty_threshold: float = 0.5  # Eq 4 parameter
```

Algorithm flow:
1. Create N bees at source node, each with empty route
2. For each iteration:
   a. FORWARD PASS: each bee constructs route step-by-step:
      P(e) = visibility_bias(e)^beta * template_bias(e)^delta
      where visibility_bias = 1/(cost+EPS), template_bias = 1+delta if e in template else 1
      Select via roulette wheel
   b. BACKWARD PASS:
      - Evaluate quality Q = 1/route_cost
      - Normalize qualities
      - LOYALTY DECISION (Eq 4): compare own quality vs average
      - RECRUITMENT: disloyal bees adopt recruiter's template
      - Template update: retain top routes
   c. Update global best, check termination
3. Return best

Diversity: Jaccard distance between templates.

### 9.3 PSO - Particle Swarm Optimization (src/e3hybrid/swarm/pso.py, 864 lines)
**Reference**: Mohemmed et al. (2008), Shi & Eberhart (1998)

```python
class PSOConfiguration:
    forward_steps: int = vehicle_count
    inertia_start: float = 0.9    # Initial inertia weight
    inertia_end: float = 0.4      # Final inertia weight (linear decay)
    cognition_weight: float = 2.0  # c1 - personal best
    social_weight: float = 2.0     # c2 - global best
    visibility_weight: float = 1.0 # c3 - heuristic
    epsilon: float = 0.1           # Random exploration
```

Algorithm flow:
1. Create N particles, each constructs initial route (greedy). Set p_best = initial, g_best = best p_best.
2. For each iteration:
   a. Compute inertia: w = w_start - (w_start-w_end) * iter/max_iter
   b. FORWARD PASS: each particle constructs route using:
      INERTIA: I(e) = w * M_cur(e)      (1 if e in current route)
      COGNITION: P(e) = c1 * M_p(e)     (1 if e in p_best at same position)
      SOCIAL: G(e) = c2 * M_g(e)        (1 if e in g_best at same position)
      VISIBILITY: H(e) = c3 * 1/cost(e)
      weight(e) = I(e) + P(e) + G(e) + H(e)
      P(e) = weight(e)/sum(weights). With prob epsilon: random edge.
   c. BACKWARD PASS: evaluate, update p_best (Eq 14), update g_best (Eq 15)
   d. Compute diversity (Jaccard on personal bests), check termination

**Bug fix**: Inertia component (w * M_cur) was missing in original E3HybridRouting implementation. Fixed.

### 9.4 E3-Hybrid - Triple Swarm (src/e3hybrid/swarm/hybrid.py, 1207 lines)
**Novel**. Combines ACO+BCO+PSO with meta-control.

Population partitioned by ant_ratio (0.33), bee_ratio (0.33), particle_ratio (0.34).

CORRECTED EQUATIONS (Section 8.4 of design doc):

Edge selection probability (HYBRID):
  P(e) = [alpha_a * A(e) + alpha_b * B(e) + alpha_p * P(e) + alpha_h * H(e)]
         / sum([...]) over all candidates

Raw components:
- Raw ACO: A(e) = tau(e)^alpha_a  (Eq 3)
- Raw BCO: B(e) = 1 + delta_b if e in template else 1  (Eq 4)
- Raw PSO: P(e) = inertia * M_cur(e) + cognition * M_p(e) + social * M_g(e)  (Eq 5)
- Raw Heuristic: H(e) = 1.0 / (cost(e) + EPS)  (Eq 6)

Each raw value normalized to [0,1] by dividing by sum across candidates (Eqs 8-11).

Local pheromone update (ants): tau(e) = tau(e)*(1-rho) + tau0*rho (Eq 13)
Global pheromone update: tau(e) = tau(e)*(1-rho) + rho*Q/best_cost if e in best (Eqs 14-16)

META-CONTROLLER (every meta_control_interval iterations):
- Compute per-subpopulation diversity
- If diversity < target - tolerance: decay weight (Eq 23)
- If diversity > target + tolerance: recover weight (Eq 24)
- Redistribute decayed weights, normalize all to sum=1.0 (Eq 25)

36 hyperparameters total. Auto-registers as "e3hybrid".


## 10. Communication Framework

### 10.1 Core Types (src/e3hybrid/communication/)
MessageId = NewType("MessageId", str). DeliveryStatus: PENDING, DELIVERED, DROPPED, EXPIRED, OUT_OF_RANGE.
MessageType: TRAFFIC_UPDATE, ROAD_CLOSURE, HAZARD, EMERGENCY_VEHICLE, PHEROMONE_UPDATE, SCOUT_REPORT, VEHICLE_STATE, HEARTBEAT, ACKNOWLEDGEMENT, ROUTE_REQUEST, ROUTE_OFFER, COORDINATION, CUSTOM.
Priority (IntEnum): LOW=1, NORMAL=2, HIGH=3, CRITICAL=4.

### 10.2 Message (src/e3hybrid/communication/message.py)
Frozen dataclass: message_id, sender_id, message_type, priority, payload, is_broadcast, receiver_id, created_at_s, ttl_s, hop_count, max_hops, delivery_status.
Factory: Message.create(). Properties: expiration_time_s, is_expired(t), can_relay(). Immutable copy: with_status(), with_incremented_hop(). Serialization: to_dict().

### 10.3 Packet (src/e3hybrid/communication/packet.py)
Frozen dataclass (one delivery attempt): packet_id, message (never modified), sender_id, intended_receiver_id, transmitted_at_s, latency_s, delivery_status, is_relay, distance_m.
Factory: Packet.create(). Properties: arrival_time_s = transmitted_at_s + latency_s. Immutable copy: with_status(), with_latency().

### 10.4 Protocol Interfaces (src/e3hybrid/communication/protocols.py)
PacketLossModel: is_lost(packet) -> bool
LatencyModel: compute_latency_s(packet) -> float
CommunicationRadiusModel: in_range(sender, receiver) -> bool, receivers_in_range(sender, all) -> frozenset
CommunicationProtocol: bundles all three sub-models (loss_model, latency_model, radius_model)

### 10.5 Deterministic Baseline Models (src/e3hybrid/communication/models.py)
NoLossModel (never drops), ZeroLatencyModel (always 0s), ConstantLatencyModel (fixed delay), InfiniteRadiusModel (all in range), FixedRadiusModel (disk model with position registration), DeterministicProtocol (bundles NoLoss+ZeroLatency+InfiniteRadius).

### 10.6 MessageBus (src/e3hybrid/communication/bus.py)
Central coordinator: maintains Receiver registry. submit(message) queues. tick(current_time_s) processes all pending: check TTL, determine targets (broadcast via radius model, unicast single+range), create Packet per target, check loss, compute latency, deliver to inbox.
Broadcaster (send validates sender_id), Receiver (drain/peek).
Statistics via CommunicationStatistics (messages_sent/delivered/dropped/expired/out_of_range, latency, derived delivery_ratio/drop_ratio/average_latency). Packet log for experiment output.


## 11. Decision Engine

### 11.1 DecisionPolicy Protocol (src/e3hybrid/decision/policy.py)
```python
class DecisionPolicy(Protocol):
    @property
    def name(self) -> str: ...
    def evaluate(self, observation: VehicleObservation) -> list[PolicyRecommendation]: ...
```
PolicyRecommendation: decision_type, priority (higher=more important), confidence [0,1], has_veto (bool), explanation, metadata.

### 11.2 Six Policies
1. **SafetyPolicy** (priority 100, veto-capable): blocks impassable edges, enforces speed limits, vetoes routes with blocked edges.
2. **EmergencyPolicy** (priority 90): yields for emergency vehicles, reroutes on road closures/hazards.
3. **CongestionPolicy** (priority 60): reroutes on congestion (compares current vs alternative cost).
4. **CommunicationPolicy** (priority 50): decides when to broadcast state/hazards/pheromones.
5. **RoutingCandidatePolicy** (priority 40): evaluates candidates by total_cost only. KEEP or SWITCH route.
6. **BatteryPolicy** (priority 30): emergency stop if SoC<=min, wait if SoC below threshold, reduce speed.

DecisionType: KEEP_CURRENT_ROUTE, SWITCH_ROUTE, RECALCULATE, YIELD, EMERGENCY_STOP, REDUCE_SPEED, BROADCAST, REROUTE.

### 11.3 DecisionEngine (src/e3hybrid/decision/engine.py)
Tick-based: evaluate(observation) -> Decision: (1) Collect recommendations from all policies (sorted by priority descending), (2) Apply veto logic, (3) Aggregate non-veto by type, (4) Select winner (highest priority then highest confidence), (5) Build Decision, (6) Validate, (7) Log, (8) Return.

### 11.4 Observation System
ObservationAssembler: assemble(vehicle, graph, emergencies, comm_state) -> VehicleObservation (snapshot of vehicle, graph, active emergencies, comm state, battery).

### 11.5 Decision (src/e3hybrid/decision/decision.py)
Frozen: decision_id, vehicle_id, decision_type, recommendations (tuple), explanation, metadata. Validated after creation.

### 11.6 PolicyRegistry & PolicyManager
PolicyRegistry: global registry mapping str->type[DecisionPolicy]. PolicyManager: handles instantiation from config. register_all_policies() registers all 6 at startup.


## 12. Emergency Framework

### 12.1 Event Types (src/e3hybrid/emergency/enums.py)
EmergencyEventType: ROAD_CLOSURE, ROAD_BLOCK, TRAFFIC_ACCIDENT, EMERGENCY_VEHICLE, HAZARD_ZONE, INFRASTRUCTURE_FAILURE, COMMUNICATION_BLACKOUT.

### 12.2 Event Lifecycle (src/e3hybrid/emergency/types.py)
EventStatus: CREATED -> SCHEDULED -> ACTIVATED -> RESOLVED/EXPIRED.
EventLocation: edge_ids (list[EdgeId]), node_ids (list[NodeId]). EventId = NewType.

### 12.3 EmergencyEvent Protocol & Events
EmergencyEvent: event_id, event_type, status, location, start_time_s, duration_s, severity [0,1], effects() -> list[NetworkEffect], update(timestep_s).

Seven concrete events:
1. **TrafficAccidentEvent**: road closure + congestion. May spawn emergency vehicle event.
2. **EmergencyVehicleEvent**: corridor priority request (adds emergency_penalty_s).
3. **HazardZoneEvent**: additive hazard_penalty_s on affected edges.
4. **InfrastructureFailureEvent**: reduces current_speed_mps.
5. **CommunicationBlackoutEvent**: adds communication_penalty_s.
6. **RoadBlockEvent**: raises congestion_factor.
7. **RoadClosureEvent**: sets is_blocked=True (infinite traversal cost).

### 12.4 Network Effects (src/e3hybrid/emergency/effects.py)
NetworkEffect Protocol: apply_to(graph, edge_id), restore(graph, edge_id).
Concrete effects: BlockedEffect (is_blocked), CongestionEffect (congestion_factor), HazardPenaltyEffect (hazard_penalty_s), EmergencyPriorityEffect (emergency_penalty_s), CommunicationEffect (communication_penalty_s). All additive composition.

### 12.5 EmergencyEventBus (src/e3hybrid/emergency/bus.py)
Publish/subscribe: subscribe(subscriber, event_type, priority), unsubscribe, publish(event) notifies matching subscribers sorted by priority. Subscriber isolation (one exception doesn't affect others).

### 12.6 EmergencyRegistry (src/e3hybrid/emergency/registry.py)
Single source of truth: register(event), get(event_id), get_active(), get_by_type(type), update(timestep_s), reset(). Statistics: event counts by type and status.

### 12.7 EventScheduler (src/e3hybrid/emergency/scheduler.py)
Deterministic scheduling: schedule_fixed (exact times), schedule_random (random placement, seeded), schedule_recurring (periodic), schedule_progressive (increasing intensity).

### 12.8 ScenarioLoader (src/e3hybrid/emergency/scenario.py)
Reads YAML scenario files with event definitions. Validates schema, constructs EmergencyEvent objects.

### 12.9 NetworkEffectSubscriber (src/e3hybrid/emergency/subscribers/network_effect.py)
The ONLY module that touches DirectedGraph for emergencies. Applies effects on event activation, restores on resolution.


## 13. Vehicle & Energy Model

### 13.1 ElectricVehicle (src/e3hybrid/vehicle/entity.py, ~278 lines)
Mutable dataclass: vehicle_id, constraints (VehicleConstraints), battery (SimpleBattery), state (VehicleState), energy_model (FioriEnergyModel), metadata.
Methods: traverse_edge(dist, speed, accel, grade, duration) computes energy, discharges battery, returns new VehicleState. update_state(new_state) syncs from SUMO. Properties: soc_kwh, soc_fraction, is_below_min_soc, can_depart.

### 13.2 Battery (src/e3hybrid/vehicle/battery.py, ~259 lines)
Battery Protocol: capacity_kwh, soc_kwh, soc_fraction, discharge(delta), charge(delta), can_discharge(delta), clone_with_soc(soc).
SimpleBattery: linear capacity model, no degradation. Factory: create(capacity_kwh, initial_soc_kwh=0.8). Frozen dataclass, returns new instances on discharge/charge.

### 13.3 Energy Model (src/e3hybrid/vehicle/energy.py, ~327 lines)
EnergyModel Protocol: compute_energy_kwh(speed_mps, distance_m, accel, grade, duration) -> float.
FioriEnergyModel: Fiori et al. (2016) physics-based model. **STUB** - compute_energy_kwh validates inputs then raises NotImplementedError. Parameters: vehicle_mass_kg, drag_coefficient, frontal_area_m2, rolling_resistance, drivetrain_efficiency, regen_efficiency, auxiliary_power_w.

### 13.4 VehicleState & VehicleConstraints (src/e3hybrid/vehicle/state.py)
VehicleConstraints (frozen): min_soc_kwh, max_soc_kwh, max_speed_mps, max_payload_kg.
VehicleState (frozen): current_node (NodeId|None), current_edge, soc_kwh, speed_mps, acceleration_mps2, distance_travelled_m, time_elapsed_s, is_charging.

### 13.5 VehicleFactory & VehicleValidator
VehicleFactory.create_from_config(config: dict) -> ElectricVehicle: extracts battery, constraints, energy model, initial state from config. Private helpers with strict validation.
VehicleValidator: validates battery capacity vs constraints, SoC in [min, max], speed vs max_speed, warns on low SoC.


## 14. SUMO/TraCI Integration

### 14.1 SumoConfig (src/e3hybrid/sumo/config.py, ~103 lines)
Frozen dataclass: sumo_net_file, sumo_route_file, sumo_additional_file, sumo_binary ("sumo"/"sumo-gui"), sumo_seed, step_length_ms (default 1000), reroute_interval_steps (10), logging_interval_steps (10), use_gui (False), traci_port (8813), use_libsumo (True), algorithm_names, algorithm_split.
Factory: from_mapping(mapping: dict) -> SumoConfig.

### 14.2 SumoTraciConnection (src/e3hybrid/sumo/connection.py, ~294 lines)
The ONLY class communicating with SUMO/TraCI. Supports TCP traci and in-process libsumo.
Methods: start(), stop(), step(), reset().
Edge queries: get_edge_ids, get_edge_travel_time, get_edge_mean_speed, get_edge_occupancy, get_edge_lane_count, get_edge_length, get_edge_speed_limit, get_edge_from_junction, get_edge_to_junction.
Lane queries: get_lane_ids(edge_id), get_lane_connections(lane_id, edge_id), has_lane_connection(e1, e2) - critical for lane-level connectivity validation.
Vehicle queries: get_vehicle_ids, get_vehicle_route, get_vehicle_position (x,y,edge_id), get_vehicle_speed, get_vehicle_type, get_vehicle_emissions, set_vehicle_route(vid, edge_list).
Junction queries: get_junction_ids.
Simulation: get_simulation_time, get_min_expected_vehicles, get_teleport_count, get_arrived_count.
Route repair: find_route(from_edge, to_edge, vehicle_type) via traci.simulation.findRoute().

### 14.3 SumoNetworkImporter (src/e3hybrid/sumo/network_importer.py, ~127 lines)
Converts SUMO .net.xml to DirectedGraph:
1. Iterate junctions -> Node objects (with x,y coordinates)
2. Iterate edges -> Edge objects (static attributes)
3. Build lane-level successor map: for each edge, for each lane, for each connection -> add target edge to successors. This is CRITICAL - junction-level connectivity has ~20% false positives.
4. Populate graph._edge_successors.

### 14.4 SumoSimulation (src/e3hybrid/sumo/simulation.py, ~140 lines)
Main step loop: owns connection + graph. step(): conn.step(), update_graph_state (pull travel_time, mean_speed, occupancy, lane_count into MutableEdgeState). run(total_steps): loop step(). check_emergency(): detect emergency vehicles by type ID.

### 14.5 SumoReroutingManager (src/e3hybrid/sumo/rerouting_manager.py, ~401 lines)
Schedules and executes rerouting:
- should_reroute(vehicle_id, step, route): based on interval, route validity, emergency proximity.
- compute_reroute(vehicle_id, graph, request, algorithm): creates RoutingRequest with source_edge_id, runs algorithm.
- apply_reroute(vehicle_id, edges, conn): validates each consecutive edge pair with has_lane_connection(). Invalid pairs repaired via find_route(). If repair fails, reject reroute.
- RerouteLogEntry per attempt.

### 14.6 SumoEmergencyManager (src/e3hybrid/sumo/emergency_manager.py, ~218 lines)
Detects emergency vehicles via TraCI (type ID contains "emergency"). Activates: determines affected edges (3-edge radius ahead), sets emergency_penalty_s = 120s. Resolves: restores penalty to 0.
ActiveEmergency dataclass: id, vehicle_id, affected_edges, start_step, duration.

### 14.7 SumoExperimentRunner (src/e3hybrid/sumo/experiment_runner.py, ~203 lines)
Orchestrates complete experiment: load config, start SUMO, import network, create algorithm instances, build vehicle-to-algorithm mapping, run step loop (step, sync, emergencies, reroute, collect metrics), collect results (SumoExperimentResult), stop SUMO.

### 14.8 SumoRoutingAdapter (src/e3hybrid/sumo/adapters.py, ~54 lines)
Wraps RoutingAlgorithm for SUMO context: delegates compute_route() to wrapped algorithm, passing graph through.


## 15. Experiment Pipeline

### 15.1 preflight.py (618 lines)
Standalone environment checker. Checks: OS (Windows), Python (3.12+, <3.14), RAM (>=4GB), Disk (>=5GB), SUMO_HOME, SUMO binary, SUMO version (>=1.20, targets 1.27.1), traci/sumolib import, PyYAML/matplotlib/psutil/pytest, project files, network file, SUMO process test, libsumo test. Exit 0=PASS, 1=FAIL.
After pass: prints all 4 presets with descriptions, estimated runtimes, and exact copy-paste commands.

### 15.2 run_thesis.py (1245 lines)
Main launcher. 5-section pipeline:
[1/5] Environment Preflight -> calls preflight.py
[2/5] Pipeline Validation -> calls scripts/run_validation.py
[3/5] Full Experiment (Online Simulation) -> per-algorithm SUMO run
[4/5] Plot Generation -> calls scripts/generate_all_plots.py
[5/5] Final Summary -> prints metrics tables, routing benchmarks, artifacts list

### 15.3 Preset System
Four presets parameterized via PRESETS dict:
- **smoke**: 30 steps, 10 veh, 1 algo (dijkstra), no emergencies, no benches, no plots. ~10-20s. Installation verification.
- **light**: 100 steps, 50 veh, all 6 algos, no emergencies, benches but no plots. ~5-15 min. Quick comparison.
- **heavy**: 300 steps, 300 veh, all 6 algos, 3 emergencies, benches, 34 auto-plots. ~30-90 min. Thesis-quality.
- **extreme**: 600 steps, 500 veh, all 6 algos, 5 emergencies, benches, plots. ~2-6 hr. Stress-test.

Multi-seed: --seeds N N N runs experiment loop for each seed, separate output directories.

### 15.4 Online Simulation (simulate_algorithm)
Per algorithm:
1. Generate routes via randomTrips.py (if not cached)
2. Start SUMO (libsumo, in-process)
3. Import graph via SumoNetworkImporter
4. Create algorithm via RoutingFactory
5. Step loop (300 steps heavy):
   - Emergency activation at scheduled steps (emergency_penalty_s = 120s)
   - Emergency resolution after duration
   - Graph sync: read travel_time, mean_speed, occupancy from TraCI
   - Rerouting (every reroute_interval): compute new route, validate lane-level connectivity, apply if valid
   - Metrics collection: active vehicles, teleports, arrivals, congestion, speed, travel times
6. Stop SUMO, record peak memory via tracemalloc

### 15.5 Output Artifacts
| File | Description |
|------|-------------|
| metrics_summary.csv | Per-algorithm: travel time, speed, reroutes, throughput, emergencies, teleports, exec time, memory |
| simulation_log.csv | Per-step log: active vehicles, reroutes, emergencies, blocked/congested edges, speed |
| algorithm_timing.csv | Per-step timing: reroute latency, completed trips, travel time |
| emergency_log.csv | Emergency event timeline |
| routing_log.csv | Offline benchmarks: success rate, runtime, distance |
| config_snapshot.yaml | Full experiment configuration |
| experiment_manifest.json | Machine-readable: git commit, versions, seed, algorithms |
| environment.json | Python/SUMO/OS environment, packages, CPU, memory |
| network_metadata.json | Network properties |
| plots/png/ | 34 publication-ready figures |
| plots/data/ | Plot source data CSVs |

### 15.6 Offline Benchmarks
run_offline_benchmarks(): 50 random routing requests per algorithm on the graph (no SUMO simulation). Measures: success rate, avg/min/max runtime, avg distance.

### 15.7 Final Summary (print_final_summary)
Prints: experiment overview (algorithms, vehicles, steps, emergencies, teleports, wall-clock, git commit/tag), per-algorithm metrics table, routing benchmark table, generated artifacts list, output directory path, rerun instructions.


## 16. Plot Generation

scripts/generate_all_plots.py generates 34 figure groups from experiment output CSVs:
1. Algorithm Comparison - bar charts (travel time, speed, reroutes, throughput, emergencies)
2. Algorithm Timing - execution time and memory
3. Time Series - per-step metrics over simulation time
4. Route Analysis - distance vs travel time scatter, edge count distribution
5. Emergency Impact - per-algorithm emergency effects
6. Speed Profiles - speed distribution
7. Memory Usage - peak memory comparison
8. Routing Benchmarks - offline benchmark comparison
Output: PNG files in plots/png/, data CSVs in plots/data/.


## 17. Configuration System

### 17.1 Base Configuration (configs/base.yaml)
experiment: {name, seed, output_dir}, simulation: {backend: local}, logging: {level, log_dir, max_bytes, backup_count}, documentation: {docs_dir, require_research_docs}.

### 17.2 ProjectConfig (src/e3hybrid/config/schemas.py)
Typed dataclass: experiment_name, seed, output_dir, simulation_backend, log_level, log_dir, log_max_bytes, log_backup_count, docs_dir, require_research_docs.

### 17.3 ExperimentConfig (defined in run_thesis.py)
Simple dataclass: steps, vehicles, departure_period, seed, algorithms (tuple), reroute_interval, emergency_count, offline_benchmarks (bool).


## 18. Testing

### 18.1 Test Summary
**201 passed, 1 warning, 17.17s. Coverage: 34% (7607 stmts, 4793 missed)**

### 18.2 Test Organization
- **Unit tests** (tests/unit/): 42 test files covering all modules
  - Each algorithm: test_aco.py, test_bco.py, test_pso.py, test_hybrid.py, test_dijkstra.py, test_astar.py
  - Infrastructure: test_swarm_infrastructure.py, test_network_core.py, test_vehicle_core.py
  - Communication: test_communication_core.py
  - Decision: test_decision_engine.py, test_decision_aggregation.py, test_decision_validation.py, test_policy_registry.py
  - Emergency: test_emergency_core.py
  - Other: test_config_loader.py, test_benchmark.py, test_reproducibility.py, test_cli.py, test_logging.py
  - SUMO: sumo/test_connection.py, test_simulation.py, test_rerouting_manager.py, test_network_importer.py, etc.

- **Integration tests** (tests/integration/): determinism, real network, SUMO integration
- **Acceptance tests** (tests/acceptance/): end-to-end scenario testing
- **Benchmark tests** (tests/benchmarks/): performance benchmarks
- **Architecture tests** (tests/test_architecture.py): ~130 constraint tests - enforces clean architecture boundaries

### 18.3 Test Data (tests/data/)
- grid.net.xml: 4x4 grid network (16 nodes, 24 edges) for basic tests
- emergency.sumocfg: emergency scenario test config
- All test networks have associated route files and SUMO configs.

### 18.4 Test Commands
```powershell
pytest                     # All tests
pytest tests/unit/         # Unit tests only
pytest tests/integration/  # Integration tests only
pytest -v                  # Verbose
pytest --cov=src           # Coverage
pytest -n auto             # Parallel
```


## 19. Key Bug Fixes & Design Decisions

### 19.1 Route Replacement Fix (Lane-Level Successors)
**Problem**: Graph built with junction-level connectivity had ~20% false-positive edges. SUMO threw errors on invalid routes.

**Fix**: Added lane-level successor map in SumoNetworkImporter: for each edge, for each lane, for each connection -> populate _edge_successors in DirectedGraph. Algorithms now use get_successors() which returns only lane-valid edges.

### 19.2 Route Validation + Repair Layer (SumoReroutingManager)
Every route validated via has_lane_connection() before setVehicleRoute(). Invalid pairs repaired via find_route(). If repair fails, route silently rejected (vehicle keeps current route). Same validation applied inline in run_thesis.py.

### 19.3 PSO Inertia-Weight Bug Fix
**Problem**: In E3HybridRouting._compute_raw_pso(), inertia component (w * M_cur) was missing from weight calculation.

**Fix**: Added inertia * M_cur to PSO raw weight. Parameters threaded through: _forward_pass -> _construct_route -> _compute_raw_pso (inertia, p_best_edges, g_best_edges, forward_step_idx).

### 19.4 ACO Double-Lookup Fix
**Problem**: _not_deadend(eid, graph) called graph.get_edge(eid) for edges already available.

**Fix**: Renamed to _is_edge_alive(edge, graph, dest) accepting Edge object directly. Reduced get_edge operations by ~55%.

### 19.5 ACO Profiling + Timeout + Stall Detection
Added: time-per-component profiling (_profile_data), timeout via perf_counter (check each iteration), stall detection (no_improvement_count >= stall_limit), node_count caching outside loop.

### 19.6 Unicode Encoding Fix
Box-drawing characters replaced with ASCII in print_final_summary() to fix UnicodeEncodeError on Windows cp1252 terminals.

### 19.7 NameError Fix
main() called ExperimentConfig() before _imports() defined the class. Fixed by moving _imports() before ExperimentConfig creation.

### 19.8 Key Design Decisions (DD-001 through DD-020)
- DD-001: Protocol-based interfaces (swappable implementations)
- DD-002: Immutable data (thread safety, determinism)
- DD-003: Pure functions for routing (fair comparison)
- DD-004: Algorithm-agnostic evaluation (only total_cost)
- DD-005: Lane-level successors (eliminate false positives)
- DD-008: Sparse pheromone matrix (memory-efficient)
- DD-009: Seeded sub-streams via SHA-256 (deterministic randomness)
- DD-011: Periodic rerouting (simpler, deterministic)
- DD-012: Emergency effects via penalty seconds (additive composition)
- DD-013: MMAS bounds on pheromone (prevent premature convergence)
- DD-020: ACO timeout = 30s (bound worst-case runtime)


## 20. Parameter Values & Justification

### 20.1 Algorithm Parameters
| Algorithm | Parameter | Value | Source |
|-----------|-----------|-------|--------|
| **ACO** | alpha (pheromone) | 1.0 | Dorigo & Gambardella (1997) |
| | beta (visibility) | 2.0 | Dorigo & Gambardella (1997) |
| | rho (evaporation) | 0.1 | Stutzle & Hoos (2000) |
| | q0 (exploitation) | 0.9 | Dorigo & Gambardella (1997) |
| | tau_min/tau_max | 0.01/10.0 | Stutzle & Hoos (2000) MMAS |
| | elitism | 2 | Dorigo & Gambardella (1997) |
| | population | 20 | ~3x candidate list |
| **BCO** | beta (visibility) | 1.0 | Teodorovic (2009) |
| | delta (template) | 0.5 | Balanced exploitation |
| | elite count | 3 | Top 15% of population |
| | population | 20 | Comparable to ACO |
| **PSO** | inertia start | 0.9 | Shi & Eberhart (1998) |
| | inertia end | 0.4 | Shi & Eberhart (1998) |
| | cognition (c1) | 2.0 | Mohemmed et al. (2008) |
| | social (c2) | 2.0 | Mohemmed et al. (2008) |
| | epsilon | 0.1 | Mohemmed et al. (2008) |
| | population | 20 | Comparable to ACO/BCO |
| **E3-Hybrid** | alpha_a (ACO weight) | 0.3 | Cross-validated |
| | alpha_b (BCO weight) | 0.3 | Cross-validated |
| | alpha_p (PSO weight) | 0.2 | Cross-validated |
| | alpha_h (heuristic) | 0.2 | Cross-validated |
| | population | 30 | ~3x single algorithm |
| | max_iterations | 50 | ~2x single algorithm |
| | stall_limit | 8 | ~2x single algorithm |
| | ant/bee/particle ratio | 0.33/0.33/0.34 | Balanced |

### 20.2 Experiment Parameters (Heavy Preset)
300 steps (rush-hour period), 300 vehicles (~1500 veh/hr), departure period 1.0s, reroute interval 10 steps, 3 emergencies (1% of vehicles), emergency duration 20 steps, emergency penalty 120s (2min delay).


## 21. Profiling Results

### 21.1 Comparative Runtime (30 requests each on Manhattan network)
| Algorithm | Avg Time | Min Time | Max Time | Success Rate | Avg Distance |
|-----------|----------|----------|----------|-------------|-------------|
| **Dijkstra** | 4 ms | 1 ms | 44 ms | 100% | 1853 m |
| **A*** | 5 ms | 1 ms | 50 ms | 100% | 1853 m |
| **PSO** | 240 ms | 142 ms | 465 ms | 100% | 1884 m |
| **E3-Hybrid** | 944 ms | 831 ms | 1124 ms | 100% | 1891 m |
| **ACO** | 1084 ms | 899 ms | 1280 ms | 100% | 1895 m |
| **BCO** | 1411 ms | 1082 ms | 1865 ms | 100% | 1920 m |

### 21.2 Key Observations
- Baseline algorithms (Dijkstra, A*) are 50-350x faster than swarm algorithms
- Swarm algorithms find slightly longer routes (~2-4% longer) but adapt to dynamic conditions
- E3-Hybrid is faster than ACO and BCO (better convergence via meta-control)
- A* found identical routes to Dijkstra (as expected with admissible heuristic)
- 100% success rate for all algorithms (fully connected graph)
- PSO is the fastest swarm algorithm (constructive discrete approach scales well)


## 22. Reproducibility

### 22.1 Deterministic Execution Chain
1. Python seed set for random module
2. SUMO seed set via SumoConfig.sumo_seed
3. SwarmRandom: SHA-256(name + seed) derived sub-streams per algorithm component
4. Emergency schedule: seeded via random.Random(seed+2000)
5. Route generation: randomTrips.py --seed
6. Offline benchmarks: random.Random(seed+1)

### 22.2 Environment Metadata (src/e3hybrid/utils/reproducibility.py)
collect_environment_metadata() returns: python_version, python_executable, operating_system, os_release, architecture, machine, processor, cpu_count, installed_packages, git_commit, sumo_version, timestamp_utc, random_seed.
Written to environment.json in each experiment output directory.

### 22.3 Git Commit Pinning
experiment_manifest.json includes git_commit (full hash). git_commit.txt in output directory. Each experiment is linked to the exact source code version.

### 22.4 Experiment Manifest (experiment_manifest.json)
Machine-readable record: git_commit, git_tag, sumo_version, python_version, network filename, vehicle_count, simulation_steps, algorithms, seed, date, machine name, output path.


## 23. How to Reproduce the Full Experiment

### 23.1 On a fresh PC
```powershell
# 1. Install SUMO 1.27.1
# 2. Clone repo
git clone <repo-url>
cd THESIS_NEW

# 3. Setup Python
python -m venv .venv
.venv\Scripts\Activate.ps1
python "%SUMO_HOME%\tools\build_supplementary.py"
pip install -r requirements.txt
pip install -e .

# 4. Verify
python preflight.py

# 5. Smoke test
python run_thesis.py --preset smoke

# 6. Run experiment (heavy preset - thesis quality)
python run_thesis.py --preset heavy

# 7. Run with multiple seeds
python run_thesis.py --preset heavy --seeds 42 43 44

# 8. Stress test
python run_thesis.py --preset extreme
```

### 23.2 Expected Outputs
- Heavy preset: ~30-90 min, 6 output directories, 34 plots, 300 steps per algorithm
- Each algorithm produces: simulation_log.csv, metrics_summary.csv, routing_log.csv
- Final summary shows comparison table across all algorithms

### 23.3 Architecture Tests
```powershell
pytest tests/test_architecture.py  # Verify clean architecture boundaries
```

### 23.4 Validation
```powershell
python preflight.py                 # Environment check
python scripts/run_validation.py    # Pipeline validation
```

### 23.5 Profiling
```powershell
python scripts/profile_all_algorithms.py  # Comparative profiling (requires SUMO)
```

### 23.6 Plot Generation
```powershell
python scripts/generate_all_plots.py  # 34 figure groups from experiment output
```

