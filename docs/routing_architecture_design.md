# Routing Architecture Design

This document defines the architecture for the routing framework that will enable fair comparison between multiple routing algorithms (SUMO Baseline, Dijkstra, A*, ACO, BCO, PSO, E³-Hybrid).

**Status:** Phase 7A — Design approved. Phase 7B (Dijkstra baseline) fully implemented and tested. Phase 7D (A* with heuristic architecture) fully implemented and tested.

---

## 1. Research Goals

### Why Multiple Routing Algorithms Are Needed

The thesis evaluates E³-Hybrid against established baselines and swarm algorithms to demonstrate its effectiveness. Multiple algorithms are required because:

- **Baseline comparison:** SUMO Baseline provides the simulator's default routing behavior. Dijkstra and A* provide classical shortest-path baselines with proven optimality guarantees.
- **Swarm comparison:** ACO, BCO, and PSO represent different swarm intelligence paradigms. Comparing E³-Hybrid against these shows whether hybrid coordination provides measurable benefits over individual swarm approaches.
- **Scientific rigor:** A single comparison (e.g., E³-Hybrid vs. Dijkstra) is insufficient for a thesis. Multiple comparisons across algorithm families strengthen the validity of claims.
- **Contribution mapping:** By comparing against multiple algorithms, we can identify which aspects of E³-Hybrid (ACO's pheromone trails, BCO's scout exploration, PSO's particle coordination) contribute most to performance.

### Why a Common Routing Interface Is Essential

A common interface is essential for scientific validity:

- **Fair comparison:** Every algorithm receives identical inputs and produces identical output structures. Differences in performance are attributable to algorithm logic, not interface advantages.
- **Reproducibility:** Identical inputs guarantee that experiments can be reproduced across different hardware and software environments.
- **Thesis defensibility:** Reviewers can verify that comparisons are fair when the interface is standardized and documented.
- **Extensibility:** New algorithms can be added without modifying the evaluation framework. Future researchers can plug in their own algorithms using the same interface.

### Why Fairness Matters in Research Evaluation

Fairness is the foundation of credible research:

- **Avoiding bias:** If one algorithm has access to privileged information (e.g., direct graph modification, hidden constants), results are biased and indefensible.
- **Statistical validity:** Fair comparison ensures that performance differences are statistically significant and not artifacts of implementation advantages.
- **Ethical obligation:** Research must not mislead. Claims of superiority must be supported by fair, transparent methodology.
- **Publication requirements:** Peer-reviewed venues require rigorous methodology. Unfair comparisons lead to rejection.

### Why the Framework Separates Routing from Decision Making

Routing and decision making serve different purposes:

- **Routing algorithms** compute paths from source to destination based on graph topology and cost models. They are pure computational procedures.
- **Decision Engine** evaluates whether to accept, reject, or modify routing recommendations based on vehicle state, battery, emergency conditions, and policy constraints.
- **Separation benefits:**
  - Routing algorithms remain pure functions (easier to test, verify, and compare).
  - Decision logic can be modified without touching routing algorithms.
  - Multiple routing algorithms can be evaluated under the same decision policy.
  - The thesis can attribute performance to routing quality vs. decision quality independently.

---

## 2. Routing Architecture

### RoutingAlgorithm Protocol

```python
class RoutingAlgorithm(Protocol):
    """Interface that every routing algorithm must satisfy.
    
    Every algorithm is a pure function: given identical inputs, it produces
    identical outputs. No global state, no side effects, no graph modification.
    """
    
    @property
    def name(self) -> str:
        """Return the stable algorithm name used in logs and metrics."""
        ...
    
    def compute_route(
        self,
        request: RoutingRequest,
        context: RoutingContext,
    ) -> RoutingResult:
        """Compute a route from source to destination.
        
        This is the ONLY method an algorithm must implement.
        
        Parameters
        ----------
        request:
            The routing request (source, destination, constraints).
        context:
            The routing context (graph snapshot, cost provider, configuration).
        
        Returns
        -------
        RoutingResult
            The routing result with candidates, primary route, and statistics.
        
        Raises
        ------
        RoutingError
            If routing fails (no path exists, timeout, etc.).
        """
        ...
```

### RoutingContext

```python
@dataclass(frozen=True, slots=True)
class RoutingContext:
    """Immutable context provided to every routing algorithm.
    
    Contains all information needed for routing without allowing modification.
    """
    
    graph_snapshot: GraphSnapshot
    cost_provider: CostProvider
    config: RoutingAlgorithmConfig
    random_stream: random.Random  # Seeded for deterministic behavior
    sim_time_s: float
```

### RoutingRequest

```python
@dataclass(frozen=True, slots=True)
class RoutingRequest:
    """Immutable routing request from the Decision Engine or simulation core.
    
    All parameters are validated at construction time.
    """
    
    source_node: NodeId
    destination_node: NodeId
    vehicle_id: VehicleId
    vehicle_constraints: VehicleConstraints
    battery_state: BatterySnapshot
    max_candidates: int
    timeout_s: float
    metadata: dict[str, Any] = field(default_factory=dict)
```

### RoutingResult

```python
@dataclass(frozen=True, slots=True)
class RoutingResult:
    """Immutable result returned by every routing algorithm.
    
    All algorithms return exactly this structure. No algorithm-specific fields.
    """
    
    candidates: tuple[RouteCandidate, ...]
    primary_route: Route | None
    success: bool
    failure_reason: str | None
    statistics: RoutingStatistics
    runtime_s: float
```

### Route

```python
@dataclass(frozen=True, slots=True)
class Route:
    """Immutable ordered sequence of edges from source to destination.
    
    The Route is the actual path. RouteCandidate wraps Route with metadata.
    """
    
    route_id: RouteId
    node_sequence: tuple[NodeId, ...]
    edge_sequence: tuple[EdgeId, ...]
    total_distance_m: float
    estimated_travel_time_s: float
    estimated_energy_kwh: float
```

### RouteSegment

```python
@dataclass(frozen=True, slots=True)
class RouteSegment:
    """Immutable segment of a route (one edge with traversal metadata).
    
    Used for incremental rerouting and partial route updates.
    """
    
    edge_id: EdgeId
    source: NodeId
    target: NodeId
    distance_m: float
    travel_time_s: float
    energy_kwh: float
    cost: float
```

### RouteCost

```python
@dataclass(frozen=True, slots=True)
class RouteCost:
    """Immutable cost breakdown for a route.
    
    Provides transparency into how total cost was computed.
    """
    
    total: float
    distance_cost: float
    time_cost: float
    energy_cost: float
    congestion_penalty: float
    hazard_penalty: float
    emergency_penalty: float
    communication_penalty: float
    components: dict[str, float]
```

### RouteCandidate

```python
@dataclass(frozen=True, slots=True)
class RouteCandidate:
    """Immutable candidate route produced by a routing algorithm.
    
    This is the structure passed to the Decision Engine for evaluation.
    """
    
    route_id: RouteId
    node_sequence: tuple[NodeId, ...]
    edge_sequence: tuple[EdgeId, ...]
    total_cost: float
    cost_breakdown: RouteCost
    algorithm: str
    metadata: dict[str, Any]
    runtime_s: float
    search_statistics: SearchStatistics
```

### RoutingStatistics

```python
@dataclass(frozen=True, slots=True)
class RoutingStatistics:
    """Immutable statistics collected during routing.
    
    Used for algorithm comparison and thesis metrics.
    """
    
    nodes_explored: int
    edges_explored: int
    candidates_generated: int
    cache_hits: int
    cache_misses: int
    memory_bytes: int
```

### RouteCache

```python
class RouteCache:
    """Cache for routing results to avoid redundant computation.
    
    Design (deferred implementation):
    - Cache key: (source, destination, graph_state_hash, config_hash)
    - Cache invalidation: on graph state change, emergency event, timeout
    - Future: incremental routing, partial rerouting
    """
    
    def get(self, key: CacheKey) -> RouteCandidate | None:
        """Retrieve cached route if available and valid."""
        ...
    
    def put(self, key: CacheKey, candidate: RouteCandidate) -> None:
        """Store a route candidate in the cache."""
        ...
    
    def invalidate(self, edge_ids: frozenset[EdgeId]) -> None:
        """Invalidate all routes affected by edge state changes."""
        ...
```

### RouteValidator

```python
class RouteValidator:
    """Validates routes before they are returned or accepted.
    
    Checks:
    - Connectivity (edges form a valid path)
    - No blocked edges (unless explicitly allowed)
    - Cost consistency
    - Battery feasibility
    """
    
    def validate(self, route: Route, context: RoutingContext) -> RouteValidationReport:
        """Validate a route against the current context."""
        ...
```

---

## 3. Routing Lifecycle

```
Receive RoutingRequest
↓
Validate Request (source/destination exist, constraints valid)
↓
Build RoutingContext (graph snapshot, cost provider, seeded random)
↓
Check RouteCache (return cached if valid)
↓
Call RoutingAlgorithm.compute_route(request, context)
↓
Algorithm explores graph using CostProvider
↓
Algorithm generates RouteCandidate(s)
↓
Validate RouteCandidate(s) with RouteValidator
↓
Return RoutingResult
```

**Invariants:**
- The routing layer never directly modifies vehicles or the graph.
- All graph access is read-only through GraphSnapshot.
- All cost queries go through CostProvider (no direct edge field access).
- Randomness is seeded via RoutingContext.random_stream for determinism.

---

## 4. Routing Inputs

Every routing algorithm receives the following inputs via `RoutingRequest` and `RoutingContext`:

### From RoutingRequest

- **source_node:** Origin node ID (must exist in graph)
- **destination_node:** Target node ID (must exist in graph)
- **vehicle_id:** Vehicle identifier (for logging and cache key)
- **vehicle_constraints:** Operational limits (min/max SoC, max speed, max payload)
- **battery_state:** Current battery snapshot (soc_kwh, capacity_kwh, soc_fraction)
- **max_candidates:** Maximum number of candidates to return
- **timeout_s:** Maximum allowed runtime before aborting
- **metadata:** Optional algorithm-specific parameters (e.g., ACO alpha, beta, rho)

### From RoutingContext

- **graph_snapshot:** Neighbourhood-scoped graph view (current edge, neighbours, blocked edges, costs)
- **cost_provider:** Cost computation interface (abstracts cost model from algorithms)
- **config:** Algorithm configuration (weights, thresholds, hyperparameters)
- **random_stream:** Seeded random generator (deterministic behavior)
- **sim_time_s:** Current simulation clock (for time-dependent costs)

### Future Swarm Parameters (Phases 8-11)

- **pheromone_trails:** ACO pheromone values on edges (read-only)
- **scout_reports:** BCO scout exploration data (read-only)
- **particle_positions:** PSO particle best-known positions (read-only)
- **swarm_state:** Hybrid coordination state (read-only)

---

## 5. Routing Outputs

Every routing algorithm must return exactly the same `RoutingResult` structure:

```python
RoutingResult(
    candidates=tuple[RouteCandidate, ...],  # All generated candidates
    primary_route=Route | None,              # Best route (or None if failure)
    success=bool,                            # Whether routing succeeded
    failure_reason=str | None,               # Human-readable failure explanation
    statistics=RoutingStatistics,             # Exploration and performance metrics
    runtime_s=float,                         # Actual computation time
)
```

### RouteCandidate Contents

- **route_id:** Unique identifier for this candidate
- **node_sequence:** Ordered nodes from source to destination
- **edge_sequence:** Ordered edges corresponding to node transitions
- **total_cost:** Scalar cost (used by Decision Engine for comparison)
- **cost_breakdown:** Detailed cost components (for thesis analysis)
- **algorithm:** Algorithm name (for logging only, never used in evaluation)
- **metadata:** Algorithm-specific annotations (pheromone levels, particle scores, etc.)
- **runtime_s:** Time taken to generate this specific candidate
- **search_statistics:** Nodes/edges explored for this candidate

### Failure Handling

If routing fails:
- `success = False`
- `primary_route = None`
- `candidates = ()` (empty tuple)
- `failure_reason` contains human-readable explanation (e.g., "No path exists", "Timeout", "Destination unreachable")

---

## 6. Cost Architecture

### Modular Cost System

Cost computation is abstracted through `CostProvider` Protocol. Each cost component is independently configurable:

```python
class CostProvider(Protocol):
    def cost(self, edge: Edge) -> EdgeCost:
        """Return the cost of traversing an edge."""
        ...
```

### Cost Components

| Component | Purpose | Configurable |
|-----------|---------|--------------|
| **DistanceCost** | Physical length of edge | Weight |
| **TravelTimeCost** | Time to traverse at current speed | Weight |
| **CongestionCost** | Traffic slow-down multiplier | Weight, threshold |
| **HazardCost** | Hazard zone penalty | Weight, threshold |
| **CommunicationCost** | Communication disruption penalty | Weight, threshold |
| **EmergencyCost** | Emergency corridor penalty | Weight, threshold |
| **EnergyCost** | Battery energy consumption | Weight, model selection |
| **CompositeCost** | Weighted sum of all components | All weights |

### Cost Composition

Total cost is computed as:

```
total_cost = w_distance * distance_cost
           + w_time * travel_time_cost
           + w_energy * energy_cost
           + w_congestion * congestion_penalty
           + w_hazard * hazard_penalty
           + w_emergency * emergency_penalty
           + w_communication * communication_penalty
```

All weights are configurable via YAML. Default weights can be tuned per experiment.

### Why Modular Cost?

- **Fair comparison:** Every algorithm uses the same cost model. Differences are due to algorithm logic, not cost computation.
- **Thesis analysis:** Cost breakdowns allow analysis of which factors (congestion, hazards, energy) most influence routing decisions.
- **Experiment flexibility:** Different experiments can emphasize different objectives (e.g., energy-focused vs. time-focused routing).
- **Extensibility:** New cost components (e.g., carbon emissions, toll costs) can be added without modifying algorithms.

---

## 7. Objective Function

### Configurable Weighted Composition

The objective function is a weighted sum of cost components:

```
f(route) = Σ (w_i * c_i(route))
```

where:
- `w_i` is the weight for component `i` (configurable)
- `c_i(route)` is the cumulative cost of component `i` along the route

### Why Weighted Composition?

- **Flexibility:** Different research questions require different objective functions (e.g., minimize time vs. minimize energy).
- **Thesis contribution:** We can study how weighting affects algorithm performance and E³-Hybrid's advantage.
- **Multi-objective optimization:** Weighted composition approximates Pareto optimization without requiring full Pareto front computation.
- **Reproducibility:** Explicit weights make the objective function transparent and reproducible.

### Independence from Algorithms

Routing algorithms never know the exact objective function equation. They:
- Call `cost_provider.cost(edge)` for each edge
- Sum edge costs to get route cost
- Return the route with minimum total cost

This separation means:
- The objective function can be changed without modifying algorithms.
- Algorithms remain pure (no knowledge of weights or component formulas).
- Fair comparison is preserved across different objective functions.

---

## 8. RouteCandidate

### Precise Definition

`RouteCandidate` is the complete, immutable representation of a candidate route:

```python
@dataclass(frozen=True, slots=True)
class RouteCandidate:
    """A candidate route produced by a routing algorithm.
    
    This is the structure passed to the Decision Engine for evaluation.
    The Decision Engine evaluates ONLY on total_cost — it never inspects
    how cost was computed or which algorithm produced the candidate.
    """
    
    route_id: RouteId
    node_sequence: tuple[NodeId, ...]
    edge_sequence: tuple[EdgeId, ...]
    total_cost: float
    cost_breakdown: RouteCost
    algorithm: str
    metadata: dict[str, Any]
    runtime_s: float
    search_statistics: SearchStatistics
```

### Field Purposes

| Field | Purpose | Used by Decision Engine? |
|-------|---------|--------------------------|
| route_id | Unique identifier | No (logging only) |
| node_sequence | Path nodes | No (logging only) |
| edge_sequence | Path edges | No (logging only) |
| total_cost | Scalar cost | **Yes** (evaluation) |
| cost_breakdown | Cost components | No (analysis only) |
| algorithm | Algorithm name | No (logging only) |
| metadata | Algorithm annotations | No (logging only) |
| runtime_s | Generation time | No (analysis only) |
| search_statistics | Exploration metrics | No (analysis only) |

### Immutability

`RouteCandidate` is frozen (immutable) because:
- Deterministic replay requires that candidates never change after generation.
- Thread safety: multiple vehicles can evaluate the same candidate concurrently.
- Auditability: logged candidates must match the original generated version.

### Validation

`RouteCandidate` is validated at construction:
- `node_sequence` and `edge_sequence` must be non-empty
- `total_cost` must be non-negative
- `edge_sequence[i]` must connect `node_sequence[i]` to `node_sequence[i+1]`
- `cost_breakdown.total` must equal `total_cost` (within floating-point tolerance)

---

## 9. Algorithm Independence

### Pure Function Requirement

Every routing algorithm must be a pure function:

**Given identical inputs → identical outputs**

### What Algorithms Implement

Each algorithm implements ONLY:

```python
def compute_route(
    self,
    request: RoutingRequest,
    context: RoutingContext,
) -> RoutingResult:
    """Compute a route. This is the ONLY method."""
    ...
```

### What Algorithms Must NOT Do

- **No logging:** Use the provided `random_stream` for deterministic behavior, but do not write logs directly. Logging is handled by the routing framework.
- **No visualization:** Do not generate plots, heatmaps, or visual output. Visualization is a separate analysis phase.
- **No SUMO:** Do not import `traci` or any SUMO-specific module. SUMO integration is handled by the adapter layer (Phase 12).
- **No communication:** Do not send or receive messages. Communication is handled by the Decision Engine and MessageBus.
- **No emergency handling:** Do not subscribe to emergency events or modify emergency state. Emergency effects are reflected in GraphSnapshot and CostProvider.
- **No decision logic:** Do not implement yielding, waiting, or speed reduction. These are Decision Engine responsibilities.
- **No graph modification:** Do not call `DirectedGraph.update_edge_state`. Graph is read-only through GraphSnapshot.
- **No vehicle modification:** Do not modify vehicle state. Vehicles are immutable entities.
- **No global state:** Do not use module-level variables or singletons. All state must be passed via `RoutingContext`.

### Why This Restriction?

- **Fair comparison:** If one algorithm has privileged access (e.g., direct graph modification), results are biased.
- **Testability:** Pure functions are easy to unit test with mock inputs.
- **Reproducibility:** No hidden state means identical inputs always produce identical outputs.
- **Thesis defensibility:** Reviewers can verify that algorithms are compared on equal terms.

---

## 10. Caching

### RouteCache Design

```python
class RouteCache:
    """Cache for routing results to avoid redundant computation.
    
    Cache key: (source, destination, graph_state_hash, config_hash)
    """
    
    def get(self, key: CacheKey) -> RouteCandidate | None:
        """Retrieve cached route if available and valid."""
        ...
    
    def put(self, key: CacheKey, candidate: RouteCandidate) -> None:
        """Store a route candidate in the cache."""
        ...
    
    def invalidate(self, edge_ids: frozenset[EdgeId]) -> None:
        """Invalidate all routes affected by edge state changes."""
        ...
```

### Cache Key Components

- **source:** Origin node ID
- **destination:** Target node ID
- **graph_state_hash:** Hash of edge states (blocked status, congestion, penalties)
- **config_hash:** Hash of algorithm configuration (weights, hyperparameters)

### Cache Invalidation

Cache entries are invalidated when:
- An edge state changes (blocked/unblocked, congestion change, penalty change)
- Emergency event affects cached edges
- Configuration changes (weights, hyperparameters)
- Cache entry expires (time-based TTL)

### Future Incremental Routing

Phase 7B+ will implement:
- **Partial rerouting:** When a road closes, recompute only the affected segment.
- **Incremental search:** Reuse previously explored graph regions.
- **Cache warming:** Pre-compute routes for high-demand origin-destination pairs.

### Deferred Implementation

Caching is designed but not implemented in Phase 7A. Implementation will proceed after the routing architecture is approved and baseline algorithms are implemented.

---

## 11. Incremental Routing

### When Rerouting Is Needed

Rerouting is required after:
- **Road closures:** Emergency events block edges on current route
- **Accidents:** Congestion penalties increase beyond threshold
- **Hazards:** Hazard penalties appear on current route
- **Communication failures:** Communication penalties affect route feasibility
- **Battery constraints:** Current route exceeds remaining energy

### Incremental Rerouting Strategy

Instead of recomputing the entire route from scratch:

1. **Identify affected segment:** Find the first blocked/penalized edge on current route
2. **Recompute sub-route:** Compute new path from affected edge's source to destination
3. **Splice routes:** Concatenate unaffected prefix with new sub-route
4. **Validate:** Ensure spliced route is valid and feasible

### Benefits

- **Performance:** Avoids exploring the entire graph for small perturbations
- **Real-time response:** Faster reaction to dynamic conditions
- **Energy efficiency:** Less computation = less energy (relevant for embedded deployment)

### Deferred Implementation

Incremental routing is designed but not implemented in Phase 7A. Implementation will proceed after baseline routing is stable.

---

## 12. Benchmark Fairness

### Identical Conditions

Every algorithm is benchmarked under identical conditions:

| Condition | Requirement |
|-----------|-------------|
| **Graph** | Same directed graph (same topology, same initial state) |
| **Requests** | Same set of source-destination pairs |
| **Seed** | Same random seed for all stochastic algorithms |
| **Scenarios** | Same emergency event sequences |
| **Hardware** | Same CPU, memory, OS (or record hardware specs) |
| **Stopping Criteria** | Same timeout, same iteration limits |
| **Timeout** | Same maximum runtime per request |
| **Metrics** | Same evaluation metrics (cost, time, energy, explored nodes) |
| **Configuration** | Same cost weights, same hyperparameters (unless comparing hyperparameter sensitivity) |

### No Algorithm-Specific Advantages

- **No privileged information:** All algorithms access the graph through the same GraphSnapshot.
- **No hidden constants:** All parameters are explicit in configuration files.
- **No special initialization:** All algorithms start from the same initial state.
- **No early termination:** All algorithms run until timeout or convergence (unless comparing early-stopping strategies).

### Benchmark Protocol

1. **Load graph:** Load the same graph file for all algorithms.
2. **Load scenarios:** Load the same emergency event sequences.
3. **Initialize random:** Seed all random streams with the same seed.
4. **Warm-up cache:** Clear cache before each algorithm (or use same cache state).
5. **Run requests:** Execute the same request sequence for each algorithm.
6. **Collect metrics:** Record runtime, cost, energy, explored nodes for each request.
7. **Statistical analysis:** Perform paired statistical tests (e.g., Wilcoxon signed-rank) to determine significance.

### Reproducibility

Every benchmark run produces:
- Environment metadata (Python version, OS, CPU, packages)
- Graph fingerprint (hash of graph serialization)
- Configuration fingerprint (hash of config files)
- Random seed
- Full results CSV (every request, every algorithm, every metric)

This ensures benchmarks can be reproduced exactly.

---

## 13. Baseline Algorithms

### SUMO Baseline

**Description:** SUMO's built-in routing algorithm (typically Dijkstra or A* with SUMO-specific cost model).

**Purpose:** Provides the simulator's default behavior as a reference point.

**Why chosen:**
- Industry standard for traffic simulation
- Represents "current practice" in routing
- Useful for showing that E³-Hybrid improves over simulator defaults

**Implementation notes:**
- Will be wrapped in the `RoutingAlgorithm` interface via SUMO adapter (Phase 12)
- SUMO's cost model will be approximated in our `CostProvider` for fair comparison

### Dijkstra

**Description:** Classical shortest-path algorithm with guaranteed optimality for non-negative edge weights.

**Purpose:** Provides a provably optimal baseline for static graphs.

**Why chosen:**
- Well-understood, extensively studied
- Optimal for static graphs (provides upper bound on cost)
- Simple implementation serves as sanity check
- Fast for sparse graphs (O(V²) with adjacency matrix, O(E + V log V) with priority queue)

**Implementation notes:**
- Standard priority queue implementation
- Uses `CostProvider` for edge costs
- Returns single best route (no candidates)

### A* (A-Star) — Phase 7D Complete

**Description:** Heuristic search algorithm that uses a distance heuristic to guide search toward the destination.

**Purpose:** Provides an efficient baseline for large graphs with good heuristics.

**Why chosen:**
- Faster than Dijkstra when a good heuristic is available
- Still optimal when heuristic is admissible (never overestimates)
- Commonly used in routing applications
- Demonstrates the value of heuristics (relevant for swarm algorithms)

**Implementation notes:**
- Implements `RoutingAlgorithm` Protocol (same interface as Dijkstra)
- Heap-based priority queue with f = g + h ordering
- Uses `CostProvider` for edge costs (same as Dijkstra)
- Returns multiple candidates (same alternative-path strategy as Dijkstra)
- Heuristic Protocol with 3 implementations: `ZeroHeuristic`, `EuclideanHeuristic`, `ManhattanHeuristic`
- `ZeroHeuristic` produces identical results to Dijkstra (verified)
- Supports tie-breaking for deterministic behavior
- Same timeout, blocked-edge, cycle, and disconnected-graph handling as Dijkstra

**Heuristic architecture:**
- `Heuristic` Protocol — `estimate(source, destination, graph) -> float`
- `ZeroHeuristic` — always returns 0.0 (A* → Dijkstra equivalence)
- `EuclideanHeuristic` — straight-line distance with optional scale factor
- `ManhattanHeuristic` — grid distance with optional scale factor
- `HeuristicFactory` — creates heuristics by name with config
- `HeuristicValidator` — checks admissibility and consistency
- All heuristics are admissible and consistent (proven)

---

## 14. Swarm Algorithms

### Common Interfaces

All swarm algorithms (ACO, BCO, PSO) implement the same `RoutingAlgorithm` Protocol:

```python
class SwarmRoutingAlgorithm(Protocol):
    @property
    def name(self) -> str:
        ...
    
    def compute_route(
        self,
        request: RoutingRequest,
        context: RoutingContext,
    ) -> RoutingResult:
        ...
```

### Shared Swarm Infrastructure (Phase 8)

Before implementing individual swarm algorithms, Phase 8 will implement:

- **SwarmState:** Shared state for pheromone trails, scout reports, particle positions
- **SwarmContext:** Extends `RoutingContext` with swarm-specific data
- **SwarmStatistics:** Common metrics (iteration count, convergence, diversity)
- **SwarmValidator:** Validates swarm state (pheromone bounds, particle constraints)

### ACO (Ant Colony Optimization) — Phase 9

**Description:** Probabilistic algorithm inspired by ant foraging behavior. Ants deposit pheromones on edges; future ants follow stronger pheromone trails.

**Key components:**
- **Pheromone trails:** Evaporate over time, reinforced by successful routes
- **Probabilistic edge selection:** Based on pheromone level and heuristic information
- **Parameters:** alpha (pheromone weight), beta (heuristic weight), rho (evaporation rate)

**Why chosen:**
- Well-established in routing literature
- Good for dynamic environments (pheromones adapt to changes)
- Decentralized (ants act independently, similar to vehicle coordination)

### BCO (Bee Colony Optimization) — Phase 10

**Description:** Inspired by bee foraging. Scout bees explore randomly; employed bees exploit known food sources; onlooker bees choose sources probabilistically.

**Key components:**
- **Scout bees:** Random exploration (good for discovering new routes)
- **Employed bees:** Exploit known good routes
- **Onlooker bees:** Probabilistic selection based on route quality
- **Parameters:** scout ratio, onlooker selection probability

**Why chosen:**
- Balances exploration (scouts) and exploitation (employed/onlookers)
- Good for dynamic environments (scouts adapt to changes)
- Less studied than ACO in routing (novel contribution potential)

### PSO (Particle Swarm Optimization) — Phase 11

**Description:** Inspired by bird flocking. Particles move through solution space, adjusting velocity based on personal best and global best positions.

**Key components:**
- **Particles:** Represent candidate routes (encoded as node sequences)
- **Velocity:** Adjusts particle movement toward best-known positions
- **Parameters:** inertia weight, cognitive coefficient, social coefficient

**Why chosen:**
- Fast convergence to good solutions
- Well-studied in optimization literature
- Different paradigm from ACO/BCO (provides diversity in comparison)

---

## 15. Hybrid Algorithm (E³-Hybrid)

### Integration Architecture

E³-Hybrid integrates ACO, BCO, and PSO through the Decision Engine:

```
ACO (pheromone trails)
↓
BCO (scout exploration)
↓
PSO (particle coordination)
↓
Decision Engine (policy evaluation)
↓
RoutingResult
```

### How Components Interact

1. **ACO phase:** Ants deposit pheromones on edges based on route quality. Pheromones guide initial route exploration.
2. **BCO phase:** Scout bees explore regions with low pheromone (potential undiscovered good routes). Scout reports supplement pheromone information.
3. **PSO phase:** Particles (representing routes) adjust based on personal best (ACO-influenced) and global best (BCO-influenced). PSO refines routes toward convergence.
4. **Decision Engine:** Evaluates final route candidates against policies (safety, battery, emergency, congestion). Selects winning route.
5. **RoutingResult:** Returns selected route with full metadata for logging and analysis.

### Why Hybrid?

- **Complementary strengths:** ACO provides pheromone guidance, BCO provides exploration, PSO provides fast convergence.
- **Robustness:** If one component underperforms (e.g., pheromones trap in local optimum), other components can compensate.
- **Novel contribution:** Hybrid swarm routing for EVs under dynamic emergencies is a novel research area.
- **Thesis impact:** Demonstrates that coordinated swarm intelligence outperforms individual approaches.

### Deferred Implementation

E³-Hybrid implementation will proceed after ACO, BCO, and PSO are individually implemented and validated.

---

## 16. Performance

### Time Complexity

| Algorithm | Best Case | Average Case | Worst Case | Notes |
|----------|-----------|--------------|------------|-------|
| Dijkstra | O(E + V log V) | O(E + V log V) | O(E + V log V) | With priority queue |
| A* | O(E) | O(E) | O(E) | With good heuristic |
| ACO | O(k × E) | O(k × E) | O(k × E) | k = iterations |
| BCO | O(k × E) | O(k × E) | O(k × E) | k = iterations |
| PSO | O(k × V) | O(k × V) | O(k × V) | k = iterations |
| E³-Hybrid | O(k × E) | O(k × E) | O(k × E) | k = iterations (ACO+BCO+PSO) |

where V = number of nodes, E = number of edges, k = number of iterations.

### Space Complexity

| Algorithm | Space Complexity | Notes |
|----------|-----------------|-------|
| Dijkstra | O(V) | Priority queue + visited set |
| A* | O(V) | Priority queue + visited set |
| ACO | O(E) | Pheromone matrix |
| BCO | O(E) | Scout reports |
| PSO | O(V × p) | p = particle count |
| E³-Hybrid | O(E + V × p) | Combined storage |

### Expected Scalability

- **Graph size:** Designed for city-scale networks (10,000–100,000 nodes). Sparse adjacency lists keep memory proportional to actual road density.
- **Vehicle count:** Routing is per-vehicle, so complexity scales linearly with vehicle count. Parallelization is possible (each vehicle routed independently).
- **Real-time requirements:** With caching and incremental rerouting, expected per-vehicle routing time < 100ms for typical city graphs.

### Memory Considerations

- **Graph storage:** O(V + E) with adjacency lists. For 50,000 nodes and 200,000 edges: ~10–20 MB.
- **Pheromone storage (ACO):** O(E). For 200,000 edges: ~1.6 MB (float64 per edge).
- **Particle storage (PSO):** O(V × p). For 50,000 nodes and 50 particles: ~20 MB.
- **Cache storage:** O(R × C) where R = routes cached, C = average route length. Configurable limit.

### Parallelization Opportunities

- **Per-vehicle parallelism:** Each vehicle can be routed independently. Embarrassingly parallel.
- **Algorithm parallelism:**
  - ACO: Ants can explore in parallel
  - BCO: Scouts can explore in parallel
  - PSO: Particle updates can be parallelized
- **Graph partitioning:** For very large graphs, partition graph and route within partitions (future optimization)

---

## 17. Testing

### Correctness Testing

**Unit tests for each algorithm:**
- Known graph with known optimal route → verify algorithm finds optimal route
- Graph with no path → verify algorithm returns failure with correct reason
- Graph with multiple equal-cost paths → verify algorithm returns one valid path
- Graph with self-loops → verify algorithm handles correctly

**Integration tests:**
- Full routing pipeline (request → context → algorithm → result)
- Cache integration (cache hit, cache miss, invalidation)
- Route validation (connectivity, cost consistency)

### Optimality Testing

**For Dijkstra and A*:**
- Compare against brute-force enumeration on small graphs
- Verify that returned route cost equals minimum possible cost
- Test with various cost weight configurations

**For swarm algorithms:**
- Compare against Dijkstra on static graphs (swarm should approach optimal)
- Measure convergence rate (cost improvement over iterations)
- Test sensitivity to hyperparameters (alpha, beta, rho, etc.)

### Edge Cases

- **Disconnected graphs:** Source and destination in different components
- **Single-node graphs:** Source equals destination
- **Blocked graphs:** All paths blocked by emergency events
- **Extreme weights:** Very high congestion or hazard penalties
- **Zero-cost edges:** Edges with zero cost (should not cause division by zero)
- **Negative costs:** Should be rejected by validation (costs must be non-negative)

### Disconnected Graph Testing

- Verify algorithm returns failure with clear reason
- Verify no infinite loops or crashes
- Verify timeout is respected

### Blocked Roads Testing

- Verify algorithm routes around blocked edges
- Verify algorithm returns failure if no alternative path exists
- Verify cost computation respects blocked edge penalties (infinite cost)

### Performance Testing

- Measure runtime on graphs of increasing size (1K, 10K, 50K, 100K nodes)
- Verify runtime scales as expected (check for O(n²) anomalies)
- Measure memory usage and verify it stays within expected bounds
- Verify timeout is respected (algorithm aborts after timeout_s)

### Deterministic Replay Testing

- Run same request with same seed multiple times → verify identical results
- Run same request with different seeds → verify results differ (for stochastic algorithms)
- Verify random_stream is correctly seeded from RoutingContext

---

## 18. Open Questions

### Resolved in This Design

- **Interface design:** `RoutingAlgorithm` Protocol, `RoutingRequest`, `RoutingContext`, `RoutingResult` — defined
- **Cost architecture:** Modular `CostProvider` with configurable weights — defined
- **Fair comparison:** Identical inputs/outputs for all algorithms — defined
- **Algorithm independence:** Pure function requirement — defined
- **Caching strategy:** Cache key composition and invalidation — designed
- **Incremental routing:** Splice-based rerouting — designed

### Deferred to Implementation Phase

- **Exact hyperparameter values:** Will be tuned during implementation and experimentation
- **Cache size limits:** Will be determined based on memory profiling
- **Timeout values:** Will be determined based on performance testing
- **Heuristic function for A*:** Will be chosen based on graph characteristics (Euclidean vs. Manhattan)
- **Swarm parameter sensitivity:** Will be studied during experimentation

### Deferred to Future Phases

- **SUMO integration details:** Phase 12 will define TraCI adapter interface
- **Experiment framework:** Phase 13 will define benchmark execution and metrics collection
- **Visualization:** Phase 15 will define how to visualize routes and algorithm behavior

### No Unresolved Architectural Questions

All major architectural decisions are resolved in this document. The design is ready for implementation approval.

---

## Appendix: Architecture Rules

### Pure Function Requirement

Every routing algorithm must be a pure function:

```
Given identical inputs → identical outputs
```

No global state. No hidden randomness. No side effects. No graph modification. No vehicle modification.

### Deterministic Replay

Given the same:
- Graph
- Request (source, destination, constraints)
- Random seed
- Configuration (weights, hyperparameters)

Every algorithm must produce identical results across multiple runs.

### No Privileged Access

All algorithms access the graph through the same `GraphSnapshot`. All algorithms query costs through the same `CostProvider`. No algorithm has direct access to edge fields or internal graph state.

### Validation Before Execution

All inputs are validated before algorithm execution:
- Source and destination nodes must exist
- Constraints must be valid (non-negative, within bounds)
- Graph snapshot must be consistent
- Configuration must be valid (weights sum to 1, hyperparameters in range)

### Failure Transparency

If routing fails, the algorithm must:
- Return `success = False`
- Provide human-readable `failure_reason`
- Return empty `candidates` tuple
- Return `primary_route = None`

No silent failures. No exceptions propagated to simulation core.

---

## Conclusion

This routing architecture provides a fair, reproducible, and extensible framework for comparing multiple routing algorithms. The design ensures that:

1. **Fair comparison:** All algorithms operate under identical conditions.
2. **Scientific rigor:** Results are reproducible and defensible.
3. **Thesis contribution:** E³-Hybrid can be evaluated against established baselines and swarm algorithms.
4. **Extensibility:** New algorithms can be added without modifying the framework.

The architecture is ready for implementation approval. Phase 7B will implement baseline algorithms (Dijkstra, A*) following this design.
