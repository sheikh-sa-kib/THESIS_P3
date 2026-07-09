# E³-Hybrid Design — Triple-Swarm Integration for Dynamic EV Routing

**Phase:** 11  
**Status:** Design (pre-implementation)  
**Target:** `src/e3hybrid/swarm/hybrid.py` + `tests/unit/test_hybrid.py`  
**Architecture:** SwarmAlgorithm Protocol → SwarmFactory → SwarmToRoutingAdapter  

---

## 1. Literature Review and Hybrid Justification

### 1.1 Why Combine ACO, BCO, and PSO?

ACO, BCO, and PSO each bring complementary optimisation strategies:

| Algorithm | Strengths | Weakness Addressed by Others |
|---|---|---|
| **ACO** | Pheromone-based global learning; edges retain long-term memory of good paths; strong exploitation via pheromone reinforcement (Dorigo & Gambardella, 1997) | Slow initial convergence; no explicit diversity mechanism; can prematurely converge on suboptimal trails |
| **BCO** | Forward/backward pass with loyalty/recruitment generates structured exploration; no global memory means less bias toward early overfitting (Teodorovic, 2009) | No long-term memory; each iteration starts mostly fresh; can waste computation revisiting poor regions |
| **PSO** | Particle-level personal best (cognitive memory) and swarm-level global best (social memory); inertia decay schedules exploration-to-exploitation (Shi & Eberhart, 1998) | No pheromone-style edge-level memory; no recruitment mechanism; less structured exploration |

**Key insight:** The three algorithms each answer a different question during route construction:

- *ACO:* "Which edges have historically been good for the colony across all iterations?" (pheromone τ)
- *BCO:* "Which edges are favoured by the current iteration's most successful routes?" (recruitment templates)
- *PSO:* "Which edges have worked for me personally and for the globally best individual?" (p_best, g_best)

A genuine hybrid synthesises all three answers into a single edge-selection decision, plus coordinates which subpopulation uses which algorithm's update rule.

### 1.2 Hybrid Swarm Literature

- **E³-Hybrid** (proposed): named after the three "E" algorithms — **E**mbedded ACO, **E**mbedded BCO, **E**mbedded PSO — plus the hybrid coordinator that unifies them. The name reflects the triple integration, not the exponential notation.

- **ACO + PSO hybrids** (existing): Shelokar et al. (2007) proposed a serial hybrid where PSO initialises the pheromone matrix for ACO, achieving faster convergence on TSP. The E³-Hybrid improves on this by making all three algorithms run **concurrently in the same iteration**, sharing real-time information rather than passing a single handoff.

- **ACO + BCO hybrids** (existing): Wong et al. (2010) combined ACO's pheromone memory with BCO's recruitment for job-shop scheduling. The E³-Hybrid extends this by adding PSO's cognitive/social memory as a third influence.

- **Three-algorithm hybrids** are rare in the literature. Most work focuses on hybridising two swarm algorithms. The E³-Hybrid is novel in its triple integration and in the **weighted-sharing architecture** described in Section 2.

### 1.3 How the Hybrid Is Genuine — Not Sequential

The E³-Hybrid does **not** run ACO, BCO, and PSO sequentially and pick the best result. Instead:

1. **Population partitioning:** The total population *N* is divided into three subpopulations: *N_a* ants, *N_b* bees, *N_p* particles (Section 6).
2. **Concurrent construction:** In each iteration, all individuals construct routes simultaneously, using the same graph state and random streams.
3. **Weighted edge influence:** During route construction, every individual considers **all three** influence sources: pheromones (Eq. 2), recruitment templates (Eq. 3), and PSO personal/global bests (Eq. 4). Each contributes a weight to the edge selection probability (Eq. 5).
4. **Cross-pollination updates:**
   - ACO pheromone is globally reinforced by the best route across **all** subpopulations, not just ants (Eq. 15–16).
   - BCO recruitment templates are drawn from the overall top *L* routes regardless of algorithm origin (Eq. 17).
   - PSO global best (g_best) is shared across all individuals and is updated by any individual's route (Eq. 19).
5. **Adaptive weight control (Section 8):** A meta-controller adjusts the contribution weights (α_a, α_b, α_p) based on subpopulation diversity — if one subpopulation converges too fast, its influence is reduced and others are boosted.

This ensures **every algorithm's component has a meaningful contribution to every individual's route construction**, and the update phase integrates information across all three subpopulations.

---

## 2. Mathematical Formulation

### 2.1 Notation

| Symbol | Meaning |
|---|---|
| *N* | Total population size |
| *N_a*, *N_b*, *N_p* | Subpopulation sizes: ants, bees, particles (Section 6) |
| *T* | Maximum iterations |
| *G* = (*V*, *E*) | Directed graph with nodes *V* and edges *E* |
| *s* ∈ *V* | Source node |
| *d* ∈ *V* | Destination node |
| **r**ᵢ(t) | Route (edge sequence) of individual *i* at iteration *t* |
| *c*ᵢ(t) | Cost of route **r**ᵢ(t) |
| **b**ᵢ(t) | Personal best route of individual *i* |
| *c*ᵢ*(t) | Cost of personal best route **b**ᵢ(t) |
| **g**(t) | Global best route across all individuals |
| τ(e, t) | Pheromone on edge *e* at iteration *t* |
| τ₀ | Initial pheromone value |
| τ_min, τ_max | Pheromone bounds |
| **T**_j(t) | Recruitment template *j* at iteration *t* |
| *L* | Number of recruitment templates |
| ω(t) | PSO inertia weight at iteration *t* |
| ω_start, ω_end | PSO inertia bounds |
| η(e) | Heuristic visibility of edge *e* |
| α_a | Hybrid influence weight for ACO pheromone |
| α_b | Hybrid influence weight for BCO template |
| α_p | Hybrid influence weight for PSO memory |
| α_h | Hybrid influence weight for heuristic visibility |
| α_a_min, α_a_max | Bounds for α_a (same pattern for α_b, α_p, α_h) |
| ρ | Global pheromone evaporation rate |
| ρ_local | Local pheromone evaporation rate |
| β_a | Pheromone exponent |
| c₁ | PSO cognitive coefficient |
| c₂ | PSO social coefficient |
| ε | Small positive constant for non-matching edges |
| δ_adapt | Meta-controller decay factor |
| K | Meta-controller update interval |
| div_min | Minimum diversity threshold for meta-controller |

### 2.2 Route Construction — Hybrid Weighted Influence Model

For **every individual** (ant, bee, or particle) at construction step *k* from current node *v*, the set of feasible candidate edges is:

*C*(v, t) = {e ∈ *N*(v) | target(e) ∉ visited, e.state.is_blocked = false, cost(e) < ∞} (1)

For each candidate edge *e* ∈ *C*(v, t) at step *k*, the selection weight is:

*w*(e, k, t) = α_a × *A*(e, k, t) + α_b × *B*(e, k, t) + α_p × *P*(e, k, t) + α_h × *H*(e, t) (2)

Each component is defined below.

**ACO pheromone component** — shared long-term memory across all iterations:

*A*(e, k, t) = τ(e, t)^β_a (3)

where β_a is the pheromone exponent (default 1.0). Higher τ means the colony has historically found this edge useful, regardless of which subpopulation discovered it.

**BCO recruitment template component** — shared best-route templates from the previous iteration:

*B*(e, k, t) = max_{j ∈ [1..L]} match_j(e, k, t) (4)

where:

match_j(e, k, t) = 1 if *k* < |**T**_j(t)| and e = **T**_j(t)[k], otherwise ε

If *L* = 0 (templates disabled) or no templates exist, *B*(e, k, t) = ε for all edges.

**PSO memory component** — personal best + global best:

*P*(e, k, t) = c₁ × *M*_p(e, k, t) + c₂ × *M*_g(e, k, t) (5)

where:

- *M*_p(e, k, t) = 1 if *k* < |**b**ᵢ(t)| and e = **b**ᵢ(t)[k], otherwise ε
- *M*_g(e, k, t) = 1 if *k* < |**g**(t)| and e = **g**(t)[k], otherwise ε

**Heuristic visibility component** — static edge-cost attraction:

*H*(e, t) = 1 / (cost(e) + ε) (6)

The probability of selecting edge *e* from candidates *C*(v, t) is:

*p*(e, k, t) = w(e, k, t) / Σ_{e′∈*C*(v,t)} w(e′, k, t) (7)

Selection uses roulette-wheel proportional selection.

### 2.3 Normalisation of Influence Components

The four components in Eq. (2) naturally have different magnitudes. To ensure no component dominates purely because of scale, each component is **brought to [0, 1]** before weighting:

**Given:** For candidate set *C*(v, t) at step *k*:

1. **ACO component *A* (Eq. 3):** Let *A_raw*(e) = τ(e, t)^β_a. Since τ ∈ [τ_min, τ_max] and β_a ≥ 0:

   *A*(e) = (*A_raw*(e) − τ_min^β_a) / (τ_max^β_a − τ_min^β_a + ε) (8)

   For β_a = 0, *A_raw*(e) = 1 for all edges; in that case *A*(e) = 0 (pheromone influence disabled).

2. **BCO component *B* (Eq. 4):** Already in {ε, 1}. Scale to [0, 1]:

   *B*(e) = (*B_raw*(e) − ε) / (1 − ε) (9)

   For ε ≈ 0, *B*(e) ≈ *B_raw*(e).

3. **PSO component *P* (Eq. 5):** *P_raw*(e) = c₁ × *M*_p + c₂ × *M*_g. Since *M*_p, *M*_g ∈ {ε, 1}:

   *P_max* = c₁ × 1 + c₂ × 1 = c₁ + c₂ (if both match)
   *P_min* = c₁ × ε + c₂ × ε = (c₁ + c₂) × ε (if neither matches)

   *P*(e) = (*P_raw*(e) − *P_min*) / (*P_max* − *P_min* + ε) (10)

   For c₁ = c₂ = 0 (PSO influence disabled), *P*(e) = 0.

4. **Visibility component *H* (Eq. 6):** *H_raw*(e) = 1 / (cost(e) + ε). Find *H_min*, *H_max* over current candidate set:

   *H*(e) = (*H_raw*(e) − *H_min*) / (*H_max* − *H_min* + ε) (11)

   If *H_max* = *H_min* (all candidates have equal cost), *H*(e) = 1 for all edges.

**After normalisation:** Each component is in [0, 1] before the α-weighted sum in Eq. (2). This means the α weights directly control **relative preference**, not absolute magnitude. α_a = α_b = α_p = α_h = 1 gives all four components equal influence.

### 2.4 Algorithm-Specific Contribution Bias

Although all individuals use the same normalised Eq. (2), the **primary update rules differ** by subpopulation:

| Individual Type | Primary Contribution | Secondary Contributions |
|---|---|---|
| **Ant** | ACO pheromone global update (Eq. 12) | Local update (Eq. 13) during construction |
| **Bee** | BCO template contribution (routes ranked to form templates) | — |
| **Particle** | PSO personal best + global best update (Eq. 17–18) | — |

Every individual tracks its own **personal best** (Eq. 17, shared logic). The **global best** (Eq. 18) is shared across all three subpopulations.

### 2.5 ACO Pheromone Updates

**Initialisation:**
τ(e, 0) = τ₀, ∀e ∈ E (implied by `PheromoneMatrix` constructor) — unnumbered.

**Local update** (performed by ants during route construction, per edge traversed):

τ(e, t+1) = (1 − ρ_local) × τ(e, t) + ρ_local × τ₀ (13)

**Global update** (performed at end of every iteration, uses best route across ALL subpopulations):

Δτ(e, t) = 1 / cost(**g**(t+1)) if e ∈ **g**(t+1), otherwise 0 (14)

τ(e, t+1) = (1 − ρ) × τ(e, t) + ρ × Δτ(e, t) (15)

τ(e, t+1) = clamp(τ(e, t+1), τ_min, τ_max) (16)

### 2.6 BCO Recruitment Template Update

After each iteration, the *L* best complete routes across all subpopulations become recruitment templates for the next iteration:

**T**_j(t+1) = **r**_{(j)}(t+1), j = 1..L (17)

where {(j)} indexes routes sorted by ascending cost. If fewer than *L* complete routes exist, all complete routes are used.

### 2.7 PSO Memory Updates

**Personal best** (every individual tracks one, not just particles):

**b**ᵢ(t+1) = **r**ᵢ(t+1), if cᵢ(t+1) < c**b**ᵢ(t)  
**b**ᵢ(t+1) = **b**ᵢ(t), otherwise (18)

**Global best** (shared across all individuals):

**g**(t+1) = **r**ᵢ(t+1), if cᵢ(t+1) < c(**g**(t)) for any *i*  
**g**(t+1) = **g**(t), otherwise (19)

### 2.8 PSO Inertia Weight

For the PSO memory component within particles specifically, the cognitive/social ratio decays linearly:

ω(t) = ω_start − (ω_start − ω_end) × (t / T) (20)

This overrides the relative weighting between c₁ and c₂ within Eq. (5); the overall α_p is managed by the meta-controller (Section 8).

### 2.9 Swarm Diversity (Jaccard)

Same Jaccard set formula across all individuals:

Let *S*ᵢ(t) = {edges in **r**ᵢ(t)}.

div(t) = 1 − (2 / (*N*(*N*−1))) × Σ_{i<j} |*S*ᵢ ∩ *S*ⱼ| / |*S*ᵢ ∪ *S*ⱼ| (21)

Subpopulation diversity (one per subpopulation, used by meta-controller in Section 8):

Let *S_x*(t) = {edges in all individuals of subpopulation *x* at iteration *t*}.

div_x(t) = |*S_x*(t)| / max(|*S_x*(t)|, N_x × 1) (22)

where complement is all edges not in *S_x*. This is computed as:

div_x(t) = |*S_x*| / (|*S_x*| + |*S*_x̄|) when using edge-set cardinality as a proxy, or simply:

div_x(t) = |*S*_x(t)| / (N_x × T_max̄)  × correction_factor

In implementation, the dominant metric is the **ratio of unique edges in the subpopulation to the maximum possible edges** (N_x × route_length_avg).

---

## 3. Architecture

### 3.1 Shared Infrastructure Reuse

The hybrid reuses the following existing framework components **without importing from `aco.py`, `bco.py`, or `pso.py`**:

| Framework Component | Location | How Hybrid Uses It |
|---|---|---|
| `SwarmAlgorithm` (Protocol) | `swarm/protocol.py` | Implements via `E3HybridRouting` |
| `SwarmContext` | `swarm/context.py` | Receives and unpacks |
| `SwarmConfig` | `swarm/config.py` | Extracts hyperparameters |
| `SwarmRandom` | `swarm/random.py` | All stochastic decisions |
| `SwarmResult` | `swarm/result.py` | Return type of `optimize()` |
| `IterationStatistics`, `SwarmStatistics` | `swarm/statistics.py` | Statistical recording |
| `TerminationChecker`, `TerminationCondition` | `swarm/termination.py` | Convergence and termination |
| `SearchState` | `swarm/models.py` | Termination tracking |
| `ParticleStatus` (Enum) | `swarm/pso.py` — **NOT reused** | Hybrid uses its own `IndividualStatus` enum |
| `PheromoneMatrix` | `swarm/aco.py` — **NOT imported** | Hybrid implements its own `HybridPheromoneMatrix` that accepts primitive float params instead of `ACSConfiguration` |
| `_edge_total_cost()` | `swarm/bco.py`, `swarm/pso.py` | Hybrid implements its own inline (3-line helper) |

### 3.2 Framework Enhancement: `swarm/pheromone.py`

To provide a shared, algorithm-agnostic pheromone matrix for the hybrid without importing from `aco.py`, the existing `PheromoneMatrix` class will be **extracted** from `aco.py` into a new shared file `swarm/pheromone.py`. ACORouting will continue to import from this new shared location after `Phase 12` (or equivalently, the file will be created as part of Phase 12 and both ACO and the hybrid will import from it). The design document assumes this extraction happens during Phase 12.

If this extraction is not desired, the hybrid will use a private `HybridPheromoneMatrix` with identical logic but primitive parameter types.

### 3.3 File: `src/e3hybrid/swarm/hybrid.py`

```
IndividualStatus(Enum) — CONSTRUCTING, COMPLETE, FAILED (reuses ParticleStatus semantics,
                         but NOT the class from pso.py)

@dataclass HybridInfluenceWeights — α_a, α_b, α_p, α_h with validation and normalisation helpers

@dataclass IndividualState        — kind, route, cost, p_best_route, p_best_cost, visited, state

@dataclass(frozen=True, slots=True) HybridConfiguration — all hyperparameters with _validate()

@dataclass(frozen=True, slots=True) HybridStatistics    — per-iteration hybrid metrics

class E3HybridRouting:

    @property name → "e3hybrid"

    optimize(context) → SwarmResult

    # Initialisation
    _initialize(config)                 — subpopulation assignment, pheromone init
    _build_visibility()                — dict[EdgeId, float] = 1/(cost+EPS), same pattern as BCO/PSO
    _edge_total_cost(edge) → float    — identical inline helper

    # Route construction + influence computation
    _compute_aco_influence(edge_id, step, pheromones) → float     — Eq. (3), then Eq. (8) norm
    _compute_bco_influence(edge_id, step, templates) → float     — Eq. (4), then Eq. (9) norm
    _compute_pso_influence(edge_id, step, p_best, g_best) → float — Eq. (5), then Eq. (10) norm
    _compute_visibility_influence(edge_id, candidates) → float   — Eq. (6), then Eq. (11) norm
    _construct_route(source, dest, ...) → list[EdgeId]             — Eqs. (1)–(7), roulette via SwarmRandom

    # Forward/backward pass
    _forward_pass(iteration, pheromones, templates, g_best, influence_weights, stream) → tuple
    _backward_pass(routes, costs, kinds, states, pheromones) → (best_cost, best_route)

    # Update logic
    _update_pheromones(pheromones, best_route, best_cost)   — Eqs. (13)–(16)
    _extract_templates(routes, costs) → list[list[EdgeId]] — Eq. (17)
    _update_personal_best(i, route, cost)                    — Eq. (18)
    _update_global_best(routes, costs)                    — Eq. (19)
    _compute_inertia(iteration, max_iters) → float         — Eq. (20)
    _compute_diversity(routes) → float                       — Eq. (21)

    # Meta-controller
    _update_meta_controller(iteration, routes, kinds)        — Section 8

    # Result building (same pattern as BCO/PSO)
    _build_swarm_result(...) → SwarmResult
    _route_to_candidate(edges, runtime) → RouteCandidate
    _build_hybrid_stats(...) → HybridStatistics
    _convergence_iteration() → int | None
    _failure_result(reason) → SwarmResult

# Auto-register
from e3hybrid.swarm.factory import SwarmFactory
SwarmFactory.register("e3hybrid", E3HybridRouting)
```

### 3.4 Naming Conventions

| BCO/PSO Name | E³-Hybrid Name | Rationale |
|---|---|---|
| `BeeStatus` / `ParticleStatus` | `IndividualStatus` | Enum: CONSTRUCTING, COMPLETE, FAILED |
| `BeeState` / `ParticleState` | `IndividualState` | Mutable individual state |
| `BCOConfiguration` / `PSOConfiguration` | `HybridConfiguration` | Hyperparameter config |
| `BCOStatistics` / `PSOStatistics` | `HybridStatistics` | Per-iteration stats |
| `_forward_pass` | `_forward_pass` | Route construction |
| `_backward_pass` | `_backward_pass` | Evaluation + update |
| `_compute_diversity` | `_compute_diversity` | Jaccard diversity |
| `_build_swarm_result` | `_build_swarm_result` | Result construction |
| `_route_to_candidate` | `_route_to_candidate` | Edge → RouteCandidate |
| `_failure_result` | `_failure_result` | Error result |
| `_compute_inertia` (PSO) | `_compute_inertia` | Linear decay for PSO inertia |

---

## 4. Configuration Schema

### 4.1 Hyperparameters

| Hyperparameter Key | Type | Default | Valid Range | Eq Ref | Notes |
|---|---|---|---|---|---|
| `ant_ratio` | float | 0.4 | [0.0, 1.0] | §6 | Fraction of population as ants |
| `bee_ratio` | float | 0.3 | [0.0, 1.0] | §6 | Fraction of population as bees |
| `particle_ratio` | float | 0.3 | [0.0, 1.0] | §6 | Fraction of population as particles |
| `alpha_a` | float | 1.0 | [0.0, ∞) | (2) | ACO influence weight (initial) |
| `alpha_a_min` | float | 0.1 | [0.0, alpha_a_max] | §8 | Lower bound for α_a |
| `alpha_a_max` | float | 3.0 | [alpha_a_min, ∞) | §8 | Upper bound for α_a |
| `alpha_b` | float | 1.0 | [0.0, ∞) | (2) | BCO influence weight (initial) |
| `alpha_b_min` | float | 0.1 | [0.0, alpha_b_max] | §8 | Lower bound for α_b |
| `alpha_b_max` | float | 3.0 | [alpha_b_min, ∞) | §8 | Upper bound for α_b |
| `alpha_p` | float | 1.0 | [0.0, ∞) | (2) | PSO influence weight (initial) |
| `alpha_p_min` | float | 0.1 | [0.0, alpha_p_max] | §8 | Lower bound for α_p |
| `alpha_p_max` | float | 3.0 | [alpha_p_min, ∞) | §8 | Upper bound for α_p |
| `alpha_h` | float | 1.0 | [0.0, ∞) | (2) | Heuristic influence weight |
| `template_count` | int | 3 | [0, ∞) | (4),(17) | L: number of recruitment templates |
| `inertia_start` | float | 0.9 | [0.0, 1.0] | (20) | PSO inertia start |
| `inertia_end` | float | 0.4 | [0.0, inertia_start] | (20) | PSO inertia end |
| `cognition_weight` | float | 2.0 | [0.0, ∞) | (5) | PSO c₁ |
| `social_weight` | float | 2.0 | [0.0, ∞) | (5) | PSO c₂ |
| `pheromone_tau0` | float | 1.0 | > 0.0 | (13) | Initial pheromone |
| `pheromone_min` | float | 0.01 | > 0.0 | (16) | Min pheromone bound |
| `pheromone_max` | float | 10.0 | > pheromone_min | (16) | Max pheromone bound |
| `rho` | float | 0.1 | (0, 1) | (15) | Global evaporation rate |
| `rho_local` | float | 0.1 | (0, 1) | (13) | Local evaporation rate |
| `beta_a` | float | 1.0 | [0.0, ∞) | (3) | Pheromone exponent |
| `epsilon` | float | 1e-10 | (0.0, 1.0] | (4) | Non-match small constant |
| `adapt_interval` | int | 5 | ≥ 1 | §8 | Meta-controller update period (K) |
| `adapt_diversity_min` | float | 0.15 | (0.0, 1.0] | §8 | Minimum diversity threshold (div_min) |
| `adapt_decay` | float | 0.9 | (0.0, 1.0) | §8 | Diversity decay factor (δ_adapt) |
| `adapt_recovery_gain` | float | 0.05 | [0.0, 1.0) | §8 | Recovery gain per check when diverse |
| `forward_steps` | int | 100 | ≥ 1 | — | Max steps per route construction |

### 4.2 Ratio Validation

```python
def _validate_ratios(self) -> None:
    total = self.ant_ratio + self.bee_ratio + self.particle_ratio
    if abs(total - 1.0) > 1e-9:
        raise ValueError(
            f"ant_ratio ({self.ant_ratio}) + bee_ratio ({self.bee_ratio}) + "
            f"particle_ratio ({self.particle_ratio}) = {total}, must sum to 1.0"
        )
```

### 4.3 Other Validation Rules

- `forward_steps >= 1`
- `adapt_interval >= 1`, `template_count >= 0`
- `0 <= epsilon <= 1`
- `inertia_start >= inertia_end`, both in `[0, 1]`
- `cognition_weight >= 0`, `social_weight >= 0`
- `alpha_a + alpha_b + alpha_p + alpha_h > 0` (at least one influence active)
- `alpha_a_min <= alpha_a <= alpha_a_max` (same for b, p)
- `0 < rho < 1`, `0 < rho_local < 1`
- `beta_a >= 0`
- `population_size >= 3` (minimum one per subpopulation)
- `0 < pheromone_min < pheromone_max`
- `0 <= adapt_recovery_gain < 1`

---

## 5. Component Isolation

`hybrid.py` must not import algorithm implementations from `aco.py`, `bco.py`, or `pso.py`. The permitted imports from the `e3hybrid.swarm` package are:

| Allowed Import | Source File | Reason |
|---|---|---|
| `SwarmAlgorithm` | `protocol.py` | Required protocol |
| `SwarmContext` | `context.py` | Input context |
| `SwarmConfig` | `config.py` | Configuration extraction |
| `SwarmRandom` | `random.py` | Deterministic randomness |
| `SwarmResult` | `result.py` | Return type |
| `SwarmStatistics`, `IterationStatistics` | `statistics.py` | Statistics collection |
| `TerminationChecker`, `TerminationCondition` | `termination.py` | Convergence detection |
| `SearchState` | `models.py` | Termination state |
| `EdgeId`, `NodeId` | `network/types.py` | Graph type primitives |

The hybrid implements its own `IndividualStatus` enum, `IndividualState` dataclass, `HybridConfiguration`, `HybridStatistics`, and hybrid-specific influence computation. It does not inherit from or instantiate any ACO/BCO/PSO class.

If the shared `PheromoneMatrix` extraction to `swarm/pheromone.py` (Section 3.2) is adopted, the hybrid may import `PheromoneMatrix` from there. If not, a private `HybridPheromoneMatrix` with the same internal logic but accepting primitive float parameters will be used instead.

---

## 6. Deterministic Population Partitioning

Given total population size *N*, subpopulation ratios *r_a*, *r_b*, *r_p* (summing to 1.0), the integer counts are computed deterministically:

```
N_a = max(1, int(N × r_a))
N_b = max(1, int(N × r_b))
N_p = N - N_a - N_b
```

**Properties:**
- All three subpopulations always have at least 1 individual.
- *N_p* absorbs any rounding residual, so *N_a* + *N_b* + *N_p* = *N* exactly.
- The assignment is purely deterministic (no randomness, no floating-point seed).
- The kind of each individual at index *i* is: [0..*N_a*−1] = ANT, [*N_a*..*N_a*+*N_b*−1] = BEE, remainder = PARTICLE.

**Examples:**

| N | r_a | r_b | r_p | N_a | N_b | N_p | Note |
|---|---|---|---|---|---|---|---|
| 30 | 0.4 | 0.3 | 0.3 | 12 | 9 | 9 | Ideal split |
| 10 | 0.4 | 0.3 | 0.3 | 4 | 3 | 3 | Ideal split |
| 5 | 0.4 | 0.3 | 0.3 | 2 | 1 | 2 | Floor + residual |
| 3 | 0.4 | 0.3 | 0.3 | 1 | 1 | 1 | Minimum: one each |
| 10 | 0.5 | 0.0 | 0.5 | 5 | 1 | 4 | r_b = 0 → floor max(1) → N_b = 1 |
| 100 | 0.333 | 0.334 | 0.333 | 33 | 33 | 34 | Residual goes to N_p |

---

## 7. Initialisation

### 7.1 Subpopulation Assignment

As per Section 6: individuals are assigned kinds deterministically. Initial routes are constructed using the **same hybrid route construction** with empty priors:

```
_construct_route(source, destination,
    current_route=[],     — empty: no personal best attraction
    p_best_route=[],   — empty: no cognitive attraction
    templates=[],      — empty: no template attraction
    g_best=[],         — empty: no global best attraction
    pheromones=initial_matrix,  — all edges at tau0
    alpha_a=0.0,       — zeroed: no ACO influence on init
    alpha_b=0.0,       — zeroed: no BCO influence on init
    alpha_p=0.0,       — zeroed: no PSO influence on init
    alpha_h=1.0,       — full visibility guidance
    stream=init_stream,
)
```

This yields a pure visibility-guided population, consistent with how ACO, BCO, and PSO all initialise.

### 7.2 Pheromone Initialisation

`HybridPheromoneMatrix(tau0, tau_min, tau_max, edge_ids)` sets τ(e, 0) = τ₀ for all e ∈ E.

### 7.3 Visibility Caching

`_build_visibility()` computes:

η(e) = 0 if edge is blocked or cost is infinite/NaN, otherwise 1 / (cost(e) + ε)

Same pattern as BCO's `VisibilityCache` and PSO's `_build_visibility`.

### 7.4 Template Initialisation

Templates initialised to empty list. After the first backward pass, populated from best routes.

---

## 8. Adaptive Meta-Controller

### 8.1 Purpose

The meta-controller prevents any single algorithm subpopulation from dominating the search by monitoring **per-subpopulation diversity** and adjusting the influence weights (α_a, α_b, α_p) accordingly.

### 8.2 When It Activates

Every `K` iterations (configurable `adapt_interval`, default 5), the meta-controller evaluates per-subpopulation diversity.

### 8.3 Per-Subpopulation Diversity

Already defined in Eq. (22). Re-stated for convenience:

div_x(t) = |S_x(t)| / max(|S_x(t)|, N_x × 1)

where *S_x*(t) is the **set of unique edges** traversed by all individuals in subpopulation *x* at iteration *t*, and 1 is a minimum edge count floor.

A simpler operational definition for implementation:

div_x(t) = number_of_unique_edges_in_subpopulation / (subpopulation_size × average_route_length)

Higher div_x means the subpopulation is exploring diverse edges; lower div_x means convergence/stagnation.

### 8.4 Decay (Low Diversity)

If div_x < div_min for check iteration `t`:

Store a `low_diversity_count_x` that increments each time the check fires.

If `low_diversity_count_x >= 1` (immediate on first detection):

α_x(t+1) = max(α_x_min, α_x(t) × δ_adapt) (23)

The amount removed:

Δ_x = α_x(t) − α_x(t+1)

This Δ_x is redistributed to the other two non-decayed influence components.

### 8.5 Redistribution

The total removed influence Δ_total = Σ_{x ∈ decayed} Δ_x is redistributed equally among **non-decayed** components:

Let *D* = {x | div_x < div_min} (decayed subpopulations).
Let *U* = {a, b, p} \ *D* (undecayed subpopulations).

If *U* ≠ ∅:

per_gain = Δ_total / |U|

For each *y* ∈ *U*:

α_y(t+1) = min(α_y_max, α_y(t) + per_gain)

If |*U*| = 0 (all three subpopulations are decaying simultaneously), the removed influence is added back to the heuristic weight α_h:

α_h = α_h + Δ_total

### 8.6 Recovery (Diversity Improves)

If div_x ≥ div_min after a prior low-diversity state:

low_diversity_count_x = 0

Additionally, a small recovery gain is applied:

α_x(t+1) = min(α_x_max, α_x(t) + α_recovery_gain) (24)

This gradually restores the component's influence when diversity returns.

### 8.7 Normalisation After Updates

After every meta-controller update, the influence weights are normalised so that the sum α_a + α_b + α_p is held at a reference sum *S_ref*:

S_ref = α_a(0) + α_b(0) + α_p(0)

After adjustments, compute current sum S = α_a + α_b + α_p. If S > 0:

α_x = α_x × (S_ref / S) for x ∈ {a, b, p} (25)

Then each α_x is clamped to [α_x_min, α_x_max].

This ensures:
- The total ACO + BCO + PSO influence remains constant over time (the relative importance changes, not the total).
- Individual weights cannot go outside configured bounds.
- α_h (heuristic) is not normalised — it serves as a baseline that is independent of the meta-controller interplay.

### 8.8 Behaviour Over Long Runs

| Scenario | Behaviour |
|---|---|
| All three subpopulations diverse | No activation. Weights stay at initial values. |
| One subpopulation converges | Its α decays, redistributed to the other two. |
| Two subpopulations converge | Their αs decay, redistributed to the one remaining. |
| All three converge | All αs clamped to their minima; the surplus moves to α_h. |
| A converged subpopulation recovers diversity | Gradual recovery gain (Eq. 24) restores its α. |
| Oscillation (converge/diverge repeatedly) | The recovery gain rate and decay rate create hysteresis; weights oscillate but remain bounded. |
| Very long run (T → ∞) | All α_x approach their configured minima/maxima based on diversity. α_h provides a floor when all three are minimal. No weight can go outside [α_min, α_max]. |

---

## 9. Deterministic Execution

All stochastic decisions route through `SwarmRandom` named streams:

| Stream Name | Used By | Eq Ref |
|---|---|---|
| `e3hybrid.init` | `_initialize()` — initial route construction | init |
| `e3hybrid.ant.selection` | Ant route construction — roulette selection | (7) |
| `e3hybrid.bee.selection` | Bee route construction — roulette selection | (7) |
| `e3hybrid.particle.selection` | Particle route construction — roulette selection | (7) |

**Determinism guarantee:** Given the same `SwarmContext.random_seed`, same graph, same configuration, and same cost calculator, `optimize()` produces an identical `SwarmResult` across runs. The deterministic population partitioning (Section 6) additionally ensures that subpopulation assignments are identical across runs.

---

## 10. Pseudocode

### 10.1 `optimize(context)`

```
def optimize(self, context):
    # 1. Validate context
    errors = validate_context(context)
    if errors: return failure_result(errors)
    
    # 2. Unpack context
    self._unpack_context(context)
    
    # 3. Build config
    self._config = HybridConfiguration.from_swarm_config(context.config)
    cfg_errors = self._config._validate()
    if cfg_errors: return failure_result(str(cfg_errors))
    
    # 4. Build visibility cache
    self._build_visibility()
    self._swarm_rng = SwarmRandom(context.random_seed)
    
    # 5. Build pheromone matrix (HybridPheromoneMatrix or shared)
    all_edge_ids = {e.edge_id for e in self._graph.edges()}
    pheromones = HybridPheromoneMatrix(
        tau0=self._config.pheromone_tau0,
        tau_min=self._config.pheromone_min,
        tau_max=self._config.pheromone_max,
        edge_ids=all_edge_ids,
    )
    
    # 6. Initialize population
    self._initialize_population()
    
    # 7. Hybrid state
    self._global_best_cost = float("inf")
    self._global_best_route = []
    self._templates = []
    self._influence_weights = self._init_weights()  # from config
    self._meta_diversity_history = {"ant": [], "bee": [], "particle": []}
    self._low_diversity_counts = {"ant": 0, "bee": 0, "particle": 0}
    
    # 8. Termination checker
    checker = TerminationChecker(context.config)
    checker.start()
    start_time = time.perf_counter()
    prev_best_score = float("inf")
    
    for iteration in range(config.max_iterations):
        iter_start = time.perf_counter()
        
        # PSO inertia (used for particle subpopulation within PSO influence)
        w = self._compute_inertia(iteration, config.max_iterations)
        
        # Forward pass
        routes, costs, kinds, states = self._forward_pass(
            iteration, pheromones, self._templates,
            self._global_best_route, self._influence_weights, w,
        )
        
        # Backward pass (update all memories)
        best_cost, best_route = self._backward_pass(
            routes, costs, kinds, states, pheromones,
        )
        
# Update global best (Eq. 19)
            if best_cost < self._global_best_cost:
                self._global_best_cost = best_cost
                self._global_best_route = list(best_route)
            
            # Update templates (Eq. 17)
            self._templates = self._extract_templates(routes, costs)
            
            # Compute diversity (Eq. 21)
        diversity = self._compute_diversity(routes)
        
        # Record per-iteration stats
        self._record_iteration_stats(iteration, best_cost, diversity, start_time)
        
        # Meta-controller (Section 8)
        self._update_meta_controller(iteration, routes, kinds)
        
        # Check termination
        search_state = SearchState(
            iteration=iteration+1,
            best_score=self._global_best_cost,
            previous_best_score=prev_best_score if iteration > 0 else float("inf"),
            no_improvement_count=...,
            diversity=diversity,
            elapsed_time_s=time.perf_counter() - start_time,
        )
        term = checker.check(search_state)
        if term.should_stop:
            return self._build_swarm_result(
                total_time=..., term_reason=term.reason,
                term_iteration=term.iteration,
            )
        
        prev_best_score = self._global_best_cost
    
    # Max iterations reached
    return self._build_swarm_result(
        total_time=..., term_reason=..., term_iteration=...,
    )
```

### 10.2 `_forward_pass(iteration, pheromones, templates, g_best, weights, w)`

```
def _forward_pass(self, iteration, pheromones, templates, g_best, weights, w):
    N = len(self._individuals)
    [... allocate routes, costs, states arrays of size N ...]
    
    for i in range(N):
        ind = self._individuals[i]
        
        # Select random stream by kind
        if ind.kind == IndividualKind.ANT:
            stream = self._swarm_rng.get_stream("e3hybrid.ant.selection")
        elif ind.kind == IndividualKind.BEE:
            stream = self._swarm_rng.get_stream("e3hybrid.bee.selection")
        elif ind.kind == IndividualKind.PARTICLE:
            stream = self._swarm_rng.get_stream("e3hybrid.particle.selection")
        
        # Construct route using hybrid weighted selection
        new_route = self._construct_route(
            source=self._source, destination=self._destination,
            current_route=ind.route,
            p_best_route=ind.p_best_route,
            templates=templates,
            g_best=g_best,
            pheromones=pheromones,
            weights=weights,
            stream=stream,
        )
        
        # Compute cost
        new_cost = sum(self._edge_total_cost(self._graph.get_edge(eid)) for eid in new_route)
        
        # Update individual state
        reached_dest = bool(new_route) and new_route[-1] == self._destination
        ind.route = new_route
        ind.cost = new_cost
        ind.state = (IndividualStatus.COMPLETE if reached_dest else IndividualStatus.FAILED)
        ind.visited = set()  # reset for next iteration
        
        # Local pheromone update for ants only (Eq. 13)
        if ind.kind == IndividualKind.ANT:
            for eid in new_route:
                pheromones.local_update(eid, self._config.rho_local)
        
        routes[i] = new_route
        costs[i] = new_cost
        states[i] = ind.state
    
    return routes, costs, [ind.kind for ind in self._individuals], states
```

### 10.3 `_construct_route(...)` — Hybrid Weighted Selection

```
def _construct_route(self, source, destination,
                     current_route, p_best_route, templates, g_best,
                     pheromones, weights, stream):
    current = source
    visited = {source}
    route = []
    
    for step in range(self._config.forward_steps):
        if current == destination:
            break
        
        # Gather candidates (Eq. 1)
        candidates = []
        for edge in self._graph.outgoing_edges(current):
            if edge.target not in visited:
                ec = self._edge_total_cost(edge)
                if ec < float("inf"):
                    candidates.append(edge)
        
        if not candidates:
            break  # dead end
        
        # Compute normalised influence values for this candidate set
        # (normalisation per Eqs. 8-11 is done over the set, not per edge)
        raw_A = [self._compute_raw_aco(e.edge_id, pheromones) for e in candidates]
        raw_B = [self._compute_raw_bco(e.edge_id, step, templates) for e in candidates]
        raw_P = [self._compute_raw_pso(e.edge_id, step, p_best_route, g_best) for e in candidates]
        raw_H = [self._compute_raw_visibility(e.edge_id) for e in candidates]
        
        # Normalise each component to [0, 1]
        norm_A = self._normalise(raw_A)
        norm_B = self._normalise(raw_B)
        norm_P = self._normalise(raw_P)
        norm_H = self._normalise(raw_H)
        
        # Compute total weights (Eq. 2)
        weights_arr = []
        for j in range(len(candidates)):
            w = (weights.alpha_a * norm_A[j] +
                 weights.alpha_b * norm_B[j] +
                 weights.alpha_p * norm_P[j] +
                 weights.alpha_h * norm_H[j])
            weights_arr.append(max(w, 0.0))
        
        # Roulette selection (Eq. 7)
        total = sum(weights_arr)
        if total <= 0.0:
            chosen = stream.choice(candidates)
        else:
            r = stream.random() * total
            cumulative = 0.0
            for j, e in enumerate(candidates):
                cumulative += weights_arr[j]
                if r <= cumulative:
                    chosen = e
                    break
            else:
                chosen = candidates[-1]
        
        route.append(chosen.edge_id)
        current = chosen.target
        visited.add(current)
    
    return route
```

### 10.4 `_backward_pass(routes, costs, kinds, states, pheromones)`

```
def _backward_pass(self, routes, costs, kinds, states, pheromones):
    # Personal best (Eq. 18) — all individuals
    for i in range(len(self._individuals)):
        if states[i] == IndividualStatus.COMPLETE and costs[i] < self._individuals[i].p_best_cost:
            self._individuals[i].p_best_route = list(routes[i])
            self._individuals[i].p_best_cost = costs[i]
    
    # Find best complete route this iteration
    valid = [(c, i) for i, (c, s) in enumerate(zip(costs, states))
             if s == IndividualStatus.COMPLETE]
    if valid:
        best_cost, best_idx = min(valid, key=lambda x: x[0])
        best_route = routes[best_idx]
    else:
        best_cost = float("inf")
        best_route = []
    
    # Global pheromone update (Eqs. 14-16) using best over all subpopulations
    if best_route and best_cost < float("inf"):
        deposit = 1.0 / best_cost
        for eid in best_route:
            current = pheromones.get(eid)
            updated = (1 - self._config.rho) * current + self._config.rho * deposit
            pheromones.set(eid, updated)
    
    return best_cost, best_route
```

### 10.5 `_update_meta_controller(iteration, routes, kinds)`

```
def _update_meta_controller(self, iteration, routes, kinds):
    K = self._config.adapt_interval
    if iteration == 0 or iteration % K != 0:
        return
    
    # Group edges by subpopulation
    edges_by_kind = {"ant": set(), "bee": set(), "particle": set()}
    kind_to_key = {IndividualKind.ANT: "ant", IndividualKind.BEE: "bee", IndividualKind.PARTICLE: "particle"}
    counts = {"ant": 0, "bee": 0, "particle": 0}
    
    for i, r in enumerate(routes):
        key = kind_to_key[kinds[i]]
        edges_by_kind[key] |= set(r)
        counts[key] += 1
    
    # Compute per-subpopulation diversity (Eq. 22)
    total_avg_len = sum(len(r) for r in routes) / max(len(routes), 1)
    diversities = {}
    for key in ("ant", "bee", "particle"):
        n = max(counts[key], 1)
        max_possible = n * max(total_avg_len, 1)
        div = len(edges_by_kind[key]) / max_usable_edges if max_possible > 0 else 1.0
        diversities[key] = div
    
    # Decide which subpopulations have low diversity
    decayed_keys = []
    for key, div in diversities.items():
        if div < self._config.adapt_diversity_min:
            self._low_diversity_counts[key] += 1
            if self._low_diversity_counts[key] >= 1:
                decayed_keys.append(key)
        else:
            # Recovery (Eq. 24)
            if self._low_diversity_counts[key] > 0:
                self._low_diversity_counts[key] = 0
                current = getattr(self._influence_weights, f"alpha_{key[0]}")
                new_val = min(getattr(self._config, f"alpha_{key[0]}_max"), current + self._config.adapt_recovery_gain)
                setattr(self._influence_weights, f"alpha_{key[0]}", new_val)
    
    # Apply decay (Eq. 23) for low-diversity subpopulations
    total_removed = 0.0
    for key in decayed_keys:
        current = getattr(self._influence_weights, f"alpha_{key[0]}")
        new_val = max(getattr(self._config, f"alpha_{key[0]}_min"), current * self._config.adapt_decay)
        removed = current - new_val
        setattr(self._influence_weights, f"alpha_{key[0]}", new_val)
        total_removed += removed
    
    # Redistribute to non-decayed components
    non_decayed = [k for k in ("a", "b", "p") if k not in [d[0] for d in decayed_keys]]
    if non_decayed and total_removed > 0:
        per_gain = total_removed / len(non_decayed)
        for key in non_decayed:
            current = getattr(self._influence_weights, f"alpha_{key}")
            new_val = min(getattr(self._config, f"alpha_{key}_max"), current + per_gain)
            setattr(self._influence_weights, f"alpha_{key}", new_val)
    elif not non_decayed and total_removed > 0:
        # All three decaying — add to heuristic weight
        self._influence_weights.alpha_h += total_removed
    
    # Normalise (Eq. 25)
    self._normalise_weights()
```

### 10.6 `_normalise_weights()`

```
def _normalise_weights(self):
    # Get initial sum from config
    S_ref = (self._config.alpha_a + self._config.alpha_b + self._config.alpha_p)
    
    a = self._influence_weights.alpha_a
    b = self._influence_weights.alpha_b
    p = self._influence_weights.alpha_p
    S = a + b + p
    
    if S > 0 and S != S_ref:
        factor = S_ref / S
        self._influence_weights.alpha_a = clamp(a * factor, self._config.alpha_a_min, self._config.alpha_a_max)
        self._influence_weights.alpha_b = clamp(b * factor, self._config.alpha_b_min, self._config.alpha_b_max)
        self._influence_weights.alpha_p = clamp(p * factor, self._config.alpha_p_min, self._config.alpha_p_max)
```

### 10.7 `_build_swarm_result(...)` — Same pattern as BCO/PSO

```
def _build_swarm_result(self, total_time, term_reason, term_iteration):
    candidates = []
    if self._global_best_route:
        candidate = self._route_to_candidate(self._global_best_route, total_time)
        candidates.append(candidate)
    
    # Build SwarmStatistics
    scores = [s.best_cost for s in self._iteration_stats]
    avg = sum(scores) / len(scores) if scores else 0.0
    
    stats = SwarmStatistics(
        total_iterations=term_iteration,
        total_runtime_s=total_time,
        best_score=self._global_best_cost if self._global_best_cost < float("inf") else 0.0,
        average_score=avg,
        worst_score=max(scores) if scores else 0.0,
        convergence_iteration=self._find_convergence_iteration(),
        candidate_count=len(candidates),
        solutions_evaluated=term_iteration * len(self._individuals),
        diversity_history=tuple(self._diversity_history),
        score_history=tuple(self._score_history),
        termination_reason=term_reason,
    )
    
    return SwarmResult(
        best_solution=candidates[0] if candidates else None,
        candidates=tuple(candidates),
        statistics=stats,
        iterations=tuple(self._build_iteration_stats()),
        success=len(candidates) > 0,
        failure_reason=None if candidates else "No feasible route found by any individual",
    )
```

---

## 11. Complexity Analysis

### 11.1 Per-Iteration Complexity

| Operation | Complexity | Notes |
|---|---|---|
| Forward pass (all individuals) | O(*N* × *V* × deḡ) | Each individual constructs up to *V* steps; each step scans outgoing degree |
| Edge weight computation (4 normalised components) | O(deḡ × (*L* + 4)) | *L* = template count (default 3). Normalisation is O(deḡ) per component over the candidate set |
| Backward pass | O(*N* + |E*|) | Update pheromones for best route edges only |
| Update templates | O(*N* log *N*) | Sort routes by cost, take top *L* |
| Meta-controller | O(*N* × avg_route_len) | Set-of-edges aggregation, O(1) per individual |

**Total per iteration:** O(*N* × *V* × deḡ + |*E*|) — same order as ACO's full colony, since *N* = *N_a* + *N_b* + *N_p* is comparable to a single-algorithm population.

### 11.2 Memory Complexity

| Structure | Size |
|---|---|
| Pheromone matrix | O(|*E*|) floats |
| Visibility cache | O(|*E*|) floats |
| Templates | O(*L* × *V*) EdgeIds |
| Individual states | O(*N* × *V*) EdgeIds (all routes) |
| Statistics history | O(*T*) HybridStatistics objects |

**Total:** O(|*E*| + *N* × *V*).

---

## 12. Edge Cases

| Edge Case | Expected Behaviour |
|---|---|
| Subpopulation too small (N < 3) | Config validation rejects N < 3. |
| Templates disabled (L = 0) | *B*(e) = ε for all edges. α_b has no effect. |
| All influence weights zero | Config validation requires at least one > 0. |
| Single subpopulation in meta-controller | If one subpopulation dominates, its α decays; redistributed to others. |
| Dead end during construction | Individual stops, state = FAILED, cost = ∞. Personal best not updated. |
| Source = destination | Context-level validation: error returned. |
| Unreachable destination | All individuals eventually fail. `SwarmResult(success=False)`. |
| Blocked edges | Filtered at Eq. (1). Visibility = 0 for blocked edges. |
| NaN/inf costs | Edge filtered from candidates. Same as BCO/PSO. |
| All three subpopulations converge | All αs approach their minima; α_h absorbs surplus. |
| No complete routes in iteration | `best_cost = inf`, `best_route = []`. No pheromone update. |
| Meta-controller with equal diversity | No weights changed. No activation needed. |

---

## 13. Equation-to-Python Mapping

| Eq | Python Method/Variable | Notes |
|---|---|---|---|
| (1) | `if e.target not in visited and not e.state.is_blocked and ec < inf` | Candidate filtering in `_construct_route` |
| (2) | `alpha_a * norm_A[j] + alpha_b * norm_B[j] + alpha_p * norm_P[j] + alpha_h * norm_H[j]` | Total selection weight |
| (3) | `tau ** beta_a` | `_compute_raw_aco()` |
| (4) | `1.0 if match else EPS` | `_compute_raw_bco()` |
| (5) | `c1 * M_p + c2 * M_g` | `_compute_raw_pso()` |
| (6) | `1.0 / (cost + EPS)` | `_compute_raw_visibility()` |
| (7) | `w / sum(weights)` for roulette | Roulette selection |
| (8) | `(raw - min) / (max - min + EPS)` → clamp | ACO component normalisation |
| (9) | `(B_raw - EPS) / (1 - EPS)` | BCO component normalisation |
| (10) | `(P_raw - P_min) / (P_max - P_min + EPS)` | PSO component normalisation |
| (11) | `(H_raw - H_min) / (H_max - H_min + EPS)` | Visibility component normalisation |
| (12) | *(unnumbered init: tau0 for all edges)* | Pheromone initialisation |
| (13) | `(1 - rho_local) * current + rho_local * tau0` | Local pheromone update |
| (14) | `1.0 / best_cost` | Global pheromone deposit |
| (15) | `(1 - rho) * current + rho * deposit` | Global pheromone update |
| (16) | `max(tau_min, min(val, tau_max))` | Pheromone bounds clamp |
| (17) | `sorted(zip(routes, costs), key=lambda x: x[1])[:L]` | Template extraction |
| (18) | `if cost < p_best_cost: update` | Personal best update |
| (19) | `if best_cost < global_best_cost: update` | Global best update |
| (20) | `w_start - (w_start - w_end) * (iter / max_iters)` | PSO inertia |
| (21) | `1.0 - avg_jaccard` | Swarm diversity |
| (22) | `len(edge_set) / max_possible` | Subpopulation diversity |
| (23) | `max(alpha_min, alpha * decay)` | Meta-controller decay |
| (24) | `min(alpha_max, alpha + recovery_gain)` | Meta-controller recovery |
| (25) | `alpha *= (S_ref / S)` | Weight normalisation |

---

## 12. Integration Points

### 12.1 SwarmFactory

```python
from e3hybrid.swarm.factory import SwarmFactory
SwarmFactory.register("e3hybrid", E3HybridRouting)
```

### 12.2 `__init__.py` Exports

Add to imports:

```python
from e3hybrid.swarm.hybrid import (
    E3HybridRouting,
    HybridConfiguration,
    HybridStatistics,
    HybridInfluenceWeights,
    IndividualKind,
    IndividualState,
)
```

Add to `__all__`:

```python
# Hybrid
"E3HybridRouting",
"HybridConfiguration",
"HybridStatistics",
"HybridInfluenceWeights",
"IndividualKind",
"IndividualState",
```

### 12.3 SwarmToRoutingAdapter

No changes needed. `E3HybridRouting` implements `SwarmAlgorithm`. Usage:

```python
hybrid = E3HybridRouting()
# Direct:
result = hybrid.optimize(swarm_context)
# Via adapter:
adapter = SwarmToRoutingAdapter(swarm_algorithm=hybrid)
routing_result = adapter.compute_route(request, graph)
```

### 12.4 YAML Configuration Template

```yaml
algorithm_name: e3hybrid
population_size: 30
max_iterations: 100
time_limit_s: 0
convergence_threshold: 0.0
stall_limit: 10
target_score: 0
seed: 42
hyperparameters:
  ant_ratio: 0.4
  bee_ratio: 0.3
  particle_ratio: 0.3
  alpha_a: 1.0
  alpha_a_min: 0.1
  alpha_a_max: 3.0
  alpha_b: 1.0
  alpha_b_min: 0.1
  alpha_b_max: 3.0
  alpha_p: 1.0
  alpha_p_min: 0.1
  alpha_p_max: 3.0
  alpha_h: 1.0
  template_count: 3
  inertia_start: 0.9
  inertia_end: 0.4
  cognition_weight: 2.0
  social_weight: 2.0
  pheromone_tau0: 1.0
  pheromone_min: 0.01
  pheromone_max: 10.0
  rho: 0.1
  rho_local: 0.1
  beta_a: 1.0
  epsilon: 1.0e-10
  adapt_interval: 5
  adapt_diversity_min: 0.15
  adapt_decay: 0.9
  adapt_recovery_gain: 0.05
  forward_steps: 100
```

---

## 13. Testing Strategy

### 13.1 Configuration Validation (12 tests)

| Test | Description |
|---|---|
| Default configuration loads without error | Minimal config produces valid `HybridConfiguration` |
| Ratios must sum to 1.0 | 0.4+0.3+0.3 → OK; 0.5+0.5+0.5 → error |
| Ratios with floating-point tolerance | 0.333+0.333+0.334 → OK (within 1e-9) |
| Forward steps validation | `forward_steps=0` → error |
| Pheromone bounds | `tau_min >= tau_max` → error |
| All-zero influence weights | `alpha_a=alpha_b=alpha_p=alpha_h=0` → error |
| Population size minimum | `N < 3` → error |
| Inertia bounds reversed | `inertia_start < inertia_end` → error |
| Adapt parameters | `adapt_interval < 1` → error; `adapt_recovery_gain > 1` → error |
| Coefficient ranges | `cognition_weight < 0` → error |
| Beta range | `beta_a < 0` → error |
| Epsilon range | `epsilon=0.0` or `epsilon > 1.0` → error |

### 13.2 Population Partitioning (6 tests)

| Test | Description |
|---|---|
| `ant_ratio=0.4, bee_ratio=0.3, particle_ratio=0.3, N=30` | N_a=12, N_b=9, N_p=9 |
| `all ratios equal, N=10` | N_a=4, N_b=3, N_p=3 (floor + residual) |
| `minimum N=3` | N_a=1, N_b=1, N_p=1 |
| `bee_ratio=0.0` | N_b=1 (floor max(1, ...)) |
| `residual always goes to particles` | Varying ratios confirm N_p absorbs remainder |
| `deterministic with same seed` | Two calls produce identical partitioning |

### 13.3 Influence Isolation (12 tests)

| Test | Description |
|---|---|
| Only ACO influence active | `alpha_a=1, alpha_b=alpha_p=alpha_h=0` → selection driven by τ only |
| Only BCO influence active | `alpha_b=1` → selection driven by templates only |
| Only PSO influence active | `alpha_p=1` → selection driven by p_best + g_best only |
| Only visibility active | `alpha_h=1` → selection driven by η only |
| ACO + BCO combined | Both components affect selection proportionally |
| ACO + PSO combined | Both components affect selection proportionally |
| BCO + PSO combined | Both components affect selection proportionally |
| All four active (equal) | Each contributes to selection |
| Zero template count | `template_count=0` → BCO component = ε for all edges |
| Zero cognition + social | `cognition_weight=social_weight=0` → PSO component = ε for all edges |
| Pheromone influence with β=0 | `beta_a=0` → τ⁰ = 1, ACO influence equal for all edges |
| Normalisation with equal candidates | All candidates have equal τ → equal normalised A value |

### 13.4 Normalisation (8 tests)

| Test | Description |
|---|---|
| ACO component normalisation | τ ∈ [τ_min, τ_max] maps to [0, 1] via Eq. (8) |
| BCO component normalisation | match ∈ {ε, 1} maps to [0, 1] via Eq. (9) |
| PSO component normalisation | P_raw ∈ [P_min, P_max] maps to [0, 1] via Eq. (10) |
| Visibility normalisation | H_raw within candidate set maps to [0, 1] via Eq. (11) |
| Equal cost → all η = 1 after norm | When all candidates have identical cost |
| τ at min → norm = 0 | τ = τ_min maps to 0 |
| τ at max → norm = 1 | τ = τ_max maps to 1 |
| No match in BCO → norm = 0 | B_raw = ε → maps to 0 |

### 13.5 Meta-Controller (12 tests)

| Test | Description |
|---|---|
| No activation when diversity > threshold | All div > div_min → weights unchanged |
| Single low-diversity subpopulation decays | div_a < div_min → α_a decays by δ |
| Two low-diversity subpopulations decay | div_a, div_b < div_min → α_a, α_b decay |
| All three low-diversity → heuristic absorbs | α_a, α_b, α_p decay; surplus → α_h |
| Redistribution to non-decayed | α_a decays; Δ_a → α_b and α_p equally |
| Recovery: diversity returns to normal | After low state, recovery_gain added each check |
| Weight bounds enforced | α cannot go below min or above max |
| Normalisation after update | Sum α_a+α_b+α_p preserved after each meta-controller update |
| No update before adapt_interval | K=5; updates only on iteration % K == 0 |
| Multiple consecutive decays | Low diversity for 3 checks → α decays 3× |
| No-op when all subpopulations absent | Edge case: zero individuals in a subpopulation |
| Hysteresis with oscillation | Alternating low/high → α oscillates but remains bounded |

### 13.6 Pheromone Evolution (8 tests)

| Test | Description |
|---|---|
| Local update decreases τ | ρ_local applied, τ → (1−ρ)τ + ρ τ₀ |
| Global update reinforces best route | τ on best-route edges increases toward τ_max |
| Bounds enforced | τ clamped to [τ_min, τ_max] |
| Zero-cost route protection | `deposit=0` if best_cost is inf or NaN |
| Evaporation with no update | τ decays toward τ₀ over time |
| Cross-population global update | Best route from bees reinforces pheromones for ants |
| Multiple updates converge to bounds | Repeated updates converge toward extremes |
| Initialisation | All edges = τ₀ |

### 13.7 Template Extraction (6 tests)

| Test | Description |
|---|---|
| Top-L routes from all subpopulations | Routes sorted by cost; top L become templates |
| Fewer than L complete routes | All complete routes used |
| No complete routes | Templates = empty list |
| Duplicate routes handled | Same route counted once |
| Template update each iteration | New templates derived from current iteration's routes |
| Template order | Templates sorted by ascending cost |

### 13.8 Personal/Global Best Updates (6 tests)

| Test | Description |
|---|---|
| Personal best improves | Lower cost → p_best updated |
| Personal best unchanged | Higher cost → p_best unchanged |
| Global best across all subpopulations | Best route from any kind updates g_best |
| Global best monotonically non-increasing | g_best never increases |
| Global best initialised as inf | First complete route becomes initial g_best |
| No improvement → unchanged | All routes worse → g_best unaffected |

### 13.9 Deterministic Replay (4 tests)

| Test | Description |
|---|---|
| Same seed → same result | Three calls with seed=42 produce identical SwarmResult |
| Different seed → different result | Seed=42 vs seed=99 produce different results (probabilistic) |
| Same seed with subpartitioning | Same seed + same N produce identical partitioning and results |
| Stream-based determinism | Each named stream produces same sequence across runs |

### 13.10 Cross-Component Interaction (6 tests)

| Test | Description |
|---|---|
| Pheromone influences bees | A route from a bee shows τ influence in weight calculation |
| Templates influence ants | Ant selection weight includes BCO template component |
| PSO memory influences ants | Ant selection weight includes p_best/g_best components |
| All four influences present in RouteCandidate metadata | Metadata has alpha_a, alpha_b, alpha_p, alpha_h |
| g_best updated by ant route | ACO's best route sets global best |
| Templates include routes from all subpopulations | At least one template from each subpopulation |

### 13.11 Edge Cases (8 tests)

| Test | Description |
|---|---|
| Dead end | Individual stops at dead end, state = FAILED |
| Blocked edges | Blocked edges excluded from candidates |
| Unreachable destination | All individuals fail; result = failure |
| Empty graph | No edges → all individuals fail immediately |
| Single-source destination where source=dest | Context-validated error |
| NaN cost in edge | Edge filtered out of candidates |
| Source node not in graph | Optimize returns failure |
| Destination node not in graph | Optimize returns failure |

### 13.12 Factory Integration (3 tests)

| Test | Description |
|---|---|
| `SwarmFactory.is_registered("e3hybrid")` | Returns True after import |
| `SwarmFactory.create_algorithm("e3hybrid")` | Returns working `E3HybridRouting` instance |
| `SwarmToRoutingAdapter` end-to-end | Adapter wraps hybrid, `compute_route` succeeds |

**Total estimated test count:** ~83–91 tests (upper bound accounts for subtests expanding in implementation).