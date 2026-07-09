# Ant Colony Optimization (ACO) Algorithm Design

**Status:** Phase 9A — Design document (awaiting approval). No implementation yet.

---

## 1. Research Motivation

### Why ACO for Dynamic Routing

Ant Colony Optimization is a natural fit for dynamic vehicle routing problems because:

- **Graph-compatible:** ACO operates directly on graph representations. Ants traverse edges just as vehicles do. No encoding or decoding of solutions is needed — the graph is its own solution space.
- **Dynamic adaptation:** Pheromone trails implicitly encode the history of successful routes. When the graph changes (road closure, congestion, emergency), pheromones evaporate and new trails form, allowing the colony to adapt without restarting from scratch.
- **Decentralized:** Each ant constructs a route independently. This mirrors real vehicle behavior and enables parallel evaluation. The colony has no central controller — emergent behavior arises from local interactions.
- **Multi-candidate generation:** A single colony run produces multiple candidate routes (one per ant per iteration). This naturally feeds the Decision Engine's requirement for alternative route candidates.

### Strengths

| Strength | Relevance to Thesis |
|----------|---------------------|
| Proven on vehicle routing | Extensive literature on ACO for VRP, dynamic VRP, and time-windowed VRP |
| Handles multiple objectives | Pheromone can encode composite cost (distance + time + energy + penalties) |
| Graceful degradation | If no path exists, pheromones converge to indicate the least-bad route |
| Parameter-tunable exploration | Alpha/beta/rho control how much the colony exploits known good paths vs. explores new ones |
| Population-based | Naturally generates N candidate solutions per iteration for the Decision Engine |

### Weaknesses

| Weakness | Mitigation in This Implementation |
|----------|-----------------------------------|
| Slow convergence | ACS pseudorandom proportional rule accelerates convergence vs. AS |
| Parameter sensitivity | Systematic parameter sweep during benchmark phase; documented default ranges |
| Stagnation in local optima | Pheromone limits (τ_min, τ_max), local pheromone decay, and diversity-aware restart |
| Computational cost | O(k × n × m) per iteration where k = ants, n = nodes, m = edges. Linear scaling. |

### Computational Complexity

- **Time per iteration:** `O(k × (E + V log V))` where k = number of ants, E = edges searched per ant, V = nodes visited per ant. Each ant performs a graph traversal proportional to path length.
- **Memory:** `O(V²)` for pheromone matrix in dense representation. Optimized to `O(E)` by storing pheromones only on edges that exist in the graph.
- **Scaling:** Linear in ants and iterations. For a city graph of 10,000 nodes and 200,000 edges, the pheromone matrix is `O(E)` ≈ 200,000 entries.

### Relationship to EV Routing Literature

ACO has been applied to EV routing problems including:
- Charge-aware routing with range constraints
- Time-dependent energy consumption minimization
- Routing under uncertain traffic conditions

This implementation adapts these approaches by integrating with the existing `CostProvider` interface, which already incorporates distance, time, energy, congestion, hazard, emergency, and communication penalties. The pheromone model operates on the composite cost returned by `CostProvider`, not on individual cost components.

---

## 2. Literature Review

### 2.1 Variant Survey

| Variant | Authors | Year | Key Feature | Suitability for Dynamic Routing |
|---------|---------|------|-------------|----------------------------------|
| **Ant System (AS)** | Dorigo, Maniezzo, Colorni | 1991/1996 | Original formulation. All ants deposit pheromones. Global update only. | Weak — slow convergence, no exploration control |
| **Ant Colony System (ACS)** | Dorigo & Gambardella | 1997 | Pseudorandom proportional rule. Local + global pheromone updates. | **Selected** — best balance of exploration/exploitation |
| **Max-Min Ant System (MMAS)** | Stützle & Hoos | 2000 | Pheromone bounds [τ_min, τ_max]. Only best ant deposits. | Good — prevents stagnation. Compatible with ACS extensions. |
| **Rank-Based ACO** | Bullnheimer, Hartl, Strauss | 1999 | Weighted pheromone deposit by rank. | Moderate — adds complexity without proportional benefit for routing |

### 2.2 Selected Variant: Ant Colony System (ACS)

**Justification:**

1. **Pseudorandom proportional rule (q₀):** ACS introduces an explicit parameter q₀ that controls the balance between exploration (random proportional selection) and exploitation (deterministic selection of the best edge). This is critical for dynamic routing where the algorithm must both exploit known good corridors and explore alternatives when conditions change.

2. **Local + Global pheromone update:** The dual update mechanism provides finer control over pheromone dynamics:
   - **Local update:** Each ant reduces pheromone on traversed edges, encouraging subsequent ants to explore different paths. This naturally increases candidate diversity.
   - **Global update:** Only the best-so-far ant deposits pheromone, concentrating search around the best-known route.

3. **Proven routing performance:** ACS has been extensively benchmarked on TSP, VRP, and dynamic VRP. The parameter q₀ provides a tunable mechanism for adapting to dynamic environments (higher q₀ = more exploitation in stable conditions, lower q₀ = more exploration when the graph changes).

4. **Comparability:** ACS is the most widely cited ACO variant in routing literature. Choosing ACS ensures our results can be compared against published benchmarks.

### 2.3 Relation to Other Variants

- **Ant System (AS)** is the baseline but is too slow for meaningful comparison. It lacks local pheromone update and the pseudorandom proportional rule, making it explore excessively without converging.
- **Max-Min Ant System (MMAS)** provides useful extensions (pheromone bounds, best-only deposit) that are compatible with ACS. We incorporate [τ_min, τ_max] bounds to prevent numerical stagnation.
- **Rank-based ACO** adds complexity (sorting, weighted deposit) without clear benefit for routing. The ACS pseudorandom rule provides equivalent exploration control with fewer parameters.

### 2.4 Primary Literature Sources

- **ACS definition:** Dorigo, M., & Gambardella, L. M. (1997). "Ant Colony System: A cooperative learning approach to the traveling salesman problem". *IEEE Transactions on Evolutionary Computation*, 1(1), 53–66.
- **ACO survey:** Dorigo, M., Birattari, M., & Stützle, T. (2006). "Ant colony optimization". *IEEE Computational Intelligence Magazine*, 1(4), 28–39.
- **ACO textbook:** Dorigo, M., & Stützle, T. (2004). *Ant Colony Optimization*. MIT Press.
- **Pheromone limits:** Stützle, T., & Hoos, H. H. (2000). "MAX-MIN ant system". *Future Generation Computer Systems*, 16(8), 889–914.

---

## 3. Architecture

### 3.1 Integration with Existing Framework

```
RoutingAlgorithm Protocol       (src/e3hybrid/routing/protocol.py)
         ↑
SwarmToRoutingAdapter           (src/e3hybrid/swarm/adapter.py)
         ↓
SwarmAlgorithm Protocol         (src/e3hybrid/swarm/protocol.py)
         ↑
ACORouting                      (THIS MODULE — src/e3hybrid/swarm/aco.py)
    ├── uses SwarmContext        (read-only: graph, cost_provider, config, random_stream)
    ├── uses SwarmLifecycle      (common iteration loop)
    ├── uses SwarmRandom         (deterministic named sub-streams)
    ├── uses SwarmConfig         (population_size = ants, max_iterations, etc.)
    ├── produces SwarmResult     (best_solution as RouteCandidate)
    └── produces RouteCandidate  (via SwarmToRoutingAdapter → RoutingResult)
```

### 3.2 What ACO Receives (from SwarmContext)

- `cost_weights` — component weights for fitness evaluation (distance, time, energy, congestion, hazard, emergency, communication)
- `config` — SwarmConfig with ACO hyperparameters (alpha, beta, rho, q, q₀, etc.)
- `random_seed` — base seed for deterministic RNG
- `routing_request` — source, destination, request constraints
- `sim_time_s` — current simulation clock

### 3.3 What ACO Produces (via SwarmResult)

- `best_solution: RouteCandidate` — the best route found (node_sequence, edge_sequence, total_cost, cost_breakdown)
- `candidates: tuple[RouteCandidate, ...]` — all candidate routes from final iteration
- `statistics: SwarmStatistics` — iterations, runtime, convergence, score history, diversity history
- `iterations: tuple[IterationStatistics, ...]` — per-iteration metrics

### 3.4 Module Boundaries

| Module | Interaction with ACO |
|--------|---------------------|
| `RoutingAlgorithm` | ACO is NOT a routing algorithm. Accesses routing only through `SwarmToRoutingAdapter`. |
| `SwarmAlgorithm` | ACO implements this Protocol. Only `optimize(context)` method. |
| `BenchmarkRunner` | No modifications needed. ACO runs through `SwarmToRoutingAdapter`. |
| `Decision Engine` | Receives `RouteCandidate` objects from ACO. Evaluates on `total_cost` only. |
| `Emergency Framework` | ACO never imports emergency modules. Emergency effects are mediated through `CostProvider`. |
| `DirectedGraph` | ACO accesses graph through `GraphSnapshot` only (read-only). No direct graph access. |
| `CostProvider` | ACO queries edge costs through `CostProvider.cost(edge)`. Blocked edges return `inf`. |
| `Vehicle` | ACO never accesses vehicle modules. Vehicle constraints are in `RoutingRequest`. |
| `Communication` | ACO uses `SwarmRandom` for randomness. No direct communication module access. |

### 3.5 Architecture Rules (Enforced)

1. **No direct graph access:** ACO uses `GraphSnapshot` from `SwarmContext`. It never imports `DirectedGraph`.
2. **No direct emergency access:** Emergency effects (blocked roads, congestion, hazards, penalties) reach ACO through `CostProvider.cost(edge)`.
3. **No direct communication access:** ACO does not send messages. Pheromone information is local to the algorithm — not transmitted between vehicles.
4. **No vehicle modification:** ACO never creates, modifies, or accesses vehicle objects.
5. **No global state:** All ACO state is contained within the `optimize()` method or in `SwarmState.internal_state`.
6. **Deterministic:** All random decisions use `SwarmRandom` with named streams.

---

## 4. State Model

### 4.1 Pheromone Matrix

```
τ: dict[EdgeId, float]
```

A dictionary mapping each directed edge in the graph to its current pheromone level. Only edges that exist in the graph are stored (sparse representation).

- **Initialization:** All edges start at `τ₀ = 1 / (N × L_avg)` where N = number of nodes and L_avg = average edge cost (Dorigo & Stützle, 2004).
- **Bounds:** `τ_min ≤ τ_ij ≤ τ_max` for all edges. Prevents numerical stagnation.
- **Default values:** τ₀ = 1.0, τ_min = 0.01, τ_max = 10.0 (configurable via `SwarmConfig.hyperparameters`).

### 4.2 Visibility Matrix

```
η: dict[EdgeId, float]
```

Heuristic desirability of each edge. Computed once at construction time from `CostProvider`.

```
η_ij = 1.0 / (cost(edge_ij) + ε)
```

where:
- `cost(edge_ij)` = composite cost from `CostProvider.cost(edge).value`
- `ε` = small constant (1e-10) to prevent division by zero
- Blocked edges (`cost = inf`) have `η_ij = 0`

Visibility is **static** (computed once) for efficiency. Dynamic re-computation can be enabled for highly dynamic scenarios where edge costs change frequently.

### 4.3 Ant State

Each ant maintains:

```
AntState:
    current_node: NodeId
    visited_nodes: set[NodeId]
    node_sequence: list[NodeId]
    edge_sequence: list[EdgeId]
    total_cost: float
    cost_breakdown: RouteCost
    is_complete: bool       # Reached destination?
    is_feasible: bool       # No blocked edges traversed?
```

Ant state is encapsulated per ant and discarded after each iteration.

### 4.4 Route Memory

```
RouteMemory:
    iteration_best: CandidateSolution    # Best route in current iteration
    global_best: CandidateSolution       # Best route across all iterations
    convergence_history: list[float]     # Best score per iteration
    diversity_history: list[float]       # Population diversity per iteration
```

### 4.5 Iteration State

```
ACOIterationState:
    ant_population: list[AntState]
    iteration_best: CandidateSolution
    iteration_worst: CandidateSolution
    average_cost: float
    diversity: float          # Normalized [0, 1]: 1 = fully diverse
```

### 4.6 Global Colony State

Stored in `SwarmState.internal_state`:

```python
{
    "pheromone_matrix": dict[EdgeId, float],
    "visibility_matrix": dict[EdgeId, float],
    "global_best": CandidateSolution,
    "iteration": int,
    "convergence_counter": int,
}
```

This state persists across iterations and is updated each iteration.

---

## 5. Transition Rule

### 5.1 Pseudorandom Proportional Rule (ACS)

Ant k at node i selects the next node j according to:

```
    ┌ argmax_{u ∈ N(i)} { τ_iu^α × η_iu^β }    if q ≤ q₀
j = ┤
    └ J                                          otherwise
```

where:
- `N(i)` = set of unvisited neighbours of node i (not in ant's tabu list)
- `τ_iu` = pheromone level on edge (i, u)
- `η_iu` = visibility (heuristic desirability) of edge (i, u)
- `α` = pheromone importance weight (α ≥ 0)
- `β` = visibility importance weight (β ≥ 0)
- `q` = uniform random number in [0, 1] from `SwarmRandom.get_stream("aco.selection")`
- `q₀` = exploitation-exploration parameter (0 ≤ q₀ ≤ 1)

### 5.2 Random Proportional Selection

When `q > q₀`, the next node J is selected with probability:

```
    τ_iJ^α × η_iJ^β
p_J = ──────────────────
      Σ_{u ∈ N(i)} τ_iu^α × η_iu^β
```

This is the standard AS transition probability, used by ACS as the exploration fallback.

### 5.3 Candidate Filtering

Before selection, candidate edges are filtered:

1. Exclude visited nodes (prevent cycles — tabu list)
2. Exclude blocked edges (cost = inf → η = 0 → zero probability)
3. Exclude edges with τ < τ_min threshold (numerical stability)

If the filtered candidate set is empty, the ant's route terminates at node i (partial path). The ant is marked as `is_complete = False` and its path is assigned a penalty cost.

### 5.4 Parameter Domains

| Parameter | Symbol | Domain | Typical Value | Effect |
|-----------|--------|--------|---------------|--------|
| Pheromone weight | α | [0, 5] | 1.0 | Higher → ants follow pheromone trails more strongly |
| Visibility weight | β | [0, 10] | 2.0 | Higher → ants prefer short/cheap edges more |
| Exploration rate | q₀ | [0, 1] | 0.9 | Higher → more exploitation, less exploration |
| Random threshold | q | [0, 1] | — | Sampled uniformly each decision |

### 5.5 Constraint: α + β > 0

If both α = 0 and β = 0, all candidate edges have equal probability. This degenerate case is detected and raises a configuration error.

---

## 6. Pheromone Update

### 6.1 Initialization

```
τ_ij(0) = τ₀
```

where:
- `τ₀` = initial pheromone level (configurable, default 1.0)
- The initial level should be high enough to encourage exploration in early iterations
- A common heuristic: `τ₀ = 1 / (N × L_avg)` where L_avg is the average cost of edges

### 6.2 Local Pheromone Update (ACS-specific)

After traversing edge (i, j), ant k immediately applies the local update:

```
τ_ij ← (1 − ρ) × τ_ij + ρ × τ₀
```

where:
- `ρ` = local pheromone decay rate (0 < ρ < 1)
- `τ₀` = initial pheromone level

**Purpose:** Reduces pheromone on traversed edges, making them less attractive to subsequent ants. This increases exploration and prevents all ants from following the same path.

**Effect:** The local update makes traversed edges slightly less desirable, encouraging the colony to explore diverse routes.

### 6.3 Global Pheromone Update (ACS-specific)

After all ants finish, the global update is applied using only the best-so-far ant:

```
τ_ij ← (1 − ρ) × τ_ij + ρ × Δτ_ij^best
```

where:
```
Δτ_ij^best = 1 / L_best   if edge (i, j) is in the best-so-far route
             0             otherwise
```

and:
- `ρ` = global pheromone decay rate (same as local ρ, 0 < ρ < 1)
- `L_best` = total cost of the best-so-far route (from `RouteCandidate.total_cost`)

**Purpose:** Reinforces pheromones on the best-known route, concentrating search around it.

### 6.4 Pheromone Bounds

To prevent stagnation (all pheromones converging to 0 or ∞):

```
τ_min ≤ τ_ij ≤ τ_max
```

After every update (local and global), pheromones are clamped:

```
τ_ij ← min(max(τ_ij, τ_min), τ_max)
```

Default bounds:
- `τ_min` = 0.01 (configurable)
- `τ_max` = 10.0 (configurable)

These bounds follow the MMAS principle (Stützle & Hoos, 2000).

### 6.5 Numerical Stability

- Pheromone values use Python `float` (IEEE 754 double precision)
- Minimum pheromone (`τ_min`) prevents underflow to zero
- Maximum pheromone (`τ_max`) prevents overflow
- Visibility uses `1 / (cost + ε)` where `ε = 1e-10`
- Pheromone updates use `ρ` decay rate, not additive decrements
- All pheromone operations are O(1) per edge

---

## 7. Termination

### 7.1 Iteration Limit

```
max_iterations: int
```

Default: 100. Stop after N iterations. Always applied as the upper bound.

### 7.2 Convergence

```
convergence_threshold: float
```

Stop when `|best_score(i) - best_score(i-1)| < threshold` for `stall_limit` consecutive iterations.

### 7.3 No Improvement

```
stall_limit: int
```

Stop when no improvement in best-so-far solution for N consecutive iterations.

### 7.4 Runtime Limit

```
time_limit_s: float
```

Stop after T seconds of wall-clock time.

### 7.5 Target Score

```
target_score: float
```

Stop when `best_score ≤ target_score`.

### 7.6 Interaction with SwarmLifecycle

All termination conditions are evaluated by `TerminationChecker` (from the swarm infrastructure), not by ACO itself. The ACO `optimize()` method uses `SwarmLifecycle.run()` which handles termination automatically.

---

## 8. Configuration

### 8.1 YAML Configuration Schema

```yaml
algorithm: "aco"
population_size: 20             # Number of ants per iteration
max_iterations: 100             # Maximum iterations
time_limit_s: 60.0              # Maximum runtime (0 = no limit)
convergence_threshold: 0.001    # Min improvement for convergence
stall_limit: 20                 # Stall iterations before convergence
target_score: 0.0               # Early stop target (0 = disabled)
seed: 42                        # Random seed
hyperparameters:
  alpha: 1.0                    # Pheromone importance weight
  beta: 2.0                     # Visibility importance weight
  rho: 0.1                      # Pheromone decay rate (local + global)
  q0: 0.9                       # Exploitation/exploration balance
  tau0: 1.0                     # Initial pheromone level
  tau_min: 0.01                 # Minimum pheromone bound
  tau_max: 10.0                 # Maximum pheromone bound
  elitism: 1                    # Number of elite ants (0 = disabled)
  candidate_list_size: 20       # Candidate list size (0 = all neighbours)
cost_weights:
  distance: 1.0
  time: 0.0
  energy: 0.0
  congestion: 0.0
  hazard: 0.0
  emergency: 0.0
  communication: 0.0
```

### 8.2 Parameter Descriptions

| Parameter | YAML Key | Required | Default | Description |
|-----------|----------|----------|---------|-------------|
| Ants per iteration | `population_size` | Yes | 20 | Number of ants that construct routes each iteration |
| Max iterations | `max_iterations` | Yes | 100 | Upper bound on total iterations |
| Time limit (s) | `time_limit_s` | No | 0.0 | Wall-clock limit (0 = no limit) |
| Convergence threshold | `convergence_threshold` | No | 0.001 | Min improvement to avoid convergence trigger |
| Stall limit | `stall_limit` | No | 20 | Iterations without improvement before converging |
| Target score | `target_score` | No | 0.0 | Score target for early stop (0 = disabled) |
| Alpha | `hyperparameters.alpha` | Yes | 1.0 | Pheromone importance [0, 5] |
| Beta | `hyperparameters.beta` | Yes | 2.0 | Visibility importance [0, 10] |
| Rho | `hyperparameters.rho` | Yes | 0.1 | Pheromone decay rate (0, 1) |
| Q0 | `hyperparameters.q0` | Yes | 0.9 | Exploration/exploitation balance [0, 1] |
| Tau0 | `hyperparameters.tau0` | Yes | 1.0 | Initial pheromone level |
| Tau min | `hyperparameters.tau_min` | No | 0.01 | Minimum pheromone bound |
| Tau max | `hyperparameters.tau_max` | No | 10.0 | Maximum pheromone bound |
| Elitism | `hyperparameters.elitism` | No | 1 | Elite ant count for additional deposit |
| Candidate list | `hyperparameters.candidate_list_size` | No | 20 | Max candidates per node (0 = all) |

### 8.3 Validation Rules

- `alpha ≥ 0` and `beta ≥ 0` and `alpha + beta > 0`
- `0 < rho < 1`
- `0 ≤ q₀ ≤ 1`
- `τ₀ > 0`
- `0 < τ_min < τ_max`
- `elitism ≥ 0` (0 = disabled)
- `candidate_list_size ≥ 0` (0 = unlimited)

---

## 9. Determinism

### 9.1 Seeded Randomness

All stochastic decisions in ACO use `SwarmRandom` with named sub-streams:

| Decision | Stream Name | Source |
|----------|-------------|--------|
| Ant route construction (q vs q₀) | `aco.selection` | `SwarmRandom.get_stream("aco.selection")` |
| Candidate selection (roulette wheel) | `aco.roulette` | `SwarmRandom.get_stream("aco.roulette")` |
| Pheromone deposit perturbation | `aco.deposit` | `SwarmRandom.get_stream("aco.deposit")` |

### 9.2 No Uncontrolled Randomness

- No direct calls to `random.random()`, `random.choice()`, or `random.randint()`
- No `numpy.random` or `secrets` module usage
- No `time.time()` for seeding
- No `os.urandom()` or `/dev/urandom`
- `SwarmRandom` is initialized from `SwarmContext.random_seed`

### 9.3 Determinism Guarantee

Given the same:
- Graph (same topology, same edge states)
- RoutingRequest (same source, destination, constraints)
- SwarmConfig (same hyperparameters, same seed)
- CostProvider (same weights, same penalties)

ACO produces identical results across multiple runs.

---

## 10. Emergency Behaviour

### 10.1 How Emergency Effects Reach ACO

```
Emergency Event
    ↓
NetworkEffectSubscriber
    ↓
DirectedGraph.update_edge_state()
    ↓
Edge (updated MutableEdgeState: is_blocked, congestion_factor, hazard_penalty_s, etc.)
    ↓
CostProvider.cost(edge)
    ↓
ACO.optimize() ← reads cost through CostProvider only
```

ACO never:
- Imports `e3hybrid.emergency` modules
- Accesses `MutableEdgeState` directly
- Subscribes to emergency events
- Inspects hazard, congestion, or penalty fields directly

### 10.2 Blocked Roads

When an edge is blocked (`is_blocked = True`), `CostProvider.cost(edge)` returns `EdgeCost(value=inf, is_blocked=True)`. ACO processes this as:

- `η_ij = 1 / inf = 0` → visibility is zero → zero transition probability
- Ants never select blocked edges during route construction
- If all outgoing edges from a node are blocked, the ant's route terminates at that node

### 10.3 Congestion, Hazards, and Penalties

These increase the composite cost returned by `CostProvider`. Higher cost → lower visibility → lower probability of selection. Ants naturally prefer cheaper (less congested, less hazardous) routes.

### 10.4 Emergency Corridors

Emergency vehicle corridors increase `emergency_penalty_s` on affected edges. This increases the effective cost, making these edges less attractive to ants. No special handling needed — the penalty flows through the standard `CostProvider` interface.

### 10.5 Dynamic Re-Optimization

When the simulation triggers a reroute request (due to emergency event or significant cost change):

1. The Decision Engine calls `SwarmToRoutingAdapter.compute_route()`
2. The adapter creates a new `SwarmContext` with the current graph state
3. ACO runs full optimization on the updated graph
4. Previous pheromone state is discarded (fresh start for each reroute request)

This is a deliberate simplification: each ACO run is independent. Inter-run pheromone persistence is a future enhancement.

---

## 11. Computational Complexity

### 11.1 Time Complexity

| Operation | Complexity | Notes |
|-----------|------------|-------|
| **Initialization** | `O(E)` | Compute visibility, initialize pheromones |
| **Per iteration** | `O(k × (P_avg))` | k = ants, P_avg = average path length in edges |
| **Per ant** | `O(P_avg × CL)` | P_avg edges selected, CL = candidate list size |
| **Pheromone local update** | `O(P_avg)` per ant | One update per traversed edge |
| **Pheromone global update** | `O(P_best)` | One update per edge in best route |
| **Total** | `O(I × k × P_avg)` | I = iterations, k = ants, P_avg = path length |

where:
- I = max_iterations (typical: 50–200)
- k = ants per iteration (typical: 10–50)
- P_avg = average path length in edges (graph-dependent)
- CL = candidate list size (typical: 10–50)
- E = edges in graph (typical: 10,000–200,000)

### 11.2 Memory Complexity

| Data Structure | Complexity | Notes |
|----------------|------------|-------|
| Pheromone matrix | `O(E)` | Sparse: one float per edge |
| Visibility matrix | `O(E)` | Static: one float per edge |
| Ant states | `O(k × P_max)` | k ants × max path length |
| Best routes | `O(P_max)` | Constant: global + iteration best |
| **Total** | `O(E + k × P_max)` | Dominated by pheromone matrix |

### 11.3 Scaling Characteristics

- **Nodes (V):** Pheromone matrix scales with E, not V. For sparse graphs (typical road networks), E ∝ V. Memory is O(V).
- **Edges (E):** Linear scaling. Each edge needs one pheromone value and one visibility value.
- **Ants (k):** Linear in compute. Ants are independent and trivially parallelizable.
- **Iterations (I):** Linear in runtime. Each iteration does the same amount of work.

### 11.4 Comparison with Dijkstra and A*

| Algorithm | Time (single query) | Memory |
|-----------|---------------------|--------|
| Dijkstra | `O(E + V log V)` | `O(V)` |
| A* | `O(E)` best, `O(E + V log V)` worst | `O(V)` |
| ACO (ACS) | `O(I × k × P_avg)` | `O(E)` |

ACO is more expensive than Dijkstra/A* per query because it runs multiple iterations with multiple ants. However:
- ACO generates multiple candidates per run (one per ant per iteration)
- ACO continues to improve solutions over time (anytime algorithm)
- For dynamic environments, ACO's adaptation may reduce total queries vs. repeated Dijkstra/A* reruns

---

## 12. Testing Strategy

### 12.1 Unit Tests

| Test | Description |
|------|-------------|
| Pheromone initialization | τ_ij = τ₀ for all edges after init |
| Pheromone local update | τ_ij decreases after ant traversal |
| Pheromone global update | τ_ij increases on best route edges |
| Pheromone bounds | τ_ij clamped to [τ_min, τ_max] |
| Visibility computation | η_ij = 1/cost, η = 0 for blocked edges |
| Transition rule | q ≤ q₀ → deterministic; q > q₀ → probabilistic |
| Tabu list | Ant cannot revisit a node in current path |
| Candidate filtering | Blocked edges excluded; visited nodes excluded |
| Route construction | Ant builds valid path from source to destination |
| Route failure | Ant returns partial path when destination unreachable |
| Deterministic replay | Same seed → same results |
| Parameter validation | Invalid parameters raise configuration errors |

### 12.2 Property Tests

| Property | Description |
|----------|-------------|
| Convergence | Best score monotonically non-increasing (or non-decreasing for cost minimization) |
| Pheromone bounds | All pheromone values within [τ_min, τ_max] after every update |
| Solution validity | All candidate routes pass `RouteValidator` checks |
| Determinism | Identical inputs → identical outputs (tested over 5 runs) |
| Cost monotonicity | Adding penalty to any edge never decreases route cost |

### 12.3 Integration Tests

| Test | Description |
|------|-------------|
| SwarmInfrastructure | ACO works with `SwarmLifecycle`, `TerminationChecker`, `SwarmRandom` |
| SwarmToRoutingAdapter | ACO produces `RouteCandidate` → `RoutingResult` conversion |
| BenchmarkRunner | ACO runs through `BenchmarkRunner` without modification |
| Reroute on blocked edge | After adding blockage, ACO finds alternative route |

### 12.4 Benchmark Tests

| Benchmark | Against | Metric |
|-----------|---------|--------|
| Small graph optimality | Dijkstra | Cost ratio (ACO_best / Dijkstra_optimal) |
| Grid graph efficiency | A* | Runtime, nodes explored |
| Blocked edge reroute | Dijkstra (re-run) | New route cost after blockage |
| Deterministic replay | — | Route cost variance across 5 runs |

### 12.5 Deterministic Replay

```python
# Given the same inputs, ACO must produce the same output
config = SwarmConfig(algorithm_name="aco", seed=42, ...)
result1 = aco.optimize(context)
result2 = aco.optimize(context)

assert result1.statistics.best_score == result2.statistics.best_score
assert result1.best_solution.node_sequence == result2.best_solution.node_sequence
```

Tested with the existing `RoutingVerifier.verify_deterministic_replay()` method.

---

## 13. Benchmark Plan

### 13.1 Comparison Against Dijkstra and A*

| Metric | Comparison | Expected Outcome |
|--------|------------|------------------|
| **Route cost** | ACO best vs. Dijkstra optimal | ACO cost ≥ Dijkstra cost. ACO should approach optimal within 1–5% on static graphs. |
| **Runtime** | ACO vs. Dijkstra vs. A* | Dijkstra < A* < ACO (ACO is population-based, more expensive) |
| **Candidate count** | ACO candidates vs. Dijkstra alternatives | ACO produces k candidates per iteration (k × I total). Dijkstra generates 1 + blocked-edge alternatives. |
| **Convergence** | ACO score over iterations | Monotonically decreasing cost. Convergence within 50–100 iterations for typical graphs. |

### 13.2 Benchmark Configuration

```yaml
# For fair comparison, all algorithms use the same:
graph: "synthetic_100_nodes"     # Same graph
requests: 50                     # Same 50 OD pairs
seed: 42                         # Same random seed
cost_weights:
  distance: 1.0                  # Same cost function
  time: 0.0

# Algorithm-specific configs:
algorithms:
  - "dijkstra"
  - "astar"
  - "aco"
```

### 13.3 Expected Results

For a static graph of 100 nodes and ~500 edges:

| Metric | Dijkstra | A* | ACO (100 iters × 20 ants) |
|--------|----------|-----|---------------------------|
| Route cost | Optimal | Optimal | ≥ Optimal (typically 1–5% above) |
| Runtime per query | ~1 ms | ~0.5 ms | ~100–500 ms |
| Candidates generated | 2–4 | 2–4 | 20 per iteration (2000 total) |
| Memory | O(V) | O(V) | O(E) |

### 13.4 Existing Framework Integration

ACO benchmarks run through the existing `BenchmarkRunner`:

```python
from e3hybrid.swarm.factory import SwarmFactory
from e3hybrid.swarm.adapter import SwarmToRoutingAdapter
from e3hybrid.routing.benchmark_runner import BenchmarkRunner

# Register ACO
SwarmFactory.register("aco", ACORouting)

# Run benchmark
config = BenchmarkConfig(algorithm_names=["dijkstra", "astar", "aco"])
runner = BenchmarkRunner(config)
results = runner.run_scenario(scenario)
```

No modifications to `BenchmarkRunner` are needed.

---

## 14. Limitations

### 14.1 Intentionally Excluded Features

| Feature | Reason for Exclusion |
|---------|----------------------|
| **Inter-vehicle pheromone sharing** | Pheromones are local to the algorithm instance. Real-time vehicle-to-vehicle pheromone exchange via `MessageBus` is a future enhancement beyond undergraduate scope. |
| **Continuous re-optimization** | Each routing request starts fresh. Pheromone persistence across requests (warm-starting) is deferred to Phase 12 (E³-Hybrid). |
| **Dynamic graph adaptation** | ACO does not detect graph changes mid-optimization. Graph changes trigger a new routing request from the Decision Engine. |
| **Parallel ant evaluation** | Ants are evaluated sequentially. Parallel evaluation is possible but deferred as an optimization. |
| **Adaptive parameter control** | Alpha, beta, rho, and q₀ are static. Adaptive tuning during optimization is a research extension. |
| **Hybrid local search** | No 2-opt, 3-opt, or other local search refinement after ant route construction. |
| **Multiple colonies** | Single colony only. Multi-colony ACO with independent pheromone matrices is deferred. |
| **Time windows** | No support for time-windowed routing constraints. |

### 14.2 Scope Boundaries

This ACO implementation is designed for an **undergraduate thesis** comparing swarm routing algorithms for EVs under dynamic emergency scenarios. The following are explicitly out of scope:

- Production-grade optimization (acceptable convergence within 1–5% of optimal)
- Real-time performance (routing latency measured in milliseconds acceptable)
- Large-scale deployment (city graphs up to 10,000 nodes)
- Distributed computation (single-process, single-thread)
- Integration with SUMO TraCI (Phase 13)

### 14.3 Known Trade-offs

| Trade-off | Choice | Rationale |
|-----------|--------|-----------|
| ACS vs. simpler ACO variants | ACS | Better exploration/exploitation balance for dynamic routing |
| Static vs. dynamic visibility | Static | Sufficient for thesis scope; dynamic re-computation adds complexity |
| Full vs. candidate list | Candidate list | Reduces per-ant computation by limiting candidate edges evaluated |
| Sequential vs. parallel ants | Sequential | Simpler implementation; parallelization is additive |

---

## 15. Open Questions

### Resolved in This Design

- **Variant selection:** ACS (Dorigo & Gambardella, 1997) with [τ_min, τ_max] bounds from MMAS (Stützle & Hoos, 2000)
- **Transition rule:** Pseudorandom proportional rule with q₀ parameter (standard ACS)
- **Pheromone update:** Local update (all ants) + global update (best-so-far only)
- **Pheromone bounds:** τ_min and τ_max clamp all pheromone values
- **Visibility:** Static, computed once from CostProvider
- **Candidate filtering:** Exclude visited nodes, blocked edges, and sub-threshold pheromone edges
- **Termination:** Handled by SwarmLifecycle (max iterations, timeout, convergence, no improvement, target score)
- **Emergency integration:** Through CostProvider only (no direct emergency module access)
- **Benchmark integration:** Through SwarmToRoutingAdapter (no BenchmarkRunner modifications)
- **Determinism:** SwarmRandom with named sub-streams (aco.selection, aco.roulette, aco.deposit)
- **Configuration:** All parameters YAML-configurable via SwarmConfig.hyperparameters

### Deferred to Implementation Phase

- **Exact candidate list size:** Will tune based on graph density during implementation
- **Candidate list sorting strategy:** By visibility, by pheromone, or by composite score
- **Elitism deposit weight:** How much additional pheromone elite ants deposit
- **Convergence detection sensitivity:** Threshold for diversity-based early stopping
- **Penalty cost for incomplete routes:** What cost to assign when an ant cannot reach the destination

### Deferred to Future Phases

- **Inter-vehicle pheromone communication:** Phase 12 (E³-Hybrid) may share pheromone information via MessageBus
- **Warm-starting with previous pheromones:** Phase 12 may persist pheromones across routing requests
- **Dynamic visibility recomputation:** Phase 13 (SUMO integration) may recompute visibility when traffic conditions change rapidly
- **Parallel ant evaluation:** Performance optimization, not required for thesis correctness

### No Unresolved Architectural Questions

All major architectural decisions for the ACO implementation are resolved in this document. The design is ready for implementation approval.
