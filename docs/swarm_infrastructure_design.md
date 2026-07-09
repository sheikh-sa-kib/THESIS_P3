# Swarm Infrastructure Implementation

**Status:** Phase 8B — Complete (implemented, tested, awaiting approval)

---

## 1. Overview

This document describes the implemented common swarm infrastructure that all swarm algorithms (ACO, BCO, PSO, E³-Hybrid) will build upon. The infrastructure was designed in Phase 8A and implemented in Phase 8B.

### Design Principles

- **Algorithm-agnostic:** No references to ACO, BCO, PSO, or E³-Hybrid anywhere in the framework
- **Immutable data models:** All shared structures are frozen dataclasses
- **Protocol-based interfaces:** `SwarmAlgorithm` Protocol for dependency injection
- **Deterministic randomness:** `SwarmRandom` with named sub-streams, no direct `random()` calls
- **Framework-managed termination:** `TerminationChecker` evaluates conditions, not algorithms
- **Adapter pattern:** `SwarmToRoutingAdapter` bridges swarm to routing without coupling

### Package Structure

```
src/e3hybrid/swarm/
├── __init__.py          # Public API exports
├── protocol.py          # SwarmAlgorithm Protocol
├── context.py           # SwarmContext (immutable optimization context)
├── config.py            # SwarmConfig (algorithm-agnostic configuration)
├── models.py            # Solution, CandidateSolution, OptimizationScore, SearchState, Population
├── state.py             # SwarmState (optimization state snapshot)
├── statistics.py        # SwarmStatistics, IterationStatistics
├── result.py            # SwarmResult (optimization result)
├── random.py            # SwarmRandom (deterministic seeded RNG)
├── termination.py       # TerminationCondition, TerminationChecker
├── lifecycle.py         # SwarmLifecycle (common iteration loop)
├── validator.py         # SwarmValidator, SwarmValidationReport
├── factory.py           # SwarmFactory (registration and creation)
└── adapter.py           # SwarmToRoutingAdapter (RoutingAlgorithm bridge)
```

---

## 2. Implemented Classes

### 2.1 SwarmAlgorithm Protocol

```python
class SwarmAlgorithm(Protocol):
    @property
    def name(self) -> str: ...
    def optimize(self, context: SwarmContext) -> SwarmResult: ...
```

Single-method Protocol. Every swarm algorithm implements exactly `optimize()`.
The framework handles lifecycle, termination, and statistics.

### 2.2 SwarmContext

Immutable context for a single optimization run:

| Field | Type | Description |
|-------|------|-------------|
| `cost_weights` | `CostWeights` | Component weights for fitness evaluation |
| `config` | `SwarmConfig` | Algorithm-agnostic configuration |
| `random_seed` | `int` | Base seed for deterministic RNG |
| `routing_request` | `RoutingRequest` | The routing request being solved |
| `sim_time_s` | `float` | Current simulation time |

### 2.3 SwarmConfig

Configuration with validation at construction:

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `algorithm_name` | `str` | `""` | Algorithm identifier |
| `population_size` | `int` | `10` | Number of individuals |
| `max_iterations` | `int` | `100` | Maximum iterations |
| `time_limit_s` | `float` | `0.0` | Wall-clock limit (0 = no limit) |
| `convergence_threshold` | `float` | `0.0` | Min improvement threshold |
| `stall_limit` | `int` | `10` | Stall iterations before convergence |
| `target_score` | `float` | `0.0` | Target score for early stop |
| `seed` | `int` | `42` | Random seed |
| `hyperparameters` | `Mapping[str, object]` | `{}` | Algorithm-specific params |
| `cost_weights` | `CostWeights` | distance=1.0 | Cost component weights |

### 2.4 Shared Models

**Solution:**
```
node_sequence: tuple[NodeId, ...]
edge_sequence: tuple[EdgeId, ...]
metadata: Mapping[str, object]
```
Properties: `source_node`, `destination_node`, `edge_count`

**CandidateSolution:**
```
solution: Solution
score: float
cost_breakdown: RouteCost | None
iteration_created: int
algorithm_specific: Mapping[str, object]
```

**OptimizationScore:**
```
total: float
components: Mapping[str, float]
normalized: float
rank: int
```

**SearchState:**
```
iteration: int
best_score: float
previous_best_score: float
no_improvement_count: int
diversity: float
elapsed_time_s: float
```

**Population:**
```
individuals: tuple[CandidateSolution, ...]
diversity: float
iteration: int
```
Properties: `size`, `best`, `average_score`, `worst_score`

### 2.5 SwarmStatistics

**SwarmStatistics** (run-level):
- `total_iterations`, `total_runtime_s`
- `best_score`, `average_score`, `worst_score`
- `convergence_iteration` (last iteration where best improved)
- `candidate_count`, `solutions_evaluated`
- `diversity_history`, `score_history`
- `termination_reason`

**IterationStatistics** (per-iteration):
- `iteration`, `best_score`, `average_score`, `midrange_score`
- `worst_score`, `std_dev`, `diversity`
- `best_solution_changed`, `runtime_s`

### 2.6 SwarmResult

```
best_solution: RouteCandidate
candidates: tuple[RouteCandidate, ...]
statistics: SwarmStatistics
iterations: tuple[IterationStatistics, ...]
success: bool
failure_reason: str | None
```

Post-init validation: success/failure_reason consistency enforced.

### 2.7 SwarmState

```
iteration: int
population: Population
best_solution: CandidateSolution | None
internal_state: Mapping[str, object]
```

`internal_state` provides an escape hatch for algorithm-specific data (pheromones, velocities, etc.) without breaking the shared interface.

### 2.8 SwarmRandom

```python
class SwarmRandom:
    def __init__(self, base_seed: int) -> None: ...
    def get_stream(self, name: str) -> random.Random: ...
    def reset(self) -> None: ...
    @property
    def base_seed(self) -> int: ...
```

- Derives named sub-streams deterministically from a base seed
- Each stream uses `hash(name) ^ base_seed` as its seed
- Adding new streams does not change existing stream sequences
- `reset()` clears cached streams for test isolation

### 2.9 TerminationCondition + TerminationChecker

**TerminationCondition:**
```
should_stop: bool
reason: str
iteration: int
elapsed_time_s: float
```

**TerminationChecker** evaluates conditions in priority order:
1. Maximum iterations reached
2. Time limit exceeded
3. Target score achieved
4. Convergence (improvement < threshold)
5. No improvement for stall_limit iterations
6. Continue (no condition triggered)

Each condition is independently testable. Conditions checked by framework, not algorithms.

### 2.10 SwarmLifecycle

Manages the common iteration loop. Callbacks for algorithm-specific steps:

```python
lifecycle = SwarmLifecycle(config)
result = lifecycle.run(
    context=context,
    initialize_fn=initialize,   # (context, config) -> Population
    update_fn=update,            # (context, config, population, best) -> Population
    extract_best_fn=extract,     # (population, prev_best) -> CandidateSolution
)
```

Lifecycle steps:
1. **Initialize:** Call initialize_fn to create initial population
2. **Record stats:** Compute iteration 0 statistics
3. **Check termination:** If triggered, return result
4. **Iterate:** For each iteration:
   a. Call update_fn to generate next population
   b. Extract best solution
   c. Update SearchState (track improvement)
   d. Record IterationStatistics
   e. Check termination
5. **Build result:** Convert final state to SwarmResult with RouteCandidate

### 2.11 SwarmValidator

Algorithm-independent checks:

| Method | Checks |
|--------|--------|
| `validate_config(config)` | algorithm_name non-empty, population_size > 0, max_iterations > 0, all limits non-negative |
| `validate_state(state)` | iteration >= 0, population non-empty, best_solution exists, score consistency |
| `validate_result(result)` | success/failure_reason consistency, statistics validity |
| `validate_population(population)` | non-empty, all scores non-negative, iteration >= 0 |

Returns `SwarmValidationReport` with `is_valid`, `errors`, `warnings`, `checks_performed`, `checks_passed`.

### 2.12 SwarmFactory

```python
SwarmFactory.register("aco", ACORouting)      # Phase 9
SwarmFactory.register("bco", BCORouting)      # Phase 10
SwarmFactory.register("pso", PSORouting)      # Phase 11

algo = SwarmFactory.create_algorithm("aco")
```

Runtime registration allows future algorithms without framework changes.

### 2.13 SwarmToRoutingAdapter

```python
adapter = SwarmToRoutingAdapter(swarm_algorithm, swarm_config)
result = adapter.compute_route(request, routing_context)
```

Converts `SwarmResult` → `RoutingResult`:
- `SwarmContext` built from routing request + metadata
- `RouteCandidate` extracted from best solution
- `RoutingStatistics` populated from swarm statistics
- Compatible with `BenchmarkRunner` without modifications

---

## 3. Optimization Lifecycle

```
Initialize (algorithm-specific)
    ↓
Record Iteration 0 Statistics (framework)
    ↓
Check Termination (framework)
    ↓── [stop] → Build Result (framework)
    │
    [continue]
    ↓
Iteration Loop:
    ├── Update Population (algorithm-specific)
    ├── Extract Best (algorithm-specific or default)
    ├── Update SearchState (framework)
    ├── Record IterationStatistics (framework)
    └── Check Termination (framework)
         ├── [stop] → Build Result
         └── [continue] → Next iteration
```

The framework handles: statistics, termination, result building.
Algorithms handle: initialization and population update only.

---

## 4. Serialization

All swarm models are frozen dataclasses with `slots=True`. They support:
- `dataclasses.asdict()` for dict conversion
- `json.dumps()` via dict conversion
- No custom serialization logic needed (pure dataclass fields)

RouteCandidate (from routing module) provides `to_dict()` for YAML/CSV export.

---

## 5. Extension Points

| Extension | What to Implement |
|-----------|-------------------|
| New swarm algorithm | `SwarmAlgorithm` Protocol + `SwarmFactory.register()` |
| New termination condition | Add check in `TerminationChecker.check()` |
| New validation rule | Add method in `SwarmValidator` |
| Custom best extraction | `extract_best_fn` parameter in `SwarmLifecycle.run()` |
| Custom statistics | Extend `IterationStatistics` or `SwarmStatistics` |

All extensions are backward-compatible. No existing code needs modification.

---

## 6. Complexity

| Operation | Complexity | Notes |
|-----------|------------|-------|
| SwarmLifecycle.run() | O(I × P × E) | I=iterations, P=population, E=edges per evaluation |
| SwarmRandom.get_stream() | O(1) | Dict lookup or seed derivation |
| TerminationChecker.check() | O(1) | 6 condition checks |
| Population.best | O(P) | Min scan over individuals |
| Population.average_score | O(P) | Sum over individuals |
| Validator.validate_config | O(1) | 8 field checks |
| Validator.validate_population | O(P) | Scan all individuals |

---

## 7. Testing

### Test Coverage

99 comprehensive unit tests across all components:

| Component | Tests | Coverage |
|-----------|-------|----------|
| Models (Solution, CandidateSolution, etc.) | 12 | 100% |
| Config (SwarmConfig) | 8 | 100% |
| Context (SwarmContext) | 4 | 100% |
| State (SwarmState) | 3 | 100% |
| Statistics | 5 | 96% |
| Result (SwarmResult) | 4 | 100% |
| Random (SwarmRandom) | 6 | 100% |
| Termination | 10 | 100% |
| Validator | 16 | 81% |
| Factory | 6 | 100% |
| Lifecycle | 5 | 74% |
| Adapter | 3 | 47% |
| Integration | 2 | — |

### What's Tested

- Immutability: all frozen dataclasses reject mutation
- Validation: constructor validation for all models
- Determinism: same seed → same results
- Stream isolation: named streams don't interfere
- Termination: each condition independently verified
- Lifecycle: iteration counting, score tracking, early termination
- Factory: registration, creation, error handling

### All 99 tests pass alongside 135 existing routing tests (234 total).

---

## 8. Design Rationale

### Why SwarmLifecycle Instead of Each Algorithm Managing Its Own Loop

The lifecycle is the same for all swarm algorithms: initialize, evaluate, update state, generate candidates, check termination. Extracting this into `SwarmLifecycle` eliminates duplicated code and ensures consistent termination, statistics, and error handling across all algorithms.

### Why Callbacks Instead of Inheritance

Callbacks (initialize_fn, update_fn) are preferred over abstract base class methods because:
- Algorithms don't need to inherit from a framework base class
- Unit testing lifecycle logic is easier without mocking inheritance
- The same lifecycle can be reused for different optimization patterns

### Why CandidateSolution.score Instead of RouteCost Directly

Swarm algorithms use a simple scalar score for comparison (fitness). `RouteCost` with its detailed breakdown is attached separately for result reporting. This separation keeps the optimization loop simple while preserving detailed cost analysis for thesis evaluation.

### Why SwarmState.internal_state Is a Generic Dict

Each swarm algorithm has unique internal state (pheromones, scout reports, velocities). Using `Mapping[str, object]` avoids type coupling while still providing deterministic snapshots for replay and debugging.

---

## 9. Files

| File | Lines | Purpose |
|------|-------|---------|
| `src/e3hybrid/swarm/__init__.py` | 53 | Public API exports |
| `src/e3hybrid/swarm/protocol.py` | 62 | SwarmAlgorithm Protocol |
| `src/e3hybrid/swarm/context.py` | 43 | SwarmContext |
| `src/e3hybrid/swarm/config.py` | 67 | SwarmConfig |
| `src/e3hybrid/swarm/models.py` | 136 | Shared data structures |
| `src/e3hybrid/swarm/state.py` | 37 | SwarmState |
| `src/e3hybrid/swarm/statistics.py` | 78 | SwarmStatistics, IterationStatistics |
| `src/e3hybrid/swarm/result.py` | 56 | SwarmResult |
| `src/e3hybrid/swarm/random.py` | 56 | SwarmRandom |
| `src/e3hybrid/swarm/termination.py` | 105 | TerminationCondition, TerminationChecker |
| `src/e3hybrid/swarm/lifecycle.py` | 259 | SwarmLifecycle |
| `src/e3hybrid/swarm/validator.py` | 296 | SwarmValidator, SwarmValidationReport |
| `src/e3hybrid/swarm/factory.py` | 86 | SwarmFactory |
| `src/e3hybrid/swarm/adapter.py` | 108 | SwarmToRoutingAdapter |
| `tests/unit/test_swarm_infrastructure.py` | 1125 | Comprehensive unit tests |
