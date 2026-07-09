# Ant Colony System (ACS) — Algorithm Documentation

> **File:** `src/e3hybrid/swarm/aco.py`  
> **Literature:** Dorigo & Gambardella (1997); Stützle & Hoos (2000)  
> **Protocol:** `e3hybrid.swarm.protocol.SwarmAlgorithm`

---

## 1. Purpose in this thesis

The ACO module provides an **Ant Colony System (ACS)** route planner for
emergency electric vehicles (e-vehicles) operating in dynamic, disaster-affected
road networks.  It serves as one of several swarm-intelligence baselines
(alongside BCO and PSO) within the E³-Hybrid framework.  The algorithm explores
the Pareto front of route cost vs. adaptability by maintaining an evolving
pheromone trail that encodes historical solution quality across the ant
population.

---

## 2. Theory actually implemented

The implementation follows **Ant Colony System (ACS)** as defined by Dorigo &
Gambardella (1997), with the following specific design choices:

| ACS Feature | Implementation |
|---|---|
| Pseudorandom proportional rule (Eq. 1 in Dorigo & Gambardella 1997) | `TransitionRule.select()` with probability `q0` for exploitation (argmax) and `1-q0` for roulette-wheel exploration |
| Local pheromone update (Eq. 2) | `PheromoneUpdater.local_update()` → `PheromoneMatrix.decay()` — `tau_ij ← (1-ρ)·tau_ij + ρ·tau0` applied after every ant step |
| Global pheromone update (Eq. 3) | `PheromoneUpdater.global_update()` → `PheromoneMatrix.reinforce()` — `tau_ij ← (1-ρ)·tau_ij + ρ·(1/L⁺)` on best-so-far edges only |
| Candidate list | Optional truncation of neighbour cache to top-K by visibility; `candidate_list_size=0` disables it |
| Heuristic visibility (eta_ij) | `VisibilityMatrix.__init__()` — `eta_ij = 1 / (edge_cost + EPS)`, blocked edges → `eta_ij = 0` |
| Elitist reinforcement | `PheromoneUpdater.global_update_elite()` — top-N ants deposit with `ρ/2` factor |

**MAX-MIN Ant System bounds** from Stützle & Hoos (2000) are enforced by
`PheromoneMatrix.set()`:
- All pheromone values are clamped to `[tau_min, tau_max]` after **every**
  mutation (decay, reinforce, direct set).
- Initial pheromone = `tau0` for all edges.
- NaN/Inf values are replaced by the nearest bound.
- `tau_min` and `tau_max` are strictly positive, validated at construction time
  by `ACSConfiguration.__post_init__()`.

**Not implemented** (to stay close to pure ACS):
- No ant colony system with look-ahead (no 2-opt local search).
- No adaptive parameter control.
- No multiple colonies.
- No dynamic pheromone evaporation tuning.

---

## 3. Inputs — `SwarmContext`

The single entry point is `ACORouting.optimize(context: SwarmContext)` at
`aco.py:690`.  `SwarmContext` (`context.py:15`) provides:

| Field | Type | Source |
|---|---|---|
| `routing_request` | `RoutingRequest` | Contains `source_node`, `destination_node`, `vehicle_id`, `max_candidates`, `timeout_s` |
| `graph` | `DirectedGraph \| None` | Full road network — nodes, edges, and mutable `edge.state` |
| `cost_calculator` | `CompositeCostCalculator \| None` | Weighted edge-cost computation via `compute_edge_cost(edge)` |
| `config` | `SwarmConfig` | Population size, max iterations, hyperparameters dict, seed |
| `random_seed` | `int` | Base seed for deterministic random streams |
| `cost_weights` | `CostWeights` | Weights for distance/time/energy/congestion/hazard/emergency/communication |
| `sim_time_s` | `float` | Current simulation wall-clock time (not consumed by ACO itself) |

---

## 4. Outputs — `SwarmResult` → `RoutingResult`

`ACORouting.optimize()` returns a `SwarmResult` (`result.py:14`):

| Field | Content |
|---|---|
| `best_solution` | `RouteCandidate` containing the best-found node/edge sequence, `total_cost`, `algorithm="aco"`, and ACO hyperparameters as `metadata` |
| `candidates` | Tuple of `RouteCandidate` (currently 1 candidate) |
| `statistics` | `SwarmStatistics` — iterations, runtime, best/average/worst scores, convergence iteration, diversity/score history |
| `iterations` | Tuple of `IterationStatistics` — per-iteration metrics |
| `success` | `bool` — whether at least one feasible route was found |
| `failure_reason` | `str \| None` |

This is adapted to the framework-standard `RoutingResult` by
`SwarmToRoutingAdapter` (`adapter.py:24`), which:
1. Builds `SwarmContext` from the `RoutingRequest` context.
2. Calls `swarm_algorithm.optimize(context)`.
3. Converts `SwarmResult` → `RoutingResult`, extracting the primary `Route`,
   computing total distance/time/energy, and wrapping in `RoutingStatistics`.

---

## 5. Configuration parameters

All defaults come from `ACSConfiguration` (`aco.py:51`).  Values can be
overridden via `SwarmConfig.hyperparameters` YAML dict.

| Parameter | Default | ACS Literature | Clamped |
|---|---|---|---|
| `alpha` (τ exponent) | `1.0` | 1 | `≥ 0` |
| `beta` (η exponent) | `2.0` | 2–5 | `≥ 0` |
| `rho` (evaporation) | `0.1` | 0.1 | `(0, 1)` |
| `q0` (exploitation) | `0.9` | 0.9 | `[0, 1]` |
| `tau0` (init phero) | `1.0` | 1.0 | `> 0` |
| `tau_min` (lower bound) | `0.01` | MMAS | `(0, tau_max)` |
| `tau_max` (upper bound) | `10.0` | MMAS | `> tau_min` |
| `elitism` (elite count) | `1` | ACS | `≥ 0` |
| `candidate_list_size` | `0` (all neighbours) | — | `≥ 0`; 0 = disabled |

`alpha + beta` must be `> 0`.  `SwarmConfig` defaults: `population_size=10`,
`max_iterations=100`, `seed=42`.

---

## 6. Internal data structures

### 6.1 `PheromoneMatrix` (`aco.py:131`)

```
_data: dict[EdgeId, float]
```

- Sparse dictionary: one entry per graph edge, initialized to `tau0`.
- `get(edge_id)` → returns `tau_min` for unknown edges.
- `set(edge_id, value)` → clamps to `[tau_min, tau_max]`, replaces NaN/Inf with
  nearest bound.
- `decay(edge_id, rho, tau0)` → `τ ← (1-ρ)·τ + ρ·tau0`.
- `reinforce(edge_id, rho, deposit)` → `τ ← (1-ρ)·τ + ρ·deposit`.
- `clone()` → deep copy for checkpointing.

### 6.2 `VisibilityMatrix` (`aco.py:183`)

```
_data: dict[EdgeId, float]
_neighbour_cache: dict[NodeId, list[EdgeId]]
```

- Static — built once in `__init__`, never mutated during optimization.
- `eta_ij = 1.0 / (edge_cost + _EPS)`; `_EPS = 1e-10`.
- Blocked edges (`edge.state.is_blocked`) → `eta_ij = 0.0`.
- Invalid costs (`NaN`, `-∞`, `∞`, negative) → `eta_ij = 0.0`.
- Zero-cost edges → `eta_ij = 1.0 / _EPS` (max heuristic).
- `_neighbour_cache` pre-computes outgoing edge lists per node, optionally
  truncated to top-K by visibility when `candidate_list_size > 0` (sorted
  descending, kept slice).

### 6.3 `Ant` (`aco.py:343`)

```
@dataclass
Ant:
    current_node: NodeId
    visited_nodes: set[NodeId]
    prev_node: NodeId | None
    node_sequence: list[NodeId]
    edge_sequence: list[EdgeId]
    total_cost: float
    is_complete: bool
    is_feasible: bool
    reached_dead_end: bool
```

- `reset(start_node)` reinitialises all fields for a new iteration.
- `create(start_node)` class-method constructor.
- Ants are pooled: `AntColony.initialize_population()` either creates new ants
  or reuses existing ones via `reset()`.

### 6.4 `TransitionRule` (`aco.py:251`)

```
config: alpha, beta, q0

select(candidates, pheromones, visibility, selection_stream, roulette_stream):
    if random() <= q0:
        return argmax(tau^alpha * eta^beta)
    else:
        return roulette(weighted by tau^alpha * eta^beta)
```

- Empty candidate list → returns `None` (ant stops with `reached_dead_end`).
- All-zero weights → uniform random fallback.
- Tabu (visited-nodes avoidance) is enforced by the caller
  (`AntColony.construct_routes()`).

### 6.5 `PheromoneUpdater` (`aco.py:382`)

```
config: rho, tau0, elitism

local_update(pheromones, edge_id):
    pheromones.decay(edge_id, rho, tau0)

global_update(pheromones, best_edges, best_cost):
    if best_cost > 0:
        deposit = 1.0 / best_cost
        for eid in best_edges:
            pheromones.reinforce(eid, rho, deposit)

global_update_elite(pheromones, elite_edges, elite_costs):
    for edges, cost in zip(...):
        deposit = 1.0 / cost
        for eid in edges:
            pheromones.reinforce(eid, rho * 0.5, deposit)
```

### 6.6 `AntColony` (`aco.py:488`)

```
config: ACSConfiguration
_transition: TransitionRule
_updater: PheromoneUpdater
_ants: list[Ant]
```

Manages the ant population lifecycle:
- `initialize_population(ant_count, start_node)` — pool management.
- `construct_routes(request, pheromones, visibility, graph, streams)` — main
  route construction loop.
- `evaluate_population()` → `(best, worst, avg)` as `CandidateSolution`.
- `compute_diversity()` → ratio of unique edges to total edges in population.

---

## 7. Step-by-step written algorithm

Matching `ACORouting.optimize()` (`aco.py:690–855`):

1. **Validate context** — `ACOValidator.validate_context()` checks graph and
   cost_calculator are non-None, source ≠ destination.
2. **Validate ACS config** — `ACOValidator.validate_config()` checks all
   hyperparameters.
3. **Build static visibility matrix** — `VisibilityMatrix(graph,
   cost_calculator, config)` — compute `eta_ij = 1/(cost+EPS)` for every edge.
4. **Build pheromone matrix** — `PheromoneMatrix(config, edge_ids)` — initialise
   all edges to `tau0`.
5. **Create random streams** — `SwarmRandom(context.random_seed)` → named
   streams `"aco.selection"` and `"aco.roulette"`.
6. **Create colony** — `AntColony(config)`.
7. **Main loop** — for `iteration = 0 .. max_iters-1`:
   1. `colony.initialize_population(ant_count, source_node)` — ants placed at
      source.
   2. `colony.construct_routes(...)` — each ant builds a route:
      - While `steps < max_nodes * 2` and `current_node ≠ destination`:
        - Gather candidate outgoing edges (filter backtrack, prefer non-dead-end
          targets if possible).
        - `TransitionRule.select(candidates, pheromones, visibility, streams)`
          → next edge or `None`.
        - If `None`, mark `reached_dead_end = True`, break.
        - `PheromoneUpdater.local_update(pheromones, next_edge)` — online
          pheromone decay.
        - Move ant to target node.
      - After loop: if `is_complete`, compute `total_cost`; else `_PENALTY_COST`.
   3. `colony.evaluate_population()` → iteration best, worst, average.
   4. `colony.compute_diversity()` → unique-edge ratio.
   5. Update global best (if iteration best < global best).
   6. **Global pheromone update** — reinforce best-so-far edges.
   7. **Elite reinforcement** — top-N ants reinforce with `ρ/2`.
   8. Record per-iteration statistics.
8. **Build result** — wrap best solution into `RouteCandidate` with `RouteCost`.
9. **Convergence detection** — scan iteration history backward for last
   improvement.
10. **Return** `SwarmResult` with candidates, statistics, iteration history.

---

## 8. Clear implementation-level pseudocode

### `ACORouting.optimize(context)`

```
function ACORouting.optimize(context):
    errors = ACOValidator.validate_context(context)
    if errors: return _failure_result(errors)

    graph      = context.graph
    calculator = context.cost_calculator
    request    = context.routing_request
    swarm_cfg  = context.config
    aco_cfg    = self._config

    visibility = VisibilityMatrix(graph, calculator, aco_cfg)
    edge_ids   = {e.edge_id for e in graph.edges()}
    pheromones = PheromoneMatrix(aco_cfg, edge_ids)

    swarm_rand = SwarmRandom(context.random_seed)
    sel_stream = swarm_rand.get_stream("aco.selection")
    roul_stream = swarm_rand.get_stream("aco.roulette")

    colony     = AntColony(aco_cfg)
    global_best = None
    global_best_iter = 0

    ant_count    = swarm_cfg.population_size ?? 20
    max_iters    = swarm_cfg.max_iterations ?? 100

    for iteration = 0..max_iters-1:
        colony.initialize_population(ant_count, request.source_node)

        colony.construct_routes(request, pheromones, visibility,
                                graph, sel_stream, roul_stream)

        iter_best, iter_worst, avg_cost = colony.evaluate_population()
        diversity = colony.compute_diversity()

        if iter_best.score < global_best.score:
            global_best = iter_best
            global_best_iter = iteration

        colony._updater.global_update(pheromones,
            global_best.solution.edge_sequence, global_best.score)

        if aco_cfg.elitism > 0:
            elite = top-N ants by total_cost
            colony._updater.global_update_elite(pheromones,
                elite_edges, elite_costs)

        record iteration statistics

    build RouteCandidate from global_best
    return SwarmResult(success=(global_best != None), ...)
```

### `VisibilityMatrix.__init__()`

```
function VisibilityMatrix.__init__(graph, calculator, config):
    for each edge in graph.edges():
        eid = edge.edge_id
        if edge.state.is_blocked:
            self._data[eid] = 0.0
        else:
            try:
                cost, _ = calculator.compute_edge_cost(edge)
            except:
                cost = inf
            if not finite(cost) or cost < 0:
                self._data[eid] = 0.0
            elif cost == 0.0:
                self._data[eid] = 1.0 / _EPS
            else:
                self._data[eid] = 1.0 / (cost + _EPS)

    for each node in graph.nodes():
        nid = node.node_id
        outgoing = []
        for e in graph.outgoing_edges(nid):
            vis = self._data[e.edge_id]
            if vis > 0.0:
                outgoing.append(e.edge_id)
        if config.candidate_list_size > 0 and |outgoing| > limit:
            sort outgoing by visibility descending
            truncate to limit
        self._neighbour_cache[nid] = outgoing
```

### `PheromoneMatrix.decay()` / `reinforce()`

```
function decay(edge_id, rho, tau0):
    current = self.get(edge_id)
    self.set(edge_id, (1 - rho) * current + rho * tau0)

function reinforce(edge_id, rho, deposit):
    current = self.get(edge_id)
    self.set(edge_id, (1 - rho) * current + rho * deposit)

function set(edge_id, value):
    if not finite(value): value = tau_max if value > 0 else tau_min
    self._data[edge_id] = clamp(value, tau_min, tau_max)
```

### `TransitionRule.select()`

```
function select(candidates, pheromones, visibility, sel_stream, roul_stream):
    if candidates is empty: return None

    if sel_stream.random() <= q0:
        // Exploitation — argmax
        best_eid = candidates[0]
        best_val = -1.0
        for eid in candidates:
            val = (tau(eid)^alpha) * (eta(eid)^beta)
            if val > best_val: best_val = val; best_eid = eid
        return best_eid
    else:
        // Exploration — roulette wheel
        weights = []
        total = 0.0
        for eid in candidates:
            w = (tau(eid)^alpha) * (eta(eid)^beta)
            if not finite(w) or w < 0: w = 0.0
            weights.append(w)
            total += w
        if total <= 0:
            return candidates[roul_stream.randint(0, |candidates|-1)]
        r = roul_stream.random() * total
        cumulative = 0.0
        for i, w in enumerate(weights):
            cumulative += w
            if r <= cumulative: return candidates[i]
        return candidates[-1]
```

### `AntColony.construct_routes()`

```
function construct_routes(request, pheromones, visibility, graph,
                          sel_stream, roul_stream):
    dest = request.destination_node
    max_steps = |graph.nodes()| * 2

    for each ant in self._ants:
        ant.prev_node = None
        for step = 0..max_steps-1:
            if ant.current_node == dest:
                ant.is_complete = True
                break

            candidates = []
            for eid in visibility.get_neighbours(ant.current_node):
                edge = graph.get_edge(eid)
                if ant.prev_node != None and edge.target == ant.prev_node:
                    continue  // no immediate backtrack
                candidates.append(eid)

            // Prefer non-dead-end targets
            if |candidates| > 1:
                alive = [c for c in candidates if _not_deadend(c, graph, dest)]
                if alive: candidates = alive

            next_edge = self._transition.select(candidates, pheromones,
                                                visibility, sel_stream,
                                                roul_stream)
            if next_edge is None:
                ant.reached_dead_end = True
                break

            self._updater.local_update(pheromones, next_edge)
            ant.edge_sequence.append(next_edge)
            ant.node_sequence.append(edge.target)
            ant.prev_node = ant.current_node
            ant.current_node = edge.target

        if ant.is_complete:
            ant.total_cost = _compute_edge_cost_sequence(ant.edge_sequence,
                                                         graph)
        else:
            ant.total_cost = _PENALTY_COST
            ant.is_feasible = False

    return self._ants
```

### `_compute_edge_cost_sequence()`

```
function _compute_edge_cost_sequence(edge_ids, graph):
    total = 0.0
    for eid in edge_ids:
        edge = graph.get_edge(eid)
        if edge.state.is_blocked:
            total += _PENALTY_COST  // 1e9
        else:
            length_m = edge.length_m
            speed = edge.state.current_speed_mps or edge.speed_limit_mps
            time_cost = length_m / speed if speed > 0 else _PENALTY_COST
            total += length_m + time_cost
    return total
```

### `AntColony.evaluate_population()`

```
function evaluate_population():
    best = None; worst = None; total_cost = 0.0

    for ant in self._ants:
        node_seq = tuple(ant.node_sequence)
        edge_seq = tuple(ant.edge_sequence)
        if |node_seq| < 2:
            // Minimal fallback path
            node_seq = (node_seq[0], node_seq[0])
            edge_seq = (EdgeId(""),)
        sol = CandidateSolution(
            solution=Solution(node_sequence=node_seq,
                              edge_sequence=edge_seq,
                              metadata={...}),
            score=ant.total_cost)
        total_cost += sol.score
        update best/worst

    avg = total_cost / |ants|
    return (best, worst, avg)
```

### `SwarmToRoutingAdapter.compute_route()`

```
function compute_route(request, graph):
    swarm_context = SwarmContext(
        cost_weights=config.cost_weights,
        config=config, random_seed=seed,
        routing_request=request, sim_time_s=0.0,
        graph=graph,
        cost_calculator=CompositeCostCalculator(config.cost_weights)
    )

    swarm_result = self._swarm.optimize(swarm_context)

    // Build primary Route from best candidate
    primary = Route(...)
    return RoutingResult(candidates, primary, swarm_result.success, ...)
```

---

## 9. Time complexity

| Phase | Complexity | Notes |
|---|---|---|
| Visibility building | `O(E · d + N · d)` = `O(E + N·d)` | `O(d)` per edge for cost calc; `O(N·d)` for neighbour cache |
| Pheromone init | `O(E)` | Dict creation over all edges |
| Per iteration: construct routes | `O(P · max_steps · d)` | `P` = ants, `max_steps = 2N`, `d` = avg out-degree |
| Per iteration: evaluate | `O(P · E)` | Iterates edge sequences of all ants |
| Per iteration: local update | `O(P · max_steps)` | One decay per ant per step |
| Per iteration: global update | `O(L_best)` | Length of best-so-far edge sequence |
| Per iteration: elite update | `O(elitism · L_elite)` | Typically 1–3 shortest ants |
| Per iteration: diversity | `O(P · max_steps)` | Set union of edge IDs |
| **Overall** | **`O(I · P · N · d)`** | `I` = iterations, `P` = population, `N` = nodes, `d` = avg degree |

In practice, `max_steps = 2N` is the worst-case — ants terminate early on
destination arrival or dead end.

---

## 10. Space complexity

| Structure | Size | Notes |
|---|---|---|
| `PheromoneMatrix._data` | `O(E)` | One float per graph edge |
| `VisibilityMatrix._data` | `O(E)` | One float per graph edge |
| `VisibilityMatrix._neighbour_cache` | `O(N · d)` | One list of edge IDs per node |
| `AntColony._ants` | `O(P · N)` | Each ant holds node + edge sequence (worst case length = max_steps) |
| **Total** | **`O(E + N + P·N)`** ≈ `O(E + N)` for `P << E` |

---

## 11. Strengths

1. **Proven combinatorial optimisation** — ACS is a well-studied algorithm with
   strong convergence guarantees for shortest-path problems.
2. **Online learning via local update** — pheromone evaporation on every step
   discourages premature convergence and encourages exploration.
3. **Explicit exploration–exploitation trade-off** — `q0` parameter directly
   controls probability of greedy argmax vs. probabilistic roulette selection.
4. **Dead-end awareness** — ants detect `reached_dead_end` and filter candidate
   edges to avoid them when alternatives exist.
5. **Pheromone bounds (MMAS)** — `[tau_min, tau_max]` clamping prevents
   stagnation and ensures every edge retains some selection probability.
6. **Deterministic reproducibility** — all randomness goes through
   `SwarmRandom` named streams; same seed + same inputs = identical results.
7. **Modular architecture** — clean separation of transition rule, pheromone
   update, and colony management.

---

## 12. Weaknesses

1. **Static heuristic** — `VisibilityMatrix` is computed once at the start and
   never updated during optimisation.  Congestion changes mid-run are reflected
   in pheromones but not in the heuristic `eta_ij`.
2. **No dynamic re-routing** — the algorithm does not support warm-start or
   incremental re-optimisation from a previous solution.
3. **Computational cost** — `O(I · P · N · d)` can be high for large graphs
   (`N > 10⁴`).
4. **Single-destination focus** — each optimisation run solves one
   source–destination pair.  No support for multiple simultaneous routes.
5. **No constraints** — vehicle constraints (battery SoC, time windows) are not
   modelled inside ACO (handled externally by the cost calculator).
6. **Elite reinforcement uses `ρ/2`** — the factor `rho * 0.5` in
   `global_update_elite` is an implementation-specific choice (not standard
   ACS), applied to dampen elite influence.

---

## 13. Why it was selected

1. **Natural fit for road networks** — ants traverse a graph edge by edge,
   mirroring vehicle navigation through road segments.
2. **Pheromone = collective memory** — in a disaster scenario, the pheromone
   matrix naturally encodes which roads the colony has found safe/cheap over
   time, analogous to real-time traffic knowledge.
3. **Population-based** — maintains a diverse set of candidate routes each
   iteration, useful for providing alternatives in the decision engine.
4. **Established baseline** — ACS is the de facto standard ant algorithm in
   the literature, making comparisons with other E³-Hybrid swarm algorithms
   meaningful.
5. **MMAS bounds for dynamic environments** — the `[tau_min, tau_max]` window
   ensures the algorithm retains exploration capability even after convergence,
   crucial when road conditions change.

---

## 14. How it interacts with SUMO

The ACO module **never imports or references SUMO directly**.  Interaction
occurs through the `SwarmToRoutingAdapter` (`adapter.py`):

```
SUMO simulation  ─→  Edge.state (current_speed_mps, is_blocked, …)
                                   ↓
                         DirectedGraph  ─→  SwarmContext.graph
                                   ↓
                    CompositeCostCalculator.compute_edge_cost(edge)
                                   ↓
                         VisibilityMatrix (eta_ij = 1/(cost+EPS))
                                   ↓
                         TransitionRule (alpha, beta, tau, eta)
                                   ↓
                         AntColony constructs routes
                                   ↓
                         SwarmResult → RouteCandidate
                                   ↓
                    SwarmToRoutingAdapter → RoutingResult
                                   ↓
                    SUMO simulation (via DecisionEngine)
```

Flow:
- SUMO updates `edge.state` (congestion, blocks, speed changes) on the graph.
- `CompositeCostCalculator` reads these states and returns weighted costs.
- `VisibilityMatrix` translates costs into heuristic values.
- `PheromoneMatrix` evolves independently, encoding the colony's learned
  preferences.
- The final route is returned as a `RoutingResult` consumable by the
  simulation's decision engine.

---

## 15. How it responds to congestion, road closures, emergency events

### Congestion

- `edge.state.congestion_factor > 1.0` increases the travel time → higher
  `edge_cost` → lower `eta_ij` → edge less attractive.
- `edge.state.current_speed_mps` (if set) reflects measured flow speed; slower
  speeds → longer time cost.
- Pheromone evaporation gradually removes preference for previously good but
  now congested edges.

### Road closures

- `edge.state.is_blocked = True` → `VisibilityMatrix` sets `eta_ij = 0.0` →
  edge never selected by any ant.
- `_compute_edge_cost_sequence` adds `_PENALTY_COST (1e9)` if a blocked edge is
  somehow in a sequence (safety guard).
- `_not_deadend()` helper checks if an edge's target has any outgoing edges
  (avoids routing through node with all outgoing roads closed).

### Emergency events

- `edge.state.hazard_penalty_s`, `edge.state.emergency_penalty_s`,
  `edge.state.communication_penalty_s` — additive penalties incorporated by
  `CompositeCostCalculator.compute_edge_cost()` into the total cost.
- Higher cost → lower visibility → reduced selection probability.
- These are **weighted** by `CostWeights` before being summed into the final
  edge cost.

### Summary table

| Event | Graph effect | Visibility effect | Pheromone effect |
|---|---|---|---|
| Congestion | `current_speed_mps ↓` or `congestion_factor ↑` | `eta ↓` (less attractive) | Gradual evaporation |
| Blocked road | `is_blocked = True` | `eta = 0` (never chosen) | Can remain but unused |
| Hazard zone | `hazard_penalty_s > 0` | `eta ↓` (proportional) | Gradual evaporation |
| Emergency corridor | `emergency_penalty_s > 0` | `eta ↓` | Gradual evaporation |
| Comms disruption | `communication_penalty_s > 0` | `eta ↓` | Gradual evaporation |

---

## 16. How randomness is controlled

All stochastic decisions use `SwarmRandom` (`random.py:12`):

```python
swarm_random = SwarmRandom(base_seed=context.random_seed)
sel_stream = swarm_random.get_stream("aco.selection")
roul_stream = swarm_random.get_stream("aco.roulette")
```

| Stream name | Used by | Purpose |
|---|---|---|
| `"aco.selection"` | `TransitionRule.select()` line 279 | `random() <= q0` — decides exploitation vs. exploration |
| `"aco.roulette"` | `TransitionRule._roulette()` line 330 | `random() * total` — roulette-wheel selection; fallback `randint()` |

Stream derivation (`SwarmRandom.get_stream()`, `random.py:48`):
```
stream_seed = (base_seed XOR hash(name)) & 0x7FFFFFFF
return random.Random(stream_seed)
```

- Each stream is an independent `random.Random` instance.
- Streams are lazily created and cached.
- `SwarmRandom.reset()` clears the cache; subsequent `get_stream()` calls
  reproduce the same sequences.

---

## 17. Determinism and reproducibility

Given:
- Same `SwarmContext` (same `graph`, `routing_request`, `config`,
  `random_seed`, `cost_calculator`)
- Same `ACSConfiguration`

Then:
- `ACORouting.optimize()` returns an identical `SwarmResult` on every call.

This is guaranteed by:
1. **All randomness through `SwarmRandom`** — no `random.random()`,
   `numpy.random`, `secrets`, or time-based seeds.
2. **No global/static state** — `AntColony`, `PheromoneMatrix`,
   `VisibilityMatrix` are all instance-local; no module-level mutation.
3. **Deterministic graph iteration** — `DirectedGraph.edges()` returns edges in
   insertion order (CPython 3.7+ dict guarantee).
4. **Immutable data structures** — `SwarmContext` is frozen; `Ant` is a
   dataclass reset every iteration.
5. **No asynchronous operations** — single-threaded synchronous optimisation.
6. **Floating-point determinism** — only uses `math.isfinite`, `math.isnan`,
   basic arithmetic (no platform-dependent SIMD / BLAS).

---

## 18. Mapping between pseudocode and implementation

| Step | Pseudocode location | Class | Method | File:Line |
|---|---|---|---|---|
| 1 | Validate context | `ACOValidator` | `validate_context()` | `aco.py:473` |
| 2 | Validate ACS config | `ACOValidator` | `validate_config()` | `aco.py:450` |
| 3 | Build visibility matrix | `VisibilityMatrix` | `__init__()` | `aco.py:193` |
| 4 | Build pheromone matrix | `PheromoneMatrix` | `__init__()` | `aco.py:141` |
| 5 | Create random streams | `SwarmRandom` | `get_stream()` | `random.py:31` |
| 6 | Create colony | `AntColony` | `__init__()` | `aco.py:491` |
| 7a | Initialise population | `AntColony` | `initialize_population()` | `aco.py:497` |
| 7b | Main loop | `ACORouting` | `optimize()` (for loop) | `aco.py:741` |
| 7c | Route construction | `AntColony` | `construct_routes()` | `aco.py:504` |
| 7d | Candidate filtering | `AntColony.construct_routes` | inline (lines 525–538) | `aco.py:525` |
| 7e | Dead-end test | module-level `_not_deadend()` | — | `aco.py:627` |
| 7f | Transition selection | `TransitionRule` | `select()` | `aco.py:269` |
| 7g | Argmax (exploitation) | `TransitionRule` | `_argmax()` | `aco.py:283` |
| 7h | Roulette (exploration) | `TransitionRule` | `_roulette()` | `aco.py:304` |
| 7i | Local pheromone update | `PheromoneUpdater` | `local_update()` | `aco.py:390` |
| 7j | Pheromone decay | `PheromoneMatrix` | `decay()` | `aco.py:155` |
| 7k | Cost computation | module-level `_compute_edge_cost_sequence()` | — | `aco.py:634` |
| 7l | Evaluate population | `AntColony` | `evaluate_population()` | `aco.py:566` |
| 7m | Diversity metric | `AntColony` | `compute_diversity()` | `aco.py:605` |
| 7n | Global best update | `ACORouting.optimize` | inline (lines 752–755) | `aco.py:752` |
| 7o | Global pheromone update | `PheromoneUpdater` | `global_update()` | `aco.py:393` |
| 7p | Pheromone reinforce | `PheromoneMatrix` | `reinforce()` | `aco.py:159` |
| 7q | Elite reinforcement | `PheromoneUpdater` | `global_update_elite()` | `aco.py:405` |
| 7r | Clamp to [tau_min, tau_max] | `PheromoneMatrix` | `set()` | `aco.py:149` |
| 8a | Build RouteCandidate | `ACORouting.optimize` | inline (lines 790–822) | `aco.py:790` |
| 8b | Convergence detection | `ACORouting.optimize` | inline (lines 826–829) | `aco.py:826` |
| 8c | Build SwarmStatistics | `ACORouting.optimize` | inline (lines 834–846) | `aco.py:834` |
| 9 | Return SwarmResult | `ACORouting.optimize` | return statement | `aco.py:848` |
| — | Adapt to RoutingResult | `SwarmToRoutingAdapter` | `compute_route()` | `adapter.py:56` |
| — | Build SwarmContext | `SwarmToRoutingAdapter` | `compute_route()` inline | `adapter.py:104` |
| — | Build primary Route | `SwarmToRoutingAdapter` | `compute_route()` inline | `adapter.py:127` |
