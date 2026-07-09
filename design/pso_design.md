# PSO Design — Constructive Discrete Particle Swarm Optimization for Dynamic EV Routing

**Phase:** 10C  
**Status:** Design (pre-implementation)  
**Target:** `src/e3hybrid/swarm/pso.py` + `tests/unit/test_pso.py`  
**Architecture:** SwarmAlgorithm Protocol → SwarmFactory → SwarmToRoutingAdapter  
**Design authority:** Matches BCO architecture exactly; both implement the same `SwarmAlgorithm` Protocol, use the same validation pattern, forward/backward pass structure, result building, and lifecycle integration.

---

## 1. Literature Review and Variant Justification

### 1.1 Canonical PSO

Particle Swarm Optimization was introduced by Kennedy and Eberhart (1995) for continuous optimisation. Each particle *i* at iteration *t* has:

- A **position** vector **x**ᵢ(t) ∈ ℝⁿ (candidate solution)
- A **velocity** vector **v**ᵢ(t) ∈ ℝⁿ (direction and magnitude of movement)

At each iteration, velocity and position are updated as:

**v**ᵢ(t+1) = ω **v**ᵢ(t) + φ₁r₁(**p**ᵢ − **x**ᵢ(t)) + φ₂r₂(**g** − **x**ᵢ(t))&emsp;&emsp;(1)  

**x**ᵢ(t+1) = **x**ᵢ(t) + **v**ᵢ(t+1)&emsp;&emsp;(2)

where **p**ᵢ is the particle's personal best position, **g** is the global best position, ω is the inertia weight (Shi & Eberhart, 1998), φ₁ and φ₂ are cognitive and social acceleration coefficients, and r₁, r₂ ∈ [0, 1] are independent uniform random variates.

### 1.2 Constructive Discrete PSO for Routing Problems

Shortest-path routing in a directed graph is a **discrete combinatorial optimisation problem** — the solution space is the set of all source-to-destination paths, which is finite but exponential. **No continuous position or velocity vector can directly represent a path in a graph.** This implementation therefore uses a **constructive discrete adaptation** of PSO.

**Primary reference:** Mohemmed, A. W., Sahoo, N. C., & Geok, T. K. (2008). Solving shortest path problem using particle swarm optimization. *Applied Soft Computing*, 8(4), 1643–1653.

**Secondary references:**
- Clerc, M. (2004). Discrete Particle Swarm Optimization, illustrated by the Traveling Salesman Problem. *New Optimization Techniques in Engineering*, Springer, 219–239.
- Shi, Y., & Eberhart, R. C. (1998). A modified particle swarm optimizer. *Proceedings of IEEE CEC*, 69–73.

### 1.3 How This Is a Discrete Adaptation

The canonical PSO velocity equation (1) has four terms — an inertia term, a cognitive term, a social term, and (implicitly) the current position — that together determine the next position. In our constructive discrete PSO, **no velocity vector is maintained**. Instead, the *effect* of each PSO term is represented as a probabilistic edge-selection weight during route construction:

| PSO Concept | Continuous Expression (Eq 1) | Discrete Representation |
|---|---|---|
| **Inertia** | ω **v**ᵢ(t) | ω × *I*(e, *k*): attraction to staying on the current route at position *k* |
| **Cognitive** | φ₁r₁(**p**ᵢ − **x**ᵢ(t)) | c₁ × *P*(e, *k*): attraction toward the personal best route at position *k* |
| **Social** | φ₂r₂(**g** − **x**ᵢ(t)) | c₂ × *G*(e, *k*): attraction toward the global best route at position *k* |
| **Total position update** | **x**ᵢ(t+1) = **x**ᵢ(t) + **v**ᵢ(t+1) | Build new route edge-by-edge using weighted selection |

Each of the three weight components (*I*, *P*, *G*) acts as a position "difference" — it has value 1 when the candidate edge matches the reference route at the current construction step *k*, and a small constant ε otherwise. This is the discrete analogue of the vector difference (**p**ᵢ − **x**ᵢ) in Eq (1). The resulting probability distribution (normalised weights) replaces the explicit velocity.

### 1.4 Relationship to BCO

The discrete PSO approach shares the iterative constructive-feedback loop with BCO. Both use:
- Forward pass: construct routes for all individuals
- Backward pass: evaluate, update best solutions, compute diversity
- Same termination, statistics, result building pipeline

Key differences from BCO:
- **No loyalty/recruitment phase** — particles influence each other only through the shared g_best.
- **Inertia weight decays deterministically** — exploration decreases over time per equation (5).
- **Each particle tracks its own personal best** (p_best) — a second memory mechanism not present in BCO (BCO only tracks the global best and templates from loyal bees).

---

## 2. Mathematical Formulation

### 2.1 Notation

| Symbol | Meaning |
|---|---|
| *P* | Swarm size (number of particles) |
| *T* | Maximum iterations |
| *G* = (*V*, *E*) | Directed graph with nodes *V* and edges *E* |
| *s* ∈ *V* | Source node |
| *d* ∈ *V* | Destination node |
| **r**ᵢ(t) | Route (ordered edge sequence) of particle *i* at iteration *t* |
| **b**ᵢ(t) | Personal best route of particle *i* up to iteration *t* |
| **g**(t) | Global best route across all particles up to iteration *t* |
| *f*(**x**) | Cost of route **x** (sum of edge costs) |
| ω(t) | Inertia weight at iteration *t* |
| ω_start | Initial inertia weight |
| ω_end | Final inertia weight |
| c₁ | Cognitive (personal best) coefficient |
| c₂ | Social (global best) coefficient |
| c₃ | Visibility (heuristic) coefficient |
| ε | Small positive constant for non-matching edges |
| η(e) | Heuristic visibility of edge *e* |

### 2.2 Particle Representation (maps to `ParticleState` dataclass)

Each particle *i* at iteration *t* is defined by the tuple:

**P**ᵢ(t) = ⟨**r**ᵢ(t), *c*ᵢ(t), **b**ᵢ(t), *c*ᵢ*(t), σᵢ(t), *V*ᵢ(t)⟩&emsp;&emsp;(3)

where:
- **r**ᵢ(t) = [e₀, e₁, …, e_{K−1}] is the current route (ordered edge sequence)
- *c*ᵢ(t) = *f*(**r**ᵢ(t)) is the total cost of the current route
- **b**ᵢ(t) is the personal best route so far
- *c*ᵢ*(t) = *f*(**b**ᵢ(t)) is the personal best cost
- σᵢ(t) ∈ {CONSTRUCTING, COMPLETE, FAILED} is the particle state
- *V*ᵢ(t) ⊆ *V* is the set of visited nodes in the current route

### 2.3 Global Best (maps to `self._global_best_cost` / `self._global_best_route`)

**g**(t) = arg min_{i} *c*ᵢ*(t)&emsp;&emsp;(4)

i.e., the route with the minimum cost across all particles' personal bests.

### 2.4 Inertia Schedule — Linear Decay (maps to `_compute_inertia_weight()`)

ω(t) = ω_start − (ω_start − ω_end) × (t / T)&emsp;&emsp;(5)

Following Shi & Eberhart (1998), who showed that linearly decreasing inertia from ~0.9 to ~0.4 balances global exploration (early) with local exploitation (late).

### 2.5 Route Construction — Discrete Position Update (maps to `_construct_route()`)

For each particle *i* at iteration *t*, a new route **r**ᵢ(t+1) is constructed edge-by-edge starting from source *s*. **No velocity vector is maintained.** Instead, at each construction step *k*, the selection probability for each candidate edge is a weighted combination of four components that discretely encode the three PSO forces.

Let *v* be the current node. The set of feasible candidate edges is:

*C*(v) = {e ∈ *N*(v) | target(e) ∉ *V*ᵢ, e.state.is_blocked = False, cost(e) < ∞}&emsp;&emsp;(6)

If *C*(v) = ∅ and *v* ≠ *d*, the particle is marked FAILED.

For each candidate edge *e* ∈ *C*(v) at step *k*, the selection weight is:

*w*(e, k) = ω(t) × *I*(e, k) + c₁ × *P*(e, k) + c₂ × *G*(e, k) + c₃ × η(e)&emsp;&emsp;(7)

where each component is defined as:

**Inertia component** (maps to `I()` helper): attraction to the step-corresponding edge of the current route.

*I*(e, k) = 1 if *k* < |**r**ᵢ(t)| and e = **r**ᵢ(t)[k], otherwise ε&emsp;&emsp;(8)

This is the discrete analogue of ω **v**ᵢ(t) in Eq (1) — it biases the particle toward its current position (route). The match-on-step-index encoding is the discrete equivalent of the velocity vector direction.

**Cognitive component** (maps to `P()` helper): attraction to the step-corresponding edge of the personal best route.

*P*(e, k) = 1 if *k* < |**b**ᵢ(t)| and e = **b**ᵢ(t)[k], otherwise ε&emsp;&emsp;(9)

This is the discrete analogue of φ₁r₁(**p**ᵢ − **x**ᵢ(t)) — it pulls the particle toward its own best-known position.

**Social component** (maps to `G()` helper): attraction to the step-corresponding edge of the global best route.

*G*(e, k) = 1 if *k* < |**g**(t)| and e = **g**(t)[k], otherwise ε&emsp;&emsp;(10)

This is the discrete analogue of φ₂r₂(**g** − **x**ᵢ(t)) — it pulls the particle toward the swarm's best-known position.

**Visibility component** (maps to `VisibilityCache`): heuristic edge-cost attraction.

η(e) = 1 / (cost(e) + ε)&emsp;&emsp;(11)

This extra term — not present in the continuous PSO — is needed because the discrete route construction must evaluate candidate edges incrementally; the heuristic guides selection in the absence of a differentiable cost landscape. Same formulation as BCO's eta.

The probability of selecting edge *e* is:

*p*(e, k) = *w*(e, k) / Σ_{e′∈*C*(v)} *w*(e′, k)&emsp;&emsp;(12)

Selection is performed via roulette-wheel (same as BCO's `_compute_selection_probs` + roulette in `_forward_pass`).

### 2.6 Particle Update (maps to `_evaluate_particle()`)

After constructing the new route **r**ᵢ(t+1):

*c*ᵢ(t+1) = *f*(**r**ᵢ(t+1)) = Σ_{e ∈ **r**ᵢ(t+1)} cost(e)&emsp;&emsp;(13)

### 2.7 Personal Best Update (maps to `_update_personal_best()`)

**b**ᵢ(t+1) = **r**ᵢ(t+1), &emsp;if *c*ᵢ(t+1) < *c*ᵢ*(t)  
**b**ᵢ(t+1) = **b**ᵢ(t), &emsp;otherwise&emsp;&emsp;(14)

### 2.8 Global Best Update (maps to `_update_global_best()`)

**g**(t+1) = **b**ᵢ(t+1), &emsp;if *c*ᵢ*(t+1) < *g*(t) for any *i*  
**g**(t+1) = **g**(t), &emsp;otherwise&emsp;&emsp;(15)

### 2.9 Diversity (maps to `_compute_diversity()`)

Same Jaccard-based formula as BCO. Let *S*ᵢ = {edges in **b**ᵢ(t)} be the edge set of each particle's personal best:

div(t) = 1 − (2 / (*P*(*P*−1))) × Σ_{i<j} |*S*ᵢ ∩ *S*ⱼ| / |*S*ᵢ ∪ *S*ⱼ|&emsp;&emsp;(16)

---

## 3. Architecture (matches BCO exactly)

### 3.1 File: `src/e3hybrid/swarm/pso.py`

```
ParticleStatus(Enum)              — CONSTRUCTING, COMPLETE, FAILED (mirrors BeeStatus)
@dataclass ParticleState           — mutable particle state (mirrors BeeState)
@dataclass PSOStatistics          — per-iteration frozen statistics (mirrors BCOStatistics)
@dataclass(frozen=True, slots=True)
    PSOConfiguration              — hyperparameter container with _validate() (mirrors BCOConfiguration)

class PSOValidator:
    @staticmethod validate_context(context) → list[str]
    @staticmethod validate_config(config, population_size) → list[str]

class PSORouting:               — main algorithm class (mirrors BCORouting)
    __init__(): identical fields: _particles, _visibility, _swarm_rng, _config,
                _context, _global_best_cost, _global_best_route, _iteration_stats,
                _graph, _cost_calculator, _source, _destination
    name → "pso"
    optimize(context) → SwarmResult   — identical structure to BCORouting.optimize()
    _initialize(config)                 — config validation (extracted for clarity; called from optimize)
    _build_visibility()              — identical to BCO's
    _edge_total_cost(edge) → float — identical to BCO's
    _compute_inertia(iteration, max_iterations) → float — Eq (5)
    _construct_route(...) → list[EdgeId] — Eq (6)-(12), roulette via SwarmRandom
    _evaluate_particle(ParticleState) — Eq (13)-(14)
    _forward_pass(iteration, inertia) → (routes, costs, states) — same pattern as BCO
    _backward_pass(routes, costs, states) → (best_cost, best_route, diversity) — Eq (14)-(16)
    _compute_diversity() → float   — Eq (16), identical logic to BCO's
    _build_swarm_result(...) → SwarmResult — identical structure to BCO
    _route_to_candidate(edges, runtime) → RouteCandidate — identical structure to BCO
    _build_iteration_stats() → list[IterationStatistics] — identical structure to BCO
    _find_convergence_iteration() → int | None — identical logic to BCO
    _failure_result(reason) → SwarmResult — identical to BCO

# Auto-register with SwarmFactory — identical pattern
from e3hybrid.swarm.factory import SwarmFactory
SwarmFactory.register("pso", PSORouting)
```

### 3.2 Naming Conventions (exact match with BCO)

| BCO Name | PSO Name | Rationale |
|---|---|---|
| `BeeStatus` | `ParticleStatus` | Enum for individual state |
| `BeeState` | `ParticleState` | Dataclass for individual state |
| `_bees` | `_particles` | Population list |
| `BCOConfiguration` | `PSOConfiguration` | Hyperparameter config |
| `BCOStatistics` | `PSOStatistics` | Per-iteration stats |
| `BCOValidator` | `PSOValidator` | Context/config validation |
| `_forward_pass` | `_forward_pass` | Route construction |
| `_backward_pass` | `_backward_pass` | Evaluation + update |
| `_compute_diversity` | `_compute_diversity` | Swarm diversity |
| `_build_swarm_result` | `_build_swarm_result` | Result construction |
| `_route_to_candidate` | `_route_to_candidate` | Edge → RouteCandidate |
| `_build_iteration_stats` | `_build_iteration_stats` | Iteration → IterationStatistics |
| `_find_convergence_iteration` | `_find_convergence_iteration` | Convergence detection |
| `_failure_result` | `_failure_result` | Error result |

### 3.3 Helpers: `I(e, k)`, `P(e, k)`, `G(e, k)` (inline in `_construct_route`)

These are implemented as inline computations within `_construct_route()`, mirroring how `BCO._compute_selection_probs()` computes `eta ** beta` and `(1 + delta)` inline. The three helpers are:
- `I(e, k)` = Eq (8): inline if-check against current route at step k
- `P(e, k)` = Eq (9): inline if-check against p_best route at step k
- `G(e, k)` = Eq (10): inline if-check against g_best route at step k

They are internal helper methods `_I(self, edge, step, route)`, `_P(self, edge, step, route)`, `_G(self, edge, step, route)` to avoid repeated len/range calculations.

---

## 4. Initialisation (standard constructive builder, no arbitrary heuristic)

Particles are initialised using a standard constructive route builder — the **same generic forward-pass route builder used at every iteration**, but with a special `_initialize=True` flag that treats the current route as empty (so inertia has no effect, since there is no prior route to be attracted to). This avoids introducing any arbitrary heuristic.

Specifically, `_initialize()` sets `self._particles = []` then for each *i*, calls:

```
route = self._construct_route(
    source, destination,
    current_route=[],           // empty — effect: I(e,k)=ε for all edges
    p_best_route=[],             // empty — effect: P(e,k)=ε for all edges  
    g_best_route=[],           // empty — effect: G(e,k)=ε for all edges
    inertia=0.0,                // zeroed — no inertia on init
    cognition=0.0,             // zeroed — no cognitive on init
    social=0.0,                // zeroed — no social on init
    visibility=c₃,          // full visibility weight
    stream=roulette_stream,
)
```

This yields a pure visibility-guided construction for the initial population, with stochastic diversification from roulette selection. This is equivalent to the **BCO initialization pattern** where initial bee routes are constructed with no template (all selection probability derives from visibility alone).

**Justification:** This is not an arbitrary heuristic — it is the same route construction algorithm used throughout the optimization, operating with no priors. This matches Mohemmed et al. (2008) who initialize particles with random feasible paths, and matches BCO where initial bees construct routes with no template guidance.

---

## 5. Configuration Schema

| Hyperparameter Key | Type | Default | Valid Range | Eq Ref | BCO Equivalent |
|---|---|---|---|---|---|
| `inertia_start` | float | 0.9 | [0.0, 1.0] | (5) | — |
| `inertia_end` | float | 0.4 | [0.0, inertia_start] | (5) | — |
| `cognition_weight` | float | 2.0 | ≥ 0.0 | (7) | — |
| `social_weight` | float | 2.0 | ≥ 0.0 | (7) | — |
| `visibility_weight` | float | 1.0 | ≥ 0.0 | (7) | beta (visibility exponent) |
| `epsilon` | float | 1e-10 | (0.0, 1.0] | (8-10) | _EPS (module-level constant) |
| `forward_steps` | int | 100 | ≥ 1 | — | forward_steps (same meaning) |

**`PSOConfiguration._validate()` rules** (mirrors `BCOConfiguration._validate()` structure):

```python
def _validate(self, population_size: int) -> None:
    if self.forward_steps < 1:
        raise ValueError("forward_steps must be >= 1")
    if not 0.0 <= self.epsilon <= 1.0:
        raise ValueError("epsilon must be in [0, 1]")
    if self.inertia_start < self.inertia_end:
        raise ValueError("inertia_start must be >= inertia_end")
    if not 0.0 <= self.inertia_end <= self.inertia_start <= 1.0:
        raise ValueError("inertia weights must be in [0, 1] with start >= end")
    if self.cognition_weight < 0:
        raise ValueError("cognition_weight must be >= 0")
    if self.social_weight < 0:
        raise ValueError("social_weight must be >= 0")
    if self.visibility_weight < 0:
        raise ValueError("visibility_weight must be >= 0")
    if population_size < 2:
        raise ValueError("population_size must be >= 2")
    if self.cognition_weight + self.social_weight + self.visibility_weight <= 0:
        raise ValueError(
            "at least one of cognition, social, or visibility weight must be > 0"
        )
```

---

## 6. Deterministic Execution

All stochastic decisions route through `SwarmRandom` named streams:

| Stream Name | Used By | Eq Ref |
|---|---|---|
| `pso.init` | `_initialize()` — initial greedy-construct roulette | init |
| `pso.selection` | `_construct_route()` — roulette selection | (12) |

**Determinism guarantee:** Given the same `SwarmContext.random_seed`, same graph, same configuration, and same cost calculator, `optimize()` produces an identical `SwarmResult` across runs. This holds because:
1. `SwarmRandom.get_stream("pso.selection")` derives a deterministic `random.Random` from the base seed.
2. The stream is the sole source of randomness.
3. No global state, no time-based seeds, no external entropy.

---

## 8. Lifecycle Integration

Same as BCO and ACO: `optimize()` handles its own iteration loop (`_forward_pass` / `_backward_pass` / termination / result). No `SwarmLifecycle` — BCO and ACO both use the same self-contained iteration pattern. Auto-registration, adapter wrapping, and exports follow the established pattern.

---

## 9. Mapping: Equations → Python (exhaustive)

| Eq | Python Method/Variable | Notes |
|---|---|---|
| (3) | `ParticleState` dataclass | route, cost, p_best_route, p_best_cost, state, visited |
| (4) | `min(p.p_best_cost for p in self._particles)` | Global best extraction |
| (5) | `self._compute_inertia(iteration, max_iters)` | Linear decay |
| (6) | `if e.target not in visited and not e.state.is_blocked and isfinite(_edge_total_cost(e))` | Feasibility filter |
| (7) | `w_inertia + w_cognitive + w_social + w_visibility` | Total weight per particle step |
| (8) | `self._I(e.edge_id, k, current_route)` | Inertia match at step |
| (9) | `self._P(e.edge_id, k, p_best_route)` | Cognitive match at step |
| (10) | `self._G(e.edge_id, k, g_best_route)` | Social match at step |
| (11) | `self._visibility.values.get(e.edge_id, 0.0)` | Visibility from cache |
| (12) | `[w / total for w in weights]`, roulette with `sel_stream` | Normalised probability |
| (13) | `sum(self._edge_total_cost(e) for e in route)` | Route cost |
| (14) | `if new_cost < self._particles[i].p_best_cost: update` | p_best update |
| (15) | `if self._particles[i].p_best_cost < self._global_best_cost: update` | g_best update |
| (16) | `1.0 - avg_jaccard(p_best_edge_sets)` | Diversity (identical to BCO) |

---

## 10. Method-Level Pseudocode

### `optimize(context)` — Identical structure to `BCORouting.optimize()`

```python
def optimize(self, context: SwarmContext) -> SwarmResult:
    # 1. Validate context
    errors = PSOValidator.validate_context(context)
    if errors:
        return self._failure_result("; ".join(errors))
    
    # 2. Unpack context
    self._context = context
    self._graph = context.graph
    self._cost_calculator = context.cost_calculator
    self._source = context.routing_request.source_node
    self._destination = context.routing_request.destination_node
    config = context.config
    
    # 3. Build config
    self._config = PSOConfiguration.from_config(config)
    
    # 4. Validate graph connectivity
    if not self._graph.has_node(self._source):
        return self._failure_result("Source node not in graph")
    if not self._graph.has_node(self._destination):
        return self._failure_result("Destination node not in graph")
    
    # 5. Build visibility cache (static heuristic)
    self._build_visibility()
    
    # 6. Random streams
    self._swarm_rng = SwarmRandom(context.random_seed)
    
    # 7. Initialize particle population
    self._initialize()
    
    # 8. Global best tracking
    self._global_best_cost = min(p.p_best_cost for p in self._particles)
    self._global_best_route = list(self._particles[
        argmin(p.p_best_cost for p in self._particles)
    ].p_best_route)
    self._iteration_stats = []
    
    # 9. Termination checker
    checker = TerminationChecker(config)
    checker.start()
    
    # 10. Iteration loop (same pattern as BCO)
    no_improvement_count = 0
    prev_best_score = self._global_best_cost
    start_time = time.perf_counter()
    
    for iteration in range(config.max_iterations):
        iteration_start = time.perf_counter()
        
        # Compute inertia weight (Eq 5)
        w = self._compute_inertia(iteration, config.max_iterations)
        
        # Forward pass
        fwd_routes, fwd_costs, fwd_states = self._forward_pass(iteration, w)
        
        # Backward pass
        bwd_best_cost, bwd_best_route, bwd_diversity = \
            self._backward_pass(fwd_routes, fwd_costs, fwd_states)
        
        # Update global best
        if bwd_best_cost < self._global_best_cost:
            self._global_best_cost = bwd_best_cost
            self._global_best_route = list(bwd_best_route)
        
        # Record per-iteration stats
        success_costs = [p.cost for p in self._particles
                        if p.state == ParticleStatus.COMPLETE]
        avg_cost = mean(success_costs) if success_costs else float("inf")
        worst_cost = max(success_costs) if success_costs else float("inf")
        
        self._iteration_stats.append(PSOStatistics(
            iteration=iteration,
            best_cost=bwd_best_cost,
            avg_cost=avg_cost,
            worst_cost=worst_cost,
            diversity=bwd_diversity,
            runtime_s=time.perf_counter() - iteration_start,
        ))
        
        # Update no-improvement count
        if self._global_best_cost >= prev_best_score:
            no_improvement_count += 1
        else:
            no_improvement_count = 0
        prev_best_score = self._global_best_cost
        
        # Check termination
        search_state = SearchState(
            iteration=iteration + 1,
            best_score=self._global_best_cost,
            previous_best_score=prev_best_score if iteration > 0 else float("inf"),
            no_improvement_count=no_improvement_count,
            diversity=bwd_diversity,
            elapsed_time_s=time.perf_counter() - start_time,
        )
        term = checker.check(search_state)
        if term.should_stop:
            return self._build_swarm_result(
                total_time=time.perf_counter() - start_time,
                term_reason=term.reason,
                term_iteration=term.iteration,
            )
    
    # 11. Max iterations
    return self._build_swarm_result(
        total_time=time.perf_counter() - start_time,
        term_reason=f"Maximum iterations reached ({config.max_iterations})",
        term_iteration=config.max_iterations,
    )
```

### `_construct_route(source, dest, current_route, p_best_route, g_best_route, w, c1, c2, c3, stream)` — Eq (6)-(12)

```python
def _construct_route(self, source, dest,
                     current_route, p_best_route, g_best_route,
                     w, c1, c2, c3, stream):
    current = source
    visited = {source}
    route = []
    
    for step in range(self._config.forward_steps):
        if current == dest:
            break
        
        # Gather feasible candidates (Eq 6)
        candidates = []
        for edge in self._graph.outgoing_edges(current):
            if edge.target not in visited:
                ec = self._edge_total_cost(edge)
                if ec < float("inf"):
                    candidates.append(edge)
        
        if not candidates:
            break  # dead end
        
        # Compute weights (Eq 7-11)
        weights = []
        for e in candidates:
            I = 1.0 if step < len(current_route) and e.edge_id == current_route[step] else EPS
            P = 1.0 if step < len(p_best_route) and e.edge_id == p_best_route[step] else EPS
            G = 1.0 if step < len(g_best_route) and e.edge_id == g_best_route[step] else EPS
            eta = self._visibility.values.get(e.edge_id, 0.0)
            w_total = w * I + c1 * P + c2 * G + c3 * eta
            weights.append(max(w_total, 0.0))
        
        # Roulette selection (Eq 12)
        total = sum(weights)
        if total <= 0.0:
            chosen = stream.choice(candidates)
        else:
            r = stream.random() * total
            cum = 0.0
            for i, e in enumerate(candidates):
                cum += weights[i]
                if r <= cum:
                    chosen = e
                    break
            else:
                chosen = candidates[-1]
        
        route.append(chosen.edge_id)
        current = chosen.target
        visited.add(current)
    
    return route
```

### `_forward_pass(iteration, inertia)` — identical pattern to BCO

```python
def _forward_pass(self, iteration: int, inertia: float) -> tuple:
    P = len(self._particles)
    routes = [[] for _ in range(P)]
    costs = [0.0] * P
    states = [ParticleStatus.CONSTRUCTING] * P
    stream = self._swarm_rng.get_stream("pso.selection")
    t0 = time.perf_counter()
    
    for i in range(P):
        p = self._particles[i]
        new_route = self._construct_route(
            source=self._source,
            destination=self._destination,
            current_route=p.route,
            p_best_route=p.p_best_route,
            g_best_route=self._global_best_route,
            w=inertia,
            c1=self._config.cognition_weight,
            c2=self._config.social_weight,
            c3=self._config.visibility_weight,
            stream=stream,
        )
        
        new_cost = sum(self._edge_total_cost(self._graph.get_edge(eid))
                       for eid in new_route)
        
        p.route = new_route
        p.cost = new_cost
        p.state = ParticleStatus.COMPLETE if new_route and \
            new_route[-1] == ...  # check destination reached
            else ParticleStatus.FAILED
        
        routes[i] = new_route
        costs[i] = new_cost
        states[i] = p.state
    
    t1 = time.perf_counter()
    return routes, costs, states
```

### `_backward_pass(routes, costs, states)` — Eq (14)-(16), identical BCO pattern

```python
def _backward_pass(self, routes, costs, states) -> tuple:
    P = len(self._particles)
    
    # Personal best update (Eq 14)
    for i in range(P):
        if states[i] == ParticleStatus.COMPLETE and costs[i] < self._particles[i].p_best_cost:
            self._particles[i].p_best_route = list(routes[i])
            self._particles[i].p_best_cost = costs[i]
        elif states[i] != ParticleStatus.COMPLETE:
            self._particles[i].cost = float("inf")
    
    # Global best update (Eq 15)
    best_idx = argmin(p.p_best_cost for p in self._particles)
    best_cost = self._particles[best_idx].p_best_cost
    best_route = self._particles[best_idx].p_best_route
    
    # Diversity (Eq 16)
    diversity = self._compute_diversity()
    
    return best_cost, best_route, diversity
```

### Remaining methods — identical structure to BCO

- `_compute_diversity()` — identical Jaccard-based formula
- `_build_swarm_result()` — identical: build RouteCandidate, SwarmStatistics, iteration stats
- `_route_to_candidate()` — identical: edge walk → RouteCandidate with PSO metadata
- `_build_iteration_stats()` — identical: PSOStatistics → IterationStatistics
- `_find_convergence_iteration()` — identical: find last improvement iteration
- `_failure_result()` — identical: return SwarmResult(success=False)

---

## 11. YAML Configuration Template

```yaml
algorithm_name: pso
population_size: 30
max_iterations: 100
time_limit_s: 0
convergence_threshold: 0.0
stall_limit: 10
target_score: 0
seed: 42
hyperparameters:
  inertia_start: 0.9
  inertia_end: 0.4
  cognition_weight: 2.0
  social_weight: 2.0
  visibility_weight: 1.0
  epsilon: 1e-10
  forward_steps: 100
```

---

## 12. Acceptance Criteria

1. All 80+ tests pass with ≥ 90% code coverage on `pso.py`.
2. **Deterministic reproducibility**: `optimize(ctx)` with seed=42 produces identical `SwarmResult` across three independent runs.
3. **Route validity**: Every COMPLETE particle produces a valid source→destination path with no cycles.
4. **Global best non-increasing**: g_best_cost never increases between iterations.
5. **Inertia decay**: ω(t) follows equation (5) exactly.
6. **Integration**: `SwarmFactory.create_algorithm("pso")` returns a working `PSORouting`; `SwarmToRoutingAdapter` end-to-end.
7. **ACS + BCO + PSO test suite fully passing** (no regressions).
8. **BCO-identical architecture**: forward/backward pass, `_build_visibility()`, `_route_to_candidate()`, `_build_swarm_result()`, `_failure_result()`, validation pattern, naming conventions all match BCO exactly.