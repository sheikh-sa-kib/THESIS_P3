# Bee Colony Optimization (BCO) Algorithm Design

**Status:** Phase 10A — Sections 1–4 approved. Section 5 written, awaiting approval.

---

## Section 1: Literature Review and Variant Selection

This chapter establishes the Bee Colony Optimization metaheuristic from first principles and provides the mathematical foundation required for implementation. Section 1 examines the biological foraging behaviour of honey bees and traces its evolution through the published literature, culminating in a rigorous variant comparison and the selection of constructive BCO (Teodorović, 2009) for the E³-Hybrid framework. Section 2 formalises every component of the selected variant as a system of equations — the graph model, the bee agent, the forward and backward pass decision rules, the recruitment mechanism, and the termination conditions — each of which maps directly to a distinct component in the implementation. The notation introduced in Section 2 is maintained consistently in the architecture, configuration, and testing sections that follow.

### 1.1 Biological Inspiration

#### 1.1.1 Honey Bee Foraging Behaviour

The Bee Colony Optimization metaheuristic draws its inspiration from the foraging behaviour of honey bees (*Apis mellifera*). In nature, a bee colony distributes its foraging effort across flower patches through a decentralized, collective decision-making process that exhibits the four essential properties of swarm intelligence identified by Bonabeau et al. (1999): positive feedback, negative feedback, fluctuations (randomness), and multiple interactions.

**Scout bees.** A small fraction of the foraging force (typically 5–10%) acts as scouts (Seeley, 1995). These bees fly outward from the hive, searching for new flower patches. For the purposes of swarm intelligence modelling, a scout's search is treated as random — it has no prior information about where nectar might be found. When a scout discovers a patch, it evaluates the patch's quality (nectar amount, sugar concentration, distance from hive) and returns to the hive.

**The waggle dance.** Upon returning, a successful scout performs a waggle dance on the vertical face of the honeycomb. The dance communicates three pieces of information to the waiting bees (recruits) in the hive: (1) the direction of the food source relative to the sun, encoded by the angle of the dance relative to vertical; (2) the distance to the food source, encoded by the duration of the waggle phase; and (3) the quality of the food source, encoded by the dance's intensity and duration (von Frisch, 1967; Seeley, 1995). This dance is the colony's primary communication mechanism for food source information.

**Recruiter bees and recruitment.** Bees that follow the waggle dance are termed recruits or follower bees. After observing one or more dances, a recruit leaves the hive to search for the advertised flower patch. The probability that a recruit follows a particular dance is proportional to the dance's intensity — higher-quality patches attract more followers. This creates a positive feedback loop: good patches are advertised more vigorously, attract more recruits, and are exploited more thoroughly.

**Forager bees and nectar collection.** Once a bee arrives at a flower patch, it collects nectar and returns to the hive. Upon return, the bee may perform its own waggle dance if the patch remains productive, thereby recruiting additional foragers. If the patch's quality declines (nectar depleted, weather changes), the bee ceases dancing and may eventually abandon the patch.

**Abandonment of poor food sources.** When a patch is no longer rewarding, bees stop recruiting for it. The colony's collective attention shifts away from depleted patches without any central command. This negative feedback mechanism prevents the colony from wasting energy on unproductive sites.

**Collective decision making.** The colony's foraging strategy emerges from the individual decisions of thousands of bees, each following simple rules: scout randomly, dance for good patches, follow dances, abandon poor patches. There is no central controller. The colony converges on the best available patches through this decentralized process.

#### 1.1.2 Mapping to Routing Framework

| Biological Concept | BCO Routing Analogue |
|--------------------|----------------------|
| Scout bee | Routes constructed from scratch (exploration phase) |
| Flower patch | A complete route from source to destination |
| Nectar quality (patch value) | Route quality (inverse of total cost) |
| Waggle dance | Information sharing about route quality among bees |
| Recruiter bee | Bee that shares its route information (loyalty decision) |
| Follower bee (recruit) | Bee that adopts information from a recruiter |
| Dance intensity | Probability of being followed (proportional to route quality) |
| Positive feedback | Good routes attract more bees to explore similar corridors |
| Negative feedback | Poor routes are abandoned; bees switch to better-known routes |
| Patch abandonment | A bee ceases to promote its route when better alternatives exist |
| Scout random search | Random proportional selection of next node during route construction |
| Hive | The central optimization context (SwarmContext) |

This mapping is consistent with the formulation of Teodorović (2008, 2009) and the applications surveyed by Davidović et al. (2015). The key difference between biological bees and artificial BCO agents is that artificial bees operate on a discrete graph representation (DirectedGraph) rather than continuous Euclidean space.

### 1.2 Literature Survey

#### 1.2.1 Origins: The Bee System (Lučić & Teodorović, 2001–2003)

The earliest bee-inspired combinatorial optimization method was the **Bee System (BS)**, introduced by Lučić and Teodorović. The Bee System was first presented at the TRISTAN IV Triennial Symposium on Transportation Analysis (Lučić & Teodorović, 2001) and subsequently elaborated in a journal publication (Lučić & Teodorović, 2003). The Bee System applied the bee foraging metaphor to the Traveling Salesman Problem (TSP) and demonstrated that the approach produced competitive results.

**Relevance to this thesis:** The Bee System established the foundational mapping between bee foraging behaviour and combinatorial optimization on graphs. However, the Bee System lacked the explicit forward pass / backward pass structure that characterizes modern BCO, and its recruitment mechanism was relatively simple.

#### 1.2.2 Bee Colony Optimization — BCO (Teodorović & Dell'Orco, 2005)

The Bee Colony Optimization metaheuristic was formally introduced by Teodorović and Dell'Orco at the 10th International Symposium on Operational Research (SOR'05) in Slovenia (Teodorović & Dell'Orco, 2005). The paper "Bee Colony Optimization — A Cooperative Learning Approach to Complex Transportation Problems" presented BCO as a general-purpose metaheuristic for combinatorial optimization under uncertainty. The ride-matching problem served as the case study.

Key characteristics of the original BCO formulation:
- A population of B artificial bees, each responsible for one solution
- Two alternating phases per iteration: **forward pass** (bees build/improve solutions) and **backward pass** (bees share information and make loyalty/recruitment decisions)
- Stochastic construction of solutions using node-by-node or component-by-component decisions
- Loyalty decisions based on solution quality compared to colony average
- Recruitment (waggle dance) where better solutions attract more followers

**Relevance to this thesis:** This is the foundational BCO paper. The forward/backward pass structure is directly compatible with the SwarmLifecycle iteration model. The ride-matching case study demonstrates BCO's applicability to transportation routing problems specifically.

#### 1.2.3 BCO Principles and Applications (Teodorović et al., 2006)

Teodorović, Lučić, Marković, and Dell'Orco (2006) published "Bee Colony Optimization: Principles and Applications" in the IEEE Conference on Neural Networks (NEUREL 2006). This paper consolidated the BCO framework, described the Bee System (BS) and Fuzzy Bee System (FBS) as specific instantiations, and presented three case studies: TSP, ride-matching, and routing and wavelength assignment in optical networks.

**Relevance to this thesis:** This paper demonstrates BCO's versatility across different problem domains and provides the algorithmic framework used by subsequent applications. The Fuzzy Bee System variant is discussed in Section 1.4.3 below.

#### 1.2.4 BCO for Transportation Engineering (Teodorović, 2008)

Teodorović (2008) published a comprehensive survey, "Swarm Intelligence Systems for Transportation Engineering: Principles and Applications", in *Transportation Research Part C*. This paper surveyed swarm intelligence methods (including ACO, BCO, and PSO) applied to transportation problems such as VRP, transit network design, traffic signal control, and ride-matching. The BCO section provided pseudo-code and parameter guidelines.

**Relevance to this thesis:** This paper establishes BCO as a recognized method in the transportation engineering literature. It provides the methodological justification for applying BCO to EV routing within a transportation network.

#### 1.2.5 BCO Textbook Chapter (Teodorović, 2009)

Teodorović (2009) contributed the chapter "Bee Colony Optimization (BCO)" to *Innovations in Swarm Intelligence* (Springer). This chapter is the most complete single reference on BCO. It provides:
- Detailed biological inspiration with honey bee foraging behaviour
- Step-by-step pseudo-code for the constructive BCO algorithm
- Discussion of parameter settings (number of bees, forward/backward pass structure, recruitment threshold)
- Extensions including BCOi (improvement-based variant) and parallel BCO
- Application domains: TSP, VRP, ride-matching, transit network design, scheduling, location problems

**Relevance to this thesis:** This chapter is the primary reference for the BCO variant selected for this thesis. The pseudo-code and parameter guidelines directly inform the implementation.

#### 1.2.6 BCO for Vehicle Routing with Time Windows (Nikolić & Teodorović, 2013)

Nikolić and Teodorović (2013) applied BCO to the Vehicle Routing Problem with Time Windows (VRPTW) using Solomon's benchmark instances. They employed the improvement-based BCO variant (BCOi), where each bee holds a complete solution and modifies it iteratively. The algorithm produced competitive results on standard benchmarks.

**Relevance to this thesis:** This paper directly demonstrates BCO's effectiveness on vehicle routing problems, which is the problem class most closely related to this thesis's EV routing domain. The improvement-based variant is discussed as a future extension.

#### 1.2.7 BCO Survey (Davidović, Teodorović, & Šelmić, 2015)

Davidović, Teodorović, and Šelmić (2015) published a comprehensive two-part survey of BCO in the *Yugoslav Journal of Operations Research*. Part I (Davidović et al., 2015) described the algorithm, its variants (constructive BCO, BCOi, parallel BCO), and convergence properties. Part II (Teodorović, Šelmić, & Davidović, 2015) surveyed applications across routing, location, scheduling, medicine, chemistry, and continuous optimization.

**Relevance to this thesis:** This survey provides the definitive taxonomy of BCO variants and their applications. It is the most comprehensive single source for understanding the BCO landscape and selecting the appropriate variant.

#### 1.2.8 ABC vs. BCO: Critical Distinction

It is essential to distinguish BCO from the **Artificial Bee Colony (ABC)** algorithm, as the two are frequently conflated in the literature.

**ABC (Karaboga, 2005)** was introduced for continuous numerical optimization. It models three types of bees (employed, onlooker, scout) that perturb candidate solutions represented as real-valued position vectors in a continuous search space. The update mechanism is a stochastic perturbation of vector components. ABC has been adapted for some combinatorial problems (e.g., Szeto et al., 2011, for capacitated VRP), but these adaptations require encoding/decoding procedures that map continuous positions to discrete routes. ABC is fundamentally a continuous optimization method.

**BCO (Teodorović & Dell'Orco, 2005)** was introduced specifically for combinatorial optimization, particularly transportation problems. Bees operate directly on the discrete solution components (e.g., graph edges, customer sequences). The forward/backward pass structure has no analogue in ABC. BCO's recruitment mechanism is based on comparing solution quality within the current iteration, not on perturbing position vectors.

**Why this distinction matters:** Selecting ABC for a graph-based routing problem would require a discrete encoding layer, adding complexity and potentially losing the natural graph mapping that makes BCO suitable. BCO operates directly on the graph, constructing routes edge-by-edge, which maps naturally to the routing problem.

### 1.3 Variant Comparison

| Criterion | BCO (Teodorović, 2009) | ABC (Karaboga, 2005) | BCOp (Davidović et al., 2015) | Fuzzy BCO (Davidović et al., 2015) |
|-----------|------------------------|---------------------|-------------------------------|---------------------------------------|
| **Year** | 2009 (matured from 2005) | 2005 | 2011 | 2012 |
| **Primary domain** | Combinatorial optimization (transportation) | Continuous numerical optimization | Combinatorial optimization | Combinatorial optimization under uncertainty |
| **Routing suitability** | High — designed for transportation, demonstrated on TSP, VRP, VRPTW | Low — designed for continuous optimization; requires encoding layer | High — adds pheromone trails to BCO | Moderate — fuzzy component adds flexibility for uncertain costs |
| **Dynamic environment support** | Good — forward/backward passes adapt each iteration | Weak — no mechanism for dynamic changes in topology | Good — pheromone trails store history | Good — fuzzy logic handles uncertain edge costs |
| **Communication mechanism** | Waggle dance (solution quality comparison, probabilistic recruitment) | None (bees share info through the colony's global best solution) | Waggle dance + pheromone trails | Fuzzy waggle dance (approximate reasoning) |
| **Exploration strategy** | Random proportional node selection during forward pass; scout bees | Random perturbation of position vector components | Random proportional selection + pheromone-guided exploration | Fuzzy stochastic selection |
| **Exploitation strategy** | Recruitment concentrates bees on high-quality routes | Bees move toward global best solution | Pheromone reinforcement of good routes; recruitment | Fuzzy aggregation of quality signals |
| **Computational complexity** | O(I × B × P_avg) — same order as ACO | O(I × N × D) where D = dimensions | O(I × B × P_avg) + O(E) pheromone | O(I × B × P_avg) + fuzzification overhead |
| **Compatibility with SwarmLifecycle** | High — forward/backward pass maps to two-phase iteration | Low — no natural mapping to forward/backward passes | High — same structure as BCO with added pheromone step | Moderate — requires fuzzy inference engine |
| **Compatibility with SwarmRandom** | High — stochastic decisions can use named streams | High — perturbation can use named streams | High — same as BCO + pheromone randomness | High — fuzzification can use named streams |
| **Compatibility with RoutingAlgorithm Protocol** | High — produces RouteCandidate solutions | Low — produces continuous vectors, not routes | High — same as BCO | Moderate — fuzzy costs require adaptation |
| **Benchmark fairness** | High — uses same cost function as Dijkstra/A*/ACO | Low — requires route encoding/decoding | High — same as BCO | Moderate — fuzzy costs may differ from baseline cost |
| **Integration into E³-Hybrid** | High — natural complement to ACO (different mechanism) | Low — fundamentally different problem representation | Moderate — pheromone overlaps with ACO | Moderate — fuzzy component adds complexity |
| **Parameter count** | 5–6 (bees, forward steps, recruitment threshold, etc.) | 3–4 (colony size, limit, dimension) | 6–7 (BCO params + pheromone params) | 7–8 (BCO params + fuzzy membership params) |

### 1.4 Why Other Variants Were Rejected

#### 1.4.1 Artificial Bee Colony (ABC)

**Rejected because** ABC is designed for continuous numerical optimization (see Section 1.2.8 for the full distinction). Translating a graph routing problem into ABC's continuous vector space would require encoding each route as a fixed-length real-valued vector and decoding the result back into a valid graph path — both problem-dependent and lossy operations. More critically, ABC's random-perturbation exploration mechanism does not exploit graph topology, making it less sample-efficient for routing than BCO, which operates directly on the graph.

#### 1.4.2 BCO with Pheromone (BCOp)

**Rejected because** the pheromone mechanism overlaps with what ACS already provides in Phase 9B. The primary reason for selecting BCO as a distinct algorithm is to provide a meaningfully different optimization mechanism (recruitment-based) for the E³-Hybrid comparison. Adding pheromone trails to BCO would create a hybrid that is difficult to attribute to either parent algorithm, complicating the thesis analysis of which mechanism contributes what. If pheromone guidance is desired, ACS is already implemented. For BCO, the pure recruitment mechanism provides maximal algorithmic diversity.

#### 1.4.3 Fuzzy BCO

**Rejected because** the fuzzy logic component adds parameter complexity (membership functions, fuzzy rules, defuzzification) without a clear benefit for the thesis scope. The existing CostProvider interface already handles uncertainty in edge costs (congestion factor, hazard penalties, emergency penalties). Adding a second layer of fuzziness at the BCO level would make it difficult to determine whether performance differences stem from the recruitment mechanism or the fuzzy preprocessing. Fuzzy BCO may be revisited as a future extension.

#### 1.4.4 Bee System (Lučić & Teodorović, 2003)

**Rejected because** the Bee System is a precursor to BCO that lacks the explicit forward/backward pass structure and the formalized recruitment mechanism. Selecting the Bee System would mean implementing a less mature algorithm that has been superseded by the more refined BCO framework. The Bee System is historically important but not the best choice for a research implementation.

#### 1.4.5 Other Notable Variants

- **Adaptive BCO**: These variants introduce online parameter adaptation that improves performance on specific benchmarks (e.g., adaptive tuning for VRPTW). However, for a controlled thesis comparison, static parameters are preferred to isolate the algorithm's intrinsic behaviour from auxiliary adaptation mechanisms.

- **Parallel BCO**: Parallelization of the bee population is a performance optimization, not an algorithmic variant. The current thesis scope requires sequential execution (as per Phase 9B design decisions). Parallel BCO is deferred as a future enhancement.

### 1.5 How the Selected BCO Fits the Existing E³-Hybrid Architecture

#### DirectedGraph
BCO reads graph topology through SwarmContext.graph (read-only). During the forward pass, each bee selects the next edge from the outgoing edges of its current node, using visibility information derived from CostProvider costs. No graph modification occurs.

#### CostProvider
BCO queries edge costs through SwarmContext.cost_calculator (CompositCostCalculator). Edge costs are used to compute route quality (nectar), which drives both the loyalty decision (backward pass) and the recruitment probability. Blocked edges (cost = inf) are excluded from candidate lists, identical to how ACS handles them.

#### Routing Framework
BCO implements the SwarmAlgorithm Protocol (not RoutingAlgorithm directly). It produces SwarmResult containing RouteCandidate objects, which are converted to RoutingResult by SwarmToRoutingAdapter. This is the same integration pattern used by ACS in Phase 9B.

#### Swarm Infrastructure
BCO uses:
- **SwarmLifecycle**: The forward pass / backward pass iteration structure maps naturally onto the lifecycle's update_fn callback. Each iteration performs one forward pass (route construction) followed by one backward pass (loyalty + recruitment).
- **SwarmRandom**: All stochastic decisions use SwarmRandom named streams ("bco.selection", "bco.loyalty", "bco.recruitment").
- **SwarmConfig**: Population size = number of bees. Max iterations = BCO iterations. Hyperparameters: forward_steps, recruitment_threshold, etc.
- **SwarmContext**: Read-only context with graph, cost_calculator, config, routing_request.
- **SwarmResult**: BCO returns SwarmResult with best_solution as RouteCandidate.

#### Benchmark Framework
BCO runs through BenchmarkRunner via SwarmToRoutingAdapter, exactly as ACS does. No modifications to BenchmarkRunner are required. BCO is compared against Dijkstra, A*, and ACS using identical benchmark scenarios.

#### Decision Engine
The Decision Engine receives RouteCandidate objects from BCO (via SwarmResult.candidates). It evaluates candidates solely on total_cost, never inspecting BCO-specific internals.

#### Emergency Framework
Emergency effects reach BCO through CostProvider only, exactly as specified for ACS in Phase 9A (Section 10). BCO never imports emergency modules, never accesses MutableEdgeState directly, and never subscribes to emergency events.

#### Communication Framework
BCO does not use the Communication Framework. All information sharing (recruitment) is internal to the BCO algorithm instance — there is no inter-vehicle or inter-colony communication. This is the same restriction applied to ACS (Phase 9A, Section 14.1).

### 1.6 Design Decision

```
DD-BCO-001: BCO Variant Selection
─────────────────────────────────
Selected: Bee Colony Optimization (Teodorović, 2009)

Rationale:
  1. BCO is designed for combinatorial optimization on graphs, making it
     a natural fit for EV routing without encoding/decoding overhead.
  2. The forward/backward pass structure maps cleanly onto the existing
     SwarmLifecycle iteration model.
  3. BCO's recruitment-based exploration/exploitation is meaningfully
     different from ACS's pheromone-based mechanism, providing fair
     algorithmic diversity for the E³-Hybrid comparison.
  4. BCO is well-documented in transportation literature with published
     benchmark results for VRP and VRPTW.
  5. BCO integrates with all existing E³-Hybrid infrastructure through
     the same patterns established by ACS in Phase 9B.
  6. ABC, BCOp, Fuzzy BCO, and other variants were rejected for specific
     technical reasons documented in Section 1.4.

Primary Reference:
  Teodorović, D. (2009). "Bee colony optimization (BCO)". In C. P. Lim,
  L. C. Jain, & S. Dehuri (Eds.), Innovations in Swarm Intelligence
  (pp. 39–60). Springer.

Status: Proposed for Phase 10A design document.
```

### References

1. Bonabeau, E., Dorigo, M., & Theraulaz, G. (1999). *Swarm Intelligence: From Natural to Artificial Systems*. Oxford University Press.

2. Davidović, T., Teodorović, D., & Šelmić, M. (2015). Bee colony optimization part I: The algorithm overview. *Yugoslav Journal of Operations Research*, 25(1), 33–56.

3. Karaboga, D. (2005). An idea based on honey bee swarm for numerical optimization. Technical Report TR06, Erciyes University, Engineering Faculty, Computer Engineering Department.

4. Lučić, P., & Teodorović, D. (2001). Bee system: Modeling combinatorial optimization transportation engineering problems by swarm intelligence. *Preprints of the TRISTAN IV Triennial Symposium on Transportation Analysis*, 441–445. São Miguel, Azores Islands.

5. Lučić, P., & Teodorović, D. (2003). Computing with bees: Attacking complex transportation engineering problems. *International Journal on Artificial Intelligence Tools*, 12(3), 375–394.

6. Nikolić, M., & Teodorović, D. (2013). Empirical study of the bee colony optimization (BCO) algorithm for the vehicle routing problem with time windows (VRPTW). *Proceedings of the 1st Logistics International Conference*, 126–131. Belgrade, Serbia.

7. Seeley, T. D. (1995). *The Wisdom of the Hive: The Social Physiology of Honey Bee Colonies*. Harvard University Press.

8. Szeto, W. Y., Wu, Y., & Ho, S. C. (2011). An artificial bee colony algorithm for the capacitated vehicle routing problem. *European Journal of Operational Research*, 215(1), 126–135.

9. Teodorović, D. (2008). Swarm intelligence systems for transportation engineering: Principles and applications. *Transportation Research Part C: Emerging Technologies*, 16(6), 651–667.

10. Teodorović, D. (2009). Bee colony optimization (BCO). In C. P. Lim, L. C. Jain, & S. Dehuri (Eds.), *Innovations in Swarm Intelligence* (pp. 39–60). Springer.

11. Teodorović, D., & Dell'Orco, M. (2005). Bee colony optimization — A cooperative learning approach to complex transportation problems. *Proceedings of the 10th International Symposium on Operational Research (SOR'05)*, 51–60. Slovenia.

12. Teodorović, D., & Dell'Orco, M. (2008). Mitigating traffic congestion: Solving the ride-matching problem by bee colony optimization. *Transportation Planning and Technology*, 31(2), 135–152.

13. Teodorović, D., Lučić, P., Marković, G., & Dell'Orco, M. (2006). Bee colony optimization: Principles and applications. *Proceedings of the 8th Seminar on Neural Network Applications in Electrical Engineering (NEUREL 2006)*, 151–156. IEEE.

14. Teodorović, D., Šelmić, M., & Davidović, T. (2015). Bee colony optimization part II: The application survey. *Yugoslav Journal of Operations Research*, 25(2), 185–219.

15. von Frisch, K. (1967). *The Dance Language and Orientation of Bees*. Harvard University Press.

---

The literature surveyed above confirms that constructive BCO (Teodorović, 2009) is the variant best suited to the EV routing problem addressed in this thesis: it operates directly on graph representations, its forward/backward pass structure integrates cleanly with the existing SwarmLifecycle, and its recruitment-based exploration provides meaningful algorithmic contrast to the pheromone-based ACS already implemented. The following section translates each component of this selected variant into a precise mathematical formulation. Every equation presented below is designed to admit a direct, one-to-one translation into Python code in Phase 10B.

## Section 2: Mathematical Formulation

### 2.1 Notation

| Symbol | Meaning | Type / Domain |
|--------|---------|---------------|
| `G` | Directed graph `(V, E)` | `DirectedGraph` |
| `V` | Set of nodes | `set[NodeId]`, `\|V\| = N` |
| `E` | Set of directed edges | `set[EdgeId]`, `\|E\| = M` |
| `N` | Number of nodes | `int` |
| `M` | Number of edges | `int` |
| `s` | Source (origin) node | `NodeId ∈ V` |
| `d` | Destination (target) node | `NodeId ∈ V` |
| `c(i, j)` | Composite cost of edge `(i, j)` | `ℝ⁺ ∪ {∞}`, from `CostProvider.cost()` |
| `ε` | Small positive constant (machine epsilon) | `float`, default `1 × 10⁻¹²` |
| `η(i, j)` | Heuristic visibility of edge `(i, j)` | `ℝ⁺`, defined in §2.6 |
| `β` | Visibility weighting exponent | `ℝ₀⁺`, configurable |
| `δ` | Template influence strength | `ℝ₀⁺`, configurable |
| `B` | Number of bees (population size) | `int`, configurable |
| `I_max` | Maximum number of iterations | `int`, configurable |
| `NS` | Forward steps per iteration | `int`, configurable |
| `i` | Current iteration index | `int`, `0 ≤ i < I_max` |
| `k` | Bee index | `int`, `1 ≤ k ≤ B` |
| `K` | Elite bee count | `int`, configurable, `0 ≤ K ≤ B` |
| `N(i)` | Set of feasible, unvisited neighbours of node `i` | `set[NodeId]` |
| `R_k` | Route constructed by bee `k` in current iteration | `list[EdgeId]` |
| `\|R_k\|` | Path length of `R_k` in edges | `int` |
| `L_k` | Total cost of route `R_k` | `ℝ⁺`, `L_k = Σ_{(i,j) ∈ R_k} c(i,j)` |
| `Q_k` | Quality (nectar) of route `R_k` | `ℝ⁺`, `Q_k = 1 / (L_k + ε)` |
| `O_k` | Normalised quality of bee `k` | `[0, 1]` |
| `Q_max` | Maximum quality in current iteration | `ℝ⁺` |
| `Q_min` | Minimum quality in current iteration | `ℝ⁺` |
| `L_max` | Maximum cost in current iteration | `ℝ⁺` |
| `L_min` | Minimum cost in current iteration | `ℝ⁺` |
| `L_avg` | Mean cost in current iteration | `ℝ⁺` |
| `T_k` | Template route of bee `k` (from loyalty/recruitment) | `list[EdgeId]` |
| `σ_k` | Bee `k` state flag | `{constructing, complete, failed}` |
| `I_T(i, j)` | Indicator: is edge `(i, j)` in template `T_k`? | `{0, 1}` |
| `L` | Set of loyal bee indices after backward pass | `set[int]`, `L ⊆ {1, …, B}` |
| `U` | Set of uncommitted bee indices after backward pass | `set[int]`, `U ⊆ {1, …, B}` |
| `ρ_k` | Random threshold for bee `k` loyalty decision | `[0, 1]`, from `SwarmRandom("bco.loyalty")` |
| `λ_k` | Random threshold for bee `k` recruiter selection | `[0, 1]`, from `SwarmRandom("bco.recruitment")` |
| `p_k^loyal` | Probability bee `k` remains loyal | `[0, 1]` |
| `p_k^recruit` | Probability a recruit selects bee `k` as recruiter | `[0, 1]` |
| `θ` | Convergence threshold | `ℝ⁺`, configurable |
| `Ω` | Stall limit (consecutive non-improving iterations) | `int`, configurable |
| `τ_max` | Maximum wall-clock runtime | `ℝ⁺`, configurable |
| `t` | Elapsed wall-clock time | `ℝ₀⁺` |
| `P_k` | Path length (edge count) of bee `k`'s route | `int`, `P_k = \|R_k\|` |
| `P_avg` | Mean path length across all bees in an iteration | `float`, `P_avg = (1/B) × Σ_{k=1}^{B} P_k` |
| `P_max` | Maximum path length across all bees | `int`, `P_max = max_k P_k` |
| `d_avg` | Mean out-degree of nodes visited during route construction | `float` |

The notation above is used consistently throughout this document and will map directly to field names in the Phase 10B implementation.

### 2.2 Objective Function

Let `R = ⟨e₁, e₂, …, e_{|R|}⟩` be a directed path from source `s` to destination `d`, where each `e_m ∈ E` is a directed edge `(i_m, j_m)` with `i_1 = s`, `j_{|R|} = d`, and `j_m = i_{m+1}` for all `m`. The objective is to minimise the total composite cost of the path:

```
f(R) = Σ_{m=1}^{|R|} c(e_m)                                                (1)
```

where `c(e_m)` is the composite cost of edge `e_m` returned by `CostProvider.cost()`. A route is feasible iff it satisfies the following constraints:

```
j_{|R|} = d                                                                 (2a)
c(e_m) < ∞  for all m ∈ {1, …, |R|}                                       (2b)
i_m ≠ i_n  for all m ≠ n  (simple path — no cycles)                       (2c)
```

The optimal solution is a feasible route `R*` that minimises `f(R)`. Because the problem is NP-hard in general (it subsumes shortest path with resource constraints), BCO seeks a near-optimal feasible route within the computational budget.

**Implementation mapping:** Equation (1) corresponds to `RouteCandidate.total_cost` in the existing framework.

### 2.3 Graph Representation

The road network is modelled as a directed graph:

```
G = (V, E)                                                                  (3)
```

where:

- `V = {v_1, v_2, …, v_N}` is the set of nodes (intersections, waypoints).
- `E ⊆ V × V` is the set of directed edges (road segments). Edge `(i, j)` is directed from node `i` to node `j`.
- `c: E → ℝ⁺ ∪ {∞}` is the edge cost function that returns the composite traversal cost of edge `(i, j)`.

Blocked edges (due to emergencies, road closures) have `c(i, j) = ∞` and are excluded from the feasible neighbour set `N(i)` during route construction.

The graph is accessed **read-only** through `SwarmContext.graph` (a `GraphSnapshot`). BCO never modifies the graph.

### 2.4 Bee Representation

Each bee `k ∈ {1, …, B}` is an autonomous agent that constructs one route per iteration. The state of bee `k` at iteration `i` is captured by the tuple:

```
S_k(i) = (R_k(i), L_k(i), Q_k(i), T_k(i), σ_k(i))                          (4)
```

where:

| Component | Symbol | Meaning |
|-----------|--------|---------|
| Constructed route | `R_k(i)` | Sequence of edges `⟨e_1, …, e_{|R|}⟩` built during the forward pass |
| Route cost | `L_k(i)` | Total cost computed by `f(R_k(i))` |
| Route quality | `Q_k(i)` | Inverse cost `1 / (L_k(i) + ε)` — the "nectar" value |
| Template route | `T_k(i)` | Route retained from the previous backward pass (loyalty or recruitment) |
| Bee state | `σ_k(i)` | One of `{constructing, complete, failed, recruited}` |

**Initial state** (before the first iteration): Each bee has an empty template `T_k(0) = ∅` and state `σ_k(0) = constructing`. The template is populated after the first backward pass.

### 2.5 Route Construction Model

Route construction occurs during the **forward pass** of each iteration. Bee `k` begins at the source node `s` and selects edges sequentially until it reaches the destination `d` or exhausts the forward-step budget `NS`.

At construction step `t` (`1 ≤ t ≤ NS`), bee `k` is at node `i_t`. The set of candidate next nodes is:

```
N(i_t) = { j ∈ V : (i_t, j) ∈ E  ∧  c(i_t, j) < ∞  ∧  j ∉ visited_k(t) }   (5)
```

where `visited_k(t)` is the set of nodes already visited by bee `k` in the current forward pass. The visited set prevents cycles.

If `N(i_t) = ∅`, the bee is blocked: it cannot proceed. Its route terminates at `i_t` with state `σ_k = failed`, and its route cost is penalised. If `i_t = d`, the bee has reached the destination and `σ_k = complete`.

The forward pass of each iteration reconstructs each bee's route **from the source node** rather than extending the previous route incrementally. However, the construction is not independent of prior iterations: the template `T_k` (populated during the previous backward pass via loyalty or recruitment) biases the **edge selection probabilities** (Section 2.8) by increasing the likelihood of choosing edges present in `T_k`. The **set** of feasible edges is unaffected by the template — only the probability distribution over those edges is biased.

### 2.6 Visibility (Heuristic) Function

The heuristic visibility of edge `(i, j)` is the inverse of its composite cost, offset by a small constant to ensure numerical stability:

```
η(i, j) = 1 / (c(i, j) + ε)                                                (6)
```

Properties:

- **Blocked edges:** If `c(i, j) = ∞`, then `η(i, j) = 0` (never selected).
- **Domain:** `η(i, j) ∈ (0, 1/ε)` for feasible edges, `η = 0` for blocked edges.
- **Efficiency:** Visibility is computed **once** per routing request and cached, because the `CostProvider` does not change during a single BCO run. If the graph changes (emergency event), the Decision Engine issues a new routing request, which creates a fresh `SwarmContext` and recomputes visibility.
- **Implementation:** In Phase 10B, `η(i, j)` is stored as a `dict[EdgeId, float]` keyed by `EdgeId`, populated once at initialisation.

### 2.7 Route Quality Function

The quality (nectar) of route `R_k` constructed by bee `k` is:

```
Q_k = 1 / (L_k + ε)                                                        (7)

where  L_k = f(R_k)  (the total composite cost from Equation (1)).
```

The quality function satisfies:
- Lower cost → higher quality (a bee with a cheaper route has more nectar).
- `Q_k → 1/ε` as `L_k → 0` (theoretical upper bound; path costs are positive in practice).
- `Q_k → 0` as `L_k → ∞` (very poor routes have negligible quality).

For failed routes (bee blocked before reaching destination), the cost is penalised:

```
L_k = ∞  ⇒  Q_k = 0                                                       (8)
```

A quality of zero ensures the bee will abandon its route in the loyalty decision (Section 2.10).

### 2.8 Edge Selection Probability (Forward Pass)

During the forward pass, bee `k` at node `i` selects the next node `j` from `N(i)` with probability:

```
p_k(i, j) = [ η(i, j)^β × (1 + δ × I_{T_k}(i, j)) ] / Σ_{u ∈ N(i)} [ η(i, u)^β × (1 + δ × I_{T_k}(i, u)) ]      (9)
```

where:

| Term | Meaning |
|------|---------|
| `η(i, j)^β` | Heuristic desirability of edge `(i, j)`, raised to power `β` |
| `δ ≥ 0` | Template influence parameter — controls how strongly the template biases edge selection |
| `I_{T_k}(i, j) = 1` | If edge `(i, j)` is present in bee `k`'s template route `T_k` |
| `I_{T_k}(i, j) = 0` | Otherwise |

**Special case — first iteration:** All template routes are empty (`T_k = ∅`), so `I_{T_k}(i, j) = 0` for all edges. Equation (9) reduces to:

```
p_k(i, j) = η(i, j)^β / Σ_{u ∈ N(i)} η(i, u)^β                           (10)
```

which is a purely heuristic-guided stochastic selection.

**Special case — blocked node:** If `N(i) = ∅`, the bee is blocked and its route terminates. The bee does not make a selection.

**Special case — destination reached:** If `i = d`, the bee stops constructing (no selection needed).

The interaction between `β` and `δ` controls the exploration–exploitation balance in BCO. The visibility exponent `β` governs how strongly the bee prefers cheap edges over expensive ones in the absence of template information. When `β = 0`, all feasible edges have equal weight `η(i, j)^0 = 1`, and selection is purely random among neighbours — this is **maximal exploration** at the edge level. As `β` increases, the weight of cheaper edges grows exponentially relative to expensive ones, and the bee becomes increasingly **greedy** in its local decisions. Very high `β` (e.g., `β > 5`) causes the bee to deterministically select the single cheapest outgoing edge at every node, eliminating stochasticity during construction. In practice, moderate values (`β ≈ 1–3`) provide a balance: cheaper edges are favoured, but expensive edges retain a non-zero chance of selection, preserving diversity.

The template strength `δ` controls how much the bee's **learned knowledge** (its template route from the previous backward pass) overrides the heuristic visibility. When `δ = 0`, the template has no influence, and every bee behaves as in the first iteration regardless of its history — this is **pure exploration** across iterations. As `δ` increases, edges that appear in the bee's template receive a multiplicative bonus `(1 + δ)` in the selection weight, making them disproportionately likely to be chosen again. This is **exploitation**: bees preferentially reconstruct routes similar to those that performed well previously. The template mechanism is the primary source of inter-iteration learning in BCO, analogous to how pheromone trails serve as the memory mechanism in ACS. However, because the template is a binary indicator (an edge either is or is not in the template), rather than a continuously valued signal, BCO's exploitation is less finely graded than ACS's pheromone-based exploitation. This coarser memory is a deliberate feature: it prevents premature convergence and maintains higher population diversity.

### 2.9 Forward Pass Algorithm

Algorithm 1 describes the forward pass executed by each bee `k` in iteration `i`.

```
Algorithm 1: ForwardPass(k, s, d, NS, T_k, β, δ)
────────────────────────────────────────────────────
  Input:  Bee index k, source s, destination d,
          forward steps NS, template T_k,
          visibility weight β, template strength δ
  Output: Route R_k, total cost L_k, state σ_k

  1:  R_k ← ∅                         // empty edge sequence
  2:  visited ← {s}                   // start node visited
  3:  current ← s                     // current node
  4:  σ_k ← constructing
  5:
  6:  for step ← 1 to NS do
  7:      if current = d then
  8:          σ_k ← complete
  9:          break                    // reached destination
 10:      end if
 11:
 12:      N ← feasible_neighbours(current, visited)
 13:      if N = ∅ then
 14:          σ_k ← failed
 15:          break                    // blocked — no outgoing feasible edges
 16:      end if
 17:
 18:      // Compute selection probabilities (Equation 9)
 19:      for each u ∈ N do
 20:          w_u ← η(current, u)^β × (1 + δ × I_T(current, u))
 21:      end for
 22:      Z ← Σ_{u ∈ N} w_u
 23:      p_u ← w_u / Z  for all u ∈ N
 24:
 25:      // Select next node via roulette wheel
 26:      j ← roulette_select(N, p, stream="bco.selection")
 27:
 28:      // Traverse edge
 29:      R_k ← R_k + [(current, j)]            // sequence append
 30:      visited ← visited ∪ {j}              // set insertion
 31:      current ← j
 32:  end for
 33:
 34:  if σ_k = constructing and current ≠ d then
 35:      σ_k ← failed                 // exhausted NS without reaching destination
 36:  end if
 37:
 38:  L_k ← Σ_{(i,j) ∈ R_k} c(i, j)
 39:  return (R_k, L_k, σ_k)
```

**Key properties:**
- Each bee's forward pass is **independent** — no communication between bees during construction.
- The `roulette_select` function uses `SwarmRandom.get_stream("bco.selection")` for deterministic reproducibility.
- If the destination is reached before `NS` steps, the bee stops early.

### 2.10 Backward Pass Algorithm

The backward pass consists of three sequential phases: evaluation, loyalty decision, and recruitment. Algorithm 2 describes the complete backward pass.

```
Algorithm 2: BackwardPass({(R_k, L_k, σ_k)}_{k=1}^B, K, I_max)
────────────────────────────────────────────────────────────────────
  Input:  All bee routes/costs/states from forward pass,
          elite count K, max iterations I_max
  Output: Updated template routes {T_k}_{k=1}^B,
          updated global best L_best

  L ← ∅                                   // loyal bee set
  U ← ∅                                   // uncommitted bee set

  // ── Phase 1: Evaluation ──────────────────────────────────────
  1:  for each bee k ∈ {1, …, B} do
  2:      if σ_k = failed then
  3:          Q_k ← 0
  4:      else
  5:          Q_k ← 1 / (L_k + ε)            // Equation (7)
  6:      end if
  7:  end for
  8:
  9:  Q_min ← min_{k} Q_k
 10:  Q_max ← max_{k} Q_k
 11:  L_best(i) ← min_{k} L_k               // best cost this iteration
 12:  if L_best(i) < L_global_best then
 13:      L_global_best ← L_best(i)
 14:      R_global_best ← argmin_{k} L_k
 15:  end if

  // ── Phase 2: Loyalty Decision ────────────────────────────────
 16:  for each bee k ∈ {1, …, B} do
 17:      if k ∈ elite(K) then               // K best bees are always loyal
 18:          T_k ← R_k
 19:          L ← L ∪ {k}
 20:          continue
 21:      end if
 22:
 23:      O_k ← (Q_k - Q_min) / (Q_max - Q_min + ε)   // normalised quality [0,1]
 24:      p_k^loyal ← O_k                              // loyalty probability
 25:
 26:      ρ_k ← uniform_random(0, 1, stream="bco.loyalty")
 27:      if ρ_k ≤ p_k^loyal then
 28:          T_k ← R_k                      // stay loyal to own route
 29:          L ← L ∪ {k}
 30:      else
 31:          T_k ← ∅                       // abandon route, become uncommitted
 32:          U ← U ∪ {k}
 33:      end if
 34:  end for

  // ── Phase 3: Recruitment ─────────────────────────────────────
 35:  if U ≠ ∅ and L ≠ ∅ then
 36:      // Compute recruitment probabilities for loyal bees
 37:      S ← Σ_{l ∈ L} O_l
 38:      if S = 0 then                         // all loyal bees have O_k = 0
 39:          for each k ∈ L do                 // equal probability for all
 40:              p_k^recruit ← 1 / |L|
 41:          end for
 42:      else
 43:          for each k ∈ L do
 44:              p_k^recruit ← O_k / S                    // Equation (13)
 45:          end for
 46:      end if
 47:
 48:      for each j ∈ U do
 49:          λ_j ← uniform_random(0, 1, stream="bco.recruitment")
 50:          recruiter ← roulette_select(L, p^recruit, λ_j)
 51:          T_j ← R_{recruiter}           // adopt recruiter's route as template
 52:      end for
 53:  end if
 54:
 55:  return ({T_k}, L_global_best, R_global_best)
```

**Phase 1 — Evaluation (lines 1–14):** Each bee's route cost `L_k` is converted to a quality score `Q_k`. Failed bees automatically receive `Q_k = 0`. The iteration's best cost and the global best cost are tracked.

**Phase 2 — Loyalty Decision (lines 16–33):** Each bee decides probabilistically whether to retain its route as a template for the next iteration. The normalised quality `O_k` is computed as:

```
O_k = (Q_k - Q_min) / (Q_max - Q_min + ε)                                 (11)

O_k ∈ [0, 1]
```

The loyalty probability equals the normalised quality:

```
p_k^loyal = O_k                                                           (12)
```

A bee whose route quality equals the maximum has `p^loyal = 1` (stays loyal deterministically). A bee whose route quality equals the minimum has `p^loyal = 0` (will abandon).

The `K` elite bees (the `K` bees with the highest quality) are always retained without probabilistic evaluation. This preserves exploitation of the best solutions found.

**Phase 3 — Recruitment (lines 35–53):** Uncommitted bees (those that abandoned their routes) select a recruiter from the loyal set. The probability that an uncommitted bee selects loyal bee `k` as its recruiter is proportional to `k`'s normalised quality:

```
p_k^recruit = O_k / Σ_{l ∈ L} O_l                                        (13)
```

The uncommitted bee then adopts the recruiter's route as its template `T_j = R_{recruiter}`. In the next forward pass, this template biases the uncommitted bee's edge selection toward edges in the recruiter's route.

If all bees are loyal (`U = ∅`) or all bees are uncommitted (`L = ∅`), recruitment is skipped and all bees proceed with their own routes as templates.

### 2.11 Loyalty Probability Equation

The loyalty probability (Equation 12) is restated here with explicit handling of edge cases:

```
p_k^loyal =

  1,                                          if k ∈ elite(K)       (14a)

  1,                                          if Q_max = Q_min      (14b)
                                                (all bees identical)

  (Q_k - Q_min) / (Q_max - Q_min + ε),       otherwise              (14c)
```

Equation (14b) handles the degenerate case where all bees produce identical routes (`Q_max = Q_min`). Because no bee is strictly better than any other, every bee has `p^loyal = 1` and stays loyal. This prevents the colony from discarding all solutions when the population has homogeneous quality.

### 2.12 Recruiter Selection Probability

The probability that an uncommitted bee selects loyal bee `k` as its recruiter is:

```
p_k^recruit = O_k / Σ_{l ∈ L} O_l                                      (15)
```

where `L = {k : p_k^loyal > ρ_k} ∪ elite(K)` is the set of loyal bees, with the guard:

```
p_k^recruit = 1 / |L|   if Σ_{l ∈ L} O_l = 0                          (15a)
```

**Guard (15a):** If all loyal bees have zero normalised quality (all routes failed), every loyal bee is equally likely to be selected as a recruiter. This prevents division by zero while still allowing recruitment to proceed.

Selection is performed via roulette-wheel (fitness-proportionate) selection: a random number `λ_j ~ U(0,1)` is drawn, and the recruiter `k` is the first index satisfying `Σ_{l=1}^{k} p_l^recruit ≥ λ_j`.

### 2.13 Recruitment Mechanism

The recruitment mechanism transfers routing information from high-quality bees to low-quality bees without requiring central coordination:

1. **Loyal bees** retain their own routes as templates. In the next forward pass, their edge selection is biased by `δ` toward edges they used previously — this is **exploitation** of known good paths.

2. **Uncommitted bees** adopt the recruiter's route as their template. In the next forward pass, their selection is biased toward edges used by a higher-quality bee — this is **social learning** (information transfer).

3. **Elite bees** are always retained, ensuring the `K` best routes are never lost. This provides a monotonically non-increasing best-cost guarantee.

The overall effect is that the colony's search effort concentrates around the best-known routes (exploitation) while maintaining diversity through the stochastic component of Equation (9) and the randomness of the loyalty/recruitment decisions (exploration).

### 2.14 Stopping Criteria

The BCO algorithm terminates when any of the following conditions is met. All conditions are evaluated by `TerminationChecker` (from the swarm infrastructure), not by BCO itself.

| Condition | Symbol | Criterion | Implementation |
|-----------|--------|-----------|----------------|
| Max iterations | `I_max` | `i ≥ I_max` | `SwarmConfig.max_iterations` |
| Solution convergence | `θ`, `Ω` | `\|L_best(i) - L_best(i-1)\| < θ` for `Ω` consecutive iterations | `SwarmConfig.convergence_threshold` and `stall_limit` |
| Time limit | `τ_max` | Wall-clock time `t ≥ τ_max` | `SwarmConfig.time_limit_s` |
| Target score | `L_target` | `L_global_best ≤ L_target` | Optional override in `SwarmConfig` |

The best route returned upon termination is `R_global_best` (the route with the lowest `L_k` encountered across all iterations).

### 2.15 Computational Complexity

Per iteration, the BCO algorithm performs:

| Operation | Complexity | Notes |
|-----------|------------|-------|
| Forward pass (B bees) | `O(Σ_{k=1}^{B} P_k × d_avg)` | `P_k` = path length of bee `k`, `d_avg` = average out-degree of nodes visited |
| Route cost evaluation | `O(Σ_{k=1}^{B} P_k)` | Summing costs along each constructed route |
| Loyalty decision | `O(B)` | Computing normalised quality (linear scan) |
| Sorting for elite selection | `O(B log B)` | Finding `K` highest-quality bees |
| Recruitment | `O(|L| + |U| × log |L|)` | Roulette selection via precomputed cumulative probabilities and binary search per uncommitted bee |

**Total per iteration:**

```
O(B × P_avg × d_avg + B log B)                                            (16)
```

**Total for complete run:**

```
O(I_max × (B × P_avg × d_avg + B log B))                                  (17)
```

**Comparison with ACS:**

| Algorithm | Per-Iteration Complexity | Candidate Routes Produced |
|-----------|-------------------------|---------------------------|
| BCO | `O(B × P_avg × d_avg + B log B)` | `B` (one per bee) |
| ACS | `O(k × P_avg × CL)` | `k` (one per ant) |

For equal population sizes (`B = k`), BCO and ACS have comparable asymptotic complexity. BCO's additional `O(B log B)` sorting term is negligible compared to the construction cost `O(B × P_avg × d_avg)` for typical graph sizes.

**Memory complexity:**

| Data Structure | Complexity | Notes |
|----------------|------------|-------|
| Visibility matrix | `O(M)` | One float per edge (cached) |
| Bee states | `O(B × P_max)` | One route per bee |
| Templates | `O(B × P_max)` | One template route per bee |
| **Total** | `O(M + B × P_max)` | Dominated by `M` for dense graphs |

Note: BCO does not maintain a pheromone matrix (unlike ACS), which eliminates the `O(M)` memory overhead that ACS incurs for pheromone storage. BCO's additional `O(B × P_max)` for templates is modest: `B ≤ 50` and `P_max ≤ 1000` for typical graphs.

### 2.16 Assumptions

The mathematical formulation above relies on the following assumptions:

1. **Graph is directed and finite.** The road network `G = (V, E)` is a finite directed graph. Undirected road segments are modelled as a pair of directed edges `(i, j)` and `(j, i)`.

2. **Edge costs are non-negative and static during a single BCO run.** BCO does not detect or adapt to cost changes mid-optimisation. Cost changes (emergency events, congestion updates) trigger a new routing request from the Decision Engine.

3. **A feasible path exists.** If the graph contains no path from `s` to `d` with finite cost, BCO returns a failed `SwarmResult` with no valid candidate. This is consistent with Dijkstra and A* behaviour.

4. **`β ≥ 0` and `δ ≥ 0`.** Both parameters are non-negative. `β = 0` disables heuristic guidance (all edges equally likely modulo template influence). `δ = 0` disables template influence.

5. **`NS ≥ minimum path length`.** The forward-step budget must be at least as large as the shortest path (in edges) from `s` to `d`. If `NS` is too small, no bee can reach the destination, and all routes fail.

6. **Population size `B ≥ K + 1`.** At least one non-elite bee must exist for the probabilistic loyalty decision to have effect.

7. **Elite count `K ≤ B`.** Elite bees are a subset of the population.

8. **Independent bee construction.** Bees construct routes independently during the forward pass. There is no communication, shared memory, or synchronisation between bees during construction.

### 2.17 Deterministic Execution

All stochastic decisions in BCO use `SwarmRandom` with named sub-streams to guarantee deterministic replay:

| Decision | Stream Name | Used In |
|----------|-------------|---------|
| Edge selection (roulette) | `"bco.selection"` | Algorithm 1, line 26 |
| Loyalty threshold | `"bco.loyalty"` | Algorithm 2, line 26 |
| Recruiter selection (roulette) | `"bco.recruitment"` | Algorithm 2, line 49 |

**Determinism guarantee:** Given identical inputs (graph topology, edge costs, `SwarmConfig`, seed, `RoutingRequest`), BCO produces identical results across multiple runs. This is enforced by:
- No direct calls to `random.random()`, `random.choice()`, `numpy.random`, or `secrets`.
- All random streams derived deterministically from `SwarmContext.random_seed` via `SwarmRandom`.
- No dependence on system time, process ID, or hardware entropy.

### 2.18 Equation-to-Implementation Correspondence

Every equation in Section 2 maps to a specific implementation component in Phase 10B:

| Equation | Description | Implementation Target |
|----------|-------------|----------------------|
| (1) `f(R) = Σ c(e)` | Route cost function | `RouteCandidate.total_cost` (existing) |
| (3) `G = (V, E)` | Graph representation | `DirectedGraph` via `SwarmContext.graph` (existing) |
| (4) `S_k(i)` | Bee state tuple | `BCORouting._bee_state: list[BeeState]` (new dataclass) |
| (5) `N(i)` | Feasible neighbour set | Helper method `_feasible_neighbours(current, visited)` |
| (6) `η(i, j)` | Visibility function | `_compute_visibility_matrix()` at initialisation |
| (7) `Q_k` | Route quality | `1 / (L_k + EPSILON)` |
| (9) `p_k(i, j)` | Edge selection probability | `_compute_selection_probs(current, template, neighbours)` |
| (10) `p_k(i, j)` (first iter) | Edge selection (no template) | Same as (9) with `δ = 0` |
| (11) `O_k` | Normalised quality | `(Q_k - Q_min) / (Q_max - Q_min + EPSILON)` |
| (14) `p_k^loyal` | Loyalty probability | `_loyalty_decision(bee_state)` |
| (15) `p_k^recruit` | Recruitment probability | `_recruitment(committed_bees, uncommitted_bees)` |
| Algorithm 1 | Forward pass | `_forward_pass(k, context)` |
| Algorithm 2 | Backward pass | `_backward_pass(all_routes, iteration)` |
| (16) complexity | Per-iteration complexity | Verified in benchmark tests |
| (17) complexity | Total complexity | Verified in benchmark tests |

The Phase 10B implementation will contain a single public method `optimize(context: SwarmContext) -> SwarmResult` that orchestrates these components via the `SwarmLifecycle`.

---

## Section 3: Architecture and Integration

### 3.1 BCO in the E³-Hybrid Architecture

The BCO algorithm lives in the **swarm layer** of the E³-Hybrid stack, at the same level as ACS (Phase 9B). It implements the `SwarmAlgorithm` Protocol and is consumed by the routing layer through `SwarmToRoutingAdapter`.

```
┌─────────────────────────────────────────────────────────┐
│                    Application Layer                      │
│  Decision Engine  │  BenchmarkRunner  │  CLI / Experiment │
└────────────────────────┬────────────────────────────────┘
                         │ RoutingAlgorithm Protocol
                         ▼
┌─────────────────────────────────────────────────────────┐
│                    Routing Layer                          │
│  DijkstraRouting │ AStarRouting │ SwarmToRoutingAdapter  │
└────────────────────────┬────────────────────────────────┘
                         │ SwarmAlgorithm Protocol
                         ▼
┌─────────────────────────────────────────────────────────┐
│                    Swarm Layer                            │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐      │
│  │  ACORouting  │  │  BCORouting  │  │  PSORouting  │     │
│  │  (Phase 9B)  │  │  (Phase 10B) │  │  (Phase 11B) │     │
│  └─────────────┘  └─────────────┘  └─────────────┘      │
│         │               │               │                │
│         ▼               ▼               ▼                │
│  ┌─────────────────────────────────────────────────┐    │
│  │         Swarm Infrastructure (Phase 8B)          │    │
│  │  SwarmContext │ SwarmLifecycle │ SwarmRandom      │    │
│  │  SwarmConfig  │ SwarmResult   │ SwarmFactory     │    │
│  └─────────────────────────────────────────────────┘    │
└────────────────────────┬────────────────────────────────┘
                         │ graph_snapshot │ cost_provider
                         ▼
┌─────────────────────────────────────────────────────────┐
│                    Domain Layer                           │
│  DirectedGraph │ CostProvider │ Emergency │ Communication │
└─────────────────────────────────────────────────────────┘
```

**BCORouting** (`src/e3hybrid/swarm/bco.py`) is the sole file that Phase 10B introduces in the swarm layer. It depends on the same swarm infrastructure that Phase 8B provides and the same domain layer that all routing algorithms use. No existing file is modified.

### 3.2 BCO Class Architecture

Phase 10B introduces one public class and several internal types:

```
┌─────────────────────────────────────────────┐
│              BCORouting                       │  ← public (implements SwarmAlgorithm)
├─────────────────────────────────────────────┤
│ + name: str                                  │
│ + optimize(context: SwarmContext) -> SwarmResult │
│                                               │
│ - _validate(context: SwarmContext) -> None    │
│ - _initialize(context: SwarmContext) -> None  │
│ - _forward_pass() -> ForwardPassResult          │
│ - _backward_pass(ForwardPassResult) -> None   │
│ - _loyalty_decision(k: int) -> bool           │
│ - _recruitment() -> None                      │
│ - _update_templates() -> None                 │
│ - _build_result() -> SwarmResult              │
│ - _build_candidates() -> tuple[RouteCandidate]│
│ - _compute_diversity() -> float               │
│ - _compute_selection_probs(current, N, T_k)    │
│    -> list[float]                              │
└──────────┬──────────────────────────────────┘
           │ owns
           ▼
┌──────────────────────────────┐
│   BeeState (internal)         │  ← one per bee
├──────────────────────────────┤
│  route: list[EdgeId]          │  ← R_k
│  cost: float                  │  ← L_k
│  quality: float               │  ← Q_k
│  template: list[EdgeId] | None│  ← T_k
│  norm_quality: float          │  ← O_k
│  state: BeeStatus             │  ← σ_k
│  is_loyal: bool               │
│  visited: set[NodeId]         │
└──────────────────────────────┘

┌──────────────────────────────┐
│   BCOStatistics (internal)    │
├──────────────────────────────┤
│  iteration: int               │
│  best_cost: float             │
│  avg_cost: float              │
│  worst_cost: float            │
│  diversity: float             │
│  loyal_count: int             │
│  uncommitted_count: int       │
│  runtime_s: float             │
└──────────────────────────────┘

┌──────────────────────────────────┐
│   VisibilityCache (internal)      │
├──────────────────────────────────┤
│  values: dict[EdgeId, float]     │  ← η(i,j) for all edges
│  initialized: bool               │
└──────────────────────────────────┘
```

**Enumerations:**

| Enum | Values | Usage |
|------|--------|-------|
| `BeeStatus` | `CONSTRUCTING`, `COMPLETE`, `FAILED` | State flag σ_k during forward pass |
| `RecruitmentPhase` | `EVALUATION`, `LOYALTY`, `RECRUITMENT`, `TEMPLATE_UPDATE` | Tracks which sub-phase of the backward pass is active for logging and statistics |

**Key design choice:** BCORouting owns all bee state internally as a flat list of `BeeState` objects. There is no separate "Bee" or "Colony" class. This flat ownership model mirrors ACS's approach where `AntColony` manages ants as a list of states. The rationale (DD-BCO-002) is that BCO has no persistent inter-bee structures (no pheromone matrix, no shared memory), so a container class provides no encapsulation benefit.

### 3.3 Integration with Existing Framework

Each of the following subsections describes the interaction between BCO and one existing framework component. Every interaction must satisfy the constraints listed below; violations are detected by `BCOValidator` (Phase 10B).

---

#### 3.3.1 SwarmLifecycle

| Aspect | Specification |
|--------|---------------|
| **Responsibilities** | Provides the iteration loop. Calls `update_fn` once per iteration. Checks termination conditions after each iteration. Collects `SwarmIteration` statistics. |
| **Inputs** | `SwarmContext` (read-only). |
| **Outputs** | `SwarmResult` with `iterations: tuple[SwarmIteration, ...]`. |
| **Ownership** | `SwarmLifecycle` is created inside `BCORouting.optimize()`. BCO owns the lifecycle instance for the duration of `optimize()`. |
| **Lifecycle** | Created → `run()` → discarded. Single-use: a new `SwarmLifecycle` is created per `optimize()` call. |
| **Dependencies** | `SwarmConfig` for iteration bounds and termination parameters. |
| **Invariants** | Exactly one forward pass and one backward pass are executed per lifecycle iteration. The lifecycle does not inspect BCO internals. |
| **Thread-safety** | Not required. `optimize()` is single-threaded. |
| **Read/write** | Read: `config`, `context`. Write: none (lifecycle mutates only its internal `SearchState`). |

**Mapping:** The BCO forward pass (Algorithm 1) constructs all new candidate routes — equivalent to the "Generate Candidate" stage (swarm_architecture_design.md §3.5). The backward pass (Algorithm 2) evaluates fitness (equivalent to "Observe", §3.2), compares scores (equivalent to "Evaluate", §3.3), and updates templates (equivalent to "Update Internal State", §3.4). The lifecycle's `update_fn` combines both passes in sequence: forward first, backward second.

**Callbacks provided to `SwarmLifecycle.run()`:**
- `initialize_fn`: Points to `_initialize()`. Creates the bee population, visibility cache, and random wrapper.
- `update_fn`: An internal lambda or method that calls `_forward_pass()` → `_backward_pass()`. This is where the forward/backward pass sequence is wired into the lifecycle iteration.
- `extract_best_fn`: Extracts `R_global_best` from the internal bee state (or from `_best_route` tracked across iterations).

---

#### 3.3.2 SwarmContext

| Aspect | Specification |
|--------|---------------|
| **Responsibilities** | Provides the immutable environment for one optimization run: graph, cost provider, config, routing request, simulation time. |
| **Inputs** | Constructed by `SwarmToRoutingAdapter` from `RoutingContext`. |
| **Outputs** | Fields accessed by BCO: `graph_snapshot`, `cost_provider`, `config`, `random_stream`, `routing_request`. |
| **Ownership** | BCO receives `context` as a parameter. BCO does not own the context; the caller (`SwarmToRoutingAdapter`) owns it. |
| **Lifecycle** | Exists for the duration of `optimize()`. Valid until `optimize()` returns. |
| **Dependencies** | None. SwarmContext is a leaf object composed of primitive fields. |
| **Invariants** | Frozen dataclass — immutable after construction. All fields are non-None. `graph_snapshot` contains the source `s` and destination `d` nodes. |
| **Thread-safety** | Naturally thread-safe (immutable). |
| **Read/write** | Read: all fields. Write: none (immutable). |

---

#### 3.3.3 SwarmConfig

| Aspect | Specification |
|--------|---------------|
| **Responsibilities** | Carries algorithm-agnostic settings (`population_size`, `max_iterations`, `seed`) plus algorithm-specific `hyperparameters` dict. |
| **Inputs** | Loaded from YAML by the caller, passed through `SwarmContext.config`. |
| **Outputs** | Fields accessed by BCO: `population_size` → `B`, `max_iterations` → `I_max`, `seed`, `hyperparameters` (see table below). |
| **Ownership** | BCO does not own config; it is part of `SwarmContext`. |
| **Lifecycle** | Exists for the duration of `optimize()`; read-only. |
| **Dependencies** | None. |
| **Invariants** | Frozen dataclass. `population_size ≥ 1`. `max_iterations ≥ 1`. `hyperparameters` contains all BCO keys with valid types. |
| **Thread-safety** | Immutable, thread-safe. |
| **Read/write** | Read only. |

**BCO hyperparameters** stored in `SwarmConfig.hyperparameters`:

| Key | Type | Default | Maps To |
|-----|------|---------|---------|
| `forward_steps` | `int` | `100` | `NS` |
| `visibility_weight` | `float` | `2.0` | `β` |
| `template_strength` | `float` | `3.0` | `δ` |
| `elite_count` | `int` | `3` | `K` |

---

#### 3.3.4 SwarmResult

| Aspect | Specification |
|--------|---------------|
| **Responsibilities** | Carries the output of a swarm optimization run. Compatible with `SwarmToRoutingAdapter` for conversion to `RoutingResult`. |
| **Inputs** | Constructed by `BCORouting._build_result()` at the end of `optimize()`. |
| **Outputs** | `best_solution: RouteCandidate`, `candidates: tuple[RouteCandidate, ...]`, `statistics: SwarmStatistics`, `iterations: tuple[SwarmIteration, ...]`, `success: bool`, `failure_reason: str | None`. |
| **Ownership** | BCO creates and returns `SwarmResult`. The caller (`SwarmToRoutingAdapter`) takes ownership. |
| **Lifecycle** | Created once at the end of `optimize()`. Immutable after creation. |
| **Dependencies** | `RouteCandidate`, `SwarmStatistics`, `SwarmIteration`. |
| **Invariants** | `best_solution` is a valid route from `s` to `d`. All `candidates` pass `RouteValidator`. Frozen dataclass. |
| **Thread-safety** | Immutable, thread-safe after construction. |
| **Read/write** | Read by caller after return. BCO never reads the result it constructs. |

---

#### 3.3.5 SwarmRandom

| Aspect | Specification |
|--------|---------------|
| **Responsibilities** | Provides deterministic, seeded sub-streams for all stochastic decisions. |
| **Inputs** | Base `random.Random` from `SwarmContext.random_stream`. |
| **Outputs** | Named sub-streams derived via `get_stream(name)`. |
| **Ownership** | BCO creates a `SwarmRandom` wrapper from the base stream. The wrapper is local to `optimize()`. |
| **Lifecycle** | Created at start of `optimize()`, discarded on return. |
| **Dependencies** | `SwarmContext.random_stream`. |
| **Invariants** | Same seed + same stream name → identical sequence across runs. No global `random` state is accessed. |
| **Thread-safety** | Streams are used sequentially within the single-threaded `optimize()`. Not thread-safe by design. |
| **Read/write** | Write: advances PRNG state on each call. |

**Named streams used by BCO:**

| Stream Name | Used In | Draws Per Iteration |
|-------------|---------|---------------------|
| `"bco.selection"` | Algorithm 1, edge selection (roulette wheel) | One per bee per forward step (≤ B × NS) |
| `"bco.loyalty"` | Algorithm 2, loyalty threshold ρ_k | One per non-elite bee (≤ B − K) |
| `"bco.recruitment"` | Algorithm 2, recruiter selection λ_j | One per uncommitted bee (≤ B) |

---

#### 3.3.6 DirectedGraph (via GraphSnapshot)

| Aspect | Specification |
|--------|---------------|
| **Responsibilities** | Provides read-only graph topology: nodes, edges, out-degree, adjacency. |
| **Inputs** | Accessed through `SwarmContext.graph_snapshot`. |
| **Outputs** | Node set, edge set, outgoing neighbours, edge existence checks. |
| **Ownership** | BCO does not own the graph snapshot. The snapshot is part of `SwarmContext`. |
| **Lifecycle** | Exists for the duration of `optimize()`. Immutable. |
| **Dependencies** | None (leaf data structure). |
| **Invariants** | Graph topology is frozen. Edge costs may change if `CostProvider` is dynamic, but BCO treats them as static per run. |
| **Thread-safety** | Immutable snapshot — thread-safe. |
| **Read/write** | Read only. BCO never calls `update_edge_state()` or any mutation method. |

**Access patterns in BCO:**
- `graph_snapshot.outgoing_edges(node)` — get outgoing edge list for neighbour set `N(i)` (Equation 5)
- `graph_snapshot.node_count()` — informational only
- BCO does not access node coordinates, elevations, or any geometric metadata.

---

#### 3.3.7 CostProvider

| Aspect | Specification |
|--------|---------------|
| **Responsibilities** | Provides composite edge costs. Encapsulates distance, time, energy, congestion, hazard, and emergency penalties. |
| **Inputs** | `SwarmContext.cost_provider`. |
| **Outputs** | `cost(edge_id) → EdgeCost(value=float, is_blocked=bool)`. |
| **Ownership** | BCO does not own. Accessed through `SwarmContext`. |
| **Lifecycle** | Exists for duration of `optimize()`. May be recomputed between runs (new `SwarmContext`), but is stable within a single run. |
| **Dependencies** | `DirectedGraph` edge state, `CostWeights`, emergency effect aggregators. |
| **Invariants** | Blocked edges return `value=inf, is_blocked=True`. All returned costs are non-negative. |
| **Thread-safety** | Assumed thread-safe (read-only within a BCO run). |
| **Read/write** | Read only. BCO never creates or modifies `EdgeCost` values. |

**Access patterns in BCO:**
- `cost_provider.cost(edge_id)` — used in Equation (1) for route cost evaluation
- `cost_provider.cost(edge_id).value` — used in Equation (6) for visibility computation
- BCO never calls `cost_provider.set_weight()`, `cost_provider.add_penalty()`, or any mutation.

---

#### 3.3.8 RouteCandidate

| Aspect | Specification |
|--------|---------------|
| **Responsibilities** | Represents a single feasible route. Used by `DecisionEngine` and `BenchmarkRunner`. |
| **Inputs** | Constructed by BCO from the best bee's route. |
| **Outputs** | `node_sequence`, `edge_sequence`, `total_cost`, `cost_breakdown`, `algorithm`, `metadata`. |
| **Ownership** | BCO constructs `RouteCandidate` objects in `_build_candidates()`. Ownership transfers to `SwarmResult`. |
| **Lifecycle** | Created at end of `optimize()`, packaged into `SwarmResult.best_solution` and `.candidates`. Immutable. |
| **Dependencies** | None (dataclass). |
| **Invariants** | Path is simple (no cycles), starts at `s`, ends at `d`. All edges have `cost < ∞`. |
| **Thread-safety** | Immutable dataclass. |
| **Read/write** | Read by caller after return. BCO writes once during construction. |

---

#### 3.3.9 SwarmToRoutingAdapter

| Aspect | Specification |
|--------|---------------|
| **Responsibilities** | Adapts `SwarmAlgorithm` to `RoutingAlgorithm` Protocol. Creates `SwarmContext` from `RoutingContext`, calls `optimize()`, converts `SwarmResult` to `RoutingResult`. |
| **Inputs** | `RoutingRequest`, `RoutingContext`. |
| **Outputs** | `RoutingResult` containing `RouteCandidate` objects from BCO. |
| **Ownership** | Created by `RoutingFactory` or user code. Owns the `BCORouting` instance it wraps. |
| **Lifecycle** | Persists across multiple `compute_route()` calls. A new `SwarmContext` is created per call. |
| **Dependencies** | `RoutingContext`, `SwarmContext`, `SwarmResult`, `RoutingResult`. |
| **Invariants** | Every `compute_route()` call produces an independent optimization run. No state leaks between calls. |
| **Thread-safety** | `compute_route()` may be called sequentially from a single thread. Not designed for concurrent use. |
| **Read/write** | Read: `RoutingContext`. Write: constructs new `SwarmContext` and `RoutingResult` per call. |

**No modifications to `SwarmToRoutingAdapter` are required for BCO.** The adapter is algorithm-agnostic; it dispatches to any `SwarmAlgorithm` implementation.

---

#### 3.3.10 BenchmarkRunner

| Aspect | Specification |
|--------|---------------|
| **Responsibilities** | Runs a set of routing algorithms (Dijkstra, A*, ACS, BCO, PSO) on a suite of benchmark scenarios. Collects metrics. |
| **Inputs** | `BenchmarkConfig` listing algorithm names (including `"bco"`). |
| **Outputs** | `BenchmarkResult` with per-algorithm, per-request metrics. |
| **Ownership** | Created by experiment scripts. Owns algorithm instances through `RoutingFactory`. |
| **Lifecycle** | Persists for the duration of the benchmark suite. |
| **Dependencies** | `RoutingFactory`, `SwarmToRoutingAdapter`, `SwarmFactory`. |
| **Invariants** | All algorithms receive identical `RoutingRequest` and `RoutingContext`. Fair comparison is enforced at the framework level. |
| **Thread-safety** | Sequential execution — benchmark scenarios run one at a time. |
| **Read/write** | Read: benchmark config, graph, scenarios. Write: benchmark results to disk/memory. |

**BCO registration for benchmarks:**

```
SwarmFactory.register("bco", BCORouting)
```

No modifications to `BenchmarkRunner` are required. The adapter pattern (`SwarmToRoutingAdapter`) makes `BCORouting` a valid `RoutingAlgorithm`.

---

#### 3.3.11 Decision Engine

| Aspect | Specification |
|--------|---------------|
| **Responsibilities** | Selects the best route from candidates produced by routing algorithms. May trigger rerouting on dynamic events. |
| **Inputs** | `RoutingResult` containing `RouteCandidate[]` from BCO (via `SwarmToRoutingAdapter`). |
| **Outputs** | The selected route for the vehicle to follow. |
| **Ownership** | The Decision Engine owns its routing algorithm instances (including `SwarmToRoutingAdapter(BCORouting())`). |
| **Lifecycle** | Persists across the simulation. BCO is invoked when `compute_route()` is called on the adapter. |
| **Dependencies** | `RoutingAlgorithm` Protocol (satisfied by BCO through `SwarmToRoutingAdapter`). |
| **Invariants** | The Decision Engine evaluates candidates solely on `total_cost`. It never inspects BCO-internal fields such as templates, loyalty probabilities, or diversity metrics. |
| **Thread-safety** | The Decision Engine calls `compute_route()` sequentially. |
| **Read/write** | Read: `RouteCandidate` fields. Write: none (BCO state is internal). |

---

#### 3.3.12 Emergency Framework

| Aspect | Specification |
|--------|---------------|
| **Responsibilities** | Models road blockages, congestion, hazards, and emergency vehicle corridors. |
| **Inputs** | Emergency effects reach BCO through `CostProvider.cost(edge)` only. |
| **Outputs** | Modified edge costs (blocked → `∞`, congested → higher cost, hazard → penalty). |
| **Ownership** | BCO does not interact with the Emergency Framework directly. All effects are mediated by `CostProvider`. |
| **Lifecycle** | Emergency events occur asynchronously. The Decision Engine issues a new routing request when an event affects the current route. |
| **Dependencies** | None. BCO never imports `e3hybrid.emergency`. |
| **Invariants** | BCO never directly accesses `MutableEdgeState`, never subscribes to emergency events, never queries `is_blocked` on edges directly. |
| **Thread-safety** | Not applicable (no direct interaction). |
| **Read/write** | None. |

**Architecture rule (enforced):** BCO must not contain any import from `e3hybrid.emergency`. Emergency effects are observable only through `CostProvider.cost(edge).value` and `.is_blocked`.

---

#### 3.3.13 Communication Framework

| Aspect | Specification |
|--------|---------------|
| **Responsibilities** | Provides inter-vehicle and inter-component message passing via `MessageBus`. |
| **Inputs** | BCO does not use the Communication Framework. |
| **Outputs** | BCO does not send messages. |
| **Ownership** | Not applicable. |
| **Lifecycle** | Not applicable. |
| **Dependencies** | None. BCO never imports `e3hybrid.communication`. |
| **Invariants** | All BCO information sharing (recruitment) is internal to the algorithm instance. No inter-vehicle or inter-colony communication occurs. |
| **Thread-safety** | Not applicable. |
| **Read/write** | None. |

**Architecture rule (enforced):** BCO must not contain any import from `e3hybrid.communication`. This restriction matches ACS (Phase 9A, Section 14.1).

### 3.4 BCO Internal Data Structures

All data structures in this section are internal to `BCORouting` and are not exposed outside the class. They are defined here for implementation clarity and are documented as frozen dataclasses where invariance matters.

#### 3.4.1 BeeStatus (Enum)

```python
class BeeStatus(Enum):
    """State flag σ_k during the forward pass."""
    CONSTRUCTING = "constructing"   # actively building route
    COMPLETE     = "complete"       # reached destination
    FAILED       = "failed"         # blocked or exhausted NS steps
```

**Ownership:** Defined in `bco.py`. Used by `BeeState.state`.

**Invariants:** Legal state transition: `CONSTRUCTING → {COMPLETE, FAILED}` only (a bee cannot change state after reaching a terminal state). Reset to `CONSTRUCTING` at the start of each forward pass.

#### 3.4.2 BeeState (Internal Dataclass)

```python
@dataclass
class BeeState:
    """Complete mutable state of one bee at a given iteration.

    Owned by BCORouting._bees: list[BeeState].
    Reset partially at the start of each forward pass.
    """
    k: int                        # bee index (1..B)
    route: list[EdgeId]           # R_k — edge sequence of constructed route
    cost: float                   # L_k — total composite cost
    quality: float                # Q_k — 1 / (cost + EPSILON)
    norm_quality: float           # O_k — normalised quality [0, 1]
    template: list[EdgeId] | None # T_k — template route from previous backward pass
    state: BeeStatus              # σ_k — CONSTRUCTING / COMPLETE / FAILED
    is_loyal: bool                # true if bee remained loyal in backward pass
    visited: set[NodeId]          # nodes visited in this forward pass (cycle prevention)
    iteration_created: int        # i — iteration when this route was constructed
```

**Lifecycle:**
1. Created at `_initialize()` — `route = []`, `template = None`, `state = CONSTRUCTING`, `visited = {s}`.
2. Forward pass populates `route` and `visited`.
3. Cost evaluation populates `cost` and `quality`.
4. Backward pass populates `norm_quality`, `is_loyal`, and updates `template`.
5. `route`, `cost`, `quality`, `norm_quality`, `state`, `is_loyal`, `visited` are **reset** each iteration.
6. `template` persists across iterations (updated each backward pass).

**Invariants:**
- `0 ≤ k < B`.
- `state = COMPLETE` iff `route[-1]` ends at destination `d`.
- `state = FAILED` iff bee could not reach `d`.
- `is_loyal = True` for elite bees and bees where `ρ_k ≤ p^loyal`.
- `template` is never mutated in place; it is replaced whole during the backward pass.

#### 3.4.3 ForwardPassResult (Internal Dataclass)

```python
@dataclass
class ForwardPassResult:
    """Aggregated result of one complete forward pass across all bees."""
    routes: list[list[EdgeId]]        # R_k for each bee k
    costs: list[float]                # L_k for each bee k
    states: list[BeeStatus]           # σ_k for each bee k
    iteration: int                    # i
    runtime_s: float                  # wall-clock time for this forward pass
```

**Ownership:** Constructed in `_forward_pass()`, consumed by `_backward_pass()`. Transient — not stored across iterations.

**Invariants:** `len(routes) == len(costs) == len(states) == B`. `iteration == current loop index`.

#### 3.4.4 BackwardPassResult (Internal Dataclass)

```python
@dataclass
class BackwardPassResult:
    """Aggregated result of one complete backward pass."""
    loyal_indices: list[int]           # L — set of loyal bee indices
    uncommitted_indices: list[int]     # U — set of uncommitted bee indices
    best_cost: float                   # L_best(i) — best cost this iteration
    best_route: list[EdgeId]           # best route this iteration
    global_best_cost: float            # L_global_best — best ever
    global_best_route: list[EdgeId]    # R_global_best — best ever
    diversity: float                   # population diversity metric
    runtime_s: float                   # wall-clock time for this backward pass
```

**Invariants:** `loyal_indices` and `uncommitted_indices` are disjoint and partition `{0..B-1}`. `|loyal_indices| + |uncommitted_indices| == B`. `best_cost <= global_best_cost` (global best never worsens within a single backward pass).

**Ownership:** Constructed in `_backward_pass()`, consumed by `_update_templates()`. Transient.

#### 3.4.5 VisibilityCache (Internal)

```python
@dataclass
class VisibilityCache:
    """Precomputed heuristic visibility for all edges.

    Computed once at initialisation from CostProvider.
    Immutable after construction.
    """
    values: dict[EdgeId, float]   # η(i,j) for every edge (i,j) ∈ E
    beta: float                   # β — stored for convenience during selection
    delta: float                  # δ — stored for convenience during selection
```

**Ownership:** Owned by `BCORouting._visibility`. Created at `_initialize()`, read-only thereafter.

**Invariants:**
- `len(values) == M` (one entry per edge).
- `values[e] = 1 / (cost_provider.cost(e).value + EPSILON)`.
- Blocked edges have `values[e] = 0`.

#### 3.4.6 BCOStatistics (Internal Dataclass)

```python
@dataclass
class BCOStatistics:
    """Per-iteration statistics specific to BCO (subset of SwarmIteration)."""
    iteration: int
    best_cost: float
    avg_cost: float
    worst_cost: float
    loyal_count: int              # |L|
    uncommitted_count: int        # |U|
    diversity: float              # population diversity [0, 1]
    runtime_s: float              # time for this iteration
```

**Invariants:** `worst_cost >= avg_cost >= best_cost`. `loyal_count + uncommitted_count == B`. `diversity ∈ [0, 1]`.

**Ownership:** Collected each iteration. Stored in `BCORouting._iteration_stats: list[BCOStatistics]`. Converted to `SwarmIteration` at the end of `optimize()`.

#### 3.4.7 BCOConfiguration (Internal Helper)

```python
@dataclass(frozen=True, slots=True)
class BCOConfiguration:
    """Type-safe extraction of BCO hyperparameters from SwarmConfig.

    Validates types and ranges at construction time.
    """
    forward_steps: int        # NS — default 100
    beta: float               # β — visibility weight, default 2.0
    delta: float              # δ — template strength, default 3.0
    elite_count: int          # K — elite bees, default 3

    @classmethod
    def from_config(cls, config: SwarmConfig) -> 'BCOConfiguration':
        """Extract and validate BCO hyperparameters from SwarmConfig."""
        ...

    def validate(self) -> None:
        """Raise ValueError on invalid parameter combinations."""
        ...
```

**Validation rules:**
- `forward_steps ≥ 1`
- `beta ≥ 0`
- `delta ≥ 0`
- `0 ≤ elite_count ≤ population_size`

### 3.5 Execution Flow and Data Flow

#### 3.5.1 optimize() Execution Flow

```
    optimize(context: SwarmContext)
    │
    ├── 1. VALIDATE
    │      _validate(context)
    │      • Verify graph contains source s and destination d
    │      • Verify BCOConfiguration.from_config() succeeds
    │      • Verify at least one path exists (fast feasibility check)
    │      → Raises ValueError on any failure
    │
    ├── 2. INITIALIZE
    │      _initialize(context)
    │      • Create VisibilityCache from CostProvider
    │      • Create B bees with BeeState(route=[], template=None, …)
    │      • Create SwarmRandom wrapper
    │      • Create empty global_best tracking
    │
    ├── 3. LIFECYCLE LOOP (SwarmLifecycle.run)
    │      │
    │      │  For each iteration i = 0..I_max-1:
    │      │  ┌────────────────────────────────────────────┐
    │      │  │  3a. FORWARD PASS                           │
    │      │  │      _forward_pass()                       │
    │      │  │      • For each bee k:                      │
    │      │  │        1. Reset route, visited to {s}       │
    │      │  │        2. For step = 1..NS:                 │
    │      │  │           - Compute N(current) (Eq 5)       │
    │      │  │           - Compute p_k(current,j) (Eq 9)   │
    │      │  │           - Roulette-select next node       │
    │      │  │           - Append edge, update visited     │
    │      │  │        3. Mark COMPLETE if at d, FAILED if blocked   │
    │      │  │      → ForwardPassResult                    │
    │      │  │                                             │
    │      │  │  3b. BACKWARD PASS                           │
    │      │  │      _backward_pass(ForwardPassResult)       │
    │      │  │      (RecruitmentPhase records which         │
    │      │  │       sub-phase is active for logging)       │
    │      │  │                                             │
    │      │  │      Phase 1 — Evaluation:                  │
    │      │  │        • Compute L_k, Q_k for each bee      │
    │      │  │        • Track L_best(i), L_global_best     │
    │      │  │      Phase 2 — Loyalty (Eq 14):             │
    │      │  │        • Compute O_k, p_k^loyal for each    │
    │      │  │        • Elite bees always loyal            │
    │      │  │        • ρ_k ~ U(0,1) → loyal or uncommitted│
    │      │  │      Phase 3 — Recruitment (Eq 15):         │
    │      │  │        • Compute p_k^recruit for loyal bees │
    │      │  │        • Each uncommitted bee selects       │
    │      │  │          recruiter via roulette wheel       │
    │      │  │        • Update T_k for all bees            │
    │      │  │      → BackwardPassResult                   │
    │      │  │                                             │
    │      │  │  3c. COLLECT STATISTICS                     │
    │      │  │      • Compute diversity metric             │
    │      │  │      • Append BCOStatistics                 │
    │      │  │                                             │
    │      │  │  3d. TERMINATION CHECK                      │
    │      │  │      (handled by SwarmLifecycle)            │
    │      │  └────────────────────────────────────────────┘
    │      │
    │      └──→ Repeat until termination
    │
    ├── 4. BUILD RESULT
    │      _build_result()
    │      • Convert global_best_route → RouteCandidate
    │      • Convert candidates (all routes from final iteration)
    │      • Convert BCOStatistics → tuple[SwarmIteration, ...]
    │      • Build SwarmResult
    │
    └──→ Return SwarmResult
```

**Internal method call relationships within the backward pass:**
- `_backward_pass()` iterates over all bees. For each non-elite bee, it calls `_loyalty_decision(k)` to compute the loyalty probability and return `True` if the bee stays loyal.
- After loyalty decisions, `_recruitment()` iterates over all uncommitted bees and recruits them from the loyal set.
- At the end of the backward pass, `_update_templates()` finalises all template assignments for the next iteration.
- `RecruitmentPhase` enum values (`EVALUATION`, `LOYALTY`, `RECRUITMENT`, `TEMPLATE_UPDATE`) are recorded per sub-phase for logging and statistics.

#### 3.5.2 Data Flow Between Passes

```
                     ┌──────────────────┐
                     │   VisibilityCache │  ← initialised once from CostProvider
                     │   (η, β, δ)       │
                     └────────┬─────────┘
                              │ read-only
                              ▼
  ┌─────────────────────────────────────────────────────────────┐
  │                    Iteration i                                │
  │                                                               │
  │  ┌──────────────────────┐     ┌──────────────────────────┐   │
  │  │   FORWARD PASS        │     │   BACKWARD PASS          │   │
  │  │                       │     │                          │   │
  │  │  Inputs:              │     │  Inputs:                 │   │
  │  │   • T_k (templates)   │◄────│   • T_k (just updated)   │   │
  │  │   • η(i,j) (vis)     │     │   • R_k, L_k from FP     │   │
  │  │   • β, δ             │     │   • Q_k computed here    │   │
  │  │                       │     │                          │   │
  │  │  Produces:            │     │  Produces:               │   │
  │  │   • R_k (new routes)  │────►│   • L (loyal set)        │   │
  │  │   • σ_k (states)     │     │   • U (uncommitted set)  │   │
  │  │                       │     │   • T_k (updated temps) │   │
  │  └──────────────────────┘     └──────────────────────────┘   │
  │              │                           │                    │
  │              │                           │                    │
  │              ▼                           ▼                    │
  │      ┌──────────────────────────────────────────┐            │
  │      │         STATISTICS COLLECTION              │            │
  │      │   BCOStatistics(L_best, diversity, ...)    │            │
  │      └──────────────────────────────────────────┘            │
  │              │                                                │
  │              ▼                                                │
  │      Updated T_k flow to iteration i+1's FORWARD PASS         │
  └─────────────────────────────────────────────────────────────┘
```

**Key data-flow rules:**
1. Templates `T_k` are the **only state** that persists across iterations within BCO. All other bee state (`R_k`, `L_k`, `Q_k`, `visited`) is ephemeral and reset each iteration.
2. `VisibilityCache` is written once during initialisation and read-only thereafter.
3. `SwarmRandom` streams advance independently per iteration; the sequence of draws is fully determined by the base seed.
4. No data flows between BCO and external components (Emergency, Communication, Decision Engine) during `optimize()`. All external interaction occurs through the `SwarmResult` at the end or through `SwarmContext` at the start.

#### 3.5.3 Candidate Production

BCO produces `B` candidate routes per iteration (one per bee). At termination, `_build_candidates()` extracts:

- **`best_solution`:** The `RouteCandidate` corresponding to `R_global_best` (lowest cost encountered across all iterations).
- **`candidates`:** All `B` routes from the **final iteration**, converted to `RouteCandidate` objects.

This matches the ACS pattern (Phase 9B), ensuring the Decision Engine receives multiple alternatives regardless of which swarm algorithm produced them.

### 3.6 Extension Points and Future Hybridization

BCO is designed with explicit extension points that enable future hybridization with ACS (Phase 9B) and PSO (Phase 11B) without modifying existing infrastructure.

#### 3.6.1 Extension Point: Template Source Swapping

The template `T_k` is the primary vehicle for inter-bee information transfer. Currently, templates are populated by the loyalty/recruitment mechanism. An extension point exists at the end of each backward pass:

```
T_k ← f(k, R_k, L_k, L, U, context)       // replace f to change template strategy
```

Possible future implementations of `f`:
- **Recruitment (current):** `T_k = R_k` if loyal, `T_k = R_recruiter` if recruited.
- **ACS hybrid:** `T_k = edges_with_high_pheromone(context.pheromone_matrix)` — bees use ACS pheromone trails instead of bee templates.
- **PSO hybrid:** `T_k = best_personal_route(k) ∪ neighbourhood_best()` — bees use PSO personal/global best.
- **E³-Hybrid:** `T_k = combine(R_k, ACS_pheromone, PSO_global_best)` — a weighted combination of all three.

**Architecture rule (DD-BCO-003):** Template assignment is isolated to a single method `_update_templates(forward_results, backward_results)`. Hybridization requires changing only this method; the forward pass, backward pass, and infrastructure remain unchanged.

#### 3.6.2 Extension Point: Selection Function Swapping

Edge selection probability `p_k(i, j)` (Equation 9) is computed in a single method `_compute_selection_probs(current, template, neighbours, beta, delta)`. This method can be swapped to incorporate other signals:

- **Current:** `η(i,j)^β × (1 + δ × I_T(i,j))`.
- **ACS hybrid:** `τ(i,j)^α × η(i,j)^β` — uses ACS pheromone instead of template indicator.
- **PSO hybrid:** `η(i,j)^β × velocity_bias(i,j)` — uses PSO velocity vector as additional bias.
- **Weighted ensemble:** `(w_aco × τ^α + w_bco × I_T + w_pso × v) × η^β` — convex combination of all three signals.

#### 3.6.3 Extension Point: Initialization Strategy

The `_initialize()` method creates empty bees. A future hybrid could warm-start BCO by seeding initial templates from ACS output:

```
def _initialize(self, context: SwarmContext, seed_templates: list[list[EdgeId]] | None = None):
    """If seed_templates provided, B bees start with non-empty templates."""
    ...
```

#### 3.6.4 Extension Point: Diversity Metric

> **Note:** The diversity metric is not part of the core BCO literature formulation (Teodorović, 2009). It is added for monitoring, statistics, and as a hybridization extension point. The core algorithm (forward pass, backward pass, recruitment) is unaffected if this metric is disabled.

BCO's diversity metric is computed in `_compute_diversity()`. The default metric measures template overlap:

```
diversity = 1 - (average pairwise Jaccard similarity of templates)
```

Other metrics can be plugged in without changing core BCO logic:
- Route cost variance (standard deviation of `L_k`).
- Edge coverage (fraction of graph edges used by at least one bee).
- Node dispersion (average Euclidean distance between route centroids).

#### 3.6.5 No-Change Guarantees

The following components require **no modifications** when BCO is hybridized with ACS or PSO:

| Component | Why Unchanged |
|-----------|---------------|
| `SwarmAlgorithm` Protocol | Signature `optimize(context) → SwarmResult` is algorithm-agnostic |
| `SwarmLifecycle` | Lifecycle does not inspect BCO internals |
| `SwarmContext` | Frozen context — all algorithms read the same environment |
| `SwarmConfig` | Hyperparameters dict accommodates any algorithm |
| `SwarmResult` | Always contains `RouteCandidate` objects |
| `SwarmToRoutingAdapter` | Adapter dispatches to any `SwarmAlgorithm` |
| `BenchmarkRunner` | Works with any `RoutingAlgorithm` via adapter |
| `DecisionEngine` | Evaluates `RouteCandidate` on `total_cost` only |
| `EmergencyFramework` | Effects mediated through `CostProvider` |
| `CommunicationFramework` | BCO does not use it |

### 3.7 Design Decisions

```
DD-BCO-002: Flat Bee State Ownership
─────────────────────────────────────
Context: BCO manages B bees, each with route, cost, quality, template,
and state fields. ACS groups ant state inside an AntColony class.

Decision: Store bee states as a flat list of BeeState dataclass instances
owned directly by BCORouting. No Bee or Colony container class.

Rationale:
  1. BCO has no persistent inter-bee structure (no pheromone matrix,
     no shared memory). A container class would hold only the list and
     delegation methods — no encapsulation benefit.
  2. Flat indexing (self._bees[k]) is simpler than self._colony.bees[k].
  3. The backward pass iterates over all bees linearly; a flat list
     is the natural representation for sequential processing.
  4. Matches the structure used internally by ACS (AntColony.ants: list).

Alternatives Considered:
  - Bee class with methods: Rejected. BeeState is a passive data holder.
    Behaviour belongs in BCORouting methods (_forward_pass, etc.).
  - Dict of bee states: Rejected. List with integer index is simpler
    and sufficient for sequential access.

Consequences:
  - BCORouting._bees is a list[BeeState] of length B.
  - Every bee is accessed by index k (0-indexed internally, 1-indexed in
    the mathematical formulation).
  - Adding a new per-bee field requires modifying only BeeState.
```

```
DD-BCO-003: Template Assignment as Single Extension Point
───────────────────────────────────────────────────────────
Context: The template T_k is the sole carrier of inter-iteration
memory in BCO. Future hybridization with ACS/PSO will need to
modify how templates are assigned.

Decision: Isolate all template assignment logic in a single method
_update_templates(forward_result, backward_result, context).

Rationale:
  1. Template assignment is the only BCO operation that depends on
     cross-iteration state. Isolating it makes the algorithm's
     memory mechanism explicit and auditable.
  2. Hybridization (Section 3.6.1) requires changing only this method.
     The forward pass, backward pass, and recruitment logic remain
     untouched when introducing ACS pheromone or PSO personal bests.
  3. Unit testing can verify template assignment independently of
     route construction and recruitment.

Consequences:
  - _update_templates() is called at the end of _backward_pass().
  - The method receives the full forward and backward pass results
    plus the SwarmContext, giving it access to all signals needed
    for future hybrid strategies.
```

```
DD-BCO-004: Visibility Computed Once, Cached
───────────────────────────────────────────────
Context: Edge costs are static during a single BCO run (Assumption 2,
Section 2.16). Visibility η(i,j) = 1 / (c(i,j) + ε) depends only on
edge costs.

Decision: Compute visibility for all edges once at initialisation and
cache in VisibilityCache. Read-only thereafter.

Rationale:
  1. Eliminates redundant division operations: up to B × NS × d_avg
     per iteration are saved.
  2. Consistency: all bees read the same η(i,j) value for the same
     edge, eliminating floating-point variation from repeated computation.
  3. Follows the same pattern as ACS visibility (Phase 9A, Section 4.2).
  4. When edge costs change (emergency), a new SwarmContext is created,
     which triggers recomputation. No stale-cache risk.

Alternatives Considered:
  - Compute on demand: Rejected. Would recompute η O(B × NS × d_avg)
    times per iteration with no accuracy benefit.
  - Dynamic recomputation on graph change: Rejected per scope
    boundary (Section 2.16, Assumption 2).

Consequences:
  - VisibilityCache is O(M) memory.
  - Initialisation is O(M) time.
  - During the forward pass, η lookups are O(1) dict access.
```

```
DD-BCO-005: Elite Preservation Without Probabilistic Evaluation
──────────────────────────────────────────────────────────────────
Context: The K best bees (those with lowest route cost) should never
be lost between iterations. The probabilistic loyalty decision could
discard a high-quality route.

Decision: Elite bees (the K bees with highest Q_k) bypass the
probabilistic loyalty decision and are forced loyal.

Rationale:
  1. Guarantees a monotonically non-increasing best-cost sequence
     (the global best never worsens).
  2. Prevents the pathological case where all bees abandon their
     routes and the colony loses all progress.
  3. Parameter K controls the exploitation rate: higher K = more
     routes preserved = more exploitation.
  4. K = 0 is permitted (no elitism), though not recommended.
     K = B would force all bees loyal, disabling recruitment entirely.

Alternatives Considered:
  - No elitism (K = 0 implicit): Rejected. Without elitism, the
    best route can be lost in a single iteration, causing oscillation.
  - Always preserve global-best only: Rejected. A single preserved
    route may not provide enough template diversity for effective
    recruitment.

Consequences:
  - Elite bees are identified by sorting on Q_k (descending), O(B log B).
  - Elite bees are skipped in the loyalty decision loop (Algorithm 2,
    lines 17–20).
  - K is configurable via SwarmConfig.hyperparameters["elite_count"].
```

### 3.8 Architecture Summary and Transition

This section defined the complete architecture for integrating BCO into the E³-Hybrid framework:

| Component | Status |
|-----------|--------|
| `BCORouting` (public class) | Defined — implements `SwarmAlgorithm` |
| `BeeState` (internal dataclass) | Defined — 11 fields |
| `BeeStatus` (enum) | Defined — 3 values |
| `ForwardPassResult` (internal) | Defined — 5 fields |
| `BackwardPassResult` (internal) | Defined — 8 fields |
| `VisibilityCache` (internal) | Defined — cached η, β, δ |
| `BCOStatistics` (internal) | Defined — 8 fields |
| `BCOConfiguration` (internal helper) | Defined — 4 params + validation |
| `_validate()` | Defined — preconditions |
| `_initialize()` | Defined — setup |
| `_forward_pass()` | Defined — Algorithm 1 |
| `_backward_pass()` | Defined — Algorithm 2 |
| `_build_result()` | Defined — output construction |
| `_compute_diversity()` | Defined — metric interface |
| `_compute_selection_probs()` | Defined — Equation 9 implementation |
| `_update_templates()` | Defined — extension point |

**No modifications to existing code are required.** BCO introduces one new file (`src/e3hybrid/swarm/bco.py`) and one registration line in benchmarks. All existing integration contracts (SwarmAlgorithm Protocol, SwarmLifecycle, SwarmToRoutingAdapter, BenchmarkRunner, DecisionEngine, Emergency, Communication) remain unchanged.

**The next design section (Section 4) specifies:** the BCO configuration schema (YAML), the complete parameter catalog with types, domains, defaults, and validation rules, the algorithm's computational complexity in terms of configurable parameters, and the mapping of every parameter to the future Phase 10B implementation.

---

## Section 4: Configuration and Complexity Analysis

### 4.1 Configuration Architecture

BCO configuration is split across two layers, matching the existing swarm infrastructure:

1. **SwarmConfig** (algorithm-agnostic): `population_size`, `max_iterations`, `time_limit_s`, `convergence_threshold`, `stall_limit`, `seed`, `target_score`, `cost_weights`. These are defined in `SwarmConfig` (swarm_infrastructure_design.md §2.3) and shared by all swarm algorithms.

2. **Hyperparameters** (algorithm-specific): Stored in `SwarmConfig.hyperparameters` as a `Mapping[str, object]`. BCO extracts and validates these via `BCOConfiguration.from_config()` at `_initialize()` time.

This two-layer design means every parameter below maps to either a `SwarmConfig` field or a `hyperparameters` key. No changes to `SwarmConfig` are required.

### 4.2 Complete Parameter Catalog

#### 4.2.1 SwarmConfig Parameters (Algorithm-Agnostic)

| # | Symbol | YAML Key | Type | Domain | Default | Validation | Implementation Target |
|---|--------|----------|------|--------|---------|------------|----------------------|
| 1 | `B` | `population_size` | `int` | `[2, 1000]` | `20` | `≥ 2` (`≥ K + 1`) | `BCORouting._bees: list[BeeState]` (length `B`) |
| 2 | `I_max` | `max_iterations` | `int` | `[1, 100000]` | `100` | `≥ 1` | `SwarmLifecycle.run()` iteration bound |
| 3 | `τ_max` | `time_limit_s` | `float` | `[0, 86400]` | `0.0` | `≥ 0` (0 = no limit) | `TerminationChecker` wall-clock limit |
| 4 | `θ` | `convergence_threshold` | `float` | `[0, ∞)` | `0.001` | `≥ 0` | `TerminationChecker` convergence criterion |
| 5 | `Ω` | `stall_limit` | `int` | `[0, I_max]` | `20` | `≥ 0` | `SwarmConfig.stall_limit` → `SearchState` termination threshold |
| 6 | — | `seed` | `int` | `[0, 2^32)` | `42` | `≥ 0` | `SwarmRandom` base seed |
| 7 | `L_target` | `target_score` | `float` | `[0, ∞)` | `0.0` | `≥ 0` (0 = disabled) | `TerminationChecker` early-stop target |

**Notes on SwarmConfig parameters:**

- **`population_size`** (`B`, #1): Must satisfy `B ≥ K + 1` to ensure at least one non-elite bee participates in the probabilistic loyalty decision. If `K = 0` (no elitism), the minimum is `2` (at least one loyal and one uncommitted bee must be possible).
- **`max_iterations`** (`I_max`, #2): Total iteration budget. Higher values are safe due to early termination via convergence (#4, #5).
- **`time_limit_s`** (`τ_max`, #3): Value `0` disables the runtime limit. When set, overrides `I_max` if the time budget is exhausted first.
- **`convergence_threshold`** (`θ`, #4): The absolute change in `L_best(i)` between consecutive iterations. A threshold of `0` means any non-zero improvement prevents convergence.
- **`stall_limit`** (`Ω`, #5): Number of consecutive iterations without improving `L_global_best` before convergence is declared. Must be `≤ I_max`.
- **`seed`** (#6): Drives all `SwarmRandom` streams. Changing the seed produces a different (but deterministic) sequence of routes. Used for statistical replication across runs.
- **`target_score`** (`L_target`, #7): When `L_target > 0`, BCO terminates early if `L_global_best ≤ L_target`. Useful when a known-good route cost exists (e.g., benchmark baseline).

#### 4.2.2 Hyperparameters (BCO-Specific)

| # | Symbol | YAML Key | Type | Domain | Default | Validation | Implementation Target |
|---|--------|----------|------|--------|---------|------------|----------------------|
| 8 | `NS` | `forward_steps` | `int` | `[1, 10000]` | `100` | `≥ 1` | `BCOConfiguration.forward_steps` → `_forward_pass()` step bound |
| 9 | `β` | `visibility_weight` | `float` | `[0, 10]` | `2.0` | `≥ 0` | `BCOConfiguration.beta` → `VisibilityCache.beta` → Equation (9) |
| 10 | `δ` | `template_strength` | `float` | `[0, 10]` | `3.0` | `≥ 0` | `BCOConfiguration.delta` → `VisibilityCache.delta` → Equation (9) |
| 11 | `K` | `elite_count` | `int` | `[0, B]` | `3` | `0 ≤ K ≤ B` | `BCOConfiguration.elite_count` → Algorithm 2 elite set |

**Notes on BCO hyperparameters:**

- **`forward_steps`** (`NS`, #8): The maximum number of edges each bee may traverse per forward pass. Must be ≥ the shortest path length (in edges) from source to destination. A value too small causes all bees to fail (σ_k = FAILED). A value too large wastes computation on bees that already reached the destination. The default of 100 covers typical graphs (N ≤ 1000, path lengths ≤ 50).
- **`visibility_weight`** (`β`, #9): Controls the steepness of the edge selection probability distribution. At `β = 0`, all feasible edges are equally likely (maximum exploration). At `β = 10`, the cheapest edge is selected with near-deterministic probability. Practical range: `[0.5, 5.0]`. The default `β = 2.0` provides a moderate heuristic bias — the cheapest edge is selected roughly twice as often as the second-cheapest, which balances exploration of alternative edges against exploitation of local cost cues.
- **`template_strength`** (`δ`, #10): Controls how strongly the template route biases edge selection. At `δ = 0`, templates have no effect (each iteration is independent). At `δ = 10`, edges in the template receive an 11× weight multiplier, virtually guaranteeing the bee retraces its template. Practical range: `[0.5, 5.0]`. The default `δ = 3.0` provides a 4× bonus for template edges, giving the template meaningful influence without forcing deterministic reconstruction.
- **`elite_count`** (`K`, #11): The number of top-quality bees that bypass the probabilistic loyalty decision. `K = 0` disables elitism (all bees subject to probabilistic loyalty). `K = B` forces all bees loyal, disabling recruitment entirely. Practical range: `[1, max(3, B/4)]`. The default `K = 3` preserves the top routes while allowing the majority of bees to participate in recruitment.

### 4.3 YAML Configuration Example

```yaml
algorithm: "bco"
population_size: 20             # B — number of bees
max_iterations: 100             # I_max — maximum iterations
time_limit_s: 60.0              # τ_max — runtime limit (0 = no limit)
convergence_threshold: 0.001    # θ — min improvement for convergence
stall_limit: 20                    # Ω — stall iterations before convergence
target_score: 0.0               # L_target — early stop (0 = disabled)
seed: 42                        # random seed
hyperparameters:
  forward_steps: 100            # NS — max edges per forward pass
  visibility_weight: 2.0        # β — heuristic importance (Eq 9)
  template_strength: 3.0        # δ — template influence (Eq 9)
  elite_count: 3                # K — elite bees (Algorithm 2)
cost_weights:
  distance: 1.0
  time: 0.0
  energy: 0.0
  congestion: 0.0
  hazard: 0.0
  emergency: 0.0
  communication: 0.0
```

### 4.4 Parameter Interaction Analysis

#### 4.4.1 β–δ Interaction (Exploration–Exploitation)

The parameters `β` (visibility weight) and `δ` (template strength) jointly control the exploration–exploitation balance in Equation (9):

```
p_k(i, j) ∝ η(i, j)^β × (1 + δ × I_{T_k}(i, j))
```

The **effective bias** of template edges relative to non-template edges is:

```
effective_bias = (1 + δ) / 1  = 1 + δ
```

This is independent of `β` — the template bonus is multiplicative, not additive to the heuristic term. Four regimes exist:

| Regime | β | δ | Behaviour |
|--------|---|---|-----------|
| **Pure exploration** | 0 | 0 | All feasible edges equally likely. No memory. Equivalent to random walk with cycle prevention. |
| **Heuristic only** | > 0 | 0 | Edge selection driven solely by static cost-based visibility. No inter-iteration learning. Equivalent to greedy stochastic search. |
| **Template only** | 0 | > 0 | All feasible edges equally likely, but template edges receive a `(1+δ)` multiplier. Learning without heuristic guidance. |
| **Balanced** | > 0 | > 0 | Heuristic guidance with template-driven exploitation. The recommended operating regime. |

**Interaction rule:** Increasing `δ` relative to `β` shifts edge selection toward template exploitation (the template-bonus term matters more), while increasing `β` relative to `δ` emphasises heuristic visibility (the edge cost dominates). Neither parameter alone determines the search character; both interact multiplicatively through Equation (9).

#### 4.4.2 K–B Interaction (Elitism vs. Population Diversity)

The elite count `K` and population size `B` jointly determine the minimum number of bees that participate in recruitment:

```
non_elite_pool = B − K
```

| Regime | K | B − K | Effect |
|--------|---|-------|--------|
| **No elitism** | 0 | B | All bees subject to probabilistic loyalty. Best routes may be lost, but maximum recruitment diversity. |
| **Moderate elitism** (default) | 3 | B − 3 | Top routes preserved; most bees participate in recruitment. |
| **High elitism** | B/2 | B/2 | Half the routes are preserved. Limited recruitment diversity. |
| **All loyal** | B | 0 | No recruitment. All bees retain their own routes. Degenerates to B independent stochastic searches. |

**Constraint:** `K ≤ B − 1` is required for any recruitment to occur. `K = B` disables recruitment entirely (Algorithm 2, line 35: `if U ≠ ∅ and L ≠ ∅` fails because `U = ∅`).

#### 4.4.3 NS–P_min Interaction (Forward Steps vs. Path Length)

The forward-step budget `NS` must satisfy `NS ≥ P_min`, where `P_min` is the minimum number of edges from source `s` to destination `d`:

| Case | Condition | Outcome |
|------|-----------|---------|
| **Sufficient budget** | `NS ≥ P_min` | Bees can reach destination. Some may exhaust NS before reaching d (`σ_k = FAILED`). |
| **Insufficient budget** | `NS < P_min` | No bee can reach the destination. All routes fail. Algorithm returns `success=False`. |

**Recommendation:** Set `NS` to at least 2× the expected shortest path length to allow for exploration of longer alternative routes. The Dijkstra shortest-path length provides a lower bound that can be computed at initialisation.

### 4.5 Time Complexity Analysis

All complexity expressions use the notation defined in Section 2.1.

#### 4.5.1 Initialisation (One-Time)

```
T_init = O(M + B)
```

| Operation | Complexity | Derivation |
|-----------|------------|------------|
| VisibilityCache construction | `O(M)` | One call to `CostProvider.cost(e)` per edge `e ∈ E`. |
| Bee population creation | `O(B)` | Create `B` `BeeState` instances with empty routes. |
| SwarmRandom wrapper creation | `O(1)` | Single object instantiation. |

#### 4.5.2 Per-Iteration Complexity

The BCO iteration consists of three phases. Using the notation from Equations (16)–(17):

**Phase 1: Forward pass (`_forward_pass()`)**

```
T_forward = Σ_{k=1}^{B} [ NS_k × (d_avg + C_selection) ]
```

where:
- `NS_k ≤ NS` is the number of steps bee `k` actually executes (stops early if destination reached).
- `d_avg = (1/N) Σ_{v ∈ V} deg_out(v)` is the mean out-degree of all nodes.
- `C_selection` is the constant cost of computing Equation (9) and performing roulette-wheel selection.

Using Section 2.15's path-length notation:

```
T_forward = B × min(NS, P_max) × (d_avg + C_selection)

where P_max = max_k P_k  (longest route across all bees in this iteration)
```

In the worst case (`NS ≤ P_max` for all bees):

```
T_forward = O(B × NS × d_avg)                                            (18)
```

**Phase 2: Backward pass (`_backward_pass()`)**

The backward pass has three sub-phases:

| Sub-phase | Complexity | Derivation |
|-----------|------------|------------|
| Evaluation (cost + quality) | `O(Σ_{k=1}^{B} P_k)` | Summing costs along each route (Equation 1) |
| Elite sorting | `O(B log B)` | Partial sort to identify top-K bees by `Q_k` |
| Loyalty decision | `O(B)` | One normalisation + one random draw per non-elite bee |
| Recruitment probability | `O(|L|)` | Summing normalised qualities of loyal bees |
| Roulette selection per U | `O(|U| × log |L|)` | Binary search on cumulative probability array |

Total backward pass:

```
T_backward = O(B × P_avg + B log B)                                      (19)
```

This matches the derivation in Section 2.15.

**Phase 3: Statistics collection**

```
T_stats = O(B)                                                            (20)
```

One pass over bee states to compute best/avg/worst cost, loyal count, and diversity metric.

**Total per iteration:**

```
T_iter = T_forward + T_backward + T_stats
       = O(B × NS × d_avg) + O(B × P_avg + B log B) + O(B)
       = O(B × NS × d_avg + B log B)                                      (21)
```

The dominant term is `B × NS × d_avg` (route construction); the backward-pass `O(B log B)` term is negligible by comparison for typical `B ≤ 1000`.

#### 4.5.3 Total Runtime

```
T_total = T_init + I × T_iter
        = O(M + B) + I_max × O(B × NS × d_avg + B log B)
        = O(I_max × B × NS × d_avg)                                        (22)
```

The initialisation term `O(M + B)` is negligible for `I_max ≥ 10`.

#### 4.5.4 Sensitivity Analysis

| Parameter | Effect on Runtime | Scaling |
|-----------|-------------------|---------|
| `B` (population_size) | Linear | Doubling B doubles forward-pass cost and adds `O(B log B)` sorting cost. |
| `NS` (forward_steps) | Linear | Doubling NS doubles per-bee construction cost. |
| `d_avg` (graph density) | Linear | Denser graphs increase neighbour-set enumeration cost. |
| `I_max` (iterations) | Linear | Doubling iterations doubles total runtime. |

**Dominant cost:** `B × NS × d_avg`. For a typical configuration (`B=20`, `NS=100`, `d_avg=10`) and `I_max=100`:

```
T_total ≈ 100 × 20 × 100 × 10 = 2,000,000 edge selections
```

Each edge selection involves 1 visibility lookup, 1 template check, and 1 random draw. The asymptotic cost class is identical to ACS for equivalent population sizes, with the specific runtime constant depending on the underlying graph and hardware.

### 4.6 Space Complexity Analysis

#### 4.6.1 Permanent Storage (Algorithm Lifetime)

| Structure | Complexity | Derivation |
|-----------|------------|------------|
| VisibilityCache | `O(M)` | One `float` per edge. |
| BeeState list | `O(B)` | Static: `B` dataclass instances. |
| Template routes | `O(B × P_max)` | Each bee stores one template route of up to `P_max` edges. Persists across iterations. |
| Statistics history | `O(I_max)` | One `BCOStatistics` per iteration, optionally summarised. |
| **Total permanent** | `O(M + B × P_max)` | Dominated by `M` for dense graphs. |

#### 4.6.2 Temporary Storage (Per Iteration)

| Structure | Complexity | Derivation |
|-----------|------------|------------|
| ForwardPassResult | `O(B × P_max)` | Routes, costs, states for all B bees. Transient — consumed and discarded each iteration. |
| BackwardPassResult | `O(B)` | Loyal/uncommitted indices, best costs. Consumed and discarded each iteration. |
| Route construction buffers | `O(NS × d_avg)` | Neighbour set, probability array per bee. Freed after each bee completes. |
| **Total temporary** | `O(B × P_max)` | Peak allocation at the end of forward pass. |

#### 4.6.3 Comparison with ACS

| Aspect | BCO | ACS |
|--------|-----|-----|
| Pheromone matrix | None | `O(M)` floats |
| Template storage | `O(B × P_max)` | None |
| Visibility cache | `O(M)` | `O(M)` |
| **Total dominant term** | `O(M + B × P_max)` | `O(M)` |

BCO eliminates the `O(M)` pheromone matrix that ACS requires, but adds `O(B × P_max)` for template storage. In practice:
- For sparse graphs (`M ≈ 10N`): BCO memory ≈ ACS memory (pheromone ≈ templates).
- For dense graphs (`M ≈ N²`): BCO memory < ACS memory (templates are negligible vs. M).
- Forward-pass routes (`ForwardPassResult`, `O(B × P_max)`) are transient (rebuilt each iteration), whereas template routes persist across iterations as part of permanent storage. ACS's forward-pass routes are likewise transient.

### 4.7 Parameter-to-Implementation Mapping

Every configurable parameter maps to a specific location in the Phase 10B implementation:

| Symbol | YAML Key | Variable in Code | Type | Used In |
|--------|----------|------------------|------|---------|
| `B` | `population_size` | `config.population_size` | `SwarmConfig` | `BCORouting._bees` list length |
| `I_max` | `max_iterations` | `config.max_iterations` | `SwarmConfig` | `SwarmLifecycle(config)` constructor |
| `τ_max` | `time_limit_s` | `config.time_limit_s` | `SwarmConfig` | `TerminationChecker` |
| `θ` | `convergence_threshold` | `config.convergence_threshold` | `SwarmConfig` | `TerminationChecker` |
| `Ω` | `stall_limit` | `config.stall_limit` | `SwarmConfig` | `TerminationChecker` via `SearchState.no_improvement_count` |
| — | `seed` | `config.seed` | `SwarmConfig` | `SwarmRandom` base seed |
| `L_target` | `target_score` | `config.target_score` | `SwarmConfig` | `TerminationChecker` |
| `NS` | `hyperparameters.forward_steps` | `self._config.forward_steps` | `BCOConfiguration` | `_forward_pass()` loop bound |
| `β` | `hyperparameters.visibility_weight` | `self._visibility.beta` | `BCOConfiguration` → `VisibilityCache` | `_compute_selection_probs()` |
| `δ` | `hyperparameters.template_strength` | `self._visibility.delta` | `BCOConfiguration` → `VisibilityCache` | `_compute_selection_probs()` |
| `K` | `hyperparameters.elite_count` | `self._config.elite_count` | `BCOConfiguration` | `_backward_pass()` elite set |

**Validation sequence:**
1. `SwarmConfig` is validated by `SwarmValidator.validate_config()` (swarm infrastructure).
2. `BCOConfiguration.from_config()` extracts hyperparameters from `SwarmConfig.hyperparameters` and validates types and ranges.
3. `BCOConfiguration.validate()` checks cross-parameter constraints (`K ≤ B`).
4. `_validate()` in `BCORouting` performs runtime checks (graph connectivity, path feasibility).

Step 4 validates graph-dependent properties — source-to-destination connectivity and path feasibility — which cannot be checked at configuration time because the graph is not available until `SwarmContext` is constructed.

No parameter is read from environment variables, global state, or hard-coded defaults outside the configuration chain.

### 4.8 Section Summary

Section 4 defined the complete BCO configuration schema and complexity analysis:

| Item | Status |
|------|--------|
| YAML configuration schema | Defined — 11 parameters across two layers |
| Parameter catalog | Defined — type, domain, default, validation for all 11 parameters |
| Parameter interactions | Defined — β–δ, K–B, NS–P_min interaction regimes |
| Time complexity | Derived — `O(I_max × B × NS × d_avg)` (Equation 22) |
| Space complexity | Derived — `O(M + B × P_max)` with breakdown into permanent/temporary |
| Parameter-to-implementation mapping | Defined — all 11 parameters mapped to Phase 10B targets |

**Transition to Section 5:** The next section specifies the concrete pseudocode that bridges the architecture (Section 3) and configuration (Section 4) to the Phase 10B implementation. Section 5 provides method-level algorithmic descriptions of every public method and private helper in `BCORouting`. Every block of pseudocode below is written as Python-idiomatic logic that maps directly to the Phase 10B implementation without requiring new algorithmic decisions.

---

## Section 5: Pseudocode and Implementation Specification

### 5.1 Class Overview

All BCO code lives in a single file: `src/e3hybrid/swarm/bco.py`. The file contains one public class (`BCORouting`) implementing `SwarmAlgorithm` and seven internal types:

| Type | Kind | Purpose |
|------|------|---------|
| `BeeStatus` | `Enum` | `CONSTRUCTING`, `COMPLETE`, `FAILED` |
| `BeeState` | `dataclass` | Per-bee mutable state (11 fields) |
| `ForwardPassResult` | `dataclass` | Aggregated forward-pass output |
| `BackwardPassResult` | `dataclass` | Aggregated backward-pass output |
| `BCOStatistics` | `dataclass` | Per-iteration stats |
| `VisibilityCache` | `dataclass` | Cached edge visibility + β, δ |
| `BCOConfiguration` | `frozen dataclass` | Type-safe hyperparameter container |

**File structure:**
```
bco.py:
  BeeStatus(Enum)
  BeeState(dataclass)
  ForwardPassResult(dataclass)
  BackwardPassResult(dataclass)
  BCOStatistics(dataclass)
  VisibilityCache(dataclass)
  BCOConfiguration(frozen dataclass)
    from_config(classmethod)
    validate()
  BCORouting
    optimize()              # SwarmAlgorithm Protocol
    _validate()
    _initialize()
    _forward_pass()
    _backward_pass()
    _loyalty_decision()
    _recruitment()
    _update_templates()
    _compute_selection_probs()
    _compute_diversity()
    _build_result()
    _build_candidates()
```

---

### 5.2 BCORouting: Public Interface

```python
class BCORouting:
    """SwarmAlgorithm implementation for Bee Colony Optimization.

    One instance per optimize() call. Not reusable.
    """

    def __init__(self) -> None:
        self._bees: list[BeeState] = []
        self._visibility: VisibilityCache | None = None
        self._swarm_rng: SwarmRandom | None = None
        self._config: BCOConfiguration | None = None
        self._context: SwarmContext | None = None
        self._global_best_cost: float = inf
        self._global_best_route: list[EdgeId] = []
        self._iteration_stats: list[BCOStatistics] = []
        self._graph: DirectedGraph | None = None
        self._cost_provider: CostProvider | None = None
        self._source: NodeId | None = None
        self._destination: NodeId | None = None
```

**Invariants after `_initialize()`:** all fields non-None except `_global_best_route` (empty until first backward pass). `_bees` length equals `population_size`.

---

### 5.3 BCOConfiguration

```python
@dataclass(frozen=True, slots=True)
class BCOConfiguration:
    forward_steps: int     # NS
    beta: float            # β
    delta: float           # δ
    elite_count: int       # K

    @classmethod
    def from_config(cls, config: SwarmConfig) -> BCOConfiguration:
        hp = config.hyperparameters
        fs = hp.get("forward_steps", 100)
        b  = hp.get("visibility_weight", 2.0)
        d  = hp.get("template_strength", 3.0)
        k  = hp.get("elite_count", 3)
        if not isinstance(fs, int):   raise TypeError(...)
        if not isinstance(b, float):  raise TypeError(...)
        if not isinstance(d, float):  raise TypeError(...)
        if not isinstance(k, int):    raise TypeError(...)
        bc = BCOConfiguration(fs, b, d, k)
        bc.validate()
        return bc

    def validate(self) -> None:
        if self.forward_steps < 1:
            raise ValueError("forward_steps must be >= 1")
        if self.beta < 0:
            raise ValueError("beta must be >= 0")
        if self.delta < 0:
            raise ValueError("delta must be >= 0")
        if not (0 <= self.elite_count <= _B):
            raise ValueError("elite_count out of range")
        if _B < 2:
            raise ValueError("population_size must be >= 2")
```

`_B` is `population_size` from `SwarmConfig`, passed into `validate()` as a parameter (not stored in `BCOConfiguration`).

---

### 5.4 `_validate()` and `_initialize()`

```python
def _validate(self, context: SwarmContext) -> None:
    # 1. Graph contains source and destination
    if context.routing_request.source not in context.graph_snapshot:
        raise ValueError("Source node not in graph")
    if context.routing_request.destination not in context.graph_snapshot:
        raise ValueError("Destination node not in graph")
    # 2. BCOConfiguration can be constructed
    self._config = BCOConfiguration.from_config(context.config)
    # 3. Fast feasibility check (source-destination connected)
    if not _is_feasible(context.graph_snapshot,
                        context.routing_request.source,
                        context.routing_request.destination):
        raise ValueError("No path from source to destination")
```

```python
def _initialize(self, context: SwarmContext) -> None:
    self._context = context
    self._graph = context.graph_snapshot
    self._cost_provider = context.cost_provider
    self._source = context.routing_request.source
    self._destination = context.routing_request.destination
    self._config = BCOConfiguration.from_config(context.config)
    self._config.validate(context.config.population_size)

    # VisibilityCache: O(M) — one entry per edge
    vis: dict[EdgeId, float] = {}
    for e in self._graph.edges():
        c = self._cost_provider.cost(e)
        if c.is_blocked:
            vis[e] = 0.0
        else:
            vis[e] = 1.0 / (c.value + EPSILON)
    self._visibility = VisibilityCache(vis, self._config.beta,
                                       self._config.delta)

    # SwarmRandom from context
    self._swarm_rng = SwarmRandom(context.random_stream)

    # Bee population: B bees, empty initial state
    B = context.config.population_size
    self._bees = []
    for k in range(B):
        self._bees.append(BeeState(
            k=k, route=[], cost=0.0, quality=0.0,
            norm_quality=0.0, template=None,
            state=BeeStatus.CONSTRUCTING, is_loyal=False,
            visited=set(), iteration_created=-1,
        ))

    # Global best tracking
    self._global_best_cost = inf
    self._global_best_route = []
    self._iteration_stats = []
```

**EPSILON:** `1e-10` — prevents division by zero for zero-cost edges.

---

### 5.5 `_forward_pass()`

Executed once per iteration. Each bee constructs a route independently.

```python
def _forward_pass(self, iteration: int) -> ForwardPassResult:
    B = len(self._bees)
    routes: list[list[EdgeId]] = [[] for _ in range(B)]
    costs: list[float] = [0.0] * B
    states: list[BeeStatus] = [BeeStatus.CONSTRUCTING] * B
    sel_stream = self._swarm_rng.get_stream("bco.selection")
    t0 = time.perf_counter()

    for k in range(B):
        bee = self._bees[k]
        # Reset ephemeral state
        bee.route = []
        bee.visited = {self._source}
        bee.state = BeeStatus.CONSTRUCTING

        current: NodeId = self._source
        route_edges: list[EdgeId] = []
        total_cost: float = 0.0

        for _step in range(self._config.forward_steps):
            neighbours = self._graph.outgoing_edges(current)
            # Filter blocked and visited
            feasible = [e for e in neighbours
                        if self._cost_provider.cost(e).value < inf
                        and e.target not in bee.visited]
            if not feasible:
                break  # dead end → FAILED

            # Compute probabilities via Equation (9)
            probs = self._compute_selection_probs(
                feasible, bee.template,
                current, sel_stream
            )

            # Roulette wheel selection
            r = sel_stream.random()
            cum = 0.0
            chosen: EdgeId = feasible[-1]
            for i, p in enumerate(probs):
                cum += p
                if r <= cum:
                    chosen = feasible[i]
                    break

            route_edges.append(chosen)
            total_cost += self._cost_provider.cost(chosen).value
            current = chosen.target
            bee.visited.add(current)

            if current == self._destination:
                break  # COMPLETE

        # Determine final state
        routes[k] = route_edges
        costs[k] = total_cost
        if current == self._destination:
            states[k] = BeeStatus.COMPLETE
        elif not route_edges:
            states[k] = BeeStatus.FAILED
        else:
            states[k] = BeeStatus.FAILED  # exhausted NS without reaching d

        # Write back to persistent bee state
        bee.route = route_edges
        bee.state = states[k]
        bee.cost = total_cost
        bee.iteration_created = iteration

    t1 = time.perf_counter()
    return ForwardPassResult(routes, costs, states, iteration, t1 - t0)
```

**Key design choices:**
- Feasible neighbours exclude blocked edges AND visited nodes (cycle prevention per Section 2.6).
- `sel_stream.random()` — one uniform draw per selection; the roulette walk is deterministic given the stream state.
- Route cost `L_k` is accumulated during construction using `CostProvider.cost(e).value`.

---

### 5.6 `_compute_selection_probs()`

Implements Equation (9):

```python
def _compute_selection_probs(
    self,
    feasible: list[EdgeId],
    template: list[EdgeId] | None,
    current: NodeId,
    stream: random.Random,
) -> list[float]:
    """Return probability distribution over feasible edges.

    p_k(i,j) ∝ η(i,j)^β × (1 + δ × I_T_k(i,j))
    """
    probs: list[float] = []
    template_set: set[EdgeId] = set(template) if template else set()

    for e in feasible:
        eta = self._visibility.values.get(e, 0.0)
        w = eta ** self._config.beta
        if e in template_set:
            w *= (1.0 + self._config.delta)
        probs.append(w)

    total = sum(probs)
    if total <= 0.0:
        p = 1.0 / len(feasible)
        return [p] * len(feasible)

    return [p / total for p in probs]
```

**Fallback:** If all feasible edges have `η = 0` (e.g., all blocked), falls back to uniform distribution.

---

### 5.7 `_backward_pass()`

Executed once per iteration after the forward pass. Three sub-phases: evaluation, loyalty, recruitment.

```python
def _backward_pass(self, forward: ForwardPassResult,
                   iteration: int) -> BackwardPassResult:
    t0 = time.perf_counter()

    # ── Phase 1: Evaluation ──
    B = len(self._bees)
    for k, bee in enumerate(self._bees):
        if bee.state == BeeStatus.COMPLETE:
            bee.quality = 1.0 / (bee.cost + EPSILON)
        else:
            bee.quality = 0.0
            bee.cost = inf

    sorted_indices = sorted(range(B),
                            key=lambda i: self._bees[i].quality,
                            reverse=True)
    best_idx = sorted_indices[0]
    best_cost = self._bees[best_idx].cost
    best_route = self._bees[best_idx].route

    if best_cost < self._global_best_cost:
        self._global_best_cost = best_cost
        self._global_best_route = list(best_route)

    # ── Phase 2: Loyalty Decision ──
    K = self._config.elite_count
    elite_set: set[int] = set(sorted_indices[:K])
    loyal: list[int] = []
    uncommitted: list[int] = []
    loyal_stream = self._swarm_rng.get_stream("bco.loyalty")

    max_q = max(bee.quality for bee in self._bees) if B > 0 else 0.0
    for bee in self._bees:
        bee.norm_quality = bee.quality / max_q if max_q > 0 else 0.0

    for k, bee in enumerate(self._bees):
        if bee.state != BeeStatus.COMPLETE:
            uncommitted.append(k)
            bee.is_loyal = False
            continue
        if k in elite_set:
            loyal.append(k)
            bee.is_loyal = True
            continue
        if self._loyalty_decision(k, loyal_stream):
            loyal.append(k)
            bee.is_loyal = True
        else:
            uncommitted.append(k)
            bee.is_loyal = False

    # ── Phase 3: Recruitment ──
    rec_stream = self._swarm_rng.get_stream("bco.recruitment")
    if uncommitted and loyal:
        self._recruitment(uncommitted, loyal, rec_stream)

    self._update_templates()
    diversity = self._compute_diversity()

    t1 = time.perf_counter()
    return BackwardPassResult(
        loyal_indices=list(loyal),
        uncommitted_indices=list(uncommitted),
        best_cost=best_cost,
        best_route=list(best_route),
        global_best_cost=self._global_best_cost,
        global_best_route=list(self._global_best_route),
        diversity=diversity,
        runtime_s=t1 - t0,
    )
```

---

### 5.8 `_loyalty_decision()`

```python
def _loyalty_decision(self, bee_index: int,
                      stream: random.Random) -> bool:
    """Return True if bee remains loyal.

    p_k^loyal = O_k  (Equation 14 with β^loyal = 1)
    """
    bee = self._bees[bee_index]
    p_loyal = bee.norm_quality
    rho = stream.random()
    return rho <= p_loyal
```

**Note:** `β^loyal = 1` gives a linear mapping from normalised quality to loyalty probability. A bee with `O_k = 0.6` has a 60% chance of remaining loyal.

---

### 5.9 `_recruitment()`

```python
def _recruitment(self, uncommitted: list[int],
                 loyal: list[int], stream: random.Random) -> None:
    """Each uncommitted bee selects a recruiter from the loyal set.

    p_j^recruit = O_j / Σ_{m ∈ L} O_m   (Equation 15)
    """
    total_o = sum(self._bees[j].quality for j in loyal)
    if total_o <= 0.0:
        for u_idx in uncommitted:
            recruiter = stream.choice(loyal)
            self._bees[u_idx].template = list(self._bees[recruiter].route)
        return

    loyal_indices = list(loyal)
    cum_probs: list[float] = []
    running = 0.0
    for j in loyal_indices:
        p = self._bees[j].quality / total_o
        running += p
        cum_probs.append(running)

    for u_idx in uncommitted:
        r = stream.random()
        lo, hi = 0, len(cum_probs)
        while lo < hi:
            mid = (lo + hi) // 2
            if r <= cum_probs[mid]:
                hi = mid
            else:
                lo = mid + 1
        recruiter_idx = loyal_indices[lo] if lo < len(loyal_indices) else loyal_indices[-1]
        self._bees[u_idx].template = list(self._bees[recruiter_idx].route)
```

**Binary search on cumulative probability array:** `O(log |L|)` per uncommitted bee. Deterministic given the stream state.

---

### 5.10 `_update_templates()`

```python
def _update_templates(self) -> None:
    """Assign templates for the next iteration.

    - Loyal bees: template = their own route
    - Uncommitted (recruited) bees: template already set by _recruitment()
    - Failed bees: template unchanged
    """
    for bee in self._bees:
        if bee.state == BeeStatus.FAILED:
            continue
        if bee.is_loyal and bee.state == BeeStatus.COMPLETE:
            bee.template = list(bee.route)
```

**Extension point (DD-BCO-003):** Replace this method to hybridize with ACS or PSO.

---

### 5.11 `_compute_diversity()`

```python
def _compute_diversity(self) -> float:
    templates = [bee.template for bee in self._bees
                 if bee.template is not None]
    if len(templates) < 2:
        return 0.0

    total_sim = 0.0
    pairs = 0
    for i in range(len(templates)):
        ti = set(templates[i])
        for j in range(i + 1, len(templates)):
            tj = set(templates[j])
            union = len(ti | tj)
            if union > 0:
                total_sim += len(ti & tj) / union
            pairs += 1
    avg_sim = total_sim / pairs if pairs > 0 else 0.0
    return 1.0 - avg_sim
```

**Range:** [0, 1]. 0 = all templates identical; 1 = all templates disjoint.

---

### 5.12 `_build_result()` and `_build_candidates()`

```python
def _build_candidates(self) -> tuple[RouteCandidate, list[RouteCandidate]]:
    best = self._route_to_candidate(self._global_best_route)
    final_routes: list[RouteCandidate] = []
    for bee in self._bees:
        if bee.state == BeeStatus.COMPLETE and bee.route:
            final_routes.append(self._route_to_candidate(bee.route))
    if not final_routes:
        final_routes = [best]
    return best, final_routes


def _route_to_candidate(self, edges: list[EdgeId]) -> RouteCandidate:
    nodes: list[NodeId] = [self._source]
    for e in edges:
        nodes.append(e.target)
    total = sum(self._cost_provider.cost(e).value for e in edges)
    return RouteCandidate(
        node_sequence=tuple(nodes),
        edge_sequence=tuple(edges),
        total_cost=total,
        algorithm="bco",
    )


def _build_result(self) -> SwarmResult:
    best_solution, candidates = self._build_candidates()
    iterations = tuple(
        SwarmIteration(
            iteration=s.iteration,
            best_cost=s.best_cost,
            avg_cost=s.avg_cost,
            worst_cost=s.worst_cost,
            diversity=s.diversity,
            algorithm_specific={
                "loyal_count": s.loyal_count,
                "uncommitted_count": s.uncommitted_count,
            },
            runtime_s=s.runtime_s,
        )
        for s in self._iteration_stats
    )
    success = len(self._global_best_route) > 0
    return SwarmResult(
        best_solution=best_solution,
        candidates=tuple(candidates),
        iterations=iterations,
        success=success,
        failure_reason=None if success else "No feasible route found",
    )
```

---

### 5.13 `optimize()` — Lifecycle Wiring

```python
def optimize(self, context: SwarmContext) -> SwarmResult:
    """SwarmAlgorithm Protocol entry point."""
    self._validate(context)

    def init_fn(ctx: SwarmContext) -> None:
        self._initialize(ctx)

    def update_fn(ctx: SwarmContext) -> None:
        fwd = self._forward_pass(len(self._iteration_stats))
        bwd = self._backward_pass(fwd, len(self._iteration_stats))

        costs = [b.cost for b in self._bees if b.state == BeeStatus.COMPLETE]
        avg_cost = statistics.mean(costs) if costs else inf
        worst_cost = max(costs) if costs else inf
        self._iteration_stats.append(BCOStatistics(
            iteration=len(self._iteration_stats),
            best_cost=bwd.best_cost,
            avg_cost=avg_cost,
            worst_cost=worst_cost,
            loyal_count=len(bwd.loyal_indices),
            uncommitted_count=len(bwd.uncommitted_indices),
            diversity=bwd.diversity,
            runtime_s=bwd.runtime_s,
        ))

    def extract_fn(ctx: SwarmContext) -> RouteCandidate:
        return self._route_to_candidate(self._global_best_route)

    lifecycle = SwarmLifecycle(config=context.config, algorithm="bco")
    lifecycle.run(
        context=context,
        initialize_fn=init_fn,
        update_fn=update_fn,
        extract_best_fn=extract_fn,
    )
    return self._build_result()
```

**Lifecycle integration:** `SwarmLifecycle` provides the iteration loop and termination checking. BCO passes three callbacks. The lifecycle handles all termination conditions through `TerminationChecker`.

---

### 5.14 Determinism Guarantee

Every stochastic decision uses `SwarmRandom.get_stream(name)` with a fixed name:

| Stream | Used In | Calls Per Iteration |
|--------|---------|---------------------|
| `"bco.selection"` | `_forward_pass()` — roulette edge selection | Up to `B × step_count` `random()` calls |
| `"bco.loyalty"` | `_loyalty_decision()` — loyalty threshold `ρ_k` | `B - K` `random()` calls |
| `"bco.recruitment"` | `_recruitment()` — recruiter selection | `\|U\|` `random()` calls + binary search |

**Determinism proof:** Given identical inputs (`SwarmContext` with same graph, `SwarmConfig`, `seed`, `RoutingRequest`), the sequence of random draws is identical across runs because:
1. `SwarmRandom` derives sub-streams deterministically from the base `RNG(seed)`.
2. All three streams are consumed in fixed order per iteration (selection → loyalty → recruitment).
3. No calls to `random.random()`, `random.choice()`, or global RNG. No system randomness.
4. Same iteration count `I` and forward-step budget `NS` produce the same total draws.

**Early termination:** Reduces iteration count but does not affect determinism within executed iterations — the draw sequence is determined by which iterations are reached, which is itself deterministic.

---

### 5.15 Complete Method Inventory

| Method | Visibility | Complexity | Calls |
|--------|-----------|------------|-------|
| `__init__()` | public | `O(1)` | Constructor |
| `optimize()` | public | Delegates | `SwarmAlgorithm` Protocol |
| `_validate()` | private | `O(N + M)` BFS | `optimize()` |
| `_initialize()` | private | `O(M + B)` | `init_fn` |
| `_forward_pass()` | private | `O(B × NS × d_avg)` | `update_fn` |
| `_compute_selection_probs()` | private | `O(d_avg)` | Per bee per step |
| `_backward_pass()` | private | `O(B × P_avg + B log B)` | `update_fn` |
| `_loyalty_decision()` | private | `O(1)` | Per non-elite bee |
| `_recruitment()` | private | `O(\|U\| × log \|L\|)` | Per iteration |
| `_update_templates()` | private | `O(B)` | `_backward_pass()` |
| `_compute_diversity()` | private | `O(B² × P_avg)` | `_backward_pass()` |
| `_build_result()` | private | `O(B × P_max)` | `optimize()` |
| `_build_candidates()` | private | `O(B × P_max)` | `_build_result()` |
| `_route_to_candidate()` | private | `O(P_k)` | `_build_candidates()` |

**Total implementation:** ~270 lines of Python logic (excluding empty lines, imports, docstrings, type definitions).

---

### 5.16 Section Summary

| Item | Status |
|------|--------|
| Class structure | Defined — 1 public class, 7 internal types |
| `optimize()` wiring | Defined — 3 callbacks to `SwarmLifecycle` |
| Forward-pass pseudocode | Defined — Algorithm 1 (Equation 9) |
| Backward-pass pseudocode | Defined — Algorithm 2 (Equations 14–15) |
| Selection probabilities | Defined — `_compute_selection_probs()` (Equation 9) |
| Loyalty decision | Defined — `_loyalty_decision()` (Equation 14) |
| Recruitment | Defined — `_recruitment()` (Equation 15) |
| Template update | Defined — `_update_templates()` (DD-BCO-003) |
| Diversity metric | Defined — `_compute_diversity()` (Jaccard-based) |
| Result construction | Defined — `_build_result()`, `_build_candidates()` |
| Determinism proof | Defined — 3 named streams, fixed draw order, no global RNG |
| Complete method inventory | 14 methods, ~270 Python lines total |

**Transition to Phase 10B:** With Sections 1–5 approved, the BCO algorithm design is complete. The Phase 10B implementation follows directly from the pseudocode above — every equation, data structure, and state transition is specified at the method level. No algorithmic decisions remain. The implementation phase will produce `src/e3hybrid/swarm/bco.py` with production-quality Python, comprehensive unit tests, and full integration into the swarm infrastructure for SUMO-based thesis simulation.
