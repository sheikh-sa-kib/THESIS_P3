# Bee Colony Optimization (BCO) — Algorithm Documentation

## 1. Purpose in this Thesis

BCO solves the **dynamic EV routing problem**: given a source node, a destination node, and a real-time road network (with congestion, road closures, hazards, and emergency events), BCO finds a near-optimal route through the graph using constructive swarm intelligence. The result feeds into the decision engine, which dispatches the route to the SUMO-simulated EV.

## 2. Theory Actually Implemented

The implementation follows **constructive BCO** (Teodorovic, 2009) with the forward pass / backward pass structure. No pheromone matrix is used.

**Key theoretical elements mapped to code:**

| Theory (Teodorovic 2009) | Code |
|---|---|
| Forward pass: each bee constructs a solution step by step | `_forward_pass()` — bees walk from source to destination selecting edges from outgoing adjacency |
| Backward pass: evaluation + loyalty decision + recruitment | `_backward_pass()` — phases 1–3 |
| Loyalty decision: bee stays with its own solution with probability proportional to its normalized quality | `_loyalty_decision()`: `p_loyal = bee.norm_quality` |
| Recruitment: uncommitted bees adopt a template from a loyal bee via roulette-wheel selection | `_recruitment()` — roulette on loyal-bee qualities |
| Template: a bee's solution that guides future construction (equivalent to a "dance" in the hive) | `BeeState.template` — updated in `_update_templates()` |

The implementation is a **constructive** BCO variant: bees build routes incrementally rather than improving existing solutions. There is no improvement pass (no local search). All randomness is controlled through `SwarmRandom` named streams.

## 3. Inputs

The `optimize()` method receives a single `SwarmContext` (`context.py:15`) containing:

| Field | Type | Purpose |
|---|---|---|
| `routing_request` | `RoutingRequest` | Source node, destination node, vehicle constraints, timeout |
| `graph` | `DirectedGraph` | Full road network: nodes, edges with mutable state |
| `cost_calculator` | `CompositeCostCalculator` | Computes weighted edge cost from state (distance, time, congestion, hazard, emergency, communication) |
| `config` | `SwarmConfig` | Population size, max iterations, hyperparameters dict, cost weights, termination settings |
| `random_seed` | `int` | Base seed for deterministic random number generation |
| `sim_time_s` | `float` | Current simulation time (for logging / cache keys) |
| `cost_weights` | `CostWeights` | 7-component weight vector applied to edge costs |

## 4. Outputs

`optimize()` returns a `SwarmResult` (`result.py:14`) which is adapted to `RoutingResult` via `SwarmToRoutingAdapter` (`adapter.py:24`):

```
BCORouting.optimize(context) → SwarmResult
        ↓
SwarmToRoutingAdapter.compute_route(request, graph) → RoutingResult
```

The `RoutingResult` contains:
- `primary_route: Route` — best route as node sequence + edge sequence + distance/time/energy estimates
- `candidates: tuple[RouteCandidate, ...]` — all unique complete routes found (deduplicated by edge tuple)
- `success: bool`
- `failure_reason: str | None`
- `statistics: RoutingStatistics`

## 5. Configuration Parameters

All BCO hyperparameters are extracted from `SwarmConfig.hyperparameters` by `BCOConfiguration.from_config()` (`bco.py:166`):

| Parameter | Code key | Default | Type | Description |
|---|---|---|---|---|
| `forward_steps` | `"forward_steps"` | `500` | `int` | Max construction steps per bee per iteration (acts as an edge-count cap) |
| `beta` | `"visibility_weight"` | `2.0` | `float` | Exponent on heuristic visibility in selection; higher = more greedy |
| `delta` | `"template_strength"` | `3.0` | `float` | Multiplicative bonus for template edges: `w *= 1.0 + delta` |
| `elite_count` | `"elite_count"` | `3` | `int` | Top-K bees by quality that are automatically loyal (bypasses `_loyalty_decision`) |

Validation (`bco.py:201`):
- `forward_steps >= 1`
- `beta >= 0`
- `delta >= 0`
- `population_size >= 2`
- `0 <= elite_count <= population_size`

## 6. Internal Data Structures

### BeeState (`bco.py:76`)
```python
@dataclass
class BeeState:
    k: int                          # Bee index (0..B-1)
    route: list[EdgeId]            # Edge sequence constructed in current iteration
    cost: float                    # Total cost of route
    quality: float                  # 1 / (cost + _EPS) if COMPLETE, else 0
    norm_quality: float             # quality / max(qualities) — used for loyalty
    template: list[EdgeId] | None   # Edges from a previous good route (recruitment target)
    state: BeeStatus                # CONSTRUCTING | COMPLETE | FAILED
    is_loyal: bool                  # True if bee keeps its own solution this iteration
    visited: set[NodeId]            # Nodes visited (constructed but not used in routing)
    iteration_created: int          # Iteration when the current route was constructed
```

### VisibilityCache (`bco.py:144`)
```python
@dataclass class VisibilityCache:
    values: dict[EdgeId, float]  # Precomputed eta = 1.0 / (edge_cost + _EPS)
    beta: float                   # Visibility exponent (cached copy of config beta)
    delta: float                  # Template bonus factor (cached copy of config delta)
```

Precomputed once in `_build_visibility()` (`bco.py:398`):
- Blocked edges → 0.0 visibility
- Non-finite or negative cost → 0.0
- Zero-cost edge → `1.0 / _EPS` (very large)
- Otherwise → `1.0 / (edge_cost + _EPS)`

### ForwardPassResult (`bco.py:96`)
```python
@dataclass class ForwardPassResult:
    routes: list[list[EdgeId]]    # Per-bee edge sequences
    costs: list[float]            # Per-bee total cost
    states: list[BeeStatus]       # Per-bee final status
    iteration: int                # Iteration number
    runtime_s: float              # Wall-clock time
```

### BackwardPassResult (`bco.py:110`)
```python
@dataclass class BackwardPassResult:
    loyal_indices: list[int]       # Indices of loyal bees
    uncommitted_indices: list[int] # Indices of uncommitted bees
    best_cost: float               # Best cost in this iteration
    best_route: list[EdgeId]       # Best route in this iteration
    global_best_cost: float        # Best cost across all iterations
    global_best_route: list[EdgeId]# Best route across all iterations
    diversity: float               # 1 - avg_jaccard_similarity of templates
    runtime_s: float
```

### BCOStatistics (`bco.py:128`)
```python
@dataclass(frozen=True, slots=True) class BCOStatistics:
    iteration: int
    best_cost: float
    avg_cost: float
    worst_cost: float
    loyal_count: int
    uncommitted_count: int
    diversity: float
    runtime_s: float
```

## 7. Step-by-Step Written Algorithm

```
Algorithm BCORouting.optimize(context):
  Input:  SwarmContext (graph G, request R, config C, seed S)
  Output: SwarmResult

  1. Validate context (graph exists, source != destination, both in graph)
  2. Build BCOConfiguration from C.hyperparameters
  3. Build VisibilityCache: for each edge e in G:
       if e.is_blocked → 0.0
       elif non-finite/negative cost → 0.0
       elif edge_cost == 0 → 1.0/_EPS
       else → 1.0 / (edge_cost + _EPS)
  4. Create SwarmRandom(base_seed=S) for 3 named streams
  5. Initialize B bees with empty route, zero cost, no template, CONSTRUCTING
  6. Create TerminationChecker(C), call start()

  7. For iteration = 0 .. C.max_iterations - 1:
       a. FORWARD PASS (see step 7a below)
           → return routes, costs, states
       b. BACKWARD PASS (see step 7b below):
           i. EVALUATION: quality = 1/(cost+_EPS), sort by quality descending
          ii. LOYALTY DECISION:
               - Top K (elite_count) bees are auto-loyal
               - Remaining COMPLETE bees: p_loyal = norm_quality
               - FAILED bees → uncommitted
         iii. RECRUITMENT:
               - If uncommitted and loyal exist:
                 Roulette-wheel on loyal bees' quality values;
                 each uncommitted bee copies the recruiter's route as template
          iv. TEMPLATE UPDATE:
               - For each COMPLETE loyal bee: template = its route
          v. DIVERSITY: 1.0 - avg_jaccard_similarity of non-None templates
       c. Update global best (if best_cost < global_best_cost)
       d. Compute iteration stats (best, avg, worst cost; loyal/uncommitted counts)
       e. Update no_improvement_count for termination
       f. Build SearchState, call TerminationChecker.check()
       g. If should_stop: build and return SwarmResult

  8. Return SwarmResult (max iterations reached)
```

### 7a. Forward Pass (one bee)

```
FORWARD PASS for bee k:
  1. Reset bee.route = [], bee.visited = ∅, bee.state = CONSTRUCTING
  2. current = source, prev_node = None, route_edges = [], total_cost = 0

  3. For step in range(forward_steps):
       a. Get outgoing_edges(current)
       b. Filter to feasible edges (edge_total_cost < ∞)
       c. If feasible > 1 AND prev_node not None:
            Remove edges that go back to prev_node (backtrack prevention)
       d. If feasible is empty: break (dead end)
       e. If feasible > 1:
            Prefer edges that lead to non-dead-end nodes
            (target == destination OR outgoing_edges(target) non-empty)
       f. Compute selection probabilities (see §7c)
       g. Roulette-wheel choose one edge via bco.selection stream
       h. Append chosen edge, compute edge_cost, add to total_cost
       i. prev_node = current, current = chosen.target
       j. If current == destination: break (reached destination)

  4. Set bee.route = route_edges, bee.cost = total_cost, bee.iteration_created = iteration
  5. If reached destination → bee.state = COMPLETE, else FAILED
```

### 7b. Selection Probability Computation

```
_compute_selection_probs(feasible, template):
  1. template_set = set(template) if template else ∅
  2. For each edge e in feasible:
       a. eta = visibility_cache.values[e.edge_id] (precomputed 1/(cost+_EPS), or 0)
       b. weight = eta ** beta
       c. If e.edge_id in template_set:
            weight *= 1.0 + delta   (template bonus)
       d. Append weight to probs list
  3. total = sum(probs)
  4. If total ≤ 0: return uniform 1/len(feasible) for each edge
  5. Return [p / total for p in probs]
```

### 7c. Recruitment Procedure

```
_recruitment(uncommitted, loyal, stream):
  1. total_o = sum of qualities of all loyal bees
  2. If total_o ≤ 0:
       For each uncommitted bee:
         recruiter = random.choice(loyal)
         template = copy of recruiter's route
       Return
  3. Build cumulative probability array from loyal bees' quality fractions
  4. For each uncommitted bee:
       a. r = stream.random()
       b. Binary search cumulative array to find recruiter index
       c. Copy recruiter's route as this bee's template
```

## 8. Implementation-Level Pseudocode

```python
# =====================================================================
# PSEUDOCODE: BCORouting.optimize(context)
# =====================================================================
def optimize(context):
    # ---- validate ----
    errors = validate_context(context)
    if errors: return failure(errors)

    G = context.graph
    cc = context.cost_calculator
    src = context.routing_request.source_node
    dst = context.routing_request.destination_node
    cfg = context.config
    bco_cfg = BCOConfiguration.from_config(cfg)

    assert G.has_node(src) and G.has_node(dst)

    # ---- build visibility ----
    self._visibility = build_visibility(G, cc, bco_cfg)
    self._swarm_rng = SwarmRandom(context.random_seed)

    # ---- initialize population ----
    B = cfg.population_size
    self._bees = [BeeState(k, [], 0, 0, 0, None, CONSTRUCTING, False, set(), -1)
                  for k in range(B)]
    self._global_best_cost = inf
    self._global_best_route = []

    # ---- iteration loop ----
    checker = TerminationChecker(cfg)
    checker.start()
    start_time = time.perf_counter()
    no_improvement_count = 0
    prev_best_score = inf

    for iteration in range(cfg.max_iterations):
        fwd = forward_pass(iteration)
        bwd = backward_pass(fwd, iteration)

        if bwd.best_cost < self._global_best_cost:
            self._global_best_cost = bwd.best_cost
            self._global_best_route = list(bwd.best_route)

        compute_BCOStatistics(iteration, bwd, self._iteration_stats)
        update_no_improvement_count(bwd.best_cost, prev_best_score)
        search_state = SearchState(...)

        term = checker.check(search_state)
        if term.should_stop:
            return build_swarm_result(term.reason, term.iteration)

    return build_swarm_result("max iterations reached", cfg.max_iterations)

# =====================================================================
# PSEUDOCODE: _build_visibility()
# =====================================================================
def _build_visibility():
    vis = {}
    for edge in self._graph.edges():
        eid = edge.edge_id
        if edge.state.is_blocked:
            vis[eid] = 0.0
        else:
            cost, _ = self._cost_calculator.compute_edge_cost(edge)
            if not finite(cost) or cost < 0:      vis[eid] = 0.0
            elif cost == 0:                        vis[eid] = 1.0 / _EPS
            else:                                   vis[eid] = 1.0 / (cost + _EPS)
    self._visibility = VisibilityCache(vis, self._config.beta, self._config.delta)

# =====================================================================
# PSEUDOCODE: _forward_pass(iteration)
# =====================================================================
def _forward_pass(iteration):
    B = len(self._bees)
    routes = [[]]*B
    costs = [0.0]*B
    states = [CONSTRUCTING]*B
    sel_stream = self._swarm_rng.get_stream("bco.selection")

    for k in range(B):
        bee = self._bees[k]
        bee.reset()  # route=[], visited=set(), state=CONSTRUCTING
        current = self._source
        prev_node = None
        route_edges = []
        total_cost = 0.0

        for _ in range(self._config.forward_steps):
            outgoing = self._graph.outgoing_edges(current)
            feasible = [e for e in outgoing if edge_total_cost(e) < inf]

            if len(feasible) > 1 and prev_node is not None:
                feasible = [e for e in feasible if e.target != prev_node]
            if not feasible:
                break
            if len(feasible) > 1:
                non_deadend = [e for e in feasible
                                if e.target == self._destination
                                or len(outgoing_edges(e.target)) > 0]
                if non_deadend:
                    feasible = non_deadend

            probs = compute_selection_probs(feasible, bee.template)
            chosen = roulette_wheel(feasible, probs, sel_stream)

            route_edges.append(chosen.edge_id)
            edge_cost, _ = self._cost_calculator.compute_edge_cost(chosen)
            total_cost += edge_cost
            prev_node = current
            current = chosen.target
            if current == self._destination:
                break

        routes[k] = route_edges
        costs[k] = total_cost
        states[k] = COMPLETE if current == self._destination else FAILED

        bee.route, bee.state, bee.cost, bee.iteration_created = route_edges, states[k], total_cost, iteration

    return ForwardPassResult(routes, costs, states, iteration, ...)

# =====================================================================
# PSEUDOCODE: _backward_pass(fwd, iteration)
# =====================================================================
def _backward_pass(fwd, iteration):
    # Phase 1: Evaluation
    for bee in self._bees:
        if bee.state == COMPLETE:
            bee.quality = 1.0 / (bee.cost + _EPS)
        else:
            bee.quality = 0.0
            bee.cost = inf

    sorted_indices = sort desc by quality
    best_idx = sorted_indices[0]
    best_cost = self._bees[best_idx].cost
    best_route = self._bees[best_idx].route

    # Phase 2: Loyalty Decision
    K = self._config.elite_count
    loyal_indices = sorted_indices[:K]  # auto-loyal
    uncommitted_indices = []

    max_q = max(bee.quality for bee in self._bees)
    for bee in self._bees:
        bee.norm_quality = bee.quality / max_q if max_q > 0 else 0.0

    loyal_stream = self._swarm_rng.get_stream("bco.loyalty")
    for k, bee in enumerate(self._bees):
        if bee.state != COMPLETE:
            uncommitted_indices.append(k)
            bee.is_loyal = False
            continue
        if k in set(loyal_indices):
            bee.is_loyal = True
            continue
        p_loyal = bee.norm_quality
        if loyal_stream.random() <= p_loyal:
            loyal_indices.append(k)
            bee.is_loyal = True
        else:
            uncommitted_indices.append(k)
            bee.is_loyal = False

    # Phase 3: Recruitment
    if uncommitted_indices and loyal_indices:
        rec_stream = self._swarm_rng.get_stream("bco.recruitment")
        recruit(uncommitted_indices, loyal_indices, rec_stream)

    update_templates_and_diversity()
    return BackwardPassResult(...)

# =====================================================================
# PSEUDOCODE: _loyalty_decision(bee_index, stream)
# =====================================================================
def _loyalty_decision(bee_index, stream):
    bee = self._bees[bee_index]
    return stream.random() <= bee.norm_quality

# =====================================================================
# PSEUDOCODE: _recruitment(uncommitted, loyal, stream)
# =====================================================================
def _recruitment(uncommitted, loyal, stream):
    total_o = sum(self._bees[j].quality for j in loyal)
    if total_o <= 0:
        for u_idx in uncommitted:
            recruiter = stream.choice(list(loyal))
            self._bees[u_idx].template = list(self._bees[recruiter].route)
        return

    loyal_list = list(loyal)
    cum_probs = cumulative sum of (quality / total_o) for each loyal bee

    for u_idx in uncommitted:
        r = stream.random()
        idx = binary_search(cum_probs, r) on loyal_list
        self._bees[u_idx].template = list(self._bees[idx].route)

# =====================================================================
# PSEUDOCODE: _update_templates()
# =====================================================================
def _update_templates():
    for bee in self._bees:
        if bee.state != FAILED and bee.is_loyal and bee.state == COMPLETE:
            bee.template = list(bee.route)

# =====================================================================
# PSEUDOCODE: _compute_diversity()
# =====================================================================
def _compute_diversity():
    templates = [t for t in bee.templates if t is not None]
    if len(templates) < 2:
        return 0.0
    total_sim = 0
    pairs = 0
    for each pair (i, j):
        ti, tj = set(templates[i]), set(templates[j])
        union = len(ti | tj)
        if union > 0:
            total_sim += len(ti & tj) / union
        pairs += 1
    avg_sim = total_sim / pairs
    return 1.0 - avg_sim

# =====================================================================
# PSEUDOCODE: _compute_selection_probs(feasible, template)
# =====================================================================
def _compute_selection_probs(feasible, template):
    template_set = set(template) if template else set()
    probs = []
    for e in feasible:
        eta = self._visibility.values.get(e.edge_id, 0.0)
        w = eta ** self._config.beta
        if e.edge_id in template_set:
            w *= 1.0 + self._config.delta
        probs.append(w)

    total = sum(probs)
    if total <= 0:
        return [1.0 / len(feasible)] * len(feasible)
    return [p / total for p in probs]
```

## 9. Time Complexity

Let:
- `I` = `max_iterations`
- `P` = `population_size`
- `F` = `forward_steps` (max construction steps)
- `d` = maximum out-degree of any node in the graph
- `B` = K (elite_count)

**Per iteration:**
- Forward pass: `O(P * F * d)` — each bee walks up to F steps, at each step iterates over `d` outgoing edges for feasibility filtering and probability computation.
- Backward pass evaluation: `O(P)` — iterate bees to set quality.
- Loyalty decision: `O(P)` — compute max quality, normalize, decide each bee.
- Recruitment: `O(P * log(B))` — binary search for each uncommitted bee; building cum_probs is `O(B)`.
- Diversity: `O(P^2 * L)` where `L` is average template length (templates are subsets of routes, at most F).
- Sorting for elite selection: `O(P log P)`.

**Total per iteration:** `O(P * F * d + P log P)` (diversity term subsumed by `P log P` when considering route set operations).

**Total:** `O(I * P * F * d + I * P log P)`

## 10. Space Complexity

- **Bee population:** `O(P * F)` — P bees each storing a route of up to F edge IDs.
- **Visibility cache:** `O(E)` — one float per edge in the graph.
- **Templates:** `O(P * L)` where L ≤ F — each bee may store a template route.
- **Statistics:** `O(I)` — iteration-by-iteration stats array.
- **Route candidates for result:** `O(P)` — at most P unique routes.

**Total:** `O(P * F + E)` — dominant terms.

## 11. Strengths

1. **No pheromone matrix** — avoids `O(E^2)` or `O(E)` matrix storage/convergence issues. Visibility is cheap, static within a call.
2. **Explicit recruitment** — uncommitted bees copy templates from high-quality bees, providing directed exploration without global communication.
3. **Elite preservation** — top `elite_count` bees are always loyal, preventing loss of the best solutions.
4. **Template-based guidance** — edges in the template get a `(1 + delta)` bonus, allowing bees to exploit known good paths while still exploring via visibility-weighted selection.
5. **Determinism** — same seed + same config = identical results (all randomness goes through `SwarmRandom` named streams).
6. **Independent bee construction** — each bee constructs its own route without global synchronization beyond the backward pass.

## 12. Weaknesses

1. **No local search** — no improvement pass after construction (no intra-route 2-opt, swap, or relocate). Pure constructive BCO gets trapped in locally optimal routes.
2. **No inter-bee communication during forward pass** — bees cannot share partial solutions during construction; all sharing happens only via template inheritance at iteration boundaries.
3. **Static visibility** — visibility (`1 / cost`) is computed once at the start from current edge states. If edge costs change mid-run (a SUMO event), visibility is stale.
4. **Dead-end vulnerability** — bees can walk into dead-end branches; they simply stop and get `FAILED`, wasting computation. The non-dead-end prefiler (`bco.py:463-469`) mitigates this but is a heuristic.
5. **No stagnation detection** — no mechanism to reset all bee templates if diversity drops to zero.

## 13. Why It Was Selected

1. **Simplicity** — constructive BCO requires only 3 hyperparameters (`beta, delta, elite_count`) versus ACO's 4+ (`alpha, beta, rho, tau0, Q, elite`).
2. **No global pheromone** — avoiding the global pheromone matrix reduces memory for large graphs and eliminates the need for pheromone evaporation tuning and daemon actions.
3. **Adaptability to dynamic events** — each `optimize()` call is independent and starts from fresh edge states from `C dynamics .rapping new` congestion/emergency/cost_calculator.`,
4. **SUMO-friendly** — `SwarmToRoutingAdapter` converts to `RoutingResult` without requiring SUMO-internal state. The adapter handles the mapping of edge IDs to node sequences and computes distance/time/energy from graph data.
5. **Theoretical grounding** — directly maps to the constructive BCO literature (Teodorovic 2009), making the thesis methodology verifiable against established research.

## 14. How It Interacts with SUMO

BCO communicates with SUMO only via the **`SwarmToRoutingAdapter`** (`adapter.py:24`):

```
SUMO Traffic Simulator
    ↓ (traci)
Decision Engine
    ↓ (RoutingRequest)
SwarmToRoutingAdapter.compute_route(request, graph)
    ↓ (builds SwarmContext)
BCORouting.optimize(context)
    ↓ (returns SwarmResult)
SwarmToRoutingAdapter.compute_route(...)
    ↓ (converts to RoutingResult)
RoutingResult → Decision Engine → SUMO via traci
```

The adapter:
1. Builds `SwarmContext` from the `RoutingRequest` + `DirectedGraph`
2. Creates a `CompositeCostCalculator` from config cost weights
3. Calls `optimize()`
4. Converts the `SwarmResult` best candidate into a `Route` (node sequence + edge sequence + distance/time/energy)
5. Wraps everything in a `RoutingResult`

No pheromone matrix needs to be maintained across SUMO time steps. Each routing decision is a fresh optimization.

## 15. How It Responds to Congestion, Road Closures, Emergency Events

BCO responds indirectly through the `cost_calculator` and `edge.state`:

| Event | Effect on `MutableEdgeState` | Effect on cost/visibility | Effect on BCO |
|---|---|---|---|
| Congestion | `congestion_factor > 1.0`, lower `current_speed_mps` | `EdgeCostBreakdown.time_cost` increases → higher total cost | Edges become less visible (`eta = 1 / (cost + EPS)`) |
| Road closure | `is_blocked = True` | `_build_visibility()` sets visibility to 0.0; `_edge_total_cost()` returns `inf` | Edge is removed from feasible set; bee must choose alternate |
| Hazard | `hazard_penalty_s > 0` | `EdgeCostBreakdown.hazard_penalty` added to weighted total | Same congestion mechanism — cost increases, attractiveness decreases |
| Emergency corridor | `emergency_penalty_s > 0` | Same as hazard | Same mechanism |
| Communication disruption | `communication_penalty_s > 0` | Same as hazard | Same mechanism |
| Speed drop | `current_speed_mps` decreased | `time_cost = length / speed` increases | Same mechanism |

**Important:** BCO never reads or modifies `MutableEdgeState` directly. It only reads the **cost** returned by `CompositeCostCalculator.compute_edge_cost(edge)`, which already incorporates all state. The visibility cache is built from these costs at the start of each `optimize()` call.

## 16. How Randomness Is Controlled

All stochastic decisions use `SwarmRandom` (`random.py:12`) with named sub-streams:

| Stream name | Usage in BCO | Method:line |
|---|---|---|
| `bco.selection` | Edge selection during roulette-wheel in forward pass | `_forward_pass()`:435 |
| `bco.loyalty` | Random decision in loyalty: `rho ≤ p_loyal` | `_loyalty_decision()`:611 |
| `bco.recruitment` | Roulette-wheel for recruiter selection; fallback `random.choice` | `_recruitment()`:622 |

Each stream is derived deterministically:
```python
name_hash = hash(name) & 0x7FFFFFFF
stream_seed = (base_seed ^ name_hash) & 0x7FFFFFFF
```

Adding or removing a stream does not affect the sequences of other streams. There is **no** use of `random.random()`, `numpy.random`, `secrets`, or time-based seeds anywhere in `bco.py`.

## 17. Determinism and Reproducibility

Given:
- Same `SwarmConfig` (same `seed`, `population_size`, `max_iterations`, `hyperparameters` keys)
- Same `RoutingRequest` (same `source_node`, `destination_node`)
- Same `DirectedGraph` (same edges, same `MutableEdgeState`)
- Same `CompositeCostCalculator` (same `CostWeights`)

Then:
- `BCOConfiguration.from_config()` will produce the same `forward_steps, beta, delta, elite_count`
- `SwarmRandom(seed)` will produce the same 3 named streams
- All bee constructions, loyalty decisions, and recruitment choices will be identical
- The output `SwarmResult.best_solution.edge_sequence` will be identical

One caveat: Python's `dict` iteration order is insertion-order in CPython 3.7+, but if the graph is created in a different order, `outgoing_edges()` order changes, which can affect roulette-wheel tie-breaking for equal-probability edges. The graph itself uses insertion-ordered dicts (`graph.py:79-87`) so this is deterministic within the same graph construction sequence.

## 18. Mapping Between Pseudocode and Implementation

| Step | Pseudocode section | Method | File:Line |
|---|---|---|---|
| Validate context | `errors = validate_context(context)` | `BCOValidator.validate_context()` | `bco.py:225` |
| Build BCO config | `bco_cfg = BCOConfiguration.from_config(cfg)` | `BCOConfiguration.from_config()` | `bco.py:166` |
| Build visibility | `build_visibility(G, cc, bco_cfg)` | `BCORouting._build_visibility()` | `bco.py:398` |
| Init population | `[BeeState(...) for k in range(B)]` | `BCORouting.optimize()` lines 305–311 | `bco.py:305` |
| Init termination | `checker = TerminationChecker(cfg)` | `BCORouting.optimize()` line 319 | `bco.py:319` |
| Iteration loop | `for iteration in range(cfg.max_iterations):` | `BCORouting.optimize()` line 328 | `bco.py:328` |
| Forward pass | `fwd = forward_pass(iteration)` | `BCORouting._forward_pass()` | `bco.py:430` |
| Feasibility filter | `feasible = [e for e in outgoing if ...]` | `BCORouting._forward_pass()` lines 451–458 | `bco.py:451` |
| Backtrack prevention | `feasible = [e for e in feasible if e.target != prev_node]` | `BCORouting._forward_pass()` line 458 | `bco.py:458` |
| Dead-end prefiler | `non_deadend = [e for e in feasible if ...]` | `BCORouting._forward_pass()` lines 462–469 | `bco.py:462` |
| Selection probs | `probs = compute_selection_probs(feasible, template)` | `BCORouting._compute_selection_probs()` | `bco.py:510` |
| Roulette edge choose | `roulette_wheel(feasible, probs, stream)` | `BCORouting._forward_pass()` lines 473–480 | `bco.py:473` |
| Edge cost at traversal | `edge_cost, _ = cost_calculator.compute_edge_cost(chosen)` | `BCORouting._forward_pass()` line 483 | `bco.py:483` |
| Destination check | `if current == destination: break` | `BCORouting._forward_pass()` line 488 | `bco.py:488` |
| Status assignment | `COMPLETE if reached else FAILED` | `BCORouting._forward_pass()` lines 493–496 | `bco.py:493` |
| Backward pass | `bwd = backward_pass(fwd, iteration)` | `BCORouting._backward_pass()` | `bco.py:535` |
| Evaluation | `quality = 1.0 / (cost + _EPS)` | `BCORouting._backward_pass()` lines 541–546 | `bco.py:541` |
| Sort by quality | `sorted_indices = sorted(..., key=quality, reverse=True)` | `BCORouting._backward_pass()` lines 548–549 | `bco.py:548` |
| Elite auto-loyal | `elite_set = set(sorted_indices[:K])` | `BCORouting._backward_pass()` line 561 | `bco.py:561` |
| Quality normalization | `bee.norm_quality = bee.quality / max_q` | `BCORouting._backward_pass()` lines 566–568 | `bco.py:566` |
| Loyalty check | `rho <= p_loyal` | `BCORouting._loyalty_decision()` | `bco.py:610` |
| Recruitment | `recruit(uncommitted, loyal, stream)` | `BCORouting._recruitment()` | `bco.py:621` |
| Roulette cumsum | `cumulative sum of quality fractions` | `BCORouting._recruitment()` lines 631–636 | `bco.py:631` |
| Binary search for recruiter | `binary_search(cum_probs, r)` | `BCORouting._recruitment()` lines 640–647 | `bco.py:640` |
| Template update | `bee.template = list(bee.route)` | `BCORouting._update_templates()` | `bco.py:654` |
| Diversity | `1 - avg_jaccard_similarity(templates)` | `BCORouting._compute_diversity()` | `bco.py:665` |
| Update global best | `if best < global_best: update` | `BCORouting.optimize()` lines 338–340 | `bco.py:338` |
| Termination check | `term = checker.check(search_state)` | `BCORouting.optimize()` line 378 | `bco.py:378` |
| Build swarm result | `build_swarm_result(reason, iter)` | `BCORouting._build_swarm_result()` | `bco.py:687` |
| Route → candidate | `self._route_to_candidate(...)` | `BCORouting._route_to_candidate()` | `bco.py:744` |
| Build iteration stats | `_build_iteration_stats()` | `BCORouting._build_iteration_stats()` | `bco.py:815` |
| Convergence iteration | `_find_convergence_iteration()` | `BCORouting._find_convergence_iteration()` | `bco.py:837` |
| Failure result | `_failure_result(reason)` | `BCORouting._failure_result()` | `bco.py:847` |
| Auto-registration | `SwarmFactory.register("bco", BCORouting)` | module-level | `bco.py:864` |
| Edge cost wrapper | `_edge_total_cost(edge)` | `BCORouting._edge_total_cost()` | `bco.py:417` |
| Adapter entry point | `compute_route(request, graph)` | `SwarmToRoutingAdapter.compute_route()` | `adapter.py:56` |
| Adapter → SwarmContext | `SwarmContext(...)` | `SwarmToRoutingAdapter.compute_route()` lines 104–112 | `adapter.py:104` |
| SwarmRandom stream derivation | `stream_seed = (base_seed ^ hash(name)) & MASK` | `SwarmRandom.get_stream()` | `random.py:48` |
| Termination: max iter | `if state.iteration >= config.max_iterations` | `TerminationChecker.check()` step 1 | `termination.py:83` |
| Termination: time limit | `if elapsed >= config.time_limit_s` | `TerminationChecker.check()` step 2 | `termination.py:92` |
| Termination: target score | `if best_score <= target_score` | `TerminationChecker.check()` step 3 | `termination.py:101` |
| Termination: convergence | `if |best - prev_best| < threshold` | `TerminationChecker.check()` step 4 | `termination.py:110` |
| Termination: stall | `if no_improvement_count >= stall_limit` | `TerminationChecker.check()` step 5 | `termination.py:124` |