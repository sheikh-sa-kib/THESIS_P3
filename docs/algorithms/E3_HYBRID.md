# E³-Hybrid — Triple-swarm integration for dynamic EV routing

## 1. Purpose in this thesis

E³-Hybrid is the **primary algorithmic contribution** of this thesis. It integrates three swarm intelligence paradigms — Ant Colony Optimization (pheromone memory), Bee Colony Optimization (recruitment templates), and Particle Swarm Optimization (cognitive/social memory) — into a single unified search. The central hypothesis is that cross-pollination between the three memory structures yields more robust routing decisions than any single paradigm alone. A meta-controller adaptively balances the influence of each subpopulation based on real-time diversity measurements.

## 2. Theory actually implemented

The E³-Hybrid is an **original design** developed for this thesis (see hybrid design document). It is not a direct reproduction of any single existing algorithm but synthesises three established paradigms:

- **ACO (Dorigo & Stützle, 2004):** Pheromone trails on edges provide indirect communication. Implemented via `HybridPheromoneMatrix` with local updates (Eq. 13: `tau ← (1-ρ_local) * tau + ρ_local * tau0`) during ant forward passes and global updates (Eqs. 14-16: `tau ← (1-ρ) * tau + ρ * (1/best_cost)`) during the backward pass.
- **BCO (Teodorović, 2008; Karaboga, 2005):** Recruitment templates form a bee-inspired memory of top routes. The top `template_count` routes from each iteration are stored and influence construction via pattern matching (`raw_B = 1.0` if edge matches template at step, else `epsilon`).
- **PSO (Kennedy & Eberhart, 1995):** Personal best (p_best) and global best (g_best) memories drive cognitive/social influence. `raw_P = cognition_weight * M_p + social_weight * M_g` where `M_p=1` if edge matches p_best at step, `M_g=1` if matches g_best (else epsilon).

All four influences (pheromone A, template B, memory P, heuristic H) are **normalised to [0,1]** before weighted combination (Eqs. 8-11):
```
norm_X[i] = (raw_X[i] - min(raw_X)) / (max(raw_X) - min(raw_X))
```
The combined weight per candidate edge is (Eq. 2):
```
weight[j] = alpha_a * norm_A[j] + alpha_b * norm_B[j] + alpha_p * norm_P[j] + alpha_h * norm_H[j]
```

A **meta-controller** (Eqs. 22-25) adapts `alpha_a`, `alpha_b`, `alpha_p` every `adapt_interval` iterations based on per-subpopulation diversity. Low-diversity subpopulations have their influence decayed (multiplied by `adapt_decay`); recovered subpopulations receive a gain (`adapt_recovery_gain`). Redistributed weight goes to the heuristic (`alpha_h`) if all three subpopulations are diverse-starved.

## 3. Inputs

Same as PSO — the `optimize(context: SwarmContext)` method receives:

| Input | Type | Source |
|-------|------|--------|
| `routing_request` | `RoutingRequest` (source_node, destination_node, vehicle_id, ...) | Decision Engine |
| `graph` | `DirectedGraph` (read-only, never mutated) | SUMO simulation |
| `cost_calculator` | `CompositeCostCalculator` | SwarmConfig.cost_weights |
| `config` | `SwarmConfig` (population_size, max_iterations, hyperparameters dict) | YAML config |
| `random_seed` | `int` (via context.random_seed) | SwarmConfig.seed |

## 4. Outputs

Identical structure to PSO: `SwarmResult` adapted via `SwarmToRoutingAdapter` to `RoutingResult`. The best solution is the global best route found across all three subpopulations. Metadata includes final `alpha_a`, `alpha_b`, `alpha_p`, `alpha_h`, template count, and per-subpopulation counts.

## 5. Configuration parameters

All hyperparameters are extracted from `SwarmConfig.hyperparameters` via `HybridConfiguration.from_swarm_config()`:

### Population partitioning
| Parameter | Default | YAML key | Description |
|-----------|---------|----------|-------------|
| `ant_ratio` | 0.4 | `ant_ratio` | Fraction of population assigned to ANT subpopulation |
| `bee_ratio` | 0.3 | `bee_ratio` | Fraction of population assigned to BEE subpopulation |
| `particle_ratio` | 0.3 | `particle_ratio` | Fraction of population assigned to PARTICLE subpopulation |
| *(Ratios must sum to 1.0)* | | | |

### Initial influence weights
| Parameter | Default | Min | Max | YAML key | Description |
|-----------|---------|-----|-----|----------|-------------|
| `alpha_a` | 1.0 | 0.1 | 3.0 | `alpha_a` | ACO (pheromone) influence weight |
| `alpha_b` | 1.0 | 0.1 | 3.0 | `alpha_b` | BCO (template) influence weight |
| `alpha_p` | 1.0 | 0.1 | 3.0 | `alpha_p` | PSO (memory) influence weight |
| `alpha_h` | 1.0 | — | — | `alpha_h` | Heuristic (visibility) influence weight (not dynamically bounded) |

### BCO templates
| Parameter | Default | YAML key | Description |
|-----------|---------|----------|-------------|
| `template_count` | 3 | `template_count` | Number of top routes retained as BCO templates |

### PSO inertia
| Parameter | Default | YAML key | Description |
|-----------|---------|----------|-------------|
| `inertia_start` | 0.9 | `inertia_start` | Initial PSO inertia weight |
| `inertia_end` | 0.4 | `inertia_end` | Final PSO inertia weight |
| `cognition_weight` | 2.0 | `cognition_weight` | PSO cognitive (p_best) weight |
| `social_weight` | 2.0 | `social_weight` | PSO social (g_best) weight |

### Pheromone
| Parameter | Default | YAML key | Description |
|-----------|---------|----------|-------------|
| `pheromone_tau0` | 1.0 | `pheromone_tau0` | Initial pheromone value on all edges |
| `pheromone_min` | 0.01 | `pheromone_min` | Minimum allowed pheromone |
| `pheromone_max` | 10.0 | `pheromone_max` | Maximum allowed pheromone |
| `rho` | 0.1 | `rho` | Global pheromone evaporation rate |
| `rho_local` | 0.1 | `rho_local` | Local pheromone evaporation rate |
| `beta_a` | 1.0 | `beta_a` | Pheromone exponent in raw_ACO computation |

### General
| Parameter | Default | YAML key | Description |
|-----------|---------|----------|-------------|
| `epsilon` | `_EPS` (1e-10) | `epsilon` | Small value for non-matching edges |
| `forward_steps` | 500 | `forward_steps` | Max steps per route construction |

### Meta-controller
| Parameter | Default | YAML key | Description |
|-----------|---------|----------|-------------|
| `adapt_interval` | 5 | `adapt_interval` | Iterations between meta-controller updates |
| `adapt_diversity_min` | 0.15 | `adapt_diversity_min` | Minimum diversity threshold for each subpopulation |
| `adapt_decay` | 0.9 | `adapt_decay` | Multiplicative decay factor for low-diversity influence |
| `adapt_recovery_gain` | 0.05 | `adapt_recovery_gain` | Additive recovery when diversity returns |

## 6. Internal data structures

### `IndividualKind` (Enum)
```
ANT = "ant", BEE = "bee", PARTICLE = "particle"
```

### `IndividualStatus` (Enum)
```
CONSTRUCTING, COMPLETE, FAILED
```

### `IndividualState` (dataclass)
```
kind: IndividualKind     # which subpopulation
route: list[EdgeId]      # current route
cost: float              # current route cost
p_best_route: list[EdgeId]  # personal best route (all individuals maintain this)
p_best_cost: float       # personal best cost
visited: set[NodeId]     # visited nodes
state: IndividualStatus  # CONSTRUCTING | COMPLETE | FAILED
+ reset_route() method
```

### `HybridInfluenceWeights` (dataclass)
```
alpha_a: float = 1.0   # ACO influence weight
alpha_b: float = 1.0   # BCO influence weight
alpha_p: float = 1.0   # PSO influence weight
alpha_h: float = 1.0   # Heuristic influence weight
```

### `HybridConfiguration` (frozen dataclass)
All hyperparameters from section 5, with comprehensive validation in `__post_init__`.

### `HybridStatistics` (frozen dataclass)
```
iteration, best_cost, avg_cost, diversity,
alpha_a, alpha_b, alpha_p, alpha_h,
template_count, runtime_s
```

### `HybridPheromoneMatrix`
```
_data: dict[EdgeId, float]   # sparse pheromone matrix
_tau0, _tau_min, _tau_max    # bounds
+ get(edge_id), set(edge_id, value), local_update(edge_id, rho_local), clone()
```

### Instance state of `E3HybridRouting`
```
_individuals: list[IndividualState]
_visibility: dict[EdgeId, float]
_swarm_rng: SwarmRandom | None
_config: HybridConfiguration
_context: SwarmContext | None
_graph: DirectedGraph | None
_cost_calculator: CompositeCostCalculator | None
_source: NodeId | None
_destination: NodeId | None
_global_best_cost: float
_global_best_route: list[EdgeId]
_templates: list[list[EdgeId]]        # BCO template memory
_influence_weights: HybridInfluenceWeights  # meta-controller weights
_low_diversity_counts: dict[str, int]  # "a", "b", "p" → consecutive low-diversity iterations
_iteration_stats: list[HybridStatistics]
_diversity_history: list[float]
_score_history: list[float]
_no_improvement_count: int
```

## 7. Step-by-step written algorithm

1. **Validate** context (graph, cost_calculator, source != destination).
2. **Build visibility cache** — `1/(cost+eps)` per edge (blocked → 0.0).
3. **Build pheromone matrix** — `HybridPheromoneMatrix` initialised to `tau0` for all edges.
4. **Initialize random streams** via `SwarmRandom` with `context.random_seed`.
5. **Initialize population:**
   - Assign subpopulations deterministically: `N_a = round(pop_size * ant_ratio)`, `N_b = round(pop_size * bee_ratio)`, `N_p = pop_size - N_a - N_b`.
   - Create `IndividualState` for each individual with its assigned `IndividualKind`.
   - Construct initial route for each individual using **pure visibility** (all influence weights = 0 except alpha_h = 1.0).
   - Set p_best = current route, p_best_cost = current cost.
6. **Initialize hybrid state:** g_best = INF, templates = [], influence_weights = (alpha_a, alpha_b, alpha_p, alpha_h), low_diversity_counts = {a:0, b:0, p:0}.
7. **Create TerminationChecker**, call `checker.start()`.
8. **Iteration loop** (for iteration in 0..max_iterations-1):
   a. Compute PSO inertia `w` via linear decay.
   b. **Forward pass:**
      - For each individual:
        1. Reset its route state.
        2. Get a named random stream based on its kind (`"e3hybrid.ant.selection"` / `".bee.selection"` / `".particle.selection"`).
        3. Construct route using hybrid weighted selection:
           - Compute `raw_A = tau(edge)^beta_a` for each candidate edge (pheromone).
           - Compute `raw_B = 1.0` if any template matches edge at step, else `epsilon` (template match).
           - Compute `raw_P = cognition * M_p + social * M_g` where M_p/m_g = 1 if edge matches p_best/g_best at step, else `epsilon` (PSO memory).
           - Compute `raw_H = visibility.get(edge_id, 0.0)` (heuristic).
           - Normalise each raw array independently to [0,1] (min-max scaling).
           - Total weight = `alpha_a * norm_A + alpha_b * norm_B + alpha_p * norm_P + alpha_h * norm_H`.
           - Roulette-wheel selection (Eq. 7).
        4. Evaluate cost.
        5. If individual is ANT: perform **local pheromone update** on traversed edges: `tau ← (1-ρ_local) * tau + ρ_local * tau0`.
   c. **Backward pass:**
      - Personal best update (Eq. 18): if complete and cost < p_best_cost, replace p_best.
      - Find iteration-best complete route (min cost across all subpopulations).
      - **Global pheromone update** (Eqs. 14-16): deposit `1/best_cost` on best route edges with evaporation: `tau ← (1-ρ) * tau + ρ * deposit`.
   d. Update global best if iteration-best improves on g_best.
   e. **Extract BCO templates** — top `template_count` complete routes by cost.
   f. Compute diversity (Jaccard-based, Eq. 21) on all constructed routes.
   g. Record HybridStatistics.
   h. **Meta-controller** (if `iteration > 0 AND iteration % adapt_interval == 0`):
      - Group routes by subpopulation.
      - Compute per-subpopulation diversity: `|unique_edges| / (count * avg_route_len)`.
      - Subpopulations below `adapt_diversity_min` threshold have influence weight decayed: `alpha_X *= adapt_decay` (clamped to min).
      - Recovered subpopulations receive `alpha_X += adapt_recovery_gain` (clamped to max).
      - Redistribute removed weight to non-decayed subpopulations (or to alpha_h if all decayed).
      - Normalise sum of (alpha_a + alpha_b + alpha_p) to reference sum.
   i. Track no-improvement count.
   j. Build SearchState, call checker.check() — if should_stop, return SwarmResult.
9. Return SwarmResult with best solution.

## 8. Clear implementation-level pseudocode

```
FUNCTION E3HybridRouting.optimize(context):
    ctx_errors = _validate_context(context)
    IF ctx_errors: return _failure_result(errors)

    self._graph, self._cost_calculator = context.graph, context.cost_calculator
    self._source, self._destination = context.routing_request.{source,destination}
    swarm_config = context.config

    self._config = HybridConfiguration.from_swarm_config(swarm_config)
    IF graph/source/destination missing: return failure
    IF nodes not in graph: return failure

    // Build visibility cache
    CALL _build_visibility()

    // Build pheromone matrix: all edges initialised to tau0
    all_edge_ids = {e.edge_id for e in graph.edges()}
    pheromones = HybridPheromoneMatrix(tau0, tau_min, tau_max, all_edge_ids)

    // Random streams
    self._swarm_rng = SwarmRandom(context.random_seed)

    // Initialize population
    CALL _initialize_population()

    // Initialize tracking state
    self._global_best_cost = INF
    self._global_best_route = []
    self._templates = []
    self._influence_weights = HybridInfluenceWeights(alpha_a, alpha_b, alpha_p, alpha_h)
    self._low_diversity_counts = {"a": 0, "b": 0, "p": 0}
    self._iteration_stats = []
    self._diversity_history = []
    self._score_history = []

    // Termination checker
    checker = TerminationChecker(swarm_config)
    checker.start()

    prev_best_score = INF
    start_time = time.perf_counter()

    FOR iteration in 0..swarm_config.max_iterations-1:
        iter_start = time.perf_counter()

        // PSO inertia linear decay
        w = _compute_inertia(iteration, swarm_config.max_iterations)

        // --- Forward Pass ---
        (routes, costs, kinds, states) = _forward_pass(iteration, pheromones, w)

        // --- Backward Pass ---
        (best_cost, best_route) = _backward_pass(routes, costs, kinds, states, pheromones)

        // Update global best
        IF best_cost < self._global_best_cost:
            self._global_best_cost = best_cost
            self._global_best_route = copy(best_route) IF best_route ELSE []

        // Extract BCO templates: top template_count complete routes by cost
        self._templates = _extract_templates(routes, costs)

        // Compute diversity (Jaccard)
        diversity = _compute_diversity(routes)

        // Record HybridStatistics
        success_costs = [c for c,s in zip(costs,states) IF s==COMPLETE AND c<INF]
        avg_cost = mean(success_costs) IF success_costs ELSE INF
        self._iteration_stats.append(HybridStatistics(
            iteration, best_cost, avg_cost, diversity,
            self._influence_weights.alpha_a, self._influence_weights.alpha_b,
            self._influence_weights.alpha_p, self._influence_weights.alpha_h,
            len(self._templates), runtime
        ))
        self._diversity_history.append(diversity)
        self._score_history.append(best_cost)

        // Meta-controller
        _update_meta_controller(iteration, routes, kinds)

        // Update no-improvement
        IF global_best is INF:
            no_improvement_count = 0
        ELIF global_best >= prev_best_score:
            no_improvement_count = (self._no_improvement_count + 1)
        ELSE:
            no_improvement_count = 0
        self._no_improvement_count = no_improvement_count
        prev_best_score = self._global_best_cost

        // Check termination
        search_state = SearchState(iteration+1, self._global_best_cost, prev_best_score,
                                   no_improvement_count, diversity, elapsed)
        term = checker.check(search_state)
        IF term.should_stop:
            RETURN _build_swarm_result(total_time, term.reason, term.iteration)

    RETURN _build_swarm_result(total_time, "Max iterations", swarm_config.max_iterations)
END FUNCTION

// ---------------------------------------------------------------------------

FUNCTION _assign_subpopulations(population_size):
    N_a = max(1, int(pop_size * ant_ratio / total_ratio))
    N_b = max(1, int(pop_size * bee_ratio / total_ratio))
    N_p = pop_size - N_a - N_b
    kinds = [ANT]*N_a + [BEE]*N_b + [PARTICLE]*N_p
    RETURN kinds
END FUNCTION

FUNCTION _initialize_population():
    kinds = _assign_subpopulations(config.population_size)
    self._individuals = [IndividualState(kind=k) for k in kinds]

    init_stream = _swarm_rng.get_stream("e3hybrid.init")
    FOR each individual:
        // Pure visibility construction (all weights 0 except alpha_h=1.0)
        route = _construct_route(
            source, destination,
            current_route=[], p_best_route=[], templates=[],
            g_best=[], pheromones=None,
            alpha_a=0.0, alpha_b=0.0, alpha_p=0.0, alpha_h=1.0,
            stream=init_stream
        )
        cost = sum(_edge_total_cost(eid) for eid in route) IF route ELSE INF
        reached = route AND graph.get_edge(route[-1]).target == destination
        ind.route = route
        ind.cost = cost
        ind.p_best_route = copy(route)
        ind.p_best_cost = cost
        ind.state = COMPLETE IF reached ELSE FAILED
END FUNCTION

FUNCTION _build_visibility():
    self._visibility = {}
    FOR each edge in graph.edges():
        IF edge.state.is_blocked:
            self._visibility[edge.edge_id] = 0.0
        ELSE:
            edge_cost = compute_edge_cost(edge)  # may raise
            IF not finite(edge_cost) OR edge_cost < 0:
                self._visibility[edge.edge_id] = 0.0
            ELIF edge_cost == 0.0:
                self._visibility[edge.edge_id] = 1.0 / _EPS
            ELSE:
                self._visibility[edge.edge_id] = 1.0 / (edge_cost + _EPS)
END FUNCTION

FUNCTION _edge_total_cost(edge):
    IF edge.state.is_blocked: return INF
    cost_val = compute_edge_cost(edge)  # may raise
    return cost_val IF finite(cost_val) AND cost_val >= 0 ELSE INF
END FUNCTION

FUNCTION _compute_inertia(iteration, max_iters):
    IF max_iters <= 0: return config.inertia_end
    return config.inertia_start - (config.inertia_start - config.inertia_end) 
           * iteration / max_iters
END FUNCTION

// ---------------------------------------------------------------------------
// Route Construction — Hybrid Weighted Selection
// ---------------------------------------------------------------------------

FUNCTION _construct_route(source, destination, current_route, p_best_route,
                           templates, g_best, pheromones,
                           alpha_a, alpha_b, alpha_p, alpha_h, stream):
    current = source
    prev = None
    route = []

    FOR step in 0..forward_steps-1:
        IF current == destination: BREAK

        // Gather candidates (Eq. 1)
        candidates = [e for e in graph.outgoing_edges(current) 
                      IF _edge_total_cost(e) < INF]
        IF len(candidates) > 1 AND prev is not None:
            candidates = [e for e in candidates IF e.target != prev]
        IF empty(candidates): BREAK
        // Prefer non-dead-end targets
        IF len(candidates) > 1:
            non_deadend = [e for e in candidates 
                          IF e.target == destination 
                          OR len(outgoing_edges(e.target)) > 0]
            IF non_deadend: candidates = non_deadend

        // Compute raw influence values
        raw_A = [_compute_raw_aco(e.edge_id, pheromones) for e in candidates]
        raw_B = [_compute_raw_bco(e.edge_id, step, templates) for e in candidates]
        raw_P = [_compute_raw_pso(e.edge_id, step, p_best_route, g_best) for e in candidates]
        raw_H = [_compute_raw_visibility(e.edge_id) for e in candidates]

        // Normalise to [0,1] (Eqs. 8-11)
        norm_A = _normalise_to_unit(raw_A)
        norm_B = _normalise_to_unit(raw_B)
        norm_P = _normalise_to_unit(raw_P)
        norm_H = _normalise_to_unit(raw_H)

        // Total weights (Eq. 2)
        weights = []
        FOR j = 0..len(candidates)-1:
            w = (alpha_a * norm_A[j] + alpha_b * norm_B[j] 
                 + alpha_p * norm_P[j] + alpha_h * norm_H[j])
            weights.append(max(w, 0.0))

        // Roulette selection (Eq. 7)
        total = sum(weights)
        IF total <= 0.0:
            chosen = stream.choice(candidates)
        ELSE:
            r = stream.random() * total
            cum = 0.0
            chosen = candidates[-1]
            FOR j, e in enumerate(candidates):
                cum += weights[j]
                IF r <= cum: chosen = e; BREAK

        route.append(chosen.edge_id)
        prev = current
        current = chosen.target

    RETURN route
END FUNCTION

FUNCTION _compute_raw_aco(edge_id, pheromones):
    IF pheromones is None: RETURN 1.0
    tau = pheromones.get(edge_id)
    RETURN tau ** config.beta_a
END FUNCTION

FUNCTION _compute_raw_bco(edge_id, step, templates):
    IF empty(templates): RETURN config.epsilon
    FOR each template in templates:
        IF step < len(template) AND edge_id == template[step]:
            RETURN 1.0
    RETURN config.epsilon
END FUNCTION

FUNCTION _compute_raw_pso(edge_id, step, p_best_route, g_best):
    M_p = 1.0 IF step < len(p_best_route) AND edge_id == p_best_route[step] ELSE epsilon
    M_g = 1.0 IF step < len(g_best) AND edge_id == g_best[step] ELSE epsilon
    RETURN cognition_weight * M_p + social_weight * M_g
END FUNCTION

FUNCTION _compute_raw_visibility(edge_id):
    RETURN self._visibility.get(edge_id, 0.0)
END FUNCTION

FUNCTION _normalise_to_unit(raw_values):
    IF empty(raw_values): RETURN []
    min_v = min(raw_values)
    max_v = max(raw_values)
    IF max_v - min_v < _EPS: RETURN [1.0] * len(raw_values)
    RETURN [(v - min_v) / (max_v - min_v) for v in raw_values]
END FUNCTION

// ---------------------------------------------------------------------------
// Forward Pass
// ---------------------------------------------------------------------------

FUNCTION _forward_pass(iteration, pheromones, inertia):
    P = len(self._individuals)
    routes = []
    costs = []
    kinds = []
    states = []

    FOR i = 0..P-1:
        ind = self._individuals[i]
        ind.reset_route()
        kinds.append(ind.kind)

        // Select named stream by individual kind
        stream = _swarm_rng.get_stream(
            "e3hybrid.ant.selection" IF ind.kind==ANT
            ELSE "e3hybrid.bee.selection" IF ind.kind==BEE
            ELSE "e3hybrid.particle.selection"
        )

        // Use current influence weights
        alpha_a_eff = self._influence_weights.alpha_a
        alpha_b_eff = self._influence_weights.alpha_b
        alpha_p_eff = self._influence_weights.alpha_p
        alpha_h_eff = self._influence_weights.alpha_h

        // Construct route
        new_route = _construct_route(
            source, destination,
            current_route=ind.route, p_best_route=ind.p_best_route,
            templates=self._templates, g_best=self._global_best_route,
            pheromones=pheromones,
            alpha_a=alpha_a_eff, alpha_b=alpha_b_eff,
            alpha_p=alpha_p_eff, alpha_h=alpha_h_eff,
            stream=stream
        )

        new_cost = sum(_edge_total_cost(eid) for eid in new_route) IF new_route ELSE INF
        reached = bool(new_route) AND graph.get_edge(new_route[-1]).target == destination
        ind.route = new_route
        ind.cost = new_cost
        ind.state = COMPLETE IF reached ELSE FAILED

        // Local pheromone update for ants (Eq. 13)
        IF ind.kind == ANT:
            FOR each eid in new_route:
                pheromones.local_update(eid, config.rho_local)

        routes.append(new_route)
        costs.append(new_cost)
        states.append(ind.state)

    RETURN (routes, costs, kinds, states)
END FUNCTION

// ---------------------------------------------------------------------------
// Backward Pass
// ---------------------------------------------------------------------------

FUNCTION _backward_pass(routes, costs, kinds, states, pheromones):
    P = len(self._individuals)

    // Personal best update (Eq. 18) — all individuals
    FOR i = 0..P-1:
        IF states[i] == COMPLETE AND costs[i] < self._individuals[i].p_best_cost:
            self._individuals[i].p_best_route = copy(routes[i])
            self._individuals[i].p_best_cost = costs[i]

    // Find best complete route this iteration
    valid = [(costs[i], i) for i in range(P) IF states[i] == COMPLETE]
    IF valid:
        (best_cost, best_idx) = min(valid, key by cost)
        best_route = routes[best_idx]
    ELSE:
        best_cost = INF
        best_route = []

    // Global pheromone update (Eqs. 14-16)
    IF best_route AND best_cost < INF:
        deposit = 1.0 / best_cost
        FOR each eid in best_route:
            current = pheromones.get(eid)
            updated = (1.0 - config.rho) * current + config.rho * deposit
            pheromones.set(eid, updated)

    RETURN (best_cost, best_route)
END FUNCTION

// ---------------------------------------------------------------------------
// BCO Templates
// ---------------------------------------------------------------------------

FUNCTION _extract_templates(routes, costs):
    L = config.template_count
    IF L <= 0: RETURN []
    valid = [(r, c) for r, c in zip(routes, costs) IF r AND c < INF]
    IF empty(valid): RETURN []
    valid.sort(key by cost ascending)
    RETURN [copy(r) for (r, _) in valid[:L]]
END FUNCTION

// ---------------------------------------------------------------------------
// Diversity (Eq. 21)
// ---------------------------------------------------------------------------

FUNCTION _compute_diversity(routes):
    // Jaccard-based diversity
    IF len(routes) < 2: RETURN 0.0
    edge_sets = [set(r) for r in routes]
    total_pairs = 0
    similarity_sum = 0.0
    FOR i = 0..len(edge_sets)-1:
        FOR j = i+1..len(edge_sets)-1:
            total_pairs++
            union = edge_sets[i] | edge_sets[j]
            IF union:
                similarity_sum += len(edge_sets[i] & edge_sets[j]) / len(union)
    IF total_pairs == 0: RETURN 0.0
    avg_jaccard = similarity_sum / total_pairs
    RETURN 1.0 - avg_jaccard
END FUNCTION

// ---------------------------------------------------------------------------
// Meta-Controller
// ---------------------------------------------------------------------------

FUNCTION _update_meta_controller(iteration, routes, kinds):
    K = config.adapt_interval
    IF iteration == 0 OR iteration % K != 0: RETURN

    // Group edges by subpopulation
    edges_by_kind = {"a": empty_set, "b": empty_set, "p": empty_set}
    kind_to_key = {ANT: "a", BEE: "b", PARTICLE: "p"}
    counts = {"a": 0, "b": 0, "p": 0}

    FOR i, r in enumerate(routes):
        key = kind_to_key.get(kinds[i], "p")
        edges_by_kind[key] |= set(r)
        counts[key]++

    // Compute per-subpopulation diversity (Eq. 22)
    total_avg_len = mean([len(r) for r in routes]) IF routes ELSE 0
    diversities = {}
    FOR key in ("a", "b", "p"):
        n = max(counts[key], 1)
        max_possible = n * max(total_avg_len, 1.0)
        diversities[key] = len(edges_by_kind[key]) / max_possible IF max_possible > 0 ELSE 1.0

    // Identify low-diversity subpopulations
    decayed_keys = []
    FOR key, div in diversities.items():
        IF div < config.adapt_diversity_min:
            self._low_diversity_counts[key]++
            IF self._low_diversity_counts[key] >= 1:
                decayed_keys.append(key)
        ELSE:
            // Recovery (Eq. 24)
            IF self._low_diversity_counts[key] > 0:
                self._low_diversity_counts[key] = 0
                current = self._influence_weights.alpha_{key}
                max_attr = config.alpha_{key}_max
                new_val = min(max_attr, current + config.adapt_recovery_gain)
                self._influence_weights.alpha_{key} = new_val

    // Apply decay (Eq. 23)
    total_removed = 0.0
    FOR key in decayed_keys:
        current = self._influence_weights.alpha_{key}
        min_attr = config.alpha_{key}_min
        new_val = max(min_attr, current * config.adapt_decay)
        removed = current - new_val
        self._influence_weights.alpha_{key} = new_val
        total_removed += removed

    // Redistribute to non-decayed components
    non_decayed = [k for k in ("a","b","p") IF k not in decayed_keys]
    IF non_decayed AND total_removed > 0:
        per_gain = total_removed / len(non_decayed)
        FOR key in non_decayed:
            current = self._influence_weights.alpha_{key}
            max_attr = config.alpha_{key}_max
            new_val = min(max_attr, current + per_gain)
            self._influence_weights.alpha_{key} = new_val
    ELIF not non_decayed AND total_removed > 0:
        self._influence_weights.alpha_h += total_removed

    // Normalise (Eq. 25)
    _normalise_influence_weights()
END FUNCTION

FUNCTION _normalise_influence_weights():
    S_ref = config.alpha_a + config.alpha_b + config.alpha_p
    a = self._influence_weights.alpha_a
    b = self._influence_weights.alpha_b
    p = self._influence_weights.alpha_p
    S = a + b + p
    IF S > 0 AND abs(S - S_ref) > _EPS:
        factor = S_ref / S
        self._influence_weights.alpha_a = clamp(a * factor, alpha_a_min, alpha_a_max)
        self._influence_weights.alpha_b = clamp(b * factor, alpha_b_min, alpha_b_max)
        self._influence_weights.alpha_p = clamp(p * factor, alpha_p_min, alpha_p_max)
END FUNCTION
```

## 9. Time complexity

Let:
- `P` = population_size
- `I` = max_iterations
- `F` = forward_steps
- `D` = average out-degree

**Per iteration:**
- **Forward pass:** `P * F * D` — each individual constructs a route of up to F steps, evaluating D outgoing edges with 4 raw computations and normalisation each.
- **Backward pass:** `P` — personal best comparisons + `O(P * L)` for finding best route + `O(L_opt)` for global pheromone update.
- **Template extraction:** `O(P * log P)` for sorting up to P routes.
- **Diversity:** `O(P² * L)` — pairwise Jaccard on route edge sets.
- **Meta-controller (every K iterations):** `O(P * L)` — grouping routes by kind.

**Overall:** **O(I * P * F * D)** — dominated by forward-pass edge evaluations. Diversity adds `O(I * P² * L)` which can be significant for large populations.

## 10. Space complexity

- **Individual states:** `O(P * F)` — P individuals, each storing routes of up to F edges.
- **Visibility cache:** `O(E)` — E = total graph edges.
- **Pheromone matrix:** `O(E)` — one float per edge.
- **Templates:** `O(K * F)` — K = template_count, each of up to F edges.
- **Iteration stats:** `O(I)` — per-iteration statistics.
- **Influence weights:** `O(1)` — 4 floats + 3 counters.

**Overall:** **O(P*F + E + I)**.

## 11. Strengths

- **Multi-paradigm integration** — three complementary memory structures (pheromone trails, route templates, cognitive/social memory) provide diverse search signals.
- **Normalised influence** — min-max scaling to [0,1] ensures fair competition between all four components regardless of their raw magnitude.
- **Adaptive meta-controller** — automatically reduces influence of subpopulations that converge too quickly (low diversity), redistributing weight to more diverse components. This actively manages the exploration–exploitation balance.
- **Per-subpopulation diversity tracking** — the meta-controller uses separate diversity estimates for ants, bees, and particles (Eq. 22), enabling targeted intervention.
- **Global pheromone reinforcement** — the iteration-best route (across all subpopulations) receives pheromone deposit, enabling cross-pollination: good routes found by bees or particles influence the pheromone landscape for ants.
- **Template memory (BCO)** — retains top routes as templates, providing an explicit "good route pattern" that influences all individuals regardless of subpopulation.
- **Dead-end avoidance and backtrack prevention** — same robust construction as PSO.
- **No single point of failure** — if one subpopulation stagnates, the others can compensate.
- **Deterministic and reproducible** — SwarmRandom named streams per subpopulation.
- **Rich statistics** — per-iteration diversity, influence weights, template count, and per-subpopulation counts are all recorded.

## 12. Weaknesses

- **Binary memory signals (ACO/PSO components)** — `raw_ACO = tau^beta` is a scalar but only reflects pheromone level, not structural similarity. `raw_BCO` is binary (1.0 if exact template match, else epsilon). `raw_PSO` is binary at each step (matching edge at exact step index). No partial credit for edges that appear in good routes at different positions.
- **Synchronous per-subpopulation diversity** — the meta-controller's per-subpopulation diversity (Eq. 22) uses `|unique_edges| / (count * avg_len)`. This is a coarse heuristic: a subpopulation with many identical routes and one outlier has the same diversity as one with evenly distributed routes.
- **Meta-controller normalisation (Eq. 25)** — only normalises `alpha_a + alpha_b + alpha_p` to the reference sum `S_ref`, keeping `alpha_h` separate. This means `alpha_h` can grow unbounded if all three subpopulations are repeatedly decayed and the redistribution falls to `alpha_h`.
- **No local route improvement** — like PSO, no 2-opt, shortcut removal, or path smoothing is performed after construction.
- **Pheromone deposit is based on `1/best_cost`** — this is the standard ACO approach but can be numerically unstable for very low or very high costs. The `PENALTY_COST = 1e9` is used for infeasible routes, which makes `1/PENALTY_COST` a negligible deposit, effectively not reinforcing bad routes.
- **Template stale retention** — templates are extracted from every iteration's routes but are overwritten each iteration. There is no mechanism to retain a good template across multiple iterations if it is not rediscovered.
- **All subpopulations use the same construction function** — ants, bees, and particles differ only in their named random stream and whether they perform local pheromone update. The actual decision-making logic is identical (`_construct_route` is shared). This means the "bee" and "particle" behaviors are differentiated only by the meta-controller signals and memory they access, not by fundamentally different construction strategies.
- **Initialisation does not seed pheromone** — initial routes are built with pure visibility, but pheromone is initialised uniformly to `tau0`. No pre-processing or heuristic seeding is applied.
- **`IterationStatistics.worst_score` is incorrectly set** — in `_build_iteration_stats()`, `worst_score` is set to `s.best_cost` (the best, not worst cost). This appears to be a bug in the implementation at `hybrid.py:1122`.

## 13. Why it was selected

- **Primary contribution** — E³-Hybrid is the central novel algorithm proposed in this thesis, designed specifically to investigate whether integrating ACO, BCO, and PSO memory structures yields better results than any single paradigm.
- **Cross-pollination hypothesis** — the design tests whether routes discovered by one subpopulation (e.g., a bee's template match) can influence the search of others (e.g., via pheromone update or global best sharing).
- **Adaptive control** — the meta-controller tests whether automated diversity management improves robustness in dynamic routing environments.
- **Completeness of comparison** — the benchmark suite compares all component algorithms (ACO, BCO, PSO) against the hybrid, enabling rigorous ablation analysis.

## 14. How it interacts with the SUMO simulation

Identical pattern to PSO — interaction is mediated by `SwarmToRoutingAdapter`:

1. SUMO provides the current graph with `MutableEdgeState` (blocked edges, congestion, speed, hazards, emergencies) via `Edge.state`.
2. `SwarmToRoutingAdapter.compute_route()` builds `SwarmContext` and calls `E3HybridRouting.optimize()`.
3. The hybrid builds a **visibility snapshot** and **pheromone matrix** from the current graph state.
4. The hybrid runs its iteration loop, constructing routes with the hybrid weighted selection formula.
5. The `SwarmResult` is adapted to `RoutingResult` with a `Route` containing standard SUMO-compatible fields.
6. The `RoutingResult` is consumed by the `BenchmarkRunner` and `DecisionEngine`, which selects the route for the SUMO vehicle.

Like PSO, E³-Hybrid operates on a **static snapshot** per optimization call — it does not receive incremental graph updates during a run.

## 15. How it responds to congestion, road closures, and emergency events

The hybrid responds at multiple levels:

- **`edge.state.is_blocked`:**
  - `_build_visibility()` sets `visibility = 0.0` for blocked edges.
  - `_edge_total_cost()` returns `INF` for blocked edges.
  - Blocked edges are excluded from the candidate set during construction (line 662-664).
  - This is the **hardest** response — blocked edges are simply untraversable.

- **`edge.state.congestion_factor`:**
  - `CompositeCostCalculator.compute_edge_cost()` multiplies base travel time by `congestion_factor` (line 139 of cost_calculator.py).
  - This increases total edge cost, which reduces heuristic visibility (`1/cost`).
  - Congested edges are less likely to be selected via `raw_H` (heuristic component).
  - The cost also influences global best selection — a route through congested areas has higher total cost and is less likely to become g_best or receive pheromone deposit.

- **`edge.state.hazard_penalty_s` and `emergency_penalty_s`:**
  - Added as additive time penalties in `CompositeCostCalculator.compute_edge_cost()` (lines 148-149 of cost_calculator.py).
  - These increase total edge cost proportionally to their weight in `CostWeights`.
  - Higher edge cost → lower visibility → lower selection probability.

- **Pheromone response:** If a route through a formerly good edge becomes expensive due to congestion/hazards, the route's total cost increases, making it less likely to be the iteration-best. Less pheromone is deposited on that route, and existing pheromone evaporates. Over multiple iterations, the swarm shifts away from the degraded edge.

- **Template response:** High-cost routes are less likely to appear in the top `template_count` routes, so they disappear from the BCO template memory.

- **Meta-controller response:** If congestion causes route diversity to drop (all individuals converging to similar bypass routes), the meta-controller detects low diversity and decays the relevant influence weights, promoting exploration.

All responses are **indirect** through the cost function — there is no explicit congestion/emergency handling logic.

## 16. How randomness is controlled

All stochastic decisions use `SwarmRandom` with named streams per subpopulation:

| Stream name | Used in | Purpose |
|-------------|---------|---------|
| `"e3hybrid.init"` | `_initialize_population()` | Roulette selection during initial route construction |
| `"e3hybrid.ant.selection"` | `_forward_pass()` for ANT individuals | Roulette selection during ant route construction |
| `"e3hybrid.bee.selection"` | `_forward_pass()` for BEE individuals | Roulette selection during bee route construction |
| `"e3hybrid.particle.selection"` | `_forward_pass()` for PARTICLE individuals | Roulette selection during particle route construction |

Each stream is deterministically derived from the base seed:
```python
name_hash = hash(name) & 0x7FFFFFFF
stream_seed = (self._base_seed ^ name_hash) & 0x7FFFFFFF
```

## 17. Determinism and reproducibility notes

- **Same seed + same config → same results** — guaranteed by SwarmRandom named streams and pure-function design.
- The graph and cost calculator are never modified by the algorithm.
- Subpopulation assignment is deterministic (uses `int()` rounding with a fixed formula).
- Iteration order is sequential.
- `hash()` cross-version stability applies (same caveat as PSO).
- The meta-controller is deterministic given the same routes and kinds arrays.
- Pheromone updates are deterministic given the same iteration-best route.

## 18. Mapping between pseudocode and implementation methods/classes

| Pseudocode section | Implementation class/method | File:line |
|-------------------|---------------------------|-----------|
| `E3HybridRouting.optimize()` | `E3HybridRouting.optimize()` | `hybrid.py:385-539` |
| `_assign_subpopulations()` | `E3HybridRouting._assign_subpopulations()` | `hybrid.py:545-559` |
| `_initialize_population()` | `E3HybridRouting._initialize_population()` | `hybrid.py:561-596` |
| `_build_visibility()` | `E3HybridRouting._build_visibility()` | `hybrid.py:598-615` |
| `_edge_total_cost()` | `E3HybridRouting._edge_total_cost()` | `hybrid.py:617-624` |
| `_compute_inertia()` | `E3HybridRouting._compute_inertia()` | `hybrid.py:626-631` |
| `_construct_route()` | `E3HybridRouting._construct_route()` | `hybrid.py:637-721` |
| `_compute_raw_aco()` | `E3HybridRouting._compute_raw_aco()` | `hybrid.py:723-731` |
| `_compute_raw_bco()` | `E3HybridRouting._compute_raw_bco()` | `hybrid.py:733-744` |
| `_compute_raw_pso()` | `E3HybridRouting._compute_raw_pso()` | `hybrid.py:746-755` |
| `_compute_raw_visibility()` | `E3HybridRouting._compute_raw_visibility()` | `hybrid.py:757-758` |
| `_normalise_to_unit()` | `E3HybridRouting._normalise_to_unit()` | `hybrid.py:760-768` |
| `_forward_pass()` | `E3HybridRouting._forward_pass()` | `hybrid.py:774-838` |
| `_backward_pass()` | `E3HybridRouting._backward_pass()` | `hybrid.py:844-877` |
| `_extract_templates()` | `E3HybridRouting._extract_templates()` | `hybrid.py:879-895` |
| `_compute_diversity()` | `E3HybridRouting._compute_diversity()` | `hybrid.py:897-917` |
| `_update_meta_controller()` | `E3HybridRouting._update_meta_controller()` | `hybrid.py:923-997` |
| `_normalise_influence_weights()` | `E3HybridRouting._normalise_influence_weights()` | `hybrid.py:999-1013` |
| `_build_swarm_result()` | `E3HybridRouting._build_swarm_result()` | `hybrid.py:1019-1059` |
| `_route_to_candidate()` | `E3HybridRouting._route_to_candidate()` | `hybrid.py:1061-1110` |
| `_build_iteration_stats()` | `E3HybridRouting._build_iteration_stats()` | `hybrid.py:1112-1128` |
| `_find_convergence_iteration()` | `E3HybridRouting._find_convergence_iteration()` | `hybrid.py:1130-1134` |
| `_failure_result()` | `E3HybridRouting._failure_result()` | `hybrid.py:1136-1138` |
| Module-level `_validate_context()` | `_validate_context()` | `hybrid.py:1145-1153` |
| Module-level `_failure_result()` | `_failure_result()` | `hybrid.py:1156-1169` |
| `IndividualState` | `IndividualState` (dataclass) | `hybrid.py:81-97` |
| `IndividualKind` | `IndividualKind` (Enum) | `hybrid.py:57-61` |
| `IndividualStatus` | `IndividualStatus` (Enum) | `hybrid.py:69-73` |
| `HybridConfiguration` | `HybridConfiguration` (dataclass) | `hybrid.py:132-286` |
| `HybridInfluenceWeights` | `HybridInfluenceWeights` (dataclass) | `hybrid.py:105-124` |
| `HybridStatistics` | `HybridStatistics` (dataclass) | `hybrid.py:318-337` |
| `HybridPheromoneMatrix` | `HybridPheromoneMatrix` | `pheromone.py:18-82` |
| SwarmResult building | `SwarmResult` (dataclass) | `result.py:13-47` |
| Adaptation to RoutingResult | `SwarmToRoutingAdapter.compute_route()` | `adapter.py:56-159` |
| Deterministic RNG | `SwarmRandom` | `random.py:12-65` |
| Termination checking | `TerminationChecker` | `termination.py:46-148` |
| SwarmAlgorithm registration | `SwarmFactory.register("e3hybrid", E3HybridRouting)` | `hybrid.py:1174` |

---

## E3-Hybrid Review: Verification Findings

### Pheromone learning — meaningful and integrated
**YES.** The `HybridPheromoneMatrix` is integral to the algorithm:
- Local pheromone update (Eq. 13) occurs for ANT individuals after each forward pass, evaporating toward `tau0` at rate `rho_local`. This diversifies ant paths.
- Global pheromone update (Eqs. 14-16) deposits `1/best_cost` on the iteration-best route (across **all** subpopulations, not just ants) at rate `rho`. This cross-pollinates: a route found by a bee or particle gets pheromone reinforcement, influencing future ant construction.
- `raw_ACO = tau^beta_a` feeds directly into the weighted selection formula, so pheromone directly influences edge selection probability.

### Bee-inspired exploration (templates) — contributes to route discovery
**YES.** BCO templates are the top `template_count` complete routes from each iteration:
- `raw_BCO = 1.0` if any template matches at step, else `epsilon`. This provides an explicit "follow a proven path pattern" signal.
- Templates are extracted from **all** individuals, not just bees — cross-pollination means ant-found routes also become templates.
- `alpha_b` weight is meta-controlled, so template influence is dynamically adjusted.
- **Limitation:** Template matching is exact step-position matching — an edge at a different position in the route gets no partial credit.

### PSO memory (p_best, g_best) — contributes to convergence
**YES.** Every individual (ant, bee, particle) maintains `p_best_route` and `p_best_cost`:
- `raw_PSO = cognition_weight * M_p + social_weight * M_g` — both personal and global best memories are always available.
- p_best is updated for all individuals in the backward pass (Eq. 18, line 854-858).
- g_best is the global best across all subpopulations, updated each iteration.
- The PSO inertia weight (linear decay) is reused from the PSO algorithm.

### Adaptive weighting (meta-controller) — mathematically justified
**PARTIALLY.** The meta-controller has a reasonable heuristic basis:
- **Premise:** When a subpopulation has low diversity, its influence should be reduced to prevent premature convergence (Eq. 23: `alpha *= adapt_decay`).
- **Premise:** When diversity recovers, influence should be restored (Eq. 24: `alpha += recover_gain`).
- **Redistribution:** Removed weight is redistributed to non-decayed subpopulations or to `alpha_h` (heuristic), which is mathematically sound — heuristic is always a "safe" unbiased signal.
- **Normalisation (Eq. 25):** Scales (a+b+p) back to reference sum `S_ref`, preserving the total influence budget. However, `alpha_h` is excluded from normalisation, meaning it can grow unbounded if all three subpopulations are repeatedly decayed.
- **Weakness:** Per-subpopulation diversity (Eq. 22) uses a coarse formula: `|unique_edges| / (count * avg_route_len)`. This is a reasonable proxy but does not capture structural diversity (e.g., two routes sharing 80% of edges but differing in the critical bottleneck).

### Diversity preservation — is effective
**YES, with caveats.** The combination of three independent subpopulations naturally preserves diversity. The meta-controller further promotes diversity by penalising low-diversity subpopulations. However:
- The three subpopulations use the **same construction function** (`_construct_route`), differing only in random stream and local pheromone update. This limits behavioral diversity.
- The Jaccard-based diversity metric (Eq. 21) captures edge-set diversity well but is computationally expensive: `O(P² * L)`.

### Premature convergence — is mitigated
**YES.** Three mechanisms work together:
1. **Multiple memory structures** mean if one component converges (e.g., pheromone), template or PSO memory may still explore.
2. **Meta-controller decay** actively reduces influence of converged components.
3. **Heuristic baseline** (`alpha_h`) always provides unbiased edge cost information.
4. **Per-subpopulation random streams** ensure different noise patterns for each subpopulation.

### Exploration and exploitation — remain balanced
**YES, dynamically.** The balance is controlled by:
- **Inertia weight** linearly decreasing from 0.9 to 0.4 (exploration → exploitation for PSO component).
- **Meta-controller** adjusting alpha weights based on diversity (explorative subpopulations gain influence).
- **Pheromone evaporation** (rho) continuously reducing stale trail strength.
- **Template turnover** — templates are refreshed every iteration from the current population.
- **Normalisation** ensures all components remain in competitive balance.

### Emergency-aware routing — integrates naturally
**YES, indirectly.** Emergency penalties (`edge.state.emergency_penalty_s`) are included in the cost calculation via `CompositeCostCalculator`. This increases edge cost → decreases visibility → reduces selection probability. The algorithm does not have explicit emergency handling logic, but the cost-weighted selection naturally avoids high-penalty edges.

### Congestion handling — integrated into route evaluation
**YES.** `congestion_factor` is integrated at the cost calculator level (cost_calculator.py:139). The congestion penalty is a multiplicative factor on base travel time, which feeds into total edge cost. All four raw components (ACO, BCO, PSO, visibility) respond to cost changes indirectly through visibility and total route cost.

### Graph updates — handled dynamically
**PARTIALLY.** Each call to `optimize()` builds a fresh visibility cache and pheromone matrix from the current graph state. This means graph changes are captured between optimization runs. However, **within a single `optimize()` call**, the graph is treated as static — edge states are read once during visibility construction and are not re-evaluated mid-optimization.

### Component necessity — every component influences routing
**YES.** All components are active:
- **ACO (alpha_a * norm_A):** Pheromone trails guide edge selection.
- **BCO (alpha_b * norm_B):** Template matching encourages following known good patterns.
- **PSO (alpha_p * norm_P):** Personal and global best memory drives convergence.
- **Heuristic (alpha_h * norm_H):** Unbiased edge cost information.
- **Meta-controller:** Dynamically adjusts weights; if it were removed, the static weights would not adapt.
- **Local pheromone update (ants only):** Prevents premature convergence on ant subpopulation.
- **Global pheromone update:** Cross-pollinates good routes across subpopulations.
- **Templates:** Provide explicit memory of top routes.
- **Personal best memory:** All individuals maintain and update p_best.

No component exists only for appearance.

### Documented bugs found

1. **`hybrid.py:1122`** — `_build_iteration_stats()` sets `worst_score=s.best_cost` instead of the actual worst cost across individuals. This is a bug: `worst_score` should use `max()` of costs or `s.worst_cost`, not the iteration's best cost. This affects statistics logging but not routing decisions.

2. **`pso.py:487-488`** — A no-op expression `if new_route and new_route[-1] == ...: pass` appears to be leftover debug code. It has no runtime effect but is dead code.

3. **Dead-end filtering consistency:** Both PSO and hybrid use `len(list(self._graph.outgoing_edges(e.target))) > 0` to check dead ends. This calls `outgoing_edges()` which returns a generator — the generator is consumed into a list every time, which is inefficient but functionally correct.
