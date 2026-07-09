# Dijkstra Algorithm — Dynamic EV Routing with SUMO

## 1. Purpose in this thesis

Dijkstra serves as the **reference shortest-path baseline** for all routing algorithms in the E3-Hybrid framework. Every other algorithm (A\*, ACO, BCO, PSO, E3-Hybrid) is compared against Dijkstra using identical `RoutingResult` structures. It establishes the gold standard for optimal path cost in the `RoutingAlgorithm` protocol and is the benchmark that heuristic search (A\*) and swarm-based methods must match or improve upon.

## 2. Theory actually implemented

The implementation in `dijkstra.py` follows the **classical label-setting Dijkstra algorithm** using a binary min-heap priority queue:

- Maintains a **distance map** `distances[node]` = shortest known cost from source to `node`
- Maintains a **predecessor map** `predecessors[node]` = previous node on the best path
- Maintains a **predecessor edge map** `predecessor_edges[node]` = edge ID used to reach `node`
- Maintains a **visited set** `visited` = nodes whose shortest distance is finalized
- Uses a **priority queue** (heapq) ordered by `(distance, node_id)`
- Only explores nodes reachable via unblocked edges with finite cost
- Terminates immediately when the destination node is popped from the priority queue (early exit)

The algorithm does **not** use a heuristic (unlike A\*). It computes pure g(n) = cost from source.

## 3. Inputs

| Input | Type | Source | Description |
|-------|------|--------|-------------|
| `request.source_node` | `NodeId` (str `NewType`) | `RoutingRequest` | Origin node, validated via `graph.has_node()` |
| `request.destination_node` | `NodeId` (str `NewType`) | `RoutingRequest` | Target node, validated via `graph.has_node()` |
| `request.timeout_s` | `float` | `RoutingRequest` | Maximum wall-clock runtime; timeout returns failure `RoutingResult` |
| `request.vehicle_id` | `VehicleId` | `RoutingRequest` | Vehicle identifier (for logging/cache key, not used in computation) |
| `request.vehicle_constraints` | `Any` | `RoutingRequest` | Operational limits (not used in current Dijkstra) |
| `request.battery_state` | `Any` | `RoutingRequest` | Battery snapshot (not used in current Dijkstra) |
| `request.max_candidates` | `int` | `RoutingRequest` | Maximum candidates (Dijkstra ignores this, always returns 1) |
| `graph` | `DirectedGraph | None` | External parameter (passed to `compute_route`) | The directed road network graph |
| `self._cost_calculator` | `CompositeCostCalculator` | Initialized in `__init__` with `CostWeights` | Computes weighted per-edge cost |

The `graph` is passed as a separate parameter (not part of `RoutingRequest`) to avoid circular imports.

## 4. Outputs

Returns a single `RoutingResult` (defined in `result.py`):

| Field | Type | Description |
|-------|------|-------------|
| `candidates` | `tuple[RouteCandidate, ...]` | Tuple with exactly 1 candidate on success, empty on failure |
| `primary_route` | `Route \| None` | Best `Route` on success, `None` on failure |
| `success` | `bool` | `True` if path found, `False` otherwise |
| `failure_reason` | `str \| None` | Human-readable failure explanation, or `None` on success |
| `statistics` | `RoutingStatistics` | `RoutingStatistics(nodes_explored, edges_explored, candidates_generated)` |
| `runtime_s` | `float` | `time.perf_counter()` delta from start to end |

Failure cases:
- **Source node missing**: `success=False`, `failure_reason="Source node X does not exist in graph"`
- **Destination node missing**: `success=False`, `failure_reason="Destination node Y does not exist in graph"`
- **Timeout**: `success=False`, `failure_reason="Routing exceeded timeout of Xs"`
- **No path**: `success=False`, `failure_reason="No path exists from X to Y"`
- **Path reconstruction failure**: `success=False`, `failure_reason="Path reconstruction failed"`

## 5. Configuration parameters (cost weights)

From `CostWeights` in `cost_calculator.py`:

| Parameter | Default | Description |
|-----------|---------|-------------|
| `distance` | 1.0 | Weight for physical distance cost (edge.length_m) |
| `time` | 1.0 | Weight for travel time cost (length_m / effective_speed × congestion_factor) |
| `energy` | 1.0 | Weight for energy cost (placeholder, always 0.0) |
| `congestion` | 1.0 | Weight for congestion penalty (congested_time - base_time) |
| `hazard` | 1.0 | Weight for hazard penalty (edge.state.hazard_penalty_s) |
| `emergency` | 1.0 | Weight for emergency penalty (edge.state.emergency_penalty_s) |
| `communication` | 1.0 | Weight for communication penalty (edge.state.communication_penalty_s) |

All weights must be non-negative (validated in `__post_init__`).

The `CompositeCostCalculator` (`cost_calculator.py:110-173`) computes the total edge cost as:

```
edge_cost = W_distance × length_m
          + W_time × (length_m / effective_speed × congestion_factor)
          + W_energy × 0.0
          + W_congestion × max((congested_time - base_time), 0)
          + W_hazard × hazard_penalty_s
          + W_emergency × emergency_penalty_s
          + W_communication × communication_penalty_s
```

## 6. Internal data structures

| Structure | Type | Scope | Purpose |
|-----------|------|-------|---------|
| `distances` | `dict[NodeId, float]` | `compute_route` | Shortest known cost from source to each node; initialized `{source: 0.0}` |
| `predecessors` | `dict[NodeId, NodeId]` | `compute_route` | Previous node on the current best path to each node for reconstruction |
| `predecessor_edges` | `dict[NodeId, EdgeId]` | `compute_route` | Edge ID used to reach each node on the best path for reconstruction |
| `visited` | `set[NodeId]` | `compute_route` | Nodes whose shortest distance is finalized (expanded from pq) |
| `pq` | `list[tuple[float, NodeId]]` | `compute_route` | Min-heap priority queue ordered by `(distance, node_id)` |
| `start_time` | `float` | `compute_route` | `time.perf_counter()` at start for timeout and runtime tracking |
| `nodes_explored` | `int` | `compute_route` | Counter incremented each time a node is popped and expanded |
| `edges_explored` | `int` | `compute_route` | Counter incremented each time an outgoing edge is examined |
| `path_nodes` | `list[NodeId]` | `compute_route` | Reconstructed node sequence (built in reverse, then reversed) |
| `path_edges` | `list[EdgeId]` | `compute_route` | Reconstructed edge sequence (built in reverse, then reversed) |

## 7. Step-by-step written algorithm

**`compute_route(request, graph)` method:**

1. **Validate graph**: If `graph is None`, raise `ValueError`.
2. **Initialize**: Record `start_time = time.perf_counter()`, set `nodes_explored = 0`, `edges_explored = 0`.
3. **Validate source node**: If `graph.has_node(request.source_node)` is `False`, return failure `RoutingResult` with `failure_reason` mentioning missing source node.
4. **Validate destination node**: If `graph.has_node(request.destination_node)` is `False`, return failure `RoutingResult` with `failure_reason` mentioning missing destination node.
5. **Initialize data structures**: Set `distances = {source: 0.0}`, `predecessors = {}`, `predecessor_edges = {}`, `visited = set()`. Push `(0.0, source)` onto `pq`.
6. **Main loop** — while `pq` is not empty:
   a. **Check timeout**: If `time.perf_counter() - start_time > request.timeout_s`, return timeout failure `RoutingResult`.
   b. **Pop smallest**: `current_distance, current_node = heapq.heappop(pq)`.
   c. **Skip stale entries**: If `current_node in visited`, `continue` (skip this entry).
   d. **Mark visited**: `visited.add(current_node)`, increment `nodes_explored`.
   e. **Goal test**: If `current_node == request.destination_node`, `break` (exit loop).
   f. **Explore edges**: For each `edge` in `graph.outgoing_edges(current_node)`:
      - Increment `edges_explored`.
      - **Skip blocked**: If `edge.state.is_blocked`, `continue`.
      - **Compute cost**: `edge_cost, _ = self._cost_calculator.compute_edge_cost(edge)`.
      - **Skip impassable**: If `edge_cost == float("inf")`, `continue`.
      - **Relax edge**: `neighbor = edge.target`, `new_distance = current_distance + edge_cost`.
      - **Better path found**: If `neighbor not in distances` or `new_distance < distances[neighbor]`:
        - Update `distances[neighbor] = new_distance`.
        - Set `predecessors[neighbor] = current_node`.
        - Set `predecessor_edges[neighbor] = edge.edge_id`.
        - Push `heapq.heappush(pq, (new_distance, neighbor))`.
7. **Check destination reached**: If `request.destination_node not in visited`, return "No path exists" failure `RoutingResult`.
8. **Reconstruct path**:
   a. `current = request.destination_node`.
   b. While `current != request.source_node`:
      - Append `current` to `path_nodes`.
      - If `current in predecessor_edges`, append `predecessor_edges[current]` to `path_edges`.
      - If `current in predecessors`, set `current = predecessors[current]`.
      - If neither (should not happen), return "Path reconstruction failed" failure `RoutingResult`.
   c. Append `request.source_node` to `path_nodes`.
   d. `path_nodes.reverse()`, `path_edges.reverse()`.
9. **Build route**: Call `self._build_route(path_nodes, path_edges, graph)` which computes total distance, travel time, and energy (energy is 0.0 placeholder).
10. **Build candidate**: Call `self._build_candidate(route, graph)` which computes total cost and cost breakdown via `self._cost_calculator.compute_route_cost(edges)`.
11. **Return success**: `RoutingResult` with `success=True`, `primary_route=route`, `candidates=(candidate,)`, `statistics`, `runtime_s`.

**`_build_route(path_nodes, path_edges, graph)` method:**

1. Initialize `total_distance_m = 0.0`, `total_time_s = 0.0`, `total_energy_kwh = 0.0`.
2. For each `edge_id` in `path_edges`:
   - `edge = graph.get_edge(edge_id)`.
   - `total_distance_m += edge.length_m`.
   - Compute effective speed: `edge.state.current_speed_mps` if not `None`, otherwise `edge.speed_limit_mps`.
   - If effective speed > 0, `total_time_s += edge.length_m / effective_speed`.
   - `total_energy_kwh += 0.0` (placeholder).
3. Return `Route` with `uuid.uuid4()` route_id, node/edge sequences as tuples, and computed totals.

**`_build_candidate(route, graph)` method:**

1. Resolve edge objects: `edges = [graph.get_edge(eid) for eid in route.edge_sequence]`.
2. Compute total cost: `total_cost, breakdown = self._cost_calculator.compute_route_cost(edges)`.
3. Build `RouteCost` from breakdown with all components in both typed fields and `components` dict.
4. Return `RouteCandidate` with `route_id`, sequences, `total_cost`, `cost_breakdown`, `algorithm="dijkstra"`, `search_statistics=SearchStatistics(iterations=0)`.

## 8. Clear implementation-level pseudocode

```
ALGORITHM DijkstraRouting:
    INPUT: request (RoutingRequest), graph (DirectedGraph or None)
    OUTPUT: RoutingResult

    METHOD __init__(cost_weights=None):
        IF cost_weights is None: cost_weights = CostWeights()
        self._cost_calculator = CompositeCostCalculator(cost_weights)

    METHOD compute_route(request, graph):
        IF graph is None: RAISE ValueError

        start_time = time.perf_counter()
        nodes_explored = 0
        edges_explored = 0

        IF NOT graph.has_node(request.source_node):
            RETURN RoutingResult(
                candidates=(), primary_route=None, success=False,
                failure_reason="Source node X does not exist in graph",
                statistics=RoutingStatistics(0, 0, 0),
                runtime_s=time.perf_counter() - start_time
            )

        IF NOT graph.has_node(request.destination_node):
            RETURN RoutingResult(
                candidates=(), primary_route=None, success=False,
                failure_reason="Destination node Y does not exist in graph",
                statistics=RoutingStatistics(0, 0, 0),
                runtime_s=time.perf_counter() - start_time
            )

        distances = {request.source_node: 0.0}
        predecessors = {}
        predecessor_edges = {}
        visited = {}
        pq = [(0.0, request.source_node)]    // min-heap of (distance, node_id)

        WHILE pq IS NOT EMPTY:
            IF time.perf_counter() - start_time > request.timeout_s:
                RETURN RoutingResult(
                    candidates=(), primary_route=None, success=False,
                    failure_reason="Routing exceeded timeout of Xs",
                    statistics=RoutingStatistics(nodes_explored, edges_explored, 0),
                    runtime_s=time.perf_counter() - start_time
                )

            current_distance, current_node = heapq.heappop(pq)

            IF current_node IN visited:              // stale priority-queue entry
                CONTINUE

            visited.ADD(current_node)
            nodes_explored += 1

            IF current_node == request.destination_node:
                BREAK

            FOR EACH edge IN graph.outgoing_edges(current_node):
                edges_explored += 1

                IF edge.state.is_blocked:              // skip impassable roads
                    CONTINUE

                edge_cost, _ = self._cost_calculator.compute_edge_cost(edge)

                IF edge_cost == float("inf"):        // impassable edge
                    CONTINUE

                neighbor = edge.target
                new_distance = current_distance + edge_cost

                IF (neighbor NOT IN distances) OR (new_distance < distances[neighbor]):
                    distances[neighbor] = new_distance
                    predecessors[neighbor] = current_node
                    predecessor_edges[neighbor] = edge.edge_id
                    heapq.heappush(pq, (new_distance, neighbor))

        IF request.destination_node NOT IN visited:
            RETURN RoutingResult(
                candidates=(), primary_route=None, success=False,
                failure_reason="No path exists from X to Y",
                statistics=RoutingStatistics(nodes_explored, edges_explored, 0),
                runtime_s=time.perf_counter() - start_time
            )

        // Path reconstruction (reverse traversal)
        path_nodes = []
        path_edges = []
        current = request.destination_node

        WHILE current != request.source_node:
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

        path_nodes.APPEND(request.source_node)
        path_nodes.REVERSE()
        path_edges.REVERSE()

        route = self._build_route(path_nodes, path_edges, graph)
        candidate = self._build_candidate(route, graph)

        runtime = time.perf_counter() - start_time

        RETURN RoutingResult(
            candidates=(candidate,), primary_route=route, success=True,
            failure_reason=None,
            statistics=RoutingStatistics(nodes_explored, edges_explored, 1),
            runtime_s-runtime
        )

    METHOD _build_route(path_nodes, path_edges, graph):
        total_distance_m = 0.0
        total_time_s = 0.0
        total_energy_kwh = 0.0

        FOR EACH edge_id IN path_edges:
            edge = graph.get_edge(edge_id)
            total_distance_m += edge.length_m
            IF edge.state.current_speed_mps IS NOT None:
                effective_speed = edge.state.current_speed_mps
            ELSE:
                effective_speed = edge.speed_limit_mps
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
            algorithm="dijkstra",
            search_statistics=SearchStatistics(iterations=0),
        )
```

## 9. Time complexity

`O((E + V) log V)` where V = number of nodes, E = number of edges.

- Each node is popped from the min-heap at most once (`O(V log V)` total for pops)
- Each edge is examined at most once (`O(E)` edge checks)
- Each edge relaxation may push a new entry onto the heap (`O(E log V)` total for pushes)
- Path reconstruction walks from destination to source (`O(V)`)

Analysis from the source code: The `while pq` loop (line 152), `heapq.heappop(pq)` (line 168), and `heapq.heappush(pq, ...)` (line 203) all confirm the heap-based complexity. The `visited` set (line 171) prevents re-expansion, ensuring each node is processed at most once.

## 10. Space complexity

`O(V)` for the main data structures:
- `distances` dict: at most V entries
- `predecessors` dict: at most V entries
- `predecessor_edges` dict: at most V entries
- `visited` set: at most V entries
- `pq` heap: at most V + E entries in worst case (may contain stale entries for already-visited nodes)

`O(V)` for the output data structures:
- `path_nodes` list: at most V nodes
- `path_edges` list: at most V - 1 edges
- `Route` and `RouteCandidate` objects: each `O(V)` due to node/edge sequences

## 11. Strengths

1. **Optimality guarantee**: Finds the true shortest path under non-negative edge weights (proven by the label-setting property of classical Dijkstra). The visited set ensures once a node is popped, its distance is minimal.

2. **Deterministic**: Given identical graph and cost weights, always produces the same path. The graph uses insertion-ordered dicts (`graph.py` line 79-87), heapq processes ties by node_id tuple ordering, and all data structures are dicts/sets with stable iteration order in CPython 3.7+.

3. **No randomness**: Zero stochastic elements — no randomness in algorithm or cost weights.

4. **Generality**: Works on any graph structure; no assumptions about road network topology.

5. **Reference standard**: Serves as the ground truth for all algorithm comparisons in the thesis framework.

6. **Timeout-safe**: Every loop iteration checks wall-clock timeout, preventing infinite loops.

7. **Graceful degradation**: Returns structured `RoutingResult` with `failure_reason` for all failure modes (missing source, missing destination, timeout, no path).

## 12. Weaknesses

1. **No heuristic guidance**: Expands nodes equally in all directions from the source, unlike A* which focuses search toward the destination.

2. **Single candidate**: Returns only one candidate route. The `max_candidates` parameter from `RoutingRequest` is ignored. Multi-path generation requires separate mechanisms (e.g., k-shortest paths).

3. **No energy awareness**: Energy computation in `_build_route` always returns 0.0 (line 303: `total_energy_kwh += 0.0`). Energy is estimated in `_build_candidate` only through the cost weights in `CompositeCostCalculator`, but `compute_edge_cost` also sets `energy_cost = 0.0` (line 144).

4. **No vehicle constraint integration**: `vehicle_constraints` and `battery_state` from `RoutingRequest` are not used in the computation.

5. **Predecessor edge map is separated from predecessor map**: The `predecessor_edges` dict maps `NodeId -> EdgeId` independently from `predecessors` (`NodeId -> NodeId`). This creates a potential inconsistency if one is updated without the other (though the code always updates both in tandem on line 201-202).

6. **No multi-objective optimization**: Single scalar cost function; cannot produce Pareto-optimal trade-offs between distance, time, energy, and penalties.

## 13. Why it was selected

1. **Baseline reference**: Dijkstra is the conventional standard shortest-path algorithm. It establishes the minimum cost that all other algorithms must match, enabling quantitative analysis of trade-offs in heuristic (A\*) and swarm-based approaches.

2. **Optimality guarantee**: Provides the theoretical lower bound for path cost, which is essential for evaluating whether approximate methods (ACO, BCO, PSO, E3-Hybrid) sacrifice optimality for computational efficiency or multi-path diversity.

3. **No configuration sensitivity**: Unlike A* (heuristic quality) or swarm algorithms (pheromone decay, particle velocity parameters), Dijkstra has no tunable parameters that affect correctness.

4. **Protocol compliance**: Satisfies the `RoutingAlgorithm` Protocol (`protocol.py`), enabling plug-and-play comparison via `BenchmarkRunner`.

## 14. How it interacts with the SUMO simulation

The interaction is indirect through the simulation pipeline:

1. **Network import**: SUMO road networks are imported into the `DirectedGraph` via `GraphImporter` (or `SumoNetworkAdapter`), creating nodes and edges with physical attributes (length, speed limit, lanes).

2. **State updates**: During simulation, `MutableEdgeState` on each `Edge` is updated by the SUMO bridge with real-time measurements:
   - `current_speed_mps`: Current flow speed from SUMO's edge mean speed measurement
   - `congestion_factor`: Derived from SUMO's lane occupancy or speed ratio
   - `is_blocked`: Set based on SUMO's edge blocking/detour events
   - `hazard_penalty_s`: Set from hazard event detectors
   - `emergency_penalty_s`: Set from emergency vehicle corridor activations

3. **Routing requests**: The Decision Engine creates `RoutingRequest` based on vehicle states and submits it to DijkstraRouting via the `RoutingAlgorithm` protocol.

4. **Route execution**: The returned `Route` (with node/edge sequences) is dispatched to the vehicle's SUMO controller, which issues TraCI commands to follow the computed path.

5. **Re-routing triggers**: After congestion or hazard events update edge states, the simulation loop can trigger re-routing requests, causing Dijkstra to recompute on the updated graph.

## 15. How it responds to congestion, road closures, and emergency events

The response is entirely through **edge state → edge cost** mapping in `CompositeCostCalculator.compute_edge_cost()`:

**Road closures (`edge.state.is_blocked`)**:
- Line 186: `if edge.state.is_blocked: continue` — blocked edges are unconditionally skipped. No path will use a blocked edge.

**Congestion (`edge.state.congestion_factor`)**:
- Line 139 of `cost_calculator.py`: `congested_time_s = base_time_s * edge.state.congestion_factor`
- A `congestion_factor` of 2.0 doubles the travel time cost, making congested edges more expensive.
- The `congestion_penalty` component (line 147) captures the excess time as a separate penalty.

**Hazard events (`edge.state.hazard_penalty_s`)**:
- Line 148 of `cost_calculator.py`: `hazard_penalty = edge.state.hazard_penalty_s`
- This additive penalty is included in the weighted linear total cost.

**Emergency corridors (`edge.state.emergency_penalty_s`)**:
- Line 149 of `cost_calculator.py`: `emergency_penalty = edge.state.emergency_penalty_s`
- This additive penalty is included in the weighted linear total cost.

**Communication disruption (`edge.state.communication_penalty_s`)**:
- Line 150 of `cost_calculator.py`: `communication_penalty = edge.state.communication_penalty_s`
- This additive penalty is included in the weighted linear total cost.

**Infinite cost (`edge_cost == float("inf")`)**:
- Line 193-194: Edges with infinite cost (e.g., effective speed ≤ 0 → `base_time_s = float("inf")` → weighted cost becomes infinite) are also skipped.

There is no dynamic re-planning within the algorithm itself — Dijkstra simply computes the shortest path on the current graph state. Re-routing is triggered externally.

## 16. How randomness is controlled

This algorithm has no randomness. There is no `random` module import, no `random.seed()`, and no stochastic decision in `compute_route`. The `uuid.uuid4()` used for `route_id` (line 306) is the only non-deterministic element, but it is purely cosmetic — it does not affect the route computation or candidate selection. All tie-breaking is determined by heapq's tuple comparison: if two nodes have equal distance, the tie is broken by NodeId string ordering.

## 17. Determinism and reproducibility notes

DijkstraRouting is fully deterministic given identical inputs:
- **Same graph** → same edges in same order from `outgoing_edges()` (deterministic by insertion-order dicts, `graph.py` lines 79-81)
- **Same cost weights** → same `edge_cost` from `CompositeCostCalculator`
- **Same source/destination** → same search path
- **Same graph state** → same edge blocking/congestion mapping

The only source of variance is `uuid.uuid4()` in `_build_route` (line 306), which generates a unique route ID. This does not affect the actual path found. For strict determinism comparisons (e.g., comparing algorithm cost), the `route_id` should be ignored.

Because the graph's `_outgoing` adjacency list preserves insertion order (`graph.py` line 82-83 uses list append, line 185-192 returns `tuple` with insertion order preserved), and `heapq` in CPython is deterministic for equal-priority entries (orders by the second tuple element, `node_id`), the algorithm produces identical results across runs.

## 18. Mapping between pseudocode and implementation

| Pseudocode Step | Method | Class/File | Line(s) | Description |
|---|---|---|---|---|
| Initialize CostCalculator | `__init__` | `DijkstraRouting.dijkstra.py` | 62-72 | Creates `CompositeCostCalculator` with `CostWeights` |
| Validate graph | `compute_route` | `DijkstraRouting.dijkstra.py` | 107-108 | Raises `ValueError` if graph is None |
| Start timer | `compute_route` | `DijkstraRouting.dijkstra.py` | 110 | `start_time = time.perf_counter()` |
| Init counters | `compute_route` | `DijkstraRouting.dijkstra.py` | 111-112 | `nodes_explored = 0`, `edges_explored = 0` |
| Validate source | `compute_route` | `DijkstraRouting.dijkstra.py` | 115-127 | `graph.has_node(source)`, returns failure if absent |
| Validate destination | `compute_route` | `DijkstraRouting.dijkstra.py` | 129-141 | `graph.has_node(dest)`, returns failure if absent |
| Init distances dict | `compute_route` | `DijkstraRouting.dijkstra.py` | 144 | `distances = {source: 0.0}` |
| Init predecessors | `compute_route` | `DijkstraRouting.dijkstra.py` | 145 | `predecessors = {}` |
| Init predecessor_edges | `compute_route` | `DijkstraRouting.dijkstra.py` | 146 | `predecessor_edges = {}` |
| Init visited set | `compute_route` | `DijkstraRouting.dijkstra.py` | 147 | `visited = set()` |
| Init priority queue | `compute_route` | `DijkstraRouting.dijkstra.py` | 150 | `pq = [(0.0, source)]` |
| Main while loop | `compute_route` | `DijkstraRouting.dijkstra.py` | 152 | `while pq:` loop start |
| Timeout check | `compute_route` | `DijkstraRouting.dijkstra.py` | 154-166 | `time.perf_counter() - start_time > timeout_s` |
| Pop smallest element | `compute_route` | `DijkstraRouting.dijkstra.py` | 168 | `current_distance, current_node = heapq.heappop(pq)` |
| Skip stale entries | `compute_route` | `DijkstraRouting.dijkstra.py` | 171-172 | `if current_node in visited: continue` |
| Mark visited | `compute_route` | `DijkstraRouting.dijkstra.py` | 174-175 | `visited.add(current_node)`, `nodes_explored += 1` |
| Goal test | `compute_route` | `DijkstraRouting.dijkstra.py` | 178-179 | `if current == destination: break` |
| Iterate outgoing edges | `compute_route` | `DijkstraRouting.dijkstra.py` | 182 | `for edge in graph.outgoing_edges(current_node)` |
| Skip blocked edges | `compute_route` | `DijkstraRouting.dijkstra.py` | 186-187 | `if edge.state.is_blocked: continue` |
| Compute edge cost | `compute_route` | `DijkstraRouting.dijkstra.py` | 190 | `self._cost_calculator.compute_edge_cost(edge)` |
| Skip impassable edges | `compute_route` | `DijkstraRouting.dijkstra.py` | 193-194 | `if edge_cost == float("inf"): continue` |
| Compute tentative distance | `compute_route` | `DijkstraRouting.dijkstra.py` | 196-197 | `new_distance = current_distance + edge_cost` |
| Relax edge | `compute_route` | `DijkstraRouting.dijkstra.py` | 199-203 | Check if better path, update distances/predecessors, push to heap |
| Update distances | `compute_route` | `DijkstraRouting.dijkstra.py` | 200 | `distances[neighbor] = new_distance` |
| Update predecessors | `compute_route` | `DijkstraRouting.dijkstra.py` | 201-202 | `predecessors[neighbor] = current`, `predecessor_edges[neighbor] = edge.edge_id` |
| Push to heap | `compute_route` | `DijkstraRouting.dijkstra.py` | 203 | `heapq.heappush(pq, (new_distance, neighbor))` |
| No path check | `compute_route` | `DijkstraRouting.dijkstra.py` | 206-218 | `if destination not in visited: return no-path failure` |
| Init reconstruction | `compute_route` | `DijkstraRouting.dijkstra.py` | 221-223 | `path_nodes = []`, `path_edges = []`, `current = destination` |
| Backtrack loop | `compute_route` | `DijkstraRouting.dijkstra.py` | 225-244 | `while current != source`: reconstruct by following predecessors |
| Reverse path | `compute_route` | `DijkstraRouting.dijkstra.py` | 246-248 | `path_nodes.reverse()`, `path_edges.reverse()` |
| Build route | `compute_route` | `DijkstraRouting.dijkstra.py` | 251-255 | `self._build_route(path_nodes, path_edges, graph)` |
| Build candidate | `compute_route` | `DijkstraRouting.dijkstra.py` | 258-261 | `self._build_candidate(route, graph)` |
| Record runtime | `compute_route` | `DijkstraRouting.dijkstra.py` | 263 | `runtime = time.perf_counter() - start_time` |
| Return result | `compute_route` | `DijkstraRouting.dijkstra.py` | 265-276 | `RoutingResult` with candidate, primary_route, success, etc. |
| Iterate edges for totals | `_build_route` | `DijkstraRouting.dijkstra.py` | 289-303 | Loop over path_edges, sum distance and time, energy = 0 |
| Compute effective speed | `_build_route` | `DijkstraRouting.dijkstra.py` | 294-297 | `current_speed_mps` or `speed_limit_mps` |
| Create Route | `_build_route` | `DijkstraRouting.dijkstra.py` | 305-312 | `Route(route_id=uuid..., ...)` |
| Resolve edge objects | `_build_candidate` | `DijkstraRouting.dijkstra.py` | 320 | `[graph.get_edge(eid) for eid in route.edge_sequence]` |
| Compute route cost | `_build_candidate` | `DijkstraRouting.dijkstra.py` | 321 | `self._cost_calculator.compute_route_cost(edges)` |
| Create candidate | `_build_candidate` | `DijkstraRouting.dijkstra.py` | 323-349 | `RouteCandidate` with cost breakdown and `SearchStatistics(0)` |
| Per-edge cost computation | `compute_edge_cost` | `CompositeCostCalculator.cost_calculator.py` | 110-173 | Computes weighted cost from edge.length_m, speed, congestion, penalties |
| Aggregated route cost | `compute_route_cost` | `CompositeCostCalculator.cost_calculator.py` | 175-230 | Sums per-edge costs, applies weights |
| Graph outgoing edges | `outgoing_edges` | `DirectedGraph.graph.py` | 185-192 | Returns tuple of Edge objects from adjacency list |
| Graph has_node | `has_node` | `DirectedGraph.graph.py` | 149-152 | `return node_id in self._nodes` |
| Graph get_edge | `get_edge` | `DirectedGraph.graph.py` | 167-173 | `return self._edges[edge_id]` |
| Edge structure | (class) | `Edge.edge.py` | 143-288 | `edge.state`, `edge.length_m`, `edge.speed_limit_mps`, `edge.target` |
| Mutable state | (class) | `MutableEdgeState.edge.py` | 48-127 | `is_blocked`, `current_speed_mps`, `congestion_factor`, etc. |
| CostWeights | (class) | `CostWeights.cost_calculator.py` | 12-57 | `distance`, `time`, `energy`, `congestion`, `hazard`, `emergency`, `communication` |

## Verification (Part 2)

### Correctness assessment

**This is a genuine, correct implementation of Dijkstra's algorithm.**

1. **Label-setting property**: The `visited` set ensures each node is expanded exactly once. When a node is popped from `pq`, its distance is the minimum possible because:
   - Edge weights are non-negative (guaranteed by `CostWeights.__post_init__` validation)
   - A node already in `visited` is skipped via `continue`
   - The `visited` check on line 171 prevents re-expansion, matching the classical invariant that popped nodes have finalized distance

   One minor concern: nodes may be pushed to `pq` multiple times with different distances (line 203 can push a new entry even if the node is already in `pq`). The `visited` check correctly handles stale entries, but the heap may contain multiple entries for the same node. This is standard practice (lazy deletion) but means the theoretical O(V + E log V) complexity holds in practice.

2. **No shortcuts**: There are no hardcoded routes, no precomputed paths, no cached results, no benchmark-specific logic, no special handling for test graphs.

3. **No hardcoded decisions**: All routing decisions are made by evaluating `edge_cost` from `CompositeCostCalculator`, which uses configurable weights and mutable edge state. There is no case analysis for specific node IDs, edge IDs, or graph sizes.

4. **Graph traversal correctness**: Uses `graph.outgoing_edges(current_node)` (line 182) which returns directed edges from the adjacency list. Path reconstruction walks `predecessors` from destination to source. Both match the classical algorithm.

5. **Cost computation correctness**: Edge costs are computed through `CompositeCostCalculator.compute_edge_cost()`, which respects all mutable state fields (blocked, congestion, hazards, emergencies). The cumulative path cost is `current_distance + edge_cost` (line 197).

### Concerns found

**Minor — Predecessor edge map potential inconsistency (line 228-230)**: The path reconstruction code at lines 225-244 accesses `predecessor_edges[current]` and `predecessors[current]` independently. If for some reason `current` is in `predecessors` but NOT in `predecessor_edges` (or vice versa), the reconstruction still works — but this is a latent fragility. Both dicts are always updated in tandem (lines 201-202), so this is not a real bug, but the reconstruction assumes both are complete.

**No concerns about correctness or integrity**. The implementation is a faithful, correct Dijkstra algorithm that handles all failure cases with structured error returns.