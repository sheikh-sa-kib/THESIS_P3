# Literature Traceability

This document maps every implemented algorithm, equation, and model in the
E³-Hybrid framework to its original academic source. Every entry includes the
original publication, the specific usage within this project, and any
modifications made from the original formulation.

---

## 1. Routing Algorithms

### 1.1 Dijkstra's Algorithm

| Field | Detail |
|-------|--------|
| **Source** | Dijkstra, E. W. (1959). "A note on two problems in connexion with graphs". *Numerische Mathematik*, 1(1), 269–271. |
| **Usage** | Baseline shortest-path routing algorithm. Standard heap-based priority queue implementation. |
| **Modifications** | None. Uses `CostProvider` for edge weights instead of raw edge lengths. Generates alternative candidates by iteratively blocking primary route edges. |
| **Implementation** | `src/e3hybrid/routing/dijkstra.py` |

### 1.2 A* (A-Star) Search

| Field | Detail |
|-------|--------|
| **Source** | Hart, P. E., Nilsson, N. J., & Raphael, B. (1968). "A formal basis for the heuristic determination of minimum cost paths". *IEEE Transactions on Systems Science and Cybernetics*, 4(2), 100–107. |
| **Usage** | Heuristic-guided shortest-path routing. Uses Euclidean, Manhattan, and Zero heuristics. |
| **Modifications** | Heuristic architecture separated from search via `Heuristic` Protocol. ZeroHeuristic degenerates to Dijkstra for verification. Supports configurable heuristic scale factor. |
| **Implementation** | `src/e3hybrid/routing/astar.py`, `src/e3hybrid/routing/heuristic.py` |

### 1.3 Ant Colony Optimization (Phase 9 — Design)

| Field | Detail |
|-------|--------|
| **Primary Source** | Dorigo, M., & Gambardella, L. M. (1997). "Ant Colony System: A cooperative learning approach to the traveling salesman problem". *IEEE Transactions on Evolutionary Computation*, 1(1), 53–66. |
| **Secondary Source** | Dorigo, M., Birattari, M., & Stutzle, T. (2006). "Ant colony optimization". *IEEE Computational Intelligence Magazine*, 1(4), 28–39. |
| **Tertiary Source** | Dorigo, M., & Stützle, T. (2004). *Ant Colony Optimization*. MIT Press. |
| **Variant** | Ant Colony System (ACS) — selected over Ant System (AS), Max-Min Ant System (MMAS), and Rank-based ACO for reasons detailed in `docs/aco_algorithm_design.md`. |
| **Modifications** | Pheromone model adapted for directed graphs (not TSP). Route construction constrained by graph topology. Edge costs mediated through `CostProvider`. |
| **Design** | `docs/aco_algorithm_design.md` |

### 1.4 Bee Colony Optimization (Phase 10 — In Design)

| Field | Detail |
|-------|--------|
| **Primary Source** | Teodorović, D. (2009). "Bee colony optimization (BCO)". In C. P. Lim, L. C. Jain, & S. Dehuri (Eds.), *Innovations in Swarm Intelligence* (pp. 39–60). Springer. |
| **Secondary Source** | Teodorović, D., & Dell'Orco, M. (2005). "Bee colony optimization — a cooperative learning approach to complex transportation problems". *Proceedings of the 10th International Symposium on Operational Research (SOR'05)*, 51–60. Slovenia. |
| **Tertiary Source** | Davidović, T., Teodorović, D., & Šelmić, M. (2015). "Bee colony optimization part I: The algorithm overview". *Yugoslav Journal of Operations Research*, 25(1), 33–56. |
| **Variant** | Constructive BCO (Teodorović, 2009) — selected over ABC, BCOp, Fuzzy BCO, and Bee System for reasons documented in `docs/bco_algorithm_design.md`. |
| **Modifications** | Route construction constrained by directed graph topology. Edge costs mediated through `CostProvider`. Recruitment mechanism adapted for single-route EV routing (not multi-vehicle VRP). |
| **Design** | `docs/bco_algorithm_design.md` (Phase 10A, in progress) |
| **Status** | Design phase active (Phase 10A). |

### 1.5 Particle Swarm Optimization (Phase 11 — Planned)

| Field | Detail |
|-------|--------|
| **Source** | Kennedy, J., & Eberhart, R. (1995). "Particle swarm optimization". *Proceedings of IEEE International Conference on Neural Networks*, 1942–1948. |
| **Secondary Source** | Shi, Y., & Eberhart, R. (1998). "A modified particle swarm optimizer". *IEEE International Conference on Evolutionary Computation*, 69–73. |
| **Variant** | To be determined during Phase 11 design. |
| **Status** | Design phase not yet started. |

---

## 2. Energy Model

### 2.1 Fiori Energy Consumption Model

| Field | Detail |
|-------|--------|
| **Source** | Fiori, C., Ahn, K., & Rakha, H. A. (2016). "Power-based electric vehicle energy consumption model: Model development and validation". *Applied Energy*, 168, 257–268. |
| **Usage** | Physics-based EV energy consumption model. Computes energy consumption from speed, acceleration, and road grade using force-balance equations. |
| **Modifications** | Not yet implemented. Design document complete but equations deferred. |
| **Implementation** | `src/e3hybrid/vehicle/energy.py` (stub), `docs/energy_model_design.md` |

### 2.2 Key Equations (from Fiori et al., 2016)

| Equation | Description | Usage |
|----------|-------------|-------|
| Traction force | `F_t = ma + mg sin(θ) + mgC_r cos(θ) + 0.5ρC_dA_f(v + v_w)²` | Total force required to move vehicle |
| Power demand | `P = F_t × v / η` | Electrical power drawn from battery |
| Regenerative braking | `P_reg = max(0, -F_t × v × η_reg)` | Energy recovered during deceleration |
| Energy consumption | `E = ∫(P - P_reg) dt` | Net energy consumed over a segment |

Full parameter definitions and units documented in `docs/energy_model_design.md`.

---

## 3. Heuristic Functions

### 3.1 Euclidean Distance

| Field | Detail |
|-------|--------|
| **Source** | Standard Euclidean geometry. No single source. |
| **Usage** | A* heuristic for continuous coordinate spaces. Admissible and consistent. |
| **Formula** | `h(n) = scale × √((x₂ − x₁)² + (y₂ − y₁)²)` |
| **Implementation** | `src/e3hybrid/routing/heuristic.py` |

### 3.2 Manhattan Distance

| Field | Detail |
|-------|--------|
| **Source** | Standard L1 distance. No single source. |
| **Usage** | A* heuristic for grid/taxicab geometry. Admissible and consistent. |
| **Formula** | `h(n) = scale × (|x₂ − x₁| + |y₂ − y₁|)` |
| **Implementation** | `src/e3hybrid/routing/heuristic.py` |

---

## 4. Graph Algorithms

### 4.1 Heap-Based Priority Queue

| Field | Detail |
|-------|--------|
| **Source** | Williams, J. W. J. (1964). "Algorithm 232: Heapsort". *Communications of the ACM*, 7(6), 347–348. |
| **Usage** | Priority queue for Dijkstra and A* search. Python's `heapq` module (binary heap). |
| **Implementation** | `src/e3hybrid/routing/dijkstra.py`, `src/e3hybrid/routing/astar.py` |

### 4.2 Adjacency List Graph Representation

| Field | Detail |
|-------|--------|
| **Source** | Standard graph theory representation. No single source. |
| **Usage** | Directed graph storage with insertion-ordered adjacency lists. |
| **Space** | O(V + E) |
| **Implementation** | `src/e3hybrid/network/graph.py` |

---

## 5. Software Engineering References

### 5.1 Protocol-Based Interface Design

| Field | Detail |
|-------|--------|
| **Source** | PEP 544 — Protocols: Structural subtyping (virtual base classes). Python 3.8+. |
| **Usage** | `RoutingAlgorithm`, `SwarmAlgorithm`, `CostProvider`, `Heuristic` Protocols for dependency injection and interface contracts. |
| **Implementation** | Throughout `src/e3hybrid/routing/` and `src/e3hybrid/swarm/` |

### 5.2 Immutable Data Models

| Field | Detail |
|-------|--------|
| **Source** | Python `dataclasses` (PEP 557) with `frozen=True`. |
| **Usage** | All routing, swarm, and shared data structures are frozen dataclasses for deterministic replay and thread safety. |
| **Implementation** | Throughout all modules |

### 5.3 Factory Pattern

| Field | Detail |
|-------|--------|
| **Source** | Gamma, E., Helm, R., Johnson, R., & Vlissides, J. (1994). *Design Patterns: Elements of Reusable Object-Oriented Software*. Addison-Wesley. |
| **Usage** | `SwarmFactory`, `HeuristicFactory`, `RoutingFactory` for configuration-driven object creation. |
| **Implementation** | `src/e3hybrid/swarm/factory.py`, `src/e3hybrid/routing/factory.py`, `src/e3hybrid/routing/heuristic_factory.py` |

### 5.4 Adapter Pattern

| Field | Detail |
|-------|--------|
| **Source** | Gamma et al. (1994). *Design Patterns*. Addison-Wesley. |
| **Usage** | `SwarmToRoutingAdapter` converts `SwarmAlgorithm` to `RoutingAlgorithm` protocol without modifying either interface. |
| **Implementation** | `src/e3hybrid/swarm/adapter.py` |

---

## 6. Statistical Methods

### 6.1 Median Calculation

| Field | Detail |
|-------|--------|
| **Source** | Standard descriptive statistics. |
| **Usage** | Per-iteration median score in `IterationStatistics`. |
| **Formula** | For sorted scores: middle value (odd N) or average of two middle values (even N). |

### 6.2 Standard Deviation

| Field | Detail |
|-------|--------|
| **Source** | Population standard deviation. |
| **Usage** | Score dispersion metric in `IterationStatistics`. |
| **Formula** | `σ = √(Σ(xᵢ − μ)² / N)` |

---

## 7. Reproducibility

### 7.1 Mersenne Twister PRNG

| Field | Detail |
|-------|--------|
| **Source** | Matsumoto, M., & Nishimura, T. (1998). "Mersenne twister: A 623-dimensionally equidistributed uniform pseudo-random number generator". *ACM Transactions on Modeling and Computer Simulation*, 8(1), 3–30. |
| **Usage** | Python's `random.Random` (Mersenne Twister) for all stochastic decisions. Seeded via project's reproducibility framework. |
| **Implementation** | `src/e3hybrid/utils/reproducibility.py`, `src/e3hybrid/swarm/random.py` |

### 7.2 Seeded Random Stream Derivation

| Field | Detail |
|-------|--------|
| **Source** | Project-specific design (DD-046). |
| **Usage** | `SwarmRandom` derives named sub-streams from a base seed using `hash(name) ^ base_seed`. Each stochastic component has its own isolated stream. |
| **Implementation** | `src/e3hybrid/swarm/random.py` |

---

## 8. Framework Structure

### 8.1 Project Layout

| Field | Detail |
|-------|--------|
| **Source** | `pyproject.toml` standards (PEP 517, PEP 518, PEP 621). `src/` layout as recommended by Python packaging documentation. |
| **Usage** | Editable install with `src/e3hybrid/` package root. |

### 8.2 Test Framework

| Field | Detail |
|-------|--------|
| **Source** | pytest (Krekel, H., et al.). pytest documentation and source. |
| **Usage** | All unit tests use pytest with `-v --tb=short` output. Coverage via pytest-cov. |

---

## 9. Complete Source Map

| Algorithm/Model | Source | Year | Status |
|-----------------|--------|------|--------|
| Dijkstra | Dijkstra, E. W. | 1959 | Implemented |
| A* | Hart, Nilsson & Raphael | 1968 | Implemented |
| ACS (ACO variant) | Dorigo & Gambardella | 1997 | Phase 9 Design |
| BCO | Teodorović & Dell'Orco | 2005 | Phase 10 Planned |
| PSO | Kennedy & Eberhart | 1995 | Phase 11 Planned |
| Fiori Energy Model | Fiori, Ahn & Rakha | 2016 | Design complete, deferred |
| Heapsort / Binary Heap | Williams | 1964 | Implemented |
| Mersenne Twister | Matsumoto & Nishimura | 1998 | Implemented |
| Design Patterns | Gamma et al. ("Gang of Four") | 1994 | Throughout |
