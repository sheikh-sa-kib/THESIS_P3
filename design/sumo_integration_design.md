# Phase 13 — SUMO Integration Design

## 1. Objective

Integrate the E³-Hybrid framework with the **Simulation of Urban Mobility (SUMO)** via **TraCI** (Traffic Control Interface). The goal is to replace static benchmark graphs with live SUMO simulation scenarios, enabling:

- Time-varying traffic conditions (congestion, blockages, speed changes)
- Dynamic rerouting triggered by simulation events
- Emergency-vehicle preemption handling
- Fair multi-algorithm evaluation within the same simulation episode
- Deterministic replay across SUMO runs

## 2. Architecture Overview

```
┌──────────────────────────────────────────────────────────────────┐
│                        SUMO Engine                               │
│  ┌─────────────┐  ┌──────────────┐  ┌────────────────────────┐  │
│  │  Network     │  │  Traffic     │  │  Vehicle Movement      │  │
│  │  (.net.xml)  │  │  (.rou.xml)  │  │  (TraCI step loop)     │  │
│  └──────┬───────┘  └──────┬───────┘  └───────────┬────────────┘  │
│         │                 │                       │               │
└─────────┼─────────────────┼───────────────────────┼───────────────┘
          │                 │                       │
    ┌─────▼─────────────────▼───────────────────────▼──────────────┐
    │                   TraCI Connection                            │
    │         (libsumo / traci Python package)                       │
    └─────────────────────────┬─────────────────────────────────────┘
                              │
┌─────────────────────────────▼─────────────────────────────────────┐
│                    E³-Hybrid Simulation Layer                       │
│                                                                     │
│  ┌─────────────────┐    ┌──────────────────┐    ┌───────────────┐  │
│  │  SumoNetworkImporter│  │  SumoSimulation  │    │  SumoTraci    │  │
│  │  (.net.xml → graph)  │  │   (step loop)   │    │  (connection) │  │
│  └─────────┬─────────┘  └────────┬─────────┘    └───────┬───────┘  │
│            │                     │                      │          │
│            ▼                     ▼                      │          │
│  ┌─────────────────────────────────────────────────┐    │          │
│  │         RoutingAlgorithm Protocol                 │    │          │
│  │  (Dijkstra, A*, ACO, BCO, PSO, E³-Hybrid)        │    │          │
│  └─────────────────────┬───────────────────────────┘    │          │
│                        │                                │          │
│                        ▼                                │          │
│  ┌─────────────────────────────────────────────────┐    │          │
│  │          SumoReroutingManager                    │◄───┘          │
│  │  (decides when to reroute, feeds current graph)  │               │
│  └─────────────────────────────────────────────────┘               │
└─────────────────────────────────────────────────────────────────────┘
```

## 3. Module Boundaries

### 3.1 New Files

| File | Purpose | Lines (est.) |
|------|---------|-------------|
| `src/e3hybrid/sumo/__init__.py` | Package init, exports | 30 |
| `src/e3hybrid/sumo/config.py` | SumoConfig dataclass (network file, route file, timestep, reroute interval, etc.) | 80 |
| `src/e3hybrid/sumo/connection.py` | `SumoTraciConnection` — connect/disconnect, step, state getters | 120 |
| `src/e3hybrid/sumo/network_importer.py` | `SumoNetworkImporter` — SUMO `.net.xml` → `DirectedGraph` via TraCI | 200 |
| `src/e3hybrid/sumo/simulation.py` | `SumoSimulation` — main step loop, event handling, reroute trigger | 250 |
| `src/e3hybrid/sumo/rerouting_manager.py` | `SumoReroutingManager` — schedules and executes rerouting decisions | 180 |
| `src/e3hybrid/sumo/adapters.py` | `SumoRoutingAdapter` — wraps any `RoutingAlgorithm` for SUMO use | 100 |
| `src/e3hybrid/sumo/experiment_runner.py` | `SumoExperimentRunner` — orchestrates a full SUMO experiment | 150 |
| `tests/unit/test_sumo_connection.py` | TraCI connection tests (requires SUMO) | 100 |
| `tests/unit/test_sumo_network_importer.py` | Network import tests (requires SUMO) | 120 |
| `tests/unit/test_sumo_simulation.py` | Simulation lifecycle tests (mock TraCI) | 150 |
| `tests/unit/test_sumo_rerouting_manager.py` | Rerouting logic tests | 100 |
| **Total new** | **12 files** | **~1,480** |

### 3.2 Modified Files

| File | Change | Lines changed (est.) |
|------|--------|---------------------|
| `pyproject.toml` | Add `sumo` extra dependency (traci >= 1.20.0) | 2 |
| `src/e3hybrid/routing/factory.py` | Add `create_algorithm("sumo/sumo")` case | 5 |
| `src/e3hybrid/swarm/factory.py` | (no change — SUMO routes consume algorithms, doesn't register new swarm ones) | 0 |
| `src/e3hybrid/config/schemas.py` | Extend `SimulationConfig` with SUMO-specific fields | 30 |
| `src/e3hybrid/core/types.py` | (no change — existing types sufficient) | 0 |

### 3.3 No Changes To

- `RoutingAlgorithm` Protocol — SUMO adapters implement it
- `DirectedGraph` — SumoNetworkImporter builds it, no graph changes needed
- Any swarm algorithm (`aco.py`, `bco.py`, `pso.py`, `hybrid.py`) — they are consumed unchanged
- `SwarmToRoutingAdapter` — not needed; SUMO uses a dedicated `SumoRoutingAdapter`

## 4. Data Flow

### 4.1 Startup Phase

```
1. SumoExperimentRunner reads SumoConfig
2. SumoTraciConnection.start() → launches SUMO via traci.start()
3. SumoNetworkImporter.import_graph() → iterates TraCI edges/nodes → builds DirectedGraph
4. SumoNetworkImporter.import_dynamic_state() → reads initial traffic light states, blockages
5. All routing algorithms receive the same initial DirectedGraph
```

### 4.2 Step Loop (per simulation timestep)

```
for step in range(total_steps):
    1. SumoTraciConnection.step()          → traci.simulationStep()
    2. SumoSimulation.update_graph_state()  → TraCI to MutableEdgeState (congestion, speeds, blockages)
    3. SumoSimulation.check_events()        → emergency vehicle enters, road closure, etc.
    4. SumoReroutingManager.check_trigger() → should we reroute vehicles?
       If yes:
         a. Snapshot current graph (DirectedGraph with live state)
         b. For each vehicle to reroute:
            - Build RoutingRequest (current position as source, original destination)
            - Call algorithm.compute_route(request, graph=snapshot)
            - Send route via traci.vehicle.setRoute()
    5. Vehicle energy/emissions logging (optional)
```

### 4.3 Rerouting Lifecycle

```
trigger_event = (reroute_interval_elapsed OR emergency_detected OR significant_congestion_change)

1. Freeze: snapshot SUMO's current network state into a DirectedGraph copy
   (edge states: is_blocked, current_speed_mps, congestion_factor, travel_time_override_s)
2. Decide: SumoReroutingManager determines which vehicles to reroute
   - All vehicles that have deviated from original route
   - Vehicles expected to encounter a newly blocked edge
   - Emergency vehicles preempting routes (reroute surrounding vehicles away)
3. Compute: for each selected vehicle:
   - source = vehicle's current edge target node (via traci.vehicle.getRoadID + edge lookup)
   - destination = vehicle's original destination
   - constraints = vehicle's max speed, battery (via TraCI)
   - result = routing_algorithm.compute_route(request)
4. Apply: for each computed route:
   - traci.vehicle.setRoute(vehicle_id, [edge_id_0, edge_id_1, ...])
5. Log: record reroute event (time, vehicle, algorithm, old_route, new_route, reason)
```

## 5. TraCI Interaction

### 5.1 Required TraCI Calls

| Purpose | TraCI Command | Frequency | E³-Hybrid Mapping |
|---------|--------------|-----------|-------------------|
| Connect/launch | `traci.start(["sumo", "-c", "config.sumocfg"])` | Once | `SumoTraciConnection.start()` |
| Step | `traci.simulationStep()` | Every timestep | `SumoTraciConnection.step()` |
| Get edge travel time | `traci.edge.getTraveltime(edge_id)` | Every timestep | → `MutableEdgeState.travel_time_override_s` |
| Get edge speed | `traci.edge.getLastStepMeanSpeed(edge_id)` | Every timestep | → `MutableEdgeState.current_speed_mps` |
| Get edge occupancy | `traci.edge.getLastStepOccupancy(edge_id)` | Every timestep | → `MutableEdgeState.congestion_factor` |
| Check edge blocked | `traci.lane.getLastStepHaltingNumber(lane_id)` | Every timestep | → `MutableEdgeState.is_blocked` (heuristic: halting > threshold) |
| Set vehicle route | `traci.vehicle.setRoute(veh_id, [edge_ids])` | On reroute | → `SumoReroutingManager.apply_reroute()` |
| Get vehicle position | `traci.vehicle.getRoadID(veh_id)` | On reroute | → determine current edge |
| Get vehicle speed | `traci.vehicle.getSpeed(veh_id)` | On reroute | → constraints |
| Get vehicle battery | `traci.vehicle.getParameter(veh_id, "battery")` | On reroute | → battery_state |
| Get edges | `traci.edge.getIDList()` | Once at startup | → build `DirectedGraph` |
| Get edge info | `traci.edge.getEdge(edge_id)` | Once at startup | → build `Edge` objects |
| Get nodes | `traci.junction.getIDList()` | Once at startup | → build `Node` objects |
| Get node position | `traci.junction.getPosition(junction_id)` | Once at startup | → `Node.x`, `Node.y` |
| Disconnect | `traci.close()` | Once at end | `SumoTraciConnection.stop()` |

### 5.2 TraCI Mode

We use **libsumo** (in-process, no port) when available, falling back to **traci** (TCP socket, default port 8813). The connection abstraction encapsulates this choice:

```python
class SumoTraciConnection:
    def __init__(self, config: SumoConfig) -> None
    def start(self) -> None
    def step(self) -> int          # returns current simulation time (ms)
    def stop(self) -> None
    # State queries (delegate to traci/libsumo)
    def get_edge_travel_time(self, edge_id: str) -> float
    def get_edge_mean_speed(self, edge_id: str) -> float
    def get_edge_occupancy(self, edge_id: str) -> float
    def get_vehicle_route(self, vehicle_id: str) -> list[str]
    def set_vehicle_route(self, vehicle_id: str, edge_ids: list[str]) -> None
    ...
```

## 6. Graph State Synchronization

### 6.1 From SUMO to E³-Hybrid

After each `simulationStep()`, the `SumoSimulation` updates `MutableEdgeState` fields:

| DirectedGraph Edge State | SUMO Source | Transformation |
|--------------------------|-------------|----------------|
| `is_blocked` | `traci.lane.getLastStepHaltingNumber(lane_id) > halt_threshold` or `traci.edge.getTraveltime(edge_id) == None` (closed edge) | `bool` |
| `current_speed_mps` | `traci.edge.getLastStepMeanSpeed(edge_id)` | `float \| None` |
| `travel_time_override_s` | `traci.edge.getTraveltime(edge_id)` | `float \| None` (overrides computed cost) |
| `congestion_factor` | Derived from occupancy: `1.0 + occupancy / lane_capacity` | `float` |
| `hazard_penalty_s` | Emergency vehicle active on this edge → penalty | `float` |
| `emergency_penalty_s` | Emergency vehicle approaching → penalty | `float` |

### 6.2 Performance Consideration

Full graph state sync on every timestep is O(E). For a 10,000-edge network with 0.1s timestep, this is acceptable (~100K edge-reads/sec). If profiling shows bottlenecks, we introduce **lazy sync**: only edges in the vicinity of active vehicles are updated on each step, with a full sync every N steps.

### 6.3 Deterministic Execution

SUMO must be launched with `--seed N` and a fixed configuration file. The E³-Hybrid `SwarmRandom` must use a separate seed from SUMO's simulation seed. Both seeds are recorded in reproducibility metadata:

```python
@dataclass(frozen=True)
class SumoReproducibilityMetadata:
    sumo_version: str
    sumo_seed: int
    swarm_seed: int
    sumo_config_path: Path
    route_file_hash: str
```

## 7. Emergency-Event Handling

### 4.1 Detection

Emergency events are detected in the simulation loop via two mechanisms:

1. **Route-file markers**: Vehicles tagged as `type="emergency"` in `.rou.xml` are identified at startup.
2. **Dynamic events**: `traci.simulation.getCollisions()` or TraCI edge state changes (e.g., `traci.edge.adaptTraveltime(edge_id, 86400)` simulating a road closure).

### 7.2 Response

When an emergency event is detected:

1. **Block affected edges**: Set `is_blocked = True` on the edges the emergency vehicle traverses.
2. **Reroute surrounding vehicles**: `SumoReroutingManager` triggers immediate reroute for all vehicles that would use blocked edges (predicted via route lookahead).
3. **Clear routes for emergency**: Emergency vehicles get a priority route via `traci.vehicle.setRoute()` using the same routing algorithm, with modified `CostWeights` that heavily penalize congestion (emergency preemption).
4. **Restore after event**: When the emergency passes, edges are unblocked, and vehicles follow new routes computed on the restored graph.

## 8. Communication Update Frequency

The simulation step loop operates at a configurable interval (default: 1 simulation second = 1000 ms):

| Update | Frequency | Justification |
|--------|-----------|---------------|
| Graph state sync | Every step (default 1 s) | Congestion and blockages change rapidly in urban scenarios |
| Rerouting check | Every `reroute_interval` steps (default: 10 steps = 10 s) | Avoids route oscillation; aggregate reroutes for efficiency |
| Emergency event check | Every step | Must respond instantly |
| Logging / metrics | Every `logging_interval` steps (default: 60 steps = 60 s) | Sufficient for analysis |

The `reroute_interval` and `logging_interval` are configurable via `SumoConfig`.

## 9. Deterministic Execution

Determinism is guaranteed by:

1. **Fixed SUMO seed**: `sumo -c config.sumocfg --seed 42` ensures identical traffic flow.
2. **Fixed E³-Hybrid seed**: `SwarmRandom(seed)` separate from SUMO seed.
3. **Deterministic graph iteration**: `DirectedGraph` preserves insertion order (CPython 3.7+ dict guarantee).
4. **Fixed reroute interval**: Same simulation step → same triggers.
5. **Algorithm determinism**: All 6 algorithms (Dijkstra, A*, ACO, BCO, PSO, E³-Hybrid) are already deterministic given the same inputs.
6. **Recorded in metadata**: Both seeds, SUMO version, config hash, and route file hash are logged for replay.

## 10. Multi-Algorithm Evaluation

### 10.1 Single-Simulation Evaluation

All routing algorithms are evaluated within the **same SUMO simulation episode** using a **rolling-snapshot** approach:

```
Timestep 0:   SUMO starts, all vehicles follow initial SUMO-assigned routes
Timestep T1:  Snapshot graph state → run Dijkstra for vehicle subset A
Timestep T2:  Snapshot graph state → run A* for vehicle subset B
Timestep T3:  Snapshot graph state → run E³-Hybrid for vehicle subset C
...
```

Each vehicle is assigned to a single algorithm for the entire simulation. Vehicles are partitioned into groups (similar to population partitioning in E³-Hybrid). Each group has its routes computed by a different algorithm. Since all algorithms receive the same `RoutingRequest` + same snapshot graph, comparisons are fair.

### 10.2 Algorithm Implementation

```python
# SumoRoutingAdapter expects any RoutingAlgorithm:
from e3hybrid.routing.factory import RoutingFactory

algo = RoutingFactory.create_algorithm("e3hybrid")
# or "dijkstra", "astar", "aco", "bco", "pso"

adapter = SumoRoutingAdapter(algo, sumo_config)
adapter.run()  # Full SUMO simulation with this algorithm for this vehicle group
```

**No algorithm-specific code paths are needed.**

### 10.3 Vehicle Partitioning

Vehicle-to-algorithm assignment is configured in a YAML mapping:

```yaml
vehicle_algorithms:
  "dijkstra":  ["veh_0", "veh_1", "veh_2"]
  "e3hybrid":  ["veh_3", "veh_4", "veh_5"]
  "aco":       ["veh_6", "veh_7"]
```

Or proportional assignment:

```yaml
algorithm_split:
  "dijkstra":  0.2   # 20% of vehicles
  "astar":     0.1   # 10%
  "aco":       0.2
  "bco":       0.1
  "pso":       0.2
  "e3hybrid":  0.2
```

## 11. Performance Considerations

| Concern | Mitigation |
|---------|-----------|
| **TraCI latency** | Use `libsumo` (in-process) for sub-millisecond calls. Fallback to TCP `traci` only for remote/debugging. |
| **Graph state sync** | Lazy sync: update only edges near active vehicles. Full sync every N steps. |
| **Reroute cost** | Only reroute vehicles whose routes intersect changed edges (route lookahead, not all vehicles). |
| **Swarm algorithm cost** | Swarm algorithms are expensive (O(population × steps)). Mitigation: use small population (5-9) for live rerouting, larger for pre-computed reference routes. |
| **Memory** | Each snapshot `DirectedGraph` copy is a shallow clone (edges share `MutableEdgeState` objects). Only the edge state objects change between steps. |

## 12. Detailed Class Design

### 12.1 SumoConfig

```python
@dataclass(frozen=True, slots=True)
class SumoConfig:
    sumo_net_file: Path             # Path to .net.xml
    sumo_route_file: Path           # Path to .rou.xml
    sumo_additional_file: Path | None = None  # Optional .add.xml (detectors, etc.)
    sumo_seed: int = 42
    step_length_ms: int = 1000      # Timestep in milliseconds
    reroute_interval_steps: int = 10  # Reroute every N steps
    logging_interval_steps: int = 60
    use_gui: bool = False
    traci_port: int = 8813
    use_libsumo: bool = True        # Prefer in-process libsumo over TCP
```

### 12.2 SumoTraciConnection

```python
class SumoTraciConnection:
    """Low-level TraCI connection wrapper."""
    def __init__(self, config: SumoConfig) -> None
    def start(self) -> None          # traci.start() or libsumo.start()
    def step(self) -> int            # traci.simulationStep(), returns current time ms
    def stop(self) -> None           # traci.close()
    def get_simulation_time(self) -> int   # current time in ms
    # Edge queries
    def get_edge_ids(self) -> list[str]
    def get_edge_travel_time(self, edge_id: str) -> float
    def get_edge_mean_speed(self, edge_id: str) -> float
    def get_edge_occupancy(self, edge_id: str) -> float
    def get_edge_lane_count(self, edge_id: str) -> int
    def get_edge_length(self, edge_id: str) -> float
    def get_edge_speed_limit(self, edge_id: str) -> float
    def get_edge_shape(self, edge_id: str) -> list[tuple[float, float]]
    def is_edge_disconnected(self, edge_id: str) -> bool
    def get_edge_from_junction(self, edge_id: str) -> str
    def get_edge_to_junction(self, edge_id: str) -> str
    # Node queries
    def get_junctions(self) -> list[str]
    def get_junction_position(self, junction_id: str) -> tuple[float, float]
    # Vehicle queries
    def get_vehicle_ids(self) -> list[str]
    def get_vehicle_route(self, veh_id: str) -> list[str]
    def get_vehicle_position(self, veh_id: str) -> tuple[float, float, str]
    def get_vehicle_speed(self, veh_id: str) -> float
    def get_vehicle_type(self, veh_id: str) -> str
    def set_vehicle_route(self, veh_id: str, edge_ids: list[str]) -> None
    def get_vehicle_emissions(self, veh_id: str) -> dict
    # Emergency
    def subscribe_emergency_events(self) -> None
    def get_emergency_vehicles(self) -> list[str]
    # Collisions / blockages
    def get_collisions(self) -> list[dict]
```

### 12.3 SumoNetworkImporter

```python
class SumoNetworkImporter:
    """Converts a SUMO network into an E³-Hybrid DirectedGraph.
    
    Called once at startup. Produces a static graph (nodes + edges without
    dynamic state). Dynamic state is updated per timestep by SumoSimulation.
    """
    def __init__(self, connection: SumoTraciConnection) -> None
    
    def import_graph(
        self,
        graph_metadata: dict[str, object] | None = None,
    ) -> DirectedGraph:
        """Build complete DirectedGraph from SUMO network.
        
        Iterates all junctions → create Node objects
        Iterates all edges → create Edge objects with length_m, speed_limit_mps
        
        Edge state is initialized with defaults (no blockages, no congestion).
        """
        ...
    
    @staticmethod
    def _edge_to_metadata(edge_id: str, connection: SumoTraciConnection) -> dict:
        """Extract SUMO-specific metadata (lane count, shape, allowed vehicle types)."""
        ...
```

### 12.4 SumoSimulation

```python
class SumoSimulation:
    """Main simulation step loop.
    
    Owns the connection, the graph, the rerouting manager, and the event handlers.
    External consumers (experiment runner, metrics collector) observe via callbacks
    or by reading the graph state after each step.
    """
    def __init__(
        self,
        connection: SumoTraciConnection,
        config: SumoConfig,
        graph: DirectedGraph,
    ) -> None
    
    def step(self) -> int:
        """Advance one timestep. Returns current simulation time (ms)."""
    
    def run(self, total_steps: int) -> None:
        """Run the step loop for total_steps iterations."""
    
    @property
    def graph(self) -> DirectedGraph:
        """Return the current graph with up-to-date edge states."""
    
    def update_graph_state(self) -> None:
        """Pull dynamic state from SUMO → Edge MutableEdgeState."""
    
    def check_emergency(self) -> list[str]:
        """Return list of emergency vehicle IDs currently active."""
```

### 9.5 SumoReroutingManager

```python
class SumoReroutingManager:
    """Manages rerouting decisions and route updates.
    
    Decoupled from the simulation loop so it can be tested independently
    with mock graph states.
    """
    def __init__(
        self,
        connection: SumoTraciConnection,
        config: SumoConfig,
        algorithm: RoutingAlgorithm,
        vehicle_groups: dict[str, list[str]],    # algorithm_name → [vehicle_ids]
    ) -> None
    
    def should_reroute(self, step_count: int) -> bool:
        """Check if rerouting should occur based on interval or events."""
    
    def compute_reroute(
        self,
        vehicle_id: str,
        graph_snapshot: DirectedGraph,
    ) -> RoutingResult:
        """Compute a new route for a single vehicle."""
    
    def compute_reroutes(
        self,
        graph_snapshot: DirectedGraph,
    ) -> list[tuple[str, list[str]]]:
        """Compute routes for all vehicles that need rerouting.
        
        Returns list of (vehicle_id, new_edge_sequence).
        """
    
    def apply_reroute(self, vehicle_id: str, edge_ids: list[str]) -> None:
        """Set the vehicle's route in SUMO."""
```

### 12.6 SumoRoutingAdapter

```python
class SumoRoutingAdapter(RoutingAlgorithm):
    """Wraps any RoutingAlgorithm for SUMO-based route computation.
    
    The adapter satisfies the RoutingAlgorithm protocol and can be used
    anywhere a routing algorithm is expected (BenchmarkRunner, experiment scripts).
    
    Unlike SwarmToRoutingAdapter, this adapter does NOT call optimize() directly.
    Instead, it:
    1. Accepts a RoutingAlgorithm (Dijkstra, A*, ACO, BCO, PSO, E³-Hybrid)
    2. On compute_route(), builds the request and delegates to the wrapped algorithm
    3. The wrapped algorithm receives a DirectedGraph (imported from SUMO) and
       works exactly as it does in the static benchmark case.
    """
    def __init__(self, algorithm: RoutingAlgorithm) -> None
    @property
    def name(self) -> str: ...
    def compute_route(self, request: RoutingRequest) -> RoutingResult: ...
```

### 12.7 SumoExperimentRunner

```python
class SumoExperimentRunner:
    """Orchestrates a complete SUMO experiment.
    
    1. Load SumoConfig from file or Mapping
    2. Start SUMO via SumoTraciConnection
    3. Import network via SumoNetworkImporter
    4. Create routing algorithm instances via RoutingFactory
    5. Build vehicle-to-algorithm mapping
    6. Create SumoSimulation and SumoReroutingManager
    7. Run step loop
    8. Collect metrics
    9. Log results
    10. Shut down SUMO
    """
    def __init__(self, config: SumoConfig) -> None
    
    def run(
        self,
        algorithm_names: list[str],
        vehicle_algorithm_map: dict[str, list[str]],
    ) -> SumoExperimentResult:
        """Run the SUMO experiment with the given algorithm assignments."""
        ...
    
    @property
    def result(self) -> SumoExperimentResult | None:
        """Return collected experiment result (None if not yet run)."""
```

## 13. Testing Strategy

### 13.1 Unit Tests (mocked TraCI)

| Test Suite | File | Tests | Approach |
|-----------|------|-------|----------|
| Connection lifecycle | `test_sumo_connection.py` | 8 | Mock `traci.start/step/close`; verify correct calls |
| Network import | `test_sumo_network_importer.py` | 10 | Mock TraCI edge/junction data; verify `DirectedGraph` structure |
| Graph state sync | `test_sumo_simulation.py` | 6 | Mock TraCI speed/occupancy responses; verify `MutableEdgeState` |
| Rerouting trigger | `test_sumo_rerouting_manager.py` | 8 | Mock should_reroute, compute_reroute with known graph snapshot |
| Rerouting application | `test_sumo_rerouting_manager.py` | 6 | Mock `traci.vehicle.setRoute`; verify correct edge sequences |
| Emergency handling | `test_sumo_simulation.py` | 6 | Mock emergency vehicle detection; verify edge blocking |
| Adapter | `test_sumo_adapters.py` | 4 | Mock RoutingAlgorithm; verify protocol compliance |
| Experiment runner | `test_sumo_experiment_runner.py` | 4 | Mock all components; verify lifecycle |
| Deterministic replay | `test_sumo_determinism.py` | 3 | Same seed → same routes; different seed → different |
| **Total** | | **55** | |

### 13.2 Integration Tests (live SUMO binary required)

| Test | File | Description |
|------|------|-------------|
| Basic step loop | `tests/integration/test_sumo_basic.py` | Start SUMO empty; run 100 steps; verify no errors |
| Network import | `tests/integration/test_sumo_network.py` | Import known network; verify node/edge counts |
| Reroute | `tests/integration/test_sumo_reroute.py` | Inject vehicle; reroute mid-simulation; verify new route |
| Emergency | `tests/integration/test_sumo_emergency.py` | Emergency vehicle enters; verify surrounding vehicles rerouted |
| All 6 algorithms | `tests/integration/test_sumo_all_algorithms.py` | Run all 6 algorithms in same simulation; verify no crash |
| Deterministic | `tests/integration/test_sumo_determinism.py` | Run twice with same seed; verify identical tripinfo |

### 13.3 Mock Strategy

TraCI is mocked using `unittest.mock.patch` at the `import traci` or `import libsumo` level. Since `SumoTraciConnection` encapsulates all TraCI calls, a single mock patch over the connection is sufficient for unit tests:

```python
@pytest.fixture
def mock_connection():
    with patch("src.e3hybrid.sumo.traci.start") as mock_start:
        with patch("src.e3hybrid.sumo.traci.simulationStep") as mock_step:
            with patch("src.e3hybrid.sumo.traci.close") as mock_close:
                # Configure mock TraCI responses
                mock_step.return_value = 42  # simulation time
                yield
```

## 14. Acceptance Criteria

| # | Criterion | Verification |
|---|-----------|-------------|
| 1 | SUMO connects and steps correctly | Test: connection start/stop lifecycle |
| 2 | Full DirectedGraph imported from SUMO network | Test: node count, edge count, edge attributes match source |
| 3 | Graph state updates every timestep | Test: after step, edge state reflects TraCI data |
| 4 | Rerouting triggers at configurable intervals | Test: should_reroute returns True at interval boundaries |
| 5 | Rerouting produces valid routes | Test: computed route reaches destination within SIM |
| 6 | Routes are applied to SUMO vehicles | Test: traci.vehicle.setRoute called with correct edge IDs |
| 7 | Emergency vehicles trigger surrounding reroutes | Test: vehicles near emergency edge get new routes |
| 8 | All 6 algorithms work without code paths | Test: create all 6 via RoutingFactory, run all in same simulation |
| 9 | Deterministic replay (same seed → identical) | Test: two runs with same seed produce same tripinfo |
| 10 | Deterministic replay (different seed → different) | Test: two runs with different seeds produce different results |
| 11 | No circular imports | Test: load `e3hybrid.sumo` module tree without error |
| 12 | Coverage ≥85% for sumo/ module | pytest --cov |

## 15. Migration Path

### Phase 13a — Core (dependencies + connection + network import)
1. Add `traci>=1.20.0` to `pyproject.toml` dependencies
2. Implement `SumoConfig`, `SumoTraciConnection`, `SumoNetworkImporter`
3. Unit tests with mocked TraCI
4. Integration test with a real SUMO binary and a minimal 2x2 grid network

### Phase 13b — Simulation Loop (step loop + graph sync + rerouting)
1. Implement `SumoSimulation`, `SumoReroutingManager`
2. Implement `SumoRoutingAdapter`, `SumoExperimentRunner`
3. Unit tests with mocked TraCI
4. Integration tests with a simple SUMO scenario (linear route, one reroute)

### Phase 13c — Emergency (event handling)
1. Implement emergency detection in `SumoSimulation.check_emergency()`
2. Implement emergency response in `SumoReroutingManager`
3. Integration test with emergency vehicle in route file

### Phase 13d — Determinism + Full Integration
1. Deterministic replay tests (same seed / different seed)
2. Full 6-algorithm test (all algorithms in one simulation)
3. Coverage measurement, final acceptance check