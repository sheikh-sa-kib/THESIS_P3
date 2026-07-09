# A\* Algorithm — Dynamic EV Routing with SUMO

## 1. Purpose in this thesis

A\* serves as the **heuristic-guided shortest-path algorithm** in the E3-Hybrid framework. It extends Dijkstra by incorporating a heuristic function `h(n)` to focus exploration toward the destination. A\* is the bridge between the uninformed baseline (Dijkstra) and the stochastic multi-path swarm algorithms (ACO, BCO, PSO, E3-Hybrid). It demonstrates whether heuristic guidance improves search efficiency on real-world road networks while maintaining optimality (when using admissible heuristics like Euclidean distance).

## 2. Theory actually implemented

The implementation in `astar.py` follows the **standard A\* best-first search algorithm** with an **open set** (priority queue ordered by `f(n) = g(n) + h(n)`) and a **closed set** for expanded nodes:

- Maintains a **g_score** map: shortest known cost from source to each node (`g(n)`)
- Maintains an **f_score** map: estimated total cost through each node (`f(n) = g(n) + h(n)`)
- Maintains a **predecessor map** and **predecessor edge map** for path reconstruction
- Maintains an **open set** (`in_open`) for O(1) membership checks
- Maintains a **closed set** for expanded nodes (prevents re-expansion)
- Uses a **priority queue** (heapq) ordered by `(f_score, node_id)`
- Only explores nodes reachable via unblocked edges with finite cost
- Terminates when the destination node is popped from the priority queue (goal test on expansion)
- Heuristic is injected via the `Heuristic` Protocol, enabling pluggable strategies (Zero, Euclidean, Manhattan)

The algorithm uses a **closed set** approach: once a node is expanded (popped from pq and added to closed), it is never revisited. This requires the heuristic to be **consistent** (monotone) for optimality — a property that holds for both Euclidean and Manhattan heuristics but is technically not guaranteed for arbitrary admissible heuristics without re-expansion logic.

## 3. Inputs

| Input | Type | Source | Description |
|-------|------|--------|-------------|
| `request.source_node` | `NodeId` (str `NewType`) | `RoutingRequest` | Origin node, validated via `graph.has_node()` |
| `request.destination_node` | `NodeId` (str `NewType`) | `RoutingRequest` | Target node, validated via `graph.has_node()` |
| `request.timeout_s` | `float` | `RoutingRequest` | Maximum wall-clock runtime; timeout returns failure `RoutingResult` |
| `request.vehicle_id` | `VehicleId` | `RoutingRequest` | Vehicle identifier (not used in computation) |
| `request.vehicle_constraints` | `Any` | `RoutingRequest` | Operational limits (not used in current A\*) |
| `request.battery_state` | `Any` | `RoutingRequest` | Battery snapshot (not used in current A\*) |
| `request.max_candidates` | `int` | `RoutingRequest` | Maximum candidates (A\* ignores this, always returns 1) |
| `graph` | `DirectedGraph \| None` | External parameter | The directed road network graph |
| `self._heuristic` | `Heuristic` | Initialized in `__init__` | Heuristic function; defaults to `ZeroHeuristic` |
| `self._cost_calculator` | `CompositeCostCalculator` | Initialized in `__init__` with `CostWeights` | Computes weighted per-edge cost |

The heuristic is injected via constructor parameter. The `HeuristicFactory` provides `"zero"`, `"euclidean"`, and `"manhattan"` options (`heuristic_factory.py`).

## 4. Outputs

Returns a single `RoutingResult` (identical structure to Dijkstra):

| Field | Type | Description |
|-------|------|-------------|
| `candidates` | `tuple[RouteCandidate, ...]` | Tuple with exactly 1 candidate on success, empty on failure |
| `primary_route` | `Route \| None` | Best `Route` on success, `None` on failure |
| `success` | `bool` | `True` if path found, `False` otherwise |
| `failure_reason` | `str \| None` | Human-readable failure explanation, or `None` on success |
| `statistics` | `RoutingStatistics` | `RoutingStatistics(nodes_explored, edges_explored, candidates_generated)` |
| `runtime_s` | `float` | `time.perf_counter()` delta from start to end |

Failure modes are identical to Dijkstra: source missing, destination missing, timeout, no path, path reconstruction failure.

## 5. Configuration parameters (cost weights)

Identical to Dijkstra — uses the same `CostWeights` from `cost_calculator.py`:

| Parameter | Default | Description |
|-----------|---------|-------------|
| `distance` | 1.0 | Weight for physical distance cost (`edge.length_m`) |
| `time` | 1.0 | Weight for travel time cost (`length_m / effective_speed × congestion_factor`) |
| `energy` | 1.0 | Weight for energy cost (placeholder, always 0.0) |
| `congestion` | 1.0 | Weight for congestion penalty |
| `hazard` | 1.0 | Weight for hazard penalty (`edge.state.hazard_penalty_s`) |
| `emergency` | 1.0 | Weight for emergency penalty (`edge.state.emergency_penalty_s`) |
| `communication` | 1.0 | Weight for communication penalty (`edge.state.communication_penalty_s`) |

Additionally, the heuristic can be configured:

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `heuristic` | `Heuristic \| None` | `ZeroHeuristic()` | Heuristic function instance |
| `scale` (via factory) | `float` | 1.0 | Scaling factor for Euclidean/Manhattan heuristics |

When `heuristic=None` (or `ZeroHeuristic`), A\* degenerates to Dijkstra's behavior: `f(n) = g(n) + 0 = g(n)`, and search order becomes identical.

## 6. Internal data structures

| Structure | Type | Scope | Purpose |
|-----------|------|-------|---------|
| `g_score` | `dict[NodeId, float]` | `compute_route` | Known shortest cost from source to each node; initialized `{source: 0.0}` |
| `f_score` | `dict[NodeId, float]` | `compute_route` | Estimated total cost `g(n) + h(n)`; initialized `{source: 0.0 + h(source)}` |
| `predecessors` | `dict[NodeId, NodeId]` | `compute_route` | Previous node on the current best path to each node for reconstruction |
| `predecessor_edges` | `dict[NodeId, EdgeId]` | `compute_route` | Edge ID used to reach each node on the best path for reconstruction |
| `pq` | `list[tuple[float, NodeId]]` | `compute_route` | Min-heap priority queue ordered by `(f_score, node_id)` |
| `in_open` | `set[NodeId]` | `compute_route` | Set of nodes currently in the priority queue (for O(1) membership checks) |
| `closed` | `set[NodeId]` | `compute_route` | Set of nodes already expanded (finalized); prevents re-expansion |
| `source` | `NodeId` | `compute_route` | `request.source_node` (local alias) |
| `destination` | `NodeId` | `compute_route` | `request.destination_node` (local alias) |
| `start_time` | `float` | `compute_route` | `time.perf_counter()` at start for timeout and runtime tracking |
| `nodes_explored` | `int` | `compute_route` | Counter incremented each time a node is expanded (added to closed) |
| `edges_explored` | `int` | `compute_route` | Counter incremented each time an outgoing edge is examined |
| `path_nodes` | `list[NodeId]` | `compute_route` | Reconstructed node sequence (built in reverse, then reversed) |
| `path_edges` | `list[EdgeId]` | `compute_route` | Reconstructed edge sequence (built in reverse, then reversed) |
| `_last_nodes_explored` | `int` | `AStarRouting` instance | Stored on `self` after search for use in `_build_candidate` |
| `self._heuristic` | `Heuristic` | `AStarRouting` instance | Injected heuristic; used via `self._heuristic.estimate(...)` |

## 7. Step-by-step written algorithm

**`compute_route(request, graph)` method:**

1. **Validate graph**: If `graph is None`, raise `ValueError`.
2. **Initialize**: Record `start_time = time.perf_counter()`, set `nodes_explored = 0`, `edges_explored = 0`. Extract `source` and `destination` from request.
3. **Validate source node**: If `graph.has_node(source)` is `False`, return failure `RoutingResult`.
4. **Validate destination node**: If `graph.has_node(destination)` is `False`, return failure `RoutingResult`.
5. **Initialize g_score**: `g_score = {source: 0.0}`.
6. **Compute initial heuristic**: `h_source = self._heuristic.estimate(source, destination, graph)`.
6. **Initialize f_score**: `f_score = {source: g_score[source] + h_source}`.
7. **Initialize predecessors**: `predecessors = {}`, `predecessor_edges = {}`.
8. **Initialize priority queue**: Push `(f_score[source], source)` to `pq`.
9. **Initialize open set**: `in_open = {source}`.
10. **Initialize closed set**: `closed = set()`.
11. **Main loop** — while `pq` is not empty:
    a. **Check timeout**: If `time.perf_counter() - start_time > request.timeout_s`, return timeout failure `RoutingResult`.
    b. **Pop smallest**: `_, current = heapq.heappop(pq)`.
    c. **Remove from open set**: `in_open.discard(current)`.
    d. **Skip processed**: If `current in closed`, `continue` (stale entry).
    e. **Mark as expanded**: `closed.add(current)`, `nodes_explored += 1`.
    f. **Goal test**: If `current == destination`, `break`.
    g. **Explore edges**: For each `edge` in `graph.outgoing_edges(current)`:
      - Increment `edges_explored`.
      - **Skip blocked**: If `edge.state.is_blocked`, `continue`.
      - **Compute cost**: `edge_cost, _ = self._cost_calculator.compute_edge_cost(edge)`.
      - **Skip impassable**: If `edge_cost == float("inf")`, `continue`.
      - **Get neighbor**: `neighbor = edge.target`.
      - **Skip closed**: If `neighbor in closed`, `continue` (already finalized).
      - **Tentative g**: `tentative_g = g_score[current] + edge_cost`.
      - **Better path**: If `neighbor not in g_score` or `tentative_g < g_score[neighbor]`:
        - Update `g_score[neighbor] = tentative_g`.
        - Set `predecessors[neighbor] = current`.
        - Set `predecessor_edges[neighbor] = edge.edge_id`.
        - Compute heuristic: `h = self._heuristic.estimate(neighbor, destination, graph)`.
        - Compute f: `f = tentative_g + h`.
        - Update `f_score[neighbor] = f`.
        - Push `heapq.heappush(pq, (f, neighbor))`.
        - Add to `in_open.add(neighbor)`.
12. **Check destination reached**: If `destination not in closed`, return "No path exists" failure `RoutingResult`.
13. **Store nodes_explored**: `self._last_nodes_explored = nodes_explored`.
14. **Reconstruct path**: (identical to Dijkstra — walk `predecessors` from destination to source, reverse).
15. **Build route**: `self._build_route(path_nodes, path_edges, graph)`.
16. **Build candidate**: `self._build_candidate(route, graph)`.
17. **Return success**: `RoutingResult` with `primary_route`, `candidates=(candidate,)`, `statistics`, `runtime_s`.

**`_build_route(path_nodes, path_edges, graph)` method**: Identical to Dijkstra — sums distances, computes travel time from effective speed, energy = 0 placeholder.

**`_build_candidate(route, graph)` method**: Identical to Dijkstra except it uses `getattr(self, "_last_nodes_explored", 0)` for `SearchStatistics(iterations=...)`.

## 8. Clear implementation-level pseudocode

```
ALGORITHM AStarRouting:
    INPUT: request (RoutingRequest), graph (DirectedGraph or None)
    OUTPUT: RoutingResult

    METHOD __init__(heuristic=None, cost_weights=None):
        IF heuristic IS None: heuristic = ZeroHeuristic()
        IF cost_weights IS None: cost_weights = CostWeights()
        self._heuristic = heuristic
        self._cost_calculator = CompositeCostCalculator(cost_weights)

    METHOD compute_route(request, graph):
        IF graph IS None: RAISE ValueError

        start_time = time.perf_counter()
        nodes_explored = 0
        edges_explored = 0
        source = request.source_node
        destination = request.destination_node

        IF NOT graph.has_node(source):
            RETURN RoutingResult(
                candidates=(), primary_route=None, success=False,
                failure_reason="Source node X does not exist in graph",
                statistics=RoutingStatistics(0, 0, 0),
                runtime_s=time.perf_counter() - start_time
            )

        IF NOT graph.has_node(destination):
            RETURN RoutingResult(
                candidates=(), primary_route=None, success=False,
                failure_reason="Destination node Y does not exist in graph",
                statistics=RoutingStatistics(0, 0, 0),
                runtime_s=time.perf_counter() - start_time
            )

        g_score = {source: 0.0}
        h_source = self._heuristic.estimate(source, destination, graph)
        f_score = {source: g_score[source] + h_source}
        predecessors = {}
        predecessor_edges = {}
        pq = [(f_score[source], source)]       // min-heap of (f_score, node_id)
        in_open = {source}                      // O(1) membership for open set
        closed = set()                           // expanded nodes (finalized)

        WHILE pq IS NOT EMPTY:
            IF time.perf_counter() - start_time > request.timeout_s:
                RETURN RoutingResult(
                    candidates=(), primary_route=None, success=False,
                    failure_reason="Routing exceeded timeout of Xs",
                    statistics=RoutingStatistics(nodes_explored, edges_explored, 0),
                    runtime_s=time.perf_counter() - start_time
                )

            _, current = heapq.heappop(pq)
            in_open.DISCARD(current)

            IF current IN closed:               // stale priority-queue entry
                CONTINUE

            closed.ADD(current)
            nodes_explored += 1

            IF current == destination:           // goal test on expansion
                BREAK

            FOR EACH edge IN graph.outgoing_edges(current):
                edges_explored += 1

                IF edge.state.is_blocked:          // skip impassable roads
                    CONTINUE

                edge_cost, _ = self._cost_calculator.compute_edge_cost(edge)

                IF edge_cost == float("inf"):    // impassable edge
                    CONTINUE

                neighbor = edge.target

                IF neighbor IN closed:          // already expanded
                    CONTINUE

                tentative_g = g_score[current] + edge_cost

                IF (neighbor NOT IN g_score) OR (tentative_g < g_score[neighbor]):
                    g_score[neighbor] = tentative_g
                    predecessors[neighbor] = current
                    predecessor_edges[neighbor] = edge.edge_id

                    h = self._heuristic.estimate(neighbor, destination, graph)
                    f = tentative_g + h
                    f_score[neighbor] = f
                    heapq.heappush(pq, (f, neighbor))
                    in_open.ADD(neighbor)

        IF destination NOT IN closed:
            RETURN RoutingResult(
                candidates=(), primary_route=None, success=False,
                failure_reason="No path exists from X to Y",
                statistics=RoutingStatistics(nodes_explored, edges_explored, 0),
                runtime_s=time.perf_counter() - start_time
            )

        self._last_nodes_explored = nodes_explored

        // Path reconstruction (identical to Dijkstra)
        path_nodes = []
        path_edges = []
        current = destination

        WHILE current != source:
            path_nodes.APPEND(current)
            IF current IN predecessor_edges:
                path_edges.APPEND(predecessor_edges[current])
            IF current IN predecessors:
                current = predecessors[current]
            ELSE:
                RETURN RoutingResult(
                    candidates=(), primary_route=None, success=False,
                    failure_reason="Path reconstruction failed",
                    statistics=RoutingStatistics(nodes_explored, edges_explored, 0),
                    runtime_s=time.perf_counter() - start_time
                )

        path_nodes.APPEND(source)
        path_nodes.REVERSE()
        path_edges.REVERSE()

        route = self._build_route(path_nodes, path_edges, graph)
        candidate = self._build_candidate(route, graph)

        runtime = time.perf_counter() - start_time

        RETURN RoutingResult(
            candidates=(candidate,), primary_route=route, success=True,
            failure_reason=None,
            statistics=RoutingStatistics(nodes_explored, edges_explored, 1),
            runtime_s=runtime
        )

    METHOD _build_route(path_nodes, path_edges, graph):
        total_distance_m = 0.0
        total_time_s = 0.0
        total_energy_kwh = 0.0

        FOR EACH edge_id IN path_edges:
            edge = graph.get_edge(edge_id)
            total_distance_m += edge.length_m
            effective_speed = edge.state.current_speed_mps OR edge.speed_limit_mps
            IF effective_speed > 0:
                total_time_s += edge.length_m / effective_speed
            total_energy_kwh += 0.0

        RETURN Route(
            route_id=RouteId(str(uuid.uuid4())),
            node_sequence=tuple(path_nodes),
            edge_sequence=tuple(path_edges),
            total_distance_m=total_distance_m,
            estimated_travel_time_s=total_time_s,
            estimated_energy_kwh=total_energy_kwh,
        )

    METHOD _build_candidate(route, graph):
        edges = [graph.get_edge(eid) FOR eid IN route.edge_sequence]
        total_cost, breakdown = self._cost_calculator.compute_route_cost(edges)

        RETURN RouteCandidate(
            route_id=route.route_id,
            node_sequence=route.node_sequence,
            edge_sequence=route.edge_sequence,
            total_cost=total_cost,
            cost_breakdown=RouteCost(
                total=total_cost,
                distance_cost=breakdown.distance_cost,
                time_cost=breakdown.time_cost,
                energy_cost=breakdown.energy_cost,
                congestion_penalty=breakdown.congestion_penalty,
                hazard_penalty=breakdown.hazard_penalty,
                emergency_penalty=breakdown.emergency_penalty,
                communication_penalty=breakdown.communication_penalty,
                components={...all components},
            ),
            algorithm="astar",
            search_statistics=SearchStatistics(iterations=self._last_nodes_explored),
        )
```

## 9. Time complexity

`O(E + V log V)` with a good heuristic, `O((E + V) log V)` worst case (degenerates to Dijkstra with ZeroHeuristic).

- Each node is popped from `pq` at most once (`O(V log V)` total)
- Each edge is examined at most once (`O(E)`)
- Each edge may push a new entry onto `pq` (`O(E log V)` worst case)
- Each `heuristic.estimate()` call is `O(1)` (Euclidean: sqrt of coordinate differences; Manhattan: sum of absolute differences)
- Path reconstruction: `O(V)`

The effective complexity depends on the heuristic's ability to reduce nodes explored. A perfect heuristic reduces explored nodes to the nodes on the optimal path. The closed set prevents re-expansion (consistent heuristic assumption), eliminating the need for the open-set re-ordering that would be required with only an admissible heuristic.

**Key implementation detail**: The `closed` set check on line 220 (`if neighbor in closed: continue`) means that if a node has been expanded but a better path is found later, it is ignored. This requires the heuristic to be **consistent** (monotone) for optimality. If a non-consistent heuristic is used, A\* may miss the optimal path (suboptimal result, not algorithm failure).

## 10. Space complexity

`O(V)` for the main data structures:
- `g_score` dict: at most V entries
- `f_score` dict: at most V entries
- `predecessors` dict: at most V entries
- `predecessor_edges` dict: at most V entries
- `pq` heap: at most V + E entries (may contain stale entries)
- `in_open` set: at most V entries
- `closed` set: at most V entries
- Path reconstruction: `O(V)` for node/edge sequence lists and output objects

Total space: `O(V)` plus heap entries which can reach `O(E)` with stale entries.

## 11. Strengths

1. **Optimality with admissible heuristics**: With Euclidean or Manhattan heuristics (which are admissible for road networks), A\* guarantees the shortest path.

2. **Efficiency through heuristics**: Euclidean heuristic focuses exploration toward the destination, typically exploring fewer nodes than Dijkstra. On real road networks, this can reduce search space substantially.

3. **Pluggable heuristics**: The `Heuristic` Protocol (`heuristic.py:18-66`) allows different heuristics to be swapped without modifying A\* code. Factory-based creation (`heuristic_factory.py`) enables configuration-driven heuristic selection.

4. **Dijkstra fallback**: `ZeroHeuristic` makes A\* behave identically to Dijkstra, useful for verification and baseline comparison.

5. **Timeout-safe**: Same wall-clock timeout mechanism as Dijkstra.

6. **Structured failure modes**: Same structured `RoutingResult` with detailed `failure_reason`.

7. **Pluggable heuristic scale**: Euclidean and Manhattan heuristics accept a `scale` parameter to match cost units, enabling correct scaling for time-based or mixed cost functions.

## 12. Weaknesses

1. **Closed set requires consistent heuristic**: The closed set approach (`if neighbor in closed: continue`, line 220) means A\* may not find the optimal path with an admissible but inconsistent heuristic. True optimal A\* requires reopening closed nodes when a better path is found, which is more complex and can degrade performance. The implementation documentation (class docstring, lines 52-54) acknowledges this: "If h is also consistent, A\* never needs to re-expand nodes."

2. **Single candidate**: Same as Dijkstra — returns only one route. `max_candidates` is ignored.

3. **No energy awareness**: Same energy placeholder as Dijkstra (`total_energy_kwh += 0.0`, line 328).

4. **Open set management**: The `in_open` set is maintained (line 170, added on 237, discarded on 190) but never actually read — it is not used for any decision. This is dead code from the perspective of search logic (the `closed` set is the only membership check). However, `in_open` is used in line 189 where `in_open.discard(current)` is called, and line 237 where `in_open.add(neighbor)` is called. It appears `in_open` is maintained for potential future use (e.g., for the open-set check that standard A\* descriptions include) but currently has no functional role.

5. **No k-shortest paths**: Does not generate alternatives or path diversity. Swarm algorithms provide this.

6. **Single-objective**: Linear scalar cost only; cannot capture Pareto-optimal trade-offs.

## 13. Why it was selected

1. **Heuristic evaluation**: A\* allows the thesis to quantitatively measure the benefit of heuristic guidance on road network routing — specifically, how much search space reduction Euclidean distance provides over the uninformed Dijkstra baseline.

2. **Algorithmic spectrum**: A\* fills the middle of the algorithmic spectrum:
   - **Uninformed**: Dijkstra (no heuristic)
   - **Heuristic-informed**: A\* (goal-directed)
   - **Metaheuristic/swarm**: ACO, BCO, PSO (population-based exploration)

3. **Optimality bridge**: A\* maintains the optimality guarantee of Dijkstra while potentially reducing computation time, providing a meaningful comparison point for swarm algorithms that sacrifice optimality for multi-path diversity.

4. **Protocol compliance**: Same `RoutingAlgorithm` Protocol as Dijkstra, enabling plug-and-play via `RoutingFactory`.

## 14. How it interacts with the SUMO simulation

Identical interaction pattern to Dijkstra:

1. **Network import**: SUMO networks → `DirectedGraph` nodes/edges
2. **State updates**: SUMO simulation loop updates `MutableEdgeState` on edges in real-time (speed, congestion, blocking, hazards, emergencies)
3. **Routing requests**: Created by Decision Engine based on vehicle states
4. **Route execution**: Returned `Route` dispatched to vehicle via TraCI

A\*'s heuristic generates better search efficiency but does not change the interaction pattern. The heuristic operates on graph node coordinates (x, y) for Euclidean/Manhattan distances, which must be populated during the SUMO→DirectedGraph import phase.

## 15. How it responds to congestion, road closures, and emergency events

Identical mechanism to Dijkstra — entirely through `CompositeCostCalculator`:

| Event | Edge field | Cost impact | Implementation |
|-------|-------------|-------------|----------------|
| Road closure | `edge.state.is_blocked` | Edge skipped entirely | Line 209: `if edge.state.is_blocked: continue` |
| Congestion | `edge.state.congestion_factor` | Multiplicative time cost increase | `cost_calculator.py:139: congested_time_s = base_time_s * congestion_factor` |
| Hazard event | `edge.state.hazard_penalty_s` | Additive penalty | `cost_calculator.py:148`: `hazard_penalty = edge.state.hazard_penalty_s` |
| Emergency corridor | `edge.state.emergency_penalty_s` | Additive penalty | `cost_calculator.py:149`: `emergency_penalty = edge.state.emergency_penalty_s` |
| Communication loss | `edge.state.communication_penalty_s` | Additive penalty | `cost_calculator.py:150`: `communication_penalty = edge.state.communication_penalty_s` |
| Effective speed zero | `edge.state.current_speed_mps` or speed limit | Infinite cost, edge skipped | `cost_calculator.py:136`: `if effective_speed > 0: ... else: base_time_s = float("inf")` |

The heuristic (Euclidean/Manhattan) is **not affected by edge state changes** — it computes pure geometric distance from node coordinates, not based on road conditions.

## 16. How randomness is controlled

This algorithm has no randomness. There is no `random` module import, no `random.seed()`, and no stochastic decision in `compute_route`. The `uuid.uuid4()` used for `route_id` (line 331) is cosmetic and does not affect computation.

All tie-breaking is deterministic: `heapq` orders by `(f_score, node_id)` tuple comparison.

## 17. Determinism and reproducibility notes

AStarRouting is fully deterministic given identical inputs:
- **Same graph** → same nodes with same coordinates → same heuristic return values
- **Same source, destination, cost weights** → same edge costs
- **Same heuristic** (instance, scale, type) → same `estimate()` return values
- **Same graph state** → same edge blocking/congestion mapping

The `uuid.uuid4()` in `_build_route` is cosmetic. The `in_open` set's discard/add operations do not affect determinism since set membership is deterministic for identical insertions.

**Important**: Two different `Heuristic` instances of the same class with the same `scale` produce identical results since the Heuristic Protocol has no mutable state.

## 18. Mapping between pseudocode and implementation

| Pseudocode Step | Method | Class/File | Line(s) | Description |
|---|---|---|---|---|
| Initialize heuristic and cost calculator | `__init__` | `AStarRouting.astar.py` | 72-90 | Sets `self._heuristic` (default ZeroHeuristic) and `self._cost_calculator` |
| Validate graph | `compute_route` | `AStarRouting.astar.py` | 121-122 | Raises `ValueError` if graph is None |
| Start timer | `compute_route` | `AStarRouting.astar.py` | 124 | `start_time = time.perf_counter()` |
| Init counters and aliases | `compute_route` | `AStarRouting.astar.py` | 125-128 | `nodes_explored = 0`, `edges_explored = 0`, `source`, `destination` |
| Validate source | `compute_route` | `AStarRouting.astar.py` | 131-141 | `graph.has_node(source)` → failure `RoutingResult` |
| Validate destination | `compute_route` | `AStarRouting.astar.py` | 143-153 | `graph.has_node(destination)` → failure `RoutingResult` |
| Init g_score | `compute_route` | `AStarRouting.astar.py` | 157 | `g_score = {source: 0.0}` |
| Compute initial heuristic | `compute_route` | `AStarRouting.astar.py` | 159 | `h_source = self._heuristic.estimate(source, destination, graph)` |
| Init f_score | `compute_route` | `AStarRouting.astar.py` | 160 | `f_score = {source: g_score[source] + h_source}` |
| Init predecessors | `compute_route` | `AStarRouting.astar.py` | 162-163 | `predecessors = {}`, `predecessor_edges = {}` |
| Init priority queue | `compute_route` | `AStarRouting.astar.py` | 168 | `pq = [(f_score[source], source)]` |
| Init open and closed sets | `compute_route` | `AStarRouting.astar.py` | 170-171 | `in_open = {source}`, `closed = set()` |
| Main while loop | `compute_route` | `AStarRouting.astar.py` | 173 | `while pq:` loop start |
| Timeout check | `compute_route` | `AStarRouting.astar.py` | 175-187 | `time.perf_counter() - start_time > timeout_s` |
| Pop smallest from pq | `compute_route` | `AStarRouting.astar.py` | 189 | `_, current = heapq.heappop(pq)` |
| Remove from open set | `compute_route` | `AStarRouting.astar.py` | 190 | `in_open.discard(current)` |
| Skip stale/closed | `compute_route` | `AStarRouting.astar.py` | 193-194 | `if current in closed: continue` |
| Mark expanded | `compute_route` | `AStarRouting.astar.py` | 197-198 | `closed.add(current)`, `nodes_explored += 1` |
| Goal test | `compute_route` | `AStarRouting.astar.py` | 201-202 | `if current == destination: break` |
| Iterate outgoing edges | `compute_route` | `AStarRouting.astar.py` | 205 | `for edge in graph.outgoing_edges(current)` |
| Skip blocked edges | `compute_route` | `AStarRouting.astar.py` | 209 | `if edge.state.is_blocked: continue` |
| Compute edge cost | `compute_route` | `AStarRouting.astar.py` | 213 | `self._cost_calculator.compute_edge_cost(edge)` |
| Skip impassable | `compute_route` | `AStarRouting.astar.py` | 214-215 | `if edge_cost == float("inf"): continue` |
| Get neighbor | `compute_route` | `AStarRouting.astar.py` | 217 | `neighbor = edge.target` |
| Skip if closed | `compute_route` | `AStarRouting.astar.py` | 220-221 | `if neighbor in closed: continue` |
| Compute tentative g | `compute_route` | `AStarRouting.astar.py` | 223 | `tentative_g = g_score[current] + edge_cost` |
| Better path check | `compute_route` | `AStarRouting.astar.py` | 225 | `if neighbor not in g_score or tentative_g < g_score[neighbor]` |
| Update g_score | `compute_route` | `AStarRouting.astar.py` | 227 | `g_score[neighbor] = tentative_g` |
| Update predecessors | `compute_route` | `AStarRouting.astar.py` | 228-229 | `predecessors[neighbor] = current`, `predecessor_edges[neighbor] = edge.edge_id` |
| Compute heuristic estimate | `compute_route` | `AStarRouting.astar.py` | 231-233 | `h = self._heuristic.estimate(neighbor, destination, graph)` |
| Compute f-score | `compute_route` | `AStarRouting.astar.py` | 234 | `f = tentative_g + h` |
| Update f_score | `compute_route` | `AStarRouting.astar.py` | 235 | `f_score[neighbor] = f` |
| Push to heap | `compute_route` | `AStarRouting.astar.py` | 236 | `heapq.heappush(pq, (f, neighbor))` |
| Add to open set | `compute_route` | `AStarRouting.astar.py` | 237 | `in_open.add(neighbor)` |
| No path check | `compute_route` | `AStarRouting.astar.py` | 240-252 | `if destination not in closed: return no-path failure` |
| Store nodes_explored | `compute_route` | `AStarRouting.astar.py` | 255 | `self._last_nodes_explored = nodes_explored` |
| Init path reconstruction | `compute_route` | `AStarRouting.astar.py` | 258-260 | `path_nodes = []`, `path_edges = []`, `current = destination` |
| Backtrack loop | `compute_route` | `AStarRouting.astar.py` | 262-280 | Walk predecessors from destination to source |
| Reverse path | `compute_route` | `AStarRouting.astar.py` | 282-284 | `path_nodes.reverse()`, `path_edges.reverse()` |
| Build route and candidate | `compute_route` | `AStarRouting.astar.py` | 287-288 | `self._build_route(...)`, `self._build_candidate(...)` |
| Return result | `compute_route` | `AStarRouting.astar.py` | 292-303 | `RoutingResult(primary_route=route, ...)` |
| Heuristic estimate (Euclidean) | `estimate` | `EuclideanHeuristic.heuristic.py` | 126-144 | `sqrt(dx² + dy²) * scale` |
| Heuristic estimate (Manhattan) | `estimate` | `ManhattanHeuristic.heuristic.py` | 181-197 | `(|dx| + |dy|) * scale` |
| Heuristic estimate (Zero) | `estimate` | `ZeroHeuristic.heuristic.py` | 83-90 | Returns 0.0 |
| Heuristic factory | `create` | `HeuristicFactory.heuristic_factory.py` | 22-59 | Maps name string to heuristic instance |
| Per-edge cost computation | `compute_edge_cost` | `CompositeCostCalculator.cost_calculator.py` | 110-173 | Weighted cost from length, speed, congestion, penalties |
| Aggregated route cost | `compute_route_cost` | `CompositeCostCalculator.cost_calculator.py` | 175-230 | Summed per-edge costs with weights |
| Node coordinate access | `get_node` | `DirectedGraph.graph.py` | 159-165 | Returns Node with x, y attributes |
| Graph outgoing edges | `outgoing_edges` | `DirectedGraph.graph.py` | 185-192 | Returns tuple of Edge objects |
| Closed set membership | (built-in) | `AStarRouting.astar.py` | 193, 220, 240 | `set` for O(1) lookups |
| Open set membership | (built-in) | `AStarRouting.astar.py` | 170, 237 | `set` for O(1) operations |

## Verification (Part 2)

### Correctness assessment

**This is a genuine implementation of A\* search.**

1. **Closed set with consistent heuristic**: The algorithm uses a closed set (expanded nodes are never revisited). This is correct for **consistent** (monotone) heuristics. The Euclidean distance heuristic is consistent on a metric space with non-negative edge costs. The ZeroHeuristic is trivially consistent. The Manhattan heuristic is consistent for grid-like graphs.

   However, if a **non-consistent admissible** heuristic were injected, this implementation would NOT guarantee optimality. This is explicitly documented in the class docstring (lines 52-54): "If h is also consistent, A\* never needs to re-expand nodes." The `Heuristic` Protocol docstring also discusses admissibility and consistency requirements (lines 22-31 of `heuristic.py`).

2. **Goal test on expansion**: Line 201 (`if current == destination: break`) checks for the goal when a node is **expanded** (popped from pq and added to closed), not when it is **generated**. This is the standard A\* approach and guarantees optimality with a consistent heuristic.

3. **No shortcuts**: No hardcoded routes, no precomputed paths, no benchmark-specific logic. All routes are computed from scratch using the graph and cost calculator.

4. **No hardcoded decisions**: All routing decisions are based on edge cost (`CompositeCostCalculator.compute_edge_cost`) and heuristic estimate (`self._heuristic.estimate`). There is no case analysis for specific node IDs, edge IDs, or graph topologies.

5. **Edge relaxation correctness**: The tentative-g comparison (`if neighbor not in g_score or tentative_g < g_score[neighbor]`) correctly identifies better paths and updates f-score accordingly.

### Concerns found

1. **Dead code: `in_open` set (lines 170, 190, 237)**: The `in_open` set is maintained (added to at line 237, discarded at line 190, initialized at line 170) but **never queried** during the algorithm. The closed set (line 193, 220, 240) is the only set used for decisions. The `in_open` set tracks which nodes are currently in the priority queue but this information is not used. This is not a correctness issue — it is dead code that wastes a trivial amount of memory and time on discard/add operations. It appears to be a vestige from a design where open-set membership might be checked (common in textbook A\* to avoid re-adding nodes that are already in the open set with a different f-score, but the algorithm works correctly without it since it simply adds duplicate entries to pq with the new f-score).

2. **f_score dictionary is never read for decisions (line 235)**: The `f_score` dictionary is written to when a better path is found (line 235: `f_score[neighbor] = f`) but **never read back** for any decision. The priority queue `pq` is the only mechanism that determines which node to expand next. The `f_score` dict appears to be maintained as a convenience for debugging or logging but has no functional role. This is not a bug — it is auxiliary state that could be removed.

3. **Predecessor edge map potential inconsistency**: Same pattern as Dijkstra — `predecessors` and `predecessor_edges` are separate dicts updated in tandem but accessed independently in path reconstruction (lines 264-279). This is safe given the tandem update but is a latent fragility.

4. **Stale entries in pq**: The same node may be pushed to `pq` multiple times (once for each discovered path that improves g_score). Stale entries are silently skipped via the closed set check on line 193. This is standard lazy-deletion A\* practice and is correct.

**Overall**: A correct A\* implementation assuming consistent heuristics. The `in_open` set is dead code and the `f_score` dict is unused for decisions, but these do not affect correctness or output. The algorithm is a faithful reproduction of standard A\* with consistent-heuristic closed-set optimization.