# PSO — Constructive Discrete Particle Swarm Optimization

## 1. Purpose in this thesis

PSO provides a **memory-guided stochastic search** for dynamic EV routing. Each particle remembers its personal best route (cognitive component) and the swarm shares the global best route (social component). The algorithm incrementally constructs routes edge-by-edge using probabilistic selection weighted by these memory signals plus heuristic visibility. It serves as a **baseline swarm intelligence method** against which the E3-Hybrid is compared in the routing benchmark.

## 2. Theory actually implemented

The implementation is a **constructive-discrete adaptation** of PSO (Kennedy & Eberhart, 1995; Mohemmed et al., 2008) for shortest-path problems. No continuous velocity vector is maintained. Instead, at each construction step the three PSO forces — inertia, cognitive, and social — are represented as probabilistic edge-selection weights:

- **Inertia (current route attraction):** `I` = 1.0 if the candidate edge matches the particle's current route at the current step, else `epsilon`.
- **Cognitive (personal best):** `P` = 1.0 if the edge matches the particle's `p_best_route` at this step, else `epsilon`.
- **Social (global best):** `G` = 1.0 if the edge matches the swarm's `g_best_route` at this step, else `epsilon`.
- **Heuristic visibility:** `eta` = 1 / (edge_cost + epsilon), or 0.0 for blocked edges.

The total weight for an edge is `w * I + c1 * P + c2 * G + c3 * eta` (line 576). A roulette-wheel selection chooses among candidate edges.

Linear inertia decay follows Shi & Eberhart (1998): `w = w_start - (w_start - w_end) * iter / max_iter` (Eq. 5, line 422).

## 3. Inputs

The `optimize(context: SwarmContext)` method receives:

| Input | Type | Source |
|-------|------|--------|
| `routing_request` | `RoutingRequest` (source_node, destination_node, vehicle_id, ...) | Decision Engine |
| `graph` | `DirectedGraph` (read-only, never mutated) | SUMO simulation |
| `cost_calculator` | `CompositeCostCalculator` | SwarmConfig.cost_weights |
| `config` | `SwarmConfig` (population_size, max_iterations, hyperparameters dict) | YAML config |
| `random_seed` | `int` (via context.random_seed) | SwarmConfig.seed |

## 4. Outputs

`SwarmResult` is returned, then adapted to `RoutingResult` via `SwarmToRoutingAdapter`:

| Output field | Description |
|-------------|-------------|
| `SwarmResult.best_solution` | Best `RouteCandidate` found (min-cost feasible route) |
| `SwarmResult.candidates` | Tuple of all unique feasible `RouteCandidate`s |
| `SwarmResult.statistics` | `SwarmStatistics` (iterations, runtime, scores, diversity history) |
| `SwarmResult.iterations` | Per-iteration `IterationStatistics` |
| `SwarmResult.success` | Boolean — whether a feasible route was found |
| `SwarmResult.failure_reason` | Human-readable error or None |

`SwarmToRoutingAdapter.compute_route()` builds `SwarmContext`, calls `optimize()`, converts `SwarmResult` into `RoutingResult` with a `Route` primary_route.

## 5. Configuration parameters

All hyperparameters are extracted from `SwarmConfig.hyperparameters` (a generic dict) via `PSOConfiguration.from_config()`:

| Parameter | Code default | YAML key | Type | Description |
|-----------|-------------|----------|------|-------------|
| `inertia_start` | 0.9 | `inertia_start` | float | Initial inertia weight (w_start) |
| `inertia_end` | 0.4 | `inertia_end` | float | Final inertia weight (w_end) |
| `cognition_weight` | 2.0 | `cognition_weight` | float | Cognitive (p_best) weight (c1) |
| `social_weight` | 2.0 | `social_weight` | float | Social (g_best) weight (c2) |
| `visibility_weight` | 1.0 | `visibility_weight` | float | Heuristic visibility weight (c3) |
| `epsilon` | 1e-10 | `epsilon` | float | Small value for non-matching edges |
| `forward_steps` | 100 | `forward_steps` | int | Max steps per route construction |

Additionally from `SwarmConfig`:

| Parameter | Description |
|-----------|-------------|
| `population_size` | Number of particles (must be >= 2) |
| `max_iterations` | Maximum optimization iterations |
| `time_limit_s` | Wall-clock time limit |
| `convergence_threshold` | Min improvement to continue |
| `stall_limit` | Iterations without improvement before stop |
| `target_score` | Target cost to achieve |
| `seed` | Random seed for reproducibility |
| `cost_weights` | `CostWeights` (distance, time, energy, congestion, hazard, emergency, communication) |

## 6. Internal data structures

### `ParticleState` (dataclass)
```
k: int                  # particle index
route: list[EdgeId]     # current constructed route
cost: float             # total cost of current route
p_best_route: list[EdgeId]  # personal best route
p_best_cost: float      # personal best cost
state: ParticleStatus   # CONSTRUCTING | COMPLETE | FAILED
visited: set[NodeId]    # nodes visited (initialised empty, not used in construction)
```

### `ParticleStatus` (Enum)
```
CONSTRUCTING, COMPLETE, FAILED
```

### `VisibilityCache` (dataclass)
```
values: dict[EdgeId, float]  # precomputed 1/(cost+eps) per edge (0.0 for blocked)
```

### `PSOConfiguration` (frozen dataclass)
Type-safe extraction of hyperparameters with validation. See section 5.

### `PSOStatistics` (frozen dataclass)
```
iteration, best_cost, avg_cost, worst_cost, inertia, diversity, runtime_s
```

### `BackwardPassResult` (dataclass)
```
best_cost, best_route, diversity
```

### Instance state of `PSORouting`
```
_particles: list[ParticleState]
_visibility: VisibilityCache | None
_swarm_rng: SwarmRandom | None
_config: PSOConfiguration | None
_context: SwarmContext | None
_global_best_cost: float
_global_best_route: list[EdgeId]
_iteration_stats: list[PSOStatistics]
_graph: DirectedGraph | None
_cost_calculator: CompositeCostCalculator | None
_source: NodeId | None
_destination: NodeId | None
```

## 7. Step-by-step written algorithm

1. **Validate** context (graph, cost_calculator, source != destination).
2. **Build visibility cache** — compute heuristic `1/(cost+eps)` for every edge; blocked edges get 0.0.
3. **Initialize random streams** via `SwarmRandom` with `context.random_seed`.
4. **Initialize population** — for each particle k:
   - Construct route using **only visibility** (w=0, c1=0, c2=0, c3=visibility_weight).
   - Compute route cost.
   - Set p_best = current route and cost.
   - Set particle state (COMPLETE if reaches destination, else FAILED).
5. **Initialize global best** — find particle with minimum p_best_cost; set g_best = its p_best.
6. **Create TerminationChecker** with config, call `checker.start()`.
7. **Iteration loop** (for iteration in 0..max_iterations-1):
   a. Compute inertia weight via linear decay `w(iter)` (Eq. 5).
   b. **Forward pass:** For each particle:
      - Construct new route using weighted probabilistic selection:
        `weight = w * I + c1 * P + c2 * G + c3 * eta`
        where I=inertia_match, P=p_best_match, G=g_best_match, eta=visibility.
      - Compute new route cost.
      - Update particle route, cost, state.
   c. **Backward pass:**
      - Personal best update (Eq. 14): if new route is complete and cost < p_best_cost, replace p_best.
      - Global best update (Eq. 15): find min p_best_cost across all particles, update g_best.
      - Compute diversity via Jaccard similarity on p_best routes (Eq. 16): `1 - avg(Jaccard_similarity)`.
   d. Update global best if this iteration found a better route.
   e. Record per-iteration statistics (PSOStatistics).
   f. Track no-improvement count for termination.
   g. Build SearchState, call checker.check() — if should_stop, build and return SwarmResult.
8. After loop, return SwarmResult with best solution found.

## 8. Clear implementation-level pseudocode

```
FUNCTION PSORouting.optimize(context):
    // Validate context
    errors = PSOValidator.validate_context(context)
    IF errors: return failure_result(errors)

    // Store context
    self._graph = context.graph
    self._cost_calculator = context.cost_calculator
    self._source = context.routing_request.source_node
    self._destination = context.routing_request.destination_node
    config = context.config

    // Build PSO configuration from hyperparameters
    self._config = PSOConfiguration.from_config(config)

    // Validate nodes exist in graph
    IF not self._graph.has_node(self._source): return failure
    IF not self._graph.has_node(self._destination): return failure

    // Precompute visibility for all edges
    CALL _build_visibility()

    // Initialize random streams
    self._swarm_rng = new SwarmRandom(context.random_seed)

    // Create particle population
    CALL _initialize()

    // Set global best from initialized population
    self._global_best_cost = min(p.p_best_cost for all particles)
    best_idx = argmin(p.p_best_cost for all particles)
    self._global_best_route = copy(p_best_route[best_idx])

    // Setup termination checker
    checker = new TerminationChecker(config)
    checker.start()

    start_time = time.perf_counter()
    no_improvement_count = 0
    prev_best_score = self._global_best_cost

    FOR iteration = 0..config.max_iterations-1:
        iteration_start = time.perf_counter()

        // Compute inertia weight (linear decay)
        w = _compute_inertia(iteration, config.max_iterations)

        // --- Forward Pass ---
        (fwd_routes, fwd_costs, fwd_states) = _forward_pass(iteration, w)

        // --- Backward Pass ---
        bwd = _backward_pass(fwd_routes, fwd_costs, fwd_states)

        // Update global best if improved
        IF bwd.best_cost < self._global_best_cost:
            self._global_best_cost = bwd.best_cost
            self._global_best_route = copy(bwd.best_route)

        // Record iteration statistics
        costs_success = [p.cost for p in self._particles if COMPLETE]
        avg_cost = mean(costs_success) IF costs_success ELSE INF
        worst_cost = max(costs_success) IF costs_success ELSE INF
        self._iteration_stats.append(PSOStatistics(
            iteration, bwd.best_cost, avg_cost, worst_cost, w, bwd.diversity, runtime
        ))

        // Update no-improvement count
        current_best = self._global_best_cost
        IF current_best >= prev_best_score:
            no_improvement_count++
        ELSE:
            no_improvement_count = 0
        prev_best_score = current_best

        // Build SearchState and check termination
        search_state = SearchState(iteration+1, current_best, prev_best, 
                                    no_improvement_count, bwd.diversity, elapsed)
        term = checker.check(search_state)
        IF term.should_stop:
            RETURN _build_swarm_result(total_time, term.reason, term.iteration)

    RETURN _build_swarm_result(total_time, "Max iterations", config.max_iterations)
END FUNCTION

// ---------------------------------------------------------------------------

FUNCTION _build_visibility():
    FOR each edge in graph.edges():
        eid = edge.edge_id
        IF edge.state.is_blocked:
            vis[eid] = 0.0
        ELSE:
            edge_cost = _cost_calculator.compute_edge_cost(edge)  # may raise
            IF not finite(edge_cost) OR edge_cost < 0:
                vis[eid] = 0.0
            ELIF edge_cost == 0.0:
                vis[eid] = 1.0 / EPS
            ELSE:
                vis[eid] = 1.0 / (edge_cost + EPS)
    self._visibility = VisibilityCache(vis)
END FUNCTION

FUNCTION _edge_total_cost(edge):
    IF edge.state.is_blocked: return INF
    cost_val = _cost_calculator.compute_edge_cost(edge)  # may raise
    return cost_val IF finite(cost_val) AND cost_val >= 0 ELSE INF
END FUNCTION

// ---------------------------------------------------------------------------

FUNCTION _compute_inertia(iteration, max_iterations):
    IF max_iterations <= 1: return config.inertia_end
    return config.inertia_start - (config.inertia_start - config.inertia_end) 
           * iteration / (max_iterations - 1)
END FUNCTION

// ---------------------------------------------------------------------------

FUNCTION _initialize():
    B = context.config.population_size
    init_stream = _swarm_rng.get_stream("pso.init")
    self._particles = []
    FOR k = 0..B-1:
        // Pure visibility-based construction (w=0, c1=0, c2=0)
        route = _construct_route(
            current_route=[], p_best_route=[], g_best_route=[],
            w=0.0, c1=0.0, c2=0.0, c3=config.visibility_weight,
            stream=init_stream
        )
        cost = _compute_route_cost(route)
        self._particles.append(ParticleState(
            k=k, route=copy(route), cost=cost,
            p_best_route=copy(route), p_best_cost=cost,
            state=COMPLETE IF route ELSE FAILED, visited=empty_set
        ))
END FUNCTION

// ---------------------------------------------------------------------------

FUNCTION _forward_pass(iteration, inertia):
    B = len(self._particles)
    routes = [empty_list] * B
    costs = [0.0] * B
    states = [CONSTRUCTING] * B
    sel_stream = _swarm_rng.get_stream("pso.selection")

    FOR k = 0..B-1:
        particle = self._particles[k]
        // Construct route with all four forces
        new_route = _construct_route(
            current_route=particle.route,
            p_best_route=particle.p_best_route,
            g_best_route=self._global_best_route,
            w=inertia,
            c1=config.cognition_weight,
            c2=config.social_weight,
            c3=config.visibility_weight,
            stream=sel_stream
        )
        new_cost = _compute_route_cost(new_route)
        particle.route = new_route
        particle.cost = new_cost
        particle.state = COMPLETE IF _route_reaches_destination(new_route) ELSE FAILED
        routes[k] = new_route
        costs[k] = new_cost
        states[k] = particle.state
    RETURN (routes, costs, states)
END FUNCTION

FUNCTION _compute_route_cost(route):
    total = 0.0
    FOR each eid in route:
        edge = _graph.get_edge(eid)
        (ec, _) = _cost_calculator.compute_edge_cost(edge)
        IF finite(ec) AND ec >= 0:
            total += ec
        ELSE:
            RETURN INF
    RETURN total
END FUNCTION

FUNCTION _route_reaches_destination(route):
    IF empty(route): RETURN False
    last_edge = _graph.get_edge(route[-1])
    RETURN last_edge.target == self._destination
END FUNCTION

// ---------------------------------------------------------------------------

FUNCTION _construct_route(current_route, p_best_route, g_best_route, 
                           w, c1, c2, c3, stream):
    current = self._source
    prev = None
    route = empty_list
    eps = config.epsilon
    max_steps = config.forward_steps

    FOR step = 0..max_steps-1:
        IF current == self._destination: BREAK

        // Gather feasible outgoing edges
        outgoing = _graph.outgoing_edges(current)
        candidates = [e for e in outgoing IF _edge_total_cost(e) < INF]
        IF len(candidates) > 1 AND prev is not None:
            candidates = [e for e in candidates IF e.target != prev]  // no back-track
        IF empty(candidates): BREAK
        // Prefer non-dead-end targets
        IF len(candidates) > 1:
            alive = [e for e in candidates 
                     IF e.target == destination 
                     OR len(outgoing_edges(e.target)) > 0]
            IF alive: candidates = alive

        // Compute selection weights
        weights = []
        FOR each e in candidates:
            I = 1.0 IF step < len(current_route) AND e.edge_id == current_route[step] ELSE eps
            P = 1.0 IF step < len(p_best_route) AND e.edge_id == p_best_route[step] ELSE eps
            G = 1.0 IF step < len(g_best_route) AND e.edge_id == g_best_route[step] ELSE eps
            eta = _visibility.values.get(e.edge_id, 0.0)
            w_total = w * I + c1 * P + c2 * G + c3 * eta
            weights.append(max(w_total, 0.0))

        // Roulette selection
        total_w = sum(weights)
        IF total_w <= 0.0:
            chosen = stream.choice(candidates)
        ELSE:
            r = stream.random() * total_w
            cum = 0.0
            chosen = candidates[-1]
            FOR each (e, j) in enumerate(candidates):
                cum += weights[j]
                IF r <= cum:
                    chosen = e; BREAK

        route.append(chosen.edge_id)
        prev = current
        current = chosen.target

    RETURN route
END FUNCTION

// ---------------------------------------------------------------------------

FUNCTION _backward_pass(routes, costs, states):
    B = len(self._particles)

    // Personal best update (Eq. 14)
    FOR i = 0..B-1:
        IF states[i] == COMPLETE AND costs[i] < self._particles[i].p_best_cost:
            self._particles[i].p_best_route = copy(routes[i])
            self._particles[i].p_best_cost = costs[i]

    // Global best update (Eq. 15)
    best_idx = argmin(p_best_cost of all particles)
    best_cost = self._particles[best_idx].p_best_cost
    best_route = self._particles[best_idx].p_best_route

    // Diversity (Eq. 16)
    diversity = _compute_diversity()

    RETURN BackwardPassResult(best_cost, copy(best_route), diversity)
END FUNCTION

// ---------------------------------------------------------------------------

FUNCTION _compute_diversity():
    // Jaccard-based diversity on p_best routes
    templates = [p.p_best_route for all particles WITH non-empty p_best_route]
    IF len(templates) < 2: RETURN 0.0

    total_sim = 0.0
    pairs = 0
    FOR i = 0..len(templates)-1:
        ti = set(templates[i])
        FOR j = i+1..len(templates)-1:
            tj = set(templates[j])
            union = len(ti OR tj)
            IF union > 0:
                total_sim += len(ti AND tj) / union
            pairs++
    avg_sim = total_sim / pairs IF pairs > 0 ELSE 0.0
    RETURN 1.0 - avg_sim
END FUNCTION

// ---------------------------------------------------------------------------

FUNCTION _build_swarm_result(total_time, term_reason, term_iteration):
    best_rc = _route_to_candidate(self._global_best_route, runtime_s=total_time)
    
    all_candidates = [best_rc]
    seen = set(self._global_best_route)
    FOR each particle:
        IF COMPLETE AND route NOT in seen:
            seen.add(route)
            all_candidates.append(_route_to_candidate(route))

    scores = [p.cost for COMPLETE particles]
    best_score = min(scores) IF scores ELSE INF
    avg_score = mean(scores) IF scores ELSE INF
    worst_score = max(scores) IF scores ELSE INF

    swarm_stats = SwarmStatistics(
        total_iterations=term_iteration, total_runtime_s=total_time,
        best_score, average_score, worst_score,
        convergence_iteration=_find_convergence_iteration(),
        candidate_count=len(all_candidates),
        solutions_evaluated=term_iteration * population_size,
        diversity_history=(s.diversity for s in _iteration_stats),
        score_history=(s.best_cost for s in _iteration_stats),
        termination_reason=term_reason
    )

    success = len(self._global_best_route) > 0
    RETURN SwarmResult(best_rc, tuple(all_candidates), swarm_stats, 
                       tuple(_build_iteration_stats()), 
                       success, None IF success ELSE "No feasible route found")
END FUNCTION

FUNCTION _route_to_candidate(edges, runtime_s):
    IF empty(edges):
        // Return failed candidate with INF cost
        RETURN RouteCandidate(route_id, (source, destination), (""), 
                              1e9, failure_cost, "pso", metadata, runtime_s)
    nodes = [source]
    total_cost = 0.0
    FOR each eid in edges:
        edge = _graph.get_edge(eid)
        nodes.append(edge.target)
        (cost_val, _) = _cost_calculator.compute_edge_cost(edge)
        total_cost += cost_val
    IF not finite(total_cost): total_cost = INF

    RETURN RouteCandidate(
        route_id, tuple(nodes), tuple(edges), total_cost,
        RouteCost(total_cost, ...), "pso", metadata, runtime_s,
        SearchStatistics(iterations, diversity, diversity)
    )
END FUNCTION

FUNCTION _build_iteration_stats():
    result = []
    FOR each s in self._iteration_stats:
        result.append(IterationStatistics(
            s.iteration, s.best_cost, s.avg_cost, (s.best_cost+s.worst_cost)/2,
            s.worst_cost, 0.0, s.diversity, True, s.runtime_s
        ))
    RETURN result
END FUNCTION

FUNCTION _find_convergence_iteration():
    FOR i from len(_iteration_stats)-1 down to 1:
        IF _iteration_stats[i].best_cost < _iteration_stats[i-1].best_cost:
            RETURN i
    RETURN 0 IF _iteration_stats ELSE None
END FUNCTION

FUNCTION _failure_result(reason):
    RETURN SwarmResult(best_solution=None, success=False, failure_reason=reason, 
                       empty_statistics, empty_iterations)
END FUNCTION
```

## 9. Time complexity

Let:
- `B` = population_size
- `I` = max_iterations
- `F` = forward_steps (max steps per route construction)
- `D` = average out-degree of graph nodes

Per iteration:
- **Forward pass:** `B * F * D` — each particle takes up to F steps, evaluating D outgoing edges per step.
- **Backward pass:** `B` — personal best comparisons plus diversity computation `O(B² * avg_route_len)`.
- **Diversity:** `O(B² * L)` where L = average route length in edges.

Overall: **O(I * B * F * D)** — dominated by forward-pass route construction. Diversity computation adds `O(I * B² * L)` which is typically smaller than the forward pass.

## 10. Space complexity

- **Particle states:** `O(B * F)` — B particles, each storing a route of up to F edges.
- **Visibility cache:** `O(E)` — E = total graph edges, one float per edge.
- **Iteration stats:** `O(I)` — one PSOStatistics per iteration.
- **Pheromone matrix:** None (PSO does not use pheromones).

Overall: **O(B*F + E + I)**.

## 11. Strengths

- **Constructive approach avoids velocity discretization** — edges are selected directly, no need to map continuous velocities to discrete graph edges.
- **Memory-guided search** — personal and global best routes focus exploration near promising paths.
- **Linearly decaying inertia** — automatic shift from exploration (high w) to exploitation (low w).
- **Dead-end avoidance** — candidates are filtered to prefer non-dead-end nodes.
- **Backtrack prevention** — immediate predecessor is excluded from candidate set.
- **Deterministic and reproducible** — SwarmRandom named streams ensure identical results for identical inputs.
- **No modification of shared state** — graph is read-only, algorithms are pure functions.
- **Diversity tracking** via Jaccard similarity enables convergence detection.
- **Visibility-only initialization** ensures coverage of the search space before memory takes over.

## 12. Weaknesses

- **No cross-pollination of memory** — each particle only uses its own p_best and the single g_best; there is no mechanism to combine partial routes from different particles.
- **Binary memory signals** — I, P, G are either 1.0 or epsilon; a route that is "close" to a good solution but not an exact match gets no partial credit.
- **No pheromone or global trail** — unlike ACO, there is no indirect communication channel; information spreads only through g_best.
- **Single global best can dominate** — if g_best converges prematurely, all particles may be drawn to a local optimum.
- **Diversity is computed but not used adaptively** — diversity is only recorded for statistics, not actively managed or used to adjust parameters (unlike the E3-Hybrid meta-controller).
- **Weak sensitivity to dynamic changes** — the algorithm operates on a static snapshot of visibility; it does not respond to graph changes within a single optimization run.
- **Visibility is based solely on base cost** — congestion_factor, hazard_penalty, emergency_penalty are all folded into the single edge cost, so the algorithm cannot distinguish between cost components.
- **No local search or path improvement** — once a route is constructed, it is not refined (e.g., no 2-opt, no shortcutting).

## 13. Why it was selected

- **Established baseline** — PSO is one of the most widely studied swarm intelligence algorithms, making it a natural baseline for comparison.
- **Constructive-discrete adaptation** — avoids the complexity of continuous-to-discrete mapping required by standard PSO with velocity vectors.
- **Simple, interpretable** — three well-defined forces (inertia, cognitive, social) make analysis straightforward.
- **Complementary to E3-Hybrid** — PSO contributes its memory model to the hybrid, so isolating its performance helps validate the hybrid's added value.
- **Lightweight** — no pheromone matrix, no template management, minimal bookkeeping.

## 14. How it interacts with the SUMO simulation

The interaction is indirect, mediated by the `SwarmToRoutingAdapter`:

1. **SUMO provides the graph** with current edge states (speed, congestion, blockages) via `MutableEdgeState` on each `Edge`.
2. **`SwarmToRoutingAdapter.compute_route()`** is called by the `BenchmarkRunner` with a `RoutingRequest` and the current `DirectedGraph`.
3. The adapter builds a `SwarmContext` with the graph, cost calculator, and config, then calls `PSORouting.optimize(context)`.
4. PSO builds **visibility from current edge states** at the start of `optimize()`, capturing the snapshot of congestion, blockages, and penalties.
5. The resulting `SwarmResult` is adapted to `RoutingResult` with a `Route` containing node_sequence, edge_sequence, total_distance_m, estimated_travel_time_s, and estimated_energy_kwh.
6. The `RoutingResult` is passed back to the BenchmarkRunner, which feeds it to the Decision Engine.
7. The Decision Engine selects a route for the SUMO vehicle, which then traverses the route in the simulation.

PSO does **not** receive incremental graph updates during a single optimization run — it solves a static shortest-path problem on the current graph snapshot.

## 15. How it responds to congestion, road closures, and emergency events

PSO responds exclusively through the **visibility cache** and **edge total cost**:

- **`edge.state.is_blocked`:** Blocked edges get `visibility = 0.0` and `_edge_total_cost() = INF`, making them effectively invisible to route construction. No particle can traverse a blocked edge (line 391-392, 406-408).
- **`edge.state.congestion_factor`:** Used by `CompositeCostCalculator.compute_edge_cost()` which multiplies base time by `congestion_factor`, increasing the overall edge cost. Higher cost means lower visibility (`1/cost`), making congested edges less likely to be selected.
- **`edge.state.hazard_penalty_s` and `emergency_penalty_s`:** These additive time penalties are included in the edge cost computation, reducing visibility proportionally.
- **`edge.state.current_speed_mps`:** Affects travel time in the cost calculator, influencing visibility.

All responses are **indirect** — the algorithm does not have explicit congestion/emergency handling logic. The cost calculator aggregates all factors into a single scalar cost, and PSO responds naturally by preferring lower-cost (higher-visibility) edges.

## 16. How randomness is controlled

All stochastic decisions use `SwarmRandom` with named streams:

| Stream name | Used in | Purpose |
|-------------|---------|---------|
| `"pso.init"` | `_initialize()` | Roulette selection during initial route construction |
| `"pso.selection"` | `_forward_pass()` | Roulette selection during forward pass |

`SwarmRandom` deterministically derives each named stream from the base seed via:
```python
name_hash = hash(name) & 0x7FFFFFFF
stream_seed = (self._base_seed ^ name_hash) & 0x7FFFFFFF
```

No calls to `random.random()`, `numpy.random`, `secrets`, or time-based seeding.

## 17. Determinism and reproducibility notes

- **Same seed + same config → same results** — guaranteed by SwarmRandom and the pure-function design.
- The graph is never modified; the cost calculator is never modified.
- The only source of non-determinism would be integer overflow in `hash()` across Python versions (stable for CPython since 3.2+).
- Particle iteration order is deterministic (sequential `range(B)`).
- For absolute reproducibility across Python versions/implementations, the `hash(name)` dependency is noted. The bitwise `& 0x7FFFFFFF` mask ensures non-negative seeds for `random.Random`.

## 18. Mapping between pseudocode and implementation methods/classes

| Pseudocode section | Implementation class/method | File:line |
|-------------------|---------------------------|-----------|
| `PSORouting.optimize()` | `PSORouting.optimize()` | `pso.py:258-381` |
| `_build_visibility()` | `PSORouting._build_visibility()` | `pso.py:387-404` |
| `_edge_total_cost()` | `PSORouting._edge_total_cost()` | `pso.py:406-413` |
| `_compute_inertia()` | `PSORouting._compute_inertia()` | `pso.py:419-424` |
| `_initialize()` | `PSORouting._initialize()` | `pso.py:430-456` |
| `_forward_pass()` | `PSORouting._forward_pass()` | `pso.py:462-500` |
| `_compute_route_cost()` | `PSORouting._compute_route_cost()` | `pso.py:502-514` |
| `_route_reaches_destination()` | `PSORouting._route_reaches_destination()` | `pso.py:516-523` |
| `_construct_route()` | `PSORouting._construct_route()` | `pso.py:529-596` |
| `_backward_pass()` | `PSORouting._backward_pass()` | `pso.py:602-630` |
| `_compute_diversity()` | `PSORouting._compute_diversity()` | `pso.py:636-652` |
| `_build_swarm_result()` | `PSORouting._build_swarm_result()` | `pso.py:658-713` |
| `_route_to_candidate()` | `PSORouting._route_to_candidate()` | `pso.py:715-785` |
| `_build_iteration_stats()` | `PSORouting._build_iteration_stats()` | `pso.py:787-807` |
| `_find_convergence_iteration()` | `PSORouting._find_convergence_iteration()` | `pso.py:809-817` |
| `_failure_result()` | `PSORouting._failure_result()` | `pso.py:819-832` |
| `ParticleState` | `ParticleState` (dataclass) | `pso.py:72-82` |
| `ParticleStatus` | `ParticleStatus` (Enum) | `pso.py:60-64` |
| `PSOConfiguration.from_config()` | `PSOConfiguration.from_config()` | `pso.py:132-177` |
| `PSOValidator.validate_context()` | `PSOValidator.validate_context()` | `pso.py:210-219` |
| `VisibilityCache` | `VisibilityCache` (dataclass) | `pso.py:107-111` |
| `BackwardPassResult` | `BackwardPassResult` (dataclass) | `pso.py:840-845` |
| `PSOStatistics` | `PSOStatistics` (dataclass) | `pso.py:90-99` |
| SwarmResult building | `SwarmResult` (dataclass) | `result.py:13-47` |
| Adaptation to RoutingResult | `SwarmToRoutingAdapter.compute_route()` | `adapter.py:56-159` |
| Deterministic RNG | `SwarmRandom` | `random.py:12-65` |
| Termination checking | `TerminationChecker` | `termination.py:46-148` |
| SwarmAlgorithm registration | `SwarmFactory.register("pso", PSORouting)` | `pso.py:851` |
