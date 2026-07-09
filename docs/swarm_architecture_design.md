# Swarm Architecture Design

**Status:** Phase 8A — Design document (awaiting approval). No implementation yet.

---

## 1. Research Motivation

### Why Common Abstractions

ACO, BCO, and PSO share a fundamental structure despite their different metaphors (ants, bees, particles). Each algorithm:

1. Maintains a **population** of candidate solutions
2. **Evaluates** each candidate against an objective function
3. **Updates internal state** based on evaluation results
4. **Generates new candidates** using updated state
5. **Iterates** until a termination condition is met

A shared framework captures this common lifecycle while allowing each algorithm to plug in its own optimization strategy. Without shared abstractions, the three swarm algorithms would evolve into three unrelated implementations with duplicated infrastructure (termination checking, statistics, parallelism, logging) — making them harder to maintain, compare, and extend.

### Fairness

A shared framework guarantees that:
- All algorithms receive identical termination conditions (same iteration limit, same timeout, same convergence criteria)
- All algorithms report identical statistics structures (same fields, same units, same precision)
- All algorithms interact with the routing layer through the same interfaces
- No algorithm can accidentally receive privileged information or bypass standard evaluation

Differences in performance are therefore attributable to the optimization strategy alone — not to infrastructure advantages.

### Maintainability

Common code lives in one place:
- Termination logic is written once, verified once, used by all algorithms
- Statistics collection is a single tested component
- Configuration parsing and validation is shared
- Logging and result serialization is uniform

Adding a bug fix to termination logic automatically benefits all swarm algorithms.

### Benchmarking

The `BenchmarkRunner` already works with any `RoutingAlgorithm`. By producing `RouteCandidate` objects compatible with the existing routing architecture, swarm algorithms are benchmarked automatically — no benchmark modifications needed.

### Future Extension

A new swarm algorithm (e.g., Firefly Algorithm, Cuckoo Search, Grey Wolf Optimizer) needs only to implement the `SwarmAlgorithm` Protocol. The framework handles population management, termination, statistics, and routing integration. This enables the framework to outlive the thesis and support future research.

---

## 2. Common Swarm Architecture

### 2.1 SwarmAlgorithm Protocol

```python
class SwarmAlgorithm(Protocol):
    """Interface that every swarm optimization algorithm must satisfy.

    Each algorithm implements ONLY its optimization strategy.
    The framework handles lifecycle, termination, statistics, and routing.
    """

    @property
    def name(self) -> str:
        """Stable algorithm name used in logs, metrics, and configuration."""
        ...

    def optimize(
        self,
        context: SwarmContext,
    ) -> SwarmResult:
        """Run the swarm optimization and return the best solution found.

        This is the ONLY method a swarm algorithm must implement.

        The algorithm receives a read-only context and returns a result.
        No side effects. No global state. Deterministic given same seed.
        """
        ...
```

### 2.2 SwarmContext

```python
@dataclass(frozen=True, slots=True)
class SwarmContext:
    """Immutable context provided to every swarm optimization.

    Contains all information needed for optimization without allowing
    modification. Analogous to RoutingContext for routing algorithms.
    """

    graph_snapshot: GraphSnapshot
    cost_provider: CostProvider
    config: SwarmConfig
    random_stream: random.Random
    routing_request: RoutingRequest
    sim_time_s: float
```

### 2.3 SwarmState

```python
@dataclass(frozen=True, slots=True)
class SwarmState:
    """Snapshot of swarm optimization state at a given iteration.

    Immutable for deterministic replay and auditability.
    """

    iteration: int
    population: tuple[CandidateSolution, ...]
    best_solution: CandidateSolution | None
    internal_state: Mapping[str, object]
    statistics: IterationStatistics
```

### 2.4 SwarmIteration

```python
@dataclass(frozen=True, slots=True)
class SwarmIteration:
    """Record of a single swarm iteration for logging and analysis."""

    iteration_number: int
    solutions_evaluated: int
    best_score: float
    average_score: float
    midrange_score: float
    worst_score: float
    diversity_measure: float
    runtime_s: float
```

### 2.5 SwarmStatistics

```python
@dataclass(frozen=True, slots=True)
class SwarmStatistics:
    """Aggregate statistics for a complete swarm optimization run."""

    total_iterations: int
    total_runtime_s: float
    best_score: float
    average_score: float
    worst_score: float
    convergence_iteration: int | None
    candidate_count: int
    solutions_evaluated: int
    diversity_history: tuple[float, ...]
    score_history: tuple[float, ...]
    termination_reason: str
```

### 2.6 SwarmResult

```python
@dataclass(frozen=True, slots=True)
class SwarmResult:
    """Result of a swarm optimization run.

    Compatible with the existing RoutingResult through conversion.
    The best_solution is always a valid RouteCandidate.
    """

    best_solution: RouteCandidate
    candidates: tuple[RouteCandidate, ...]
    statistics: SwarmStatistics
    iterations: tuple[SwarmIteration, ...]
    success: bool
    failure_reason: str | None
```

### 2.7 SwarmConfig

```python
@dataclass(frozen=True, slots=True)
class SwarmConfig:
    """Configuration for a swarm optimization run.

    Algorithm-specific hyperparameters are stored in the generic
    hyperparameters dict, keeping the config structure algorithm-agnostic.
    """

    algorithm_name: str
    population_size: int
    max_iterations: int
    time_limit_s: float
    convergence_threshold: float
    no_improvement_limit: int
    seed: int
    hyperparameters: Mapping[str, object]
    cost_weights: CostWeights
```

### 2.8 SwarmValidator

```python
class SwarmValidator:
    """Validates swarm configurations, states, and results.

    Algorithm-independent checks that apply to ACO, BCO, PSO, and any
    future swarm algorithm.
    """

    @staticmethod
    def validate_config(config: SwarmConfig) -> SwarmValidationReport:
        """Check config for structural validity (bounds, types, ranges)."""
        ...

    @staticmethod
    def validate_state(state: SwarmState) -> SwarmValidationReport:
        """Check state invariants (population size, score ranges, iteration)."""
        ...

    @staticmethod
    def validate_result(result: SwarmResult) -> SwarmValidationReport:
        """Check result consistency (scores, candidates, statistics)."""
        ...
```

### 2.9 SwarmFactory

```python
class SwarmFactory:
    """Creates swarm algorithms by name from configuration.

    Supports 'aco', 'bco', 'pso', and future algorithms.
    """

    @staticmethod
    def create_algorithm(
        name: str,
        config: SwarmConfig | None = None,
    ) -> SwarmAlgorithm:
        """Create a swarm algorithm by name.

        Raises ValueError for unknown algorithm names.
        """
        ...

    @staticmethod
    def available_algorithms() -> dict[str, str]:
        """Return mapping of algorithm names to descriptions."""
        ...
```

### 2.10 SwarmToRoutingAdapter

```python
class SwarmToRoutingAdapter:
    """Adapts SwarmAlgorithm to the RoutingAlgorithm Protocol.

    Allows any SwarmAlgorithm to be used wherever a RoutingAlgorithm is
    expected (e.g., BenchmarkRunner, DecisionEngine).
    """

    def __init__(self, swarm_algorithm: SwarmAlgorithm) -> None:
        self._swarm = swarm_algorithm

    @property
    def name(self) -> str:
        return self._swarm.name

    def compute_route(
        self,
        request: RoutingRequest,
        context: RoutingContext,
    ) -> RoutingResult:
        """Convert SwarmResult to RoutingResult."""
        ...
```

---

## 3. Common Optimization Lifecycle

Every swarm algorithm follows this lifecycle:

```
                    ┌─────────────────────────────┐
                    │       Initialize             │
                    │  (create initial population) │
                    └─────────────┬───────────────┘
                                  │
                                  ▼
                    ┌─────────────────────────────┐
                    │         Observe              │
                    │  (evaluate each candidate)   │
                    └─────────────┬───────────────┘
                                  │
                                  ▼
                    ┌─────────────────────────────┐
                    │        Evaluate              │
                    │  (compute fitness scores)    │
                    └─────────────┬───────────────┘
                                  │
                                  ▼
              ┌─────────────────────────────────────┐
              │      Update Internal State          │
              │  (pheromones, scout reports,        │
              │   particle velocities, best-known)  │
              └─────────────┬───────────────────────┘
                            │
                            ▼
              ┌─────────────────────────────────────┐
              │      Generate Candidate             │
              │  (produce new population from       │
              │   updated internal state)           │
              └─────────────┬───────────────────────┘
                            │
                            ▼
              ┌─────────────────────────────────────┐
              │      Check Termination              │
              │  (max iterations? timeout?          │
              │   converged? no improvement?)       │
              └─────────────┬───────────────────────┘
                            │
              ┌─────────────┴─────────────┐
              ▼                           ▼
        ┌───────────┐           ┌─────────────────┐
        │  Return   │           │   Repeat:        │
        │  Best     │           │   Observe →      │
        │  Solution │           │   Evaluate →     │
        └───────────┘           │   Update →       │
                                │   Generate       │
                                └─────────────────┘
```

### 3.1 Initialize

Each algorithm creates its initial population differently:
- **ACO:** Place ants at source node with initial pheromone levels
- **BCO:** Deploy scout bees for random exploration
- **PSO:** Initialize particles at random positions in solution space

All algorithms receive the same `SwarmContext` and produce a `SwarmState`.

### 3.2 Observe

Each candidate solution is evaluated against the current graph and cost provider. The evaluation produces a fitness score (total route cost). This step is identical across all algorithms — they all use the same `CostProvider` and `RoutingVerifier`.

### 3.3 Evaluate

Fitness scores are compared. The best solution so far is tracked. Per-iteration statistics are computed (best score, average score, diversity).

### 3.4 Update Internal State

Algorithm-specific state update:
- **ACO:** Evaporate pheromones, deposit pheromones on successful routes
- **BCO:** Update scout reports, employ bees at food sources, recruit onlookers
- **PSO:** Update personal bests, global best, adjust particle velocities

### 3.5 Generate Candidate

Each algorithm generates the next population:
- **ACO:** Ants construct routes using pheromone-guided probabilistic edge selection
- **BCO:** Scouts explore new regions, employed bees exploit known good routes
- **PSO:** Particles move through solution space with velocity-adjusted positions

### 3.6 Repeat

Continue until a termination condition is met (see Section 6).

### 3.7 Return Best Solution

The best solution found across all iterations is returned as a `SwarmResult`, which the `SwarmToRoutingAdapter` converts to a `RoutingResult`.

---

## 4. Shared Data Structures

### 4.1 Solution

```python
@dataclass(frozen=True, slots=True)
class Solution:
    """Base representation of a candidate route in swarm optimization.

    Algorithm-agnostic. ACO, BCO, and PSO all produce Solutions that
    are evaluated and compared using the same fitness function.
    """

    node_sequence: tuple[NodeId, ...]
    edge_sequence: tuple[EdgeId, ...]
    metadata: Mapping[str, object]
```

### 4.2 CandidateSolution

```python
@dataclass(frozen=True, slots=True)
class CandidateSolution:
    """A candidate solution with its evaluated fitness score.

    This is the core evaluation unit across all swarm algorithms.
    """

    solution: Solution
    score: float
    cost_breakdown: RouteCost
    iteration_created: int
    algorithm_specific: Mapping[str, object]
```

### 4.3 OptimizationScore

```python
@dataclass(frozen=True, slots=True)
class OptimizationScore:
    """Fitness value with detailed breakdown for analysis."""

    total: float
    components: Mapping[str, float]
    normalized: float
    rank: int
```

### 4.4 SearchState

```python
@dataclass(frozen=True, slots=True)
class SearchState:
    """Tracks the optimization progress across iterations.

    Updated every iteration. Used for convergence detection
    and termination decisions.
    """

    iteration: int
    best_score: float
    previous_best_score: float
    no_improvement_count: int
    diversity: float
    elapsed_time_s: float
```

### 4.5 IterationStatistics

```python
@dataclass(frozen=True, slots=True)
class IterationStatistics:
    """Per-iteration metrics for logging and analysis."""

    iteration: int
    best_score: float
    average_score: float
    midrange_score: float
    worst_score: float
    std_dev: float
    diversity: float
    best_solution_changed: bool
    runtime_s: float
```

### 4.6 TerminationCondition

```python
@dataclass(frozen=True, slots=True)
class TerminationCondition:
    """Signals whether optimization should continue or stop.

    Evaluated after each iteration by the framework.
    """

    should_stop: bool
    reason: str
    iteration: int
    elapsed_time_s: float

    @staticmethod
    def check(
        state: SearchState,
        config: SwarmConfig,
    ) -> TerminationCondition:
        """Evaluate all configured stopping conditions."""
        ...
```

### 4.7 Population

```python
@dataclass(frozen=True, slots=True)
class Population:
    """Generic population container used by all swarm algorithms.

    ACO: population = ants
    BCO: population = bees (scouts + employed + onlookers)
    PSO: population = particles
    """

    individuals: tuple[CandidateSolution, ...]
    diversity: float
    iteration: int
```

---

## 5. Randomness

### 5.1 Seeded Random Streams

All swarm algorithms must use the existing reproducibility framework. No direct `random.random()` or `random.choice()` calls are permitted.

```python
class SwarmRandom:
    """Deterministic random number generation for swarm algorithms.

    Derives named sub-streams from the base random_stream in SwarmContext.
    This ensures each stochastic component has its own deterministic
    sequence, and results are reproducible across runs with the same seed.
    """

    def __init__(self, base_stream: random.Random) -> None:
        self._base = base_stream
        self._streams: dict[str, random.Random] = {}

    def get_stream(self, name: str) -> random.Random:
        """Get or create a named sub-stream.

        Each stream is derived deterministically from the base seed.
        Example: SwarmRandom(base).get_stream("aco.ant_selection")
                 SwarmRandom(base).get_stream("bco.scout_direction")
                 SwarmRandom(base).get_stream("pso.velocity_noise")
        """
        if name not in self._streams:
            child_seed = self._base.randint(0, 2**31 - 1)
            # Combine base state with stream name hash for unique sequence
            name_hash = hash(name) & 0x7FFFFFFF
            self._streams[name] = random.Random(
                (child_seed ^ name_hash) & 0x7FFFFFFF
            )
        return self._streams[name]
```

### 5.2 Rules

- Every `SwarmContext` contains exactly one `random.Random` instance seeded by `RoutingContext.random_stream`
- Algorithms must use `SwarmRandom` for all stochastic decisions
- No global `random` module calls
- No `os.urandom`, `secrets`, or other entropy sources
- The same seed must produce identical results across platforms and Python versions

### 5.3 Stream Naming Convention

Named streams ensure that adding or removing a stochastic component in one algorithm does not change random sequences in another algorithm. The convention is:

```
<algorithm>.<component>.<purpose>
```

Examples:
- `aco.ant_selection` — ant k choosing next edge
- `aco.pheromone_deposit` — pheromone update noise
- `bco.scout_direction` — scout exploration direction
- `bco.onlooker_selection` — onlooker bee recruitment
- `pso.velocity_noise` — particle velocity perturbation
- `pso.initial_position` — particle initialization

---

## 6. Termination

### 6.1 Supported Stopping Conditions

| Condition | Config Field | Description |
|-----------|-------------|-------------|
| Maximum iterations | `max_iterations` | Stop after N iterations |
| Time limit | `time_limit_s` | Stop after T seconds |
| Solution convergence | `convergence_threshold` | Stop when `|best - previous_best| < ε` for K iterations |
| No improvement | `no_improvement_limit` | Stop when no improvement for N consecutive iterations |
| Target score | `target_score` | Stop when best score ≤ target (optional override) |

### 6.2 Termination Evaluation

```python
@dataclass(frozen=True, slots=True)
class TerminationChecker:
    """Evaluates all configured stopping conditions after each iteration.

    Checks are evaluated in order. The first condition that triggers
    determines the termination reason.
    """

    config: SwarmConfig
    start_time: float

    def check(self, state: SearchState) -> TerminationCondition:
        """Evaluate all conditions and return the result.

        1. Has max_iterations been reached?
        2. Has time_limit_s been exceeded?
        3. Has convergence_threshold been met?
        4. Has no_improvement_limit been reached?
        5. Has target_score been achieved?
        6. Otherwise, continue.
        """
        ...
```

### 6.3 Early Termination

Any condition can trigger early termination. The framework handles this uniformly — algorithms do not check termination themselves. The lifecycle loop:

```python
def optimize(self, context: SwarmContext) -> SwarmResult:
    state = self._initialize(context)
    checker = TerminationChecker(context.config, time.perf_counter())

    while True:
        condition = checker.check(state.search_state)
        if condition.should_stop:
            return self._build_result(
                state, condition, context
            )
        state = self._iteration(state, context)
```

---

## 7. Benchmark Fairness

### 7.1 Identical Conditions

Every swarm algorithm is benchmarked under identical conditions:

| Condition | Guarantee |
|-----------|-----------|
| **Graph** | Same `GraphSnapshot` used by all algorithms |
| **Requests** | Same `RoutingRequest` (source, destination, constraints) |
| **Seed** | Same base seed, same `SwarmRandom` derivation |
| **Population size** | Same `population_size` (configurable but equal across algorithms) |
| **Max iterations** | Same `max_iterations` |
| **Time limit** | Same `time_limit_s` |
| **Convergence** | Same `convergence_threshold`, same `no_improvement_limit` |
| **Cost provider** | Same `CostProvider` with same weights |
| **Hardware** | Same CPU, memory, OS (or hardware specs recorded) |
| **Metrics** | Same `SwarmStatistics` fields, same evaluation pipeline |

### 7.2 No Algorithm-Specific Advantages

- All algorithms use the same `CostProvider` — differences are due to optimization strategy, not cost computation
- All algorithms have the same iteration budget — no algorithm gets more time or iterations
- All algorithms report statistics through the same `SwarmStatistics` structure — no hidden metrics
- All algorithms produce `RouteCandidate` objects — the Decision Engine evaluates them identically

### 7.3 Benchmark Integration

The existing `BenchmarkRunner` works with swarm algorithms through `SwarmToRoutingAdapter`:

```python
aco_adapter = SwarmToRoutingAdapter(ACORouting())
bco_adapter = SwarmToRoutingAdapter(BCORouting())
pso_adapter = SwarmToRoutingAdapter(PSORouting())

config = BenchmarkConfig(algorithm_names=["aco", "bco", "pso"])
runner = BenchmarkRunner(config)
results = runner.run_scenario(scenario)
```

No modifications to `BenchmarkRunner` are needed.

---

## 8. Statistics

### 8.1 SwarmStatistics Fields

| Field | Type | Description | Collected How |
|-------|------|-------------|---------------|
| `total_iterations` | `int` | Number of iterations completed | Counter in lifecycle loop |
| `total_runtime_s` | `float` | Wall-clock time from start to end | `time.perf_counter()` delta |
| `best_score` | `float` | Minimum (best) score found | Tracked across all iterations |
| `average_score` | `float` | Mean score across all iterations | Averaged from iteration stats |
| `worst_score` | `float` | Maximum (worst) score encountered | Tracked across all iterations |
| `convergence_iteration` | `int | None` | Iteration when best score last improved | Tracked via `best_solution_changed` |
| `candidate_count` | `int` | Total unique candidates generated | Count of distinct solutions |
| `solutions_evaluated` | `int` | Total evaluations (candidates × iterations) | Population size × iterations |
| `diversity_history` | `tuple[float, ...]` | Population diversity per iteration | Computed per iteration |
| `score_history` | `tuple[float, ...]` | Best score per iteration | Recorded per iteration |
| `termination_reason` | `str` | Why optimization stopped | From `TerminationCondition.reason` |

### 8.2 IterationStatistics Fields

| Field | Type | Description |
|-------|------|-------------|
| `iteration` | `int` | Iteration number (0-indexed) |
| `best_score` | `float` | Best score in this iteration |
| `average_score` | `float` | Mean score of population |
| `midrange_score` | `float` | Midrange score (best+worst)/2 of population |
| `worst_score` | `float` | Worst score in population |
| `std_dev` | `float` | Standard deviation of scores |
| `diversity` | `float` | Population diversity metric (algorithm-defined) |
| `best_solution_changed` | `bool` | Whether global best improved this iteration |
| `runtime_s` | `float` | Time taken for this iteration |

### 8.3 Diversity Metric

Each algorithm defines its own diversity metric:
- **ACO:** Average pheromone variance across edges
- **BCO:** Ratio of scout-explored vs. employed-exploited regions
- **PSO:** Average pairwise distance between particles

All diversity measures are normalized to `[0, 1]` for comparability across algorithms.

---

## 9. Extension Strategy

### 9.1 Adding a New Swarm Algorithm

A new algorithm (e.g., Firefly Algorithm) requires:

1. **Implement `SwarmAlgorithm` Protocol:**
   ```python
   class FireflyRouting:
       @property
       def name(self) -> str: return "firefly"

       def optimize(self, context: SwarmContext) -> SwarmResult:
           # Only the optimization strategy
           ...
   ```

2. **Register in `SwarmFactory`:**
   ```python
   SwarmFactory.register("firefly", FireflyRouting)
   ```

3. **Use with existing infrastructure:**
   ```python
   adapter = SwarmToRoutingAdapter(FireflyRouting())
   result = adapter.compute_route(request, routing_context)
   ```

No modifications to:
- `SwarmContext`, `SwarmState`, `SwarmResult` — existing data structures suffice
- `SwarmValidator` — validation rules are algorithm-independent
- `TerminationChecker` — termination is handled by the framework
- `BenchmarkRunner` — adapter pattern makes any swarm algorithm a `RoutingAlgorithm`
- `DecisionEngine` — receives `RouteCandidate` objects, unaware of swarm origin

### 9.2 Adding a New Shared Component

If a new shared capability is needed (e.g., population seeding from file), it is added to the common framework and automatically available to all algorithms.

### 9.3 Algorithm-Specific Extensions

If an algorithm needs capabilities not covered by the shared structures, it can use the `internal_state` field in `SwarmState` and the `algorithm_specific` field in `CandidateSolution`. These generic containers provide escape hatches without breaking the shared interface.

---

## 10. Relationship to Routing

### 10.1 Integration with Routing Architecture

Swarm algorithms are **not routing algorithms**. They are **optimization algorithms** that produce routes. The distinction is important:

| Aspect | Routing Algorithm | Swarm Algorithm |
|--------|------------------|-----------------|
| Input | `RoutingRequest` + `RoutingContext` | `SwarmContext` |
| Output | `RoutingResult` | `SwarmResult` |
| Method | `compute_route()` | `optimize()` |
| Search | Single-pass (Dijkstra, A*) | Iterative (population-based) |
| State | Stateless | Maintains internal state across iterations |

### 10.2 SwarmToRoutingAdapter

The `SwarmToRoutingAdapter` bridges the two architectures:

```python
class SwarmToRoutingAdapter:
    """Adapts SwarmAlgorithm to RoutingAlgorithm Protocol."""

    def compute_route(
        self,
        request: RoutingRequest,
        context: RoutingContext,
    ) -> RoutingResult:
        # Build SwarmContext from RoutingContext
        swarm_context = SwarmContext(
            graph_snapshot=context.graph_snapshot,
            cost_provider=context.cost_provider,
            config=self._build_config(request, context),
            random_stream=context.random_stream,
            routing_request=request,
            sim_time_s=context.sim_time_s,
        )

        # Run swarm optimization
        swarm_result = self._swarm.optimize(swarm_context)

        # Convert SwarmResult to RoutingResult
        return RoutingResult(
            candidates=swarm_result.candidates,
            primary_route=(
                swarm_result.candidates[0]
                if swarm_result.candidates
                else None
            ),
            success=swarm_result.success,
            failure_reason=swarm_result.failure_reason,
            statistics=self._convert_statistics(swarm_result),
            runtime_s=swarm_result.statistics.total_runtime_s,
        )
```

### 10.3 RouteCandidate Production

Every swarm algorithm produces `RouteCandidate` objects:

```python
@dataclass(frozen=True, slots=True)
class RouteCandidate:
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

This ensures:
- The Decision Engine evaluates swarm routes identically to Dijkstra/A* routes
- The `RoutingVerifier` validates swarm routes without modification
- The `BenchmarkRunner` compares swarm algorithms against baselines fairly

### 10.4 No Bypass

Swarm algorithms must not:
- Access `DirectedGraph` directly (use `GraphSnapshot`)
- Call `CostProvider` bypass methods
- Modify graph state
- Produce routes that violate `RouteValidator` rules
- Return objects that are not valid `RouteCandidate` instances

---

## 11. Testing Strategy

### 11.1 Common Component Tests (Algorithm-Independent)

These tests validate the shared framework without any swarm algorithm:

| Test | Description |
|------|-------------|
| `SwarmConfig` validation | Bounds, types, required fields |
| `TerminationChecker` | Max iterations, timeout, convergence, no-improvement |
| `SwarmStatistics` | Aggregation, edge case (single iteration, empty population) |
| `SwarmRandom` | Determinism, stream isolation, seed derivation |
| `SwarmValidator` | Config, state, result validation rules |
| `SwarmToRoutingAdapter` | Conversion of SwarmResult → RoutingResult |
| `SwarmFactory` | Creation by name, unknown name error |
| `SwarmIteration` | Construction, field validation |
| `SearchState` | State transitions, convergence detection |

### 11.2 Algorithm-Specific Tests (Per Algorithm)

Each swarm algorithm (ACO, BCO, PSO) has its own test suite that validates:

- Correctness on known graphs
- Deterministic replay (same seed → same result)
- Termination condition adherence
- Integration with `SwarmToRoutingAdapter`
- Integration with `BenchmarkRunner`
- Edge cases (blocked edges, no-path, disconnected graph)

### 11.3 Integration Tests

- Full pipeline: `RoutingRequest` → `SwarmContext` → `SwarmAlgorithm.optimize()` → `SwarmToRoutingAdapter` → `RoutingResult`
- Benchmark integration: swarm algorithm runs via `BenchmarkRunner` without modification
- Verification: `RoutingVerifier` validates swarm-produced routes

### 11.4 Test Data

All swarm tests reuse the same graph fixtures from existing routing tests:
- `linear_graph` — simple path for correctness verification
- `grid_graph` — 3×3 grid for heuristic-based comparison
- `graph_with_blocked` — blocked edge for rerouting verification
- `graph_with_cycle` — cyclic graph for convergence testing
- `disconnected_graph` — no-path case for graceful failure

---

## 12. Open Questions

### Resolved in This Design

- **Common protocol:** `SwarmAlgorithm` Protocol with single `optimize()` method
- **Shared data structures:** `Solution`, `CandidateSolution`, `Population`, `SearchState`, `TerminationCondition`
- **Statistics:** `SwarmStatistics` (run-level) and `IterationStatistics` (per-iteration)
- **Termination:** Configurable conditions evaluated by framework, not algorithms
- **Randomness:** `SwarmRandom` with named sub-streams from `SwarmContext.random_stream`
- **Routing integration:** `SwarmToRoutingAdapter` converts `SwarmResult` → `RoutingResult`
- **Benchmarking:** Adapter pattern makes any swarm algorithm a `RoutingAlgorithm`
- **Validation:** `SwarmValidator` checks algorithm-independent invariants
- **Factory:** `SwarmFactory` creates algorithms by name with config

### Deferred to Implementation Phase

- **Exact hyperparameter ranges:** Will be determined during ACO, BCO, PSO implementation
- **Diversity metric formulas:** Each algorithm defines its own (normalized to [0,1])
- **Population seeding strategy:** Warm-start vs. random initialization per algorithm
- **Internal state serialization:** For checkpoint/resume in long-running experiments
- **Parallel evaluation:** Whether to evaluate candidates sequentially or in parallel

### Deferred to Future Phases

- **Hybrid coordination:** How E³-Hybrid combines ACO, BCO, and PSO state (Phase 12)
- **SUMO integration:** Real-time swarm adaptation in simulation (Phase 13)
- **Visualization:** Swarm metrics overlaid on road network (Phase 15)

### No Unresolved Architectural Questions

All major architectural decisions for the common swarm infrastructure are resolved in this document. The design is ready for implementation approval.
